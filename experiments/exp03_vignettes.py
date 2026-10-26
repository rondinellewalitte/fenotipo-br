"""Exp 03, step 1: draw the cases and write PT-BR vignettes with the Anthropic API.

Cases: Phenopacket Store, 3-15 observed terms under HP:0000118, one case per gene; the
pilot (50) and the full run (300) use disjoint genes (hpolab.vignettes.draw). Each vignette
states the observed terms as present and up to 5 excluded terms as absent. The generator
sees English labels and definitions only (no HPO ids, no disease, no gene). Every output
goes through hpolab.vignettes.check_vignette; a case that fails twice is replaced by the
next reserve gene. Design: results/exp03/PREREG.md.

API calls need ANTHROPIC_API_KEY. Spending is capped at BUDGET_USD summed over every call
in results/exp03/llm_calls.jsonl (worst case checked before each call). Outputs are stored
in results/exp03/vignettes.jsonl and reused: a case with a passing vignette for the current
prompt and model is never sent again.

    uv run python experiments/exp03_vignettes.py --set pilot --dry-run    # no API calls
    uv run python experiments/exp03_vignettes.py --set pilot
    uv run python experiments/exp03_vignettes.py --set pilot --review 5
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from hpolab import llm
from hpolab.data import RAW_DIR, ROOT, iter_phenopackets
from hpolab.hpo import Ontology, load_babelon, load_ontology, pt_labels
from hpolab.provenance import base_config, paths_dirty
from hpolab.vignettes import (
    GENERATOR_MODEL,
    GENERATOR_PROMPT,
    MAX_NEGATED,
    MAX_TERMS,
    MIN_TERMS,
    SEX_TEXT,
    age_text,
    case_record,
    check_vignette,
    draw,
    eligible,
    final_vignettes,
    item_lines,
    items,
    negation_pool,
    pick_negated,
)

SEED = 42
N_PILOT, N_FULL = 50, 300
BUDGET_USD = 5.00  # cumulative over every Exp 03 API call
EFFORT = "low"
MAX_TOKENS = 4000
MAX_ATTEMPTS = 2
EXPECTED_OUTPUT_TOKENS = 900  # dry-run estimate only; the real number comes from the log
CHARS_PER_TOKEN_ESTIMATE = 3.5
OUT = ROOT / "results" / "exp03"
SAMPLE = OUT / "sample.csv"
VIGNETTES = OUT / "vignettes.jsonl"
CALL_LOG = OUT / "llm_calls.jsonl"
PROMPT_STEM = ROOT / "prompts" / GENERATOR_PROMPT
SCHEMA = {
    "type": "object",
    "properties": {
        "vignette": {"type": "string"},
        "phrases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"item": {"type": "string"}, "phrase": {"type": "string"}},
                "required": ["item", "phrase"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["vignette", "phrases"],
    "additionalProperties": False,
}


def load_cases(ont: Ontology) -> pd.DataFrame:
    rows = [case_record(member, pp, ont) for member, pp in iter_phenopackets()]
    return pd.DataFrame(rows)


def build_sample(ont: Ontology) -> tuple[pd.DataFrame, dict]:
    cases = load_cases(ont)
    elig = eligible(cases)
    sample = draw(elig, SEED, N_PILOT, N_FULL)
    sample["negated"] = [
        pick_negated(r.observed, r.excluded, ont, SEED, r.case_id) for r in sample.itertuples()
    ]
    sample["n_observed"] = sample["observed"].map(len)
    sample["n_excluded_eligible"] = [
        len(negation_pool(r.observed, r.excluded, ont)) for r in sample.itertuples()
    ]
    counts = {
        "n_cases": len(cases),
        "n_eligible": len(elig),
        "n_genes_eligible": int(elig["gene"].nunique()),
        "by_set": sample["set"].value_counts().to_dict(),
    }
    return sample, counts


def write_sample(sample: pd.DataFrame) -> None:
    out = sample.copy()
    for col in ("observed", "excluded", "negated"):
        out[col] = out[col].map("|".join)
    cols = ["draw_rank", "set", "case_id", "gene", "member", "disease_id", "sex", "age_iso8601"]
    cols += ["n_observed", "n_excluded_eligible", "n_gene_eligible_cases"]
    cols += ["observed", "negated", "excluded"]
    OUT.mkdir(parents=True, exist_ok=True)
    out[cols].sort_values("draw_rank").to_csv(SAMPLE, index=False)


def load_jsonl(path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def spent_usd() -> float:
    return sum(r.get("cost_usd", 0.0) for r in load_jsonl(CALL_LOG))


def render(case, ont: Ontology, prompt: llm.Prompt) -> tuple[str, list[dict]]:
    item_list = items(list(case.observed), list(case.negated))
    user = prompt.render(
        sex=SEX_TEXT.get(case.sex, "not stated"),
        age=age_text(case.age_iso8601) or "not stated",
        present=item_lines(item_list, ont, "present"),
        absent=item_lines(item_list, ont, "absent"),
    )
    return user, item_list


def pt_vocabulary(ont: Ontology) -> str:
    pt = pt_labels(load_babelon(RAW_DIR / "hp-pt.babelon.tsv"), ont)
    return "\n".join(" ".join(s.split()).casefold() for s in pt["pt_label"])


class Generator:
    def __init__(self, sample: pd.DataFrame, ont: Ontology, prompt: llm.Prompt, client, budget):
        self.by_id = sample.set_index("case_id", drop=False)
        self.reserve = list(sample[sample["set"] == "reserve"].sort_values("draw_rank")["case_id"])
        self.ont, self.prompt, self.client, self.budget = ont, prompt, client, budget
        self.pt_vocab = pt_vocabulary(ont)
        self.records = load_jsonl(VIGNETTES)

    def _mine(self, case_id: str) -> list[dict]:
        return [
            r
            for r in self.records
            if r["case_id"] == case_id
            and r["prompt_sha256"] == self.prompt.sha256
            and r["model"] == GENERATOR_MODEL
        ]

    def _attempt(self, case_id: str, set_name: str, replaces: str | None, n: int) -> dict:
        case = self.by_id.loc[case_id]
        user, item_list = render(case, self.ont, self.prompt)
        out = llm.json_call(
            self.client,
            model=GENERATOR_MODEL,
            prompt=self.prompt,
            user=user,
            schema=SCHEMA,
            max_tokens=MAX_TOKENS,
            effort=EFFORT,
            budget=self.budget,
            log_path=CALL_LOG,
            meta={"experiment": "exp03", "set": set_name, "case_id": case_id, "attempt": n},
        )
        labels_en = [self.ont.terms[it["hpo_id"]].label for it in item_list]
        if out is None:
            text, phrases = "", []
            checks = {"pass": False, "fail": ["no_output"], "warn": [], "n_words": 0}
        else:
            text, phrases = out["vignette"], out["phrases"]
            genes = str(case.gene).split("|")
            checks = check_vignette(text, phrases, item_list, labels_en, self.pt_vocab, genes)
        phrase_of: dict[str, str] = {}
        for p in phrases:
            phrase_of.setdefault(str(p["item"]), p["phrase"])
        rec = {
            "case_id": case_id,
            "set": set_name,
            "replaces": replaces,
            "attempt": n,
            "model": GENERATOR_MODEL,
            "prompt_sha256": self.prompt.sha256,
            "effort": EFFORT,
            "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "items": [
                {**it, "label_en": lab, "phrase": phrase_of.get(it["item"], "")}
                for it, lab in zip(item_list, labels_en, strict=True)
            ],
            "vignette": text,
            "checks": checks,
        }
        llm.append_jsonl(VIGNETTES, rec)
        self.records.append(rec)
        status = "ok" if checks["pass"] else "FAIL " + ";".join(checks["fail"])
        print(f"[{set_name}] {case_id} attempt {n}: {status}  (spent ${self.budget.spent_usd:.4f})")
        return rec

    def _case(self, case_id: str, set_name: str, replaces: str | None) -> bool:
        """True once the case has a passing vignette; False after MAX_ATTEMPTS failures."""
        recs = self._mine(case_id)
        if any(r["checks"]["pass"] for r in recs):
            return True
        while len(recs) < MAX_ATTEMPTS:
            rec = self._attempt(case_id, set_name, replaces, len(recs) + 1)
            recs.append(rec)
            if rec["checks"]["pass"]:
                return True
        return False

    def _replacement(self, case_id: str) -> str:
        mine = [r for r in self.records if r["prompt_sha256"] == self.prompt.sha256]
        done = next((r["case_id"] for r in mine if r.get("replaces") == case_id), None)
        if done:
            return done
        used = {r["case_id"] for r in mine if r.get("replaces")}
        return next(c for c in self.reserve if c not in used)

    def run(self, target: list[str], set_name: str) -> None:
        for case_id in target:
            current, replaces = case_id, None
            while not self._case(current, set_name, replaces):
                current, replaces = self._replacement(current), current


def summarize(set_name: str, prompt: llm.Prompt) -> dict:
    records = [
        r
        for r in load_jsonl(VIGNETTES)
        if r["set"] == set_name and r["prompt_sha256"] == prompt.sha256
    ]
    final = final_vignettes(records, set_name, prompt.sha256, GENERATOR_MODEL)
    calls = [
        r
        for r in load_jsonl(CALL_LOG)
        if r.get("set") == set_name and r.get("prompt_sha256") == prompt.sha256
    ]
    fails = Counter(f.split(":")[0] for r in records for f in r["checks"]["fail"])
    warns = Counter(w.split(":")[0] for r in final.values() for w in r["checks"]["warn"])
    return {
        "n_attempts": len(records),
        "n_final": len(final),
        "n_replacements": sum(1 for r in final.values() if r.get("replaces")),
        "fail_reasons_all_attempts": dict(fails),
        "warnings_final": dict(warns),
        "n_words_final": {
            "mean": round(float(np.mean([r["checks"]["n_words"] for r in final.values()])), 1)
            if final
            else None,
            "max": max((r["checks"]["n_words"] for r in final.values()), default=None),
        },
        "api_calls": len(calls),
        "input_tokens": sum(r["input_tokens"] for r in calls),
        "output_tokens": sum(r["output_tokens"] for r in calls),
        "cost_usd": round(sum(r["cost_usd"] for r in calls), 4),
    }


def dry_run(sample: pd.DataFrame, set_name: str, ont: Ontology, prompt: llm.Prompt) -> None:
    target = sample[sample["set"] == set_name].sort_values("draw_rank")
    chars = [len(prompt.system) + len(render(c, ont, prompt)[0]) for c in target.itertuples()]
    p = llm.PRICES[GENERATOR_MODEL]
    tokens_in = sum(chars) / CHARS_PER_TOKEN_ESTIMATE
    expected = (tokens_in * p["input"] + len(chars) * EXPECTED_OUTPUT_TOKENS * p["output"]) / 1e6
    worst = llm.Budget(BUDGET_USD).worst_case(GENERATOR_MODEL, max(chars), MAX_TOKENS)
    print(
        f"{set_name}: {len(target)} cases, prompt chars mean {np.mean(chars):.0f} max {max(chars)}"
    )
    print(
        f"expected ≈ ${expected:.2f} (assumes {EXPECTED_OUTPUT_TOKENS} output tokens/call, "
        f"one attempt); worst case per call ${worst:.3f}; already spent ${spent_usd():.4f} "
        f"of ${BUDGET_USD:.2f}"
    )
    first = target.iloc[0]
    print("\n--- example prompt (user part) ---\n" + render(first, ont, prompt)[0])


def review(set_name: str, n: int, ont: Ontology, prompt: llm.Prompt) -> None:
    pt = pt_labels(load_babelon(RAW_DIR / "hp-pt.babelon.tsv"), ont).set_index("hpo_id")
    final = final_vignettes(load_jsonl(VIGNETTES), set_name, prompt.sha256, GENERATOR_MODEL)
    ids = sorted(final)
    pick = sorted(np.random.default_rng(SEED).choice(len(ids), min(n, len(ids)), replace=False))
    for k in pick:
        r = final[ids[k]]
        print(f"\n=== {r['case_id']} ({r['checks']['n_words']} palavras) ===\n{r['vignette']}\n")
        print("| item | estado | HPO | rótulo EN | rótulo PT oficial | frase na vinheta |")
        print("|---|---|---|---|---|---|")
        for it in r["items"]:
            label_pt = pt["pt_label"].get(it["hpo_id"], "—")
            state = "presente" if it["polarity"] == "present" else "ausente"
            print(
                f"| {it['item']} | {state} | {it['hpo_id']} | {it['label_en']} | {label_pt} "
                f"| {it['phrase']} |"
            )
        if r["checks"]["warn"]:
            print(f"avisos: {r['checks']['warn']}")


def check_frozen_generator(prompt: llm.Prompt) -> None:
    """The 300 vignettes use the generator prompt frozen after the pilot (frozen.json)."""
    frozen = OUT / "frozen.json"
    if not frozen.exists():
        sys.exit("frozen.json missing: freeze the pilot before generating the full set.")
    want = json.loads(frozen.read_text(encoding="utf-8"))["generator_prompt"]
    if want != {"stem": GENERATOR_PROMPT, "sha256": prompt.sha256}:
        sys.exit("Generator prompt differs from frozen.json.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", required=True, choices=["pilot", "full"])
    parser.add_argument("--dry-run", action="store_true", help="draw and render, no API calls")
    parser.add_argument("--review", type=int, metavar="N", help="print N random vignettes")
    parser.add_argument(
        "--allow-dirty", action="store_true", help="call the API on uncommitted code"
    )
    args = parser.parse_args()
    ont = load_ontology(RAW_DIR / "hp.json")
    prompt = llm.Prompt.load(PROMPT_STEM)
    if args.review:
        review(args.set, args.review, ont, prompt)
        return
    sample, counts = build_sample(ont)
    write_sample(sample)
    print(f"Sample: {counts} -> {SAMPLE}")
    if args.dry_run:
        dry_run(sample, args.set, ont, prompt)
        return
    if paths_dirty() and not args.allow_dirty:
        sys.exit(
            "Refusing to call the API: src/, experiments/ or prompts/ has uncommitted changes."
        )
    if args.set == "full":
        check_frozen_generator(prompt)
    if not llm.has_api_key():
        sys.exit("ANTHROPIC_API_KEY is not set; nothing was sent.")
    import anthropic

    budget = llm.Budget(BUDGET_USD, spent_usd=spent_usd())
    gen = Generator(sample, ont, prompt, anthropic.Anthropic(), budget)
    target = list(sample[sample["set"] == args.set].sort_values("draw_rank")["case_id"])
    try:
        gen.run(target, args.set)
    except llm.BudgetExceeded as e:
        print(f"Stopped by the budget cap: {e}")
    cfg = base_config("exp03_vignettes", SEED)
    cfg.update(
        {
            "sample": {
                **counts,
                "eligibility": f"{MIN_TERMS}-{MAX_TERMS} observed terms under HP:0000118",
                "max_negated": MAX_NEGATED,
                "n_pilot": N_PILOT,
                "n_full": N_FULL,
            },
            "generator": {
                "model": GENERATOR_MODEL,
                "effort": EFFORT,
                "max_tokens": MAX_TOKENS,
                "max_attempts": MAX_ATTEMPTS,
                "prompt": GENERATOR_PROMPT,
                "prompt_sha256": prompt.sha256,
                "budget_usd_cumulative": BUDGET_USD,
                "price_per_mtok": llm.PRICES[GENERATOR_MODEL],
            },
            "spent_usd_total": round(spent_usd(), 4),
            "summary": summarize(args.set, prompt),
        }
    )
    path = OUT / f"vignettes_config_{args.set}.json"
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(cfg["summary"], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
