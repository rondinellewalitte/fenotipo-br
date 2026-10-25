# HPO-PTBR Lab

Research lab measuring how well Brazilian Portuguese clinical text maps to
[Human Phenotype Ontology](https://hpo.jax.org/) terms. Research support only; not a
clinical or diagnostic tool. See `CLAUDE.md` for the research questions and rules.

```bash
uv sync
uv run python -m hpolab.data    # download HPO + Phenopacket Store into data/raw/
uv run python -m hpolab.hpo     # summary: active terms, PT label coverage
uv run pytest
```

Data sources: HPO (obophenotype/human-phenotype-ontology) and Phenopacket Store
(monarch-initiative/phenopacket-store), each under its own license.
