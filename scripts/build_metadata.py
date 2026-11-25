"""Capture provenance at build time; package validation must never recreate it."""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import subprocess

from motion_server.version import VERSION


def source_state(root):
    def git(*args):
        return subprocess.check_output(['git', '-C', str(root), *args])
    changes = git('diff', 'HEAD', '--binary')
    return {
        'source_commit': git('rev-parse', 'HEAD').decode().strip(),
        'source_dirty': bool(changes),
        'source_diff_sha256': hashlib.sha256(changes).hexdigest(),
    }


def capture(root):
    return {
        'version': VERSION,
        'audience': 'internal-dt-demo',
        'built_at_utc': datetime.now(timezone.utc).isoformat(),
        **source_state(root),
        'python': platform.python_version(),
        'platform': platform.platform(),
        'dependencies': dict(sorted(
            (dist.metadata['Name'], dist.version) for dist in metadata.distributions()
            if dist.metadata['Name']
        )),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.verify:
        recorded = json.loads(args.output.read_text(encoding='utf-8'))
        if any(recorded[key] != value for key, value in source_state(root).items()):
            parser.error('Tracked source changed during build; rebuild the package')
    else:
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(capture(root), stream, indent=2)


if __name__ == '__main__':
    main()
