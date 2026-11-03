"""Durable work queue shared by the web process and one background worker."""
import contextlib
import os
from pathlib import Path
import sqlite3
import time
from data import ROOT

JOBS = {'live':300, 'weather':3600, 'analytics':600, 'daily':86400, 'backup':86400}

def state_root():
    return Path(os.environ.get('NEPAL_STATE_ROOT', ROOT/'disaster_lab/local')).resolve()

def archive_root():
    return Path(os.environ.get('NEPAL_ARCHIVE_ROOT', ROOT/'disaster_archive')).resolve()

class Operations:
    def __init__(self, root=None):
        self.root=Path(root or state_root());self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'operations.sqlite'
        with self.db() as db:
            db.executescript('''PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS jobs(name TEXT PRIMARY KEY,state TEXT NOT NULL,next_at REAL NOT NULL,
                started_at REAL,finished_at REAL,last_success REAL,failures INTEGER NOT NULL DEFAULT 0,detail TEXT NOT NULL DEFAULT '');
              CREATE TABLE IF NOT EXISTS worker(id INTEGER PRIMARY KEY CHECK(id=1),heartbeat REAL);
              CREATE TABLE IF NOT EXISTS login_attempts(at REAL NOT NULL);
              CREATE INDEX IF NOT EXISTS attempts_time ON login_attempts(at);
            ''')
            db.execute('BEGIN IMMEDIATE')
            if 'requested_at' not in {r[1] for r in db.execute('PRAGMA table_info(jobs)')}:
                db.execute('ALTER TABLE jobs ADD COLUMN requested_at REAL NOT NULL DEFAULT 0')
            db.executemany("INSERT OR IGNORE INTO jobs(name,state,next_at) VALUES (?,'queued',0)",[(n,) for n in JOBS])
    @contextlib.contextmanager
    def db(self):
        with contextlib.closing(sqlite3.connect(self.path,timeout=20)) as db:
            db.row_factory=sqlite3.Row
            with db:yield db
    def recover(self):
        with self.db() as db:
            db.execute("UPDATE jobs SET state='queued',next_at=0,detail='Worker restarted; interrupted work will retry' WHERE state='running'")
    def heartbeat(self, at=None):
        with self.db() as db:db.execute('INSERT OR REPLACE INTO worker VALUES(1,?)',(time.time() if at is None else at,))
    def request(self, names=('live','weather','analytics')):
        # Repeated browser clicks coalesce and cannot defeat error retry backoff.
        with self.db() as db:
            for name in names:
                if name not in JOBS:raise ValueError('Unknown job')
                stamp=time.time()
                db.execute("UPDATE jobs SET requested_at=?,state=CASE WHEN state='running' THEN state ELSE 'queued' END,next_at=min(next_at,?) WHERE name=? AND state NOT IN ('failed','deferred')",(stamp,stamp,name))
        return {'state':'queued','log':'Refresh queued. The background worker processes it independently.'}
    def due(self):
        with self.db() as db:return [dict(r) for r in db.execute("SELECT * FROM jobs WHERE state!='running' AND next_at<=? ORDER BY next_at",(time.time(),))]
    def begin(self,name):
        with self.db() as db:
            return db.execute("UPDATE jobs SET state='running',started_at=?,detail='' WHERE name=? AND state!='running'",(time.time(),name)).rowcount==1
    def finish(self,name,code,detail='',at=None):
        at=time.time() if at is None else at
        with self.db() as db:
            job=db.execute('SELECT failures,requested_at,started_at FROM jobs WHERE name=?',(name,)).fetchone()
            old=job['failures'];repeat=code==0 and job['started_at'] is not None and job['requested_at']>job['started_at']
            failures=0 if code==0 else old if code==3 else old+1
            delay=0 if repeat else JOBS[name] if code==0 else 60 if code==3 else min(3600,60*2**min(failures-1,6))
            db.execute('''UPDATE jobs SET state=?,finished_at=?,next_at=?,failures=?,detail=?,
                last_success=CASE WHEN ?=0 THEN ? ELSE last_success END WHERE name=?''',
                ('queued' if repeat else 'completed' if code==0 else 'deferred' if code==3 else 'failed',at,at+delay,failures,detail[-2000:],code,at,name))
    def status(self, at=None):
        at=time.time() if at is None else at
        with self.db() as db:
            beat=db.execute('SELECT heartbeat FROM worker WHERE id=1').fetchone()
            jobs=[dict(r) for r in db.execute('SELECT * FROM jobs ORDER BY name')]
        age=at-beat[0] if beat else None
        alive=age is not None and 0<=age<90
        return {'worker':'online' if alive else 'offline','heartbeat_age_seconds':age,'jobs':jobs,
                'schedule_seconds':JOBS,'note':'Refresh cadence is a local target. Source updates and station measurement times may lag.'}
    def refresh_status(self):
        status=self.status();jobs=[j for j in status['jobs'] if j['name'] in ('live','weather','analytics')]
        state='needs_attention' if status['worker']=='offline' or any(j['state']=='failed' for j in jobs) else 'running' if any(j['state'] in ('queued','running','deferred') for j in jobs) else 'completed'
        return {'state':state,'log':('Worker offline. Start the worker service.\n' if status['worker']=='offline' else '')+'\n'.join(j['name']+': '+j['state']+(' — '+j['detail'] if j['state'] in ('failed','deferred') else '') for j in jobs)}
    def admit_login(self, at=None):
        # Global owner-login limit also works behind a proxy without trusting client IP headers.
        at=time.time() if at is None else at
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM login_attempts WHERE at<?',(at-300,))
            if db.execute('SELECT count(*) FROM login_attempts').fetchone()[0]>=10:return False
            db.execute('INSERT INTO login_attempts VALUES(?)',(at,))
        return True
