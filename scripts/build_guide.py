#!/usr/bin/env python3
"""
Build or extract an offline interactive HTML study guide using assets/template.html.

Build mode:
    python3 build_guide.py content.slots.txt -o Study_Guide.html [--min-questions 12]

Round-trip extract mode (reconstruct editable slots from a compiled HTML guide):
    python3 build_guide.py --extract Study_Guide.html -o content.slots.txt
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
from typing import Any, Dict, List, Tuple

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_DIR / "assets" / "template.html"
VERIFIER = SKILL_DIR / "scripts" / "verify_html_quiz.py"
REQUIRED_SLOTS = ("meta", "hero", "teoria", "practica", "quiz", "xuleta")
HTML_SLOTS = ("hero", "teoria", "practica", "xuleta")
VALID_PRESETS = ("warm-serif", "ink-editorial", "slate-tech")

_TEMPLATE_TOKEN_RE = re.compile(
    r"\{\{(ui\.\w+|LANG|PRESET|TITLE|TOPBAR_META|SIDEBAR_FOOT|NAV|META_JSON|QUIZ_JSON|slot\.(?:hero|teoria|practica|xuleta))\}\}"
)

UI_DEFAULTS: Dict[str, Dict[str, str]] = {
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
        "examMode": "Exam mode", "submitExam": "Submit exam", "timeLeft": "Time left", "exportAnki": "Anki (.tsv)",
        "score": "Level", "grade": "Score", "globalScore": "Total", "toReview": "To review",
        "noWrong": "No pending mistakes in this level.", "empty": "No questions in this level.",
        "allCorrect": "All correct.", "correctCount": "correct", "hint": "Hint", "exportProgress": "Progress for AI", "exportProgressHint": "Copy a summary of your mistakes to paste back to the AI so it can build a targeted review",
        "progressCopied": "Copied: paste it in the chat ✓", "progressSaved": "Saved .txt: paste it in the chat ✓",
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
        "examMode": "Modo examen", "submitExam": "Corregir examen", "timeLeft": "Tiempo", "exportAnki": "Anki (.tsv)",
        "score": "Nivel", "grade": "Nota", "globalScore": "Global", "toReview": "Por repasar",
        "noWrong": "Ningún error pendiente en este nivel.", "empty": "No hay preguntas en este nivel.",
        "allCorrect": "Todo correcto.", "correctCount": "correctas", "hint": "Pista", "exportProgress": "Progreso para la IA", "exportProgressHint": "Copia un resumen de tus fallos para pegarlo en el chat y que la IA prepare un repaso dirigido",
        "progressCopied": "Copiado: pégalo en el chat ✓", "progressSaved": "Guardado .txt: pégalo en el chat ✓",
    },
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
        "examMode": "Mode examen", "submitExam": "Corregir examen", "timeLeft": "Temps", "exportAnki": "Anki (.tsv)",
        "score": "Nivell", "grade": "Nota", "globalScore": "Global", "toReview": "Per repassar",
        "noWrong": "Cap error pendent en aquest nivell.", "empty": "No hi ha preguntes en aquest nivell.",
        "allCorrect": "Tot correcte.", "correctCount": "correctes", "hint": "Pista", "exportProgress": "Progrés per a la IA", "exportProgressHint": "Copia un resum dels teus errors per enganxar-lo al xat i que la IA prepari un repàs dirigit",
        "progressCopied": "Copiat: enganxa'l al xat ✓", "progressSaved": "Desat .txt: enganxa'l al xat ✓",
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
        "examMode": "Mode examen", "submitExam": "Valider l'examen", "timeLeft": "Temps", "exportAnki": "Anki (.tsv)",
        "score": "Niveau", "grade": "Note", "globalScore": "Total", "toReview": "À revoir",
        "noWrong": "Aucune erreur en attente dans ce niveau.", "empty": "Aucune question dans ce niveau.",
        "allCorrect": "Tout est correct.", "correctCount": "correctes", "hint": "Indice", "exportProgress": "Progrès pour l'IA", "exportProgressHint": "Copie un résumé de tes erreurs à coller dans le chat pour une révision ciblée",
        "progressCopied": "Copié : colle-le dans le chat ✓", "progressSaved": "Enregistré .txt : colle-le dans le chat ✓",
    },
    "de": {
        "index": "Inhalt", "closeIndex": "Inhalt schließen", "skipToContent": "Zum Inhalt",
        "filterPlaceholder": "Abschnitte filtern (/)...", "noMatches": "Keine Treffer.",
        "dark": "Dunkelmodus", "light": "Hellmodus",
        "print": "A4-Spickzettel", "printFull": "Gesamter Leitfaden",
        "copy": "Kopieren", "copied": "Kopiert ✓", "resetEx": "Zurücksetzen",
        "start": "Start", "theory": "Erklärung", "practice": "Lückentext-Übungen",
        "quiz": "Selbsttest I · II · III", "sheet": "A4-Spickzettel",
        "practiceEyebrow": "Block 2 · Übung", "practiceTitle": "Interaktive Übungen",
        "quizEyebrow": "Block 3 · Stufentest", "quizTitle": "3-Stufen-Quiz",
        "sheetEyebrow": "Block 4 · A4-Druck", "sheetTitle": "Spickzettel",
        "level1": "Stufe I · Grundlagen", "level2": "Stufe II · Anwendung", "level3": "Stufe III · Meisterschaft",
        "onlyWrong": "Nur Fehler wiederholen", "reset": "Stufe zurücksetzen",
        "examMode": "Prüfungsmodus", "submitExam": "Abgeben", "timeLeft": "Restzeit", "exportAnki": "Anki (.tsv)",
        "score": "Stufe", "grade": "Note", "globalScore": "Gesamt", "toReview": "Zu wiederholen",
        "noWrong": "Keine offenen Fehler in dieser Stufe.", "empty": "Keine Fragen in dieser Stufe.",
        "allCorrect": "Alles richtig.", "correctCount": "richtig", "hint": "Hinweis", "exportProgress": "Fortschritt für die KI", "exportProgressHint": "Kopiert eine Fehlerübersicht zum Einfügen in den Chat für eine gezielte Wiederholung",
        "progressCopied": "Kopiert: im Chat einfügen ✓", "progressSaved": "Als .txt gespeichert: im Chat einfügen ✓",
    },
    "pt": {
        "index": "Índice", "closeIndex": "Fechar índice", "skipToContent": "Ir para o conteúdo",
        "filterPlaceholder": "Filtrar seções (/)...", "noMatches": "Sem correspondências.",
        "dark": "Modo escuro", "light": "Modo claro",
        "print": "Resumo A4", "printFull": "Guia completo",
        "copy": "Copiar", "copied": "Copiado ✓", "resetEx": "Reiniciar",
        "start": "Início", "theory": "Explicação do professor", "practice": "Prática interativa",
        "quiz": "Autoavaliação I · II · III", "sheet": "Resumo A4",
        "practiceEyebrow": "Bloco 2 · Prática", "practiceTitle": "Atividades para completar",
        "quizEyebrow": "Bloco 3 · Autoavaliação progressiva", "quizTitle": "Quiz em 3 níveis",
        "sheetEyebrow": "Bloco 4 · Impressão A4", "sheetTitle": "Folha de resumo",
        "level1": "Nível I · Fundamentos", "level2": "Nível II · Aplicação", "level3": "Nível III · Domínio",
        "onlyWrong": "Rever apenas erros", "reset": "Reiniciar nível",
        "examMode": "Modo exame", "submitExam": "Corrigir exame", "timeLeft": "Tempo", "exportAnki": "Anki (.tsv)",
        "score": "Nível", "grade": "Nota", "globalScore": "Global", "toReview": "Para rever",
        "noWrong": "Nenhum erro pendente neste nível.", "empty": "Sem perguntas neste nível.",
        "allCorrect": "Tudo correto.", "correctCount": "corretas", "hint": "Dica", "exportProgress": "Progresso para a IA", "exportProgressHint": "Copia um resumo dos teus erros para colar no chat e a IA preparar uma revisão dirigida",
        "progressCopied": "Copiado: cola no chat ✓", "progressSaved": "Guardado .txt: cola no chat ✓",
    },
    "it": {
        "index": "Indice", "closeIndex": "Chiudi indice", "skipToContent": "Vai al contenuto",
        "filterPlaceholder": "Filtra sezioni (/)...", "noMatches": "Nessun risultato.",
        "dark": "Modalità scura", "light": "Modalità chiara",
        "print": "Scheda A4", "printFull": "Guida completa",
        "copy": "Copia", "copied": "Copiato ✓", "resetEx": "Ripristina",
        "start": "Inizio", "theory": "Spiegazione del docente", "practice": "Esercizi a completamento",
        "quiz": "Autovalutazione I · II · III", "sheet": "Scheda A4",
        "practiceEyebrow": "Blocco 2 · Pratica", "practiceTitle": "Attività interattive",
        "quizEyebrow": "Blocco 3 · Autovalutazione progressiva", "quizTitle": "Quiz in 3 livelli",
        "sheetEyebrow": "Blocco 4 · Stampa A4", "sheetTitle": "Scheda riassuntiva",
        "level1": "Livello I · Fondamenti", "level2": "Livello II · Applicazione", "level3": "Livello III · Padronanza",
        "onlyWrong": "Ripassa solo errori", "reset": "Ripristina livello",
        "examMode": "Modalità esame", "submitExam": "Consegna esame", "timeLeft": "Tempo", "exportAnki": "Anki (.tsv)",
        "score": "Livello", "grade": "Voto", "globalScore": "Totale", "toReview": "Da ripassare",
        "noWrong": "Nessun errore in sospeso in questo livello.", "empty": "Nessuna domanda in questo livello.",
        "allCorrect": "Tutto corretto.", "correctCount": "corrette", "hint": "Suggerimento", "exportProgress": "Progressi per l'IA", "exportProgressHint": "Copia un riepilogo dei tuoi errori da incollare in chat per un ripasso mirato",
        "progressCopied": "Copiato: incollalo in chat ✓", "progressSaved": "Salvato .txt: incollalo in chat ✓",
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
            f"JSON error in <!-- @slot {slot_name} --> (line {exc.lineno}, col {exc.colno}): {exc.msg}\n"
            f"  Line: {bad_line}\n"
            f"  → AI Fix: provide valid pure JSON inside '@slot {slot_name}' (no <script> tags or trailing commas)."
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
            f"Duplicate slots found: {', '.join(sorted(set(duplicates)))}. "
            f"→ AI Fix: each <!-- @slot NAME --> marker may appear only once."
        )
    unknown = sorted(set(slots) - set(REQUIRED_SLOTS))
    if unknown:
        raise SystemExit(
            f"Unknown slots found: {', '.join(unknown)}. "
            f"→ AI Fix: use only {', '.join(REQUIRED_SLOTS)}."
        )
    missing = [s for s in REQUIRED_SLOTS if s not in slots]
    if missing:
        raise SystemExit(
            f"Missing required slots: {', '.join(missing)}. "
            f"→ AI Fix: include all <!-- @slot NAME --> markers ({', '.join(REQUIRED_SLOTS)})."
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
        raise SystemExit("Error in @slot quiz: must be a non-empty JSON array of questions.")
    errs: List[str] = []
    ids = set()
    for i, q in enumerate(quiz, start=1):
        if not isinstance(q, dict):
            errs.append(f"Question {i}: each item must be a JSON object.")
            continue
        missing_fields = [f for f in ("id", "level", "q", "options", "correct", "why") if f not in q]
        if missing_fields:
            errs.append(f"Question {i}: missing required fields {missing_fields}.")
            continue
        qid = q["id"]
        if not isinstance(qid, str) or not qid.strip():
            errs.append(f"Question {i}: 'id' must be a non-empty string.")
        elif qid in ids:
            errs.append(f"Question {i}: duplicate id '{qid}'.")
        else:
            ids.add(qid)
        if not isinstance(q["q"], str) or not q["q"].strip():
            errs.append(f"Question {i} ({qid}): 'q' must be a non-empty string.")
        if type(q["level"]) is not int or q["level"] not in (1, 2, 3):
            errs.append(f"Question {i} ({qid}): 'level' must be integer 1, 2, or 3 (never boolean).")
        opts = q["options"]
        if not isinstance(opts, list) or len(opts) < 2:
            errs.append(f"Question {i} ({qid}): 'options' must contain at least 2 options.")
            continue
        norm_opts = [str(o).strip().lower() for o in opts]
        if any(not o for o in norm_opts) or len(set(norm_opts)) != len(norm_opts):
            errs.append(f"Question {i} ({qid}): contains empty or duplicate options.")
        if type(q["correct"]) is not int or not 0 <= q["correct"] < len(opts):
            errs.append(f"Question {i} ({qid}): 'correct' must be an integer within 0..{len(opts) - 1}.")
        if not isinstance(q["why"], str) or not q["why"].strip():
            errs.append(f"Question {i} ({qid}): 'why' cannot be empty.")
    if errs:
        raise SystemExit("\n".join(errs))


def json_for_script(data: object, *, multiline: bool = False) -> str:
    indent = 2 if multiline else None
    return json.dumps(data, ensure_ascii=False, indent=indent).replace("<", "\\u003c")


def _read_text_or_exit(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise SystemExit(f"Error: file does not exist: {path}")
    except OSError as exc:
        raise SystemExit(f"Error reading {path}: {exc}")


def build(content_path: Path, out_path: Path) -> None:
    slots = parse_slots(_read_text_or_exit(content_path))
    meta = _parse_json_slot(slots["meta"], "meta")
    if not isinstance(meta, dict):
        raise SystemExit("Error in @slot meta: must be a JSON object.")

    lang = str(meta.get("lang", "en")).strip() or "en"
    meta["lang"] = lang
    preset = str(meta.get("themePreset", "warm-serif")).strip() or "warm-serif"
    if preset not in VALID_PRESETS:
        raise SystemExit(
            f"Unknown themePreset '{preset}' in @slot meta. "
            f"→ AI Fix: use one of {', '.join(VALID_PRESETS)}."
        )

    defaults = UI_DEFAULTS.get(lang, UI_DEFAULTS["en"])
    raw_ui = meta.get("ui")
    if raw_ui is not None:
        if not isinstance(raw_ui, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in raw_ui.items()):
            raise SystemExit("Error in @slot meta.ui: all keys and values must be strings.")
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
        "PRESET": html.escape(preset),
        "TITLE": html.escape(str(meta.get("title", ""))),
        "TOPBAR_META": html.escape(str(meta.get("topbarMeta", ""))),
        "SIDEBAR_FOOT": html.escape(str(meta.get("sidebarFoot", "Study Guide"))),
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
        raise SystemExit(f"Template tokens without mapped value: {missing_keys}")

    # Single-pass substitution prevents user code snippets or meta fields from colliding with template tokens
    out = _TEMPLATE_TOKEN_RE.sub(lambda m: token_values[m.group(1)], template_text)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(out, encoding="utf-8")
    print(f"Built guide: {out_path} ({len(out.encode('utf-8'))} bytes, {len(quiz)} questions, preset={preset})")


def extract_slots_from_html(html_path: Path, out_path: Path) -> None:
    raw = _read_text_or_exit(html_path)
    meta_m = re.search(r'<script[^>]+id=["\']guide-meta["\'][^>]*>(.*?)</script>', raw, flags=re.DOTALL | re.IGNORECASE)
    quiz_m = re.search(r'<script[^>]+id=["\']quiz-data["\'][^>]*>(.*?)</script>', raw, flags=re.DOTALL | re.IGNORECASE)
    if not meta_m or not quiz_m:
        raise SystemExit(f"Missing #guide-meta or #quiz-data in {html_path}. Only guides built with template.html can be extracted.")

    try:
        meta = json.loads(meta_m.group(1))
        quiz = json.loads(quiz_m.group(1))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Malformed JSON inside {html_path}: {exc}")

    lang = meta.get("lang", "en")
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
            raise SystemExit(f"Missing round-trip marker <!-- @slot-begin:{key} --> in {html_path}.")
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
    print(f"Extracted slots to: {out_path} ({len(quiz)} questions)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile or extract offline interactive HTML study guides")
    parser.add_argument("content", nargs="?", type=Path, help="Slots content file (compile mode)")
    parser.add_argument("--extract", type=Path, metavar="HTML_FILE", help="Extract editable 6 slots from a compiled HTML guide")
    parser.add_argument("-o", "--out", type=Path, required=True, help="Output file path (.html or .slots.txt)")
    parser.add_argument("--min-questions", type=int, default=12, help="Minimum global question count (default: 12)")
    parser.add_argument("--min-per-level", type=int, default=None, help="Minimum per level 1/2/3 (default: max(1, min_questions // 3))")
    parser.add_argument("--no-verify", action="store_true", help="Skip verify_html_quiz.py")
    args = parser.parse_args()

    if args.extract:
        extract_slots_from_html(args.extract, args.out)
        return

    if not args.content:
        parser.error("Provide either a content slots file or --extract <file.html>.")

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
        print(f"Verified and saved guide: {args.out}")
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    main()
