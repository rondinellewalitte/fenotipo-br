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
R1, R2 = ROOT / "results" / "exp01", ROOT / "results" / "exp02"
OUT = ROOT / "README.md"
# Zenodo: the concept DOI cites the project (resolves to the latest version); the version DOI
# pins the archived release whose results/ produced the numbers in the README.
CONCEPT_DOI = "10.5281/zenodo.23662825"
RELEASE = {"version": "0.1.0", "tag": "v0.1.0", "doi": "10.5281/zenodo.23662826", "year": 2026}
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


def check_release_results() -> None:
    """Stop if results/ changed since the release the README cites for its numbers."""
    diff = subprocess.run(
        ["git", "diff", "--quiet", RELEASE["tag"], "--", "results/"], cwd=ROOT, capture_output=True
    )
    if diff.returncode == 1:
        raise SystemExit(
            f"results/ changed since {RELEASE['tag']}; make a new release and update RELEASE."
        )
    if diff.returncode != 0:
        print(f"WARNING: could not compare results/ with tag {RELEASE['tag']}.")


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

Both experiments were pre-registered (`results/exp0*/PREREG.md`) before any result was read.
Post-hoc analyses are dated in each file's "Desvios" section. The full report, in Portuguese,
is `reports/piloto.md`.

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

# Reports
uv run python reports/build_piloto.py
uv run python reports/build_piloto_pdf.py      # PDF of the report; needs Chrome or Edge
uv run python reports/build_review.py          # add --translate to fill candidate_pt via the API
uv run python reports/build_readme.py
```

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

## How to cite

- **The project (all versions):** concept DOI [{CONCEPT_DOI}](https://doi.org/{CONCEPT_DOI}). It always resolves to the latest version.
- **To reproduce the numbers above:** version {RELEASE["version"]}, DOI [{RELEASE["doi"]}](https://doi.org/{RELEASE["doi"]}) (tag `{RELEASE["tag"]}`). Every number in this README comes from this release; papers should cite it.

> Walitte R. *Fenótipo-BR: mapping Brazilian Portuguese phenotype terms to the Human Phenotype Ontology* (v{RELEASE["version"]}). Zenodo; {RELEASE["year"]}. https://doi.org/{RELEASE["doi"]}

Machine-readable metadata: `CITATION.cff` (GitHub's "Cite this repository"). Please also cite the data sources:

- Gargano MA, et al. *The Human Phenotype Ontology in 2024: phenotypes around the world.* Nucleic Acids Res 52(D1):D1333–D1346. https://doi.org/10.1093/nar/gkad1005
- Danis D, et al. *A corpus of GA4GH phenopackets: Case-level phenotyping for genomic diagnostics and discovery.* HGG Adv 6(1):100371 (2025). https://doi.org/10.1016/j.xhgg.2024.100371

Author: R. Walitte (Rondinelle Walitte Pedro de Jesus), ORCID [0009-0004-1776-2754](https://orcid.org/0009-0004-1776-2754).
"""
    OUT.write_text(md, encoding="utf-8")
    print(f"-> {OUT} ({len(md.split())} words)")


if __name__ == "__main__":
    main()
