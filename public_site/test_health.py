import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
import health


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.s = json.loads(health.pipeline.SEED.read_text())
        self.at = health.epoch(self.s['built_at'])

    def test_retained_does_not_mean_current(self):
        r = health.report(self.s, self.at + 7 * 86400)
        self.assertEqual(r['status'], 'degraded')
        self.assertEqual(r['products']['weather']['stored'], 14)
        self.assertEqual(r['products']['weather']['recent'], 0)
        self.assertEqual(r['products']['weather']['usable'], 0)
        self.assertFalse(r['publication']['recent'])

    def test_recent_failed_attempt_preserves_usable_forecast(self):
        w = self.s['weather'][0]
        w['latest_attempt'] = {'status': 'error', 'fetched_at': self.s['built_at']}
        r = health.report(self.s, self.at)
        self.assertEqual(r['products']['weather']['stored'], 14)
        self.assertEqual(r['products']['weather']['latest_failed'], 1)
        self.assertTrue(r['products']['weather']['pairs'][0]['usable'])
        self.assertEqual(r['status'], 'degraded')

    def test_missing_future_hour_withholds_usable_not_recent(self):
        w = self.s['weather'][0]
        point = next(p for p in w['normalized']['points'] if p['epoch'] > self.at + 3600)
        point['precipitation'] = None
        r = health.report(self.s, self.at)['products']['weather']['pairs'][0]
        self.assertTrue(r['recent'])
        self.assertFalse(r['complete_horizon']['precipitation'])
        self.assertFalse(r['usable'])

    def test_future_publication_invalid(self):
        self.assertEqual(health.report(self.s, self.at - 301)['status'], 'invalid')

    def test_explicit_clock_skew_boundary_retains_actual_age(self):
        for offset, invalid in [(0,False),(120,False),(300,False),(301,True)]:
            with self.subTest(offset=offset):
                r=health.report(self.s,self.at-offset)
                self.assertEqual(r['status']=='invalid',invalid)
                if not invalid:
                    self.assertEqual(r['publication']['age_seconds'],-offset)
                    self.assertEqual(r['publication']['clock_skew_seconds'],offset)
                    self.assertEqual(r['clock_skew_tolerance_seconds'],300)

    def test_future_observation_invalid(self):
        self.s['rivers'][0]['observed_at'] = '2099-01-01T00:00:00Z'
        self.assertEqual(health.report(self.s, self.at)['status'], 'invalid')

    def test_malformed_attempt_invalid(self):
        self.s['weather'][0]['latest_attempt'] = None
        self.assertEqual(health.report(self.s, self.at)['status'], 'invalid')

    def test_incomplete_pair_set_reported(self):
        self.s['weather'].pop()
        r = health.report(self.s, self.at)
        self.assertEqual(r['products']['weather']['stored'], 13)
        self.assertEqual(r['status'], 'degraded')

    def test_bad_schema_and_check_time_invalid(self):
        for value in [None, {}, {'schema_version': 999}]:
            self.assertEqual(health.report(value, self.at)['status'], 'invalid')
        self.assertEqual(health.report(self.s, float('nan'))['status'], 'invalid')
        self.assertEqual(health.report(self.s, self.at, hours=0)['status'], 'invalid')

    def test_cli_read_failure_json_and_nonzero(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as out:
            self.assertEqual(health.main([str(Path(tmp) / 'missing.json')]), 2)
        self.assertEqual(json.loads(out.getvalue())['status'], 'invalid')

if __name__ == '__main__':
    unittest.main()
