"""Scheduled backend for Pages: collect, validate, retain history, then publish."""
from __future__ import annotations
import concurrent.futures
import contextlib
import copy
import datetime as dt
import json
import os
from pathlib import Path
import time

import pipeline as p
import history
import sources

def due(item, seconds, at):
    stamp=p.timestamp(item.get('fetched_at')) if item else None
    return stamp is None or stamp>at or at-stamp>=seconds

def update(snapshot, name, state, detail, success=False):
    previous=snapshot['updates'].get(name,{})
    snapshot['updates'][name]={'attempted_at':p.now(),'state':state,
        'last_success_at':p.now() if success else previous.get('last_success_at'),'detail':detail}

def collect_hydrology(a, snapshot, state, stamp):
    for feed,field in [('river','water_level_on'),('rain','measured_on')]:
        start,end=history.query_window(state,feed,stamp)
        # Once per UTC day, revisit a full day to catch late records/corrections.
        prior=state['watermarks'].get(feed)
        if prior and prior[:10]!=stamp[:10]:
            start=min(start,(dt.datetime.fromisoformat(stamp)-dt.timedelta(days=1)).isoformat())
        for attempt in range(2):
            status=a.bipad(feed,{field+'__gt':start,field+'__lt':end},max_pages=160,window=(start,end))
            if status!='failed' or attempt:break
            failure=a.db.execute('SELECT http_status FROM fetches WHERE run_id=? ORDER BY id DESC LIMIT 1',(a.run_id,)).fetchone()
            if not failure or failure[0] not in (0,429,500,502,503,504):break
            time.sleep(2)
        job=a.db.execute('SELECT * FROM collection_runs WHERE run_id=? AND collection=? ORDER BY id DESC LIMIT 1',(a.run_id,'bipad:'+feed)).fetchone()
        if status=='traversed':state['watermarks'][feed]=end
        update(snapshot,feed,status,f'{job["rows_seen"]} rows traversed in {start} to {end}; {job["pages"]} pages. {job["note"] or ""} Query success does not establish sensor coverage.',status=='traversed')
    rivers,rain=p.station_rows(a.db)
    snapshot['rivers']=p.merge_stations(snapshot['rivers'],rivers)
    snapshot['rain_stations']=p.merge_stations(snapshot['rain_stations'],rain)

def collect_weather(snapshot, runtime, at):
    store=p.ForecastStore(runtime/'weather')
    prior={(w['place_id'],w['model']):w for w in snapshot['weather']}
    jobs=[(place,model) for place in p.PLACES for model in p.MODELS if due(prior.get((place['id'],model)),3600,at)]
    def fetch(place,model):
        result=store.fetch(place,model,force=True)
        if result['status']=='error' and (result.get('error') or '').startswith('Fetch failed:'):
            time.sleep(2);result=store.fetch(place,model,force=True)
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda args:fetch(*args),jobs))
    for w in p.weather_rows(store):
        key=(w['place_id'],w['model'])
        if key not in prior or p.timestamp(w['fetched_at'])>=p.timestamp(prior[key]['fetched_at']):prior[key]=w
    for r in results:
        if (r['place'],r['model']) in prior:prior[(r['place'],r['model'])]['latest_attempt']={'status':r['status'],'fetched_at':p.now()}
    snapshot['weather']=list(prior.values())
    if results:
        good=sum(r['status']=='ok' for r in results)
        update(snapshot,'weather','completed' if good==len(results) else 'partial',f'{good}/{len(results)} due requests succeeded; {14-len(results)} snapshots reused within hourly cadence. Original retrieval times retained.',good==len(results))
    with contextlib.closing(store.db()) as db:
        return [dict(r) for r in db.execute('SELECT place_id,model,url,fetched_at,status,sha256,error FROM weather_fetches WHERE fetched_at>=?',(sources.iso(at),))]

def collect_extra(a, snapshot, at):
    if due(snapshot.get('earthquakes'),3600,at):
        try:
            raw,fid,stamp=sources.fetch_json(a,'usgs',sources.USGS_URL)
            normalized=sources.normalize_quakes(raw,time.time())
            sha=a.db.execute('SELECT sha256 FROM fetches WHERE id=?',(fid,)).fetchone()[0]
            snapshot['earthquakes']={'fetched_at':stamp,'sha256':sha,'url':sources.USGS_URL,'normalized':normalized}
            update(snapshot,'earthquakes','completed',f'{len(normalized["events"])} earthquake records in regional box in the USGS past-week feed. An empty result is not proof of no earthquakes.',True)
        except (RuntimeError,ValueError,TypeError,KeyError) as exc:
            update(snapshot,'earthquakes','failed',f'{type(exc).__name__}: {str(exc)[:200]}. Previous successful feed retained.')
    previous={f['normalized']['point_id']:f for f in snapshot.get('discharge',[])}
    jobs=[point for point in sources.FLOOD_POINTS if due(previous.get(point['id']),6*3600,at)]
    good=0;errors=[]
    for point in jobs:
        try:
            url=sources.flood_url(point);raw,fid,stamp=sources.fetch_json(a,'open_meteo_flood',url)
            normalized=sources.normalize_flood(raw,point,time.time())
            sha=a.db.execute('SELECT sha256 FROM fetches WHERE id=?',(fid,)).fetchone()[0]
            previous[point['id']]={'fetched_at':stamp,'sha256':sha,'url':url,'normalized':normalized};good+=1
        except (RuntimeError,ValueError,TypeError,KeyError) as exc:errors.append(point['id']+': '+str(exc)[:160])
    snapshot['discharge']=list(previous.values())
    if jobs:update(snapshot,'discharge','completed' if good==len(jobs) else 'partial',f'{good}/{len(jobs)} due point requests succeeded. Six-hour retrieval cadence; provider forecast updates daily. River reach mapping unverified. '+'; '.join(errors),good==len(jobs))

def quality(snapshot, at):
    warnings=[]
    q={}
    for source,field in [('river','rivers'),('rain','rain_stations')]:
        rows=snapshot[field];recent=sum(p.timestamp(r['observed_at']) is not None and 0<=at-p.timestamp(r['observed_at'])<=7200 for r in rows)
        q[source+'_recent']=recent;q[source+'_total']=len(rows)
        if not rows:warnings.append(source+': no retained station observations are available.')
        elif recent<len(rows)*.5:warnings.append(f'{source}: fewer than half of retained stations have an observation within two hours; station operation status is unverified.')
    for name,u in snapshot['updates'].items():
        if u['state'] in ('failed','partial','running'):warnings.append(name+': '+u['state']+' latest collection')
    q['warnings']=warnings
    return q

def collect(output, state_root):
    from archive import Archive
    state_root=Path(state_root);state_root.mkdir(parents=True,exist_ok=True)
    # Local lock also protects manual overlapping refreshes. CI uses workflow concurrency.
    import fcntl
    with (state_root/'.refresh.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        return _collect(output,state_root)

def _collect(output,state_root):
    from archive import Archive
    state=history.load_state(state_root);latest=state_root/'latest.json'
    if state['runs'] and not latest.exists():raise ValueError('Durable state has no matching latest snapshot')
    snapshot=copy.deepcopy(p.validate(json.loads(latest.read_text())) if latest.exists() else p.previous_snapshot())
    if state['runs'] and snapshot.get('pipeline',{}).get('history_runs')!=state['runs']:raise ValueError('Durable state and latest snapshot disagree; refusing to reset')
    seed=p.validate(json.loads(p.SEED.read_text()))
    if p.timestamp(seed['archive']['as_of'])>p.timestamp(snapshot['archive']['as_of']):snapshot['archive']=seed['archive']
    snapshot.update(schema_version=2)
    snapshot.setdefault('earthquakes',None);snapshot.setdefault('discharge',[])
    stamp=p.now();at=time.time()
    runtime=state_root/'raw-local';a=Archive(runtime/'archive');a.start('scheduled_public_collection')
    try:
        collect_hydrology(a,snapshot,state,stamp)
        weather_fetches=collect_weather(snapshot,runtime,at)
        collect_extra(a,snapshot,at)
        changes=history.record_versions(state,history.observation_versions(a.db,a.run_id),stamp)
        fetches=[dict(r) for r in a.db.execute('SELECT source,url,fetched_at,http_status,sha256,byte_count,error FROM fetches WHERE run_id=? ORDER BY id',(a.run_id,))]
        fetches.extend({'source':'open_meteo_weather',**r} for r in weather_fetches)
        q=quality(snapshot,time.time())
        invalid=sum(bool(c['record'].get('quality_issues')) for c in changes)
        if invalid:q['warnings'].append(f'{invalid} selected observation versions contain invalid fields; those fields are marked missing with quality issues, and source response hashes are retained.')
        if state['gaps']:q['warnings'].append(f'{len(state["gaps"])} catch-up intervals remain unresolved; see recorded coverage gaps.')
        snapshot['built_at']=p.now();snapshot['limitations']=p.LIMITATIONS
        parent=(state_root/'.parent').read_text().strip() if (state_root/'.parent').exists() else ''
        snapshot['pipeline']={'schedule_minutes':30,'history_started_at':state['history_started_at'] or snapshot['built_at'],
            'history_runs':state['runs']+1,'revisions':state['revisions'],'catchup_gaps':state['gaps'],
            'quality':q,'history_branch':'codex/data-snapshots','previous_revision':parent or None}
        p.validate(snapshot)
        report=history.save_run(state_root,state,snapshot,changes,fetches)
        p.write(output,snapshot)
        a.db.execute('UPDATE runs SET status=?,finished_at=? WHERE id=?',('partial' if q['warnings'] else 'completed',p.now(),a.run_id));a.db.commit()
        for warning in q['warnings']:print('::warning::'+warning)
        report.update(updates=snapshot['updates'],quality=q)
        p.write(state_root/'run-report.json',report)
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a') as f:
                f.write('## Public data refresh\n\n'+f'History run {state["runs"]}; {len(changes)} new selected observation versions.\n\n')
                for name,u in snapshot['updates'].items():f.write(f'- **{name}**: {u["state"]}. {u["detail"]}\n')
                for warning in q['warnings']:f.write('\n- Quality concern: '+warning)
        print(json.dumps(report,indent=2))
        return report
    finally:a.db.close()
