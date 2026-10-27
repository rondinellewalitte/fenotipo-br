"""Manuscript tables as Markdown, every value read from results/. Each function returns the
table text; build_manuscript.py adds the numbered caption.

    uv run python paper/figures/tables.py      # prints all tables
"""
# ruff: noqa: E501  (table text and English summaries are prose; long lines are intended)

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from figures.common import (  # noqa: E402
    ARMS,
    MODELS,
    R1,
    R2,
    R3,
    REGISTER,
    ci,
    dec,
    load,
    num,
    pct,
    pp,
)

EXP01_METHODS = [
    ("bge-m3", "bge-m3"),
    ("e5-base", "multilingual-e5-base (query/query, primary)"),
    ("e5-base_qp", "multilingual-e5-base (query/passage)"),
    ("mpnet-multi", "paraphrase-multilingual-mpnet-base-v2"),
    ("lexical_token_sort", "Lexical baseline (token sort ratio)"),
]
# English wording of the pre-specified hypotheses; criteria as in results/exp0N/PREREG.md.
HYP01 = {
    "H1_ordering": "Top-1 ordering bge-m3 > e5 > mpnet > lexical (each pair, Holm-adjusted McNemar)",
    "H2_identical_top1_ge_0.85": "Identical cognates: every method top-1 ≥ 0.85",
    "H3_nonidentical": "Non-identical labels: lexical top-1 ≤ 0.40 and best embedding ≥ 30 points below its identical-cognate top-1",
    "H4_top10_minus_top1_ge_0.15": "Best embedding: top-10 − top-1 ≥ 15 points",
    "H5_stale_lt_current": "Labels translating an outdated English label: lower top-1 than current ones",
    "H6_ablation_all_scopes": "Adding related/broad/narrow synonyms changes top-1 by ≤ 3 points, never upwards",
    "H7_e5_query_query_ge_query_passage": "e5 with query/query prefixes ≥ query/passage",
    "H8_near_miss_share_of_errors_ge_0.20": "Best embedding: near-misses ≥ 20% of top-1 errors",
}
EXP02_EXP = {
    "E1_annotation_coverage_0.40_to_0.60": "Annotation coverage between 40% and 60%",
    "E2_pct_cases_full_le_0.10": "At most 10% of cases fully covered",
    "E3_median_frac_0.35_to_0.65": "Median per-case coverage between 0.35 and 0.65",
    "E4_top300_gain_ge_0.15": "Translating the 300 most frequent missing terms adds ≥ 15 points of annotation coverage (in sample)",
    "E5_hpoa_close_to_claude_md": "phenotype.hpoa figures close to the project's prior notes (tolerance set post hoc)",
}
HYP03 = {
    "H1_A_noninferior_to_B_margin_0.03": "H1 (primary): A non-inferior to B, lower 97.5% CI limit of F1(A) − F1(B) > −0.03",
    "H2_C_better_than_A_gain_le_0.05": "H2: C better than A (95% CI > 0), gain ≤ 0.05",
    "H3_A_beats_baseline_by_0.05": "H3: F1(A) − F1(baseline) ≥ 0.05, 95% CI > 0",
    "H4_negation_A_le_0.10_baseline_ge_0.25": "H4: negation false-positive rate ≤ 0.10 in A and ≥ 0.25 in the baseline",
    "H5_ceiling_ge_0.75_selection_loss_ge_0.10": "H5: in A, retrieval ceiling ≥ 0.75 and selection loss ≥ 0.10",
    "H6_lay_harder_than_technical": "H6 (added before extraction): technical-only recall > lay-only recall in every arm and the baseline",
}


def yes(b: bool) -> str:
    return "Yes" if b else "No"


def h03_criteria(key: str, h: dict) -> str:
    """Which half of a composite Exp 03 criterion held. H4 and H5 are conjunctions in which the
    criterion about arm A held and the one about the comparator did not, so a bare 'No' would
    read as a failure of the very thing the hypothesis is named after."""
    per = h["per_model"]
    models = list(MODELS)

    def vals(field: str) -> str:
        return ", ".join(dec(per[k][field]) for k in models)

    def all_models(field: str, test) -> bool:
        return all(test(per[k][field]) for k in models)

    if key == "H4_negation_A_le_0.10_baseline_ge_0.25":
        base = per[models[0]]["baseline_rate"]
        a_ok = yes(all_models("A_rate", lambda v: v <= 0.10)).lower()
        return (
            f"A ≤ 0.10: {a_ok} ({vals('A_rate')}); "
            f"baseline ≥ 0.25: {yes(base >= 0.25).lower()} ({dec(base)})"
        )
    if key == "H5_ceiling_ge_0.75_selection_loss_ge_0.10":
        c_ok = yes(all_models("ceiling", lambda v: v >= 0.75)).lower()
        s_ok = yes(all_models("selection_loss", lambda v: v >= 0.10)).lower()
        return (
            f"ceiling ≥ 0.75: {c_ok} ({vals('ceiling')}); "
            f"selection loss ≥ 0.10: {s_ok} ({vals('selection_loss')})"
        )
    if key == "H2_C_better_than_A_gain_le_0.05":
        return (
            f"C − A > 0 with 95% CI above 0: "
            f"{yes(all_models('diff', lambda v: v > 0)).lower()} ({vals('diff')}); "
            f"gain ≤ 0.05: {yes(all(per[k]['diff'] <= 0.05 for k in models)).lower()}"
        )
    if key == "H3_A_beats_baseline_by_0.05":
        ci_ok = all(per[k]["ci95"][0] > 0 for k in models)
        return (
            f"A − baseline ≥ 0.05: {yes(all_models('diff', lambda v: v >= 0.05)).lower()} "
            f"({vals('diff')}); 95% CI above 0: {yes(ci_ok).lower()}"
        )
    return "–"


def exp01() -> str:
    m, surf = load(R1 / "metrics.json"), load(R1 / "surface_sim.json")
    n50 = surf["by_method"]["bge-m3"]["<50"]["n"]
    out = [
        f"| Method | Top-1 (95% CI) | Top-10 | Top-1, surface similarity < 50 (n = {num(n50)}) |",
        "|---|---|---|---|",
    ]
    for key, label in EXP01_METHODS:
        s = m["results"][key]["exact"]["main"]
        out.append(
            f"| {label} | {pct(s['top1'])} ({ci(s['top1_ci95'], pct)}) | {pct(s['top10'])} "
            f"| {pct(surf['by_method'][key]['<50']['top1'])} |"
        )
    return "\n".join(out)


def exp02() -> str:
    m, oos = load(R2 / "metrics.json"), load(R2 / "out_of_sample.json")
    k_list = load(R2 / "config.json")["gain_k"]
    cov = m["coverage"]
    seeds = oos["gene_split"]["seeds_summary_annotation_coverage_gain"]
    out = [
        "| Translated terms added | Annotation coverage, in sample | Gain out of sample, mean (min–max) [post hoc] | Annotation coverage, list ranked by phenotype.hpoa [post hoc] | Cases fully covered, in sample |",
        "|---|---|---|---|---|",
        f"| 0 (official labels today) | {pct(cov['annotation_coverage'])} | – | – | {pct(cov['pct_cases_full'])} |",
    ]
    for k in k_list:
        ins = m["simulated_gain"][f"top{k}_missing_added"]
        g = seeds[f"top{k}"]["oos_gain"]
        hp = oos["hpoa_ranked_list"][f"top{k}"]["hpoa_ranked"]
        out.append(
            f"| {k} most frequent missing | {pct(ins['annotation_coverage'])} "
            f"| {pp(g['mean'])} ({pp(g['min'])} to {pp(g['max'])}) "
            f"| {pct(hp['annotation_coverage'])} | {pct(ins['pct_cases_full'])} |"
        )
    return "\n".join(out)


def exp03_main() -> str:
    m = load(R3 / "metrics.json")
    out = [
        "| Model | Arm | Precision | Recall | Micro-F1 | Macro-F1 | Stated negations predicted as present (95% CI) | Seconds per case, median |",
        "|---|---|---|---|---|---|---|---|",
    ]
    keys = [(k, a) for k in MODELS for a in ARMS] + [("none", "baseline")]
    for k, a in keys:
        s = m["arms"][f"{k}/{a}"]
        neg = s["negation_fp"]
        model = MODELS.get(k, "–")
        arm = ARMS.get(a, f"No-LLM baseline (τ = {m['baseline_tau']:.2f})")
        out.append(
            f"| {model} | {arm} | {dec(s['micro']['precision'])} | {dec(s['micro']['recall'])} "
            f"| **{dec(s['micro']['f1'])}** | {dec(s['macro']['f1'])} "
            f"| {pct(neg['rate'])} ({ci(neg['ci95'], pct)}) | {dec(s['seconds_per_case']['median'], 1)} |"
        )
    return "\n".join(out)


def hypotheses() -> str:
    h1, e2, h3 = (
        load(R1 / "hypotheses.json"),
        load(R2 / "expectations.json"),
        load(R3 / "hypotheses.json"),
    )
    if set(h1["summary"]) != set(HYP01) or set(e2["summary"]) != set(EXP02_EXP):
        raise SystemExit("hypothesis keys changed in results/; update tables.py")
    if set(h3["hypotheses"]) != set(HYP03):
        raise SystemExit("Exp 03 hypothesis keys changed in results/; update tables.py")
    out = [
        "| Exp | Pre-specified statement | Held | Criteria |",
        "|---|---|---|---|",
    ]
    for key, text in HYP01.items():
        out.append(f"| 01 | {key.split('_')[0]}: {text} | {yes(h1['summary'][key])} | – |")
    for key, text in EXP02_EXP.items():
        out.append(
            f"| 02 | {key.split('_')[0]} (expectation, no test): {text} "
            f"| {yes(e2['summary'][key])} | – |"
        )
    for key, text in HYP03.items():
        h = h3["hypotheses"][key]
        per = h["per_model"]
        cells = "; ".join(f"{MODELS[k]} {yes(per[k]['confirmed']).lower()}" for k in MODELS)
        out.append(
            f"| 03 | {text} | {yes(h['confirmed_both_models'])} ({cells}) "
            f"| {h03_criteria(key, h)} |"
        )
    return "\n".join(out)


def exp03_register() -> str:
    m = load(R3 / "metrics.json")
    d2 = m["register"]["d2"]
    out = [
        "| Model | Arm | "
        + " | ".join(
            f"{v} (n = {num(d2['qwen3-4b/A']['recall'][k]['n'])})" for k, v in REGISTER.items()
        )
        + " | Technical − lay (95% CI) |",
        "|---|---|" + "---|" * (len(REGISTER) + 1),
    ]
    for k, a in [(k, a) for k in MODELS for a in ARMS] + [("none", "baseline")]:
        r = d2[f"{k}/{a}"]
        cells = " | ".join(dec(r["recall"][g]["recall"]) for g in REGISTER)
        t = r["technical_minus_lay"]
        out.append(
            f"| {MODELS.get(k, '–')} | {ARMS.get(a, 'No-LLM baseline')} | {cells} "
            f"| {dec(t['diff'])} ({ci(t['ci95'])}) |"
        )
    return "\n".join(out)


def exp03_branches(min_gold: int = 50) -> str:
    bb = load(R3 / "by_branch.json")
    cols = [f"{k}/{a}" for k in MODELS for a in ("A", "B")] + ["none/baseline"]
    names = [f"{MODELS[c.split('/')[0]]} {c.split('/')[1]}" for c in cols[:-1]] + ["Baseline"]
    ref = bb["by_arm"][cols[0]]
    out = [
        "| HPO branch | Gold terms | " + " | ".join(f"Recall, {n}" for n in names) + " |",
        "|---|---|" + "---|" * len(cols),
    ]
    for b, v in ref.items():
        if v["n_gold"] < min_gold:
            continue
        cells = " | ".join(dec(bb["by_arm"][c].get(b, {}).get("recall")) for c in cols)
        out.append(f"| {bb['branch_labels'][b]} | {num(v['n_gold'])} | {cells} |")
    return "\n".join(out)


def exp02_missing(n: int = 10) -> str:
    missing = pd.read_csv(R2 / "missing_terms.csv")
    out = [
        "| Rank | Term without an official Portuguese label | Cases | Genes |",
        "|---|---|---|---|",
    ]
    for r in missing.head(n).itertuples():
        out.append(
            f"| {r.rank} | {r.en_label} ({r.hpo_id}) | {num(r.n_cases)} ({pct(r.pct_cases)}) | {num(r.n_genes)} |"
        )
    return "\n".join(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for fn in (exp01, exp02, exp02_missing, exp03_main, exp03_register, hypotheses, exp03_branches):
        print(f"## {fn.__name__}\n\n{fn()}\n")
