"""Bounded original-run collection for weather research, separate from live feeds."""
from __future__ import annotations
import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
import urllib.parse
from weather import PLACES, MODELS, normalize

ENDPOINT = 'https://single-runs-api.open-meteo.com/v1/forecast'

def run_time(value):
    parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None or parsed.utcoffset() != dt.timedelta(0):
        raise ValueError('Run initialization must explicitly use UTC')
    if parsed.minute or parsed.second or parsed.microsecond or parsed.hour % 6:
        raise ValueError('Expected a 00, 06, 12 or 18 UTC initialization')
    return parsed

def request_url(place_id, model, run, at):
    place = next((p for p in PLACES if p['id'] == place_id), None)
    if place is None or model not in MODELS:
        raise ValueError('Unsupported research location or model')
    initialized = run_time(run)
    if initialized.timestamp() > at:
        raise ValueError('Cannot retrieve a future model initialization')
    return ENDPOINT + '?' + urllib.parse.urlencode({
        'latitude':place['latitude'], 'longitude':place['longitude'],
        'models':model, 'run':initialized.strftime('%Y-%m-%dT%H:%M'),
        'hourly':'precipitation,temperature_2m,wind_gusts_10m',
        'forecast_days':4, 'timeformat':'unixtime', 'timezone':'GMT',
        'wind_speed_unit':'ms', 'precipitation_unit':'mm'}), place, initialized

def normalize_run(payload, place, initialized, model=None):
    data = normalize(payload, place, model)
    points = data['points']
    if points[0]['epoch'] < initialized.timestamp():
        raise ValueError('Single-run response contains pre-initialization values')
    if points[0]['epoch'] > initialized.timestamp() + 3600:
        raise ValueError('Single-run response does not start near requested initialization')
    # This timestamp comes from the documented request contract, not an echoed field.
    data['model_issued_at'] = None  # Deprecated ambiguous field; never publication time.
    data['initialized_at'] = initialized.isoformat()
    data['published_at'] = None
    data['time_note'] = 'Initialization selected by Single Runs API request; not independently echoed by response. Retrieval time records actual archive availability.'
    return data

def collect(root, place_id, model, run):
    url, place, initialized = request_url(place_id, model, run, time.time())
    root = Path(root); raw_dir = root/'raw'; raw_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(['curl','--silent','--show-error','--fail-with-body',
            '--proto','=https','--connect-timeout','10','--max-time','45',
            '--max-filesize','2000000',url],capture_output=True,timeout=50)
    except (OSError, subprocess.TimeoutExpired) as exc:
        result = subprocess.CompletedProcess([],1,getattr(exc,'stdout',None) or b'',str(exc).encode())
    raw = result.stdout; sha = hashlib.sha256(raw).hexdigest(); path = raw_dir/(sha+'.json')
    with tempfile.NamedTemporaryFile(dir=raw_dir,delete=False) as f:
        f.write(raw); temporary=Path(f.name)
    try:
        try: os.link(temporary,path)
        except FileExistsError:
            if path.read_bytes()!=raw: raise ValueError('Raw response integrity collision')
    finally: temporary.unlink()
    fetched = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    error = None; normalized = None
    try:
        if result.returncode:
            reason=result.stderr.decode(errors='replace')[:300]
            try:
                body=json.loads(raw)
                if isinstance(body,dict) and isinstance(body.get('reason'),str): reason=body['reason'][:300]
            except (ValueError,UnicodeError): pass
            raise ValueError('Source request failed: '+reason)
        normalized = normalize_run(json.loads(raw), place, initialized, model)
    except (ValueError, TypeError, KeyError) as exc:
        error = str(exc)
    with contextlib.closing(sqlite3.connect(root/'runs.sqlite')) as db, db:
        db.execute('CREATE TABLE IF NOT EXISTS fetches (id INTEGER PRIMARY KEY, place_id TEXT, model TEXT, requested_run TEXT, fetched_at TEXT, url TEXT, sha256 TEXT, status TEXT, normalized TEXT, error TEXT)')
        db.execute('INSERT INTO fetches VALUES (NULL,?,?,?,?,?,?,?,?,?)',
            (place_id,model,initialized.isoformat(),fetched,url,sha,
             'error' if error else 'ok',json.dumps(normalized,allow_nan=False) if normalized else None,error))
    return {'place_id':place_id,'model':model,'requested_run':initialized.isoformat(),
            'fetched_at':fetched,'sha256':sha,'status':'error' if error else 'ok','error':error,
            'note':'Historical retrieval does not prove availability at initialization. Not published to the live forecast.'}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--place',choices=[p['id'] for p in PLACES],required=True)
    parser.add_argument('--model',choices=list(MODELS),required=True)
    parser.add_argument('--run',required=True,help='Explicit UTC initialization, e.g. 2026-11-15T00:00:00Z')
    args=parser.parse_args()
    report=collect(args.root,args.place,args.model,args.run)
    print(json.dumps(report,indent=2));raise SystemExit(report['status']!='ok')
