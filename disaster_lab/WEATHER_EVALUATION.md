# Offline weather evaluation

`python3 disaster_lab/weather_evaluation.py paired.json --output report.json`

Input schema 1 contains `evaluation_as_of` and a `cases` array. Each case contains
`forecast_origin`, `mapping`, `forecast` and `observation`. See the explicitly
synthetic fixtures in `test_weather_evaluation.py` for the complete contract.

This is paired evaluation, not training, live forecasting or certification.
Mapping `verified: true` with evidence and observation `quality: verified` are
caller attestations. This module cannot verify those claims independently.
GHCNh candidates must not be promoted automatically. Source hashes and mapping
review records must accompany any real study outside this compact evaluator.

All timestamps are timezone-aware. Forecast issuance must precede retrieval,
which must precede forecast origin. Observations may arrive after forecast origin
but must exist by evaluation time. Retrospectively downloaded forecasts cannot
be presented as having been available before their actual retrieval time.

Temperature and wind speed are instantaneous. Precipitation requires equal,
positive accumulation windows. Canonical units are degC, m/s and mm, with no
implicit conversion. Wind gusts cannot substitute for wind speed. Lead groups
use period end minus forecast origin, with the upper boundary inclusive.
Accumulation durations remain separate. Duplicate forecast targets are excluded
entirely; changing the origin label does not bypass duplicate detection.

Output includes matched/excluded counts and exclusion reasons, MAE and signed
bias (forecast minus observation) by provider/model/variable/lead/duration.
Empty input produces no metric, not zero error. Different provider groups can
contain different cases; their scores alone must not be used to rank providers.

Still needed before claims of improved skill: verified station/grid mappings,
prospective paired observations, comparisons on identical cases, persistence and
climatology baselines, sample uncertainty, chronological and geographic holdouts,
and separate severe-event evaluation. No real accuracy score is claimed here.

## Audit hardening

Prefer forecast `initialized_at`, optional `published_at`, and `retrieved_at`.
Publication, when known, must lie between initialization and retrieval. For old
input fixtures only, `issued_at` remains accepted as a legacy initialization
reference; output counts explicitly label this assumption. It is never treated
as proof of publication. Metrics now report decision lead, initialization lead
and run age at decision origin as separate minimum/maximum ranges.

Canonical observation identity is station, variable, units and measurement
period, independent of provider and model run. Conflicting accepted values or
explicit source/revision identifiers exclude all corresponding candidate cases.
Observation `source_id` and `revision`, when supplied, must be strings. This is
conflict detection, not automatic revision selection or independent provenance
verification. Invalid cases are excluded by their own contract reason first.

`common_case_comparisons` uses the intersection of station/measurement-period/
decision-origin targets across every provider/model in each variable, units,
lead-group and accumulation-duration stratum. Multiple runs for a provider at
one comparison target are ambiguous and excluded from the comparison rather
than selecting the most favorable one. Empty intersections have no scores.
A cohort hash records the aligned target identities. These descriptive scores
do not establish statistical significance, national representativeness or skill
improvement. Individual-provider metrics retain their explicit separate cohorts.
