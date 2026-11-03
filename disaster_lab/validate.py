"""Regenerate consistency audit and model-comparison artifacts from real data."""
import collections
import contextlib
import hashlib
import json
from pathlib import Path
import time
from analytics import analyze, quality_audit
from data import Dataset, now
from weather import ForecastStore, PLACES, normalize

if __name__=='__main__':
    dataset=Dataset().ensure();store=ForecastStore();stamp=time.time()
    out=Path(__file__).resolve().parent/'reports';out.mkdir(exist_ok=True)
    quality=quality_audit(dataset,stamp)
    checks=[]
    with contextlib.closing(store.db()) as db:
        database_check=db.execute('PRAGMA quick_check').fetchone()[0]
        for row in db.execute("SELECT * FROM weather_fetches WHERE status='ok'"):
            errors=[]
            try:
                raw=(store.raw/row['raw_file']).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=row['sha256']:errors.append('checksum mismatch')
                place=next(p for p in PLACES if p['id']==row['place_id'])
                if normalize(json.loads(raw),place)!=json.loads(row['normalized']):errors.append('normalized values differ')
            except (OSError,ValueError,StopIteration) as e:errors.append(str(e))
            checks.append({'fetch_id':row['id'],'place':row['place_id'],'model':row['model'],'errors':errors})
    analyses=[]
    for s in dataset.stations:
        a=analyze(dataset.river_groups[s['id']],60,stamp)
        analyses.append({'id':s['id'],'name':s['station_name'],**a})
    report={'generated_at':now(),'weather_database_check':database_check,'weather_raw_checks':checks,
            'quality':quality,'river_model_evaluations':analyses,
            'summary':{'stations':len(analyses),'selected_models':dict(collections.Counter(a['selected_model'] for a in analyses)),
                       'upcoming_projections':sum(a['projection'] is not None for a in analyses),
                       'stations_with_8_test_pairs':sum(a['test'].get('persistence',{}).get('pairs',0)>=8 for a in analyses)},
            'warning_accuracy_validated':False}
    (out/'analytical-validation.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (out/'weather-outlook.json').write_text(json.dumps(store.outlook(stamp),indent=2,allow_nan=False)+'\n')
    lines=['# Analytical release validation','',f'Generated {report["generated_at"]}','',
           f'- Weather SQLite check: {database_check}.',
           f'- {len(checks)} saved successful weather responses checked against original SHA-256 hashes and normalization.',
           f'- Weather integrity failures: {sum(bool(c["errors"]) for c in checks)}.',
           f'- {len(analyses)} river stations evaluated independently at a one-hour horizon.',
           f'- {report["summary"]["stations_with_8_test_pairs"]} stations have at least eight eligible held-out test pairs.',
           f'- {report["summary"]["upcoming_projections"]} upcoming projections passed the local freshness and evidence gates.',
           f'- {quality["counts"]["over_two_hours_old"]} stations have measurements more than two hours old.',
           '', 'Per-station errors, model selection results, test samples and provenance are in `analytical-validation.json`. No national mean error is computed; station units and datum are unconfirmed. Weather snapshots are in `weather-outlook.json`. These are development-time snapshots, not a live warning bulletin.', '',
           'Integrity checks verify saved bytes and transformations. Tests verify code behavior. Neither establishes physical accuracy or severe-event predictive reliability.', '']
    (out/'analytical-validation.md').write_text('\n'.join(lines))
    print(json.dumps({'weather_database_check':database_check,'weather_raw_checks':len(checks),
                      'weather_integrity_failures':sum(bool(c['errors']) for c in checks),**report['summary']},indent=2))
    raise SystemExit(1 if database_check!='ok' or any(c['errors'] for c in checks) else 0)
