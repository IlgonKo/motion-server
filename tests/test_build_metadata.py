import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts.build_metadata import source_state
from scripts.validate_package import load_build_info


class BuildMetadataTests(unittest.TestCase):
    def test_validation_preserves_original_build_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = dict(version='1.0.0', source_commit='older-build',
                            source_dirty=False, dependencies={'pysoem': '1.1.13'},
                            built_at_utc='2026-11-25T00:00:00+00:00')
            (root/'build-info.json').write_text(json.dumps(original), encoding='utf-8')
            self.assertEqual(load_build_info(root), original)

    def test_missing_provenance_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(FileNotFoundError):
                load_build_info(root)
            (root/'build-info.json').write_text('{}', encoding='utf-8')
            with self.assertRaises(ValueError):
                load_build_info(root)

    def test_source_changes_are_detectable_with_same_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def git(*args):
                subprocess.run(['git', '-C', str(root), *args], check=True,
                               capture_output=True)
            git('init')
            (root/'source.py').write_text('first', encoding='utf-8')
            git('add', '.')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                'commit', '-m', 'initial')
            original = source_state(root)
            (root/'source.py').write_text('second', encoding='utf-8')
            modified = source_state(root)
            self.assertEqual(original['source_commit'], modified['source_commit'])
            self.assertFalse(original['source_dirty'])
            self.assertTrue(modified['source_dirty'])
            self.assertNotEqual(original['source_diff_sha256'], modified['source_diff_sha256'])

    @unittest.skipUnless(sys.platform == 'win32', 'Windows build script')
    def test_existing_package_is_not_removed(self):
        script = Path(__file__).resolve().parents[1]/'scripts/windows/build_exe.ps1'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = root/'parameters.sqlite'
            sentinel.write_bytes(b'preserve existing device data')
            result = subprocess.run([
                'powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                '-File', str(script), '-PackageDirectory', str(root), '-SkipInstall',
            ], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(sentinel.read_bytes(), b'preserve existing device data')


if __name__ == '__main__':
    unittest.main()
