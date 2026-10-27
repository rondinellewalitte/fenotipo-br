# Changelog

Each version is a git tag archived on Zenodo (concept DOI
[10.5281/zenodo.23662825](https://doi.org/10.5281/zenodo.23662825)). Results are not repeated
here: each entry points to the files that hold them.

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
