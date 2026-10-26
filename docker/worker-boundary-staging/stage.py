"""Provision synthetic, non-delivering staging only. Never reads production secrets."""
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request

server_image = os.environ.get('ONECLI_STAGING_IMAGE', 'onecli-owner-isolation:cached-auth-20261026')
root = Path(__file__).resolve().parent
private = root/'private'
if private.exists():
    raise SystemExit('Staging state already exists; refusing to replace credentials')
private.mkdir(mode=0o700)
os.umask(0o077)

def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kwargs)

def write(name, text):
    path = private/name
    path.write_text(text)
    path.chmod(0o600)
    return path

password = secrets.token_hex(24)
tokens = {name:'aoc_'+secrets.token_hex(32) for name in ['worker-a','worker-b','default']}
admin = 'oc_'+secrets.token_hex(32)
write('operator-token', admin)
write('db.env', f'POSTGRES_USER=boundary\nPOSTGRES_DB=boundary\nPOSTGRES_PASSWORD={password}\n')
write('app.env', f'DATABASE_URL=postgresql://boundary:{password}@oxfa-boundary-db:5432/boundary\nGATEWAY_BASE_URL=127.0.0.1:10255\nNEXTAUTH_URL=http://127.0.0.1:10374\n')
for name in ['worker-a','worker-b']:
    write(name+'.token', tokens[name]).chmod(0o400)
run('docker','network','create','--internal','oxfa-boundary-backend')
run('docker','run','-d','--name','oxfa-boundary-db','--network','oxfa-boundary-backend',
    '--memory','512m','--cpus','1','--env-file',str(private/'db.env'),'postgres:17-alpine')
for _ in range(60):
    if subprocess.run(['docker','exec','oxfa-boundary-db','pg_isready','-U','boundary'],capture_output=True).returncode == 0:
        break
    time.sleep(1)
else:
    raise SystemExit('Synthetic database did not become ready')
run('docker','run','-d','--name','oxfa-boundary-api','--network','oxfa-boundary-backend',
    '--memory','3g','--cpus','2','--cap-drop','ALL','--security-opt','no-new-privileges','--env-file',str(private/'app.env'),
    server_image)
api_info = json.loads(run('docker','inspect','oxfa-boundary-api').stdout)[0]
api_ip = api_info['NetworkSettings']['Networks']['oxfa-boundary-backend']['IPAddress']
for _ in range(120):
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f'http://{api_ip}:10254/v1/health',timeout=2) as response:
            if response.status == 200:break
    except Exception:pass
    time.sleep(1)
else:
    raise SystemExit('Isolated API did not become ready')
# All identifiers and tokens below belong solely to this disposable test database.
sql = """
INSERT INTO organizations(id,name,slug,updated_at) VALUES
 ('boundary-org','Boundary fixture','boundary-fixture',now());
INSERT INTO projects(id,name,organization_id,updated_at) VALUES
 ('boundary-project','Boundary fixture','boundary-org',now());
INSERT INTO users(id,email,external_auth_id,updated_at) VALUES
 ('boundary-owner','owner@example.test','boundary-owner',now());
INSERT INTO organization_members(organization_id,user_id,user_email,role) VALUES
 ('boundary-org','boundary-owner','owner@example.test','owner');
"""
for name, token in tokens.items():
    sql += f"INSERT INTO agents(id,project_id,name,identifier,access_token,is_default,secret_mode,updated_at) VALUES ('{name}','boundary-project','{name}','{name}','{token}',{'true' if name == 'default' else 'false'},'selective',now());\n"
sql += f"INSERT INTO api_keys(id,scope,project_id,user_id,user_email,key,updated_at) VALUES ('boundary-key','project','boundary-project','boundary-owner','owner@example.test','{admin}',now());"
run('docker','exec','-i','oxfa-boundary-db','psql','-U','boundary','-d','boundary','-v','ON_ERROR_STOP=1',input=sql)
# Restrict the staging gateway too: forwarding CONNECT must not provide an
# indirect route to the live unauthenticated management service.
api_info = json.loads(run('docker','inspect','oxfa-boundary-api').stdout)[0]
db_info = json.loads(run('docker','inspect','oxfa-boundary-db').stdout)[0]
api_ip = api_info['NetworkSettings']['Networks']['oxfa-boundary-backend']['IPAddress']
db_ip = db_info['NetworkSettings']['Networks']['oxfa-boundary-backend']['IPAddress']
run('sudo','-n','iptables','-w','-N','OXFA_BOUNDARY')
run('sudo','-n','iptables','-w','-A','OXFA_BOUNDARY','-m','conntrack','--ctstate','ESTABLISHED,RELATED','-j','RETURN')
run('sudo','-n','iptables','-w','-A','OXFA_BOUNDARY','-d',db_ip,'-p','tcp','--dport','5432','-j','RETURN')
run('sudo','-n','iptables','-w','-A','OXFA_BOUNDARY','-j','DROP')
run('sudo','-n','iptables','-w','-I','DOCKER-USER','1','-s',api_ip,'-j','OXFA_BOUNDARY')
run('sudo','-n','iptables','-w','-I','INPUT','1','-s',api_ip,'-m','conntrack','--ctstate','NEW','-j','DROP')
write('firewall.json',json.dumps({'apiIP':api_ip,'dbIP':db_ip,'chain':'OXFA_BOUNDARY'}))
# Relays accept only these fixed staging destinations. Workers have no external IP route.
bridge = private/'bridge'
bridge.mkdir(mode=0o700)
relay_pids=[]
for name, port in [('api',10254),('gateway',10255)]:
    with (private/(name+'-relay.log')).open('w') as output:
        child = subprocess.Popen([sys.executable,str(root/'relay.py'),'--listen','unix',
                     '--unix',str(bridge/(name+'.sock')),'--tcp-host',api_ip,'--tcp-port',str(port)],
                     stdout=output,stderr=output,start_new_session=True)
        relay_pids.append(child.pid)
write('relay-pids.json', json.dumps(relay_pids))
for _ in range(30):
    if all((bridge/(name+'.sock')).exists() for name in ['api','gateway']):break
    time.sleep(.1)
else:raise SystemExit('Fixed staging relays unavailable')
for name in ['worker-a','worker-b']:
    run('docker','run','-d','--name','oxfa-boundary-'+name,'--network','none','--init',
        '--user','1000:1000','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
        '--pids-limit','64','--memory','256m','--cpus','0.5',
        '--tmpfs','/tmp:rw,nosuid,nodev,noexec,size=64m,uid=1000,gid=1000',
        '--tmpfs','/home/worker:rw,nosuid,nodev,size=16m,uid=1000,gid=1000',
        '--tmpfs','/workspace:rw,nosuid,nodev,size=64m,uid=1000,gid=1000',
        '--mount',f'type=bind,src={bridge},dst=/bridge,readonly',
        '--mount',f'type=bind,src={private/(name+".token")},dst=/run/assigned-agent-token,readonly',
        'oxfa-boundary-worker:106ca2b')
write('manifest.json',json.dumps({'mode':'synthetic-staging','serverImage':server_image,'serverImageId':api_info['Image'],
    'cliSource':'106ca2b','workers':['oxfa-boundary-worker-a','oxfa-boundary-worker-b'],
    'providerConnections':0,'productionChanges':False},indent=2))
print('Isolated staging provisioned. No production credentials or provider connections.')
