import copy
import json
import math
import unittest

import intelligence as i
import pipeline
from health import epoch


class IntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.s = json.loads(pipeline.SEED.read_text())
        self.at = epoch(self.s['built_at'])

    def test_replay_identity_and_evidence_changes(self):
        a = i.brief(self.s, self.at)
        self.assertEqual(a, i.brief(copy.deepcopy(self.s), self.at))
        self.s['rivers'][0]['level'] = None
        b = i.brief(self.s, self.at)
        self.assertNotEqual(a['brief_id'], b['brief_id'])
        self.assertNotEqual(a['snapshot_sha256'], b['snapshot_sha256'])
        self.assertNotEqual(a['brief_id'], i.brief(json.loads(pipeline.SEED.read_text()), self.at+1)['brief_id'])

    def test_exported_cutoff_replays_submicrosecond_clock(self):
        b = i.brief(self.s, self.at + 0.1234567)
        self.assertEqual(b, i.brief(self.s, epoch(b['assessed_at'])))

    def test_no_historical_knowledge_leak(self):
        with self.assertRaisesRegex(ValueError, 'not available'):
            i.brief(self.s, self.at - 1)
        with self.assertRaises(ValueError):
            i.brief(self.s, self.at - 301)

    def test_clock_skew_is_not_historical_knowledge(self):
        import datetime as dt
        future = dt.datetime.fromtimestamp(self.at+1, dt.timezone.utc).isoformat()
        self.s['weather'][0]['fetched_at'] = future
        with self.assertRaisesRegex(ValueError, 'not available'):
            i.brief(self.s, self.at)

    def test_cli_cannot_overwrite_evidence(self):
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'snapshot.json'
            original = json.dumps(self.s)
            source.write_text(original)
            p = subprocess.run([sys.executable, i.__file__, str(source), '--output', str(source)], capture_output=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertEqual(source.read_text(), original)

    def test_stale_values_withheld_not_zero(self):
        b = i.brief(self.s, self.at + 7*86400)
        self.assertTrue(all(all(v is None for v in w['values'].values()) for w in b['weather']))
        self.assertTrue(all(set(w['withheld'].values()) == {'stale_retrieval'} for w in b['weather']))
        self.assertNotIn('| 0.0 |', i.markdown(b))

    def test_precipitation_window_excludes_partial_hour(self):
        start = math.ceil(self.at/3600)*3600
        w = self.s['weather'][0]
        for p in w['normalized']['points']:
            p['precipitation'] = 1 if start < p['epoch'] <= start + 24*3600 else 999
        b = i.brief(self.s, self.at)
        self.assertEqual(b['weather'][0]['values']['precipitation']['total'], 24)

    def test_one_missing_variable_does_not_destroy_others(self):
        w = self.s['weather'][0]
        next(p for p in w['normalized']['points'] if p['epoch'] > self.at+3600)['precipitation'] = None
        b = i.brief(self.s, self.at)['weather'][0]
        self.assertIsNone(b['values']['precipitation'])
        self.assertIsNotNone(b['values']['temperature_2m'])
        self.assertEqual(b['withheld']['precipitation'], 'incomplete_window')

    def test_failed_attempt_kept_visible_with_last_valid_values(self):
        self.s['weather'][0]['latest_attempt'] = {'status':'error', 'fetched_at': self.s['built_at']}
        b = i.brief(self.s, self.at)
        self.assertTrue(b['weather'][0]['latest_attempt_failed'])
        self.assertEqual(b['availability']['status'], 'degraded')
        self.assertIsNotNone(b['weather'][0]['values']['temperature_2m'])

    def test_conflicts_and_sectors_never_become_safe_or_impact_claims(self):
        self.s['rivers'][0].update(level=None, conflicting=True)
        b = i.brief(self.s, self.at)
        self.assertGreaterEqual(b['river_review']['conflicting_stations'], 1)
        self.assertEqual(len(b['sector_readiness']), 12)
        self.assertTrue(all(s['impact_assessment']=='not_established' for s in b['sector_readiness']))
        self.assertFalse(b['release']['validated_local_prediction'])
        self.assertFalse(b['release']['operational_warnings'])
        self.assertIn('Not a warning', i.markdown(b))

    def test_invalid_source_hash_rejected(self):
        self.s['weather'][0]['sha256'] = 'not-a-sha256'
        with self.assertRaisesRegex(ValueError, 'response hash'):
            i.brief(self.s, self.at)

    def test_malformed_evidence_rejected(self):
        self.s['rivers'][0]['level'] = float('nan')
        with self.assertRaises(ValueError): i.brief(self.s, self.at)

if __name__ == '__main__':
    unittest.main()
