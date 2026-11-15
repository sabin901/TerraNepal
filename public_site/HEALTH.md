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

Any invalid schema or future publication/observation/retrieval/attempt timestamp
makes the entire report invalid. Future forecast valid times are expected.
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
