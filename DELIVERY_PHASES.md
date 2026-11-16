# TerraRaksha delivery phases

Reviewed 15 November 2026. Scope includes every previously agreed sector. Phases are dependency groups, not claims of completed scientific validation. The user now permits a backend host, preferably free. GitHub Pages remains the public read-only dashboard; private records remain authenticated.

## Current evaluation

Engineering foundation: implemented and tested. Independent Nepal forecast skill: not established. Hydrological prediction: simple river baselines only. Exposure: supplied polygon/point analysis only. Remote full application: awaiting account/host provisioning. Commercial or warning-system readiness: not established.

## Phase 1: Lab evaluation and deployment
**Status: In progress.**

Align public/private navigation; keep all existing local tools; deploy authenticated web service and worker with persistent storage.

**Acceptance:** Remote TLS login, restart persistence, backup/restore, worker health and privacy checks pass on the selected host.

## Phase 2: Verified Nepal observations
**Status: Partial foundation.**

Review station/grid mappings, gauge units/datums and metadata; add period-aware rainfall and wind parsing; measure observation coverage.

**Acceptance:** Versioned mapping evidence and compatible observation periods; unresolved stations excluded explicitly.

## Phase 3: Measured weather skill
**Status: Offline evaluator exists.**

Automate paired evaluation, common-case provider comparisons, seasonal/geographic holdouts, uncertainty and extreme-event scorecards.

**Acceptance:** Reproducible results on independent observations, with sample counts, exclusions and baselines; no unsupported national claim.

## Phase 4: Flood and inundation models
**Status: Not implemented beyond river baselines.**

Build reviewed catchments, rainfall-runoff and routing models; add soil/terrain inputs, rating curves and independently tested flood footprints.

**Acceptance:** Held-out event timing, peaks, false alarms, misses and delivered lead time meet a predefined reviewed acceptance protocol.

## Phase 5: Exposure and sector workflows
**Status: Generic engine exists.**

Acquire verified assets and boundaries; connect hazard outputs to cases and reviewed workflows across all sectors.

**Acceptance:** Real inventory lineage, validated spatial results and user-tested decisions; intersection is not damage.

## Phase 6: Other hazards and compound events
**Status: Not implemented as validated engines.**

Develop separate landslide, heat/cold, drought, wildfire and GLOF methods; earthquake detection/impact intelligence, not occurrence prediction.

**Acceptance:** Each hazard passes its own independent evaluation; unsupported products stay unavailable.

## Phase 7: Operational and scientific acceptance
**Status: Not completed.**

Independent review, Nepali accessibility testing, delivery monitoring, security exercises, off-host recovery and commercial data-rights review.

**Acceptance:** Documented external scientific and field acceptance plus host-level operational tests; software tests alone are insufficient.

## Deployment decision

Prepare the existing Docker Compose application for an Oracle Always Free eligible Ampere VM if capacity and signup are available. Do not select paid resources or rely on trial credits. A provider account, owner-controlled SSH access and HTTPS hostname are external prerequisites. Actual quota must be checked in the account; free availability is not guaranteed. No remote instance has been created.

The current runtime uses SQLite on shared local persistent disk with one web service and one worker. An ephemeral free web container is not an equivalent deployment. Preserve raw archive evidence and private state with verified backups; do not publish the archive or credentials to GitHub.

## Immediate work record

- [x] Inspect existing engines, deployment configuration and public/private differences.
- [x] Record phases, gaps and acceptance gates.
- [x] Add shared capability page and consistent lab branding.
- [ ] Provision owner-controlled backend host and hostname.
- [ ] Restore verified archive/state and initialize owner login securely.
- [ ] Verify remote TLS, worker, persistence, restore and authenticated tools.
- [ ] Complete scientific acceptance phases; no calendar promise substitutes for evidence.
