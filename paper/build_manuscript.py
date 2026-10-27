"""Render paper/manuscript.md (English, IMRaD) from the result files. Every number comes from a
file under results/ (CLAUDE.md, rule 2); tables and figures come from paper/figures/; the
references come from the Crossref-checked cache paper/refs.json (paper/refs.py --fetch).
Nothing here reads the network or writes under results/.

    uv run --group paper python paper/build_manuscript.py
"""
# ruff: noqa: E501  (the Markdown template below is prose; long lines are intended)

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reports"))
sys.path.insert(0, str(ROOT / "paper"))
from build_readme import CONCEPT_DOI, RELEASE, V010, check_release_results  # noqa: E402
from figures import (  # noqa: E402
    deviations,
    fig_exp03_differences,
    fig_exp03_register,
    fig_exp03_retrieval,
    tables,
)
from figures.common import MODELS, R1, R2, R3, ci, dec, load, num, pct, pp, sgn  # noqa: E402

OUT = ROOT / "paper" / "manuscript.md"
REFS = ROOT / "paper" / "refs.json"
REPO = "https://github.com/rondinellewalitte/fenotipo-br"
AUTHOR_EMAIL = "rondinellewalitte@gmail.com"  # public address in pyproject.toml
ABSTRACT_MAX = 250
CITE = re.compile(r"\[(@\w+(?:;\s*@\w+)*)\]")


def both(fn, sep: str = " and ") -> str:
    """'X for Qwen3-4B and Y for Gemma 3 4B'."""
    return sep.join(f"{fn(k)} for {name}" for k, name in MODELS.items())


def pair(fn) -> str:
    """'X and Y' in model order (Qwen3-4B, Gemma 3 4B)."""
    return " and ".join(fn(k) for k in MODELS)


def compress(nums: list[int]) -> str:
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(f"{nums[i]}–{nums[j]}" if j - i >= 2 else ",".join(map(str, nums[i : j + 1])))
        i = j + 1
    return ",".join(out)


def number_citations(md: str, refs: dict) -> tuple[str, list[str]]:
    order: list[str] = []

    def repl(m: re.Match) -> str:
        keys = [k.strip()[1:] for k in m.group(1).split(";")]
        for k in keys:
            if k not in refs:
                raise SystemExit(f"citation @{k} is not in {REFS.name}")
            if k not in order:
                order.append(k)
        return "[" + compress(sorted(order.index(k) + 1 for k in keys)) + "]"

    out = CITE.sub(repl, md)
    unused = sorted(set(refs) - set(order))
    if unused:
        raise SystemExit(f"references never cited: {unused}")
    return out, order


def initials(given: str) -> str:
    return "".join(p[0].upper() for p in re.split(r"[\s.\-]+", given) if p)


def reference(r: dict) -> str:
    names = [f"{a['family']} {initials(a['given'])}".strip() for a in r["authors"]]
    who = ", ".join(names[:6]) + (", et al" if len(names) > 6 else "")
    title = re.sub(r"<[^>]+>", "", r["title"]).rstrip(".")
    page = (r["page"] or "").replace("-", "–")
    tail = f" doi:{r['doi']}" + (f". PMID: {r['pmid']}" if r["pmid"] else "")
    if r["type"] == "journal-article":
        issue = f"({r['issue']})" if r["issue"] else ""
        journal = (r["short_container"] or r["container"]).rstrip(".")
        where = f"{journal}. {r['year']};{r['volume']}{issue}:{page}."
    elif r["type"] == "proceedings-article":
        where = f"In: {r['container']}. {r['publisher']}; {r['year']}. p. {page}."
    else:
        where = f"{r['publisher']}; {r['year']}."
    return f"{who}. {title}. {where}{tail}"


def words(text: str) -> int:
    keep = [
        ln for ln in text.splitlines() if not ln.startswith(("|", "![", "**Figure", "**Table", "#"))
    ]
    body = CITE.sub("", "\n".join(keep))
    body = re.sub(r"\[\d[\d,–]*\]", "", body)
    return len(body.split())


def section(md: str, start: str, end: str) -> str:
    return md.split(start, 1)[1].split(end, 1)[0]


def render() -> str:
    hs = load(ROOT / "results" / "hpo_summary.json")
    c1, m1, h1 = load(R1 / "config.json"), load(R1 / "metrics.json"), load(R1 / "hypotheses.json")
    surf, hier, wtd = (
        load(R1 / "surface_sim.json"),
        load(R1 / "hierarchy_errors.json"),
        load(R1 / "weighted.json"),
    )
    c2, m2, e2 = load(R2 / "config.json"), load(R2 / "metrics.json"), load(R2 / "expectations.json")
    oos = load(R2 / "out_of_sample.json")
    c3, m3, h3 = load(R3 / "config.json"), load(R3 / "metrics.json"), load(R3 / "hypotheses.json")
    vfull = load(R3 / "vignettes_config_full.json")
    kappa = load(R3 / "pilot" / "register_kappa.json")
    regmeta = load(R3 / "register_labels_full.meta.json")
    thr = load(R3 / "pilot" / "threshold.json")
    refs = load(REFS)["refs"]

    # --- shared values -------------------------------------------------------------------
    hpo_rel, ppkt = c1["hpo_release"], c2["phenopacket_store_release"]
    n_active, n_pt = hs["active_terms"], hs["pt_labels_active"]
    exp01 = {
        k: m1["results"][k]["exact"]["main"]
        for k in ("bge-m3", "e5-base", "e5-base_qp", "mpnet-multi", "lexical_token_sort")
    }
    bge, lex = exp01["bge-m3"], exp01["lexical_token_sort"]
    q = c1["queries"]
    mc = m1["paired_top1_mcnemar"]
    hh1 = h1["hypotheses"]
    s50 = surf["by_method"]
    hb = hier["by_method"]["bge-m3"]
    swaps = hb["hand_foot_swaps"]
    w_bge = wtd["by_method"]["bge-m3"]["weight_phenopacket_cases"]
    cov = m2["coverage"]
    gain = oos["gene_split"]["seeds_summary_annotation_coverage_gain"]
    hpoa_list = oos["hpoa_ranked_list"]
    ins50 = m2["simulated_gain"]["top50_missing_added"]
    hpoa = m2["hpoa_check"]
    k_list = c2["gain_k"]
    top_missing = pd.read_csv(R2 / "missing_terms.csv").iloc[0]
    n_seeds = len(oos["gene_split"]["seeds"])

    sample = vfull["sample"]
    vs = vfull["summary"]
    gen = vfull["generator"]
    arms, comp, d2 = m3["arms"], m3["comparisons"], m3["register"]["d2"]
    hh3 = h3["hypotheses"]
    e3 = h3["expectations"]
    oll = c3["ollama"]
    opts = c3["llm_options"]
    ret = c3["retrieval"]
    oracle = m3["oracle_spans_bge_m3_en_index"]
    base = arms["none/baseline"]
    grid = sorted(float(x) for x in thr["grid"])
    vram = max(v.get("peak_vram_mib") or 0 for v in c3["stages"].values() if isinstance(v, dict))
    calib = [v["agreement_with_pilot_labels"] for v in regmeta["calibration"]["per_batch"].values()]
    classes = regmeta["classes"]
    dev_counts = deviations.counts()
    n_held = {
        "01": (sum(h1["summary"].values()), len(h1["summary"])),
        "02": (sum(e2["summary"].values()), len(e2["summary"])),
        "03": (sum(h["confirmed_both_models"] for h in hh3.values()), len(hh3)),
    }
    held03 = [k.split("_")[0] for k, h in hh3.items() if h["confirmed_both_models"]]

    def micro(k: str, a: str, f: str = "f1") -> str:
        return dec(arms[f"{k}/{a}"]["micro"][f])

    def diff(k: str, name: str, ci_key: str = "ci95") -> str:
        d = comp[k][name]
        return f"{sgn(d['diff'])} ({'97.5' if ci_key == 'ci97_5' else '95'}% CI {ci(d[ci_key])})"

    def strat(k: str, col: str, key: str, arm: str) -> float:
        return arms[f"{k}/{arm}"]["recall_by_stratum"][col][key]["recall"]

    # The text states these directions; stop if the results no longer support them.
    for k in MODELS:
        ab = comp[k]["A-B"]["ci97_5"]
        assert ab[0] < -0.03 and ab[1] < 0, "H1 failed and B superior"
        assert comp[k]["C-A"]["ci95"][0] <= 0, "C did not improve on A"
        assert comp[k]["A-baseline"]["ci95"][0] > 0, "A beat the baseline"
        sims = {
            b: strat(k, "sim_bin", b, "A") - strat(k, "sim_bin", b, "B")
            for b in ("<50", "50-80", ">=80")
        }
        assert sims["<50"] == min(sims.values()) and sims["<50"] < 0, "B gain largest at < 50"
        assert arms[f"{k}/A"]["retrieval_ceiling_recall"] < 0.75, "H5 ceiling not met"
        assert hh3["H6_lay_harder_than_technical"]["per_model"][k]["confirmed"]
    assert not e2["summary"]["E1_annotation_coverage_0.40_to_0.60"], "Exp 02 E1 described as unmet"
    lay_below = [
        MODELS[k]
        for k in MODELS
        if d2[f"{k}/A"]["recall"]["lay"]["recall"] < d2["none/baseline"]["recall"]["lay"]["recall"]
    ]
    assert lay_below == ["Gemma 3 4B"], (
        "text says only Gemma falls below the baseline on lay-only terms"
    )
    assert vs["n_replacements"] == 0, "text says every drawn case was kept"
    n_drop = len(vs["dropped_items_final"])
    dropped_text = (
        f"{n_drop} items were dropped in the full set"
        if n_drop
        else "no item was dropped in the full set"
    )
    assert mc["bge-m3 vs e5-base"]["p_holm"] < 0.001, "text says Holm-adjusted p < 0.001"
    assert comp["gemma3-4b"]["C-A"]["ci95"][1] < 0, "text says C was worse than A for Gemma"
    assert comp["qwen3-4b"]["C-A"]["ci95"][1] >= 0, "text says C was worse only for Gemma"
    assert hs["babelon_rows"] - hs["babelon_label_rows"] == 1, "text says one non-label row"
    bb = load(R3 / "by_branch.json")
    gem_a = {b: v for b, v in bb["by_arm"]["gemma3-4b/A"].items() if v["n_gold"] >= 50}
    top_branch = max(gem_a, key=lambda b: gem_a[b]["n_gold"])
    low_branch = min(gem_a, key=lambda b: gem_a[b]["recall"])
    miss_top10 = {k: 1 - arms[f"{k}/A"]["retrieval_ceiling_recall"] for k in MODELS}

    # --- figures and tables --------------------------------------------------------------
    fig1 = fig_exp03_differences.render().relative_to(OUT.parent).as_posix()
    fig2 = fig_exp03_retrieval.render().relative_to(OUT.parent).as_posix()
    fig3 = fig_exp03_register.render().relative_to(OUT.parent).as_posix()

    pt_phrase_n = arms["qwen3-4b/A"]["recall_by_stratum"]["phrase_is_pt_label"]["True"]["n"]
    has_pt_n = arms["qwen3-4b/A"]["recall_by_stratum"]["has_pt_label"]["True"]["n"]
    sim_n = {
        b: arms["qwen3-4b/A"]["recall_by_stratum"]["sim_bin"][b]["n"]
        for b in ("<50", "50-80", ">=80")
    }
    e_held = {name.split("_")[0]: [MODELS[k] for k in MODELS if v[k]] for name, v in e3.items()}

    def e_text(e: str) -> str:
        who = e_held[e]
        return "both models" if len(who) == 2 else (who[0] if who else "neither model")

    doi_v2 = RELEASE["doi"]
    if not doi_v2:
        raise SystemExit(
            "RELEASE['doi'] is empty: the manuscript cites the version DOI of its numbers"
        )

    md = f"""<!-- Generated by paper/build_manuscript.py from results/; do not edit by hand. -->

# Brazilian Portuguese phenotype text and the Human Phenotype Ontology: translation coverage, cross-lingual retrieval and extraction with small local language models

*Provisional title. Draft for medRxiv (Health Informatics) or arXiv (cs.CL).*

**R. Walitte** (Rondinelle Walitte Pedro de Jesus)<sup>1</sup> · ORCID [0009-0004-1776-2754](https://orcid.org/0009-0004-1776-2754)
**[Clinical co-author: name, affiliation, ORCID. TODO]**<sup>2</sup>

<sup>1</sup> Independent researcher. [TODO: city, country.] <sup>2</sup> [TODO.]
Corresponding author: R. Walitte, {AUTHOR_EMAIL}

> Research support only. Nothing in this work is a clinical or diagnostic tool or should guide patient care. Only public data and synthetic text were used; no patient data.

## Abstract

**Background:** Tools extracting Human Phenotype Ontology (HPO) terms from clinical text are built for English, and only {pct(hs["pt_coverage_active"])} of active HPO terms have an official Portuguese label. We measured the consequences for Brazilian Portuguese.

**Methods:** Three experiments followed analysis plans time-stamped in git before any results existed. Experiment 1 searched {num(q["n_main_under_HP:0000118"])} official Portuguese labels in an English-only index with embedding models and a lexical baseline. Experiment 2 measured label coverage in {num(cov["n_cases"])} Phenopacket Store cases. In Experiment 3, a large language model (LLM) wrote {num(c3["n_cases"])} synthetic Brazilian Portuguese vignettes from published cases; two local LLMs ({", ".join(MODELS.values())}) extracted findings directly in Portuguese (A) or after translation to English (B), against a no-LLM baseline. The primary outcome was micro-F1, A versus B.

**Results:** In Experiment 1, bge-m3 ranked the correct term first for {pct(bge["top1"])} of labels. In Experiment 2, official labels covered {pct(cov["annotation_coverage"])} of case annotations and {pct(cov["pct_cases_full"])} of cases fully. In Experiment 3, translating first scored higher: F1(A) − F1(B) was {sgn(comp["qwen3-4b"]["A-B"]["diff"])} (97.5% CI {ci(comp["qwen3-4b"]["A-B"]["ci97_5"])}) for Qwen3-4B and {sgn(comp["gemma3-4b"]["A-B"]["diff"])} ({ci(comp["gemma3-4b"]["A-B"]["ci97_5"])}) for Gemma 3 4B, so non-inferiority was not shown. Adding Portuguese labels to the index did not help, and hurt Gemma 3 4B. The correct term was among retrieved candidates for {pair(lambda k: pct(arms[f"{k}/A"]["retrieval_ceiling_recall"]))} of gold terms, and lay-only descriptions were recalled at {pair(lambda k: dec(d2[f"{k}/A"]["recall"]["lay"]["recall"]))}.

**Conclusions:** On synthetic text, retrieval and lay wording limited small local models more than the extraction language did. The translate-first advantage needs testing on real Brazilian clinical notes.

**Keywords:** Human Phenotype Ontology; Brazilian Portuguese; rare diseases; phenotype extraction; large language models; cross-lingual retrieval

## Introduction

Rare diseases are individually uncommon but together affect an estimated 3.5–5.9% of the population [@nguengangwakap2020]. Their diagnosis depends on precise phenotyping, and the Human Phenotype Ontology (HPO) is the standard vocabulary for it [@robinson2012; @kohler2021; @gargano2024]. HPO terms feed phenotype-driven prioritization of genes and diseases [@smedley2015; @robinson2020], and case-level descriptions are exchanged as GA4GH Phenopackets [@jacobsen2022], of which Phenopacket Store is a large public collection [@danis2025]. In Brazil, a national rare-disease network is collecting clinical data with international ontologies [@felix2022].

Clinicians write free text, so HPO terms must be extracted from notes. Concept recognizers such as ClinPhen and PhenoTagger [@deisseroth2019; @luo2021], general LLMs [@groza2024] and LLMs combined with retrieval, as in RAG-HPO [@garcia2025], were developed and evaluated on English text. LLMs have also been benchmarked for diagnosis from phenopacket-derived prompts [@reese2026]. [TODO: the multilingual vignettes derived from Phenopacket Store (phenopacket2prompt, Zenodo 10.5281/zenodo.14907503) cover ten languages but not Portuguese; that DOI is registered with DataCite, not Crossref, so it is not yet cited.] Clinical language processing in other languages has fewer resources [@neveol2018]. Brazilian Portuguese has a semantically annotated clinical corpus, annotated with UMLS rather than HPO [@oliveira2022], and clinical language models [@schneider2020].

The HPO has community translations, and its browser shows labels in ten languages besides English [@gargano2024]; English also has plain-language synonyms for lay descriptions [@vasilevsky2018]. The official Portuguese file of release {hpo_rel} has labels for {num(n_pt)} of {num(n_active)} active terms ({pct(hs["pt_coverage_active"])}), and {num(hs["babelon_label_rows"])} of its {num(hs["babelon_rows"])} rows are labels (the other is a definition), so it has no synonyms. A Portuguese note can be mapped directly, with multilingual retrieval and models, or translated to English first. Which works better, and how much the incomplete translation limits either route, has not been measured.

We report three analyses, each with a plan written before its results existed:

1. **Experiment 1:** can an official Portuguese label be mapped to its HPO term by searching English text only?
2. **Experiment 2:** how much of the phenotype annotation of published rare-disease cases already has an official Portuguese label, and which missing terms matter most?
3. **Experiment 3:** on synthetic Brazilian Portuguese clinical vignettes, does a small LLM running locally extract HPO terms as well directly in Portuguese as after translating to English? Does adding the Portuguese labels to the index help, and how much does the LLM add to a retrieval-only baseline?

Whether extraction errors change the ranking of candidate genes or diseases is outside the scope of this work.

## Methods

### Pre-specification, deviations and reproducibility

For each experiment, hypotheses, outcomes and analysis rules were written in a pre-specification file (`results/exp0N/PREREG.md`) and committed to the project's git repository before any of its results were computed (Experiments 1 and 2) or any vignette was generated (Experiment 3); the structural counts seen beforehand are listed in each file. Later changes were only appended, dated, to a "Deviations" section. The plans were not deposited in an external registry. The git timestamps are the only record of their order, and the repository became public only after each experiment's results existed (see Limitations). We use "pre-specified" for what was in these files from the start, "amendment" for dated changes made before the affected data or results existed, and "post hoc" for analyses defined after results were seen. The three files list {dev_counts["01"]}, {dev_counts["02"]} and {dev_counts["03"]} dated entries, all summarized in Supplementary Table S1.

Every number, table and figure in this manuscript is generated by `paper/build_manuscript.py` from the result files of release v{RELEASE["version"]}, which stops if those files differ from the tagged release. The Experiment 1 and 2 results are identical to those of release v{V010["version"]}, which the same check verifies.

### Data

We used HPO release {hpo_rel} (`hp.json`, `phenotype.hpoa` and the Portuguese translation file `hp-pt.babelon.tsv` of the same tag) and Phenopacket Store {ppkt} [@danis2025]. HPO {hpo_rel} has {num(n_active)} active terms, {num(hs["active_terms_under_HP:0000118"])} of them under Phenotypic abnormality (HP:0000118). Of the official Portuguese labels of active terms, {num(hs["pt_labels_active_stale"])} translate an earlier version of the English label. Files were downloaded by script and their SHA-256 hashes recorded in each experiment's `config.json`.

### Experiment 1: cross-lingual normalization of official labels

The queries were the {num(q["n_total"])} official Portuguese labels of active terms; the {num(q["n_main_under_HP:0000118"])} under HP:0000118 formed the primary scope. The index held only English text: the label and exact synonyms of all {num(c1["index"]["variants"]["exact"]["n_ids"])} active terms ({num(c1["index"]["variants"]["exact"]["n_texts"])} texts). We compared bge-m3 [@chen2024], multilingual-e5-base with two prefix schemes, paraphrase-multilingual-mpnet-base-v2 [@reimers2020] (revisions in `results/exp01/config.json`) and a lexical baseline (rapidfuzz token-sort ratio on case- and accent-folded text). A term's score was the maximum over its texts, and ties counted against a hit. The primary outcome was top-1 accuracy; pairwise differences were tested with exact McNemar tests [@mcnemar1947] and Holm correction over four pre-specified comparisons. The {len(h1["summary"])} hypotheses in Table 1 were fixed in advance. Post-hoc analyses, all labeled as such below, classified top-1 errors by their hierarchical relation to the correct term, counted hand/foot swaps and weighted accuracy by how often each term is used in Phenopacket Store.

### Experiment 2: translation coverage in published cases

The terms of a case were its observed phenotypic features (excluded features did not count), resolved to current primary IDs and counted once per case. Of {num(c2["counts"]["n_cases"])} phenopackets, {num(c2["counts"]["n_cases_without_observed_terms"])} had no observed term and were excluded. A term counted as translated if it had an official Portuguese label. Outcomes were annotation coverage (case–term pairs), the share of fully covered cases and the distribution of per-case coverage, plus a ranked list of untranslated terms by number of cases. The {len(e2["summary"])} descriptive expectations in Table 1 were written in advance, without tests. Post-hoc checks estimated the coverage gain from translating the k most frequent missing terms out of sample: the list was ranked on half of the genes and evaluated on the other half (seed 42; spread over {n_seeds} other seeds). A second list was ranked by the number of annotated diseases in `phenotype.hpoa`.

### Experiment 3: extraction from synthetic Portuguese vignettes

**Cases.** Eligible cases had 3 to 15 observed terms under HP:0000118 ({num(sample["n_eligible"])} cases, {num(sample["n_genes_eligible"])} genes). With a fixed seed, one case was drawn per gene; the first {sample["n_pilot"]} genes formed the pilot, the next {sample["n_full"]} the full set and the rest a reserve, with no gene shared between sets. The gold standard was the observed terms; up to {sample["max_negated"]} excluded terms per case, other than ancestors or descendants of an observed term, were stated as absent in the text and counted as false positives if extracted. The full set had {num(m3["n_gold_terms"])} gold terms and {num(m3["n_negated_terms"])} stated negations.

**Vignettes.** `{gen["model"]}` (Anthropic API, effort "{gen["effort"]}") wrote each vignette as a Brazilian first-visit history from the patient's sex and age and the English label and definition of each item; it saw no HPO ID, disease, gene or publication. The prompt asked for each item in Brazilian clinical language, mixing lay and technical wording, nothing clinical beyond the items, and the exact phrase expressing each item. An automatic check rejected a vignette containing an HPO or disease ID, the gene symbol or an English label, or with fewer than 3 present items left; by amendment, an item without a verbatim phrase in the text left the gold standard instead of failing the vignette ({dropped_text}). A label counted as English only if it was not part of an official Portuguese label and contained a spelling impossible in Portuguese, so that Greco-Latin cognates passed (an amendment; Supplementary Table S1). A case failing twice would be replaced from the reserve; after the amendments in Supplementary Table S1, all {vs["n_final"]} drawn cases of the full set were kept. The API no longer accepts sampling parameters, so reproducibility rests on the fixed model, versioned prompts and stored outputs, which are reused and never regenerated. Generation cost was capped at US$ {gen["budget_usd_cumulative"]:.0f} cumulative; the full set took {num(vs["api_calls"])} calls (US$ {vs["cost_usd"]:.2f}), and Experiment 3 spent US$ {vfull["spent_usd_total"]:.2f} in total. The generator was never used as an extractor.

**Arms.** Two local models ran through Ollama {oll["ollama_version"]}: `{oll["models"]["qwen3-4b"]["tag"]}` (digest {oll["models"]["qwen3-4b"]["digest"][:12]}) and `{oll["models"]["gemma3-4b"]["tag"]}` (digest {oll["models"]["gemma3-4b"]["digest"][:12]}), with temperature {opts["temperature"]}, seed {opts["seed"]} and a {num(opts["num_ctx"])}-token context; extraction and selection outputs were constrained by JSON schemas. In arm A, the LLM listed present and absent findings in Portuguese; each present finding was embedded with `{ret["model"]}` and the {ret["topk"]} closest terms were retrieved from an English index (label and exact synonyms of the {num(ret["index_en"]["n_ids"])} terms under HP:0000118, {num(ret["index_en"]["n_texts"])} texts); the LLM then chose one candidate or none, constrained to the {ret["topk"]} IDs. In arm B, the same LLM first translated the vignette to English and the same steps followed. Arm C reused A's findings but searched a bilingual index that added the {num(ret["index_bi"]["n_pt_labels"])} official Portuguese labels. The selector always saw the finding and each candidate's ID and English label. The baseline split the Portuguese text into clauses, took the top-1 term of each clause from the English index and kept it if its score was at least τ, with no negation handling. Prompts were identical for both models.

**Outcomes and hypotheses.** The primary outcome was micro-averaged F1 over terms with exact ID match, compared between A and B within each model and paired by case. Intervals came from a case bootstrap ({num(m3["bootstrap"]["n_boot"])} resamples, percentile method) [@efron1993]. H1, the primary hypothesis, stated non-inferiority of A: the lower limit of the 97.5% CI of F1(A) − F1(B) (Bonferroni over two models) above −0.03 in both models; if the interval excluded zero, superiority in either direction would be reported. Secondary hypotheses H2–H6 (Table 1) used 95% CIs without adjustment. Diagnostics included the retrieval ceiling (the share of gold terms among the candidates of any finding), the selection loss (ceiling minus recall) and a phrase oracle (the generator's own phrase searched with bge-m3, without an LLM).

**Back-translation strata.** The generator wrote from English labels, so translating back could recover them artificially. Each gold term was stratified by surface similarity between its Portuguese phrase and its English label (rapidfuzz ratio, bands < 50, 50–80, ≥ 80), and by whether the phrase equalled the official Portuguese label.

**Clinical register.** Before any full-set extraction, each gold item was labeled as written in technical terms only, lay terms only or both (stratum D2). Labels came from independent Claude Code subagents (`{gen["model"]}`), blind to a rule-based classification and to any extraction, in batches that each repeated the same calibration cases. The author, who is not a clinician, labeled {kappa["n_items"]} pilot items, stratified by the labeler's class ({kappa["per_class_drawn"]["technical"]} technical only, {kappa["per_class_drawn"]["lay"]} lay only, {kappa["per_class_drawn"]["both"]} both), without seeing the labeler's answer. Cohen's kappa [@cohen1960] was {dec(kappa["cohen_kappa"], 2)} (95% CI {ci(kappa["cohen_kappa_ci95"], lambda x: dec(x, 2))}), above the 0.6 threshold, set by amendment before any extraction, for treating D2 as confirmatory. Agreement with the pilot labels on the repeated calibration items ranged from {pct(min(calib), 0)} to {pct(max(calib), 0)} across batches. H6 and expectations E6–E8 on these strata were added by amendment before any extraction. A literal, rule-based stratum (D1) is reported descriptively.

**Pilot and freezing.** The pilot ({num(sample["n_pilot"])} cases, both models, all arms) measured time and memory and set τ = {m3["baseline_tau"]:.2f}, the value maximizing pilot micro-F1 on a grid from {grid[0]:.2f} to {grid[-1]:.2f}. The extraction prompts were not changed after the pilot; prompts, τ and models were frozen before the full set, which refused to run with uncommitted code. Pilot numbers enter no hypothesis.

### Software and compute

Analyses used Python {c3["python"].split()[0]}. Embeddings and local LLMs ran on a laptop GPU with 6 GB of memory ({c3["retrieval"]["encode_device"]["gpu"]}); the run was staged so that the LLM and the embedding model never shared the GPU. Peak memory use of the whole GPU, display included, was {num(vram)} MiB, and the full Experiment 3 run took {c3["wall_seconds"] / 3600:.1f} h for {num(c3["new_ollama_calls"])} model calls.

## Results

### Primary outcomes and pre-specified hypotheses

Table 1 lists every pre-specified hypothesis and expectation with its outcome: {n_held["01"][0]} of {n_held["01"][1]} hypotheses held in Experiment 1, {n_held["02"][0]} of {n_held["02"][1]} expectations in Experiment 2, and {n_held["03"][0]} of {n_held["03"][1]} hypotheses in both models in Experiment 3 ({", ".join(held03)}).

**Table 1.** Pre-specified hypotheses (Experiments 1 and 3) and expectations (Experiment 2). Sources: `results/exp01/hypotheses.json`, `results/exp02/expectations.json`, `results/exp03/hypotheses.json`.

{tables.hypotheses()}

**Experiment 1.** Searching English text only, bge-m3 ranked the correct term first for {pct(bge["top1"])} (95% CI {ci(bge["top1_ci95"], pct)}) of the {num(bge["n"])} labels, against {pct(lex["top1"])} for the lexical baseline (Table 2). bge-m3 exceeded e5 by {mc["bge-m3 vs e5-base"]["diff_a_minus_b"] * 100:.1f} percentage points (Holm-adjusted p < 0.001), but mpnet scored {abs(mc["mpnet-multi vs lexical_token_sort"]["diff_a_minus_b"]) * 100:.1f} percentage points below the lexical baseline, so the pre-specified ordering (H1) failed. The top-10 − top-1 gap for bge-m3 was {hh1["H4_top10_minus_top1_ge_0.15"]["gap"] * 100:.1f} points, below the 15 of H4, and e5 scored higher with query/passage prefixes than with the query/query scheme expected by H7.

**Table 2.** Experiment 1: top-1 and top-10 accuracy of official Portuguese labels searched against an English-only index (primary scope, n = {num(bge["n"])}; ties count against a hit). Sources: `results/exp01/metrics.json`, `results/exp01/surface_sim.json`.

{tables.exp01()}

**Experiment 2.** In {num(cov["n_cases"])} cases with {num(cov["n_annotations"])} observed annotations, {pct(cov["annotation_coverage"])} of annotations had an official Portuguese label, below the 40–60% range of expectation E1. Only {pct(cov["pct_cases_full"])} of cases were fully covered and {pct(cov["pct_cases_zero"])} had no translated term; the median per-case coverage was {dec(cov["frac_median"], 2)}. In `phenotype.hpoa`, {pct(hpoa["annotation_coverage"])} of disease annotations and {hpoa["top500_by_n_diseases_with_pt"]} of the 500 terms annotated to the most diseases had a Portuguese label.

**Experiment 3.** Table 3 gives precision, recall and F1 per arm. Translating first gave the highest F1 for both models. F1(A) − F1(B) was {both(lambda k: diff(k, "A-B", "ci97_5"))} (Figure 1). Both lower limits fell below the −0.03 margin, so H1 was not supported. Both intervals excluded zero, so, as pre-specified, we report B as superior to A in both models.

**Table 3.** Experiment 3: extraction from {num(c3["n_cases"])} synthetic vignettes ({num(m3["n_gold_terms"])} gold terms, {num(m3["n_negated_terms"])} stated negations). Micro scores pool all terms; macro scores average per case. Source: `results/exp03/metrics.json`.

{tables.exp03_main()}

![Figure 1]({fig1})

**Figure 1.** Paired differences in micro-F1 between arms, by model. The primary comparison (A − B) shows the pre-specified 97.5% CI and the non-inferiority margin; the others show 95% CIs. Case bootstrap, {num(m3["bootstrap"]["n_boot"])} resamples. Source: `results/exp03/metrics.json` → `comparisons`.

The bilingual index did not improve on A: F1(C) − F1(A) was {both(lambda k: diff(k, "C-A"))}, so H2 was not supported; for Gemma 3 4B the whole interval lies below zero, so C was worse than A. Both LLM pipelines beat the no-LLM baseline (H3): F1(A) − F1(baseline) was {both(lambda k: diff(k, "A-baseline"))}. H4 failed on its second criterion: in arm A, {pair(lambda k: pct(arms[f"{k}/A"]["negation_fp"]["rate"]))} of the stated negations were predicted as present (criterion ≤ 10%), but the baseline rate was {pct(base["negation_fp"]["rate"])}, not ≥ 25%. H5 failed on the retrieval ceiling. H6 held: technical-only terms were recalled better than lay-only terms in every arm and in the baseline.

### Secondary and exploratory analyses

**Experiment 1.** Where the Portuguese label is spelled far from the English text (surface similarity < 50, n = {num(s50["bge-m3"]["<50"]["n"])}), bge-m3 reached {pct(s50["bge-m3"]["<50"]["top1"])} top-1 against {pct(s50["lexical_token_sort"]["<50"]["top1"])} for the lexical baseline (Table 2). Labels translating an outdated English label scored lower than current ones ({pct(hh1["H5_stale_lt_current"]["stale_top1"])} vs {pct(hh1["H5_stale_lt_current"]["current_top1"])}, n = {hh1["H5_stale_lt_current"]["stale_n"]}; H5). Near-misses, where the top term is a direct parent or child of the correct one, were {pct(hh1["H8_near_miss_share_of_errors_ge_0.20"]["share_of_top1_errors"])} of top-1 errors (H8). Post hoc, {pct(hb["main"]["share_of_errors"]["distant"])} of bge-m3 top-1 errors were hierarchically distant from the correct term, and {pct(swaps["share_of_errors"])} swapped hand and foot, as in "toe" for "finger". Weighting each term by its number of Phenopacket Store cases (post hoc) gave a bge-m3 top-1 of {pct(w_bge["top1_weighted"])} (95% CI {ci(w_bge["top1_weighted_ci95_bootstrap"], pct)}).

**Experiment 2.** The most frequent untranslated terms were common neurodevelopmental findings (Supplementary Table S2); the first, {top_missing["en_label"]}, appears in {pct(top_missing["pct_cases"])} of cases. Translating the 50 most frequent missing terms would raise annotation coverage to {pct(ins50["annotation_coverage"])} in sample. Post hoc, out of sample, the gain was {pp(gain["top50"]["oos_gain"]["mean"])} on average (range {pp(gain["top50"]["oos_gain"]["min"])} to {pp(gain["top50"]["oos_gain"]["max"])}), and a list ranked independently by `phenotype.hpoa` reached {pct(hpoa_list["top50"]["hpoa_ranked"]["annotation_coverage"])} (Table 4).

**Table 4.** Experiment 2: annotation coverage of official Portuguese labels in Phenopacket Store {ppkt}, and simulated coverage if the k most frequent missing terms were translated (k = {", ".join(map(str, k_list))}). Sources: `results/exp02/metrics.json`, `results/exp02/out_of_sample.json`.

{tables.exp02()}

**Experiment 3: where terms are lost.** In arm A, the correct term was among the {ret["topk"]} candidates of some finding for only {pct(arms["qwen3-4b/A"]["retrieval_ceiling_recall"])} of gold terms with Qwen3-4B and {pct(arms["gemma3-4b/A"]["retrieval_ceiling_recall"])} with Gemma 3 4B, and the selection step lost a further {pair(lambda k: pct(arms[f"{k}/A"]["selection_loss"]))} (Figure 2). With the generator's own phrase and no LLM, bge-m3 placed the correct term first for {pct(oracle["top1"])} and in the top 10 for {pct(oracle["top10"])} of gold terms. For comparison, clean official labels reached {pct(bge["top10"])} top-10 in Experiment 1. This cross-experiment comparison is descriptive, and the Experiment 3 index was smaller (terms under HP:0000118 only), which should make its task easier. Near-misses were {pair(lambda k: pct(arms[f"{k}/A"]["near_miss"]["share_of_fp"]))} of false positives in arm A (E2), and hand/foot swaps {pair(lambda k: pct(arms[f"{k}/A"]["hand_foot_swap"]["share_of_fp"]))} (E3). Qwen3-4B answered "none" for {pct(arms["qwen3-4b/A"]["none_rate"])} of findings in arm A and Gemma 3 4B for {pct(arms["gemma3-4b/A"]["none_rate"])}.

![Figure 2]({fig2})

**Figure 2.** Share of gold terms found (recall), retrieved among the 10 candidates but not chosen, and never retrieved, by model and arm. The number at the right end of the light segment is the retrieval ceiling. The dotted line is the phrase oracle (generator phrase, bge-m3, top-10, no LLM). Source: `results/exp03/metrics.json` → `arms`, `oracle_spans_bge_m3_en_index`.

**Back-translation strata.** Most gold phrases were far from their English label ({num(sim_n["<50"])} below 50, {num(sim_n["50-80"])} from 50 to 80 and {num(sim_n[">=80"])} at 80 or above). B's advantage was largest in the lowest band (recall A − B: {pair(lambda k: sgn(strat(k, "sim_bin", "<50", "A") - strat(k, "sim_bin", "<50", "B")))}) and absent at 80 or above ({pair(lambda k: sgn(strat(k, "sim_bin", ">=80", "A") - strat(k, "sim_bin", ">=80", "B")))}). Literal recovery of the English source label would predict the opposite pattern. The generator used the official Portuguese label as the phrase for {num(pt_phrase_n)} of {num(m3["n_gold_terms"])} gold terms ({num(has_pt_n)} gold terms had such a label). Source: `results/exp03/metrics.json` → `recall_by_stratum`.

**Clinical register.** Of the {num(regmeta["n_items"])} gold items, {num(classes["technical"])} were technical only, {num(classes["lay"])} lay only and {num(classes["both"])} both. Lay-only recall in arm A was {both(lambda k: dec(d2[f"{k}/A"]["recall"]["lay"]["recall"]))}, against {pair(lambda k: dec(d2[f"{k}/A"]["recall"]["technical"]["recall"]))} for technical-only terms (Figure 3). For Gemma 3 4B, lay-only recall in A fell below the no-LLM baseline ({dec(d2["none/baseline"]["recall"]["lay"]["recall"])}). Translating first raised lay-only recall by {pair(lambda k: dec(-d2[f"{k}/between_arms"]["lay"]["A-B"]["diff"]))} (95% CI {pair(lambda k: ci([-x for x in reversed(d2[f"{k}/between_arms"]["lay"]["A-B"]["ci95"])]))}). The A–B gap was larger for lay-only than for technical-only terms in {e_text("E6")} (E6). The bilingual index did not gain more on technical-only terms (E7: {e_text("E7")}), and the baseline's drop from technical to lay was not larger than A's (E8: {e_text("E8")}).

![Figure 3]({fig3})

**Figure 3.** Recall by clinical register of the gold term (D2), by arm and model, with 95% case-bootstrap CIs. The baseline does not use an LLM and is the same in both panels. Source: `results/exp03/metrics.json` → `register.d2`.

**Other expectations and post-hoc analyses.** Micro-F1 of arm A fell within the expected 0.35–0.65 range in {e_text("E1")} (E1). The time expectation (E4: median ≤ 30 s per case in A and B at least 1.5 times slower) held for {e_text("E4")}. Recall was higher for terms with an official Portuguese label in {e_text("E5")} (E5). Post hoc, recall by top-level HPO branch is given in Supplementary Table S3. The branch with the most gold terms was {bb["branch_labels"][top_branch]} (n = {num(gem_a[top_branch]["n_gold"])}); Gemma 3 4B in arm A had its lowest recall in {bb["branch_labels"][low_branch]} ({dec(gem_a[low_branch]["recall"])}).

## Discussion

Across three analyses, the language of the input was not the main obstacle to mapping Brazilian Portuguese text to the HPO. Experiment 1 showed that a multilingual embedding model finds most clean Portuguese labels in an English-only index. In Experiment 3, the losses came from retrieval and from lay wording.

**Retrieval was the bottleneck.** Even with a perfect choice step, {pct(miss_top10["qwen3-4b"])} of gold terms with Qwen3-4B and {pct(miss_top10["gemma3-4b"])} with Gemma 3 4B were never among the candidates in arm A. The phrase oracle shows that this is not only an LLM problem: with the generator's own phrases, bge-m3 missed the top 10 for {pct(1 - oracle["top10"])} of terms, against {pct(1 - bge["top10"])} for clean labels in Experiment 1, although its index was smaller here. Free-text descriptions sit further from HPO labels than translated labels do. Improving what is searched and how, through more synonyms, lay phrasing or candidate reranking, may matter more than a larger extractor. This study did not test any of these.

**"Translate first" won on synthetic vignettes, and that may not transfer.** The pre-specified hypothesis was that direct extraction would be non-inferior; instead translation helped both models. The back-translation strata argue against the simplest artifact, recovery of the English source label: the gain was largest where the Portuguese phrase was least like that label. A subtler artifact remains possible. An LLM wrote the vignettes from English material, and its Portuguese may follow English structure that a translator easily maps back. Real Brazilian notes, with abbreviations, local expressions and typing errors, may behave differently, so this result supports testing the translate-first route on real text, not adopting it.

**Lay language is the largest gap for small models.** Both models recalled lay-only descriptions worse than technical ones. Gemma 3 4B recalled them worse than a retrieval baseline without any LLM. It had already skipped lay descriptions in a timing benchmark on an out-of-sample synthetic text, before the pilot; the prompts were deliberately not tuned per model. English HPO has plain-language synonyms [@vasilevsky2018], and the official Portuguese file has none. Histories often record findings in the family's own words, so this gap matters for any Portuguese pipeline.

**The Portuguese translation is not prioritized by use.** Experiment 2 showed that the untranslated terms include the most frequent findings in published cases. Translating the 50 most frequent missing terms would raise coverage of case annotations substantially, and the gain held out of sample (post hoc). Labels alone are not enough, however: adding the official labels to the index (arm C) did not help, and lowered F1 for Gemma 3 4B, partly because the vignettes rarely used the official label as written. A translation effort ranked by use, with synonyms including lay wording, is the change these data point to; whether it improves extraction on real notes remains to be measured.

**Comparison with other work.** RAG-HPO reported higher F1 on English case reports with a 70-billion-parameter model [@garcia2025]; data, language, model size and scoring differ, so the figures are not comparable. Our setting was deliberately small: 4-billion-parameter models on a laptop GPU, a setting in which clinical text need not leave a local machine. The results describe that setting only.

## Limitations

- **Synthetic vignettes.** All Experiment 3 texts were written by an LLM from curated term lists. They lack the typing errors, abbreviations, contradictions and disorder of real notes, and their lay and technical wording is more regular. No result here was validated on real clinical records.
- **The same model generated the vignettes and labeled their register.** `{gen["model"]}` wrote the vignettes and, as independent subagents, labeled the D2 strata. The labeler may recognize its own phrasing. Author–labeler agreement covers part of this risk; review by a geneticist is planned.
- **Possible contamination with the original articles.** The cases come from published articles that the generator and the extractors may have seen during training, as may Phenopacket Store itself, and the embedding models may have seen the HPO and its translations [@sainz2023]. The generator was told not to add details, but the automatic check catches only part of this.
- **The human check was done by a non-clinician.** The author checked the register labels on {kappa["n_items"]} items and is not a clinician; the labeler also tended to mark borderline phrases as "both", which shifts absolute stratum levels but not comparisons between arms.
- **No validation on real Brazilian records.** Real clinical notes in Portuguese, such as SemClinBr [@oliveira2022], require a data-use agreement that was not in place.
- **Pre-specification without an external registry.** The plans were time-stamped only in the project's git history, which became public after each experiment's results existed, so the public record alone cannot prove their order.
- **Scope.** There was a single author and a single generator, two quantized 4-billion-parameter models, exact-ID scoring (near-misses count as errors), clean labels in Experiment 1 and literature cases in Experiment 2, which do not reflect the distribution of terms in Brazilian records. Effects on gene or disease ranking were not measured.

## Data and code availability

Code, pre-specification files, prompts, result files, vignettes, register labels and every local-model call with its output are at {REPO} and archived on Zenodo. The version that produced every number in this manuscript is v{RELEASE["version"]}, DOI [{doi_v2}](https://doi.org/{doi_v2}). The generators of this manuscript (`paper/`) were added to the repository after that release; they read its result files unchanged and will be archived with the next release. The concept DOI for all versions is [{CONCEPT_DOI}](https://doi.org/{CONCEPT_DOI}). HPO {hpo_rel} and Phenopacket Store {ppkt} are not redistributed. They are downloaded by script and verified against recorded SHA-256 hashes. The local models are identified by Ollama tag and digest; their weights are not redistributed.

## Ethics statement

This study used only public data (the HPO and Phenopacket Store, which is curated from published, de-identified case reports) and synthetic text generated from them. No patient took part, and no patient record was accessed. [TODO: confirm with the venue whether a statement of ethics-committee exemption is required.] The work is research support and not a diagnostic tool.

## AI use statement

- **Claude Code** (Anthropic; model `{gen["model"]}`) wrote and tested the analysis code, ran the experiments and drafted the pre-specification files, the reports and this manuscript under the author's direction. Every number in the text is inserted by script from the result files. [TODO: the author confirms having read and revised the full text and takes responsibility for it.]
- **Vignettes.** The same model, through the Anthropic API, generated the synthetic vignettes from versioned prompts. Its outputs are stored and reused.
- **Register labels.** Independent Claude Code subagents running the same model produced the blind D2 labels; the author checked a sample.
- **Objects of study.** The local models (Qwen3-4B Instruct 2507 and Gemma 3 4B) are what was evaluated; they had no other role.

## Funding, competing interests and author contributions

[TODO: funding statement.] [TODO: competing interests.] [TODO: author contributions (CRediT), including the clinical co-author.]

## Acknowledgements

This product uses the Human Phenotype Ontology (version {hpo_rel}). Find out more at https://hpo.jax.org. We thank the HPO Consortium and the curators of Phenopacket Store.

## References

{{REFERENCES}}

## Supplementary material

**Supplementary Table S1.** All dated deviations in the three pre-specification files, in order. Source: `results/exp01/PREREG.md`, `results/exp02/PREREG.md`, `results/exp03/PREREG.md` (section "Desvios").

{deviations.table()}

**Supplementary Table S2.** The ten untranslated terms observed in the most Phenopacket Store cases. Source: `results/exp02/missing_terms.csv`.

{tables.exp02_missing()}

**Supplementary Table S3.** Experiment 3, post hoc: recall by top-level HPO branch, for branches with at least 50 gold terms; a term in several branches counts in each. Source: `results/exp03/by_branch.json`.

{tables.exp03_branches()}
"""
    md, order = number_citations(md, refs)
    ref_list = "\n".join(f"{i}. {reference(refs[k])}" for i, k in enumerate(order, 1))
    return md.replace("{REFERENCES}", ref_list)


def main() -> None:
    check_release_results()
    md = render()
    abstract = section(md, "## Abstract", "**Keywords:**")
    n_abs = len(abstract.split())
    if n_abs > ABSTRACT_MAX:
        raise SystemExit(f"abstract has {n_abs} words; the limit is {ABSTRACT_MAX}")
    main_text = section(md, "## Introduction", "## Data and code availability")
    OUT.write_text(md, encoding="utf-8")
    print(f"-> {OUT}")
    print(f"abstract: {n_abs} words (limit {ABSTRACT_MAX}, headings included)")
    print(
        f"main text (Introduction to Limitations, without headings, tables, figure captions and citation markers): {words(main_text)} words"
    )


if __name__ == "__main__":
    main()
