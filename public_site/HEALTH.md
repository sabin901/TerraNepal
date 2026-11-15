# Independent data-health check

`health.py` reads a downloaded public snapshot without running collection,
publishing, changing state or contacting services. The current deployment stays
GitHub-only: no external monitor or notification service is provisioned or planned
for this release. A report produced by the collection job cannot detect that
same job failing to start. The CLI can also be run manually; detecting a stopped
scheduler automatically would require an independently triggered check in a
separately agreed future scope.

```sh
curl --fail --silent --show-error --max-time 30 https://sabin901.github.io/TerraNepal/data/snapshot.json -o /tmp/terranepal-snapshot.json &&
python3 public_site/health.py /tmp/terranepal-snapshot.json
```

The monitor must treat **download failure as failure**, and only execute the
check after a successful download. Do not silently reuse an old temporary file.
No credentials are needed. Exit codes: 0 availability checks pass, 1 degraded,
2 invalid input or inaccessible file. Output is machine-readable JSON.

Defaults: publication age at most 120 minutes; river/rain observations at most
two hours; weather retrieval at most six hours; earthquake retrieval at most two
hours; discharge retrieval at most 24 hours. These are explicit local policies,
not guarantees of source timeliness or accuracy. Use
`--publication-max-age-minutes` to set the publication policy and `--hours`
(1–72) for the weather horizon. `--at` accepts a timezone-aware timestamp for
replay; omit it for operational monitoring.

Weather reports separately count stored pairs, recent retrievals, complete
future horizons for each variable, usable pairs and latest failed attempts.
Failure of a recent attempt does not erase a still-usable earlier forecast.
Complete windows follow the public display: whole future hourly intervals,
precipitation labeled by the interval end; missing values remain missing.
Fourteen pairs are expected. No provider issuance time is invented.

The shared clock-skew allowance is 300 seconds for publication, observation,
retrieval and attempt timestamps. A timestamp more than 300 seconds ahead
makes the report invalid. Within the allowance, the original negative age is
retained and `clock_skew_seconds` reports it explicitly; no timestamp is rewritten.
Invalid schema also makes the report invalid. Future forecast valid times are expected.
Missing products, zero recent observations for a product, missing usable weather
pairs, stale publication or a failed/partial latest update cause degradation.
Individual stale stations remain visible in counts; they do not alone make all
products unavailable. Schema-1 snapshots lack the later earthquake/discharge
products and therefore degrade. Discharge mapping readiness is reported
separately and never promoted to operational flood-prediction readiness.

Historical archive dating is reported separately, excluded from the live gate.
Health is neither national completeness nor scientific validation. A green check
does not mean safe weather, calibrated forecasts or verified sensors. This CLI
does not issue warnings or messages to users.

## Publication enforcement

The collector writes `health-report.json` before its publication decision. An
invalid result stops the run before writing the new public snapshot, durable
latest/state files or selected-history batch. The previous published artifact
remains available with its original dates. The standalone build also rejects
invalid health. Degraded availability (including missing products, stale data
and failed source requests) does not block honest partial publication.

New river/rain rows beyond the clock-skew allowance are excluded from the display
and listed in the health report's `quarantined_observations`, with station ID,
source, timestamp and reason. Previous valid readings remain. Source evidence is
retained by the raw-response retention path; quarantine does not modify it.
