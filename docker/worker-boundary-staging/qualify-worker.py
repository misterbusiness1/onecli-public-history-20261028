"""Adversarial checks inside the real worker. Outputs verdicts, never credentials."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

name = sys.argv[1]
token = Path('/run/assigned-agent-token').read_text().strip()
api = urllib.request.build_opener(urllib.request.ProxyHandler({}))
results = []
def request(path, credential=token, headers=None):
    headers = dict(headers or {})
    if credential is not None: headers['Authorization'] = 'Bearer '+credential
    try:
        with api.open(urllib.request.Request('http://127.0.0.1:10254'+path,headers=headers),timeout=8) as res:
            return res.status,json.loads(res.read())
    except urllib.error.HTTPError as error:
        return error.code,{}
def check(label, fn):
    try: good = bool(fn())
    except Exception: good = False
    results.append({'check':label,'pass':good})
def own_config(path='/v1/container-config'):
    status,body=request(path)
    return status == 200 and urllib.parse.urlsplit(body['env']['HTTPS_PROXY']).password == token

env=dict(PATH='/usr/local/bin:/usr/bin:/bin',HOME='/home/worker',
         ONECLI_API_HOST='http://127.0.0.1:10254',ONECLI_AGENT_TOKEN=token)
probe="import os,json,urllib.parse; print(json.dumps({'assigned':urllib.parse.urlsplit(os.environ['HTTPS_PROXY']).password==os.environ['ONECLI_AGENT_TOKEN'],'adminAbsent':'ONECLI_API_KEY' not in os.environ}))"
def native(args=(), changes=None, missing=False):
    actual=dict(env)
    if changes:actual.update(changes)
    if missing:actual.pop('ONECLI_AGENT_TOKEN',None)
    return subprocess.run(['onecli','run',*args,'--no-ca','--','python3','-c',probe],
                          env=actual,capture_output=True,text=True,timeout=15)
def assigned_native(changes=None):
    result=native(changes=changes)
    return result.returncode==0 and json.loads(result.stdout)=={'assigned':True,'adminAbsent':True}
def alias_cannot_escalate():
    result=native(changes={'ONECLI_AGENT':'default'})
    return result.returncode != 0 or json.loads(result.stdout)['assigned'] is True

def no_network_route():
    for host in ['1.1.1.1','172.17.0.1']:
        try:
            with socket.create_connection((host,10254),timeout=1):return False
        except OSError:pass
    return len(Path('/proc/net/route').read_text().splitlines()) == 1

check('assigned identity succeeds without default fallback',own_config)
check('explicit own selector succeeds',lambda:own_config('/v1/container-config?agent='+name))
for selector in ['default','worker-b' if name=='worker-a' else 'worker-a']:
    check('direct API rejects selector '+selector,lambda selector=selector:request('/v1/container-config?agent='+selector)[0]==403)
check('foreign project header denied',lambda:request('/v1/container-config',headers={'X-Project-Id':'foreign-project'})[0]==403)
check('foreign organization header denied',lambda:request('/v1/container-config',headers={'X-Organization-Id':'foreign-org'})[0]==403)
check('missing bearer denied',lambda:request('/v1/container-config',None)[0]==401)
check('invalid bearer denied',lambda:request('/v1/container-config','aoc_'+'0'*64)[0]==401)
check('agent cannot list management identities',lambda:request('/v1/agents')[0]==401)
check('query token cannot become management authentication',lambda:request('/v1/agents?_token='+token,None)[0]==401)
check('native assigned command succeeds',assigned_native)
check('native child strips management key',lambda:assigned_native({'ONECLI_API_KEY':'oc_unusable_staging_sentinel'}))
check('native default override denied',lambda:native(['--agent','default']).returncode!=0)
check('environment alias cannot escalate',alias_cannot_escalate)
check('unsetting token cannot discover administrator login',lambda:native(missing=True).returncode!=0)
check('empty token cannot fall back',lambda:native(changes={'ONECLI_AGENT_TOKEN':''}).returncode!=0)
check('host credential files absent',lambda:all(not Path(p).exists() for p in [
    '/home/ubuntu/.onecli','/home/ubuntu/.paperclip/auth.json',
    '/paperclip/instances/default/data/.paperclip-onecli-home',
    '/var/run/docker.sock','/run/host','/run/worker-b-token','/run/worker-a-token']))
check('server credentials absent from worker environment',lambda:all(k not in os.environ for k in [
    'DATABASE_URL','SECRET_ENCRYPTION_KEY','GATEWAY_INTERNAL_SECRET','ONECLI_API_KEY','NEXTAUTH_SECRET']))
check('no external or host network route',no_network_route)
check('only loopback interface exposed',lambda:set(os.listdir('/sys/class/net'))=={'lo'})
check('native CLI filesystem not writable',lambda:not os.access('/usr/local/bin/onecli',os.W_OK))
check('no effective Linux capabilities',lambda:'CapEff:\t0000000000000000' in Path('/proc/self/status').read_text())
check('no new privileges enforced',lambda:'NoNewPrivs:\t1' in Path('/proc/self/status').read_text())
print(json.dumps({'worker':name,'checks':results,'passed':all(r['pass'] for r in results)}))
sys.exit(0 if all(r['pass'] for r in results) else 1)
