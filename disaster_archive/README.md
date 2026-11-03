# Nepal disaster data archive

This is a local research database and collector, initially built on 29 September 2026. The operational status and exact record counts are in [exports/status.md](exports/status.md). The machine-readable audit is [exports/manifest.json](exports/manifest.json).

## What is collected

| Source | Data retained | Coverage and cautions |
|---|---|---|
| [BIPAD public API](https://bipadportal.gov.np/api/) | Incident records, expanded aggregate losses, hazard taxonomy, province/district/municipality/ward lookups | Traverses available API records. Reports may describe different local impacts of the same disaster. All source hazard types are retained; `natural_incidents` filters the source's natural-hazard classification. |
| BIPAD rainfall and river endpoints | Timestamped source observations, station IDs, values, interval labels and source warning fields | Initially recent observations, then daily overlap/catchup. This is not a full historical station archive. Source-native units/accumulation semantics remain explicitly unconfirmed; do not sum rolling rainfall intervals. |
| BIPAD alert endpoint | A bounded sample of the latest 2,000 source messages per run, with original validity fields and revision history | Not a comprehensive warning feed. Old-record updates/cancellations may be missed. The local lab shows only public natural-hazard messages and treats missing expiry as unknown validity. |
| [USGS earthquake catalogue](https://earthquake.usgs.gov/fdsnws/event/1/) | Earthquake locations, origin time, magnitude/type, depth and catalogue review status | Requested from 1971 onward inside 26–31 N, 80–89 E. Includes parts of neighboring countries; not a Nepal-only catalogue. Detection thresholds change over time. |
| [Nepal DesInventar profile](https://www.desinventar.net/DesInventar/profiletab.jsp?countrycode=npl&lang=EN) | Annual and hazard aggregates, with original column labels | Profile period 1971–2013. Individual historical data cards were not obtained: the bulk download page timed out twice. No claim of a complete event-level 55-year record. |
| Earlier research | Source bibliography only | Imported into `research_references` as `prior_research_not_revalidated`. Narrative claims and news totals are NOT converted into database events. |

Raw replies remain compressed, with SHA-256 checksums, request URLs, HTTP status, retrieval time and selected response headers. Parsed record versions and every observed change remain in SQLite. Repeated unchanged records do not create duplicate versions. A value changing A → B → A retains all three observations in `changes`.

## Run and inspect

For a browser interface, run `python3 disaster_lab/server.py` from the project root and open http://localhost:8765. See `../disaster_lab/README.md` for the incident explorer, station replay and local action notebook.

Requires Python 3.10+ with SQLite JSON functions, macOS/Linux `fcntl`, and curl with a working trusted certificate store. No paid service, API key, account creation or Python package installation is needed for enabled sources. TLS verification stays enabled.

```sh
cd /Users/god/Documents/ChatGPT/Flood
python3 disaster_archive/archive.py collect
python3 disaster_archive/archive.py status
python3 disaster_archive/archive.py verify
```

`bootstrap` explicitly performs full incident/earthquake reconciliation and refreshes the historical profile. `collect` performs that full refresh automatically at least every seven days; otherwise it collects recently reported incidents and a bounded sample of recently modified incidents. This means a mass revision of old records may not be fully detected until the weekly refresh.

Hydrology uses a two-day overlap to retrieve source observations between daily runs. It can catch up at most seven days after downtime; longer outages are logged as gaps. The archive never substitutes zeroes for missing observations. API page caps, timeouts, unexpected schema and repeated pages are visible as incomplete/failed collections. BIPAD's reported total count is a placeholder, so exhaustion is checked using actual pages. Live pagination is not an atomic provider snapshot.

For a known gap, request a bounded historical window explicitly, for example:

```sh
python3 disaster_archive/archive.py backfill-hydro --feed river --start 2026-09-20T00:00:00+00:00 --end 2026-09-21T00:00:00+00:00
```

Use timezone-aware timestamps and windows no longer than seven days. Adjacent windows should overlap slightly because source filters use strict bounds. Availability of older observations is not guaranteed; inspect the manifest and measurement dates after each backfill.

The process takes an exclusive local lock. Another simultaneous collection exits without writing. If a run fails, records already obtained remain, and the run is marked failed or partial. Raw responses are retained even when they contain HTTP errors. An unavailable source is not interpreted as absence of disasters.

## Files

- `data/archive.sqlite`: queryable database; keep its raw source archive alongside it.
- `data/raw/`: checksum-addressed compressed original HTTP responses.
- `exports/*.ndjson.gz`: compressed, analysis-ready row exports.
- `exports/annual_incident_reports.json`: source incident reports by year/hazard.
- `exports/quality.json`: missing values, geography and basic database checks.
- `backups/`: compressed, consistent local SQLite snapshots. These are **not off-site backups**; no cloud upload is configured. Backups and observations accumulate; collection stops below 2 GiB free space. Nothing is silently deleted.
- `analysis.sql`: example queries for trends, place-based reporting burden, revisions and response actions.
- `sources-and-gaps.md`: source access requirements and next data priorities.

## Interpreting the data

1. Keep **physical hazards**, **local incident reports**, **loss estimates**, **historical aggregates** and **response actions** distinct. An earthquake can have many local incident reports. No cross-source event merging is done automatically.
2. Missing values remain null. Source-reported zeroes remain zero but can reflect source defaults; a present zero is not proof of no loss.
3. Deaths and missing persons remain separate. Household/family counts are not converted into people. Financial values are retained in source units without an unverified currency or inflation conversion.
4. Original timestamp offsets are preserved. BIPAD event dates commonly contain midnight timestamps and should not be assumed to have precise event-time resolution. Reporting, measurement and archive-retrieval times have separate meanings.
5. Source `verified`/`approved` flags are preserved; they are not independent verification by this project.
6. Multi-ward incident joins can multiply rows. Use distinct incident IDs, or the single-ward example in `analysis.sql`, before aggregation. Reference lookups contain source-maintained records, including potentially historical entries; they do not prove today's legal administrative boundaries.
7. Rising report counts can reflect improved reporting, changed boundaries or population exposure. Counts alone are not normalized risk or proof of climate causation.
8. Models must use information available before a prediction time. `first_seen_at` and `changes` support prospective analysis from archive inception, not reconstruction of unknown historical revisions. Evaluate chronologically and across held-out basins; never split overlapping windows or copies of one disaster randomly between train and test.
9. River stage may use station-specific datums and must not be treated as comparable discharge across stations. Rainfall interval values must not be summed without verified accumulation semantics and units.
10. Neither the archive nor its scheduled task is a live public-warning service or a validated disaster prediction system.

## Recording what helped

The empty `response_actions` table is ready for real, evidence-backed entries: action type, organization, place/event reference, request/start/completion times, outcome value/unit, evidence URL and verification status. This supports questions such as service-restoration duration or unresolved response tasks. It does not establish causal effectiveness without comparison groups and attention to differences in hazard severity/exposure.

`event_links` stores reviewed relationships between records when future research establishes that they concern the same event. No guessed links or fabricated response outcomes are seeded. Keep personal names, beneficiary phone numbers, medical information and household identifiers out of these research tables. Raw official source text may contain public personal details; the local archive is not cleared for public redistribution.

`response-actions.template.json` is an unpopulated field template, not real data. Enter actual institutional records using SQLite with parameterized statements after checking their evidence and timestamps. No automatic response-log import or external publication is enabled.

## Verification

```sh
cd /Users/god/Documents/ChatGPT/Flood/disaster_archive
python3 -m unittest -v test_archive.py
python3 archive.py verify
```

The tests exercise duplicate imports, revision/reversion history, missing-versus-zero values, source separation, unsafe pagination, changing schemas, incomplete downloads and historical table parsing. `verify` checks database integrity and all retained raw-response checksums.
