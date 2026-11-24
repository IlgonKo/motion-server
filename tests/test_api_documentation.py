import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from scripts.check_api_docs import check
from scripts.check_api_docs import ROOT


class ApiDocumentationTest(unittest.TestCase):
    def test_public_inventory_and_examples_match_schema_and_handlers(self):
        errors, count = check()
        self.assertGreater(count, 0)
        self.assertEqual(errors, [])

    def test_command_inventory_drift_is_rejected(self):
        source = (ROOT/'docs/motion_server_api_basic.md').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'docs').mkdir()
            (root/'docs/motion_server_api_basic.md').write_text(
                source.replace('system/axis/enable\n', 'system/axis/not_supported\n'), encoding='utf-8')
            with patch('scripts.check_api_docs.ROOT', root):
                errors, _ = check()
        self.assertTrue(any('Document command inventory' in error for error in errors))

    def test_numeric_string_example_is_rejected(self):
        source = (ROOT/'docs/motion_server_api_basic.md').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'docs').mkdir()
            (root/'docs/motion_server_api_basic.md').write_text(
                source+'\n```json\n{"cmd":"system/axis/enable","axis":"0"}\n```\n', encoding='utf-8')
            with patch('scripts.check_api_docs.ROOT', root):
                errors, _ = check()
        self.assertTrue(any('JSON example' in error for error in errors))
