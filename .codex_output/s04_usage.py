"""Preserve raw CLI usage, without double counting cached input."""
import json
import sys
from pathlib import Path

report = Path(__file__).resolve().parent / sys.argv[1]
events = [json.loads(line) for line in (report/'generation-events.jsonl').read_text(encoding='utf-8').splitlines() if line]
turns = [e['usage'] for e in events if e.get('type')=='turn.completed' and 'usage' in e]
if not turns:
    raise RuntimeError('No completed-turn usage: do not interpret as zero')
totals = {k:sum(t.get(k,0) for t in turns) for k in set().union(*(t.keys() for t in turns))}
summary = {'scope':'Independent generation session only; evaluator conversation excluded',
           'thread_id':next(e['thread_id'] for e in events if e['type']=='thread.started'),
           'raw_completed_turn_usage':turns, 'totals':totals,
           'total_input_plus_output':totals['input_tokens']+totals['output_tokens'],
           'note':'Cached input is included in input; reasoning output may be included in output. No monetary cost conversion.',
           'cases':{name:{'additional_model_calls':0,'input_tokens':0,'output_tokens':0,
                          'shared_generation_usage':'totals; not allocated or counted once per execution case'}
                    for name in sorted(p.name for p in (report/'evaluation').iterdir() if p.is_dir())}}
(report/'token-usage.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
