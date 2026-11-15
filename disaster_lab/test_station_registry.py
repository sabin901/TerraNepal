import copy
import unittest
from station_registry import build,distance_km

PLACE=[dict(id='test',latitude=27.,longitude=85.)]
def row():return dict(station_id='NPI0000VNKT',observed_at='2026-11-01T00:00:00Z',retrieved_at='2026-11-02T00:00:00Z',latitude=27.,longitude=85.,elevation_m=1300.,variable='temperature_2m',units='degC',value=0.,eligible_temperature=True,quality_flags=[],response_sha256='a'*64,source_line=2)
def registry(rows):return build(dict(schema_version=1,records=rows),PLACE)

class StationRegistryTests(unittest.TestCase):
    def test_candidate_is_never_verified_even_at_identical_point(self):
        r=registry([row()]);c=r['candidates'][0]
        self.assertFalse(c['verified']);self.assertEqual(r['verified_mapping_count'],0)
        self.assertEqual(c['metadata_variants'][0]['distances_to_requested_city_points'][0]['distance_km'],0)
        self.assertIsNone(c['native_model_grid_elevation_m']);self.assertEqual(c['eligible_temperature_candidates'],1)
    def test_conflicting_metadata_preserved_not_selected(self):
        a,b=row(),row();b.update(source_line=3,elevation_m=1400.,latitude=27.1)
        c=registry([a,b])['candidates'][0]
        self.assertEqual(len(c['metadata_variants']),2);self.assertIn('conflicting_station_metadata',c['review_reasons'])
    def test_missing_metadata_and_future_time_are_review_needed(self):
        x=row();x.update(latitude=None,elevation_m=None,observed_at='2026-11-03T00:00:00Z')
        c=registry([x])['candidates'][0]
        self.assertEqual(c['eligible_temperature_candidates'],0);self.assertEqual(c['metadata_variants'][0]['distances_to_requested_city_points'],[])
        self.assertIn('invalid_observation_or_retrieval_time',c['review_reasons'])
    def test_source_identity_duplicate_and_conflict(self):
        a,b=row(),row();r=registry([a,b]);self.assertEqual(r['included_records'],1);self.assertEqual(r['duplicate_input_records'],1)
        b['value']=1
        with self.assertRaises(ValueError):registry([a,b])
    def test_bad_provenance_excluded_not_fabricated(self):
        x=row();x['response_sha256']='unknown'
        r=registry([x]);self.assertEqual(r['excluded_records'],1);self.assertEqual(r['station_count'],0)
    def test_determinism_and_no_mutation(self):
        a,b=row(),row();b.update(source_line=3,latitude=27.1);original=copy.deepcopy(a)
        self.assertEqual(registry([a,b]),registry([b,a]));self.assertEqual(a,original)
    def test_timezone_and_flags_preserved_as_eligibility_boundary(self):
        x=row();x['observed_at']='2026-11-01T05:45:00+05:45';x['quality_flags']=['requires_review']
        c=registry([x])['candidates'][0];self.assertEqual(c['observed_start'],'2026-11-01T00:00:00+00:00');self.assertEqual(c['eligible_temperature_candidates'],0)
    def test_distance_known_boundary(self):
        self.assertAlmostEqual(distance_km(0,0,0,1),111.195,places=3)
        self.assertAlmostEqual(distance_km(0,180,0,-180),0,places=6)
    def test_empty_and_invalid_schema(self):
        self.assertEqual(registry([])['station_count'],0)
        with self.assertRaises(ValueError):build({'schema_version':True,'records':[]})
