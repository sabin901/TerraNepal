"""Allowlisted public snapshots. The complete research archive stays local."""
from __future__ import annotations
import argparse
import contextlib
import copy
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
import urllib.parse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'disaster_lab'))
sys.path.insert(0, str(ROOT / 'disaster_archive'))
from data import timestamp, number, now
from weather import ForecastStore, PLACES, MODELS, normalize

SEED = Path(__file__).with_name('snapshot.json')
PUBLIC_URL = 'https://sabin901.github.io/TerraNepal/data/snapshot.json'
ASSETS = ('index.html', 'app.js', 'style.css', 'logic.js', 'favicon.svg')
ROOT_KEYS = {'schema_version','built_at','archive','rivers','rain_stations','weather','updates','limitations'}
V2_KEYS = ROOT_KEYS | {'earthquakes','discharge','pipeline'}
RIVER_KEYS = {'id','name','basin','observed_at','level','latitude','longitude','conflicting','units'}
RAIN_KEYS = {'id','name','observed_at'}
WEATHER_KEYS = {'place_id','model','fetched_at','sha256','normalized','latest_attempt'}
LIMITATIONS = [
    'Research beta. No flood probabilities, evacuation advice or disaster warnings are generated.',
    'BIPAD station units, vertical datums and threshold mappings need independent confirmation. No warning thresholds are interpreted here.',
    'Weather covers seven city points, not catchment rainfall or all of Nepal. Two model outputs are not a confidence interval.',
    'A successful request does not establish complete coverage or sensor accuracy. Missing observations are never treated as zero.',
    'GitHub schedules can be delayed or skipped. Freshness is recalculated in your browser; publication time is not measurement time.',
    'Historical incident totals describe the local archive at its stated date; scheduled runs do not refresh that full incident archive.',
    'GloFAS discharge is a gridded model, not a gauge reading. The selected river reaches are unverified; ensemble percentiles are not calibrated flood probabilities.',
    'USGS reports past earthquakes in a regional bounding box that includes neighboring countries. This feed cannot predict earthquakes.',
]

def write(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    text=json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n'
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(text);tmp.replace(path)

def require_keys(obj, expected):
    if not isinstance(obj,dict) or set(obj)!=set(expected):raise ValueError('Unexpected public schema keys')

def validate(s):
    require_keys(s,V2_KEYS if s.get('schema_version')==2 else ROOT_KEYS)
    if s['schema_version'] not in (1,2) or timestamp(s['built_at']) is None:raise ValueError('Invalid snapshot version or timestamp')
    require_keys(s['archive'],{'as_of','counts','annual','coverage','quality','audit'})
    if timestamp(s['archive']['as_of']) is None:raise ValueError('Invalid archive timestamp')
    for key,fields in [('rivers',RIVER_KEYS),('rain_stations',RAIN_KEYS)]:
        if not isinstance(s[key],list) or len(s[key])>2000:raise ValueError('Unexpected station count')
        seen=set()
        for r in s[key]:
            require_keys(r,fields)
            if not isinstance(r['id'],str) or r['id'] in seen:raise ValueError('Duplicate or invalid station ID')
            seen.add(r['id'])
            if timestamp(r['observed_at']) is None:raise ValueError('Invalid observation time')
            if key=='rivers':
                if r['level'] is not None and not number(r['level']):raise ValueError('Invalid level')
                if not isinstance(r['conflicting'],bool) or r['units']!='unconfirmed source units':raise ValueError('Invalid observation metadata')
    if not isinstance(s['weather'],list) or len(s['weather'])>14:raise ValueError('Unexpected weather count')
    seen=set()
    for w in s['weather']:
        require_keys(w,WEATHER_KEYS);pair=(w['place_id'],w['model'])
        if pair in seen or w['place_id'] not in {p['id'] for p in PLACES} or w['model'] not in MODELS:raise ValueError('Unexpected weather location/model')
        seen.add(pair)
        if timestamp(w['fetched_at']) is None:raise ValueError('Invalid forecast retrieval time')
        n=w['normalized'];require_keys(n,{'grid_latitude','grid_longitude','elevation','units','points','model_issued_at','time_note'})
        if n['model_issued_at'] is not None:raise ValueError('Issuance not supplied by source')
        if not 72<=len(n['points'])<=200:raise ValueError('Unexpected forecast length')
        for p in n['points']:
            require_keys(p,{'at','epoch','precipitation','temperature_2m','wind_gusts_10m'})
            if timestamp(p['at'])!=p['epoch']:raise ValueError('Invalid forecast timestamp')
        place=next(p for p in PLACES if p['id']==w['place_id'])
        payload={'latitude':n['grid_latitude'],'longitude':n['grid_longitude'],'elevation':n['elevation'],'utc_offset_seconds':0,'hourly_units':n['units'],'hourly':{'time':[p['epoch'] for p in n['points']],**{k:[p[k] for p in n['points']] for k in ('precipitation','temperature_2m','wind_gusts_10m')}}}
        if normalize(payload,place)!=n:raise ValueError('Forecast validation failed')
    # Aggregate fields are generated by SQL and never include incident narratives.
    require_keys(s['archive']['audit'],{'tests_passed','raw_responses_verified','raw_hash_failures','warning_accuracy_validated'})
    for row in s['archive']['annual']:require_keys(row,{'year','hazard','reports'})
    for c in s['archive']['coverage'].values():require_keys(c,{'records_by_utc_day','dates_without_archived_observations'})
    for u in s['updates'].values():
        require_keys(u,{'attempted_at','state','last_success_at','detail'})
        if timestamp(u['attempted_at']) is None:raise ValueError('Invalid attempt time')
    if s['schema_version']==2:
        from sources import validate_extensions
        validate_extensions(s)
    json.dumps(s,allow_nan=False)
    return s

def station_rows(db, at=None):
    at=time.time() if at is None else at
    groups={}
    # Window queries bound CI input size; the local seed query covers all archived stations.
    for r in db.execute('SELECT * FROM river_observations'):
        t=timestamp(r['observed_at'])
        if r['station_id'] is None or t is None or t>at+300:continue
        sid=str(r['station_id']);prev=groups.get(sid)
        row={'id':sid,'name':r['station_name'],'basin':r['basin'],'observed_at':r['observed_at'],
             'level':r['water_level_source_units'] if number(r['water_level_source_units']) else None,
             'latitude':r['latitude'],'longitude':r['longitude'],'conflicting':False,'units':'unconfirmed source units'}
        if prev is None or t>timestamp(prev['observed_at']):groups[sid]=row
        elif t==timestamp(prev['observed_at']) and (prev['conflicting'] or prev['level']!=row['level']):prev.update(level=None,conflicting=True)
    rain={}
    for r in db.execute("SELECT json_extract(payload,'$.station') id,json_extract(payload,'$.title') name,json_extract(payload,'$.measuredOn') observed_at FROM current_payloads WHERE collection='bipad:rain'"):
        t=timestamp(r['observed_at'])
        if r['id'] is None or t is None or t>at+300:continue
        sid=str(r['id'])
        if sid not in rain or t>timestamp(rain[sid]['observed_at']):rain[sid]={'id':sid,'name':r['name'],'observed_at':r['observed_at']}
    return sorted(groups.values(),key=lambda s:s['id']),sorted(rain.values(),key=lambda s:s['id'])

def weather_rows(store):
    rows=[]
    with contextlib.closing(store.db()) as db:
        for p in PLACES:
            for model in MODELS:
                good=db.execute("SELECT * FROM weather_fetches WHERE place_id=? AND model=? AND status='ok' ORDER BY id DESC LIMIT 1",(p['id'],model)).fetchone()
                last=db.execute('SELECT status,fetched_at FROM weather_fetches WHERE place_id=? AND model=? ORDER BY id DESC LIMIT 1',(p['id'],model)).fetchone()
                if not good:continue
                raw=(store.raw/good['raw_file']).read_bytes();n=normalize(json.loads(raw),p)
                if hashlib.sha256(raw).hexdigest()!=good['sha256'] or n!=json.loads(good['normalized']):raise ValueError('Weather integrity failure')
                rows.append({'place_id':p['id'],'model':model,'fetched_at':good['fetched_at'],'sha256':good['sha256'],'normalized':n,'latest_attempt':dict(last)})
    return rows

def export_local(output):
    path=ROOT/'disaster_archive/data/archive.sqlite';db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    try:
        rivers,rain=station_rows(db)
        counts=dict(db.execute('SELECT collection,count(*) FROM records GROUP BY collection'))
        annual=[dict(r) for r in db.execute("SELECT substr(local_event_date,1,4) year,hazard,count(*) reports FROM incident_current WHERE hazard IN ('Flood','Landslide') GROUP BY year,hazard ORDER BY year,hazard")]
        stamp=now();quality=json.loads((ROOT/'disaster_archive/exports/quality.json').read_text())['checks']
        recovery=json.loads((ROOT/'disaster_archive/exports/maintenance-recovery-2026-11-03.json').read_text())['audit']
        updates={}
        for feed in ('river','rain'):
            r=db.execute("SELECT * FROM collection_runs WHERE collection=? AND query_end IS NOT NULL ORDER BY query_end DESC LIMIT 1",('bipad:'+feed,)).fetchone()
            updates[feed]={'attempted_at':r['finished_at'],'state':r['status'],'last_success_at':r['finished_at'],'detail':'Historical and recent archive; daily gaps are listed below.'}
        updates['weather']={'attempted_at':stamp,'state':'checked','last_success_at':None,'detail':'See per-model retrieval timestamps.'}
        s={'schema_version':1,'built_at':stamp,'archive':{'as_of':stamp,'counts':counts,'annual':annual,'coverage':recovery['coverage'],'quality':quality,'audit':{'tests_passed':94,'raw_responses_verified':recovery['raw_responses_checked'],'raw_hash_failures':recovery['raw_hash_failures'],'warning_accuracy_validated':False}},'rivers':rivers,'rain_stations':rain,'weather':weather_rows(ForecastStore()),'updates':updates,'limitations':LIMITATIONS}
        write(output,validate(s));print(f'Public seed: {len(rivers)} river stations, {len(rain)} rain station timestamps, {len(s["weather"])} model snapshots')
    finally:db.close()

def merge_stations(previous, current):
    merged={s['id']:copy.deepcopy(s) for s in previous}
    for s in current:
        p=merged.get(s['id'])
        if p is None or timestamp(s['observed_at'])>timestamp(p['observed_at']):merged[s['id']]=s
        elif timestamp(s['observed_at'])==timestamp(p['observed_at']) and 'level' in s and (p['level']!=s['level'] or p['conflicting'] or s['conflicting']):
            merged[s['id']].update(level=None,conflicting=True)
    return sorted(merged.values(),key=lambda s:s['id'])

def previous_snapshot():
    seed=validate(json.loads(SEED.read_text()))
    try:
        # A fixed public URL. No arbitrary remote file, credentials or database restore.
        response=subprocess.run(['curl','--fail','--silent','--show-error','--proto','=https',
                                 '--connect-timeout','10','--max-time','20','--max-filesize','2000000',PUBLIC_URL],
                                capture_output=True,timeout=25,check=True)
        raw=response.stdout
        if len(raw)>2_000_000:raise ValueError('Oversized previous snapshot')
        remote=validate(json.loads(raw))
        if timestamp(remote['built_at'])<=time.time()+300 and timestamp(remote['built_at'])>timestamp(seed['built_at']):
            # A newer hourly build must not hide a separately reviewed archive update.
            if timestamp(seed['archive']['as_of'])>timestamp(remote['archive']['as_of']):remote['archive']=seed['archive']
            return remote
    except Exception as exc:
        print('Previous public snapshot unavailable or invalid; using dated seed:',type(exc).__name__)
    return seed

def refresh(output, state_root=None):
    from collector import collect
    return collect(output,Path(state_root) if state_root else ROOT/'runtime/public-state')

def build(snapshot,output):
    s=validate(json.loads(Path(snapshot).read_text()));out=Path(output)
    if out.exists() and any(out.iterdir()):raise ValueError('Build destination must be empty')
    out.mkdir(parents=True,exist_ok=True)
    for name in ASSETS:shutil.copyfile(Path(__file__).with_name('static')/name,out/name)
    write(out/'data/snapshot.json',s);(out/'.nojekyll').touch()
    print('Built allowlisted Pages artifact:',out)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['export-local','refresh','build']);parser.add_argument('--snapshot',default=str(SEED));parser.add_argument('--state-root');parser.add_argument('--output',required=True);args=parser.parse_args()
    if args.command=='export-local':export_local(args.output)
    elif args.command=='refresh':refresh(args.output,args.state_root)
    else:build(args.snapshot,args.output)
