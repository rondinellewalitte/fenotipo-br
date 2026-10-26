"""Exp 03 building blocks on synthetic inputs: no network, no GPU, no downloaded data."""

import numpy as np
import pandas as pd
import pytest

from hpolab import casemetrics as cm
from hpolab import ollama
from hpolab.extraction import (
    NONE_ID,
    example_term_clashes,
    parse_extraction,
    parse_selection,
    segments,
    select_schema,
)
from hpolab.hpo import parse_obographs
from hpolab.register import classify, respell
from hpolab.retrieval import TermIndex, top_ids
from hpolab.vignettes import (
    MAX_NEGATED,
    age_text,
    case_record,
    check_vignette,
    draw,
    eligible,
    final_vignettes,
    impossible_in_portuguese,
    item_lines,
    items,
    label_leaks,
    negation_pool,
    pick_negated,
)

OBO = "http://purl.obolibrary.org/obo/"
TERMS = {
    "0000001": ("All", None),
    "0000118": ("Phenotypic abnormality", "0000001"),
    "0000006": ("Autosomal dominant inheritance", "0000001"),
    "0000707": ("Abnormality of the nervous system", "0000118"),
    "0001250": ("Seizure", "0000707"),
    "0007359": ("Focal-onset seizure", "0001250"),
    "0002121": ("Absence seizure", "0001250"),
    "0001252": ("Hypotonia", "0000707"),
    "0001251": ("Ataxia", "0000707"),
    "0040064": ("Abnormality of limbs", "0000118"),
    "0006101": ("Finger syndactyly", "0040064"),
    "0001770": ("Toe syndactyly", "0040064"),
    "0000790": ("Hematuria", "0000118"),
}


@pytest.fixture(scope="module")
def ont():
    nodes = [
        {"id": f"{OBO}HP_{n}", "lbl": lbl, "type": "CLASS", "meta": {}}
        for n, (lbl, _) in TERMS.items()
    ]
    nodes[4]["meta"]["basicPropertyValues"] = [
        {
            "pred": "http://www.geneontology.org/formats/oboInOwl#hasAlternativeId",
            "val": "HP:0001275",
        }
    ]
    edges = [
        {"sub": f"{OBO}HP_{n}", "pred": "is_a", "obj": f"{OBO}HP_{p}"}
        for n, (_, p) in TERMS.items()
        if p
    ]
    return parse_obographs(
        {"graphs": [{"meta": {"version": "2026-09-01"}, "nodes": nodes, "edges": edges}]}
    )


def _feature(hpo_id: str, excluded: bool = False) -> dict:
    f = {"type": {"id": hpo_id, "label": ""}}
    if excluded:
        f["excluded"] = True
    return f


# ---------------------------------------------------------------- vignettes


def test_case_record_resolves_ids_and_keeps_only_phenotypic_abnormality(ont):
    pp = {
        "id": "PMID_1_Case_1",
        "subject": {"sex": "FEMALE", "timeAtLastEncounter": {"age": {"iso8601duration": "P5Y"}}},
        "phenotypicFeatures": [
            _feature("HP:0001275"),  # alt id of Seizure
            _feature("HP:0001252"),
            _feature("HP:0000006"),  # inheritance: outside HP:0000118
            _feature("HP:0001251", excluded=True),
            _feature("HP:0001252", excluded=True),  # also observed: dropped from excluded
        ],
        "interpretations": [],
    }
    rec = case_record("0.1.27/GENE1/PMID_1_Case_1.json", pp, ont)
    assert rec["observed"] == ["HP:0001250", "HP:0001252"]
    assert rec["excluded"] == ["HP:0001251"]
    assert rec["gene"] == "GENE1" and rec["sex"] == "FEMALE" and rec["age_iso8601"] == "P5Y"


def _cases(n_genes: int = 12, per_gene: int = 3) -> pd.DataFrame:
    rows = []
    for g in range(n_genes):
        for k in range(per_gene):
            rows.append(
                {"case_id": f"C{g:02d}_{k}", "gene": f"G{g:02d}", "observed": ["x"] * (3 + k)}
            )
    return pd.DataFrame(rows)


def test_eligible_bounds():
    df = pd.DataFrame({"observed": [["a"] * n for n in (2, 3, 15, 16)]})
    assert eligible(df)["observed"].map(len).tolist() == [3, 15]


def test_draw_one_case_per_gene_disjoint_sets_deterministic():
    cases = _cases()
    d1 = draw(cases, 42, n_pilot=3, n_full=4)
    d2 = draw(cases, 42, n_pilot=3, n_full=4)
    pd.testing.assert_frame_equal(d1, d2)
    assert d1["gene"].is_unique and len(d1) == 12
    assert d1["set"].value_counts().to_dict() == {"reserve": 5, "full": 4, "pilot": 3}
    sets = {s: set(g["gene"]) for s, g in d1.groupby("set")}
    assert not (sets["pilot"] & sets["full"]) and not (sets["full"] & sets["reserve"])
    assert list(d1["draw_rank"]) == list(range(12))
    assert not draw(cases, 7, 3, 4)["case_id"].equals(d1["case_id"])


def test_negation_pool_skips_ancestors_and_descendants_of_observed(ont):
    pool = negation_pool(
        ["HP:0007359"], ["HP:0001250", "HP:0002121", "HP:0001251"], ont
    )  # Seizure is an ancestor of the observed Focal-onset seizure
    assert pool == ["HP:0001251", "HP:0002121"]
    assert negation_pool(["HP:0001250"], ["HP:0007359", "HP:0001252"], ont) == ["HP:0001252"]


def test_pick_negated_caps_and_is_deterministic(ont):
    excluded = ["HP:0001251", "HP:0001252", "HP:0000790", "HP:0006101", "HP:0001770", "HP:0002121"]
    a = pick_negated(["HP:0040064"], excluded, ont, 42, "case-1")
    assert a == pick_negated(["HP:0040064"], excluded, ont, 42, "case-1")
    # limb children are descendants of the observed limb term, so 4 remain: no cap needed
    assert a == ["HP:0000790", "HP:0001251", "HP:0001252", "HP:0002121"]
    b = pick_negated([], excluded, ont, 42, "case-1")
    assert len(b) == MAX_NEGATED and set(b) <= set(excluded) and b == sorted(b)


@pytest.mark.parametrize(
    "iso,text",
    [("P5Y3M", "5 years 3 months"), ("P1Y", "1 year"), ("P2W", "2 weeks"), ("", ""), ("bad", "")],
)
def test_age_text(iso, text):
    assert age_text(iso) == text


def test_items_hide_ids(ont):
    its = items(["HP:0001250", "HP:0001252"], ["HP:0001251"])
    assert [i["item"] for i in its] == ["1", "2", "N1"]
    lines = item_lines(its, ont, "present") + item_lines(its, ont, "absent")
    assert "HP:" not in lines and "[N1] Ataxia" in lines


PT_VOCAB = "ataxia\nataxia cerebelar\nhipotonia"


def test_label_leaks_keep_accents_and_spare_cognates():
    text = (
        "Apresenta ataxia, hematúria, microtia, diabetes mellitus, pectus carinatum, "
        "talon cusp, short stature e Seizure."
    )
    labels = ["Ataxia", "Hematuria", "Microtia", "Diabetes mellitus", "Pectus carinatum"]
    labels += ["Talon cusp", "Short stature", "Seizure"]
    # Seizure looks Portuguese in spelling and passes; the English function-word warning
    # is the net for English prose (PREREG, Desvios).
    assert label_leaks(text, labels, PT_VOCAB) == ["Talon cusp", "Short stature"]


@pytest.mark.parametrize(
    "word,impossible",
    [
        ("cusp", True),
        ("delay", True),
        ("hypotonia", True),
        ("stature", False),
        ("microtia", False),
        ("mellitus", False),
        ("carinatum", False),
        ("ptosis", False),
        ("thumb", True),
        ("IgG", True),
    ],
)
def test_impossible_in_portuguese(word, impossible):
    assert impossible_in_portuguese(word) is impossible


def test_labeled_description_warning():
    its, phrases = _items_and_phrases()
    text = CLEAN.replace("hipotonia", "tônus baixo, compatível com hipotonia")
    phrases = [{**p, "phrase": "tônus baixo"} if p["item"] == "1" else p for p in phrases]
    chk = check_vignette(text, phrases, its, LABELS, PT_VOCAB, [])
    assert chk["pass"] and "labeled_description:1" in chk["warn"], chk


LABELS = ["Hypotonia", "Ataxia", "Hematuria", "Seizure"]
CLEAN = "Criança com hipotonia, marcha atáxica e hematúria. Mãe nega crises epilépticas."


def _items_and_phrases():
    its = items(["HP:0001252", "HP:0001251", "HP:0000790"], ["HP:0001250"])
    phrases = [
        {"item": "1", "phrase": "hipotonia"},
        {"item": "2", "phrase": "marcha atáxica"},
        {"item": "3", "phrase": "hematúria"},
        {"item": "N1", "phrase": "nega crises epilépticas"},
    ]
    return its, phrases


def test_check_vignette_passes_clean_text():
    its, phrases = _items_and_phrases()
    chk = check_vignette(CLEAN, phrases, its, LABELS, PT_VOCAB, ["SCN1A"])
    assert chk["pass"] and chk["dropped"] == {}, chk


@pytest.mark.parametrize(
    "text,reason",
    [
        (CLEAN + " (HP:0001252)", "hpo_id_or_mention"),
        (CLEAN + " Hypotonia.", "english_label"),
        (CLEAN + " Variante em SCN1A.", "gene_symbol"),
        ("Criança com hipotonia. Nega crises epilépticas.", "too_few_present_items:1"),
    ],
)
def test_check_vignette_failures(text, reason):
    its, phrases = _items_and_phrases()
    chk = check_vignette(text, phrases, its, LABELS, PT_VOCAB, ["SCN1A"])
    assert not chk["pass"] and any(f.startswith(reason) for f in chk["fail"]), chk


def test_check_vignette_drops_items_without_phrase_in_text():
    its, phrases = _items_and_phrases()
    text = "Criança com hipotonia, marcha atáxica e hematúria."  # negation missing
    extra = {"item": "4", "phrase": "baixa estatura"}  # unknown item: warning only
    chk = check_vignette(text, phrases[:3] + [extra], its, LABELS, PT_VOCAB, [])
    assert chk["pass"] and chk["dropped"] == {"N1": "no_phrase"}, chk
    assert "unknown_item:4" in chk["warn"] and "dropped_items:N1" in chk["warn"]
    chk = check_vignette(text, phrases, its, LABELS, PT_VOCAB, [])
    assert chk["pass"] and chk["dropped"] == {"N1": "phrase_not_in_text"}
    chk = check_vignette(CLEAN, phrases[1:], its, LABELS, PT_VOCAB, [])
    assert chk["dropped"] == {"1": "no_phrase"}
    assert not chk["pass"] and "too_few_present_items:2" in chk["fail"]


def test_check_vignette_accepts_shared_and_overlapping_phrases():
    # "Polegares e háluces alargados": Broad thumb got the phrase "Polegares", Broad hallux
    # "háluces alargados"; both stretches of one sentence, so both items are kept.
    its = items(["HP:0011304", "HP:0010055", "HP:0001252"], [])
    text = "Exame físico: Polegares e háluces alargados. Hipotonia global."
    phrases = [
        {"item": "1", "phrase": "Polegares"},
        {"item": "2", "phrase": "háluces alargados"},
        {"item": "3", "phrase": "Hipotonia global"},
    ]
    chk = check_vignette(text, phrases, its, [], PT_VOCAB, [])
    assert chk["pass"] and chk["dropped"] == {}, chk
    same = [{**p, "phrase": "Polegares e háluces alargados"} for p in phrases[:2]] + phrases[2:]
    chk = check_vignette(text, same, its, [], PT_VOCAB, [])
    assert chk["pass"] and chk["dropped"] == {}, chk


def test_final_vignettes_filters_prompt_model_and_pass():
    base = {"set": "pilot", "prompt_sha256": "s1", "model": "m"}
    recs = [
        {**base, "case_id": "a", "checks": {"pass": False}},
        {**base, "case_id": "a", "checks": {"pass": True}, "vignette": "ok"},
        {**base, "case_id": "b", "checks": {"pass": True}, "prompt_sha256": "old"},
        {**base, "case_id": "c", "checks": {"pass": True}, "set": "full"},
    ]
    out = final_vignettes(recs, "pilot", "s1", "m")
    assert list(out) == ["a"] and out["a"]["vignette"] == "ok"


# ---------------------------------------------------------------- extraction


def test_example_term_clashes(ont):
    assert example_term_clashes({"c1": {"HP:0001250"}}, ont) == []
    clash = example_term_clashes({"c1": {"HP:0001250"}, "c2": {"HP:0010605"}}, ont)
    assert clash == [{"case_id": "c2", "example_term": "HP:0010605", "case_term": "HP:0010605"}]


def test_select_schema_and_parse_selection():
    sch = select_schema(["HP:1", "HP:2"])
    assert sch["properties"]["hpo_id"]["enum"] == ["HP:1", "HP:2", NONE_ID]
    assert parse_selection('{"hpo_id": "HP:2"}', ["HP:1", "HP:2"]) == "HP:2"
    assert parse_selection('{"hpo_id": "NONE"}', ["HP:1"]) is None
    assert parse_selection('{"hpo_id": "HP:9"}', ["HP:1"]) is None
    assert parse_selection("not json", ["HP:1"]) is None


def test_parse_extraction_cleans_and_flags_bad_output():
    present, absent, ok = parse_extraction(
        '{"present": ["hipotonia", " Hipotonia ", "", 3, "baixa  estatura"], "absent": ["crises"]}'
    )
    assert ok and present == ["hipotonia", "baixa estatura"] and absent == ["crises"]
    assert parse_extraction("```json nope") == ([], [], False)


def test_segments_split_clauses_but_not_decimal_commas():
    text = "Ao exame: microcefalia, hipertelorismo; perímetro 1,5 cm abaixo.\nSem crises"
    assert segments(text) == [
        "Ao exame",
        "microcefalia",
        "hipertelorismo",
        "perímetro 1,5 cm abaixo",
        "Sem crises",
    ]


# ---------------------------------------------------------------- metrics


def test_summary_micro_macro_and_empty_prediction():
    c = np.array([[2, 0, 1], [0, 0, 3]])  # second case: no prediction -> P = 0
    s = cm.summary(c)
    assert s["micro"] == {"precision": 1.0, "recall": 0.3333, "f1": 0.5}
    assert s["macro"]["precision"] == 0.5 and s["macro"]["recall"] == pytest.approx(0.3333)


def test_paired_diff_identical_and_better_arm():
    c = np.array([[2, 1, 1], [1, 0, 2], [3, 1, 0]])
    idx = cm.bootstrap_indices(3, 500, 42)
    same = cm.paired_diff(c, c, idx)
    assert same["diff"] == 0 and same["ci95"] == [0.0, 0.0]
    moved = (c[:, 2] > 0).astype(int)  # one FN becomes a TP wherever there is an FN
    better = c + np.stack([moved, np.zeros_like(moved), -moved], axis=1)
    d = cm.paired_diff(better, c, idx)
    assert d["diff"] > 0 and d["ci95"][0] >= 0


def test_boot_ratio_ci_bounds():
    idx = cm.bootstrap_indices(4, 200, 1)
    lo, hi = cm.boot_ratio_ci(np.array([1, 0, 0, 1]), np.array([2, 2, 2, 2]), idx)
    assert 0 <= lo <= 0.25 <= hi <= 1


def test_near_miss_pairs_one_to_one(ont):
    pairs = cm.near_miss_pairs({"HP:0001250"}, {"HP:0007359", "HP:0002121"}, ont)
    assert pairs == [("HP:0001250", "HP:0002121")]
    assert cm.near_miss_pairs({"HP:0001252"}, {"HP:0007359"}, ont) == []


@pytest.mark.parametrize(
    "a,b,swap",
    [
        ("Finger syndactyly", "Toe syndactyly", True),
        ("Broad thumb", "Broad hallux", True),
        ("Short metacarpal", "Short metatarsal", True),
        ("Abnormality of the upper limb", "Abnormality of the lower limb", True),
        ("Thin upper lip vermilion", "Thin lower lip vermilion", False),
        ("Finger syndactyly", "Finger syndactyly", False),
        ("Finger syndactyly", "Toe clinodactyly", False),
    ],
)
def test_hand_foot_swap(a, b, swap):
    assert cm.is_hand_foot_swap(a, b) is swap


def test_swap_pairs_and_fp_category(ont):
    assert cm.swap_pairs({"HP:0001770"}, {"HP:0006101"}, ont) == [("HP:0001770", "HP:0006101")]
    gold = {"HP:0007359"}
    assert cm.fp_category("HP:0001250", gold, {"HP:0001250"}, ont) == "negated"
    assert cm.fp_category("HP:0001250", gold, set(), ont) == "parent_child"
    assert cm.fp_category("HP:0002121", gold, set(), ont) == "sibling"
    dropped = frozenset({"HP:0002121"})
    assert cm.fp_category("HP:0002121", gold, set(), ont, dropped) == "dropped_from_gold"


# ---------------------------------------------------------------- ollama, retrieval


@pytest.mark.parametrize(
    "host,url",
    [
        (None, "http://127.0.0.1:11434"),
        ("0.0.0.0", "http://127.0.0.1:11434"),
        ("localhost:8080", "http://localhost:8080"),
        ("http://gpu-box", "http://gpu-box:11434"),
    ],
)
def test_base_url(host, url, monkeypatch):
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert ollama.base_url(host) == url


def test_chat_payload():
    p = ollama.chat_payload("m:tag", "sys", "usr", {"temperature": 0, "seed": 42})
    assert p["stream"] is False and "format" not in p
    assert [m["role"] for m in p["messages"]] == ["system", "user"]
    assert ollama.chat_payload("m", "s", "u", {}, {"type": "object"})["format"] == {
        "type": "object"
    }


def test_top_ids_max_over_strings():
    idx = TermIndex.build([("a", "HP:1"), ("b", "HP:1"), ("c", "HP:2"), ("d", "HP:3")])
    emb = np.eye(4, dtype=np.float32)  # one dimension per string
    q = np.array([[0.1, 0.9, 0.5, 0.0]], dtype=np.float32)
    pos, sc = top_ids(q, emb, idx, k=2)
    assert [idx.ids[p] for p in pos[0]] == ["HP:1", "HP:2"]
    assert sc[0].tolist() == pytest.approx([0.9, 0.5])


# ---------------------------------------------------------------- register


@pytest.mark.parametrize(
    "en,pt",
    [
        ("hypotonia", "hipotonia"),
        ("microcephaly", "microcefalia"),
        ("scoliosis", "escoliose"),
        ("cardiomyopathy", "cardiomiopatia"),
        ("uveitis", "uveite"),
        ("hypermobility", "hipermobilidade"),
        ("malformation", "malformacao"),
        ("intellectual", "intelectual"),
    ],
)
def test_respell(en, pt):
    assert respell(en) == pt


def test_register_classes():
    text = "A mãe acha a filha molinha. Exame físico: hipotonia global. Baixa estatura."
    assert classify(text, "hipotonia global", "Hypotonia", None)["register"] == "technical"
    assert classify(text, "molinha", "Hypotonia", None)["register"] == "both"
    assert classify(text, "Baixa estatura", "Short stature", "Baixa estatura")["register"] == (
        "technical"
    )
    lay = classify(
        "Demorou para sentar e andar.", "Demorou para sentar e andar", "Motor delay", None
    )
    assert lay["register"] == "lay" and lay["technical_sentence"] == ""
