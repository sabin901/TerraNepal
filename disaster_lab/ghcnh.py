"""Conservative temperature-only normalization of archived NOAA GHCNh PSV files.

No forecast/station match is approved here. Source flags remain inspectable.
"""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
from pathlib import Path
import re

GOOD_LEGACY_SOURCES={'220','221','222','223','347','348'}
REQUIRED={'STATION','DATE','LATITUDE','LONGITUDE','ELEVATION','temperature',
          'temperature_Quality_Code','temperature_Source_Code','temperature_Measurement_Code'}

def normalize(raw, retrieved_at):
    acquired=dt.datetime.fromisoformat(retrieved_at.replace('Z','+00:00'))
    if acquired.tzinfo is None:raise ValueError('Retrieval time must be timezone-aware')
    reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')),delimiter='|')
    if not REQUIRED.issubset(reader.fieldnames or []):raise ValueError('Missing GHCNh temperature contract fields')
    digest=hashlib.sha256(raw).hexdigest();records=[]
    for line,row in enumerate(reader,2):
        flags=[];value=None;observed=None;latitude=longitude=elevation=None
        station=row['STATION']
        if not re.fullmatch(r'NP[A-Z0-9-]{9}',station or ''):flags.append('invalid_nepal_station_id')
        try:
            t=dt.datetime.fromisoformat(row['DATE'])
            # NOAA documents DATE and calendar columns as UTC; PSV omits suffix.
            if t.tzinfo is None:t=t.replace(tzinfo=dt.timezone.utc)
            if t.utcoffset()!=dt.timedelta(0):raise ValueError('Not UTC')
            observed=t.isoformat()
            if t>acquired:flags.append('observation_after_retrieval')
        except (TypeError,ValueError):flags.append('invalid_observation_time')
        try:
            latitude=float(row['LATITUDE']);longitude=float(row['LONGITUDE'])
            if not math.isfinite(latitude) or not math.isfinite(longitude) or not -90<=latitude<=90 or not -180<=longitude<=180:raise ValueError('Invalid coordinates')
        except (TypeError,ValueError):latitude=longitude=None;flags.append('invalid_coordinates')
        try:
            elevation=float(row['ELEVATION'])
            if not math.isfinite(elevation) or elevation in (-999,-999.9):raise ValueError('Missing elevation')
        except (TypeError,ValueError):elevation=None;flags.append('missing_elevation')
        if not row['temperature']:flags.append('missing_temperature')
        else:
            try:
                value=float(row['temperature'])
                if not math.isfinite(value) or not -100<=value<=70:raise ValueError('Invalid temperature')
            except (TypeError,ValueError):value=None;flags.append('invalid_temperature')
        qc=row['temperature_Quality_Code'];source=row['temperature_Source_Code'];measurement=row['temperature_Measurement_Code']
        if source not in GOOD_LEGACY_SOURCES or qc!='1':flags.append('quality_policy_not_accepted')
        if measurement:flags.append('measurement_code_requires_review')
        records.append({'station_id':station,'observed_at':observed,'retrieved_at':retrieved_at,
            'latitude':latitude,'longitude':longitude,'elevation_m':elevation,
            'variable':'temperature_2m','units':'degC','value':value,
            'eligible_temperature':not flags,'quality_flags':flags,
            'source_quality_code':qc,'source_code':source,'measurement_code':measurement,
            'response_sha256':digest,'source_line':line})
    return records

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input',type=Path)
    p.add_argument('--retrieved-at',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();rows=normalize(a.input.read_bytes(),a.retrieved_at)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps({'schema_version':1,'records':rows,
        'note':'Conservative temperature candidates only; no forecast mapping or national coverage assertion.'},allow_nan=False))
    print(json.dumps({'records':len(rows),'eligible_temperature':sum(r['eligible_temperature'] for r in rows)}))
