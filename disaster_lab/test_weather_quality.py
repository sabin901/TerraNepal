"""Synthetic regression tests for physical-value quarantine and diagnostics."""
import copy
import unittest
import test_forecast_runs as fixtures
from weather import normalize,PLACES

class WeatherQualityTests(unittest.TestCase):
    def test_impossible_values_and_metadata_rejected_without_mutation(self):
        for field,value in [('temperature_2m',999),('temperature_2m',-101),('precipitation',2001),('wind_gusts_10m',151)]:
            p=fixtures.OriginalRuns().payload();p['hourly'][field][0]=value;original=copy.deepcopy(p)
            with self.assertRaises(ValueError):normalize(p,PLACES[0])
            self.assertEqual(p,original)
        for elevation in ['1300',True,float('inf'),9001,-501]:
            p=fixtures.OriginalRuns().payload();p['elevation']=elevation
            with self.assertRaises(ValueError):normalize(p,PLACES[0])
    def test_negative_precipitation_reports_exact_sample_without_clamping(self):
        # Mirrors the value class observed in retained ECMWF responses, without
        # treating a negative quantity as dry weather or silently accepting it.
        p=fixtures.OriginalRuns().payload()
        p['hourly']['precipitation'][17]=-0.1
        original=copy.deepcopy(p)
        with self.assertRaises(ValueError) as raised:
            normalize(p,PLACES[0],'ecmwf_ifs025')
        message=str(raised.exception)
        self.assertIn('precipitation; index=17;',message)
        self.assertIn('value=-0.1; allowed=0..2000 mm',message)
        from analytics import iso
        self.assertIn('at='+iso(p['hourly']['time'][17]),message)
        self.assertEqual(p,original)

    def test_zero_null_and_extreme_but_in_envelope_preserved(self):
        p=fixtures.OriginalRuns().payload();p['hourly']['precipitation'][:3]=[0,None,500]
        p['elevation']=None
        self.assertEqual([r['precipitation'] for r in normalize(p,PLACES[0])['points'][:3]],[0,None,500])
    def test_grid_envelope_is_not_mapping_approval(self):
        p=fixtures.OriginalRuns().payload();p['latitude']+=.49
        # Terrain-selected cells may be displaced; broad guard is not a reviewed mapping.
        self.assertEqual(normalize(p,PLACES[0],'ecmwf_ifs025')['grid_latitude'],p['latitude'])
        p['latitude']+=.02
        with self.assertRaises(ValueError):normalize(p,PLACES[0],'ecmwf_ifs025')
        with self.assertRaises(ValueError):normalize(fixtures.OriginalRuns().payload(),PLACES[0],'unknown')
