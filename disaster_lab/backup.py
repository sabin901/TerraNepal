"""Portable verified backups: consistent SQLite snapshots plus referenced immutable raw files."""
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import tempfile
import time
import zipfile
from operations import archive_root, state_root


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def snapshot(source,dest):
    with contextlib.closing(sqlite3.connect(Path(source).as_uri()+'?mode=ro',uri=True)) as src,contextlib.closing(sqlite3.connect(dest)) as db:
        src.backup(db)
        if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise RuntimeError('Database integrity check failed')

def safe_path(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or not p.parts or p.parts[0] not in ('archive','state'):
        raise ValueError('Unsafe backup member')
    return p

def create(archive=None,state=None,output=None):
    archive=Path(archive or archive_root()).resolve();state=Path(state or state_root()).resolve()
    output=Path(output or state/'backups'/('snapshot-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'.zip'))
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists():raise ValueError('Backup already exists')
    files={};manifest={'format':1,'created_at':time.time(),'files':{},'note':'Per-database consistent snapshots. Raw files referenced by each snapshot are included. Exports are regenerated. Credentials and session keys are excluded; reinitialize owner login after restore.'}
    with tempfile.TemporaryDirectory(dir=output.parent,prefix='.backup-') as temp:
        temp=Path(temp)
        for source,name in [(archive/'data/archive.sqlite','archive/data/archive.sqlite'),(state/'forecasts.sqlite','state/forecasts.sqlite'),(state/'actions.sqlite','state/actions.sqlite'),(state/'operations.sqlite','state/operations.sqlite')]:
            if not source.exists():continue
            dest=temp/name;dest.parent.mkdir(parents=True,exist_ok=True);snapshot(source,dest);files[name]=dest
        if 'archive/data/archive.sqlite' not in files:raise ValueError('No archive database to back up')
        with contextlib.closing(sqlite3.connect(files['archive/data/archive.sqlite'])) as db:
            for (raw,) in db.execute('SELECT DISTINCT raw_path FROM fetches WHERE raw_path IS NOT NULL'):
                safe_path('archive/'+raw);path=(archive/raw).resolve()
                if not path.is_relative_to(archive):raise ValueError('Raw path leaves archive')
                files['archive/'+raw]=path
        if 'state/forecasts.sqlite' in files:
            with contextlib.closing(sqlite3.connect(files['state/forecasts.sqlite'])) as db:
                for (raw,) in db.execute('SELECT DISTINCT raw_file FROM weather_fetches WHERE raw_file IS NOT NULL'):
                    name='state/weather_raw/'+raw;safe_path(name);path=(state/'weather_raw'/raw).resolve()
                    if not path.is_relative_to(state/'weather_raw'):raise ValueError('Raw path leaves weather archive')
                    files[name]=path
        for name in ('config.json','schema.sql'):
            if (archive/name).exists():files['archive/'+name]=archive/name
        staging=temp/'snapshot.zip'
        with zipfile.ZipFile(staging,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name,path in sorted(files.items()):
                manifest['files'][name]={'sha256':digest(path),'bytes':path.stat().st_size};z.write(path,name)
            z.writestr('manifest.json',json.dumps(manifest,indent=2))
        os.chmod(staging,0o600);staging.replace(output)
    return {'path':str(output),'sha256':digest(output),'files':len(files),'bytes':output.stat().st_size}

def restore(source,destination):
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError('Restore destination must not already exist')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent,prefix='.restore-') as temp:
        stage=Path(temp)/'restored';stage.mkdir()
        with zipfile.ZipFile(source) as z:
            manifest=json.loads(z.read('manifest.json'))
            if manifest.get('format')!=1:raise ValueError('Unsupported backup format')
            names=z.namelist()
            if len(names)!=len(set(names)) or set(names)!=set(manifest['files'])|{'manifest.json'}:raise ValueError('Backup member manifest mismatch')
            for name,meta in manifest['files'].items():
                safe_path(name);out=stage/name;out.parent.mkdir(parents=True,exist_ok=True)
                with z.open(name) as src,out.open('wb') as dst:shutil.copyfileobj(src,dst)
                if out.stat().st_size!=meta['bytes'] or digest(out)!=meta['sha256']:raise ValueError('Backup checksum mismatch: '+name)
            for dbpath in stage.rglob('*.sqlite'):
                with contextlib.closing(sqlite3.connect(dbpath)) as db:
                    if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':raise ValueError('Restored database failed integrity check')
        stage.rename(destination)
    return {'restored_to':str(destination),'files':len(manifest['files'])}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path);p.add_argument('--restore',type=Path);p.add_argument('--destination',type=Path);args=p.parse_args();os.umask(0o077)
    if args.restore and not args.destination:p.error('--restore requires --destination')
    print(json.dumps(restore(args.restore,args.destination) if args.restore else create(output=args.output),indent=2))
