#!/usr/bin/env python3
"""
Anti-bias and structural verifier for HTML study guides and quizzes.
Checks global AND per-level quiz balance with prescriptive AI fix hints, plus
optional strict structural validation (100% offline, DOM-safe, dark-mode SVGs,
HTML sanitization, and solvable Block 4 autocomplete exercises).
"""

from __future__ import annotations

import argparse
import html as html_lib
import json
import math
import re
import sys
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_TRIVIAL_ALL_NONE_RE = re.compile(
    r"^(?:totes\s+les\s+anteriors|cap\s+de\s+les\s+anteriors|"
    r"todas\s+las\s+anteriores|ninguna\s+de\s+las\s+anteriores|"
    r"all\s+of\s+the\s+above|none\s+of\s+the\s+above|"
    r"toutes\s+les\s+r[ée]ponses|aucune\s+des\s+r[ée]ponses)\.?$",
    re.IGNORECASE,
)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _norm(raw: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(raw)).strip().lower()


def _clean_plain_text(raw: str) -> str:
    """Clean JSON string option text without stripping technical tags like List<String>."""
    txt = html_lib.unescape(raw)
    txt = re.sub(r"\s+", " ", txt).strip()
    txt = re.sub(r"^[A-Da-d][\)\.\-:]\s+", "", txt)
    return txt.strip()


def _clean_option_text(raw: str) -> str:
    """Clean HTML DOM extracted option text by removing markup tags."""
    txt = re.sub(r"<[^>]+>", " ", raw)
    return _clean_plain_text(txt)


def _extract_balanced_array(text: str, start_bracket_idx: int) -> Optional[str]:
    depth = 0
    in_str: Optional[str] = None
    escaped = False
    for idx in range(start_bracket_idx, len(text)):
        ch = text[idx]
        if in_str is not None:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'", "`"):
            in_str = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return text[start_bracket_idx : idx + 1]
    return None


def _parse_js_string(raw: str, start_idx: int) -> Tuple[str, int]:
    quote = raw[start_idx]
    out: List[str] = []
    idx = start_idx + 1
    while idx < len(raw):
        ch = raw[idx]
        if ch == "\\" and idx + 1 < len(raw):
            nxt = raw[idx + 1]
            escape_map = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"', "`": "`"}
            out.append(escape_map.get(nxt, nxt))
            idx += 2
            continue
        if ch == quote:
            return "".join(out), idx + 1
        out.append(ch)
        idx += 1
    return "".join(out), idx


def _parse_js_string_array(raw_arr: str) -> List[str]:
    items: List[str] = []
    idx = 0
    while idx < len(raw_arr):
        ch = raw_arr[idx]
        if ch in ('"', "'", "`"):
            val, idx = _parse_js_string(raw_arr, idx)
            items.append(val)
        else:
            idx += 1
    return items


def _extract_div_blocks_by_class(raw_html: str, cls_name: str) -> List[str]:
    blocks: List[str] = []
    cls_re = re.compile(rf'\bclass=["\'][^"\']*\b{re.escape(cls_name)}\b[^"\']*["\']', re.IGNORECASE)
    tag_re = re.compile(r"<div\b[^>]*>|</div\s*>", re.IGNORECASE)
    tokens = list(tag_re.finditer(raw_html))
    for i, tok in enumerate(tokens):
        tag_txt = tok.group(0)
        if tag_txt.lower().startswith("<div") and cls_re.search(tag_txt):
            depth = 0
            for j in range(i, len(tokens)):
                if tokens[j].group(0).lower().startswith("<div"):
                    depth += 1
                else:
                    depth -= 1
                    if depth == 0:
                        blocks.append(raw_html[tok.start() : tokens[j].end()])
                        break
    return blocks


def _attr_val(tag: str, attr: str) -> Optional[str]:
    m = re.search(rf'\b{re.escape(attr)}=(["\'])(.*?)\1', tag, flags=re.DOTALL | re.IGNORECASE)
    return m.group(2) if m else None


class _StructureSecurityParser(HTMLParser):
    """Inspect HTML tags for unsafe attributes, iframes, javascript: URLs, and extra scripts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.errors: List[str] = []
        self.engine_scripts = 0
        self.allowed_json_ids = {"guide-meta", "quiz-data"}
        self.in_svg_stack = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        t = tag.lower()
        attr_map = {k.lower(): (v or "") for k, v in attrs}

        if t == "svg":
            self.in_svg_stack += 1

        if t in ("iframe", "embed"):
            self.errors.append(
                f"Seguretat HTML: etiqueta prohibida <{t}>. → Correcció IA: elimina <{t}> i usa HTML/SVG nadiu."
            )

        if t == "script":
            stype = attr_map.get("type", "").lower()
            sid = attr_map.get("id", "")
            if "src" in attr_map:
                self.errors.append(
                    f"Seguretat/Offline: <script src='{attr_map['src']}'> prohibit. → Correcció IA: cap script extern."
                )
            elif "application/json" in stype and sid in self.allowed_json_ids:
                pass
            else:
                self.engine_scripts += 1
                if self.engine_scripts > 1:
                    self.errors.append(
                        "Seguretat HTML: s'ha detectat un <script> addicional fora del motor de la plantilla. "
                        "→ Correcció IA: no escriguis blocs <script> dins els slots."
                    )

        for k, v in attrs:
            kl = k.lower()
            val = (v or "").strip()
            if kl.startswith("on"):
                self.errors.append(
                    f"Seguretat DOM: atribut inline prohibit '{k}=' a <{t}>. "
                    "→ Correcció IA: elimina els handlers inline dels slots."
                )
            if kl in ("href", "src", "data", "poster", "formaction", "xlink:href"):
                normalized_scheme = re.sub(r"[\s\x00-\x1f]+", "", val).lower()
                if normalized_scheme.startswith("javascript:") or normalized_scheme.startswith("vbscript:"):
                    self.errors.append(
                        f"Seguretat URL: esquema prohibit '{val}' a <{t} {k}=...>. "
                        "→ Correcció IA: usa ancoratges '#id' o rutes segures."
                    )

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "svg" and self.in_svg_stack > 0:
            self.in_svg_stack -= 1


def audit_guide_structure(raw_html: str) -> Tuple[List[str], List[str]]:
    """Verify offline purity, required 4 blocks, DOM safety, dark-mode SVGs, and Block 4 solvability."""
    errors: List[str] = []
    warnings: List[str] = []

    lang_m = re.search(r'<html\b[^>]*\blang=["\']([^"\']*)["\']', raw_html, flags=re.IGNORECASE)
    if not lang_m or not lang_m.group(1).strip() or "{{" in lang_m.group(1):
        errors.append("Estructura: falta <html lang='...'> vàlid. → Correcció IA: defineix 'lang' dins @slot meta.")

    for req_id in ("teoria", "practica", "autoavaluacio", "xuleta"):
        if not re.search(rf'\bid=["\']{req_id}["\']', raw_html):
            errors.append(f"Estructura: falta el contenidor obligatori #{req_id}.")

    if "@media print" not in raw_html:
        errors.append("Estructura: falta la regla @media print per a la Xuleta A4.")

    # Strip code blocks and script bodies before checking remote tags/URLs so code examples don't trigger false positives
    non_code_html = re.sub(r"<pre\b[^>]*>.*?</pre>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    non_code_html = re.sub(r"<code\b[^>]*>.*?</code>", "", non_code_html, flags=re.DOTALL | re.IGNORECASE)
    non_code_html = re.sub(r"<script\b([^>]*)>.*?</script>", r"<script\1></script>", non_code_html, flags=re.DOTALL | re.IGNORECASE)

    ext_attr_refs = re.findall(
        r'<(?:script|img|iframe|link|video|audio|source|object|embed)\b[^>]*\b(?:src|href|data|poster)=["\']\s*((?:https?:)?//[^"\']+)["\']',
        non_code_html,
        flags=re.IGNORECASE,
    )
    for url in ext_attr_refs:
        errors.append(f"Offline: recurs extern prohibit '{url}'. → Correcció IA: fes tot el CSS, fonts i SVG 100% inline.")

    for style_body in re.findall(r"<style\b[^>]*>(.*?)</style>", raw_html, flags=re.DOTALL | re.IGNORECASE):
        css_urls = re.findall(
            r'(?:@import\s+(?:url\()?\s*["\']?((?:https?:)?//[^"\')\s]+)|url\(\s*["\']?((?:https?:)?//[^"\')\s]+))',
            style_body,
            flags=re.IGNORECASE,
        )
        for tup in css_urls:
            url = next((u for u in tup if u), "")
            errors.append(f"Offline CSS: recurs extern prohibit '{url}'. → Correcció IA: elimina URLs externes del CSS.")

    # HTMLParser tag & attribute security check
    sec_parser = _StructureSecurityParser()
    sec_parser.feed(non_code_html)
    sec_parser.close()
    errors.extend(sec_parser.errors)

    # DOM safety check on executable <script> tags
    for sc_m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", raw_html, flags=re.DOTALL | re.IGNORECASE):
        attrs, body = sc_m.group(1), sc_m.group(2)
        if "application/json" in attrs.lower():
            continue
        if re.search(
            r"\.(?:innerHTML|outerHTML)\s*[+]?=|\binsertAdjacentHTML\s*\(|\bdocument\.write\s*\(|\beval\s*\(|\bnew\s+Function\s*\(",
            body,
        ):
            errors.append(
                "Seguretat DOM: ús prohibit d'innerHTML/outerHTML/insertAdjacentHTML/document.write/eval. "
                "→ Correcció IA: usa createElement i textContent."
            )

    # Dark-mode SVG check
    for idx, svg_body in enumerate(re.findall(r"<svg\b.*?</svg>", raw_html, flags=re.DOTALL | re.IGNORECASE), start=1):
        bad_color = re.search(
            r'(?:fill|stroke)\s*[:=]\s*["\']?\s*(#000(?:000)?|#111(?:111)?|#1f2421|black)\b',
            svg_body,
            flags=re.IGNORECASE,
        )
        if bad_color:
            errors.append(
                f"SVG #{idx}: color fosc fix '{bad_color.group(1)}' invisible en mode fosc. "
                f"→ Correcció IA: usa style='fill:var(--ink)' o 'stroke:var(--border-strong)'."
            )

    # Block 4 solvability check
    exercises = _extract_div_blocks_by_class(raw_html, "exercise")
    if not exercises:
        warnings.append("Bloc 4: no s'ha trobat cap bloc .exercise dins #practica.")
    for ex_idx, ex_html in enumerate(exercises, start=1):
        chip_vals = set()
        for span_tag in re.findall(r"<span\b[^>]*>", ex_html, flags=re.IGNORECASE):
            cls = (_attr_val(span_tag, "class") or "").split()
            val = _attr_val(span_tag, "data-val")
            if "chip" in cls and val is not None:
                chip_vals.add(_norm(val))

        for span_tag in re.findall(r"<span\b[^>]*>", ex_html, flags=re.IGNORECASE):
            cls = (_attr_val(span_tag, "class") or "").split()
            ans = _attr_val(span_tag, "data-ans")
            if "slot" in cls and ans is None:
                errors.append(f"Bloc 4 Exercici #{ex_idx}: hi ha un <span class='slot'> sense atribut data-ans.")
            elif "slot" in cls and ans is not None:
                alts = [_norm(a) for a in ans.split("|") if _norm(a)]
                if not alts or not any(a in chip_vals for a in alts):
                    errors.append(
                        f"Bloc 4 Exercici #{ex_idx}: el buit data-ans='{ans}' no té cap .chip[data-val] coincident "
                        f"(disponibles: {sorted(chip_vals)}). → Correcció IA: afegeix <span class=\"chip\" data-val=\"{ans.split('|')[0]}\">."
                    )

        for inp_tag in re.findall(r"<input\b[^>]*>", ex_html, flags=re.IGNORECASE):
            ans = _attr_val(inp_tag, "data-ans")
            if ans is not None and not _norm(ans):
                errors.append(f"Bloc 4 Exercici #{ex_idx}: hi ha un <input> amb data-ans buit.")

        for sel_m in re.finditer(r"(<select\b[^>]*>)(.*?)</select>", ex_html, flags=re.DOTALL | re.IGNORECASE):
            sel_tag, sel_body = sel_m.group(1), sel_m.group(2)
            ans = _attr_val(sel_tag, "data-ans")
            if ans is None:
                continue
            alts = [_norm(a) for a in ans.split("|") if _norm(a)]
            opt_vals = set()
            for opt_m in re.finditer(r"(<option\b[^>]*>)(.*?)</option>", sel_body, flags=re.DOTALL | re.IGNORECASE):
                v = _attr_val(opt_m.group(1), "value")
                opt_vals.add(_norm(v if v is not None else re.sub(r"<[^>]+>", "", opt_m.group(2))))
            if not alts or not any(a in opt_vals for a in alts):
                errors.append(
                    f"Bloc 4 Exercici #{ex_idx}: el <select data-ans='{ans}'> no té cap <option> amb aquest valor "
                    f"(opcions: {sorted(opt_vals)})."
                )

    return errors, warnings


def extract_questions(raw_html: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Extract quiz questions from JSON script, JS QUIZ array, or HTML DOM cards."""
    json_match = re.search(
        r'<script[^>]+id=["\']quiz-data["\'][^>]*>(.*?)</script>',
        raw_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if json_match:
        try:
            data = json.loads(json_match.group(1).strip().replace("<\\/", "</"))
        except json.JSONDecodeError:
            return "json-invalid", []
        if isinstance(data, list) and data:
            parsed: List[Dict[str, Any]] = []
            for idx, item in enumerate(data, start=1):
                if not isinstance(item, dict):
                    continue
                opts = item.get("options") if "options" in item else item.get("opts", [])
                corr = item.get("correct") if "correct" in item else item.get("a")
                if isinstance(opts, list) and ("correct" in item or "a" in item):
                    entry: Dict[str, Any] = {
                        "num": idx,
                        "id": str(item.get("id", f"q{idx}")),
                        "q": _clean_plain_text(str(item.get("q", f"Q{idx}"))),
                        "options": [_clean_plain_text(str(o)) for o in opts],
                        "correct": corr,
                    }
                    if "level" in item and item["level"] is not None:
                        entry["level"] = item["level"]
                    parsed.append(entry)
            if parsed:
                return "json-quiz-data", parsed

    js_match = re.search(r"(?:const|let|var)\s+QUIZ\s*=\s*\[", raw_html)
    if js_match:
        arr_start = raw_html.find("[", js_match.start())
        arr_body = _extract_balanced_array(raw_html, arr_start)
        if arr_body:
            parsed_js: List[Dict[str, Any]] = []
            pos = 0
            q_num = 0
            for opts_m in re.finditer(r"\b(?:opts|options)\s*:\s*\[", arr_body):
                q_num += 1
                inner_arr = _extract_balanced_array(arr_body, opts_m.end() - 1)
                if not inner_arr:
                    continue
                opts = [_clean_option_text(o) for o in _parse_js_string_array(inner_arr)]
                after_slice = arr_body[opts_m.end() + len(inner_arr) - 1 : opts_m.end() + len(inner_arr) + 200]
                ans_m = re.search(r"\b(?:a|correct)\s*:\s*(\d+)", after_slice)
                if not ans_m:
                    continue
                q_slice = arr_body[pos : opts_m.start()]
                q_text_m = re.search(r'\bq\s*:\s*(["\'])(.*?)\1', q_slice, flags=re.DOTALL)
                q_label = _clean_option_text(q_text_m.group(2)) if q_text_m else f"Q{q_num}"
                pos = opts_m.end()
                parsed_js.append(
                    {
                        "num": q_num,
                        "id": f"q{q_num}",
                        "q": q_label,
                        "options": opts,
                        "correct": int(ans_m.group(1)),
                    }
                )
            if parsed_js:
                return "js-QUIZ", parsed_js

    cards = re.findall(
        r'<div[^>]+class=["\'][^"\']*quiz-question-card[^"\']*["\'][^>]*data-correct=["\'](\d+)["\'][^>]*>(.*?)<div[^>]+class=["\'][^"\']*explanation-box',
        raw_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if cards:
        parsed_cards: List[Dict[str, Any]] = []
        for idx, (corr_s, body) in enumerate(cards, start=1):
            btns = re.findall(
                r'<button[^>]+class=["\'][^"\']*quiz-option-btn[^"\']*["\'][^>]*>(.*?)</button>',
                body,
                flags=re.DOTALL | re.IGNORECASE,
            )
            if btns:
                parsed_cards.append(
                    {
                        "num": idx,
                        "id": f"card_{idx}",
                        "q": f"Card {idx}",
                        "options": [_clean_option_text(b) for b in btns],
                        "correct": int(corr_s),
                    }
                )
        if parsed_cards:
            return "dom-quiz-card", parsed_cards

    boxes = re.findall(
        r'<div[^>]+class=["\'][^"\']*quiz-question-box[^"\']*["\'][^>]*data-qid=["\'](\d+)["\'][^>]*>(.*?)<div[^>]+class=["\'][^"\']*quiz-feedback',
        raw_html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if boxes:
        parsed_boxes: List[Dict[str, Any]] = []
        for qid_s, body in boxes:
            btns = re.findall(
                r"checkAnswer\(\s*\d+\s*,\s*(\d+)\s*,\s*(true|false)\s*\)[^>]*>(.*?)</button>",
                body,
                flags=re.DOTALL | re.IGNORECASE,
            )
            if btns:
                corr_indices = [int(i) for i, flag, _ in btns if flag.lower() == "true"]
                if corr_indices:
                    parsed_boxes.append(
                        {
                            "num": int(qid_s),
                            "id": f"box_{qid_s}",
                            "q": f"Box {qid_s}",
                            "options": [_clean_option_text(txt) for _, _, txt in btns],
                            "correct": corr_indices[0],
                        }
                    )
        if parsed_boxes:
            return "dom-quiz-box", parsed_boxes

    return "none", []


def _audit_distribution(
    questions: List[Dict[str, Any]],
    *,
    scope_label: Optional[str],
    max_letter_ratio_ge6: float,
    max_longest_ratio: float,
    require_all_slots_ge8: bool,
) -> Tuple[List[str], Dict[str, Any]]:
    """Audit letter distribution, all consecutive streaks >= 3, and longest-option ratio."""
    errors: List[str] = []
    max_opts = max((len(q.get("options", [])) for q in questions), default=4)
    slot_count = max(2, max_opts)
    pos_counts: Dict[int, int] = {i: 0 for i in range(slot_count)}
    correct_seq: List[int] = []
    seq_meta: List[Tuple[int, str]] = []
    longest_eligible = 0
    longest_correct_hits = 0

    for idx, item in enumerate(questions, start=1):
        opts = item["options"]
        corr = item["correct"]
        if len(opts) < 2 or not _is_int(corr) or corr < 0 or corr >= len(opts):
            continue

        num = int(item.get("num", idx))
        pos_counts[corr] = pos_counts.get(corr, 0) + 1
        correct_seq.append(corr)
        seq_meta.append((num, str(item.get("id", f"P{num}"))))

        lens = [len(o) for o in opts]
        corr_len = lens[corr]
        dist_lens = [lens[i] for i in range(len(opts)) if i != corr]
        max_dist = max(dist_lens)
        if max(lens) >= 25:
            longest_eligible += 1
            if corr_len > max_dist:
                longest_correct_hits += 1

    n_valid = len(correct_seq)
    prefix = f"[{scope_label}] " if scope_label else ""
    min_cnt = min(pos_counts.values()) if pos_counts else 0
    underused = [f"{chr(65 + k)} (correct={k})" for k, v in sorted(pos_counts.items()) if v == min_cnt]

    if n_valid >= 6:
        max_allowed = math.ceil(n_valid * max_letter_ratio_ge6)
        for idx, cnt in sorted(pos_counts.items()):
            letter = chr(65 + idx)
            if cnt > max_allowed:
                errors.append(
                    f"{prefix}Sesgo de lletra '{letter}': apareix {cnt}/{n_valid} vegades com a correcta (màxim permès: {max_allowed}). "
                    f"→ Correcció IA: intercanvia l'opció correcta cap a {', '.join(underused)}."
                )
    elif n_valid >= 4:
        max_allowed_small = math.floor(n_valid * 0.50)
        for idx, cnt in sorted(pos_counts.items()):
            letter = chr(65 + idx)
            if cnt > max_allowed_small:
                errors.append(
                    f"{prefix}Sesgo de lletra '{letter}': apareix {cnt}/{n_valid} vegades com a correcta (màxim permès: {max_allowed_small}). "
                    f"→ Correcció IA: intercanvia l'opció correcta cap a {', '.join(underused)}."
                )

    if require_all_slots_ge8 and n_valid >= 8:
        missing = [chr(65 + idx) for idx in range(slot_count) if pos_counts.get(idx, 0) == 0]
        if missing:
            errors.append(
                f"{prefix}Distribució incompleta: les posicions {', '.join(missing)} no s'han fet servir cap vegada amb {n_valid} preguntes. "
                f"→ Correcció IA: mou alguna resposta correcta a {', '.join(missing)}."
            )

    # Report every contiguous streak >= 3 across the subset
    run_start = 0
    for idx in range(1, len(correct_seq) + 1):
        at_end = idx == len(correct_seq)
        if at_end or correct_seq[idx] != correct_seq[run_start]:
            run_len = idx - run_start
            if run_len >= 3:
                letter = chr(65 + correct_seq[run_start])
                mid = run_start + 1
                s_num, s_id = seq_meta[run_start]
                e_num, e_id = seq_meta[idx - 1]
                m_num, m_id = seq_meta[mid]
                errors.append(
                    f"{prefix}Ratxa previsible: {run_len} respostes consecutives amb la lletra '{letter}' "
                    f"(P{s_num} [{s_id}]..P{e_num} [{e_id}]). "
                    f"→ Correcció IA: canvia la posició correcta de P{m_num} ({m_id})."
                )
            run_start = idx

    if longest_eligible >= 4:
        ratio_longest = longest_correct_hits / longest_eligible
        if ratio_longest > max_longest_ratio:
            scope_word = "de nivell" if scope_label else "global"
            errors.append(
                f"{prefix}Sesgo {scope_word} de longitud: la resposta correcta és la més llarga en {longest_correct_hits}/{longest_eligible} "
                f"preguntes ({ratio_longest:.0%} > {max_longest_ratio:.0%} màxim permès). "
                f"→ Correcció IA: escurça les respostes correctes o detalla un distractor perquè sigui més llarg."
            )

    stats = {
        "questions": len(questions),
        "letter_distribution": {chr(65 + k): v for k, v in sorted(pos_counts.items())},
        "longest_eligible": longest_eligible,
        "longest_correct_hits": longest_correct_hits,
        "longest_ratio": round(longest_correct_hits / longest_eligible, 3) if longest_eligible else 0.0,
    }
    return errors, stats


def audit_quiz(
    questions: List[Dict[str, Any]],
    min_questions: int = 4,
    *,
    min_per_level: int = 0,
) -> Dict[str, Any]:
    """Run global and per-level letter-distribution, length-bias, duplicate, and shortcut checks."""
    errors: List[str] = []
    warnings: List[str] = []
    n = len(questions)

    if n == 0:
        errors.append("No s'ha trobat cap pregunta de test reconeixible a l'HTML.")
        return {"ok": False, "count": 0, "errors": errors, "warnings": warnings, "stats": {}}

    if n < min_questions:
        errors.append(f"Només hi ha {n} preguntes (mínim requerit: {min_questions}).")
    elif n < 8:
        warnings.append(f"Només hi ha {n} preguntes; per a simulacres d'examen es recomana >= 8.")

    per_question_issues: List[Dict[str, Any]] = []

    for idx, item in enumerate(questions, start=1):
        num = item.get("num", idx)
        qid = item.get("id", f"P{num}")
        opts = item["options"]
        corr = item["correct"]

        if "level" in item and isinstance(item["level"], bool):
            errors.append(f"P{num} ({qid}): 'level' no pot ser booleà ({item['level']}). → Correcció IA: usa 1, 2 o 3.")

        if len(opts) < 2:
            errors.append(f"P{num} ({qid}): té menys de 2 opcions.")
            continue
        if not _is_int(corr):
            errors.append(f"P{num} ({qid}): 'correct' ha de ser un enter (no booleà/text: {corr!r}).")
            continue
        if corr < 0 or corr >= len(opts):
            errors.append(f"P{num} ({qid}): índex correct={corr} fora de rang (0..{len(opts) - 1}).")
            continue

        norm_opts = [_norm(o) for o in opts]
        if any(not o for o in norm_opts) or len(set(norm_opts)) != len(norm_opts):
            errors.append(f"P{num} ({qid}): conté opcions buides o duplicades. → Correcció IA: fes les 4 opcions diferents.")

        corr_text = opts[corr]
        if _TRIVIAL_ALL_NONE_RE.match(corr_text):
            errors.append(f"P{num} ({qid}): la resposta correcta és una opció comodí ('{corr_text}').")

        lens = [len(o) for o in opts]
        corr_len = lens[corr]
        dist_lens = [lens[i] for i in range(len(opts)) if i != corr]
        max_dist = max(dist_lens)
        mean_dist = sum(dist_lens) / len(dist_lens)

        if corr_len >= 30 and (corr_len - max_dist) > 8:
            ratio_max = corr_len / max(max_dist, 1)
            ratio_mean = corr_len / max(mean_dist, 1.0)
            if ratio_max > 1.20 or ratio_mean > 1.35:
                max_safe = min(int(max_dist * 1.20), int(mean_dist * 1.35))
                msg = (
                    f"P{num} ({qid}): opció correcta massa llarga ({corr_len} chars vs distractors {dist_lens}, "
                    f"ratio_max={ratio_max:.2f}x, ratio_mean={ratio_mean:.2f}x). "
                    f"→ Correcció IA: escurça la correcta a <= {max_safe} caràcters o amplia els distractors."
                )
                errors.append(msg)
                per_question_issues.append(
                    {
                        "num": num,
                        "correct_len": corr_len,
                        "distractor_lens": dist_lens,
                        "ratio_max": round(ratio_max, 2),
                        "ratio_mean": round(ratio_mean, 2),
                    }
                )

    global_errors, global_stats = _audit_distribution(
        questions,
        scope_label=None,
        max_letter_ratio_ge6=0.35,
        max_longest_ratio=0.30,
        require_all_slots_ge8=True,
    )
    errors.extend(global_errors)

    level_buckets: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    for item in questions:
        if "level" in item and not isinstance(item["level"], bool):
            lvl_key = str(item["level"])
            level_buckets.setdefault(lvl_key, []).append(item)

    if min_per_level > 0:
        for req_lvl in ("1", "2", "3"):
            cnt = len(level_buckets.get(req_lvl, []))
            if cnt < min_per_level:
                errors.append(
                    f"[Nivell {req_lvl}] Només té {cnt} preguntes (mínim per nivell: {min_per_level}). "
                    f"→ Correcció IA: afegeix {min_per_level - cnt} preguntes amb \"level\": {req_lvl}."
                )

    per_level_stats: Dict[str, Any] = {}
    if level_buckets:
        for lvl_key, lvl_questions in level_buckets.items():
            lvl_errors, lvl_stats = _audit_distribution(
                lvl_questions,
                scope_label=f"Nivell {lvl_key}",
                max_letter_ratio_ge6=0.35,
                max_longest_ratio=0.35,
                require_all_slots_ge8=True,
            )
            errors.extend(lvl_errors)
            per_level_stats[lvl_key] = lvl_stats

    stats = {
        **global_stats,
        "length_outliers": per_question_issues,
    }
    if per_level_stats:
        stats["per_level"] = per_level_stats

    return {"ok": len(errors) == 0, "count": n, "errors": errors, "warnings": warnings, "stats": stats}


def verify_html_file(
    path: Path,
    min_questions: int = 4,
    *,
    strict_guide: bool = False,
    min_per_level: int = 0,
) -> Dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    fmt, questions = extract_questions(raw)
    if fmt == "json-invalid":
        report: Dict[str, Any] = {
            "ok": False,
            "count": 0,
            "errors": ["JSON invàlid dins <script id='quiz-data'>. → Correcció IA: revisa la sintaxi JSON del banc de preguntes."],
            "warnings": [],
            "stats": {},
        }
    else:
        report = audit_quiz(questions, min_questions=min_questions, min_per_level=min_per_level)

    if strict_guide:
        struct_errors, struct_warnings = audit_guide_structure(raw)
        report["errors"] = struct_errors + report["errors"]
        report["warnings"] = struct_warnings + report["warnings"]
        report["ok"] = len(report["errors"]) == 0
    report["file"] = str(path)
    report["format"] = fmt
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Verificador anti-sesgo i estructural de guies HTML")
    parser.add_argument("html_file", type=Path, help="Ruta del fitxer HTML a auditar")
    parser.add_argument("--min-questions", type=int, default=4, help="Mínim de preguntes globals (per defecte: 4)")
    parser.add_argument("--min-per-level", type=int, default=0, help="Mínim de preguntes per nivell 1/2/3 (per defecte: 0)")
    parser.add_argument("--strict-guide", action="store_true", help="Audita també blocs HTML, offline, seguretat DOM, SVG fosc i Bloc 4")
    parser.add_argument("--json", action="store_true", help="Retorna l'informe en format JSON")
    args = parser.parse_args()

    if not args.html_file.exists():
        print(f"Error: no existeix el fitxer {args.html_file}", file=sys.stderr)
        sys.exit(2)

    report = verify_html_file(
        args.html_file,
        min_questions=args.min_questions,
        strict_guide=args.strict_guide,
        min_per_level=args.min_per_level,
    )
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        status = "PASS" if report["ok"] else "FAIL"
        stats = report.get("stats", {})
        print(f"[{status}] {args.html_file.name} (format={report['format']}, preguntes={report['count']})")
        if stats:
            print(
                f"  Distribució lletres: {stats.get('letter_distribution')} | "
                f"Correcta més llarga: {stats.get('longest_correct_hits')}/{stats.get('longest_eligible')} "
                f"({stats.get('longest_ratio', 0):.0%})"
            )
            for lvl_key, lvl_stats in stats.get("per_level", {}).items():
                print(
                    f"  Nivell {lvl_key} ({lvl_stats.get('questions')}p): "
                    f"lletres={lvl_stats.get('letter_distribution')} | "
                    f"més llarga={lvl_stats.get('longest_correct_hits')}/{lvl_stats.get('longest_eligible')} "
                    f"({lvl_stats.get('longest_ratio', 0):.0%})"
                )
        for w in report["warnings"]:
            print(f"  AVÍS: {w}")
        for err in report["errors"]:
            print(f"  ERROR: {err}")

    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
