# Changelog

Each version is a git tag archived on Zenodo (concept DOI
[10.5281/zenodo.23662825](https://doi.org/10.5281/zenodo.23662825)). Results are not repeated
here: each entry points to the files that hold them.

## [0.2.1] (2026-10-28)

Statistical reporting fixes from an independent critical review. **No point estimate, interval
or hypothesis outcome changed**: re-running `exp03_extraction.py --set full --metrics-only`
leaves `hypotheses.json` identical apart from two added diagnostic fields, and every changed
value in `metrics.json` is a `p_boot_two_sided`.

Set the version DOI in `RELEASE` (`reports/build_readme.py`) once the tag is deposited; until
then the manuscript prints a TODO in its place.

### Fixed

- **Bootstrap p-values could be reported as exactly 0.** `casemetrics.paired_diff` now uses the
  `(k + 1) / (B + 1)` convention, so the smallest reportable value is `2 / (B + 1)`; 10 of the
  comparisons in `results/exp03/metrics.json` previously read `0.0`. No pre-registered decision
  uses these p-values, which the `bootstrap` block of `metrics.json` now states.

### Added

- **Post-hoc: surface similarity crossed with clinical register**
  (`experiments/exp03_strata_cross.py`, `results/exp03/strata_cross.json`), defined in
  `results/exp03/PREREG.md` before computing. The back-translation defence and the register
  analysis used strata that are correlated by construction, so they could not be told apart.
  Within technical-only terms alone, arm B keeps its advantage at low similarity and loses it at
  high similarity, so the gradient is not a by-product of lay wording.
- `casemetrics.recall_diff` now reports `n_items` and `n_distinct_boot` behind each recall
  difference, and flags `granular` when the resample support is too coarse to read as an
  interval. This is how the D1 "both" stratum (45 gold terms) shows that its limits are coarse.
- Table 1 of the manuscript gains a "Criteria" column: H4 and H5 are conjunctions in which the
  criterion about arm A held and the one about the comparator did not.
- Manuscript: the vignettes' information density, the baseline's fitted threshold, the
  intersection–union argument about H1's multiplicity adjustment, and the note that the
  percentile intervals are of a ratio of sums.
- README: that `--metrics-only` rewrites `errors.csv` and drops the `branches` column, that
  `vignettes.jsonl` keeps superseded attempts, and the `items_dropped_no_phrase` field name.

### Documented

- `near_miss_pairs` and `swap_pairs` match greedily, so the pair counts are a lower bound that
  depends on the HPO id order. The pre-registered metric is unchanged.

## [0.2.0] (2026-10-27)

Version DOI [10.5281/zenodo.23688007](https://doi.org/10.5281/zenodo.23688007).

### Added

- **Exp 03:** phenotype extraction from 300 synthetic Brazilian Portuguese vignettes with two
  local LLMs (Qwen3-4B Instruct 2507 and Gemma 3 4B, Q4_K_M, through Ollama) and bge-m3
  retrieval. Arms: A (direct in Portuguese), B (translate to English first), C (bilingual index)
  and a no-LLM baseline.
  - Pre-registration and dated deviations: `results/exp03/PREREG.md` (first commit `6fca3a2`,
    before any vignette).
  - Vignettes written by Claude Opus 5.5 through the Anthropic API under a cost cap, with an
    automatic leak check: `experiments/exp03_vignettes.py`, `results/exp03/vignettes.jsonl`.
  - Blind clinical-register labels (technical, lay, both), checked by the author on 40 items
    (`results/exp03/pilot/register_kappa.json`): `experiments/exp03_register_check.py`,
    `experiments/exp03_register_labels.py`.
  - Full-run results (`98c092d`): `results/exp03/metrics.json`, `hypotheses.json`,
    `errors.csv`. Pilot: `results/exp03/pilot/`.
  - Post-hoc errors by HPO branch, defined in the PREREG before computing (`603c403`):
    `results/exp03/by_branch.json`.
  - Report, in Portuguese: `reports/exp03.md` (`reports/build_exp03.py`).
- `reports/summary.md`: two-page summary of Exp 01–03, in Portuguese (`reports/build_summary.py`).
- `CHANGELOG.md`.

### Changed

- README: Exp 03 section and limitations. The release check now compares Exp 01–02 results with
  v0.1.0 and all of `results/` with v0.2.0 once that tag exists.
- Version 0.2.0 in `pyproject.toml`, `CITATION.cff` and `.zenodo.json`; `NOTICE.md` covers the
  local LLMs and the synthetic vignettes.
- Zenodo DOIs in the README, `CITATION.cff` and the e-mail draft (`10109e1`, `be2d2f2`).

### Unchanged

- Exp 01 and Exp 02 results; `reports/piloto.md` and `reports/piloto.pdf` still document
  v0.1.0.

## [0.1.0] (2026-10-26)

Version DOI [10.5281/zenodo.23662826](https://doi.org/10.5281/zenodo.23662826).

### Added

- **Exp 01:** normalization of official Portuguese HPO labels against an English-only index,
  with three embedding models and a lexical baseline: `results/exp01/` (results `847a27e`).
- **Exp 02:** coverage of the official Portuguese translation in Phenopacket Store cases, and
  which missing terms matter most: `results/exp02/` (code `f93b18d`).
- Pilot report in Portuguese, `reports/piloto.md`, and its PDF.
- Review package for clinicians (`reports/review/`) and the Rede RARAS e-mail draft (not sent).
- MIT license, `NOTICE.md`, `CITATION.cff` and `.zenodo.json`.
