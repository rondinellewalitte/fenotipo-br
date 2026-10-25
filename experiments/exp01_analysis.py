"""Exp 01 follow-up analyses that need no rerun (read results/exp01/ranks.csv.gz).

- surface_sim.json: top-1 per method by surface-similarity bin (pre-registered as
  exploratory in PREREG.md). Bins fixed here before the output was read.
- index_language_check.json: evidence that the English index holds no PT text.
- hierarchy_errors.json: post-hoc secondary metric (PREREG.md, Desvios, 25/out/2026):
  top-1 errors by hierarchical relation of the predicted id to the gold id.

    uv run python experiments/exp01_analysis.py
"""

from __future__ import annotations

import json
import re

import pandas as pd

from hpolab.data import RAW_DIR, ROOT
from hpolab.hpo import Ontology, index_entries, load_babelon, load_ontology, pt_labels
from hpolab.metrics import topk_summary
from hpolab.retrieval import TermIndex, fold

OUT = ROOT / "results" / "exp01"
MAIN_INDEX = "exact"
# surface_sim = rapidfuzz ratio between fold(pt_label) and the closest fold() of the
# gold term's English label / exact synonyms, stored rounded to 1 decimal. The identical
# bin uses the `identical` flag, since a non-identical pair can round up to 100.0.
BINS = [(0, 50, "<50"), (50, 70, "50-70"), (70, 85, "70-85"), (85, 101, "85-100 (not identical)")]
IDENTICAL = "identical"
PT_MARKERS = re.compile(r"[ãõç]|ção|ções|ões", re.IGNORECASE)
RELATIONS = ["parent_child", "sibling", "ancestor_descendant", "close_relative", "distant"]
TIED = "gold_tied_at_top"
UNCLASSIFIED = "unclassified_tie_gt10"
LIMBS = "HP:0040064"
# Post-hoc, exploratory (found while inspecting the sibling metric): same finding on the
# wrong extremity. Matched on English labels of gold and predicted top-1.
HAND = re.compile(r"finger|thumb|hand|metacarp", re.IGNORECASE)
FOOT = re.compile(r"toe|hallux|foot|metatars", re.IGNORECASE)


def surface_bin(sim: float, identical: bool) -> str:
    if identical:
        return IDENTICAL
    return next(label for lo, hi, label in BINS if lo <= sim < hi)


def surface_sim_table(ranks: pd.DataFrame) -> dict:
    main = ranks[(ranks["index"] == MAIN_INDEX) & ranks["in_pa"]].copy()
    main["bin"] = [
        surface_bin(s, i) for s, i in zip(main["surface_sim"], main["identical"], strict=True)
    ]
    order = [b[2] for b in BINS] + [IDENTICAL]
    out: dict = {"bins": order, "by_method": {}}
    for method, grp in main.groupby("method", sort=True):
        out["by_method"][method] = {
            b: {k: v for k, v in topk_summary(grp[grp["bin"] == b]).items()} for b in order
        }
    return out


def index_language_check() -> dict:
    ont = load_ontology(RAW_DIR / "hp.json")
    union = TermIndex.build(index_entries(ont, ("exact", "related", "broad", "narrow")))
    with_markers = [t for t in union.texts if PT_MARKERS.search(t)]
    pt = pt_labels(load_babelon(RAW_DIR / "hp-pt.babelon.tsv"), ont)
    pt_fold = {}
    for hpo_id, label in zip(pt["hpo_id"], pt["pt_label"], strict=True):
        pt_fold.setdefault(fold(label), set()).add(hpo_id)
    cross = []
    for text, ids in zip(union.texts, union.text_ids, strict=True):
        other = pt_fold.get(fold(text), set()) - set(ids)
        if other:
            cross.append({"index_text": text, "index_ids": list(ids), "pt_label_of": sorted(other)})
    return {
        "n_index_texts": len(union.texts),
        "pt_marker_regex": PT_MARKERS.pattern,
        "n_texts_with_pt_markers": len(with_markers),
        "texts_with_pt_markers": with_markers[:50],
        "n_texts_equal_to_pt_label_of_other_term": len(cross),
        "examples_equal_to_pt_label_of_other_term": cross[:50],
    }


def error_category(row, ont: Ontology) -> str:
    """Category of a top-1 error (rank_pess > 1). With ties at the top, the farthest
    relation among the tied ids counts; ties wider than the saved top-k are unclassified."""
    if row.rank_opt == 1:
        return TIED
    top = row.top_ids.split("|")
    if row.n_top > len(top):
        return UNCLASSIFIED
    cats = [ont.relation(t, row.hpo_id) for t in top[: row.n_top]]
    return max(cats, key=RELATIONS.index)


def category_summary(errors: pd.DataFrame, n_queries: int) -> dict:
    counts = errors["category"].value_counts()
    cats = [*RELATIONS, TIED, UNCLASSIFIED]
    n_err = len(errors)
    return {
        "n_queries": n_queries,
        "n_top1_errors": n_err,
        "count": {c: int(counts.get(c, 0)) for c in cats},
        "share_of_errors": {c: round(counts.get(c, 0) / n_err, 4) if n_err else None for c in cats},
        "sibling_miss_rate": round(counts.get("sibling", 0) / n_queries, 4),
    }


def hierarchy_errors(ranks: pd.DataFrame) -> dict:
    ont = load_ontology(RAW_DIR / "hp.json")
    main = ranks[(ranks["index"] == MAIN_INDEX) & ranks["in_pa"]]
    out: dict = {
        "definition": "PREREG.md, Desvios, 25/out/2026 (post-hoc, secondary)",
        "order": RELATIONS,
        "by_method": {},
    }
    for method, grp in main.groupby("method", sort=True):
        errors = grp[grp["rank_pess"] > 1].copy()
        errors["category"] = [error_category(r, ont) for r in errors.itertuples()]
        in_limbs = grp["branches"].str.contains(LIMBS, regex=False)
        err_limbs = errors["branches"].str.contains(LIMBS, regex=False)
        out["by_method"][method] = {
            "main": category_summary(errors, len(grp)),
            "limbs_HP:0040064": category_summary(errors[err_limbs], int(in_limbs.sum())),
            "hand_foot_swaps": hand_foot_swaps(errors, ont),
        }
    return out


def hand_foot_swaps(errors: pd.DataFrame, ont: Ontology) -> dict:
    """Top-1 errors (gold strictly below top) whose gold mentions hand/finger and whose
    top-1 mentions foot/toe, or the reverse."""
    strict = errors[errors["rank_opt"] > 1]
    pred = strict["top_ids"].str.split("|").str[0]
    pred_label = pred.map(lambda i: ont.terms[i].label)
    gold_label = strict["en_label"]
    is_swap = (gold_label.str.contains(HAND) & pred_label.str.contains(FOOT)) | (
        gold_label.str.contains(FOOT) & pred_label.str.contains(HAND)
    )
    swaps = strict[is_swap]
    return {
        "regex_hand": HAND.pattern,
        "regex_foot": FOOT.pattern,
        "n_strict_top1_errors": len(strict),
        "n_swaps": len(swaps),
        "share_of_errors": round(len(swaps) / len(strict), 4) if len(strict) else None,
        "category_count": swaps["category"].value_counts().to_dict(),
        "examples": [
            {"gold": g, "pt": p, "pred": pred_label[i]}
            for i, g, p in zip(swaps.index[:10], swaps["en_label"], swaps["pt_label"], strict=False)
        ],
    }


def write_json(name: str, obj: dict) -> None:
    path = OUT / name
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"-> {path}")


def main() -> None:
    ranks = pd.read_csv(OUT / "ranks.csv.gz")
    write_json("surface_sim.json", surface_sim_table(ranks))
    write_json("index_language_check.json", index_language_check())
    write_json("hierarchy_errors.json", hierarchy_errors(ranks))


if __name__ == "__main__":
    main()
