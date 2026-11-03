# TerraNepal

A public research dashboard for Nepal's river observations, weather outlooks and disaster archive coverage. **Research beta: this project does not issue disaster warnings or validated flood probabilities.**

The public site is designed for GitHub Pages at https://sabin901.github.io/TerraNepal/. Availability depends on the repository's Pages configuration and the latest successful deployment.

## Public dashboard

The `public_site/` app is static, uses relative URLs and needs no API key, account or paid runtime. GitHub Actions requests recent public hydrology observations and 14 Open-Meteo model/location forecasts once per hour at minute 17. Schedules can be delayed, dropped or disabled after repository inactivity; they are not emergency monitoring infrastructure.

- Per-station observation times are separate from page build time.
- Missing stations retain their last observation and age; absence never becomes zero.
- Conflicting same-time river values are withheld. Gauge units/datums and thresholds remain unconfirmed.
- Weather totals require complete future windows and retrieval age at most six hours. Browser checks run every minute.
- Source failures preserve older successes with their original times. If every source fails, the build fails and the last successful deployment remains available with aging timestamps.
- The historical archive totals and coverage audit are dated snapshots. Hourly runs do **not** refresh the historical incident archive.
- Public output contains only reviewed station summaries, weather model data and aggregate archive evidence. No incident narratives, private notebook, credentials, raw archive, database or backups are published.

### Run locally

```sh
python3 -m unittest discover -s public_site -p 'test_*.py' -v
node public_site/test_logic.cjs
python3 public_site/pipeline.py build --output runtime/site
python3 -m http.server 8765 --bind 127.0.0.1 --directory runtime/site
```

Use an empty output directory for each build. To fetch fresh public data first:

```sh
python3 public_site/pipeline.py refresh --output runtime/public-snapshot.json
python3 public_site/pipeline.py build --snapshot runtime/public-snapshot.json --output runtime/refreshed-site
```

These public commands use Python's standard library and TLS-verified curl. The private Flask dependencies are not required to build the public page.

### GitHub Pages deployment

In the repository's **Settings → Pages → Build and deployment**, select **GitHub Actions**. The `Publish TerraNepal research dashboard` workflow publishes only `runtime/site`; it never uploads the repository root. A push to `main`, manual workflow dispatch or hourly schedule builds a new artifact. Pull requests validate/build without publishing or fetching live data. Check the Actions deployment result before sharing the URL.

The local `disaster_archive/` collector remains the durable research archive. CI's temporary collection files are not a durable archive or an off-site backup. Keep running the local collector and its backup process. To update public historical aggregates after a reviewed local maintenance audit, regenerate and review the public seed before committing it. The current export command points to the documented 3 November 2026 recovery audit; update that explicit audit reference for a later release.

## Private research service

`disaster_lab/` contains the authenticated Python/SQLite workspace, experimental river models, prospective prediction ledger, worker and operations tools. It requires a persistent server and cannot run on GitHub Pages. See [deployment instructions](disaster_lab/DEPLOYMENT.md) and [scientific methods](disaster_lab/METHODS.md).

## Evidence and attribution

As of the 3 November 2026 local audit: 65,160 BIPAD incident reports, 597,073 river records and 265,170 rainfall records. Counts refer to source records, not unique disasters. Rainfall observations are absent on 22–27 October UTC; river observations are absent on 22–24 October and very sparse on 25–27 October. Successful backfill traversals did not establish complete source coverage.

Source attribution: Nepal BIPAD and originating agencies; Open-Meteo, ECMWF and NOAA (weather data CC BY 4.0, free API for noncommercial use); USGS regional earthquake catalog. BIPAD's bulk redistribution license has not been verified. No blanket license for third-party datasets is granted by this repository. Read the source terms before expanding redistribution or commercial use.

Use Nepal's [DHM](https://dhm.gov.np/) and [BIPAD](https://bipadportal.gov.np/) for authoritative information. Source byte integrity and passing software tests do not establish physical sensor accuracy or severe-event predictive reliability.
