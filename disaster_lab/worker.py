"""One durable scheduler; sources and analysis run in independently supervised processes."""
import argparse
import contextlib
import concurrent.futures
import fcntl
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from data import ROOT
from operations import Operations, archive_root, state_root

TIMEOUTS={'live':900,'daily':7200,'weather':300,'analytics':900,'backup':3600}
LANES={'live':'archive','daily':'archive','weather':'weather','analytics':'analysis','backup':'backup'}

def command(name):
    if name in ('live','daily'):
        return [sys.executable,str(ROOT/'disaster_archive/archive.py'),'live' if name=='live' else 'collect','--root',str(archive_root())]
    script={'weather':'weather.py','analytics':'predictions.py','backup':'backup.py'}[name]
    return [sys.executable,str(ROOT/'disaster_lab'/script)]

def execute(ops,name,stop):
    logs=ops.root/'job_logs';logs.mkdir(exist_ok=True)
    path=logs/(name+'-'+str(time.time_ns())+'.log')
    proc=None
    try:
        if name=='daily' and (archive_root()/'data/archive.sqlite').exists():
            with contextlib.closing(sqlite3.connect(archive_root()/'data/archive.sqlite',timeout=10)) as db:
                row=db.execute("SELECT max(finished_at) FROM runs WHERE mode IN ('daily','full') AND status='completed'").fetchone()
            from data import timestamp
            if row and row[0] and time.time()-timestamp(row[0])<86400:
                ops.finish(name,0,'Archive reconciliation already completed at '+row[0])
                with ops.db() as db:db.execute('UPDATE jobs SET next_at=? WHERE name=?',(timestamp(row[0])+86400,name))
                return
        with path.open('w') as out:
            proc=subprocess.Popen(command(name),stdout=out,stderr=subprocess.STDOUT,cwd=ROOT,start_new_session=True)
            deadline=time.monotonic()+TIMEOUTS[name]
            while proc.poll() is None:
                if stop.wait(1) or time.monotonic()>deadline:
                    os.killpg(proc.pid,signal.SIGTERM)
                    try:proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid,signal.SIGKILL);proc.wait()
                    raise RuntimeError('Worker stopped' if stop.is_set() else 'Job exceeded its time limit')
            code=proc.returncode
        detail='Log: '+path.name
        if code:detail+='\n'+path.read_text(errors='replace')[-1500:]
        ops.finish(name,code,detail)
        if code==0 and name in ('live','daily'):ops.request(('analytics',))
    except Exception as e:
        ops.finish(name,1,str(e))
    finally:
        # Bounded operational logs; source responses and revision records are never pruned here.
        for old in sorted(logs.glob(name+'-*.log'))[:-30]:old.unlink(missing_ok=True)

def main():
    os.umask(0o077)
    p=argparse.ArgumentParser();p.add_argument('--health',action='store_true');args=p.parse_args()
    ops=Operations()
    if args.health:
        report=ops.status();print(json.dumps({'worker':report['worker']}));return 0 if report['worker']=='online' else 1
    lock=(state_root()/'.worker.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        print('Another worker owns this state directory',file=sys.stderr);return 3
    os.umask(0o077);stop=threading.Event()
    for sig in (signal.SIGINT,signal.SIGTERM):signal.signal(sig,lambda *_:stop.set())
    ops.recover();active={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        while not stop.is_set():
            ops.heartbeat()
            for name,future in list(active.items()):
                if future.done():future.result();del active[name]
            lanes={LANES[n] for n in active}
            for job in sorted(ops.due(),key=lambda j: j['name']=='daily'):
                name=job['name'];lane=LANES[name]
                if lane not in lanes and ops.begin(name):
                    active[name]=pool.submit(execute,ops,name,stop);lanes.add(lane)
            stop.wait(5)
    lock.close();return 0

if __name__=='__main__':raise SystemExit(main())
