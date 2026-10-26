"""Set-based metrics for case-level phenotype extraction (Exp 03).

A case's prediction is a set of HPO ids (several findings mapped to one id count once).
Headline metrics use exact id match. Hierarchical near-misses and hand/foot swaps are
counted separately and never added to the headline.

- micro: precision/recall/F1 from TP, FP, FN summed over cases;
- macro: mean over cases of per-case P, R, F1; a case with no prediction has P = 0;
- paired bootstrap: cases resampled with replacement, the same resample for both arms.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import numpy as np

from hpolab.hpo import Ontology

RELATION_ORDER = ("parent_child", "sibling", "ancestor_descendant", "close_relative", "distant")


def counts(pred: set[str], gold: set[str]) -> tuple[int, int, int]:
    return len(pred & gold), len(pred - gold), len(gold - pred)


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)}


def micro_f1(c: np.ndarray) -> float:
    """c: (n_cases, 3) array of TP, FP, FN."""
    tp, fp, fn = c.sum(axis=0)
    return 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 0.0


def summary(c: np.ndarray) -> dict:
    tp, fp, fn = (int(x) for x in c.sum(axis=0))
    per_case = [prf(*row) for row in c.tolist()]
    macro = {
        k: round(float(np.mean([pc[k] for pc in per_case])), 4) if per_case else 0.0
        for k in ("precision", "recall", "f1")
    }
    return {
        "n_cases": len(c),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "micro": prf(tp, fp, fn),
        "macro": macro,
    }


def bootstrap_indices(n_cases: int, n_boot: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, n_cases, size=(n_boot, n_cases))


def boot_micro_f1(c: np.ndarray, idx: np.ndarray) -> np.ndarray:
    s = c[idx].sum(axis=1)  # (n_boot, 3)
    tp, fp, fn = s[:, 0], s[:, 1], s[:, 2]
    denom = 2 * tp + fp + fn
    return np.divide(2 * tp, denom, out=np.zeros(len(s), dtype=float), where=denom > 0)


def paired_diff(c_a: np.ndarray, c_b: np.ndarray, idx: np.ndarray) -> dict:
    """Micro-F1(a) - micro-F1(b) on the same cases, with percentile bootstrap intervals."""
    diff = micro_f1(c_a) - micro_f1(c_b)
    boot = boot_micro_f1(c_a, idx) - boot_micro_f1(c_b, idx)

    def interval(level: float) -> list[float]:
        lo, hi = np.quantile(boot, [(1 - level) / 2, (1 + level) / 2])
        return [round(float(lo), 4), round(float(hi), 4)]

    p_two = 2 * min(float((boot <= 0).mean()), float((boot >= 0).mean()))
    return {
        "diff": round(float(diff), 4),
        "ci95": interval(0.95),
        "ci97_5": interval(0.975),
        "p_boot_two_sided": round(min(1.0, p_two), 4),
        "n_boot": len(idx),
    }


def boot_ratio_ci(num: np.ndarray, den: np.ndarray, idx: np.ndarray) -> list[float]:
    """95% case-bootstrap interval of sum(num)/sum(den), e.g. the negation FP rate."""
    n, d = num[idx].sum(axis=1), den[idx].sum(axis=1)
    r = np.divide(n, d, out=np.zeros(len(n), dtype=float), where=d > 0)
    return [round(float(np.quantile(r, 0.025)), 4), round(float(np.quantile(r, 0.975)), 4)]


def group_recall(hits: np.ndarray, totals: np.ndarray, idx: np.ndarray, groups: list[str]) -> dict:
    """Recall per group of gold items with 95% case-bootstrap intervals.
    hits, totals: (n_cases, n_groups) counts of found / gold items of each group."""
    h, t = hits[idx].sum(axis=1), totals[idx].sum(axis=1)  # (n_boot, n_groups)
    boot = np.divide(h, t, out=np.full(h.shape, np.nan), where=t > 0)
    out = {}
    for j, g in enumerate(groups):
        n = int(totals[:, j].sum())
        out[g] = {
            "n": n,
            "recall": round(float(hits[:, j].sum() / n), 4) if n else None,
            "ci95": [round(float(x), 4) for x in np.nanquantile(boot[:, j], [0.025, 0.975])]
            if n
            else None,
        }
    return out


def recall_diff(
    hits_a: np.ndarray, hits_b: np.ndarray, totals: np.ndarray, idx: np.ndarray, ja: int, jb: int
) -> dict:
    """recall(arm a, group ja) - recall(arm b, group jb), same cases, with a 95% case-bootstrap
    interval. Use a = b to compare two groups within one arm, ja = jb to compare two arms."""

    def rec(h, j, sel):
        num, den = h[sel, j].sum(axis=-1), totals[sel, j].sum(axis=-1)
        return np.divide(num, den, out=np.full(np.shape(num), np.nan, dtype=float), where=den > 0)

    every = np.arange(len(totals))
    diff = float(rec(hits_a, ja, every) - rec(hits_b, jb, every))
    if np.isnan(diff):  # a group without items
        return {"diff": None, "ci95": None}
    boot = rec(hits_a, ja, idx) - rec(hits_b, jb, idx)
    lo, hi = np.nanquantile(boot, [0.025, 0.975])
    return {"diff": round(diff, 4), "ci95": [round(float(lo), 4), round(float(hi), 4)]}


# ---------------------------------------------------------------- error categories


def near_miss_pairs(fp: Iterable[str], fn: Iterable[str], ont: Ontology) -> list[tuple[str, str]]:
    """One-to-one (FP, FN) pairs where the FP is a direct is_a parent or child of the FN.
    Greedy in sorted order, so the count is deterministic."""
    free = sorted(fn)
    pairs = []
    for p in sorted(fp):
        g = next((g for g in free if ont.is_neighbor(p, g)), None)
        if g is not None:
            free.remove(g)
            pairs.append((p, g))
    return pairs


# Hand and foot words mapped to a shared placeholder; two labels that become equal name the
# same lesion on the other extremity (e.g. 'Finger syndactyly' / 'Toe syndactyly').
_LIMB_SUBS = [
    (r"\b(fingers?|toes?)\b", "<digit>"),
    (r"\b(thumbs?|halluces|hallux)\b", "<first-digit>"),
    (r"\b(hands?|feet|foot)\b", "<autopod>"),
    (r"\b(metacarpals?|metatarsals?)\b", "<metapod>"),
    (r"\b(metacarpophalangeal|metatarsophalangeal)\b", "<mp-joint>"),
    (r"\b(carpals?|tarsals?)\b", "<basipod>"),
    (r"\b(wrists?|ankles?)\b", "<basipod-joint>"),
    (r"\b(palms?|palmar|soles?|plantar)\b", "<surface>"),
    (r"\b(upper|lower) (limbs?|extremit(y|ies))\b", "<limb>"),
    (r"\b(arms?|legs?)\b", "<limb>"),
    (r"\b(forearms?)\b", "<zeugopod>"),
    (r"\b(elbows?|knees?)\b", "<zeugopod-joint>"),
]
_HAND_RE = re.compile(
    r"\b(fingers?|thumbs?|hands?|metacarp\w*|carpals?|wrists?|palms?|palmar|upper|arms?|forearms?|elbows?)\b",
    re.I,
)
_FOOT_RE = re.compile(
    r"\b(toes?|hallux|halluces|foot|feet|metatars\w*|tarsals?|ankles?|soles?|plantar|lower|legs?|knees?)\b",
    re.I,
)


def limb_neutral(label: str) -> str:
    s = label.casefold()
    for pat, rep in _LIMB_SUBS:
        s = re.sub(pat, rep, s)
    return re.sub(r"\s+", " ", s).strip()


def is_hand_foot_swap(label_a: str, label_b: str) -> bool:
    """Same lesion, other extremity: one label is hand/upper-limb, the other foot/lower-limb,
    and they become identical once limb words are neutralized."""
    if label_a.casefold() == label_b.casefold():
        return False
    sides = (
        bool(_HAND_RE.search(label_a)) and bool(_FOOT_RE.search(label_b)),
        bool(_FOOT_RE.search(label_a)) and bool(_HAND_RE.search(label_b)),
    )
    return any(sides) and limb_neutral(label_a) == limb_neutral(label_b)


def swap_pairs(fp: Iterable[str], fn: Iterable[str], ont: Ontology) -> list[tuple[str, str]]:
    free = sorted(fn)
    pairs = []
    for p in sorted(fp):
        g = next(
            (g for g in free if is_hand_foot_swap(ont.terms[p].label, ont.terms[g].label)), None
        )
        if g is not None:
            free.remove(g)
            pairs.append((p, g))
    return pairs


def fp_category(
    p: str, gold: set[str], negated: set[str], ont: Ontology, dropped: frozenset[str] = frozenset()
) -> str:
    """Descriptive category of one false positive: 'negated' if the vignette states it as
    absent; 'dropped_from_gold' if it was an item removed from the gold because the generator
    gave no phrase found in the text; else the closest relation to any gold term."""
    if p in negated:
        return "negated"
    if p in dropped:
        return "dropped_from_gold"
    rels = {ont.relation(p, g) for g in gold}
    return next(r for r in RELATION_ORDER if r in rels)
