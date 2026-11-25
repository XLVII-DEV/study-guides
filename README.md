# Master Study Guides (Agent Skill)

A standard, 100% offline **Agent Skill** (`SKILL.md`) that turns course notes, slides, and exercises into high-retention interactive HTML study guides — while cutting LLM output token usage by **~75–80%**.

## Features
- **Token-Saving Slot Compiler (`scripts/build_guide.py`)**: the AI only authors 6 lightweight content slots (`meta`, `hero`, `teoria`, `practica`, `quiz`, `xuleta`) instead of rewriting 1,000+ lines of CSS/JS every time.
- **Lossless Round-Trip Editing (`--extract`)**: reconstruct editable slots directly from any compiled HTML guide in milliseconds.
- **Warm Academic Serif Aesthetic**: eye-care warm paper light theme (`#fbf7ec`) + warm dark mode (`#141310`) with Bronze/Ocre accents, `Times New Roman` serif headings, collapsible searchable sidebar (`/`), 1-click code Copy buttons, and WCAG 2.1 contrast.
- **4 Core Pedagogical Blocks**:
  1. **Theory & Visual Diagrams**: structured cards, inline dark-mode-safe SVGs, exam-trap callouts, and collapsible oral/paper self-check prompts.
  2. **Adaptive Fill-in Practice**: drag/click chips, text inputs (`Enter` to validate), dropdowns, and per-exercise reset.
  3. **3-Level Anti-Bias Self-Assessment**: Foundations / Application / Mastery, runtime Fisher-Yates shuffling, persistent `localStorage` answers, `/10` score, and active mistake-retry mode.
  4. **Dual-Mode A4 Print**: `🖨️ A4 cheat-sheet` prints a crisp 1–2 page summary (even from dark mode); `📄 Full guide` prints the full theory + cheat-sheet.
- **Strict Structural & Psychometric Verifier (`scripts/verify_html_quiz.py`)**: enforces 100% offline purity, DOM/HTML safety (`HTMLParser`), dark-mode SVG safety, Block 2 solvability, and global + per-level anti-bias balance (letter distribution, streak detection, and option-length parity).

## Installation

### Standard Agent Skill (Antigravity, Claude Code, Cursor, Codex, Gemini CLI)
Clone or copy this folder into your global or workspace skills directory:

```bash
git clone https://github.com/<your-username>/master-study-guides.git ~/.agents/skills/master-study-guides
```

Or install via the open skills CLI:

```bash
npx skills add <your-username>/master-study-guides
```

## Quick Usage (CLI)

Compile the included canonical example:

```bash
python3 scripts/build_guide.py examples/minimal_guide.slots.txt -o Study_Guide_ACID.html --min-questions 12
```

Extract slots back from a compiled guide for fast edits:

```bash
python3 scripts/build_guide.py --extract Study_Guide_ACID.html -o acid.slots.txt
```

## Running Tests

Requires Python 3.9+ (no third-party packages):

```bash
python3 -m unittest discover -s tests -v
```

## License

MIT — see [LICENSE](./LICENSE).
