<!-- Gerado por reports/build_email.py; não edite à mão. -->
# E-mail: Rede RARAS (rascunho, não enviado)

**Para:** [Nome], coordenação da Rede RARAS <[e-mail]>
**Anexos:** `reports/review/top50_terms.xlsx`, `reports/piloto.pdf`

```text
Assunto: Revisão de 50 termos do HPO sem tradução para o português (convite de coautoria)

Prezado(a) [Nome],

Sou Rondinelle Walitte, desenvolvedor independente, e estudo como descrever fenótipos de doenças raras em português com a Human Phenotype Ontology (HPO).

Num piloto com casos publicados na literatura (Phenopacket Store), só 38% das anotações de fenótipo têm rótulo oficial em português, e só 5,8% dos casos têm todos os fenótipos com esse rótulo. Faltam justamente termos muito comuns, como atraso global do desenvolvimento, deficiência intelectual e hipotonia. Traduzir os 50 mais frequentes elevaria a cobertura das anotações de fenótipo para ≈61% (estimativa fora da amostra).

É um piloto só com rótulos do HPO e casos da literatura: sem prontuários, sem dados de pacientes, e não é ferramenta clínica.

Meu pedido é um só: que um(a) geneticista da Rede RARAS revise esses 50 termos na planilha anexa, que já traz o termo em inglês, a definição e uma tradução automática para corrigir. Quem revisar será coautor(a) da submissão das traduções ao HPO e do artigo do piloto.

Relatório do piloto (PDF anexo); código e resultados: https://github.com/rondinellewalitte/fenotipo-br e https://doi.org/10.5281/zenodo.23662825

O projeto é de pesquisa aberta e não tem interesse comercial.

Atenciosamente,
Rondinelle Walitte
rondinellewalitte@gmail.com
ORCID 0009-0004-1776-2754
```

---

## NÃO ENVIAR: notas internas

Gerado em 2026-10-26 (commit `10109e1`). Assunto + corpo: **200 palavras** (limite 200).

**Números do e-mail e de onde vêm**

| No e-mail | Valor no arquivo | Arquivo e campo |
|---|---|---|
| 38% das anotações de fenótipo | 0.3831 | `results/exp02/metrics.json` → `coverage.annotation_coverage` |
| 5,8% dos casos com todos os fenótipos traduzidos | 0.0576 | `results/exp02/metrics.json` → `coverage.pct_cases_full` |
| ≈61% das anotações após os 50 termos | 0.3831 + 0.2226 = 0.6057 | `results/exp02/out_of_sample.json` → `gene_split.seeds_summary_annotation_coverage_gain.top50.oos_gain.mean` |

- O ≈61% é a cobertura atual mais o ganho médio fora da amostra em 20 divisões por gene: +22,3 p.p. (faixa +19,5 p.p. a +24,4 p.p.). Cada divisão mede o ganho na metade de teste; somar à cobertura da amostra toda é uma aproximação.
- Exemplos citados: HP:0001263, HP:0001249, HP:0001252, entre os 5 termos sem tradução mais frequentes (`results/exp02/missing_terms.csv`).

**Antes de enviar**

- Preencher `[Nome]` e `[e-mail]` com os dados de quem recebe (coordenação da Rede RARAS). Ajustar "Prezado(a)" ao nome.
- Conferir que https://github.com/rondinellewalitte/fenotipo-br está público e com o último commit, e que https://doi.org/10.5281/zenodo.23662825 abre o registro no Zenodo.
- Anexar `reports/review/top50_terms.xlsx` e `reports/piloto.pdf`. Gerar o PDF de novo (`reports/build_piloto_pdf.py`) sempre que o `piloto.md` mudar.
