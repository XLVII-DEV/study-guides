# HTML Study Architecture Reference (`master-study-guides`)

Tota la capa visual i interactiva (Warm Academic Serif Bronze/Ocre, mode fosc, índex amb filtre `/`, botó *Copiar* a `<pre>`, motors del Bloc 2 i Bloc 3 amb persistència real i impressió A4 en 2 modes) viu a [`assets/template.html`](../assets/template.html). **No la reescriguis mai**: redacta només els 6 slots i compila amb `scripts/build_guide.py`.

---

## 1. Paleta i Regles Visuals (SVG Dark-Mode Safe)

| Token CSS | Mode Clar | Mode Fosc | Ús |
| :--- | :--- | :--- | :--- |
| `--bg` / `--surface` | `#fbf7ec` / `#fffdf7` | `#141310` / `#1d1b17` | Fons de pàgina i targetes |
| `--surface-low` / `--surface-code` | `#f4eedb` / `#ede5cf` | `#26231d` / `#2c2821` | Índex, callouts i codi |
| `--border` / `--border-strong` | `#dfd6bc` / `#8a7e63` | `#3a342a` / `#7e7360` | Contorns (`>= 3:1`) i caixes SVG |
| `--ink` / `--ink-muted` | `#1f2421` / `#5a5549` | `#ede8dc` / `#aba392` | Text principal i secundari |
| `--accent` / `--on-accent` | `#8c5214` / `#ffffff` | `#e5a94c` / `#1d1b17` | Bronze/Ocre i text sobre botó |
| `--ok` / `--err` | `#146c53` / `#b42318` | `#4ade80` / `#fb7185` | Validació i trampes |

> **Regla SVG crítica**: dins `<svg>`, usa **sempre** variables CSS via `style="fill:var(--ink)"`, `style="stroke:var(--border-strong)"`, `style="fill:var(--accent)"`. **Prohibit** posar `fill="#000"`, `fill="#1f2421"` o `fill="black"` (queden invisibles en mode fosc i el verificador els rebutja).

---

## 2. Contracte dels 6 Slots i Components HTML

Vegeu un fitxer complet i executable a [`examples/minimal_guide.slots.txt`](../examples/minimal_guide.slots.txt).

1. **`<!-- @slot meta -->`** (JSON pur):
   ```json
   {"lang": "ca", "title": "Guia Mestra · Tema", "topbarMeta": "Assignatura · Unitat", "storageKey": "study_tema_v1", "sidebarFoot": "Nota breu al peu"}
   ```
   - Idiomes integrats (`UI_DEFAULTS`): `ca`, `es`, `en`, `fr`.
   - Claus sobreescrivibles amb `"ui": {...}`: `index`, `closeIndex`, `skipToContent`, `filterPlaceholder`, `noMatches`, `dark`, `light`, `print`, `printFull`, `copy`, `copied`, `resetEx`, `start`, `theory`, `practice`, `quiz`, `sheet`, `practiceEyebrow`, `practiceTitle`, `quizEyebrow`, `quizTitle`, `sheetEyebrow`, `sheetTitle`, `level1`, `level2`, `level3`, `onlyWrong`, `reset`, `score`, `grade`, `globalScore`, `toReview`, `noWrong`, `empty`, `allCorrect`, `correctCount`, `hint`.
2. **`<!-- @slot hero -->`** (HTML):
   - `.eyebrow`, `<h1>`, paràgraf d'enfocament i `.summary-strip > .pill-box > .pill-label + strong`.
3. **`<!-- @slot teoria -->`** (HTML — **Bloc 1**):
   - Agrupa cada subtema dins `<section class="card" id="t-slug">` amb `<h2 id="h-slug">Títol</h2>` (`Bloc 1 · 01...`). `build_guide.py` enllaça l'índex a `#t-slug` perquè el ressaltat d'scroll cobreixi tota la targeta.
   - **Components disponibles**: `.src-tag`, `.callout`, `.callout.trap`, `figure.diagram > svg + figcaption`, `<pre><code>` (rep botó *Copiar*) i `<details class="oral-check"><summary>...</summary><div class="oral-ans">...</div></details>`.
4. **`<!-- @slot practica -->`** (HTML — **Bloc 2**):
   - Cada exercici és `<div class="exercise" data-hint="pista curta" data-ok="Missatge d'èxit">` amb xips `.chip[data-val]` + `.slot[data-ans]`, `<input class="field" type="text" data-ans="opcio1|opcio2">` (valida amb `Enter` o clic) i `<select class="field" data-ans="valor">`, tancat amb `<button class="btn primary check" type="button">Comprovar</button><div class="feedback"></div>` (el botó *Reiniciar* s'injecta sol).
5. **`<!-- @slot quiz -->`** (JSON pur, **sense** `<script>` — **Bloc 3**):
   ```json
   [{"id": "n1_q1", "level": 1, "src": "Tema 1 p.3", "q": "Enunciat...", "options": ["A", "B", "C", "D"], "correct": 2, "why": "..."}]
   ```
6. **`<!-- @slot xuleta -->`** (HTML — **Bloc 4**):
   - Taules i regles condensades en HTML pur. `🖨️ Xuleta A4` imprimeix només el resum + `#xuleta`; `📄 Guia completa` imprimeix tota la teoria + xuleta.

### IDs reservats de la plantilla (no els redeclarïs dins els slots)
`mainContent`, `inici`, `teoria`, `practica`, `autoavaluacio`, `xuleta`, `sidebar`, `sidebarBackdrop`, `navFilter`, `navList`, `navEmpty`, `btnToggleIndex`, `btnCloseIndex`, `btnTheme`, `btnPrint`, `btnPrintFull`, `quizScore`, `quizHost`, `btnOnlyWrong`, `btnResetQuiz`, `guide-meta`, `quiz-data`.

---

## 3. Regles Auditades per `build_guide.py` + `verify_html_quiz.py --strict-guide`
1. **Estructura, Seguretat i Offline**: `<html lang>` vàlid, `#teoria/#practica/#autoavaluacio/#xuleta`, zero URLs `http(s)://` o `//` en atributs/CSS, zero `<iframe>/<embed>/on*=/javascript:/<script>` aliens, zero `innerHTML/eval`, i SVGs sense colors negres fixos (`#000`, `#1f2421`, `black`).
2. **Resolubilitat Bloc 2 (Pràctica)**: cada `.slot[data-ans]` té un `.chip[data-val]` coincident al seu `.exercise`; cada `<select data-ans>` conté l'`<option>` guanyadora.
3. **Equilibri Bloc 3 (Test, global i per nivell `1`, `2`, `3`)**:
   - Tots 3 nivells tenen `>= min_per_level` preguntes (`max(1, min_questions // 3)` per defecte).
   - Cap lletra supera `35%` (`>= 6` preguntes) o `50%` (`4–5` preguntes), sense ratxes `>= 3` iguals seguides.
   - L'opció correcta no és la més llarga en `> 30%` global (`35%` per nivell) ni excedeix `1.20x` el màxim distractor / `1.35x` la mitjana quan fa `>= 30` chars.
   - Cap booleà a `correct`/`level`, cap opció buida, duplicada ni comodí.
4. **Escriptura atòmica**: `build_guide.py` valida sobre un fitxer temporal abans d'escriure el fitxer final.
