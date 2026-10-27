"""Shared loaders, number formats and chart style for the manuscript tables and figures."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
R1, R2, R3 = (RESULTS / f"exp0{i}" for i in (1, 2, 3))
OUT = Path(__file__).resolve().parent / "out"
MODELS = {"qwen3-4b": "Qwen3-4B", "gemma3-4b": "Gemma 3 4B"}
ARMS = {"A": "A, direct in Portuguese", "B": "B, translate first", "C": "C, bilingual index"}
REGISTER = {"technical": "Technical only", "lay": "Lay only", "both": "Both"}

# Chart tokens (dataviz reference palette, light surface; validated: the three categorical
# slots pass all-pairs CVD and normal-vision checks; aqua is below 3:1 contrast, so every
# chart that uses it carries direct labels or a legend plus values in the text).
SURFACE = "#ffffff"
INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # categorical slots 1-3: blue, orange, aqua
BLUE_LIGHT = "#86b6ef"  # blue ramp step 250
NEUTRAL = "#c3c2b7"
BASELINE_INK = "#52514e"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def src(path: Path) -> str:
    return f"`{path.relative_to(ROOT).as_posix()}`"


def dec(x: float | None, d: int = 3) -> str:
    if x is None:
        return "–"
    if abs(x) < 0.5 * 10**-d:
        x = 0.0
    return f"{x:.{d}f}".replace("-", "−")


def sgn(x: float, d: int = 3) -> str:
    return ("+" if x >= 0 else "") + dec(x, d)


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


def pp(x: float, d: int = 1) -> str:
    return ("+" if x >= 0 else "−") + f"{abs(x) * 100:.{d}f} pp"


def num(n: float) -> str:
    return f"{int(round(n)):,}"


def ci(pair, f=dec) -> str:
    return f"{f(pair[0])} to {f(pair[1])}"


def style():
    """Matplotlib with a bundled font (DejaVu Sans) so the PNGs are the same on any machine."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.edgecolor": AXIS,
            "axes.labelcolor": INK_2,
            "axes.titlesize": 9,
            "axes.titlecolor": INK,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK_2,
            "ytick.labelcolor": INK_2,
            "legend.frameon": False,
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
        }
    )
    return plt


def save(fig, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    fig.savefig(path, dpi=300, bbox_inches="tight", metadata={"Software": None})
    return path
