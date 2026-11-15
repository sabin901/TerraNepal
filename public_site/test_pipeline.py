import copy
from contextlib import closing
import datetime as dt
import sqlite3
import time
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
    def quarantined_snapshot(self):
        s=copy.deepcopy(self.seed)
        n=s['weather'][0]['normalized'];point=n['points'][17]
        point['precipitation']=None
        n['quality']=[{'variable':'precipitation','index':17,'at':point['at'],
                       'value':-0.1,'reason':'outside_physical_bounds'}]
        return s

    def test_quarantine_receipt_replays_and_preserves_source_missingness(self):
        s=self.quarantined_snapshot()
        n=s['weather'][0]['normalized'];n['points'][18]['precipitation']=None
        checked=p.validate(s)['weather'][0]['normalized']
        self.assertIsNone(checked['points'][17]['precipitation'])
        self.assertIsNone(checked['points'][18]['precipitation'])
        self.assertEqual(len(checked['quality']),1)
        self.assertIsNotNone(checked['points'][17]['temperature_2m'])
        self.assertEqual(checked['quality'][0]['value'],-0.1)

    def test_quarantine_rejects_forged_or_ambiguous_receipts(self):
        mutations=[
            lambda n:n['quality'].append(copy.deepcopy(n['quality'][0])),
            lambda n:n['quality'][0].update(index=True),
            lambda n:n['quality'][0].update(index=-1),
            lambda n:n['quality'][0].update(index=999),
            lambda n:n['quality'][0].update(at=n['points'][18]['at']),
            lambda n:n['quality'][0].update(variable='time'),
            lambda n:n['quality'][0].update(value=0),
            lambda n:n['quality'][0].update(value=True),
            lambda n:n['quality'][0].update(value=float('nan')),
            lambda n:n['quality'][0].update(reason='source_missing'),
            lambda n:n['quality'][0].update(extra='unreviewed'),
            lambda n:n['points'][17].update(precipitation=0),
            lambda n:n.update(quality=[]),
            lambda n:n.update(quality=None),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                s=self.quarantined_snapshot();mutate(s['weather'][0]['normalized'])
                with self.assertRaises(ValueError):p.validate(s)

    def test_raw_weather_rows_replay_quarantine_and_detect_tampering(self):
        import hashlib
        s=self.quarantined_snapshot();w=s['weather'][0];n=w['normalized']
        payload={'latitude':n['grid_latitude'],'longitude':n['grid_longitude'],
                 'elevation':n['elevation'],'utc_offset_seconds':0,'hourly_units':n['units'],
                 'hourly':{'time':[x['epoch'] for x in n['points']],
                           **{k:[x[k] for x in n['points']] for k in p.PLAUSIBILITY_LIMITS}}}
        payload['hourly']['precipitation'][17]=-0.1
        raw=json.dumps(payload).encode();sha=hashlib.sha256(raw).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            store=p.ForecastStore(tmp);(store.raw/(sha+'.json')).write_bytes(raw)
            with closing(store.db()) as db,db:
                db.execute('INSERT INTO weather_fetches(place_id,model,fetched_at,status,sha256,raw_file,normalized) VALUES (?,?,?,?,?,?,?)',
                           (w['place_id'],w['model'],w['fetched_at'],'ok',sha,sha+'.json',json.dumps(n)))
            rows=p.weather_rows(store)
            self.assertEqual(rows[0]['normalized'],n)
            self.assertEqual((store.raw/(sha+'.json')).read_bytes(),raw)
            with closing(store.db()) as db,db:
                wrong=copy.deepcopy(n);wrong['quality'][0]['value']=-0.2
                db.execute('UPDATE weather_fetches SET normalized=?',(json.dumps(wrong),))
            with self.assertRaisesRegex(ValueError,'integrity'):p.weather_rows(store)

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
            self.assertEqual(files,set(p.ASSETS)|{'data/snapshot.json','data/situation-brief.json','situation-brief.md','.nojekyll'})
            with self.assertRaises(ValueError):p.build(p.SEED,d)
    def test_build_rejects_future_health_but_allows_stale_partial_seed(self):
        s=copy.deepcopy(self.seed)
        s['rivers'][0]['observed_at']=dt.datetime.fromtimestamp(time.time()+3600,dt.timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'snapshot.json';source.write_text(json.dumps(s));out=Path(d)/'site'
            with self.assertRaisesRegex(ValueError,'Invalid publication health'):p.build(source,out)
            self.assertFalse(out.exists())
            p.build(p.SEED,out)
            self.assertTrue((out/'data/snapshot.json').exists())

    def test_future_station_rows_quarantined_at_shared_boundary(self):
        with closing(sqlite3.connect(':memory:')) as db:
            db.row_factory=sqlite3.Row
            db.execute('CREATE TABLE river_observations(station_id, station_name, basin, observed_at, water_level_source_units, latitude, longitude)')
            db.execute('CREATE TABLE current_payloads(collection,payload)')
            at=1800000000
            for i,offset in enumerate((300,301)):
                stamp=dt.datetime.fromtimestamp(at+offset,dt.timezone.utc).isoformat()
                db.execute('INSERT INTO river_observations VALUES(?,?,?,?,?,?,?)',(i,'station','basin',stamp,0,28,85))
                db.execute('INSERT INTO current_payloads VALUES(?,?)',('bipad:rain',json.dumps(dict(station=i,title='station',measuredOn=stamp))))
            quarantine=[];rivers,rain=p.station_rows(db,at,quarantine)
            self.assertEqual([r['id'] for r in rivers],['0']);self.assertEqual([r['id'] for r in rain],['0'])
            self.assertEqual(rivers[0]['level'],0)
            self.assertEqual({r['source'] for r in quarantine},{'river','rain'})
            self.assertTrue(all(r['station_id']=='1' for r in quarantine))

    def test_repeat_same_time_correction_does_not_invent_resolution(self):
        r=copy.deepcopy(self.seed['rivers'][0]);r['level']=1
        correction={**r,'level':2}
        first=p.merge_stations([r],[correction])
        self.assertEqual(p.merge_stations(first,[correction]),first)
        self.assertTrue(first[0]['conflicting'])

    def test_download_failure_falls_back_to_dated_seed(self):
        with patch.object(p.subprocess,'run',side_effect=OSError('offline')):
            self.assertEqual(p.previous_snapshot()['built_at'],self.seed['built_at'])
    def test_duplicate_station_rejected(self):
        s=copy.deepcopy(self.seed);s['rivers'].append(s['rivers'][0])
        with self.assertRaises(ValueError):p.validate(s)

if __name__=='__main__':unittest.main()
