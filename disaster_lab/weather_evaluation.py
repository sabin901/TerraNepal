"""Offline paired weather verification; caller supplies reviewed mapping/truth."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
import hashlib
from pathlib import Path

UNITS = {'temperature_2m':'degC','precipitation':'mm','wind_speed_10m':'m/s'}

def timestamp(value):
    if not isinstance(value,str): raise ValueError('invalid_timestamp')
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
        if result.utcoffset() is None: raise ValueError()
        return result.astimezone(timezone.utc)
    except (ValueError,OverflowError): raise ValueError('invalid_timestamp') from None

def number(value):
    try:return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
    except OverflowError:return False

def checked(case,as_of):
    if not isinstance(case,dict):raise ValueError('invalid_case')
    forecast,observation,mapping=(case.get(k) for k in ('forecast','observation','mapping'))
    if not all(isinstance(x,dict) for x in (forecast,observation,mapping)):raise ValueError('missing_pair_or_mapping')
    if mapping.get('verified') is not True or not isinstance(mapping.get('evidence'),str) or not mapping['evidence'].strip():raise ValueError('unverified_mapping')
    station=mapping.get('station_id')
    if not isinstance(station,str) or not station.strip() or any(x.get('station_id')!=station for x in (forecast,observation)):raise ValueError('station_mismatch')
    provider,model=forecast.get('provider'),forecast.get('model')
    if not all(isinstance(x,str) and x.strip() for x in (provider,model)):raise ValueError('missing_provider_or_model')
    variable=forecast.get('variable')
    if not isinstance(variable,str) or variable not in UNITS:raise ValueError('unsupported_variable')
    if observation.get('variable')!=variable:raise ValueError('variable_mismatch')
    if any(x.get('units')!=UNITS[variable] for x in (forecast,observation)):raise ValueError('incompatible_units')
    if observation.get('quality')!='verified':raise ValueError('unverified_observation')
    if not all(number(x.get('value')) for x in (forecast,observation)):raise ValueError('missing_or_nonfinite_value')
    if variable!='temperature_2m' and any(x['value']<0 for x in (forecast,observation)):raise ValueError('negative_amount_or_speed')
    origin=timestamp(case.get('forecast_origin'))
    # Legacy issued_at was an initialization reference, not proven publication.
    time_basis='explicit_initialization' if forecast.get('initialized_at') is not None else 'legacy_issued_at_assumed_initialization'
    issued=timestamp(forecast.get('initialized_at') if forecast.get('initialized_at') is not None else forecast.get('issued_at'))
    if forecast.get('initialized_at') is not None and forecast.get('issued_at') is not None and timestamp(forecast['issued_at'])!=issued:raise ValueError('ambiguous_legacy_initialization')
    retrieved=timestamp(forecast.get('retrieved_at'))
    published=timestamp(forecast['published_at']) if forecast.get('published_at') is not None else None
    if published is not None and not issued<=published<=retrieved:raise ValueError('invalid_publication_order')
    available=timestamp(observation.get('available_at'))
    start,end=(timestamp(forecast.get(k)) for k in ('period_start','period_end'))
    observed_start,observed_end=(timestamp(observation.get(k)) for k in ('period_start','period_end'))
    if (start,end)!=(observed_start,observed_end):raise ValueError('period_mismatch')
    if end<start or (variable=='precipitation' and end==start) or (variable!='precipitation' and start!=end):raise ValueError('invalid_period')
    if issued>retrieved or retrieved>origin or origin>as_of or start<origin:raise ValueError('forecast_not_available_at_origin')
    if available<end or available>as_of or end>as_of:raise ValueError('observation_not_available_at_evaluation')
    lead=(end-origin).total_seconds()/3600
    group='0-24h' if lead<=24 else '24-72h' if lead<=72 else '72-168h' if lead<=168 else '>168h'
    key=(provider,model,station,variable,issued,start,end)
    error=forecast['value']-observation['value']
    if not math.isfinite(error):raise ValueError('nonfinite_error')
    truth_key=(station,variable,UNITS[variable],start,end)
    # Revisions are explicit: do not choose a truth value by input order.
    truth_version=(observation['value'],observation.get('source_id'),observation.get('revision'))
    if any(v is not None and not isinstance(v,str) for v in truth_version[1:]):raise ValueError('invalid_observation_identity')
    run_lead=(end-issued).total_seconds()/3600
    return dict(key=key,group=(provider,model,variable,UNITS[variable],group,(end-start).total_seconds()/3600),error=error,
        truth_key=truth_key,truth_version=truth_version,cohort_key=(truth_key,origin),
        decision_lead_hours=lead,initialization_lead_hours=run_lead,run_age_at_origin_hours=(origin-issued).total_seconds()/3600,time_basis=time_basis)

def evaluate(document):
    if not isinstance(document,dict) or type(document.get('schema_version')) is not int or document['schema_version']!=1 or not isinstance(document.get('cases'),list):raise ValueError('Expected schema_version 1 and cases array')
    as_of=timestamp(document.get('evaluation_as_of'));candidates=[];excluded=Counter()
    for case in document['cases']:
        try:candidates.append(checked(case,as_of))
        except ValueError as exc:excluded[str(exc)]+=1
    counts=Counter(row['key'] for row in candidates)
    truths=defaultdict(set)
    for row in candidates:truths[row['truth_key']].add(row['truth_version'])
    groups=defaultdict(list);accepted=[]
    for row in candidates:
        if len(truths[row['truth_key']])>1:excluded['conflicting_observation_truth']+=1
        elif counts[row['key']]>1:excluded['duplicate_forecast_target']+=1
        else:groups[row['group']].append(row);accepted.append(row)
    def scores(rows):
        n=len(rows)
        return dict(matched_cases=n,mae=math.fsum(abs(r['error'])/n for r in rows),bias=math.fsum(r['error']/n for r in rows))
    metrics=[]
    for (provider,model,variable,units,lead,duration),rows in sorted(groups.items()):
        entry=dict(provider=provider,model=model,variable=variable,units=units,lead_group=lead,period_hours=duration,**scores(rows))
        for field in ('decision_lead_hours','initialization_lead_hours','run_age_at_origin_hours'):
            entry[field]=dict(min=min(r[field] for r in rows),max=max(r[field] for r in rows))
        entry['time_basis_counts']=dict(Counter(r['time_basis'] for r in rows))
        metrics.append(entry)
    # Comparisons use the same station/period/decision origin across every model
    # in a stratum. Multiple runs for one target are ambiguous, never cherry-picked.
    strata=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    for r in accepted:
        provider,model,variable,units,lead,duration=r['group']
        strata[(variable,units,lead,duration)][(provider,model)][r['cohort_key']].append(r)
    comparisons=[]
    for (variable,units,lead,duration),models in sorted(strata.items()):
        if len(models)<2:continue
        eligible={model:{k:v[0] for k,v in targets.items() if len(v)==1} for model,targets in models.items()}
        common=set.intersection(*(set(targets) for targets in eligible.values()))
        keys=sorted(common,key=str)
        cohort_hash=hashlib.sha256(json.dumps([str(k) for k in keys],separators=(',',':')).encode()).hexdigest()
        comparisons.append(dict(variable=variable,units=units,lead_group=lead,period_hours=duration,
            common_cases=len(keys),cohort_sha256=cohort_hash,
            model_metrics=[dict(provider=model[0],model=model[1],**scores([rows[k] for k in keys])) for model,rows in sorted(eligible.items())] if keys else []))
    return dict(schema_version=1,evaluation_as_of=as_of.isoformat(),input_cases=len(document['cases']),matched_cases=len(accepted),excluded_cases=sum(excluded.values()),exclusions=dict(sorted(excluded.items())),metrics=metrics,common_case_comparisons=comparisons,status='offline_evaluation_only',limitations=[
        'Mapping and observation verification are caller attestations, not independently verified here.',
        'Individual provider metrics can contain different cases. Common-case comparisons align targets and decision origins but do not establish statistical significance.',
        'Legacy issued_at is treated as an initialization reference, never proof of publication. Run age and initialization lead are reported separately.',
        'No training, calibrated probabilities, or operational warning validation is performed.'])

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
    try:
        rendered=json.dumps(evaluate(json.loads(args.input.read_text())),indent=2,allow_nan=False)+'\n'
        if args.output:
            if args.output.resolve()==args.input.resolve():raise ValueError('Output must not overwrite input evidence')
            args.output.write_text(rendered)
        else:print(rendered,end='')
    except (ValueError,OSError) as exc:parser.exit(2,f'Weather evaluation failed: {exc}\n')

if __name__=='__main__':main()
