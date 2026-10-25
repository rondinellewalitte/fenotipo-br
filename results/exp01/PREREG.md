# Exp 01: pré-registro

**Escrito em 25/out/2026, antes do run completo** e antes de qualquer número do piloto ser lido. Um primeiro piloto em CPU foi interrompido, e sua saída não foi lida, quando os embeddings passaram para a GPU. O piloto (`--pilot`) roda depois deste commit e mede só o tempo de execução, o baseline lexical em 200 consultas e um teste de sanidade dos embeddings num mini-índice. Nada aqui foi ajustado a resultados. Este arquivo entra no mesmo commit do código que gera os resultados (`experiments/exp01_normalization.py`). Mudanças posteriores só podem ser acrescentadas na seção "Desvios", com data e motivo.

## Pergunta

Para um termo em português (rótulo PT oficial do HPO), uma busca **só nos textos em inglês** do HPO (rótulo + sinônimos) encontra o ID certo? Esse é o cenário dos ~64% de termos que não têm tradução PT.

## Dados e versões

- HPO v2026-09-01 (`hp.json`, `hp-pt.babelon.tsv` do mesmo tag). Os sha256 estão em `data/raw/MANIFEST.json` e são copiados em `config.json`.
- **Consultas:** 7.154 rótulos PT oficiais de termos ativos (filtro `hpo.pt_labels`).
- **Escopo principal:** as 6.976 consultas cujo termo está sob HP:0000118 (Phenotypic abnormality). As 178 restantes (herança, frequência, modificadores clínicos, o próprio HP:0000118) aparecem numa linha separada e não entram em nenhuma hipótese.
- **Gabarito:** o ID HPO de cada rótulo.

## Métodos (fixados antes dos resultados)

| Nome | O que é |
|---|---|
| `lexical_token_sort` | rapidfuzz `token_sort_ratio`, textos em minúsculas, sem acentos e com não-alfanuméricos trocados por espaço. **Baseline.** |
| `e5-base` | `intfloat/multilingual-e5-base`, prefixo `query: ` nos dois lados (tarefa simétrica, como recomenda o card do modelo). **Esquema principal do e5.** |
| `e5-base_qp` | O mesmo modelo, com `query: ` na consulta e `passage: ` no índice. Variante. |
| `mpnet-multi` | `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` |
| `bge-m3` | `BAAI/bge-m3` (densa), no conjunto completo, como os demais. |

Os embeddings são calculados na GPU (CUDA, pesos em fp32, `max_seq_length` = 128), e o device fica registrado em `config.json`. A pontuação (produto interno de vetores normalizados) e o ranqueamento rodam em CPU.

**Índice:** só textos em inglês de todos os 19.894 termos ativos.
- **Principal (`exact`):** rótulo + sinônimos exact.
- **Ablação (`all_scopes`):** rótulo + sinônimos exact, related, broad e narrow.

**Ranqueamento:**
- A unidade é o ID único; a pontuação de um ID é o máximo entre os seus textos.
- **Empates contam contra o acerto:** posição pessimista = número de IDs com pontuação ≥ à do ID correto. A posição otimista e a taxa de empate no topo saem separadas.
- **Near-miss** = o ID correto fica estritamente abaixo do topo, e todos os IDs no topo são pai ou filho direto (is_a) do correto. É reportado à parte e nunca somado ao top-k.

## Desfecho primário

**Top-1 com empate pessimista, índice `exact`, escopo principal (n = 6.976).**

Secundários: top-5, top-10, top-1 otimista, taxa de empate no topo, near-miss.

## Teste estatístico

McNemar exato (binomial) no acerto top-1, pareado por consulta, com correção de Holm sobre estas 4 comparações (lista `PRIMARY_COMPARISONS` no script). α = 0,05.

1. `e5-base` vs `mpnet-multi`
2. `mpnet-multi` vs `lexical_token_sort`
3. `e5-base` vs `lexical_token_sort`
4. `bge-m3` vs `e5-base` (só se o bge-m3 rodar; se não rodar, Holm usa 3 comparações)

## Hipóteses

Todas se referem ao desfecho primário, salvo indicação.

- **H1 (ordenação):** `bge-m3` > `e5-base` > `mpnet-multi` > `lexical_token_sort` no top-1. Confirmada para cada par se a diferença tiver o sinal previsto e p_Holm < 0,05.
- **H2 (cognatos idênticos):** no subconjunto `main_identical` (n = 95, rótulo PT sem acento e em minúsculas idêntico a um texto inglês do termo), todos os métodos têm top-1 ≥ 85%.
- **H3 (não idênticos):** no subconjunto `main_nonidentical` (n = 6.881), o lexical tem top-1 ≤ 40%. O melhor embedding fica pelo menos 30 pontos abaixo do seu próprio top-1 em `main_identical`.
- **H4 (espaço para reranqueamento):** para o melhor embedding, top-10 − top-1 ≥ 15 pontos. Isso sustentaria um Exp 03 que reordena candidatos.
- **H5 (traduções desatualizadas):** `main_stale` (n = 227) tem top-1 menor que `main_current` para o melhor embedding. Só a direção; n pequeno, IC largo.
- **H6 (ablação de sinônimos):** para cada método, top-1 em `all_scopes` ≤ top-1 em `exact`, com |Δ| ≤ 3 pontos.
- **H7 (prefixos do e5):** top-1 de `e5-base` ≥ top-1 de `e5-base_qp`.
- **H8 (erros hierárquicos):** para o melhor embedding, near-miss ≥ 20% dos erros de top-1 no escopo principal.

## Análises exploratórias (sem hipótese)

- Acurácia por ramo de topo de HP:0000118. Um termo em vários ramos conta em cada um.
- Acerto em função de `surface_sim` (similaridade de superfície entre o rótulo PT e o texto inglês mais próximo do termo correto).
- Leitura qualitativa dos 200 piores erros por método (`errors.csv`).

## Ameaças à validade (registradas antes)

- Rótulos PT oficiais são curtos e limpos. Texto de prontuário é muito mais difícil, então os números aqui são um **teto otimista** para normalização de termo isolado.
- Algumas traduções usam grafia de Portugal. Isso pode penalizar ou não os modelos; não há como separar sem anotação manual.
- Os modelos de embedding podem ter visto o HPO (inclusive traduções) no pré-treino.

## Desvios

- **25/out/2026, tamanho dos subconjuntos:** os n de `main_identical` (95) e `main_nonidentical` (6.881) citados acima vieram de uma exploração anterior ao código. Ela usava uma normalização sem a troca de pontuação por espaço. A definição implementada (`retrieval.fold`, commitada antes dos resultados) dá **96 e 6.880** (`config.json` → `queries.n_main_identical`). A definição e os critérios das hipóteses não mudam.
- **25/out/2026, análise por `surface_sim`** (`experiments/exp01_analysis.py`): faixas <50, 50–70, 70–85, 85–100 e idênticos, fixadas antes de ler a saída. A faixa "idênticos" usa a flag `identical`, porque `surface_sim` é gravado com 1 casa decimal e um par não idêntico pode arredondar para 100,0. Isso foi notado na primeira execução do script e corrigido antes de qualquer interpretação.
