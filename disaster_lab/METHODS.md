# Nepal Disaster Lab — implemented methods

River methods originally documented 30 September 2026 UTC; weather acquisition and verification documentation reconciled 15 November 2026. The research service provides weather outlooks and experimental station-level modeling. It does not estimate validated disaster probabilities or issue public warnings. Consistency checks cannot establish that a source measurement is true.

## Weather: two explicitly selected forecast models

The collector requests ECMWF IFS 0.25° (`ecmwf_ifs025`) and NOAA GFS global (`gfs_global`) through Open-Meteo. Seven approximate city coordinates provide illustrative coverage: Kathmandu, Pokhara, Biratnagar, Janakpur, Nepalgunj, Birendranagar and Dhangadhi. These points are not surveyed stations, catchment averages, administrative polygons or nationwide coverage.

Each source response is saved unchanged, SHA-256 hashed, and linked to its request URL, retrieval timestamp and normalized values in SQLite. Single-location requests avoid positional ambiguity between places. The normalizer requires expected units, an hourly ordered time axis, equal array lengths, plausible coordinate correspondence and finite numeric values. Nulls remain missing. Zero precipitation remains zero. Nonfinite and physically implausible values reject the whole response under the current normalized schema; diagnostic errors identify the variable, sample index/time, value and permitted bounds. Negative precipitation is not clamped to zero. Per-variable partial acceptance would require explicit quality provenance and a separately reviewed schema change. Failed attempts are recorded without replacing the last valid snapshot.

Forecast variables are total precipitation (mm of water equivalent, including snow), 2 m temperature (°C), and 10 m wind gusts (m/s). Precipitation labeled at time t covers the preceding hour. Summary windows start at the next whole UTC hour, so partially elapsed hours are excluded. A 24-hour total requires all 24 hourly amounts; a 72-hour total requires all 72. A missing hour never becomes a dry hour. The interface shows window boundaries in Nepal time. Values older than six hours since retrieval have their summary values withheld; six hours is a local display rule, not a provider guarantee. Stored charts remain inspectable with their age shown.

The rolling public endpoint does not provide a model run issuance timestamp. We preserve `model_issued_at = null`; retrieval time and the API's computation duration are not substituted for it. A separate implemented collector, `forecast_runs.py`, requests explicitly initialized original runs. Its `initialized_at` is the requested reference time, not publication time; `published_at` remains null when unknown. The request URL and returned time axis are checked, but the response does not independently echo the requested run identity. Acquiring an old run now does not establish that users had it at initialization.

The GitHub workflow invokes `public_site/weather_evidence.py` to attempt the latest six-hour initialization at least eight hours old. Successful per-location/model runs are deduplicated, failed requests retry no sooner than an hour, and missed initializations are not automatically backfilled. The original-run step has a six-minute budget; it may fail independently of otherwise valid public snapshot publication. See [original-run acquisition](ORIGINAL_RUNS.md).

Exact permitted weather response bytes, including error responses, are retained in attributed, content-addressed gzip envelopes on the data branch. Hashes bind the envelope and raw response; receipt validation requires a referenced evidence blob. Rolling responses also have a 90-day Actions recovery artifact when durable publication fails. This does not extend permission to publish raw BIPAD data and does not establish complete forecast-run coverage.

### Weather verification and geographic review

`weather_evaluation.py` implements offline matched-case evaluation with timezone-aware chronology, compatible units and accumulation windows, canonical observation-conflict exclusion, and identical-case provider comparisons. Reports distinguish decision lead, model initialization lead and run age. Legacy initialization assumptions remain labelled. Scores on different provider cohorts cannot establish a provider ranking. See [evaluation contract](WEATHER_EVALUATION.md).

`station_registry.py` inventories GHCNh station metadata, provenance and coordinate/elevation variants. It measures distances to requested city points, not native model cells, and never approves a mapping. The existing local inventory contains 17 candidate stations and zero verified mappings. See [station registry](STATION_REGISTRY.md). The evaluator's mapping and quality fields are caller attestations, not independent verification.

These implemented tools are a verification foundation, not evidence of locally improved weather skill. Verified station/grid representativeness, compatible independent observations, chronological/geographic holdouts, uncertainty and extreme-event evaluation remain required. No real Nepal-wide forecast accuracy score or calibrated flood probability has been established.

The two-model range and absolute difference are descriptive comparisons, not ensemble probabilities or confidence intervals. Both models may share errors. Hourly output may be interpolated from coarser native timesteps. Mountain rainfall extremes and local flash flooding may be unresolved. Rainfall is not converted directly into flood severity.

Primary provider documentation and terms:

- [Open-Meteo ECMWF documentation](https://open-meteo.com/en/docs/ecmwf-api): selected model, native resolution and temporal interpolation.
- [Open-Meteo NOAA GFS documentation](https://open-meteo.com/en/docs/gfs-api): variables and forecast models.
- [Open-Meteo terms](https://open-meteo.com/en/terms): free API for non-commercial use, rate limits, CC BY 4.0 attribution and availability limitations. The current research collection uses that access; commercial use of the hosted service requires an appropriate permitted arrangement. Open data licensing and hosted API access terms are separate.
- [ECMWF open data](https://www.ecmwf.int/en/forecasts/datasets/open-data): underlying public forecast products.

Collector policy: at most three concurrent requests; fourteen requests on a full uncached collection; successful pairs cached for one hour and failed pairs for five minutes. Manual refresh runs observation and weather collection, then saves all eligible 30-minute, 1-hour and 3-hour river projections. The previously configured daily archive automation continues collecting the observation archive; use the complete refresh command for both datasets. This is not continuous emergency monitoring.

## River models: one station and one horizon at a time

Two deliberately simple candidates are implemented in `analytics.py`, version `river-local-v2.0`:

1. **Persistence:** future level equals the latest observed level.
2. **Damped local trend:** ordinary least squares slope over the preceding three hours, anchored at the latest observed level. The rate decays exponentially with a fixed two-hour time constant. Prediction = latest level + slope × 2 × (1 − exp(−h/2)), with h in hours and slope in source units/hour. The window needs at least four measurements spanning at least 45 minutes, with no internal gap greater than one hour.

Parameters are fixed research choices, not locally calibrated hydrological constants. The models do not ingest rainfall, catchment geometry, soil moisture, discharge rating curves, upstream routing, snowmelt or infrastructure operations. Weather outlooks are displayed separately. A forecast of water level is not a forecast of affected homes.

For each station, finite timestamp/value pairs are ordered and identical timestamps deduplicated deterministically. Conflicting values at one timestamp block upcoming predictions rather than silently treating the last value as verified. Null and non-finite levels are excluded and counted. Recent constant levels and large steps are review flags; neither is automatically deleted because real hydrology can produce them. The large-step rule is ten scaled median absolute deviations of successive changes; if that deviation is zero, the test is unavailable, not passed.

### Chronological evaluation

The observed time span is divided into 60% model selection, 20% residual-range calibration and 20% final testing. Targets crossing boundaries are removed. Forecast origin windows do not overlap, although temporal dependence remains. Target matching takes the first observation at/after the requested horizon, no later than half the typical sampling interval or 30 minutes, whichever is smaller. No distant later observation stands in for the intended target.

Candidate predictions use only values at/before each origin. Both candidates are compared on the same eligible origin-target pairs. Selection chooses damped trend only when there are at least 12 selection pairs and its MAE improves on persistence by more than 2%; otherwise persistence remains selected. The final test scores do not select or tune the model. A selected model may perform worse on the final test, and the interface displays that result.

A signed-error range uses the 10th and 90th nearest-rank percentiles from the separate calibration period. Adding these to a new point prediction gives an empirical prior-error range. It is not a calibrated probability guarantee, especially with few samples, flat sensors or changing river conditions. Held-out coverage is reported to reveal failures. Test skill = 1 − selected-model MAE / persistence MAE; it is undefined when persistence MAE is zero. Errors remain in unconfirmed source units and are never pooled across stations.

This evaluation is **retrospective measurement-time** evaluation. It uses current archive revisions and does not establish what the provider had delivered at historical origins. The separate replay page can reconstruct what this archive had actually seen at a historical cutoff, including corrections and reversions. Neither workflow reconstructs instrument availability before this archive existed.

### Upcoming projections and prospective records

A projection's origin is the latest measurement time, not the time you open the page. Its target is origin + 30, 60 or 180 minutes; the remaining lead time is shown. The system withholds upcoming predictions if the measurement is over two hours old, the target is already past, future-dated or contradictory station measurements exist, the selected model cannot use recent inputs, or minimum counts are unmet (12 selection, 8 calibration and 8 final-test pairs).

Eligible projections are saved immutably before their target time, both in the complete refresh workflow and when inspected in the forecast studio. The write itself checks the target has not expired during computation. The identifier binds station, horizon, model version and a hash of the cleaned input series. Repeated views do not overwrite the first result for those inputs. The evidence-health page matches saved projections to later archived observations using the same target tolerance. The verification is recomputed against current observation revisions and can change after a source correction. It is not yet a multi-season performance study. Withheld projections are not added as successful forecasts.

## What accuracy checks do and do not establish

- The archive preserves raw responses, record versions and changes. `python3 disaster_archive/archive.py verify` checks SQLite integrity and retained raw checksums.
- Weather normalization checks units, arrays, location and time consistency; `python3 disaster_lab/validate.py` verifies its stored raw hashes and regenerates the quality/model audit.
- Automated tests cover future-data exclusion, partition isolation, revision replay, target matching, missing values, stale forecasts, source failures, storage and HTTP protections.
- Browser checks cover the actual UI, forecast controls, filters, exports, persistence, network failure and mobile overflow.
- These checks establish software behavior and provenance. They do not verify each gauge, show that all incidents were reported, or prove predictions are accurate during severe floods.

Operational flood warnings still require origin-provider confirmation of units/datums and dated thresholds, multiple seasons of event histories, independent impact observations, catchment/runoff modeling, event-level validation, reliable low-latency delivery and local response procedures. Earthquake occurrence cannot be reliably predicted as an exact place/time/magnitude forecast; earthquake catalogs are observations of events already detected. Landslide, glacial-lake and other hazard models need their own data and validation. The UI makes no all-hazard prediction claim.


## Prospective verification update

The production worker now verifies all saved predictions, not just the visible ledger page. Every changed verification outcome is retained in `outcome_history`, including a source observation ID and version where available. Missing or contradictory observations are not scored. Metrics are grouped by station, horizon, model and version; no errors are pooled across unconfirmed source units. Repeated/overlapping targets are dependent samples. These prospective metrics complement the existing chronological retrospective tests and do not validate warning thresholds or disaster impacts.
