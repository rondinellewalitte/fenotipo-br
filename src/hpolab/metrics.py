"""Top-k summaries over per-query rank tables.

Headline top-k uses the pessimistic rank (ties count against the hit). The optimistic
value, the share of queries whose gold is tied at the top, and the hierarchical
near-miss rate are reported as separate fields, never added to top-k.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import binomtest

KS = (1, 5, 10)


def wilson_ci(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = hits / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(center - half, 4), round(center + half, 4))


def topk_summary(df: pd.DataFrame) -> dict:
    """Expects columns rank_pess, rank_opt, near_miss."""
    n = len(df)
    out: dict = {"n": n}
    if n == 0:
        return out
    for k in KS:
        hits = int((df["rank_pess"] <= k).sum())
        out[f"top{k}"] = round(hits / n, 4)
        out[f"top{k}_ci95"] = wilson_ci(hits, n)
    for k in KS:
        out[f"top{k}_optimistic"] = round(float((df["rank_opt"] <= k).mean()), 4)
    out["top1_tied"] = round(float(((df["rank_opt"] == 1) & (df["rank_pess"] > 1)).mean()), 4)
    out["near_miss"] = round(float(df["near_miss"].mean()), 4)
    return out


def subset_summaries(df: pd.DataFrame) -> dict:
    """Subsets of one (method, index) rank table. `main` = gold under HP:0000118."""
    main = df[df["in_pa"]]
    return {
        "main": topk_summary(main),
        "main_identical": topk_summary(main[main["identical"]]),
        "main_nonidentical": topk_summary(main[~main["identical"]]),
        "main_stale": topk_summary(main[main["stale"]]),
        "main_current": topk_summary(main[~main["stale"]]),
        "outside_HP:0000118": topk_summary(df[~df["in_pa"]]),
        "all": topk_summary(df),
    }


def mcnemar(hits_a: np.ndarray, hits_b: np.ndarray) -> dict:
    """Exact McNemar test on paired binary outcomes (same queries, two methods)."""
    a, b = np.asarray(hits_a, dtype=bool), np.asarray(hits_b, dtype=bool)
    a_only, b_only = int((a & ~b).sum()), int((~a & b).sum())
    n_disc = a_only + b_only
    p = binomtest(a_only, n_disc, 0.5).pvalue if n_disc else 1.0
    return {
        "n": len(a),
        "a_only": a_only,
        "b_only": b_only,
        "diff_a_minus_b": round((a_only - b_only) / len(a), 4),
        "p_value": float(p),
    }


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni adjusted p-values."""
    order = sorted(pvalues, key=pvalues.get)
    m, running, out = len(order), 0.0, {}
    for i, key in enumerate(order):
        running = max(running, min(1.0, (m - i) * pvalues[key]))
        out[key] = running
    return out


def branch_summaries(df: pd.DataFrame, branch_labels: dict[str, str]) -> dict:
    """Per top-level branch of HP:0000118 (main scope). A term in several branches
    (polyhierarchy) counts once in each."""
    main = df[df["in_pa"]].assign(branch=lambda d: d["branches"].str.split("|")).explode("branch")
    out = {}
    for branch, grp in main.groupby("branch", sort=True):
        out[branch] = {"label": branch_labels.get(branch, ""), **topk_summary(grp)}
    return out
