"""Isolated local container/TLS/auth/restart smoke test; no source collection or public listener."""
import contextlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tempfile
import time
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]
IMAGE=os.environ.get('LAB_IMAGE','nepal-disaster-lab:local')
CADDY='caddy:2-alpine@sha256:d8542f48d34a9cf4e4c11a478865229840e87e4c96ea3f439101f31a5d35f75f'

def docker(*args,input=None,check=True):
    result=subprocess.run(['docker',*args],input=input,text=True,capture_output=True,timeout=120)
    if check and result.returncode:raise RuntimeError(result.stderr[-2000:])
    return result.stdout.strip()

def main():
    suffix=uuid.uuid4().hex[:8];network='nepal-test-'+suffix;volume=network+'-data';web=network+'-web';proxy=network+'-proxy'
    password=secrets.token_urlsafe(32);base='https://localhost:8843';results=[]
    with tempfile.TemporaryDirectory(prefix='nepal-docker-smoke-') as t:
        tmp=Path(t);config=tmp/'Caddyfile';config.write_text('https://localhost {\n tls internal\n reverse_proxy web:8765\n}\n')
        docker('network','create',network);docker('volume','create',volume)
        try:
            script=f'''import os,sys,json,time,sqlite3
from pathlib import Path
sys.path[:0]=['/app/disaster_lab','/app/disaster_archive']
from werkzeug.security import generate_password_hash
from archive import Archive
from operations import Operations
assert os.getuid()==10001
assert not Path('/app/disaster_lab/local').exists()
assert not Path('/app/disaster_archive/data').exists()
a=Archive();a.db.close()
state=Path('/data/state');state.mkdir(exist_ok=True)
(state/'owner.json').write_text(json.dumps({{'password_hash':generate_password_hash({password!r}),'version':'smoke-only'}}))
os.chmod(state/'owner.json',0o600)
Operations().heartbeat()
print('Nonroot fixture initialized; no private data embedded in image')
'''
            docker('run','--rm','-i','--mount',f'source={volume},target=/data',IMAGE,'python','-',input=script)
            docker('run','-d','--name',web,'--network',network,'--network-alias','web','--read-only','--tmpfs','/tmp','--cap-drop','ALL','--security-opt','no-new-privileges:true','--mount',f'source={volume},target=/data','-e','NEPAL_PUBLIC_ORIGIN='+base,IMAGE)
            docker('run','-d','--name',proxy,'--network',network,'-p','127.0.0.1:8843:443','--mount',f'type=bind,source={config},target=/etc/caddy/Caddyfile,readonly',CADDY)
            cert=tmp/'root.crt'
            for _ in range(30):
                copied=subprocess.run(['docker','cp',proxy+':/data/caddy/pki/authorities/local/root.crt',str(cert)],capture_output=True)
                if copied.returncode==0:break
                time.sleep(1)
            context=ssl.create_default_context(cafile=cert)
            opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=context),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            def request(path,data=None,token=None):
                headers={};body=None
                if data is not None:
                    body=json.dumps(data).encode();headers={'Content-Type':'application/json','X-Lab-Token':token or '','Origin':base}
                try:
                    with opener.open(urllib.request.Request(base+path,data=body,headers=headers),timeout=15) as r:return r.status,r.read().decode(),dict(r.headers)
                except urllib.error.HTTPError as e:return e.code,e.read().decode(),dict(e.headers)
            for _ in range(30):
                try:
                    if request('/health/live')[0]==200:break
                except (OSError,urllib.error.URLError):pass
                time.sleep(1)
            assert request('/health/live')[0]==200
            assert request('/health/ready')[0]==200
            assert request('/api/actions')[0]==401
            status,html,headers=request('/login');assert status==200
            token=re.search(r'name="token" value="([^"]+)',html).group(1)
            body=urllib.parse.urlencode({'token':token,'password':password}).encode()
            with opener.open(urllib.request.Request(base+'/login',data=body,headers={'Origin':base}),timeout=15) as response:assert response.status==200
            token=json.loads(request('/api/session')[1])['token']
            assert request('/api/actions',{'title':'Isolated container test','kind':'research','status':'open'},token)[0]==201
            results.extend(['nonroot image contains no private archive or state','HTTPS through Caddy with explicitly trusted local CA','anonymous API blocked; owner login and CSRF-protected write succeed'])
            docker('restart',web)
            for _ in range(30):
                if request('/api/actions')[0]==200:break
                time.sleep(1)
            assert len(json.loads(request('/api/actions')[1]))==1
            results.append('session and notebook survive container restart on persistent volume')
            assert request('/api/refresh',{},'invalid')[0]==403
            if os.environ.get('LAB_NODE'):
                env={**os.environ,'LAB_TEST_URL':base,'LAB_TEST_PASSWORD':password}
                subprocess.run([env['LAB_NODE'],str(ROOT/'disaster_lab/production_browser_check.cjs')],env=env,check=True,timeout=120)
                results.append('browser login, authenticated navigation and logout over local TLS')
            assert request('/logout',{},token)[0]==200
            assert request('/api/actions')[0]==401
            results.append('logout denies subsequent private API access')
            report={'checked_at':time.time(),'image':docker('image','inspect',IMAGE,'--format','{{.Id}}'),'results':results}
            (ROOT/'disaster_lab/reports/docker-smoke.json').write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps(report,indent=2))
        finally:
            docker('rm','-f',web,proxy,check=False);docker('volume','rm',volume,check=False);docker('network','rm',network,check=False)

if __name__=='__main__':main()
