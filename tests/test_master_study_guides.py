"""Standalone unit tests for master-study-guides (build_guide.py and verify_html_quiz.py)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
BUILD_PATH = SKILL_DIR / "scripts" / "build_guide.py"
VERIFY_PATH = SKILL_DIR / "scripts" / "verify_html_quiz.py"
EXAMPLE_SLOTS = SKILL_DIR / "examples" / "minimal_guide.slots.txt"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guide_builder = _load_module("build_guide", BUILD_PATH)
quiz_verifier = _load_module("verify_html_quiz", VERIFY_PATH)


class MasterStudyGuidesTests(unittest.TestCase):
    def test_compile_verify_and_roundtrip_example(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_html = Path(tmp) / "compiled.html"
            extracted = Path(tmp) / "extracted.slots.txt"
            rebuilt = Path(tmp) / "rebuilt.html"

            guide_builder.build(EXAMPLE_SLOTS, out_html)
            rep = quiz_verifier.verify_html_file(out_html, min_questions=12, strict_guide=True, min_per_level=4)
            self.assertTrue(rep["ok"], msg=f"Unexpected errors: {rep['errors']}")

            guide_builder.extract_slots_from_html(out_html, extracted)
            guide_builder.build(extracted, rebuilt)
            self.assertEqual(out_html.read_text(encoding="utf-8"), rebuilt.read_text(encoding="utf-8"))

    def test_edge_cases_and_atomic_cli_write(self) -> None:
        base_raw = EXAMPLE_SLOTS.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            # 1. Code templates {{user.name}}, {{slot.teoria}} in title, HTML entities in h2, Java generics in options
            edge_raw = (
                base_raw.replace(
                    '"title": "Guia Mestra · Exemple Mínim · Transaccions ACID"',
                    '"title": "Test {{slot.teoria}} Guide"',
                )
                .replace(
                    '<h2 id="h-cicle">Cicle de vida d\'una transacció</h2>',
                    '<h2 id="h-cicle">C++ &amp; Java &lt;T&gt;</h2>',
                )
                .replace("<pre><code>", "<pre><code>const tpl = '{{user.name}}';\n")
                .replace('"Atomicitat"', '"List<String>"')
                .replace('"Consistència d\'esquema"', '"List<Integer>"')
            )
            edge_slots = Path(tmp) / "edge.slots.txt"
            edge_slots.write_text(edge_raw, encoding="utf-8")
            edge_html = Path(tmp) / "edge.html"
            guide_builder.build(edge_slots, edge_html)
            html_out = edge_html.read_text(encoding="utf-8")
            self.assertIn("C++ &amp; Java &lt;T&gt;", html_out)
            self.assertNotIn("&amp;amp;", html_out)
            self.assertIn("{{user.name}}", html_out)
            meta_json = json.loads(
                html_out.split('<script type="application/json" id="guide-meta">')[1].split("</script>")[0]
            )
            self.assertEqual(meta_json["title"], "Test {{slot.teoria}} Guide")
            rep = quiz_verifier.verify_html_file(edge_html, min_questions=12, strict_guide=True, min_per_level=4)
            self.assertTrue(rep["ok"], msg=f"Unexpected errors: {rep['errors']}")

            # 2. Booleans rejected and 4/5 letter bias caught globally
            rep_bool = quiz_verifier.audit_quiz(
                [{"id": "q1", "level": True, "q": "Q?", "options": ["A", "B"], "correct": True, "why": "x"}],
                min_questions=1,
            )
            self.assertFalse(rep_bool["ok"])
            short_b = [
                {"id": f"b{i}", "q": f"Q{i}", "options": ["Opt A1", "Opt B2", "Opt C3", "Opt D4"], "correct": 1 if i < 4 else 0}
                for i in range(5)
            ]
            self.assertFalse(quiz_verifier.audit_quiz(short_b, min_questions=5)["ok"])

            # 3. Atomic CLI build does not write invalid guide to disk
            failing = Path(tmp) / "fail.slots.txt"
            failing.write_text(
                base_raw.replace(
                    '<span class="slot" data-ans="COMMIT"></span>',
                    '<span class="slot" data-ans="MISSING_CHIP"></span>',
                ),
                encoding="utf-8",
            )
            never_written = Path(tmp) / "should_not_exist.html"
            res = subprocess.run(
                [sys.executable, str(BUILD_PATH), str(failing), "-o", str(never_written), "--min-questions", "12"],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(res.returncode, 0)
            self.assertFalse(never_written.exists())


if __name__ == "__main__":
    unittest.main()
