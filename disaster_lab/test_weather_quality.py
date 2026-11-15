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

    def test_variable_quarantine_preserves_valid_values_and_missingness(self):
        p=fixtures.OriginalRuns().payload()
        p['hourly']['precipitation'][:3]=[-0.1,None,0]
        original=copy.deepcopy(p)
        n=normalize(p,PLACES[0],quarantine=True)
        self.assertEqual([x['precipitation'] for x in n['points'][:3]],[None,None,0])
        self.assertEqual(n['points'][0]['temperature_2m'],12)
        self.assertEqual(n['points'][0]['wind_gusts_10m'],3)
        self.assertEqual(n['quality'],[{'variable':'precipitation','index':0,
                         'at':n['points'][0]['at'],'value':-0.1,'reason':'outside_physical_bounds'}])
        self.assertEqual(p,original)
        # A complete horizon is still mandatory for rainfall totals.
        from weather import summarize
        window=summarize(n,n['points'][0]['at'],at=p['hourly']['time'][0])['windows']['24']
        self.assertIsNone(window['precipitation_mm'])
        self.assertEqual(window['max_temperature_c'],12)
        self.assertEqual(window['max_gust_ms'],3)

    def test_quarantine_does_not_accept_schema_or_nonfinite_errors(self):
        for value in ['-0.1',True,float('inf'),float('nan'),{},[]]:
            with self.subTest(value=value):
                p=fixtures.OriginalRuns().payload();p['hourly']['precipitation'][0]=value
                with self.assertRaises(ValueError):normalize(p,PLACES[0],quarantine=True)
        p=copy.deepcopy(fixtures.OriginalRuns().payload());p['hourly_units']['precipitation']='inch'
        with self.assertRaises(ValueError):normalize(p,PLACES[0],quarantine=True)

    def test_rolling_quarantine_retains_exact_raw_and_quality_after_reopen(self):
        import contextlib
        import hashlib
        import json
        import subprocess
        import tempfile
        from unittest.mock import patch
        import weather
        p=fixtures.OriginalRuns().payload();p['hourly']['precipitation'][17]=-0.1
        body=json.dumps(p,indent=2).encode()
        with tempfile.TemporaryDirectory() as tmp, patch.object(weather.subprocess,'run',return_value=subprocess.CompletedProcess([],0,body,b'')):
            store=weather.ForecastStore(tmp)
            result=store.fetch(PLACES[0],'ecmwf_ifs025',force=True)
            self.assertEqual(result['status'],'ok')
            reopened=weather.ForecastStore(tmp)
            with contextlib.closing(reopened.db()) as db:
                row=db.execute('SELECT * FROM weather_fetches').fetchone()
            self.assertEqual(row['sha256'],hashlib.sha256(body).hexdigest())
            self.assertEqual((reopened.raw/row['raw_file']).read_bytes(),body)
            n=json.loads(row['normalized'])
            self.assertEqual(n,normalize(json.loads(body),PLACES[0],'ecmwf_ifs025',quarantine=True))
            self.assertEqual(n['quality'][0]['value'],-0.1)
            self.assertIsNone(n['points'][17]['precipitation'])
            self.assertEqual(n['points'][17]['temperature_2m'],12)

    def test_valid_payload_normalized_shape_is_backward_compatible(self):
        p=fixtures.OriginalRuns().payload()
        self.assertEqual(normalize(p,PLACES[0]),normalize(p,PLACES[0],quarantine=True))
        self.assertNotIn('quality',normalize(p,PLACES[0],quarantine=True))
