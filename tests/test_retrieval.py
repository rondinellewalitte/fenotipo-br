import numpy as np
import pandas as pd

from hpolab.metrics import holm, mcnemar, topk_summary, wilson_ci
from hpolab.retrieval import TermIndex, fold, ids_at_top, rank_gold, text_key


def _index() -> TermIndex:
    # "ASD" is shared by two ids; B has two strings
    return TermIndex.build(
        [
            ("Atrial septal defect", "HP:A"),
            ("ASD", "HP:A"),
            ("Autism", "HP:B"),
            ("asd ", "HP:B"),
            ("Seizure", "HP:C"),
        ]
    )


def test_build_dedupes_strings_and_keeps_all_ids():
    idx = _index()
    assert idx.texts == ["Atrial septal defect", "ASD", "Autism", "Seizure"]
    assert idx.text_ids[1] == ("HP:A", "HP:B")
    assert idx.ids == ["HP:A", "HP:B", "HP:C"]
    assert idx.n_ambiguous_texts() == 1


def test_id_scores_take_max_over_strings():
    idx = _index()
    text_scores = np.array([[0.1, 0.9, 0.3, 0.2]], dtype=np.float32)
    np.testing.assert_allclose(idx.id_scores(text_scores), [[0.9, 0.9, 0.2]])


def test_shared_string_is_a_tie_not_a_hit():
    idx = _index()
    s = idx.id_scores(np.array([[0.1, 0.9, 0.3, 0.2]], dtype=np.float32))
    r = rank_gold(s, np.array([idx.id_pos["HP:B"]]))
    assert r["rank_opt"][0] == 1
    assert r["rank_pess"][0] == 2
    assert r["n_top"][0] == 2


def test_lexical_style_tie_and_strict_loss():
    s = np.array(
        [
            [80.0, 80.0, 80.0, 10.0],  # gold (pos 2) in a 3-way tie at top
            [95.0, 70.0, 50.0, 50.0],  # gold (pos 1) strictly below a winner
            [10.0, 20.0, 30.0, 90.0],  # gold (pos 3) strict winner
        ],
        dtype=np.float32,
    )
    r = rank_gold(s, np.array([2, 1, 3]), k=3)
    assert r["rank_opt"].tolist() == [1, 2, 1]
    assert r["rank_pess"].tolist() == [3, 2, 1]
    # display order breaks ties by id position, scoring does not
    assert r["top_idx"][0].tolist() == [0, 1, 2]
    assert ids_at_top(s[0]).tolist() == [0, 1, 2]


def test_topk_summary_uses_pessimistic_rank():
    df = pd.DataFrame({"rank_opt": [1, 2, 1], "rank_pess": [3, 2, 1], "near_miss": [0, 1, 0]})
    m = topk_summary(df)
    assert m["top1"] == round(1 / 3, 4)
    assert m["top1_optimistic"] == round(2 / 3, 4)
    assert m["top1_tied"] == round(1 / 3, 4)
    assert m["top5"] == 1.0
    assert m["near_miss"] == round(1 / 3, 4)


def test_fold_and_key():
    assert fold("Microcefalia  congênita!") == "microcefalia congenita"
    assert text_key("  Abnormal   Gait ") == "abnormal gait"


def test_wilson_ci_bounds():
    lo, hi = wilson_ci(50, 100)
    assert lo < 0.5 < hi


def test_mcnemar_and_holm():
    a = np.array([1, 1, 1, 1, 0, 1], dtype=bool)
    b = np.array([0, 0, 0, 1, 0, 1], dtype=bool)
    r = mcnemar(a, b)
    assert (r["a_only"], r["b_only"]) == (3, 0)
    assert r["p_value"] == 0.25  # exact binomial, 3 of 3 discordant
    adj = holm({"x": 0.01, "y": 0.04, "z": 0.03})
    assert adj == {"x": 0.03, "z": 0.06, "y": 0.06}
