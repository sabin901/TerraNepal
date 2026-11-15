# Direct NOAA GFS research adapter

Implemented 15 November 2026. `direct_gfs.py` is a separate, bounded research acquisition
and native-interval decoder. It does not replace public Open-Meteo collection, enable
commercial publication of other sources, or establish locally accurate predictions.

## Run

Install the optional official ecCodes Python decoder separately:

```sh
.venv/bin/python -m pip install -r requirements-direct-weather.txt
.venv/bin/python disaster_lab/direct_gfs.py \
  --initialized 2026-11-15T12:00:00Z --leads 12,15 \
  --root runtime/direct-gfs-native
```

Choose an actually available NOAA cycle. The example is a historical experiment,
not a permanently available URL. The command supports at most 8 distinct leads,
1–24 hours, three fields per lead, serial HTTPS requests,2 MB/file and45 seconds/request.
It stops the batch on 401/403/429 rather than circumventing restrictions. No automatic
schedule is installed. HTTP/decoder failures and partial response bytes are retained.

`raw/` contains content-addressed bytes; `receipts/` records request identity,
acquisition time, checksum, HTTP/decoding result and native normalized messages;
`reports/` binds a bounded batch and measured resource use. Identical bytes deduplicate.
Reports and receipts are never overwritten. Local raw/receipt paths are not portable
identifiers: replay resolves raw bytes by hash under the explicitly supplied root.

Offline verification:

```python
from direct_gfs import replay
normalized = replay('runtime/direct-gfs-native', 'runtime/direct-gfs-native/receipts/HASH.json')
```

The optional `as_of` timezone-aware cutoff rejects evidence acquired later. Replay
checks receipt content hash, approved request identity, raw byte length/hash and
exact decoded output. Decoder-version changes can therefore require a reviewed
migration rather than silently rewriting prior results.

## Exact semantics

The only source host/path is NOAA NOMADS `/cgi-bin/filter_gfs_0p25.pl`. Region is
80–89°E, 26–31°N. GFS 0.25° regular-grid metadata, requested cycle, lead, valid time,
field/level/units and accumulation windows must agree with the request.

- TMP 2 m: kelvin converted to Celsius; instantaneous native forecast.
- APCP surface: kg/m² water equivalent retained as mm over its explicit native
  `startStep`–`endStep`. Multiple accumulations can overlap; they remain separate.
  No hourly interpolation, overlapping sum or silent differencing is implemented.
- GUST surface: instantaneous surface gust in m/s. It is deliberately named
  `surface_gust`, not the existing Open-Meteo 10 m hourly-maximum variable.

Each message retains native GRIB metadata and nearest-grid values for the existing
seven city coordinates. Grid coordinates/index and distance remain visible; there
is no elevation adjustment or approved station mapping. Bitmap-missing values stay
missing. Physically implausible values become missing with a reason and original
native value retained. This is source quality checking, not climatological validation.

The parser rejects extra/truncated framing, duplicate native intervals, unexpected
parameters/levels/units, changed resolution/region, initialization/valid-time mismatch
and distant sample cells. It preserves up to two native precipitation messages per
requested field/lead because actual NOAA files provide both shorter and cumulative
accumulations. Changed product structure requires a deliberate contract update.

## Actual measured experiment

Run 2026-11-15T12 UTC, leads 12 and 15, was retrieved on 15 November 2026:

- Six HTTP requests, all six decoded after native dual-accumulation handling.
- Eight GRIB messages: one temperature, two rainfall, one gust per lead.
- Seven city samples per message; 56 native samples, not 56 independent observations.
- Raw response bytes: 7,843; acquisition/decoding wall time about 3.00 seconds.
- Process peak RSS: 59,224,064 bytes on this macOS host (approximately 56.5 MiB).
- All six receipts/raw responses replayed exactly with the installed decoder.
- f012 rainfall contains 6–12 h and 0–12 h totals; f015 contains 12–15 h and 0–15 h totals.

The first bounded attempt conservatively rejected the multi-message rainfall and
retained its evidence. Its failed report is still present. The corrected native
contract did not alter those receipts or their bytes.

Successful report (local ignored evidence):
`runtime/direct-gfs-native/reports/82f6e5e85b0a18385c127ee56b6602838c62a9084f7dc85dcc6be9c5b4ff2157.json`.

These measurements exclude initial dependency installation (optional packages included
native ecCodes and numpy), are one host/two leads/one cycle, and are not a monthly cost,
GitHub reliability or complete 24-hour coverage estimate. Package versions are recorded
in each decoded message; `requirements-direct-weather.txt` pins the Python wrapper,
not every platform-specific native/transitive dependency.

## Remaining before public/provider replacement

- A second independent cycle, controlled outage/restore and longer operational trials.
- Complete non-overlapping accumulation interval selection and evaluated native-time UI.
- Independent decoder comparison and reviewed station/grid/elevation mappings.
- Full resource/retention measurements and deployment dependency review.
- Separate evidence allowlist integration, source-identity migration and public contracts.
- Independent Nepal forecast evaluation; commercial rights/access review for all
  non-GFS feeds. Direct weather does not clear BIPAD or Open-Meteo discharge rights.

## Primary documentation checked

- https://nomads.ncep.noaa.gov/info.php
- https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl
- https://www.nco.ncep.noaa.gov/pmb/products/gfs/
- https://www.nco.ncep.noaa.gov/pmb/products/gfs/gfs.t00z.pgrb2.0p25.f003.shtml
- https://www.weather.gov/disclaimer
- https://github.com/ecmwf/eccodes-python

NOAA/NWS data are generally public domain unless otherwise stated; preserve source
attribution and do not imply NOAA endorsement. Review terms for the actual chosen
products. Public accessibility alone is not a blanket rights clearance.
