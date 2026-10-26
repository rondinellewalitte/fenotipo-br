# Exp 03: pré-registro

**Escrito em 26/out/2026, antes de gerar qualquer vinheta e antes de qualquer chamada a modelo de linguagem.** Este arquivo entra no mesmo commit do código que gera os resultados (`experiments/exp03_vignettes.py`, `experiments/exp03_extraction.py`, `src/hpolab/{vignettes,extraction,casemetrics,ollama,gpu}.py`) e dos prompts v1 em `prompts/exp03_*`. Mudanças posteriores só entram em "Desvios", com data e motivo.

**O que foi visto antes de escrever:**
- Contagens estruturais do Phenopacket Store: 10.377 casos; 7.770 elegíveis; 632 genes elegíveis; termos excluídos por caso elegível com mediana 6, p90 29 e máximo 174.
- O tamanho dos prompts do gerador nos casos sorteados: média de ~5.100 caracteres; os itens por vinheta têm média 10,5 no piloto e 11,4 no run completo, com máximo 20.
- As páginas de tags do Ollama (qwen3, gemma3).
- O log de custo do pacote de revisão (`results/review/llm_calls.jsonl`).
- Os resultados já publicados do Exp 01 e do Exp 02.

Nenhuma vinheta, extração ou métrica do Exp 03 existia.

## Perguntas

1. Em texto clínico em português do Brasil, extrair e mapear direto em PT (braço A) é tão bom quanto traduzir para o inglês antes (braço B)? Pergunta 1 do projeto.
2. Quanto um índice que também contém os rótulos PT oficiais (braço C) melhora sobre o índice só em inglês? Liga-se à pergunta 2 do projeto, a tradução PT incompleta.
3. Quanto um LLM local pequeno (4B, numa GPU de notebook de 6 GB) acrescenta a um baseline só de embeddings?

O impacto no ranking de genes/doenças (pergunta 3 do projeto) fica fora deste experimento.

## Dados e versões

- HPO v2026-09-01 e Phenopacket Store 0.1.27. Os sha256 estão em `data/raw/MANIFEST.json` e são copiados em cada `config.json`.
- **Termos de um caso:** `phenotypicFeatures` com IDs resolvidos para o ID primário atual (`Ontology.resolve`), só termos sob HP:0000118 (o próprio HP:0000118 fica de fora).
  - Observados: `excluded` ausente ou falso.
  - Excluídos: `excluded` verdadeiro e o termo não está entre os observados.
- **Elegibilidade:** de 3 a 15 termos observados distintos (7.770 casos, 632 genes). "Gene" segue a definição do Exp 02: símbolo da variante; sem variante, o nome da pasta da coorte.
- **Sorteio** (`hpolab.vignettes.draw`, seed 42):
  - Os genes são ordenados e permutados.
  - Para cada gene, sorteia-se um caso entre os elegíveis do gene, ordenados por `case_id`.
  - Os 50 primeiros genes formam o **piloto**, os 300 seguintes o **run completo** e os 282 restantes a **reserva** para substituições, usada na ordem.
  - Piloto, run completo e reserva não compartilham gene nem caso. Nenhum gene, nem STXBP1, aparece mais de uma vez.
  - Saída: `results/exp03/sample.csv`.
- **Gabarito:** os termos observados do caso.
- **Negações:**
  - Dos termos excluídos, descartam-se os que são ancestrais ou descendentes (is_a) de um termo observado: "sem crises" ao lado de "crises focais" contradiria a nota.
  - Dos restantes, sorteiam-se **até 5** por caso (gerador por caso: seed 42 + `case_id`). Eles entram na vinheta como ausentes.
  - Esperado: 3,1 por caso no piloto e 3,2 no run completo; 18% dos casos sem nenhuma negação.
  - Se forem extraídos, contam como falso positivo.

## Vinhetas em PT-BR

- **Gerador:** `claude-opus-5-5` pela API da Anthropic, esforço `low`, `max_tokens` 4.000, saída JSON validada por esquema.
  - Prompt: `prompts/exp03_vignette_pt_br_v1.{system,user}.md`. O sha256 vai em cada registro.
  - Desde 21/out/2026 a API não aceita temperatura. A reprodutibilidade vem do modelo fixo, do prompt versionado e das saídas gravadas em `results/exp03/vignettes.jsonl`. Uma vinheta aprovada nunca é pedida de novo.
- **O que o gerador vê:** sexo, idade no último atendimento (quando houver) e, para cada item, o rótulo inglês e a definição. Os itens são numerados: 1..n presentes, N1..Nk ausentes. Ele não vê IDs HPO, doença, gene, variante, PMID nem ID do caso.
- **O que se pede:**
  - Uma anamnese de primeira consulta como a escreveria um médico brasileiro.
  - Cada item com o mesmo conceito e a mesma especificidade, descrito em linguagem clínica brasileira e não traduzido palavra por palavra.
  - Mistura de registros: relato da família e termos técnicos.
  - Nada clínico além dos itens: nem achado normal, nem diagnóstico, gene ou síndrome.
  - Nenhum ID nem rótulo inglês. No máximo 350 palavras.
  - Para cada item, a frase exata do texto que o expressa.
- **Checagem automática** (`hpolab.vignettes.check_vignette`). A vinheta é **reprovada** se tiver:
  - ID HPO (`HP:0001250`, `HP_0001250`, `HP 0001250`) ou a palavra "HPO";
  - ID de doença (`OMIM:`, `MONDO:`, `ORPHA:`);
  - o rótulo inglês de algum item, como string exata entre limites de palavra. A comparação ignora maiúsculas, mas **mantém os acentos**: "hematúria" não conta como "Hematuria". Exceção: rótulos que aparecem dentro de algum rótulo PT oficial do HPO, que são cognatos atestados em português, como "Ataxia" e "Glaucoma";
  - o símbolo do gene do caso;
  - item sem frase, ou frase que não aparece literalmente no texto.
  
  **Avisos**, que não reprovam: palavras funcionais inglesas (the, of, with…), mais de uma frase para o mesmo item, comprimento fora de 60–600 palavras.
- **Reprovação:** nova tentativa, no máximo 2 por caso. Com duas reprovações, o caso é substituído pelo próximo gene da reserva. Todas as tentativas ficam no jsonl.
- **Custo:**
  - Trava de **US$ 5**, somada sobre todas as chamadas do Exp 03 (`results/exp03/llm_calls.jsonl`, com tokens e custo por chamada). O pior caso é conferido antes de cada chamada.
  - Estimativa feita antes, com o tamanho real dos prompts e o log do pacote de revisão: ~1.400 tokens de entrada e ~900 de saída por vinheta, ~US$ 0,024 cada. Isso dá ~US$ 1,2 no piloto e ~US$ 7 no run completo.
  - **A trava cobre o piloto, não o run completo.** O custo real do piloto e a projeção para 300 serão informados antes de gerar o run completo. Qualquer mudança (trava, Batches API, modelo) vira desvio registrado antes de gerar as 300.
- **Separação:** o gerador (Claude) nunca é extrator neste experimento. Na extração, nada além do campo `vignette` chega aos modelos.

## Braços

Os dois modelos locais rodam nos braços A, B e C, via Ollama, com **tags explícitas**. O alias `qwen3:4b` aponta hoje para a variante *thinking*, que não serve aqui.

- `qwen3:4b-instruct-2507-q4_K_M` (Qwen3-4B Instruct 2507, Q4_K_M)
- `gemma3:4b-it-q4_K_M` (Gemma 3 4B IT, Q4_K_M)

**Configuração das chamadas:**
- Ficam no `config.json`: o digest sha256 completo (`/api/tags`), a versão do Ollama e os detalhes do modelo.
- Opções: `temperature` 0, `seed` 42, `num_ctx` 4096. `num_predict`: 2.048 na tradução, 1.024 na extração e 64 na escolha.
- Extração e escolha usam saída JSON restrita por esquema (`format` do Ollama).
- Toda chamada fica em `ollama_calls.jsonl.gz` e é reaproveitada em execuções posteriores.

**Recuperação:**
- Modelo `BAAI/bge-m3`, densa, fp32, `max_seq_length` 128, como no Exp 01.
- Top-10 IDs únicos. A pontuação de um ID é o máximo entre os seus textos.
- **Índice EN:** rótulo + sinônimos exact, como o índice principal do Exp 01, **restrito aos termos sob HP:0000118**. Isso é um desvio em relação ao Exp 01, que indexou os 19.894 termos ativos: o gabarito só tem termos sob HP:0000118, e termos de herança, início ou modificador no índice só gerariam falso positivo.
- **Índice bilíngue:** o índice EN mais os rótulos PT oficiais (`hpo.pt_labels`) dos termos sob HP:0000118.

| Braço | O que faz |
|---|---|
| **A** (direto em PT) | O LLM extrai os achados presentes e ausentes, em PT (`exp03_extract_v1`). Cada achado presente passa pelo bge-m3 (top-10 no índice EN). O LLM escolhe um candidato ou NONE (`exp03_select_v1`), com a resposta restrita aos 10 IDs + NONE. |
| **B** (traduz antes) | O mesmo LLM traduz a vinheta para o inglês (`exp03_translate_pt_en_v1`). Seguem a mesma extração (mesmo prompt), a mesma busca e a mesma escolha, sobre o texto inglês. |
| **C** (índice bilíngue) | Reaproveita a extração do A (mesmas frases, mesma chamada) e busca no índice bilíngue. A escolha é a mesma. |
| **Baseline** (sem LLM) | A vinheta PT é dividida em frases e orações: ponto, `;`, `:`, quebra de linha e vírgula, exceto a vírgula decimal (`hpolab.extraction.segments`). Cada segmento passa pelo bge-m3 (top-1 no índice EN), e o ID entra se o escore for ≥ τ. Sem tratamento de negação. |

**Regras comuns:**
- **O que o seletor vê:** o achado e, para cada candidato, o ID e o rótulo inglês, igual em A, B e C. Assim C difere de A só no conjunto de candidatos.
- **Predição do caso:** o conjunto de IDs escolhidos. Vários achados no mesmo ID contam uma vez. Os achados que o LLM lista como ausentes não são mapeados.
- **τ do baseline:** escolhido no piloto, na grade 0,30–0,95 com passo 0,01, maximizando o F1 micro do baseline nos 50 casos. Empate vai para o maior τ. O valor é congelado em `results/exp03/frozen.json` antes do run completo.

**Estágios.** A GPU de 6 GB não comporta o LLM e o bge-m3 juntos, então a execução tem quatro passos:
1. bge-m3: embeddings do índice, baseline e oráculo de frases.
2. Para cada modelo, o LLM traduz e extrai.
3. bge-m3: busca.
4. O LLM escolhe.

O modelo é descarregado ao fim de cada estágio.

**Tempo por caso:**
- Soma das chamadas Ollama do braço para o caso, cada uma contada como `total_duration` − `load_duration`, mais o tempo de busca rateado por achado.
- O braço C inclui a extração do A.
- O tempo de carga dos modelos é relatado à parte.

**VRAM:** pico de `memory.used` (nvidia-smi) por estágio, na GPU inteira, incluindo ~0,7 GB do vídeo, mais o `size_vram` do Ollama.

## Desfechos

**Primário:** F1 micro por termo, com match exato do ID HPO, comparando A e B em cada modelo.
- A diferença A − B é pareada por caso.
- O intervalo vem de bootstrap de casos (10.000 reamostragens, seed 42, percentil). A mesma matriz de reamostragem serve a todas as comparações.

**Secundários,** por braço e modelo:
- Precisão, recall e F1 micro.
- Precisão, recall e F1 macro: média por caso. Um caso sem predição tem precisão 0.
- **Taxa de FP em negação:** termos negados previstos / termos negados mostrados, com IC95 por bootstrap de casos.
- **Near-miss hierárquico:** FP que é pai ou filho direto (is_a) de um FN do mesmo caso, com pareamento 1:1. Sai separado, junto com um F1 "relaxado" que nunca vai para o título.
- **Mesma lesão, extremidade errada:** um FP e um FN do mesmo caso cujos rótulos ficam idênticos quando se neutralizam as palavras de mão/pé e de membro superior/inferior (`casemetrics.is_hand_foot_swap`).
- Segundos por caso (média, mediana, p90) e VRAM.

**Diagnósticos (sem hipótese):**
- Teto de recuperação: fração dos termos do gabarito que aparecem entre os candidatos de algum achado. Perda na escolha: teto − recall.
- Achados e ausentes por caso, taxa de NONE, falhas de JSON, saídas truncadas e chamadas com contexto cheio.
- Categorias de FP: negado, pai/filho, irmão, ancestral/descendente, parente próximo, distante, com as definições do Exp 01.
- Oráculo de frases: bge-m3 aplicado à frase do gerador para cada termo do gabarito, top-1/top-10 no índice EN, sem LLM.
- Recall por estrato (seção seguinte).
- Comparação entre os dois modelos, só exploratória.

Saídas: `config.json`, `metrics.json`, `predictions.jsonl`, `errors.csv` (cada FP e FN com categoria, frase de origem e se o termo era recuperável) e, no run completo, `hypotheses.json`. O piloto grava em `results/exp03/pilot/` e o run completo em `results/exp03/`.

## Estratos: ameaça da retrotradução

O gerador escreve em PT a partir dos rótulos ingleses. Ao traduzir de volta, um modelo pequeno pode recuperar quase literalmente o rótulo inglês. Isso facilitaria B artificialmente em relação a uma nota brasileira real. C se beneficia do mesmo jeito quando a frase coincide com o rótulo PT oficial.

Para cada termo do gabarito, ficam gravados:
1. se tem rótulo PT oficial;
2. se a frase do gerador é igual ao rótulo PT oficial (ignorando maiúsculas e espaços);
3. a similaridade de superfície (rapidfuzz `ratio` sobre `fold`) entre a frase e o rótulo inglês, nas faixas <50, 50–80 e ≥80.

O recall de cada braço por estrato e a diferença A − B dentro de cada estrato são relatados de forma descritiva. A mitigação no prompt é pedir a descrição de um médico brasileiro, não a tradução do rótulo.

## Hipóteses

São julgadas **só no run completo** (n = 300) e por modelo. No H1, a decisão usa o IC 97,5% (Bonferroni para 2 modelos, α familiar 0,05). As secundárias usam IC95 sem ajuste e são relatadas como secundárias. Os critérios estão implementados em `evaluate_hypotheses` (`experiments/exp03_extraction.py`).

- **H1 (primária, não inferioridade):** para cada modelo, o limite inferior do IC 97,5% de F1(A) − F1(B) fica acima de **−0,03**. Só é confirmada no experimento se valer nos dois modelos. Se o intervalo excluir zero, em qualquer direção, a superioridade também será relatada.
- **H2 (índice bilíngue):** para cada modelo, F1(C) − F1(A) > 0, com limite inferior do IC95 > 0, e diferença ≤ **0,05**.
- **H3 (LLM vs. baseline):** para cada modelo, F1(A) − F1(baseline) ≥ **0,05**, com limite inferior do IC95 > 0.
- **H4 (negação):** para cada modelo, a taxa de FP em negação do A fica ≤ **0,10**, e a do baseline ≥ **0,25**.
- **H5 (teto e escolha):** para cada modelo, no braço A, o teto de recuperação fica ≥ **0,75** e a perda na escolha ≥ **0,10**.

**Expectativas** (descritivas, sem teste):
- **E1:** F1 micro do A entre 0,35 e 0,65 nos dois modelos.
- **E2:** near-miss responde por ≥ 10% dos FP do A.
- **E3:** as trocas mão↔pé ficam em ≤ 2% dos FP do A.
- **E4:** mediana de segundos por caso ≤ 30 s no A; no B, ≥ 1,5× a do A.
- **E5:** no A, o recall é maior nos termos com rótulo PT oficial do que nos sem rótulo. O ganho de C sobre A é maior nos termos com rótulo PT.

## Piloto e congelamento

- **O que o piloto roda:** os 50 casos nos 4 braços e nos 2 modelos.
- **Para que serve:**
  - medir tempo e VRAM;
  - verificar o contexto de 4.096 tokens e as falhas de formato;
  - escolher τ;
  - ajustar os prompts de tradução, extração e escolha.
- **Versões de prompt:** cada uma é um arquivo novo (`_v2`, …), commitado antes de rodar e registrado em "Desvios" com o motivo. Os resultados do piloto de cada versão ficam no histórico do git.
- **O que não muda depois deste commit**, salvo desvio registrado: amostra, braços, modelos e tags, índices, top-10, métricas, hipóteses, número de reamostragens.
- **Prompt do gerador:**
  - Só muda se a revisão humana das 5 vinhetas sorteadas do piloto pedir.
  - Nesse caso, as 50 vinhetas do piloto são refeitas com a nova versão.
  - Fica congelado antes de gerar as 300.
- **Congelamento:**
  - `--freeze` grava `frozen.json` com as versões e os sha256 dos prompts, τ e os modelos.
  - O run completo se recusa a rodar se algum prompt for diferente do congelado, ou se `src/`, `experiments/` ou `prompts/` tiverem mudanças não commitadas.
- Números do piloto nunca entram nas hipóteses.

## Ameaças à validade

- **Texto sintético.** As vinhetas são escritas por um LLM a partir de listas curadas, não são prontuários brasileiros. Faltam erros de digitação, abreviações locais variadas e contexto desorganizado. Os números valem para um cenário controlado e tendem a ser otimistas.
- **Contaminação.**
  - Os casos vêm de artigos publicados. O gerador pode ter visto o artigo e acrescentar detalhes; o prompt proíbe isso, e a checagem automática pega só parte.
  - Os modelos locais podem ter visto os artigos ou o próprio Phenopacket Store, com termos HPO. Eles só recebem o texto PT novo, sem IDs.
- **Retrotradução:** ver a seção de estratos.
- **Fidelidade da vinheta.** A frase do gerador pode deslocar o conceito para um termo mais geral ou mais específico. Mitigações:
  - a frase tem de aparecer literalmente no texto;
  - revisão humana de 5 vinhetas do piloto;
  - oráculo de frases.
  
  Achados que o gerador acrescentar indevidamente contam como FP do extrator.
- **Determinismo.** Temperature 0 e seed fixa no Ollama; a GPU pode ter pequena variação numérica. Mitigação: as saídas ficam gravadas e são reaproveitadas.
- **Quantização.** Os resultados valem para as versões Q4_K_M desses modelos.
- **Tamanho.** No run completo, ~2.470 termos no gabarito e ~960 negações. No piloto, ~370 termos: serve para ajuste, não para conclusão.
- **Viés em experimento futuro.** Se o mesmo prompt de extração for usado depois com o Claude como extrator, ele estará lendo texto escrito pelo próprio Claude (familiaridade de estilo). Registrado aqui para esse experimento.

## Ética e licenças

- Somente dados públicos: Phenopacket Store (BSD 3-Clause) e HPO, com a licença e a citação em `NOTICE.md`.
- As vinhetas são texto sintético derivado de relatos publicados e desidentificados. Nenhum dado de paciente real.
- É apoio à pesquisa, não ferramenta diagnóstica.

## Desvios

(nenhum até aqui)
