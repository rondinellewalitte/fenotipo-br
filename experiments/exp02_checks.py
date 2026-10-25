"""Exp 02 post-hoc checks (results/exp02/PREREG.md, Desvios, 25/out/2026).

- out_of_sample.json: gain of translating the top-k missing terms when the list is ranked
  on one half of the genes and measured on the other half (split by gene, never by case),
  plus a list ranked from phenotype.hpoa (independent of the phenopackets).
- generality.json: PT coverage of leaf vs non-leaf terms and by depth under HP:0000118.

    uv run python experiments/exp02_checks.py
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd
from exp02_coverage import GAIN_K, coverage, load_cases, missing_terms

from hpolab.data import RAW_DIR, ROOT, load_hpoa
from hpolab.hpo import PHENOTYPIC_ABNORMALITY, Ontology, load_babelon, load_ontology, pt_labels
from hpolab.provenance import base_config

SEED = 42
SEEDS = range(20)
OUT = ROOT / "results" / "exp02"
KEYS = ("annotation_coverage", "pct_cases_full", "frac_median")
DEPTH_BINS = [(1, 3, "1-3"), (4, 5, "4-5"), (6, 7, "6-7"), (8, 10**6, "8+")]


def pick(cov: dict) -> dict:
    return {k: cov[k] for k in KEYS}


def split_genes(genes: list[str], seed: int) -> tuple[set[str], set[str]]:
    perm = np.random.default_rng(seed).permutation(sorted(genes))
    half = len(perm) // 2
    return set(perm[:half]), set(perm[half:])


def subset(cases: pd.DataFrame, terms: pd.DataFrame, genes: set[str]):
    c = cases[cases["gene"].isin(genes)]
    return c, terms[terms["case_id"].isin(c["case_id"])]


def gain_eval(train, test, translated: set[str], ont: Ontology) -> dict:
    """Rank missing terms on `train`, add the top-k, measure on `test`. The in-sample
    ceiling ranks on `test` itself."""
    (train_c, train_t), (test_c, test_t) = train, test
    ranked_train = missing_terms(train_t, train_c, translated, ont)["hpo_id"].tolist()
    ranked_test = missing_terms(test_t, test_c, translated, ont)["hpo_id"].tolist()
    out: dict = {
        "n_test_cases": len(test_c),
        "baseline": pick(coverage(test_t, test_c, translated)),
    }
    for k in GAIN_K:
        oos = coverage(test_t, test_c, translated | set(ranked_train[:k]))
        ins = coverage(test_t, test_c, translated | set(ranked_test[:k]))
        out[f"top{k}"] = {
            "out_of_sample": pick(oos),
            "in_sample_ceiling": pick(ins),
            "lists_overlap": len(set(ranked_train[:k]) & set(ranked_test[:k])),
        }
    return out


def gene_split(cases: pd.DataFrame, terms: pd.DataFrame, translated, ont) -> dict:
    genes = sorted(cases["gene"].unique())
    a, b = split_genes(genes, SEED)
    A, B = subset(cases, terms, a), subset(cases, terms, b)
    primary = {
        "A_to_B": gain_eval(A, B, translated, ont),
        "B_to_A": gain_eval(B, A, translated, ont),
    }

    rows = []
    for seed in SEEDS:
        a, b = split_genes(genes, seed)
        A, B = subset(cases, terms, a), subset(cases, terms, b)
        for direction, (train, test) in (("A_to_B", (A, B)), ("B_to_A", (B, A))):
            r = gain_eval(train, test, translated, ont)
            base = r["baseline"]["annotation_coverage"]
            for k in GAIN_K:
                rows.append(
                    {
                        "seed": seed,
                        "direction": direction,
                        "k": k,
                        "oos_gain": r[f"top{k}"]["out_of_sample"]["annotation_coverage"] - base,
                        "ceiling_gain": r[f"top{k}"]["in_sample_ceiling"]["annotation_coverage"]
                        - base,
                    }
                )
    df = pd.DataFrame(rows)
    df["ratio"] = df["oos_gain"] / df["ceiling_gain"]
    seeds_summary = {
        f"top{k}": {
            col: {
                "mean": round(float(g[col].mean()), 4),
                "min": round(float(g[col].min()), 4),
                "max": round(float(g[col].max()), 4),
            }
            for col in ("oos_gain", "ceiling_gain", "ratio")
        }
        for k, g in df.groupby("k")
    }
    return {
        "unit": "gene (cohort folder when no gene)",
        "n_genes": len(genes),
        "primary_seed": SEED,
        "primary": primary,
        "seeds": list(SEEDS),
        "seeds_summary_annotation_coverage_gain": seeds_summary,
    }


def hpoa_ranked(cases, terms, translated, ont, ranked_ppkt: list[str]) -> dict:
    df, _ = load_hpoa()
    p = df[(df["aspect"] == "P") & (df["qualifier"] != "NOT")].copy()
    p["primary"] = p["hpo_id"].map(ont.resolve)
    n_dis = p.dropna(subset=["primary"]).groupby("primary")["database_id"].nunique()
    n_dis = n_dis.rename("n").reset_index().sort_values(["n", "primary"], ascending=[False, True])
    ranked = [t for t in n_dis["primary"] if t not in translated]
    out: dict = {"baseline": pick(coverage(terms, cases, translated))}
    for k in GAIN_K:
        out[f"top{k}"] = {
            "hpoa_ranked": pick(coverage(terms, cases, translated | set(ranked[:k]))),
            "phenopacket_ranked_in_sample": pick(
                coverage(terms, cases, translated | set(ranked_ppkt[:k]))
            ),
            "lists_overlap": len(set(ranked[:k]) & set(ranked_ppkt[:k])),
        }
    return out


def depth_bin(d: int | None) -> str:
    if d is None:
        return "outside_HP:0000118"
    return next(label for lo, hi, label in DEPTH_BINS if lo <= d <= hi)


def coverage_by(df: pd.DataFrame, col: str, weight: str | None = None) -> dict:
    out = {}
    for key, g in df.groupby(col, sort=True):
        w = g[weight] if weight else pd.Series(1, index=g.index)
        out[str(key)] = {
            "n": int(w.sum()),
            "share_translated": round(float((w * g["translated"]).sum() / w.sum()), 4),
        }
    return out


def generality(terms: pd.DataFrame, translated: set[str], ont: Ontology) -> dict:
    def describe(ids) -> pd.DataFrame:
        d = pd.DataFrame({"hpo_id": list(ids)})
        d["leaf"] = ~d["hpo_id"].isin(ont.children.keys())
        d["depth_bin"] = [
            depth_bin(ont.up_steps(t).get(PHENOTYPIC_ABNORMALITY)) for t in d["hpo_id"]
        ]
        d["translated"] = d["hpo_id"].isin(translated)
        return d

    in_pa = [t for t in ont.terms if PHENOTYPIC_ABNORMALITY in ont.ancestors(t)]
    onto = describe(in_pa)
    counts = terms["hpo_id"].value_counts().rename("n_cases").reset_index()
    cased = describe(counts["hpo_id"]).merge(counts, on="hpo_id")
    return {
        "depth": "min is_a steps from the term up to HP:0000118",
        "ontology_terms_under_HP:0000118": {
            "by_leaf": coverage_by(onto, "leaf"),
            "by_depth": coverage_by(onto, "depth_bin"),
        },
        "case_terms_distinct": {
            "by_leaf": coverage_by(cased, "leaf"),
            "by_depth": coverage_by(cased, "depth_bin"),
        },
        "case_annotations": {
            "by_leaf": coverage_by(cased, "leaf", weight="n_cases"),
            "by_depth": coverage_by(cased, "depth_bin", weight="n_cases"),
        },
    }


def write_json(name: str, obj: dict) -> None:
    path = OUT / name
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"-> {path}")


def main() -> None:
    cfg = base_config("exp02_checks", SEED)
    if cfg["git"]["dirty"] and "--allow-dirty" not in sys.argv:
        sys.exit("Refusing to run: git tree is dirty. Commit first (or --allow-dirty).")
    ont = load_ontology(RAW_DIR / "hp.json")
    translated = set(pt_labels(load_babelon(RAW_DIR / "hp-pt.babelon.tsv"), ont)["hpo_id"])
    cases, terms, _ = load_cases(ont)
    cases = cases[cases["n_observed"] > 0]
    ranked_ppkt = missing_terms(terms, cases, translated, ont)["hpo_id"].tolist()
    write_json(
        "out_of_sample.json",
        {
            "git": cfg["git"],
            "definitions": "results/exp02/PREREG.md, Desvios, 25/out/2026",
            "gene_split": gene_split(cases, terms, translated, ont),
            "hpoa_ranked_list": hpoa_ranked(cases, terms, translated, ont, ranked_ppkt),
        },
    )
    write_json("generality.json", {"git": cfg["git"], **generality(terms, translated, ont)})


if __name__ == "__main__":
    main()
