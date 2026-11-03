# Next release: a validated flood-preparedness pilot

Prepared 30 September 2026. This is a proposed development plan, not a claim that a public warning service is ready.

## Decision

Focus the next release on one river basin and a small group of local reviewers. Select the basin using source access, gauge metadata, historical event coverage and a willing local partner. Do not select it solely from incident counts or promise national coverage before evaluating performance.

## Evidence behind the priorities

The saved analytical audit dated 2026-09-30T04:50:41Z covers 192 stations. Median collected measurement span is approximately 59.7 hours. Among 87 stations where damped trend was selected and at least eight held-out pairs were available, it beat persistence at 55 and performed worse at 32. These are station counts, not an average error across incompatible units, and not independent flood events. They demonstrate that model selection on earlier observations does not guarantee later improvement.

Current weather inputs are seven city points, separate from the river model. The current models have no catchment rainfall-to-runoff or downstream routing component. Station units, datum and reference thresholds still lack independent verification. The initial archive scheduler runs daily, while the complete collection/prediction workflow can be run manually. Neither constitutes continuously operated emergency monitoring.

Source for local findings: `disaster_lab/reports/analytical-validation.json` and `disaster_lab/METHODS.md`.

## Ordered work packages

| Priority | Deliverable | Evidence required to advance |
|---|---|---|
| 1 | Complete prediction-verification service | Every saved forecast has its original inputs, creation/target times and model version; all matured forecasts are evaluated or explicitly marked unmatched; no 100-row display cap limits evaluation |
| 2 | Station registry and dependable ingestion | Units, vertical datum, station identity and dated thresholds have provenance; live collection, historical backfill and revisions are distinguishable; outages and measurement age are measured |
| 3 | Pilot-basin historical dataset | Several monsoon seasons where obtainable, significant floods and non-flood high-water events, original forecast runs or honestly labeled alternatives, documented gaps and independent event evidence |
| 4 | Rainfall-informed forecast candidates | Catchment-average forecast rainfall, upstream levels and wetness inputs linked to a runoff/routing or appropriately constrained statistical model; tested against existing baselines |
| 5 | Impact and preparedness workspace | Documented flood-hazard mapping linked to settlements and facilities; local reviewers verify shelters, closures and action guidance; uncertainty and dates are displayed |
| 6 | Supervised pilot | Forecasts first run privately alongside official information; missed events, false alarms, useful lead time and delivery/action outcomes are reviewed before any public service |

## First engineering sprint

1. Persist verification outcomes for the entire prediction archive, including the observation version used. Retain verification revisions when source observations change. The UI currently shows only the last 100 forecasts; keep that as pagination, never as an analytical limit.
2. Add per-station and per-horizon scorecards: sample size, errors, error-range coverage, time coverage, unmatched forecasts and comparisons with persistence. Separate retrospective tests from genuinely saved-ahead-of-time performance. Add event-level metrics only after verified event labels and thresholds exist.
3. Build a station metadata registry with unknown, source-supplied and independently-confirmed states. Store evidence and effective dates; do not silently promote source fields to verified truth.
4. Split small live observation updates from slower historical backfills and correction scans. Preserve raw evidence. Measure observation-to-retrieval delay for live collection separately from initial historical imports. Provider publication times remain null when unknown.
5. Add a supervised worker with bounded retries, idempotent jobs, concurrency locks, outage visibility and recoverable backups. Choose polling intervals from provider publication cadence and allowed access, rather than assuming faster polling creates fresher data.
6. Add a model registry with frozen versions and predeclared promotion criteria. Evaluate candidates on untouched flood events/seasons; use a fresh prospective period after any change guided by previous test results.

These software improvements can proceed locally. Paid hosting, data requests, organizational outreach and public delivery are separate deployment or partnership decisions, not actions performed by this plan.

## Better forecasting

- Obtain catchment boundaries and terrain, then calculate rainfall over each catchment rather than extrapolating a city-point forecast to a river basin.
- Include rainfall observations, forecast precipitation, antecedent wetness and upstream measurements where their units and timing are verified.
- Compare a simple calibrated runoff/routing model and a constrained statistical candidate against persistence. More complicated models must earn promotion through independent results.
- Treat 6–24-hour lead times as research targets whose usefulness depends on basin response and forecast skill, not promised service levels.
- Use forecast ensembles and calibrate uncertainty when enough independent data exist. Two-model disagreement alone is not a probability distribution.
- Evaluate misses, false alarms, peak timing, actionable lead time and calibration during important events, in addition to mean level error. Define acceptable tradeoffs with local users before the final test.

## Product and community work

The main screen should answer: What changed? Where? Over what period? How strong is the evidence? Which locally reviewed action follows?

A pilot interface should include basin/station navigation, rainfall and level timelines, official source notices kept distinct from experimental projections, an event replay, forecast-versus-outcome scorecards and verified local resources. Do not infer safe evacuation routes from an ordinary road map or inundation depths from an unverified gauge datum.

The user's most useful non-monetary contribution is helping identify a local hydrologist or university reviewer and a municipality or community group willing to test the workflow. They can help confirm station metadata, document past inundation, check preparedness guidance and evaluate whether messages would arrive early enough to change a decision. Collect only necessary field information and avoid exposing personal household details.

## Advancement gates

- **Data:** metadata, revisions, coverage and delivery latency are sufficiently understood for the intended decision.
- **Forecast:** improvement over baseline is demonstrated on untouched events and prospective records; sample size and uncertainty are reported.
- **Impact:** the relationship between predicted water conditions and affected places is validated locally.
- **Operation:** outages, backup restoration, delivery failures and message updates/cancellations have been exercised.
- **Action:** local reviewers understand the message and have a feasible response. A model score alone does not establish this.

Begin with engineering and data access in the first sprint. Historical backtesting depends on access to suitable records. A private shadow pilot can then accumulate prospective evidence; a few weeks without significant floods cannot validate severe-event reliability. Expansion to another basin or hazard depends on the gates above, not a calendar deadline.

## Primary references

- [DHM data-request process](https://www.dhm.gov.np/pages/how-to-request-data): an official route to request suitable historical records. Access, review and possible costs must be confirmed for the requested dataset.
- [WMO Early Warnings for All framework](https://wmo.int/resources/wmo-bulletin/wmo-bulletin-vol-72-1-2023/overview-of-early-warnings-all-executive-action-plan-2023-2027): risk knowledge, hazard monitoring/forecasting, communication and preparedness/response are complementary components.
- [WMO nowcasting and verification guidance](https://wmo.int/media/magazine-article/nowcasting-guidelines-summary): choose verification around user decisions and maintain representative forecast–observation records.
