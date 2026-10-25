# Notas para o artigo

Decisões de método e limitações que precisam entrar no texto do artigo. Os números ficam fora daqui: o artigo cita os arquivos em `results/`.

## Métodos

- **Tradução candidata por LLM** (pacote de revisão, `reports/build_review.py`).
  - Modelo fixo (`claude-opus-5-5`), esforço `low`, saída JSON validada por esquema.
  - Prompt versionado em `prompts/translate_hpo_label_pt_br_v1.*.md`; o sha256 dele fica registrado.
  - Frase para os Métodos: "As saídas do modelo foram armazenadas e reutilizadas; a API não oferece mais controle de amostragem (temperatura)."
  - Custo e tokens por chamada: `results/review/llm_calls.jsonl`. Teto de US$ 2, conferido antes de cada chamada.
- **Pré-registro.** Hipóteses e desfechos do Exp 01 e do Exp 02 estão em `results/exp0*/PREREG.md`, commitados antes dos resultados. Análises pós-hoc estão datadas em "Desvios".

## Limitações

- **Viés de ancoragem na revisão.** O revisor vê a tradução candidata e tende a aprová-la. Mitigação: a planilha pede que ele corrija sem receio e marque "candidata aceita sem alteração". A taxa de aceitação é um teto do acerto da tradução automática, não uma medida independente. Uma avaliação sem viés exigiria tradução às cegas por um segundo revisor.
- As demais limitações do piloto estão em `reports/piloto.md`, seção Limitações.
