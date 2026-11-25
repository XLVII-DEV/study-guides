# HTML Study Architecture Reference (`study-guides`)

All styling, dark mode, 3 theme presets, searchable sidebar (`/`), 1-click code copy, timed exam mode, Anki `.tsv` exporter, and Block 2/3 engines live in [`assets/template.html`](../assets/template.html). **Never rewrite CSS or JS by hand** — author only the 6 slots and compile with `scripts/build_guide.py`.

---

## 1. Visual Presets & Dark-Mode-Safe SVG Rules

Set `"themePreset"` inside `<!-- @slot meta -->`:

| Preset | Light Feel | Dark Feel | Ideal Domain |
| :--- | :--- | :--- | :--- |
| `warm-serif` *(default)* | Warm yellow paper `#fbf7ec` + Bronze `#8c5214` + Serif titles | Warm charcoal `#141310` + Ocre `#e5a94c` | General academic, reading-heavy courses |
| `ink-editorial` | Ivory `#fcfaf7` + Burgundy `#881337` + Serif titles | Deep slate `#121214` + Rose `#fb7185` | Law, History, Biology/Medicine, Humanities |
| `slate-tech` | Crisp white/slate `#f6f8fa` + Petrol `#0f5c73` + Geometric Sans | GitHub-dark `#0d1117` + Sky `#58a6ff` | Software Engineering, Cloud, Math, Physics |

> **Critical SVG rule**: inside inline `<svg>`, **always** use CSS variables via `style="fill:var(--ink)"`, `style="stroke:var(--border-strong)"`, `style="fill:var(--accent)"`. **Never** use hardcoded `#000`, `#1f2421`, or `black` (invisible in dark mode and rejected by `--strict-guide`).

---

## 2. Six-Slot Contract & Pedagogical Components

1. **`<!-- @slot meta -->`** (pure JSON):
   ```json
   {
     "lang": "en",
     "themePreset": "warm-serif",
     "title": "Study Guide · Topic",
     "topbarMeta": "Subject · Unit",
     "storageKey": "study_topic_v1",
     "sidebarFoot": "Course · Level"
   }
   ```
   - Built-in `UI_DEFAULTS` languages: `en`, `es`, `ca`, `fr`, `de`, `pt`, `it`.
   - Any label can be overridden via `"ui": {...}` (`index`, `closeIndex`, `skipToContent`, `filterPlaceholder`, `noMatches`, `dark`, `light`, `print`, `printFull`, `copy`, `copied`, `resetEx`, `start`, `theory`, `practice`, `quiz`, `sheet`, `practiceEyebrow`, `practiceTitle`, `quizEyebrow`, `quizTitle`, `sheetEyebrow`, `sheetTitle`, `level1`, `level2`, `level3`, `onlyWrong`, `reset`, `examMode`, `submitExam`, `timeLeft`, `exportAnki`, `score`, `grade`, `globalScore`, `toReview`, `noWrong`, `empty`, `allCorrect`, `correctCount`, `hint`).
2. **`<!-- @slot hero -->`** (HTML): `.eyebrow`, `<h1>`, concise intro `<p>`, `.summary-strip > .pill-box > .pill-label + strong`.
3. **`<!-- @slot teoria -->`** (HTML — **Block 1**):
   - Wrap each subtopic in `<section class="card" id="t-slug">` with `<h2 id="h-slug">Title</h2>`.
   - **Pedagogical components**:
     - `<span class="src-tag">Source: Lecture 3</span>`: traceability badge.
     - `<ol class="step-trace"><li>...</li></ol>`: numbered whiteboard step-by-step execution or derivation trace.
     - `<div class="compare-grid"><div class="compare-box bad"><strong>Common mistake</strong>...</div><div class="compare-box good"><strong>Right way</strong>...</div></div>`: side-by-side mistake vs fix.
     - `<div class="callout">` and `<div class="callout trap"><strong>Exam trap:</strong> ...</div>`.
     - `<div class="key-takeaway"><strong>Key takeaway:</strong> ...</div>`: closing synthesis rule.
     - `<details class="oral-check"><summary>Question...</summary><div class="oral-ans">Model answer...</div></details>`: active recall card (automatically included in `Anki (.tsv)` export).
     - `<figure class="diagram"><svg ...>...</svg><figcaption>...</figcaption></figure>` and `<pre><code>...</code></pre>`.
4. **`<!-- @slot practica -->`** (HTML — **Block 2**):
   - `<div class="exercise" data-hint="short hint" data-ok="Success message">` combining `.chip[data-val]` + `.slot[data-ans]`, `<input class="field" type="text" data-ans="a|b">`, and `<select class="field" data-ans="a"><option value="a">...</option></select>`, ending with `<button class="btn primary check" type="button">Check</button><div class="feedback"></div>`.
5. **`<!-- @slot quiz -->`** (pure JSON, **no** `<script>` tags — **Block 3**):
   ```json
   [{"id": "n1_q1", "level": 1, "src": "Unit 1", "q": "Question...", "options": ["A", "B", "C", "D"], "correct": 2, "why": "Rule proving C is correct, and why the primary distractor fails."}]
   ```
   - Supports **Timed Exam Mode** (`1 min/question`, hides answers until submit, grades `/10`) and **Anki `.tsv` export**.
6. **`<!-- @slot xuleta -->`** (HTML — **Block 4**): pure-HTML A4 tables and checklists.

### Reserved Template IDs (do not reuse inside slots)
`mainContent`, `inici`, `teoria`, `practica`, `autoavaluacio`, `xuleta`, `sidebar`, `sidebarBackdrop`, `navFilter`, `navList`, `navEmpty`, `btnToggleIndex`, `btnCloseIndex`, `btnTheme`, `themeLabel`, `examTimer`, `examTimerText`, `btnExamMode`, `btnSubmitExam`, `btnExportAnki`, `quizScore`, `quizHost`, `btnOnlyWrong`, `btnResetQuiz`, `guide-meta`, `quiz-data`.

---

## 3. Automated Checks Enforced by `--strict-guide`
1. **Offline & DOM/HTML Security**: `<html lang>` present, required 4 block containers `#teoria/#practica/#autoavaluacio/#xuleta`, zero external `http(s)://` or `//` URLs in attributes/CSS, zero `<iframe>/<embed>/on*=/javascript:/<script>` tags, zero `innerHTML/eval`, and dark-mode-safe SVGs.
2. **Block 2 Solvability**: every `.slot[data-ans]` has a matching `.chip[data-val]` in its `.exercise`; every `<select data-ans>` has a matching `<option>`.
3. **Block 3 Anti-Bias Audit (Global & Per-Level `1`, `2`, `3`)**:
   - Enforces `--min-questions` and `--min-per-level` (`max(1, min_questions // 3)` default).
   - Caps any single letter at `35%` (`>= 6` questions) or `50%` (`4–5` questions) and forbids `>= 3` consecutive identical answer positions.
   - Caps longest-option correct hits at `30%` global / `35%` per level and flags length outliers (`>= 30` chars exceeding `1.20x max` or `1.35x mean`).
   - Rejects booleans in `correct`/`level`, duplicate/empty options, and giveaway options (*"All of the above"*); warns if `"why"` is `< 35` chars.
4. **Atomic Output**: `build_guide.py` validates on a temporary file before overwriting the destination.
