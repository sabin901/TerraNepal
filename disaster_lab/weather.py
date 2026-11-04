"""Public weather forecasts, preserved before normalization. No API key required.

Personal/non-commercial Open-Meteo access only; see provider terms in METHODS.md.
"""
from __future__ import annotations
import concurrent.futures
import bisect
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import subprocess
import time
import urllib.parse
from analytics import iso
from data import ROOT, number, timestamp, clean_points

PLACES = [
    {'id':'kathmandu','name':'Kathmandu','latitude':27.7172,'longitude':85.3240},
    {'id':'pokhara','name':'Pokhara','latitude':28.2096,'longitude':83.9856},
    {'id':'biratnagar','name':'Biratnagar','latitude':26.4525,'longitude':87.2718},
    {'id':'janakpur','name':'Janakpur','latitude':26.7288,'longitude':85.9263},
    {'id':'nepalgunj','name':'Nepalgunj','latitude':28.0500,'longitude':81.6167},
    {'id':'birendranagar','name':'Birendranagar','latitude':28.6019,'longitude':81.6339},
    {'id':'dhangadhi','name':'Dhangadhi','latitude':28.7017,'longitude':80.5947},
]
MODELS = {'ecmwf_ifs025':'ECMWF IFS 0.25°','gfs_global':'NOAA GFS global'}
UNITS = {'time':'unixtime','precipitation':'mm','temperature_2m':'°C','wind_gusts_10m':'m/s'}

def normalize(payload, place):
    if not isinstance(payload,dict) or payload.get('error'): raise ValueError('Provider returned an error or unexpected shape')
    if not isinstance(payload.get('hourly_units'),dict) or not isinstance(payload.get('hourly'),dict):raise ValueError('Unexpected weather units or hourly schema')
    if payload.get('utc_offset_seconds')!=0: raise ValueError('Expected UTC timestamps')
    if any(payload.get('hourly_units',{}).get(k)!=v for k,v in UNITS.items()): raise ValueError('Unexpected forecast units')
    lat,lon=payload.get('latitude'),payload.get('longitude')
    if not number(lat) or not number(lon) or abs(lat-place['latitude'])>.5 or abs(lon-place['longitude'])>.5:
        raise ValueError('Forecast grid point does not match requested location')
    hourly=payload.get('hourly',{});times=hourly.get('time',[])
    if not isinstance(times,list) or not 72<=len(times)<=200: raise ValueError('Expected 72–200 hourly forecast values')
    if any(not number(t) or not 946684800<=t<4102444800 for t in times) or any(b-a!=3600 for a,b in zip(times,times[1:])):
        raise ValueError('Forecast timestamps must be ordered, distinct and hourly')
    if any(not isinstance(hourly.get(k),list) or len(hourly[k])!=len(times) for k in UNITS):
        raise ValueError('Forecast arrays have inconsistent lengths')
    points=[]
    for i,t in enumerate(times):
        point={'at':iso(t),'epoch':t}
        for k in UNITS:
            if k=='time': continue
            v=hourly[k][i]
            if v is not None and (not number(v) or (k!='temperature_2m' and v<0)):
                raise ValueError('Invalid numeric forecast value: '+k)
            point[k]=v
        points.append(point)
    return {'grid_latitude':lat,'grid_longitude':lon,'elevation':payload.get('elevation'),
            'units':UNITS,'points':points,'model_issued_at':None,
            'time_note':'Model run issuance is not supplied by this endpoint. Retrieval time is not issuance time.'}

def summarize(normalized, fetched_at, at=None):
    at=time.time() if at is None else at
    # Precipitation at t is the sum over (t-1h,t]. Start at the next full UTC hour.
    start=math.ceil(at/3600)*3600
    lookup={p['epoch']:p for p in normalized['points']}
    age=(at-timestamp(fetched_at))/3600
    state='recent' if 0<=age<=6 else 'stale' if age>6 else 'future_retrieval'
    windows={}
    for hours in (24,48,72):
        pp=[lookup.get(start+(i+1)*3600) for i in range(hours)]
        def complete(field):return state=='recent' and all(p is not None and number(p[field]) for p in pp)
        windows[str(hours)]={'start_at':iso(start),'end_at':iso(start+hours*3600),
                            'precipitation_mm':sum(p['precipitation'] for p in pp) if complete('precipitation') else None,
                            'max_hourly_precipitation_mm':max(p['precipitation'] for p in pp) if complete('precipitation') else None,
                            'max_gust_ms':max(p['wind_gusts_10m'] for p in pp) if complete('wind_gusts_10m') else None,
                            'max_temperature_c':max(p['temperature_2m'] for p in pp) if complete('temperature_2m') else None,
                            'valid_precipitation_hours':sum(p is not None and number(p['precipitation']) for p in pp)}
    return {'state':state,'retrieval_age_hours':age,'windows':windows,
            'points':[p for p in normalized['points'] if start<p['epoch']<=start+72*3600]}

class ForecastStore:
    def __init__(self, root=None):
        self.root=Path(root or os.environ.get('NEPAL_STATE_ROOT', ROOT/'disaster_lab/local'));self.root.mkdir(parents=True,exist_ok=True)
        self.raw=self.root/'weather_raw';self.raw.mkdir(exist_ok=True)
        self.path=self.root/'forecasts.sqlite'
        with contextlib.closing(self.db()) as db,db:
            db.executescript('''
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS weather_fetches(id INTEGER PRIMARY KEY,place_id TEXT,model TEXT,fetched_at TEXT,url TEXT,status TEXT,sha256 TEXT,raw_file TEXT,normalized TEXT,error TEXT);
              CREATE INDEX IF NOT EXISTS weather_lookup ON weather_fetches(place_id,model,id);
              CREATE TABLE IF NOT EXISTS river_predictions(id TEXT PRIMARY KEY,station_id TEXT,horizon INTEGER,origin_at TEXT,target_at TEXT,generated_at TEXT,model_version TEXT,input_sha256 TEXT,payload TEXT);
            ''')
    def db(self):
        db=sqlite3.connect(self.path,timeout=20);db.row_factory=sqlite3.Row;return db
    def fetch(self, place, model, force=False):
        with contextlib.closing(self.db()) as db:
            last=db.execute('SELECT * FROM weather_fetches WHERE place_id=? AND model=? ORDER BY id DESC LIMIT 1',(place['id'],model)).fetchone()
        if last and time.time()-timestamp(last['fetched_at'])<(3600 if last['status']=='ok' else 300) and not force:
            return {'place':place['id'],'model':model,'status':'cached','last_status':last['status']}
        params={'latitude':place['latitude'],'longitude':place['longitude'],'hourly':'precipitation,temperature_2m,wind_gusts_10m',
                'models':model,'forecast_hours':96,'timeformat':'unixtime','timezone':'GMT','wind_speed_unit':'ms','precipitation_unit':'mm'}
        url='https://api.open-meteo.com/v1/forecast?'+urllib.parse.urlencode(params)
        digest=rawfile=normalized=error=None;status='error'
        try:
            r=subprocess.run(['curl','--fail-with-body','--silent','--show-error','--proto','=https','--connect-timeout','10','--max-time','35','--max-filesize','2000000',url],capture_output=True,timeout=40)
            digest=hashlib.sha256(r.stdout).hexdigest();rawfile=digest+'.json'
            if not (self.raw/rawfile).exists():
                # Publish a complete immutable blob before the database references it.
                import tempfile
                with tempfile.NamedTemporaryFile(dir=self.raw,delete=False) as out:
                    out.write(r.stdout);temp=Path(out.name)
                temp.replace(self.raw/rawfile)
            if r.returncode: raise ValueError('Fetch failed: '+r.stderr.decode(errors='replace')[:300])
            normalized=json.dumps(normalize(json.loads(r.stdout),place),allow_nan=False)
            status='ok'
        except (ValueError,OSError,subprocess.TimeoutExpired) as e:error=str(e)
        stamp=iso(time.time())
        with contextlib.closing(self.db()) as db,db:
            db.execute('INSERT INTO weather_fetches(place_id,model,fetched_at,url,status,sha256,raw_file,normalized,error) VALUES (?,?,?,?,?,?,?,?,?)',
                       (place['id'],model,stamp,url,status,digest,rawfile,normalized,error))
        return {'place':place['id'],'model':model,'status':status,'error':error}
    def collect(self, force=False):
        # Single-location requests avoid relying on positional multi-location mappings.
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            jobs=[pool.submit(self.fetch,p,m,force) for p in PLACES for m in MODELS]
            return [j.result() for j in jobs]
    def outlook(self, at=None):
        at=time.time() if at is None else at
        places=[]
        with contextlib.closing(self.db()) as db:
            for p in PLACES:
                sources=[]
                for model,label in MODELS.items():
                    latest=db.execute('SELECT status,error,fetched_at FROM weather_fetches WHERE place_id=? AND model=? ORDER BY id DESC LIMIT 1',(p['id'],model)).fetchone()
                    good=db.execute("SELECT * FROM weather_fetches WHERE place_id=? AND model=? AND status='ok' ORDER BY id DESC LIMIT 1",(p['id'],model)).fetchone()
                    source={'model':model,'label':label,'latest_attempt':dict(latest) if latest else None,'state':'missing','windows':{},'points':[]}
                    if good:
                        normalized=json.loads(good['normalized'])
                        source.update(summarize(normalized,good['fetched_at'],at))
                        source.update({k:good[k] for k in ('id','fetched_at','url','sha256')})
                        source.update({k:normalized[k] for k in ('grid_latitude','grid_longitude','model_issued_at','time_note')})
                    sources.append(source)
                disagreements={}
                for hours in ('24','48','72'):
                    totals=[s['windows'].get(hours,{}).get('precipitation_mm') for s in sources]
                    disagreements[hours]=abs(totals[0]-totals[1]) if all(v is not None for v in totals) else None
                places.append({**p,'sources':sources,'model_difference_mm':disagreements})
            fetch_count=db.execute('SELECT count(*) FROM weather_fetches').fetchone()[0]
            saved=db.execute('SELECT count(*) FROM river_predictions').fetchone()[0]
        return {'generated_at':iso(at),'places':places,'fetch_count':fetch_count,'saved_river_predictions':saved,
                'attribution':'Weather data: Open-Meteo, ECMWF and NOAA. CC BY 4.0. Personal/non-commercial API access.',
                'limitations':['Seven illustrative city points, not catchment-average rainfall or national coverage.',
                               'Hourly values may be interpolated from coarser model timesteps; terrain-scale extremes may be missed.',
                               'Difference between two models is not a probability interval; both models can be wrong.',
                               'Summaries require complete windows and retrieval age <=6h (local display policy, not provider SLA).',
                               'Future precipitation includes rain and snow water equivalent; no flood conversion is applied.']}
    def save_river(self, sid, analysis, at=None):
        if analysis['projection'] is None: return None
        p=analysis['projection']
        at=time.time() if at is None else at
        if timestamp(p['target_at'])<=at:return None
        # Saving must itself precede the target, even if computation crossed that time.
        payload={**analysis,'generated_at':iso(at)}
        key=hashlib.sha256(f"{sid}:{analysis['horizon_minutes']}:{analysis['version']}:{analysis['input_sha256']}".encode()).hexdigest()
        with contextlib.closing(self.db()) as db,db:
            db.execute('INSERT OR IGNORE INTO river_predictions VALUES (?,?,?,?,?,?,?,?,?)',
                       (key,sid,analysis['horizon_minutes'],p['origin_at'],p['target_at'],payload['generated_at'],analysis['version'],analysis['input_sha256'],json.dumps(payload,allow_nan=False)))
        return key
    def ledger(self, dataset=None, at=None, limit=100, offset=0):
        from verification import verify, ledger
        if dataset is not None:verify(self,dataset,at)
        return ledger(self,limit,offset)

if __name__=='__main__':
    results=ForecastStore().collect()
    print(json.dumps(results,indent=2))
    raise SystemExit(1 if any(r['status']=='error' or r.get('last_status')=='error' for r in results) else 0)
