"""Retain attributable public weather response bytes and identifiable research runs.

Only credential-free Open-Meteo weather endpoints are allowed. BIPAD raw records
are deliberately outside this publication contract. No forecast accuracy claim.
"""
from __future__ import annotations
import argparse
import base64
import contextlib
import concurrent.futures
import datetime as dt
import gzip
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import sys
import time
from urllib.parse import urlparse,parse_qs

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'disaster_lab'))
import forecast_runs
from weather import PLACES,MODELS

MAX_RAW=2_000_000
KEYS={'schema_version','source','place_id','model','initialized_at','fetched_at','url','status','error','response_sha256','response_base64','attribution'}
ATTRIBUTION='Open-Meteo / ECMWF / NOAA; CC BY 4.0. Noncommercial hosted API access. Research evidence, not verified accuracy.'

def stamp(value):
    parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('Evidence timestamps must be timezone-aware')
    return parsed

def validate(envelope):
    if not isinstance(envelope,dict) or set(envelope)!=KEYS or envelope['schema_version']!=1:raise ValueError('Invalid weather evidence envelope')
    if envelope['source'] not in ('rolling_weather','original_run'):raise ValueError('Unsupported evidence source')
    place=next((p for p in PLACES if p['id']==envelope['place_id']),None)
    if not place or envelope['model'] not in MODELS:raise ValueError('Unknown evidence model/location')
    url=urlparse(envelope['url']);query=parse_qs(url.query)
    host='single-runs-api.open-meteo.com' if envelope['source']=='original_run' else 'api.open-meteo.com'
    allowed={'latitude','longitude','models','hourly','forecast_days','forecast_hours','timeformat','timezone','wind_speed_unit','precipitation_unit','run'}
    if url.scheme!='https' or url.netloc!=host or url.path!='/v1/forecast' or url.fragment or set(query)-allowed or any(len(v)!=1 for v in query.values()):raise ValueError('Unapproved weather evidence URL')
    if query.get('models')!=[envelope['model']] or query.get('latitude')!=[str(place['latitude'])] or query.get('longitude')!=[str(place['longitude'])]:raise ValueError('Evidence URL/model/location mismatch')
    fetched=stamp(envelope['fetched_at'])
    if envelope['source']=='original_run':
        initialized=forecast_runs.run_time(envelope['initialized_at'])
        if initialized>fetched or query.get('run')!=[initialized.strftime('%Y-%m-%dT%H:%M')]:raise ValueError('Original-run identity mismatch')
    elif envelope['initialized_at'] is not None:raise ValueError('Rolling response cannot invent initialization')
    if envelope['status'] not in ('ok','error') or (envelope['error'] is not None and not isinstance(envelope['error'],str)):raise ValueError('Invalid evidence result')
    if envelope['attribution']!=ATTRIBUTION:raise ValueError('Missing attribution')
    raw=base64.b64decode(envelope['response_base64'],validate=True)
    if len(raw)>MAX_RAW or hashlib.sha256(raw).hexdigest()!=envelope['response_sha256']:raise ValueError('Weather response integrity failure')
    return raw

def retain(root,source,row,raw):
    envelope=dict(schema_version=1,source=source,place_id=row['place_id'],model=row['model'],initialized_at=row.get('requested_run'),fetched_at=row['fetched_at'],url=row['url'],status=row['status'],error=row.get('error'),response_sha256=row['sha256'],response_base64=base64.b64encode(raw).decode(),attribution=ATTRIBUTION)
    validate(envelope)
    encoded=json.dumps(envelope,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    digest=hashlib.sha256(encoded).hexdigest();path=Path(root)/'evidence'/'weather'/row['fetched_at'][:10]/(digest+'.json.gz')
    path.parent.mkdir(parents=True,exist_ok=True);blob=gzip.compress(encoded,mtime=0)
    if path.exists() and path.read_bytes()!=blob:raise ValueError('Immutable weather evidence collision')
    path.write_bytes(blob)
    return path.relative_to(root).as_posix()

def collect(root,at=None,rolling_only=False):
    root=Path(root);at=time.time() if at is None else at
    state_path=root/'weather-evidence-state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else {'schema_version':1,'runs':{}}
    validate_state(state)
    report={'schema_version':1,'retained_rolling':0,'retained_original':0,'original_ok':0,'original_errors':0,'skipped':0,'coverage_note':'Best-effort one mature initialization per executed job; missed runs are not backfilled or claimed complete.'}
    dbpath=root/'raw-local'/'weather'/'forecasts.sqlite'
    if dbpath.exists():
        with contextlib.closing(sqlite3.connect(dbpath)) as db:
            db.row_factory=sqlite3.Row
            for r in db.execute('SELECT * FROM weather_fetches ORDER BY id'):
                r=dict(r)
                if not r['sha256'] or not r['raw_file']:continue
                path=dbpath.parent/'weather_raw'/(r['sha256']+'.json')
                retain(root,'rolling_weather',r,path.read_bytes());report['retained_rolling']+=1
    if rolling_only:
        (root/'weather-evidence-report.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
    # Conservative 8h publication lag; request initialization, never infer availability.
    init=dt.datetime.fromtimestamp((int(at-8*3600)//21600)*21600,dt.timezone.utc).isoformat()
    research=root/'raw-local'/'original-runs'
    jobs=[]
    for place in PLACES:
        for model in MODELS:
            key=place['id']+':'+model;prior=state['runs'].get(key)
            if prior and prior['initialized_at']==init and (prior['status']=='ok' or at-stamp(prior['fetched_at']).timestamp()<3600):
                report['skipped']+=1;continue
            jobs.append((place['id'],model))
    report['collection_errors']=[]
    def checkpoint():
        validate_state(state)
        temporary=state_path.with_suffix('.tmp');temporary.write_text(json.dumps(state,sort_keys=True)+'\n');temporary.replace(state_path)
        (root/'weather-evidence-report.json').write_text(json.dumps(report,indent=2)+'\n')
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        pending={pool.submit(forecast_runs.collect,research,place_id,model,init):(place_id,model) for place_id,model in jobs}
        for future in concurrent.futures.as_completed(pending):
            place_id,model=pending[future];key=place_id+':'+model
            try:result=future.result()
            except Exception as exc:
                report['collection_errors'].append({'place_id':place_id,'model':model,'error':str(exc)[:300]})
                print('::warning::Original-run acquisition failed for '+key)
                checkpoint();continue
            with contextlib.closing(sqlite3.connect(research/'runs.sqlite')) as db:
                db.row_factory=sqlite3.Row
                r=dict(db.execute('SELECT * FROM fetches WHERE place_id=? AND model=? AND requested_run=? AND sha256=? ORDER BY id DESC LIMIT 1',(place_id,model,init,result['sha256'])).fetchone())
            path=retain(root,'original_run',r,(research/'raw'/(r['sha256']+'.json')).read_bytes())
            state['runs'][key]={'initialized_at':r['requested_run'],'fetched_at':r['fetched_at'],'status':r['status'],'evidence_path':path}
            report['retained_original']+=1;report['original_ok' if result['status']=='ok' else 'original_errors']+=1
            checkpoint()
    validate_state(state)
    temporary=state_path.with_suffix('.tmp');temporary.write_text(json.dumps(state,sort_keys=True)+'\n');temporary.replace(state_path)
    (root/'weather-evidence-report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def validate_state(state):
    if not isinstance(state,dict) or set(state)!={'schema_version','runs'} or state['schema_version']!=1 or not isinstance(state['runs'],dict):raise ValueError('Invalid weather evidence state')
    keys={p['id']+':'+m for p in PLACES for m in MODELS}
    for key,row in state['runs'].items():
        if key not in keys or not isinstance(row,dict) or set(row)!={'initialized_at','fetched_at','status','evidence_path'}:raise ValueError('Invalid research run state')
        if forecast_runs.run_time(row['initialized_at'])>stamp(row['fetched_at']) or row['status'] not in ('ok','error') or not re.fullmatch(r'evidence/weather/\d{4}-\d{2}-\d{2}/[0-9a-f]{64}\.json\.gz',row['evidence_path']):raise ValueError('Invalid research run receipt')
    return state

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,default=Path('runtime/public-state'));parser.add_argument('--rolling-only',action='store_true');args=parser.parse_args()
    print(json.dumps(collect(args.root,rolling_only=args.rolling_only),indent=2))
