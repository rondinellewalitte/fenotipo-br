"""Figure 1: paired differences in micro-F1 between arms (Exp 03), from results/exp03/metrics.json
-> comparisons. A − B uses the pre-specified 97.5% CI and shows the non-inferiority margin;
the other comparisons use 95% CIs.

    uv run --group paper python paper/figures/fig_exp03_differences.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from figures.common import AXIS, INK_2, MODELS, R3, SERIES, load, save, sgn, style  # noqa: E402

NAME = "fig1_exp03_differences.png"
ROWS = [  # (comparison key, label, CI key)
    ("A-B", "A − B (primary)\n97.5% CI", "ci97_5"),
    ("C-A", "C − A\n95% CI", "ci95"),
    ("A-baseline", "A − baseline\n95% CI", "ci95"),
]
MARGIN = -0.03  # H1 non-inferiority margin, results/exp03/PREREG.md


def render() -> Path:
    plt = style()
    comp = load(R3 / "metrics.json")["comparisons"]
    fig, ax = plt.subplots(figsize=(6.7, 2.9))
    offsets = {k: o for k, o in zip(MODELS, (0.14, -0.14), strict=True)}
    for i, (key, _, ci_key) in enumerate(ROWS):
        y0 = len(ROWS) - 1 - i
        for (k, name), color in zip(MODELS.items(), SERIES, strict=False):
            d = comp[k][key]
            lo, hi = d[ci_key]
            y = y0 + offsets[k]
            ax.plot([lo, hi], [y, y], color=color, linewidth=2, solid_capstyle="round", zorder=2)
            ax.plot(
                d["diff"], y, "o", markersize=6, color=color, markeredgecolor="white",
                markeredgewidth=1.2, zorder=3, label=name if i == 0 else None,
            )  # fmt: skip
            ax.annotate(
                sgn(d["diff"]), (lo, y), xytext=(-5, 0), textcoords="offset points", ha="right",
                va="center", fontsize=7.5, color=INK_2,
            )  # fmt: skip
    top = len(ROWS) - 1
    ax.plot(
        [MARGIN, MARGIN], [top - 0.42, top + 0.42], color=INK_2, linewidth=1, linestyle=(0, (3, 2))
    )
    ax.annotate(
        "non-inferiority margin −0.03", (MARGIN, top + 0.42), xytext=(0, 2),
        textcoords="offset points", ha="center", va="bottom", fontsize=7, color=INK_2,
    )  # fmt: skip
    ax.axvline(0, color=AXIS, linewidth=1, zorder=1)
    ax.set_yticks(range(len(ROWS)), [r[1] for r in reversed(ROWS)])
    ax.set_ylim(-0.6, len(ROWS) - 0.25)
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("Difference in micro-F1, paired by case (bootstrap CI)")
    ax.legend(loc="lower right", fontsize=7.5, handletextpad=0.3)
    xs = [v for k in MODELS for key, _, c in ROWS for v in comp[k][key][c]]
    ax.set_xlim(min(xs + [MARGIN]) - 0.05, max(xs) + 0.02)
    path = save(fig, NAME)
    plt.close(fig)
    return path


if __name__ == "__main__":
    print(f"-> {render()}")
