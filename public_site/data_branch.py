"""Persist only the approved public state on an independent Git branch.

No checkout, force push, raw database, credentials or expiring Actions cache.
History files are immutable; a normal push rejects competing writers.
"""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

BRANCH='codex/data-snapshots'
REF='refs/remotes/origin/'+BRANCH
MAX_BYTES=256*1024*1024
MAX_FILE=32*1024*1024

def git(*args, input=None, env=None):
    result=subprocess.run(['git',*args],input=input,capture_output=True,env=env)
    if result.returncode:raise RuntimeError('git '+args[0]+' failed: '+result.stderr.decode(errors='replace')[:1000])
    return result.stdout

def allowed(name):
    return name in ('latest.json','state.json','manifest.json') or bool(re.fullmatch(r'history/\d{4}-\d{2}-\d{2}/[0-9a-f]{64}\.json\.gz',name))

def tree(ref):
    result={}
    for line in git('ls-tree','-r','-l',ref).decode().splitlines():
        meta,name=line.split('\t',1);mode,kind,sha,size=meta.split()
        if mode!='100644' or kind!='blob' or not allowed(name):raise ValueError('Unexpected data branch entry: '+name)
        result[name]=(sha,int(size))
    if any(v[1]>MAX_FILE for v in result.values()) or sum(v[1] for v in result.values())>MAX_BYTES:raise ValueError('Public history storage budget exceeded; migrate/export history before continuing')
    return result

def verify_file(name,raw):
    if not allowed(name) or len(raw)>MAX_FILE:raise ValueError('Unexpected public data file')
    if name.startswith('history/'):
        # Bound decompression before decoding untrusted restored objects.
        import io
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:decoded=stream.read(MAX_FILE+1)
        if len(decoded)>MAX_FILE or hashlib.sha256(decoded).hexdigest()!=Path(name).name.split('.')[0]:raise ValueError('History content hash mismatch')
        obj=json.loads(decoded)
        if set(obj)!={'schema_version','recorded_at','snapshot','observation_changes','fetches'}:raise ValueError('Invalid history envelope')
        from pipeline import validate
        validate(obj['snapshot'])
        from history import digest
        for change in obj['observation_changes']:
            if set(change)!={'record','sha256','previous_sha256','provenance'}:raise ValueError('Unexpected observation change fields')
            row=change['record'];base={'source','id','station_id','observed_at','units','values'}
            if set(row) not in (base,base|{'quality_issues'}) or row['source'] not in ('bipad:river','bipad:rain'):raise ValueError('Unexpected observation fields')
            if change['sha256']!=digest(row) or (change['previous_sha256'] is not None and not re.fullmatch('[0-9a-f]{64}',change['previous_sha256'])):raise ValueError('Observation version hash mismatch')
            if set(change['provenance'])!={'response_sha256','source_record_sha256','fetched_at'}:raise ValueError('Unexpected observation provenance')
            values=row['values']
            if row['source']=='bipad:river':
                if set(values)!={'level'}:raise ValueError('Unexpected river value fields')
            elif set(values)!={'averages'} or any(set(a)!={'interval','value'} for a in values['averages']):raise ValueError('Unexpected rain value fields')
        from urllib.parse import urlparse
        for fetch in obj['fetches']:
            weather=fetch.get('source')=='open_meteo_weather'
            keys={'source','place_id','model','url','fetched_at','status','sha256','error'} if weather else {'source','url','fetched_at','http_status','sha256','byte_count','error'}
            # URL was added to weather receipts after the first local bootstrap.
            if set(fetch) not in (keys,keys-{'url'} if weather else keys):raise ValueError('Unexpected fetch receipt fields')
            if fetch['source'] not in ('bipad','usgs','open_meteo_flood','open_meteo_weather'):raise ValueError('Unexpected receipt source')
            if 'url' in fetch:
                url=urlparse(fetch['url'])
                if url.scheme!='https' or url.hostname not in ('bipadportal.gov.np','earthquake.usgs.gov','flood-api.open-meteo.com','api.open-meteo.com') or url.username or url.password:raise ValueError('Unexpected receipt URL')
    else:
        obj=json.loads(raw)
        if name=='latest.json':
            from pipeline import validate
            validate(obj)
        if name=='state.json':
            from history import validate_state
            validate_state(obj)
    return obj

def restore(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    if (root/'state.json').exists():raise ValueError('Restore requires an empty state destination')
    remote=git('ls-remote','--heads','origin','refs/heads/'+BRANCH).decode().strip()
    if not remote:
        (root/'.parent').write_text('')
        print('No data branch yet; bootstrap from reviewed public seed/latest deployment')
        return
    git('fetch','--no-tags','origin',f'refs/heads/{BRANCH}:{REF}')
    parent=git('rev-parse',REF).decode().strip();entries=tree(parent)
    for required in ('latest.json','state.json','manifest.json'):
        if required not in entries:raise ValueError('Incomplete durable data branch: '+required)
    manifest=verify_file('manifest.json',git('show',parent+':manifest.json'))
    files={}
    for name in ('latest.json','state.json'):
        raw=git('show',parent+':'+name);verify_file(name,raw)
        if hashlib.sha256(raw).hexdigest()!=manifest['sha256'][name]:raise ValueError('State manifest hash mismatch')
        files[name]=raw
    for name,raw in files.items():(root/name).write_bytes(raw)
    (root/'.parent').write_text(parent)
    from history import load_state
    load_state(root)
    print(f'Restored {parent[:12]}; {len(entries)} files, {sum(v[1] for v in entries.values())} bytes retained')

def save(root):
    root=Path(root)
    if not (root/'.parent').exists():raise ValueError('Run restore before save to establish an explicit parent')
    parent=(root/'.parent').read_text().strip()
    prior=tree(parent) if parent else {}
    files={name:(root/name).read_bytes() for name in ('latest.json','state.json')}
    for path in sorted((root/'history').rglob('*.json.gz')):
        name=path.relative_to(root).as_posix();raw=path.read_bytes();verify_file(name,raw)
        if name in prior:
            if git('hash-object','--stdin',input=raw).decode().strip()!=prior[name][0]:raise ValueError('Refusing history overwrite')
        else:files[name]=raw
    for name,raw in files.items():verify_file(name,raw)
    manifest={'schema_version':1,'sha256':{n:hashlib.sha256(files[n]).hexdigest() for n in ('latest.json','state.json')},
              'history_files':sum(n.startswith('history/') for n in set(prior)|set(files))}
    files['manifest.json']=(json.dumps(manifest,sort_keys=True)+'\n').encode()
    total=sum(size for name,(_,size) in prior.items() if name not in files)+sum(map(len,files.values()))
    if total>MAX_BYTES:raise ValueError('Public history storage budget exceeded; no history deleted and no push attempted')
    with tempfile.TemporaryDirectory() as temp:
        env={**os.environ,'GIT_INDEX_FILE':str(Path(temp)/'index'),
             'GIT_AUTHOR_NAME':'TerraNepal data collector','GIT_AUTHOR_EMAIL':'actions@users.noreply.github.com',
             'GIT_COMMITTER_NAME':'TerraNepal data collector','GIT_COMMITTER_EMAIL':'actions@users.noreply.github.com'}
        git('read-tree',parent if parent else '--empty',env=env)
        for name,raw in files.items():
            oid=git('hash-object','-w','--stdin',input=raw,env=env).decode().strip()
            git('update-index','--add','--cacheinfo','100644',oid,name,env=env)
        tree_id=git('write-tree',env=env).decode().strip()
        args=['commit-tree',tree_id]+(['-p',parent] if parent else [])
        revision=git(*args,input=b'Retain public observations, revisions and collection evidence\n',env=env).decode().strip()
        git('push','origin',revision+':refs/heads/'+BRANCH,env=env)
    (root/'.parent').write_text(revision)
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('revision='+revision+'\n')
    print(f'Saved {revision}; {total} bytes of {MAX_BYTES} byte history budget')
    if total>MAX_BYTES*.75:print('::warning::Public data branch is above 75% of its storage budget; plan an archive export/migration.')
    return revision

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['restore','save']);parser.add_argument('--root',default='runtime/public-state');args=parser.parse_args()
    {'restore':restore,'save':save}[args.command](args.root)
