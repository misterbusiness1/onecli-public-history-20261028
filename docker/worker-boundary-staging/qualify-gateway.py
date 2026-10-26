"""Synthetic gateway probes. No provider calls or production credentials."""
import ipaddress
import json
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time

root = Path(__file__).resolve().parent
private = root/'private'
manifest = json.loads((private/'manifest.json').read_text())
assert manifest['mode'] == 'synthetic-staging' and manifest['providerConnections'] == 0
results = []
def record(name, value):
    results.append({'check': name, 'pass': bool(value)})
def worker(code):
    p = subprocess.run(['docker','exec','-i','oxfa-boundary-worker-b','python3','-'],
                       input=code, capture_output=True, text=True, timeout=20)
    assert p.returncode == 0, 'Worker probe failed (output withheld)'
    return json.loads(p.stdout)
probe = '''
import base64,json,socket
from pathlib import Path
token=Path('/run/assigned-agent-token').read_text().strip()
def connect(credential):
 auth=base64.b64encode(('dummy:'+credential).encode()).decode()
 with socket.create_connection(('127.0.0.1',10255),timeout=5) as s:
  s.sendall(('CONNECT example.invalid:443 HTTP/1.1\\r\\nHost: example.invalid:443\\r\\nProxy-Authorization: Basic '+auth+'\\r\\n\\r\\n').encode())
  return int(s.recv(4096).split(b' ',2)[1])
print(json.dumps({'assigned':connect(token),'invalid':connect('aoc_'+'0'*64)}))
'''
initial = worker(probe)
record('assigned token establishes gateway tunnel',initial['assigned'] == 200)
record('invalid proxy credential is rejected',initial['invalid'] == 407)
replacement = 'aoc_'+secrets.token_hex(32)
sql = f"UPDATE agents SET access_token='{replacement}',updated_at=now() WHERE id='worker-b';"
p = subprocess.run(['docker','exec','-i','oxfa-boundary-db','psql','-U','boundary','-d','boundary','-v','ON_ERROR_STOP=1'],
                   input=sql,text=True,capture_output=True)
assert p.returncode == 0, 'Fixture rotation failed'
try:
    after = worker(probe)
    record('revoked proxy token is rejected on new CONNECT',after['assigned'] == 407)
finally:
    path = private/'worker-b.token'
    path.chmod(0o600)
    path.write_text(replacement)
    path.chmod(0o400)
    subprocess.run(['docker','restart','oxfa-boundary-worker-b'],check=True,capture_output=True)
for _ in range(30):
    ready = subprocess.run(['docker','exec','oxfa-boundary-worker-b','python3','-c',
        "import socket; socket.create_connection(('127.0.0.1',10255),timeout=1).close()"],capture_output=True)
    if ready.returncode == 0:
        break
    time.sleep(0.2)
else:
    raise RuntimeError('Worker gateway relay did not become ready')
record('replacement gateway credential succeeds',worker(probe)['assigned'] == 200)
# A positive local canary proves the listener works. The worker then tries to
# reach it through an anonymous raw CONNECT tunnel. A provisional HTTP 200 is
# not evidence of connectivity: the listener must observe no connection.
net = json.loads(subprocess.check_output(['docker','network','inspect','oxfa-boundary-backend']))[0]
subnet = ipaddress.ip_network(net['IPAM']['Config'][0]['Subnet'])
host_ip = str(subnet.network_address+1)
listener = socket.socket()
listener.bind(('0.0.0.0',0))
listener.listen(5)
listener.settimeout(4)
port = listener.getsockname()[1]
with socket.create_connection((host_ip,port),timeout=2):
    accepted,_ = listener.accept()
    accepted.close()
record('host canary is reachable from host',True)
seen = []
def accept_probe():
    try:
        conn,_ = listener.accept()
        seen.append(True)
        conn.close()
    except socket.timeout:
        pass
thread = threading.Thread(target=accept_probe)
thread.start()
code = f'''
import json,socket
try:
 with socket.create_connection(('127.0.0.1',10255),timeout=2) as s:
  s.settimeout(2)
  s.sendall(b'CONNECT {host_ip}:{port} HTTP/1.1\\r\\nHost: {host_ip}:{port}\\r\\n\\r\\n')
  s.recv(4096)
  s.sendall(b'isolated-fixture-canary')
  s.recv(4096)
except OSError:pass
print(json.dumps({{'completed':True}}))
'''
worker(code)
thread.join(6)
listener.close()
record('gateway cannot tunnel to host canary',not seen and not thread.is_alive())
(root/'gateway-results.json').write_text(json.dumps(results,indent=2))
print(json.dumps({'checks':results,'passed':all(r['pass'] for r in results)}))
raise SystemExit(0 if all(r['pass'] for r in results) else 1)
