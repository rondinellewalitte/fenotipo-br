"""Exp 02: how much of real rare-disease case descriptions already has an official PT label.

Cases: Phenopacket Store (all_phenopackets.zip), observed (non-excluded) features, ids
resolved to current primary HPO ids. Translated = active term with an official PT label
(hpo.pt_labels). Definitions and expectations: results/exp02/PREREG.md.

    uv run python experiments/exp02_coverage.py
"""

from __future__ import annotations

import argparse
import json
import math
import sys

import numpy as np
import pandas as pd

from hpolab.data import RAW_DIR, ROOT, iter_phenopackets, load_hpoa, phenopacket_case
from hpolab.hpo import (
    PHENOTYPIC_ABNORMALITY,
    Ontology,
    load_babelon,
    load_ontology,
    pt_labels,
)
from hpolab.provenance import base_config

SEED = 42  # nothing is sampled; recorded for the config convention
TOP_MISSING = 300
GAIN_K = (50, 100, 300)
HPOA_TOP = 500
OUT = ROOT / "results" / "exp02"
HIST_EDGES = [round(x, 1) for x in np.arange(0, 1.01, 0.1)]


def load_cases(ont: Ontology) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """(cases, case_terms, counts). case_terms has one row per (case, primary id)."""
    cases, pairs = [], []
    counts = {"n_observed_annotations": 0, "n_alt_or_obsolete_resolved": 0, "unresolvable": {}}
    for member, pp in iter_phenopackets():
        case = phenopacket_case(member, pp)
        ids = set()
        for raw in case.pop("observed"):
            counts["n_observed_annotations"] += 1
            primary = ont.resolve(raw)
            if primary is None:
                counts["unresolvable"][raw] = counts["unresolvable"].get(raw, 0) + 1
                continue
            if primary != raw:
                counts["n_alt_or_obsolete_resolved"] += 1
            ids.add(primary)
        case["n_observed"] = len(ids)
        cases.append(case)
        pairs.extend((case["case_id"], i) for i in sorted(ids))
    cases_df = pd.DataFrame(cases)
    terms_df = pd.DataFrame(pairs, columns=["case_id", "hpo_id"])
    counts["n_cases"] = len(cases_df)
    counts["n_cases_without_observed_terms"] = int((cases_df["n_observed"] == 0).sum())
    counts["n_cases_gene_from_cohort_folder"] = int(
        (cases_df["gene_source"] == "cohort_folder").sum()
    )
    counts["n_case_term_pairs"] = len(terms_df)
    counts["n_distinct_terms"] = int(terms_df["hpo_id"].nunique())
    counts["n_distinct_terms_outside_HP:0000118"] = int(
        sum(
            1 for t in terms_df["hpo_id"].unique() if PHENOTYPIC_ABNORMALITY not in ont.ancestors(t)
        )
    )
    return cases_df, terms_df, counts


def hist_label(frac: float) -> str:
    """Bins [0.0, 0.1), ..., [0.9, 1.0) and exactly 1.0; tolerance keeps k/n on a bin edge
    (e.g. 3/10) out of the bin below."""
    if frac >= 1:
        return "1.0"
    lo = math.floor(frac * 10 + 1e-9) / 10
    return f"{lo:.1f}-{lo + 0.1:.1f}"


def coverage(terms: pd.DataFrame, cases: pd.DataFrame, translated: set[str]) -> dict:
    tr = terms["hpo_id"].isin(translated)
    per_case = tr.groupby(terms["case_id"]).mean()
    n = len(per_case)
    distinct = terms["hpo_id"].drop_duplicates()
    gene_of = cases.set_index("case_id")["gene"]
    per_gene = per_case.groupby(gene_of.reindex(per_case.index)).mean()
    labels = [hist_label(x) for x in HIST_EDGES[:-1]] + ["1.0"]
    hist = per_case.map(hist_label).value_counts()
    return {
        "n_cases": n,
        "pct_cases_full": round(float((per_case == 1).mean()), 4),
        "pct_cases_zero": round(float((per_case == 0).mean()), 4),
        "frac_mean": round(float(per_case.mean()), 4),
        "frac_median": round(float(per_case.median()), 4),
        "frac_q1": round(float(per_case.quantile(0.25)), 4),
        "frac_q3": round(float(per_case.quantile(0.75)), 4),
        "hist_cases": {b: int(hist.get(b, 0)) for b in labels},
        "annotation_coverage": round(float(tr.mean()), 4),
        "n_annotations": len(terms),
        "distinct_term_coverage": round(float(distinct.isin(translated).mean()), 4),
        "n_distinct_terms": len(distinct),
        "n_genes": len(per_gene),
        "gene_weighted_frac_mean": round(float(per_gene.mean()), 4),
    }


def per_case_table(cases: pd.DataFrame, terms: pd.DataFrame, translated: set[str]) -> pd.DataFrame:
    tr = terms.assign(tr=terms["hpo_id"].isin(translated)).groupby("case_id")["tr"]
    out = cases.set_index("case_id").join(tr.sum().rename("n_translated"))
    out["n_translated"] = out["n_translated"].fillna(0).astype(int)
    out["frac_translated"] = (out["n_translated"] / out["n_observed"]).round(4)
    return out.reset_index()


def by_group(
    per_case: pd.DataFrame, terms: pd.DataFrame, key: list[str], translated
) -> pd.DataFrame:
    pc = per_case[per_case["n_observed"] > 0]
    grp = pc.groupby(key, sort=False)
    out = pd.DataFrame(
        {
            "n_cases": grp.size(),
            "frac_mean": grp["frac_translated"].mean().round(4),
            "pct_cases_full": grp["frac_translated"].apply(lambda s: (s == 1).mean()).round(4),
            "pct_cases_zero": grp["frac_translated"].apply(lambda s: (s == 0).mean()).round(4),
        }
    )
    t = terms.merge(pc[["case_id", *key]], on="case_id")
    distinct = t.drop_duplicates([*key, "hpo_id"])
    out["n_distinct_terms"] = distinct.groupby(key).size()
    untr = distinct[~distinct["hpo_id"].isin(translated)]
    out["n_distinct_untranslated"] = untr.groupby(key).size().reindex(out.index).fillna(0)
    out["n_distinct_untranslated"] = out["n_distinct_untranslated"].astype(int)
    return out.reset_index().sort_values(["n_cases", *key], ascending=[False] + [True] * len(key))


def missing_terms(terms: pd.DataFrame, cases: pd.DataFrame, translated, ont) -> pd.DataFrame:
    n_cases = int((cases["n_observed"] > 0).sum())
    t = terms[~terms["hpo_id"].isin(translated)].merge(
        cases[["case_id", "gene", "disease_id"]], on="case_id"
    )
    g = t.groupby("hpo_id")
    out = pd.DataFrame(
        {
            "n_cases": g.size(),
            "n_genes": g["gene"].nunique(),
            "n_diseases": g["disease_id"].nunique(),
        }
    ).reset_index()
    out["pct_cases"] = (out["n_cases"] / n_cases).round(4)
    out["en_label"] = out["hpo_id"].map(lambda i: ont.terms[i].label)
    out["branches"] = out["hpo_id"].map(
        lambda i: "|".join(sorted(ont.terms[b].label for b in ont.top_branches(i)))
    )
    out = out.sort_values(["n_cases", "hpo_id"], ascending=[False, True]).reset_index(drop=True)
    out.insert(0, "rank", out.index + 1)
    cols = ["rank", "hpo_id", "en_label", "n_cases", "pct_cases", "n_genes", "n_diseases"]
    return out[[*cols, "branches"]]


def hpoa_check(ont: Ontology, translated: set[str]) -> dict:
    df, header = load_hpoa()
    p = df[(df["aspect"] == "P") & (df["qualifier"] != "NOT")].copy()
    p["primary"] = p["hpo_id"].map(ont.resolve)
    unresolved = int(p["primary"].isna().sum())
    p = p.dropna(subset=["primary"])
    n_dis = p.groupby("primary")["database_id"].nunique().rename("n").reset_index()
    n_dis = n_dis.sort_values(["n", "primary"], ascending=[False, True]).reset_index(drop=True)
    top = n_dis.head(HPOA_TOP)
    cutoff = int(top["n"].iloc[-1])
    return {
        "hpoa_version": header.get("version"),
        "hpoa_hpo_version": header.get("hpo-version"),
        "definition": "aspect == P and qualifier != NOT; ids resolved to primary",
        "n_annotations": len(p),
        "n_unresolved_ids": unresolved,
        "n_diseases": int(p["database_id"].nunique()),
        "annotation_coverage": round(float(p["primary"].isin(translated).mean()), 4),
        f"top{HPOA_TOP}_by_n_diseases_with_pt": int(top["primary"].isin(translated).sum()),
        f"top{HPOA_TOP}_cutoff_n_diseases": cutoff,
        "n_terms_tied_at_cutoff": int((n_dis["n"] == cutoff).sum()),
    }


def write_json(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    cfg = base_config("exp02_coverage", SEED)
    if cfg["git"]["dirty"] and not args.allow_dirty:
        sys.exit("Refusing to run: git tree is dirty. Commit first (or --allow-dirty).")

    ont = load_ontology(RAW_DIR / "hp.json")
    pt = pt_labels(load_babelon(RAW_DIR / "hp-pt.babelon.tsv"), ont)
    translated = set(pt["hpo_id"])
    translated_current = set(pt.loc[~pt["stale"], "hpo_id"])

    cases, terms, counts = load_cases(ont)
    with_obs = cases[cases["n_observed"] > 0]
    missing = missing_terms(terms, cases, translated, ont)
    per_case = per_case_table(cases, terms, translated)

    gains = {}
    for k in GAIN_K:
        added = translated | set(missing["hpo_id"].head(k))
        gains[f"top{k}_missing_added"] = coverage(terms, with_obs, added)

    metrics = {
        "definitions": "results/exp02/PREREG.md",
        "coverage": coverage(terms, with_obs, translated),
        "coverage_translated_current": coverage(terms, with_obs, translated_current),
        "simulated_gain": gains,
        "n_untranslated_distinct_terms_in_cases": len(missing),
        "hpoa_check": hpoa_check(ont, translated),
    }
    by_gene = by_group(per_case, terms, ["gene"], translated)
    by_disease = by_group(per_case, terms, ["disease_id", "disease_label"], translated)
    for name, table in (("by_gene", by_gene), ("by_disease", by_disease)):
        metrics[f"{name}_summary"] = {
            "n_groups": len(table),
            "median_of_group_frac_mean": round(float(table["frac_mean"].median()), 4),
            "pct_groups_with_no_full_case": round(float((table["pct_cases_full"] == 0).mean()), 4),
            "pct_groups_all_cases_full": round(float((table["pct_cases_full"] == 1).mean()), 4),
        }

    cfg.update(
        {
            "hpo_version_in_file": ont.version,
            "counts": counts,
            "translated_definition": "active term with an official PT label (hpo.pt_labels), "
            "stale included; coverage_translated_current excludes stale",
            "n_translated_terms": len(translated),
            "n_translated_current_terms": len(translated_current),
            "top_missing": TOP_MISSING,
            "gain_k": list(GAIN_K),
            "hpoa_top": HPOA_TOP,
        }
    )
    OUT.mkdir(parents=True, exist_ok=True)
    missing.head(TOP_MISSING).to_csv(OUT / "missing_terms.csv", index=False)
    by_gene.to_csv(OUT / "by_gene.csv", index=False)
    by_disease.to_csv(OUT / "by_disease.csv", index=False)
    per_case.to_csv(OUT / "cases.csv.gz", index=False)
    write_json(OUT / "metrics.json", metrics)
    write_json(OUT / "config.json", cfg)
    print(json.dumps(metrics["coverage"], indent=2))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
