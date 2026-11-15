# TerraNepal independent release evaluation — 15 November 2026

## CTO decision

**NO-GO for an authoritative Nepal weather, disaster-warning or sector decision-support launch.**
**Conditional demonstration only as an explicitly limited research dashboard.**
The current public deployment is not evidence of operational or scientific readiness.
Do not claim perfect accuracy, improved forecast skill, national completeness or government endorsement.
The freshness-expiry and mobile outage defects should be corrected before broader promotion.

Scope: commit `9c0232547048060c698ea9f4ddcbc333659db364`, deployed public snapshot built
`2026-11-15T19:08:33Z`, checked at `2026-11-15T19:14:31Z` (13:14 Chicago).
Three independent AI review agents covered ten specialist perspectives; the lead agent
performed the CTO consolidation and additional browser reproductions. No external
meteorologists, Nepal agencies or human CTO were consulted. This is a bounded technical
review, not independent scientific certification, penetration testing or user research.
Production code and deployment were not changed during this evaluation.

## Ten-role review board

| Role | Assessment | Required evidence |
| --- | --- | --- |
| Weather forecasting scientist | No demonstrated TerraNepal weather skill; provider display exists | Real held-out forecast/observation benchmark and raw-provider baselines |
| Nepal observation specialist | Candidate data are delayed and geographically concentrated | Reviewed station register; terrain, season and station coverage |
| Forecast verification scientist | Arithmetic evaluator exists, defensible comparison study does not | Canonical truth, common cases, uncertainty and independent holdouts |
| Hydrologist | Gauge interpretation and reach mapping unverified | Units, datum, catchments, thresholds and event evaluation |
| Scientific provenance reviewer | Initialization/issuance and elevation semantics insufficiently separated | Versioned metadata and resolvable source lineage |
| Backend engineer | Useful validation but inconsistent invalid-data policies | Unified policy, quarantine behavior and failure-path tests |
| Reliability engineer | Best-effort scheduling and bounded storage are not an operational SLA | Measured freshness, outage/restore/retention runbooks |
| Security/release engineer | Small static surface is positive; no confirmed critical exploit in this review | Continued dependency/release controls and bounded security review |
| Product/Nepal-sector reviewer | General weather and sector scope largely absent | Supported-user journeys and validated sector inputs |
| Accessibility/UX reviewer | Confirmed mobile fallback and focus bugs; chart equivalents missing | Keyboard/mobile/failure-path and assistive-technology acceptance tests |

## Measured current state

- 14 stored weather model/location pairs; 10 recent and usable under the local 24-hour-window policy.
- Four failed latest requests, all ECMWF: Kathmandu, Biratnagar, Birendranagar, Dhangadhi.
- 205 river stations; 148 recent at audit time. All river levels have unconfirmed source units.
- 398 rain station records; 298 recent timestamps. Timestamp freshness does not verify rainfall amount semantics.
- Six discharge study points; zero verified reach mappings. Numeric public display is appropriately withheld.
- Historical export dated 3 November, separate from current collection.
- Public payload 258,440 bytes. Seven city locations; no nationwide terrain-aware coverage claim is supported.
- Local NOAA acquisition: 17 station files, 31,378 rows, 6,204 conservative temperature candidates.
  Kathmandu accounts for 4,025 candidates (64.9%). Candidates are not verified forecast matches.
- Live health result: `degraded`, no schema errors, weather product partial.

Evidence retained locally in `runtime/release-audit-2026-11-15/`: downloaded snapshot,
health JSON, mobile outage screenshot and isolated browser fixtures. Scientific source
inventory remains in `runtime/weather-source-audit/`. These are dated samples, not future guarantees.

## Confirmed defects and robustness gaps

### H1 — Focus can prevent forecast expiry from reaching the display

`public_site/static/app.js:66` skips rerendering non-river content while focus is inside
`#content`. `:51–56` also skips rendering when a refetched snapshot has the same build time.

Browser reproduction using exact application assets plus an isolated test-clock fixture:
1. Set retrieval age to 5h59m; GFS displays `recent`, 1.6 mm and gust 2.5 m/s.
2. Keep focus on the Open-Meteo link inside forecast content; advance test clock two minutes.
3. Minute callbacks run, but the expired numeric forecast and `recent` label remain.
4. Move focus to the navigation outside content; the next callback changes it to `stale`
   and withholds both numbers.

The publication banner can already warn that the snapshot is old; that does not cure
an incorrect freshness label on the forecast itself. Test-clock acceleration was confined
to the local audit fixture, not the real browser/system clock or public site.

Acceptance: expire every affected number and status independently of focused control,
while preserving focus. Test unchanged-snapshot, offline and background/resume paths.

### H2 — Mobile data-outage fallback directs users to a hidden link

`public_site/static/style.css:1` hides `.source-link` below 1000px. Initial data-load
failure at `app.js:59` says to use the official DHM link above. At 390px with the snapshot
absent, the actual browser contains no DHM link; Evidence cannot render without a snapshot.
Screenshot: `runtime/release-audit-2026-11-15/mobile-outage.png`.

Acceptance: an explicit official-source link remains usable at every width, without
successful JavaScript data loading. Test initial failure, offline and malformed payloads.

### H3 — Conflicting observation truth can pass offline verification

`disaster_lab/weather_evaluation.py:51,62–65` identifies duplicates with provider/model
in the key. Synthetic cases for the same station/time/temperature but two providers and
observation values 10°C versus 30°C are both accepted. This does not prove any published
accuracy score is false: no real score is published. It blocks use of this utility as a
credible provider-comparison system without a canonical observation layer.

Acceptance: observation identity/version must be independent of forecast provider; reject
or explicitly resolve conflicting truth, and compare providers on the same case cohort.

### H4 — Invalid-data policy is inconsistent and health is diagnostic only

`public_site/collector.py:142–150` saves/publishes regardless of invalid health status.
`pipeline.py:103,113` and `static/logic.js:8` tolerate five minutes of future time;
`health.py:20–23` rejects any future timestamp.

Synthetic reproduction: a river reading at build time +120 seconds passes schema validation,
produces invalid health, builds successfully, and is classified recent by frontend logic.
No corrupt live reading was demonstrated.

Acceptance: one documented skew policy; quarantine genuinely invalid records and expose
why. Keep publishing honest partial data when a source is unavailable; do not make every
source outage a whole-site outage.

### H5 — Plausibility and metadata checks are weaker than the word validation suggests

`disaster_lab/weather.py:38–58` accepts synthetic 999°C, string elevation and a grid point
shifted +0.49° latitude. A 0.5° tolerance may fit coarse model resolution, but does not
prove a point represents the intended terrain. No such corrupt live value was observed.

Acceptance: explicit model-aware coordinate and terrain matching; typed metadata and
physical plausibility policies. Preserve and flag suspect evidence; do not clamp it into
apparently safe weather or reject legitimate extremes without a documented rule.

### M1 — Keyboard focus is lost after location selection

`public_site/static/app.js:32` replaces the content and focused button. Reproduced on live
site by keyboard-activating Pokhara: active element becomes BODY.

Acceptance: preserve logical focus across selection and automatic updates; add keyboard
and assistive-technology checks, not only click/overflow tests.

### M2 — Initialization, availability and lead times need distinct metadata

`forecast_runs.py:48–50` stores requested initialization as `model_issued_at`, with an honest
explanatory note. `weather_evaluation.py:49–50` groups lead by caller origin, as documented,
but does not report initialization lead/run age. A seven-day-old run can enter a `0-24h`
decision-lead group. This is a reporting limitation, not a contradiction of its current docs.

Acceptance: separate initialized/published/retrieved timestamps, run age, decision lead and
initialization lead; predeclare run selection. Returned Open-Meteo elevation must not be
silently treated as native model-grid elevation or corrected twice.

### M3 — Chart accessibility and missingness are incomplete

`app.js:24,29` has no equivalent accessible data table; missing historical values and zero
have the same zero-height visual encoding. Tooltips and caveats do not fully fix this.

Acceptance: distinct missingness, usable chart tables and textual summaries, tested with
keyboard and screen reader. No WCAG certification is claimed by this review.

## Operational and evidence-retention gaps

1. **Automated original bodies are not durably retained.** `collector.py:124` uses ephemeral
   `raw-local`; `data_branch.py:27–28` selects transformed state/history; workflow artifacts
   retain compact reports for 14 days. Hashes cannot reconstruct original bodies. The local
   archive does not automatically contain every independently fetched GitHub response.
   Gate: permitted immutable response retention, checksums, receipts and restore/replay drill.
2. **Scheduler blind spot is accepted but material.** A health job running in the collection
   job cannot detect that the job never started. GitHub-only remains the user's decision.
   Gate: honest best-effort scope, measured freshness and operator/outage procedure; no
   emergency SLA. GitHub documents scheduled jobs may be delayed or dropped.
3. **Public corrections are narrowly reconciled.** `history.py:40–49,86–88` and
   `collector.py:28–31` use limited overlap/catch-up and bounded deduplication; late historical
   corrections may be missed. Local archive reconciliation is a separate mechanism.
   Gate: tests and bounded reconciliation for delayed corrections and long outages.
4. **Storage cap can stop publication.** `data_branch.py:19–20,36,120–121` limits current tree
   to 256MiB; save precedes build. Git history growth is additional. No time-to-exhaustion was
   measured in this audit. Gate: actual growth accounting and tested export/rotation/restore.
5. **Same-time corrections remain conflicted.** `pipeline.py:148–154`: level1 then level2 at
   the same timestamp becomes null/conflicting; a subsequent level2 remains conflicted.
   Withholding is conservative. Gate: version evidence and reviewed correction resolution,
   not an arbitrary choice of a winner.

## Scientific and product gates not met

- No completed real weather verification study, corrected weather model, calibrated event
  probabilities or demonstrated improvement over raw providers.
- No approved station/grid registry or representative rainfall/gust validation network.
- No independently evaluated monsoon/extreme-event performance or false-alarm/miss analysis.
- Unconfirmed gauge units/datum and unverified river reaches prohibit flood interpretation.
- Main weather view offers precipitation and gusts at seven cities; temperature presentation,
  municipality search, daily general-weather journeys and sector views are absent.
- English-only interface; no Nepali comprehension/user evaluation evidence.
- Source reuse basis needs a documented register. The UI itself says BIPAD bulk redistribution
  permission is unverified. This is unresolved due diligence, not a legal conclusion.
- Free hosted API access is not equivalent to unlimited/commercial use or guaranteed service.

## Evidence required for the next release decision

Order matters. A new visual redesign or additional model does not remove these gates.

1. Correct and regression-test expiry, mobile fallback and focus; unify invalid-data policy.
2. Complete provenance/observation registry, canonical truth and original-run scheduling/
   retention. Report coverage and missingness by station/season/elevation.
3. Produce a reproducible temperature verification report at explicitly verified locations:
   untouched chronological test data, raw-provider and simple baselines, common cases,
   MAE/bias, sample counts, uncertainty and geographic holdouts. Predeclare thresholds.
4. Evaluate rainfall and gusts separately; do not transfer temperature validation to hazards.
5. Test restore, late correction, source outage and storage exhaustion. Measure achieved
   refresh performance under GitHub-only constraints and document responsible ownership.
6. Deliver supported Nepal user journeys, bilingual critical content and accessible charts;
   validate sector claims using their extra impact/exposure data and decision criteria.
7. Assemble an institutional evidence pack: data dictionary, lineage and reuse register,
   benchmark protocol/results, limitations, incident/change log and recovery procedure.

No arbitrary accuracy percentage or 100-point readiness score is supplied: the gates above
are not interchangeable and averaging them would hide release blockers. Presenting this to
an authority for technical feedback is reasonable; presenting it as an approved operational
forecasting service is not supported by current evidence.

## Positive findings to preserve

Explicit research identity, no disaster-warning claims, source timestamps and attribution,
null preservation, retained earlier-success ages, withheld unverified discharge values,
selected-field public artifact, concurrency-safe history writes and substantial automated
failure tests are worthwhile foundations. No confirmed critical exploitable vulnerability
was found in this bounded review; that is not a security certification.

## Test scope and references

Current review: 47 public Python tests passed (backend reviewer), 96 research Python tests
and 26 JavaScript assertions passed (lead reviewer). Synthetic adversarial examples and
browser failure-path reproductions exposed issues not caught by those tests. Passing counts
measure software checks, not forecast skill or national coverage.

- GitHub scheduling: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- Open-Meteo Single Runs: https://open-meteo.com/en/docs/single-runs-api
- Open-Meteo forecast/elevation semantics: https://open-meteo.com/en/docs
- Open-Meteo terms: https://open-meteo.com/en/terms
- W3C focus order: https://www.w3.org/WAI/WCAG22/Understanding/focus-order.html
- W3C non-text alternatives: https://www.w3.org/WAI/WCAG22/Understanding/non-text-content.html
