"""Exp 01 follow-up analyses that need no rerun (read results/exp01/ranks.csv.gz).

- surface_sim.json: top-1 per method by surface-similarity bin (pre-registered as
  exploratory in PREREG.md). Bins fixed here before the output was read.
- index_language_check.json: evidence that the English index holds no PT text.

    uv run python experiments/exp01_analysis.py
"""

from __future__ import annotations

import json
import re

import pandas as pd

from hpolab.data import RAW_DIR, ROOT
from hpolab.hpo import index_entries, load_babelon, load_ontology, pt_labels
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


def write_json(name: str, obj: dict) -> None:
    path = OUT / name
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"-> {path}")


def main() -> None:
    ranks = pd.read_csv(OUT / "ranks.csv.gz")
    write_json("surface_sim.json", surface_sim_table(ranks))
    write_json("index_language_check.json", index_language_check())


if __name__ == "__main__":
    main()
