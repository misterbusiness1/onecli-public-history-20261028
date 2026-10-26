"""Host-side staging checks. Never uses a production token or provider connection."""
import base64
import ipaddress
import json
import os
from pathlib import Path
import secrets
import subprocess
import urllib.request

root=Path(__file__).resolve().parent
private=root/'private'
manifest=json.loads((private/'manifest.json').read_text())
assert manifest['mode']=='synthetic-staging' and manifest['providerConnections']==0
results=[]
def run(args, **kwargs):
    return subprocess.run(args,capture_output=True,text=True,**kwargs)
def inspect(name):
    return json.loads(subprocess.check_output(['docker','inspect',name]))[0]
def record(name,value):
    results.append({'check':name,'pass':bool(value)})
app=inspect('oxfa-boundary-api')
worker_a=inspect('oxfa-boundary-worker-a')
worker_b=inspect('oxfa-boundary-worker-b')
api_ip=app['NetworkSettings']['Networks']['oxfa-boundary-backend']['IPAddress']
firewall=json.loads((private/'firewall.json').read_text())
record('firewall remains bound to the staged API',firewall['apiIP']==api_ip)
record('forwarding restriction installed',run(['sudo','-n','iptables','-w','-C','DOCKER-USER','-s',api_ip,'-j','OXFA_BOUNDARY']).returncode==0)
record('host access restriction installed',run(['sudo','-n','iptables','-w','-C','INPUT','-s',api_ip,'-m','conntrack','--ctstate','NEW','-j','DROP']).returncode==0)
record('gateway drops other forwarded destinations',run(['sudo','-n','iptables','-w','-C','OXFA_BOUNDARY','-j','DROP']).returncode==0)
namespace_ids=[]
for item in [worker_a,worker_b]:
    name=item['Name'].lstrip('/')
    config=item['HostConfig']
    record(name+' uses no external network',config['NetworkMode']=='none')
    record(name+' has no host PID namespace',not config['PidMode'])
    record(name+' root filesystem is read-only',config['ReadonlyRootfs'])
    destinations={entry['Destination'] for entry in item['Mounts']}
    record(name+' exposes only its capability and fixed sockets',destinations=={'/bridge','/run/assigned-agent-token'})
    namespace_ids.append(os.readlink(f"/proc/{item['State']['Pid']}/ns/pid"))
record('workers and host have distinct PID namespaces',len(set(namespace_ids+[os.readlink('/proc/self/ns/pid')]))==3)
# Operator API access must continue to work, but its credential remains host-only.
admin=(private/'operator-token').read_text().strip()
request=urllib.request.Request(f'http://{api_ip}:10254/v1/agents',headers={'Authorization':'Bearer '+admin})
with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=10) as response:
    record('authenticated operator management still works',response.status==200)
# Rotate a fixture worker token. Check both route and native-client behavior before
# provisioning the replacement. No production identity or stored send is modified.
replacement='aoc_'+secrets.token_hex(32)
sql=f"UPDATE agents SET access_token='{replacement}',updated_at=now() WHERE id='worker-b';"
p=run(['docker','exec','-i','oxfa-boundary-db','psql','-U','boundary','-d','boundary','-v','ON_ERROR_STOP=1'],input=sql)
assert p.returncode==0,'Fixture revocation failed'
revocation_probe="""
import os,json,urllib.request,urllib.error,subprocess
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
request=urllib.request.Request('http://127.0.0.1:10254/v1/container-config',headers={'Authorization':'Bearer '+os.environ['ONECLI_AGENT_TOKEN']})
try:
 with opener.open(request,timeout=8) as r:status=r.status
except urllib.error.HTTPError as e:status=e.code
p=subprocess.run(['onecli','run','--no-ca','--','true'],capture_output=True,timeout=15)
print(json.dumps({'apiDenied':status==401,'nativeDenied':p.returncode!=0}))
"""
try:
    p=run(['docker','exec','-i','oxfa-boundary-worker-b','python3','/opt/isolation/run.py','python3','-'],input=revocation_probe,timeout=30)
    proof=json.loads(p.stdout)
    record('revoked token is denied by the API',proof['apiDenied'])
    record('revoked native token cannot fall back',proof['nativeDenied'])
finally:
    path=private/'worker-b.token'
    path.chmod(0o600)
    path.write_text(replacement)
    path.chmod(0o400)
    p=run(['docker','restart','oxfa-boundary-worker-b'])
    assert p.returncode==0,'Replacement worker restart failed'
(root/'host-results.json').write_text(json.dumps(results,indent=2))
print(json.dumps({'checks':results,'passed':all(item['pass'] for item in results)}))
raise SystemExit(0 if all(item['pass'] for item in results) else 1)
