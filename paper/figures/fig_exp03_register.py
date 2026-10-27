"""Figure 3: recall by clinical register of the gold term (D2: technical only, lay only, both),
per arm, with 95% bootstrap CIs, from results/exp03/metrics.json -> register.d2.

    uv run --group paper python paper/figures/fig_exp03_register.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from figures.common import (  # noqa: E402
    BASELINE_INK,
    MODELS,
    R3,
    REGISTER,
    SERIES,
    load,
    save,
    style,
)

NAME = "fig3_exp03_register.png"
SERIES_ARMS = [("A", "A, direct in PT"), ("B", "B, translate first"), ("C", "C, bilingual index")]


def render() -> Path:
    plt = style()
    d2 = load(R3 / "metrics.json")["register"]["d2"]
    fig, axes = plt.subplots(1, 2, figsize=(6.7, 2.8), sharey=True)
    groups = list(REGISTER)
    series = [(f"{a}", label, color) for (a, label), color in zip(SERIES_ARMS, SERIES, strict=True)]
    series.append(("baseline", "No-LLM baseline", BASELINE_INK))
    offsets = [0.27, 0.09, -0.09, -0.27]
    for ax, (k, name) in zip(axes, MODELS.items(), strict=True):
        for (arm, label, color), off in zip(series, offsets, strict=True):
            key = "none/baseline" if arm == "baseline" else f"{k}/{arm}"
            for j, g in enumerate(groups):
                r = d2[key]["recall"][g]
                y = len(groups) - 1 - j + off
                ax.plot(r["ci95"], [y, y], color=color, linewidth=2, solid_capstyle="round")
                ax.plot(
                    r["recall"], y, "o", markersize=5.5, color=color, markeredgecolor="white",
                    markeredgewidth=1, label=label if j == 0 else None,
                )  # fmt: skip
        ax.set_title(name, loc="left")
        ax.set_xlim(0, 0.8)
        ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8])
        ax.grid(axis="y", visible=False)
        ax.tick_params(axis="y", length=0)
        ax.set_xlabel("Recall (95% CI)")
    n = {g: d2["qwen3-4b/A"]["recall"][g]["n"] for g in groups}
    axes[0].set_yticks(
        range(len(groups)), [f"{REGISTER[g]}\n(n = {n[g]:,})" for g in reversed(groups)]
    )
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles, labels, loc="lower center", ncol=4, fontsize=7.5, bbox_to_anchor=(0.5, -0.06)
    )
    fig.subplots_adjust(bottom=0.27, wspace=0.18)
    path = save(fig, NAME)
    plt.close(fig)
    return path


if __name__ == "__main__":
    print(f"-> {render()}")
