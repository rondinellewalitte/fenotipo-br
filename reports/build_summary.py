"""Render reports/summary.md: Exp 01-03 in at most two pages, in Portuguese. Every number comes
from a file under results/ (CLAUDE.md, rule 2) and each one names its source file. The full
reports stay where they are: reports/piloto.md (Exp 01-02, v0.1.0) and reports/exp03.md.

    uv run python reports/build_summary.py
    uv run python reports/build_summary.py --check-pages   # A4 page count; needs Chrome or Edge
"""
# ruff: noqa: E501  (the Markdown template below is prose; long lines are intended)

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import pandas as pd
from build_readme import CONCEPT_DOI, RELEASE, V010

ROOT = Path(__file__).resolve().parents[1]
R1, R2, R3 = (ROOT / "results" / f"exp0{i}" for i in (1, 2, 3))
OUT = ROOT / "reports" / "summary.md"
MAX_PAGES = 2
MODELS = {"qwen3-4b": "Qwen3-4B", "gemma3-4b": "Gemma 3 4B"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dec(x: float, d: int = 3) -> str:
    if abs(x) < 0.5 * 10**-d:  # no "−0,000"
        x = 0.0
    return f"{x:.{d}f}".replace(".", ",").replace("-", "−")


def sgn(x: float, d: int = 3) -> str:
    return ("+" if x >= 0 else "") + dec(x, d)


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%".replace(".", ",")


def pts(x: float, d: int = 1) -> str:
    return ("+" if x >= 0 else "−") + f"{abs(x) * 100:.{d}f}".replace(".", ",") + " p.p."


def num(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def ci(pair, f=dec) -> str:
    return f"{f(pair[0])} a {f(pair[1])}"


def src(path: Path, key: str = "") -> str:
    rel = f"`{path.relative_to(ROOT).as_posix()}`"
    return f"{rel} → `{key}`" if key else rel


def per_model(fn) -> str:
    return "; ".join(f"{name} {fn(k)}" for k, name in MODELS.items())


def render() -> str:
    hs = load(ROOT / "results" / "hpo_summary.json")
    c1, m1, h1 = load(R1 / "config.json"), load(R1 / "metrics.json"), load(R1 / "hypotheses.json")
    surf, hier = load(R1 / "surface_sim.json"), load(R1 / "hierarchy_errors.json")
    c2, m2, oos = (
        load(R2 / "config.json"),
        load(R2 / "metrics.json"),
        load(R2 / "out_of_sample.json"),
    )
    missing = pd.read_csv(R2 / "missing_terms.csv")
    c3, m3, h3 = load(R3 / "config.json"), load(R3 / "metrics.json"), load(R3 / "hypotheses.json")
    vcfg = load(R3 / "vignettes_config_full.json")
    kappa = load(R3 / "pilot" / "register_kappa.json")

    # Exp 01
    bge, lex = (m1["results"][m]["exact"]["main"] for m in ("bge-m3", "lexical_token_sort"))
    s50 = {m: surf["by_method"][m]["<50"] for m in ("bge-m3", "lexical_token_sort")}
    swaps = hier["by_method"]["bge-m3"]["hand_foot_swaps"]
    # Exp 02
    cov = m2["coverage"]
    g50 = oos["gene_split"]["seeds_summary_annotation_coverage_gain"]["top50"]["oos_gain"]
    top3 = ", ".join(f"{r.en_label} ({num(r.n_cases)} casos)" for r in missing.head(3).itertuples())
    # Exp 03
    arms, comp, d2 = m3["arms"], m3["comparisons"], m3["register"]["d2"]
    hh = h3["hypotheses"]
    held = [n.split("_")[0] for n, h in hh.items() if h["confirmed_both_models"]]
    base_lay = d2["none/baseline"]["recall"]["lay"]["recall"]
    below = [MODELS[k] for k in MODELS if d2[f"{k}/A"]["recall"]["lay"]["recall"] < base_lay]
    oracle = m3["oracle_spans_bge_m3_en_index"]
    for k in MODELS:  # the wording below states these directions
        sim = {
            b: arms[f"{k}/A"]["recall_by_stratum"]["sim_bin"][b]["recall"]
            - arms[f"{k}/B"]["recall_by_stratum"]["sim_bin"][b]["recall"]
            for b in ("<50", "50-80", ">=80")
        }
        assert comp[k]["A-B"]["ci97_5"][1] < 0 and sim["<50"] == min(sim.values())
        assert comp[k]["C-A"]["ci95"][0] <= 0
        assert hh["H6_lay_harder_than_technical"]["per_model"][k]["confirmed"]

    f1 = [
        "| Modelo | A, direto em PT | B, traduz antes | C, índice bilíngue |",
        "|---|---|---|---|",
    ]
    for k, name in MODELS.items():
        cells = " | ".join(dec(arms[f"{k}/{a}"]["micro"]["f1"]) for a in "ABC")
        f1.append(f"| {name} | {cells} |")
    f1.append(f"| Baseline sem LLM | {dec(arms['none/baseline']['micro']['f1'])} | — | — |")

    v2_doi = (
        f"[{RELEASE['doi']}](https://doi.org/{RELEASE['doi']})"
        if RELEASE["doi"]
        else "a ser atribuído pelo Zenodo na publicação"
    )
    below_text = (
        f" No {' e no '.join(below)}, esse recall ficou abaixo do baseline sem LLM ({dec(base_lay)})."
        if below
        else ""
    )

    return f"""# Fenótipo-BR: resumo dos Exp 01 a 03

R. Walitte (ORCID 0009-0004-1776-2754). Versão {RELEASE["version"]}. Gerado por `reports/build_summary.py`; cada número cita o arquivo de `results/` de onde saiu. Relatórios completos: `reports/piloto.md` (Exp 01–02, v{V010["version"]}) e `reports/exp03.md`.

> **Apoio à pesquisa, não é ferramenta diagnóstica.** Nada aqui deve orientar conduta clínica (ANVISA RDC 657/2022). Só dados públicos e sintéticos; nenhum dado de paciente.

Ferramentas de extração de fenótipo foram feitas para inglês, e só {pct(hs["pt_coverage_active"])} dos termos ativos do HPO {c1["hpo_release"]} ({num(hs["pt_labels_active"])} de {num(hs["active_terms"])}) têm rótulo oficial em português ({src(ROOT / "results" / "hpo_summary.json")}). Os três experimentos foram pré-registrados antes de qualquer resultado; desvios e análises pós-hoc estão datados no `PREREG.md` de cada um.

## Exp 01: rótulo PT → termo HPO, buscando só em inglês

- {num(bge["n"])} rótulos PT oficiais buscados num índice só com rótulos e sinônimos em inglês. bge-m3: top-1 {pct(bge["top1"])} (IC95 {ci(bge["top1_ci95"], pct)}), top-10 {pct(bge["top10"])}. Baseline lexical: top-1 {pct(lex["top1"])} ({src(R1 / "metrics.json")}).
- Com grafia distante do inglês (similaridade < 50, n = {num(s50["bge-m3"]["n"])}), o bge-m3 acerta {pct(s50["bge-m3"]["top1"])} no top-1, contra {pct(s50["lexical_token_sort"]["top1"])} do lexical ({src(R1 / "surface_sim.json")}).
- {sum(h1["summary"].values())} de {len(h1["summary"])} hipóteses confirmadas ({src(R1 / "hypotheses.json")}). Pós-hoc: {pct(swaps["share_of_errors"])} dos erros top-1 do bge-m3 trocam mão por pé ({src(R1 / "hierarchy_errors.json")}).

## Exp 02: quanto dos casos publicados já tem rótulo PT

- Phenopacket Store {c2["phenopacket_store_release"]}: {num(cov["n_cases"])} casos e {num(cov["n_annotations"])} anotações de fenótipo observado. {pct(cov["annotation_coverage"])} das anotações têm rótulo PT, e só {pct(cov["pct_cases_full"])} dos casos estão totalmente cobertos ({src(R2 / "metrics.json")}).
- Termos sem tradução mais frequentes: {top3} ({src(R2 / "missing_terms.csv")}).
- Traduzir os 50 termos faltantes mais frequentes sobe a cobertura das anotações em {pts(g50["mean"])}, fora da amostra (média de {len(oos["gene_split"]["seeds"])} divisões por gene; {src(R2 / "out_of_sample.json")}).

## Exp 03: extração de vinhetas sintéticas com LLMs locais

{num(c3["n_cases"])} vinhetas em PT-BR escritas por `{vcfg["generator"]["model"]}` a partir de casos do Phenopacket Store ({num(m3["n_gold_terms"])} termos no gabarito, {num(m3["n_negated_terms"])} negações no texto). Dois modelos de 4B rodando localmente (Ollama, Q4_K_M) extraem os achados, e o `{c3["retrieval"]["model"]}` busca 10 candidatos no HPO para o LLM escolher. Braços: **A** direto em português, **B** traduz para o inglês antes, **C** igual ao A com os rótulos PT no índice. F1 micro por termo, ID exato ({src(R3 / "metrics.json")}):

{chr(10).join(f1)}

- **Traduzir antes foi melhor** (desfecho primário). F1(A) − F1(B): {per_model(lambda k: f"{sgn(comp[k]['A-B']['diff'])} (IC 97,5% {ci(comp[k]['A-B']['ci97_5'])})")}. A não inferioridade pré-registrada (margem −0,03) não se confirmou, e a superioridade do B é relatada como o PREREG previa. A diferença é maior nas frases distantes do rótulo inglês, o que afasta a simples recuperação do rótulo de origem do gerador ({src(R3 / "metrics.json", "comparisons")} e `recall_by_stratum`).
- **Rótulos PT no índice não ajudaram.** F1(C) − F1(A): {per_model(lambda k: f"{sgn(comp[k]['C-A']['diff'])} (IC95 {ci(comp[k]['C-A']['ci95'])})")} ({src(R3 / "metrics.json", "comparisons")}).
- **A busca é o gargalo.** No braço A, o termo certo estava entre os 10 candidatos (teto de recuperação) para esta fração do gabarito: {per_model(lambda k: dec(arms[f"{k}/A"]["retrieval_ceiling_recall"]))} ({src(R3 / "metrics.json", "arms")}). Com a frase exata do gerador e sem LLM, o bge-m3 põe o termo certo no top-10 em {pct(oracle["top10"])} dos termos, contra {pct(bge["top10"])} com rótulos limpos no Exp 01 (comparação entre experimentos, descritiva; {src(R3 / "metrics.json", "oracle_spans_bge_m3_en_index")} e {src(R1 / "metrics.json")}).
- **Linguagem leiga é a mais difícil.** Recall no braço A dos termos escritos só em linguagem leiga (n = {num(d2["qwen3-4b/A"]["recall"]["lay"]["n"])}): {per_model(lambda k: dec(d2[f"{k}/A"]["recall"]["lay"]["recall"]))}.{below_text} Rótulos de registro feitos às cegas e conferidos pelo autor em 40 itens: kappa {dec(kappa["cohen_kappa"], 2)} (IC95 {ci(kappa["cohen_kappa_ci95"], lambda x: dec(x, 2))}) ({src(R3 / "metrics.json", "register.d2")}; {src(R3 / "pilot" / "register_kappa.json")}).
- {len(held)} de {len(hh)} hipóteses confirmadas nos dois modelos ({", ".join(held)}) ({src(R3 / "hypotheses.json")}).

## Limitações

- **Vinhetas sintéticas**, escritas por LLM; não há validação em prontuário real.
- **Gerador e rotulador de registro são o mesmo modelo** (`{vcfg["generator"]["model"]}`).
- **Contaminação:** os casos vêm de artigos publicados que os modelos podem ter visto.
- **Conferência humana feita por não clínico** (o autor); a revisão por geneticista está prevista.
- **Rótulos limpos não são texto clínico:** o Exp 01 é um teto otimista para a normalização.

## Versões

HPO {c1["hpo_release"]}; Phenopacket Store {c2["phenopacket_store_release"]}. Código: Exp 01 `{c1["git"]["commit"][:7]}`, Exp 02 `{c2["git"]["commit"][:7]}`, Exp 03 `{c3["git"]["commit"][:7]}` (`config.json` de cada experimento). DOI do projeto: [{CONCEPT_DOI}](https://doi.org/{CONCEPT_DOI}); v{V010["version"]} (Exp 01–02): [{V010["doi"]}](https://doi.org/{V010["doi"]}); v{RELEASE["version"]} (Exp 03): {v2_doi}.
"""


def page_count(md: str) -> int:
    from build_piloto_pdf import find_browser, print_pdf, to_html
    from pypdf import PdfReader

    with tempfile.TemporaryDirectory() as tmp:
        html, pdf = Path(tmp) / "summary.html", Path(tmp) / "summary.pdf"
        html.write_text(to_html(md), encoding="utf-8")
        print_pdf(find_browser(), html, pdf, Path(tmp) / "profile")
        return len(PdfReader(pdf).pages)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-pages", action="store_true", help=f"fail above {MAX_PAGES} A4 pages"
    )
    args = parser.parse_args()
    md = render()
    OUT.write_text(md, encoding="utf-8")
    print(f"-> {OUT} ({len(md.split())} words)")
    if args.check_pages:
        n = page_count(md)
        print(f"{n} A4 pages with the reports/build_piloto_pdf.py layout")
        if n > MAX_PAGES:
            raise SystemExit(f"summary.md is {n} pages; the limit is {MAX_PAGES}.")


if __name__ == "__main__":
    main()
