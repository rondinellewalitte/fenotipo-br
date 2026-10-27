"""Exp 03, post-hoc (PREREG, Desvios, 27/out/2026): errors by top-level HPO branch.

For each model x arm and the baseline, per child of HP:0000118: gold terms in the branch,
TP, FN, recall, FP and precision. A term in several branches counts in each. Descriptive
only; read from predictions.jsonl, nothing is run again. Also adds a `branches` column to
errors.csv (no other column or row changes).

    uv run python experiments/exp03_by_branch.py            # full run
    uv run python experiments/exp03_by_branch.py --pilot
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict

import pandas as pd

from hpolab.data import RAW_DIR, ROOT
from hpolab.hpo import PHENOTYPIC_ABNORMALITY, load_ontology


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    base = ROOT / "results" / "exp03" / ("pilot" if args.pilot else "")
    ont = load_ontology(RAW_DIR / "hp.json")
    branches_of = lambda t: sorted(ont.top_branches(t))  # noqa: E731
    with (base / "predictions.jsonl").open(encoding="utf-8") as fh:
        preds = [json.loads(line) for line in fh if line.strip()]

    counts: dict = defaultdict(
        lambda: defaultdict(lambda: {"n_gold": 0, "tp": 0, "fn": 0, "fp": 0})
    )
    for p in preds:
        key = f"{p['model']}/{p['arm']}"
        pred, gold = set(p["pred"]), set(p["gold"])
        for t in gold:
            for b in branches_of(t):
                c = counts[key][b]
                c["n_gold"] += 1
                c["tp" if t in pred else "fn"] += 1
        for t in pred - gold:
            for b in branches_of(t):
                counts[key][b]["fp"] += 1
    out = {
        "note": "post-hoc, descriptive (PREREG, Desvios 27/out/2026); "
        "a term counts in each of its branches",
        "branch_labels": {
            b: ont.terms[b].label for b in sorted(ont.children[PHENOTYPIC_ABNORMALITY])
        },
        "by_arm": {},
    }
    for key in sorted(counts):
        out["by_arm"][key] = {}
        for b, c in sorted(counts[key].items(), key=lambda kv: -kv[1]["n_gold"]):
            out["by_arm"][key][b] = {
                **c,
                "recall": round(c["tp"] / c["n_gold"], 4) if c["n_gold"] else None,
                "precision": round(c["tp"] / (c["tp"] + c["fp"]), 4) if c["tp"] + c["fp"] else None,
            }
    (base / "by_branch.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    errors = pd.read_csv(base / "errors.csv", dtype=str, keep_default_na=False)
    errors["branches"] = errors["hpo_id"].map(lambda t: "|".join(branches_of(t)))
    errors.to_csv(base / "errors.csv", index=False)
    print(f"-> {base / 'by_branch.json'}; branches column added to {base / 'errors.csv'}")


if __name__ == "__main__":
    main()
