"""Exp 03 extraction pieces shared by every arm: JSON schemas for the LLM steps (the same
schemas work as Ollama `format` and as Anthropic `output_config.format`), parsing of model
output, candidate lists for the selection step, and the sentence/clause segmenter of the
no-LLM baseline.
"""

from __future__ import annotations

import json
import re

NONE_ID = "NONE"

EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "present": {"type": "array", "items": {"type": "string"}},
        "absent": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["present", "absent"],
    "additionalProperties": False,
}


def select_schema(candidate_ids: list[str]) -> dict:
    """The answer is constrained to one of the retrieved ids or NONE."""
    return {
        "type": "object",
        "properties": {"hpo_id": {"type": "string", "enum": [*candidate_ids, NONE_ID]}},
        "required": ["hpo_id"],
        "additionalProperties": False,
    }


def parse_json(content: str) -> dict | None:
    try:
        obj = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    return obj if isinstance(obj, dict) else None


def clean_findings(values) -> list[str]:
    """Strings only, whitespace collapsed, empty and duplicate (casefolded) items dropped,
    first occurrence order kept."""
    out, seen = [], set()
    for v in values if isinstance(values, list) else []:
        if not isinstance(v, str):
            continue
        s = re.sub(r"\s+", " ", v).strip()
        key = s.casefold()
        if s and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def parse_extraction(content: str) -> tuple[list[str], list[str], bool]:
    """(present, absent, ok). ok is False when the output is not the expected JSON."""
    obj = parse_json(content)
    if obj is None or "present" not in obj:
        return [], [], False
    return clean_findings(obj.get("present")), clean_findings(obj.get("absent")), True


def parse_selection(content: str, candidate_ids: list[str]) -> str | None:
    """Selected id, or None for NONE / invalid output."""
    obj = parse_json(content)
    chosen = obj.get("hpo_id") if obj else None
    return chosen if chosen in candidate_ids else None


def candidate_lines(candidate_ids: list[str], labels: dict[str, str]) -> str:
    """What the selector sees for each candidate in every arm: id and English label."""
    return "\n".join(f"- {i}: {labels[i]}" for i in candidate_ids)


# Sentence ends, line breaks, semicolons, colons and commas split the text. A comma between
# digits (decimal comma, e.g. "1,5 cm") does not split.
_SPLIT_RE = re.compile(r"[.!?;:\n]+|,(?!\d)|(?<!\d),")


def segments(text: str, min_chars: int = 3) -> list[str]:
    """Baseline units: sentences, then clauses split at commas, semicolons and colons."""
    out = []
    for part in _SPLIT_RE.split(text):
        s = re.sub(r"\s+", " ", part).strip(" -–—()[]\"'")
        if len(s) >= min_chars:
            out.append(s)
    return out
