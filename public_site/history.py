"""Compact, append-only public research history; raw local archive is never copied."""
from __future__ import annotations
import datetime as dt
import gzip
import hashlib
import json
import re
from pathlib import Path
import uuid

# Leave headroom below data_branch.MAX_FILE for decompression verification.
MAX_RUN_PART_BYTES=16*1024*1024

def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()

def digest(value):return hashlib.sha256(canonical(value)).hexdigest()

def fresh_state():
    return {'version':1,'watermarks':{},'gaps':[],'index':{},'runs':0,'history_started_at':None,'revisions':0}

def load_state(root):
    path=Path(root)/'state.json'
    if not path.exists():return fresh_state()
    state=json.loads(path.read_text())
    return validate_state(state)

def validate_state(state):
    from data import timestamp
    if set(state)!=set(fresh_state()) or state['version']!=1 or not isinstance(state['index'],dict):raise ValueError('Invalid durable state; refusing to reset history')
    if not isinstance(state['watermarks'],dict) or set(state['watermarks'])-{'river','rain'} or any(timestamp(t) is None for t in state['watermarks'].values()):raise ValueError('Invalid collection watermarks')
    if any(not isinstance(state[k],int) or isinstance(state[k],bool) or state[k]<0 for k in ('runs','revisions')):raise ValueError('Invalid history counters')
    if state['history_started_at'] is not None and timestamp(state['history_started_at']) is None:raise ValueError('Invalid history start')
    for key,value in state['index'].items():
        if not re.fullmatch(r'bipad:(river|rain):[0-9]+',key) or not isinstance(value,dict) or set(value)!={'sha256','seen_at'} or not re.fullmatch('[0-9a-f]{64}',value['sha256']) or timestamp(value['seen_at']) is None:raise ValueError('Invalid observation index')
    for gap in state['gaps']:
        if set(gap)!={'source','start','end','reason'} or gap['source'] not in ('river','rain') or any(timestamp(gap[k]) is None for k in ('start','end')):raise ValueError('Invalid catch-up gap')
    return state

def query_window(state, feed, end):
    end=dt.datetime.fromisoformat(end)
    prior=state['watermarks'].get(feed)
    desired=dt.datetime.fromisoformat(prior)-dt.timedelta(hours=3) if prior else end-dt.timedelta(hours=3)
    if desired>end:raise ValueError('Future collection watermark')
    floor=end-dt.timedelta(days=7)
    if desired<floor:
        gap={'source':feed,'start':desired.isoformat(),'end':floor.isoformat(),'reason':'Outage exceeded seven-day automatic catch-up; older interval requires explicit backfill.'}
        if gap not in state['gaps']:state['gaps'].append(gap)
    return max(desired,floor).isoformat(),end.isoformat()

def observation_versions(db, run_id):
    """Only selected station facts and source provenance; no descriptions/contacts."""
    sql='''SELECT v.collection,v.native_id,v.payload,v.sha256 source_record_sha256,
                  f.sha256 response_sha256,f.fetched_at
           FROM current_payloads v JOIN fetches f ON f.id=v.latest_fetch_id
           WHERE v.collection IN ('bipad:river','bipad:rain') AND f.run_id=? ORDER BY v.collection,v.native_id'''
    for r in db.execute(sql,(run_id,)):
        p=json.loads(r['payload']);river=r['collection']=='bipad:river'
        from data import timestamp
        from sources import finite
        issues=[]
        def numeric(value):
            if value is None or finite(value):return value
            issues.append('invalid_numeric_value');return None
        observed=p.get('waterLevelOn' if river else 'measuredOn')
        if timestamp(observed) is None:observed=None;issues.append('invalid_observation_time')
        averages=p.get('averages',[])
        if not isinstance(averages,list):averages=[];issues.append('invalid_rainfall_array')
        station=p.get('station')
        if not isinstance(station,(int,str)) or isinstance(station,bool):station=None;issues.append('invalid_station_id')
        row={'source':r['collection'],'id':r['native_id'],'station_id':str(station) if station is not None else None,
             'observed_at':observed,
             'units':'unconfirmed source units' if river else 'unconfirmed source units and accumulation',
             'values':{'level':numeric(p.get('waterLevel'))} if river else {'averages':[{'interval':numeric(a.get('interval')),'value':numeric(a.get('value'))} for a in averages if isinstance(a,dict)]}}
        if issues:row['quality_issues']=issues
        yield row,{'response_sha256':r['response_sha256'],'source_record_sha256':r['source_record_sha256'],'fetched_at':r['fetched_at']}

def record_versions(state, rows, at):
    changes=[]
    for row,provenance in rows:
        key=row['source']+':'+row['id'];sha=digest(row);old=state['index'].get(key)
        if not old or old['sha256']!=sha:
            changes.append({'record':row,'sha256':sha,'previous_sha256':old['sha256'] if old else None,'provenance':provenance})
            state['revisions']+=bool(old)
        state['index'][key]={'sha256':sha,'seen_at':at}
    # Index eviction affects deduplication only, never deletes immutable history.
    floor=(dt.datetime.fromisoformat(at)-dt.timedelta(days=8)).isoformat()
    state['index']={k:v for k,v in state['index'].items() if v['seen_at']>=floor}
    return changes

def save_run(root, state, snapshot, changes, fetches):
    root=Path(root);at=snapshot['built_at'];state['runs']+=1
    state['history_started_at']=state['history_started_at'] or at
    body={'schema_version':1,'recorded_at':at,'snapshot':snapshot,'observation_changes':[],'fetches':fetches}
    base_size=len(canonical(body))
    if base_size>MAX_RUN_PART_BYTES:raise ValueError('Snapshot and fetch receipts exceed history part budget')
    parts=[];part=[];size=base_size
    for change in changes:
        change_size=len(canonical(change))
        if base_size+change_size>MAX_RUN_PART_BYTES:raise ValueError('One observation version exceeds history part budget')
        extra=change_size+bool(part)  # comma between array elements
        if size+extra>MAX_RUN_PART_BYTES:
            parts.append(part);part=[];size=base_size;extra=change_size
        part.append(change);size+=extra
    if part or not parts:parts.append(part)
    compressed_bytes=0
    for part in parts:
        raw=canonical({**body,'observation_changes':part})
        if len(raw)>MAX_RUN_PART_BYTES:raise ValueError('History part sizing mismatch')
        sha=hashlib.sha256(raw).hexdigest()
        target=root/'history'/at[:10]/(sha+'.json.gz');target.parent.mkdir(parents=True,exist_ok=True)
        blob=gzip.compress(raw,mtime=0)
        if target.exists() and target.read_bytes()!=blob:raise ValueError('Immutable history collision')
        target.write_bytes(blob);compressed_bytes+=len(blob)
    for name,value in [('latest.json',snapshot),('state.json',state)]:
        tmp=root/(name+'.'+uuid.uuid4().hex+'.tmp');tmp.write_bytes(canonical(value)+b'\n');tmp.replace(root/name)
    return {'new_observation_versions':len(changes),'compressed_run_bytes':compressed_bytes,'history_files_written':len(parts),'run_number':state['runs']}
