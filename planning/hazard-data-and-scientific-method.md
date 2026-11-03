# Hazard data and scientific method for the Nepal program

Research checked 29 September 2026. This is a source catalogue and methodology proposal. Newly listed external datasets have not been bulk-downloaded, integrated or validated for Nepal by this project. Provider documentation was checked online; endpoint availability, service latency and local predictive skill require separate testing.

## Present archive

The saved collection manifest contains 64,383 BIPAD incident reports dated 2011–2026, 18,465 rainfall records and 36,565 river readings in an initial two-day window, 1,932 USGS regional earthquakes, and DesInventar annual/hazard aggregates for 1971–2013. Counts represent source records, not necessarily unique physical events. The earthquake selection includes neighboring countries. The historical aggregates are not individual event microdata.

No predictive hazard model is currently running. The archive preserves observations, reports and source revisions. Station units, rainfall accumulation conventions, thresholds and datum still need verification before quantitative warning rules use those fields. A two-day hydrology sample is not a multiyear training dataset.

## Online sources and their role

| Data and provider | What it contributes | Coverage, access and limitations | Project status |
|---|---|---|---|
| [BIPAD](https://bipadportal.gov.np/api/) | Incident dates/places/types, reported impacts and recent river/rain records | Nepal; public API already used. Reports can overlap, be revised or omit events. | Collected in existing archive |
| [DHM data services](https://dhm.gov.np/pages/data) and [request form](https://dhm.gov.np/request-data) | Historical station rainfall, river stage/discharge and metadata needed to calibrate local models | Formal request process and pricing information; station availability and permitted use must be checked. No request or payment submitted. | Additional historical series not obtained |
| [DHM bulletins](https://dhm.gov.np/bulletins) | Authoritative weather/flood messages and forecast context | Verify actual issuance/validity, source format and delivery timeliness. A bulletin webpage is not proof of a stable API. | Warning connector planned |
| [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) | Spatial rainfall estimates, including upstream areas beyond Nepal's border | Half-hourly estimates; Early Run has approximately four-hour latency. Product/version and format determine units/scaling. Earthdata/PPS access requirements vary by route. Gauge comparison is necessary. | Found; not ingested |
| [UCSB CHIRPS v3](https://chc.ucsb.edu/data/chirps3) and [data documentation](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/README-CHIRPSv3.0.txt) | Long rainfall history for seasonality, anomalies and retrospective analysis | 1981 to near-present, 0.05-degree grid, satellite-plus-station estimates. Preliminary and final products arrive on different schedules; not immediate rainfall telemetry. Public download documentation available. | Found; not ingested |
| [ERA5-Land](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=overview) | Historical modeled soil moisture, temperature, precipitation and land-water conditions | Hourly, 1950 onward, approximately 9 km native grid. Reanalysis reconstructs the past, not an issued forecast. [Download interface](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=download) requires login and licence acceptance. | Found; not ingested |
| [ECMWF Open Data](https://www.ecmwf.int/en/forecasts/datasets/open-data) | Future precipitation, temperature, wind and ensemble weather forecasts | Public forecast subset, generally 0.25-degree grid. Short rolling retention means issue-time snapshots should be archived promptly. The provider lists separate routes/terms for other products. | Found; not ingested |
| [GloFAS forecast data](https://ewds.climate.copernicus.eu/datasets/cems-glofas-forecast?tab=overview) | Ensemble river-discharge forecasts; regional comparison model | Combines weather forecasts with LISFLOOD hydrology. The data-store page explicitly advises against its use for time-critical operations. Verify a suitable operational delivery route separately. | Found; research access only proposed |
| [NASA SMAP L4 SPL4SMGP v8](https://nsidc.org/data/spl4smgp/versions/8) | Estimated surface/root-zone soil wetness, informing runoff and landslide preconditions | Three-hourly fields, 9 km grid, since March 2015. Satellite observations assimilated into a land model; not a direct sensor at every depth/location. Earthdata login required. | Found; not ingested |
| [Copernicus DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) | Elevation, slope and terrain context | Global 30 m and 90 m products; registered-user download routes. It is a surface model that includes vegetation/buildings, not surveyed riverbed geometry. [Product handbook](https://dataspace.copernicus.eu/sites/default/files/media/files/2024-06/geo1988-copernicusdem-spe-002_producthandbook_i5.0.pdf). | Found; not ingested |
| [HydroBASINS](https://www.hydrosheds.org/products/hydrobasins) and [HydroRIVERS](https://www.hydrosheds.org/products/hydrorivers) | Catchment boundaries and upstream/downstream river connectivity | Public continental downloads include Asia. Check scale, licensing, geometry and local modifications. Does not capture every drain, levee or newly blocked channel. | Found; not ingested |
| [Sentinel-1](https://documentation.dataspace.copernicus.eu/Data/SentinelMissions/Sentinel1.html) | Radar imagery for mapping observed inundation and checking forecast footprints | Radar can observe through clouds; acquisition timing and terrain/urban effects limit coverage. Observed flood maps are validation evidence, not forecasts. [ESA application description](https://www.esa.int/Applications/Observing_the_Earth/Copernicus/Sentinel-1/Emergency_response). | Found; not ingested |
| [NASA LHASA](https://github.com/nasa/LHASA) and [model viewer documentation](https://pmmpublisher.pps.eosdis.nasa.gov/about) | Existing landslide assessments and a scientific comparison model | Combines rainfall, prior rainfall, wetness, snow, slope, lithology and fault proximity. Product scale, latency and best-effort service matter. Model output is not independent truth for evaluating another model. | Found; not ingested |
| [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/) | Active-fire and thermal-anomaly detections | Global near-real-time detections can arrive within about three hours after observation; acquisition timing is an additional limitation. Download/service credentials depend on route. Not a forecast of ignition. | Found; not ingested |
| [USGS catalogue](https://earthquake.usgs.gov/fdsnws/event/1/) | Detected earthquake time, location, magnitude and depth | Existing regional collection; magnitude completeness and reporting delays change. Not an earthquake prediction feed. | Collected |
| [ICIMOD Nepal lake inventory](https://rds.icimod.org/metadata/19304eac-3615-40c0-be9f-cc610e9b1138) | Historical lake locations and mountain-hazard context | This specific inventory was published in 2011 from 2005/2006 imagery. It must not be used as a current dangerous-lake list without updated imagery/field assessment. | Found; historical context only |
| [WorldPop Nepal population example](https://hub.worldpop.org/doi/10.5258/SOTON/WP00531) | Estimated population exposure | This catalogue entry covers older modeled years including 2020. Choose the correct analysis year and compare with census/local records; it does not describe current evacuation needs. | Found; not ingested |

Additional pilot-specific requirements include dated land cover, soil/geology, channel cross-sections or rating curves, reservoir operations where relevant, verified roads/bridges/shelters, and community response information. These have not been acquired. Public global layers cannot fully replace local surveys.

Three dimensions must be recorded separately: spatial resolution, observation/model timestep, and delivery latency. Resampling a coarse field to a finer grid creates no new measurements. Several products may share inputs, so agreement is not automatically independent corroboration.

## Scientific reasoning

Scientists define a specific outcome and forecast horizon, describe a mechanism, fit uncertain parameters or statistical relationships, and test predictions against observations they did not use for fitting. Physics-based, statistical and machine-learning methods can be combined. An assumption is a documented simplification whose consequences should be examined.

### River floods

Inputs include measured and forecast rainfall across the upstream basin, current river conditions, soil wetness, snowmelt where relevant, terrain, land cover, channel properties, and reservoir behavior where relevant. A rainfall-runoff model estimates how much water infiltrates, evaporates, is stored, and reaches the river. Routing estimates downstream movement. A hydraulic model with adequate channel/floodplain geometry is needed to estimate inundation depth and extent.

Scientists calibrate uncertain process parameters against observed discharge and test at other times/locations. For example, GloFAS v5 calibration uses historical precipitation, temperature and evapotranspiration, with discharge and reservoir observations where available. [GloFAS calibration documentation](https://confluence.ecmwf.int/spaces/CEMS/pages/673567677/GloFAS%2Bv5%2Bcalibration%2Bdata).

Our first target could be: probability that a particular station exceeds its documented danger stage within the next six hours. The horizon is a proposed research target, not demonstrated lead time. It requires sufficient observations and metadata. Predicting flooded households is a separate, more demanding task.

### Rainfall-triggered landslides

Slope, material strength and geometry create susceptibility. Rain and snowmelt can change wetness and pore pressure, affecting stability. Empirical approaches compare rainfall intensity/duration and prior rainfall with landslide occurrences; physical approaches model water and slope stability; machine learning fits combinations of predictors to inventories.

A Nepal study by Dahal and Hasegawa examined 677 historical landslides, using 193 with associated rainfall to estimate regional thresholds. This illustrates how data availability constrains scientific inference. Its thresholds are research results from that sample, not a rule we should apply unchanged to every present-day slope. [2008 study](https://www.sciencedirect.com/science/article/pii/S0169555X08000172).

A study in the Annapurna region linked both accumulated monsoon rainfall and daily rainfall to landsliding, with a slope-stability model explaining why the triggering rainfall changes as the season progresses. [Gabet and colleagues, 2004](https://www.sciencedirect.com/science/article/abs/pii/S0169555X04001114). This supports measuring antecedent wetness rather than using today's rainfall alone.

### Other hazards

- Fire assessment separates observed hotspots from conditions favoring ignition/spread, such as fuel, moisture, wind and terrain.
- Heat/cold assessment uses forecast temperature, duration and relevant humidity/wind metrics, with local thresholds and exposure.
- Drought assessment compares deficits and soil/vegetation/water conditions to a consistent seasonal baseline; different drought impacts require different indicators.
- Earthquake hazard research uses catalogues, faults, geodesy, geological history and ground-motion relationships. Exact earthquake prediction is not currently reliable; early warning begins after rupture starts. [USGS explanation](https://www.usgs.gov/faqs/what-difference-between-earthquake-early-warning-earthquake-forecasts-earthquake-probabilities).
- Mountain lake/avalanche warning requires specialist site information and appropriate instrumentation; an old satellite inventory does not establish when failure will occur.

### Uncertainty and testing

Use ensembles to explore plausible weather/input/parameter states. The fraction of simulations exceeding a threshold is a model-based estimate, not proof. Check whether predicted probabilities match observed frequencies and whether the model improves on simple alternatives. [ECMWF probability calibration](https://confluence.ecmwf.int/pages/viewpage.action?pageId=240849388), [forecast verification](https://confluence.ecmwf.int/spaces/WLS/pages/394992254/Verification).

For our program, separate training, threshold selection and final evaluation by event, season and where appropriate basin. Do not randomly divide nearby copies of one storm between train/test. Preserve issue-time inputs; later corrected rainfall and reanalysis cannot be silently substituted for what an operational system knew. Missing reports are uncertain labels, not proven non-events.

Evaluate missed events, false alerts per location/time, lead-time distribution, probability reliability, severe-event performance and delivery gaps. Overall accuracy can hide failure on rare disasters. Report uncertainty where only a few major events exist. Review how climate, river morphology, roads and land cover have changed since the training period.

## Assumptions we must explicitly examine

| Assumption | How to check it |
|---|---|
| A satellite/grid estimate represents rainfall over the target basin | Compare with quality-controlled local gauges; examine elevation, season and storm-intensity biases |
| River stage and the warning threshold use the same datum and station identity | Verify metadata, relocations, unit conversions and dated threshold definitions |
| Stage can be converted to discharge reliably | Obtain a valid rating curve and inspect shifts after channel change or sedimentation |
| The nearest station represents the community's river | Use upstream connectivity and catchment geography, not distance alone |
| Historical event reports are sufficiently complete | Reconcile field records and independent imagery; flag unknown periods and reporting differences |
| Historical relationships remain useful | Test on later seasons, other basins and changed land-use conditions; monitor drift |
| Inputs will arrive early enough | Measure end-to-end source availability and message-receipt delays |
| Multiple sources provide independent confirmation | Trace shared model/observation inputs before interpreting agreement |
| A warning translates to reduced harm | Measure receipt, comprehension and completed actions; do not equate sent messages with protection |

Exposure and vulnerability are separate from the physical hazard. Population, buildings and access information help estimate who may be harmed and what support is needed. [UNDRR exposure definition](https://www.undrr.org/terminology/exposure).

## First acquisition priorities

1. Verify existing station metadata and obtain several seasons of appropriate DHM measurements if available, including non-disaster periods and quality flags.
2. Archive actual weather forecast runs with issue/valid/first-seen times, starting prospectively; do not assume the public rolling archive preserves past runs indefinitely.
3. Acquire pilot-area rainfall history, terrain and upstream catchment geometry, retaining cross-border catchments.
4. Evaluate soil wetness products and independent satellite/field evidence of events.
5. Add dated population/assets and maintained local response information to convert hazard assessments into useful actions.

Source-specific findings affecting implementation:

- The GloFAS EWDS catalogue carries a warning against time-critical use through its data-store access route. Treat this route as research access unless a suitable delivery arrangement is verified.
- NSIDC's SMAP page currently displays a geolocation notice for 14 May–28 July 2026, with reprocessing information. Determine the applicability and corrected granule versions for the exact selected product before using that period; the banner alone does not establish which L4 records are affected.
- Copernicus changed access to its DEM 30 m **view service** in August 2026. This is distinct from the documented registered-user GLO-30 download eligibility. [Service notice](https://dataspace.copernicus.eu/news/2026-8-25-copernicus-dem-30m-view-service-update).

The immediate scientific deliverable is a reproducible dataset for one explicit basin/outcome, with an assumption register and a baseline evaluation. It is not a universal disaster probability generated from incident counts.
