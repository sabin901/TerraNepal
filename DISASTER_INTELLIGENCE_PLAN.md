# TerraRaksha disaster intelligence plan (formerly TerraNepal)

Research date: 15 November 2026. Proposed technical strategy; audience scope follows the
user's confirmed all-sector ambition. No outreach, accounts, hosting changes or deployment
were performed for this planning task. AI review roles do not substitute for human scientific
or institutional approval. Research findings and recommendations are distinguished below.

## Product definition and scope

TerraNepal should connect trustworthy evidence about hazards to places, people, assets and
reviewable decisions across preparedness, response and recovery. Its purpose is to answer:
what changed; where it may matter; who/what is exposed; how strong the evidence is; what
requires review; and what actually happened afterward.

All intended audiences remain in scope: the public, farmers, municipal/provincial/national
disaster teams, infrastructure/hydropower operators, transport/logistics, health, education,
water/sanitation, tourism, responders, researchers and environmental/risk assessors.
Delivery order follows evidence dependencies, not exclusion of audiences. A bounded geographic
validation area can include all these roles; it is not a decision to serve only one customer.

National coverage must carry explicit assessed/unassessed geography and product availability.
A blank area is not a safe area. No universal disaster score or universal prediction formula.

## Research findings about Nepal's ecosystem

SATARK's own description combines DHM, ECMWF and IMD products with BIPAD exposure/vulnerability
and hazard thresholds; it includes agriculture and NAVIGATE road services [1]. RIMES reports
additional hazard and evacuation-route work [2]. BIPAD has an impact-based flood forecasting
pilot history [3]. DHM publishes forecasts, warnings and agrometeorological bulletins [4].
ICIMOD HIWAT provides regional high-impact weather tools [5].

These public descriptions establish overlap. They do not establish complete current coverage,
performance, uptime, accessibility, open APIs or data rights. We have not audited those systems
or proved that any proposed differentiator is absent from them.

Proposed differentiation hypotheses:
- Reconstruct what information was actually available at a historical decision time.
- Show revisions, disagreements, missingness and consequences for an assessment.
- Compare forecast providers on identical verified local cases.
- Produce auditable, bilingual, place/asset-specific situation briefs.
- Track review and action outcomes with an evidence trail.
- Interoperate with existing official products rather than invent an issuing authority.

These become an advantage only if demonstrated in real workflows. No customers, partnerships,
government endorsement or willingness to pay were established by this research.

## Current foundation and gaps

The repository already has observation archives/revisions, weather provider collection,
original-run acquisition, raw weather evidence retention, quality/freshness checks, exploratory
river baselines, prospective records, an offline weather evaluator, a candidate station
registry and a static public exporter. The recent hardening fixed several audit defects.

It does not have independently established Nepal-wide forecast skill, approved nationwide
station/grid/reach mappings, calibrated disaster probabilities, validated flood depths,
complete sector workflows or operational warning availability. Persistence and damped trend
are useful baselines, not a rainfall-runoff model. The older METHODS.md needs reconciliation
with newer original-run collection and evaluation documentation; documentation dates must
not obscure which component actually exists.

## Shared product engine

1. Source contracts: authority, access/rights, variables, units, measurement windows, latency,
   geographic/temporal coverage, version and failure behavior.
2. Immutable evidence: exact permitted responses, request receipts, hashes and parser versions;
   retain observation time AND acquisition time, including corrections and withdrawals.
3. Verified geographic registry: station, grid cell, reach, catchment, administrative boundary,
   asset, CRS, elevation/datum, relocations and reviewed mapping evidence.
4. Hazard analysis: provider baselines, independently evaluated local corrections and separate
   hydrological, landslide, heat, drought/fire and other hazard methods.
5. Exposure/capacity: dated population estimates, assets, services, roads, shelters and local
   capacities. Public infrastructure detail must be separated from restricted operational data.
6. Impact assessment: intersect hazard and exposure, then apply explicit vulnerability models
   only where supported. An exposed building is not automatically damaged; a nearby road is
   not automatically closed; a catalog entry is not a verified unique disaster.
7. Decision workspaces: prepare/review/approve a brief, assign a verification task, record a
   rationale, track expiry/correction and preserve the later observed outcome.
8. Public delivery: accessible Nepali/English explanations, official warning provenance,
   low-bandwidth data, offline dated briefs and visibly unavailable products.
9. Verification: measure source coverage, forecast skill, delivered lead time, missed events,
   false alarms, uncertainty and usefulness of the workflow.

An event case is the core product record. It links a geography and valid period to immutable
inputs, official bulletins, hazard assessments, exposure versions, review status, actions,
corrections and outcomes. Observation, forecast, experimental inference, scenario, confirmed
impact and official warning remain distinct types.

## Product-and-evidence matrix

| Audience | Proposed workflow | Additional evidence required | Claim boundary |
| --- | --- | --- | --- |
| Public/households | Local situation brief, weather outlook, official notices, service information | Location coverage, validated translations, dated official sources | No invented safety/all-clear or evacuation order |
| Municipal/disaster teams | Ward/site review queue, preparedness brief, shelter/resource status | Verified boundaries/assets/capacity, local procedures, official warning lifecycle | Review priorities are not automatic evacuation decisions |
| Farmers/livestock | Rain/heat windows, crop-stage and livestock exposure briefing | Crop calendars, soil/irrigation, crop/livestock thresholds and agronomic review | No generic forecast-to-yield-loss conversion |
| Hydropower/utilities | Upstream evidence, intake/access exposure, operating review packet | Catchment/gauges, rating curves, operating rules, asset data, engineering review | No automatic gate control or generation/loss promise |
| Roads/logistics | Segment exposure, reported closure changes and inspection priorities | Road topology, verified closures, drainage/slope/bridge information | Unreported closure does not mean passable |
| Health | Heat/flood service preparedness and facility exposure | Locally reviewed thresholds, facility capacity, health authority guidance | No individual diagnosis or unsupported disease prediction |
| Schools | School/access exposure, official guidance and continuity review | School roster, access conditions, approved closure/continuity procedures | No autonomous closure instruction |
| Water/sanitation | Intakes/pumps/services exposed to hazard scenarios | Network assets, operating state and actual water-quality evidence | Flood proximity does not establish contamination |
| Tourism/outdoor work | Route/location weather and official advisory briefing | Route condition, elevation, local reports and specialist review | No route-safety guarantee from weather alone |
| Responders/NGOs | Incident evidence, verified needs and resource/coverage gaps | Authorized field verification, privacy rules, resource status | Unverified community reports remain separate |
| Researchers | Versioned dataset export, replay, common-case validation | Source contracts, station approval, benchmark protocol | Archive size is not scientific accuracy |
| Environmental/risk assessors | Reproducible site history and scenario evidence pack | Asset/site details, hazard/exposure/vulnerability methods | No unsupported insured-loss or engineering certification |

Shared analysis should feed these views. Adding a sector tab is not evidence that the sector
method is valid. Every sector release needs a decision owner, accepted inputs, permitted
claims, evaluation test and explicit unsupported cases.

## Hazard methods and release boundaries

| Hazard | Useful intelligence product | Analytical path | Validation needed |
| --- | --- | --- | --- |
| River flooding | Reach/catchment evidence, outlooks and asset exposure | Verified gauges + basin rainfall + soil/terrain/land cover + hydrological baseline/routing | Event timing/peaks, missed/false alerts, independent impacts; hydraulic surveys for depth |
| Urban/flash flooding | Drainage/corridor review and rainfall monitoring context | High-resolution forcing, drainage/terrain, rapid observations and routing | Lead time shorter than real source/delivery latency is not useful warning |
| Rain-triggered landslide | Susceptibility plus rainfall-conditioned corridor assessment | Geology/slope/land cover, antecedent rainfall/moisture, LHASA benchmark | Independent landslide inventories and non-event periods; local slope specificity |
| GLOF/landslide dam | Lake/valley register, satellite-change review and downstream scenarios | ICIMOD inventory, dated imagery, dam/valley terrain, breach/routing scenarios | No exact breach-time claim from periodic imagery or weather alone |
| Heat/cold | Local outlook plus exposure/action planning | Temperature/humidity/duration/night-time conditions + representative observations | Local thresholds and health/agricultural relevance; do not import thresholds blindly |
| Drought | Rainfall/soil/vegetation anomalies and water/crop context | Long consistent baselines, seasonal climate, soil moisture and land cover | Drought type and baseline validity; no instant district-wide agricultural loss claim |
| Wildfire | Satellite detections, weather/susceptibility context and exposure | FIRMS detections, fuel/vegetation, wind and moisture | Detection latency/cloud/terrain and false positives; no guaranteed ignition timing |
| Earthquake | Detected-event/revision/shaking/exposure briefing | USGS/Nepal-authority event products, official shaking where available | No exact future earthquake prediction; catalog polling is not seismic early warning |

Compound events need an explicit causal scenario (e.g. slope failure → blockage → breach →
downstream flood), not addition of incompatible risk scores. Upstream catchments and hazards
can cross Nepal's border, so national clipping must not erase causal upstream context.

## Candidate data register

These are candidate inputs, not claims that all APIs, licensing or ingestion are completed.

| Source | Intended use | Access/quality limitation |
| --- | --- | --- |
| DHM [4] | Official forecasts/warnings, gauges and metadata | Verify available interfaces, update/cancel semantics, rights and station units |
| BIPAD/SATARK [1,3] | Incidents, exposure and official context | Revisions/coverage/duplicates; source-specific access and redistribution not assumed |
| ECMWF/GFS/Open-Meteo [6] | Forecast runs and baseline weather | Record init/publication/acquisition; terrain bias; hosted free API is noncommercial |
| NOAA GHCNh [7] | Temperature verification candidates | Delayed/uneven station coverage, QC/source semantics, relocation/mapping review |
| NASA GPM IMERG [8] | Catchment precipitation estimates | 0.1-degree, half-hour estimates; Early Run approximately four-hour latency, not a gauge |
| GloFAS [9] | Hydrological baseline/context | Reach matching, model version and local performance; not a street-level flood map |
| NASA LHASA [10] | Landslide benchmark/context | Coarse/global product; Nepal corridor/slope validation still required |
| ICIMOD inventories/HIWAT [5,11] | Cryosphere and regional weather context | Inventory dates, product rights/interface and actual local skill must be checked |
| Copernicus DEM/Sentinel [12] | Terrain and dated change/flood-mapping evidence | Resolution, vertical/surface semantics, acquisition delay and image-processing errors |
| WorldPop/OSM/local asset sources [13,14] | Population/assets/network exposure | Estimated population, incomplete map features, reference dates, applicable licence terms |
| USGS [15] | Detected events and subsequent revisions | Source latency and region; no future earthquake prediction |

Satellite estimates/reanalysis must never silently become independent gauge truth. A 30m
terrain grid or 100m population grid does not imply equivalent flood-depth or household accuracy.
Earthdata/Copernicus accounts may be required for some endpoints; no accounts are created by
this plan. Free data, free processing and unrestricted commercial redistribution are different.

## Scientific validation and operational gates

- Define hazard, geography, variable, decision horizon, thresholds, baseline and failure costs
  before examining held-out test results. No universal 90% accuracy target.
- Confirm units, observation windows, mapping and chronology. Retain unresolved conflicts.
- Compare models on the same cases; separate acquisition-time prospective evaluation from
  retrospectively reconstructed studies. Later revisions cannot leak into historical inputs.
- Use untouched chronological events plus geographic/season/elevation holdouts. Test ordinary
  conditions and extremes. Report sample size, uncertainty, coverage and all exclusions.
- Weather: MAE/bias and useful probabilistic scores where appropriate. Flood/hazard events:
  detection, false-alarm ratio, missed-event rate, peak/timing errors and useful lead time.
- Exposure/impact: verify asset location, footprint overlap, population assumptions and observed
  impacts independently. A good weather score does not validate an impact model.
- Delivered lead time = event onset minus the time usable information actually reached the user.
  Do not report theoretical model lead as if it survived source/scheduler/delivery delays.
- Shadow operation: preserve assessments before outcomes; issue no experimental public warning;
  test stale feeds, corrupted inputs, delayed corrections, outages and restore/rollback.
- User acceptance: distinguish observed/forecast/experimental/official content; correct source
  interpretation, preparation time, error rates and accessible bilingual comprehension.
- Publish only the scope that passes. Do not declare warning readiness without accountable
  human scientific, operational and authority-specific review.

WMO's four pillars encompass risk knowledge; observation/forecasting; communication; and
preparedness/response [16]. Technical output alone is not an end-to-end warning system.
UNDRR defines risk through hazard, exposure, vulnerability and capacity [17]; no arbitrary
multiplication of uncalibrated dashboard scores implements that definition.

## Architecture and hosting

Extend the existing Python archive/worker and static exporter; avoid a wholesale rewrite.
Use a modular monolith with explicit contracts. Keep SQLite for current research. Introduce
PostgreSQL/PostGIS only when multi-user spatial operations require it [18]; large rasters
belong in file/object storage with catalogued lineage. Separate analysis, review and publication.

Boundary standards: CAP for official alert identity/update/cancel/expiry where a verified
source supports it [19]; OGC interfaces when interoperability is needed [20]; STAC for dated
Earth-observation asset catalogues [21]. CAP compatibility is not authorization to issue alerts.
Do not assume Nepal offers any particular machine-readable feed without checking it.

Keep GitHub Pages/Actions now, as the user chose. It can host public information, dated briefs,
approved maps and reproducible research collection. GitHub documents schedule delays/dropped
jobs [22]; it does not provide the independent worker/monitor required for a time-critical
warning promise. A future persistent backend, private organizational workspaces, independently
triggered monitoring and backup service would require a separately agreed hosting/budget decision.
No such migration is approved or performed here.

## Work packages and acceptance criteria

1. **Scope/claim register:** every audience and feature mapped to decision, evidence, allowed
   output, unsupported conditions and responsible reviewer. Reconcile old methods docs.
2. **Spatial/evidence foundation:** inventory candidate basins across verified gauges, dated
   exposure, independent events and permitted data. Select geography on evidence, not fame.
   Include public, municipal, agricultural and infrastructure views in its validation exercise.
3. **Event-case engine:** build immutable event/forecast/bulletin/asset references and a replayable
   local situation brief with changes, gaps and official provenance. No invented impact counts.
4. **Hazard/exposure analysis:** build source-aware spatial joins and baseline products; preserve
   distinctions between a scenario, exposure, predicted damage and observed damage.
5. **Verification workspace:** canonical matched cases, event cohorts, model/run versions,
   predeclared tests, calibration/holdouts and reports reproducible from recorded inputs.
6. **Role workspaces/public experience:** shared engine, sector-specific views and extra evidence,
   accessible tables/maps, Nepali/English critical content and dated offline exports.
7. **Readiness review:** recovery drills, delivery measurement, source rights, human scientific
   review and actual user workflow evaluation before broader operational claims.

Engineering milestones can be planned in weeks. Scientific validation depends on accessible
historical ground truth and prospective observations, including relevant seasons/events; no
fixed number of coding weeks proves it. The next work package is the event-case/evidence and
geographic foundation, not another unvalidated prediction feature.

## People, institutional work and economics

AI roles can implement, test, research and challenge designs. They cannot be counted as a
hydrologist's independent sign-off, a municipal user study or government endorsement.
Eventually the relevant human scientist and actual users must inspect the methods/workflow.
No outreach is authorized by this plan; engineering/public-data work can continue meanwhile.

Public benefit remains the product goal. Institutional revenue, if pursued, is a hypothesis:
maintained organizational workspaces, local evidence integration, reports, support and
service commitments might be paid for. No demand or procurement route has been established.
Do not charge on a claim of guaranteed disaster prediction. Open-Meteo's free hosted API is
noncommercial [6]; monetization requires an appropriate permitted access arrangement or a
separately assessed direct-data/self-hosted path. Open source is not zero operating cost.

Before institutional presentation prepare: precise scope; source/rights register; replayable
case study; independent validation report; failure/correction examples; measured delivery;
recovery procedure; interoperability/export sample; maintenance responsibility; and explicit
requests for technical/user feedback rather than an unsupported endorsement claim.

## Primary references

1. https://satark.bipadportal.gov.np/
2. https://mc4.rimes.int/wp-content/uploads/2025/05/RIMES-2024-Annual-Report.pdf
3. https://www.anticipation-hub.org/news/developing-an-impact-based-forecasting-model-within-nepals-national-disaster-information-management-system-the-bipad-portal
4. https://dhm.gov.np/mfd/ and https://dhm.gov.np/agromet-services/weekly-weather-bulletin
5. https://servir.icimod.org/science-applications/high-impact-weather-assessment-toolkit/
6. https://open-meteo.com/en/terms and https://open-meteo.com/en/docs/single-runs-api
7. https://www.ncei.noaa.gov/products/global-historical-climatology-network-hourly
8. https://science.data.nasa.gov/disasters/data-gallery/gpm-imerg-precipitation
9. https://confluence.ecmwf.int/pages/viewpage.action?pageId=340759426
10. https://gis.earthdata.nasa.gov/portal/home/item.html?id=9e65a60a305b458bba6330baa93c0238
11. https://lib.icimod.org/records/p869r-n4132
12. https://sentinels.copernicus.eu/-/copernicus-dem-30-metre-dataset-now-freely-available
13. https://www.worldpop.org/
14. https://www.openstreetmap.org/copyright
15. https://www.usgs.gov/programs/earthquake-hazards/earthquake-facts-earthquake-fantasy
16. https://public.wmo.int/all-activities/build-resilience/early-warnings-all
17. https://www.undrr.org/terminology/disaster-risk
18. https://postgis.net/workshops/postgis-intro/indexing.html
19. https://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2.html
20. https://developer.ogc.org/
21. https://github.com/radiantearth/stac-spec
22. https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
