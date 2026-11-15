# TerraRaksha regional point exposure engine

Implemented 15 November 2026. `exposure.py` calculates whether **supplied point
assets** intersect **supplied hazard footprints**. It does not generate a flood map,
verify its accuracy, geocode assets, estimate population, predict damage, or issue
warnings. No real asset inventory or hazard footprint was introduced by this work.
Synthetic coordinates in tests are not evidence of a real disaster.

## Interface and inputs

```python
from exposure import assess
result = assess(hazards, assets, at='2026-11-15T12:00:00Z', valid_at=None)
```

`at` is the evidence-availability cutoff. `valid_at` selects a footprint's represented
validity instant; default is `at`. A future scenario can be assessed if its evidence
was acquired by `at`. Acquisition times, metadata as-of dates and declared valid
periods remain separate. Later asset inventory cannot establish historical exposure:
an asset with `as_of > valid_at` is unassessed. Older inventory does not prove that its
location, function or existence remained unchanged.

Both inputs are strict GeoJSON FeatureCollections with exactly `type` and `features`.
Each Feature contains exactly `type: Feature`, unique nonempty string `id`, `geometry`
and `properties`. Additional fields are rejected so that unsupported CRS overrides,
geometries or semantics cannot be silently ignored. A preprocessing step may copy
approved source fields into this narrow contract; retain its input/output hashes.

Asset geometry: `Point`, exactly two WGS84 coordinates `[longitude, latitude]`.
Asset properties: `sector` (nonempty string) and `evidence`.

Hazard geometry: `Polygon` or `MultiPolygon`. Hazard properties:

- `kind`: `scenario` or `observed_extent`, never automatically inferred.
- `valid_from`, `valid_until`: timezone-aware timestamps, half-open `[from, until)`.
- `evidence`: source lineage. An observed extent's entire validity interval must end by its
  acquisition. Carrying an old observed footprint forward requires an explicitly
  labelled scenario; an observation does not establish future exposure.

Every `evidence` object has exactly:

```json
{
  "source_id": "source-identifier",
  "source_version": "dated-source-version",
  "evidence_id": "record-or-artifact-identifier",
  "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "as_of": "2026-11-15T10:00:00Z",
  "acquired_at": "2026-11-15T11:00:00Z"
}
```

The example hash is a placeholder, **not verified evidence**. The engine checks
format and chronology (`as_of <= acquired_at <= at`), not raw bytes or authenticity.
Caller systems must verify the corresponding retained bytes and record review status.
Source IDs and versions are required but do not establish source authority.

## Geometry method and bounds

A pure-Python regional planar ray-crossing implementation avoids adding a new binary
geospatial dependency to the existing research deployment. Polygon validity is checked
before intersections, including closed rings, duplicate vertices, degeneracy,
self-intersections and adjacent edge reversals. Holes must lie strictly inside the
exterior without touching/overlapping other holes. MultiPolygon components may be
islands in another component's hole, but may not overlap or touch.

**Boundary policy:** exterior and hole boundaries count as intersecting. The numerical
tolerance is `1e-10` in planar coordinate tests; it is not a survey-accuracy statement.
A point inside a hole is outside the footprint. Ring winding direction does not alter
membership. Longitude/latitude is interpreted as GeoJSON regional linework, not a
geodesic segment or a distance/area measurement.

Unsupported inputs fail explicitly: antimeridian-crossing segments, polar footprints
above 80° absolute latitude, footprints exceeding 30° in longitude or latitude,
altitude coordinates, nonfinite/bool coordinates, malformed polygons and CRS overrides.
Limits: 2,000 features per collection, 2,000 vertices per Polygon/MultiPolygon,
100 rings/components, and 10,000 vertices across hazard features. Validation has
quadratic edge comparisons. This is bounded research processing, not a national
high-volume spatial database or a replacement for independently tested GIS tooling.

## Outputs and meaning

The deterministic result records engine version, assessment/target times, canonical
input hashes, lineage, excluded expired/not-yet-valid footprints and per-asset matches.
Each match retains `hazard_id`, `kind`, `relation` (`inside`/`boundary`) and source evidence.
The canonical result SHA-256 is `assessment_id` (computed before adding that field).

Per-asset statuses:

- `intersects_supplied_extent`: geometric intersection with listed supplied extents.
- `no_intersection_in_supplied_footprints`: no intersection with the eligible inputs;
  **never an all-clear**, since other hazards and positional errors may exist.
- `unassessed`: no eligible footprint, or asset inventory postdates the target.

`damage_assessment` and `safety_assessment` always remain `not_established`. No household,
facility, road, affected-person or financial-loss count is inferred. Point intersections
are inappropriate for estimating the full exposure of line/area assets; representativeness
requires separate review. Duplicate feature IDs reject the input rather than inflating
results. Multiple footprint matches remain separate instead of double-counting damages.

## CLI

```sh
python disaster_lab/exposure.py --hazards /path/verified-footprints.json \
  --assets /path/verified-point-assets.json --at 2026-11-15T12:00:00Z \
  --output /path/new-exposure-assessment.json
```

The output must be a new path, distinct from both inputs. Existing outputs are never
overwritten. Results are generated locally; this CLI neither downloads nor publishes.
For replay, retain both exact input documents, the cutoff, target and engine version.

## Acceptance evidence and remaining validation

16 synthetic tests cover interior/exterior/boundary, holes, component islands,
self-intersection, degeneracy, adjacent reversal, CRS/antimeridian/polar rejection,
duplicate IDs, invalid/future timestamps, scenario versus observation, historical
inventory exclusion, empty coverage, deterministic replay and CLI overwrite protection.
These establish bounded software behaviour, not accuracy of real hazard maps/assets.

Before operational use: compare an independently selected geometry corpus against a
trusted GIS implementation; acquire licensed dated hazard/asset inputs; verify source
lineage, location and coverage with domain reviewers; record source corrections; and
validate real local workflows. Exposure must remain separate from vulnerability,
expected damage, confirmed damage and any official response decision.
