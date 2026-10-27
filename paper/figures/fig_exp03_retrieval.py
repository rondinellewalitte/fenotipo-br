"""Figure 2: where gold terms are lost (Exp 03). For each model and arm, the share of gold terms
found (recall), retrieved among the 10 candidates but not chosen (selection loss) and never
retrieved (1 − retrieval ceiling), from results/exp03/metrics.json -> arms. The dotted line is
the phrase oracle (the generator's own phrase, no LLM, top-10), a descriptive reference.

    uv run --group paper python paper/figures/fig_exp03_retrieval.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from figures.common import (  # noqa: E402
    ARMS,
    BLUE_LIGHT,
    INK,
    INK_2,
    MODELS,
    NEUTRAL,
    R3,
    SERIES,
    SURFACE,
    dec,
    load,
    pct,
    save,
    style,
)

NAME = "fig2_exp03_retrieval.png"


def render() -> Path:
    plt = style()
    m = load(R3 / "metrics.json")
    oracle = m["oracle_spans_bge_m3_en_index"]["top10"]
    rows = [(k, a) for k in MODELS for a in ARMS]
    fig, ax = plt.subplots(figsize=(6.7, 3.0))
    for i, (k, a) in enumerate(rows):
        s = m["arms"][f"{k}/{a}"]
        rec, ceil = s["micro"]["recall"], s["retrieval_ceiling_recall"]
        y = len(rows) - 1 - i
        parts = [
            (0, rec, SERIES[0], "Found (recall)"),
            (rec, ceil - rec, BLUE_LIGHT, "Retrieved, not chosen"),
            (ceil, 1 - ceil, NEUTRAL, "Never among the 10 candidates"),
        ]
        for left, width, color, label in parts:
            ax.barh(
                y, width, left=left, height=0.62, color=color, edgecolor=SURFACE,
                linewidth=1.5, label=label if i == 0 else None,
            )  # fmt: skip
        ax.text(rec / 2, y, dec(rec), ha="center", va="center", fontsize=7, color="white")
        ax.text(ceil - 0.01, y, dec(ceil), ha="right", va="center", fontsize=7, color=INK)
    ax.axvline(oracle, color=INK_2, linewidth=1, linestyle=(0, (1, 1.5)), zorder=0.5)
    ax.annotate(
        f"phrase oracle, top-10: {pct(oracle)}", (oracle, len(rows) - 0.45), xytext=(3, 0),
        textcoords="offset points", fontsize=7, color=INK_2, va="bottom",
    )  # fmt: skip
    labels = [f"{MODELS[k]}  {ARMS[a].split(',')[0]}" for k, a in rows]
    ax.set_yticks(range(len(rows)), list(reversed(labels)))
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.6, len(rows) - 0.1)
    ax.set_xlabel("Share of gold terms")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, fontsize=7.5)
    path = save(fig, NAME)
    plt.close(fig)
    return path


if __name__ == "__main__":
    print(f"-> {render()}")
