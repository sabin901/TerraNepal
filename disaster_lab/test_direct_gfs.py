import copy
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import direct_gfs as g

RUN='2026-11-15T12:00:00Z'


def metadata(field='precipitation', lead=3):
    f=g.FIELDS[field]
    valid=g.utc(RUN)+dt.timedelta(hours=lead)
    return {**{k:f[k] for k in ('shortName','typeOfLevel','level','units','stepType')},
            'edition':2,'centre':'kwbc','stepUnits':1,'dataDate':20261115,'dataTime':1200,
            'validityDate':int(valid.strftime('%Y%m%d')),'validityTime':valid.hour*100,
            'startStep':0 if field=='precipitation' else lead,'endStep':lead,'gridType':'regular_ll','Ni':37,'Nj':21,
            'iDirectionIncrementInDegrees':.25,'jDirectionIncrementInDegrees':.25,
            'latitudeOfFirstGridPointInDegrees':26,'latitudeOfLastGridPointInDegrees':31,
            'longitudeOfFirstGridPointInDegrees':80,'longitudeOfLastGridPointInDegrees':89}


class DirectGFSTests(unittest.TestCase):
    def test_bounded_fixed_source_contract(self):
        u=g.url(RUN,3,'temperature_2m')
        self.assertTrue(u.startswith('https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?'))
        self.assertIn('lev_2_m_above_ground=on',u)
        self.assertIn('var_TMP=on',u)
        for lead in (0,25,True,3.5):
            with self.assertRaises(ValueError):g.url(RUN,lead,'precipitation')
        with self.assertRaises(ValueError):g.url(RUN,3,'arbitrary')
        for run in ('2026-11-15T12:00:00','2026-11-15T13:00:00Z','2026-11-15T12:01:00Z'):
            with self.assertRaises(ValueError):g.url(run,3,'precipitation')

    def test_native_accumulation_never_invents_hourly_values(self):
        r=g.validate_metadata(metadata(),RUN,3,'precipitation')
        self.assertEqual(r['interval_start'],'2026-11-15T12:00:00+00:00')
        self.assertEqual(r['interval_end'],'2026-11-15T15:00:00+00:00')
        self.assertEqual(r['statistic'],'accumulation')
        self.assertNotIn('hourly',r)

    def test_instant_gust_not_interval_maximum(self):
        r=g.validate_metadata(metadata('surface_gust'),RUN,3,'surface_gust')
        self.assertEqual(r['statistic'],'instantaneous')
        self.assertEqual(r['interval_start'],r['interval_end'])

    def test_wrong_units_run_grid_level_and_interval_fail(self):
        for key,value in [('units','m'),('dataDate',20261114),('validityTime',1600),('endStep',4),('startStep',3),('gridType','reduced_gg'),('Ni',36),('level',2),('centre','ecmf'),('stepUnits',0),('latitudeOfFirstGridPointInDegrees',25)]:
            m=metadata();m[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):g.validate_metadata(m,RUN,3,'precipitation')

    def test_accumulation_reset_native_start_preserved(self):
        m=metadata(lead=15);m['startStep']=12
        r=g.validate_metadata(m,RUN,15,'precipitation')
        self.assertEqual(r['interval_start'],'2026-11-16T00:00:00+00:00')
        self.assertEqual(r['interval_end'],'2026-11-16T03:00:00+00:00')

    def test_physical_values_missing_and_zero_distinguished(self):
        self.assertEqual(g.normalize_value(273.15,'temperature_2m'),(0.0,None))
        self.assertEqual(g.normalize_value(0,'precipitation'),(0,None))
        self.assertEqual(g.normalize_value(-.1,'precipitation'),(None,'outside_physical_bounds'))
        self.assertEqual(g.normalize_value(9999,'precipitation',missing=True),(None,'source_missing'))
        self.assertEqual(g.normalize_value(float('nan'),'surface_gust'),(None,'nonfinite_source_value'))
        self.assertEqual(g.normalize_value(True,'surface_gust'),(None,'nonfinite_source_value'))

    def test_truncated_multiple_and_html_messages_fail_before_decoder(self):
        for raw in (b'<html>error</html>',b'GRIB',b'GRIB\0\0\0\2'+(20).to_bytes(8,'big')+b'7777'+b'extra'):
            with self.assertRaises(ValueError):g.decode(raw,RUN,3,'precipitation')

    def test_two_native_rain_intervals_remain_separate(self):
        message=b'GRIB\0\0\0\2'+(20).to_bytes(8,'big')+b'7777'
        self.assertEqual(len(g.split_messages(message*2)),2)
        with self.assertRaises(ValueError):g.split_messages(message*3)
        with patch.object(g,'decode_message',side_effect=[{'interval_start':'a','interval_end':'c','statistic':'accumulation'},{'interval_start':'b','interval_end':'c','statistic':'accumulation'}]):
            result=g.decode(message*2,RUN,3,'precipitation')
            self.assertEqual(len(result['messages']),2)
        with patch.object(g,'decode_message',return_value={'interval_start':'a','interval_end':'c','statistic':'accumulation'}):
            with self.assertRaisesRegex(ValueError,'Duplicate native'):g.decode(message*2,RUN,3,'precipitation')
        with self.assertRaisesRegex(ValueError,'Duplicate instantaneous'):g.decode(message*2,RUN,3,'surface_gust')

    def test_immutable_evidence_deduplicates_and_detects_damage(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=g.retain(tmp,b'exact original bytes','.grib2')
            self.assertEqual(g.retain(tmp,b'exact original bytes','.grib2'),r)
            Path(r['path']).write_bytes(b'changed')
            with self.assertRaises(ValueError):g.retain(tmp,b'exact original bytes','.grib2')

    def test_http_error_retains_original_response_and_does_not_decode(self):
        def request(cmd,**kwargs):
            from types import SimpleNamespace
            Path(cmd[cmd.index('--output')+1]).write_bytes(b'Access unavailable')
            return SimpleNamespace(returncode=0,stdout=b'403',stderr=b'')
        with tempfile.TemporaryDirectory() as tmp,patch.object(g.subprocess,'run',side_effect=request),patch.object(g,'decode') as decoder:
            r=g.acquire(tmp,RUN,3,'precipitation')
            self.assertEqual(r['status'],'error');self.assertEqual(r['http_status'],403)
            self.assertEqual(Path(r['response']['path']).read_bytes(),b'Access unavailable')
            self.assertIsNone(r['normalized']);decoder.assert_not_called()
            self.assertEqual(json.loads(Path(r['receipt']['path']).read_text())['request_url'],g.url(RUN,3,'precipitation'))

    def test_receipt_replay_checks_raw_and_acquisition_cutoff(self):
        def request(cmd,**kwargs):
            from types import SimpleNamespace
            Path(cmd[cmd.index('--output')+1]).write_bytes(b'retained raw fixture')
            return SimpleNamespace(returncode=0,stdout=b'200',stderr=b'')
        with tempfile.TemporaryDirectory() as tmp,patch.object(g.subprocess,'run',side_effect=request),patch.object(g,'decode',return_value={'native_intervals':['fixture']}):
            r=g.acquire(tmp,RUN,3,'precipitation')
            self.assertEqual(g.replay(tmp,r['receipt']['path']),r['normalized'])
            with self.assertRaisesRegex(ValueError,'cutoff'):g.replay(tmp,r['receipt']['path'],as_of='2000-01-01T00:00:00Z')
            Path(r['response']['path']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Raw checksum'):g.replay(tmp,r['receipt']['path'])

    def test_receipt_tampering_rejected_before_decoding(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(g,'decode') as decoder:
            p=Path(tmp)/('0'*64+'.json');p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'Receipt checksum'):g.replay(tmp,p)
            decoder.assert_not_called()

    def test_future_run_does_not_fetch(self):
        with patch.object(g.subprocess,'run') as request:
            with self.assertRaises(ValueError):g.acquire('unused','2099-01-01T00:00:00Z',3,'precipitation')
            request.assert_not_called()


if __name__=='__main__':unittest.main()
