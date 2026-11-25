#!/usr/bin/env python3
"""
Anti-bias and structural verifier for HTML study guides and quizzes.
Checks global AND per-level quiz balance with prescriptive AI fix hints, plus
optional strict structural validation (100% offline, DOM-safe, dark-mode SVGs,
HTML sanitization, and solvable Block 2 autocomplete exercises).
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
                f"HTML security: forbidden <{t}> tag. → AI Fix: remove <{t}> and use native HTML/SVG."
            )

        if t == "script":
            stype = attr_map.get("type", "").lower()
            sid = attr_map.get("id", "")
            if "src" in attr_map:
                self.errors.append(
                    f"Security/Offline: forbidden <script src='{attr_map['src']}'>. → AI Fix: no external scripts allowed."
                )
            elif "application/json" in stype and sid in self.allowed_json_ids:
                pass
            else:
                self.engine_scripts += 1
                if self.engine_scripts > 1:
                    self.errors.append(
                        "HTML security: extra <script> detected outside the template engine. "
                        "→ AI Fix: do not write <script> blocks inside content slots."
                    )

        for k, v in attrs:
            kl = k.lower()
            val = (v or "").strip()
            if kl.startswith("on"):
                self.errors.append(
                    f"DOM security: forbidden inline event handler '{k}=' on <{t}>. "
                    "→ AI Fix: remove inline handlers from content slots."
                )
            if kl in ("href", "src", "data", "poster", "formaction", "xlink:href"):
                normalized_scheme = re.sub(r"[\s\x00-\x1f]+", "", val).lower()
                if normalized_scheme.startswith("javascript:") or normalized_scheme.startswith("vbscript:"):
                    self.errors.append(
                        f"URL security: forbidden URI scheme '{val}' on <{t} {k}=...>. "
                        "→ AI Fix: use '#id' anchors or safe relative links."
                    )

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "svg" and self.in_svg_stack > 0:
            self.in_svg_stack -= 1


def audit_guide_structure(raw_html: str) -> Tuple[List[str], List[str]]:
    """Verify offline purity, required 4 blocks, DOM safety, dark-mode SVGs, and Block 2 solvability."""
    errors: List[str] = []
    warnings: List[str] = []

    lang_m = re.search(r'<html\b[^>]*\blang=["\']([^"\']*)["\']', raw_html, flags=re.IGNORECASE)
    if not lang_m or not lang_m.group(1).strip() or "{{" in lang_m.group(1):
        errors.append("Structure: missing valid <html lang='...'>. → AI Fix: define 'lang' inside @slot meta.")

    for req_id in ("teoria", "practica", "autoavaluacio", "xuleta"):
        if not re.search(rf'\bid=["\']{req_id}["\']', raw_html):
            errors.append(f"Structure: missing required container #{req_id}.")

    if "@media print" not in raw_html:
        errors.append("Structure: missing @media print rules for the A4 cheat-sheet.")

    non_code_html = re.sub(r"<pre\b[^>]*>.*?</pre>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
    non_code_html = re.sub(r"<code\b[^>]*>.*?</code>", "", non_code_html, flags=re.DOTALL | re.IGNORECASE)
    non_code_html = re.sub(r"<script\b([^>]*)>.*?</script>", r"<script\1></script>", non_code_html, flags=re.DOTALL | re.IGNORECASE)

    ext_attr_refs = re.findall(
        r'<(?:script|img|iframe|link|video|audio|source|object|embed)\b[^>]*\b(?:src|href|data|poster)=["\']\s*((?:https?:)?//[^"\']+)["\']',
        non_code_html,
        flags=re.IGNORECASE,
    )
    for url in ext_attr_refs:
        errors.append(f"Offline: forbidden external asset '{url}'. → AI Fix: keep all CSS, fonts, and SVGs 100% inline.")

    for style_body in re.findall(r"<style\b[^>]*>(.*?)</style>", raw_html, flags=re.DOTALL | re.IGNORECASE):
        css_urls = re.findall(
            r'(?:@import\s+(?:url\()?\s*["\']?((?:https?:)?//[^"\')\s]+)|url\(\s*["\']?((?:https?:)?//[^"\')\s]+))',
            style_body,
            flags=re.IGNORECASE,
        )
        for tup in css_urls:
            url = next((u for u in tup if u), "")
            errors.append(f"Offline CSS: forbidden external asset '{url}'. → AI Fix: remove external URLs from CSS.")

    sec_parser = _StructureSecurityParser()
    sec_parser.feed(non_code_html)
    sec_parser.close()
    errors.extend(sec_parser.errors)

    for sc_m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", raw_html, flags=re.DOTALL | re.IGNORECASE):
        attrs, body = sc_m.group(1), sc_m.group(2)
        if "application/json" in attrs.lower():
            continue
        if re.search(
            r"\.(?:innerHTML|outerHTML)\s*[+]?=|\binsertAdjacentHTML\s*\(|\bdocument\.write\s*\(|\beval\s*\(|\bnew\s+Function\s*\(",
            body,
        ):
            errors.append(
                "DOM security: forbidden innerHTML/outerHTML/insertAdjacentHTML/document.write/eval usage. "
                "→ AI Fix: use createElement and textContent."
            )

    for idx, svg_body in enumerate(re.findall(r"<svg\b.*?</svg>", raw_html, flags=re.DOTALL | re.IGNORECASE), start=1):
        bad_color = re.search(
            r'(?:fill|stroke)\s*[:=]\s*["\']?\s*(#000(?:000)?|#111(?:111)?|#1f2421|black)\b',
            svg_body,
            flags=re.IGNORECASE,
        )
        if bad_color:
            errors.append(
                f"SVG #{idx}: hardcoded dark color '{bad_color.group(1)}' is invisible in dark mode. "
                f"→ AI Fix: use style='fill:var(--ink)' or 'stroke:var(--border-strong)'."
            )

    exercises = _extract_div_blocks_by_class(raw_html, "exercise")
    if not exercises:
        warnings.append("Practice Block: no .exercise blocks found inside #practica.")
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
                errors.append(f"Practice Exercise #{ex_idx}: found <span class='slot'> without data-ans attribute.")
            elif "slot" in cls and ans is not None:
                alts = [_norm(a) for a in ans.split("|") if _norm(a)]
                if not alts or not any(a in chip_vals for a in alts):
                    errors.append(
                        f"Practice Exercise #{ex_idx}: slot data-ans='{ans}' has no matching .chip[data-val] "
                        f"(available: {sorted(chip_vals)}). → AI Fix: add <span class=\"chip\" data-val=\"{ans.split('|')[0]}\">."
                    )

        for inp_tag in re.findall(r"<input\b[^>]*>", ex_html, flags=re.IGNORECASE):
            ans = _attr_val(inp_tag, "data-ans")
            if ans is not None and not _norm(ans):
                errors.append(f"Practice Exercise #{ex_idx}: found <input> with empty data-ans.")

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
                    f"Practice Exercise #{ex_idx}: <select data-ans='{ans}'> has no matching <option> value "
                    f"(options: {sorted(opt_vals)})."
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
                    if "why" in item and item["why"] is not None:
                        entry["why"] = _clean_plain_text(str(item["why"]))
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
        seq_meta.append((num, str(item.get("id", f"Q{num}"))))

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
                    f"{prefix}Letter bias '{letter}': appears {cnt}/{n_valid} times as correct (max allowed: {max_allowed}). "
                    f"→ AI Fix: swap a correct option toward {', '.join(underused)}."
                )
    elif n_valid >= 4:
        max_allowed_small = math.floor(n_valid * 0.50)
        for idx, cnt in sorted(pos_counts.items()):
            letter = chr(65 + idx)
            if cnt > max_allowed_small:
                errors.append(
                    f"{prefix}Letter bias '{letter}': appears {cnt}/{n_valid} times as correct (max allowed: {max_allowed_small}). "
                    f"→ AI Fix: swap a correct option toward {', '.join(underused)}."
                )

    if require_all_slots_ge8 and n_valid >= 8:
        missing = [chr(65 + idx) for idx in range(slot_count) if pos_counts.get(idx, 0) == 0]
        if missing:
            errors.append(
                f"{prefix}Incomplete answer coverage: slots {', '.join(missing)} were never used across {n_valid} questions. "
                f"→ AI Fix: move at least one correct answer into {', '.join(missing)}."
            )

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
                    f"{prefix}Predictable streak: {run_len} consecutive '{letter}' answers "
                    f"(Q{s_num} [{s_id}]..Q{e_num} [{e_id}]). "
                    f"→ AI Fix: rotate the correct position of Q{m_num} ({m_id})."
                )
            run_start = idx

    if longest_eligible >= 4:
        ratio_longest = longest_correct_hits / longest_eligible
        if ratio_longest > max_longest_ratio:
            scope_word = "level" if scope_label else "global"
            errors.append(
                f"{prefix}Length bias ({scope_word}): the correct option is strictly longest in {longest_correct_hits}/{longest_eligible} "
                f"questions ({ratio_longest:.0%} > {max_longest_ratio:.0%} max). "
                f"→ AI Fix: shorten correct options or expand distractors with comparable technical depth."
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
    check_why_quality: bool = False,
) -> Dict[str, Any]:
    """Run global and per-level letter-distribution, length-bias, duplicate, and shortcut checks."""
    errors: List[str] = []
    warnings: List[str] = []
    n = len(questions)

    if n == 0:
        errors.append("No recognizable quiz questions found in the HTML file.")
        return {"ok": False, "count": 0, "errors": errors, "warnings": warnings, "stats": {}}

    if n < min_questions:
        errors.append(f"Only {n} questions found (minimum required: {min_questions}).")
    elif n < 8:
        warnings.append(f"Only {n} questions found; >= 8 is recommended for balanced exams.")

    per_question_issues: List[Dict[str, Any]] = []

    for idx, item in enumerate(questions, start=1):
        num = item.get("num", idx)
        qid = item.get("id", f"Q{num}")
        opts = item["options"]
        corr = item["correct"]

        if "level" in item and isinstance(item["level"], bool):
            errors.append(f"Q{num} ({qid}): 'level' cannot be boolean ({item['level']}). → AI Fix: use 1, 2, or 3.")

        if len(opts) < 2:
            errors.append(f"Q{num} ({qid}): has fewer than 2 options.")
            continue
        if not _is_int(corr):
            errors.append(f"Q{num} ({qid}): 'correct' must be an integer (not boolean/string: {corr!r}).")
            continue
        if corr < 0 or corr >= len(opts):
            errors.append(f"Q{num} ({qid}): correct index {corr} out of range (0..{len(opts) - 1}).")
            continue

        norm_opts = [_norm(o) for o in opts]
        if any(not o for o in norm_opts) or len(set(norm_opts)) != len(norm_opts):
            errors.append(f"Q{num} ({qid}): contains empty or duplicate options. → AI Fix: make all 4 options distinct.")

        if check_why_quality and "why" in item and len(str(item["why"]).strip()) < 35:
            warnings.append(
                f"Q{num} ({qid}): explanation 'why' is brief ({len(str(item['why']).strip())} chars); "
                "explain both why the right answer holds AND why the main distractor fails."
            )

        corr_text = opts[corr]
        if _TRIVIAL_ALL_NONE_RE.match(corr_text):
            errors.append(f"Q{num} ({qid}): giveaway option '{corr_text}' cannot be the correct answer.")

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
                    f"Q{num} ({qid}): correct option too long ({corr_len} chars vs distractors {dist_lens}, "
                    f"ratio_max={ratio_max:.2f}x, ratio_mean={ratio_mean:.2f}x). "
                    f"→ AI Fix: trim correct option to <= {max_safe} chars or expand distractors."
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
                    f"[Level {req_lvl}] Only has {cnt} questions (minimum per level: {min_per_level}). "
                    f"→ AI Fix: add {min_per_level - cnt} questions with \"level\": {req_lvl}."
                )

    per_level_stats: Dict[str, Any] = {}
    if level_buckets:
        for lvl_key, lvl_questions in level_buckets.items():
            lvl_errors, lvl_stats = _audit_distribution(
                lvl_questions,
                scope_label=f"Level {lvl_key}",
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
            "errors": ["Invalid JSON inside <script id='quiz-data'>. → AI Fix: check quiz JSON syntax."],
            "warnings": [],
            "stats": {},
        }
    else:
        report = audit_quiz(
            questions,
            min_questions=min_questions,
            min_per_level=min_per_level,
            check_why_quality=strict_guide,
        )

    if strict_guide:
        struct_errors, struct_warnings = audit_guide_structure(raw)
        report["errors"] = struct_errors + report["errors"]
        report["warnings"] = struct_warnings + report["warnings"]
        report["ok"] = len(report["errors"]) == 0
    report["file"] = str(path)
    report["format"] = fmt
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Anti-bias and structural verifier for HTML study guides")
    parser.add_argument("html_file", type=Path, help="Path to HTML file to audit")
    parser.add_argument("--min-questions", type=int, default=4, help="Minimum global question count (default: 4)")
    parser.add_argument("--min-per-level", type=int, default=0, help="Minimum questions per level 1/2/3 (default: 0)")
    parser.add_argument("--strict-guide", action="store_true", help="Also verify offline purity, DOM security, dark-mode SVGs, and Block 2 solvability")
    parser.add_argument("--json", action="store_true", help="Output JSON report")
    args = parser.parse_args()

    if not args.html_file.exists():
        print(f"Error: file does not exist: {args.html_file}", file=sys.stderr)
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
        print(f"[{status}] {args.html_file.name} (format={report['format']}, questions={report['count']})")
        if stats:
            print(
                f"  Letter distribution: {stats.get('letter_distribution')} | "
                f"Correct longest: {stats.get('longest_correct_hits')}/{stats.get('longest_eligible')} "
                f"({stats.get('longest_ratio', 0):.0%})"
            )
            for lvl_key, lvl_stats in stats.get("per_level", {}).items():
                print(
                    f"  Level {lvl_key} ({lvl_stats.get('questions')}q): "
                    f"letters={lvl_stats.get('letter_distribution')} | "
                    f"longest={lvl_stats.get('longest_correct_hits')}/{lvl_stats.get('longest_eligible')} "
                    f"({lvl_stats.get('longest_ratio', 0):.0%})"
                )
        for w in report["warnings"]:
            print(f"  WARN: {w}")
        for err in report["errors"]:
            print(f"  ERROR: {err}")

    sys.exit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
