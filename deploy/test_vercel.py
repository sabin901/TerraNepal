import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from deploy import vercel_app as v
from deploy.build_vercel import build

class VercelTests(unittest.TestCase):
    def setUp(self):
        v._cache=None
        v._cached_at=0
        self.client=v.app.test_client()
        self.seed=json.loads((ROOT/'public_site/snapshot.json').read_text())

    def test_public_snapshot_and_cache_preserve_dates(self):
        with patch.object(v,'fetch_snapshot',return_value=self.seed) as fetch:
            for _ in range(2):
                result=self.client.get('/data/snapshot.json')
                self.assertEqual(result.status_code,200)
                self.assertEqual(result.json['built_at'],self.seed['built_at'])
                self.assertEqual(result.headers['Cache-Control'],'no-store')
            self.assertEqual(fetch.call_count,1)

    def test_failed_refresh_does_not_serve_expired_cached_success(self):
        v._cache=self.seed;v._cached_at=-1000
        with patch.object(v,'fetch_snapshot',side_effect=OSError('private error detail')):
            result=self.client.get('/data/snapshot.json')
            self.assertEqual(result.status_code,503)
            self.assertNotIn('private error',result.text)
            self.assertNotIn('built_at',result.json)

    def test_brief_is_derived_from_snapshot(self):
        with patch.object(v,'fetch_snapshot',return_value=self.seed):
            self.assertEqual(self.client.get('/data/situation-brief.json').status_code,200)
            self.assertEqual(self.client.get('/situation-brief.md').status_code,200)

    def test_no_private_routes_or_writes(self):
        for path in ('/api/cases','/api/actions','/workspace.html','/.env','/disaster_archive/data/archive.sqlite'):
            self.assertEqual(self.client.get(path).status_code,404)
        self.assertEqual(self.client.post('/data/snapshot.json',json={}).status_code,405)
        self.assertEqual(self.client.get('/api/capabilities').json['mode'],'public_read_only')

    def test_upstream_size_and_schema_fail_closed(self):
        class Reply:
            def __init__(self,body):self.body=body
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):return self.body[:limit]
        for body in (b'{}',b'x'*(v.MAX_BYTES+1)):
            with patch.object(v.urllib.request,'build_opener') as opener:
                opener.return_value.open.return_value=Reply(body)
                self.assertEqual(self.client.get('/data/snapshot.json').status_code,503)

    def test_dashboard_and_all_linked_assets(self):
        for path in ('/', '/index.html', '/app.js', '/logic.js', '/style.css', '/favicon.svg', '/i18n.js', '/terra-map.js', '/manifest.json', '/sw.js', '/lab-status.html', '/lab-status.css'):
            self.assertEqual(self.client.get(path).status_code,200,path)
        self.assertIn('VERCEL PUBLIC RESEARCH',self.client.get('/').text)
        self.assertEqual(self.client.get('/vercel_app.py').status_code,404)

    def test_redirects_rejected(self):
        with self.assertRaises(ValueError):v.NoRedirect().redirect_request(None,None,None,None,None,None)

    def test_build_contains_only_reviewed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'public';build(out)
            self.assertEqual({p.name for p in out.iterdir()}, {'index.html','app.js','style.css','logic.js','favicon.svg','i18n.js','terra-map.js','manifest.json','sw.js','lab-status.html','lab-status.css'})
            self.assertIn('Private archive and case editing remain', (out/'index.html').read_text())
            with self.assertRaises(ValueError):build(out)

if __name__=='__main__':unittest.main()
