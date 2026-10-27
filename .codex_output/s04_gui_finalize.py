"""Archive usage and source integrity without mutating generation artifacts."""
import hashlib
import json
from pathlib import Path
import sys

report = Path(__file__).resolve().parent/sys.argv[1]
env = json.loads((report/'environment.json').read_text())
workspace = Path(env['workspace'])
manifest = json.loads((report/'manifest.json').read_text())
mismatches = [name for name,digest in manifest.items()
              if hashlib.sha256((workspace/name).read_bytes()).hexdigest()!=digest]
events=[json.loads(line) for line in (report/'generation-events.jsonl').read_text(encoding='utf-8').splitlines() if line]
usage=[e['usage'] for e in events if e.get('type')=='turn.completed']
totals={key:sum(u.get(key,0) for u in usage) for key in set().union(*(u.keys() for u in usage))}
cases={}
for base in ('evaluation','evaluation-recheck'):
    for path in (report/base).glob('*/result.json'):
        cases[str(path.relative_to(report))]={'additional_model_calls':0,'input_tokens':0,'output_tokens':0}
summary={'scope':'Independent generation only; evaluator conversation excluded',
         'thread_id':next(e['thread_id'] for e in events if e['type']=='thread.started'),
         'totals':totals,'total_input_plus_output':totals['input_tokens']+totals['output_tokens'],
         'note':'Cached input included in input, not added twice; reasoning is not added again.',
         'execution_cases':cases}
(report/'token-usage.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
audit={'supplied_files':len(manifest),'mismatches':mismatches,
       'snapshots':len(list((report/'snapshots').iterdir())),
       'final_python_copy_mismatches':[str(p.relative_to(workspace/'generated')) for p in (workspace/'generated').rglob('*.py')
           if p.read_bytes()!=(report/'submitted'/p.relative_to(workspace/'generated')).read_bytes()]}
(report/'integrity.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
print(json.dumps({'usage':summary,'integrity':audit},indent=2))
