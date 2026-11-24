"""Offline public documentation contract check; never sends API requests."""
import json
from pathlib import Path
import re

from motion_server.api.schema_loader import api_contracts
from motion_server.api.specification import command_names
from motion_server.handlers.command.registry import COMMAND_HANDLERS
from motion_server.handlers.status.registry import STATUS_HANDLERS
from motion_server.handlers.authority.registry import AUTHORITY_HANDLERS

ROOT = Path(__file__).resolve().parents[1]


def json_values(block):
    decoder = json.JSONDecoder()
    while block.strip():
        block = block.lstrip()
        value, end = decoder.raw_decode(block)
        yield value
        block = block[end:]


def check():
    errors = []
    source = (ROOT / 'docs/motion_server_api_basic.md').read_text(encoding='utf-8')
    names = command_names()
    routes = set(COMMAND_HANDLERS) | set(STATUS_HANDLERS) | set(AUTHORITY_HANDLERS)
    if names != routes:
        errors.append(f'Schema/registry mismatch: {sorted(names ^ routes)}')
    # Plain-text namespace lists form the documented command inventory.
    documented = set()
    for block in re.findall(r'```text\s*\n(.*?)\n```', source, re.S):
        documented.update(re.findall(r'^system/[a-zA-Z_/]+$', block, re.M))
    documented.discard('system/feedback')
    if names != documented:
        errors.append(f'Document command inventory: missing={sorted(names-documented)} unknown={sorted(documented-names)}')
    count = 0
    for number, block in enumerate(re.findall(r'```json\s*\n(.*?)\n```', source, re.S), 1):
        try:
            for value in json_values(block):
                count += 1
                if not isinstance(value, dict):
                    continue
                if 'cmd' in value:
                    if value['cmd'] not in names:
                        raise ValueError(f'Unknown command {value["cmd"]}')
                    for error in api_contracts().request_errors(value['cmd'], value):
                        errors.append(f'JSON example {number}: {error.message}')
                elif value.get('type') in names:
                    api_contracts().response_validator(value['type']).validate(value)
                elif value.get('type') == 'command_rejected' or 'ok' in value:
                    raise ValueError('Legacy response envelope')
        except Exception as error:
            errors.append(f'JSON example {number}: {error}')
    if not count:
        errors.append('No JSON examples found')
    return errors, count


def main():
    errors, count = check()
    for error in errors:
        print(error)
    print(f'API documentation: {len(command_names())} commands, {count} JSON examples, {len(errors)} errors')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
