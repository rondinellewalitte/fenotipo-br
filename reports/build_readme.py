"""Render the repository README.md (English) from the result files. Every number comes from
a file under results/ (CLAUDE.md, rule 2).

    uv run python reports/build_readme.py
"""
# ruff: noqa: E501  (Markdown template below is prose)

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R1, R2, R3 = ROOT / "results" / "exp01", ROOT / "results" / "exp02", ROOT / "results" / "exp03"
OUT = ROOT / "README.md"
# Zenodo: the concept DOI cites the project (resolves to the latest version); a version DOI
# pins the archived release whose results/ produced a part of the README. Exp 01-02 numbers
# come from v0.1.0, Exp 03 numbers from RELEASE. Zenodo mints a version DOI only when the
# GitHub release is published: until then RELEASE["doi"] is None and the README says so.
CONCEPT_DOI = "10.5281/zenodo.23662825"
V010 = {"version": "0.1.0", "tag": "v0.1.0", "doi": "10.5281/zenodo.23662826", "year": 2026}
V010_RESULTS = ("results/", ":(exclude)results/exp03")
RELEASE = {"version": "0.2.0", "tag": "v0.2.0", "doi": "10.5281/zenodo.23688007", "year": 2026}
MODELS = {"qwen3-4b": "Qwen3-4B Instruct 2507", "gemma3-4b": "Gemma 3 4B"}
SHORT = {"qwen3-4b": "Qwen3-4B", "gemma3-4b": "Gemma 3 4B"}
ARMS = {"A": "A, direct in PT", "B": "B, translate first", "C": "C, bilingual index"}
ROWS = [
    ("bge-m3", "bge-m3"),
    ("e5-base", "multilingual-e5-base (primary, `query:`/`query:`)"),
    ("e5-base_qp", "multilingual-e5-base (variant, `query:`/`passage:`)"),
    ("lexical_token_sort", "Lexical baseline (rapidfuzz `token_sort_ratio`)"),
    ("mpnet-multi", "paraphrase-multilingual-mpnet-base-v2"),
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


def pp(x: float, d: int = 1) -> str:
    return f"{'+' if x >= 0 else '−'}{abs(x) * 100:.{d}f} pp"


def ci(pair) -> str:
    return f"{pair[0] * 100:.1f}–{pair[1] * 100:.1f}"


def dec(x: float, d: int = 3) -> str:
    return f"{x:.{d}f}".replace("-", "−")


def sgn(x: float, d: int = 3) -> str:
    return ("+" if x >= 0 else "") + dec(x, d)


def dci(pair) -> str:
    return f"{dec(pair[0])} to {dec(pair[1])}"


def tag_exists(tag: str) -> bool:
    ref = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=ROOT, capture_output=True
    )
    return ref.returncode == 0


def changed_since(tag: str, *paths: str) -> bool:
    diff = subprocess.run(
        ["git", "diff", "--quiet", tag, "--", *paths], cwd=ROOT, capture_output=True
    )
    if diff.returncode not in (0, 1):
        raise SystemExit(f"could not compare {' '.join(paths)} with tag {tag}.")
    return diff.returncode == 1


def check_release_results() -> None:
    """Stop if the results a cited release produced changed since its tag. Exp 01-02 are
    checked against v0.1.0 always; all of results/ against RELEASE once its tag exists."""
    if changed_since(V010["tag"], *V010_RESULTS):
        raise SystemExit(
            f"Exp 01-02 results changed since {V010['tag']}, which the README cites for them."
        )
    if not tag_exists(RELEASE["tag"]):
        print(f"NOTE: tag {RELEASE['tag']} does not exist yet; results/ not checked against it.")
    elif changed_since(RELEASE["tag"], "results/"):
        raise SystemExit(
            f"results/ changed since {RELEASE['tag']}; make a new release and update RELEASE."
        )


def exp03_section() -> tuple[str, str]:
    """(Exp 03 results section, Exp 03 limitations), every number from results/exp03."""
    m, hyp = load(R3 / "metrics.json"), load(R3 / "hypotheses.json")
    c, vcfg = load(R3 / "config.json"), load(R3 / "vignettes_config_full.json")
    kappa = load(R3 / "pilot" / "register_kappa.json")
    exp01_top10 = load(R1 / "metrics.json")["results"]["bge-m3"]["exact"]["main"]["top10"]
    arms, comp, d2 = m["arms"], m["comparisons"], m["register"]["d2"]
    base = arms["none/baseline"]
    gen = vcfg["generator"]["model"]
    hh = hyp["hypotheses"]
    held = [name.split("_")[0] for name, h in hh.items() if h["confirmed_both_models"]]

    table = ["| Model | Arm | Precision | Recall | Micro F1 |", "|---|---|---|---|---|"]
    for k, model in MODELS.items():
        for a, label in ARMS.items():
            s = arms[f"{k}/{a}"]["micro"]
            table.append(
                f"| {model} | {label} | {dec(s['precision'])} | {dec(s['recall'])} | **{dec(s['f1'])}** |"
            )
    s = base["micro"]
    table.append(
        f"| — | No-LLM baseline (bge-m3 top-1, τ = {m['baseline_tau']:.2f}) | {dec(s['precision'])} "
        f"| {dec(s['recall'])} | **{dec(s['f1'])}** |"
    )

    def per_model(fn) -> str:
        return "; ".join(f"{SHORT[k]} {fn(k)}" for k in MODELS)

    ab = per_model(
        lambda k: f"{sgn(comp[k]['A-B']['diff'])} (97.5% CI {dci(comp[k]['A-B']['ci97_5'])})"
    )
    ca = per_model(
        lambda k: f"{sgn(comp[k]['C-A']['diff'])} (95% CI {dci(comp[k]['C-A']['ci95'])})"
    )
    far = per_model(
        lambda k: sgn(
            arms[f"{k}/A"]["recall_by_stratum"]["sim_bin"]["<50"]["recall"]
            - arms[f"{k}/B"]["recall_by_stratum"]["sim_bin"]["<50"]["recall"]
        )
    )
    n_far = arms["qwen3-4b/A"]["recall_by_stratum"]["sim_bin"]["<50"]["n"]
    pt_phrase = arms["qwen3-4b/A"]["recall_by_stratum"]["phrase_is_pt_label"]["True"]["n"]
    ceil = per_model(
        lambda k: (
            f"{dec(arms[f'{k}/A']['retrieval_ceiling_recall'])} (choice loses {dec(arms[f'{k}/A']['selection_loss'])})"
        )
    )
    lay = per_model(lambda k: dec(d2[f"{k}/A"]["recall"]["lay"]["recall"]))
    tech = per_model(lambda k: dec(d2[f"{k}/A"]["recall"]["technical"]["recall"]))
    oracle = m["oracle_spans_bge_m3_en_index"]
    n_lay = d2["qwen3-4b/A"]["recall"]["lay"]["n"]
    base_lay = d2["none/baseline"]["recall"]["lay"]["recall"]
    below = [SHORT[k] for k in MODELS if d2[f"{k}/A"]["recall"]["lay"]["recall"] < base_lay]
    below_text = (
        f" For {' and '.join(below)}, lay-only recall fell below the no-LLM baseline ({dec(base_lay)})."
        if below
        else ""
    )
    # The wording below states these directions; stop if the results no longer support them.
    for k in MODELS:
        sim = {
            b: arms[f"{k}/A"]["recall_by_stratum"]["sim_bin"][b]["recall"]
            - arms[f"{k}/B"]["recall_by_stratum"]["sim_bin"][b]["recall"]
            for b in ("<50", "50-80", ">=80")
        }
        assert comp[k]["A-B"]["ci97_5"][1] < 0, "finding 1 says B beat A"
        assert sim["<50"] == min(sim.values()), "finding 1 says the gap is largest at < 50"
        assert comp[k]["C-A"]["ci95"][0] <= 0, "finding 2 says C did not help"
        assert not hh["H5_ceiling_ge_0.75_selection_loss_ge_0.10"]["per_model"][k]["confirmed"]
        assert hh["H6_lay_harder_than_technical"]["per_model"][k]["confirmed"]

    section = f"""**Exp 03:** {c["n_cases"]} synthetic Portuguese vignettes were written by an LLM (`{gen}`, which never extracts) from Phenopacket Store {c["phenopacket_store_release"]} cases, one case per gene, with {m["n_gold_terms"]:,} observed terms as the gold standard and {m["n_negated_terms"]:,} excluded terms stated as negations. Two local 4B models ({", ".join(f"`{v['tag']}`" for v in c["ollama"]["models"].values())}, Ollama, temperature 0) extracted the findings; `{c["retrieval"]["model"]}` retrieved 10 HPO candidates per finding and the LLM chose one or none. Arms: **A** extracts directly in Portuguese, **B** translates the note to English first, **C** is A with the official PT labels added to the index. Micro F1 per term, exact HPO ID. Source: `results/exp03/metrics.json`.

{chr(10).join(table)}

{len(held)} of {len(hh)} pre-registered hypotheses held in both models ({", ".join(held)}); both LLM pipelines beat the no-LLM baseline (`results/exp03/hypotheses.json`). Main findings:

1. **Translating first beat extracting in Portuguese** (primary outcome). F1(A) − F1(B): {ab}. The pre-registered non-inferiority hypothesis (margin −0.03) failed and, as pre-specified, B's superiority is reported. The gap is largest where the Portuguese phrase is far from the English label (surface similarity < 50, n = {n_far:,}; recall A − B: {far}), not in near-copies of it, so it is not explained by recovering the generator's English source label. It may still be specific to LLM-written text (`results/exp03/metrics.json` → `comparisons`, `recall_by_stratum`).
2. **Adding the official Portuguese labels to the index did not help.** F1(C) − F1(A): {ca}. The vignettes used the official PT label for only {pt_phrase:,} of {m["n_gold_terms"]:,} gold terms (`results/exp03/metrics.json` → `comparisons`, `recall_by_stratum.phrase_is_pt_label`).
3. **Retrieval is the bottleneck.** Even with a perfect choice, the right term was among the 10 candidates for only this share of gold terms in arm A: {ceil}. With the generator's exact phrases and no LLM, bge-m3 put the right term in the top 10 for {pct(oracle["top10"])} of terms, against {pct(exp01_top10)} for clean official labels in Exp 01 (cross-experiment, descriptive; `results/exp03/metrics.json` → `arms`, `oracle_spans_bge_m3_en_index`; `results/exp01/metrics.json`).
4. **Lay wording is the hardest.** Recall in arm A on terms written only in lay words (n = {n_lay}): {lay}; on terms written only technically: {tech}.{below_text} Register labels came from a blind LLM labeler, checked by the author on 40 items (Cohen's kappa {kappa["cohen_kappa"]:.2f}, 95% CI {kappa["cohen_kappa_ci95"][0]:.2f} to {kappa["cohen_kappa_ci95"][1]:.2f}) (`results/exp03/metrics.json` → `register.d2`, `results/exp03/pilot/register_kappa.json`).

The Exp 03 report, in Portuguese, has the full tables, error categories and errors by HPO branch: `reports/exp03.md`."""

    limits = f"""- **Exp 03 vignettes are synthetic.** An LLM wrote them from curated term lists: no typos, few abbreviations, lay and technical wording more regular than in real notes. Nothing here was validated on real clinical records.
- **Same model as generator and register labeler** (`{gen}`). The labeler may recognize its own phrasing; the author's check covers part of this risk.
- **The human check was done by a non-clinician** (the author). A review by a geneticist is planned.
- **Contamination (Exp 03).** The cases come from published articles; the generator and the extractors may have seen those articles or the Phenopacket Store.
- **Two quantized small models.** Exp 03 results hold for the Q4_K_M versions of two 4B models on a 6 GB GPU."""
    return section, limits


def main() -> None:
    check_release_results()
    hs = load(ROOT / "results" / "hpo_summary.json")
    c1, m1, hyp = load(R1 / "config.json"), load(R1 / "metrics.json"), load(R1 / "hypotheses.json")
    surf, hier = load(R1 / "surface_sim.json"), load(R1 / "hierarchy_errors.json")
    c2, m2, oos = (
        load(R2 / "config.json"),
        load(R2 / "metrics.json"),
        load(R2 / "out_of_sample.json"),
    )
    missing = pd.read_csv(R2 / "missing_terms.csv")

    main1 = {m: m1["results"][m]["exact"]["main"] for m, _ in ROWS}
    n_main = main1["bge-m3"]["n"]
    s50 = {m: surf["by_method"][m]["<50"] for m in ("bge-m3", "lexical_token_sort")}
    swaps = hier["by_method"]["bge-m3"]["hand_foot_swaps"]
    cov = m2["coverage"]
    g50 = oos["gene_split"]["seeds_summary_annotation_coverage_gain"]["top50"]["oos_gain"]
    n_seeds = len(oos["gene_split"]["seeds"])
    total_s = sum(c1["timings_seconds"].values())
    gpu = c1["encode_device"]
    exp03, exp03_limits = exp03_section()
    c3 = load(R3 / "config.json")
    cap = load(R3 / "vignettes_config_full.json")["generator"]["budget_usd_cumulative"]
    v2_doi = (
        f", DOI [{RELEASE['doi']}](https://doi.org/{RELEASE['doi']})"
        if RELEASE["doi"]
        else ". Zenodo assigns its version DOI when the release is published; until then, cite the concept DOI"
    )
    cite_doi = RELEASE["doi"] or CONCEPT_DOI

    table = ["| Method | top-1 (95% CI) | top-10 |", "|---|---|---|"]
    for key, label in ROWS:
        s = main1[key]
        table.append(
            f"| {label} | **{pct(s['top1'])}** ({ci(s['top1_ci95'])}) | {pct(s['top10'])} |"
        )
    top5 = ", ".join(f"{r.en_label} ({r.n_cases:,} cases)" for r in missing.head(5).itertuples())
    data_rows = ["| File | Release | sha256 |", "|---|---|---|"]
    for name, e in c1["data"].items():
        data_rows.append(f"| `{name}` | {e['release_tag']} | `{e['sha256'][:16]}…` |")

    md = f"""# Fenótipo-BR

[![DOI](https://zenodo.org/badge/DOI/{CONCEPT_DOI}.svg)](https://doi.org/{CONCEPT_DOI})

Research lab measuring how well **Brazilian Portuguese** phenotype terms map to the
[Human Phenotype Ontology](https://hpo.jax.org) (HPO), with a focus on rare-disease
diagnosis research.

> **Research support only. This is not a clinical or diagnostic tool** and must not guide
> patient care (cf. ANVISA RDC 657/2022). Only public data are used; there is no patient data
> in this repository.

This product uses the Human Phenotype Ontology (version {c1["hpo_release"]}). Find out more at https://hpo.jax.org.

## Questions

Phenotype-extraction tools are built for English, and only {pct(hs["pt_coverage_active"])} of active HPO terms
({hs["pt_labels_active"]:,} of {hs["active_terms"]:,}) have an official Portuguese label. The pilot asks:

1. **Exp 01:** can a Portuguese term be mapped to the right HPO ID by searching **English** labels only?
2. **Exp 02:** how much of published rare-disease case descriptions already has an official Portuguese label, and which missing terms matter most?
3. **Exp 03:** from a Portuguese clinical text, does a small local LLM extract HPO terms as well **directly in Portuguese** as when it **translates to English first**?

All three experiments were pre-registered (`results/exp0*/PREREG.md`) before any result was read.
Deviations and post-hoc analyses are dated in each file's "Desvios" section. Reports, in
Portuguese: `reports/summary.md` (all three, two pages), `reports/exp03.md` (Exp 03 in full)
and `reports/piloto.md` (Exp 01–02, as released in v0.1.0).

## Main results

**Exp 01:** official PT labels of terms under HP:0000118 (n = {n_main:,}) were searched against
an English-only index (label + exact synonyms of all active terms). Ties count against a hit.
Source: `results/exp01/metrics.json`.

{chr(10).join(table)}

- {sum(hyp["summary"].values())} of {len(hyp["summary"])} pre-registered hypotheses held (`results/exp01/hypotheses.json`). The mpnet model did *worse* than the lexical baseline.
- Where the Portuguese spelling is far from the English one (surface similarity < 50, n = {s50["bge-m3"]["n"]:,}), bge-m3 reaches {pct(s50["bge-m3"]["top1"])} top-1 against {pct(s50["lexical_token_sort"]["top1"])} for the lexical baseline (`results/exp01/surface_sim.json`).
- **Same lesion, wrong extremity** (post-hoc): {pct(swaps["share_of_errors"])} of bge-m3 top-1 errors swap hand and foot, for example "toe" for "finger". Most of these are far apart in the HPO hierarchy, so parent/child metrics miss them (`results/exp01/hierarchy_errors.json`).

**Exp 02:** Phenopacket Store {c2["phenopacket_store_release"]}, {cov["n_cases"]:,} cases and {cov["n_annotations"]:,} observed phenotype annotations. Source: `results/exp02/metrics.json`.

- {pct(cov["annotation_coverage"])} of annotations have an official PT label, and only {pct(cov["pct_cases_full"])} of cases are fully covered.
- The most frequent untranslated terms are {top5} (`results/exp02/missing_terms.csv`).
- Translating the top 50 missing terms raises annotation coverage by {pp(g50["mean"])} on average out of sample (range {pp(g50["min"])} to {pp(g50["max"])}). The list was ranked on half of the genes and measured on the other half, over {n_seeds} splits (`results/exp02/out_of_sample.json`).

{exp03}

## Reproduce

Python 3.12 with [uv](https://docs.astral.sh/uv/). Embeddings ran on an {gpu["gpu"]} (CUDA {gpu["torch_cuda"]}, fp32). Encoding plus ranking took about {total_s / 60:.0f} min (`results/exp01/config.json`). `--device cpu` also works, only slower.

```bash
uv sync
uv run python -m hpolab.data --hpo-tag {c1["hpo_release"]} --ppkt-tag {c2["phenopacket_store_release"]}   # into data/raw/
uv run python -m hpolab.hpo --out results/hpo_summary.json
uv run pytest

# Exp 01 (the full run refuses to start on a dirty git tree: commit first)
uv run python experiments/exp01_normalization.py --pilot   # optional time estimate
uv run python experiments/exp01_normalization.py
uv run python experiments/exp01_hypotheses.py
uv run python experiments/exp01_analysis.py

# Exp 02
uv run python experiments/exp02_coverage.py
uv run python experiments/exp02_expectations.py
uv run python experiments/exp02_checks.py
uv run python experiments/exp01_weighted.py   # needs Exp 02 inputs

# Exp 03 (see the notes below)
uv run python experiments/exp03_vignettes.py --set pilot
uv run python experiments/exp03_vignettes.py --set full
uv run python experiments/exp03_register_labels.py --make    # batches for the D2 labelers
uv run python experiments/exp03_register_labels.py --merge   # after the batches are labeled
uv run python experiments/exp03_extraction.py --set pilot --freeze
uv run python experiments/exp03_extraction.py --set full
uv run python experiments/exp03_by_branch.py

# Reports
uv run python reports/build_piloto.py
uv run python reports/build_piloto_pdf.py      # PDF of the report; needs Chrome or Edge
uv run python reports/build_review.py          # add --translate to fill candidate_pt via the API
uv run python reports/build_exp03.py
uv run python reports/build_summary.py
uv run python reports/build_readme.py

# Manuscript draft (needs the paper dependency group)
uv run python paper/refs.py --fetch           # re-checks the references in Crossref and PubMed
uv run --group paper python paper/build_manuscript.py
```

Exp 03 notes:

- **Vignettes** need `ANTHROPIC_API_KEY` and stop at a cumulative cap of US$ {cap:.0f} (`results/exp03/vignettes_config_full.json`). Stored outputs in `results/exp03/vignettes.jsonl` are reused, so a rerun of the same sets makes no API call.
- **Register labels (D2)** were made by independent Claude Code subagents, one per batch, following `prompts/exp03_register_manual_v1.md`. This is not a scripted step: `--make` writes the batches and `--merge` checks and joins the answers (`results/exp03/register_labels_full.meta.json`).
- **Extraction** needs [Ollama](https://ollama.com) {c3["ollama"]["ollama_version"]} with the model tags and digests recorded in `results/exp03/config.json`. Every call is cached in `results/exp03/ollama_calls.jsonl.gz` and reused. The full run took {c3["wall_seconds"] / 3600:.1f} h on the same GPU.

The files used for these results, as recorded in `results/exp01/config.json` (full hashes in `data/raw/MANIFEST.json` after download):

{chr(10).join(data_rows)}

The optional LLM step (`reports/build_review.py --translate`) needs `ANTHROPIC_API_KEY`. It is
capped at US$ 2 and logs every call. The API no longer accepts sampling parameters, so outputs
are stored and reused instead of being regenerated.

## Layout

```
src/hpolab/      reusable code (data, hpo, retrieval, embed, metrics, llm, provenance)
experiments/     one script per experiment
results/expNN/   generated outputs: config.json, metrics.json, PREREG.md, ...
reports/         Portuguese report, review package for clinicians, document generators
prompts/         versioned LLM prompts
paper/           manuscript draft (English), its tables, figures and checked references
data/            downloads and caches (not committed)
```

## Limitations

- **Clean labels are not clinical notes.** Official labels are short and full of Greco-Latin cognates, so Exp 01 numbers are an optimistic ceiling for single-term normalization, not for free text.
- **Translated terms are not representative of untranslated ones.** Exp 01 can only score terms that have a Portuguese label, and the most frequent clinical terms are among the untranslated ones.
- **Contamination.** The embedding models may have seen HPO, and its translations, during pretraining.
- **European spelling.** Some official labels use European Portuguese spelling; its effect was not isolated.
- **Literature cases.** Phenopacket Store cases come from the English-language literature, and large cohorts weigh heavily in case-level averages.
{exp03_limits}

## Data and licenses

- **Code:** MIT (`LICENSE`).
- **Raw data:** not redistributed; `python -m hpolab.data` downloads it.
- **Derived values:** `results/` and `reports/` contain values derived from HPO and Phenopacket Store, which remain under their sources' terms. See `NOTICE.md`.
  - **HPO:** custom HPO license. Acknowledge and cite the HPO Consortium, show the version when displaying HPO files, and do not alter HPO content or its logical relationships.
  - **Phenopacket Store:** BSD 3-Clause, © 2022 Monarch Initiative.
  - **Embedding models:** not redistributed; each is under its own model-card license.
  - **Local LLMs** (Exp 03, via Ollama): weights not redistributed; each model is under its own license.
- **Exp 03 vignettes** (`results/exp03/vignettes.jsonl`): synthetic text written by `{load(R3 / "vignettes_config_full.json")["generator"]["model"]}` through the Anthropic API from the HPO terms of published cases (English labels and definitions only). They describe no real patient.

## How to cite

- **The project (all versions):** concept DOI [{CONCEPT_DOI}](https://doi.org/{CONCEPT_DOI}). It always resolves to the latest version.
- **To reproduce the numbers above:**
  - Exp 01–02: version {V010["version"]}, DOI [{V010["doi"]}](https://doi.org/{V010["doi"]}) (tag `{V010["tag"]}`). Their results are unchanged since that tag, which `reports/build_readme.py` checks.
  - Exp 03: version {RELEASE["version"]} (tag `{RELEASE["tag"]}`){v2_doi}.

> Walitte R. *Fenótipo-BR: mapping Brazilian Portuguese phenotype terms to the Human Phenotype Ontology* (v{RELEASE["version"]}). Zenodo; {RELEASE["year"]}. https://doi.org/{cite_doi}

Machine-readable metadata: `CITATION.cff` (GitHub's "Cite this repository"). Please also cite the data sources:

- Gargano MA, et al. *The Human Phenotype Ontology in 2024: phenotypes around the world.* Nucleic Acids Res 52(D1):D1333–D1346. https://doi.org/10.1093/nar/gkad1005
- Danis D, et al. *A corpus of GA4GH phenopackets: Case-level phenotyping for genomic diagnostics and discovery.* HGG Adv 6(1):100371 (2025). https://doi.org/10.1016/j.xhgg.2024.100371

Author: R. Walitte (Rondinelle Walitte Pedro de Jesus), ORCID [0009-0004-1776-2754](https://orcid.org/0009-0004-1776-2754).
"""
    OUT.write_text(md, encoding="utf-8")
    print(f"-> {OUT} ({len(md.split())} words)")


if __name__ == "__main__":
    main()
