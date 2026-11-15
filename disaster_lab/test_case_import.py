import copy
import json
from pathlib import Path
import tempfile
import unittest
from cases import CaseStore,epoch
from case_import import import_weather

class CaseImportTests(unittest.TestCase):
    def test_real_schema_import_is_unverified_forecast_not_incident(self):
        s=json.loads((Path(__file__).parents[1]/'public_site/snapshot.json').read_text())
        at=epoch(s['built_at']);before=copy.deepcopy(s)
        with tempfile.TemporaryDirectory() as tmp:
            store=CaseStore(tmp,clock=lambda:at)
            r=import_weather(s,store,at)
            self.assertEqual(len(r['case_ids']),7)
            self.assertEqual(import_weather(s,store,at),r)
            self.assertEqual(store.verify()['events'],7)
            d=store.replay(r['case_ids'][0],s['built_at'])['latest_revision']['payload']
            self.assertEqual(d['hazard'],'weather')
            self.assertEqual(d['geography']['review']['status'],'unverified')
            self.assertTrue(all(e['kind']=='provider_forecast' for e in d['evidence']))
            self.assertEqual(s,before)

    def test_no_source_means_no_invented_case(self):
        s=json.loads((Path(__file__).parents[1]/'public_site/snapshot.json').read_text());s['weather']=[]
        with tempfile.TemporaryDirectory() as tmp:
            store=CaseStore(tmp,clock=lambda:epoch(s['built_at']))
            self.assertEqual(import_weather(s,store)['case_ids'],[])

if __name__=='__main__':unittest.main()
