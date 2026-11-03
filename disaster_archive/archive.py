#!/usr/bin/env python3
"""Local, auditable Nepal disaster archive. Python standard library + TLS-verified curl."""
from __future__ import annotations
import argparse
import contextlib
import datetime as dt
import fcntl
import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse
import uuid

CODE_ROOT = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('NEPAL_ARCHIVE_ROOT', CODE_ROOT)).resolve()
UTC = dt.timezone.utc
PARSER_VERSION = '1.0'

def now():
    return dt.datetime.now(UTC).isoformat(timespec='seconds')

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)

def parse_time(value):
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.astimezone(UTC) if parsed.tzinfo is not None else None
    except (TypeError, ValueError):
        return None

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)

class Archive:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        for name in ('config.json', 'schema.sql'):
            if not (self.root/name).exists():
                shutil.copyfile(CODE_ROOT/name, self.root/name)
        self.config = json.loads((self.root / 'config.json').read_text())
        for name in ('data/raw', 'exports', 'backups', 'logs'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.root / 'data/archive.sqlite', timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript((self.root / 'schema.sql').read_text())
        self.run_id = None
        self.register_sources()

    def register_sources(self):
        sources = [
            ('bipad', 'Government of Nepal BIPAD public API', 'https://bipadportal.gov.np/api/', 'public_read_access',
             'No explicit dataset reuse license verified; attribute BIPAD/originating agencies. Private research archive; review terms before republication.',
             'Administrative incident reports are not unique physical disasters. Zeroes may be defaults. False total-count sentinel; pages may change during traversal.'),
            ('usgs', 'USGS earthquake catalogue', 'https://earthquake.usgs.gov/fdsnws/event/1/', 'public_read_access',
             'USGS data attribution; see https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits',
             'Bounding box includes Nepal and parts of neighboring countries. Catalogue completeness varies over time and magnitude.'),
            ('desinventar', 'Nepal DesInventar historical profile', self.config['desinventar_profile'], 'public_aggregate_profile',
             'Attribute DesInventar, NSET and source agencies; bulk-download license not verified because export page timed out.',
             '1971–2013 profile aggregates only; data cards are not unique disasters. Do not add to overlapping BIPAD losses.'),
            ('reliefweb', 'ReliefWeb humanitarian reports', 'https://apidoc.reliefweb.int/', 'requires_approved_appname',
             'Original publishers retain rights. Store metadata/links and review rights before copying full documents.',
             'Connector disabled until a ReliefWeb-approved appname is supplied; no borrowed appname or bypass.'),
        ]
        self.db.executemany('INSERT OR REPLACE INTO sources VALUES (?,?,?,?,?,?)', sources)
        self.db.commit()

    def issue(self, collection, code, detail, severity='warning'):
        self.db.execute('INSERT INTO issues(run_id,collection,severity,code,detail,observed_at) VALUES (?,?,?,?,?,?)',
                        (self.run_id, collection, severity, code, detail, now()))
        self.db.commit()

    def meta(self, key, default=None):
        row = self.db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key, value):
        self.db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)', (key, str(value)))
        self.db.commit()

    def start(self, mode):
        self.run_id = uuid.uuid4().hex
        self.db.execute('INSERT INTO runs(id,started_at,mode,status) VALUES (?,?,?,?)', (self.run_id, now(), mode, 'running'))
        self.db.commit()

    def fetch(self, source, url):
        """Retain exact response bytes, checksum, URL, status and fetch time, including errors."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != 'https':
            raise ValueError('HTTPS required')
        stamp = now()
        with tempfile.TemporaryDirectory(prefix='disaster-fetch-') as temp:
            body, headers = Path(temp)/'body', Path(temp)/'headers'
            command = ['curl', '--silent', '--show-error', '--location', '--proto', '=https', '--proto-redir', '=https',
                       '--connect-timeout', '15', '--max-time', '55', '--max-filesize', '52428800',
                       '--user-agent', 'NepalDisasterArchive/1.0 (private public-data research)',
                       '--dump-header', str(headers), '--output', str(body), '--write-out', '%{http_code}', url]
            result = subprocess.run(command, capture_output=True, text=True)
            raw = body.read_bytes() if body.exists() else b''
            try:
                status = int(result.stdout.strip()[-3:])
            except ValueError:
                status = 0
            error = result.stderr.strip() if result.returncode else None
            if not error and status != 200:
                error = f'HTTP {status}'
            digest = hashlib.sha256(raw).hexdigest()
            rel = Path('data/raw')/source/(digest + '.bin.gz')
            target = self.root/rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(gzip.compress(raw, mtime=0))
            kept_headers = {}
            if headers.exists():
                for line in headers.read_text(errors='replace').splitlines():
                    if ':' in line:
                        key, val = line.split(':', 1)
                        if key.lower() in ('content-type', 'etag', 'last-modified', 'date', 'content-length'):
                            kept_headers[key.lower()] = val.strip()
            cursor = self.db.execute('INSERT INTO fetches(run_id,source,url,fetched_at,http_status,sha256,raw_path,byte_count,headers,error) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (self.run_id, source, url, stamp, status, digest, str(rel), len(raw), canonical(kept_headers), error))
            fetch_id = cursor.lastrowid
            self.db.commit()
            time.sleep(self.config['request_pause_seconds'])
            if error:
                raise RuntimeError(f'{source}: {error[:300]} (fetch {fetch_id})')
            return raw, fetch_id, stamp

    def ingest(self, collection, rows, fetch_id, stamp):
        added = revised = 0
        for item in rows:
            if not isinstance(item, dict) or item.get('id') is None:
                raise ValueError(f'{collection}: record missing id')
            native_id = str(item['id'])
            payload = canonical(item)
            digest = hashlib.sha256(payload.encode()).hexdigest()
            old = self.db.execute('SELECT version_id FROM records WHERE collection=? AND native_id=?', (collection, native_id)).fetchone()
            self.db.execute('INSERT OR IGNORE INTO record_versions(collection,native_id,sha256,payload,first_fetch_id,first_seen_at) VALUES (?,?,?,?,?,?)',
                            (collection, native_id, digest, payload, fetch_id, stamp))
            version_id = self.db.execute('SELECT id FROM record_versions WHERE collection=? AND native_id=? AND sha256=?',
                                         (collection, native_id, digest)).fetchone()[0]
            if not old or old[0] != version_id:
                added += int(not old)
                revised += int(bool(old))
                self.db.execute('INSERT INTO changes(collection,native_id,previous_version_id,version_id,observed_at,fetch_id) VALUES (?,?,?,?,?,?)',
                                (collection, native_id, old[0] if old else None, version_id, stamp, fetch_id))
            self.db.execute('INSERT INTO records VALUES (?,?,?,?,?,?) ON CONFLICT(collection,native_id) DO UPDATE SET version_id=excluded.version_id,last_seen_at=excluded.last_seen_at,latest_fetch_id=excluded.latest_fetch_id',
                            (collection, native_id, version_id, stamp, stamp, fetch_id))
        self.db.commit()
        return added, revised

    def collection_start(self, name, start=None, end=None):
        c = self.db.execute('INSERT INTO collection_runs(run_id,collection,query_start,query_end,status,started_at) VALUES (?,?,?,?,?,?)',
                            (self.run_id, name, start, end, 'running', now()))
        self.db.commit()
        return c.lastrowid

    def collection_finish(self, job, pages, rows, added, revised, status, note):
        self.db.execute('UPDATE collection_runs SET pages=?,rows_seen=?,new_records=?,revised_records=?,status=?,note=?,finished_at=? WHERE id=?',
                        (pages, rows, added, revised, status, note, now(), job))
        self.db.commit()

    def bipad(self, endpoint, params=None, max_pages=None, intentional_sample=False, window=None):
        collection = 'bipad:' + endpoint
        params = dict(params or {})
        params.setdefault('ordering', 'id')
        params['limit'] = self.config['page_size']
        url = self.config['bipad_base'] + endpoint + '/?' + urllib.parse.urlencode(params)
        job = self.collection_start(collection, *(window or (None, None)))
        pages = total = added = revised = 0
        seen_urls, seen_ids = set(), set()
        status, note = 'failed', ''
        try:
            for _ in range(max_pages or self.config['max_pages_per_collection']):
                if url in seen_urls:
                    raise ValueError('Pagination loop; traversal incomplete')
                seen_urls.add(url)
                raw, fetch_id, stamp = self.fetch('bipad', url)
                obj = json.loads(raw)
                if not isinstance(obj, dict) or not isinstance(obj.get('results'), list):
                    raise ValueError('Unexpected BIPAD schema, expected results list')
                batch = obj['results']
                pages += 1
                if any(not isinstance(x, dict) or x.get('id') is None for x in batch):
                    raise ValueError('BIPAD page contains records without IDs')
                ids = {str(x['id']) for x in batch}
                if batch and not ids - seen_ids:
                    raise ValueError('Repeated page/IDs; traversal incomplete')
                if seen_ids & ids:
                    self.issue(collection, 'overlapping_pages', 'IDs repeated across pages; upstream dataset may have changed during pagination.')
                seen_ids.update(ids)
                a, r = self.ingest(collection, batch, fetch_id, stamp)
                added += a
                revised += r
                total += len(batch)
                if pages == 1 or pages % 10 == 0:
                    print(f'{collection}: {pages} pages, {total} source rows', flush=True)
                nxt = obj.get('next')
                # Some BIPAD endpoints advertise an endless next URL and 2^63-1 count.
                # Confirm exhaustion using an actual empty page, never by advertised count.
                if not batch or not nxt:
                    status = 'traversed'
                    note = 'Reached source end. Live API traversal is not an atomic snapshot or proof of real-world completeness.'
                    break
                nxt = urllib.parse.urljoin(url, nxt)
                allowed = urllib.parse.urlparse(self.config['bipad_base'])
                n = urllib.parse.urlparse(nxt)
                if n.scheme != 'https' or n.netloc != allowed.netloc or not n.path.startswith(allowed.path):
                    raise ValueError('Rejected unexpected pagination origin/path')
                url = nxt
            else:
                status = 'sampled' if intentional_sample else 'partial'
                note = f'Page cap reached; only {total} source rows processed. Remaining pages not collected.'
                if not intentional_sample:
                    self.issue(collection, 'page_cap', note)
        except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
            note = str(exc)
            self.issue(collection, 'collection_failed', note, 'error')
        self.collection_finish(job, pages, total, added, revised, status, note)
        return status

    def usgs(self, start, end):
        job = self.collection_start('usgs:earthquake', start, end)
        pages = total = added = revised = 0
        status, note = 'failed', ''
        params = dict(self.config['usgs_bounds'])
        params.update(format='geojson', eventtype='earthquake', starttime=start, endtime=end, orderby='time-asc', limit=10000)
        offset, seen = 1, set()
        try:
            for _ in range(20):
                params['offset'] = offset
                url = 'https://earthquake.usgs.gov/fdsnws/event/1/query?' + urllib.parse.urlencode(params)
                raw, fid, stamp = self.fetch('usgs', url)
                data = json.loads(raw)
                if data.get('type') != 'FeatureCollection' or not isinstance(data.get('features'), list):
                    raise ValueError('Unexpected USGS schema')
                batch = data['features']
                ids = {x['id'] for x in batch}
                if batch and not ids - seen:
                    raise ValueError('Repeated USGS page')
                seen.update(ids)
                a, r = self.ingest('usgs:earthquake', batch, fid, stamp)
                pages += 1; total += len(batch); added += a; revised += r
                if len(batch) < params['limit']:
                    status = 'traversed'
                    note = 'Catalogue records within configured Nepal-and-neighbors bounding box; not Nepal-only or uniform magnitude completeness.'
                    break
                offset += len(batch)
            else:
                status, note = 'partial', 'USGS page cap reached'
        except (RuntimeError, ValueError, KeyError) as exc:
            note = str(exc)
            self.issue('usgs:earthquake', 'collection_failed', note, 'error')
        self.collection_finish(job, pages, total, added, revised, status, note)
        return status

    @staticmethod
    def parse_profile(text):
        results = {}
        for marker, name in [('YEAR', 'annual'), ('EVENTS', 'hazard')]:
            match = re.search(r'<!-- Start stat: ' + marker + r' -->.*?<table[^>]*>(.*?)</table>', text, re.S | re.I)
            if not match:
                raise ValueError(f'DesInventar {marker} table not found; schema changed')
            rows = re.findall(r'<tr\b[^>]*>(.*?)</tr>', match.group(1), re.S | re.I)
            clean = lambda value: ' '.join(html.unescape(re.sub('<[^>]+>', ' ', value)).split())
            headers = [clean(x) for x in re.findall(r'<th\b[^>]*>(.*?)</th>', rows[0], re.S | re.I)]
            if len(headers) < 10 or headers[1] != 'DataCards':
                raise ValueError('Unrecognized historical profile column layout')
            values = []
            for row in rows[1:]:
                cells = [clean(x) for x in re.findall(r'<td\b[^>]*>(.*?)</td>', row, re.S | re.I)]
                if not cells:
                    continue
                if len(cells) != len(headers):
                    raise ValueError('Historical row/header length mismatch')
                if name == 'annual' and not re.fullmatch(r'\d{4}', cells[0]):
                    continue
                item = {'id': cells[0], 'scope': 'Nepal historical profile aggregate', 'aggregation': name,
                        'coverage': '1971–2013', 'record_unit': 'source_data_cards_not_unique_disasters', 'fields': {}}
                for key, val in zip(headers, cells):
                    if key == headers[0]:
                        item['fields'][key] = val
                    elif val == '':
                        item['fields'][key] = None
                    elif re.fullmatch(r'-?\d+(\.\d+)?', val):
                        item['fields'][key] = float(val) if '.' in val else int(val)
                    else:
                        raise ValueError(f'Unrecognized historical numeric value: {key}={val}')
                values.append(item)
            results[name] = values
        return results

    def desinventar(self):
        job = self.collection_start('desinventar:profile', '1971', '2013')
        total = added = revised = pages = 0
        status, note = 'failed', ''
        try:
            raw, fid, stamp = self.fetch('desinventar', self.config['desinventar_profile'])
            pages = 1
            groups = self.parse_profile(raw.decode('utf-8', errors='strict'))
            for key, values in groups.items():
                a, r = self.ingest('desinventar:' + key, values, fid, stamp)
                total += len(values); added += a; revised += r
            status = 'traversed'
            note = 'Annual and hazard aggregates only. Individual 1971–2013 data cards were not obtained; bulk export timed out during setup.'
        except (RuntimeError, ValueError, UnicodeError) as exc:
            note = str(exc)
            self.issue('desinventar:profile', 'collection_failed', note, 'error')
        self.collection_finish(job, pages, total, added, revised, status, note)

    def import_references(self):
        file = self.root.parent / 'source-ledger.json'
        if not file.exists():
            file = CODE_ROOT.parent / 'source-ledger.json'
        if not file.exists():
            return
        for item in json.loads(file.read_text()).get('sources', []):
            self.db.execute('INSERT OR IGNORE INTO research_references(id,title,publisher,publication_date,url,prior_access_notes) VALUES (?,?,?,?,?,?)',
                (item['id'], item.get('title'), item.get('publisher'), item.get('date'), item.get('url'), item.get('access')))
        self.db.commit()

    def validate(self):
        tests = {
            'incident_missing_date': "SELECT count(*) FROM incident_current WHERE occurred_at IS NULL",
            'incident_unknown_hazard': "SELECT count(*) FROM incident_current WHERE hazard IS NULL",
            'incident_bad_coordinates': "SELECT count(*) FROM incident_current WHERE longitude NOT BETWEEN -180 AND 180 OR latitude NOT BETWEEN -90 AND 90",
            'incident_missing_coordinates': "SELECT count(*) FROM incident_current WHERE longitude IS NULL OR latitude IS NULL",
            'incident_negative_deaths': "SELECT count(*) FROM incident_current WHERE reported_deaths<0",
            'incident_missing_loss': "SELECT count(*) FROM incident_current WHERE reported_deaths IS NULL",
            'incident_without_ward': "SELECT count(*) FROM incident_current WHERE ward_count=0 OR ward_count IS NULL",
            'incident_multiple_wards': "SELECT count(*) FROM incident_current WHERE ward_count>1",
            'river_missing_time_or_value': "SELECT count(*) FROM river_observations WHERE observed_at IS NULL OR water_level_source_units IS NULL",
        }
        result = {name: self.db.execute(sql).fetchone()[0] for name, sql in tests.items()}
        result['foreign_key_errors'] = len(self.db.execute('PRAGMA foreign_key_check').fetchall())
        result['quick_check'] = self.db.execute('PRAGMA quick_check').fetchone()[0]
        write_json(self.root/'exports/quality.json', {'checked_at': now(), 'checks': result,
                    'interpretation': 'Flags do not automatically invalidate a source report. Missing is not zero; no national completeness assertion.'})
        return result

    def live(self):
        """Bounded recent observations; daily catchup watermarks are never advanced."""
        cutoff = now()
        start = (parse_time(cutoff)-dt.timedelta(hours=2)).isoformat()
        self.start('live')
        results = {}
        for endpoint, field in [('river', 'water_level_on'), ('rain', 'measured_on')]:
            results[endpoint] = self.bipad(endpoint, {field+'__gt':start, field+'__lt':cutoff,
                'ordering':'id'}, max_pages=20, window=(start, cutoff))
            if results[endpoint] == 'traversed':
                self.set_meta('last_live_'+endpoint, cutoff)
        results['alert'] = self.bipad('alert', {'ordering':'-id'}, max_pages=2, intentional_sample=True)
        bad = self.db.execute("SELECT count(*) FROM collection_runs WHERE run_id=? AND status IN ('partial','failed','running')", (self.run_id,)).fetchone()[0]
        status = 'partial' if bad else 'completed'
        self.db.execute('UPDATE runs SET status=?,finished_at=? WHERE id=?', (status,now(),self.run_id))
        self.db.commit()
        report = {'run_id':self.run_id, 'status':status, 'finished_at':now(), 'window':[start,cutoff],
            'results':results, 'note':'Recent bounded source traversal, not a national completeness or sensor freshness claim. Daily exports are separate.'}
        write_json(self.root/'exports/live.json', report)
        print(json.dumps(report), flush=True)
        return 2 if bad else 0

    def collect(self, full=False):
        cutoff = now()
        cutoff_dt = parse_time(cutoff)
        last_full = parse_time(self.meta('last_full_incident_traversal'))
        full = full or not last_full or (cutoff_dt-last_full).days >= self.config['full_refresh_days']
        self.start('full' if full else 'daily')
        self.import_references()
        self.set_meta('parser_version', PARSER_VERSION)
        # A bounded recent bulletin sample, explicitly not a complete national warning feed.
        self.bipad('alert', {'ordering':'-id'}, max_pages=2, intentional_sample=True)
        for endpoint in ('hazard', 'province', 'district', 'municipality', 'ward'):
            # Stable lookup dimensions; full refresh on bootstrap/weekly reconciliation.
            if full or not self.db.execute('SELECT 1 FROM records WHERE collection=? LIMIT 1', ('bipad:'+endpoint,)).fetchone():
                self.bipad(endpoint, max_pages=30)
        if full:
            result = self.bipad('incident', {'expand': 'loss'})
            if result == 'traversed':
                self.set_meta('last_full_incident_traversal', cutoff)
        else:
            start = (cutoff_dt-dt.timedelta(days=self.config['incident_overlap_days'])).isoformat()
            self.bipad('incident', {'expand':'loss','reported_on__gt':start,'reported_on__lt':cutoff}, window=(start,cutoff))
            self.bipad('incident', {'expand':'loss','ordering':'-modified_on'},
                       max_pages=self.config['incident_revision_pages'], intentional_sample=True)
        for endpoint, time_field in [('rain', 'measured_on'), ('river', 'water_level_on')]:
            last = parse_time(self.meta('last_hydro_' + endpoint))
            proposed = cutoff_dt-dt.timedelta(days=self.config['hydro_overlap_days'])
            if last:
                proposed = min(proposed, last-dt.timedelta(hours=1))
            floor = cutoff_dt-dt.timedelta(days=self.config['hydro_max_catchup_days'])
            if proposed < floor:
                self.issue('bipad:'+endpoint, 'catchup_gap', f'Outage before {floor.isoformat()} exceeds automatic catchup window; explicit backfill needed.')
                proposed = floor
            start = proposed.isoformat()
            result = self.bipad(endpoint, {time_field+'__gt':start,time_field+'__lt':cutoff,'ordering':'id'}, window=(start,cutoff))
            if result == 'traversed':
                self.set_meta('last_hydro_' + endpoint, cutoff)
                key = 'measuredOn' if endpoint == 'rain' else 'waterLevelOn'
                row = self.db.execute("SELECT max(julianday(json_extract(payload,?))) FROM current_payloads WHERE collection=?", ('$.'+key,'bipad:'+endpoint)).fetchone()
                if row[0] is None or self.db.execute('SELECT julianday(?)-?',(cutoff,row[0])).fetchone()[0] > 1:
                    self.issue('bipad:'+endpoint, 'stale_or_empty_feed', 'No measurement within the last 24 hours. Do not interpret an empty/stale response as safe conditions.')
        usgs_start = self.config['usgs_start'] if full else (cutoff_dt-dt.timedelta(days=90)).isoformat()
        self.usgs(usgs_start, cutoff)
        if full:
            self.desinventar()
        # The earlier research is kept as a bibliography, never converted into events.
        self.validate()
        bad = self.db.execute("SELECT count(*) FROM collection_runs WHERE run_id=? AND status IN ('partial','failed','running')", (self.run_id,)).fetchone()[0]
        status = 'partial' if bad else 'completed'
        self.db.execute('UPDATE runs SET status=?,finished_at=? WHERE id=?',(status,now(),self.run_id))
        self.db.commit()
        self.export()
        self.backup()
        print(json.dumps({'run_id':self.run_id,'status':status,'summary':str(self.root/'exports/status.md')},indent=2), flush=True)
        return 2 if bad else 0

    def export(self):
        views = ['incident_current','natural_incidents','incident_places','river_observations','rain_observations','earthquake_current','alert_current']
        for view in views:
            path = self.root/'exports'/(view+'.ndjson.gz')
            temp = path.with_suffix(path.suffix+'.tmp')
            with gzip.open(temp, 'wt', encoding='utf-8') as out:
                for row in self.db.execute('SELECT * FROM '+view):
                    out.write(canonical(dict(row))+'\n')
            temp.replace(path)
        historical = self.root/'exports/desinventar_aggregates.ndjson.gz'
        with gzip.open(historical, 'wt', encoding='utf-8') as out:
            for row in self.db.execute("SELECT collection,native_id,payload,latest_fetch_id FROM current_payloads WHERE collection LIKE 'desinventar:%'"):
                out.write(canonical({'collection':row['collection'],'id':row['native_id'],'data':json.loads(row['payload']),'fetch_id':row['latest_fetch_id']})+'\n')
        counts = [dict(r) for r in self.db.execute('SELECT collection,count(*) records FROM records GROUP BY collection ORDER BY collection')]
        current_run = self.db.execute('SELECT * FROM runs ORDER BY started_at DESC,rowid DESC LIMIT 1').fetchone()
        run = dict(current_run) if current_run else {}
        jobs = [dict(r) for r in self.db.execute('SELECT * FROM collection_runs WHERE run_id=? ORDER BY id', (run.get('id'),))]
        issue_rows = [dict(r) for r in self.db.execute('SELECT collection,severity,code,detail FROM issues WHERE run_id=? ORDER BY id', (run.get('id'),))]
        years = [dict(r) for r in self.db.execute("SELECT substr(local_event_date,1,4) year,hazard,source_hazard_type,count(*) incident_reports FROM incident_current GROUP BY 1,2,3 ORDER BY 1,2")]
        write_json(self.root/'exports/annual_incident_reports.json', years)
        bounds = dict(self.db.execute('SELECT min(local_event_date) first_date,max(local_event_date) last_date FROM incident_current').fetchone())
        manifest = {'generated_at':now(),'parser_version':PARSER_VERSION,'run':run,'collections':counts,'collection_runs':jobs,
                    'incident_date_range':bounds,'issues':issue_rows,'scope':self.config['scope'],
                    'not_for_operational_warnings':True,'historical_microdata_available':False,
                    'limitations':['Reported incidents are not unique disasters.','Do not sum overlapping sources or incident-to-ward joins.',
                     'Source zero may be a default. Null is preserved.','River/rain units and accumulation semantics require source confirmation before quantitative modeling.',
                     'Full-source pagination is live and not atomic. Historical source deletions are not inferred.',
                     'Earlier reports/news are references only; not revalidated incident evidence.','Backup is local, not off-site.']}
        write_json(self.root/'exports/manifest.json', manifest)
        lines = ['# Nepal disaster archive', '', f"Updated: {manifest['generated_at']}", f"Latest run: **{run.get('status','not_run')}**", '',
                 '## Collected records', '', '| Collection | Records |', '|---|---:|']
        lines += [f"| {r['collection']} | {r['records']:,} |" for r in counts]
        lines += ['',f"BIPAD incident dates: {bounds['first_date']} to {bounds['last_date']}.", '',
                  '## Coverage and source status', '', '| Collection | Query start | Query end | Result |', '|---|---|---|---|']
        lines += [f"| {j['collection']} | {j['query_start'] or 'source traversal'} | {j['query_end'] or ''} | {j['status']} |" for j in jobs]
        lines += ['', '## Limits', ''] + ['- '+s for s in manifest['limitations']]
        lines += ['- DesInventar: annual and hazard aggregates for 1971–2013; original individual data cards not downloaded.',
                  '- ReliefWeb report ingestion: awaiting a user-owned approved appname; no access bypass.',
                  '- Not a live warning service or a validated prediction model.', '', '## This run\'s issues', '']
        lines += [f"- {i['collection']}: {i['code']} — {i['detail']}" for i in issue_rows] or ['- No collector issues logged. Source completeness still requires review.']
        (self.root/'exports/status.md').write_text('\n'.join(lines)+'\n')
        return manifest

    def backup(self):
        stamp = dt.datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
        path = self.root/'backups'/('archive-'+stamp+'.sqlite.gz')
        with tempfile.TemporaryDirectory(prefix='disaster-backup-') as temp:
            plain = Path(temp)/'snapshot.sqlite'
            with sqlite3.connect(plain) as dest:
                self.db.backup(dest)
            with plain.open('rb') as inp, gzip.open(path,'wb') as out:
                shutil.copyfileobj(inp,out)
        self.set_meta('last_backup', str(path.relative_to(self.root)))

    def verify_raw(self):
        bad = []
        for row in self.db.execute('SELECT DISTINCT raw_path,sha256 FROM fetches WHERE raw_path IS NOT NULL'):
            path = self.root/row['raw_path']
            try:
                actual = hashlib.sha256(gzip.decompress(path.read_bytes())).hexdigest()
                if actual != row['sha256']:
                    bad.append(str(path))
            except (OSError, EOFError):
                bad.append(str(path))
        return bad

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['collect','live','bootstrap','status','export','verify','backfill-hydro'])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--feed', choices=['rain','river'])
    parser.add_argument('--start', help='Timezone-aware ISO timestamp for explicit hydrology backfill')
    parser.add_argument('--end', help='Timezone-aware ISO timestamp for explicit hydrology backfill')
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    with (args.root/'.collector.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('Another archive operation is running; exiting without overlapping writes.', file=sys.stderr)
            return 3
        archive = Archive(args.root)
        try:
            # Holding the exclusive filesystem lock proves earlier running rows are orphaned.
            if args.command in ('collect','live','bootstrap','backfill-hydro'):
                archive.db.execute("UPDATE runs SET status='interrupted',finished_at=? WHERE status='running'", (now(),))
                archive.db.execute("UPDATE collection_runs SET status='partial',note='Collector interrupted; retained partial data' WHERE status='running'")
                archive.db.commit()
            if args.command == 'live':
                if shutil.disk_usage(args.root).free < 2*1024**3:
                    raise RuntimeError('Less than 2 GiB free disk space; collection stopped')
                return archive.live()
            if args.command == 'backfill-hydro':
                if not all((args.feed,args.start,args.end)):
                    raise ValueError('backfill-hydro requires --feed, --start and --end')
                start, end = parse_time(args.start), parse_time(args.end)
                if not start or not end or start>=end or end>dt.datetime.now(UTC):
                    raise ValueError('Backfill range must be valid, ordered and not in the future')
                if end-start>dt.timedelta(days=7):
                    raise ValueError('Use backfill windows of seven days or less to limit source load')
                archive.start('explicit_hydro_backfill')
                field = 'measured_on' if args.feed=='rain' else 'water_level_on'
                status = archive.bipad(args.feed,{field+'__gt':start.isoformat(),field+'__lt':end.isoformat()},window=(start.isoformat(),end.isoformat()))
                archive.db.execute('UPDATE runs SET status=?,finished_at=? WHERE id=?',('completed' if status=='traversed' else 'partial',now(),archive.run_id))
                archive.db.commit()
                archive.validate(); archive.export(); archive.backup()
                return 0 if status=='traversed' else 2
            if args.command in ('collect','bootstrap'):
                if shutil.disk_usage(args.root).free < 2*1024**3:
                    raise RuntimeError('Less than 2 GiB free disk space; collection stopped')
                return archive.collect(full=args.command=='bootstrap')
            if args.command == 'verify':
                result = {'database':archive.validate(),'bad_raw_files':archive.verify_raw()}
                print(json.dumps(result, indent=2))
                return int(bool(result['bad_raw_files']) or result['database']['quick_check']!='ok' or result['database']['foreign_key_errors']>0)
            if args.command == 'export':
                archive.export()
            print((args.root/'exports/status.md').read_text() if (args.root/'exports/status.md').exists() else 'No collection run yet.')
            return 0
        except Exception as exc:
            if archive.run_id:
                archive.db.execute('UPDATE runs SET status=?,finished_at=?,error=? WHERE id=?',('failed',now(),str(exc),archive.run_id))
                archive.db.commit()
            print(f'Archive failed: {exc}',file=sys.stderr)
            return 1
        finally:
            archive.db.close()

if __name__ == '__main__':
    sys.exit(main())
