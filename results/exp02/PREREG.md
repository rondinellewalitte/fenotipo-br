# Exp 02: pré-registro

**Escrito em 25/out/2026, antes de qualquer cobertura ser calculada.** Até aqui só foram contados dados estruturais: 10.377 casos, 92.068 anotações observadas, 17 IDs alternativos ou obsoletos e 3 casos sem termo observado. Este arquivo entra no commit do código (`experiments/exp02_coverage.py`). Mudanças posteriores vão para "Desvios".

## Pergunta

Quanto da descrição fenotípica de casos reais de doença rara (Phenopacket Store v0.1.27) já tem rótulo PT oficial no HPO (v2026-09-01)? E quais termos sem tradução mais fazem falta?

## Definições

- **Termos de um caso:** os `phenotypicFeatures` com `excluded` ausente ou falso. Os excluídos não contam. Os IDs passam para o ID primário atual (`Ontology.resolve`: alt_id e replaced_by) e se contam uma vez por caso.
- **Termo traduzido:** o termo ativo tem rótulo PT oficial (`hpo.pt_labels`, 7.154 termos), inclusive os 227 desatualizados (`stale`). Uma variante secundária, `translated_current`, exclui os desatualizados.
- **Fração traduzida do caso:** termos traduzidos / termos observados. Os 3 casos sem termo observado ficam de fora das métricas por caso e são contados à parte.
- **Gene do caso:** o símbolo em `interpretations[].diagnosis.genomicInterpretations[].variantInterpretation.variationDescriptor.geneContext`. Se não houver, usa o nome da pasta da coorte (69 casos, deleções estruturais). Se houver vários genes, entram juntos, separados por `|`.
- **Doença do caso:** `interpretations[].diagnosis.disease` (ID e rótulo).

## Métricas

1. **% de casos com 100% dos termos traduzidos**, além de % com 0%.
2. **Distribuição da fração traduzida por caso:** média, mediana, quartis e histograma em faixas de 0,1, mais a faixa exata 1,0.
3. **Cobertura por anotação** (pares caso × termo) e **por termo distinto**.
4. **Por gene e por doença:** n de casos, fração média e % de casos 100% traduzidos (`by_gene.csv`, `by_disease.csv`). Grandes coortes dominam a média por caso, então também reporto a média das médias por gene.
5. **`missing_terms.csv`:** os 300 termos sem tradução que aparecem em mais casos. A ordem é n de casos decrescente, com empate pelo ID HPO. Colunas: n de genes, n de doenças e ramos.
6. **Ganho simulado:** as métricas 1–3 recalculadas como se os primeiros k termos da lista (k = 50, 100, 300) tivessem tradução. Isso mede o tamanho da proposta de contribuição ao HPO.
7. **Reconferência dos fatos do CLAUDE.md com `phenotype.hpoa`:**
   - **Cobertura das anotações de doença:** linhas com aspect = P e qualifier ≠ NOT, com IDs resolvidos.
   - **Rótulo PT entre os 500 termos mais usados:** "mais usado" é medido pelo n de doenças distintas anotadas.

## Expectativas (descritivas, sem teste)

- **E1:** cobertura por anotação entre 40% e 60%.
- **E2:** no máximo 10% dos casos com 100% dos termos traduzidos.
- **E3:** mediana da fração traduzida por caso entre 0,35 e 0,65.
- **E4:** traduzir os 300 primeiros termos de `missing_terms.csv` sobe a cobertura por anotação em pelo menos 15 pontos.
- **E5:** os números do `phenotype.hpoa` ficam perto dos do CLAUDE.md (~40% das anotações; ~193 de 500). Diferenças de definição ou de versão serão relatadas.

## Ameaças à validade

- Os casos vêm da literatura (inglês) e foram curados com termos HPO. Não representam a distribuição de termos num prontuário brasileiro.
- Grandes coortes de um único artigo pesam na média por caso.
- Ter rótulo PT oficial não garante que ele seja o termo usado na clínica brasileira (grafia de Portugal, termos pouco usuais).

## Desvios

- **25/out/2026, tolerância da E5:** o pré-registro dizia só "perto". A tolerância numérica usada em `expectations.json` (±3 pontos de cobertura e ±15 termos no top-500) foi fixada **depois** de ver os valores (40,3% e 193). Os valores coincidem com o CLAUDE.md, então a conclusão não depende da tolerância.
- **25/out/2026, checagem pontual fora do pipeline:** para confirmar que termos muito usados (Seizure, Hypotonia, Global developmental delay) não têm tradução, consultei `src/translations/hp-pt-not-translated.babelon.tsv` no mesmo tag v2026-09-01. Ele os marca como `NOT_TRANSLATED`. Esse arquivo não entra em nenhum número.
