import copy
import datetime as dt
import gzip
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import collector
import data_branch as branch
import history
import pipeline as p
import sources

AT=dt.datetime(2026,11,4,12,tzinfo=dt.timezone.utc).timestamp()

def flood_fixture():
    point=sources.FLOOD_POINTS[0];start=int(AT//86400)*86400
    return {'latitude':point['latitude'],'longitude':point['longitude'],'utc_offset_seconds':0,
            'daily_units':{'time':'unixtime',**{k:'m³/s' for k in sources.DISCHARGE_FIELDS}},
            'daily':{'time':[start+i*86400 for i in range(7)],
                     'river_discharge_mean':[3]*7,'river_discharge_p25':[1]*7,'river_discharge_p75':[4]*7}}

def quake_fixture():
    return {'type':'FeatureCollection','metadata':{'generated':AT*1000,'status':200,'count':1},
            'features':[{'id':'test-earthquake','geometry':{'type':'Point','coordinates':[85,28,10]},
                         'properties':{'type':'earthquake','time':(AT-3600)*1000,'updated':(AT-1800)*1000,
                                       'mag':4.1,'magType':'mb','status':'reviewed'}}]}

class SourceContracts(unittest.TestCase):
    def test_discharge_null_stays_missing(self):
        raw=flood_fixture();raw['daily']['river_discharge_mean'][2]=None
        n=sources.normalize_flood(raw,sources.FLOOD_POINTS[0],AT)
        self.assertIsNone(n['days'][2]['river_discharge_mean']);self.assertFalse(n['reach_verified']);self.assertIsNone(n['model_issued_at'])
    def test_discharge_wrong_units_rejected(self):
        raw=flood_fixture();raw['daily_units']['river_discharge_mean']='m'
        with self.assertRaises(ValueError):sources.normalize_flood(raw,sources.FLOOD_POINTS[0],AT)
    def test_discharge_wrong_grid_rejected(self):
        raw=flood_fixture();raw['longitude']+=1
        with self.assertRaises(ValueError):sources.normalize_flood(raw,sources.FLOOD_POINTS[0],AT)
    def test_discharge_inverted_percentiles_rejected(self):
        raw=flood_fixture();raw['daily']['river_discharge_p25'][0]=20
        with self.assertRaises(ValueError):sources.normalize_flood(raw,sources.FLOOD_POINTS[0],AT)
    def test_stale_or_irregular_model_dates_rejected(self):
        for mutate in (lambda t:[x-3*86400 for x in t],lambda t:t[:3]+[t[2]]+t[4:]):
            raw=flood_fixture();raw['daily']['time']=mutate(raw['daily']['time'])
            with self.assertRaises(ValueError):sources.normalize_flood(raw,sources.FLOOD_POINTS[0],AT)
    def test_usgs_scope_and_null_magnitude(self):
        raw=quake_fixture();raw['features'][0]['properties']['mag']=None
        n=sources.normalize_quakes(raw,AT);self.assertEqual(len(n['events']),1);self.assertIsNone(n['events'][0]['magnitude'])
        raw['features'][0]['geometry']['coordinates'][0]=100
        self.assertEqual(sources.normalize_quakes(raw,AT)['events'],[])
    def test_empty_feed_is_valid_but_count_mismatch_is_not(self):
        raw=quake_fixture();raw['features']=[];raw['metadata']['count']=0
        self.assertEqual(sources.normalize_quakes(raw,AT)['events'],[])
        raw['metadata']['count']=1
        with self.assertRaises(ValueError):sources.normalize_quakes(raw,AT)
    def test_usgs_future_and_stale_feed_rejected(self):
        for offset in (86400,-2*86400):
            raw=quake_fixture();raw['metadata']['generated']=(AT+offset)*1000
            with self.assertRaises(ValueError):sources.normalize_quakes(raw,AT)
    def test_usgs_duplicate_ids_rejected(self):
        raw=quake_fixture();raw['features']*=2;raw['metadata']['count']=2
        with self.assertRaises(ValueError):sources.normalize_quakes(raw,AT)
    def test_transient_retry_only(self):
        a=MagicMock();a.fetch.side_effect=[RuntimeError('HTTP 503'),(b'{}',1,'time')]
        a.db.execute.return_value.fetchone.return_value=(503,)
        with patch.object(sources.time,'sleep'):
            self.assertEqual(sources.fetch_json(a,'usgs',sources.USGS_URL)[0],{})
        self.assertEqual(a.fetch.call_count,2)
        a=MagicMock();a.fetch.side_effect=RuntimeError('HTTP 403');a.db.execute.return_value.fetchone.return_value=(403,)
        with self.assertRaises(RuntimeError):sources.fetch_json(a,'usgs',sources.USGS_URL)
        self.assertEqual(a.fetch.call_count,1)
    def test_refresh_cadence_is_per_source(self):
        item={'fetched_at':sources.iso(AT-3700)}
        self.assertTrue(collector.due(item,3600,AT));self.assertFalse(collector.due(item,21600,AT))
        self.assertTrue(collector.due({'fetched_at':sources.iso(AT+60)},3600,AT))
    def test_weather_failed_http_body_is_preserved(self):
        from types import SimpleNamespace
        import hashlib
        body=b'{"error":true,"reason":"rate limited"}'
        with tempfile.TemporaryDirectory() as temp:
            store=p.ForecastStore(temp)
            with patch('weather.subprocess.run',return_value=SimpleNamespace(returncode=22,stdout=body,stderr=b'HTTP 429')):
                result=store.fetch(p.PLACES[0],next(iter(p.MODELS)),force=True)
            self.assertEqual(result['status'],'error')
            self.assertEqual((store.raw/(hashlib.sha256(body).hexdigest()+'.json')).read_bytes(),body)
            with store.db() as db:
                self.assertIsNone(db.execute('SELECT normalized FROM weather_fetches').fetchone()[0])
            db.close()
    def test_malformed_provider_containers_fail_as_schema_errors(self):
        raw=quake_fixture();raw['metadata']=None
        with self.assertRaises(ValueError):sources.normalize_quakes(raw,AT)
        raw=flood_fixture();raw['daily']=None
        with self.assertRaises(ValueError):sources.normalize_flood(raw,sources.FLOOD_POINTS[0],AT)
    def test_v2_public_contract_revalidates_models(self):
        s=json.loads(p.SEED.read_text());s['schema_version']=2
        s['earthquakes']={'fetched_at':sources.iso(AT),'sha256':'a'*64,'url':sources.USGS_URL,'normalized':sources.normalize_quakes(quake_fixture(),AT)}
        s['discharge']=[{'fetched_at':sources.iso(AT),'sha256':'b'*64,'url':sources.flood_url(sources.FLOOD_POINTS[0]),'normalized':sources.normalize_flood(flood_fixture(),sources.FLOOD_POINTS[0],AT)}]
        s['pipeline']={'schedule_minutes':30,'history_started_at':sources.iso(AT),'history_runs':1,'revisions':0,'catchup_gaps':[],
                       'quality':{'river_recent':0,'river_total':205,'rain_recent':0,'rain_total':397,'warnings':[]},'history_branch':branch.BRANCH,'previous_revision':None}
        p.validate(s)
        s['discharge'][0]['normalized']['reach_verified']=True
        with self.assertRaises(ValueError):p.validate(s)

class HistoryContracts(unittest.TestCase):
    def test_revisions_and_nulls_retained_without_overlap_duplicates(self):
        state=history.fresh_state();row={'source':'bipad:river','id':'1','observed_at':sources.iso(AT),'values':{'level':None}}
        self.assertEqual(len(history.record_versions(state,[(row,{})],sources.iso(AT))),1)
        self.assertEqual(history.record_versions(state,[(row,{})],sources.iso(AT)),[])
        row['values']['level']=0
        revisions=history.record_versions(state,[(row,{})],sources.iso(AT+1800))
        self.assertEqual(len(revisions),1);self.assertIsNotNone(revisions[0]['previous_sha256']);self.assertEqual(state['revisions'],1)
        self.assertEqual(revisions[0]['record']['values']['level'],0)
    def test_adaptive_catchup_and_explicit_gap(self):
        state=history.fresh_state();state['watermarks']['river']=sources.iso(AT-2*86400)
        start,end=history.query_window(state,'river',sources.iso(AT))
        self.assertEqual(p.timestamp(start),AT-2*86400-3*3600);self.assertEqual(state['gaps'],[])
        state['watermarks']['river']=sources.iso(AT-10*86400)
        start,_=history.query_window(state,'river',sources.iso(AT));self.assertEqual(p.timestamp(start),AT-7*86400);self.assertEqual(len(state['gaps']),1)
    def test_future_watermark_rejected(self):
        state=history.fresh_state();state['watermarks']['river']=sources.iso(AT+86400)
        with self.assertRaises(ValueError):history.query_window(state,'river',sources.iso(AT))
    def test_partial_traversal_does_not_advance_watermarks(self):
        from archive import Archive
        with tempfile.TemporaryDirectory() as temp:
            a=Archive(temp);a.start('test');state=history.fresh_state();snapshot={'updates':{},'rivers':[],'rain_stations':[]}
            def fake(feed,params,max_pages,window):
                job=a.collection_start('bipad:'+feed,*window);a.collection_finish(job,1,5,5,0,'partial','page cap');return 'partial'
            with patch.object(a,'bipad',side_effect=fake):collector.collect_hydrology(a,snapshot,state,sources.iso(AT))
            self.assertEqual(state['watermarks'],{});self.assertEqual(snapshot['updates']['river']['state'],'partial');a.db.close()
    def test_valid_traversal_advances_query_watermark_even_if_no_observations(self):
        from archive import Archive
        with tempfile.TemporaryDirectory() as temp:
            a=Archive(temp);a.start('test');state=history.fresh_state();snapshot={'updates':{},'rivers':[],'rain_stations':[]}
            def fake(feed,params,max_pages,window):
                job=a.collection_start('bipad:'+feed,*window);a.collection_finish(job,1,0,0,0,'traversed','empty');return 'traversed'
            with patch.object(a,'bipad',side_effect=fake):collector.collect_hydrology(a,snapshot,state,sources.iso(AT))
            self.assertEqual(state['watermarks']['river'],sources.iso(AT));self.assertEqual(snapshot['rivers'],[]);a.db.close()
    def test_raw_source_rollback_to_previous_version_is_retained(self):
        from archive import Archive,canonical
        with tempfile.TemporaryDirectory() as temp:
            a=Archive(temp);a.start('one')
            def ingest(level):
                fid=a.db.execute('INSERT INTO fetches(run_id,source,url,fetched_at,sha256) VALUES (?,?,?,?,?)',(a.run_id,'bipad','https://bipadportal.gov.np/api/v1/river/',sources.iso(AT),'a'*64)).lastrowid
                a.ingest('bipad:river',[{'id':1,'station':2,'waterLevelOn':sources.iso(AT),'waterLevel':level}],fid,sources.iso(AT))
            ingest(2);state=history.fresh_state();history.record_versions(state,history.observation_versions(a.db,a.run_id),sources.iso(AT))
            a.start('two');ingest(3);history.record_versions(state,history.observation_versions(a.db,a.run_id),sources.iso(AT))
            a.start('three');ingest(2);changes=history.record_versions(state,history.observation_versions(a.db,a.run_id),sources.iso(AT))
            self.assertEqual(changes[0]['record']['values']['level'],2);self.assertEqual(state['revisions'],2);a.db.close()
    def test_history_hash_and_private_paths_rejected(self):
        with self.assertRaises(ValueError):branch.verify_file('history/2026-11-04/'+'a'*64+'.json.gz',gzip.compress(b'{}'))
        self.assertFalse(branch.allowed('data/archive.sqlite'));self.assertFalse(branch.allowed('../../secret.json'));self.assertFalse(branch.allowed('history/../../latest.json'))
    def test_history_publication_rejects_unapproved_record_fields(self):
        row={'source':'bipad:river','id':'1','station_id':'2','observed_at':sources.iso(AT),'units':'unconfirmed source units','values':{'level':1},'private_note':'must not publish'}
        body={'schema_version':1,'recorded_at':sources.iso(AT),'snapshot':json.loads(p.SEED.read_text()),
              'observation_changes':[{'record':row,'sha256':history.digest(row),'previous_sha256':None,'provenance':{}}],'fetches':[]}
        name='history/2026-11-04/'+history.digest(body)+'.json.gz'
        with self.assertRaises(ValueError):branch.verify_file(name,gzip.compress(history.canonical(body),mtime=0))
    def test_failed_new_sources_preserve_original_values_and_times(self):
        old={'fetched_at':sources.iso(AT-86400),'sha256':'a'*64,'url':sources.USGS_URL,'normalized':sources.normalize_quakes(quake_fixture(),AT)}
        snapshot={'earthquakes':copy.deepcopy(old),'discharge':[],'updates':{}}
        with patch.object(sources,'fetch_json',side_effect=RuntimeError('HTTP 503')):
            collector.collect_extra(MagicMock(),snapshot,AT)
        self.assertEqual(snapshot['earthquakes'],old);self.assertEqual(snapshot['updates']['earthquakes']['state'],'failed');self.assertEqual(snapshot['discharge'],[])

class DataBranchIntegration(unittest.TestCase):
    def test_roundtrip_append_only_and_competing_writer(self):
        original=Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);remote=root/'remote.git'
            subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
            repos=[]
            for name in ('one','two'):
                repo=root/name;subprocess.run(['git','clone',str(remote),str(repo)],check=True,capture_output=True);repos.append(repo)
            try:
                os.chdir(repos[0]);state_root=repos[0]/'state';branch.restore(state_root)
                s=json.loads(p.SEED.read_text());state=history.fresh_state();history.save_run(state_root,state,s,[],[])
                first=branch.save(state_root)
                os.chdir(repos[1]);other=repos[1]/'state';branch.restore(other)
                self.assertEqual(history.load_state(other)['runs'],1)
                self.assertEqual(json.loads((other/'latest.json').read_text()),s)
                os.chdir(repos[0]);s['built_at']=sources.iso(AT);history.save_run(state_root,state,s,[],[]);second=branch.save(state_root)
                self.assertNotEqual(first,second);self.assertEqual(sum(n.startswith('history/') for n in branch.tree(second)),2)
                # A writer based on the old revision must not erase the first writer's history.
                os.chdir(repos[1]);other_state=history.load_state(other);s['built_at']=sources.iso(AT+60);history.save_run(other,other_state,s,[],[])
                with self.assertRaises(RuntimeError):branch.save(other)
                # Budget exhaustion fails before a push and preserves existing history.
                os.chdir(repos[0])
                with patch.object(branch,'MAX_BYTES',1):
                    with self.assertRaises(ValueError):branch.save(state_root)
            finally:os.chdir(original)

if __name__=='__main__':unittest.main()
