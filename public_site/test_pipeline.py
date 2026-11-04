import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pipeline as p

class PublicSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.seed=json.loads(p.SEED.read_text())
    def test_seed_schema(self):p.validate(self.seed)
    def test_private_field_rejected(self):
        s=copy.deepcopy(self.seed);s['rivers'][0]['incident_narrative']='Private'
        with self.assertRaises(ValueError):p.validate(s)
    def test_nonfinite_rejected(self):
        s=copy.deepcopy(self.seed);s['rivers'][0]['level']=float('nan')
        with self.assertRaises(ValueError):p.validate(s)
    def test_units_rejected(self):
        s=copy.deepcopy(self.seed);s['weather'][0]['normalized']['units']['precipitation']='inch'
        with self.assertRaises(ValueError):p.validate(s)
    def test_missing_weather_value_preserved(self):
        s=copy.deepcopy(self.seed);s['weather'][0]['normalized']['points'][0]['precipitation']=None
        self.assertIsNone(p.validate(s)['weather'][0]['normalized']['points'][0]['precipitation'])
    def test_missing_stations_keep_original_timestamp(self):
        rows=self.seed['rivers'][:2]
        self.assertEqual(p.merge_stations(rows,[]),sorted(rows,key=lambda s:s['id']))
    def test_old_response_does_not_replace_new(self):
        r=copy.deepcopy(self.seed['rivers'][0]);old={**r,'observed_at':'2000-01-01T00:00:00Z','level':99}
        self.assertEqual(p.merge_stations([r],[old]),[r])
    def test_equal_time_conflict_withholds_level(self):
        r=copy.deepcopy(self.seed['rivers'][0]);new={**r,'level':(r['level'] or 0)+1}
        result=p.merge_stations([r],[new])[0]
        self.assertTrue(result['conflicting']);self.assertIsNone(result['level'])
    def test_new_time_can_resolve_conflict(self):
        r=copy.deepcopy(self.seed['rivers'][0]);r.update(level=None,conflicting=True)
        new={**r,'observed_at':'2090-01-01T00:00:00Z','level':3,'conflicting':False}
        self.assertEqual(p.merge_stations([r],[new]),[new])
    def test_build_only_allowlisted_files(self):
        with tempfile.TemporaryDirectory() as d:
            p.build(p.SEED,d)
            files={str(f.relative_to(d)) for f in Path(d).rglob('*') if f.is_file()}
            self.assertEqual(files,set(p.ASSETS)|{'data/snapshot.json','.nojekyll'})
            with self.assertRaises(ValueError):p.build(p.SEED,d)
    def test_download_failure_falls_back_to_dated_seed(self):
        with patch.object(p.subprocess,'run',side_effect=OSError('offline')):
            self.assertEqual(p.previous_snapshot()['built_at'],self.seed['built_at'])
    def test_duplicate_station_rejected(self):
        s=copy.deepcopy(self.seed);s['rivers'].append(s['rivers'][0])
        with self.assertRaises(ValueError):p.validate(s)

if __name__=='__main__':unittest.main()
