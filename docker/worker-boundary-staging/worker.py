"""No inherited operator environment, shared home, external network, or host PID view."""
import os
from pathlib import Path
import subprocess
import time

token = Path('/run/assigned-agent-token').read_text().strip()
if not token.startswith('aoc_') or len(token) != 68:
    raise SystemExit('Assigned staging token missing or malformed')
# This explicit environment is also used by the native CLI qualification probes.
os.environ.clear()
os.environ.update(PATH='/usr/local/bin:/usr/bin:/bin', HOME='/home/worker',
                  ONECLI_API_HOST='http://127.0.0.1:10254', ONECLI_AGENT_TOKEN=token)
children = [subprocess.Popen(['python3','/opt/isolation/relay.py','--listen','tcp',
              '--unix',f'/bridge/{name}.sock','--tcp-port',str(port)])
            for name, port in [('api',10254),('gateway',10255)]]
while all(child.poll() is None for child in children):
    time.sleep(1)
for child in children:
    child.terminate()
raise SystemExit('A fixed transport relay exited; worker is unavailable')
