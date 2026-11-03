"""Read-only views and reproducible research over the Nepal archive."""
from __future__ import annotations
import bisect
import collections
import datetime as dt
import json
import math
import os
from pathlib import Path
import sqlite3
import statistics
import threading
import time

UTC = dt.timezone.utc
ROOT = Path(__file__).resolve().parents[1]

def now():
    return dt.datetime.now(UTC).isoformat(timespec='seconds')

def timestamp(value):
    try:
        t = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return t.timestamp() if t.tzinfo is not None else None
    except (ValueError, TypeError):
        return None

def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def csv_safe(value):
    """Keep text cells inert in spreadsheet imports, including leading control characters."""
    if isinstance(value,str) and (value.startswith(('\t','\r','\n')) or value.lstrip(' \t\r\n\ufeff').startswith(('=','+','-','@'))):
        return "'"+value
    return value

def freshness(value, at=None):
    t = timestamp(value)
    at = time.time() if at is None else at
    if t is None:
        return {'state':'unknown','age_minutes':None}
    age = (at-t)/60
    # Operational age labels, never estimates of safety or source service agreements.
    state = 'future_timestamp' if age < -5 else 'recent' if age <= 60 else 'delayed' if age <= 360 else 'stale'
    return {'state':state,'age_minutes':round(age,1)}

def alert_validity(item, at=None):
    at = time.time() if at is None else at
    start, end = timestamp(item.get('starts_at')), timestamp(item.get('expires_at'))
    if not item.get('source_verified'):
        return 'source_unverified'
    if start is None or end is None or end <= start:
        return 'validity_unknown'
    if at >= end:
        return 'expired'
    if at < start:
        return 'not_started'
    # Source-declared validity, not independently confirmed current authority status.
    return 'within_source_window'

def clean_points(rows):
    by_time = {}
    for r in rows:
        t = timestamp(r.get('observed_at'))
        if t is not None and number(r.get('water_level_source_units')):
            # Keep the last encountered source record at identical measurement time.
            by_time[t] = r
    return [(t, by_time[t]) for t in sorted(by_time)]

def replay(rows, cutoff, horizon_minutes=60, known_only=False):
    """One persistence prediction. Future observations are excluded from all inputs."""
    end = timestamp(cutoff)
    if end is None:
        raise ValueError('Replay cutoff must include a timezone')
    points = [(t,r) for t,r in clean_points(rows) if t <= end and
              (not known_only or (timestamp(r.get('first_seen_at')) is not None and timestamp(r['first_seen_at']) <= end))]
    if not points:
        return {'status':'no_input','prediction':None,'input_points':0,
                'explanation':'No measurements meet this cutoff and availability mode.'}
    t, r = points[-1]
    age = (end-t)/60
    if age > 120:
        return {'status':'stale_input','prediction':None,'input_points':len(points), 'age_minutes':age,
                'explanation':'Latest eligible input is over two hours old; baseline withheld.'}
    return {'status':'experimental','prediction':r['water_level_source_units'],
            'origin_at':dt.datetime.fromtimestamp(end,UTC).isoformat(),
            'target_at':dt.datetime.fromtimestamp(end+horizon_minutes*60,UTC).isoformat(),
            'last_input_at':r['observed_at'],'input_points':len(points),'age_minutes':age,
            'method':'Persistence: future level equals the most recent eligible level.',
            'availability_mode':'archive_first_seen' if known_only else 'retrospective_measurement_time',
            'hazard_assessment':'not_assessed','units':'source units — unconfirmed',
            'explanation':'Baseline only. No probability, flood footprint or warning is produced.'}

def evaluate(rows, horizon_minutes=60):
    points = clean_points(rows)
    if len(points)<3:
        return {'pairs':0,'mae':None,'rmse':None,'reason':'Insufficient observations'}
    times = [t for t,r in points]
    deltas = [b-a for a,b in zip(times,times[1:]) if b>a]
    cadence = statistics.median(deltas)
    # A target is at/after the requested horizon, within half a typical interval,
    # bounded at 30 min. Never substitute a substantially later observation.
    tolerance = min(cadence/2,1800)
    errors, actual_horizons = [], []
    skipped = 0
    for i,(t,r) in enumerate(points):
        target = t+horizon_minutes*60
        j = bisect.bisect_left(times,target)
        if j>=len(points) or times[j]-target>tolerance:
            skipped += 1
            continue
        errors.append(points[j][1]['water_level_source_units']-r['water_level_source_units'])
        actual_horizons.append((times[j]-t)/60)
    return {'pairs':len(errors),'skipped_origins':skipped,'horizon_minutes':horizon_minutes,
            'median_cadence_minutes':round(cadence/60,2),
            'target_tolerance_minutes':round(tolerance/60,2),
            'mean_actual_horizon_minutes':round(statistics.mean(actual_horizons),2) if errors else None,
            'mae':statistics.mean(map(abs,errors)) if errors else None,
            'rmse':math.sqrt(statistics.mean(e*e for e in errors)) if errors else None,
            'mode':'retrospective_measurement_time','method':'persistence',
            'units':'unconfirmed source units',
            'limitations':'Overlapping pairs are not independent events. Retrospective observations may be revised. This is not a forecast skill or warning validation claim.'}

class Dataset:
    def __init__(self, root=ROOT):
        self.root=Path(root)
        self.path=Path(os.environ.get('NEPAL_ARCHIVE_ROOT', self.root/'disaster_archive')).resolve()/'data/archive.sqlite'
        self.lock=threading.RLock()
        self.loaded=0
        self.signature=None

    def ensure(self, force=False):
        with self.lock:
            if getattr(self,'pinned',False) and self.loaded:return self
            sig=tuple((p.stat().st_mtime_ns,p.stat().st_size) if p.exists() else (0,0)
                      for p in [self.path,Path(str(self.path)+'-wal')])
            if self.loaded and not force and (time.monotonic()-self.loaded<20 or sig==self.signature):
                return self
            db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True,timeout=20)
            db.row_factory=sqlite3.Row
            try:
                db.execute('BEGIN')
                def rows(sql): return [dict(r) for r in db.execute(sql)]
                self.counts={r['collection']:r['n'] for r in rows('SELECT collection,count(*) n FROM records GROUP BY collection')}
                places=collections.defaultdict(set)
                for r in rows('SELECT incident_id,district FROM incident_places'):
                    if r['district']: places[r['incident_id']].add(r['district'])
                # Avoid individual names/descriptions in the dashboard incident view.
                self.incidents=rows('SELECT incident_id,local_event_date,hazard,source_hazard_type,latitude,longitude,reported_deaths,reported_missing,source_verified,first_seen_at FROM incident_current')
                for r in self.incidents:
                    r['districts']=sorted(places[r['incident_id']])
                self.rivers=rows('SELECT * FROM river_observations ORDER BY station_id,julianday(observed_at),CAST(observation_id AS INTEGER)')
                # The dashboard only needs the latest rainfall station timestamp, not every interval expansion.
                self.rain=rows("""SELECT station_id,observed_at FROM (
                    SELECT json_extract(payload,'$.station') station_id,json_extract(payload,'$.measuredOn') observed_at,
                    row_number() OVER(PARTITION BY json_extract(payload,'$.station') ORDER BY julianday(json_extract(payload,'$.measuredOn')) DESC) rank
                    FROM current_payloads WHERE collection='bipad:rain') WHERE rank=1""")
                self.quakes=rows('SELECT * FROM earthquake_current ORDER BY occurred_epoch_ms DESC LIMIT 50')
                self.alerts=rows("SELECT a.*,json_extract(h.payload,'$.title') hazard,json_extract(h.payload,'$.type') hazard_type FROM alert_current a LEFT JOIN current_payloads h ON h.collection='bipad:hazard' AND h.native_id=CAST(a.hazard_id AS TEXT) WHERE source_public=1 ORDER BY CAST(alert_id AS INTEGER) DESC")
                self.jobs=rows('SELECT * FROM collection_runs WHERE id IN (SELECT max(id) FROM collection_runs GROUP BY collection) ORDER BY id DESC')
                self.runs=rows('SELECT * FROM runs ORDER BY started_at DESC LIMIT 10')
                self.issues=rows('SELECT * FROM issues ORDER BY id DESC LIMIT 30')
                self.revisions=rows('SELECT collection,count(*) n FROM changes WHERE previous_version_id IS NOT NULL GROUP BY collection')
                self.fetch_count=db.execute('SELECT count(*) FROM fetches').fetchone()[0]
            finally:
                db.close()
            self.river_groups=collections.defaultdict(list)
            for r in self.rivers:
                if r['station_id'] is not None: self.river_groups[str(r['station_id'])].append(r)
            self.stations=[]
            for sid,rr in self.river_groups.items():
                pp=clean_points(rr)
                if not pp: continue
                last=pp[-1][1]
                gaps=[b[0]-a[0] for a,b in zip(pp,pp[1:])]
                self.stations.append({**last,'id':sid,'points':len(pp),'first_observed_at':pp[0][1]['observed_at'],
                                      'span_hours':round((pp[-1][0]-pp[0][0])/3600,1),
                                      'max_gap_minutes':round(max(gaps)/60,1) if gaps else None,
                                      'threshold_present':number(last['warning_level_source_units'])})
            self.stations.sort(key=lambda r:(r['basin'] or '',r['station_name'] or ''))
            self.loaded=time.monotonic(); self.signature=sig; self.loaded_at=now()
            return self

    def overview(self):
        self.ensure()
        hazards=collections.Counter(r['hazard'] or 'Unspecified' for r in self.incidents)
        annual=collections.defaultdict(lambda:collections.Counter())
        for r in self.incidents:
            if r['hazard'] in ('Flood','Landslide') and r.get('local_event_date'): annual[r['local_event_date'][:4]][r['hazard']]+=1
        basins=collections.defaultdict(list)
        for s in self.stations: basins[s['basin'] or 'Unspecified'].append(s)
        coverage=[{'basin':b,'stations':len(ss),'with_reference_threshold':sum(s['threshold_present'] for s in ss),
                   'median_span_hours':statistics.median(s['span_hours'] for s in ss),
                   'latest':max(ss,key=lambda s:timestamp(s['observed_at']))['observed_at']} for b,ss in basins.items()]
        return {'as_of':now(),'loaded_at':self.loaded_at,'counts':self.counts,'runs':self.runs,
                'natural_reports':sum(r['source_hazard_type']=='natural' for r in self.incidents),
                'date_start':min((r['local_event_date'] for r in self.incidents if r.get('local_event_date')),default=None),'date_end':max((r['local_event_date'] for r in self.incidents if r.get('local_event_date')),default=None),
                'hazards':dict(hazards),'annual':[{'year':y,**v} for y,v in sorted(annual.items())],
                'districts':sorted({d for r in self.incidents for d in r['districts']}),
                'basins':sorted(coverage,key=lambda r:-r['stations']),
                'stations':[dict(s,freshness=freshness(s['observed_at'])) for s in self.stations],
                'fetch_count':self.fetch_count,'revisions':self.revisions,'issues':self.issues,
                'hazard_assessment':'not_assessed','unit_verification':'pending'}

    def incident_query(self, hazard='',district='',year=''):
        self.ensure()
        if len(hazard)>100 or len(district)>100 or len(year)>4: raise ValueError('Invalid filter')
        rr=[r for r in self.incidents if (not hazard or r['hazard']==hazard) and
            (not district or district in r['districts']) and (not year or (r.get('local_event_date') or '').startswith(year))]
        by_district=collections.Counter()
        month=collections.Counter()
        unallocated=0
        for r in rr:
            month[(r.get('local_event_date') or '')[5:7]]+=1
            if len(r['districts'])==1: by_district[r['districts'][0]]+=1
            else: unallocated+=1
        rr=sorted(rr,key=lambda r:((r.get('local_event_date') or ''),int(r['incident_id'])),reverse=True)
        return {'total':len(rr),'rows':rr[:150],'row_limit':150,'points':rr[:2000],'map_limit':2000,
                'districts':[{'district':k,'reports':v} for k,v in by_district.most_common()],
                'unallocated_district_reports':unallocated,'monthly':[{'month':str(m).zfill(2),'reports':month[str(m).zfill(2)]} for m in range(1,13)],
                'interpretation':'Source reports, not unique disasters or population-adjusted risk. Multi-district reports are excluded from district rankings.'}

    def river(self, sid,cutoff=None,horizon=60,known=False):
        self.ensure()
        if sid not in self.river_groups: raise ValueError('Unknown station')
        rr=self.river_groups[sid]
        pp=clean_points(rr)
        station=next(s for s in self.stations if s['id']==sid)
        cutoff=cutoff or pp[-1][1]['observed_at']
        evaluation=evaluate(rr,horizon)
        inputs=self.as_known_river(sid,cutoff) if known else rr
        # Entire series is returned as observations; prediction always uses only eligible past inputs.
        return {'station':dict(station,freshness=freshness(station['observed_at'])),
                'points':[{'at':r['observed_at'],'level':r['water_level_source_units'],
                           'first_seen_at':r['first_seen_at'],'warning':r['warning_level_source_units'],
                           'danger':r['danger_level_source_units']} for t,r in pp],
                'replay':replay(inputs,cutoff,horizon,known),'evaluation':evaluation,
                'availability_mode':'archive_first_seen' if known else 'retrospective_measurement_time',
                'eligible_points':[{'at':r['observed_at'],'level':r['water_level_source_units']} for t,r in clean_points(inputs) if t<=(timestamp(cutoff) or 0)],
                'provenance_url':'https://bipadportal.gov.np/api/v1/river/?station='+sid}

    def as_known_river(self,sid,cutoff):
        if timestamp(cutoff) is None:raise ValueError('Replay cutoff must include a timezone')
        db=sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
        db.row_factory=sqlite3.Row
        try:
            rows=db.execute('''WITH known AS (
              SELECT native_id,version_id,observed_at,
                     row_number() OVER(PARTITION BY native_id ORDER BY observed_at DESC,id DESC) rank
              FROM changes WHERE collection='bipad:river' AND julianday(observed_at)<=julianday(?)
            ) SELECT k.native_id observation_id,k.observed_at first_seen_at,
                json_extract(v.payload,'$.waterLevelOn') observed_at,
                json_extract(v.payload,'$.waterLevel') water_level_source_units
              FROM known k JOIN record_versions v ON v.id=k.version_id
              WHERE k.rank=1 AND CAST(json_extract(v.payload,'$.station') AS TEXT)=?
              ORDER BY julianday(json_extract(v.payload,'$.waterLevelOn')),CAST(k.native_id AS INTEGER)''',(cutoff,sid))
            return [dict(r) for r in rows]
        finally:db.close()

    def source_health(self):
        self.ensure()
        seen=set(); jobs=[]
        for j in self.jobs:
            if j['collection'] in seen: continue
            seen.add(j['collection']);jobs.append(j)
        alerts=[]
        for a in self.alerts:
            if a['hazard_type']!='natural': continue
            alerts.append(dict(a,validity=alert_validity(a),freshness=freshness(a['created_at']),
                               url='https://bipadportal.gov.np/api/v1/alert/'+a['alert_id']+'/'))
        rain_by_station={}
        for r in self.rain:
            if r['station_id'] is not None: rain_by_station[str(r['station_id'])]=r
        return {'jobs':jobs,'issues':self.issues,'alerts':alerts[:60], 'alert_total':len(alerts),
                'alert_scope':'Latest 2,000 source records per collection, filtered here to public natural-hazard messages. Not comprehensive; lifecycle changes may be missed.',
                'rain_stations':len(rain_by_station),'rain_latest':max((r['observed_at'] for r in self.rain),key=lambda x:timestamp(x) or 0,default=None),
                'quakes':self.quakes,'metadata_verified':False}

    def report(self):
        self.ensure()
        evaluations=[]
        for sid,rr in self.river_groups.items():
            ev=evaluate(rr,60)
            station=next((s for s in self.stations if s['id']==sid),None)
            if station: evaluations.append({'station_id':sid,'name':station['station_name'],'basin':station['basin'],**ev})
        result={'generated_at':now(),'source_snapshot':self.loaded_at,'method':'persistence','horizon_minutes':60,
                'stations':evaluations,'operational_warning_ready':False,
                'limitations':['Source units/datum unconfirmed; errors cannot be pooled meaningfully across stations.',
                               'Short observation window; no independently verified flood outcomes.',
                               'Measurement-time retrospective evaluation, not archive-known-at-time backtesting.',
                               'Overlapping pairs are not independent disasters; no confidence or accuracy claim.']}
        return result
