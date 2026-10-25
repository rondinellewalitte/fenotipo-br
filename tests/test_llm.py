from types import SimpleNamespace

import pytest

from hpolab.llm import Budget, BudgetExceeded, Prompt, usage_cost


def test_usage_cost_opus_prices():
    usage = SimpleNamespace(
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_creation_input_tokens=None,
        cache_read_input_tokens=0,
    )
    assert usage_cost("claude-opus-5-5", usage) == pytest.approx(4.0 + 2.0)


def test_budget_refuses_call_that_could_exceed_limit():
    b = Budget(limit_usd=0.05)
    b.reserve("claude-opus-5-5", input_chars=1000, max_tokens=1000)  # worst ~$0.022
    b.charge(0.04)
    with pytest.raises(BudgetExceeded):
        b.reserve("claude-opus-5-5", input_chars=1000, max_tokens=1000)


def test_prompt_load_and_render(tmp_path):
    (tmp_path / "p.system.md").write_text("System text.\n", encoding="utf-8")
    (tmp_path / "p.user.md").write_text("Term: {hpo_id}\n", encoding="utf-8")
    p = Prompt.load(tmp_path / "p")
    assert p.system == "System text."
    assert p.render(hpo_id="HP:0000001") == "Term: HP:0000001"
    assert len(p.sha256) == 64
