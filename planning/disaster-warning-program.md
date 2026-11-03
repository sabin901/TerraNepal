# Nepal disaster warning program — implementation plan

Prepared 29 September 2026. Status: proposal, not a deployed warning service.

Build a program that helps people in Nepal understand relevant official warnings, monitor changing conditions, and complete useful preparedness actions. Add locally evaluated forecasts progressively. The first users are assumed to be a small team of local volunteers or responders; this assumption can change without rebuilding the data foundation.

The first release should cover official warnings wherever reliable source coverage exists in Nepal, with experimental flood and rainfall-triggered landslide analysis restricted to one pilot basin. Select that basin using actual feed quality and a willing local partner. Do not claim to predict every natural disaster.

## 1. What the program can promise

Keep four products visibly separate:

1. **Official warning:** a traceable message from an identified warning authority, with its original area, severity, instructions and validity period.
2. **Observed condition:** a measurement or detected event, such as a rising river or an earthquake that has already started.
3. **Forecast or experimental assessment:** an estimate for a defined place, period and outcome, with source/model version, uncertainty and limitations.
4. **Long-term preparedness information:** exposure, susceptibility and historical patterns. This is not a timed warning.

Hazard-specific scope:

| Hazard | Useful capability | Boundary | Priority |
|---|---|---|---|
| River flooding | Relay warnings; plot fresh upstream/downstream measurements; evaluate forecasts of station threshold exceedance | Lead time depends on the basin, observations and model. River stage alone does not describe the flood footprint. | First |
| Rainfall-triggered landslides | Combine official rainfall guidance with susceptibility, antecedent wetness and evaluated regional models | Cannot identify the exact hillside and minute of failure from a coarse global model. | First, experimental analysis |
| Flash/urban floods | Relay local warnings and research small-catchment rainfall/runoff indicators | Separate problem from large-river flooding; may offer little lead time and require denser observations. | Later local pilot |
| Heat, cold and severe weather | Relay relevant official forecasts and warnings; support preparation | Preserve provider validity and spatial resolution; do not invent exact lightning-strike predictions. | Second |
| Wildfire | Display detected thermal anomalies and separately evaluated fire-weather conditions | A detected hotspot is not a forecast of ignition or proof of a dangerous wildfire. | Second |
| Earthquakes | Report detected events and long-term seismic hazard; integrate a genuine early-warning feed if one becomes available and is verified | Exact earthquake time, location and magnitude cannot currently be reliably predicted. A catalogue feed is not seconds-level early warning. | Information layer |
| Drought | Monitor sustained deficits and seasonal outlooks with appropriate baselines | Separate meteorological drought from crop impacts and drinking-water shortages. | Later |
| Glacier lake outbursts, avalanches and river blockages | Display verified advisories and site-specific monitoring when partner data exist | Requires specialist assessment and, for rapid warnings, suitable local instrumentation and communications. | Partner-led extension |

USGS distinguishes earthquake detection/early warning from prediction: early warning begins after an earthquake starts. [USGS explanation](https://www.usgs.gov/faqs/what-difference-between-earthquake-early-warning-earthquake-forecasts-earthquake-probabilities). NASA's LHASA is a rainfall-triggered landslide assessment model; its published spatial and temporal scale does not justify household-level certainty. [NASA LHASA](https://github.com/nasa/LHASA).

## 2. Reuse the archive and close the critical gaps

The existing `disaster_archive` has BIPAD incidents and losses, recent river/rain observations, regional USGS events, historical aggregates, immutable source versions and local backups. It supports retrospective research and reproducibility. Its daily collection does not establish warning-service latency, and the initial hydrology window is only two days.

| Input | Existing state | Work required before warning use |
|---|---|---|
| BIPAD historical incidents | Collected | Review reporting bias, duplicates, uncertain event times and administrative boundary changes; construct independently checked event labels |
| BIPAD river/rain observations | Recent records collected | Verify original provider, units, accumulation periods, station coordinates, datum, quality flags, thresholds, update cadence and actual latency |
| Official DHM bulletins/warnings | Official pages identified; no operational connector | Verify a supported machine-readable feed and reuse terms; preserve original messages and updates; use operator-reviewed extraction if only documents exist |
| Weather and river forecasts | Not ingested | Obtain permitted access; retain issue time, valid time, ensemble members, grid/catchment and model version; measure update reliability |
| Terrain, catchments and exposure | Not ingested | Acquire dated/licensed pilot-area layers; check boundaries, resolution and downstream connectivity |
| Road status, shelters and local instructions | Not verified | A local partner must maintain availability, accessibility and last-checked time; never treat an old map as a safe evacuation route |
| Warning receipt and response | Empty response schema exists | Agree on minimal, consented aggregate records for delivery, acknowledgement, action and outcome |

DHM publishes flood/weather bulletin categories and three-day weather products. Those pages establish available products, not a guaranteed API or service-level agreement. [DHM bulletins](https://dhm.gov.np/bulletins), [DHM forecast page](https://www.dhm.gov.np/meteorology-forecast/4).

Candidate supplementary sources:

- **Copernicus GloFAS:** broader river forecast and seasonal context. Verify the current product/version, access rules and local skill; do not substitute its grid for small-stream or street-level forecasts. Preserve reanalysis, reforecast and operational forecasts as distinct products. [GloFAS](https://global-flood.emergency.copernicus.eu/), [forecast evaluation research](https://hess.copernicus.org/articles/27/1/2023/).
- **Access constraint checked 29 September 2026:** the [GloFAS data-store catalogue](https://ewds.climate.copernicus.eu/datasets/cems-glofas-forecast?tab=overview) advises against time-critical operation through that access route. Use it for research; verify a suitable operational delivery arrangement separately. The companion `hazard-data-and-scientific-method.md` records additional sources and scientific assumptions.
- **NASA LHASA:** regional landslide assessment and a useful comparison model. NASA documents best-effort data delivery and server downtime; it cannot be the sole source for a dependable service. Running the model ourselves also requires dependable inputs and operational support. [NASA repository](https://github.com/nasa/LHASA).
- **NASA FIRMS:** later fire detection layer, with acquisition time, delivery latency and confidence retained. Detection products may later be replaced by science-quality versions. [FIRMS data](https://firms.modaps.eosdis.nasa.gov/active_fire/).
- **ICIMOD/local monitoring partners:** specialist mountain hazard and community warning context. Existing community systems are a basis for collaboration. [Community flood warning example](https://www.icimod.org/an-advanced-community-based-flood-early-warning-system/).

Use a CAP-compatible internal alert structure. WMO reported work on Nepal's Common Alerting Protocol implementation in 2025; this does not prove that a usable live Nepal CAP feed is currently available. Discover and test the actual endpoint. [WMO Nepal update](https://public.wmo.int/media/project-update/wmo-strengthens-early-warning-services-nepal), [CAP overview](https://wmo.int/activities/common-alerting-protocol-cap).

## 3. First user experience

Build a mobile-friendly browser application with Nepali and English presentation and a usable text/list view alongside the map.

1. Choose a municipality, ward or a saved place. Manual selection works without granting precise device location.
2. See current official messages, expiry times and affected areas. Keep experimental assessments in a separate labeled layer.
3. Open an alert card to see what is known, where, for which period, the source, when it was last updated, and the source's recommended action.
4. Inspect river/rain charts with units and data-age labels. Missing coverage appears as unknown, never as an all-clear.
5. For responder accounts, record acknowledgement, assign a preparation task, and mark its outcome. A delivered SMS is not evidence that it was read or acted upon.
6. Review the event afterward: what the program knew, what it sent, who acknowledged, and when actions were completed.

First-version pages: overview map/list; place detail; alert detail; source-health page; responder action log; historical replay. Show locally verified shelter information only when an owner and recent verification exist. Offline cached content must clearly show that it is historical, and cannot display a live-safe status.

## 4. Alert and decision rules

Start with understandable, versioned rules and existing forecast products. A custom machine-learning model is optional and must improve on a measured baseline.

**Official-message path:** authenticate the source, validate fields and area, preserve its wording/severity, apply the source's updates/cancellations and display promptly. Once an authorized relay policy exists, authentic official messages need not wait for our experimental model or a manual review queue. An unavailable sensor must not suppress a valid official warning.

**Experimental flood path:** confirm fresh observations and compatible units/datum; compare against the correct station's documented thresholds; examine upstream rainfall and source-defined forecast windows; create an internal assessment with evidence and uncertainty. Use catchment connectivity to map relevance, not simply the geographically nearest gauge. Quantitative threshold rules remain disabled where metadata or necessary observations are unverified.

**Experimental landslide path:** combine locally relevant susceptibility and wetness/rainfall information; evaluate against verified event and non-event periods; present regional elevated potential. Never infer that absence of a reported incident means that no landslide happened.

Notification policy must handle deduplication, meaningful escalation, corrections, cancellation, expiry and cooldowns without hiding a severity increase. Preserve conflicting source claims visibly rather than averaging warning categories. An expired warning is not an all-clear. A stale input changes the data-health state and can stop dependent experimental calculations; it does not erase still-valid official information.

For messages generated by our own experimental rules, the initial workflow ends in a private operator review queue. Human review is an interim control, not evidence of scientific validity. Later release depends on local evaluation and an agreed operating procedure.

Store alert identity, origin/issuer, hazard, status, source severity/certainty/urgency, issued/effective/expiry times, geographic footprint, original text and URL, update/cancellation references, evidence IDs, model/rule version, reviewer decision and delivery history. Do not invent an expiry when one is missing; flag it for source-specific handling.

AI may assist with reviewed translation, document extraction and investigation. Threshold decisions and alert lifecycle must remain reproducible. Dates, place names, severity, numerical values and instructions require strict validation; generative text must not manufacture warnings or safe routes.

## 5. Technical architecture

Use a Python API and collection workers, PostgreSQL with PostGIS for operational geographic queries, a responsive browser application, a durable delivery queue, and object storage for original source files. Keep the current SQLite archive as the existing research record; introduce a versioned export/import path so new work does not overwrite it.

Information flow: source adapters → immutable originals → normalized observations/forecasts/official alerts → quality checks and spatial matching → official relay or experimental assessments → operator/application views → authorized delivery → acknowledgement and response log.

Add these logical tables or equivalent versioned records:

- `station_metadata_versions`: identifiers, location, catchment, unit, datum, thresholds, metadata provenance and validity dates.
- `forecast_runs` / `forecast_values`: issue time, publication/first-seen time, valid time, ensemble, version, units and geometry.
- `official_alert_versions`: original and parsed content, authority, area, validity and lifecycle references.
- `assessments`: outcome being estimated, location, forecast horizon, evidence versions, probability where calibrated, model version and quality state.
- `subscriptions`, `delivery_attempts`, `acknowledgements`: consent, minimal contact data, retries and receipt distinctions.
- `response_actions`, `ground_truth_events`, `evaluation_runs`: verified actions, reviewed outcomes and reproducible evaluation results.

Separate historical collection from the prospective service. Aim initially to check warning/river feeds every 5–15 minutes only if provider cadence and permitted usage support it; choose per-feed intervals after measurement. Fast polling cannot fix a slow provider, and this target does not promise enough lead time for flash floods. Weather/model feeds update according to their actual release cycle.

Store UTC timestamps; display Nepal time explicitly. Track acquisition/observation time, issue time, source availability, retrieval, assessment, queue, provider delivery and acknowledgement separately. Proposed internal target: process eligible messages within one minute after successful ingestion under expected pilot load. This is an engineering target, not end-to-end warning lead time.

For continuous service, budget an always-on host, health monitoring, off-site backups, restore procedures, credentials management and an operator rota. The desktop research automation is not a continuous warning host. Test outages, lost connectivity, delayed jobs, credential expiration, duplicate processing, provider schema changes and clock errors.

Account roles should separate viewer, responder, reviewer and administrator. Limit access to subscriber contacts and household needs; use explicit subscriptions, retention rules and access logs. Aggregate response data for public analysis. Broadcasting, paid messaging and public deployment are later implementation steps requiring concrete configuration and authorization; none are part of this planning turn.

## 6. Validation and release gates

Define the outcome before modeling: for example, whether a specific river station exceeds its documented danger threshold within a specified horizon. The impact outcome, such as flooding in a ward, needs separate observations and evaluation.

1. Audit representative severe events, modest events and quiet periods. Review missing and uncertain labels, and reconcile reports describing one physical event.
2. Reconstruct what inputs were available at the time. Historical final/revised records and reanalysis cannot be treated as contemporaneous forecasts. Our archive only records first-seen history from its own inception; older operational availability may remain unknown.
3. Compare candidate methods to persistence, seasonal baselines, documented threshold rules and relevant existing forecasts. Do not split copies of one event or overlapping rainfall windows across training and test sets.
4. Hold out later seasons and, where applicable, entire basins. Report uncertainty and performance separately by horizon, severity and place. Do not promise one accuracy percentage for all hazards.
5. Run privately on incoming data while normal official warnings continue. Measure missed events, false alerts per location/month, precision/recall, probability calibration, warning duration, lead-time distribution, source outages, delivery latency and acknowledgement.
6. Conduct local message-comprehension and response drills, including low connectivity, disability/access needs and people who cannot read the main interface language.
7. Agree on acceptable trade-offs with a qualified hazard specialist and local response partner before changing private assessments into public warnings. Select thresholds using validation data, not the final holdout.

Software acceptance can be measured early: every displayed warning has provenance and a data-age indicator; lifecycle replay handles updates/cancellations; duplicates do not generate repeated messages; unknown coverage never becomes safe; simulated outages are visible; backup restoration works. Scientific and public-service acceptance requires representative event evidence and local response readiness, not simply a calendar deadline or passing software tests.

## 7. Delivery sequence and effort assumptions

These are planning estimates for a dedicated technical lead with access to a part-time hydrologist/geohazard reviewer and a local coordinator. Access delays, fieldwork and event coverage can dominate elapsed time. No paid resource is purchased by this plan.

| Stage | Indicative effort | Deliverable | Exit condition |
|---|---|---|---|
| Source and pilot audit | 3–5 working days | Feed inventory, station metadata audit, latency samples, one candidate basin and clear outcome | At least one usable official-information path; gaps explicitly recorded |
| Read-only application | 1–2 additional weeks | Map/list, source freshness, official messages, station charts and replay | Demonstration data separated from current data; no false live-status claims |
| Private experimental monitoring | 2–4 additional weeks, after inputs exist | Versioned flood rules, landslide context, evaluation report, operator queue and draft messages | Reproducible baselines and lifecycle/outage tests pass |
| Local operational pilot | Event-dependent; may require a monsoon season or longer | Opt-in delivery, reviewed local instructions, drills and measured response records | Agreed scientific, delivery and response criteria met |
| Expansion | Only after each module qualifies | Further basins and hazard modules | Each new geography/hazard passes its own review |

The first useful software demonstration can precede a scientifically credible forecast model. Neither software delivery nor a quiet month demonstrates that a warning service is dependable.

Budget separately for hosting/database/storage, observation or forecast access, SMS/voice delivery, field verification, specialist review and operational coverage. Estimate SMS costs from recipients × message segments × updates/retries using the actual provider quote. A local read-only prototype can reuse the current machine; dependable public operation is an ongoing responsibility rather than a one-time software cost.

## 8. Concrete first backlog

1. Audit existing station metadata and sample actual observation/publication delays; produce a coverage map and list of unresolved units.
2. Verify the official-warning delivery format, authority identification, update/cancellation behavior and access limits. Begin preserving original warning versions and forecast issue times.
3. Select one pilot basin with usable observations, verified downstream geography and a local partner; document the selection rather than assuming the basin with most reports is best.
4. Build read-only map/list and place pages over the existing archive, with separate tabs for official alerts, observations and research assessments.
5. Add a historical replay and a clearly labeled synthetic test mode for development. Synthetic messages never enter real delivery channels.
6. Implement source-health indicators and a tested official-alert lifecycle before adding custom forecasts.
7. Establish event labels, simple baselines and the prospective evaluation log; then prototype flood rules privately.
8. Add response recording and draft, evidence-linked message templates. Field-test comprehension with a partner before opt-in delivery.

Measure success by useful warning lead time and completed protective actions, alongside forecast and system performance. WMO's framework includes risk knowledge, monitoring/forecasting, communication, and preparedness/response; the program must address all four to be useful. [WMO Early Warnings for All](https://public.wmo.int/all-activities/build-resilience/early-warnings-all).
