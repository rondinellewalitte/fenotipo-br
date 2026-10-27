# Fenótipo-BR: resumo dos Exp 01 a 03

R. Walitte (ORCID 0009-0004-1776-2754). Versão 0.2.0. Gerado por `reports/build_summary.py`; cada número cita o arquivo de `results/` de onde saiu. Relatórios completos: `reports/piloto.md` (Exp 01–02, v0.1.0) e `reports/exp03.md`.

> **Apoio à pesquisa, não é ferramenta diagnóstica.** Nada aqui deve orientar conduta clínica (ANVISA RDC 657/2022). Só dados públicos e sintéticos; nenhum dado de paciente.

Ferramentas de extração de fenótipo foram feitas para inglês, e só 36,0% dos termos ativos do HPO v2026-09-01 (7.154 de 19.894) têm rótulo oficial em português (`results/hpo_summary.json`). Os três experimentos foram pré-registrados antes de qualquer resultado; desvios e análises pós-hoc estão datados no `PREREG.md` de cada um.

## Exp 01: rótulo PT → termo HPO, buscando só em inglês

- 6.976 rótulos PT oficiais buscados num índice só com rótulos e sinônimos em inglês. bge-m3: top-1 81,2% (IC95 80,2% a 82,1%), top-10 95,0%. Baseline lexical: top-1 54,1% (`results/exp01/metrics.json`).
- Com grafia distante do inglês (similaridade < 50, n = 3.139), o bge-m3 acerta 73,6% no top-1, contra 39,8% do lexical (`results/exp01/surface_sim.json`).
- 4 de 8 hipóteses confirmadas (`results/exp01/hypotheses.json`). Pós-hoc: 7,4% dos erros top-1 do bge-m3 trocam mão por pé (`results/exp01/hierarchy_errors.json`).

## Exp 02: quanto dos casos publicados já tem rótulo PT

- Phenopacket Store 0.1.27: 10.374 casos e 92.068 anotações de fenótipo observado. 38,3% das anotações têm rótulo PT, e só 5,8% dos casos estão totalmente cobertos (`results/exp02/metrics.json`).
- Termos sem tradução mais frequentes: Global developmental delay (2.623 casos), Delayed speech and language development (1.765 casos), Intellectual disability (1.627 casos) (`results/exp02/missing_terms.csv`).
- Traduzir os 50 termos faltantes mais frequentes sobe a cobertura das anotações em +22,3 p.p., fora da amostra (média de 20 divisões por gene; `results/exp02/out_of_sample.json`).

## Exp 03: extração de vinhetas sintéticas com LLMs locais

300 vinhetas em PT-BR escritas por `claude-opus-5-5` a partir de casos do Phenopacket Store (2.466 termos no gabarito, 959 negações no texto). Dois modelos de 4B rodando localmente (Ollama, Q4_K_M) extraem os achados, e o `BAAI/bge-m3` busca 10 candidatos no HPO para o LLM escolher. Braços: **A** direto em português, **B** traduz para o inglês antes, **C** igual ao A com os rótulos PT no índice. F1 micro por termo, ID exato (`results/exp03/metrics.json`):

| Modelo | A, direto em PT | B, traduz antes | C, índice bilíngue |
|---|---|---|---|
| Qwen3-4B | 0,525 | 0,582 | 0,517 |
| Gemma 3 4B | 0,416 | 0,454 | 0,396 |
| Baseline sem LLM | 0,328 | — | — |

- **Traduzir antes foi melhor** (desfecho primário). F1(A) − F1(B): Qwen3-4B −0,056 (IC 97,5% −0,076 a −0,036); Gemma 3 4B −0,038 (IC 97,5% −0,062 a −0,015). A não inferioridade pré-registrada (margem −0,03) não se confirmou, e a superioridade do B é relatada como o PREREG previa. A diferença é maior nas frases distantes do rótulo inglês, o que afasta a simples recuperação do rótulo de origem do gerador (`results/exp03/metrics.json` → `comparisons` e `recall_by_stratum`).
- **Rótulos PT no índice não ajudaram.** F1(C) − F1(A): Qwen3-4B −0,008 (IC95 −0,018 a 0,003); Gemma 3 4B −0,019 (IC95 −0,032 a −0,007) (`results/exp03/metrics.json` → `comparisons`).
- **A busca é o gargalo.** No braço A, o termo certo estava entre os 10 candidatos (teto de recuperação) para esta fração do gabarito: Qwen3-4B 0,736; Gemma 3 4B 0,537 (`results/exp03/metrics.json` → `arms`). Com a frase exata do gerador e sem LLM, o bge-m3 põe o termo certo no top-10 em 74,7% dos termos, contra 95,0% com rótulos limpos no Exp 01 (comparação entre experimentos, descritiva; `results/exp03/metrics.json` → `oracle_spans_bge_m3_en_index` e `results/exp01/metrics.json`).
- **Linguagem leiga é a mais difícil.** Recall no braço A dos termos escritos só em linguagem leiga (n = 645): Qwen3-4B 0,412; Gemma 3 4B 0,102. No Gemma 3 4B, esse recall ficou abaixo do baseline sem LLM (0,153). Rótulos de registro feitos às cegas e conferidos pelo autor em 40 itens: kappa 0,85 (IC95 0,70 a 0,96) (`results/exp03/metrics.json` → `register.d2`; `results/exp03/pilot/register_kappa.json`).
- 2 de 6 hipóteses confirmadas nos dois modelos (H3, H6) (`results/exp03/hypotheses.json`).

## Limitações

- **Vinhetas sintéticas**, escritas por LLM; não há validação em prontuário real.
- **Gerador e rotulador de registro são o mesmo modelo** (`claude-opus-5-5`).
- **Contaminação:** os casos vêm de artigos publicados que os modelos podem ter visto.
- **Conferência humana feita por não clínico** (o autor); a revisão por geneticista está prevista.
- **Rótulos limpos não são texto clínico:** o Exp 01 é um teto otimista para a normalização.

## Versões

HPO v2026-09-01; Phenopacket Store 0.1.27. Código: Exp 01 `6bb3334`, Exp 02 `f93b18d`, Exp 03 `f187e1f` (`config.json` de cada experimento). DOI do projeto: [10.5281/zenodo.23662825](https://doi.org/10.5281/zenodo.23662825); v0.1.0 (Exp 01–02): [10.5281/zenodo.23662826](https://doi.org/10.5281/zenodo.23662826); v0.2.0 (Exp 03): a ser atribuído pelo Zenodo na publicação.
