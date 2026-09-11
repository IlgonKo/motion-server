"""Offline checks for the RF-019 S02 AI input bundle, not AI generation evaluation."""

import json
import re
import unittest
from pathlib import Path

from motion_server.api.schema_loader import api_contracts


ROOT = Path(__file__).resolve().parents[1]
AI_DOCS = ROOT / "docs" / "ai"


class AiDocumentationTests(unittest.TestCase):
    def test_required_bundle_and_local_links_exist(self):
        expected = {
            "README.md", "configuration.md", "sequence_guide.md",
            "prompts/motion_sequence.md", "prompts/io_sequence.md",
            "prompts/motion_io_sequence.md", "prompts/sequence_gui.md",
        }
        self.assertEqual({p.relative_to(AI_DOCS).as_posix() for p in AI_DOCS.rglob("*.md")}, expected)
        for path in AI_DOCS.rglob("*.md"):
            content = path.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", content):
                with self.subTest(document=path.name, target=target):
                    self.assertNotIn("://", target, "Bundle references must be available offline")
                    self.assertTrue((path.parent / target.split("#")[0]).resolve().exists())

    def test_json_request_examples_match_actual_schema(self):
        count = 0
        for path in AI_DOCS.rglob("*.md"):
            for block in re.findall(r"```json\s*\n(.*?)\n```", path.read_text(encoding="utf-8"), re.S):
                request = json.loads(block)
                with self.subTest(document=path.name, command=request["cmd"]):
                    self.assertEqual(list(api_contracts().request_errors(request["cmd"], request)), [])
                count += 1
        self.assertGreaterEqual(count, 4)

    def test_prompts_include_editable_requirements_and_generation_boundary(self):
        for name in ("motion_sequence.md", "io_sequence.md", "motion_io_sequence.md"):
            content = (AI_DOCS / "prompts" / name).read_text(encoding="utf-8")
            with self.subTest(prompt=name):
                for required in ("[사용자 수정 영역]", "timeout", "실장비", "테스트", "제어권"):
                    self.assertIn(required, content)
        gui = (AI_DOCS / "prompts" / "sequence_gui.md").read_text(encoding="utf-8")
        self.assertIn("동일한 시퀀스 실행 코드", gui)
        self.assertIn("포커스 상실", gui)


if __name__ == "__main__":
    unittest.main()
