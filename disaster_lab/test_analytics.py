import copy
import datetime as dt
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from analytics import analyze, predict, station_quality
from data import Dataset, clean_points
from weather import normalize, summarize, ForecastStore, PLACES
from test_lab import BASE, point
from predictions import record_predictions

def linear_series():
    return [point(i*15,10+i*.25) for i in range(480)]

def weather_payload():
    t=BASE.timestamp()
    return {'latitude':27.75,'longitude':85.25,'utc_offset_seconds':0,
            'hourly_units':{'time':'unixtime','precipitation':'mm','temperature_2m':'°C','wind_gusts_10m':'m/s'},
            'hourly':{'time':[t+i*3600 for i in range(96)],'precipitation':[1.0]*96,'temperature_2m':[20.0]*96,'wind_gusts_10m':[5.0]*96}}

class ModelTests(unittest.TestCase):
    def setUp(self):self.rows=linear_series();self.at=BASE.timestamp()+479*900
    def test_linear_trend_beats_persistence_on_selection_and_test(self):
        d=analyze(self.rows,60,self.at)
        self.assertEqual(d['selected_model'],'damped_trend')
        self.assertEqual(d['status'],'experimental')
        self.assertGreater(d['test_skill_vs_persistence'],.7)
        self.assertLess(d['test_skill_vs_persistence'],1)
    def test_modify_only_final_period_does_not_choose_a_different_model(self):
        first=analyze(self.rows,60,self.at)
        rows=copy.deepcopy(self.rows)
        for i in range(395,480):rows[i]['water_level_source_units']+=(-1)**i*10
        second=analyze(rows,60,self.at)
        self.assertEqual(first['selected_model'],second['selected_model'])
        self.assertEqual(first['selection'],second['selection'])
        self.assertEqual(first['calibration'],second['calibration'])
        self.assertNotEqual(first['test'],second['test'])
    def test_future_targets_excluded_from_analysis(self):
        a=analyze(self.rows,60,self.at)
        b=analyze(self.rows+[point(9000,1e9)],60,self.at)
        self.assertEqual(a['test'],b['test']);self.assertEqual(a['input_sha256'],b['input_sha256'])
        self.assertIsNone(b['projection']) # Future clock anomaly is also a source review gate.
    def test_past_only_prediction_unchanged_by_later_values(self):
        pp=clean_points(self.rows)
        before=predict(pp,100,60,'damped_trend')
        pp[101][1]['water_level_source_units']=99999
        self.assertEqual(before,predict(pp,100,60,'damped_trend'))
    def test_nonoverlapping_test_windows(self):
        samples=analyze(self.rows,60,self.at)['samples']
        self.assertTrue(all(a['target_at']<=b['origin_at'] for a,b in zip(samples,samples[1:])))
    def test_insufficient_calibration_withholds_projection(self):
        d=analyze(self.rows[:50],60,BASE.timestamp()+49*900)
        self.assertIsNone(d['projection']);self.assertIn('12 selection',d['reason'])
    def test_stale_and_expired_target_withholds_projection(self):
        d=analyze(self.rows,60,self.at+10800)
        self.assertEqual(d['status'],'withheld');self.assertIn('past',d['reason'])
    def test_conflicting_source_records_withhold_projection(self):
        d=analyze(self.rows+[point(479*15,900)],60,self.at)
        self.assertEqual(d['quality']['conflicting_times'],1);self.assertIsNone(d['projection'])
    def test_zero_not_invalid_and_null_is_invalid(self):
        q=station_quality([point(0,0),point(15,None)],BASE.timestamp()+900)
        self.assertEqual(q['usable_points'],1);self.assertEqual(q['invalid_rows'],1)
    def test_invalid_horizon(self):
        with self.assertRaises(ValueError):analyze(self.rows,999,self.at)

class WeatherTests(unittest.TestCase):
    def setUp(self):self.payload=weather_payload();self.place=PLACES[0]
    def test_precipitation_sums_only_complete_future_hours(self):
        normalized=normalize(self.payload,self.place)
        # 00:30 -> sum hours ending 02:00 to 01:00 tomorrow, excluding partial 00:00–01:00.
        normalized['points'][1]['precipitation']=999
        result=summarize(normalized,BASE.isoformat(),BASE.timestamp()+1800)
        self.assertEqual(result['windows']['24']['precipitation_mm'],24)
        self.assertEqual(result['windows']['24']['start_at'],'2026-09-01T01:00:00+00:00')
    def test_nulls_do_not_become_zero_or_partial_totals(self):
        self.payload['hourly']['precipitation'][3]=None
        r=summarize(normalize(self.payload,self.place),BASE.isoformat(),BASE.timestamp())
        self.assertIsNone(r['windows']['24']['precipitation_mm']);self.assertEqual(r['windows']['24']['valid_precipitation_hours'],23)
    def test_zero_is_preserved(self):
        self.payload['hourly']['precipitation']=[0]*96
        r=summarize(normalize(self.payload,self.place),BASE.isoformat(),BASE.timestamp())
        self.assertEqual(r['windows']['24']['precipitation_mm'],0)
    def test_stale_snapshot_withholds_summary(self):
        r=summarize(normalize(self.payload,self.place),BASE.isoformat(),BASE.timestamp()+7*3600)
        self.assertEqual(r['state'],'stale');self.assertIsNone(r['windows']['24']['precipitation_mm'])
    def test_rejects_units_mismatch(self):
        self.payload['hourly_units']['precipitation']='inch'
        with self.assertRaises(ValueError):normalize(self.payload,self.place)
    def test_rejects_wrong_location(self):
        self.payload['latitude']=51
        with self.assertRaises(ValueError):normalize(self.payload,self.place)
    def test_rejects_duplicate_timestamp(self):
        self.payload['hourly']['time'][3]=self.payload['hourly']['time'][2]
        with self.assertRaises(ValueError):normalize(self.payload,self.place)
    def test_rejects_length_mismatch(self):
        self.payload['hourly']['precipitation'].pop()
        with self.assertRaises(ValueError):normalize(self.payload,self.place)
    def test_rejects_negative_or_nonfinite_precipitation(self):
        for v in (-2,float('nan'),True):
            self.payload['hourly']['precipitation'][0]=v
            with self.assertRaises(ValueError):normalize(self.payload,self.place)
    def test_issuance_is_unknown_not_manufactured(self):
        self.assertIsNone(normalize(self.payload,self.place)['model_issued_at'])

class ArchiveAndLedgerTests(unittest.TestCase):
    def test_refresh_batch_records_eligible_horizons_without_opening_ui(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=ForecastStore(tmp);dataset=Dataset();dataset.ensure=lambda:dataset
            dataset.river_groups={'1':linear_series()};at=BASE.timestamp()+479*900
            with patch('weather.time.time',return_value=at):
                result=record_predictions(dataset,store,(30,60))
            self.assertEqual(result['eligible_saved_or_already_present'],2)
            self.assertEqual(len(store.ledger()['rows']),2)
    def test_as_known_revisions_and_reversion_use_historical_change_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)/'disaster_archive/data';directory.mkdir(parents=True)
            db=sqlite3.connect(directory/'archive.sqlite')
            db.executescript('CREATE TABLE changes(id INTEGER,collection TEXT,native_id TEXT,version_id INTEGER,observed_at TEXT); CREATE TABLE record_versions(id INTEGER,payload TEXT);')
            for version,level in ((1,3),(2,30)):
                db.execute('INSERT INTO record_versions VALUES (?,?)',(version,json.dumps({'station':1,'waterLevel':level,'waterLevelOn':point(0,0)['observed_at']})))
            for index,minutes,version in ((1,30,1),(2,90,2),(3,150,1)):
                db.execute('INSERT INTO changes VALUES (?,?,?,?,?)',(index,'bipad:river','100',version,point(minutes,0)['observed_at']))
            db.commit();db.close();d=Dataset(tmp)
            self.assertEqual(d.as_known_river('1',point(20,0)['observed_at']),[])
            for cutoff,expected in ((60,3),(120,30),(180,3)):
                self.assertEqual(d.as_known_river('1',point(cutoff,0)['observed_at'])[0]['water_level_source_units'],expected)
    def test_prediction_ledger_is_immutable_and_matches_only_after_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=ForecastStore(tmp);rows=linear_series();at=BASE.timestamp()+479*900
            d=analyze(rows,60,at);key=store.save_river('1',d,at)
            modified=copy.deepcopy(d);modified['projection']['level']=999
            self.assertEqual(store.save_river('1',modified,at),key)
            dataset=Dataset();dataset.ensure=lambda:dataset;dataset.river_groups={'1':rows+[point(483*15,10+483*.25)]}
            pending=store.ledger(dataset,at+1800)['rows'][0]
            self.assertEqual(pending['verification']['state'],'pending')
            self.assertNotEqual(pending['projection']['level'],999)
            verified=store.ledger(dataset,at+3600)['rows'][0]
            self.assertEqual(verified['verification']['state'],'matched')
            self.assertAlmostEqual(verified['verification']['actual'],130.75)
    def test_target_expires_between_computation_and_save(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=ForecastStore(tmp);at=BASE.timestamp()+479*900
            d=analyze(linear_series(),60,at)
            self.assertIsNone(store.save_river('1',d,at+3601))
            self.assertEqual(store.ledger()['rows'],[])
    def test_failed_refresh_does_not_replace_success_or_hide_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=ForecastStore(tmp)
            class Response: returncode=0;stdout=json.dumps(weather_payload()).encode();stderr=b''
            with patch('weather.subprocess.run',return_value=Response()):store.fetch(PLACES[0],'ecmwf_ifs025',True)
            with patch('weather.subprocess.run',side_effect=OSError('offline')):store.fetch(PLACES[0],'ecmwf_ifs025',True)
            s=store.outlook()['places'][0]['sources'][0]
            self.assertEqual(s['latest_attempt']['status'],'error');self.assertTrue(s['sha256']);self.assertTrue(s['points'] or s['windows'])
            self.assertEqual(len(list(store.raw.glob('*.json'))),1)

if __name__=='__main__':unittest.main()
