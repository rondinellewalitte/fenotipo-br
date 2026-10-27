# Fenótipo-BR

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23662825.svg)](https://doi.org/10.5281/zenodo.23662825)

Research lab measuring how well **Brazilian Portuguese** phenotype terms map to the
[Human Phenotype Ontology](https://hpo.jax.org) (HPO), with a focus on rare-disease
diagnosis research.

> **Research support only. This is not a clinical or diagnostic tool** and must not guide
> patient care (cf. ANVISA RDC 657/2022). Only public data are used; there is no patient data
> in this repository.

This product uses the Human Phenotype Ontology (version v2026-09-01). Find out more at https://hpo.jax.org.

## Questions

Phenotype-extraction tools are built for English, and only 36.0% of active HPO terms
(7,154 of 19,894) have an official Portuguese label. The pilot asks:

1. **Exp 01:** can a Portuguese term be mapped to the right HPO ID by searching **English** labels only?
2. **Exp 02:** how much of published rare-disease case descriptions already has an official Portuguese label, and which missing terms matter most?
3. **Exp 03:** from a Portuguese clinical text, does a small local LLM extract HPO terms as well **directly in Portuguese** as when it **translates to English first**?

All three experiments were pre-registered (`results/exp0*/PREREG.md`) before any result was read.
Deviations and post-hoc analyses are dated in each file's "Desvios" section. Reports, in
Portuguese: `reports/summary.md` (all three, two pages), `reports/exp03.md` (Exp 03 in full)
and `reports/piloto.md` (Exp 01–02, as released in v0.1.0).

## Main results

**Exp 01:** official PT labels of terms under HP:0000118 (n = 6,976) were searched against
an English-only index (label + exact synonyms of all active terms). Ties count against a hit.
Source: `results/exp01/metrics.json`.

| Method | top-1 (95% CI) | top-10 |
|---|---|---|
| bge-m3 | **81.2%** (80.2–82.1) | 95.0% |
| multilingual-e5-base (primary, `query:`/`query:`) | **72.4%** (71.3–73.4) | 91.6% |
| multilingual-e5-base (variant, `query:`/`passage:`) | **74.7%** (73.6–75.7) | 92.6% |
| Lexical baseline (rapidfuzz `token_sort_ratio`) | **54.1%** (52.9–55.3) | 73.0% |
| paraphrase-multilingual-mpnet-base-v2 | **52.0%** (50.9–53.2) | 78.9% |

- 4 of 8 pre-registered hypotheses held (`results/exp01/hypotheses.json`). The mpnet model did *worse* than the lexical baseline.
- Where the Portuguese spelling is far from the English one (surface similarity < 50, n = 3,139), bge-m3 reaches 73.6% top-1 against 39.8% for the lexical baseline (`results/exp01/surface_sim.json`).
- **Same lesion, wrong extremity** (post-hoc): 7.4% of bge-m3 top-1 errors swap hand and foot, for example "toe" for "finger". Most of these are far apart in the HPO hierarchy, so parent/child metrics miss them (`results/exp01/hierarchy_errors.json`).

**Exp 02:** Phenopacket Store 0.1.27, 10,374 cases and 92,068 observed phenotype annotations. Source: `results/exp02/metrics.json`.

- 38.3% of annotations have an official PT label, and only 5.8% of cases are fully covered.
- The most frequent untranslated terms are Global developmental delay (2,623 cases), Delayed speech and language development (1,765 cases), Intellectual disability (1,627 cases), Hypotonia (1,544 cases), Seizure (825 cases) (`results/exp02/missing_terms.csv`).
- Translating the top 50 missing terms raises annotation coverage by +22.3 pp on average out of sample (range +19.5 pp to +24.4 pp). The list was ranked on half of the genes and measured on the other half, over 20 splits (`results/exp02/out_of_sample.json`).

**Exp 03:** 300 synthetic Portuguese vignettes were written by an LLM (`claude-opus-5-5`, which never extracts) from Phenopacket Store 0.1.27 cases, one case per gene, with 2,466 observed terms as the gold standard and 959 excluded terms stated as negations. Two local 4B models (`qwen3:4b-instruct-2507-q4_K_M`, `gemma3:4b-it-q4_K_M`, Ollama, temperature 0) extracted the findings; `BAAI/bge-m3` retrieved 10 HPO candidates per finding and the LLM chose one or none. Arms: **A** extracts directly in Portuguese, **B** translates the note to English first, **C** is A with the official PT labels added to the index. Micro F1 per term, exact HPO ID. Source: `results/exp03/metrics.json`.

| Model | Arm | Precision | Recall | Micro F1 |
|---|---|---|---|---|
| Qwen3-4B Instruct 2507 | A, direct in PT | 0.482 | 0.577 | **0.525** |
| Qwen3-4B Instruct 2507 | B, translate first | 0.527 | 0.648 | **0.582** |
| Qwen3-4B Instruct 2507 | C, bilingual index | 0.472 | 0.572 | **0.517** |
| Gemma 3 4B | A, direct in PT | 0.451 | 0.386 | **0.416** |
| Gemma 3 4B | B, translate first | 0.489 | 0.424 | **0.454** |
| Gemma 3 4B | C, bilingual index | 0.430 | 0.368 | **0.396** |
| — | No-LLM baseline (bge-m3 top-1, τ = 0.70) | 0.372 | 0.293 | **0.328** |

2 of 6 pre-registered hypotheses held in both models (H3, H6); both LLM pipelines beat the no-LLM baseline (`results/exp03/hypotheses.json`). Main findings:

1. **Translating first beat extracting in Portuguese** (primary outcome). F1(A) − F1(B): Qwen3-4B −0.056 (97.5% CI −0.076 to −0.036); Gemma 3 4B −0.038 (97.5% CI −0.062 to −0.015). The pre-registered non-inferiority hypothesis (margin −0.03) failed and, as pre-specified, B's superiority is reported. The gap is largest where the Portuguese phrase is far from the English label (surface similarity < 50, n = 1,894; recall A − B: Qwen3-4B −0.083; Gemma 3 4B −0.056), not in near-copies of it, so it is not explained by recovering the generator's English source label. It may still be specific to LLM-written text (`results/exp03/metrics.json` → `comparisons`, `recall_by_stratum`).
2. **Adding the official Portuguese labels to the index did not help.** F1(C) − F1(A): Qwen3-4B −0.008 (95% CI −0.018 to 0.003); Gemma 3 4B −0.019 (95% CI −0.032 to −0.007). The vignettes used the official PT label for only 199 of 2,466 gold terms (`results/exp03/metrics.json` → `comparisons`, `recall_by_stratum.phrase_is_pt_label`).
3. **Retrieval is the bottleneck.** Even with a perfect choice, the right term was among the 10 candidates for only this share of gold terms in arm A: Qwen3-4B 0.736 (choice loses 0.159); Gemma 3 4B 0.537 (choice loses 0.151). With the generator's exact phrases and no LLM, bge-m3 put the right term in the top 10 for 74.7% of terms, against 95.0% for clean official labels in Exp 01 (cross-experiment, descriptive; `results/exp03/metrics.json` → `arms`, `oracle_spans_bge_m3_en_index`; `results/exp01/metrics.json`).
4. **Lay wording is the hardest.** Recall in arm A on terms written only in lay words (n = 645): Qwen3-4B 0.412; Gemma 3 4B 0.102; on terms written only technically: Qwen3-4B 0.633; Gemma 3 4B 0.504. For Gemma 3 4B, lay-only recall fell below the no-LLM baseline (0.153). Register labels came from a blind LLM labeler, checked by the author on 40 items (Cohen's kappa 0.85, 95% CI 0.70 to 0.96) (`results/exp03/metrics.json` → `register.d2`, `results/exp03/pilot/register_kappa.json`).

The Exp 03 report, in Portuguese, has the full tables, error categories and errors by HPO branch: `reports/exp03.md`.

## Reproduce

Python 3.12 with [uv](https://docs.astral.sh/uv/). Embeddings ran on an NVIDIA GeForce RTX 3050 6GB Laptop GPU (CUDA 13.0, fp32). Encoding plus ranking took about 8 min (`results/exp01/config.json`). `--device cpu` also works, only slower.

```bash
uv sync
uv run python -m hpolab.data --hpo-tag v2026-09-01 --ppkt-tag 0.1.27   # into data/raw/
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

- **Vignettes** need `ANTHROPIC_API_KEY` and stop at a cumulative cap of US$ 12 (`results/exp03/vignettes_config_full.json`). Stored outputs in `results/exp03/vignettes.jsonl` are reused, so a rerun of the same sets makes no API call.
- **Register labels (D2)** were made by independent Claude Code subagents, one per batch, following `prompts/exp03_register_manual_v1.md`. This is not a scripted step: `--make` writes the batches and `--merge` checks and joins the answers (`results/exp03/register_labels_full.meta.json`).
- **Extraction** needs [Ollama](https://ollama.com) 0.40.11 with the model tags and digests recorded in `results/exp03/config.json`. Every call is cached in `results/exp03/ollama_calls.jsonl.gz` and reused. The full run took 4.1 h on the same GPU.

The files used for these results, as recorded in `results/exp01/config.json` (full hashes in `data/raw/MANIFEST.json` after download):

| File | Release | sha256 |
|---|---|---|
| `hp.json` | v2026-09-01 | `a7b3a012e7b4007a…` |
| `phenotype.hpoa` | v2026-09-01 | `e89aa39c8f97bf5a…` |
| `hp-pt.babelon.tsv` | v2026-09-01 | `31f642ef8f695128…` |
| `all_phenopackets.zip` | 0.1.27 | `d0c70005bb09b870…` |

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
- **Exp 03 vignettes are synthetic.** An LLM wrote them from curated term lists: no typos, few abbreviations, lay and technical wording more regular than in real notes. Nothing here was validated on real clinical records.
- **Same model as generator and register labeler** (`claude-opus-5-5`). The labeler may recognize its own phrasing; the author's check covers part of this risk.
- **The human check was done by a non-clinician** (the author). A review by a geneticist is planned.
- **Contamination (Exp 03).** The cases come from published articles; the generator and the extractors may have seen those articles or the Phenopacket Store.
- **Two quantized small models.** Exp 03 results hold for the Q4_K_M versions of two 4B models on a 6 GB GPU.

## Data and licenses

- **Code:** MIT (`LICENSE`).
- **Raw data:** not redistributed; `python -m hpolab.data` downloads it.
- **Derived values:** `results/` and `reports/` contain values derived from HPO and Phenopacket Store, which remain under their sources' terms. See `NOTICE.md`.
  - **HPO:** custom HPO license. Acknowledge and cite the HPO Consortium, show the version when displaying HPO files, and do not alter HPO content or its logical relationships.
  - **Phenopacket Store:** BSD 3-Clause, © 2022 Monarch Initiative.
  - **Embedding models:** not redistributed; each is under its own model-card license.
  - **Local LLMs** (Exp 03, via Ollama): weights not redistributed; each model is under its own license.
- **Exp 03 vignettes** (`results/exp03/vignettes.jsonl`): synthetic text written by `claude-opus-5-5` through the Anthropic API from the HPO terms of published cases (English labels and definitions only). They describe no real patient.

## How to cite

- **The project (all versions):** concept DOI [10.5281/zenodo.23662825](https://doi.org/10.5281/zenodo.23662825). It always resolves to the latest version.
- **To reproduce the numbers above:**
  - Exp 01–02: version 0.1.0, DOI [10.5281/zenodo.23662826](https://doi.org/10.5281/zenodo.23662826) (tag `v0.1.0`). Their results are unchanged since that tag, which `reports/build_readme.py` checks.
  - Exp 03: version 0.2.0 (tag `v0.2.0`), DOI [10.5281/zenodo.23688007](https://doi.org/10.5281/zenodo.23688007).

> Walitte R. *Fenótipo-BR: mapping Brazilian Portuguese phenotype terms to the Human Phenotype Ontology* (v0.2.0). Zenodo; 2026. https://doi.org/10.5281/zenodo.23688007

Machine-readable metadata: `CITATION.cff` (GitHub's "Cite this repository"). Please also cite the data sources:

- Gargano MA, et al. *The Human Phenotype Ontology in 2024: phenotypes around the world.* Nucleic Acids Res 52(D1):D1333–D1346. https://doi.org/10.1093/nar/gkad1005
- Danis D, et al. *A corpus of GA4GH phenopackets: Case-level phenotyping for genomic diagnostics and discovery.* HGG Adv 6(1):100371 (2025). https://doi.org/10.1016/j.xhgg.2024.100371

Author: R. Walitte (Rondinelle Walitte Pedro de Jesus), ORCID [0009-0004-1776-2754](https://orcid.org/0009-0004-1776-2754).
