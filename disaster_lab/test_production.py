import contextlib
import io
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
import zipfile
from werkzeug.security import generate_password_hash
from production import create_app
from operations import Operations
from weather import ForecastStore
from verification import verify, ledger
from data import Dataset
from analytics import iso
from backup import create, restore

class ProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password_hash=generate_password_hash('a long test-only password')
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.state=self.root/'state';self.state.mkdir()
        (self.state/'owner.json').write_text(json.dumps({'password_hash':self.password_hash,'version':'test-version'}))
        self.app=create_app(self.root,self.state,origin='https://research.example.org');self.client=self.app.test_client()
        self.base='https://research.example.org'
    def tearDown(self):self.app.extensions['snapshots'].stop.set();self.tmp.cleanup()
    def login(self):
        page=self.client.get('/login',base_url=self.base)
        token=re.search(r'name="token" value="([^"]+)',page.text).group(1)
        return self.client.post('/login',base_url=self.base,data={'token':token,'password':'a long test-only password'})
    def test_archive_is_not_exposed_before_login(self):
        self.assertEqual(self.client.get('/api/overview',base_url=self.base).status_code,401)
        self.assertEqual(self.client.get('/',base_url=self.base).location,'/login')
    def test_host_rebinding_rejected(self):self.assertEqual(self.client.get('/login',base_url='https://evil.example').status_code,400)
    def test_login_requires_csrf(self):self.assertEqual(self.client.post('/login',base_url=self.base,data={'password':'x'}).status_code,403)
    def test_login_cookie_security_and_rotation(self):
        page=self.client.get('/login',base_url=self.base);old=re.search(r'name="token" value="([^"]+)',page.text).group(1)
        response=self.login();self.assertEqual(response.status_code,302)
        cookie=response.headers.get('Set-Cookie');self.assertIn('Secure',cookie);self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
        new=self.client.get('/api/session',base_url=self.base).json['token'];self.assertNotEqual(old,new)
    def test_write_origin_and_token(self):
        self.login();token=self.client.get('/api/session',base_url=self.base).json['token']
        self.assertEqual(self.client.post('/api/refresh',base_url=self.base,json={}).status_code,403)
        self.assertEqual(self.client.post('/api/refresh',base_url=self.base,json={},headers={'X-Lab-Token':token,'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/refresh',base_url=self.base,json={},headers={'X-Lab-Token':token,'Origin':self.base}).status_code,202)
    def test_logout_revokes_session(self):
        self.login();token=self.client.get('/api/session',base_url=self.base).json['token']
        self.assertEqual(self.client.post('/logout',base_url=self.base,json={},headers={'X-Lab-Token':token}).status_code,200)
        self.assertEqual(self.client.get('/api/actions',base_url=self.base).status_code,401)
    def test_unavailable_archive_is_not_ready_or_path_leak(self):
        self.assertEqual(self.client.get('/health/ready',base_url=self.base).status_code,503)
        self.login()
        with self.assertLogs(self.app.logger,level='ERROR'):
            response=self.client.get('/api/overview',base_url=self.base)
        self.assertEqual(response.status_code,503);self.assertNotIn(str(self.root),response.text)
    def test_traversal_and_request_limits(self):
        self.login();self.assertEqual(self.client.get('/../state/owner.json',base_url=self.base).status_code,404)
        self.assertEqual(self.client.post('/api/refresh',base_url=self.base,data='x'*17000,content_type='application/json').status_code,413)
    def test_export_neutralizes_spreadsheet_formulas_after_whitespace(self):
        self.login()
        from types import SimpleNamespace
        row={'incident_id':'1','local_event_date':'2026-01-01','hazard':' \t=1+1','districts':[],
             'latitude':-1,'longitude':1,'reported_deaths':None,'reported_missing':None,'source_verified':False}
        self.app.extensions['snapshots'].current=SimpleNamespace(ensure=lambda:None,incidents=[row])
        response=self.client.get('/api/export',base_url=self.base)
        import csv
        record=next(csv.DictReader(io.StringIO(response.text)))
        self.assertEqual(record['hazard'],"' \t=1+1");self.assertEqual(record['latitude'],'-1');self.assertEqual(record['reported_deaths'],'')
    def test_api_validation_errors(self):
        self.login();self.assertEqual(self.client.get('/api/predictions?limit=100000',base_url=self.base).status_code,400)
        self.assertEqual(self.client.get('/api/river?horizon=0',base_url=self.base).status_code,400)
    def test_security_headers(self):
        r=self.client.get('/login',base_url=self.base)
        self.assertIn("frame-ancestors 'none'",r.headers['Content-Security-Policy']);self.assertEqual(r.headers['Cache-Control'],'no-store')
    def test_owner_credential_required_for_remote(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(FileNotFoundError):create_app(state=t,origin=self.base)

class OperationsTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.ops=Operations(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def job(self,name='live'):return next(j for j in self.ops.status()['jobs'] if j['name']==name)
    def test_heartbeat_expires(self):
        self.ops.heartbeat(at=100);self.assertEqual(self.ops.status(at=101)['worker'],'online');self.assertEqual(self.ops.status(at=191)['worker'],'offline')
    def test_manual_refresh_coalesces_and_does_not_defeat_backoff(self):
        self.ops.begin('live');self.ops.finish('live',1,at=100)
        before=self.job();self.ops.request();self.assertEqual(self.job(),before)
    def test_source_lock_is_deferred_not_failed(self):
        self.ops.begin('live');self.ops.finish('live',3,at=100);j=self.job()
        self.assertEqual((j['state'],j['failures'],j['next_at']),('deferred',0,160))
    def test_recovery_retries_interrupted_jobs(self):
        self.ops.begin('live');self.ops.recover();self.assertEqual(self.job()['state'],'queued')
    def test_login_limit_is_persistent_and_expires(self):
        for _ in range(10):self.assertTrue(self.ops.admit_login(at=100))
        self.assertFalse(Operations(self.tmp.name).admit_login(at=101));self.assertTrue(self.ops.admit_login(at=401))
    def test_refresh_arriving_during_work_is_not_lost(self):
        with patch('operations.time.time',return_value=100):self.ops.begin('analytics')
        with patch('operations.time.time',return_value=101):self.ops.request(('analytics',));self.ops.request(('analytics',))
        self.ops.finish('analytics',0,at=102)
        self.assertEqual(self.job('analytics')['state'],'queued');self.assertEqual(self.job('analytics')['next_at'],102)
        with patch('operations.time.time',return_value=103):self.ops.begin('analytics')
        self.ops.finish('analytics',0,at=104)
        self.assertEqual(self.job('analytics')['state'],'completed')
    def test_failure_backoff_then_success(self):
        for _ in range(3):self.ops.finish('live',1,at=100)
        self.assertEqual(self.job()['next_at'],340)
        self.ops.finish('live',0,at=400);self.assertEqual(self.job()['failures'],0);self.assertEqual(self.job()['last_success'],400)

class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=ForecastStore(self.tmp.name)
        self.dataset=Dataset();self.dataset.ensure=lambda:self.dataset
        self.dataset.river_groups={'s':[{'observed_at':iso(2000),'water_level_source_units':12,'observation_id':'1','version_id':1}]}
        with contextlib.closing(self.store.db()) as db,db:
            for i in range(130):
                payload={'projection':{'level':10,'lower':8,'upper':14},'selected_model':'persistence','partitions':{'target_tolerance_minutes':1}}
                db.execute('INSERT INTO river_predictions VALUES(?,?,?,?,?,?,?,?,?)',(str(i),'s',60,iso(0),iso(2000),iso(1000),'v1','hash',json.dumps(payload)))
    def tearDown(self):self.tmp.cleanup()
    def test_verifies_all_rows_and_paginates_separately(self):
        verify(self.store,self.dataset,at=2100);r=ledger(self.store)
        self.assertEqual(r['total'],130);self.assertEqual(len(r['rows']),100);self.assertEqual(r['counts']['matched'],130)
        self.assertEqual(r['metrics'][0]['mae'],2);self.assertEqual(len(ledger(self.store,offset=100)['rows']),30)
    def test_observation_revision_preserves_outcome_history(self):
        verify(self.store,self.dataset,at=2100);verify(self.store,self.dataset,at=2200)
        with contextlib.closing(self.store.db()) as db:self.assertEqual(db.execute('SELECT count(*) FROM outcome_history').fetchone()[0],130)
        self.dataset.river_groups['s'][0].update(water_level_source_units=0,version_id=2)
        verify(self.store,self.dataset,at=2300)
        self.assertEqual(ledger(self.store)['metrics'][0]['mae'],10)
        with contextlib.closing(self.store.db()) as db:self.assertEqual(db.execute('SELECT count(*) FROM outcome_history').fetchone()[0],260)
    def test_missing_observation_is_not_zero_or_matched(self):
        self.dataset.river_groups={};verify(self.store,self.dataset,at=2100);r=ledger(self.store)
        self.assertEqual(r['counts']['awaiting_observation'],130);self.assertEqual(r['metrics'],[])
    def test_conflicting_target_values_are_not_scored(self):
        self.dataset.river_groups['s'].append({'observed_at':iso(2000),'water_level_source_units':40,'observation_id':'2','version_id':2})
        verify(self.store,self.dataset,at=2100);r=ledger(self.store)
        self.assertEqual(r['counts']['conflicting_observation'],130);self.assertEqual(r['metrics'],[])
    def test_future_measurements_not_scored(self):
        verify(self.store,self.dataset,at=1900);self.assertEqual(ledger(self.store)['counts']['pending'],130)

class SnapshotTests(unittest.TestCase):
    def test_empty_archive_and_failed_refresh_preserve_complete_snapshot(self):
        from snapshots import SnapshotCache
        import os
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);archive=root/'disaster_archive';(archive/'data').mkdir(parents=True)
            schema=Path(__file__).resolve().parents[1]/'disaster_archive/schema.sql'
            with contextlib.closing(sqlite3.connect(archive/'data/archive.sqlite')) as db:db.executescript(schema.read_text())
            cache=SnapshotCache(root);cache.refresh();original=cache.get()
            self.assertIsNone(original.overview()['date_start']);self.assertEqual(original.incident_query()['total'],0)
            os.utime(archive/'data/archive.sqlite',None)
            with patch('snapshots.Dataset.ensure',side_effect=OSError('test outage')),self.assertLogs('snapshots',level='ERROR'):
                cache.refresh()
            self.assertIs(cache.get(),original);self.assertIsNotNone(cache.last_error)
    def test_missing_incident_date_is_not_invented_or_crashing(self):
        d=Dataset();d.ensure=lambda:d
        d.incidents=[{'incident_id':'1','local_event_date':None,'hazard':'Flood','districts':[]}]
        self.assertEqual(d.incident_query('Flood')['total'],1);self.assertEqual(d.incident_query('Flood',year='2024')['total'],0)

class BackupTests(unittest.TestCase):
    def test_roundtrip_is_checked_and_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);archive=root/'archive';state=root/'state';(archive/'data/raw').mkdir(parents=True);state.mkdir()
            raw=archive/'data/raw/original.gz';raw.write_bytes(b'original-response')
            with contextlib.closing(sqlite3.connect(archive/'data/archive.sqlite')) as db,db:
                db.execute('CREATE TABLE fetches(raw_path TEXT)');db.execute('INSERT INTO fetches VALUES(?)',('data/raw/original.gz',))
            ForecastStore(state)
            report=create(archive,state,root/'backup.zip');self.assertGreater(report['files'],1)
            restore(root/'backup.zip',root/'restored')
            self.assertEqual((root/'restored/archive/data/raw/original.gz').read_bytes(),raw.read_bytes())
            with self.assertRaises(ValueError):restore(root/'backup.zip',root/'restored')
    def test_tampered_backup_is_rejected_without_publishing_partial_restore(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            with zipfile.ZipFile(root/'bad.zip','w') as z:
                z.writestr('state/a','bad');z.writestr('manifest.json',json.dumps({'format':1,'files':{'state/a':{'bytes':3,'sha256':'wrong'}}}))
            with self.assertRaises(ValueError):restore(root/'bad.zip',root/'restored')
            self.assertFalse((root/'restored').exists())
    def test_traversal_archive_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            with zipfile.ZipFile(root/'bad.zip','w') as z:
                z.writestr('../escape','x');z.writestr('manifest.json',json.dumps({'format':1,'files':{'../escape':{}}}))
            with self.assertRaises(ValueError):restore(root/'bad.zip',root/'restored')
            self.assertFalse((root/'escape').exists())

if __name__=='__main__':unittest.main()
