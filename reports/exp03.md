# Exp 03: extração de fenótipos de vinhetas em PT-BR com LLMs locais (run completo)

R. Walitte (ORCID 0009-0004-1776-2754). Gerado por `reports/build_exp03.py` a partir de `results/exp03`. Código: `f187e1f`. Pré-registro: `results/exp03/PREREG.md`.

> **Apoio à pesquisa, não é ferramenta diagnóstica.** Nada aqui deve orientar conduta clínica (ANVISA RDC 657/2022). As vinhetas são sintéticas, derivadas de casos publicados; não há dado de paciente.

## Pergunta

Em texto clínico em português do Brasil, um LLM pequeno que roda localmente (4B parâmetros, GPU de notebook com 6 GB) extrai os fenótipos e os mapeia para o HPO:

- **direto em português** (braço A) tão bem quanto **traduzindo antes para o inglês** (B)?
- melhor quando o índice de busca também tem os **rótulos PT oficiais** (C)?
- melhor que uma busca só por embeddings, **sem LLM** (baseline)?

## Dados e métodos

- **Casos:** 300 casos do Phenopacket Store 0.1.27, um por gene, com 3 a 15 termos observados; HPO v2026-09-01.
  - Gabarito: 2.466 termos. Negações mostradas na vinheta: 959.
  - Termos fora do gabarito por falta de trecho na vinheta: 0. Casos trocados por reserva: 0.
- **Vinhetas:** escritas por `claude-opus-5-5` (prompt `exp03_vignette_pt_br_v2`), que nunca é extrator neste experimento.
  - Custo deste conjunto: US$ 7,12 em 308 chamadas. Gasto acumulado do Exp 03: US$ 9,60 (`results/exp03/vignettes_config_full.json`).
- **Extratores:** `qwen3:4b-instruct-2507-q4_K_M` (0edcdef34593), `gemma3:4b-it-q4_K_M` (68ceab7e468a), via Ollama 0.40.11, temperatura 0, seed 42, contexto de 4.096 tokens. Prompts congelados após o piloto (`results/exp03/frozen.json`).
- **Busca:** `BAAI/bge-m3`, 10 candidatos por achado entre os termos sob HP:0000118.
  - Índice EN: 41.466 textos. Índice bilíngue: 48.377 textos, incluindo 6.976 rótulos PT oficiais.
  - O seletor vê o achado e, para cada candidato, ID e rótulo inglês, igual nos três braços.
- **Desfecho primário:** F1 micro por termo, com ID exato, A contra B, pareado por caso.
  - Bootstrap de casos: 10.000 reamostragens, seed 42.
  - O H1 usa o IC 97,5% (dois modelos) com margem de não inferioridade de −0,03.
- **Registro clínico de cada termo (D2):** "só técnico", "só leigo" ou "ambos", rotulado às cegas antes da extração.
  - Conferência humana de 40 itens: kappa de Cohen 0,85 (IC95 0,700 a 0,963). O estrato é confirmatório (`results/exp03/pilot/register_kappa.json`).

## Resultados

### Resultado principal

| Modelo | Braço | Precisão | Recall | F1 micro | F1 macro | FP em negação | s/caso (mediana) |
|---|---|---|---|---|---|---|---|
| Qwen3-4B Instruct 2507 | A, direto em PT | 0,482 | 0,577 | **0,525** | 0,527 | 4,9% | 10,9 |
| Qwen3-4B Instruct 2507 | B, traduz antes | 0,527 | 0,648 | **0,582** | 0,588 | 3,2% | 15,0 |
| Qwen3-4B Instruct 2507 | C, índice bilíngue | 0,472 | 0,572 | **0,517** | 0,523 | 4,9% | 10,9 |
| Gemma 3 4B | A, direto em PT | 0,451 | 0,386 | **0,416** | 0,412 | 6,9% | 6,9 |
| Gemma 3 4B | B, traduz antes | 0,489 | 0,424 | **0,454** | 0,453 | 5,5% | 11,0 |
| Gemma 3 4B | C, índice bilíngue | 0,430 | 0,368 | **0,396** | 0,393 | 6,7% | 7,0 |
| — | Baseline sem LLM (τ = 0,70) | 0,372 | 0,293 | **0,328** | 0,303 | 11,4% | 0,2 |

Fonte: `results/exp03/metrics.json`.

### Comparações pareadas

| Modelo | Comparação | Diferença de F1 | IC95 | IC 97,5% |
|---|---|---|---|---|
| Qwen3-4B Instruct 2507 | A − B | −0,056 | −0,073 a −0,039 | −0,076 a −0,036 |
| Qwen3-4B Instruct 2507 | C − A | −0,008 | −0,018 a 0,003 | −0,020 a 0,004 |
| Qwen3-4B Instruct 2507 | A − baseline | +0,198 | 0,176 a 0,219 | 0,173 a 0,222 |
| Qwen3-4B Instruct 2507 | B − baseline | +0,254 | 0,231 a 0,277 | 0,228 a 0,280 |
| Qwen3-4B Instruct 2507 | C − baseline | +0,190 | 0,169 a 0,211 | 0,166 a 0,213 |
| Gemma 3 4B | A − B | −0,038 | −0,059 a −0,018 | −0,062 a −0,015 |
| Gemma 3 4B | C − A | −0,019 | −0,032 a −0,007 | −0,034 a −0,005 |
| Gemma 3 4B | A − baseline | +0,088 | 0,067 a 0,110 | 0,063 a 0,113 |
| Gemma 3 4B | B − baseline | +0,126 | 0,100 a 0,153 | 0,096 a 0,157 |
| Gemma 3 4B | C − baseline | +0,069 | 0,048 a 0,090 | 0,045 a 0,093 |

Fonte: `results/exp03/metrics.json` → `comparisons`.

### Hipóteses pré-registradas

| Hipótese | Qwen3-4B Instruct 2507 | Gemma 3 4B | Nos dois |
|---|---|---|---|
| `H1_A_noninferior_to_B_margin_0.03` | não | não | **não** |
| `H2_C_better_than_A_gain_le_0.05` | não | não | **não** |
| `H3_A_beats_baseline_by_0.05` | sim | sim | **sim** |
| `H4_negation_A_le_0.10_baseline_ge_0.25` | não | não | **não** |
| `H5_ceiling_ge_0.75_selection_loss_ge_0.10` | não | não | **não** |
| `H6_lay_harder_than_technical` | sim | sim | **sim** |

| Expectativa (descritiva) | Qwen3-4B Instruct 2507 | Gemma 3 4B |
|---|---|---|
| `E1_A_f1_in_0.35_0.65` | sim | sim |
| `E2_near_miss_ge_0.10_of_fp` | sim | sim |
| `E3_hand_foot_le_0.02_of_fp` | sim | sim |
| `E4_time` | não | sim |
| `E5_pt_label_strata` | sim | sim |
| `E6_A_vs_B_gap_larger_in_lay` | não | sim |
| `E7_C_vs_A_gain_larger_in_technical` | não | não |
| `E8_baseline_drop_larger_than_A` | não | não |

Fonte: `results/exp03/hypotheses.json`. Critérios em `results/exp03/PREREG.md`.

### Traduzir antes ajuda onde? Estratos de retrotradução

A ameaça pré-registrada: o gerador escreveu em português a partir do rótulo inglês, e traduzir de volta pode recuperar esse rótulo de forma artificial. Se fosse isso, a vantagem do B ficaria nas frases parecidas com o rótulo inglês (similaridade ≥ 80).

| Modelo | Estrato | n | Recall A | Recall B | Recall C | A − B |
|---|---|---|---|---|---|---|
| Qwen3-4B Instruct 2507 | similaridade com o rótulo inglês < 50 | 1894 | 0,526 | 0,609 | 0,527 | −0,083 |
| Qwen3-4B Instruct 2507 | similaridade com o rótulo inglês 50–80 | 472 | 0,725 | 0,765 | 0,691 | −0,040 |
| Qwen3-4B Instruct 2507 | similaridade com o rótulo inglês ≥ 80 | 100 | 0,850 | 0,840 | 0,860 | +0,010 |
| Qwen3-4B Instruct 2507 | frase = rótulo PT oficial | 199 | 0,804 | 0,784 | 0,854 | +0,020 |
| Qwen3-4B Instruct 2507 | frase ≠ rótulo PT oficial | 2267 | 0,557 | 0,636 | 0,547 | −0,079 |
| Qwen3-4B Instruct 2507 | termo com rótulo PT | 975 | 0,612 | 0,678 | 0,661 | −0,066 |
| Qwen3-4B Instruct 2507 | termo sem rótulo PT | 1491 | 0,554 | 0,629 | 0,513 | −0,075 |
| Gemma 3 4B | similaridade com o rótulo inglês < 50 | 1894 | 0,325 | 0,381 | 0,314 | −0,056 |
| Gemma 3 4B | similaridade com o rótulo inglês 50–80 | 472 | 0,568 | 0,553 | 0,515 | +0,015 |
| Gemma 3 4B | similaridade com o rótulo inglês ≥ 80 | 100 | 0,690 | 0,620 | 0,700 | +0,070 |
| Gemma 3 4B | frase = rótulo PT oficial | 199 | 0,704 | 0,658 | 0,719 | +0,045 |
| Gemma 3 4B | frase ≠ rótulo PT oficial | 2267 | 0,358 | 0,403 | 0,337 | −0,045 |
| Gemma 3 4B | termo com rótulo PT | 975 | 0,493 | 0,517 | 0,516 | −0,024 |
| Gemma 3 4B | termo sem rótulo PT | 1491 | 0,316 | 0,363 | 0,271 | −0,047 |

Fonte: `results/exp03/metrics.json` → `recall_by_stratum`.

### Linguagem leiga e técnica (registro clínico, D2)

| Modelo | Braço | Recall só técnico | Recall só leigo | Recall ambos | Técnico − leigo (IC95) |
|---|---|---|---|---|---|
| Qwen3-4B Instruct 2507 | A, direto em PT | 0,633 (n = 1447) | 0,412 (n = 645) | 0,644 (n = 374) | +0,221 (0,174 a 0,268) |
| Qwen3-4B Instruct 2507 | B, traduz antes | 0,722 (n = 1447) | 0,465 (n = 645) | 0,679 (n = 374) | +0,257 (0,210 a 0,305) |
| Qwen3-4B Instruct 2507 | C, índice bilíngue | 0,627 (n = 1447) | 0,408 (n = 645) | 0,642 (n = 374) | +0,219 (0,169 a 0,268) |
| Gemma 3 4B | A, direto em PT | 0,504 (n = 1447) | 0,102 (n = 645) | 0,420 (n = 374) | +0,402 (0,364 a 0,438) |
| Gemma 3 4B | B, traduz antes | 0,535 (n = 1447) | 0,160 (n = 645) | 0,449 (n = 374) | +0,375 (0,332 a 0,418) |
| Gemma 3 4B | C, índice bilíngue | 0,477 (n = 1447) | 0,105 (n = 645) | 0,396 (n = 374) | +0,372 (0,336 a 0,408) |
| — | Baseline | 0,338 (n = 1447) | 0,153 (n = 645) | 0,358 (n = 374) | +0,184 (0,147 a 0,222) |

| Modelo | Grupo | A − B (IC95) | C − A (IC95) |
|---|---|---|---|
| Qwen3-4B Instruct 2507 | só técnico | −0,089 (−0,116 a −0,061) | −0,006 (−0,022 a 0,010) |
| Qwen3-4B Instruct 2507 | só leigo | −0,053 (−0,091 a −0,015) | −0,005 (−0,023 a 0,014) |
| Qwen3-4B Instruct 2507 | ambos | −0,035 (−0,081 a 0,011) | −0,003 (−0,035 a 0,029) |
| Gemma 3 4B | só técnico | −0,031 (−0,061 a −0,001) | −0,026 (−0,043 a −0,010) |
| Gemma 3 4B | só leigo | −0,057 (−0,089 a −0,026) | +0,003 (−0,011 a 0,017) |
| Gemma 3 4B | ambos | −0,029 (−0,073 a 0,015) | −0,024 (−0,055 a 0,006) |

**Termo do HPO presente no texto (D1, regra literal, descritivo):** a vinheta traz o rótulo PT oficial ou um cognato do rótulo inglês? É a pergunta sobre a tradução incompleta do HPO, não sobre linguagem leiga.

| Modelo | Braço | Recall: termo do HPO no texto (D1 técnico/ambos) | Recall: sem termo do HPO (D1 leigo) |
|---|---|---|---|
| Qwen3-4B Instruct 2507 | A, direto em PT | 0,715 (n = 670) | 0,526 (n = 1796) |
| Qwen3-4B Instruct 2507 | B, traduz antes | 0,742 (n = 670) | 0,614 (n = 1796) |
| Qwen3-4B Instruct 2507 | C, índice bilíngue | 0,722 (n = 670) | 0,516 (n = 1796) |
| Gemma 3 4B | A, direto em PT | 0,624 (n = 670) | 0,297 (n = 1796) |
| Gemma 3 4B | B, traduz antes | 0,610 (n = 670) | 0,354 (n = 1796) |
| Gemma 3 4B | C, índice bilíngue | 0,601 (n = 670) | 0,281 (n = 1796) |
| — | Baseline | 0,409 (n = 670) | 0,249 (n = 1796) |

Fonte: `results/exp03/metrics.json` → `register.d2` e `recall_by_stratum.register_d1`. Ressalva: o rotulador tende a marcar "ambos" em frases de fronteira, o que muda o nível absoluto de cada grupo, mas não a comparação entre braços (PREREG, Desvios).

### Onde se perde: busca, escolha e erros

| Modelo | Braço | Teto de recuperação | Perda na escolha | Achados/caso | NONE | Near-miss (% dos FP) | Mão↔pé (% dos FP) |
|---|---|---|---|---|---|---|---|
| Qwen3-4B Instruct 2507 | A, direto em PT | 0,736 | 0,159 | 10,9 | 6,7% | 18,1% | 0,1% |
| Qwen3-4B Instruct 2507 | B, traduz antes | 0,811 | 0,163 | 10,8 | 3,1% | 19,9% | 0,0% |
| Qwen3-4B Instruct 2507 | C, índice bilíngue | 0,738 | 0,167 | 10,9 | 5,9% | 19,4% | 0,1% |
| Gemma 3 4B | A, direto em PT | 0,537 | 0,151 | 7,2 | 0,1% | 18,5% | 0,0% |
| Gemma 3 4B | B, traduz antes | 0,587 | 0,163 | 7,3 | 0,1% | 22,5% | 0,0% |
| Gemma 3 4B | C, índice bilíngue | 0,536 | 0,168 | 7,2 | 0,1% | 20,3% | 0,1% |

- **Oráculo de frases:** com a frase exata do gerador, sem LLM, o bge-m3 põe o termo certo em 1º lugar em 49,5% e entre os 10 primeiros em 74,7% dos 2.466 termos.
- **Falsos positivos por categoria** e exemplos de cada erro: `results/exp03/errors.csv`.

### Custo computacional

- O pico de memória da GPU foi de 4.674 MiB, com a GPU inteira contada. Os modelos ficaram 100% na GPU.
- O run levou 4,1 h ao todo (`results/exp03/config.json`).

## Limitações

- **Texto sintético.** As vinhetas foram escritas por um LLM a partir de listas curadas. Não têm erros de digitação nem abreviações variadas, e a mesma queixa aparece em linguagem leiga e técnica de forma regular. Os números valem para esse cenário.
- **Contaminação.** Os casos vêm de artigos publicados. O gerador pode ter visto o artigo; os extratores podem ter visto o artigo ou o Phenopacket Store.
- **Retrotradução.** Ver a tabela de estratos acima.
- **Rótulos de registro.** Foram feitos por um agente e conferidos pelo autor, que não é clínico, com viés do rotulador para "ambos". A revisão por um geneticista está prevista no contato com a Rede RARAS.
- **Gerador e rotulador são o mesmo modelo** (`claude-opus-5-5`). O rotulador pode reconhecer o próprio jeito de escrever. O kappa com o autor cobre a maior parte desse risco; a checagem independente é a revisão por geneticista.
- **Quantização.** Os resultados valem para as versões Q4_K_M dos modelos.

## Próximos passos

1. **Exp 04:** o mesmo protocolo com o Claude via API como extrator (custo separado), sabendo que o texto foi escrito por um modelo da mesma família.
2. **Revisão por geneticista** das vinhetas e dos rótulos de registro.
3. **Notas clínicas reais em português** (SemClinBr, após o acordo de uso).
4. **Efeito dos erros de extração no ranqueamento de genes e doenças.**
