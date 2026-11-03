"""Prospective verification of every saved prediction, with revision history."""
import bisect
import collections
import contextlib
import hashlib
import json
import math
import time
from analytics import iso
from data import clean_points, timestamp, number

SCHEMA='''
CREATE TABLE IF NOT EXISTS prediction_outcomes(prediction_id TEXT PRIMARY KEY REFERENCES river_predictions(id),
 fingerprint TEXT NOT NULL,checked_at TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS outcome_history(id INTEGER PRIMARY KEY,prediction_id TEXT NOT NULL,
 fingerprint TEXT NOT NULL,checked_at TEXT NOT NULL,payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS outcome_prediction ON outcome_history(prediction_id,id);
'''

def initialize(store):
    with contextlib.closing(store.db()) as db,db:db.executescript(SCHEMA)

def verify(store,dataset,at=None):
    at=time.time() if at is None else at;dataset.ensure();initialize(store)
    series={};conflicts={};counts=collections.Counter()
    with contextlib.closing(store.db()) as db,db:
        for row in db.execute('SELECT * FROM river_predictions').fetchall():
            payload=json.loads(row['payload']);projection=payload['projection'];target=timestamp(row['target_at'])
            outcome={'state':'pending','actual':None,'absolute_error':None}
            if timestamp(row['generated_at'])>=target:outcome['state']='ineligible_late_generation'
            elif target<=at:
                outcome['state']='awaiting_observation'
                sid=row['station_id']
                if sid not in series:
                    source=dataset.river_groups.get(sid,[]);points=clean_points(source);series[sid]=([t for t,r in points],points)
                    values=collections.defaultdict(set)
                    for item in source:
                        if number(item.get('water_level_source_units')):values[timestamp(item.get('observed_at'))].add(item['water_level_source_units'])
                    conflicts[sid]={t for t,v in values.items() if len(v)>1}
                times,points=series[sid];j=bisect.bisect_left(times,target)
                tolerance=payload.get('partitions',{}).get('target_tolerance_minutes',0)*60
                if j<len(points) and target<=times[j]<=min(at,target+tolerance):
                    observation=points[j][1];actual=observation['water_level_source_units'];error=actual-projection['level']
                    outcome={'state':'matched','actual':actual,'observed_at':iso(times[j]),'absolute_error':abs(error),
                        'signed_error':error,'in_error_range':projection['lower']<=actual<=projection['upper'],
                        'observation_id':observation.get('observation_id'),'observation_version_id':observation.get('version_id')}
                    if times[j] in conflicts[sid]:outcome={'state':'conflicting_observation','actual':None,'absolute_error':None,'observed_at':iso(times[j])}
            raw=json.dumps(outcome,sort_keys=True,allow_nan=False);fingerprint=hashlib.sha256(raw.encode()).hexdigest()
            previous=db.execute('SELECT fingerprint FROM prediction_outcomes WHERE prediction_id=?',(row['id'],)).fetchone()
            if not previous or previous[0]!=fingerprint:
                db.execute('INSERT INTO outcome_history(prediction_id,fingerprint,checked_at,payload) VALUES(?,?,?,?)',(row['id'],fingerprint,iso(at),raw));counts['outcome_revisions']+=1
            db.execute('INSERT OR REPLACE INTO prediction_outcomes VALUES(?,?,?,?)',(row['id'],fingerprint,iso(at),raw))
            counts[outcome['state']]+=1
    return {'checked_at':iso(at),'counts':dict(counts),'total':sum(counts[k] for k in ('matched','pending','awaiting_observation','ineligible_late_generation','conflicting_observation'))}

def ledger(store,limit=100,offset=0):
    initialize(store)
    if not 1<=limit<=200 or offset<0:raise ValueError('Invalid ledger page')
    with contextlib.closing(store.db()) as db:
        rows=[]
        for r in db.execute('''SELECT p.*,o.payload AS outcome,o.checked_at FROM river_predictions p
            LEFT JOIN prediction_outcomes o ON o.prediction_id=p.id ORDER BY p.generated_at DESC,p.id LIMIT ? OFFSET ?''',(limit,offset)):
            row=dict(r);row['projection']=json.loads(row.pop('payload'))['projection']
            row['verification']=json.loads(row.pop('outcome') or '{"state":"unverified","actual":null,"absolute_error":null}')
            rows.append(row)
        total=db.execute('SELECT count(*) FROM river_predictions').fetchone()[0]
        counts=collections.Counter();groups=collections.defaultdict(list)
        for r in db.execute('''SELECT p.station_id,p.horizon,p.model_version,p.payload,o.payload AS outcome FROM river_predictions p
            LEFT JOIN prediction_outcomes o ON o.prediction_id=p.id'''):
            outcome=json.loads(r['outcome'] or '{"state":"unverified"}');counts[outcome['state']]+=1
            if outcome['state']=='matched':
                model=json.loads(r['payload']).get('selected_model','unknown')
                groups[(r['station_id'],r['horizon'],r['model_version'],model)].append(outcome)
        checked=db.execute('SELECT min(checked_at),max(checked_at) FROM prediction_outcomes').fetchone()
    metrics=[]
    for (sid,horizon,version,model),outcomes in sorted(groups.items()):
        n=len(outcomes);metrics.append({'station_id':sid,'horizon_minutes':horizon,'model_version':version,'model':model,'pairs':n,
            'mae':sum(o['absolute_error'] for o in outcomes)/n,'rmse':math.sqrt(sum(o['signed_error']**2 for o in outcomes)/n),
            'bias':sum(o['signed_error'] for o in outcomes)/n,'error_range_coverage':sum(o['in_error_range'] for o in outcomes)/n})
    return {'rows':rows,'matched':sum(r['verification']['state']=='matched' for r in rows),'total':total,'limit':limit,'offset':offset,
        'counts':dict(counts),'metrics':metrics,'verified_at_min':checked[0],'verified_at_max':checked[1],
        'note':'All saved projections contribute to counts and station/horizon/model scorecards. The table is paginated. Outcomes use latest archived revisions; changes are retained. Overlapping forecast targets are dependent samples. Scores use unconfirmed station units and do not establish warning accuracy.'}
