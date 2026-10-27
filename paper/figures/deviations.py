"""Supplementary Table S1: every dated deviation in the three pre-specification files.

The entries are parsed from the "Desvios" section of results/exp0N/PREREG.md (top-level bullets
only) and matched 1:1 to the English summaries below; the build stops if a PREREG gains,
loses or renames an entry without a summary here. The summaries hold no result numbers.

    uv run python paper/figures/deviations.py      # prints the table
"""
# ruff: noqa: E501  (table text and English summaries are prose; long lines are intended)

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from figures.common import R1, R2, R3, src  # noqa: E402

MONTHS = {"out": "Oct", "nov": "Nov", "set": "Sep"}
PRE = "Amendment before any data"
PILOT = "Amendment after pilot vignettes, before any extraction"
PRE_EXT = "Amendment before any extraction"
LIMIT = "Recorded limitation"
POST = "Post-hoc analysis"
# (experiment, start of the bold Portuguese title, type, English summary)
SUMMARIES = [
    ("01", "25/out/2026, tamanho dos subconjuntos", "Correction before results",
     "The sizes of the identical and non-identical cognate subsets quoted in the plan came from an exploration with a different text normalization; the implemented definition, committed before results, gives slightly different sizes. Definitions and criteria unchanged."),
    ("01", "25/out/2026, análise por `surface_sim`", "Detail of a pre-specified exploratory analysis",
     "Surface-similarity bands fixed before reading the output; the identical band uses the identity flag, because the stored similarity is rounded (noticed on the first run, fixed before interpretation)."),
    ("01", "25/out/2026, métrica secundária pós-hoc de irmãos", POST,
     "Sibling-miss metric and a descriptive classification of top-1 errors (parent/child, sibling, other ancestor/descendant, close relative, distant), requested after reading errors in the limb branch; defined before computing."),
    ("01", "25/out/2026, contagem exploratória pós-hoc de trocas", POST,
     "Count of hand/foot swaps among top-1 errors (regular expression on the English labels), defined after seeing examples; descriptive only."),
    ("01", "25/out/2026, top-k ponderado por frequência clínica", POST,
     "Top-k accuracy weighted by the number of Phenopacket Store cases (and, as a variant, of annotated diseases) per term, with a bootstrap 95% CI."),
    ("02", "25/out/2026, tolerância da E5", "Post-hoc criterion",
     "The numeric tolerance of expectation E5 was fixed after the values were seen; the conclusion does not depend on it."),
    ("02", "25/out/2026, checagem pontual fora do pipeline", "Note (no reported number depends on it)",
     "Spot check of the HPO file of terms marked as not translated, to confirm that very frequent terms lack a Portuguese label."),
    ("02", "25/out/2026, checagens pós-hoc", POST,
     "Out-of-sample coverage gain (term list ranked on half of the genes, measured on the other half; seed 42 primary, seeds 0–19 for spread), a list ranked by phenotype.hpoa, and coverage by term generality; defined before computing."),
    ("03", "Gerador, trava de custo e regra do H1", PRE,
     "Generator model kept for pilot and full set; cumulative API cost cap raised; Batches API not used; H1 decision rule (97.5% CI, margin −0.03) confirmed."),
    ("03", "Termos sem trecho na vinheta", PRE,
     "An item without a verbatim phrase in the vignette leaves that case's gold standard (or negation list) instead of failing the vignette; if extracted it counts as a false positive in its own category."),
    ("03", "Exemplos do prompt de extração", PRE,
     "Few-shot examples of the extraction prompt replaced by terms absent from all drawn cases (and from their direct parents and children), with an automatic clash check."),
    ("03", "Exemplo de negação no prompt do gerador", PRE,
     "The negation example of the generator prompt reduced to its form, because it named a frequent term."),
    ("03", "Travas de código", PRE,
     "Code locks: no API call with uncommitted code or prompts; the generator prompt is frozen with the extraction prompts."),
    ("03", "Regra de vazamento por rótulo inglês", PILOT,
     "Leak rule: an English label counts as a leak only if it is not part of an official Portuguese label and contains a spelling impossible in Portuguese; Greco-Latin cognates had been excluding cases systematically. Replaced pilot cases returned to the sample."),
    ("03", "Prompt do gerador v2", PILOT,
     "Generator prompt v2: a lay description is never labeled with its technical term, and a finding is never decomposed into other findings; pilot vignettes regenerated."),
    ("03", "Trava de custo: US$ 12", PILOT,
     "Cumulative API cost cap raised again, so that the cap could not stop the full set midway."),
    ("03", "Revisão humana", PILOT,
     "Human-review sampling may favor chosen HPO branches (skin, behavior); used for reading only."),
    ("03", "Gerador v2 congelado", PRE_EXT,
     "Generator v2 frozen for the full set; a finding told in lay words and later named in the examination section was kept, as in real notes."),
    ("03", "Os prompts dos extratores são os mesmos", PRE_EXT,
     "Extractor prompts are identical for both models; no per-model tuning."),
    ("03", "Estratos de registro de cada item do gabarito", PRE_EXT,
     "Register strata defined: D2, clinical (technical only, lay only, both; blind LLM labeler; primary) and D1, literal (deterministic rule; secondary)."),
    ("03", "Conferência humana do D2", PRE_EXT,
     "Human check of D2 on 40 stratified pilot items, blind to the labeler; Cohen's kappa below 0.6 would make D2 results exploratory only."),
    ("03", "Hipótese e expectativas sobre o D2", PRE_EXT,
     "Hypothesis H6 (technical-only recall above lay-only recall) and expectations E6–E8 added."),
    ("03", "Limitação registrada", LIMIT,
     "The human checker of D2 is not a clinician."),
    ("03", "Resultado da conferência humana", "Result of a pre-specified check, before any extraction metric",
     "Kappa above the pre-specified threshold, so D2 is confirmatory (value in the Methods)."),
    ("03", "Limitação do D2: viés do rotulador", LIMIT,
     "The labeler tends to mark borderline phrases as 'both'; this shifts absolute stratum levels, not comparisons between arms."),
    ("03", '"oo" deixa de marcar grafia impossível', "Amendment after the 300 vignettes, before labeling and extraction",
     "'oo' removed from the impossible-spelling markers, because a term spelled identically in Portuguese (Oligozoospermia) was being rejected."),
    ("03", "Reavaliação das tentativas gravadas", "Amendment after the 300 vignettes, before labeling and extraction",
     "Stored failing attempts re-checked with the corrected rule, without new API calls; the final set returned exactly to the 300 drawn cases."),
    ("03", "Limitação: o gerador das vinhetas e o rotulador", LIMIT,
     "The vignette generator and the D2 labeler are the same model."),
    ("03", "Erros por ramo do HPO", POST,
     "Errors by top-level HPO branch, descriptive; defined before computing."),
    ("03", "Similaridade de superfície cruzada com registro", POST,
     "Surface-similarity bands crossed with the clinical register, because the two are correlated by construction and were reported only separately, so the back-translation reading could not be told apart from the register reading; descriptive, defined before computing."),
]  # fmt: skip
DATE = re.compile(r"(\d{1,2})/(\w{3})/(\d{4})")


def english_date(text: str) -> str:
    d, m, y = DATE.search(text).groups()
    return f"{int(d)} {MONTHS[m]} {y}"


def parse(prereg: Path) -> list[dict]:
    """Top-level bold bullets of the Desvios section, with the date of their (sub)section."""
    lines = prereg.read_text(encoding="utf-8").splitlines()
    start = lines.index("## Desvios")
    date, out = None, []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if line.startswith("### ") or (line[:1] not in ("", " ", "-") and DATE.search(line)):
            date = english_date(line)
        m = re.match(r"- \*\*(.+?)\*\*", line)
        if m:
            title = m.group(1)
            out.append(
                {"title": title, "date": english_date(title) if DATE.search(title) else date}
            )
    return out


def rows() -> list[dict]:
    out = []
    for exp, path in (("01", R1 / "PREREG.md"), ("02", R2 / "PREREG.md"), ("03", R3 / "PREREG.md")):
        parsed = parse(path)
        mine = [s for s in SUMMARIES if s[0] == exp]
        if len(parsed) != len(mine):
            raise SystemExit(f"{src(path)}: {len(parsed)} deviations, {len(mine)} summaries")
        for p, (_, prefix, kind, text) in zip(parsed, mine, strict=True):
            if not p["title"].startswith(prefix):
                raise SystemExit(f"{src(path)}: {p['title']!r} does not match {prefix!r}")
            out.append({"exp": exp, "date": p["date"], "type": kind, "text": text})
    return out


def table() -> str:
    lines = ["| Exp | Date | Type | Deviation |", "|---|---|---|---|"]
    for r in rows():
        lines.append(f"| {r['exp']} | {r['date']} | {r['type']} | {r['text']} |")
    return "\n".join(lines)


def counts() -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows():
        out[r["exp"]] = out.get(r["exp"], 0) + 1
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(table())
    print(counts())
