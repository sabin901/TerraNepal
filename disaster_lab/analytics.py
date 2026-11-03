"""Versioned, auditable short-horizon experiments. Not a flood-warning model."""
from __future__ import annotations
import bisect
import collections
import datetime as dt
import hashlib
import json
import math
import statistics
import time
from data import clean_points, number, timestamp, UTC

VERSION = 'river-local-v2.0'
MODELS = ('persistence', 'damped_trend')

def iso(t):
    return dt.datetime.fromtimestamp(t, UTC).isoformat(timespec='seconds')

def quantile(values, q):
    if not values: return None
    s = sorted(values)
    return s[min(len(s)-1, max(0, math.ceil(q*len(s))-1))]

def predict(points, index, horizon_minutes, model, times=None):
    t, row = points[index]
    level = row['water_level_source_units']
    if model == 'persistence': return level
    if model != 'damped_trend': raise ValueError('Unknown model')
    # Only past values in a fixed 3-hour window; never fit on the target.
    times = times if times is not None else [p[0] for p in points]
    window = points[bisect.bisect_left(times, t-10800):index+1]
    if len(window)<4 or t-window[0][0]<2700: return None
    if max(b[0]-a[0] for a,b in zip(window,window[1:]))>3600: return None
    xs = [(a-t)/3600 for a,r in window]
    ys = [r['water_level_source_units'] for a,r in window]
    xm, ym = statistics.mean(xs), statistics.mean(ys)
    slope = sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/sum((x-xm)**2 for x in xs)
    # Fixed exponential rate decay, time constant 2 hours. No tuning on test data.
    return level + slope*2*(1-math.exp(-(horizon_minutes/60)/2))

def metrics(samples, model, band=None):
    residuals = [s['actual']-s['predictions'][model] for s in samples]
    return {'pairs':len(samples), 'mae':statistics.mean(abs(e) for e in residuals) if residuals else None,
            'rmse':math.sqrt(statistics.mean(e*e for e in residuals)) if residuals else None,
            'bias_actual_minus_prediction':statistics.mean(residuals) if residuals else None,
            'band_coverage':sum(band[0]<=e<=band[1] for e in residuals)/len(residuals) if residuals and band else None}

def station_quality(rows, at=None):
    at = time.time() if at is None else at
    points = clean_points(rows)
    groups = collections.defaultdict(set)
    for r in rows:
        if timestamp(r.get('observed_at')) is not None and number(r.get('water_level_source_units')):
            groups[timestamp(r['observed_at'])].add(r['water_level_source_units'])
    future = sum(t>at+300 for t,r in points)
    past = [(t,r) for t,r in points if t<=at]
    gaps = [(b[0]-a[0])/60 for a,b in zip(past,past[1:])]
    changes = [b[1]['water_level_source_units']-a[1]['water_level_source_units'] for a,b in zip(past,past[1:])]
    md = statistics.median(changes) if changes else 0
    mad = statistics.median(abs(x-md) for x in changes) if changes else 0
    # This is a review flag, never an automatic deletion or physical validity claim.
    unusual = sum(abs(x-md)>10*1.4826*mad for x in changes) if mad>0 else None
    return {'raw_rows':len(rows),'usable_points':len(past),
            'invalid_rows':sum(timestamp(r.get('observed_at')) is None or not number(r.get('water_level_source_units')) for r in rows),
            'duplicate_times':sum(n-1 for n in collections.Counter(timestamp(r.get('observed_at')) for r in rows if timestamp(r.get('observed_at')) is not None).values()),
            'conflicting_times':sum(len(s)>1 for s in groups.values()),'future_timestamps':future,
            'age_minutes':(at-past[-1][0])/60 if past else None,
            'span_hours':(past[-1][0]-past[0][0])/3600 if len(past)>1 else 0,
            'median_cadence_minutes':statistics.median(gaps) if gaps else None,
            'max_gap_minutes':max(gaps) if gaps else None,
            'review_large_steps':unusual,'constant_last_12_points':len(past)>=12 and len({r['water_level_source_units'] for t,r in past[-12:]})==1,
            'units_verified':False,'datum_verified':False,'thresholds_verified':False}

def analyze(rows, horizon=60, at=None):
    if horizon not in (30,60,180): raise ValueError('Unsupported horizon')
    at = time.time() if at is None else at
    quality = station_quality(rows,at)
    pp = [(t,r) for t,r in clean_points(rows) if t<=at]
    fingerprint = hashlib.sha256(json.dumps([(t,r['water_level_source_units'],r.get('first_seen_at')) for t,r in pp],separators=(',',':')).encode()).hexdigest()
    result = {'version':VERSION,'generated_at':iso(at),'input_sha256':fingerprint,'horizon_minutes':horizon,
              'units':'source units — unconfirmed','quality':quality,'selected_model':'persistence',
              'status':'withheld','projection':None,'selection':{},'calibration':{},'test':{},'samples':[],
              'hazard_assessment':'not_assessed','limitations':[
                  'Water-level experiment only; not flood extent, damage, or disaster probability.',
                  'Retrospective measurement-time testing uses the latest archived revisions, not historical delivery times.',
                  'Short, serially dependent history cannot establish performance across flood events or seasons.',
                  'Error range is the 10th–90th percentile of prior signed errors, not a guaranteed 80% probability interval.',
                  'Local level models use past levels only; weather forecasts are separate and are not yet coupled to runoff.']}
    if len(pp)<16:
        result['reason']='Fewer than 16 usable measurements.';return result
    times = [t for t,r in pp]
    start, end = times[0], times[-1]
    boundary1, boundary2 = start+(end-start)*.6, start+(end-start)*.8
    tolerance = min(statistics.median(b-a for a,b in zip(times,times[1:]))/2,1800)
    phases = {'selection':[],'calibration':[],'test':[]}
    next_origin = start
    for i,(t,r) in enumerate(pp):
        if t<next_origin: continue
        j = bisect.bisect_left(times,t+horizon*60)
        if j>=len(pp) or times[j]-(t+horizon*60)>tolerance: continue
        preds = {m:predict(pp,i,horizon,m,times) for m in MODELS}
        if any(v is None for v in preds.values()): continue
        phase = 'selection' if times[j]<=boundary1 else 'calibration' if t>=boundary1 and times[j]<=boundary2 else 'test' if t>=boundary2 else None
        if phase is None: continue  # Purge intervals crossing a partition boundary.
        phases[phase].append({'origin_at':iso(t),'target_at':iso(times[j]),'actual':pp[j][1]['water_level_source_units'],'predictions':preds})
        next_origin = times[j]  # Target windows do not overlap; independence is not assumed.
    result['partitions'] = {'selection_end':iso(boundary1),'calibration_end':iso(boundary2),'end':iso(end),
                            'rule':'60/20/20 of elapsed measurement time; boundary-crossing targets purged; non-overlapping target windows',
                            'target_tolerance_minutes':tolerance/60}
    result['selection'] = {m:metrics(phases['selection'],m) for m in MODELS}
    scores = result['selection']
    chosen = 'persistence'
    if scores['persistence']['pairs']>=12 and scores['persistence']['mae']>0 and scores['damped_trend']['mae']<scores['persistence']['mae']*.98:
        chosen = 'damped_trend'
    result['selected_model'] = chosen
    result['selection_rule'] = 'Use damped trend only with >=12 selection pairs and >2% lower MAE; otherwise persistence. Test scores never choose the model.'
    residuals = [s['actual']-s['predictions'][chosen] for s in phases['calibration']]
    band = [quantile(residuals,.1),quantile(residuals,.9)] if len(residuals)>=8 else None
    result['calibration'] = {'pairs':len(residuals),'residual_range':band,'nominal_central_fraction':.8}
    result['test'] = {m:metrics(phases['test'],m,band if m==chosen else None) for m in MODELS}
    base, selected = result['test']['persistence']['mae'],result['test'][chosen]['mae']
    result['test_skill_vs_persistence'] = 1-selected/base if base and selected is not None else None
    result['samples'] = phases['test']
    reasons = []
    if quality['age_minutes']>120: reasons.append('Latest measurement is over two hours old.')
    if end+horizon*60<=at: reasons.append('Projection target is already in the past.')
    if quality['future_timestamps']: reasons.append('Station contains future-dated measurements; review source clock.')
    if quality['conflicting_times']: reasons.append('Conflicting source levels at identical measurement times.')
    if scores['persistence']['pairs']<12 or len(phases['calibration'])<8 or len(phases['test'])<8:
        reasons.append('Need at least 12 selection, 8 calibration and 8 test pairs.')
    predicted = predict(pp,len(pp)-1,horizon,chosen,times)
    if predicted is None: reasons.append('Recent observations cannot support the selected model.')
    if reasons:
        result['reason']=' '.join(reasons);return result
    result['status']='experimental'
    result['reason']='Passed local data and sample checks; independent flood-event validation remains pending.'
    result['projection']={'origin_at':iso(end),'target_at':iso(end+horizon*60),
                          'remaining_minutes':(end+horizon*60-at)/60,'last_level':pp[-1][1]['water_level_source_units'],
                          'level':predicted,'lower':predicted+band[0],'upper':predicted+band[1],
                          'change':predicted-pp[-1][1]['water_level_source_units']}
    return result

def quality_audit(dataset, at=None):
    dataset.ensure();at=time.time() if at is None else at
    rows=[]
    for s in dataset.stations:
        q=station_quality(dataset.river_groups[s['id']],at)
        rows.append({'id':s['id'],'name':s['station_name'],'basin':s['basin'],**q})
    return {'generated_at':iso(at),'station_count':len(rows),'stations':rows,
            'counts':{'recent':sum(r['age_minutes'] is not None and r['age_minutes']<=60 for r in rows),
                      'over_two_hours_old':sum(r['age_minutes'] is None or r['age_minutes']>120 for r in rows),
                      'with_conflicting_times':sum(r['conflicting_times']>0 for r in rows),
                      'with_future_timestamps':sum(r['future_timestamps']>0 for r in rows),
                      'invalid_rows':sum(r['invalid_rows'] for r in rows),
                      'metadata_verified':0},
            'interpretation':'Automated consistency checks, not independent verification of sensors or source claims. Review flags are retained, not silently removed.'}
