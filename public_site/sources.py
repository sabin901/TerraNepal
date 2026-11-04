"""Public, keyless sources. Measurements, catalog events and models stay separate."""
from __future__ import annotations
import datetime as dt
import json
import math
import time
import urllib.parse

USGS_URL = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson'
BBOX = {'south':26, 'north':31, 'west':80, 'east':89}
FLOOD_POINTS = [
    {'id':'karnali','name':'Karnali study point','latitude':28.65305556,'longitude':81.28694444},
    {'id':'narayani','name':'Narayani study point','latitude':27.71,'longitude':84.43},
    {'id':'koshi','name':'Koshi study point','latitude':26.855192,'longitude':87.152283},
    {'id':'west_rapti','name':'West Rapti study point','latitude':28.0075,'longitude':82.093889},
    {'id':'babai','name':'Babai study point','latitude':28.3565601,'longitude':81.7135456},
    {'id':'kankai','name':'Kankai study point','latitude':26.833324,'longitude':87.89934},
]
DISCHARGE_FIELDS = ('river_discharge_mean','river_discharge_p25','river_discharge_p75')

def finite(v):
    return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)

def iso(epoch):
    return dt.datetime.fromtimestamp(epoch,dt.timezone.utc).isoformat(timespec='seconds')

def fetch_json(archive, source, url):
    """Two attempts only for transport/429/5xx failures; both raw bodies are retained."""
    for attempt in range(2):
        try:
            raw,fetch_id,stamp=archive.fetch(source,url)
            if len(raw)>5_000_000:raise ValueError('Response exceeds source contract')
            return json.loads(raw),fetch_id,stamp
        except RuntimeError:
            last=archive.db.execute('SELECT http_status FROM fetches WHERE run_id=? ORDER BY id DESC LIMIT 1',(archive.run_id,)).fetchone()
            if attempt or not last or last[0] not in (0,429,500,502,503,504):raise
            time.sleep(2)

def normalize_quakes(payload, at):
    if not isinstance(payload,dict) or payload.get('type')!='FeatureCollection':raise ValueError('Invalid USGS feature collection')
    meta=payload.get('metadata',{});features=payload.get('features')
    if not isinstance(meta,dict):raise ValueError('Invalid USGS metadata')
    generated=meta.get('generated')
    if not finite(generated) or not at-86400<=generated/1000<=at+300:raise ValueError('USGS feed generation time is stale or future')
    if meta.get('status')!=200 or not isinstance(features,list) or meta.get('count')!=len(features):raise ValueError('USGS count/status mismatch')
    result=[];seen=set()
    for f in features:
        if not isinstance(f,dict):raise ValueError('Invalid USGS feature')
        key=f.get('id');p=f.get('properties',{});g=f.get('geometry',{})
        if not isinstance(p,dict) or not isinstance(g,dict):raise ValueError('Invalid USGS properties or geometry')
        c=g.get('coordinates',[])
        if not isinstance(key,str) or not key or key in seen:raise ValueError('Invalid or duplicate USGS ID')
        seen.add(key)
        if g.get('type')!='Point' or not isinstance(c,list) or len(c)!=3 or not all(finite(x) for x in c) or not -180<=c[0]<=180 or not -90<=c[1]<=90:raise ValueError('Invalid USGS coordinates')
        t,updated=p.get('time'),p.get('updated');mag=p.get('mag')
        if not finite(t) or not at-9*86400<=t/1000<=at+300 or not finite(updated) or not t<=updated<=max(at+300,generated/1000)*1000:raise ValueError('Invalid USGS event time')
        if mag is not None and (not finite(mag) or not -5<=mag<=12):raise ValueError('Invalid earthquake magnitude')
        if p.get('type')!='earthquake':continue
        if BBOX['west']<=c[0]<=BBOX['east'] and BBOX['south']<=c[1]<=BBOX['north']:
            result.append({'id':key,'occurred_at':iso(t/1000),'source_updated_at':iso(updated/1000),
                           'magnitude':mag,'magnitude_type':p.get('magType'),'longitude':c[0],'latitude':c[1],
                           'depth_km':c[2],'review_status':p.get('status')})
    return {'generated_at':iso(generated/1000),'region':BBOX,'events':sorted(result,key=lambda r:r['occurred_at'],reverse=True),
            'scope':'USGS past-week earthquake feed, 26–31°N / 80–89°E; includes neighboring countries. Catalog coverage is not complete.'}

def flood_url(point):
    # The documented default is GloFAS v4 seamless. Record this selection; do not
    # pretend the response supplies an exact model run or a verified river reach.
    return 'https://flood-api.open-meteo.com/v1/flood?'+urllib.parse.urlencode({
        'latitude':point['latitude'],'longitude':point['longitude'],'daily':','.join(DISCHARGE_FIELDS),
        'forecast_days':7,'timeformat':'unixtime','timezone':'GMT'})

def normalize_flood(payload, point, at):
    if not isinstance(payload,dict) or payload.get('error') or payload.get('utc_offset_seconds')!=0:raise ValueError('Invalid discharge response or timezone')
    lat,lon=payload.get('latitude'),payload.get('longitude')
    if not finite(lat) or not finite(lon) or abs(lat-point['latitude'])>.15 or abs(lon-point['longitude'])>.15:raise ValueError('Discharge grid is too far from requested point')
    units=payload.get('daily_units',{})
    if not isinstance(units,dict) or not isinstance(payload.get('daily'),dict):raise ValueError('Invalid discharge arrays or units')
    if units.get('time')!='unixtime' or any(units.get(k)!='m³/s' for k in DISCHARGE_FIELDS):raise ValueError('Unexpected discharge units')
    daily=payload.get('daily',{});times=daily.get('time',[])
    if not isinstance(times,list) or len(times)!=7 or any(not finite(t) or t%86400 for t in times) or any(b-a!=86400 for a,b in zip(times,times[1:])):raise ValueError('Expected seven consecutive UTC model days')
    if not at-86400<=times[0]<=at+86400:raise ValueError('Discharge forecast starts outside current model day')
    if any(not isinstance(daily.get(k),list) or len(daily[k])!=7 for k in DISCHARGE_FIELDS):raise ValueError('Incomplete discharge arrays')
    days=[]
    for i,t in enumerate(times):
        values={k:daily[k][i] for k in DISCHARGE_FIELDS}
        if any(v is not None and (not finite(v) or v<0) for v in values.values()):raise ValueError('Invalid discharge value')
        lo,hi=values['river_discharge_p25'],values['river_discharge_p75']
        if lo is not None and hi is not None and lo>hi:raise ValueError('Inverted ensemble percentiles')
        days.append({'date':iso(t)[:10],**values})
    return {'point_id':point['id'],'name':point['name'],'requested_latitude':point['latitude'],'requested_longitude':point['longitude'],
            'grid_latitude':lat,'grid_longitude':lon,'selection':'Open-Meteo default: documented GloFAS v4 seamless',
            'model_issued_at':None,'reach_verified':False,'units':'m³/s','days':days}

def validate_extensions(snapshot):
    from pipeline import require_keys, timestamp
    import re
    def provenance(obj):
        if timestamp(obj['fetched_at']) is None or not re.fullmatch('[0-9a-f]{64}',obj['sha256']):raise ValueError('Invalid source provenance')
    quake=snapshot['earthquakes']
    if quake is not None:
        require_keys(quake,{'fetched_at','sha256','url','normalized'});provenance(quake)
        n=quake['normalized'];require_keys(n,{'generated_at','region','events','scope'})
        if quake['url']!=USGS_URL:raise ValueError('Unexpected catalog URL')
        features=[]
        for e in n['events']:
            require_keys(e,{'id','occurred_at','source_updated_at','magnitude','magnitude_type','longitude','latitude','depth_km','review_status'})
            features.append({'id':e['id'],'geometry':{'type':'Point','coordinates':[e['longitude'],e['latitude'],e['depth_km']]},
                             'properties':{'type':'earthquake','time':timestamp(e['occurred_at'])*1000,'updated':timestamp(e['source_updated_at'])*1000,'mag':e['magnitude'],'magType':e['magnitude_type'],'status':e['review_status']}})
        raw={'type':'FeatureCollection','metadata':{'generated':timestamp(n['generated_at'])*1000,'status':200,'count':len(features)},'features':features}
        if normalize_quakes(raw,timestamp(quake['fetched_at']))!=n:raise ValueError('Catalog normalization mismatch')
    if not isinstance(snapshot['discharge'],list) or len(snapshot['discharge'])>6:raise ValueError('Unexpected discharge count')
    seen=set()
    for f in snapshot['discharge']:
        require_keys(f,{'fetched_at','sha256','url','normalized'});provenance(f);n=f['normalized']
        point=next((p for p in FLOOD_POINTS if p['id']==n.get('point_id')),None)
        if not point or point['id'] in seen or f['url']!=flood_url(point):raise ValueError('Unexpected discharge point')
        seen.add(point['id'])
        raw={'latitude':n['grid_latitude'],'longitude':n['grid_longitude'],'utc_offset_seconds':0,
             'daily_units':{'time':'unixtime',**{k:'m³/s' for k in DISCHARGE_FIELDS}},
             'daily':{'time':[timestamp(p['date']+'T00:00:00Z') for p in n['days']],**{k:[p[k] for p in n['days']] for k in DISCHARGE_FIELDS}}}
        if normalize_flood(raw,point,timestamp(f['fetched_at']))!=n:raise ValueError('Discharge normalization mismatch')
    require_keys(snapshot['pipeline'],{'schedule_minutes','history_started_at','history_runs','revisions','catchup_gaps','quality','history_branch','previous_revision'})
    require_keys(snapshot['pipeline']['quality'],{'river_recent','river_total','rain_recent','rain_total','warnings'})
