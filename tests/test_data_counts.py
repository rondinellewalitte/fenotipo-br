"""Sanity checks on the downloaded files. Skipped when data/raw/ is empty.
Expected values (CLAUDE.md, HPO v2026-09-01): ~19,894 active terms, ~7,213 PT labels."""

import pytest

from hpolab.data import PPKT_ASSET, RAW_DIR, iter_phenopackets, phenopacket_case
from hpolab.hpo import load_babelon, load_ontology, summary

pytestmark = pytest.mark.data

HP_JSON = RAW_DIR / "hp.json"
BABELON = RAW_DIR / "hp-pt.babelon.tsv"

needs_hpo = pytest.mark.skipif(
    not (HP_JSON.exists() and BABELON.exists()), reason="run `python -m hpolab.data` first"
)


@needs_hpo
def test_hpo_counts_match_claude_md():
    s = summary(load_ontology(HP_JSON), load_babelon(BABELON))
    print(s)
    assert abs(s["active_terms"] - 19_894) / 19_894 < 0.05
    assert abs(s["babelon_label_rows"] - 7_213) / 7_213 < 0.05
    assert s["pt_labels_active"] <= s["babelon_label_rows"]


@needs_hpo
def test_phenotypic_abnormality_has_23_branches():
    ont = load_ontology(HP_JSON)
    assert len(ont.children["HP:0000118"]) >= 20


@pytest.mark.skipif(not (RAW_DIR / PPKT_ASSET).exists(), reason="phenopacket store missing")
def test_phenopacket_store_readable():
    n = 0
    for _, pp in iter_phenopackets():
        assert "id" in pp
        n += 1
    print(f"phenopackets: {n}")
    assert n > 9_000


def test_phenopacket_case_drops_excluded_and_reads_gene():
    pp = {
        "id": "PMID_1_Individual_1",
        "phenotypicFeatures": [
            {"type": {"id": "HP:0000252"}},
            {"type": {"id": "HP:0001250"}, "excluded": True},
            {"type": {"id": "HP:0001263"}, "excluded": False},
        ],
        "interpretations": [
            {
                "diagnosis": {
                    "disease": {"id": "OMIM:1", "label": "Some syndrome"},
                    "genomicInterpretations": [
                        {
                            "variantInterpretation": {
                                "variationDescriptor": {"geneContext": {"symbol": "ESAM"}}
                            }
                        }
                    ],
                }
            }
        ],
    }
    case = phenopacket_case("0.1.27/ESAM/PMID_1_Individual_1.json", pp)
    assert case["observed"] == ["HP:0000252", "HP:0001263"]
    assert (case["gene"], case["gene_source"], case["cohort"]) == ("ESAM", "variant", "ESAM")
    assert (case["disease_id"], case["disease_label"]) == ("OMIM:1", "Some syndrome")
    no_gene = phenopacket_case("0.1.27/11q_del/x.json", {"id": "x", "interpretations": []})
    assert (no_gene["gene"], no_gene["gene_source"]) == ("11q_del", "cohort_folder")
