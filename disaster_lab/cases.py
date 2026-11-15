"""Append-only local disaster evidence cases. Records are not operational warnings."""
from __future__ import annotations
import argparse
import contextlib
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import urlparse

KINDS = {'observation','provider_forecast','scenario','official_warning','confirmed_impact'}
HAZARDS = {'flood','landslide','heat','cold','drought','wildfire','earthquake','glof','multi_hazard','weather'}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def stamp(value):
    if not isinstance(value,str): raise ValueError('Expected timezone-aware timestamp')
    try: parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError as exc: raise ValueError('Invalid timestamp') from exc
    if parsed.tzinfo is None: raise ValueError('Timestamp requires timezone')
    return parsed.astimezone(dt.timezone.utc).isoformat()


def epoch(value): return dt.datetime.fromisoformat(stamp(value)).timestamp()
def text(value, name, limit=4000):
    if not isinstance(value,str) or not value.strip() or len(value)>limit: raise ValueError('Invalid '+name)
    return value

def keys(value, expected):
    if not isinstance(value,dict) or set(value)!=set(expected):raise ValueError('Unexpected record fields')

def finite(value):
    try:
        return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)
    except OverflowError:
        return False

def hash_string(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{64}',value):raise ValueError('Invalid evidence SHA256')

def identifier(value):
    if not isinstance(value,str) or not re.fullmatch('[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}',value):raise ValueError('Invalid case identifier')

def interval(start,end):
    start,end=stamp(start),stamp(end)
    if epoch(end)<epoch(start):raise ValueError('Reversed valid interval')
    return start,end

def review(value, at):
    keys(value,{'status','reviewer','reviewed_at','reason'})
    if not isinstance(value['status'],str) or value['status'] not in ('unverified','reviewed','rejected'):raise ValueError('Invalid review status')
    text(value['reason'],'review reason')
    if value['status']=='unverified':
        if value['reviewer'] is not None or value['reviewed_at'] is not None:raise ValueError('Unverified record cannot imply completed review')
    else:
        text(value['reviewer'],'reviewer',200)
        value['reviewed_at']=stamp(value['reviewed_at'])
        if epoch(value['reviewed_at'])>at:raise ValueError('Future review')
    return value


def evidence(value, at):
    keys(value,{'kind','source','source_url','sha256','acquired_at','valid_from','valid_to','review'})
    if not isinstance(value['kind'],str) or value['kind'] not in KINDS:raise ValueError('Unsupported evidence kind')
    text(value['source'],'source',200);hash_string(value['sha256'])
    url=urlparse(text(value['source_url'],'source URL',2000))
    if url.scheme!='https' or not url.netloc or url.username or url.password or url.fragment:raise ValueError('Expected credential-free HTTPS source URL')
    # Query strings may carry API credentials and are deliberately not exported here.
    if url.query:raise ValueError('Source reference URL must omit query parameters')
    value['acquired_at']=stamp(value['acquired_at'])
    if epoch(value['acquired_at'])>at:raise ValueError('Future acquisition cannot enter a case')
    value['valid_from'],value['valid_to']=interval(value['valid_from'],value['valid_to'])
    if value['kind'] in ('observation','confirmed_impact') and epoch(value['valid_to'])>epoch(value['acquired_at']):
        raise ValueError('Observed/confirmed evidence cannot describe future outcomes')
    value['review']=review(value['review'],at)
    if value['review']['reviewed_at'] and epoch(value['review']['reviewed_at'])<epoch(value['acquired_at']):raise ValueError('Review precedes acquisition')
    if value['kind']=='confirmed_impact' and value['review']['status']!='reviewed':raise ValueError('Confirmed impact requires an attributed review')
    return value


def document(value, at):
    value=json.loads(canonical(value))
    keys(value,{'title','hazard','geography','valid_from','valid_to','summary','evidence'})
    text(value['title'],'title',200);text(value['summary'],'summary',10000)
    if not isinstance(value['hazard'],str) or value['hazard'] not in HAZARDS:raise ValueError('Unsupported hazard')
    value['valid_from'],value['valid_to']=interval(value['valid_from'],value['valid_to'])
    g=value['geography'];keys(g,{'type','coordinates','label','review'})
    if not isinstance(g['type'],str) or g['type'] not in ('point','bbox'):raise ValueError('Geography requires point or bbox')
    text(g['label'],'geographic label',200)
    c=g['coordinates'];length=2 if g['type']=='point' else 4
    if not isinstance(c,list) or len(c)!=length or any(not finite(x) for x in c):raise ValueError('Invalid WGS84 coordinates')
    if not -180<=c[0]<=180 or not -90<=c[1]<=90:raise ValueError('Coordinates out of range')
    if length==4 and not(c[0]<=c[2]<=180 and c[1]<=c[3]<=90):raise ValueError('Invalid bbox; antimeridian crossing requires separate cases')
    g['review']=review(g['review'],at)
    rows=value['evidence']
    if not isinstance(rows,list) or not 1<=len(rows)<=1000:raise ValueError('Case requires 1–1000 evidence references')
    value['evidence']=[evidence(x,at) for x in rows]
    identities=[sha(x) for x in value['evidence']]
    if len(set(identities))!=len(identities):raise ValueError('Duplicate evidence reference')
    return value


class CaseStore:
    def __init__(self, root, clock=time.time):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'cases.sqlite';self.clock=clock
        with self.db() as db:
            db.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS case_events (
              seq INTEGER PRIMARY KEY AUTOINCREMENT,
              case_id TEXT NOT NULL, kind TEXT NOT NULL, recorded_at TEXT NOT NULL,
              previous_sha256 TEXT, payload TEXT NOT NULL, sha256 TEXT NOT NULL UNIQUE);
            CREATE INDEX IF NOT EXISTS cases_lookup ON case_events(case_id,seq);
            CREATE TRIGGER IF NOT EXISTS immutable_case_update BEFORE UPDATE ON case_events
              BEGIN SELECT RAISE(ABORT,'Case events are immutable'); END;
            CREATE TRIGGER IF NOT EXISTS immutable_case_delete BEFORE DELETE ON case_events
              BEGIN SELECT RAISE(ABORT,'Case events are immutable'); END;
            ''')

    @contextlib.contextmanager
    def db(self):
        with contextlib.closing(sqlite3.connect(self.path,timeout=20)) as db:
            db.row_factory=sqlite3.Row
            with db:yield db

    def _events(self,db,case_id=None):
        rows=db.execute('SELECT * FROM case_events'+(' WHERE case_id=?' if case_id else '')+' ORDER BY seq',(case_id,) if case_id else ()).fetchall()
        heads={};times={};result=[]
        for r in rows:
            payload=json.loads(r['payload'])
            envelope=dict(case_id=r['case_id'],kind=r['kind'],recorded_at=r['recorded_at'],previous_sha256=r['previous_sha256'],payload=payload)
            if r['previous_sha256']!=heads.get(r['case_id']) or sha(envelope)!=r['sha256']:raise ValueError('Case hash chain integrity failure')
            if epoch(r['recorded_at'])<times.get(r['case_id'],float('-inf')):raise ValueError('Case chronology integrity failure')
            heads[r['case_id']]=r['sha256'];times[r['case_id']]=epoch(r['recorded_at'])
            result.append({**envelope,'sha256':r['sha256']})
        return result

    def _append(self,case_id,kind,payload):
        identifier(case_id)
        current=self.clock()
        if isinstance(current,bool) or not isinstance(current,(int,float)) or not math.isfinite(current):raise ValueError('Invalid recording clock')
        recorded=dt.datetime.fromtimestamp(current,dt.timezone.utc).isoformat();at=epoch(recorded)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            existing=self._events(db,case_id)
            if existing and epoch(existing[-1]['recorded_at'])>at:raise ValueError('Recording clock moved backward')
            if kind=='revision':
                payload=document(payload,at)
                revisions=[e for e in existing if e['kind']=='revision']
                # Repeated unchanged imports are idempotent; intentional corrections append.
                if revisions and revisions[-1]['payload']==payload:return revisions[-1]
            else:
                payload=json.loads(canonical(payload))
                keys(payload,{'revision_sha256','text','actor','occurred_at','evidence','review'})
                hash_string(payload['revision_sha256']);text(payload['text'],'entry text',10000);text(payload['actor'],'entry actor',200)
                if not any(e['kind']=='revision' and e['sha256']==payload['revision_sha256'] for e in existing):raise ValueError('Entry requires an existing revision in this case')
                payload['occurred_at']=stamp(payload['occurred_at'])
                if epoch(payload['occurred_at'])>at:raise ValueError('Action/outcome cannot already have occurred in the future')
                if not isinstance(payload['evidence'],list) or len(payload['evidence'])>1000:raise ValueError('Invalid entry evidence')
                payload['evidence']=[evidence(x,at) for x in payload['evidence']]
                if kind=='outcome' and not payload['evidence']:raise ValueError('Outcome requires evidence')
                payload['review']=review(payload['review'],at)
                # An exact repeated event is idempotent, even after intervening records.
                for entry in existing:
                    if entry['kind']==kind and entry['payload']==payload:return entry
            envelope=dict(case_id=case_id,kind=kind,recorded_at=recorded,previous_sha256=existing[-1]['sha256'] if existing else None,payload=payload)
            digest=sha(envelope)
            db.execute('INSERT INTO case_events(case_id,kind,recorded_at,previous_sha256,payload,sha256) VALUES(?,?,?,?,?,?)',
                       (case_id,kind,recorded,envelope['previous_sha256'],canonical(payload),digest))
            return {**envelope,'sha256':digest}

    def append_revision(self,case_id,value):return self._append(case_id,'revision',value)
    def append_action(self,case_id,value):return self._append(case_id,'action',value)
    def append_outcome(self,case_id,value):return self._append(case_id,'outcome',value)

    def verify(self):
        with self.db() as db:
            if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('SQLite integrity failure')
            events=self._events(db)
        return {'events':len(events),'cases':len({e['case_id'] for e in events}),'hash_chains':'verified',
                'note':'Hash consistency is not source authenticity, reviewer identity verification or scientific validation.'}

    def list_cases(self,cutoff=None):
        cutoff=stamp(cutoff) if cutoff else dt.datetime.fromtimestamp(self.clock(),dt.timezone.utc).isoformat()
        with self.db() as db:events=self._events(db)
        grouped={}
        for event in events:
            if epoch(event['recorded_at'])<=epoch(cutoff):grouped.setdefault(event['case_id'],[]).append(event)
        result=[]
        for case_id,rows in sorted(grouped.items()):
            revisions=[r for r in rows if r['kind']=='revision']
            if not revisions:continue
            latest=revisions[-1];d=latest['payload']
            result.append({'case_id':case_id,'title':d['title'],'hazard':d['hazard'],
                           'geography':d['geography'],'latest_revision_sha256':latest['sha256'],
                           'recorded_at':latest['recorded_at'],'revision_count':len(revisions),
                           'action_count':sum(r['kind']=='action' for r in rows),
                           'outcome_count':sum(r['kind']=='outcome' for r in rows)})
        return result

    def replay(self,case_id,cutoff):
        identifier(case_id);cutoff=stamp(cutoff)
        with self.db() as db:all_events=self._events(db,case_id)
        events=[e for e in all_events if epoch(e['recorded_at'])<=epoch(cutoff)]
        revisions=[e for e in events if e['kind']=='revision']
        return {'schema_version':1,'case_id':case_id,'as_of':cutoff,
                'latest_revision':revisions[-1] if revisions else None,'events':events,
                'limitations':['Replay uses local acquisition/recording history, not undocumented prior source availability.',
                               'Review attribution is entered by the operator; reviewer identity and issuing authority are not independently authenticated.',
                               'References do not verify raw bytes unless separately checked against the retained archive.',
                               'No warning, evacuation order or safe-area determination is generated.']}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('command',choices=['revision','action','outcome','export','verify']);p.add_argument('--case');p.add_argument('--input',type=Path);p.add_argument('--at');p.add_argument('--output',type=Path)
    a=p.parse_args(argv)
    if a.command!='verify' and not a.case:p.error('--case is required')
    if a.command in ('revision','action','outcome') and not a.input:p.error('--input is required')
    if a.command=='export' and not a.at:p.error('--at is required for reproducible export')
    if a.output:
        if a.output.exists():p.error('Output exists; preserve previous evidence')
        if a.input and a.input.resolve()==a.output.resolve():p.error('Output must not replace input')
    store=CaseStore(a.root)
    if a.command=='verify':result=store.verify()
    elif a.command=='export':result=store.replay(a.case,a.at)
    else:result=getattr(store,'append_'+a.command)(a.case,json.loads(a.input.read_text()))
    encoded=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        with a.output.open('x') as f:f.write(encoded)
    else:print(encoded,end='')
    return 0

if __name__=='__main__':raise SystemExit(main())
