# Fenótipo-BR

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

Both experiments were pre-registered (`results/exp0*/PREREG.md`) before any result was read.
Post-hoc analyses are dated in each file's "Desvios" section. The full report, in Portuguese,
is `reports/piloto.md`.

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

# Reports
uv run python reports/build_piloto.py
uv run python reports/build_review.py          # add --translate to fill candidate_pt via the API
uv run python reports/build_readme.py
```

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
data/            downloads and caches (not committed)
```

## Limitations

- **Clean labels are not clinical notes.** Official labels are short and full of Greco-Latin cognates, so Exp 01 numbers are an optimistic ceiling for single-term normalization, not for free text.
- **Translated terms are not representative of untranslated ones.** Exp 01 can only score terms that have a Portuguese label, and the most frequent clinical terms are among the untranslated ones.
- **Contamination.** The embedding models may have seen HPO, and its translations, during pretraining.
- **European spelling.** Some official labels use European Portuguese spelling; its effect was not isolated.
- **Literature cases.** Phenopacket Store cases come from the English-language literature, and large cohorts weigh heavily in case-level averages.

## Data and licenses

- **Code:** MIT (`LICENSE`).
- **Raw data:** not redistributed; `python -m hpolab.data` downloads it.
- **Derived values:** `results/` and `reports/` contain values derived from HPO and Phenopacket Store, which remain under their sources' terms. See `NOTICE.md`.
  - **HPO:** custom HPO license. Acknowledge and cite the HPO Consortium, show the version when displaying HPO files, and do not alter HPO content or its logical relationships.
  - **Phenopacket Store:** BSD 3-Clause, © 2022 Monarch Initiative.
  - **Embedding models:** not redistributed; each is under its own model-card license.

## Citation

See `CITATION.cff`. Please also cite:

- Gargano MA, et al. *The Human Phenotype Ontology in 2024: phenotypes around the world.* Nucleic Acids Res 52(D1):D1333–D1346. https://doi.org/10.1093/nar/gkad1005
- Danis D, et al. *A corpus of GA4GH phenopackets: Case-level phenotyping for genomic diagnostics and discovery.* HGG Adv 6(1):100371 (2025). https://doi.org/10.1016/j.xhgg.2024.100371

Author: R. Walitte (Rondinelle Walitte Pedro de Jesus), ORCID [0009-0004-1776-2754](https://orcid.org/0009-0004-1776-2754).
