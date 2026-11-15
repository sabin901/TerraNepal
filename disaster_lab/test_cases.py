import copy
import datetime as dt
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from cases import CaseStore, epoch

BASE='2026-11-15T12:00:00+00:00'
def unverified():return {'status':'unverified','reviewer':None,'reviewed_at':None,'reason':'Not yet reviewed'}
def reference():return {'kind':'observation','source':'Synthetic test source','source_url':'https://example.org/observations','sha256':'a'*64,'acquired_at':BASE,'valid_from':BASE,'valid_to':BASE,'review':unverified()}
def doc():return {'title':'Synthetic test case','hazard':'flood','geography':{'type':'point','coordinates':[85,27],'label':'Synthetic site','review':unverified()},'valid_from':BASE,'valid_to':BASE,'summary':'Synthetic fixture, not a real incident','evidence':[reference()]}
def entry(revision):return {'revision_sha256':revision['sha256'],'text':'Synthetic test action','actor':'Test operator','occurred_at':BASE,'evidence':[],'review':unverified()}

class CasesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.now=epoch(BASE);self.store=CaseStore(self.tmp.name,clock=lambda:self.now)
    def later(self,seconds=60):self.now+=seconds;return dt.datetime.fromtimestamp(self.now,dt.timezone.utc).isoformat()
    def test_revision_is_immutable_idempotent_and_corrections_replay(self):
        original=doc();first=self.store.append_revision('case-1',original)
        self.assertEqual(original,doc())
        self.later();self.assertEqual(first,self.store.append_revision('case-1',doc()))
        changed=doc();changed['summary']='Later correction'
        second=self.store.append_revision('case-1',changed)
        self.assertNotEqual(first['sha256'],second['sha256'])
        self.assertEqual(second['previous_sha256'],first['sha256'])
        self.assertEqual(self.store.replay('case-1',BASE)['latest_revision'],first)
        self.assertEqual(len(self.store.replay('case-1',self.later())['events']),2)
        self.assertEqual(self.store.verify()['events'],2)
    def test_future_acquisition_and_observation_rejected_but_forecasts_allowed(self):
        d=doc();d['evidence'][0]['acquired_at']='2026-11-15T12:00:01Z'
        with self.assertRaisesRegex(ValueError,'Future acquisition'):self.store.append_revision('c',d)
        d=doc();d['evidence'][0]['valid_to']='2026-11-16T12:00:00Z'
        with self.assertRaisesRegex(ValueError,'future outcomes'):self.store.append_revision('c',d)
        d['evidence'][0]['kind']='provider_forecast';r=self.store.append_revision('c',d)
        self.assertEqual(r['payload']['evidence'][0]['kind'],'provider_forecast')
    def test_action_and_outcome_link_existing_case_revision(self):
        r=self.store.append_revision('c',doc());a=entry(r)
        with self.assertRaisesRegex(ValueError,'existing revision'):self.store.append_action('another',a)
        self.later();event=self.store.append_action('c',a)
        self.assertEqual(self.store.append_action('c',a),event)
        with self.assertRaisesRegex(ValueError,'requires evidence'):self.store.append_outcome('c',a)
        o=entry(r);o['text']='Synthetic outcome';o['evidence']=[reference()]
        self.later();self.store.append_outcome('c',o)
        self.assertEqual(len(self.store.replay('c',BASE)['events']),1)
        latest=self.store.list_cases()[0]
        self.assertEqual((latest['action_count'],latest['outcome_count']),(1,1))
    def test_clock_rollback_rejected(self):
        self.store.append_revision('c',doc());self.now-=1
        with self.assertRaisesRegex(ValueError,'backward'):self.store.append_revision('c',doc())
    def test_naive_clock_and_bad_evidence_rejected(self):
        for key,value in [('acquired_at','2026-11-15T12:00:00'),('sha256','garbage'),('source_url','https://example.org/?api_key=secret'),('kind',{})]:
            d=doc();d['evidence'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.store.append_revision('c',d)
        d=doc();d['evidence'].append(copy.deepcopy(d['evidence'][0]))
        with self.assertRaisesRegex(ValueError,'Duplicate'):self.store.append_revision('c',d)
    def test_review_is_explicit_and_confirmed_impact_needs_attribution(self):
        d=doc();d['evidence'][0]['kind']='confirmed_impact'
        with self.assertRaisesRegex(ValueError,'attributed review'):self.store.append_revision('c',d)
        d['evidence'][0]['review']={'status':'reviewed','reviewer':'Test reviewer','reviewed_at':BASE,'reason':'Synthetic review evidence'}
        r=self.store.append_revision('c',d)
        self.assertEqual(r['payload']['geography']['review']['status'],'unverified')
        self.assertIn('not independently authenticated',' '.join(self.store.replay('c',BASE)['limitations']))
    def test_geography_no_implicit_accuracy_or_invalid_bbox(self):
        for coords in [[True,27],[85,float('nan')],[181,27],[10**1000,27],[85,10**1000]]:
            d=doc();d['geography']['coordinates']=coords
            with self.assertRaises(ValueError):self.store.append_revision('c',d)
        d=doc();d['geography'].update(type='bbox',coordinates=[85,27,84,28])
        with self.assertRaisesRegex(ValueError,'bbox'):self.store.append_revision('c',d)
    def test_sql_triggers_protect_history_and_hash_detects_bypass(self):
        self.store.append_revision('c',doc())
        with self.store.db() as db:
            with self.assertRaises(sqlite3.IntegrityError):db.execute("UPDATE case_events SET payload='{}'")
            with self.assertRaises(sqlite3.IntegrityError):db.execute('DELETE FROM case_events')
            db.execute('DROP TRIGGER immutable_case_update')
            db.execute("UPDATE case_events SET payload='{}'")
        with self.assertRaisesRegex(ValueError,'integrity'):self.store.verify()
        with self.assertRaisesRegex(ValueError,'integrity'):self.store.replay('c',BASE)
    def test_new_instance_replays_persisted_history(self):
        r=self.store.append_revision('c',doc());other=CaseStore(self.tmp.name)
        self.assertEqual(other.replay('c',BASE)['latest_revision'],r)
        self.assertEqual(other.replay('c','2026-11-15T11:59:59Z')['events'],[])
        self.assertEqual(other.list_cases('2026-11-15T11:59:59Z'),[])
    def test_cli_refuses_existing_output(self):
        from cases import main
        target=Path(self.tmp.name)/'do-not-overwrite.json';target.write_text('original')
        with self.assertRaises(SystemExit):main(['--root',self.tmp.name,'verify','--output',str(target)])
        self.assertEqual(target.read_text(),'original')

if __name__=='__main__':unittest.main()
