"""Build unverified station-to-city mapping candidates from normalized GHCNh records."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from weather import PLACES


def number(value):
    try:return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
    except OverflowError:return False


def utc(value):
    try:
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.utcoffset() is None:raise ValueError()
        return parsed.astimezone(timezone.utc).isoformat()
    except (AttributeError,ValueError,OverflowError):return None


def distance_km(lat,lon,other_lat,other_lon):
    """Great-circle separation, not elevation, terrain or representativeness."""
    lat1,lat2=math.radians(lat),math.radians(other_lat)
    a=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(math.radians(other_lon-lon)/2)**2
    return 6371.0088*2*math.asin(math.sqrt(min(1,max(0,a))))


def build(document,places=None):
    if not isinstance(document,dict) or type(document.get('schema_version')) is not int or document['schema_version']!=1 or not isinstance(document.get('records'),list):
        raise ValueError('Expected GHCNh schema_version 1 with records array')
    places=PLACES if places is None else places
    ids=set()
    for p in places:
        if not isinstance(p.get('id'),str) or p['id'] in ids or not number(p.get('latitude')) or not number(p.get('longitude')) or not -90<=p['latitude']<=90 or not -180<=p['longitude']<=180:raise ValueError('Invalid requested-place registry')
        ids.add(p['id'])
    rows=defaultdict(list);excluded=Counter();seen={};duplicates=0
    for r in document['records']:
        if not isinstance(r,dict) or not isinstance(r.get('station_id'),str) or not re.fullmatch(r'NP[A-Z0-9-]{9}',r['station_id']):excluded['invalid_station_id']+=1;continue
        sha=r.get('response_sha256');line=r.get('source_line')
        if not isinstance(sha,str) or not re.fullmatch(r'[a-f0-9]{64}',sha) or type(line) is not int or line<2:excluded['missing_source_provenance']+=1;continue
        if r.get('variable')!='temperature_2m' or r.get('units')!='degC':excluded['unsupported_variable_or_units']+=1;continue
        identity=(sha,line)
        if identity in seen:
            if seen[identity]!=r:raise ValueError('Conflicting normalized content for one source hash and line')
            duplicates+=1;continue
        seen[identity]=r;rows[r['station_id']].append(r)
    candidates=[]
    for station,records in sorted(rows.items()):
        variants=defaultdict(list);reasons=set();dates=[];eligible=0;hashes=set()
        for r in records:
            hashes.add(r['response_sha256']);observed=utc(r.get('observed_at'));retrieved=utc(r.get('retrieved_at'))
            if observed:dates.append(observed)
            if not observed or not retrieved or observed>retrieved:reasons.add('invalid_observation_or_retrieval_time')
            lat,lon,elevation=(r.get(k) for k in ('latitude','longitude','elevation_m'))
            valid_coords=number(lat) and number(lon) and -90<=lat<=90 and -180<=lon<=180
            valid_elevation=number(elevation) and -500<=elevation<=9000
            if not valid_coords:lat=lon=None;reasons.add('invalid_or_missing_coordinates')
            if not valid_elevation:elevation=None;reasons.add('invalid_or_missing_elevation')
            variants[(lat,lon,elevation)].append(r)
            valid_value=number(r.get('value')) and -100<=r['value']<=70
            if r.get('eligible_temperature') is True and r.get('quality_flags')==[] and valid_value and valid_coords and valid_elevation and observed and retrieved and observed<=retrieved:eligible+=1
        if len(variants)>1:reasons.add('conflicting_station_metadata')
        if not eligible:reasons.add('no_eligible_temperature_candidates')
        metadata=[]
        for (lat,lon,elevation),members in sorted(variants.items(),key=lambda item:str(item[0])):
            stamps=sorted(filter(None,(utc(r.get('observed_at')) for r in members)))
            distances=[] if lat is None else [dict(place_id=p['id'],requested_latitude=p['latitude'],requested_longitude=p['longitude'],distance_km=round(distance_km(lat,lon,p['latitude'],p['longitude']),3)) for p in sorted(places,key=lambda p:p['id'])]
            metadata.append(dict(latitude=lat,longitude=lon,station_elevation_m=elevation,record_count=len(members),observed_start=min(stamps) if stamps else None,observed_end=max(stamps) if stamps else None,source_sha256=sorted({r['response_sha256'] for r in members}),distances_to_requested_city_points=distances))
        candidates.append(dict(station_id=station,verified=False,status='mapping_review_needed',review_reasons=sorted(reasons|{'station_grid_representativeness_unverified'}),record_count=len(records),eligible_temperature_candidates=eligible,observed_start=min(dates) if dates else None,observed_end=max(dates) if dates else None,source_sha256=sorted(hashes),metadata_variants=metadata,native_model_grid_elevation_m=None))
    return dict(schema_version=1,status='unverified_mapping_candidates_only',input_records=len(document['records']),included_records=sum(len(r) for r in rows.values()),duplicate_input_records=duplicates,excluded_records=sum(excluded.values()),exclusions=dict(sorted(excluded.items())),station_count=len(candidates),verified_mapping_count=0,candidates=candidates,limitations=[
        'Distance is to requested illustrative city coordinates, not returned forecast grid cells; proximity never approves a mapping.',
        'Station metadata variants require review for relocation or reporting changes; no variant is automatically selected.',
        'Provider target/downscaling elevation is not native model grid height. No grid height is inferred.',
        'Temperature candidates retain source quality-policy status; no independent observational accuracy or national coverage is established.'])


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('input',type=Path);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    try:
        if args.input.resolve()==args.output.resolve():raise ValueError('Output must not overwrite source evidence')
        raw=args.input.read_bytes();result=build(json.loads(raw));result['normalized_input_sha256']=hashlib.sha256(raw).hexdigest()
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        print(json.dumps({k:result[k] for k in ('station_count','included_records','excluded_records','verified_mapping_count')}))
    except (ValueError,OSError) as exc:parser.exit(2,f'Station registry failed: {exc}\n')

if __name__=='__main__':main()
