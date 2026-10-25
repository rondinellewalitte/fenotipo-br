<!-- Gerado por reports/build_email.py; não edite à mão. -->
# E-mail: Rede RARAS (rascunho, não enviado)

**Para:** [Nome], coordenação da Rede RARAS <[e-mail]>
**Anexo:** `reports/review/top50_terms.xlsx`

```text
Assunto: Revisão de 50 termos do HPO sem tradução para o português (convite de coautoria)

Prezado(a) [Nome],

Sou Rondinelle Walitte, desenvolvedor independente, e estudo como descrever fenótipos de doenças raras em português com a Human Phenotype Ontology (HPO).

Num piloto com casos publicados na literatura (Phenopacket Store), só 38% das anotações de fenótipo têm rótulo oficial em português, e só 5,8% dos casos têm todos os fenótipos com esse rótulo. Faltam justamente termos muito comuns, como atraso global do desenvolvimento, deficiência intelectual e hipotonia. Traduzir os 50 mais frequentes elevaria a cobertura das anotações de fenótipo para ≈61% (estimativa fora da amostra).

É um piloto só com rótulos do HPO e casos da literatura: sem prontuários, sem dados de pacientes, e não é ferramenta clínica.

Meu pedido é um só: que um(a) geneticista da Rede RARAS revise esses 50 termos na planilha anexa, que já traz o termo em inglês, a definição e uma tradução automática para corrigir. Quem revisar será coautor(a) da submissão das traduções ao HPO e do artigo do piloto.

Código e resultados: [link]

O projeto é de pesquisa aberta e não tem interesse comercial.

Atenciosamente,
Rondinelle Walitte Pedro de Jesus
ORCID 0009-0004-1776-2754
```

---

## NÃO ENVIAR: notas internas

Gerado em 2026-10-25 (commit `dc67e7f, com mudanças não commitadas`). Assunto + corpo: **195 palavras** (limite 200).

**Números do e-mail e de onde vêm**

| No e-mail | Valor no arquivo | Arquivo e campo |
|---|---|---|
| 38% das anotações de fenótipo | 0.3831 | `results/exp02/metrics.json` → `coverage.annotation_coverage` |
| 5,8% dos casos com todos os fenótipos traduzidos | 0.0576 | `results/exp02/metrics.json` → `coverage.pct_cases_full` |
| ≈61% das anotações após os 50 termos | 0.3831 + 0.2226 = 0.6057 | `results/exp02/out_of_sample.json` → `gene_split.seeds_summary_annotation_coverage_gain.top50.oos_gain.mean` |

- O ≈61% é a cobertura atual mais o ganho médio fora da amostra em 20 divisões por gene: +22,3 p.p., faixa +19,5 p.p. a +24,4 p.p.. Cada divisão mede o ganho na metade de teste; somar à cobertura da amostra toda é uma aproximação.
- Exemplos citados: HP:0001263, HP:0001249, HP:0001252, entre os 5 termos sem tradução mais frequentes (`results/exp02/missing_terms.csv`).

**Antes de enviar**

- Preencher `[Nome]` e `[e-mail]`. Ajustar "Prezado(a)" ao nome.
- Trocar `[link]` pelo endereço do repositório, que ainda não é público.
- Anexar `reports/review/top50_terms.xlsx`. O `reports/review/README.md` explica a revisão e pode ir junto.
