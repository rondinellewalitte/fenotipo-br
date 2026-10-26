"""Exp 03: blind clinical register labels (D2) for the full set, made before any extraction.

--make writes one input and one instruction file per batch under results/exp03/register_batches/.
Each batch holds BATCH_CASES full-set vignettes plus the same CALIBRATION pilot vignettes,
whose labels were checked by the author (kappa in results/exp03/pilot/register_kappa.json).
The instruction text is prompts/exp03_register_manual_v1.md verbatim, with only the counts
and file paths changed. An independent Claude Code subagent labels each batch, blind to the
rule output; no extraction of the full set exists at that point.

--merge checks every batch, measures agreement with the pilot labels on the calibration
items, and writes results/exp03/register_labels_full.csv plus its .meta.json.

    uv run python experiments/exp03_register_labels.py --make
    uv run python experiments/exp03_register_labels.py --merge
"""
# ruff: noqa: E501  (metadata strings below are prose)

from __future__ import annotations

import argparse
import hashlib
import json

import numpy as np
import pandas as pd

from hpolab.casemetrics import cohen_kappa
from hpolab.data import RAW_DIR, ROOT
from hpolab.hpo import load_babelon, load_ontology, pt_labels
from hpolab.llm import Prompt
from hpolab.vignettes import GENERATOR_MODEL, GENERATOR_PROMPT, final_vignettes

SEED = 42
BATCH_CASES = 50
CALIBRATION = 3  # pilot vignettes repeated in every batch
OUT = ROOT / "results" / "exp03"
DIR = OUT / "register_batches"
INSTRUCTIONS = ROOT / "prompts" / "exp03_register_manual_v1.md"
PILOT_LABELS = OUT / "pilot" / "register_check.csv"
FULL_LABELS = OUT / "register_labels_full.csv"
HEADER = "case_id,hpo_id,d2_technical,d2_lay,evidence"


def finals(set_name: str) -> dict:
    sha = Prompt.load(ROOT / "prompts" / GENERATOR_PROMPT).sha256
    with (OUT / "vignettes.jsonl").open(encoding="utf-8") as fh:
        recs = [json.loads(line) for line in fh if line.strip()]
    return final_vignettes(recs, set_name, sha, GENERATOR_MODEL)


def items_of(r: dict) -> list[dict]:
    return [it for it in r["items"] if it["polarity"] == "present" and not it.get("dropped")]


def case_block(r: dict, pt) -> str:
    lines = [f"## CASE {r['case_id']}", "", r["vignette"], "", "Items:"]
    for it in items_of(r):
        label_pt = pt.get(it["hpo_id"], "(none)")
        lines.append(
            f"- {it['hpo_id']} | EN label: {it['label_en']} | official PT label: {label_pt} "
            f"| generator phrase: {it['phrase']}"
        )
    return "\n".join(lines) + "\n"


def instructions(n_cases: int, n_items: int, input_path, output_path) -> str:
    """The pilot instructions, verbatim except counts and the two file paths."""
    text = INSTRUCTIONS.read_text(encoding="utf-8").split("\n---\n", 1)[1].strip()
    text = text.replace("50 synthetic clinical notes", f"{n_cases} synthetic clinical notes")
    text = text.replace("There are 372 items in total", f"There are {n_items} items in total")
    text = text.replace("all 372 items", f"all {n_items} items")
    text = text.replace("Input: register_input.md", f"Input: {input_path}")
    text = text.replace("to: register_manual.csv", f"to: {output_path}")
    return text


def make() -> None:
    ont = load_ontology(RAW_DIR / "hp.json")
    pt = pt_labels(load_babelon(RAW_DIR / "hp-pt.babelon.tsv"), ont).set_index("hpo_id")["pt_label"]
    full, pilot = finals("full"), finals("pilot")
    rng = np.random.default_rng(SEED)
    calib_ids = sorted(rng.choice(sorted(pilot), CALIBRATION, replace=False))
    full_ids = sorted(full)
    DIR.mkdir(parents=True, exist_ok=True)
    plan = []
    for b, start in enumerate(range(0, len(full_ids), BATCH_CASES), 1):
        ids = full_ids[start : start + BATCH_CASES]
        blocks = [(cid, full[cid]) for cid in ids] + [(cid, pilot[cid]) for cid in calib_ids]
        order = rng.permutation(len(blocks))  # calibration cases mixed in, not at the end
        blocks = [blocks[i] for i in order]
        n_items = sum(len(items_of(r)) for _, r in blocks)
        inp, out = DIR / f"batch_{b:02d}_input.md", DIR / f"batch_{b:02d}_labels.csv"
        inp.write_text("\n".join(case_block(r, pt) for _, r in blocks), encoding="utf-8")
        text = instructions(len(blocks), n_items, inp, out)
        (DIR / f"batch_{b:02d}_instructions.md").write_text(text + "\n", encoding="utf-8")
        plan.append({"batch": b, "cases": len(blocks), "items": n_items, "full_cases": ids})
    meta = {"calibration_cases": calib_ids, "batches": plan}
    (DIR / "plan.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(f"{len(plan)} batches; calibration cases {calib_ids}")
    for p in plan:
        print(f"  batch {p['batch']}: {p['cases']} cases, {p['items']} items")


def d2(t: str, la: str) -> str:
    t, la = t.strip().lower() == "yes", la.strip().lower() == "yes"
    return "both" if t and la else "technical" if t else "lay" if la else "none"


def merge() -> None:
    plan = json.loads((DIR / "plan.json").read_text(encoding="utf-8"))
    full, pilot = finals("full"), finals("pilot")
    pilot_lab = pd.read_csv(PILOT_LABELS, dtype=str, keep_default_na=False)
    pilot_cls = dict(
        zip(zip(pilot_lab.case_id, pilot_lab.hpo_id, strict=True), pilot_lab.man_d2, strict=True)
    )
    calib = set(plan["calibration_cases"])
    frames, calib_rows = [], []
    for p in plan["batches"]:
        path = DIR / f"batch_{p['batch']:02d}_labels.csv"
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
        expected = {
            (cid, it["hpo_id"])
            for cid in p["full_cases"] + plan["calibration_cases"]
            for it in items_of(full.get(cid) or pilot[cid])
        }
        got = set(zip(df.case_id, df.hpo_id, strict=True))
        if got != expected or len(df) != len(expected):
            raise SystemExit(
                f"batch {p['batch']}: {len(expected - got)} missing, {len(got - expected)} unexpected"
            )
        bad = df[
            ~df.d2_technical.str.lower().isin({"yes", "no"})
            | ~df.d2_lay.str.lower().isin({"yes", "no"})
        ]
        if len(bad):
            raise SystemExit(f"batch {p['batch']}: {len(bad)} rows without yes/no")
        df["batch"] = p["batch"]
        is_cal = df.case_id.isin(calib)
        frames.append(df[~is_cal])
        cal = df[is_cal].assign(
            labeler=lambda d: [d2(t, la) for t, la in zip(d.d2_technical, d.d2_lay, strict=True)],
            pilot=lambda d: [pilot_cls[k] for k in zip(d.case_id, d.hpo_id, strict=True)],
        )
        calib_rows.append(cal)
    labels = pd.concat(frames, ignore_index=True)
    labels[
        ["case_id", "hpo_id", "d1_technical", "d2_technical", "d2_lay", "evidence", "batch"]
    ].to_csv(FULL_LABELS, index=False)
    cal = pd.concat(calib_rows, ignore_index=True)
    per_batch = {
        int(b): {
            "items": len(g),
            "agreement_with_pilot_labels": round(float((g.labeler == g.pilot).mean()), 4),
            "kappa_with_pilot_labels": round(cohen_kappa(list(g.pilot), list(g.labeler)), 4),
        }
        for b, g in cal.groupby("batch")
    }
    classes = pd.Series(
        [d2(t, la) for t, la in zip(labels.d2_technical, labels.d2_lay, strict=True)]
    )
    meta = {
        "what": "blind clinical register labels (D2) of the present, non-dropped gold items, full set",
        "labeler": "independent Claude Code subagents (general-purpose), model claude-opus-5-5, one per batch; not the Anthropic API, so no cost under the Exp 03 API cap",
        "blind_to": [
            "hpolab.register rule output",
            "extraction results (none existed for the full set)",
        ],
        "instructions": INSTRUCTIONS.relative_to(ROOT).as_posix(),
        "instructions_sha256": hashlib.sha256(INSTRUCTIONS.read_bytes()).hexdigest(),
        "batch_files": (DIR.relative_to(ROOT)).as_posix(),
        "n_items": len(labels),
        "classes": classes.value_counts().to_dict(),
        "calibration": {
            "cases": plan["calibration_cases"],
            "reference": "pilot labels checked by the author (results/exp03/pilot/register_kappa.json)",
            "per_batch": per_batch,
        },
    }
    FULL_LABELS.with_name(FULL_LABELS.stem + ".meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: meta[k] for k in ("n_items", "classes", "calibration")}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--make", action="store_true")
    parser.add_argument("--merge", action="store_true")
    args = parser.parse_args()
    if args.make:
        make()
    elif args.merge:
        merge()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
