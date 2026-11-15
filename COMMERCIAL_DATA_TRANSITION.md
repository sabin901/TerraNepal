# TerraRaksha commercial data transition

Prepared 15 November 2026. This is an implementation plan, not a completed migration,
a commercial licence clearance or evidence of forecast accuracy. The user chose to
publish the current project as noncommercial research while preparing a separate
company option. Existing source identities, evidence and attribution must survive.

## Recommended sequence

1. Build a bounded direct NOAA GFS acquisition/decode experiment outside the public
   collection path. Establish source semantics and resource measurements first.
2. Repeat for direct ECMWF IFS open data. Do not remove the current research providers
   until an independently tested replacement meets the product's requirements.
3. Evaluate source rights for every remaining feed, especially BIPAD and discharge.
   A weather-source migration alone does not clear the whole company product.
4. Review public claims, attribution, infrastructure budgets and observed availability
   before enabling company publication. Commercial access does not establish warning
   reliability or locally verified scientific skill.

## Access findings checked against primary sources

NOAA/NWS information is generally public domain unless otherwise noted. Its terms
permit lawful use while prohibiting ownership and endorsement misrepresentation.
NOMADS links directly to these terms and supplies GRIB access/filter tools [1–3].
Verify the chosen product carries no contrary notice and retain attribution.

ECMWF explicitly permits commercial use and redistribution of its open subset under
CC BY 4.0 and its terms. Some delivery/service arrangements can incur charges. The
free subset is available as GRIB2 with a rolling archive and several mirrors; the
official client selects parameters and forecast steps [4–5]. At the reviewed date,
IFS forecasts include native three-hour steps through 144 hours; later steps depend
on cycle. Parameter names include `2t`, `tp` and `10fg`. These do not establish that
its gust interval or precipitation accumulation matches our existing hourly product.

Open-Meteo's free hosted API remains noncommercial; its terms list commercial products
and promotional activities as commercial uses [6]. The data's attribution licence
and permission to use the hosted service are separate questions. Do not simply change
the existing UI's licence wording or assume no subscription revenue means noncommercial.

## Proposed source contract

Use separate identifiers such as `noaa_gfs_direct` and `ecmwf_ifs_direct`, with a
versioned processing policy. They are not interchangeable with Open-Meteo's
`gfs_global` and `ecmwf_ifs025`: grid selection, elevation adjustment, interpolation
and variable processing can differ. A provider transition starts a new evaluation
series; do not pool historical metrics silently.

Each retained acquisition must record:

- Approved HTTPS host/path, request parameters, acquisition start/end, HTTP status,
  transport errors, checksum and exact permitted response bytes.
- Model, model/version metadata when supplied, initialization in UTC, forecast lead,
  valid time, and publication time only if the provider actually supplies it.
- GRIB edition, parameter identity, level/type, units, `stepType`, start/end steps,
  statistical processing and missing-value semantics; preserve original keys.
- Requested point/region, returned grid, latitude/longitude convention, grid ordering,
  native resolution and sampling method. Model orography is not surveyed site height.
- Parser/library versions, transformations, sample quality records and raw-reference
  identifiers. Archive availability is acquisition time, not model initialization.
- Applicable source terms/attribution URL and date checked; no claim of endorsement.

Candidate variables to verify from real GRIB messages:

| Product | Candidate parameter | Required interpretation |
| --- | --- | --- |
| GFS | `TMP` at 2 m above ground | Verify kelvin, convert to Celsius using K − 273.15, retain native valid time |
| GFS | `APCP` at surface | Verify kg/m² and accumulation start/end; water-equivalent kg/m² corresponds to mm |
| GFS | `GUST` at surface | Verify m/s and instantaneous/statistical semantics; do not relabel automatically as a 10 m interval maximum |
| IFS | `2t` | Verify kelvin and 2 m parameter identity; convert as above |
| IFS | `tp` | Verify metres of water equivalent and cumulative/interval semantics; convert to mm only after checking units |
| IFS | `10fg` | Verify m/s, maximum statistic and represented time interval |

These are expected contract candidates, not claims of an implemented parser. Check
actual units and step keys on every file. Fail closed on unit or semantic changes.
The GFS official inventory documents the candidate fields [3,7].

Precipitation must use its actual represented interval. Difference cumulative values
only within the same run, grid, member, parameter and cumulative origin. Handle reset
boundaries explicitly; do not subtract overlapping or unrelated accumulations. A
negative increment is a quality problem, not automatically dry weather. A missing
boundary prevents that interval total. Never divide a three-hour amount into three
invented hourly observations. Temperature interpolation, if introduced, needs a
separately identified derived product; gust maxima must not be interpolated into
unsupported hourly extrema. The public schema/UI must support native intervals before
these products replace hourly cards.

## Bounded resource experiment

Proposed initial experiment, not measured or executed by this document:

- One published GFS cycle, a Nepal bounding region with margin, only the three candidate
  fields, and enough native steps for one 24-hour outlook. Fetch each regional field
  once and extract all seven existing city points from that shared data.
- Use documented filtering or indexed byte ranges where supported. Request serially
  initially; bounded retries and explicit byte/time caps. Stop on access restrictions.
- Record requested/received bytes, wall time, CPU time, peak memory, compressed archive
  growth, request count and missing/late steps. Include decoder installation time.
- Run a second cycle to test incremental acquisition, restart, deduplication and model
  reset handling. Simulate an interrupted download and missing interval.
- Repeat an equivalently bounded IFS trial. Do not download whole global archives or
  claim that global-file costs equal the subset cost.
- Extrapolate resource use from measured retained bytes per cycle and chosen retention;
  label that estimate and include Git object-history overhead. Compare with current
  GitHub runner limits and the repository's 256 MiB current-tree data budget.

No monetary cost, bandwidth or runtime estimate is established here. If adequate
retention cannot fit the approved free setup, surface that decision instead of deleting
scientific evidence or silently shortening coverage. GitHub schedules remain best effort.

## Evidence-store and release changes required

The current weather envelope allowlist accepts only approved Open-Meteo endpoints.
Introduce explicit source-specific schemas and host/path/request validators for each
new source. Do not relax this into arbitrary URL fetching. Use binary-safe GRIB
retention with content hashes, bounded decompression and typed metadata. Define how
regional/subset responses and index receipts reconstruct the exact decoded inputs.

Add native-interval fields to analytical/public contracts with migration tests. Keep
old snapshots replayable. Separate raw retrieval, decoding, normalization, quality
quarantine and publication statuses. A successful download is not a valid forecast;
a correctly decoded forecast is not an accurate prediction.

## Acceptance criteria before enabling a replacement

- Real sample fixtures decode expected parameter, level, units, grid and time keys;
  a separately inspected reference decoder confirms selected cells and values.
- Wrong units/levels, truncated GRIB, missing steps, duplicate/conflicting fields,
  reset boundaries and changed grids fail or quarantine explicitly.
- Derived totals use complete non-overlapping intervals. No future-acquired inputs
  enter replay; exact raw hashes and transformation versions reproduce results.
- Original and normalized evidence survives save/restore with byte-identical raw data.
- New and existing sources are visibly distinct. Differences are reported, not treated
  as evidence one is correct. Local scientific verification remains separately required.
- Measured resource use fits the approved budget; outage/restore and partial-run tests
  pass; publication contains only permitted, attributed material.

## Other source reviews still necessary

BIPAD API accessibility does not establish bulk redistribution or commercial rights.
Retain the current selected-summary scope; do not infer permission from the OpenAPI
schema. DHM bulletins, station metadata and any future scraped sources need their own
terms, attribution and access review.

The current discharge feed is also hosted by Open-Meteo. Replacing weather alone does
not resolve that access arrangement. A direct Copernicus/GloFAS path requires its own
access, licence, product-version, reach-mapping and retention contract. Its outputs
remain model discharge, not verified gauges, inundation depth or calibrated flood risk.

## Primary references

1. https://www.weather.gov/disclaimer
2. https://nomads.ncep.noaa.gov/info.php
3. https://www.nco.ncep.noaa.gov/pmb/products/gfs/
4. https://www.ecmwf.int/en/forecasts/datasets/open-data
5. https://github.com/ecmwf/ecmwf-opendata
6. https://open-meteo.com/en/terms
7. https://www.nco.ncep.noaa.gov/pmb/products/gfs/gfs.t00z.pgrb2.0p25.f003.shtml

## Implemented bounded experiment — 15 November 2026

The first direct-GFS trial is now implemented in `disaster_lab/direct_gfs.py`;
see `disaster_lab/DIRECT_GFS.md` for commands, source contracts and measurements.
It acquired/decoded six real native field requests, retained exact raw evidence,
and replayed it. This replaces the earlier "not executed" status only for that
bounded experiment. It does not switch the public providers, clear other source
rights, establish local forecast accuracy or complete the commercial migration.
