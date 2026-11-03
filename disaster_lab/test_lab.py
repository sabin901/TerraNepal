import contextlib
import datetime as dt
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from data import timestamp, freshness, replay, evaluate, alert_validity, clean_points, Dataset
from server import State, make_server

BASE=dt.datetime(2026,9,1,tzinfo=dt.timezone.utc)
def point(minutes,level,seen=None):
    return {'observed_at':(BASE+dt.timedelta(minutes=minutes)).isoformat(),
            'water_level_source_units':level,'first_seen_at':(BASE+dt.timedelta(minutes=minutes if seen is None else seen)).isoformat()}

class ScientificBehaviorTests(unittest.TestCase):
    def test_replay_does_not_use_future_observations(self):
        r=replay([point(0,1),point(60,2),point(120,999)],point(60,0)['observed_at'])
        self.assertEqual(r['prediction'],2);self.assertEqual(r['input_points'],2)
    def test_zero_is_a_valid_measurement(self):
        self.assertEqual(replay([point(0,0)],point(0,0)['observed_at'])['prediction'],0)
    def test_null_is_not_zero(self):
        self.assertIsNone(replay([point(0,None)],point(0,0)['observed_at'])['prediction'])
    def test_as_known_replay_rejects_late_archive_inputs(self):
        rr=[point(0,3,180),point(60,4,180)]
        self.assertEqual(replay(rr,point(60,0)['observed_at'],known_only=True)['status'],'no_input')
    def test_as_known_accepts_available_inputs_only(self):
        rr=[point(0,3,30),point(60,4,180)]
        self.assertEqual(replay(rr,point(60,0)['observed_at'],known_only=True)['prediction'],3)
    def test_stale_input_withholds_baseline(self):
        self.assertEqual(replay([point(0,3)],point(181,0)['observed_at'])['status'],'stale_input')
    def test_timezone_offsets_are_equivalent(self):
        self.assertEqual(timestamp('2026-09-01T05:45:00+05:45'),timestamp('2026-09-01T00:00:00Z'))
    def test_naive_cutoff_rejected(self):
        with self.assertRaises(ValueError):replay([point(0,3)],'2026-09-01T00:00:00')
    def test_evaluation_known_errors(self):
        r=evaluate([point(0,1),point(60,2),point(120,3)],60)
        self.assertEqual(r['pairs'],2);self.assertEqual(r['mae'],1)
    def test_evaluation_does_not_substitute_far_future_target(self):
        r=evaluate([point(0,1),point(180,2),point(360,3)],60)
        self.assertEqual(r['pairs'],0);self.assertIsNone(r['mae'])
    def test_duplicate_times_not_independent_pairs(self):
        self.assertEqual(len(clean_points([point(0,1),point(0,2)])),1)
    def test_missing_expiry_is_not_active(self):
        self.assertEqual(alert_validity({'starts_at':point(0,0)['observed_at'],'source_verified':True},BASE.timestamp()+100),'validity_unknown')
    def test_expiry_boundary_is_expired(self):
        a={'starts_at':point(0,0)['observed_at'],'expires_at':point(60,0)['observed_at'],'source_verified':True}
        self.assertEqual(alert_validity(a,BASE.timestamp()+3600),'expired')
        self.assertEqual(alert_validity(a,BASE.timestamp()+60),'within_source_window')
    def test_unverified_message_cannot_appear_source_valid(self):
        a={'starts_at':point(0,0)['observed_at'],'expires_at':point(60,0)['observed_at'],'source_verified':False}
        self.assertEqual(alert_validity(a,BASE.timestamp()+60),'source_unverified')
    def test_freshness_unknown_and_future_not_safe(self):
        self.assertEqual(freshness(None)['state'],'unknown')
        self.assertEqual(freshness(point(60,0)['observed_at'],BASE.timestamp())['state'],'future_timestamp')
    def test_multidistrict_report_once_in_total_excluded_from_ranking(self):
        d=Dataset();d.ensure=lambda: d
        d.incidents=[{'incident_id':'1','local_event_date':'2026-01-01','hazard':'Flood','districts':['A','B']},
                     {'incident_id':'2','local_event_date':'2026-01-01','hazard':'Flood','districts':['A']}]
        r=d.incident_query('Flood')
        self.assertEqual(r['total'],2);self.assertEqual(r['districts'],[{'district':'A','reports':1}])
        self.assertEqual(r['unallocated_district_reports'],1)
        self.assertEqual(d.incident_query('Flood','A')['total'],2)

class LocalStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=State(self.tmp.name)
        self.item={'title':'Check a datum','kind':'research','status':'open','place':'Station','notes':'','evidence_url':''}
    def tearDown(self):self.tmp.cleanup()
    def test_actions_start_empty(self):self.assertEqual(self.s.list(),[])
    def test_edit_retains_history(self):
        r=self.s.save(self.item);self.s.save({**r,'status':'completed'})
        self.assertEqual(len(self.s.list()),1)
        with contextlib.closing(self.s.db()) as c:self.assertEqual(c.execute('SELECT count(*) FROM action_history').fetchone()[0],2)
    def test_javascript_evidence_url_rejected(self):
        with self.assertRaises(ValueError):self.s.save({**self.item,'evidence_url':'javascript:alert(1)'})
    def test_invalid_status_rejected(self):
        with self.assertRaises(ValueError):self.s.save({**self.item,'status':'verified_by_government'})

class LocalHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.server=make_server(0,state_root=Path(self.tmp.name))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,path,method='GET',body=None,headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        c.request(method,path,body=json.dumps(body) if body is not None else None,headers=headers or {})
        r=c.getresponse();data=r.read();c.close();return r.status,json.loads(data)
    def test_unknown_route_rejected(self):self.assertEqual(self.request('/../data/archive.sqlite')[0],404)
    def test_host_rebinding_rejected(self):self.assertEqual(self.request('/api/session',headers={'Host':'evil.example'})[0],403)
    def test_write_requires_session_token(self):self.assertEqual(self.request('/api/actions','POST',{})[0],403)
    def test_cross_origin_write_rejected(self):
        token=self.request('/api/session')[1]['token']
        self.assertEqual(self.request('/api/actions','POST',{}, {'X-Lab-Token':token,'Origin':'https://evil.example'})[0],403)
    def test_local_action_roundtrip(self):
        token=self.request('/api/session')[1]['token']
        status,r=self.request('/api/actions','POST',{'title':'Test only','kind':'research','status':'open'}, {'X-Lab-Token':token})
        self.assertEqual(status,201);self.assertEqual(len(self.request('/api/actions')[1]),1)

if __name__=='__main__':unittest.main()
