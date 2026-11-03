# Production service update

The authenticated web service, independent refresh worker, prospective scorecards, health checks and backup/restore procedures are documented in [DEPLOYMENT.md](DEPLOYMENT.md). For the current local page use `.venv/bin/python disaster_lab/production.py --local` and run `.venv/bin/python disaster_lab/worker.py` separately. Double-click `Start Disaster Lab.command` to start the production web service in local mode and its worker. The legacy `server.py` remains for development.

# Nepal Disaster Lab

A working local application over the auditable disaster archive. It supports investigation, two-model weather outlooks, chronological river-model evaluation and prospective prediction tracking. It does not issue public warnings or calculate validated disaster probabilities.

## Start

In Terminal:

```sh
cd /Users/god/Documents/ChatGPT/Flood
python3 disaster_lab/server.py
```

Open **http://localhost:8765**. Stop with Ctrl+C. If the port is already occupied, use `--port 8766` and open that port instead. The root folder also contains `Start Disaster Lab.command` for launching from Finder. The app runs on this computer; the server needs to stay running while you use it.

Only Python 3.10+ and the existing archive are needed for the application. The collection button also uses the archive's curl dependency. No frontend build, cloud account or API key is required. All fonts, scripts and map geometry are local, so exploring already collected records works without internet. Collecting new data requires internet.

## A first walkthrough

1. **Overview:** review coverage, the generalized station map and annual report counts. The current year is incomplete. Station/report density is not a risk score.
2. **Forecast studio:** compare ECMWF and NOAA precipitation, temperature and gust forecasts for seven city points over 24/48/72 hours. Choose a river station to compare persistence against damped local trend using separate selection, calibration and test periods. Stale or insufficient river evidence withholds an upcoming projection; historical model scores remain inspectable.
3. **Evidence health:** inspect all station age/gap/conflict checks and saved projections matched to later observations. Source consistency is not independent accuracy verification.
4. **Incident explorer:** choose Flood or Landslide, a district and year. Map points and table rows are capped for display; CSV exports include all matching source records. Each incident appears once in totals. Reports assigned to multiple districts are excluded from district rankings, with the excluded count shown.
5. **River & replay lab:** choose a station and horizon. Move the cutoff slider to an earlier observation. The green line shows measurements up to that cutoff; gray shows later measurements for retrospective inspection. The dashed baseline assumes the last eligible level persists to the target time.
6. Turn on **Only inputs already archived at this time** to exclude records first seen after the cutoff. For periods before this archive began, it is normal to have no eligible input. This does not mean the real instrument had no observations then.
7. Download the **Evaluation report** for station-specific persistence errors. It uses matched later measurements and excludes targets too far from the requested horizon. This is a retrospective baseline exercise, not evidence of flood-warning accuracy.
8. **Sources & messages:** inspect collection completeness and source bulletins. Only public, source-classified natural-hazard messages are shown. Missing or invalid expiry is unknown validity, never an active warning. Source verification does not establish independent verification or present validity.
9. **Action notebook:** enter actual research/preparedness/response tasks. Changes are retained locally. A completed task is a user-reported status, not verified evidence that harm was reduced. Do not enter beneficiary contact or medical information.
10. **Collect latest data:** runs the bounded observation archive collector followed by weather collection and recording of every eligible 30-minute, 1-hour and 3-hour river projection. Progress appears in the page; another archive operation will be blocked by its lock. Routine scheduled collection remains configured separately. Reload the page after a scheduled refresh to see updated records.

See [METHODS.md](METHODS.md) for equations, source documentation, validation rules and exact limitations.

## Scientific boundaries

- Station units, datum, accumulation conventions and reference thresholds remain unconfirmed. The app therefore does not interpret threshold exceedance as a warning.
- Persistence predicts a station value, not flooding at a home. It uses no rainfall forecast or physical river model.
- Retrospective evaluation uses measurement time and currently retained versions. Strict replay reconstructs the last source version this archive had observed at the cutoff, including revisions and reversions, and excludes measurements from after the cutoff. It cannot reconstruct knowledge before this archive began collecting.
- Overlapping evaluation pairs are not independent events. A short history does not provide a reliable estimate of skill in severe disasters. Errors are reported per station and not averaged across unverified units/datums.
- Freshness labels are interface heuristics: recent <=60 minutes; delayed <=360 minutes; stale beyond that; timestamps >5 minutes ahead are flagged. They are not provider service guarantees or hazard states. Persistence is withheld if its latest eligible input is over two hours old.
- No automatic hazard probabilities, evacuation routes, public broadcasts or language-model warning generation are enabled. Archived source messages are displayed as archived source records with their validity limits.
- The bulletin collector stores only the latest 2,000 source records per run. This can miss messages or updates to older records, and polling latency is not suitable for emergency relay. Missing messages never imply no hazard.
- Natural Earth's generalized Nepal outline is map context, not a legal boundary or an inundation model. Map provenance is stored in `static/map-provenance.json`.

## Files and persistence

- `../disaster_archive/data/archive.sqlite`: original source archive, opened read-only by the application.
- `local/actions.sqlite`: local notebook and its edit history. It is separate from source observations. Back this up separately; archive backups do not include it.
- `local/forecasts.sqlite` and `local/weather_raw/`: original weather snapshots, normalization, failed attempts and immutable prospective river projections. Back up this whole local directory, alongside the source archive.
- `local/refresh.log`: latest manually requested collector output.
- `reports/`: reproducible research outputs and verification results produced during development.
- `../planning/hazard-data-and-scientific-method.md`: online dataset catalogue and scientific assumptions.

The server binds to 127.0.0.1. It is for one local user, not public hosting. Writes require a local session token and reject foreign origins/hosts. Source/user text is escaped, external evidence URLs are restricted to HTTP(S), and file routes are explicitly listed. There is no multi-user authentication. Do not expose this development server publicly.

## Verify

```sh
cd /Users/god/Documents/ChatGPT/Flood
python3 -m unittest discover -s disaster_lab -p 'test_*.py' -v
python3 -m unittest discover -s disaster_archive -p 'test_*.py' -v
```

Run both collectors from Terminal with `python3 disaster_lab/refresh.py`. Collect only weather with `python3 disaster_lab/weather.py`. Record eligible projections from the existing archive with `python3 disaster_lab/predictions.py`. Regenerate quality checks and model evaluations with `python3 disaster_lab/validate.py`. The complete refresh command does not alter the already configured archive-only daily schedule.

Further deployment requires the access, scientific validation and local response work documented in the implementation plan. This local research release is complete independently of those future operational requirements.
