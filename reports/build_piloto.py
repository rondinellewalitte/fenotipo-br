"""Render reports/piloto.md from the result files. Every number in the report comes from a
file under results/ (CLAUDE.md, rule 2); derived values are computed here, not typed.

    uv run python reports/build_piloto.py
"""
# ruff: noqa: E501  (the Markdown template below is prose; long lines are intended)

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
R1, R2 = ROOT / "results" / "exp01", ROOT / "results" / "exp02"
OUT = ROOT / "reports" / "piloto.md"

SUP = str.maketrans("-0123456789", "⁻⁰¹²³⁴⁵⁶⁷⁸⁹")
EXP01_ROWS = [
    ("bge-m3", "bge-m3"),
    ("e5-base", "e5-base (principal, `query:`/`query:`)"),
    ("e5-base_qp", "e5-base_qp (variante, `query:`/`passage:`)"),
    ("lexical_token_sort", "Lexical rapidfuzz (baseline)"),
    ("mpnet-multi", "mpnet-multi"),
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%".replace(".", ",")


def pts(x: float, d: int = 1) -> str:
    sign = "+" if x >= 0 else "−"
    return f"{sign}{abs(x) * 100:.{d}f}".replace(".", ",") + " p.p."


def pts_abs(x: float, d: int = 1) -> str:
    return f"{abs(x) * 100:.{d}f}".replace(".", ",") + " p.p."


def num(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def ci(pair) -> str:
    lo, hi = pair
    return f"{lo * 100:.1f}–{hi * 100:.1f}".replace(".", ",")


def sci(p: float) -> str:
    mant, exp = f"{p:.1e}".split("e")
    return f"{mant.replace('.', ',')}×10{str(int(exp)).translate(SUP)}"


def src(path: Path) -> str:
    return f"`{path.relative_to(ROOT).as_posix()}`"


def main() -> None:
    hs = load(ROOT / "results" / "hpo_summary.json")
    c1, m1 = load(R1 / "config.json"), load(R1 / "metrics.json")
    hyp, surf = load(R1 / "hypotheses.json"), load(R1 / "surface_sim.json")
    hier, wtd = load(R1 / "hierarchy_errors.json"), load(R1 / "weighted.json")
    langchk = load(R1 / "index_language_check.json")
    c2, m2 = load(R2 / "config.json"), load(R2 / "metrics.json")
    oos, gen = load(R2 / "out_of_sample.json"), load(R2 / "generality.json")
    missing = pd.read_csv(R2 / "missing_terms.csv")

    # Exp 01
    main1 = {m: m1["results"][m]["exact"]["main"] for m, _ in EXP01_ROWS}
    wcase = {m: wtd["by_method"][m]["weight_phenopacket_cases"] for m, _ in EXP01_ROWS}
    n_main = main1["bge-m3"]["n"]
    n_conf, n_hyp = sum(hyp["summary"].values()), len(hyp["summary"])
    h1 = hyp["hypotheses"]["H1_ordering"]["pairs"]["mpnet-multi > lexical_token_sort"]
    bge_vs_e5 = m1["paired_top1_mcnemar"]["bge-m3 vs e5-base"]
    max_abl = max(
        abs(m1["results"][m]["all_scopes"]["main"]["top1"] - main1[m]["top1"])
        for m, _ in EXP01_ROWS
    )
    drops = [main1[m]["top1"] - wcase[m]["top1_weighted"] for m, _ in EXP01_ROWS if m != "bge-m3"]
    s50 = {m: surf["by_method"][m]["<50"] for m in ("bge-m3", "lexical_token_sort")}
    bge_h, lex_h = hier["by_method"]["bge-m3"], hier["by_method"]["lexical_token_sort"]
    swaps = bge_h["hand_foot_swaps"]
    w_bge = wcase["bge-m3"]
    revs = {k: (v.get("revision") or "")[:7] for k, v in c1["embeddings"].items()}
    idx = c1["index"]["variants"]["exact"]

    # Exp 02
    cov = m2["coverage"]
    base_ann, base_full = cov["annotation_coverage"], cov["pct_cases_full"]
    gs = oos["gene_split"]
    seeds_sum = gs["seeds_summary_annotation_coverage_gain"]
    ratios = [seeds_sum[f"top{k}"]["ratio"]["mean"] for k in c2["gain_k"]]
    hpoa_list = oos["hpoa_ranked_list"]
    leaf_onto = gen["ontology_terms_under_HP:0000118"]["by_leaf"]
    leaf_ann = gen["case_annotations"]["by_leaf"]
    hpoa = m2["hpoa_check"]
    k_max = max(c2["gain_k"])

    exp01_table = [
        "| Método | top-1 (IC95) | top-10 | top-1 ponderado, pós-hoc (IC95) |",
        "|---|---|---|---|",
    ]
    for key, label in EXP01_ROWS:
        s, w = main1[key], wcase[key]
        exp01_table.append(
            f"| {label} | **{pct(s['top1'])}** ({ci(s['top1_ci95'])}) | {pct(s['top10'])} "
            f"| {pct(w['top1_weighted'])} ({ci(w['top1_weighted_ci95_bootstrap'])}) |"
        )

    missing_rows = ["| # | Termo sem tradução PT | Casos | Genes |", "|---|---|---|---|"]
    for r in missing.head(10).itertuples():
        missing_rows.append(
            f"| {r.rank} | {r.en_label} (`{r.hpo_id}`) | {num(r.n_cases)} ({pct(r.pct_cases)}) "
            f"| {num(r.n_genes)} |"
        )

    gain_rows = [
        "| Termos a mais | Anotações: dentro da amostra | Anotações: fora da amostra (média; mín–máx) | Anotações: lista hpoa | Casos 100%: dentro | Casos 100%: fora (seed 42) | Casos 100%: lista hpoa |",
        "|---|---|---|---|---|---|---|",
    ]
    for k in c2["gain_k"]:
        ins = m2["simulated_gain"][f"top{k}_missing_added"]
        g = seeds_sum[f"top{k}"]["oos_gain"]
        hp = hpoa_list[f"top{k}"]["hpoa_ranked"]
        a = gs["primary"]["A_to_B"][f"top{k}"]["out_of_sample"]["pct_cases_full"]
        b = gs["primary"]["B_to_A"][f"top{k}"]["out_of_sample"]["pct_cases_full"]
        gain_rows.append(
            f"| {k} | {pct(ins['annotation_coverage'])} ({pts(ins['annotation_coverage'] - base_ann)}) "
            f"| {pts(g['mean'])} ({pts_abs(g['min'])}–{pts_abs(g['max'])}) "
            f"| {pct(hp['annotation_coverage'])} ({pts(hp['annotation_coverage'] - base_ann)}) "
            f"| {pct(ins['pct_cases_full'])} | {pct(min(a, b))}–{pct(max(a, b))} "
            f"| {pct(hp['pct_cases_full'])} |"
        )

    md = f"""# Piloto HPO-PTBR: termos em português e a tradução PT do HPO

R. Walitte (ORCID 0009-0004-1776-2754). Gerado por `reports/build_piloto.py` a partir de `results/`. Código: Exp 01 `{c1["git"]["commit"][:7]}`, Exp 02 `{c2["git"]["commit"][:7]}`.

> **Apoio à pesquisa, não é ferramenta diagnóstica.** Nada aqui deve orientar conduta clínica (ANVISA RDC 657/2022). Só foram usados dados públicos, sem dado de paciente.

## Pergunta

Só {pct(hs["pt_coverage_active"])} dos termos ativos do HPO têm rótulo oficial em português. O piloto mede duas coisas:

- **Exp 01:** um termo em português encontra o ID HPO certo buscando só nos textos em inglês?
- **Exp 02:** quanto dos casos reais de doença rara já tem rótulo PT, e quais termos mais fazem falta?

O impacto no ranqueamento de genes e doenças ainda não foi medido.

## Dados e métodos

- **Fontes:**
  - HPO {c1["hpo_release"]}: {num(hs["active_terms"])} termos ativos.
  - Tradução PT do mesmo tag: {num(hs["pt_labels_active"])} rótulos de termos ativos, {num(hs["pt_labels_active_stale"])} deles desatualizados ({src(ROOT / "results" / "hpo_summary.json")}).
  - Phenopacket Store {c2["phenopacket_store_release"]}: {num(c2["counts"]["n_cases"])} casos da literatura, {num(c2["counts"]["n_observed_annotations"])} anotações observadas.
  - `phenotype.hpoa` {hpoa["hpoa_version"]}.
  - Versões, sha256 e revisões dos modelos estão em `results/exp0*/config.json`.
- **Exp 01** ({src(R1 / "PREREG.md")}):
  - **Consultas:** {num(n_main)} rótulos PT oficiais de termos sob HP:0000118. Gabarito: o ID de cada um.
  - **Índice:** só inglês, rótulo + sinônimos exact, {num(idx["n_texts"])} textos de {num(idx["n_ids"])} termos. Têm marcas de português {num(langchk["n_texts_with_pt_markers"])} textos ({src(R1 / "index_language_check.json")}).
  - **Métodos:** bge-m3 (`{revs["bge-m3"]}`), multilingual-e5-base (`{revs["e5-base"]}`), paraphrase-multilingual-mpnet (`{revs["mpnet-multi"]}`) e um baseline lexical, sem ajuste fino.
  - **Ranqueamento e teste:** ranqueamento por ID; empate no topo não conta como acerto. Desfecho primário: top-1. McNemar exato pareado com correção de Holm.
- **Exp 02** ({src(R2 / "PREREG.md")}):
  - **Termos de um caso:** os fenótipos observados, sem os excluídos.
  - **Termo traduzido:** tem rótulo PT oficial.
  - **Termos que faltam:** ordenados pelo n de casos.
  - **Checagem fora da amostra:** a lista é ordenada numa metade dos **genes** e medida na outra ({len(gs["seeds"])} seeds).
- **Pós-hoc:** as análises com essa marca foram declaradas com data em "Desvios" no PREREG antes de serem calculadas.

## Resultados

### Exp 01: português contra índice só em inglês

{chr(10).join(exp01_table)}

Fonte: {src(R1 / "metrics.json")} (n = {num(n_main)}). Coluna ponderada: {src(R1 / "weighted.json")}. O peso é o n de casos em que o termo aparece; cobre {num(w_bge["n_queries_with_weight"])} consultas.

- **bge-m3 é o melhor.** Supera o e5-base em {pts(bge_vs_e5["diff_a_minus_b"])} (p_Holm = {sci(bge_vs_e5["p_holm"])}).
  - Ponderado por frequência clínica, mantém {pct(w_bge["top1_weighted"])}. Os outros métodos caem de {pts_abs(min(drops))} a {pts_abs(max(drops))}
  - Os sinônimos related, broad e narrow mudam o top-1 em no máximo {pts_abs(max_abl)}
- **Hipóteses:** {n_conf} das {n_hyp} pré-registradas se confirmaram ({src(R1 / "hypotheses.json")}).
  - Falhou a ordenação prevista: o mpnet-multi é **pior** que o baseline lexical ({pts(h1["diff_top1"])}, p_Holm = {sci(h1["p_holm"])}). Nem todo embedding multilíngue serve.
- **Onde o português não se parece com o inglês** (similaridade de superfície < 50, n = {num(s50["bge-m3"]["n"])}): bge-m3 {pct(s50["bge-m3"]["top1"])}, lexical {pct(s50["lexical_token_sort"]["top1"])} ({src(R1 / "surface_sim.json")}).
- **"Mesma lesão, extremidade errada"** (pós-hoc, {src(R1 / "hierarchy_errors.json")}):
  - O achado certo vai para o membro errado, por exemplo "dedo do pé" vira "dedo da mão". São {num(swaps["n_swaps"])} dos {num(swaps["n_strict_top1_errors"])} erros de top-1 do bge-m3 ({pct(swaps["share_of_errors"])}); o lexical comete {num(lex_h["hand_foot_swaps"]["n_swaps"])}.
  - {num(swaps["category_count"].get("distant", 0))} dessas trocas ficam "distantes" na hierarquia do HPO, então métricas de pai/filho ou irmão não as veem.
  - Pai/filho direto: {pct(bge_h["main"]["share_of_errors"]["parent_child"])} dos erros. Irmão: {pct(bge_h["main"]["share_of_errors"]["sibling"])}.
- **Leitura para RAG:** com rótulos limpos, o ID certo está entre os 10 primeiros do bge-m3 em {pct(main1["bge-m3"]["top10"])} das consultas. É um teto otimista para uma etapa de reordenação, não um resultado de extração.

### Exp 02: cobertura PT nos casos

- **Cobertura geral** ({src(R2 / "metrics.json")}):
  - {pct(base_ann)} das {num(cov["n_annotations"])} anotações têm rótulo PT.
  - Só {pct(base_full)} dos {num(cov["n_cases"])} casos estão 100% traduzidos; a mediana por caso é {pct(cov["frac_median"], 0)}.
  - {pct(m2["by_gene_summary"]["pct_groups_with_no_full_case"], 0)} dos {num(m2["by_gene_summary"]["n_groups"])} genes não têm nenhum caso 100% traduzido.
- **Reconferência no `phenotype.hpoa`:** {pct(hpoa["annotation_coverage"])} das anotações de doença e {hpoa["top500_by_n_diseases_with_pt"]} dos 500 termos mais usados.

{chr(10).join(missing_rows)}

Fonte: {src(R2 / "missing_terms.csv")} (lista completa: 300 termos).

**A tradução não foi priorizada pela frequência de uso** (pós-hoc, {src(R2 / "generality.json")}). Não é um viés contra termos gerais:

- Na ontologia, {pct(leaf_onto["False"]["share_translated"])} dos termos não-folha têm tradução, contra {pct(leaf_onto["True"]["share_translated"])} das folhas.
- Nas anotações dos casos a ordem se inverte: {pct(leaf_ann["False"]["share_translated"])} contra {pct(leaf_ann["True"]["share_translated"])}. Poucos termos gerais e muito frequentes estão sem tradução.

**Ganho ao traduzir os primeiros termos da lista** (base: {pct(base_ann)} das anotações, {pct(base_full)} dos casos 100%):

{chr(10).join(gain_rows)}

Fontes: {src(R2 / "metrics.json")} e {src(R2 / "out_of_sample.json")}.

- **Fora da amostra** (lista ordenada em outros genes), o ganho em anotações fica em {pct(min(ratios), 0)}–{pct(max(ratios), 0)} do ganho dentro da amostra. Já a fração de casos 100% traduzidos cai bastante.
- **A lista ordenada pelo `phenotype.hpoa`** independe destes casos e tem desempenho parecido.

## Limitações

- **Rótulos limpos ≠ prontuário.** As consultas são rótulos curtos e cheios de cognatos; os números do Exp 01 são um teto otimista.
- **Os traduzidos não representam os não traduzidos.** O Exp 01 só mede termos com tradução, e os mais frequentes na clínica ficam de fora. A ponderação corrige isso só em parte.
- **Contaminação.** Os modelos podem ter visto o HPO e suas traduções no pré-treino.
- **Grafia de Portugal.** Parte dos rótulos oficiais usa grafia europeia, e o efeito não foi isolado.
- **Casos da literatura, em inglês.** A distribuição não é a de um ambulatório brasileiro, e coortes grandes pesam nas médias.
- **Análises pós-hoc.** Estão marcadas como tal.

## Próximos passos

1. **Revisão de {k_max} termos em PT-BR por geneticista**, para submeter ao HPO no formato babelon, a partir de {src(R2 / "missing_terms.csv")} (a ordenação do hpoa é alternativa).
2. **Exp 03:** vinhetas clínicas em PT-BR, comparando extração direta em português com traduzir e depois extrair. Usar LLMs locais pequenos com RAG sobre os 10 primeiros candidatos do bge-m3. Pergunta de pesquisa: quanto o RAG recupera de um modelo que roda em GPU comum, sem enviar dados para fora.
3. **Validação com casos publicados em português** (SciELO), anotados por geneticista.
4. **Efeito dos erros no ranqueamento de genes e doenças.**
"""
    OUT.write_text(md, encoding="utf-8")
    print(f"-> {OUT} ({len(md.split())} words)")


if __name__ == "__main__":
    main()
