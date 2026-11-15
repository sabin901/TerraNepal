# Disaster intelligence case ledger

`cases.py` is an append-only local evidence/decision ledger, not a hazard model or
an authority to issue warnings. It links dated evidence, geography, case revisions,
operator-recorded actions and later outcomes. No real cases or impacts are invented
by initialization. Public exposure must be separately reviewed; case narratives and
actor names are private operational information by default.

## Storage and API

```python
from cases import CaseStore
store = CaseStore('/private/state/cases')  # creates cases.sqlite
revision = store.append_revision(case_id, document)
store.append_action(case_id, action)
store.append_outcome(case_id, outcome)
store.replay(case_id, '2026-11-15T20:00:00Z')
store.list_cases('2026-11-15T20:00:00Z')  # cutoff optional: current clock
store.verify()
```

SQLite transactions serialize writes. Every event carries its case ID, recording
time, previous event hash and canonical payload SHA-256. SQLite triggers disallow
updates/deletes; correction means appending a new revision. An unchanged repeat
revision or identical repeat action/outcome is idempotent. A changed revision can
intentionally revert to an earlier payload and is retained as a new event.

All reference/acquisition/review dates require an explicit timezone and normalize
to UTC. Source references must use HTTPS without user credentials, fragments or
query strings. Keep a sanitized source document URL here; exact request URLs and
bytes belong in the separate archive. A source hash reference does not itself
verify corresponding raw bytes or rights to redistribute them.

`document` has exactly these fields:

- `title`: nonempty string, at most200 characters.
- `hazard`: `flood`, `landslide`, `heat`, `cold`, `drought`, `wildfire`, `earthquake`,
  `glof`, `multi_hazard` or `weather`.
- `geography`: `{type, coordinates, label, review}`. `point` uses `[longitude,
  latitude]`; `bbox` uses `[west,south,east,north]`, WGS84 degrees. Cross-antimeridian
  regions need separate cases. This is a geographic reference, not a flood extent.
- `valid_from`, `valid_to`: ordered timestamps for the case's subject period.
- `summary`: nonempty text, at most10000 characters.
- `evidence`: one to1000 references, with exact duplicate references rejected.

Each evidence reference has exactly:
`{kind, source, source_url, sha256, acquired_at, valid_from, valid_to, review}`.
Kinds remain distinct: `observation`, `provider_forecast`, `scenario`,
`official_warning`, `confirmed_impact`. Forecast/scenario/warning validity may extend
into the future; observations and confirmed impacts cannot end after acquisition.
Acquisition cannot be after the local recording clock.

Every `review` contains exactly `{status, reviewer, reviewed_at, reason}`. A new
record should use `{status:"unverified", reviewer:null, reviewed_at:null,
reason:"Not yet reviewed"}`. `reviewed` and `rejected` require reviewer attribution,
a review timestamp and rationale. Review cannot be in the future; evidence review
cannot precede acquisition. Confirmed-impact references require `reviewed` status.
These are operator attestations. The software does not authenticate a reviewer's
identity, expertise, source authenticity or authority. Classifying a reference as
`official_warning` is not verification that it came from an authorized issuer.

Action and outcome payloads both contain exactly:
`{revision_sha256, text, actor, occurred_at, evidence, review}`. They must reference
an existing revision in the same case. `occurred_at` cannot be in the future.
Actions can have an empty evidence list; outcomes require evidence. An action
record says what an operator reported, not proof that the action occurred. A planned
future action belongs in case narrative until a separate planning contract exists.

## Replay and integrity boundaries

Replay selects events by local recording time, never by a backdated observation
alone. A correction recorded later cannot rewrite an earlier replay. Future-acquired
evidence and future reviews cannot enter a revision. Local clock rollback rejects
new writes rather than creating an invalid chronology. A replay validates retained
hash chains before returning records and rejects corruption even in later history.

Hash chains detect accidental edits and simple tampering; they are not signatures
or externally anchored audit logs. Someone with full database and code control can
rewrite hashes or remove terminal records. Backup, access control and independent
external checkpoints remain necessary for a stronger evidentiary claim. `verify()`
reports database/hash consistency only, never scientific correctness.

## CLI

```sh
python disaster_lab/cases.py --root /private/state/cases revision \
  --case my-case-id --input reviewed-document.json
python disaster_lab/cases.py --root /private/state/cases action \
  --case my-case-id --input action.json
python disaster_lab/cases.py --root /private/state/cases export \
  --case my-case-id --at 2026-11-15T20:00:00Z --output case-replay.json
python disaster_lab/cases.py --root /private/state/cases verify
```

Export never overwrites an existing output. Keep exports private unless narratives,
actor identities, infrastructure detail, source rights and claims were explicitly
reviewed for publication. No automatic public publishing is performed by this module.
Include `cases.sqlite` using SQLite's backup API in private service backups.
