# Unverified Nepal station mapping candidates

`station_registry.py` converts the schema-1 normalized output of `ghcnh.py` into
a review inventory. It never approves a station, forecast grid cell or evaluated
pair, including when city-to-station distance is zero.

```sh
python3 disaster_lab/station_registry.py \
  runtime/weather-source-audit/temperature-records-for-registry.json \
  --output runtime/weather-source-audit/station-mapping-candidates.json
```

The input is a JSON object with `schema_version: 1` and `records`, using the
existing GHCNh temperature-normalizer contract. Multiple normalized station-file
record arrays can be concatenated into one such input. Use the actual retrieval
time from each raw file's ledger when running the normalizer. Do not substitute
the registry build time for observation acquisition.

The output retains station identifiers, raw response SHA-256 references, record
counts, candidate temperature counts, observed periods and every distinct
coordinate/elevation tuple. Missing/invalid metadata and temporal inconsistencies
require review. Multiple metadata variants are explicitly marked conflicting;
they could reflect relocations or reporting changes and are never resolved by
choosing the latest or most frequent tuple. Invalid source identifiers or missing
hash/line provenance are excluded with counts. Repeated identical source hash/line
records count once; conflicting normalized content for the same hash/line fails
the build. The CLI also records a hash of the exact normalized input JSON.

Every retained coordinate variant receives great-circle distances to each of the
seven requested city points from `weather.PLACES`. These are **not distances to
returned forecast grid cells**, nor a measure of valley/terrain representativeness.
No cutoff approves a mapping. Native model grid elevation stays null; station
height is never substituted for it. The tool makes no external requests.

On 15 November 2026 the existing 17 local NOAA GHCNh raw responses were hash-
checked against the retrieval ledger, normalized using their original acquisition
times and processed into the local aggregate above. Result: 31,378 included rows,
17 stations, no metadata variants within these files, **zero verified mappings**.
Stable metadata is not independent station validation. No raw observations or
this local aggregate are automatically published by this script.

Still required: compare station identities/relocation history with authoritative
metadata, inspect returned forecast coordinates and provider downscaling rules,
review terrain and elevation mismatch, record a versioned decision and then
construct observation/forecast pairs. This inventory is evidence for that review,
not permission to label candidates as ground truth.
