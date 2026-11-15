# TerraNepal weather engine specification

Status: implementation contract, 15 November 2026. Research foundations are being
implemented; the complete engine is not yet delivered. No trained weather
model or demonstrated skill improvement is claimed. No external collaboration
or outreach is required for this research work.

## Objective

Provide traceable Nepal weather forecasts by combining established numerical
weather predictions with quality-controlled local observations and statistical
post-processing. Keep raw provider forecasts available as baselines and fallbacks.
Use one shared engine for public and sector views. Weather alone does not predict
road closures, crop losses, hydropower output or flood impacts.

## Existing foundation and gaps

The repository already collects ECMWF IFS and GFS forecasts at seven illustrative
city points. Local weather normalization includes temperature, precipitation and
gusts. It preserves raw responses and missing values. The existing river lab has
chronological and prospective evaluation machinery, but its water-level trend
models are not atmospheric weather models.

The current weather endpoint does not identify model issue time. Retrieval time
must never be substituted for initialization time. Independent, quality-controlled
temperature/wind observations and a verified rainfall station register are not
yet established as a nationwide training dataset. Public river/rain units and
accumulation semantics remain unconfirmed. Resolve these before training on them.

## Nepal context

Represent elevation, model-grid elevation mismatch, terrain exposure, region,
season, local hour and forecast lead time. Evaluate separately across Terai,
hills and mountains, east/west regions and monsoon/non-monsoon conditions.
Investigate rain shadows and winter western disturbances. Geographic features
must come from documented datasets, not invented district-wide constants.

## Data contract

Forecast records: provider, model/version, run identifier, issue time, retrieved
time, valid start/end, lead time, member, requested and returned coordinates,
grid elevation when available, variable, units, value, quality flags, source hash.

Observation records: source, station ID, coordinates/elevation, variable, units,
measurement start/end, received time, revision, value, quality flags and hash.

Registry: station aliases, relocation history where known, measurement semantics,
licence, source terms, coverage and geographic mapping evidence.

Unknown timestamps/units remain null or explicitly unconfirmed. UTC is canonical;
Nepal time is presentation. Precipitation amounts require aligned accumulation
windows. Reanalysis and satellite estimates remain distinct from gauge truth.

## Candidate models

Temperature baseline: each unmodified provider and persistence/climatology where
the observation history permits. Candidate corrected blend:

    prediction(x,t,h) = sum_m w_m(g,h,v) * F_m(x,t,h) + b(g,h,v)
    w_m >= 0; sum_m w_m = 1

Here g is a documented geographic/seasonal grouping, h lead time and v variable.
Fit weights and bias only on past matched forecast/observation pairs, regularize
toward the uncorrected baseline, and shrink sparse groups toward broader groups.
There are no preset Nepal-wide weights, lapse rates or claimed improvements.
Elevation residual features may be tested; avoid correcting an adjustment the
provider already applied. Compare one-model correction before complex blending.

Rainfall uses a separate two-part model: calibrated probability of exceeding a
documented wet threshold and a nonnegative conditional amount distribution.
Candidate predictors include raw model amounts, genuine ensemble members, season,
terrain and antecedent observations available at issuance. Expected amount can be
P(wet)*E(amount|wet), but it is not a maximum, percentile or event guarantee.
Use separate calibration for each accumulation window. Two deterministic models
do not constitute a calibrated probabilistic ensemble. Preserve heavy-rain tails
and report extreme-event failures rather than smoothing them out of evaluation.

Wind/gusts require their own observation matching and model. Do not apply the
temperature formula blindly to gusts or precipitation. Experimental 0–6-hour
nowcasting requires sufficiently timely observations; it is not promised merely
because hourly model output exists.

## Validation and release gates

Keep chronological training, tuning/calibration and untouched test periods.
Add held-out locations and elevation bands. Prevent overlap of target windows
across splits and exclude inputs unavailable at forecast issuance. Record missing
targets and later revisions; distinguish retrospective from as-known evaluation.

Temperature/wind: MAE, bias and performance by lead time. Rain: amount error,
event detection, false alarms and missed events; Brier score/reliability for
probabilities and CRPS for predictive distributions. Report sample counts,
uncertainty, seasonal coverage and severe-event performance. Compare all candidates
on the same valid cases. Do not tune on the final test set.

Promote a corrected product only after predeclared evaluation shows useful skill
against the relevant raw-provider and simple baselines without unacceptable
event-performance regressions. Define acceptable error tradeoffs per use case
before examining final tests. Sparse evidence means provider-only output, not
fabricated confidence. Dry-season performance cannot validate monsoon extremes.

## Implementation dependencies

1. Diagnose schedule delivery and source failures; instrument per-source freshness.
2. Audit observation semantics and permitted data coverage.
3. Collect identifiable forecast runs and maintain the observation registry.
4. Implement matching, baselines and immutable evaluation reports.
5. Fit candidate corrections offline; run prospective shadow comparisons.
6. Publish only evidence-supported outputs, including fallback and quality state.
7. Connect all sector pages to this shared service, with extra inputs required
   for sector-specific impact calculations.

Each output carries model version, source runs, valid period, freshness, evaluation
coverage and whether it is raw-provider, experimental or locally evaluated.
Retain rollback versions and independently monitor publication age.

## Primary references

- https://old.dhm.gov.np/uploads/climatic/52837744climate-05-00004.pdf
- https://dhm.gov.np/climate-services/seasonal-outlook
- https://www.ecmwf.int/en/forecasts/datasets/open-data
- https://open-meteo.com/en/docs/single-runs-api
- https://open-meteo.com/en/docs/previous-runs-api
- https://open-meteo.com/en/docs/historical-forecast-api
- https://open-meteo.com/en/docs/ensemble-api
- https://www.ecmwf.int/sites/default/files/elibrary/2014/9607-calibration-medium-range-weather-forecasts.pdf

Check product coverage, access and service terms before ingestion. An open-data
licence does not guarantee free hosted processing or operational uptime.

## Implementation evidence, 15 November 2026

Original-run retrieval now preserves exact responses and an append-only fetch ledger
(`disaster_lab/forecast_runs.py`). NOAA GHCNh temperature parsing retains source
quality flags and excludes unconfirmed records from candidate evaluation
(`disaster_lab/ghcnh.py`). Downloaded Nepal records are delayed research inputs,
not real-time observations or an approved nationwide training set.

The public collector now emits a data-health report; the overview distinguishes
stored forecasts from recent, complete future windows. Hosting remains GitHub-only.
The configured schedule is not a delivery guarantee, and a job cannot independently
detect that its own scheduler stopped. Verified station-to-grid mappings, prospective
scoring, calibrated model corrections and sector-specific validation remain outstanding.
