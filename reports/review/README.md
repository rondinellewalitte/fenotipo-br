# Revisão de 50 termos HPO sem tradução PT-BR

Gerado por `reports/build_review.py` em 2026-10-25 (commit `79a1f34`). Os números vêm de `results/`; não edite este arquivo à mão.

> Apoio à pesquisa. Não é ferramenta diagnóstica nem orienta conduta clínica (ANVISA RDC 657/2022).

## O que é

Os 50 termos do HPO (v2026-09-01) **sem rótulo oficial em português** que mais aparecem nos casos do Phenopacket Store (0.1.27). A lista vem de `results/exp02/missing_terms.csv`.

- `top50_terms.xlsx`: para abrir no Excel. A aba **LEIA-ME** tem as instruções e um exemplo; a aba **termos** tem a lista.
- `top50_terms.csv`: o mesmo conteúdo em texto (UTF-8).

## Por que estes termos

- **Hoje:** 38,3% das anotações de fenótipo desses casos têm rótulo PT oficial, e só 5,8% dos casos estão 100% traduzidos (`results/exp02/metrics.json`).
- **Ganho esperado** com a tradução destes 50 termos: **≈38% → ≈61% de cobertura por anotação**, fora da amostra (`results/exp02/out_of_sample.json`).
  - O ganho médio é de +22,3 p.p. (faixa +19,5 p.p. a +24,4 p.p.). Ele foi medido em 20 divisões dos genes em duas metades: a lista é ordenada numa metade e o ganho é medido na outra.
  - Casos 100% traduzidos: de 5,8% para 11,4%–11,8%, fora da amostra.
  - Para comparação: dentro da amostra, que é um teto otimista, a cobertura chega a 62,9%. Com uma lista ordenada pelo `phenotype.hpoa`, que independe destes casos, chega a 60,1%.
- **Limites:**
  - Os casos vêm da literatura e foram anotados em inglês. A frequência num ambulatório brasileiro pode ser outra.
  - **Viés de ancoragem:** quem revisa tende a aprovar a tradução candidata que já está na planilha. Por isso pedimos que corrija sem receio e marque explicitamente quando aceitar a candidata sem alteração. A taxa de aceitação deve ser lida como teto do acerto da tradução automática, não como medida independente.

## Como revisar

Preencha as duas colunas em amarelo:

- **`reviewer_pt`:** o rótulo final em PT-BR, mesmo que seja igual ao candidato. Use grafia brasileira, o termo usual na clínica e na genética médica no Brasil, e a forma de rótulo do HPO (substantivo, só a primeira letra maiúscula, sem ponto final).
- **`reviewer_notes`:** opcional. Dúvidas, termos alternativos, uso regional.
- **Corrija sem receio.** A tradução candidata é só um ponto de partida e pode estar errada ou soar estranha. Corrija sem receio sempre que preferir outro termo. Se aceitar a candidata exatamente como está, copie-a em reviewer_pt e escreva em reviewer_notes: candidata aceita sem alteração. Isso permite medir quanto a tradução automática acertou.

As colunas `label_en`, `definition_en` e `synonyms_en` trazem o conceito oficial em inglês. Sinônimos que não são exatos vêm marcados, por exemplo `[related]`.

## Sobre `candidate_pt`

**TRADUÇÃO AUTOMÁTICA (gerada por máquina). Exige revisão humana; não usar sem revisão.**

Preenchida para os 50 termos pelo modelo `claude-opus-5-5` (prompt `prompts/translate_hpo_label_pt_br_v1.system.md`, sha256 `2778aaf0b0fc`).

- **Configuração:** modelo fixo `claude-opus-5-5`, esforço `low` e saída em JSON validado por esquema.
  - A API não aceita mais o parâmetro de temperatura. Por isso, cada resposta é guardada em `results/review/translations.jsonl` e reaproveitada, em vez de ser gerada de novo.
- **Custo:** as chamadas, com tokens e custo, ficam em `results/review/llm_calls.jsonl`. O resumo está em `results/review/run_summary.json`, com teto de US$ 2,00. Total gasto até agora: US$ 0,33 em 50 chamadas.

## Depois da revisão

1. **Conversão:** o rótulo de `reviewer_pt` vira uma linha no formato babelon do HPO (`src/translations/hp-pt.babelon.tsv`), com o ORCID de quem revisou na coluna `translator`.
2. **Submissão:** um pull request ao repositório `obophenotype/human-phenotype-ontology`, com crédito de tradução e coautoria no artigo do piloto.
