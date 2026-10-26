"""Launch any worker command with only its assigned capability and clean environment."""
import os
from pathlib import Path
import sys
if len(sys.argv) < 2:
    raise SystemExit('Worker command required')
token = Path('/run/assigned-agent-token').read_text().strip()
if len(token) != 68 or not token.startswith('aoc_'):
    raise SystemExit('Assigned capability unavailable')
env = dict(PATH='/usr/local/bin:/usr/bin:/bin', HOME='/home/worker',
           ONECLI_API_HOST='http://127.0.0.1:10254', ONECLI_AGENT_TOKEN=token)
os.execvpe(sys.argv[1], sys.argv[1:], env)
