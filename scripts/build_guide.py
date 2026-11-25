#!/usr/bin/env python3
"""
Build or extract a Warm Academic Serif study guide using assets/template.html.

Build mode:
    python3 build_guide.py content.slots.txt -o Guia_Mestra_Tema.html [--min-questions 12]

Round-trip extract mode (reconstruct editable slots from a compiled HTML guide):
    python3 build_guide.py --extract Guia_Mestra_Tema.html -o content.slots.txt
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_DIR / "assets" / "template.html"
VERIFIER = SKILL_DIR / "scripts" / "verify_html_quiz.py"
REQUIRED_SLOTS = ("meta", "hero", "teoria", "practica", "quiz", "xuleta")
HTML_SLOTS = ("hero", "teoria", "practica", "xuleta")

_TEMPLATE_TOKEN_RE = re.compile(
    r"\{\{(ui\.\w+|LANG|TITLE|TOPBAR_META|SIDEBAR_FOOT|NAV|META_JSON|QUIZ_JSON|slot\.(?:hero|teoria|practica|xuleta))\}\}"
)

UI_DEFAULTS: Dict[str, Dict[str, str]] = {
    "ca": {
        "index": "Índex", "closeIndex": "Tancar índex", "skipToContent": "Ves al contingut",
        "filterPlaceholder": "Filtrar seccions (/)...", "noMatches": "Cap coincidència.",
        "dark": "Mode fosc", "light": "Mode clar",
        "print": "Xuleta A4", "printFull": "Guia completa",
        "copy": "Copiar", "copied": "Copiat ✓", "resetEx": "Reiniciar",
        "start": "Inici", "theory": "Explicació del professor", "practice": "Pràctica autocompletable",
        "quiz": "Autoavaluació I · II · III", "sheet": "Xuleta A4",
        "practiceEyebrow": "Bloc 2 · Pràctica", "practiceTitle": "Activitats autocompletables",
        "quizEyebrow": "Bloc 3 · Autoavaluació progressiva", "quizTitle": "Test en 3 nivells",
        "sheetEyebrow": "Bloc 4 · Impressió A4", "sheetTitle": "Xuleta del professor",
        "level1": "Nivell I · Fonaments", "level2": "Nivell II · Aplicació", "level3": "Nivell III · Mestria",
        "onlyWrong": "Repassar només errors", "reset": "Reiniciar nivell",
        "score": "Nivell", "grade": "Nota", "globalScore": "Global", "toReview": "Per repassar",
        "noWrong": "Cap error pendent en aquest nivell.", "empty": "No hi ha preguntes en aquest nivell.",
        "allCorrect": "Tot correcte.", "correctCount": "correctes", "hint": "Pista",
    },
    "es": {
        "index": "Índice", "closeIndex": "Cerrar índice", "skipToContent": "Ir al contenido",
        "filterPlaceholder": "Filtrar secciones (/)...", "noMatches": "Sin coincidencias.",
        "dark": "Modo oscuro", "light": "Modo claro",
        "print": "Chuleta A4", "printFull": "Guía completa",
        "copy": "Copiar", "copied": "Copiado ✓", "resetEx": "Reiniciar",
        "start": "Inicio", "theory": "Explicación del profesor", "practice": "Práctica autocompletable",
        "quiz": "Autoevaluación I · II · III", "sheet": "Chuleta A4",
        "practiceEyebrow": "Bloque 2 · Práctica", "practiceTitle": "Actividades autocompletables",
        "quizEyebrow": "Bloque 3 · Autoevaluación progresiva", "quizTitle": "Test en 3 niveles",
        "sheetEyebrow": "Bloque 4 · Impresión A4", "sheetTitle": "Chuleta del profesor",
        "level1": "Nivel I · Fundamentos", "level2": "Nivel II · Aplicación", "level3": "Nivel III · Maestría",
        "onlyWrong": "Repasar solo errores", "reset": "Reiniciar nivel",
        "score": "Nivel", "grade": "Nota", "globalScore": "Global", "toReview": "Por repasar",
        "noWrong": "Ningún error pendiente en este nivel.", "empty": "No hay preguntas en este nivel.",
        "allCorrect": "Todo correcto.", "correctCount": "correctas", "hint": "Pista",
    },
    "en": {
        "index": "Contents", "closeIndex": "Close contents", "skipToContent": "Skip to content",
        "filterPlaceholder": "Filter sections (/)...", "noMatches": "No matches.",
        "dark": "Dark mode", "light": "Light mode",
        "print": "A4 cheat-sheet", "printFull": "Full guide",
        "copy": "Copy", "copied": "Copied ✓", "resetEx": "Reset",
        "start": "Start", "theory": "Teacher's explanation", "practice": "Fill-in practice",
        "quiz": "Self-assessment I · II · III", "sheet": "A4 cheat-sheet",
        "practiceEyebrow": "Block 2 · Practice", "practiceTitle": "Fill-in activities",
        "quizEyebrow": "Block 3 · Progressive self-assessment", "quizTitle": "3-level quiz",
        "sheetEyebrow": "Block 4 · A4 print", "sheetTitle": "Teacher's cheat-sheet",
        "level1": "Level I · Foundations", "level2": "Level II · Application", "level3": "Level III · Mastery",
        "onlyWrong": "Review mistakes only", "reset": "Reset level",
        "score": "Level", "grade": "Score", "globalScore": "Total", "toReview": "To review",
        "noWrong": "No pending mistakes in this level.", "empty": "No questions in this level.",
        "allCorrect": "All correct.", "correctCount": "correct", "hint": "Hint",
    },
    "fr": {
        "index": "Sommaire", "closeIndex": "Fermer le sommaire", "skipToContent": "Aller au contenu",
        "filterPlaceholder": "Filtrer les sections (/)...", "noMatches": "Aucun résultat.",
        "dark": "Mode sombre", "light": "Mode clair",
        "print": "Fiche A4", "printFull": "Guide complet",
        "copy": "Copier", "copied": "Copié ✓", "resetEx": "Réinitialiser",
        "start": "Accueil", "theory": "Explication du professeur", "practice": "Exercices à compléter",
        "quiz": "Auto-évaluation I · II · III", "sheet": "Fiche A4",
        "practiceEyebrow": "Bloc 2 · Pratique", "practiceTitle": "Activités interactives",
        "quizEyebrow": "Bloc 3 · Auto-évaluation progressive", "quizTitle": "Quiz en 3 niveaux",
        "sheetEyebrow": "Bloc 4 · Impression A4", "sheetTitle": "Fiche de révision",
        "level1": "Niveau I · Bases", "level2": "Niveau II · Application", "level3": "Niveau III · Maîtrise",
        "onlyWrong": "Revoir les erreurs", "reset": "Réinitialiser",
        "score": "Niveau", "grade": "Note", "globalScore": "Total", "toReview": "À revoir",
        "noWrong": "Aucune erreur en attente dans ce niveau.", "empty": "Aucune question dans ce niveau.",
        "allCorrect": "Tout est correct.", "correctCount": "correctes", "hint": "Indice",
    },
}


def _strip_llm_wrappers(raw: str) -> str:
    txt = raw.strip()
    txt = re.sub(r"^```(?:json|html)?\s*", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\s*```$", "", txt)
    txt = re.sub(r"^<script\b[^>]*>\s*", "", txt, flags=re.IGNORECASE)
    txt = re.sub(r"\s*</script>$", "", txt, flags=re.IGNORECASE)
    return txt.strip()


def _parse_json_slot(raw: str, slot_name: str) -> Any:
    cleaned = _strip_llm_wrappers(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        lines = cleaned.splitlines()
        bad_line = lines[exc.lineno - 1] if 1 <= exc.lineno <= len(lines) else ""
        raise SystemExit(
            f"Error JSON a <!-- @slot {slot_name} --> (línia {exc.lineno}, col {exc.colno}): {exc.msg}\n"
            f"  Línia: {bad_line}\n"
            f"  → Correcció IA: posa JSON pur vàlid dins '@slot {slot_name}' (sense etiquetes <script> ni comes finals)."
        )


def parse_slots(raw: str) -> Dict[str, str]:
    parts = re.split(r"<!--\s*@slot\s+([\w-]+)\s*-->", raw)
    slots: Dict[str, str] = {}
    duplicates: List[str] = []
    for i in range(1, len(parts) - 1, 2):
        key = parts[i].lower()
        if key in slots:
            duplicates.append(key)
        slots[key] = parts[i + 1].strip()
    if duplicates:
        raise SystemExit(
            f"Slots duplicats: {', '.join(sorted(set(duplicates)))}. "
            f"→ Correcció IA: cada marcador <!-- @slot NOM --> ha d'aparèixer un sol cop."
        )
    unknown = sorted(set(slots) - set(REQUIRED_SLOTS))
    if unknown:
        raise SystemExit(
            f"Slots desconeguts: {', '.join(unknown)}. "
            f"→ Correcció IA: usa només {', '.join(REQUIRED_SLOTS)}."
        )
    missing = [s for s in REQUIRED_SLOTS if s not in slots]
    if missing:
        raise SystemExit(
            f"Falten slots obligatoris: {', '.join(missing)}. "
            f"→ Correcció IA: inclou tots els marcadors <!-- @slot NOM --> ({', '.join(REQUIRED_SLOTS)})."
        )
    return slots


def build_nav(teoria: str, ui: Dict[str, str]) -> str:
    items: List[str] = [f'        <li><a class="nav-link" href="#inici">{html.escape(ui["start"])}</a></li>']
    items.append(f'        <li><a class="nav-link" href="#teoria">{html.escape(ui["theory"])}</a></li>')

    sub_entries: List[Tuple[str, str]] = []
    for sec_m in re.finditer(r'<section\b[^>]*\bid=["\']([^"\']+)["\'][^>]*>(.*?)</section>', teoria, flags=re.DOTALL | re.IGNORECASE):
        sec_id, sec_body = sec_m.group(1), sec_m.group(2)
        h2_m = re.search(r"<h2\b[^>]*>(.*?)</h2>", sec_body, flags=re.DOTALL | re.IGNORECASE)
        if h2_m:
            raw_title = re.sub(r"<[^>]+>", "", h2_m.group(1))
            sub_entries.append((sec_id, html.unescape(raw_title).strip()))

    if not sub_entries:
        for h2_id, h2_label in re.findall(r'<h2[^>]*\bid=["\']([^"\']+)["\'][^>]*>(.*?)</h2>', teoria, flags=re.DOTALL):
            raw_title = re.sub(r"<[^>]+>", "", h2_label)
            sub_entries.append((h2_id, html.unescape(raw_title).strip()))

    for anchor, label in sub_entries:
        items.append(f'        <li><a class="nav-link sub" href="#{html.escape(anchor)}">{html.escape(label)}</a></li>')

    for anchor, key in (("practica", "practice"), ("autoavaluacio", "quiz"), ("xuleta", "sheet")):
        items.append(f'        <li><a class="nav-link" href="#{anchor}">{html.escape(ui[key])}</a></li>')
    return "\n".join(items)


def validate_quiz(quiz: Any) -> None:
    if not isinstance(quiz, list) or not quiz:
        raise SystemExit("Error a @slot quiz: ha de ser un array JSON no buit de preguntes.")
    errs: List[str] = []
    ids = set()
    for i, q in enumerate(quiz, start=1):
        if not isinstance(q, dict):
            errs.append(f"Pregunta {i}: cada element ha de ser un objecte JSON.")
            continue
        missing_fields = [f for f in ("id", "level", "q", "options", "correct", "why") if f not in q]
        if missing_fields:
            errs.append(f"Pregunta {i}: falten camps {missing_fields}.")
            continue
        qid = q["id"]
        if not isinstance(qid, str) or not qid.strip():
            errs.append(f"Pregunta {i}: 'id' ha de ser una cadena no buida.")
        elif qid in ids:
            errs.append(f"Pregunta {i}: id duplicat '{qid}'.")
        else:
            ids.add(qid)
        if not isinstance(q["q"], str) or not q["q"].strip():
            errs.append(f"Pregunta {i} ({qid}): 'q' ha de ser una cadena no buida.")
        if type(q["level"]) is not int or q["level"] not in (1, 2, 3):
            errs.append(f"Pregunta {i} ({qid}): 'level' ha de ser enter 1, 2 o 3 (mai booleà).")
        opts = q["options"]
        if not isinstance(opts, list) or len(opts) < 2:
            errs.append(f"Pregunta {i} ({qid}): 'options' ha de tenir almenys 2 opcions.")
            continue
        norm_opts = [str(o).strip().lower() for o in opts]
        if any(not o for o in norm_opts) or len(set(norm_opts)) != len(norm_opts):
            errs.append(f"Pregunta {i} ({qid}): hi ha opcions buides o duplicades.")
        if type(q["correct"]) is not int or not 0 <= q["correct"] < len(opts):
            errs.append(f"Pregunta {i} ({qid}): 'correct' ha de ser un enter dins 0..{len(opts) - 1}.")
        if not isinstance(q["why"], str) or not q["why"].strip():
            errs.append(f"Pregunta {i} ({qid}): 'why' no pot estar buit.")
    if errs:
        raise SystemExit("\n".join(errs))


def json_for_script(data: object, *, multiline: bool = False) -> str:
    indent = 2 if multiline else None
    return json.dumps(data, ensure_ascii=False, indent=indent).replace("<", "\\u003c")


def _read_text_or_exit(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"Error: no existeix el fitxer {path}")
    except OSError as exc:
        raise SystemExit(f"Error en llegir {path}: {exc}")


def build(content_path: Path, out_path: Path) -> None:
    slots = parse_slots(_read_text_or_exit(content_path))
    meta = _parse_json_slot(slots["meta"], "meta")
    if not isinstance(meta, dict):
        raise SystemExit("Error a @slot meta: ha de ser un objecte JSON.")

    lang = str(meta.get("lang", "ca")).strip() or "ca"
    meta["lang"] = lang
    defaults = UI_DEFAULTS.get(lang, UI_DEFAULTS["en"])
    raw_ui = meta.get("ui")
    if raw_ui is not None:
        if not isinstance(raw_ui, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in raw_ui.items()):
            raise SystemExit("Error a @slot meta.ui: totes les claus i valors han de ser cadenes de text.")
    custom_ui = raw_ui if isinstance(raw_ui, dict) else {}
    ui = {**defaults, **custom_ui}
    full_meta = {**meta, "ui": ui}
    if not full_meta.get("storageKey"):
        slug = re.sub(r"\W+", "_", str(meta.get("title", "guide")).lower()).strip("_")[:36] or "guide"
        full_meta["storageKey"] = f"study_{slug}_v1"

    quiz = _parse_json_slot(slots["quiz"], "quiz")
    validate_quiz(quiz)

    template_text = _read_text_or_exit(TEMPLATE)
    token_values: Dict[str, str] = {
        "LANG": html.escape(lang),
        "TITLE": html.escape(str(meta.get("title", ""))),
        "TOPBAR_META": html.escape(str(meta.get("topbarMeta", ""))),
        "SIDEBAR_FOOT": html.escape(str(meta.get("sidebarFoot", "Warm Academic Serif"))),
        "NAV": build_nav(slots["teoria"], ui),
        "META_JSON": json_for_script(full_meta),
        "QUIZ_JSON": json_for_script(quiz, multiline=True),
    }
    for k, v in ui.items():
        token_values[f"ui.{k}"] = html.escape(v)
    for key in HTML_SLOTS:
        token_values[f"slot.{key}"] = slots[key]

    missing_keys = sorted(
        {m.group(1) for m in _TEMPLATE_TOKEN_RE.finditer(template_text) if m.group(1) not in token_values}
    )
    if missing_keys:
        raise SystemExit(f"Claus de plantilla sense valor: {missing_keys}")

    # Single-pass substitution prevents user code snippets or meta fields from colliding with template tokens
    out = _TEMPLATE_TOKEN_RE.sub(lambda m: token_values[m.group(1)], template_text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out, encoding="utf-8")
    print(f"Guia generada: {out_path} ({len(out.encode('utf-8'))} bytes, {len(quiz)} preguntes)")


def extract_slots_from_html(html_path: Path, out_path: Path) -> None:
    raw = _read_text_or_exit(html_path)
    meta_m = re.search(r'<script[^>]+id=["\']guide-meta["\'][^>]*>(.*?)</script>', raw, flags=re.DOTALL | re.IGNORECASE)
    quiz_m = re.search(r'<script[^>]+id=["\']quiz-data["\'][^>]*>(.*?)</script>', raw, flags=re.DOTALL | re.IGNORECASE)
    if not meta_m or not quiz_m:
        raise SystemExit(f"No s'han trobat #guide-meta o #quiz-data a {html_path}. Només es poden extreure guies compilades amb template.html.")

    try:
        meta = json.loads(meta_m.group(1))
        quiz = json.loads(quiz_m.group(1))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON malformat dins {html_path}: {exc}")

    lang = meta.get("lang", "ca")
    defaults = UI_DEFAULTS.get(lang, UI_DEFAULTS["en"])
    if isinstance(meta.get("ui"), dict):
        overrides = {k: v for k, v in meta["ui"].items() if defaults.get(k) != v}
        if overrides:
            meta["ui"] = overrides
        else:
            meta.pop("ui", None)

    html_parts: Dict[str, str] = {}
    for key in HTML_SLOTS:
        m = re.search(rf"<!--\s*@slot-begin:{key}\s*-->\n?(.*?)\n?<!--\s*@slot-end:{key}\s*-->", raw, flags=re.DOTALL)
        if not m:
            raise SystemExit(f"Falta el marcador round-trip <!-- @slot-begin:{key} --> a {html_path}.")
        html_parts[key] = m.group(1).strip()

    blocks = [
        f"<!-- @slot meta -->\n{json.dumps(meta, ensure_ascii=False)}",
        f"<!-- @slot hero -->\n{html_parts['hero']}",
        f"<!-- @slot teoria -->\n{html_parts['teoria']}",
        f"<!-- @slot practica -->\n{html_parts['practica']}",
        f"<!-- @slot quiz -->\n{json.dumps(quiz, ensure_ascii=False, indent=2)}",
        f"<!-- @slot xuleta -->\n{html_parts['xuleta']}\n",
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n\n".join(blocks), encoding="utf-8")
    print(f"Slots extrets a: {out_path} ({len(quiz)} preguntes)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compila o extreu guies HTML amb la plantilla Warm Academic Serif")
    parser.add_argument("content", nargs="?", type=Path, help="Fitxer de contingut amb slots (mode compilació)")
    parser.add_argument("--extract", type=Path, metavar="HTML_FILE", help="Extreu els 6 slots editables d'un HTML compilat")
    parser.add_argument("-o", "--out", type=Path, required=True, help="Ruta de sortida (.html o .slots.txt)")
    parser.add_argument("--min-questions", type=int, default=12, help="Mínim de preguntes globals (per defecte: 12)")
    parser.add_argument("--min-per-level", type=int, default=None, help="Mínim per nivell 1/2/3 (per defecte: max(1, min_questions // 3))")
    parser.add_argument("--no-verify", action="store_true", help="Omet verify_html_quiz.py")
    args = parser.parse_args()

    if args.extract:
        extract_slots_from_html(args.extract, args.out)
        return

    if not args.content:
        parser.error("Cal indicar el fitxer de contingut o bé --extract <fitxer.html>.")

    if args.no_verify:
        build(args.content, args.out)
        return

    min_lvl: int = args.min_per_level if args.min_per_level is not None else max(1, args.min_questions // 3)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=args.out.parent, prefix=".tmp_guide_", suffix=".html")
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        build(args.content, tmp_path)
        res = subprocess.run([
            sys.executable,
            str(VERIFIER),
            str(tmp_path),
            "--min-questions",
            str(args.min_questions),
            "--min-per-level",
            str(min_lvl),
            "--strict-guide",
        ])
        if res.returncode != 0:
            tmp_path.unlink(missing_ok=True)
            sys.exit(res.returncode)
        tmp_path.replace(args.out)
        print(f"Guia verificada i desada a: {args.out}")
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
