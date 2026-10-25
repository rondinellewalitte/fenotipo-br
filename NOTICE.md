# Third-party notices

The MIT license in `LICENSE` covers the code in this repository only. The repository does
not redistribute the raw files below (they are downloaded into `data/raw/`, which is not
committed). Files under `results/` and `reports/` contain values derived from them, such as
HPO term IDs, labels, definitions and synonyms, and per-case counts. Those derived values
stay under the terms of their sources.

## Human Phenotype Ontology (HPO)

This product uses the Human Phenotype Ontology (version v2026-09-01).
Find out more at https://hpo.jax.org.

The HPO is distributed under its own license (`hp.json` points to
https://hpo.jax.org/app/license; the repository's `LICENSE.md` points to the same page).
Its files may be used if three conditions are met:

1. The HPO Consortium is acknowledged and cited.
2. Any HPO file shown publicly includes its date or version.
3. Neither the content of HPO files nor their logical relationships are altered.

Proposed additions and changes go to the HPO project through its issue tracker.

The Portuguese labels (`src/translations/hp-pt.babelon.tsv`) are part of the HPO
repository and fall under the same terms.

`phenotype.hpoa` includes annotations derived from OMIM and from Orphanet, and each carries
its own reuse terms. This project uses only aggregate counts from it, such as the number of
diseases per term.

Citation: Gargano MA, et al. The Human Phenotype Ontology in 2024: phenotypes around the
world. *Nucleic Acids Research* 52(D1):D1333–D1346. https://doi.org/10.1093/nar/gkad1005

## Phenopacket Store

Phenopacket Store v0.1.27 (https://github.com/monarch-initiative/phenopacket-store),
distributed under the BSD 3-Clause License. `results/exp02/cases.csv.gz` and the other
Exp 02 outputs contain values derived from it. The license text is reproduced below as it
requires.

Citation: Danis D, et al. A corpus of GA4GH phenopackets: Case-level phenotyping for
genomic diagnostics and discovery. *Human Genetics and Genomics Advances* 6(1):100371
(2025). https://doi.org/10.1016/j.xhgg.2024.100371

```
BSD 3-Clause License

Copyright (c) 2022, Monarch Initiative

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## Embedding models

`BAAI/bge-m3`, `intfloat/multilingual-e5-base` and
`sentence-transformers/paraphrase-multilingual-mpnet-base-v2` are downloaded from Hugging
Face at the revisions recorded in `results/exp01/config.json`. They are not redistributed
here, and each model is under the license on its model card.
