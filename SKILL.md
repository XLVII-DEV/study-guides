---
name: study-guides
description: >-
  Turns a student's notes, slides, PDFs, exercises or code into a single-file, fully
  offline interactive HTML study guide (teacher-style explanations, fill-in practice,
  a 3-level quiz with timed exam mode, Anki export and a printable A4 cheat-sheet),
  and closes the study loop: the guide exports the student's mistakes so the next
  guide targets exactly what they got wrong. Use it whenever someone wants to study,
  review or prepare for an exam, test, oral defense or certification, even if they
  never say "study guide": "I have a Biochem exam on Friday, help me", "turn these
  slides into something I can revise with", "quiz me on unit 3", "make me a cheat
  sheet", "tengo examen de Redes el lunes", "ayúdame a estudiar estos apuntes",
  "fes-me una guia per estudiar", "repàs per a l'examen", or when they paste a
  "STUDY-GUIDES PROGRESS" report. Not for one-off factual questions, plain-text
  summaries the user explicitly wants inline in chat, or general web-app UI work.
---

# Study Guides

This skill helps a student learn a topic and pass an exam with it, not just receive a document. Two ideas shape everything below:

1. **You write content, the compiler writes the page.** All HTML, CSS and JavaScript (dark mode, quiz engine, exam timer, Anki export, print layout) already lives in [`assets/template.html`](./assets/template.html) and has been tested. You only write a short 6-slot text file and compile it with [`scripts/build_guide.py`](./scripts/build_guide.py). Writing the page by hand would cost about 5x more tokens and would lose the validator's safety net, so don't.
2. **Studying is a loop, not a one-off.** Plan → teach → practice → see what failed → review the failures. The guide's **"Progress for AI"** button copies a report of the student's mistakes. When they paste it back, you build a targeted review guide (see *Review mode*).

---

## Step 0 · Understand the student's situation (briefly)

A guide for "exam tomorrow, multiple choice" looks completely different from one for "oral defense in a month". Before reading long PDFs or searching the web, make sure you know these. Take whatever the prompt, the files or the workspace already say, and ask only for what is missing and actually changes the result, in **one** short message.

| Need | Why it matters |
| :--- | :--- |
| **Subject / scope** | What goes in the guide. Unit, chapter or syllabus. |
| **Language** | Output and UI language (`en`, `es`, `ca`, `fr`, `de`, `pt`, `it` built in). Default to the language the user writes in. |
| **Level** | High school, vocational/undergraduate or advanced. Sets the depth and the kind of traps (see Step 2). |
| **Time until the exam** | Picks the mode below. If unknown, assume *Standard*. |
| **Exam format** | Multiple choice, numeric problems, written essay, oral, practical/code. Decides what goes into practice and the quiz. |
| **Known weak spots** (optional) | Lets you spend depth where it pays. |

Then **look at the student's own material first** (notes, slides, past exams, lab code). It is what the exam is built from. Use outside sources only to fill clear gaps, and label them (see *Source fidelity*).

### Choose a mode

- **Sprint**: exam in under ~48 h, or the user says they are short on time. One compact guide: 3–5 theory cards on the highest-yield concepts, the classic exam traps, 9–12 questions (`--min-questions 9`), and a very dense cheat-sheet. Leave out everything "nice to know".
- **Standard** (default): one guide for one unit or topic. 4–8 cards, 18 questions (`--min-questions 18`).
- **Course**: the scope is too big for one guide (several units, a whole syllabus, weeks of time). First reply with a short **study plan**: the units, their order, and one guide per unit, highest weight or weakest first. Then build the first guide. One guide per unit keeps each file easy to use and lets the progress report point at one unit.
- **Review**: the user pasted a `STUDY-GUIDES PROGRESS` report. See *Review mode* below.

---

## Step 1 · New guide or edit an existing one

- **Editing a guide built with this skill**: pull its slots back out instead of reading the compiled HTML (much cheaper):
  ```bash
  python3 scripts/build_guide.py --extract "<Existing_Guide.html>" -o "<temp>/guide.slots.txt"
  ```
  Change only what is needed, then go to Step 3.
- **New guide**: read [references/html-study-architecture.md](./references/html-study-architecture.md) for the components and the exact slot contract. Use [examples/cs_acid_transactions.slots.txt](./examples/cs_acid_transactions.slots.txt) (STEM) or [examples/biology_cell_respiration.slots.txt](./examples/biology_cell_respiration.slots.txt) (life sciences) as a model.

---

## Step 2 · Write the 6 slots like a great teacher

The student can find definitions anywhere. What they need from you is **understanding**: why a concept exists, how it works inside, and where people usually get it wrong. Lists of isolated definitions feel productive but don't survive an exam.

Calibrate to `level`:
- *High school / intro*: everyday analogies before notation. Break every calculation or mechanism into explicit small steps.
- *Vocational / undergraduate*: intuitive model plus exact terminology, formulas or API contracts, and realistic exam traps.
- *Advanced / certification / oral defense*: trade-offs, edge cases, failure modes, and "what happens if we change X?" questions.

Calibrate to the **exam format** too. Numeric problems need worked calculations in theory and calculation drills in practice. An oral exam needs many `oral-check` cards with model answers. Code exams need runnable snippets and "predict the output" questions.

The six slots, in order (full markup in the reference file):

1. **`meta`** (JSON): `lang`, `themePreset`, `title`, `topbarMeta`, `storageKey`, optional `sidebarFoot`. Presets: `warm-serif` (default, general reading), `ink-editorial` (law, humanities, biology/medicine), `slate-tech` (engineering, CS, maths, physics). Use a distinct `storageKey` per guide (e.g. `study_networks_u3_v1`), so progress from different guides never mixes.
2. **`hero`** (HTML): eyebrow, `<h1>`, one paragraph saying what this guide covers and why it matters, and a summary strip of the 3–4 ideas to remember.
3. **`teoria`** (HTML, Block 1, the explanation): one `<section class="card">` per subtopic, each following four moves:
   1. **Intuition first**: the real problem this concept solves, in 1–2 sentences, before any formal definition.
   2. **Mechanism**: how it works inside, shown with a diagram (inline `<svg>` using CSS variables so it stays visible in dark mode), a numbered step-trace or a comparison table.
   3. **Worked example**: concrete input → intermediate state → result. Take it from the student's own exercises when possible.
   4. **Contrast and takeaway**: a "common mistake vs right way" pair or an exam-trap callout, then a one-sentence key takeaway.
   Add `oral-check` cards (question → model answer) for active recall. They also go into the Anki export.
4. **`practica`** (HTML, Block 2): short fill-in exercises (drag chips, text fields, selects) that make the student *produce* the key terms and steps, not just recognise them.
5. **`quiz`** (pure JSON array, Block 3): `{id, level, q, options, correct, why, src?}` over three levels: 1 Foundations, 2 Application, 3 Mastery. Level 3 should feel like the hardest real exam question. The `why` is where most of the learning happens, so write two sentences: the rule that makes the right answer right, and why the most tempting wrong option is tempting but wrong.
6. **`xuleta`** (HTML, Block 4, the cheat-sheet): dense tables and rules that print on 1–2 A4 pages. Put in the things the student would write on their hand the night before.

### Source fidelity

A study guide that teaches something wrong is worse than no guide, because the student will trust it in the exam. So:
- When the student gave you material, tag each card and quiz question with where it comes from (`<span class="src-tag">Source: Slides U3 p.12</span>`, `"src": "Slides U3"`). The student can then check anything that looks odd.
- If you add something that is **not** in their material (a gap you filled from general knowledge or the web), tag it `Source: complementary` so they know it may not be in their syllabus.
- If their material contradicts what you believe is correct, don't silently "fix" it. Add a `.callout` noting the discrepancy, because their teacher's version is what gets graded.

---

## Step 3 · Compile and verify (one command)

```bash
python3 scripts/build_guide.py "<content.slots.txt>" -o "<output>/Study_Guide_<Topic>.html" --min-questions 18
```

This builds into a temporary file, runs the strict validator (offline-only, safe HTML, dark-mode-safe SVG, every practice exercise solvable, quiz not biased toward one letter or the longest option) and only then writes the output. You don't need to run `verify_html_quiz.py` separately. If it fails, every problem comes with a `→ AI Fix:` hint: fix the `.slots.txt` and run again until you get `[PASS]`.

Use `--min-questions` to match the mode: 9 for Sprint, 18 for Standard. In Review mode, use the number of questions you actually wrote, but at least 6.

---

## Step 4 · Hand it over and explain the loop

When the guide is built, tell the student in two or three lines, in their language:
- where the file is (it opens in any browser, works offline, progress is saved automatically);
- a suggested way to use it: read Block 1 → do Block 2 → quiz level by level (Exam mode for a timed run) → print the cheat-sheet;
- **after the quiz, press "Progress for AI" and paste the result here**, and you will prepare a review focused on their mistakes.

That last line keeps the student coming back and turns one guide into a study process.

---

## Review mode (the student pasted a progress report)

The report looks like this:

```text
=== STUDY-GUIDES PROGRESS v1 ===
guide: Study Guide · Cellular Respiration
storageKey: study_bio_respiration_v1
level 1: 3/4 correct, 4/4 answered
...
missed (2):
- [bio1_q2 · L1 · Ch. 9 §2] What is the 3-carbon end product of glycolysis?
    chose: Two molecules of Oxaloacetate | correct: Two molecules of Pyruvate
unanswered: bio3_q1, bio3_q2
=== END PROGRESS ===
```

Treat it as a diagnosis:
1. **Find the misconception behind each miss.** Choosing *oxaloacetate* over *pyruvate* suggests the student mixes up glycolysis and the Krebs cycle. That confusion is what to fix, not just this one question. Group misses that share a cause.
2. **Unanswered Level 3 questions** usually mean the student stopped before the hard part. Give them a gentler path up to it.
3. **Build a short review guide** (new `storageKey`, e.g. `..._review1`): one card per misconception, re-explained from a **different angle** than the original (new analogy, new diagram, new worked example), then a contrast box with *exactly* the confusion they showed. Write **new** questions on the same concepts. Reusing the old ones only tests whether they remember the answer.
4. If you have the original guide or its slots, reuse its sources and examples for consistency.
5. Reply with a one-paragraph diagnosis ("you know X well; the gap is between Y and Z") before the file. Students find this as useful as the guide itself.

If the report shows few or no misses, congratulate them briefly and offer the next step: harder Level 3 questions, the next unit in the study plan, or a timed mock exam.
