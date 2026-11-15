import contextlib
import datetime as dt
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import forecast_runs as r
from weather import UNITS, PLACES

class OriginalRuns(unittest.TestCase):
    def payload(self):
        start=r.run_time('2026-11-15T00:00:00Z').timestamp()
        return {'latitude':PLACES[0]['latitude'],'longitude':PLACES[0]['longitude'],
                'elevation':1300,'utc_offset_seconds':0,'hourly_units':UNITS,
                'hourly':{'time':[start+i*3600 for i in range(96)],
                          'temperature_2m':[12]*96,'precipitation':[0]*96,'wind_gusts_10m':[3]*96}}
    def test_explicit_initialization_and_future_guard(self):
        for value in ['2026-11-15T00:00:00','2026-11-15T01:00:00Z','2026-11-15T00:01:00Z']:
            with self.assertRaises(ValueError):r.run_time(value)
        with self.assertRaises(ValueError):r.request_url('kathmandu','ecmwf_ifs025','2026-11-15T00:00:00Z',0)
    def test_contract_and_no_fabricated_issuance_echo(self):
        initialized=r.run_time('2026-11-15T00:00:00Z')
        x=r.normalize_run(self.payload(),PLACES[0],initialized)
        self.assertEqual(x['model_issued_at'],initialized.isoformat())
        self.assertIn('not independently echoed',x['time_note'])
        with self.assertRaises(ValueError):r.normalize_run(self.payload(),PLACES[0],initialized+dt.timedelta(hours=6))
    def test_failed_retry_preserves_prior_success_and_exact_error_body(self):
        body=json.dumps(self.payload()).encode();bad=b'{"error":true,"reason":"unavailable"}'
        with tempfile.TemporaryDirectory() as tmp,patch.object(r.time,'time',return_value=1800000000),patch.object(r.subprocess,'run',side_effect=[subprocess.CompletedProcess([],0,body,b''),subprocess.CompletedProcess([],22,bad,b'HTTP 503')]):
            a=r.collect(tmp,'kathmandu','ecmwf_ifs025','2026-11-15T00:00:00Z')
            b=r.collect(tmp,'kathmandu','ecmwf_ifs025','2026-11-15T00:00:00Z')
            self.assertEqual(a['status'],'ok');self.assertEqual(b['status'],'error')
            self.assertEqual((Path(tmp)/'raw'/(b['sha256']+'.json')).read_bytes(),bad)
            with contextlib.closing(sqlite3.connect(Path(tmp)/'runs.sqlite')) as db:
                self.assertEqual(db.execute('SELECT status FROM fetches ORDER BY id').fetchall(),[('ok',),('error',)])
    def test_transport_timeout_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(r.time,'time',return_value=1800000000),patch.object(r.subprocess,'run',side_effect=subprocess.TimeoutExpired('curl',50)):
            self.assertEqual(r.collect(tmp,'kathmandu','ecmwf_ifs025','2026-11-15T00:00:00Z')['status'],'error')
