"""Exp 01 top-k weighted by clinical frequency (results/exp01/PREREG.md, Desvios,
25/out/2026). Weight of a PT query = number of Phenopacket Store cases in which its term
is observed (Exp 02 definition); variant weight = number of diseases in phenotype.hpoa.

    uv run python experiments/exp01_weighted.py
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
from exp02_coverage import load_cases

from hpolab.data import RAW_DIR, ROOT, load_hpoa
from hpolab.hpo import load_ontology
from hpolab.provenance import base_config

SEED = 42
N_BOOT = 1000
KS = (1, 5, 10)
MAIN_INDEX = "exact"
OUT = ROOT / "results" / "exp01"


def weighted_summary(df: pd.DataFrame, w: pd.Series, rng: np.random.Generator) -> dict:
    pos = w > 0
    d, wp = df[pos], w[pos].to_numpy(dtype=float)
    out: dict = {"n_queries_with_weight": int(pos.sum()), "total_weight": float(wp.sum())}
    for k in KS:
        hit = (d["rank_pess"] <= k).to_numpy(dtype=float)
        out[f"top{k}_weighted"] = round(float((wp * hit).sum() / wp.sum()), 4)
    hit1 = (d["rank_pess"] == 1).to_numpy(dtype=float)
    idx = rng.integers(0, len(wp), size=(N_BOOT, len(wp)))
    boot = (wp[idx] * hit1[idx]).sum(axis=1) / wp[idx].sum(axis=1)
    out["top1_weighted_ci95_bootstrap"] = [
        round(float(np.quantile(boot, 0.025)), 4),
        round(float(np.quantile(boot, 0.975)), 4),
    ]
    out["top1_unweighted_same_subset"] = round(float(hit1.mean()), 4)
    return out


def main() -> None:
    cfg = base_config("exp01_weighted", SEED)
    if cfg["git"]["dirty"] and "--allow-dirty" not in sys.argv:
        sys.exit("Refusing to run: git tree is dirty. Commit first (or --allow-dirty).")
    ont = load_ontology(RAW_DIR / "hp.json")
    _, terms, _ = load_cases(ont)
    w_cases = terms["hpo_id"].value_counts()

    hpoa, _ = load_hpoa()
    p = hpoa[(hpoa["aspect"] == "P") & (hpoa["qualifier"] != "NOT")].copy()
    p["primary"] = p["hpo_id"].map(ont.resolve)
    w_dis = p.dropna(subset=["primary"]).groupby("primary")["database_id"].nunique()

    ranks = pd.read_csv(OUT / "ranks.csv.gz")
    main_scope = ranks[(ranks["index"] == MAIN_INDEX) & ranks["in_pa"]]
    out: dict = {
        "git": cfg["git"],
        "definitions": "results/exp01/PREREG.md, Desvios, 25/out/2026",
        "n_case_term_pairs_total": len(terms),
        "by_method": {},
    }
    for method, df in main_scope.groupby("method", sort=True):
        df = df.reset_index(drop=True)
        wc = df["hpo_id"].map(w_cases).fillna(0)
        wd = df["hpo_id"].map(w_dis).fillna(0)
        out["by_method"][method] = {
            "weight_phenopacket_cases": weighted_summary(df, wc, np.random.default_rng(SEED)),
            "weight_hpoa_diseases": weighted_summary(df, wd, np.random.default_rng(SEED)),
        }
    path = OUT / "weighted.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"-> {path}")


if __name__ == "__main__":
    main()
