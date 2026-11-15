"""Conservative regional point/footprint intersection with explicit evidence lineage.

No hazard generation, geocoding, population estimation, damage or safety inference.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

VERSION = 'regional-point-exposure-1'
EPS = 1e-10
MAX_VERTICES = 2000
MAX_FEATURES = 2000


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def stamp(value):
    if not isinstance(value, str):
        raise ValueError('Expected timezone-aware timestamp')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.utcoffset() is None:
            raise ValueError()
        return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ValueError('Expected timezone-aware timestamp') from None


def finite(value):
    try:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    except OverflowError:
        return False


def coordinate(value):
    if (not isinstance(value, list) or len(value) != 2 or
            any(not finite(v) for v in value) or
            not -180 <= value[0] <= 180 or not -90 <= value[1] <= 90):
        raise ValueError('Expected finite WGS84 longitude/latitude pair without altitude')
    return tuple(value)


def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def on_segment(p, a, b):
    return (abs(cross(a, b, p)) <= EPS and
            min(a[0], b[0])-EPS <= p[0] <= max(a[0], b[0])+EPS and
            min(a[1], b[1])-EPS <= p[1] <= max(a[1], b[1])+EPS)


def intersect(a, b, c, d):
    if any((on_segment(p, x, y)) for p, x, y in ((a,c,d),(b,c,d),(c,a,b),(d,a,b))):
        return True
    return ((cross(a,b,c)>0) != (cross(a,b,d)>0) and
            (cross(c,d,a)>0) != (cross(c,d,b)>0))


def ring_relation(point, ring):
    """Return boundary, inside or outside; planar lon/lat only at regional scale."""
    inside = False
    x, y = point
    for a, b in zip(ring, ring[1:]):
        if on_segment(point, a, b):
            return 'boundary'
        if (a[1] > y) != (b[1] > y):
            if x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
                inside = not inside
    return 'inside' if inside else 'outside'


def rings_touch(a, b):
    return any(intersect(x,y,u,v) for x,y in zip(a,a[1:]) for u,v in zip(b,b[1:]))


def polygon_relation(point, polygon):
    outer = ring_relation(point, polygon[0])
    if outer != 'inside':
        return outer
    for hole in polygon[1:]:
        relation = ring_relation(point, hole)
        if relation == 'boundary':
            return 'boundary'
        if relation == 'inside':
            return 'outside'
    return 'inside'


def validate_ring(raw):
    if not isinstance(raw, list) or not 4 <= len(raw) <= MAX_VERTICES:
        raise ValueError('Ring requires 4–2000 positions')
    ring = [coordinate(p) for p in raw]
    if ring[0] != ring[-1] or len(set(ring[:-1])) != len(ring)-1:
        raise ValueError('Ring must close once without duplicate vertices')
    if any(abs(a[0]-b[0]) > 180 for a,b in zip(ring,ring[1:])):
        raise ValueError('Antimeridian geometry is unsupported')
    if max(p[0] for p in ring)-min(p[0] for p in ring)>30 or max(p[1] for p in ring)-min(p[1] for p in ring)>30:
        raise ValueError('Footprint exceeds supported regional span of 30 degrees')
    if any(abs(p[1]) > 80 for p in ring):
        raise ValueError('Polar geometry is unsupported')
    edges = list(zip(ring, ring[1:]))
    area = sum(a[0]*b[1]-b[0]*a[1] for a,b in edges)
    if abs(area) <= EPS:
        raise ValueError('Degenerate ring area')
    for i,(a,b) in enumerate(edges):
        for j,(c,d) in enumerate(edges[i+1:],i+1):
            if j == i+1 or (i == 0 and j == len(edges)-1):
                # Adjacent edges may share their endpoint but cannot double back.
                shared = b if j == i+1 else a
                other_a = a if j == i+1 else b
                other_b = d if j == i+1 else c
                if on_segment(other_a, shared, other_b) or on_segment(other_b, other_a, shared):
                    raise ValueError('Overlapping adjacent ring edges')
                continue
            if intersect(a,b,c,d):
                raise ValueError('Self-intersecting ring')
    return ring


def validate_polygon(raw):
    if not isinstance(raw, list) or not raw or len(raw)>100:
        raise ValueError('Invalid polygon rings')
    if sum(len(r) if isinstance(r,list) else MAX_VERTICES+1 for r in raw)>MAX_VERTICES:
        raise ValueError('Polygon vertex limit exceeded')
    polygon = [validate_ring(r) for r in raw]
    for i,hole in enumerate(polygon[1:],1):
        if rings_touch(polygon[0],hole) or ring_relation(hole[0],polygon[0])!='inside':
            raise ValueError('Hole must be strictly inside exterior')
        for other in polygon[1:i]:
            if rings_touch(other,hole) or ring_relation(hole[0],other)!='outside' or ring_relation(other[0],hole)!='outside':
                raise ValueError('Holes overlap or contain one another')
    return polygon


def geometry(raw, point=False):
    if not isinstance(raw,dict) or set(raw)!={'type','coordinates'}:
        raise ValueError('Unexpected geometry fields; only WGS84 GeoJSON supported')
    if point:
        if raw['type']!='Point':raise ValueError('Assets must be Points')
        return coordinate(raw['coordinates'])
    if raw['type']=='Polygon':
        return [validate_polygon(raw['coordinates'])]
    if raw['type']!='MultiPolygon' or not isinstance(raw['coordinates'],list) or not 1<=len(raw['coordinates'])<=100:
        raise ValueError('Hazards must be Polygon or MultiPolygon')
    # Reject oversized inputs before quadratic ring validation.
    if any(not isinstance(p,list) for p in raw['coordinates']):
        raise ValueError('Invalid MultiPolygon components')
    if sum(len(r) if isinstance(r,list) else MAX_VERTICES+1 for p in raw['coordinates'] for r in p)>MAX_VERTICES:
        raise ValueError('MultiPolygon vertex limit exceeded')
    polygons=[validate_polygon(p) for p in raw['coordinates']]
    if sum(len(r) for p in polygons for r in p)>MAX_VERTICES:
        raise ValueError('MultiPolygon vertex limit exceeded')
    for i,p in enumerate(polygons):
        for other in polygons[:i]:
            if (any(rings_touch(r,s) for r in p for s in other) or
                    polygon_relation(p[0][0],other)!='outside' or polygon_relation(other[0][0],p)!='outside'):
                raise ValueError('MultiPolygon components overlap or touch')
    return polygons


def evidence(value, at):
    keys={'source_id','source_version','evidence_id','sha256','as_of','acquired_at'}
    if not isinstance(value,dict) or set(value)!=keys:
        raise ValueError('Missing or unexpected evidence fields')
    if any(not isinstance(value[k],str) or not value[k].strip() or len(value[k])>300 for k in ('source_id','source_version','evidence_id')):
        raise ValueError('Invalid source/evidence identity')
    if not isinstance(value['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',value['sha256']):
        raise ValueError('Invalid evidence SHA256')
    if not stamp(value['as_of']) <= stamp(value['acquired_at']) <= at:
        raise ValueError('Future or inconsistent evidence chronology')
    return dict(value)


def features(document, at, assets=False):
    if (not isinstance(document,dict) or set(document)!={'type','features'} or
            document['type']!='FeatureCollection' or not isinstance(document['features'],list) or
            len(document['features'])>MAX_FEATURES):
        raise ValueError('Expected bounded WGS84 GeoJSON FeatureCollection without CRS overrides')
    seen=set();result=[];total_vertices=0
    for f in document['features']:
        if not isinstance(f,dict) or set(f)!={'type','id','geometry','properties'} or f['type']!='Feature':
            raise ValueError('Invalid feature fields')
        identifier=f['id']
        if not isinstance(identifier,str) or not identifier.strip() or len(identifier)>300 or identifier in seen:
            raise ValueError('Invalid or duplicate feature ID')
        seen.add(identifier)
        props=f['properties']
        keys={'evidence','sector'} if assets else {'evidence','kind','valid_from','valid_until'}
        if not isinstance(props,dict) or set(props)!=keys:
            raise ValueError('Unexpected feature properties')
        provenance=evidence(props['evidence'],at)
        parsed=geometry(f['geometry'],point=assets)
        if assets:
            if not isinstance(props['sector'],str) or not props['sector'].strip() or len(props['sector'])>100:
                raise ValueError('Invalid asset sector')
        else:
            if props['kind'] not in ('scenario','observed_extent'):
                raise ValueError('Extent kind must distinguish scenario and observation')
            start,end=stamp(props['valid_from']),stamp(props['valid_until'])
            if start>=end:raise ValueError('Invalid extent validity interval')
            if props['kind']=='observed_extent' and end>stamp(provenance['acquired_at']):
                raise ValueError('Observed extent cannot describe periods after its acquisition')
            total_vertices+=sum(len(r) for p in parsed for r in p)
            if total_vertices>10000:raise ValueError('Collection vertex budget exceeded')
        result.append((f,parsed))
    return result


def assess(hazards, assets, at, valid_at=None):
    cutoff=stamp(at);target=stamp(valid_at) if valid_at else cutoff
    hz=features(hazards,cutoff);points=features(assets,cutoff,assets=True)
    eligible=[(f,p) for f,p in hz if stamp(f['properties']['valid_from'])<=target<stamp(f['properties']['valid_until'])]
    excluded=[{'hazard_id':f['id'],'reason':'outside_validity_interval'} for f,_ in hz if not stamp(f['properties']['valid_from'])<=target<stamp(f['properties']['valid_until'])]
    results=[]
    for asset,point in points:
        matches=[]
        dated_for_target = stamp(asset['properties']['evidence']['as_of']) <= target
        for hazard,polygons in eligible if dated_for_target else []:
            relations=[polygon_relation(point,p) for p in polygons]
            relation='boundary' if 'boundary' in relations else 'inside' if 'inside' in relations else 'outside'
            if relation!='outside':
                matches.append({'hazard_id':hazard['id'],'kind':hazard['properties']['kind'],'relation':relation,
                                'hazard_evidence':hazard['properties']['evidence']})
        matches.sort(key=lambda m:m['hazard_id'])
        results.append({'asset_id':asset['id'],'sector':asset['properties']['sector'],
                        'asset_evidence':asset['properties']['evidence'],
                        'status':'intersects_supplied_extent' if matches else 'no_intersection_in_supplied_footprints' if eligible and dated_for_target else 'unassessed',
                        'unassessed_reason': 'asset_record_postdates_target' if not dated_for_target else 'no_eligible_footprints' if not eligible else None,
                        'matches':matches,'damage_assessment':'not_established','safety_assessment':'not_established'})
    result={'schema_version':1,'engine_version':VERSION,'assessed_at':cutoff.isoformat(),'valid_at':target.isoformat(),
            'input_sha256':{'hazards':digest(hazards),'assets':digest(assets)},
            'boundary_policy':'Boundary (including hole boundary) is counted as intersecting; EPS=1e-10 planar degrees.',
            'geometry_method':'Regional planar longitude/latitude point containment; no area, distance or terrain calculation.',
            'eligible_footprints':len(eligible),'excluded_footprints':excluded,
            'assets':sorted(results,key=lambda r:r['asset_id']),
            'coverage':'Supplied footprints and point assets only; completeness and positional accuracy are not established.',
            'limitations':['No intersection does not mean safe or outside all hazards.',
                           'An intersection establishes geometric exposure to the supplied extent, not damage or expected loss.',
                           'Scenario extents are not observed events or calibrated probabilities.',
                           'Evidence hashes are references; raw bytes and source authenticity are not verified by this engine.',
                           'This engine does not approve evacuation, operating, closure or warning decisions.']}
    result['assessment_id']=digest(result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hazards',type=Path,required=True);parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--at',required=True);parser.add_argument('--valid-at');parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists() or args.output.resolve() in (args.hazards.resolve(),args.assets.resolve()):
        parser.error('Output must be a new path distinct from input evidence')
    try:
        result=assess(json.loads(args.hazards.read_text()),json.loads(args.assets.read_text()),args.at,args.valid_at)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open('x') as stream:stream.write(json.dumps(result,ensure_ascii=False,allow_nan=False,indent=2)+'\n')
    except (ValueError,OSError) as exc:parser.error(str(exc))


if __name__=='__main__':main()
