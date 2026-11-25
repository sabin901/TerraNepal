"""Bounded direct NOAA GFS research acquisition; not a public weather replacement."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
try: import resource
except ImportError: resource=None
import subprocess
import tempfile
import time
from urllib.parse import urlencode

from weather import PLACES

SOURCE = 'noaa_gfs_direct'
VERSION = 'gfs-native-intervals-1'
MAX_BYTES = 2_000_000
REGION = {'leftlon':80,'rightlon':89,'toplat':31,'bottomlat':26}
FIELDS = {
    'temperature_2m': {'var':'TMP','lev':'2_m_above_ground','shortName':'2t','typeOfLevel':'heightAboveGround','level':2,'units':'K','stepType':'instant'},
    'precipitation': {'var':'APCP','lev':'surface','shortName':'tp','typeOfLevel':'surface','level':0,'units':'kg m**-2','stepType':'accum'},
    'surface_gust': {'var':'GUST','lev':'surface','shortName':'gust','typeOfLevel':'surface','level':0,'units':'m s**-1','stepType':'instant'},
}
META = ('edition','centre','shortName','typeOfLevel','level','units','dataDate','dataTime','validityDate','validityTime','stepType','stepUnits','startStep','endStep','gridType','Ni','Nj','iDirectionIncrementInDegrees','jDirectionIncrementInDegrees','latitudeOfFirstGridPointInDegrees','latitudeOfLastGridPointInDegrees','longitudeOfFirstGridPointInDegrees','longitudeOfLastGridPointInDegrees','iScansNegatively','jScansPositively','jPointsAreConsecutive','bitmapPresent','numberOfMissing')


def utc(value):
    parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('Timezone-aware initialization required')
    parsed=parsed.astimezone(dt.timezone.utc)
    if parsed.minute or parsed.second or parsed.microsecond or parsed.hour not in (0,6,12,18):
        raise ValueError('Initialization must be a six-hour UTC GFS cycle')
    return parsed


def iso(value):
    return value.astimezone(dt.timezone.utc).isoformat()


def url(initialized, lead, field):
    run=utc(initialized)
    if type(lead) is not int or not 1<=lead<=24:raise ValueError('Research lead must be1–24 hours')
    if field not in FIELDS:raise ValueError('Unknown field')
    f=FIELDS[field]
    query={'file':f'gfs.t{run:%H}z.pgrb2.0p25.f{lead:03}',f'lev_{f["lev"]}':'on',f'var_{f["var"]}':'on','subregion':'',**REGION,'dir':f'/gfs.{run:%Y%m%d}/{run:%H}/atmos'}
    return 'https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?'+urlencode(query)


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()


def retain(root, raw, suffix):
    digest=hashlib.sha256(raw).hexdigest();path=Path(root)/(digest+suffix)
    path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with path.open('xb') as out:out.write(raw)
    except FileExistsError:
        if path.read_bytes()!=raw:raise ValueError('Immutable evidence hash conflict')
    return {'sha256':digest,'path':str(path),'bytes':len(raw)}


def validate_metadata(meta, initialized, lead, field):
    run=utc(initialized);expected=FIELDS[field]
    if any(meta[k]!=expected[k] for k in ('shortName','typeOfLevel','level','units','stepType')):
        raise ValueError('Unexpected native GFS field/level/units/statistic')
    if meta['edition']!=2 or meta['centre']!='kwbc' or meta['stepUnits']!=1:
        raise ValueError('Unexpected GRIB edition, centre or forecast time units')
    if meta['dataDate']!=int(run.strftime('%Y%m%d')) or meta['dataTime']!=run.hour*100:
        raise ValueError('GRIB initialization does not match request')
    valid=run+dt.timedelta(hours=lead)
    if meta['endStep']!=lead or meta['validityDate']!=int(valid.strftime('%Y%m%d')) or meta['validityTime']!=valid.hour*100:
        raise ValueError('GRIB lead/valid time does not match request')
    start=meta['startStep']
    if type(start) not in (int,float) or not math.isfinite(start) or not 0<=start<=lead:
        raise ValueError('Invalid native interval start')
    if (field=='precipitation' and start>=lead) or (field!='precipitation' and start!=lead):
        raise ValueError('Unexpected accumulation/instant interval')
    if meta['gridType']!='regular_ll' or meta['Ni']!=37 or meta['Nj']!=21 or meta['iDirectionIncrementInDegrees']!=.25 or meta['jDirectionIncrementInDegrees']!=.25:
        raise ValueError('Unexpected regional grid')
    if set((meta['latitudeOfFirstGridPointInDegrees'],meta['latitudeOfLastGridPointInDegrees']))!={26,31} or set((meta['longitudeOfFirstGridPointInDegrees'],meta['longitudeOfLastGridPointInDegrees']))!={80,89}:
        raise ValueError('Regional grid bounds mismatch')
    return {'initialized_at':iso(run),'valid_at':iso(valid),'interval_start':iso(run+dt.timedelta(hours=start)),
            'interval_end':iso(valid),'statistic':'accumulation' if field=='precipitation' else 'instantaneous'}


def normalize_value(value, field, missing=False):
    if missing:return None,'source_missing'
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value):
        return None,'nonfinite_source_value'
    value=value-273.15 if field=='temperature_2m' else value
    lo,hi=(-100,70) if field=='temperature_2m' else (0,2000) if field=='precipitation' else (0,150)
    if not lo<=value<=hi:return None,'outside_physical_bounds'
    return value,None


def decode_message(raw, initialized, lead, field):
    if not 16<=len(raw)<=MAX_BYTES or raw[:4]!=b'GRIB' or raw[7]!=2 or int.from_bytes(raw[8:16],'big')!=len(raw) or raw[-4:]!=b'7777':
        raise ValueError('Expected exactly one bounded complete GRIB2 message')
    import eccodes as ec
    handle=ec.codes_new_from_message(raw)
    try:
        meta={k:ec.codes_get(handle,k) for k in META}
        timing=validate_metadata(meta,initialized,lead,field)
        bitmap=ec.codes_get_array(handle,'bitmap') if meta['bitmapPresent'] else None
        points=[]
        for place in PLACES:
            nearest=ec.codes_grib_find_nearest(handle,place['latitude'],place['longitude'],npoints=1)[0]
            if nearest['distance']>25:raise ValueError('Selected grid cell is too distant')
            missing=bitmap is not None and not bitmap[nearest['index']]
            value,quality=normalize_value(nearest['value'],field,missing)
            points.append({'place_id':place['id'],'requested_latitude':place['latitude'],'requested_longitude':place['longitude'],
                           'grid_latitude':nearest['lat'],'grid_longitude':nearest['lon'],'distance_km':nearest['distance'],
                           'grid_index':nearest['index'],'native_value':None if missing else nearest['value'],
                           'value':value,'quality':quality})
        return {'source':SOURCE,'parser_version':VERSION,'field':field,**timing,'unit':'°C' if field=='temperature_2m' else 'mm' if field=='precipitation' else 'm/s',
                'native_metadata':meta,'sampling':'nearest regular grid point; no elevation/bias adjustment',
                'points':points,'decoder_version':importlib.metadata.version('eccodes'),'eccodes_api_version':str(ec.codes_get_api_version())}
    finally:ec.codes_release(handle)


def split_messages(raw):
    if not raw or len(raw)>MAX_BYTES:raise ValueError('Empty or oversized GRIB response')
    result=[];offset=0
    while offset<len(raw):
        header=raw[offset:offset+16]
        if len(header)!=16 or header[:4]!=b'GRIB' or header[7]!=2:
            raise ValueError('Unexpected/truncated GRIB framing')
        length=int.from_bytes(header[8:16],'big')
        if length<20 or offset+length>len(raw) or raw[offset+length-4:offset+length]!=b'7777':
            raise ValueError('Incomplete GRIB message')
        result.append(raw[offset:offset+length]);offset+=length
        if len(result)>2:raise ValueError('Unexpected number of native field intervals')
    return result


def decode(raw, initialized, lead, field):
    messages=split_messages(raw)
    if field!='precipitation' and len(messages)!=1:raise ValueError('Duplicate instantaneous field')
    decoded=[decode_message(message,initialized,lead,field) for message in messages]
    identities=[(d['interval_start'],d['interval_end'],d['statistic']) for d in decoded]
    if len(identities)!=len(set(identities)):raise ValueError('Duplicate native intervals')
    return {'source':SOURCE,'parser_version':VERSION,'field':field,'messages':decoded,
            'note':'Multiple precipitation accumulations may overlap; they are not added or silently differenced.'}


def acquire(root, initialized, lead, field):
    request=url(initialized,lead,field);root=Path(root)
    started=dt.datetime.now(dt.timezone.utc)
    if utc(initialized)>started:raise ValueError('Cannot acquire a future initialization')
    wall=time.monotonic();cpu=time.process_time()
    raw=b'';error=None;code=None;normalized=None
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'response'
        try:
            proc=subprocess.run(['curl','--silent','--show-error','--proto','=https','--connect-timeout','10','--max-time','45','--max-filesize',str(MAX_BYTES),'--output',str(path),'--write-out','%{http_code}',request],capture_output=True,timeout=50)
            raw=path.read_bytes() if path.exists() else b''
            code=int(proc.stdout.decode()) if proc.stdout.decode().isdigit() else None
            if proc.returncode or code!=200:raise ValueError(f'HTTP {code}; curl exit {proc.returncode}: '+proc.stderr.decode(errors='replace')[:200])
            normalized=decode(raw,initialized,lead,field)
        except Exception as exc:
            raw=path.read_bytes() if path.exists() else raw
            error=f'{type(exc).__name__}: {str(exc)[:400]}'
    response=retain(root/'raw',raw,'.grib2')
    receipt={'schema_version':1,'source':SOURCE,'request_url':request,'initialized_at':iso(utc(initialized)),'lead_hours':lead,'field':field,
             'acquired_started_at':iso(started),'acquired_finished_at':iso(dt.datetime.now(dt.timezone.utc)),'http_status':code,
             'response':response,'status':'error' if error else 'decoded','error':error,'normalized':normalized,
             'wall_seconds':time.monotonic()-wall,'cpu_seconds':time.process_time()-cpu,
             'attribution':'NOAA/NCEP GFS; https://www.weather.gov/disclaimer; no NOAA endorsement',
             'limitations':['Native model grid, not verified Nepal station mapping.','No interpolation to invented hourly precipitation or gust maxima.','No local accuracy or hazard/impact validation.']}
    evidence=retain(root/'receipts',canonical(receipt),'.json')
    return {'receipt':evidence,**receipt}


def replay(root, receipt_path, as_of=None):
    """Verify a retained receipt and raw bytes before deterministic offline decode."""
    path=Path(receipt_path);encoded=path.read_bytes()
    if path.name!=hashlib.sha256(encoded).hexdigest()+'.json':raise ValueError('Receipt checksum mismatch')
    receipt=json.loads(encoded)
    if receipt['source']!=SOURCE or receipt['request_url']!=url(receipt['initialized_at'],receipt['lead_hours'],receipt['field']):
        raise ValueError('Receipt source identity mismatch')
    acquired=dt.datetime.fromisoformat(receipt['acquired_finished_at'])
    if acquired.tzinfo is None:raise ValueError('Missing acquisition timezone')
    if as_of is not None:
        cutoff=dt.datetime.fromisoformat(as_of.replace('Z','+00:00'))
        if cutoff.tzinfo is None or acquired>cutoff:raise ValueError('Evidence unavailable at replay cutoff')
    if receipt['status']!='decoded':raise ValueError('Receipt did not decode successfully')
    digest=receipt['response']['sha256']
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Invalid response hash')
    raw=(Path(root)/'raw'/(digest+'.grib2')).read_bytes()
    if len(raw)!=receipt['response']['bytes'] or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Raw checksum mismatch')
    normalized=decode(raw,receipt['initialized_at'],receipt['lead_hours'],receipt['field'])
    if normalized!=receipt['normalized']:raise ValueError('Decoder replay differs from retained normalized output')
    return normalized


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--initialized',required=True);p.add_argument('--leads',default='3,6')
    p.add_argument('--root',type=Path,required=True)
    a=p.parse_args();leads=[int(x) for x in a.leads.split(',')]
    if not 1<=len(leads)<=8 or len(set(leads))!=len(leads):p.error('Choose1–8 distinct native leads')
    for lead in leads:
        for field in FIELDS:url(a.initialized,lead,field)
    started=time.monotonic();results=[]
    for lead in leads:
        for field in FIELDS:
            result=acquire(a.root,a.initialized,lead,field);results.append(result)
            # Access failures are not retried or bypassed. Decoder errors remain reviewable.
            if result['http_status'] in (401,403,429):break
        if results[-1]['http_status'] in (401,403,429):break
    report={'source':SOURCE,'parser_version':VERSION,'results':results,'requests':len(results),
            'response_bytes':sum(r['response']['bytes'] for r in results),'wall_seconds':time.monotonic()-started,
            'max_rss_native_units':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None,
            'rss_note':'macOS bytes; Linux KiB; process peak includes imported decoder',
            'complete_requested_fields':len(results)==len(leads)*len(FIELDS) and all(r['status']=='decoded' for r in results)}
    evidence=retain(a.root/'reports',canonical(report),'.json')
    print(json.dumps({'report':evidence,**{k:v for k,v in report.items() if k!='results'}},indent=2))
    return 0 if report['complete_requested_fields'] else 1


if __name__=='__main__':raise SystemExit(main())
