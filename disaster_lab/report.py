#!/usr/bin/env python3
"""Reproduce the station baseline evaluation and a factual research handover."""
from pathlib import Path
import collections
import json
from data import Dataset,now

if __name__=='__main__':
    d=Dataset();o=d.overview();health=d.source_health();evaluation=d.report()
    out=Path(__file__).resolve().parent/'reports';out.mkdir(exist_ok=True)
    (out/'river-baseline-evaluation.json').write_text(json.dumps(evaluation,indent=2)+'\n')
    valid=sum(s['pairs']>0 for s in evaluation['stations'])
    comparable=sum(s['points']>=48 and s['span_hours']>=24 and s['max_gap_minutes'] is not None and s['max_gap_minutes']<=60 for s in o['stations'])
    lines=['# Research handover','',f'Generated: {now()}','',
           'The local research application is implemented. Hazard prediction and public warnings remain unvalidated.','',
           '## What the current evidence supports','',
           f"- {o['counts'].get('bipad:incident',0):,} source incident reports, dated {o['date_start']} to {o['date_end']}.",
           f"- {len(o['stations'])} river station identifiers with usable timestamp/value pairs.",
           f'- {comparable} stations with at least 48 distinct observations, at least 24 hours of span and no observed internal gap over 60 minutes. This is a coverage screen only.',
           f'- {valid} stations support at least one matched one-hour persistence evaluation pair.',
           f"- {o['counts'].get('bipad:alert',0):,} source message records retained. The collection is deliberately bounded, not a complete national warning service.",
           '', '## Basin data coverage', '', '| Source basin label | Stations | Median observed span (hours) | Numeric source reference thresholds |', '|---|---:|---:|---:|']
    for r in o['basins']:
        lines.append(f"| {r['basin']} | {r['stations']} | {r['median_span_hours']:.1f} | {r['with_reference_threshold']} |")
    lines += ['', 'Labels are retained verbatim; similarly named basins may need reviewed reconciliation. These counts do not rank hazard, exposure or overall model readiness.', '',
              '## Baseline result interpretation', '',
              'The JSON report contains station-specific one-hour persistence errors, matched pair counts and skipped origins. No national mean error is calculated because station units/datums remain unconfirmed. Overlapping pairs are correlated and are not independent disaster events. The short observation window and absence of verified flood outcomes prevent a defensible warning-accuracy claim.', '',
              '## Next scientific work', '',
              '1. Choose one basin and a participating local reviewer; use station coverage to identify feasible candidates, not to infer which community is most at risk.',
              '2. Confirm station units, datum, rating curves and dated warning thresholds with the originating provider.',
              '3. Obtain multiple seasons of observations, preserved forecast runs, terrain/catchments and independent event outcomes.',
              '4. Compare a local model to the persistence baseline with event/season holdouts, probability calibration and measured delivery delay.',
              '5. Establish locally tested instructions and opt-in delivery before operational use.', '',
              'The software demonstration, source-message display and data archive are useful now. These remaining dependencies are scientific and operational work; they are not resolved by adding a generic AI model.', '']
    (out/'research-handover.md').write_text('\n'.join(lines))
    print(json.dumps({'stations':len(o['stations']),'stations_with_evaluation_pairs':valid,'coverage_screen':comparable,'report':str(out/'research-handover.md')},indent=2))
