"""Small, logged, budget-capped Anthropic API jobs.

CLAUDE.md: the LLM is optional and only used when ANTHROPIC_API_KEY is set; other credential
sources are deliberately ignored so nothing is billed by accident. The API rejects sampling
parameters (temperature/top_p/top_k) since 2026-10-21, so runs are made reproducible by
pinning model and prompt, and by caching every output on disk.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MODEL = "claude-opus-5-5"
# USD per million tokens. Source: Anthropic model table as of 2026-10-06; recheck
# https://platform.claude.com/docs/en/about-claude/pricing before relying on it.
PRICES = {
    "claude-opus-5-5": {"input": 4.00, "output": 20.00, "cache_write": 5.00, "cache_read": 0.20},
}
CHARS_PER_TOKEN_LOWER_BOUND = 2  # conservative input estimate for the pre-call budget check


class BudgetExceeded(RuntimeError):
    pass


def has_api_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


@dataclass(frozen=True)
class Prompt:
    """A versioned prompt: <stem>.system.md + <stem>.user.md (str.format template)."""

    stem: Path
    system: str
    user_template: str
    sha256: str

    @classmethod
    def load(cls, stem: Path) -> Prompt:
        system = stem.with_name(stem.name + ".system.md").read_text(encoding="utf-8").strip()
        user = stem.with_name(stem.name + ".user.md").read_text(encoding="utf-8").strip()
        sha = hashlib.sha256(f"{system}\n\x00\n{user}".encode()).hexdigest()
        return cls(stem, system, user, sha)

    def render(self, **fields: str) -> str:
        return self.user_template.format(**fields)


def usage_cost(model: str, usage) -> float:
    p = PRICES[model]
    tokens = {
        "input": getattr(usage, "input_tokens", 0) or 0,
        "output": getattr(usage, "output_tokens", 0) or 0,
        "cache_write": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read": getattr(usage, "cache_read_input_tokens", 0) or 0,
    }
    return sum(tokens[k] * p[k] for k in tokens) / 1e6


@dataclass
class Budget:
    limit_usd: float
    spent_usd: float = 0.0

    def worst_case(self, model: str, input_chars: int, max_tokens: int) -> float:
        p = PRICES[model]
        est_input = input_chars / CHARS_PER_TOKEN_LOWER_BOUND
        return (est_input * p["input"] + max_tokens * p["output"]) / 1e6

    def reserve(self, model: str, input_chars: int, max_tokens: int) -> None:
        """Refuse a call whose worst-case cost could push spending past the limit."""
        worst = self.worst_case(model, input_chars, max_tokens)
        if self.spent_usd + worst > self.limit_usd:
            raise BudgetExceeded(
                f"spent ${self.spent_usd:.4f} + worst case ${worst:.4f} "
                f"> limit ${self.limit_usd:.2f}"
            )

    def charge(self, cost: float) -> None:
        self.spent_usd += cost


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def json_call(
    client,
    *,
    model: str,
    prompt: Prompt,
    user: str,
    schema: dict,
    max_tokens: int,
    effort: str,
    budget: Budget,
    log_path: Path,
    meta: dict,
) -> dict | None:
    """One structured-output call. Logs usage and cost; returns the parsed JSON, or None
    when the model did not finish normally (refusal, max_tokens)."""
    budget.reserve(model, len(prompt.system) + len(user), max_tokens)
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=prompt.system,
        messages=[{"role": "user", "content": user}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    cost = usage_cost(model, response.usage)
    budget.charge(cost)
    u = response.usage
    append_jsonl(
        log_path,
        {
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            "model": response.model,
            "request_id": getattr(response, "_request_id", None),
            "prompt_sha256": prompt.sha256,
            "effort": effort,
            "max_tokens": max_tokens,
            "stop_reason": response.stop_reason,
            "input_tokens": u.input_tokens,
            "output_tokens": u.output_tokens,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", None),
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", None),
            "cost_usd": round(cost, 6),
            "spent_usd_cumulative": round(budget.spent_usd, 6),
            **meta,
        },
    )
    if response.stop_reason != "end_turn":
        return None
    text = next((b.text for b in response.content if b.type == "text"), None)
    return json.loads(text) if text else None
