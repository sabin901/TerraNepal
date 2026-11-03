import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from archive import Archive, ROOT, parse_time

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for file in ('config.json','schema.sql'):
            shutil.copy(ROOT/file,self.root/file)
        self.a = Archive(self.root)
        self.a.start('test')
        self.stamp = '2026-09-29T00:00:00+00:00'

    def tearDown(self):
        self.a.db.close()
        self.temp.cleanup()

    def fetch_row(self):
        c=self.a.db.execute('INSERT INTO fetches(run_id,source,url,fetched_at,http_status) VALUES (?,?,?,?,?)',
             (self.a.run_id,'test','https://example.org/data',self.stamp,200))
        self.a.db.commit()
        return c.lastrowid

    def put(self, item, collection='bipad:incident'):
        return self.a.ingest(collection,[item],self.fetch_row(),self.stamp)

    def test_live_does_not_advance_daily_catchup_watermark(self):
        self.a.set_meta('last_hydro_river','2026-09-01T00:00:00Z')
        with patch.object(self.a,'bipad',return_value='traversed') as fetch:
            self.assertEqual(self.a.live(),0)
        self.assertEqual(self.a.meta('last_hydro_river'),'2026-09-01T00:00:00Z')
        self.assertIsNotNone(self.a.meta('last_live_river'))
        self.assertEqual(fetch.call_args_list[0].kwargs['max_pages'],20)
        start,end=fetch.call_args_list[0].kwargs['window']
        self.assertEqual((parse_time(end)-parse_time(start)).total_seconds(),7200)
    def test_external_root_bootstraps_config_without_overwriting(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)/'external';a=Archive(root);a.db.close()
            self.assertTrue((root/'config.json').exists());original=(root/'config.json').read_text()
            (root/'config.json').write_text(original+'\n')
            a=Archive(root);a.db.close();self.assertEqual((root/'config.json').read_text(),original+'\n')
    def test_repeated_import_is_idempotent(self):
        self.assertEqual(self.put({'id':1,'title':'A'}),(1,0))
        self.assertEqual(self.put({'title':'A','id':1}),(0,0))
        self.assertEqual(self.a.db.execute('SELECT count(*) FROM changes').fetchone()[0],1)

    def test_naive_timestamps_are_rejected(self):
        self.assertIsNone(parse_time('2026-09-29T00:00:00'))
        self.assertEqual(parse_time('2026-09-29T05:45:00+05:45').isoformat(),'2026-09-29T00:00:00+00:00')

    def test_revision_and_reversion_preserve_observation_history(self):
        self.put({'id':1,'title':'A'})
        self.assertEqual(self.put({'id':1,'title':'B'}),(0,1))
        self.assertEqual(self.put({'id':1,'title':'A'}),(0,1))
        self.assertEqual(self.a.db.execute('SELECT count(*) FROM record_versions').fetchone()[0],2)
        self.assertEqual(self.a.db.execute('SELECT count(*) FROM changes').fetchone()[0],3)

    def test_same_id_in_different_sources_not_merged(self):
        self.put({'id':1},'bipad:incident')
        self.put({'id':1},'usgs:earthquake')
        self.assertEqual(self.a.db.execute('SELECT count(*) FROM records').fetchone()[0],2)

    def test_missing_loss_is_not_zero(self):
        self.put({'id':1,'loss':None})
        self.put({'id':2,'loss':{'peopleDeathCount':0}})
        rows=self.a.db.execute('SELECT incident_id,reported_deaths FROM incident_current ORDER BY incident_id').fetchall()
        self.assertIsNone(rows[0][1])
        self.assertEqual(rows[1][1],0)

    def test_multiple_wards_do_not_duplicate_incident_view(self):
        self.put({'id':1,'wards':[1,2]})
        self.assertEqual(self.a.db.execute('SELECT count(*) FROM incident_current').fetchone()[0],1)
        self.assertEqual(self.a.db.execute('SELECT count(*) FROM incident_places').fetchone()[0],2)

    def test_zero_rain_is_retained_and_missing_not_coerced(self):
        self.put({'id':2,'averages':[{'interval':1,'value':0},{'interval':3,'value':None}]},'bipad:rain')
        rows=self.a.db.execute('SELECT rainfall_source_units FROM rain_observations ORDER BY source_interval').fetchall()
        self.assertEqual(rows[0][0],0)
        self.assertIsNone(rows[1][0])

    def test_false_count_and_endless_next_stop_at_empty_page(self):
        pages=[{'count':2**63-1,'results':[{'id':1}],'next':'https://bipadportal.gov.np/api/v1/hazard/?offset=1000'},
               {'count':2**63-1,'results':[],'next':'https://bipadportal.gov.np/api/v1/hazard/?offset=2000'}]
        def fetch(source,url):
            return json.dumps(pages.pop(0)).encode(),self.fetch_row(),self.stamp
        with patch.object(self.a,'fetch',side_effect=fetch):
            self.assertEqual(self.a.bipad('hazard'),'traversed')
        self.assertFalse(pages)

    def test_repeat_page_is_failure_not_false_completion(self):
        pages=[{'results':[{'id':1}],'next':'https://bipadportal.gov.np/api/v1/hazard/?offset=1000'},
               {'results':[{'id':1}],'next':None}]
        with patch.object(self.a,'fetch',side_effect=lambda s,u:(json.dumps(pages.pop(0)).encode(),self.fetch_row(),self.stamp)):
            self.assertEqual(self.a.bipad('hazard'),'failed')

    def test_page_cap_is_partial(self):
        item={'results':[{'id':1}],'next':'https://bipadportal.gov.np/api/v1/hazard/?offset=1000'}
        with patch.object(self.a,'fetch',return_value=(json.dumps(item).encode(),self.fetch_row(),self.stamp)):
            self.assertEqual(self.a.bipad('hazard',max_pages=1),'partial')

    def test_unexpected_pagination_host_is_rejected(self):
        item={'results':[{'id':1}],'next':'https://example.org/collect'}
        with patch.object(self.a,'fetch',return_value=(json.dumps(item).encode(),self.fetch_row(),self.stamp)):
            self.assertEqual(self.a.bipad('hazard'),'failed')

    def test_broken_schema_not_counted_as_no_disasters(self):
        with patch.object(self.a,'fetch',return_value=(b'{"message":"maintenance"}',self.fetch_row(),self.stamp)):
            self.assertEqual(self.a.bipad('incident'),'failed')

    def test_historical_empty_cells_remain_null(self):
        headers=['Year','DataCards','Deaths','Injured','Missing','Houses Destroyed','Houses Damaged','Indirectly Affected','Directly affected','Relocated']
        header=''.join('<th>'+h+'</th>' for h in headers)
        cells='<td>1971</td><td>114</td><td>0</td>'+('<td></td>'*7)
        table='<table><tr>'+header+'</tr><tr>'+cells+'</tr></table>'
        text='<!-- Start stat: YEAR -->'+table+'<!-- Start stat: EVENTS -->'+table.replace('<td>1971</td>','<td>FLOOD</td>')
        row=Archive.parse_profile(text)['annual'][0]
        self.assertEqual(row['fields']['Deaths'],0)
        self.assertIsNone(row['fields']['Missing'])

if __name__=='__main__':
    unittest.main()
