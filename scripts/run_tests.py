"""Offline unit/mock regression profiles with machine-readable failure evidence."""
import argparse
import json
from pathlib import Path
import platform
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = {'test_ai_pick_place_tcp', 'test_ai_pick_place_extended'}


class ReportResult(unittest.TextTestResult):
    def startTest(self, test):
        self.started = time.monotonic()
        super().startTest(test)

    def stopTest(self, test):
        self.durations.append({'test': test.id(), 'seconds': time.monotonic()-self.started})
        super().stopTest(test)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.durations = []


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('unit', 'integration', 'all'), default='unit')
    parser.add_argument('--report', default='.codex_output/regression/report.json')
    args = parser.parse_args()
    modules, excluded = [], []
    for path in sorted((ROOT/'tests').glob('test_*.py')):
        # Node-RED is explicitly outside the authorized test scope.
        if any(token in path.stem.lower() for token in ('node_red', 'nodered')):
            excluded.append(path.stem)
            continue
        integration = path.stem in INTEGRATION
        if args.profile == 'all' or integration == (args.profile == 'integration'):
            modules.append('tests.'+path.stem)
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    started = time.monotonic()
    result = unittest.TextTestRunner(verbosity=2, resultclass=ReportResult).run(suite)
    report = {'profile': args.profile, 'python': sys.version, 'platform': platform.platform(),
              'seconds': time.monotonic()-started, 'modules': modules, 'excluded': excluded,
              'tests_run': result.testsRun, 'success': result.wasSuccessful(),
              'failures': [{'test': t.id(), 'traceback': msg} for t, msg in result.failures],
              'errors': [{'test': t.id(), 'traceback': msg} for t, msg in result.errors],
              'skipped': [{'test': t.id(), 'reason': msg} for t, msg in result.skipped],
              'durations': result.durations}
    target = Path(args.report)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Report: {target.resolve()}')
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
