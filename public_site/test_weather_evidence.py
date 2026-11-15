import base64
import contextlib
import copy
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import weather_evidence as e
import data_branch as branch
import pipeline
import history

class WeatherEvidenceTests(unittest.TestCase):
    def row(self,raw=b'{"error":true}'):
        url,_,_=e.forecast_runs.request_url('kathmandu','gfs_global','2026-11-15T00:00:00Z',1800000000)
        return dict(place_id='kathmandu',model='gfs_global',requested_run='2026-11-15T00:00:00+00:00',fetched_at='2026-11-15T10:00:00+00:00',url=url,status='error',error='Source unavailable',sha256=hashlib.sha256(raw).hexdigest())
    def test_exact_error_bytes_roundtrip_and_tamper_rejected(self):
        raw=b'provider error\n with original whitespace\x00'
        with tempfile.TemporaryDirectory() as tmp:
            name=e.retain(tmp,'original_run',self.row(raw),raw)
            envelope=branch.verify_file(name,(Path(tmp)/name).read_bytes())
            self.assertEqual(e.validate(envelope),raw)
            envelope['response_base64']=base64.b64encode(b'tampered').decode()
            with self.assertRaises(ValueError):e.validate(envelope)
    def test_unapproved_url_and_private_fields_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            name=e.retain(tmp,'original_run',self.row(),b'{"error":true}')
            obj=json.loads(gzip.decompress((Path(tmp)/name).read_bytes()))
            for url in ['https://single-runs-api.open-meteo.com.evil.test/v1/forecast','https://user:password@single-runs-api.open-meteo.com/v1/forecast',obj['url']+'&apikey=secret']:
                with self.assertRaises(ValueError):e.validate({**obj,'url':url})
            with self.assertRaises(ValueError):e.validate({**obj,'private_note':'not allowed'})
    def test_scheduled_run_deduplication_and_error_retry(self):
        at=e.stamp('2026-11-15T10:00:00Z').timestamp()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path='evidence/weather/2026-11-15/'+'a'*64+'.json.gz'
            state={'schema_version':1,'runs':{p['id']+':'+m:dict(initialized_at='2026-11-15T00:00:00+00:00',fetched_at='2026-11-15T09:59:00Z',status='ok',evidence_path=path) for p in e.PLACES for m in e.MODELS}}
            (root/'weather-evidence-state.json').write_text(json.dumps(state))
            with patch.object(e.forecast_runs,'collect') as collect:
                report=e.collect(root,at);self.assertEqual(report['skipped'],14);collect.assert_not_called()
            # Error retries are bounded to an hour; never silently called successful.
            state['runs']['kathmandu:gfs_global']['status']='error'
            (root/'weather-evidence-state.json').write_text(json.dumps(state))
            with patch.object(e.forecast_runs,'collect') as collect:
                self.assertEqual(e.collect(root,at)['skipped'],14);collect.assert_not_called()
    def test_rolling_only_never_fetches_originals(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(e.forecast_runs,'collect') as fetch:
            report=e.collect(tmp,rolling_only=True)
            fetch.assert_not_called();self.assertEqual(report['retained_original'],0)

    def test_original_acquisition_and_rolling_errors_are_retained(self):
        from types import SimpleNamespace
        from urllib.parse import urlparse,parse_qs
        from weather import ForecastStore,UNITS
        def response(args,**kwargs):
            q=parse_qs(urlparse(args[-1]).query)
            start=e.stamp(q['run'][0]+'+00:00').timestamp()
            payload=dict(latitude=float(q['latitude'][0]),longitude=float(q['longitude'][0]),elevation=1300,utc_offset_seconds=0,hourly_units=UNITS,
                hourly=dict(time=[start+i*3600 for i in range(96)],temperature_2m=[12]*96,precipitation=[0]*96,wind_gusts_10m=[2]*96))
            return SimpleNamespace(returncode=0,stdout=json.dumps(payload).encode(),stderr=b'')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);store=ForecastStore(root/'raw-local'/'weather')
            failed=b'{"error":true,"reason":"rate limited"}'
            with patch('weather.subprocess.run',return_value=SimpleNamespace(returncode=22,stdout=failed,stderr=b'HTTP429')):
                store.fetch(e.PLACES[0],'gfs_global',force=True)
            with patch.object(e.forecast_runs.subprocess,'run',side_effect=response):
                result=e.collect(root,e.stamp('2026-11-15T19:00:00Z').timestamp())
            self.assertEqual(result['retained_rolling'],1)
            self.assertEqual(result['original_ok'],14)
            self.assertEqual(result['original_errors'],0)
            files=list((root/'evidence'/'weather').rglob('*.json.gz'))
            self.assertEqual(len(files),15)
            rows=[branch.verify_file(p.relative_to(root).as_posix(),p.read_bytes()) for p in files]
            self.assertIn(failed,[e.validate(r) for r in rows])
            self.assertEqual(len({(r['place_id'],r['model']) for r in rows if r['source']=='original_run'}),14)
            state=json.loads((root/'weather-evidence-state.json').read_text())
            for key,r in state['runs'].items():
                body=branch.verify_file(r['evidence_path'],(root/r['evidence_path']).read_bytes())
                self.assertEqual(key,body['place_id']+':'+body['model'])

    def test_one_worker_failure_does_not_lose_completed_receipt(self):
        import threading
        original=e.forecast_runs.collect;completed=threading.Event()
        from types import SimpleNamespace
        def acquire(root,place,model,run):
            if model=='ecmwf_ifs025':
                result=original(root,place,model,run);completed.set();return result
            completed.wait(5);raise RuntimeError('simulated worker failure')
        with tempfile.TemporaryDirectory() as tmp,patch.object(e,'PLACES',[e.PLACES[0]]),patch.object(e.forecast_runs,'collect',side_effect=acquire),patch.object(e.forecast_runs.subprocess,'run',return_value=SimpleNamespace(returncode=22,stdout=b'{"error":true}',stderr=b'HTTP 503')):
            r=e.collect(tmp,e.stamp('2026-11-15T19:00:00Z').timestamp())
            self.assertEqual(r['retained_original'],1);self.assertEqual(len(r['collection_errors']),1)
            state=json.loads((Path(tmp)/'weather-evidence-state.json').read_text())
            receipt=state['runs']['kathmandu:ecmwf_ifs025']
            self.assertTrue((Path(tmp)/receipt['evidence_path']).exists())

    def test_evidence_state_restores_from_git_with_raw_replay(self):
        original=Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);remote=root/'remote.git';repo=root/'repo';repo.mkdir()
            subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
            subprocess.run(['git','init',str(repo)],check=True,capture_output=True)
            try:
                os.chdir(repo);subprocess.run(['git','remote','add','origin',str(remote)],check=True)
                state_root=root/'state';branch.restore(state_root)
                snapshot=json.loads(pipeline.SEED.read_text());history.save_run(state_root,history.fresh_state(),snapshot,[],[])
                raw=b'{"error":true}';name=e.retain(state_root,'original_run',self.row(raw),raw)
                state={'schema_version':1,'runs':{'kathmandu:gfs_global':dict(initialized_at=self.row()['requested_run'],fetched_at=self.row()['fetched_at'],status='error',evidence_path=name)}}
                (state_root/'weather-evidence-state.json').write_text(json.dumps(state))
                commit=branch.save(state_root);restored=root/'restored';branch.restore(restored)
                self.assertEqual(json.loads((restored/'weather-evidence-state.json').read_text()),state)
                blob=branch.git('show',commit+':'+name);self.assertEqual(e.validate(branch.verify_file(name,blob)),raw)
                self.assertGreater(json.loads((state_root/'storage-report.json').read_text())['current_tree_bytes'],0)
                state['runs']['kathmandu:gfs_global']['evidence_path']='evidence/weather/2026-11-15/'+'0'*64+'.json.gz'
                (state_root/'weather-evidence-state.json').write_text(json.dumps(state))
                with self.assertRaisesRegex(ValueError,'missing blob'):branch.save(state_root)
            finally:os.chdir(original)
