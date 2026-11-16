# Deploy TerraRaksha on Vercel

This deploys the public research dashboard and a stateless Python evidence API.
It does **not** deploy the full private lab. No database, password or environment
variables are required for this public mode. No account or deployment has been created
by these files. Vercel account eligibility and any signup verification are controlled
by Vercel; no no-card guarantee is made.

## Easiest route: import the existing repository

1. Sign in to Vercel with your own account.
2. Choose **Add New → Project** and import `sabin901/TerraNepal`.
3. Use branch **main**, root directory **./**, framework **Flask**.
4. Keep the repository's build command (`python deploy/build_vercel.py`). Do not set
   a custom output directory; Flask's `public/` directory is generated automatically.
5. Select Hobby for the personal, noncommercial research project, then Deploy.
6. Open the supplied HTTPS URL, `/health/live`, `/api/capabilities`, and the Evidence
   view. Confirm displayed observation/publication dates; health is not data freshness.

Importing the existing repository keeps subsequent main-branch pushes connected.
Alternatively the Deploy button clones a separate repository into your account;
changes to the original will not automatically update that clone.

[Deploy a copy on Vercel](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2Fsabin901%2FTerraNepal&project-name=terraraksha&repository-name=terraraksha)

## Data updates

The API reads the existing allowlisted GitHub Pages snapshot, validates its schema
and health, and caches it in memory for at most 60 seconds per warm instance.
Existing GitHub collection continues; deploying Vercel creates no new collector.
Dates remain the source's dates. Old-but-valid data remains explicitly aged by the UI.
Failed acquisition or invalid data returns 503; it does not publish a fresh seed.
Briefs are regenerated from the validated snapshot at request time.
This deployment depends on the original GitHub pipeline, even if you clone the repo.
Do not claim real-time or guaranteed emergency refreshes.

## What remains local

Private archive browsing, notebook/case writes, historical replay and the private
exposure workspace require a durable storage migration. The adapter deliberately
never imports production.py, opens SQLite databases, launches worker threads, or
writes credentials/records to Vercel's temporary filesystem. .vercelignore excludes
local originals, reports, state, notebooks and credentials. Do not deploy the private
loopback server with `--local` to the internet.

For the full lab: first select database and private object storage, implement and
verify transactional/revision semantics, migrate hashed originals and backups, adapt
collection jobs, and validate authentication plus restart/recovery. No full-lab
migration or operational prediction readiness is claimed by this deployment.

## Local checks

```
.venv/bin/python -m unittest discover -s deploy -p 'test_*.py' -v
.venv/bin/python deploy/build_vercel.py
```

The build refuses a nonempty public/ directory to prevent mixed artifacts. Use a new
checkout/output for another build. The Vercel platform build and live acceptance
must still be checked after the owner connects the account.

References:
- https://vercel.com/docs/frameworks/backend/flask
- https://vercel.com/docs/plans/hobby
- https://vercel.com/docs/daemons
