"""Swap complete read snapshots so source refreshes do not block page requests."""
import logging
import threading
import time
from data import Dataset

class SnapshotCache:
    def __init__(self,root,interval=60):
        self.root=root;self.interval=interval;self.current=None;self.loaded_at=None;self.last_error=None
        self.lock=threading.Lock();self.stop=threading.Event()
    def refresh(self):
        with self.lock:
            try:
                candidate=Dataset(self.root)
                if self.current:
                    path=candidate.path
                    from pathlib import Path
                    signature=tuple((p.stat().st_mtime_ns,p.stat().st_size) if p.exists() else (0,0) for p in (path,Path(str(path)+'-wal')))
                    if signature==self.current.signature:return
                candidate.ensure();candidate.pinned=True
                self.current=candidate;self.loaded_at=time.time();self.last_error=None
            except Exception:
                self.last_error='Read-model refresh failed; the previous complete snapshot is retained.'
                logging.getLogger(__name__).exception('Read-model refresh failed')
    def get(self):
        if self.current is None:raise OSError('Read snapshot unavailable')
        return self.current
    def start(self):
        def loop():
            while not self.stop.wait(self.interval):self.refresh()
        threading.Thread(target=loop,name='read-snapshot',daemon=True).start()
