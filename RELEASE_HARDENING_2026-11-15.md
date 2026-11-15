# Release hardening — 15 November 2026

This implements the first corrective actions from RELEASE_EVALUATION_2026-11-15.md.
It does not reverse the NO-GO verdict for an authoritative forecasting service.

## Implemented and checked

- Forecast expiry recalculates with focus inside the weather view; control focus,
  expanded data disclosures and table position survive refresh.
- Mobile outage output links directly to official DHM information. Keyboard location
  selection retains its logical focus. Charts have expandable equivalent data tables.
- Five-minute future clock-skew tolerance is consistent across public health/display;
  genuinely invalid health prevents a new artifact. Degraded partial data remains dated
  and publishable. Future station rows are quarantined, not turned into observations.
- Canonical conflicting observation truth is excluded across providers and model runs.
  Common-case comparisons use identical station/time/origin cohorts. Run age, decision
  lead and initialization lead are separate. No real skill score is claimed.
- Original-run initialization is separated from unknown publication time. Broad physical
  plausibility and elevation checks reject suspect records while retaining response bytes.
- GitHub collection retains exact attributed weather response bodies and attempts mature
  initialized research runs. A durable data-branch receipt must reference an existing blob.
  Failure-path rolling evidence has a 90-day recovery artifact; BIPAD raw is not republished.
- Current-tree storage accounting and an explicit recovery procedure are documented.
- A reproducible station candidate registry retains hashes, metadata variants and distances
  to requested city points. Seventeen stations were inventoried locally; none is auto-approved.

## Verification evidence

60 public Python tests, 114 research Python tests, and 29 JavaScript assertions pass.
Git data-branch roundtrip tests recover byte-identical weather responses, reject tampering
and missing receipt blobs, and exercise concurrent original-run identity handling.
Browser checks reproduced and then verified the focus/expiry and mobile fallback fixes.
The checked fixture advanced retrieval age from 5h59m to 6h01m while a control stayed focused;
precipitation/gust numbers became withheld and focus stayed on that same control.

A live standalone archive trial retained 14 original-run responses: 10 accepted, four errors.
These are availability results, not forecast accuracy. The scheduled workflow provides
best-effort acquisition, not uninterrupted or complete model-run coverage.

## Still blocked by evidence or remaining implementation

Verified station/grid approval, prospective matched observations, independent seasonal and
extreme-event evaluation, calibrated corrections, rainfall/gust verification, hydrological
units/reaches/thresholds, broad sector features and Nepal user validation remain outstanding.
Station metadata consistency alone cannot approve a match. The evaluator still trusts caller
mapping attestations until an independently reviewed registry is connected.

Automatic BIPAD raw redistribution is unresolved; public corrections beyond the bounded
reconciliation window may be missed. Same-time competing measurements remain withheld until
reviewed. No automatic history deletion/rotation or independent scheduler monitor is added.
GitHub-only operation remains best effort. No public warnings are issued.
