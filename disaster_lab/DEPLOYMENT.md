# Private production deployment

This release adds an authenticated single-owner service, a durable independent worker, prospective scorecards, verified backups and a Docker Compose deployment. It is a private research service, not a validated public warning system. A remote deployment still needs a selected server, domain, login initialization and on-host acceptance tests. Container configuration alone is not evidence that a deployment succeeded.

## Runtime and data

Use a Linux VM or persistent container host. A starting allocation for this archive is 2 CPU cores, 8 GB RAM and 20 GB free persistent disk; measure actual use and growth. SQLite requires a local filesystem shared by one web service and one worker. Do not mount the databases over NFS, scale writer replicas, or use an ephemeral/serverless filesystem. Put only Caddy's ports 80 and 443 on the public network. The Python port is internal to Compose.

`NEPAL_ARCHIVE_ROOT` holds the archive database, original responses, revisions, configuration, exports and archive snapshots. `NEPAL_STATE_ROOT` holds weather responses, prospective predictions and outcome revisions, actions, operations state and private credentials. Their defaults retain the existing local directories. Data is excluded from the container image. Keep backups off the server using the operator's chosen private storage as well; this release does not silently copy data elsewhere.

The worker targets recent river/rain observations every five minutes, weather hourly, analytical recording and verification every ten minutes, daily archive reconciliation and daily full portable backups. These intervals are not source update guarantees. The live collector overlaps two hours and is bounded at 20 pages per observation feed; it does not advance the daily seven-day catchup watermark. Daily collection handles older revisions and weekly full incident traversal. The writer lock serializes archive work; a long reconciliation can defer live jobs. A pre-existing Codex archive heartbeat may remain enabled because it uses the same archive lock. When the remote worker becomes authoritative, keep the local archive as a separate copy or explicitly retire its local automation.

Failures retain last good data, retry with bounded exponential backoff, and appear in Service health. Source lock contention is deferred, not reported as lost data. Worker restart requeues interrupted jobs. Logs retain 30 runs per job. Original source responses, database revisions and backups are not automatically pruned. Monitor disk growth; archive ingestion stops below 2 GiB free disk. Define backup retention and off-host copies before unattended long-term operation. Provider failures, missing station data and partial traversal never become zero rainfall or safe conditions.

## Run locally

From the project root:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python disaster_lab/worker.py
```

In a second terminal:

```sh
.venv/bin/python disaster_lab/production.py --local --port 8765
```

Open http://localhost:8765/. Local mode binds only loopback and uses session CSRF protection. For remote use, omit `--local`; startup requires hashed owner credentials and a configured HTTPS origin. Double-click `Start Disaster Lab.command` to start the worker when needed and open the local web service. The original `server.py` remains a legacy loopback development entry point for compatibility. A complete read snapshot is loaded at startup and rebuilt in the background every 60 seconds when the archive changes, so ordinary requests do not wait for repeated historical joins.

## First remote deployment

1. Identify the operator's server/SSH alias and domain. Confirm the domain points to that host, Docker Engine/Compose are available, persistent local disk is writable, and incoming ports 80/443 reach Caddy. No purchase is required by this package.
2. Transfer only project source to the private server. Build once with `docker compose build`. Copy `.env.example` to `.env` and set the real `NEPAL_DOMAIN`, an absolute `NEPAL_DATA_DIR`, and a release tag. Never put passwords in `.env`, shell arguments, chat or Git.
3. Create a portable snapshot locally: `.venv/bin/python disaster_lab/backup.py --output /absolute/private/nepal-snapshot.zip`. Transfer it privately to the selected host and compare the returned SHA-256. Restore into a new, nonexistent data directory with `python disaster_lab/backup.py --restore /private/nepal-snapshot.zip --destination /srv/nepal-data`. This can be run inside the built image using a private bind mount and an operator account with write permission. Do not copy a live SQLite database directly without its WAL or a backup API snapshot.
4. Give UID/GID `10001:10001` read/write ownership of the new data directory only. The runtime containers run as that user, with a read-only image and writable data volume. Never apply ownership changes to unrelated host paths.
5. Run `docker compose run --rm web python disaster_lab/production.py --set-password`. Enter a unique password of at least 16 characters at the terminal. The service stores a scrypt hash and a separate signing key; both stay in the state volume. Password replacement invalidates earlier sessions after restarting the web service.
6. Pin the tested Python base and Caddy images to digests for the final deployment, record them with the release tag, then `docker compose up -d`. Caddy obtains TLS for the configured domain. This contacts the certificate authority only when the operator actually starts the remote deployment.
7. Verify `/health/live` returns 200, `/health/ready` returns 200 after the worker is online, anonymous API requests return 401, login works over HTTPS, and Service health shows successful live/weather/analysis jobs. Inspect the actual observation ages under Evidence health; HTTP readiness is not scientific readiness. Check a notebook write, a CSV export, forecast provenance, backup restoration and persistence after `docker compose restart`.

Caddy preserves the configured Host. The app rejects other hosts and ignores untrusted proxy headers. Health checks set the expected Host explicitly. Cookies are Secure, HttpOnly, SameSite=Strict with an eight-hour session lifetime. Login has a persistent global limit of ten attempts per five minutes, appropriate to one owner; this is not a multi-tenant identity service. TLS terminates at Caddy. Remote browser tests must check the real TLS/proxy path.

## Health, maintenance and recovery

- `GET /health/live`: process responds; no data or secrets.
- `GET /health/ready`: archive readable and worker heartbeat younger than 90 seconds. A 503 makes a disconnected worker visible. Docker's liveness check does not restart a healthy web process solely because the worker is down.
- Authenticated `GET /api/operations`: last success, next attempt, retries and job state. `GET /api/quality` covers station evidence. `GET /api/predictions?limit=100&offset=0` includes all-record verification counts and grouped scorecards plus one ledger page.
- `docker compose logs --tail 100 web worker`; detailed per-job logs also live under `state/job_logs`. Avoid copying raw records or private notebook entries into public issue trackers.
- Back up: `docker compose exec worker python disaster_lab/backup.py`. Portable snapshots include consistent SQLite snapshots and all raw files referenced by those snapshots, with checksums. Each database is internally consistent; snapshots are not a distributed transaction across databases. Source exports can be regenerated. Passwords/session keys are deliberately excluded.
- Restore: stop services; verify and restore into a new path, initialize owner login there, and change `NEPAL_DATA_DIR` after verification. The restore command refuses overwrite, verifies every member checksum and SQLite integrity, and publishes the destination only after all checks pass. Run `archive.py export --root <restored archive>` to regenerate exports.
- Roll back: retain the prior source/image release and a pre-upgrade portable backup. Stop services and restore that snapshot into a new path; point the prior release at the restored path. Do not overwrite the current data volume or discard revisions made after the backup. The added schema is additive (`CREATE TABLE IF NOT EXISTS`); do not assume a future destructive migration is reversible.
- Update dependencies using the pinned requirements, rerun tests and the advisory audit, then rebuild and record new image digests. An audit reports known vulnerabilities only; it is not a penetration test.

## Scientific and access gates

Every saved river projection is checked, including records beyond the displayed 100-row page. Verification matches the first observation at/after the target inside the saved tolerance, never a future observation relative to verification time. Missing and conflicting target observations are not scored. Corrected source measurements create new outcome-history entries. Scores stay grouped by station, horizon, model and version because station units and datums are unconfirmed; overlapping targets are dependent samples. This change improves accountability, not established predictive accuracy.

The archive's source distinctions, raw checksums and revision history remain intact. BIPAD public access does not establish redistribution rights, so remote access remains private. ReliefWeb collection still requires an approved operator-owned appname. The current free Open-Meteo endpoint is for non-commercial use; private deployment does not itself authorize commercial use. Its [terms](https://open-meteo.com/en/terms) permit fewer than 10,000 calls/day, 5,000/hour and 600/minute; the normal weather schedule uses 336 individual requests/day. Credentials, paid data access and public warning dissemination are not enabled by this release.

Further warning-system readiness requires confirmed station units/datums/thresholds, independent multi-season and event validation, catchment and exposure data, local agency review and an agreed warning authority. No earthquake timing prediction or universal disaster prediction is supported.

Implementation references: [Flask production deployment](https://flask.palletsprojects.com/en/stable/tutorial/deploy/), [Flask web security](https://flask.palletsprojects.com/en/stable/web-security/), [Waitress proxy handling](https://docs.pylonsproject.org/projects/waitress/en/latest/reverse-proxy.html), [Caddy HTTPS reverse proxy](https://caddyserver.com/docs/quick-starts/reverse-proxy).
