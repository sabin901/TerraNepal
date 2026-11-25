"""Stateless read-only adapter for the existing public GitHub collection pipeline."""
from pathlib import Path
import json
import sys
import threading
import time
import urllib.request
from flask import Flask, Response, jsonify

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'public_site'))
from health import report
from intelligence import brief, markdown

SOURCE='https://sabin901.github.io/TerraNepal/data/snapshot.json'
MAX_BYTES=2*1024*1024
CACHE_SECONDS=60
_lock=threading.Lock()
_cache=None
_cached_at=0.0
app=Flask(__name__,static_folder=None)
app.config['MAX_CONTENT_LENGTH']=16000

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise ValueError('Unexpected upstream redirect')

def fetch_snapshot():
    req=urllib.request.Request(SOURCE,headers={'User-Agent':'TerraRaksha-public-adapter/1','Accept':'application/json'})
    with urllib.request.build_opener(NoRedirect()).open(req,timeout=10) as response:
        raw=response.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES:raise ValueError('Upstream snapshot exceeds size limit')
    value=json.loads(raw)
    if report(value)['status']=='invalid':raise ValueError('Upstream snapshot failed validation')
    return value

def snapshot():
    global _cache,_cached_at
    with _lock:
        if _cache is not None and time.monotonic()-_cached_at<CACHE_SECONDS:
            return _cache
        value=fetch_snapshot()
        _cache=value
        _cached_at=time.monotonic()
        return value

@app.after_request
def headers(response):
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Cache-Control']='no-store'
    return response

# Explicit allowlist also serves the dashboard when platform static routing is absent.
PUBLIC_ASSETS = {'index.html':'text/html', 'app.js':'text/javascript',
    'logic.js':'text/javascript', 'style.css':'text/css', 'favicon.svg':'image/svg+xml',
    'i18n.js':'text/javascript', 'terra-map.js':'text/javascript',
    'lab-status.html':'text/html', 'lab-status.css':'text/css'}

@app.get('/')
@app.get('/<name>')
def asset(name='index.html'):
    if name not in PUBLIC_ASSETS:
        return missing(None)
    folder = ROOT/'disaster_lab/static' if name.startswith('lab-status.') else ROOT/'public_site/static'
    content=(folder/name).read_text(encoding='utf-8')
    if name=='index.html':
        content=content.replace('NEPAL / PUBLIC RESEARCH BETA','NEPAL / VERCEL PUBLIC RESEARCH')
        content=content.replace('<div id="status"', '<p>Public evidence deployment. Private archive and case editing remain in the local lab. <a href="/api/capabilities">Deployment capabilities</a></p><div id="status"')
    return Response(content,content_type=PUBLIC_ASSETS[name]+'; charset=utf-8')

@app.get('/health/live')
def live():
    return jsonify(status='ok',mode='public_read_only',scientific_validation='not_established')

@app.get('/api/capabilities')
def capabilities():
    return jsonify(mode='public_read_only',collection='Existing GitHub workflow; best-effort schedule',
        source=SOURCE,cache_seconds=CACHE_SECONDS,
        available=['public_dashboard','validated_public_snapshot','dated_evidence_brief'],
        unavailable=['private_archive','case_writes','private_exposure_workspace','continuous_worker'],
        storage='No persistent writes; private lab requires a separate durable-storage migration')

@app.get('/data/snapshot.json')
@app.get('/data/situation-brief.json')
@app.get('/situation-brief.md')
def evidence():
    from flask import request
    try:
        value=snapshot()
        if request.path=='/data/snapshot.json':return jsonify(value)
        assessment=brief(value)
        if request.path.endswith('.md'):
            return Response(markdown(assessment),content_type='text/markdown; charset=utf-8')
        return jsonify(assessment)
    except (ValueError,KeyError,TypeError,OSError,OverflowError):
        # Do not turn a network/schema failure into a fresh-looking seed snapshot.
        return jsonify(error='Published evidence unavailable or invalid. Retry later or check the original dashboard.',source=SOURCE),503

@app.errorhandler(404)
def missing(error):
    return jsonify(error='Not available in this public deployment',capabilities='/api/capabilities'),404
