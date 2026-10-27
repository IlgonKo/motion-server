"""External Codex invocation; no user-unapproved generation deadline."""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

report = Path(__file__).resolve().parent / sys.argv[1]
env = json.loads((report/'environment.json').read_text(encoding='utf-8'))
workspace = Path(env['workspace'])
command = [shutil.which('codex'), 'exec', '--ignore-user-config', '--skip-git-repo-check',
           '--sandbox', 'workspace-write', '-c', 'windows.sandbox="elevated"',
           '-c', 'sandbox_workspace_write.network_access=true', '--json',
           '-o', str(report/'generation-final.txt'), '-']
started = time.time()
with (report/'generation-events.jsonl').open('w',encoding='utf-8') as output, \
     (report/'generation-stderr.txt').open('w',encoding='utf-8') as errors:
    process = subprocess.Popen(command,cwd=workspace,stdin=subprocess.PIPE,stdout=output,stderr=errors,
                               text=True,encoding='utf-8')
    process.communicate((workspace/'prompt.txt').read_text(encoding='utf-8'))
    outcome = 'finished'
duration = time.time()-started
(report/'invocation.json').write_text(json.dumps({'command':command,'exit_code':process.returncode,
    'outcome':outcome,'duration_seconds':duration,'started_unix':started},indent=2),encoding='utf-8')
if (workspace/'generated').exists():
    shutil.copytree(workspace/'generated',report/'submitted',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
print(outcome, process.returncode, duration, flush=True)
