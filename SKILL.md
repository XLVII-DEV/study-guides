---
name: master-study-guides
description: >-
  Builds high-retention, 100% offline interactive HTML study guides ("study guide",
  "cheat-sheet", "exam prep") for any subject, language, and academic level in the
  Warm Academic Serif (Bronze/Ocre + dark mode) aesthetic. Uses a token-saving
  slot template compiler with round-trip extraction, adaptive fill-in drills,
  persistent 3-level anti-bias quizzes, and a printable A4 cheat-sheet.
---

# Master Study Guides

> **GOLDEN RULE FOR THE AGENT**: **NEVER** hand-write a full HTML document, CSS, sidebar, or JavaScript engine from scratch. The entire visual and interactive layer lives in [`assets/template.html`](./assets/template.html). Your only job is to author a **6-slot** content file and compile it with [`scripts/build_guide.py`](./scripts/build_guide.py), which automatically runs all structural, security, and anti-bias checks before writing the output file.

---

## Deterministic 4-Step Workflow

### Step 0 · Minimal Context Gate & Local Inventory
1. **Ensure 3 parameters** before reading long PDFs or searching externally:
   - **`language`**: HTML `<html lang="...">` and content language (`en`, `es`, `ca`, `fr`, etc.).
   - **`subject`**: exact subject or module.
   - **`level`**: academic level (High School, Vocational/CFGS, University, Certification, etc.) to calibrate depth and rigor.
   - **Zero-friction rule**: never re-ask values already present in the prompt or workspace rules.
2. **Local inventory first**: inspect existing notes, slides, exercises, and code in the user's workspace before searching externally. Only supplement with external research calibrated to `level` when local materials have gaps.

### Step 1 · Edit Mode vs New Guide Mode
- **Updating an existing guide** built with this skill:
  Extract its editable slots instead of reading the full compiled HTML:
  ```bash
  python3 scripts/build_guide.py --extract "<Existing_Guide.html>" -o "<temp>/guide.slots.txt"
  ```
  Edit only the needed slots and jump to Step 3.
- **Creating a new guide**:
  Read [references/html-study-architecture.md](./references/html-study-architecture.md) and follow [examples/minimal_guide.slots.txt](./examples/minimal_guide.slots.txt) as the exact template.

### Step 2 · Author the 6 Slots ("Master Professor" Tone)
Write as an extraordinary, straight-to-the-point professor: zero motivational fluff, clear mental models explaining *why*, real examples from the course notes/exercises, and brief source tags (`<span class="src-tag">Source: ...</span>` and `"src"` in quiz JSON).

The content file must contain exactly these 6 `<!-- @slot NAME -->` markers:
1. **`meta`** (JSON): `{"lang": "en", "title": "...", "topbarMeta": "...", "storageKey": "study_..."}`.
2. **`hero`** (HTML): `.eyebrow`, `<h1>`, concise scope summary, and `.summary-strip` with `.pill-box` items.
3. **`teoria`** (HTML — **Block 1**): `<section class="card" id="t-...">` cards with `<h2 id="h-...">` (`Block 1 · 01...`), comparison tables, `<pre><code>` blocks (automatically get a *Copy* button), inline `<svg>` diagrams using CSS variables (`style="fill:var(--ink)"`, never hardcoded `#000`), `.callout.trap` exam-pitfall callouts, and optional `<details class="oral-check">` oral/paper self-check cards.
4. **`practica`** (HTML — **Block 2**): `.exercise` blocks adapted to the subject mixing `.chip[data-val]` + `.slot[data-ans]`, `input.field[data-ans]`, and `select.field[data-ans]` (alternatives separated by `|`).
5. **`quiz`** (pure JSON, no `<script>` tags or Markdown fences — **Block 3**): array of `{id, level, q, options, correct, why, src?}` split across **3 levels** (`1` Foundations, `2` Application, `3` Mastery; recommended `6` questions per level = `18` total).
6. **`xuleta`** (HTML — **Block 4**): compact golden-rules and pitfalls summary designed to fit cleanly on **1–2 A4 pages** when printing.

### Step 3 · Compile & Strictly Verify (Single Command)
Run `build_guide.py` (compiles atomically to a temp file, injects round-trip markers, and automatically runs `verify_html_quiz.py --strict-guide` — do **not** run `verify_html_quiz.py` separately):

```bash
python3 scripts/build_guide.py "<content.slots.txt>" -o "<output>/Study_Guide_<Topic>.html" --min-questions 18
```

- If verification exits non-zero, follow each `→ Correcció IA:` hint in the output, fix the `.slots.txt` file, and re-run `build_guide.py` until `[PASS]` (`exit 0`).
