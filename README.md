# Study Guides (Agent Skill)

[![CI](https://github.com/XLVII-DEV/study-guides/actions/workflows/ci.yml/badge.svg)](https://github.com/XLVII-DEV/study-guides/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-8c5214.svg)](./LICENSE)
[![100% Offline](https://img.shields.io/badge/Output-100%25%20Offline%20HTML-146c53.svg)](#-features)
[![Zero Dependencies](https://img.shields.io/badge/Python-3.9%2B%20Stdlib%20Only-1f2421.svg)](#-quick-usage-cli)

An open **Agent Skill** (`SKILL.md`) that turns lecture slides, PDFs, notes, or codebases into **single-file, 100% offline interactive HTML study guides** — while cutting LLM output token consumption by **~75–80%**.

👉 **[Live Interactive Demo (GitHub Pages)](https://xlvii-dev.github.io/study-guides/)** · *([docs/index.html](./docs/index.html) compiled straight from `examples/cs_acid_transactions.slots.txt`)*

---

## Why This Skill Exists

Asking an AI agent to "make an interactive HTML study guide" from scratch usually wastes **~37,000+ output tokens** rewriting CSS, dark mode, and JavaScript every time — and still ships broken `innerHTML`, unreadable dark-mode SVGs, print views that dump 10 pages, and quizzes where option `B` is always the longest and correct answer.

**Study Guides fixes both problems architecturally:**

| Metric (Real Syllabus Benchmark) | Hand-written HTML by AI | `study-guides` Slot Compiler | Improvement |
| :--- | :---: | :---: | :---: |
| Lines written by the LLM | `2,387` lines (`138 KB`) | `255` lines (`27 KB` slots) | **`-89%` lines** |
| LLM output tokens consumed | `~37,150` tokens | `~7,382` tokens | **`-80.1%` tokens (`5x` cheaper)** |
| Local build + strict verification | Manual prompt retries | `build_guide.py` in `~60 ms` | **Deterministic `PASS`/`FAIL`** |
| Regressions across guides | Constant CSS/JS drift | Single audited `template.html` | **`0` UI regressions** |

---

## Features

- **Master Professor Pedagogy (4-Move Cards)**: guides agents to explain *intuition first*, *internal mechanism* (with dark-mode-safe `<svg>` + `<ol class="step-trace">`), a *worked example*, and *side-by-side mistake comparisons* (`.compare-grid`) + `.key-takeaway`.
- **3 Visual Presets + Warm Dark Mode**: choose `warm-serif` (Bronze/Ocre reading paper), `ink-editorial` (Ivory + Burgundy), or `slate-tech` (Crisp Slate + Petrol Teal) — all with dark mode, `/` sidebar search, and 1-click `Copy` buttons on code blocks.
- **3-Level Anti-Bias Quiz + Timed Exam Mode**: splits questions into *Foundations*, *Application*, and *Mastery* with runtime Fisher-Yates shuffling, persistent `localStorage` scores (`/10`), active mistake-retry mode, and a **Timed Exam Mode** that hides feedback until submission.
- **1-Click Anki Export (`.tsv`)**: exports every quiz item and `<details class="oral-check">` card directly to an Anki-ready UTF-8 `.tsv` file with level and source tags.
- **Dual-Mode A4 Print**: `🖨️ A4 cheat-sheet` prints only the 1–2 page summary even while browsing in dark mode; `📄 Full guide` prints the full theory + cheat-sheet.
- **Lossless Round-Trip Editing (`--extract`)**: pull editable 6-slot files back out of any compiled guide in milliseconds without cluttering your study folders.
- **7 Native UI Languages**: `en`, `es`, `ca`, `fr`, `de`, `pt`, `it` out of the box (plus full `"ui"` overrides).
- **Strict Structural & Psychometric Verifier (`scripts/verify_html_quiz.py`)**: blocks external CDNs, unsafe DOM/`HTMLParser` vectors, dark-mode-broken SVGs, unsolvable drag-and-drop drills, boolean JSON traps, letter overuse, streaks `>= 3`, and length-biased correct answers with actionable `→ AI Fix:` hints.

---

## Installation

Compatible with **Antigravity, Claude Code, Cursor, OpenAI Codex, Windsurf, and Gemini CLI**:

```bash
npx skills add XLVII-DEV/study-guides
```

Or clone manually into your skills directory:

```bash
git clone https://github.com/XLVII-DEV/study-guides.git ~/.agents/skills/study-guides
```

---

## Example Prompts

- *"Use study-guides to turn my Operating Systems PDFs and lab exercises into an interactive study guide (`en`, undergraduate level)."*
- *"Use study-guides with the `ink-editorial` preset to build an exam prep guide and Anki deck from my Cellular Respiration notes."*
- *"Extract the slots from `Study_Guide_SQL.html` and add 6 harder Level III edge-case questions."*

---

## Quick Usage (CLI)

Compile either included example (`warm-serif` CS or `ink-editorial` Biology):

```bash
python3 scripts/build_guide.py examples/cs_acid_transactions.slots.txt -o Study_Guide_ACID.html --min-questions 12
python3 scripts/build_guide.py examples/biology_cell_respiration.slots.txt -o Study_Guide_Bio.html --min-questions 12
```

Extract slots back from a compiled guide for quick edits:

```bash
python3 scripts/build_guide.py --extract Study_Guide_ACID.html -o acid.slots.txt
```

Run the standalone test suite (Python 3.9+, zero third-party packages):

```bash
python3 -m unittest discover -s tests -v
```

---

## License

MIT — see [LICENSE](./LICENSE).
