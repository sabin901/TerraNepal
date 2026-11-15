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
