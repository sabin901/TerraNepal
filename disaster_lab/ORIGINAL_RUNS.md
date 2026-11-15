# Original weather runs

`forecast_runs.py` retrieves one explicitly initialized ECMWF IFS 0.25° or GFS
forecast at one of the seven existing research locations. It preserves exact
response bytes by SHA-256 and an append-only SQLite fetch ledger, including
failed requests. It does not change the published rolling weather feed.

Example, from the repository root:

```sh
python3 disaster_lab/forecast_runs.py --root runtime/original-runs \
  --place kathmandu --model ecmwf_ifs025 --run 2026-11-15T00:00:00Z
```

Initialization is selected using the provider's documented `run` parameter; the
response does not independently echo it. The collector checks that the returned
time axis begins at or within one hour after the selected initialization and
applies the existing units, coordinates, hourly-array and numeric checks.
Preserve the URL as evidence of the request contract. This is not a guarantee
that the provider supplied the intended underlying model run.

Retrieval time records when this archive actually acquired the forecast.
Downloading an old run now does not prove it was available to users at its
initialization time. It cannot enter a prospective evaluation before acquisition.
Historical and prospective results must remain separate.

The standalone collector is now invoked by the GitHub Pages workflow through
`public_site/weather_evidence.py`. Each executed job requests the latest six-hour
initialization at least eight hours old, with at most three concurrent requests.
Successful requests for that initialization are deduplicated using durable receipts;
failed requests may retry after one hour. Missed initializations are not automatically
backfilled. This remains best-effort research acquisition, not complete coverage.
No observations or station mappings are fabricated. Training is blocked until
compatible, quality-controlled observations and mapping evidence are supplied.

Reference: https://open-meteo.com/en/docs/single-runs-api

## Scheduler investigation, 15 November 2026

The public GitHub REST API returned 60 runs in total, of which 46 were scheduled.
Across those scheduled runs (3–15 November UTC), the median interval was
385.58 minutes and the maximum was 623.98 minutes. The remote default-branch
workflow matches the local file and is active, with `17,47 * * * *` configured.
The cause of sparse triggers remains unresolved. No cadence guarantee should be
made from configuration alone. A monitor running under the same scheduler is
not independent protection against scheduler outages.

These are observed trigger intervals, not source-observation intervals or proof
of permanent data loss. Retries cannot recover a workflow that never started.
Sources: GitHub repository Actions API and default-branch workflow contents.

## Scientific metadata and quarantine policy

New normalized runs use `initialized_at` for the requested model reference time,
`published_at: null` when actual publication is unknown, and the deprecated
`model_issued_at: null`. Existing SQLite rows remain immutable; older rows that
stored initialization in `model_issued_at` must be interpreted using their stored
`requested_run` and time note, never as proven publication. Retrieval remains a
separate ledger timestamp. No existing ledger column or collector call changed.

The shared normalizer quarantines nonfinite or out-of-envelope numeric values:
2 m temperature -100 to 70 degC, hourly precipitation 0 to 2000 mm and gust 0 to
150 m/s. These deliberately broad local screening limits are neither climate
ranges nor warning thresholds; flagged responses require investigation and exact
raw bytes are retained. Nothing is clamped. Missing values stay null. Non-null
returned target elevation must be numeric and within -500 to 9000 metres.

Both currently supported coarse global model identifiers use an explicit 0.5
latitude/longitude degree envelope around the requested point. This is a gross
mismatch check accommodating terrain-based cell selection, not station mapping
approval; even an accepted displacement can span a different Nepal valley.
Unknown model policies are rejected when a model is supplied. Legacy normalizer
callers without a model retain the same coarse envelope. A reviewed station/grid
register is still required before scientific comparisons. Returned `elevation`
is provider target/downscaling elevation, not verified native grid height.

## Durable public weather evidence

Exact response bytes (including source errors) are base64 encoded inside attributed,
content-addressed gzip envelopes on `codex/data-snapshots` under `evidence/weather/`.
Rolling weather responses are retained even if final snapshot validation fails,
with a 90-day Actions recovery artifact when durable publication cannot proceed.
Successful data-branch publication is the durable path; artifacts alone are not
permanent retention. BIPAD raw records are outside this publication contract.
The original-run step has a six-minute budget and failure does not block otherwise
valid public weather publication. Diagnostics must be checked separately.
