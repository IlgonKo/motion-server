"""Local configuration and metadata checks; no drive operating interlocks."""
from pathlib import Path
from .sequence import load_json, prepare

CONFIG = Path(__file__).with_name('sequence.json')

def load_config(path=CONFIG):
    c = prepare(load_json(path), {})
    if not isinstance(c['host'], str) or not c['host'].strip():
        raise ValueError('Host required')
    if type(c['port']) is not int or not 1 <= c['port'] <= 65535:
        raise ValueError('Port must be integer 1..65535')
    return c

def check_metadata(data, config):
    metadata = data['axis_metadata']
    for role, item in config['roles'].items():
        actual = next((m for m in metadata if m.get('axis') == item['axis']), None)
        if not actual or actual.get('position_unit') != item['unit']:
            raise ValueError(f'{role}: metadata missing/unit mismatch: {actual}')
    return metadata
