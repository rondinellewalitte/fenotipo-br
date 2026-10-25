"""Check the expectations of results/exp02/PREREG.md against results/exp02/metrics.json
and write results/exp02/expectations.json. Criteria transcribe PREREG.md.

    uv run python experiments/exp02_expectations.py
"""

from __future__ import annotations

import json

from hpolab.data import ROOT

OUT = ROOT / "results" / "exp02"


def main() -> None:
    m = json.loads((OUT / "metrics.json").read_text(encoding="utf-8"))
    cov, hpoa = m["coverage"], m["hpoa_check"]
    gain300 = m["simulated_gain"]["top300_missing_added"]["annotation_coverage"]
    delta = gain300 - cov["annotation_coverage"]
    e = {
        "E1_annotation_coverage_0.40_to_0.60": {
            "value": cov["annotation_coverage"],
            "met": 0.40 <= cov["annotation_coverage"] <= 0.60,
        },
        "E2_pct_cases_full_le_0.10": {
            "value": cov["pct_cases_full"],
            "met": cov["pct_cases_full"] <= 0.10,
        },
        "E3_median_frac_0.35_to_0.65": {
            "value": cov["frac_median"],
            "met": 0.35 <= cov["frac_median"] <= 0.65,
        },
        "E4_top300_gain_ge_0.15": {"value": round(delta, 4), "met": delta >= 0.15},
        "E5_hpoa_close_to_claude_md": {
            "annotation_coverage": hpoa["annotation_coverage"],
            "claude_md_annotation_coverage": "~0.40",
            "top500_with_pt": hpoa["top500_by_n_diseases_with_pt"],
            "claude_md_top500_with_pt": 193,
            "met": abs(hpoa["annotation_coverage"] - 0.40) <= 0.03
            and abs(hpoa["top500_by_n_diseases_with_pt"] - 193) <= 15,
            "tolerance": "±3 points and ±15 terms (set when writing this check)",
        },
    }
    out = {"expectations": e, "summary": {k: v["met"] for k, v in e.items()}}
    path = OUT / "expectations.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))


if __name__ == "__main__":
    main()
