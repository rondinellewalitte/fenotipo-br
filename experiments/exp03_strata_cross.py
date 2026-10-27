"""Exp 03, post-hoc (PREREG, Desvios, 27/out/2026): surface similarity crossed with register.

The back-translation defence reads arm B's advantage by `sim_bin`, and the register analysis
reads it by `register_d2`. The two strata are not independent: a finding written in lay words
is far from the English label by construction. This script measures the overlap and separates
the two readings, by asking whether B keeps its advantage across similarity bands *within* one
register. Descriptive only, no hypothesis; read from predictions.jsonl, nothing is run again.

    uv run python experiments/exp03_strata_cross.py            # full run
    uv run python experiments/exp03_strata_cross.py --pilot
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from exp03_extraction import (  # noqa: E402
    MODELS,
    N_BOOT,
    REGISTERS,
    SEED,
    build_indexes,
    gold_covariates,
    load_cases,
    load_jsonl,
    load_register_labels,
    write_json,
)

from hpolab import casemetrics as cm  # noqa: E402
from hpolab.data import RAW_DIR, ROOT  # noqa: E402
from hpolab.hpo import load_ontology  # noqa: E402

SIM_BINS = ("<50", "50-80", ">=80")


def cell_counts(cov: pd.DataFrame, cases, groups: dict, keys: list[str], col: str):
    """(totals, hits_by_arm) as (n_cases, n_keys) integer matrices over the cells of `col`."""
    case_ids = sorted(cases["case_id"])
    cell_of = {(r.case_id, r.hpo_id): getattr(r, col) for r in cov.itertuples()}
    gold_of = dict(zip(cases["case_id"], cases["gold"], strict=True))
    totals = np.array(
        [[sum(cell_of[(cid, g)] == k for g in gold_of[cid]) for k in keys] for cid in case_ids]
    )
    hits = {}
    for key, recs in groups.items():
        found = {r["case_id"]: set(r["pred"]) & set(r["gold"]) for r in recs}
        hits[key] = np.array(
            [[sum(cell_of[(cid, g)] == k for g in found[cid]) for k in keys] for cid in case_ids]
        )
    return totals, hits


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true")
    args = parser.parse_args()
    set_name = "pilot" if args.pilot else "full"
    out_dir = ROOT / "results" / "exp03" / ("pilot" if args.pilot else "")

    ont = load_ontology(RAW_DIR / "hp.json")
    cases, _ = load_cases(set_name)
    _, pt_map = build_indexes(ont)
    d2, _ = load_register_labels(set_name, cases)
    cov = gold_covariates(cases, ont, pt_map, d2)
    records = load_jsonl(out_dir / "predictions.jsonl")

    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(f"{r['model']}/{r['arm']}", []).append(r)
    idx = cm.bootstrap_indices(len(cases), N_BOOT, SEED)

    # --- how much do the two strata overlap? -------------------------------------------
    table = cov.groupby(["sim_bin", "register_d2"]).size().unstack(fill_value=0).reindex(SIM_BINS)
    contingency = {
        sim: {reg: int(table.loc[sim, reg]) for reg in REGISTERS if reg in table.columns}
        for sim in SIM_BINS
        if sim in table.index
    }
    # Cramer's V on the 3x3 table: 0 = the strata carry independent information.
    obs = table.reindex(columns=list(REGISTERS), fill_value=0).to_numpy(dtype=float)
    exp = obs.sum(axis=1, keepdims=True) * obs.sum(axis=0, keepdims=True) / obs.sum()
    chi2 = float(((obs - exp) ** 2 / np.where(exp > 0, exp, np.nan)).sum())
    cramers_v = float(np.sqrt(chi2 / (obs.sum() * (min(obs.shape) - 1))))

    # --- recall per cell of sim_bin x register_d2 ---------------------------------------
    cov = cov.assign(cell=cov["sim_bin"] + "|" + cov["register_d2"])
    cells = [f"{s}|{r}" for s in SIM_BINS for r in REGISTERS]
    totals, hits = cell_counts(cov, cases, groups, cells, "cell")
    by_cell = {
        key: {
            "recall": cm.group_recall(hits[key], totals, idx, cells),
        }
        for key in sorted(groups)
    }
    for m in MODELS:
        if f"{m}/A" not in groups:
            continue
        ha, hb = hits[f"{m}/A"], hits[f"{m}/B"]
        by_cell[f"{m}/A-B"] = {
            "diff": {c: cm.recall_diff(ha, hb, totals, idx, j, j) for j, c in enumerate(cells)}
        }

    # --- A - B by similarity band, within one register ----------------------------------
    within = {}
    for reg in REGISTERS:
        sub = cov[cov["register_d2"] == reg]
        if sub.empty:
            continue
        keys = list(SIM_BINS)
        tot_r, hits_r = cell_counts(
            cov.assign(band=np.where(cov["register_d2"] == reg, cov["sim_bin"], "")),
            cases,
            groups,
            keys,
            "band",
        )
        entry = {"n_items": {k: int(tot_r[:, j].sum()) for j, k in enumerate(keys)}}
        for m in MODELS:
            if f"{m}/A" not in groups:
                continue
            entry[m] = {
                "recall_A": cm.group_recall(hits_r[f"{m}/A"], tot_r, idx, keys),
                "recall_B": cm.group_recall(hits_r[f"{m}/B"], tot_r, idx, keys),
                "A-B": {
                    k: cm.recall_diff(hits_r[f"{m}/A"], hits_r[f"{m}/B"], tot_r, idx, j, j)
                    for j, k in enumerate(keys)
                },
            }
        within[reg] = entry

    out = {
        "note": "post-hoc, descriptive (PREREG, Desvios 27/out/2026); no hypothesis, no decision "
        "criterion. Separates the back-translation reading (sim_bin) from the register "
        "reading (register_d2), which are correlated by construction.",
        "bootstrap": {
            "unit": "case",
            "n_boot": N_BOOT,
            "seed": SEED,
            "intervals": "percentile",
            "note": "cells with few gold terms carry a granular interval; see the `granular` flag",
        },
        "n_gold_terms": int(len(cov)),
        "arms": sorted(groups),
        "overlap": {
            "contingency_sim_bin_x_register_d2": contingency,
            "chi2": round(chi2, 2),
            "cramers_v": round(cramers_v, 4),
            "reading": "Cramer's V is 0 when the two strata are independent and 1 when one "
            "determines the other.",
        },
        "by_cell": by_cell,
        "a_minus_b_by_sim_within_register": within,
    }
    write_json(out_dir / "strata_cross.json", out)
    print(f"-> {out_dir / 'strata_cross.json'}  (Cramer's V = {cramers_v:.3f})")


if __name__ == "__main__":
    main()
