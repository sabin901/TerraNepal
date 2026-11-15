"""Read-only publication health; invoke independently of the collection scheduler."""
from __future__ import annotations
import argparse
import datetime as dt
import json
import math
from pathlib import Path
import sys

import pipeline

CLOCK_SKEW_SECONDS = pipeline.CLOCK_SKEW_SECONDS

def epoch(value):
    if not isinstance(value, str):
        raise ValueError('Expected timezone-aware timestamp')
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Timestamp has no timezone')
    return parsed.timestamp()

def freshness(value, at, limit):
    age = at - epoch(value)
    if age < -CLOCK_SKEW_SECONDS:
        raise ValueError('Future observation, retrieval or publication timestamp')
    return {'age_seconds': age, 'recent': age <= limit,
            'clock_skew_seconds': max(0, -age)}

def report(snapshot, at=None, publication_limit=7200, hours=24):
    """Health is data availability, never a disaster/sensor accuracy assessment."""
    result = {'status': 'invalid', 'errors': [], 'products': {}}
    try:
        at = dt.datetime.now(dt.timezone.utc).timestamp() if at is None else at
        if not isinstance(at, (int, float)) or isinstance(at, bool) or not math.isfinite(at):
            raise ValueError('Invalid check time')
        if not isinstance(hours, int) or isinstance(hours, bool) or not 1 <= hours <= 72:
            raise ValueError('Horizon must be 1–72 hours')
        if not math.isfinite(publication_limit) or publication_limit <= 0:
            raise ValueError('Publication limit must be positive and finite')
        pipeline.validate(snapshot)
        result['clock_skew_tolerance_seconds'] = CLOCK_SKEW_SECONDS
        result['checked_at'] = dt.datetime.fromtimestamp(at, dt.timezone.utc).isoformat()
        result['publication'] = freshness(snapshot['built_at'], at, publication_limit)
        result['publication']['limit_seconds'] = publication_limit
        result['archive'] = {'as_of': snapshot['archive']['as_of'], **freshness(snapshot['archive']['as_of'], at, publication_limit),
                             'note': 'Separately dated historical export; excluded from live health gate.'}
        products = result['products']
        for name, key in [('river', 'rivers'), ('rain', 'rain_stations')]:
            rows = snapshot[key]
            recent = sum(freshness(r['observed_at'], at, 7200)['recent'] for r in rows)
            usable = sum(freshness(r['observed_at'], at, 7200)['recent'] and r['level'] is not None and not r['conflicting'] for r in rows) if name == 'river' else None
            products[name] = {'stored': len(rows), 'recent': recent, 'usable_levels': usable,
                              'note': 'Rain reports timestamps only; units and sensor accuracy remain unverified.' if name == 'rain' else 'Unconfirmed units; no warning thresholds.'}
        start = math.ceil(at / 3600) * 3600
        weather = []
        for w in snapshot['weather']:
            fresh = freshness(w['fetched_at'], at, 21600)
            attempt = w['latest_attempt']
            if not isinstance(attempt, dict) or attempt.get('status') not in ('ok', 'error'):
                raise ValueError('Invalid latest weather attempt')
            freshness(attempt.get('fetched_at'), at, 21600)
            lookup = {p['epoch']: p for p in w['normalized']['points']}
            points = [lookup.get(start + (i + 1) * 3600) for i in range(hours)]
            complete = {key: all(p is not None and p[key] is not None for p in points)
                        for key in ('precipitation', 'temperature_2m', 'wind_gusts_10m')}
            weather.append({'place_id': w['place_id'], 'model': w['model'], **fresh,
                            'complete_horizon': complete, 'latest_failed': attempt['status'] == 'error',
                            'usable': fresh['recent'] and all(complete.values())})
        products['weather'] = {'expected': 14, 'stored': len(weather), 'recent': sum(w['recent'] for w in weather),
                               'usable': sum(w['usable'] for w in weather), 'latest_failed': sum(w['latest_failed'] for w in weather),
                               'horizon_hours': hours, 'window_start': start, 'window_end': start + hours * 3600, 'pairs': weather}
        for name, rows, limit in [('discharge', snapshot.get('discharge', []), 86400),
                                  ('earthquakes', [snapshot['earthquakes']] if snapshot.get('earthquakes') else [], 7200)]:
            products[name] = {'stored': len(rows), 'recent': sum(freshness(r['fetched_at'], at, limit)['recent'] for r in rows)}
            if name == 'discharge':
                products[name]['verified_reaches'] = sum(r['normalized'].get('reach_verified') is True for r in rows)
                products[name]['note'] = 'Mapping is separate from retrieval health; not validated flood predictions.'
        failed = []
        for name, update in snapshot['updates'].items():
            freshness(update['attempted_at'], at, publication_limit)
            if update['last_success_at'] is not None:
                freshness(update['last_success_at'], at, publication_limit)
            if update['state'] in ('failed', 'partial'):
                failed.append(name)
        result['latest_failed_or_partial_products'] = failed
        degraded = (not result['publication']['recent'] or products['weather']['usable'] != 14
                    or products['weather']['latest_failed'] > 0 or bool(failed)
                    or any(products[n]['recent'] == 0 for n in ('river', 'rain', 'earthquakes', 'discharge')))
        result['status'] = 'degraded' if degraded else 'healthy'
        result['note'] = 'Healthy means configured availability checks pass, not complete coverage or forecast accuracy. Individual stale stations remain counted.'
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        result['status'] = 'invalid'
        result['errors'].append(str(exc))
    return result

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path, help='Downloaded public snapshot JSON; no collection or writes occur')
    parser.add_argument('--at', help='Timezone-aware timestamp for deterministic replay; default current UTC')
    parser.add_argument('--publication-max-age-minutes', type=float, default=120)
    parser.add_argument('--hours', type=int, default=24)
    args = parser.parse_args(argv)
    try:
        value = json.loads(args.snapshot.read_text(), parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
        result = report(value, epoch(args.at) if args.at else None, args.publication_max_age_minutes * 60, args.hours)
    except (OSError, ValueError) as exc:
        result = {'status': 'invalid', 'errors': [str(exc)]}
    print(json.dumps(result, allow_nan=False, indent=2))
    return {'healthy': 0, 'degraded': 1, 'invalid': 2}[result['status']]

if __name__ == '__main__':
    sys.exit(main())
