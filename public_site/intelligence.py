"""Reproducible evidence briefs, not hazard probabilities or operational warnings."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

from health import epoch, report

ENGINE_VERSION = 'evidence-brief-1'
SECTORS = {
    'public': 'Verified local coverage and reviewed Nepali guidance',
    'government': 'Verified ward boundaries, assets, capacities and response procedures',
    'agriculture': 'Crop stage, soil, irrigation and locally reviewed agronomic thresholds',
    'hydropower': 'Verified catchments, gauges, rating curves and operating rules',
    'transport': 'Road topology and verified closures, bridges and slope conditions',
    'health': 'Local heat thresholds, facility capacity and authority guidance',
    'education': 'School locations, access conditions and continuity procedures',
    'water_sanitation': 'Network state and measured water quality',
    'tourism': 'Route elevation, current conditions and specialist review',
    'response': 'Verified needs, authorized reports and resource availability',
    'research': 'Approved station mappings and independent held-out observations',
    'environmental_assessment': 'Verified site assets and hazard/vulnerability methods',
}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def brief(snapshot, at=None, hours=24):
    """Bind every result to one validated snapshot and an explicit assessment time.

    This is snapshot replay, not reconstruction of source delivery before acquisition.
    A later snapshot cannot be used to reconstruct an earlier knowledge state.
    """
    at = dt.datetime.now(dt.timezone.utc).timestamp() if at is None else at
    # Persist the exact precision used by arithmetic so the exported cutoff replays.
    if isinstance(at, (int, float)) and not isinstance(at, bool):
        at = epoch(dt.datetime.fromtimestamp(at, dt.timezone.utc).isoformat())
    health = report(snapshot, at=at, hours=hours)
    if health['status'] == 'invalid':
        raise ValueError('Invalid evidence: ' + '; '.join(health['errors']))
    # Knowledge cannot be borrowed from even a slightly later publication.
    known_times = [snapshot['built_at'], snapshot['archive']['as_of']]
    known_times += [r['observed_at'] for key in ('rivers', 'rain_stations') for r in snapshot[key]]
    known_times += [stamp for w in snapshot['weather'] for stamp in (w['fetched_at'], w['latest_attempt']['fetched_at'])]
    known_times += [r['fetched_at'] for r in snapshot.get('discharge', [])]
    if snapshot.get('earthquakes'):
        known_times += [snapshot['earthquakes']['fetched_at']]
    known_times += [stamp for u in snapshot['updates'].values() for stamp in (u['attempted_at'], u['last_success_at']) if stamp]
    if any(epoch(stamp) > at for stamp in known_times):
        raise ValueError('Snapshot evidence was not available by assessment time')
    start = health['products']['weather']['window_start']
    weather = []
    for source, availability in zip(snapshot['weather'], health['products']['weather']['pairs']):
        points = {p['epoch']: p for p in source['normalized']['points']}
        window = [points.get(start + (i + 1) * 3600) for i in range(hours)]
        values = {}
        reasons = {}
        for variable in ('precipitation', 'temperature_2m', 'wind_gusts_10m'):
            available = availability['recent'] and availability['complete_horizon'][variable]
            if not available:
                values[variable] = None
                reasons[variable] = 'stale_retrieval' if not availability['recent'] else 'incomplete_window'
                continue
            series = [p[variable] for p in window]
            values[variable] = ({'total': sum(series), 'unit': 'mm'} if variable == 'precipitation' else
                                {'minimum': min(series), 'maximum': max(series), 'unit': '°C'} if variable == 'temperature_2m' else
                                {'maximum': max(series), 'unit': 'm/s'})
        weather.append({
            'kind': 'provider_forecast', 'place_id': source['place_id'], 'model': source['model'],
            'source_response_sha256': source['sha256'], 'retrieved_at': source['fetched_at'],
            'initialized_at': source['normalized']['model_issued_at'],
            'initialization_note': 'Rolling response does not establish model initialization time.',
            'provenance_note': 'Source hash reference from snapshot; this brief does not reverify raw response bytes.',
            'latest_attempt_failed': availability['latest_failed'], 'values': values, 'withheld': reasons,
        })
    rivers = health['products']['river']
    result = {
        'schema_version': 1, 'engine_version': ENGINE_VERSION,
        'assessed_at': health['checked_at'], 'snapshot_built_at': snapshot['built_at'],
        'snapshot_sha256': digest(snapshot), 'assessment_type': 'dated_evidence_brief',
        'availability': health, 'weather_window': {
            'start': dt.datetime.fromtimestamp(start, dt.timezone.utc).isoformat(),
            'end': dt.datetime.fromtimestamp(start + hours * 3600, dt.timezone.utc).isoformat(),
            'hours': hours, 'precipitation_semantics': 'Each endpoint represents the preceding hour.'},
        'weather': weather,
        'river_review': {
            'stored': rivers['stored'], 'recent': rivers['recent'],
            'recent_nonconflicting_levels': rivers['usable_levels'],
            'conflicting_stations': sum(r['conflicting'] for r in snapshot['rivers']),
            'missing_levels': sum(r['level'] is None for r in snapshot['rivers']),
            'threshold_assessment': 'unavailable_unconfirmed_units_and_thresholds'},
        'sector_readiness': [
            {'sector': sector, 'status': 'context_only', 'missing_evidence': evidence,
             'impact_assessment': 'not_established'} for sector, evidence in SECTORS.items()],
        'release': {'public_research_information': True, 'validated_local_prediction': False,
                    'operational_warnings': False, 'institutional_endorsement': False},
        'limitations': list(snapshot['limitations']) + [
            'This brief is dated; its availability assessment does not update after export.',
            'No official warning lifecycle is ingested here; consult DHM directly.',
            'No exposure, damage, safe-route or evacuation assessment is established.',
            'Snapshot digest identifies normalized evidence, not the original HTTP bytes.',
            'Snapshot build time is not proof of deployment or delivery to a user.',
        ],
        'official_information_url': 'https://dhm.gov.np/',
    }
    result['brief_id'] = digest(result)
    return result


def markdown(value):
    lines = ['# TerraRaksha — dated situation brief', '',
             f"Assessment time (UTC): {value['assessed_at']}",
             f"Snapshot built at: {value['snapshot_built_at']}",
             f"Brief ID: `{value['brief_id']}`", '',
             '**Research information. Not a warning or a validated local impact prediction.**', '',
             f"Configured data availability: **{value['availability']['status']}**. This is not a safety rating.", '',
             '## Weather outlook evidence', '',
             f"Window: {value['weather_window']['start']} to {value['weather_window']['end']}.", '',
             '| Location / model | Rain total (mm) | Temperature range (°C) | Maximum gust (m/s) |',
             '| --- | --- | --- | --- |']
    for w in value['weather']:
        v = w['values']; rain = v['precipitation']; temp = v['temperature_2m']; gust = v['wind_gusts_10m']
        lines.append(f"| {w['place_id']} / {w['model']} | " +
                     (f"{rain['total']:.1f}" if rain else 'Withheld') + ' | ' +
                     (f"{temp['minimum']:.1f}–{temp['maximum']:.1f}" if temp else 'Withheld') + ' | ' +
                     (f"{gust['maximum']:.1f}" if gust else 'Withheld') + ' |')
    lines += ['', 'Two model outputs are not probabilities or independent confirmation. Per-variable withholding reasons, retrieval times and failed attempts are in the JSON brief.', '',
              '## River evidence', '',
              f"{value['river_review']['recent']} of {value['river_review']['stored']} stored stations have recent timestamps; "
              f"{value['river_review']['conflicting_stations']} have conflicting latest levels. Units and thresholds remain unconfirmed.", '',
              '## Sector assessment gaps', '']
    lines += [f"- {s['sector']}: context only; requires {s['missing_evidence']}." for s in value['sector_readiness']]
    lines += ['', '## Limits', ''] + ['- ' + x for x in value['limitations']]
    lines += ['', '[Check official DHM information](https://dhm.gov.np/).', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--at', help='Timezone-aware assessment time for replay')
    parser.add_argument('--hours', type=int, default=24)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    from pipeline import write
    outputs = (args.output.resolve(), args.output.with_suffix('.md').resolve())
    if args.snapshot.resolve() in outputs or outputs[0] == outputs[1]:
        parser.error('Output paths must differ from input evidence and each other')
    if any(path.exists() for path in outputs):
        parser.error('Output already exists; choose new paths to preserve prior briefs')
    result = brief(json.loads(args.snapshot.read_text()), epoch(args.at) if args.at else None, args.hours)
    write(args.output, result)
    args.output.with_suffix('.md').write_text(markdown(result))


if __name__ == '__main__':
    main()
