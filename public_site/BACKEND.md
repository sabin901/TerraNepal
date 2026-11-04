# Automatic public-data backend

The same broad pattern as Footlyzer is used: GitHub Actions does the collection,
a separate Git branch retains approved data, and GitHub Pages serves a static
artifact. Your computer does not need to stay on for these public updates.
The authenticated Flask service and full raw research archive remain local.

## What refreshes

| Source | Requested cadence | Public output | Important distinction |
| --- | --- | --- | --- |
| BIPAD river observations | Every scheduled run, nominally 30 minutes | Latest station observations plus selected historical versions | Source units, datums and danger thresholds remain unconfirmed |
| BIPAD rainfall observations | Every scheduled run | Latest station timestamps; selected accumulation fields in research history | Source intervals/units are unconfirmed; no conversion to catchment rainfall |
| Open-Meteo ECMWF IFS and NOAA GFS | Each of 14 model/location snapshots becomes due after one hour | 96 hourly forecast steps at seven city points | Forecast, not observed rainfall; retrieval is not model issuance |
| USGS all-week GeoJSON | Becomes due after one hour | Earthquakes inside 26–31°N / 80–89°E | Includes neighboring countries; retrospective and incomplete catalog coverage |
| Open-Meteo GloFAS | Each of six study points becomes due after six hours | Seven UTC model days of mean, p25 and p75 discharge | Provider forecast updates daily; grid-to-river mapping is unverified |
| Historical incident totals and October coverage audit | Separately reviewed local export | Dated historical baseline | Not refreshed or relabeled as current by the cloud job |

Actual intervals depend on GitHub scheduling and request completion. The workflow
uses minute 17 and 47 rather than the top of the hour. An open browser fetches a
new snapshot every five minutes, on returning to the tab, and after reconnection.
Station ages are recalculated every minute. Filters survive a data refresh.

Numeric public discharge outlooks are withheld until the returned model cell is
verified against the intended river reach. All six current mappings are
unverified; their model data remain in the research JSON and history. See the
[4 November review](REVIEW-2026-11-04.md) for the spatial-sensitivity check and
prioritized improvements.

## Persistence and recovery

1. The non-PR job restores `latest.json` and `state.json` from
   `codex/data-snapshots`, checking their manifest hashes and schemas. PR jobs
   have read-only permissions, run offline tests, and cannot publish data.
2. Hydrology uses a three-hour overlap with the last successful **query end**,
   expands to catch up after outages, and revisits 24 hours on the first run of
   a new UTC day. Catch-up is bounded to seven days and 160 pages per feed.
   Anything older is recorded as an unresolved interval, never silently assumed
   covered. A failed or page-capped traversal does not advance its watermark.
3. Transient hydrology/USGS/discharge transport, 429 and selected 5xx failures
   receive one retry. Weather transport failures receive one retry. Schema
   errors are surfaced rather than retried indefinitely. At most three weather
   requests run concurrently; other sources are requested sequentially.
4. Missing or failed feeds retain the previous valid data and its original
   times. A valid empty USGS feed is distinct from a failed request. Source
   timestamps, units, array lengths, coordinates and model-day order are checked.
5. A compressed immutable file is added under
   `history/YYYY-MM-DD/<sha256>.json.gz`. It includes the public snapshot,
   selected observation changes, source response hashes and fetch results.
   The filename hashes the canonical **uncompressed** JSON. Same ID with changed
   selected facts records the previous hash; unchanged overlapping records do
   not create new versions within the eight-day index window.
6. Git commits preserve existing history without checking out or merging the
   application branch. A normal fast-forward push rejects competing writers.
   Publication proceeds only after the data push succeeds. No force push,
   automatic history deletion or credentials in data files are used.

Deduplicate analytical imports by `(source, native ID, selected-record hash)`.
An item reappearing after index eviction can occur in more than one batch.
Within a run the final observed version is retained; these files do not claim
to capture every intermediate source change. Forecast snapshots are retained
even when unchanged; each keeps its original fetch time.

The branch is a compact public history, **not a raw-response backup**. Exact
response bodies remain in `runtime/public-state/raw-local/` for local runs.
CI raw bodies are temporary and are not published. Cloud files retain selected
normalized facts and raw-response SHA-256 receipts, which cannot reconstruct an
original response by themselves. Continue the separate local archive collection
and backups for full source-response research and historical reconciliation.
No incident narratives, contact details, local notebooks or SQLite files are
copied to the data branch.

The current data tree has a 256 MiB budget, with a warning above 75%; individual
files have a 32 MiB cap. Reaching the cap stops publication and requires an
explicit archival/storage decision. Nothing is erased to stay under the cap.
Git object history adds overhead beyond the current tree. This is deliberately
bounded storage, not an unlimited free database. Run diagnostics are also kept
as Actions artifacts for 14 days, but durable data does not depend on artifacts.

## Run and inspect

From the project root, for a local refresh (retains local state between runs):

```sh
python3 public_site/pipeline.py refresh --output runtime/public-snapshot.json
python3 public_site/pipeline.py build --snapshot runtime/public-snapshot.json --output runtime/site-new
```

For a fresh runner, restore before collecting, then persist before building:

```sh
python3 public_site/data_branch.py restore --root runtime/public-state
python3 public_site/pipeline.py refresh --state-root runtime/public-state --output runtime/public-snapshot.json
python3 public_site/data_branch.py save --root runtime/public-state
```

`restore` requires a fresh destination so it cannot replace active local state.
`save` requires Git write access to this repository and the explicit parent from
`restore`. A local lock prevents overlapping refreshes into the same state root;
workflow concurrency prevents scheduled runs from sharing the production job.

Inspect the site's **Evidence** view, `data/snapshot.json`, Actions step summary,
and `runtime/public-state/run-report.json`. They expose attempts separately from
successful fetches, retained station freshness, query intervals, data gaps and
version counts. `built_at` means publication data preparation, not measurement
time. If every provider is down, a new health report can still be published
alongside old observations; their age continues increasing.

Use **Actions → Publish TerraNepal research dashboard → Run workflow** to request
a refresh. No secrets or manual uploads are needed. GitHub can delay/drop
scheduled jobs and disables schedules in public repositories after 60 days of
inactivity. Check Actions if updates stop; this is not an emergency-response SLA.

## Free-source choices and next additions

The integrated baseline makes approximately 336 weather + 24 discharge requests
per day if schedules run regularly, before retries. This is below the published
Open-Meteo free API limits. It remains a **noncommercial, no-ads/no-subscription**
deployment; adding monetization requires a terms review. Data attribution is
shown in the public UI. BIPAD bulk redistribution rights remain unverified;
only selected factual station fields are retained publicly.

| Additional resource | Best use | Status and prerequisite |
| --- | --- | --- |
| NASA GPM IMERG | Catchment precipitation estimates and retrospective evaluation | Not connected. The documented PPS download route requires registration; the larger Giovanni analysis route uses free Earthdata registration. Choose and validate a product/version, latency, scaling and area aggregation before ingestion. |
| NASA FIRMS | Satellite fire detections, separate from flood analytics | Not connected. Requires a user-owned MAP_KEY; satellite detection is not a prediction of ignition. |
| Google Flood Forecasting API | Independent river forecasts for comparison where covered | Not connected. No-charge access requires waitlist approval, a Cloud project, API key and enablement. |
| Google GRRR / GloFAS reanalysis | Historical discharge benchmarks | Available for a separately scoped offline evaluation; not a substitute for confirmed local gauge data. |

The next scientific milestone is verified river-reach/gauge matching and
multi-season, out-of-time evaluation against observations. The retained forecast
history now supports that work without replacing forecasts with later revisions.
Do not infer flood probabilities from model disagreement or forecast percentiles.

Primary documentation checked 4 November 2026:

- [Open-Meteo flood API, model selection and grid limitations](https://open-meteo.com/en/docs/flood-api)
- [Open-Meteo terms and free limits](https://open-meteo.com/en/terms)
- [USGS GeoJSON feeds](https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php)
- [NASA IMERG products and access routes](https://gpm.nasa.gov/data/imerg)
- [NASA FIRMS API and MAP_KEY](https://firms.modaps.eosdis.nasa.gov/api/)
- [Google Flood Forecasting API and historical datasets](https://developers.google.com/flood-forecasting)
- [GitHub schedule behavior](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)
- [GitHub repository storage guidance](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
