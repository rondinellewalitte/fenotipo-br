# Piloto Fenótipo-BR: termos em português e a tradução PT do HPO

R. Walitte (ORCID 0009-0004-1776-2754). Gerado por `reports/build_piloto.py` a partir de `results/`. Código: Exp 01 `6bb3334`, Exp 02 `f93b18d`.

> **Apoio à pesquisa, não é ferramenta diagnóstica.** Nada aqui deve orientar conduta clínica (ANVISA RDC 657/2022). Só foram usados dados públicos, sem dado de paciente.

## Pergunta

Só 36,0% dos termos ativos do HPO têm rótulo oficial em português. O piloto mede duas coisas:

- **Exp 01:** um termo em português encontra o ID HPO certo buscando só nos textos em inglês?
- **Exp 02:** quanto dos casos reais de doença rara já tem rótulo PT, e quais termos mais fazem falta?

O impacto no ranqueamento de genes e doenças ainda não foi medido.

## Dados e métodos

- **Fontes:**
  - HPO v2026-09-01: 19.894 termos ativos.
  - Tradução PT do mesmo tag: 7.154 rótulos de termos ativos, 227 deles desatualizados (`results/hpo_summary.json`).
  - Phenopacket Store 0.1.27: 10.377 casos da literatura, 92.068 anotações observadas.
  - `phenotype.hpoa` 2026-09-02.
  - Versões, sha256 e revisões dos modelos estão em `results/exp0*/config.json`.
- **Exp 01** (`results/exp01/PREREG.md`):
  - **Consultas:** 6.976 rótulos PT oficiais de termos sob HP:0000118. Gabarito: o ID de cada um.
  - **Índice:** só inglês, rótulo + sinônimos exact, 42.581 textos de 19.894 termos. Têm marcas de português 0 textos (`results/exp01/index_language_check.json`).
  - **Métodos:** bge-m3 (`5617a9f`), multilingual-e5-base (`d128750`), paraphrase-multilingual-mpnet (`4328cf2`) e um baseline lexical, sem ajuste fino.
  - **Ranqueamento e teste:** ranqueamento por ID; empate no topo não conta como acerto. Desfecho primário: top-1. McNemar exato pareado com correção de Holm.
- **Exp 02** (`results/exp02/PREREG.md`):
  - **Termos de um caso:** os fenótipos observados, sem os excluídos.
  - **Termo traduzido:** tem rótulo PT oficial.
  - **Termos que faltam:** ordenados pelo n de casos.
  - **Checagem fora da amostra:** a lista é ordenada numa metade dos **genes** e medida na outra (20 seeds).
- **Pós-hoc:** as análises com essa marca foram declaradas com data em "Desvios" no PREREG antes de serem calculadas.

## Resultados

### Exp 01: português contra índice só em inglês

| Método | top-1 (IC95) | top-10 | top-1 ponderado, pós-hoc (IC95) |
|---|---|---|---|
| bge-m3 | **81,2%** (80,2–82,1) | 95,0% | 81,7% (76,5–86,1) |
| e5-base (principal, `query:`/`query:`) | **72,4%** (71,3–73,4) | 91,6% | 68,8% (61,9–74,8) |
| e5-base_qp (variante, `query:`/`passage:`) | **74,7%** (73,6–75,7) | 92,6% | 64,2% (57,1–71,7) |
| Lexical rapidfuzz (baseline) | **54,1%** (52,9–55,3) | 73,0% | 50,5% (42,9–57,7) |
| mpnet-multi | **52,0%** (50,9–53,2) | 78,9% | 48,2% (40,7–55,3) |

Fonte: `results/exp01/metrics.json` (n = 6.976). Coluna ponderada: `results/exp01/weighted.json`. O peso é o n de casos em que o termo aparece; cobre 1.688 consultas.

- **bge-m3 é o melhor.** Supera o e5-base em +8,8 p.p. (p_Holm = 5,5×10⁻⁶⁵).
  - Ponderado por frequência clínica, mantém 81,7%. Os outros métodos caem de 3,6 p.p. a 10,4 p.p.
  - Os sinônimos related, broad e narrow mudam o top-1 em no máximo 0,1 p.p.
- **Hipóteses:** 4 das 8 pré-registradas se confirmaram (`results/exp01/hypotheses.json`).
  - Falhou a ordenação prevista: o mpnet-multi é **pior** que o baseline lexical (−2,1 p.p., p_Holm = 4,8×10⁻³). Nem todo embedding multilíngue serve.
- **Onde o português não se parece com o inglês** (similaridade de superfície < 50, n = 3.139): bge-m3 73,6%, lexical 39,8% (`results/exp01/surface_sim.json`).
- **"Mesma lesão, extremidade errada"** (pós-hoc, `results/exp01/hierarchy_errors.json`):
  - O achado certo vai para o membro errado, por exemplo "dedo do pé" vira "dedo da mão". São 97 dos 1.314 erros de top-1 do bge-m3 (7,4%); o lexical comete 278.
  - 87 dessas trocas ficam "distantes" na hierarquia do HPO, então métricas de pai/filho ou irmão não as veem.
  - Pai/filho direto: 21,1% dos erros. Irmão: 14,7%.
- **Leitura para RAG:** com rótulos limpos, o ID certo está entre os 10 primeiros do bge-m3 em 95,0% das consultas. É um teto otimista para uma etapa de reordenação, não um resultado de extração.

### Exp 02: cobertura PT nos casos

- **Cobertura geral** (`results/exp02/metrics.json`):
  - 38,3% das 92.068 anotações têm rótulo PT.
  - Só 5,8% dos 10.374 casos estão 100% traduzidos; a mediana por caso é 36%.
  - 86% dos 700 genes não têm nenhum caso 100% traduzido.
- **Reconferência no `phenotype.hpoa`:** 40,3% das anotações de doença e 193 dos 500 termos mais usados.

| # | Termo sem tradução PT | Casos | Genes |
|---|---|---|---|
| 1 | Global developmental delay (`HP:0001263`) | 2.623 (25,3%) | 254 |
| 2 | Delayed speech and language development (`HP:0000750`) | 1.765 (17,0%) | 182 |
| 3 | Intellectual disability (`HP:0001249`) | 1.627 (15,7%) | 165 |
| 4 | Hypotonia (`HP:0001252`) | 1.544 (14,9%) | 206 |
| 5 | Seizure (`HP:0001250`) | 825 (8,0%) | 178 |
| 6 | Motor delay (`HP:0001270`) | 796 (7,7%) | 121 |
| 7 | Feeding difficulties (`HP:0011968`) | 774 (7,5%) | 136 |
| 8 | Delayed ability to walk (`HP:0031936`) | 755 (7,3%) | 96 |
| 9 | Autistic behavior (`HP:0000729`) | 634 (6,1%) | 89 |
| 10 | Scoliosis (`HP:0002650`) | 571 (5,5%) | 146 |

Fonte: `results/exp02/missing_terms.csv` (lista completa: 300 termos).

**A tradução não foi priorizada pela frequência de uso** (pós-hoc, `results/exp02/generality.json`). Não é um viés contra termos gerais:

- Na ontologia, 40,5% dos termos não-folha têm tradução, contra 34,6% das folhas.
- Nas anotações dos casos a ordem se inverte: 30,9% contra 48,8%. Poucos termos gerais e muito frequentes estão sem tradução.

**Ganho ao traduzir os primeiros termos da lista** (base: 38,3% das anotações, 5,8% dos casos 100%):

| Termos a mais | Anotações: dentro da amostra | Anotações: fora da amostra (média; mín–máx) | Anotações: lista hpoa | Casos 100%: dentro | Casos 100%: fora (seed 42) | Casos 100%: lista hpoa |
|---|---|---|---|---|---|---|
| 50 | 62,9% (+24,6 p.p.) | +22,3 p.p. (19,5 p.p.–24,4 p.p.) | 60,1% (+21,8 p.p.) | 14,2% | 11,4%–11,8% | 10,8% |
| 100 | 70,7% (+32,4 p.p.) | +29,0 p.p. (26,5 p.p.–31,6 p.p.) | 67,5% (+29,2 p.p.) | 21,9% | 15,3%–15,4% | 16,0% |
| 300 | 84,6% (+46,3 p.p.) | +41,1 p.p. (38,4 p.p.–43,4 p.p.) | 79,5% (+41,2 p.p.) | 42,8% | 27,0%–28,9% | 27,9% |

Fontes: `results/exp02/metrics.json` e `results/exp02/out_of_sample.json`.

- **Fora da amostra** (lista ordenada em outros genes), o ganho em anotações fica em 86%–87% do ganho dentro da amostra. Já a fração de casos 100% traduzidos cai bastante.
- **A lista ordenada pelo `phenotype.hpoa`** independe destes casos e tem desempenho parecido.

## Limitações

- **Rótulos limpos ≠ prontuário.** As consultas são rótulos curtos e cheios de cognatos; os números do Exp 01 são um teto otimista.
- **Os traduzidos não representam os não traduzidos.** O Exp 01 só mede termos com tradução, e os mais frequentes na clínica ficam de fora. A ponderação corrige isso só em parte.
- **Contaminação.** Os modelos podem ter visto o HPO e suas traduções no pré-treino.
- **Grafia de Portugal.** Parte dos rótulos oficiais usa grafia europeia, e o efeito não foi isolado.
- **Casos da literatura, em inglês.** A distribuição não é a de um ambulatório brasileiro, e coortes grandes pesam nas médias.
- **Análises pós-hoc.** Estão marcadas como tal.

## Próximos passos

1. **Revisão de 300 termos em PT-BR por geneticista**, para submeter ao HPO no formato babelon, a partir de `results/exp02/missing_terms.csv` (a ordenação do hpoa é alternativa).
2. **Exp 03:** vinhetas clínicas em PT-BR, comparando extração direta em português com traduzir e depois extrair. Usar LLMs locais pequenos com RAG sobre os 10 primeiros candidatos do bge-m3. Pergunta de pesquisa: quanto o RAG recupera de um modelo que roda em GPU comum, sem enviar dados para fora.
3. **Validação com casos publicados em português** (SciELO), anotados por geneticista.
4. **Efeito dos erros no ranqueamento de genes e doenças.**
