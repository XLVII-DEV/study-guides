---
name: study-guides
description: >-
  Builds high-retention, 100% offline interactive HTML study guides ("study guide",
  "cheat-sheet", "exam prep", "flashcards", "guia mestra") for any subject, language,
  and academic level. Uses a token-saving 6-slot template compiler with round-trip
  extraction, 3 visual presets with dark mode, master-professor explanations,
  adaptive fill-in drills, persistent 3-level anti-bias quizzes with timed exam
  mode, 1-click Anki (.tsv) export, and a printable A4 cheat-sheet. Do not use for
  short plain-text Q&A, raw Markdown notes, or general web-app UI prototypes.
---

# Study Guides

> **GOLDEN RULE FOR THE AGENT**: **NEVER** hand-write a full HTML document, CSS, sidebar, or JavaScript engine from scratch. The entire visual and interactive layer lives in [`assets/template.html`](./assets/template.html). Author only a lightweight **6-slot** content file and compile it with [`scripts/build_guide.py`](./scripts/build_guide.py), which handles theme presets, timed exam mode, Anki export, and strict structural/anti-bias validation in one command.

---

## Deterministic 4-Step Workflow

### Step 0 · Minimal Context Gate & Level Calibration
1. **Ensure 3 parameters** before reading long PDFs or searching externally:
   - **`language`**: HTML `<html lang="...">` and output language (`en`, `es`, `ca`, `fr`, `de`, `pt`, `it` supported out of the box, or custom `"ui"`).
   - **`subject`**: exact topic, module, or syllabus.
   - **`level`**: academic level — calibrate depth and teaching tone accordingly:
     - *High School / Intro*: concrete everyday analogies before formal notation; break every calculation or mechanism into explicit step-by-step traces.
     - *Vocational (CFGS) / Undergraduate*: balance intuitive mental models with exact terminology, API/formula contracts, and realistic exam traps.
     - *Advanced / Certification / Oral Defense*: emphasize architectural trade-offs, subtle edge cases, performance/security failure modes, and live "what happens if we change X?" scenarios.
   - **Zero-friction rule**: never re-ask parameters already given in the prompt or workspace rules.
2. **Local inventory first**: inspect existing user notes, slides, exercises, and code before external research. Only fetch external references (calibrated to `level`) to fill syllabus gaps.

### Step 1 · Edit Mode vs New Guide Mode
- **Updating an existing guide** built with this skill:
  Extract its editable slots instead of reading the full compiled HTML:
  ```bash
  python3 scripts/build_guide.py --extract "<Existing_Guide.html>" -o "<temp>/guide.slots.txt"
  ```
  Edit only the needed slots and run Step 3.
- **Creating a new guide**:
  Read [references/html-study-architecture.md](./references/html-study-architecture.md) and follow [examples/cs_acid_transactions.slots.txt](./examples/cs_acid_transactions.slots.txt) or [examples/biology_cell_respiration.slots.txt](./examples/biology_cell_respiration.slots.txt).

### Step 2 · Author the 6 Slots ("Master Professor" Pedagogy)
Teach like an extraordinary classroom professor, not a dry encyclopedia. Never dump lists of isolated definitions.

1. **`meta`** (JSON): `{"lang": "en", "themePreset": "warm-serif", "title": "...", "topbarMeta": "...", "storageKey": "study_..."}`
   - Presets: `"warm-serif"` (default: Bronze/Ocre, warm paper, Times serif), `"ink-editorial"` (ivory + burgundy for law/humanities), `"slate-tech"` (crisp slate + petrol teal for engineering/STEM). All presets include dark mode and dark-safe A4 printing.
2. **`hero`** (HTML): `.eyebrow`, `<h1>`, crisp scope paragraph, and `.summary-strip` with `.pill-box` items.
3. **`teoria`** (HTML — **Block 1**): `<section class="card" id="t-...">` with `<h2 id="h-...">` (`Block 1 · 01...`). Follow the **4-Move Card Structure**:
   - **Move 1 · Intuition first**: state what real problem this concept solves (1–2 sentences) before introducing formal definitions.
   - **Move 2 · Mechanism & Visual**: show how it works internally via dark-mode-safe `<svg>` (`style="fill:var(--ink)"`), `<ol class="step-trace">` whiteboard traces, or comparison tables.
   - **Move 3 · Worked Example**: walk through concrete input → intermediate state → final output (pulled from real course exercises when available).
   - **Move 4 · Contrast & Takeaway**: pair `<div class="compare-grid">` (`Common mistake` vs `Right way`) or `.callout.trap` with a closing `<div class="key-takeaway"><strong>Key takeaway:</strong> ...</div>`.
   - Use `<span class="src-tag">Source: ...</span>` for traceability, `<pre><code>` for code (auto-gets Copy button), and optional `<details class="oral-check">` for active recall / oral exam practice (also exported to Anki `.tsv`).
4. **`practica`** (HTML — **Block 2**): `.exercise` blocks mixing `.chip[data-val]` + `.slot[data-ans]`, `input.field[data-ans]`, and `select.field[data-ans]` (alternatives separated by `|`).
5. **`quiz`** (pure JSON, no `<script>` or Markdown fences — **Block 3**): array of `{id, level, q, options, correct, why, src?}` across `1` (Foundations), `2` (Application), and `3` (Mastery); recommended `6` questions per level (`18` total).
   - **2-Layer Diagnostic `why` Rule**: never just restate the correct option. Write 2 concise sentences: *(a)* the rule that proves the right answer, and *(b)* why the most tempting distractor misleads.
6. **`xuleta`** (HTML — **Block 4**): ultra-dense pure-HTML tables and rules designed to fit cleanly on **1–2 A4 pages** when printing via `Cmd/Ctrl + P` (`@media print`).

### Step 3 · Compile & Strictly Verify (Single Command)
Run `build_guide.py` (writes atomically via temp file, injects round-trip markers, and runs `verify_html_quiz.py --strict-guide` — do **not** run `verify_html_quiz.py` separately):

```bash
python3 scripts/build_guide.py "<content.slots.txt>" -o "<output>/Study_Guide_<Topic>.html" --min-questions 18
```

- If verification exits non-zero, follow each `→ AI Fix:` hint, edit `.slots.txt`, and re-run until `[PASS]` (`exit 0`).
