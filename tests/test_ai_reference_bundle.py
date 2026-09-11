import re
from pathlib import Path
import tempfile
import unittest

from scripts.windows.ai_reference_bundle import build


class AiReferenceBundleTests(unittest.TestCase):
    def test_bundle_keeps_ai_links_and_does_not_copy_local_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "bundle"
            build(target)
            self.assertFalse(list(target.rglob(".env")))
            self.assertEqual(len(list((target / "motion_server/api/schema").glob("*.json"))), 6)
            self.assertTrue((target / "reference_clients/python/examples/pick_place/program.py").is_file())
            for path in (target / "docs/ai").rglob("*.md"):
                for link in re.findall(r"\[[^\]]+\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                    with self.subTest(file=path.name, link=link):
                        self.assertTrue((path.parent / link.split("#")[0]).resolve().exists())
            with self.assertRaises(FileExistsError):
                build(target)
