"""Evaluate the pre-registered hypotheses of Exp 01 (results/exp01/PREREG.md) against
results/exp01/metrics.json and write results/exp01/hypotheses.json.

The criteria below transcribe PREREG.md; they are not tuned to the results.

    uv run python experiments/exp01_hypotheses.py
"""

from __future__ import annotations

import json

from hpolab.data import ROOT

OUT = ROOT / "results" / "exp01"
EMBEDDING_METHODS = ("e5-base", "e5-base_qp", "mpnet-multi", "bge-m3")
ALPHA = 0.05


def main() -> None:
    m = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))
    res, paired = m["results"], m["paired_top1_mcnemar"]

    def s(method: str, subset: str = "main", index: str = "exact") -> dict:
        return res[method][index][subset]

    best = max((e for e in EMBEDDING_METHODS if e in res), key=lambda e: s(e)["top1"])
    out: dict = {"best_embedding_by_primary_top1": best, "hypotheses": {}}
    h = out["hypotheses"]

    pairs = [
        ("bge-m3", "e5-base"),
        ("e5-base", "mpnet-multi"),
        ("mpnet-multi", "lexical_token_sort"),
    ]
    h1 = {}
    for a, b in pairs:
        t = paired.get(f"{a} vs {b}")
        if t is None:
            continue
        h1[f"{a} > {b}"] = {
            "diff_top1": t["diff_a_minus_b"],
            "p_holm": t["p_holm"],
            "confirmed": t["diff_a_minus_b"] > 0 and t["p_holm"] < ALPHA,
        }
    h["H1_ordering"] = {"pairs": h1, "confirmed": all(v["confirmed"] for v in h1.values())}

    ident = {meth: s(meth, "main_identical")["top1"] for meth in res}
    h["H2_identical_top1_ge_0.85"] = {
        "top1": ident,
        "confirmed": all(v >= 0.85 for v in ident.values()),
    }

    lex_non = s("lexical_token_sort", "main_nonidentical")["top1"]
    drop = s(best, "main_identical")["top1"] - s(best, "main_nonidentical")["top1"]
    h["H3_nonidentical"] = {
        "lexical_nonidentical_top1": lex_non,
        "lexical_le_0.40": lex_non <= 0.40,
        "best_identical_minus_nonidentical": round(drop, 4),
        "best_drop_ge_0.30": drop >= 0.30,
        "confirmed": lex_non <= 0.40 and drop >= 0.30,
    }

    gap = s(best)["top10"] - s(best)["top1"]
    h["H4_top10_minus_top1_ge_0.15"] = {"gap": round(gap, 4), "confirmed": gap >= 0.15}

    stale, current = s(best, "main_stale")["top1"], s(best, "main_current")["top1"]
    h["H5_stale_lt_current"] = {
        "stale_top1": stale,
        "stale_n": s(best, "main_stale")["n"],
        "current_top1": current,
        "confirmed": stale < current,
    }

    h6 = {}
    for meth in res:
        delta = s(meth, index="all_scopes")["top1"] - s(meth)["top1"]
        h6[meth] = {
            "delta_all_minus_exact": round(delta, 4),
            "ok": delta <= 0 and abs(delta) <= 0.03,
        }
    h["H6_ablation_all_scopes"] = {
        "per_method": h6,
        "confirmed": all(v["ok"] for v in h6.values()),
    }

    qq, qp = s("e5-base")["top1"], s("e5-base_qp")["top1"]
    h["H7_e5_query_query_ge_query_passage"] = {
        "e5-base": qq,
        "e5-base_qp": qp,
        "confirmed": qq >= qp,
        "note": "direction only; no significance test was pre-registered for this pair",
    }

    near, top1 = s(best)["near_miss"], s(best)["top1"]
    share = near / (1 - top1)
    h["H8_near_miss_share_of_errors_ge_0.20"] = {
        "near_miss_rate": near,
        "share_of_top1_errors": round(share, 4),
        "confirmed": share >= 0.20,
    }

    out["summary"] = {k: v["confirmed"] for k, v in h.items()}
    path = OUT / "hypotheses.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))
    print(f"-> {path}")


if __name__ == "__main__":
    main()
