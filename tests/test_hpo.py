import pandas as pd

from hpolab.hpo import iri_to_curie, parse_obographs, pt_labels

OBO = "http://purl.obolibrary.org/obo/"


def _node(num: str, lbl: str, **meta) -> dict:
    return {"id": f"{OBO}HP_{num}", "lbl": lbl, "type": "CLASS", "meta": meta}


def _edge(sub: str, obj: str) -> dict:
    return {"sub": f"{OBO}HP_{sub}", "pred": "is_a", "obj": f"{OBO}HP_{obj}"}


TOY = {
    "graphs": [
        {
            "meta": {"version": f"{OBO}hp/releases/2026-09-01/hp.json"},
            "nodes": [
                _node("0000001", "All"),
                _node("0000118", "Phenotypic abnormality"),
                _node("0000707", "Abnormality of the nervous system"),
                _node("0000152", "Abnormality of head or neck"),
                _node(
                    "0001250",
                    "Seizure",
                    synonyms=[
                        {"pred": "hasExactSynonym", "val": "Epileptic seizure"},
                        {
                            "pred": "hasRelatedSynonym",
                            "val": "Epilepsy",
                            "synonymType": f"{OBO}hp#layperson",
                        },
                    ],
                    basicPropertyValues=[
                        {
                            "pred": "http://www.geneontology.org/formats/oboInOwl#hasAlternativeId",
                            "val": "HP:0001275",
                        }
                    ],
                ),
                _node("0000252", "Microcephaly"),
                _node(
                    "0000057",
                    "obsolete Clitoromegaly",
                    deprecated=True,
                    basicPropertyValues=[{"pred": f"{OBO}IAO_0100001", "val": "HP:0000252"}],
                ),
                {"id": f"{OBO}RO_0002200", "type": "PROPERTY"},
            ],
            "edges": [
                _edge("0000118", "0000001"),
                _edge("0000707", "0000118"),
                _edge("0000152", "0000118"),
                _edge("0001250", "0000707"),
                _edge("0000252", "0000707"),
                _edge("0000252", "0000152"),
            ],
        }
    ]
}


def test_iri_to_curie():
    assert iri_to_curie(f"{OBO}HP_0000118") == "HP:0000118"


def test_parse_counts_and_version():
    ont = parse_obographs(TOY)
    assert ont.version == "2026-09-01"
    assert len(ont.terms) == 6
    assert "HP:0000057" not in ont.terms
    assert ont.obsolete == {"HP:0000057": "HP:0000252"}


def test_synonyms_scope_and_type():
    syn = parse_obographs(TOY).terms["HP:0001250"].synonyms
    assert [(s.text, s.scope, s.type) for s in syn] == [
        ("Epileptic seizure", "exact", None),
        ("Epilepsy", "related", "layperson"),
    ]


def test_resolve_alt_and_obsolete():
    ont = parse_obographs(TOY)
    assert ont.resolve("HP:0001250") == "HP:0001250"
    assert ont.resolve("HP:0001275") == "HP:0001250"
    assert ont.resolve("HP:0000057") == "HP:0000252"
    assert ont.resolve("HP:9999999") is None


def test_ancestors_branches_neighbors():
    ont = parse_obographs(TOY)
    assert ont.ancestors("HP:0001250") == {"HP:0000707", "HP:0000118", "HP:0000001"}
    assert ont.top_branches("HP:0000252") == {"HP:0000707", "HP:0000152"}
    assert ont.top_branches("HP:0000707") == {"HP:0000707"}
    assert ont.top_branches("HP:0000001") == frozenset()
    assert ont.is_neighbor("HP:0000707", "HP:0001250")
    assert ont.is_neighbor("HP:0001250", "HP:0000707")
    assert not ont.is_neighbor("HP:0000118", "HP:0001250")


def test_relation_categories():
    ont = parse_obographs(TOY)
    assert ont.relation("HP:0001250", "HP:0001250") == "same"
    assert ont.relation("HP:0000707", "HP:0001250") == "parent_child"
    assert ont.relation("HP:0000252", "HP:0001250") == "sibling"
    assert ont.relation("HP:0000118", "HP:0001250") == "ancestor_descendant"
    # Seizure (under nervous system) vs head-or-neck: common ancestor HP:0000118 is
    # 2 steps up from Seizure and 1 step up from HP:0000152
    assert ont.relation("HP:0001250", "HP:0000152") == "close_relative"
    assert ont.relation("HP:0001250", "HP:0000152", max_up=1) == "distant"
    assert ont.up_steps("HP:0001250") == {
        "HP:0001250": 0,
        "HP:0000707": 1,
        "HP:0000118": 2,
        "HP:0000001": 3,
    }


def test_pt_labels_filter_and_stale():
    ont = parse_obographs(TOY)
    bab = pd.DataFrame(
        [
            ["HP:0001250", "rdfs:label", "Seizure", "Convulsão", "OFFICIAL"],
            ["HP:0000252", "rdfs:label", "Small head", "Microcefalia", "OFFICIAL"],
            ["HP:0000057", "rdfs:label", "Clitoromegaly", "Clitoromegalia", "OFFICIAL"],
            ["HP:0000707", "IAO:0000115", "def", "definição", "OFFICIAL"],
            ["HP:0000152", "rdfs:label", "Abnormality of head or neck", "", "OFFICIAL"],
        ],
        columns=[
            "subject_id",
            "predicate_id",
            "source_value",
            "translation_value",
            "translation_status",
        ],
    )
    pt = pt_labels(bab, ont).set_index("hpo_id")
    assert sorted(pt.index) == ["HP:0000252", "HP:0001250"]
    assert pt.loc["HP:0001250", "pt_label"] == "Convulsão"
    assert not pt.loc["HP:0001250", "stale"]
    assert pt.loc["HP:0000252", "stale"]
