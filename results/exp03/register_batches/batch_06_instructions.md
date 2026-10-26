You are labeling data for a research experiment. Work alone; do not run any experiment code, do not call any API, do not modify anything outside the output file named below.

Input: C:\Users\Rondinelle\PROJETOS\fenotipo-br\results\exp03\register_batches\batch_06_input.md
It contains 53 synthetic clinical notes in Brazilian Portuguese (## CASE <id>), each followed by its items: HPO id, English HPO label, official Portuguese HPO label (or "(none)"), and the phrase of the note that a generator said expresses the item. There are 468 items in total. Read the WHOLE note for each item, not only the phrase: an item may be mentioned more than once in a note (e.g. in lay words in the history and again with a medical term in the physical exam).

For every item, give three yes/no labels:

1. d1_technical: does the note (anywhere) contain, for this item, EITHER the official Portuguese label (allowing inflection: plural, gender, small word-order changes) OR a close Portuguese cognate of the English label, i.e. the same Greek/Latin-rooted word(s) with Portuguese spelling ("Hypotonia" -> "hipotonia", "Microcephaly" -> "microcefalia", "Cardiomyopathy" -> "cardiomiopatia")? For multi-word labels, the cognate must cover the label's meaningful words, not just one generic word. A translation that uses different roots does NOT count here ("Global developmental delay" -> "atraso global do desenvolvimento" is not a cognate; "Thrombocytopenia" -> "plaquetopenia" is not a cognate). If there is no official PT label, only the cognate test applies.

2. d2_technical: is the item expressed anywhere in the note with standard medical terminology, i.e. the name a physician would use for the finding in a chart or paper, with or without official label/cognate status? Abbreviations count ("CIV", "TDAH"). Examples that are technical: "atraso global do desenvolvimento", "plaquetopenia", "derrame pleural", "hipermobilidade articular", "fendas palpebrais oblíquas para baixo", "perímetro cefálico abaixo de -2 DP".

3. d2_lay: is the item ALSO or ONLY expressed anywhere in the note with everyday or descriptive wording that does not use the medical term (typically what the family reports, or a plain description of what is seen)? Examples: "demorou para sentar, andar e falar", "fica com manchas roxas fácil", "a pele parece sobrando", "olhos bem afastados", "o testículo não estava na bolsa".

Write a CSV (UTF-8, comma-separated, header exactly: case_id,hpo_id,d1_technical,d2_technical,d2_lay,evidence) to: C:\Users\Rondinelle\PROJETOS\fenotipo-br\results\exp03\register_batches\batch_06_labels.csv
Use yes/no values. evidence: the short quote(s) from the note you based the decision on, at most ~15 words, quoted with double quotes escaped per CSV rules. One row per item, all 468 items, in the input order. Every item must have at least one of d2_technical or d2_lay = yes (if you truly cannot find the item in the note, put no/no and write "NOT FOUND" in evidence).

When done, reply with: the row count, and the counts of yes for each of the three labels. Nothing else.
