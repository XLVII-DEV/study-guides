"""Standalone unit tests for study-guides (build_guide.py, verify_html_quiz.py, and template.html)."""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
BUILD_PATH = SKILL_DIR / "scripts" / "build_guide.py"
VERIFY_PATH = SKILL_DIR / "scripts" / "verify_html_quiz.py"
EXAMPLES_DIR = SKILL_DIR / "examples"
EXAMPLE_SLOTS = EXAMPLES_DIR / "cs_acid_transactions.slots.txt"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


guide_builder = _load_module("build_guide", BUILD_PATH)
quiz_verifier = _load_module("verify_html_quiz", VERIFY_PATH)


class StudyGuidesTests(unittest.TestCase):
    def test_all_examples_compile_verify_and_roundtrip(self) -> None:
        slot_files = sorted(EXAMPLES_DIR.glob("*.slots.txt"))
        self.assertGreaterEqual(len(slot_files), 2)
        node_bin = shutil.which("node")

        with tempfile.TemporaryDirectory() as tmp:
            for slot_file in slot_files:
                out_html = Path(tmp) / f"{slot_file.stem}.html"
                extracted = Path(tmp) / f"{slot_file.stem}.extracted.txt"
                rebuilt = Path(tmp) / f"{slot_file.stem}.rebuilt.html"

                guide_builder.build(slot_file, out_html)
                rep = quiz_verifier.verify_html_file(out_html, min_questions=12, strict_guide=True, min_per_level=4)
                self.assertTrue(rep["ok"], msg=f"{slot_file.name} errors: {rep['errors']}")

                guide_builder.extract_slots_from_html(out_html, extracted)
                guide_builder.build(extracted, rebuilt)
                self.assertEqual(out_html.read_text(encoding="utf-8"), rebuilt.read_text(encoding="utf-8"))

                html_text = out_html.read_text(encoding="utf-8")
                self.assertIn("btnExportAnki", html_text)
                self.assertIn("btnExportProgress", html_text)
                self.assertIn("=== STUDY-GUIDES PROGRESS v1 ===", html_text)
                self.assertIn("btnExamMode", html_text)
                self.assertNotIn("btnPrint", html_text)
                self.assertIn('<svg class="ico', html_text)
                for banned_emoji in ("\U0001f319", "\u2600\ufe0f", "\U0001f5a8", "\U0001f4c4", "\u23f1", "\U0001f4e5", "\u274c", "\u2705"):
                    self.assertNotIn(banned_emoji, html_text)

                if node_bin:
                    js_file = Path(tmp) / f"{slot_file.stem}.js"
                    js_file.write_text(re.findall(r"<script>(.*?)</script>", html_text, re.S)[-1], encoding="utf-8")
                    res = subprocess.run([node_bin, "--check", str(js_file)], capture_output=True, text=True)
                    self.assertEqual(res.returncode, 0, msg=res.stderr)

    def test_presets_and_seven_languages(self) -> None:
        base_raw = EXAMPLE_SLOTS.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            for preset in ("warm-serif", "ink-editorial", "slate-tech"):
                raw = base_raw.replace('"themePreset": "warm-serif"', f'"themePreset": "{preset}"')
                p = Path(tmp) / f"{preset}.slots.txt"
                p.write_text(raw, encoding="utf-8")
                out = Path(tmp) / f"{preset}.html"
                guide_builder.build(p, out)
                self.assertIn(f'data-preset="{preset}"', out.read_text(encoding="utf-8"))

            bad_raw = base_raw.replace('"themePreset": "warm-serif"', '"themePreset": "neon-cyber"')
            bad_p = Path(tmp) / "bad_preset.slots.txt"
            bad_p.write_text(bad_raw, encoding="utf-8")
            with self.assertRaises(SystemExit):
                guide_builder.build(bad_p, Path(tmp) / "bad.html")

            for lang in ("en", "es", "ca", "fr", "de", "pt", "it"):
                l_raw = base_raw.replace('"lang": "en"', f'"lang": "{lang}"')
                lp = Path(tmp) / f"{lang}.slots.txt"
                lp.write_text(l_raw, encoding="utf-8")
                out = Path(tmp) / f"{lang}.html"
                guide_builder.build(lp, out)
                self.assertIn(f'<html lang="{lang}"', out.read_text(encoding="utf-8"))
                for key in ("exportProgress", "exportProgressHint", "progressCopied", "progressSaved"):
                    self.assertTrue(guide_builder.UI_DEFAULTS[lang].get(key), msg=f"{lang} missing UI label {key}")

    def test_edge_cases_english_hints_and_atomic_cli_write(self) -> None:
        base_raw = EXAMPLE_SLOTS.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            edge_raw = (
                base_raw.replace(
                    '"title": "Study Guide · Database Transactions & ACID Guarantees"',
                    '"title": "Test {{slot.teoria}} Guide"',
                )
                .replace(
                    '<h2 id="h-lifecycle">Why Transactions Exist &amp; How They Execute</h2>',
                    '<h2 id="h-lifecycle">C++ &amp; Java &lt;T&gt;</h2>',
                )
                .replace("<pre><code>", "<pre><code>const tpl = '{{user.name}}';\n")
                .replace('"Atomicity"', '"List<String>"')
                .replace('"Schema Consistency checks"', '"List<Integer>"')
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

            # Booleans rejected and 4/5 letter bias caught with English AI Fix hints
            rep_bool = quiz_verifier.audit_quiz(
                [{"id": "q1", "level": True, "q": "Q?", "options": ["A", "B"], "correct": True, "why": "x"}],
                min_questions=1,
            )
            self.assertFalse(rep_bool["ok"])
            short_b = [
                {"id": f"b{i}", "q": f"Q{i}", "options": ["Opt A1", "Opt B2", "Opt C3", "Opt D4"], "correct": 1 if i < 4 else 0}
                for i in range(5)
            ]
            rep_b = quiz_verifier.audit_quiz(short_b, min_questions=5)
            self.assertFalse(rep_b["ok"])
            self.assertTrue(any("AI Fix:" in e for e in rep_b["errors"]))

            # Atomic CLI build does not leave broken file on disk
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
            self.assertIn("AI Fix:", res.stdout + res.stderr)


if __name__ == "__main__":
    unittest.main()
