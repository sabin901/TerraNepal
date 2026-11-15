# Nepal observation research inputs

Checked 15 November 2026. No accounts, purchases or outreach.

NOAA GHCNh is the documented successor to ISD. The older ISD station history
listed 17 Nepal entries, with recent end dates stopping at 24 August 2025; this
must not be mistaken for current observational coverage.

The official GHCNh object-store listing exposed 17 Nepal station files for 2026.
All 17 were retrieved locally (22,415,783 bytes), retaining URLs, acquisition
times, SHA-256 hashes and exact PSV responses under
`runtime/weather-source-audit/`. The files contain 31,378 rows. Their most recent
measurement dates are 10 November, so these are delayed research observations,
not a real-time feed. National completeness is not implied.

`ghcnh.py` implements a deliberately conservative temperature-only parser.
It preserves numeric values and source flags, excludes missing/nonfinite values,
bad metadata and observations later than acquisition, and accepts only empty
measurement codes with source codes 220/221/222/223/347/348 and quality code 1.
Other combinations are retained but require review. This strict policy accepted
6,204 temperature candidates in the retrieved files; that count is neither
independent accuracy validation nor a count of verified forecast/observation pairs.

Temperatures in PSV are decimal Celsius and are not divided by ten again.
NOAA documents calendar fields as UTC even when DATE omits a suffix. Station
mapping, relocations, grid elevation and representativeness remain separate checks.
Duplicate/conflicting station times must be resolved by the evaluation contract;
the normalizer does not silently pick one record.

Rainfall is deliberately not normalized by this parser. NOAA describes nominal
hourly totals and intermediate reports, trace amounts, and separate accumulation
fields. These require period-aware processing before any rainfall comparison.
Wind speed and peak gust are distinct variables and must not be substituted.

Example:

```sh
python3 disaster_lab/ghcnh.py /path/to/preserved-station.psv \
  --retrieved-at 2026-11-15T19:00:00Z --output runtime/temperature-candidates.json
```

Use the actual acquisition time from the retrieval ledger, not this example.

Primary documentation:
- https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly
- https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh_DOCUMENTATION.pdf
- https://www.ncei.noaa.gov/oa/global-historical-climatology-network/hourly/doc/ghcnh-station-list.txt
- https://www.ncei.noaa.gov/oa/global-historical-climatology-network/index.html
