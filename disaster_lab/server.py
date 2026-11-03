#!/usr/bin/env python3
"""Run the local Nepal Disaster Lab: python3 disaster_lab/server.py"""
from __future__ import annotations
import argparse
import contextlib
import csv
import io
import json
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import threading
import urllib.parse
import uuid
from data import Dataset, ROOT, now, csv_safe
from analytics import analyze, quality_audit
from weather import ForecastStore

STATIC=Path(__file__).resolve().parent/'static'

class State:
    def __init__(self, root):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'actions.sqlite'
        with contextlib.closing(self.db()) as c, c:
            c.executescript('''CREATE TABLE IF NOT EXISTS actions(id TEXT PRIMARY KEY,title TEXT NOT NULL,place TEXT,kind TEXT,status TEXT,notes TEXT,evidence_url TEXT,created_at TEXT,updated_at TEXT);
            CREATE TABLE IF NOT EXISTS action_history(id INTEGER PRIMARY KEY,action_id TEXT,payload TEXT,changed_at TEXT);''')
    def db(self):
        c=sqlite3.connect(self.path,timeout=10);c.row_factory=sqlite3.Row;return c
    def list(self):
        with contextlib.closing(self.db()) as c, c: return [dict(r) for r in c.execute('SELECT * FROM actions ORDER BY created_at DESC')]
    def save(self, obj):
        if not isinstance(obj,dict): raise ValueError('Expected an action object')
        def field(k,maxlen,required=False):
            v=obj.get(k,'')
            if not isinstance(v,str) or len(v)>maxlen or (required and not v.strip()):raise ValueError('Invalid '+k)
            return v.strip()
        title=field('title',180,True);place=field('place',100);notes=field('notes',2000);url=field('evidence_url',1000)
        kind=field('kind',30);status=field('status',30)
        if kind not in ('research','preparedness','response'):raise ValueError('Invalid action kind')
        if status not in ('open','in_progress','completed','cancelled'):raise ValueError('Invalid action status')
        if url and urllib.parse.urlparse(url).scheme not in ('https','http'):raise ValueError('Evidence must be an HTTP(S) URL')
        sid=field('id',64) or uuid.uuid4().hex
        stamp=now()
        with contextlib.closing(self.db()) as c, c:
            old=c.execute('SELECT * FROM actions WHERE id=?',(sid,)).fetchone()
            if obj.get('id') and not old:raise ValueError('Unknown action')
            row={'id':sid,'title':title,'place':place,'kind':kind,'status':status,'notes':notes,'evidence_url':url,
                 'created_at':old['created_at'] if old else stamp,'updated_at':stamp}
            c.execute('INSERT OR REPLACE INTO actions VALUES (?,?,?,?,?,?,?,?,?)',tuple(row.values()))
            c.execute('INSERT INTO action_history(action_id,payload,changed_at) VALUES (?,?,?)',(sid,json.dumps(row),stamp))
        return row

class App:
    def __init__(self, root=ROOT,state_root=None):
        self.dataset=Dataset(root);self.state=State(state_root or Path(root)/'disaster_lab/local')
        self.forecasts=ForecastStore(self.state.root)
        self.token=secrets.token_urlsafe(32);self.lock=threading.Lock();self.process=None;self.log=None;self.reconciled=False
    def refresh_status(self):
        with self.lock:
            if self.process is None:return {'state':'idle','log':''}
            code=self.process.poll()
            if code is not None and not self.reconciled:
                self.dataset.loaded=0;self.reconciled=True
            tail=self.log.read_text(errors='replace')[-3500:] if self.log and self.log.exists() else ''
            return {'state':'running' if code is None else 'completed' if code==0 else 'needs_attention','exit_code':code,'log':tail}
    def refresh(self):
        with self.lock:
            if self.process is not None and self.process.poll() is None:return {'state':'running'}
            self.log=self.state.root/'refresh.log'
            self.reconciled=False
            with self.log.open('w') as out:
                self.process=subprocess.Popen([sys.executable,str(self.dataset.root/'disaster_lab/refresh.py'),str(self.state.root)],
                    cwd=self.dataset.root,stdout=out,stderr=subprocess.STDOUT)
            return {'state':'running'}

class Handler(BaseHTTPRequestHandler):
    server_version='NepalDisasterLab/2.0'
    def log_message(self,format,*args):pass
    def send(self,body,status=200,kind='application/json; charset=utf-8',download=None):
        if not isinstance(body,bytes):body=json.dumps(body,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status)
        self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if download:self.send_header('Content-Disposition','attachment; filename="'+download+'"')
        self.end_headers();self.wfile.write(body)
    def valid_host(self):
        return self.headers.get('Host','') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')
    def do_GET(self):
        if not self.valid_host():return self.send({'error':'Local host required'},403)
        parsed=urllib.parse.urlparse(self.path);p=parsed.path;q=urllib.parse.parse_qs(parsed.query)
        one=lambda k,d='':q.get(k,[d])[0]
        a=self.server.app
        try:
            if p=='/api/session':return self.send({'token':a.token})
            if p=='/api/overview':return self.send(a.dataset.overview())
            if p=='/api/incidents':return self.send(a.dataset.incident_query(one('hazard'),one('district'),one('year')))
            if p=='/api/river':
                h=int(one('horizon','60'))
                if h not in (30,60,180):raise ValueError('Unsupported horizon')
                return self.send(a.dataset.river(one('id'),one('cutoff') or None,h,one('known')=='1'))
            if p=='/api/sources':return self.send(a.dataset.source_health())
            if p=='/api/weather':return self.send(a.forecasts.outlook())
            if p=='/api/quality':return self.send(quality_audit(a.dataset))
            if p=='/api/predictions':return self.send(a.forecasts.ledger(a.dataset))
            if p=='/api/analytics':
                a.dataset.ensure();sid=one('id');h=int(one('horizon','60'))
                if sid not in a.dataset.river_groups:raise ValueError('Unknown station')
                result=analyze(a.dataset.river_groups[sid],h)
                result['station']=next(s for s in a.dataset.stations if s['id']==sid)
                result['archive_prediction_id']=a.forecasts.save_river(sid,result)
                return self.send(result,download='station-model-evaluation.json' if one('download')=='1' else None)
            if p=='/api/actions':return self.send(a.state.list())
            if p=='/api/refresh':return self.send(a.refresh_status())
            if p=='/api/evaluation':return self.send(a.dataset.report(),download='river-baseline-evaluation.json')
            if p=='/api/export':
                result=a.dataset.incident_query(one('hazard'),one('district'),one('year'))
                # Full filtered export; same filtering rules as the UI.
                rows=[r for r in a.dataset.incidents if (not one('hazard') or r['hazard']==one('hazard')) and
                      (not one('district') or one('district') in r['districts']) and
                      (not one('year') or r['local_event_date'].startswith(one('year')))]
                out=io.StringIO();cols=['incident_id','local_event_date','hazard','districts','latitude','longitude','reported_deaths','reported_missing','source_verified']
                writer=csv.DictWriter(out,fieldnames=cols);writer.writeheader()
                for r in rows:
                    item={k:('; '.join(r[k]) if isinstance(r[k],list) else r[k]) for k in cols}
                    for k,v in item.items():
                        item[k]=csv_safe(v)
                    writer.writerow(item)
                return self.send(out.getvalue().encode(),kind='text/csv; charset=utf-8',download='incident-reports.csv')
            docs={'/guide':a.dataset.root/'disaster_lab/README.md','/methods':a.dataset.root/'disaster_lab/METHODS.md','/research':a.dataset.root/'planning/hazard-data-and-scientific-method.md'}
            if p in docs:return self.send(docs[p].read_bytes(),kind='text/plain; charset=utf-8')
            files={'/':'index.html','/app.js':'app.js','/forecast.js':'forecast.js','/style.css':'style.css','/modern.css':'modern.css','/nepal.geojson':'nepal.geojson','/favicon.svg':'favicon.svg'}
            if p in files:
                file=STATIC/files[p]
                kinds={'.html':'text/html','.js':'text/javascript','.css':'text/css','.geojson':'application/geo+json','.svg':'image/svg+xml'}
                return self.send(file.read_bytes(),kind=kinds[file.suffix]+'; charset=utf-8')
            return self.send({'error':'Not found'},404)
        except ValueError as e:return self.send({'error':str(e)},400)
        except (OSError,sqlite3.Error) as e:return self.send({'error':'Archive unavailable: '+str(e)},503)
    def do_POST(self):
        if not self.valid_host() or self.headers.get('X-Lab-Token')!=self.server.app.token:
            return self.send({'error':'Local session token required'},403)
        origin=self.headers.get('Origin')
        if origin and origin not in (f'http://localhost:{self.server.server_port}',f'http://127.0.0.1:{self.server.server_port}'):
            return self.send({'error':'Origin rejected'},403)
        try:
            size=int(self.headers.get('Content-Length','0'))
            if size<0 or size>16000:raise ValueError('Request too large')
            obj=json.loads(self.rfile.read(size) or b'{}')
            if self.path=='/api/actions':return self.send(self.server.app.state.save(obj),201)
            if self.path=='/api/refresh':return self.send(self.server.app.refresh(),202)
            return self.send({'error':'Not found'},404)
        except (ValueError,TypeError) as e:return self.send({'error':str(e)},400)
        except (OSError,sqlite3.Error) as e:return self.send({'error':'Local storage unavailable: '+str(e)},503)

def make_server(port=8765,root=ROOT,state_root=None):
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    server.app=App(root,state_root)
    return server

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8765);p.add_argument('--state-root',type=Path)
    args=p.parse_args();server=make_server(args.port,state_root=args.state_root)
    print(f'Nepal Disaster Lab: http://localhost:{server.server_port} — Ctrl+C to stop',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
