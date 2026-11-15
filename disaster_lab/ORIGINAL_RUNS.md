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

This is a local research collector, not yet a continuously scheduled archive.
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
