"""Authenticated private production web service. See DEPLOYMENT.md."""
from __future__ import annotations
import argparse
import contextlib
import csv
import datetime as dt
import getpass
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import threading
from urllib.parse import urlsplit
from flask import Flask, Response, request, session, redirect, render_template_string
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from waitress import serve
from server import App, STATIC
from data import ROOT, csv_safe
from analytics import analyze, quality_audit
from operations import Operations, state_root
from snapshots import SnapshotCache

LOGIN='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Sign in · Nepal Disaster Lab</title><link rel="stylesheet" href="/login.css"></head><body><main class="login-card"><div class="brand">◭ NEPAL DISASTER LAB</div><p class="eyebrow">PRIVATE RESEARCH WORKSPACE</p><h1>Evidence for<br>better preparation.</h1><p>Sign in to explore observations, weather outlooks and experimental river models.</p><form method="post" action="/login"><input type="hidden" name="token" value="{{ token }}"><label for="password">Workspace password</label><input id="password" name="password" type="password" autocomplete="current-password" required maxlength="1024"><button type="submit">Open workspace →</button></form>{% if error %}<p role="alert" class="error">{{ error }}</p>{% endif %}<small>This research workspace does not issue disaster warnings.</small></main></body></html>'''

def secret_file(root):
    path=root/'session.key'
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:pass
    else:
        with os.fdopen(fd,'w') as out:out.write(secrets.token_hex(32))
    key=path.read_text().strip()
    if len(key)<64:raise RuntimeError('Invalid session key; regenerate it with the service stopped')
    return key

def set_password(root):
    root.mkdir(parents=True,exist_ok=True)
    password=getpass.getpass('New workspace password (at least 16 characters): ')
    if len(password)<16 or len(password)>1024:raise ValueError('Use 16–1024 characters')
    if password!=getpass.getpass('Repeat password: '):raise ValueError('Passwords did not match')
    path=root/'owner.json';temp=root/'owner.json.tmp'
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
    with os.fdopen(fd,'w') as out:json.dump({'password_hash':generate_password_hash(password),'version':secrets.token_hex(16)},out)
    temp.replace(path);secret_file(root)
    print('Owner password saved as a hash. Restart the web service to apply it.')

def create_app(root=ROOT,state=None,local=False,hosts=None,origin=None):
    state=Path(state or state_root());state.mkdir(parents=True,exist_ok=True)
    owner=None
    if not local:
        owner=json.loads((state/'owner.json').read_text())
        origin=origin or os.environ.get('NEPAL_PUBLIC_ORIGIN','')
        parsed=urlsplit(origin)
        if parsed.scheme!='https' or not parsed.hostname or parsed.path or parsed.query or parsed.fragment or parsed.username:
            raise ValueError('Set NEPAL_PUBLIC_ORIGIN to the HTTPS origin, without a trailing slash or path')
        hosts=hosts or [parsed.hostname]
    else:hosts=hosts or ['localhost','127.0.0.1']
    app=Flask(__name__,static_folder=None)
    app.config.update(SECRET_KEY=secret_file(state),TRUSTED_HOSTS=hosts,MAX_CONTENT_LENGTH=16000,
        MAX_FORM_MEMORY_SIZE=16000,MAX_FORM_PARTS=10,SESSION_COOKIE_NAME='nepal_session',
        SESSION_COOKIE_SECURE=not local,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE='Strict',
        PERMANENT_SESSION_LIFETIME=dt.timedelta(hours=8),SESSION_REFRESH_EACH_REQUEST=False)
    backend=App(root,state);ops=Operations(state);view_lock=threading.RLock()
    cache=SnapshotCache(root)
    if backend.dataset.path.exists():cache.refresh()
    cache.start()
    app.extensions.update(lab=backend,operations=ops,snapshots=cache)
    def json_response(value,status=200,download=None):
        response=Response(json.dumps(value,ensure_ascii=False,allow_nan=False),status=status,content_type='application/json; charset=utf-8')
        if download:response.headers['Content-Disposition']='attachment; filename="'+download+'"'
        return response
    def csrf():
        if 'csrf' not in session:session['csrf']=secrets.token_urlsafe(32)
        return session['csrf']
    def authorized():return local or session.get('owner_version')==owner['version']
    @app.before_request
    def guard():
        # Reading request.host invokes Flask trusted-host validation before any route.
        _=request.host
        if request.path in ('/health/live','/health/ready'):return None
        if request.path not in ('/login','/login.css') and not authorized():
            return json_response({'error':'Sign in required'},401) if request.path.startswith('/api/') else redirect('/login')
        if request.method not in ('GET','HEAD','OPTIONS'):
            expected=csrf();provided=request.headers.get('X-Lab-Token') or request.form.get('token','')
            if not secrets.compare_digest(expected,provided):return json_response({'error':'Session token required'},403)
            allowed={origin} if not local else {'http://'+request.host}
            if request.headers.get('Origin') and request.headers['Origin'] not in allowed:
                return json_response({'error':'Origin rejected'},403)
    @app.after_request
    def headers(response):
        response.headers.update({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin',
            'X-Frame-Options':'DENY','Permissions-Policy':'geolocation=(), microphone=(), camera=()',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'"})
        if not local:response.headers['Strict-Transport-Security']='max-age=31536000'
        return response
    @app.errorhandler(Exception)
    def failure(error):
        if isinstance(error,HTTPException):return json_response({'error':error.name},error.code)
        if isinstance(error,ValueError):return json_response({'error':str(error)},400)
        app.logger.exception('Request failed')
        return json_response({'error':'The service could not complete this request. Check the service logs.'},503)
    @app.route('/login',methods=['GET','POST'])
    def login():
        error=''
        if local:return redirect('/')
        if request.method=='POST':
            if not ops.admit_login():return Response(render_template_string(LOGIN,token=csrf(),error='Too many attempts. Try again in five minutes.'),status=429,headers={'Retry-After':'300'})
            if check_password_hash(owner['password_hash'],request.form.get('password','')):
                session.clear();session['owner_version']=owner['version'];session.permanent=True;csrf();return redirect('/')
            error='Password not recognized.'
        return Response(render_template_string(LOGIN,token=csrf(),error=error),status=401 if error else 200,content_type='text/html; charset=utf-8')
    @app.post('/logout')
    def logout():session.clear();return json_response({'ok':True})
    @app.get('/health/live')
    def live():return json_response({'status':'alive'})
    @app.get('/health/ready')
    def ready():
        try:
            with contextlib.closing(sqlite3.connect(backend.dataset.path.as_uri()+'?mode=ro',uri=True,timeout=2)) as db:db.execute('SELECT 1 FROM records LIMIT 1').fetchone()
            ok=ops.status()['worker']=='online' and cache.current is not None
        except sqlite3.Error:ok=False
        return json_response({'status':'ready' if ok else 'not_ready'},200 if ok else 503)
    @app.get('/login.css')
    def login_css():return Response((STATIC/'login.css').read_bytes(),content_type='text/css')
    @app.route('/api/<name>',methods=['GET','POST'])
    def api(name):
        if request.method=='POST':
            obj=request.get_json()
            if not isinstance(obj,dict):raise ValueError('Expected an object')
            if name=='actions':return json_response(backend.state.save(obj),201)
            if name=='refresh':return json_response(ops.request(),202)
            return json_response({'error':'Not found'},404)
        q=request.args
        if name=='session':return json_response({'token':csrf(),'authenticated':not local})
        if name=='operations':return json_response({**ops.status(),'read_snapshot':{'loaded_at':cache.loaded_at,'error':cache.last_error}})
        if name=='refresh':return json_response(ops.refresh_status())
        if name=='actions':return json_response(backend.state.list())
        if name=='weather':return json_response(backend.forecasts.outlook())
        if name=='predictions':return json_response(backend.forecasts.ledger(limit=int(q.get('limit',100)),offset=int(q.get('offset',0))))
        if name in ('river','analytics') and int(q.get('horizon',60)) not in (30,60,180):raise ValueError('Unsupported horizon')
        with view_lock:
            d=cache.get()
            if name=='overview':return json_response(d.overview())
            if name=='incidents':return json_response(d.incident_query(q.get('hazard',''),q.get('district',''),q.get('year','')))
            if name in ('river','analytics'):
                horizon=int(q.get('horizon',60))
                if horizon not in (30,60,180):raise ValueError('Unsupported horizon')
                if name=='river':return json_response(d.river(q.get('id',''),q.get('cutoff'),horizon,q.get('known')=='1'))
                d.ensure();sid=q.get('id','')
                if sid not in d.river_groups:raise ValueError('Unknown station')
                result=analyze(d.river_groups[sid],horizon);result['station']=next(s for s in d.stations if s['id']==sid)
                # Background worker owns prospective recording; read requests have no write side effect.
                result['archive_prediction_id']=None;result['recording_mode']='background_worker'
                return json_response(result,download='station-model-evaluation.json' if q.get('download')=='1' else None)
            if name=='sources':return json_response(d.source_health())
            if name=='quality':return json_response(quality_audit(d))
            if name=='evaluation':return json_response(d.report(),download='river-baseline-evaluation.json')
            if name=='export':
                d.ensure();rows=[r for r in d.incidents if (not q.get('hazard') or r['hazard']==q['hazard']) and (not q.get('district') or q['district'] in r['districts']) and (not q.get('year') or (r.get('local_event_date') or '').startswith(q['year']))]
                out=io.StringIO();cols=['incident_id','local_event_date','hazard','districts','latitude','longitude','reported_deaths','reported_missing','source_verified']
                writer=csv.DictWriter(out,fieldnames=cols);writer.writeheader()
                for r in rows:
                    item={k:'; '.join(r[k]) if isinstance(r[k],list) else r[k] for k in cols}
                    for k,v in item.items():
                        item[k]=csv_safe(v)
                    writer.writerow(item)
                return Response(out.getvalue(),content_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="incident-reports.csv"'})
        return json_response({'error':'Not found'},404)
    @app.get('/')
    @app.get('/<path:path>')
    def files(path='index.html'):
        docs={'guide':Path(root)/'disaster_lab/README.md','methods':Path(root)/'disaster_lab/METHODS.md','research':Path(root)/'planning/hazard-data-and-scientific-method.md'}
        if path in docs:return Response(docs[path].read_bytes(),content_type='text/plain; charset=utf-8')
        allowed={'index.html':'text/html','app.js':'text/javascript','forecast.js':'text/javascript','style.css':'text/css','modern.css':'text/css','nepal.geojson':'application/geo+json','favicon.svg':'image/svg+xml'}
        if path not in allowed:return json_response({'error':'Not found'},404)
        return Response((STATIC/path).read_bytes(),content_type=allowed[path]+'; charset=utf-8')
    return app

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--local',action='store_true');p.add_argument('--set-password',action='store_true');p.add_argument('--host',default=os.environ.get('NEPAL_BIND','127.0.0.1'));p.add_argument('--port',type=int,default=int(os.environ.get('PORT','8765')))
    args=p.parse_args();os.umask(0o077)
    if args.set_password:set_password(state_root());return
    if args.local and args.host not in ('127.0.0.1','::1'):p.error('--local requires a loopback bind address')
    app=create_app(local=args.local)
    print(f'Nepal Disaster Lab web service listening on {args.host}:{args.port}',flush=True)
    serve(app,host=args.host,port=args.port,threads=6,connection_limit=100,channel_timeout=30,
        max_request_body_size=16000,max_request_header_size=16384,clear_untrusted_proxy_headers=True,
        expose_tracebacks=False,ident='NepalDisasterLab')

if __name__=='__main__':main()
