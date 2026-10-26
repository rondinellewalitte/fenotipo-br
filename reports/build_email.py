"""Render reports/emails/rede_raras.md: the first-contact e-mail to the Rede RARAS coordination
(PT-BR). Every number comes from a file under results/ (CLAUDE.md, rule 2). The e-mail is a
draft; nothing here sends it.

    uv run python reports/build_email.py
"""
# ruff: noqa: E501  (the e-mail template below is prose; long lines are intended)

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from hpolab.provenance import git_info

ROOT = Path(__file__).resolve().parents[1]
R2 = ROOT / "results" / "exp02"
OUT = ROOT / "reports" / "emails" / "rede_raras.md"
ATTACHMENTS = ("reports/review/top50_terms.xlsx", "reports/piloto.pdf")
REPO_URL = "https://github.com/rondinellewalitte/fenotipo-br"
DOI_URL = "https://doi.org/10.5281/zenodo.23662825"  # Zenodo concept DOI (all versions)
SENDER = ("Rondinelle Walitte", "rondinellewalitte@gmail.com", "0009-0004-1776-2754")
N_TERMS = 50
MAX_WORDS = 200
# Figure the author approved for the e-mail; the build stops if the results no longer give it.
APPROVED_AFTER_PCT = 61
# Examples named in the e-mail, in PT; each must be among the 5 most frequent missing terms.
EXAMPLES = {
    "HP:0001263": "atraso global do desenvolvimento",
    "HP:0001249": "deficiência intelectual",
    "HP:0001252": "hipotonia",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%".replace(".", ",")


def pts(x: float, d: int = 1) -> str:
    sign = "+" if x >= 0 else "−"
    return f"{sign}{abs(x) * 100:.{d}f}".replace(".", ",") + " p.p."


def n_words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def main() -> None:
    m2, oos = load(R2 / "metrics.json"), load(R2 / "out_of_sample.json")
    missing = pd.read_csv(R2 / "missing_terms.csv")
    cov = m2["coverage"]
    base, full = cov["annotation_coverage"], cov["pct_cases_full"]
    gain = oos["gene_split"]["seeds_summary_annotation_coverage_gain"][f"top{N_TERMS}"]["oos_gain"]
    after = base + gain["mean"]
    if round(after * 100) != APPROVED_AFTER_PCT:
        raise SystemExit(
            f"Coverage after top {N_TERMS} is now {pct(after)}, not ≈{APPROVED_AFTER_PCT}% as "
            "approved; ask the author before changing the e-mail."
        )
    top5 = set(missing.head(5)["hpo_id"])
    if not set(EXAMPLES) <= top5:
        raise SystemExit(f"Examples {sorted(set(EXAMPLES) - top5)} left the top 5 missing terms.")
    examples = ", ".join(list(EXAMPLES.values())[:-1]) + " e " + list(EXAMPLES.values())[-1]

    subject = (
        f"Revisão de {N_TERMS} termos do HPO sem tradução para o português (convite de coautoria)"
    )
    body = f"""Prezado(a) [Nome],

Sou Rondinelle Walitte, desenvolvedor independente, e estudo como descrever fenótipos de doenças raras em português com a Human Phenotype Ontology (HPO).

Num piloto com casos publicados na literatura (Phenopacket Store), só {pct(base, 0)} das anotações de fenótipo têm rótulo oficial em português, e só {pct(full)} dos casos têm todos os fenótipos com esse rótulo. Faltam justamente termos muito comuns, como {examples}. Traduzir os {N_TERMS} mais frequentes elevaria a cobertura das anotações de fenótipo para ≈{APPROVED_AFTER_PCT}% (estimativa fora da amostra).

É um piloto só com rótulos do HPO e casos da literatura: sem prontuários, sem dados de pacientes, e não é ferramenta clínica.

Meu pedido é um só: que um(a) geneticista da Rede RARAS revise esses {N_TERMS} termos na planilha anexa, que já traz o termo em inglês, a definição e uma tradução automática para corrigir. Quem revisar será coautor(a) da submissão das traduções ao HPO e do artigo do piloto.

Relatório do piloto (PDF anexo); código e resultados: {REPO_URL} e {DOI_URL}

O projeto é de pesquisa aberta e não tem interesse comercial.

Atenciosamente,
{SENDER[0]}
{SENDER[1]}
ORCID {SENDER[2]}"""
    words = n_words(subject) + n_words(body)
    if words > MAX_WORDS:
        raise SystemExit(f"E-mail has {words} words (subject + body); the limit is {MAX_WORDS}.")

    git = git_info()
    sha = (git["commit"] or "")[:7] + (", com mudanças não commitadas" if git["dirty"] else "")
    gain_src = f"gene_split.seeds_summary_annotation_coverage_gain.top{N_TERMS}.oos_gain.mean"
    md = f"""<!-- Gerado por reports/build_email.py; não edite à mão. -->
# E-mail: Rede RARAS (rascunho, não enviado)

**Para:** [Nome], coordenação da Rede RARAS <[e-mail]>
**Anexos:** {", ".join(f"`{a}`" for a in ATTACHMENTS)}

```text
Assunto: {subject}

{body}
```

---

## NÃO ENVIAR: notas internas

Gerado em {datetime.now(UTC).strftime("%Y-%m-%d")} (commit `{sha}`). Assunto + corpo: **{words} palavras** (limite {MAX_WORDS}).

**Números do e-mail e de onde vêm**

| No e-mail | Valor no arquivo | Arquivo e campo |
|---|---|---|
| {pct(base, 0)} das anotações de fenótipo | {base} | `results/exp02/metrics.json` → `coverage.annotation_coverage` |
| {pct(full)} dos casos com todos os fenótipos traduzidos | {full} | `results/exp02/metrics.json` → `coverage.pct_cases_full` |
| ≈{APPROVED_AFTER_PCT}% das anotações após os {N_TERMS} termos | {base} + {gain["mean"]} = {after:.4f} | `results/exp02/out_of_sample.json` → `{gain_src}` |

- O ≈{APPROVED_AFTER_PCT}% é a cobertura atual mais o ganho médio fora da amostra em {len(oos["gene_split"]["seeds"])} divisões por gene: {pts(gain["mean"])} (faixa {pts(gain["min"])} a {pts(gain["max"])}). Cada divisão mede o ganho na metade de teste; somar à cobertura da amostra toda é uma aproximação.
- Exemplos citados: {", ".join(EXAMPLES)}, entre os 5 termos sem tradução mais frequentes (`results/exp02/missing_terms.csv`).

**Antes de enviar**

- Preencher `[Nome]` e `[e-mail]` com os dados de quem recebe (coordenação da Rede RARAS). Ajustar "Prezado(a)" ao nome.
- Conferir que {REPO_URL} está público e com o último commit, e que {DOI_URL} abre o registro no Zenodo.
- Anexar {" e ".join(f"`{a}`" for a in ATTACHMENTS)}. Gerar o PDF de novo (`reports/build_piloto_pdf.py`) sempre que o `piloto.md` mudar.
"""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(md, encoding="utf-8")
    print(f"-> {OUT} ({words} words, subject + body)")


if __name__ == "__main__":
    main()
