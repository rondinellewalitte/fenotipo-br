"""Exp 03: phenotype extraction from PT-BR vignettes with local LLMs (Ollama) and bge-m3 RAG.

Arms (definitions and hypotheses: results/exp03/PREREG.md):
  A         the LLM extracts findings in PT -> bge-m3 top-10 over the English-only index ->
            the LLM picks one candidate id or NONE
  B         the LLM translates the note to English, then the same extraction and RAG
  C         A's extraction, but the index also holds the official PT labels
  baseline  no LLM: clauses -> bge-m3 top-1 over the English index, kept if score >= tau

The 6 GB GPU cannot hold an LLM and bge-m3 at once, so the run is staged:
  bge-m3 (index, baseline, oracle spans) -> per model: [LLM: translate + extract]
  -> [bge-m3: retrieve] -> [LLM: select]
Every Ollama call is cached (ollama_calls.jsonl.gz) and reused on reruns.

    uv run python experiments/exp03_extraction.py --set pilot
    uv run python experiments/exp03_extraction.py --set pilot --freeze   # writes frozen.json
    uv run python experiments/exp03_extraction.py --set full             # needs frozen.json
    uv run python experiments/exp03_extraction.py --set pilot --metrics-only
"""

from __future__ import annotations

import argparse
import gc
import gzip
import hashlib
import json
import os
import sys
import time
from collections import Counter
from datetime import UTC, datetime

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import numpy as np
import pandas as pd
import torch
from rapidfuzz import fuzz

from hpolab import casemetrics as cm
from hpolab import embed, gpu, ollama
from hpolab.data import RAW_DIR, ROOT
from hpolab.extraction import (
    EXTRACT_SCHEMA,
    PROMPT_EXAMPLE_TERMS,
    candidate_lines,
    example_term_clashes,
    parse_extraction,
    parse_selection,
    segments,
    select_schema,
)
from hpolab.hpo import (
    PHENOTYPIC_ABNORMALITY,
    Ontology,
    index_entries,
    load_babelon,
    load_ontology,
    pt_labels,
)
from hpolab.llm import Prompt
from hpolab.provenance import base_config, paths_dirty
from hpolab.register import classify
from hpolab.retrieval import TermIndex, fold, subindex_rows, top_ids
from hpolab.vignettes import GENERATOR_MODEL, GENERATOR_PROMPT, final_vignettes

SEED = 42
N_CASES = {"pilot": 50, "full": 300}
# Explicit tags, never floating aliases: `qwen3:4b` points to the *thinking* variant.
MODELS = {"qwen3-4b": "qwen3:4b-instruct-2507-q4_K_M", "gemma3-4b": "gemma3:4b-it-q4_K_M"}
EMBED_MODEL = "BAAI/bge-m3"
MAX_SEQ = 128
TOPK = 10
NUM_CTX = 4096
NUM_PREDICT = {"translate": 2048, "extract": 1024, "select": 64}
PROMPTS = {
    "translate": "exp03_translate_pt_en_v1",
    "extract": "exp03_extract_v1",
    "select": "exp03_select_v1",
}
LLM_ARMS = ("A", "B", "C")
REGISTERS = ("technical", "lay", "both")  # hpolab.register
TAU_GRID = [round(float(x), 2) for x in np.arange(0.30, 0.951, 0.01)]
N_BOOT = 10_000
THREADS = 8
OUT = ROOT / "results" / "exp03"
FROZEN = OUT / "frozen.json"


# ---------------------------------------------------------------- inputs


def load_jsonl(path) -> list[dict]:
    if not path.exists():
        return []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_json(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_cases(set_name: str) -> tuple[pd.DataFrame, str]:
    """Final vignettes of the set with their gold (present items) and negated (absent items).
    Only `text` ever reaches a model."""
    gen = Prompt.load(ROOT / "prompts" / GENERATOR_PROMPT)
    final = final_vignettes(
        load_jsonl(OUT / "vignettes.jsonl"), set_name, gen.sha256, GENERATOR_MODEL
    )
    rows = []
    for cid in sorted(final):
        r = final[cid]
        kept = [it for it in r["items"] if not it.get("dropped")]  # no phrase in the text
        rows.append(
            {
                "case_id": cid,
                "text": r["vignette"],
                "gold": sorted(it["hpo_id"] for it in kept if it["polarity"] == "present"),
                "negated": sorted(it["hpo_id"] for it in kept if it["polarity"] == "absent"),
                "phrases": {it["hpo_id"]: it["phrase"] for it in kept},
                "dropped": sorted(it["hpo_id"] for it in r["items"] if it.get("dropped")),
            }
        )
    return pd.DataFrame(rows), gen.sha256


def pa_terms(ont: Ontology) -> set[str]:
    return {t for t in ont.terms if PHENOTYPIC_ABNORMALITY in ont.ancestors(t)}


def build_indexes(ont: Ontology) -> tuple[dict[str, TermIndex], dict[str, str]]:
    """English-only index (label + exact synonyms, as in Exp 01) and bilingual index (the same
    plus official PT labels), both restricted to terms under HP:0000118."""
    pa = pa_terms(ont)
    en = [(t, i) for t, i in index_entries(ont, ("exact",)) if i in pa]
    pt = pt_labels(load_babelon(RAW_DIR / "hp-pt.babelon.tsv"), ont)
    pt = pt[pt["hpo_id"].isin(pa)]
    bi = en + list(zip(pt["pt_label"], pt["hpo_id"], strict=True))
    pt_map = dict(zip(pt["hpo_id"], pt["pt_label"], strict=True))
    return {"en": TermIndex.build(en), "bi": TermIndex.build(bi)}, pt_map


# ---------------------------------------------------------------- local models


class Encoder:
    """bge-m3 on the GPU for one stage; freed on exit so an LLM can use the memory."""

    def __init__(self, device: str):
        self.device, self.model = device, None

    def __enter__(self) -> Encoder:
        self.model = embed.load_model(EMBED_MODEL, MAX_SEQ, self.device)
        return self

    def __exit__(self, *exc) -> None:
        self.model = None
        gc.collect()
        if self.device == "cuda":
            torch.cuda.empty_cache()

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1024), dtype=np.float32)
        return embed.encode(self.model, texts)


class CallCache:
    """Every Ollama call, keyed by model digest + prompt + input + options."""

    def __init__(self, path):
        self.path = path
        self.records = {r["key"]: r for r in load_jsonl(path)}
        self.new = 0

    def call(self, model_key: str, digest: str, step: str, prompt: Prompt, user: str, fmt=None):
        opts = {
            "temperature": 0,
            "seed": SEED,
            "num_ctx": NUM_CTX,
            "num_predict": NUM_PREDICT[step],
        }
        blob = json.dumps(
            [digest, prompt.sha256, user, fmt, opts], sort_keys=True, ensure_ascii=False
        )
        key = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        if key in self.records:
            return self.records[key]
        r = ollama.chat(MODELS[model_key], prompt.system, user, opts, fmt)
        used = (r["prompt_eval_count"] or 0) + (r["eval_count"] or 0)
        rec = {
            "key": key,
            "model": model_key,
            "tag": MODELS[model_key],
            "digest": digest,
            "step": step,
            "prompt_sha256": prompt.sha256,
            "options": opts,
            "user": user,
            "at": datetime.now(UTC).isoformat(timespec="seconds"),
            **r,
            "seconds": round(((r["total_duration"] or 0) - (r["load_duration"] or 0)) / 1e9, 3),
            "ctx_full": used >= NUM_CTX - 16,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(self.path, "at", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self.records[key] = rec
        self.new += 1
        return rec


def stage_extract(cases, model_key, digest, prompts, cache) -> dict:
    """A: extract from the PT note. B: translate to English, then the same extraction."""
    out: dict = {"A": {}, "B": {}}
    for k, c in enumerate(cases.itertuples(), 1):
        a = cache.call(
            model_key,
            digest,
            "extract",
            prompts["extract"],
            prompts["extract"].render(note=c.text),
            EXTRACT_SCHEMA,
        )
        t = cache.call(
            model_key,
            digest,
            "translate",
            prompts["translate"],
            prompts["translate"].render(note=c.text),
        )
        b = cache.call(
            model_key,
            digest,
            "extract",
            prompts["extract"],
            prompts["extract"].render(note=t["content"].strip()),
            EXTRACT_SCHEMA,
        )
        out["A"][c.case_id] = {"extract": a}
        out["B"][c.case_id] = {"translate": t, "extract": b}
        if k % 10 == 0:
            print(f"  [{model_key}] extract {k}/{len(cases)}")
    return out


def queries_of(ext: dict) -> list[tuple[str, int, str]]:
    """(case_id, finding position, text) for every 'present' finding of an arm."""
    out = []
    for cid in sorted(ext):
        present, _, _ = parse_extraction(ext[cid]["extract"]["content"])
        out += [(cid, j, f) for j, f in enumerate(present)]
    return out


def stage_retrieve(ext, enc, emb, indexes) -> dict:
    """Top-10 candidates per finding. A and C share A's findings (and their embeddings)."""
    res = {}
    for arm, src, index in (("A", "A", "en"), ("C", "A", "bi"), ("B", "B", "en")):
        q = queries_of(ext[src])
        t0 = time.perf_counter()
        Q = enc.encode([x[2] for x in q])
        t_enc = time.perf_counter() - t0
        t0 = time.perf_counter()
        pos, sc = top_ids(Q, emb[index], indexes[index], TOPK)
        t_search = time.perf_counter() - t0
        ids = indexes[index].ids
        res[arm] = {
            "queries": q,
            "candidates": [[ids[p] for p in row] for row in pos],
            "scores": [[round(float(s), 4) for s in row] for row in sc],
            "seconds_per_query": (t_enc + t_search) / len(q) if q else 0.0,
        }
    return res


def stage_select(ret, model_key, digest, prompt, labels_en, cache) -> dict:
    out = {}
    for arm in LLM_ARMS:
        r = ret[arm]
        picks = []
        for k, ((cid, j, text), cands) in enumerate(
            zip(r["queries"], r["candidates"], strict=True), 1
        ):
            user = prompt.render(finding=text, candidates=candidate_lines(cands, labels_en))
            rec = cache.call(model_key, digest, "select", prompt, user, select_schema(cands))
            picks.append(
                {
                    "case_id": cid,
                    "pos": j,
                    "rec": rec,
                    "selected": parse_selection(rec["content"], cands),
                }
            )
            if k % 200 == 0:
                print(f"  [{model_key}/{arm}] select {k}/{len(r['queries'])}")
        out[arm] = picks
    return out


def assemble(cases, model_key, ext, ret, sel) -> list[dict]:
    """One prediction record per (model, arm, case)."""
    records = []
    for arm in LLM_ARMS:
        src = "B" if arm == "B" else "A"
        r = ret[arm]
        by_case: dict[str, list[dict]] = {}
        for (cid, _j, text), cands, scores, pick in zip(
            r["queries"], r["candidates"], r["scores"], sel[arm], strict=True
        ):
            by_case.setdefault(cid, []).append(
                {
                    "text": text,
                    "candidates": cands,
                    "scores": scores,
                    "selected": pick["selected"],
                    "seconds": pick["rec"]["seconds"],
                    "ctx_full": pick["rec"]["ctx_full"],
                    "truncated": pick["rec"]["done_reason"] == "length",
                }
            )
        for c in cases.itertuples():
            e = ext[src][c.case_id]
            present, absent, ok = parse_extraction(e["extract"]["content"])
            findings = by_case.get(c.case_id, [])
            llm_calls = [e["extract"]] + ([e["translate"]] if arm == "B" else [])
            seconds_llm = sum(x["seconds"] for x in llm_calls) + sum(f["seconds"] for f in findings)
            seconds_ret = r["seconds_per_query"] * len(findings)
            flags = []
            if not ok:
                flags.append("extract_unparsed")
            if any(x["done_reason"] == "length" for x in llm_calls) or any(
                f["truncated"] for f in findings
            ):
                flags.append("output_truncated")
            if any(x["ctx_full"] for x in llm_calls) or any(f["ctx_full"] for f in findings):
                flags.append("ctx_full")
            records.append(
                {
                    "model": model_key,
                    "arm": arm,
                    "case_id": c.case_id,
                    "pred": sorted({f["selected"] for f in findings if f["selected"]}),
                    "gold": c.gold,
                    "negated": c.negated,
                    "dropped": c.dropped,
                    "findings": [
                        {k: f[k] for k in ("text", "candidates", "scores", "selected")}
                        for f in findings
                    ],
                    "absent": absent,
                    "translation": e["translate"]["content"] if arm == "B" else None,
                    "flags": flags,
                    "seconds": {
                        "llm": round(seconds_llm, 3),
                        "retrieval": round(seconds_ret, 4),
                        "total": round(seconds_llm + seconds_ret, 3),
                    },
                }
            )
    return records


# ---------------------------------------------------------------- baseline and diagnostics


def baseline_segments(cases, enc, emb, index) -> tuple[dict, float]:
    segs = [(c.case_id, s) for c in cases.itertuples() for s in segments(c.text)]
    t0 = time.perf_counter()
    pos, sc = top_ids(enc.encode([s for _, s in segs]), emb, index, 1)
    per_seg = (time.perf_counter() - t0) / max(len(segs), 1)
    out: dict[str, list[dict]] = {c: [] for c in cases["case_id"]}
    for (cid, s), p, v in zip(segs, pos[:, 0], sc[:, 0], strict=True):
        out[cid].append({"text": s, "top1": index.ids[p], "score": round(float(v), 4)})
    return out, per_seg


def baseline_records(cases, segs: dict, tau: float, per_seg: float) -> list[dict]:
    recs = []
    for c in cases.itertuples():
        ss = segs[c.case_id]
        recs.append(
            {
                "model": "none",
                "arm": "baseline",
                "case_id": c.case_id,
                "pred": sorted({s["top1"] for s in ss if s["score"] >= tau}),
                "gold": c.gold,
                "negated": c.negated,
                "dropped": c.dropped,
                "segments": ss,
                "tau": tau,
                "flags": [],
                "seconds": {
                    "llm": 0.0,
                    "retrieval": round(per_seg * len(ss), 4),
                    "total": round(per_seg * len(ss), 4),
                },
            }
        )
    return recs


def choose_tau(cases, segs: dict) -> dict:
    """Pilot only: the grid value with the best micro-F1; ties go to the higher tau."""
    curve = {}
    for tau in TAU_GRID:
        c = np.array(
            [
                cm.counts({s["top1"] for s in segs[x.case_id] if s["score"] >= tau}, set(x.gold))
                for x in cases.itertuples()
            ]
        )
        curve[tau] = round(cm.micro_f1(c), 4)
    best = max(curve.values())
    tau = max(t for t, f in curve.items() if f == best)
    return {
        "tau": tau,
        "micro_f1_at_tau": best,
        "grid": curve,
        "rule": "max micro-F1, ties -> higher tau",
    }


def oracle_spans(cases, enc, emb, index) -> dict:
    """bge-m3 on the generator's own phrase for each gold term (no LLM): an upper bound on
    retrieval when extraction is perfect, and a measure of how hard the phrasing is."""
    pairs = [(c.case_id, g, c.phrases[g]) for c in cases.itertuples() for g in c.gold]
    pos, _ = top_ids(enc.encode([p for *_, p in pairs]), emb, index, TOPK)
    ranks = []
    for (_, g, _), row in zip(pairs, pos, strict=True):
        ids = [index.ids[p] for p in row]
        ranks.append(ids.index(g) + 1 if g in ids else None)
    n = len(ranks)
    return {
        "n_gold_phrases": n,
        "top1": round(sum(r == 1 for r in ranks) / n, 4) if n else None,
        "top10": round(sum(r is not None for r in ranks) / n, 4) if n else None,
    }


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


def gold_covariates(cases, ont: Ontology, pt_map: dict) -> pd.DataFrame:
    """Per gold term: has an official PT label; the generator's phrase equals it; surface
    similarity of the phrase to the English label (back-translation threat, PREREG); and the
    register of the item in the note: technical, lay or both (hpolab.register)."""
    rows = []
    for c in cases.itertuples():
        for g in c.gold:
            phrase = c.phrases[g]
            sim = fuzz.ratio(fold(phrase), fold(ont.terms[g].label))
            reg = classify(c.text, phrase, ont.terms[g].label, pt_map.get(g))["register"]
            rows.append(
                {
                    "case_id": c.case_id,
                    "hpo_id": g,
                    "has_pt_label": g in pt_map,
                    "phrase_is_pt_label": g in pt_map and _norm(phrase) == _norm(pt_map[g]),
                    "sim_en_label": round(sim, 1),
                    "sim_bin": "<50" if sim < 50 else "50-80" if sim < 80 else ">=80",
                    "register": reg,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- metrics


def arm_metrics(recs: list[dict], ont: Ontology, idx: np.ndarray, cov: pd.DataFrame) -> dict:
    recs = sorted(recs, key=lambda r: r["case_id"])
    c = np.array([cm.counts(set(r["pred"]), set(r["gold"])) for r in recs])
    s = cm.summary(c)
    neg_hit = np.array([len(set(r["pred"]) & set(r["negated"])) for r in recs])
    neg_den = np.array([len(r["negated"]) for r in recs])
    s["negation_fp"] = {
        "rate": round(float(neg_hit.sum() / neg_den.sum()), 4) if neg_den.sum() else None,
        "n_negated_shown": int(neg_den.sum()),
        "n_negated_predicted": int(neg_hit.sum()),
        "ci95": cm.boot_ratio_ci(neg_hit, neg_den, idx),
    }
    n_near = n_swap = 0
    cats: Counter = Counter()
    for r in recs:
        pred, gold, neg = set(r["pred"]), set(r["gold"]), set(r["negated"])
        fp, fn = pred - gold, gold - pred
        n_near += len(cm.near_miss_pairs(fp, fn, ont))
        n_swap += len(cm.swap_pairs(fp, fn, ont))
        drop = frozenset(r.get("dropped", []))
        cats.update(cm.fp_category(p, gold, neg, ont, drop) for p in fp)
    tp, fp, fn = s["tp"], s["fp"], s["fn"]
    s["near_miss"] = {
        "pairs": n_near,
        "share_of_fp": round(n_near / fp, 4) if fp else None,
        "relaxed_micro": cm.prf(tp + n_near, fp - n_near, fn - n_near),
        "note": "FP that is a direct is_a parent/child of an FN of the same case, paired 1:1",
    }
    s["hand_foot_swap"] = {"pairs": n_swap, "share_of_fp": round(n_swap / fp, 4) if fp else None}
    s["fp_categories"] = dict(sorted(cats.items()))
    secs = [r["seconds"]["total"] for r in recs]
    s["seconds_per_case"] = {
        "mean": round(float(np.mean(secs)), 2),
        "median": round(float(np.median(secs)), 2),
        "p90": round(float(np.quantile(secs, 0.9)), 2),
    }
    s["flags"] = dict(Counter(f for r in recs for f in r["flags"]))
    if recs and recs[0]["arm"] != "baseline":
        cand = [set().union(*[set(f["candidates"]) for f in r["findings"]]) for r in recs]
        hit = sum(len(cs & set(r["gold"])) for cs, r in zip(cand, recs, strict=True))
        n_gold = sum(len(r["gold"]) for r in recs)
        n_find = sum(len(r["findings"]) for r in recs)
        s["retrieval_ceiling_recall"] = round(hit / n_gold, 4)
        s["selection_loss"] = round(hit / n_gold - s["micro"]["recall"], 4)
        s["findings_per_case"] = round(n_find / len(recs), 2)
        s["absent_per_case"] = round(sum(len(r["absent"]) for r in recs) / len(recs), 2)
        s["none_rate"] = (
            round(sum(f["selected"] is None for r in recs for f in r["findings"]) / n_find, 4)
            if n_find
            else None
        )
    hits = {(r["case_id"], g) for r in recs for g in set(r["pred"]) & set(r["gold"])}
    hit_col = [(cid, g) in hits for cid, g in zip(cov["case_id"], cov["hpo_id"], strict=True)]
    cv = cov.assign(hit=hit_col)
    s["recall_by_stratum"] = {
        col: {
            str(k): {"n": len(g), "recall": round(float(g["hit"].mean()), 4)}
            for k, g in cv.groupby(col)
        }
        for col in ("has_pt_label", "phrase_is_pt_label", "sim_bin", "register")
    }
    return s


def compute_metrics(records, cases, ont, pt_map, cov) -> dict:
    idx = cm.bootstrap_indices(len(cases), N_BOOT, SEED)
    groups: dict[str, list[dict]] = {}
    for r in records:
        groups.setdefault(f"{r['model']}/{r['arm']}", []).append(r)
    arms = {k: arm_metrics(v, ont, idx, cov) for k, v in sorted(groups.items())}

    def counts_of(key):
        rs = sorted(groups[key], key=lambda r: r["case_id"])
        return np.array([cm.counts(set(r["pred"]), set(r["gold"])) for r in rs])

    case_ids = sorted(cases["case_id"])
    reg_of = {(r.case_id, r.hpo_id): r.register for r in cov.itertuples()}
    totals = np.array(
        [
            [sum(reg_of[(cid, g)] == reg for g in gold) for reg in REGISTERS]
            for cid, gold in sorted(zip(cases["case_id"], cases["gold"], strict=True))
        ]
    )

    def reg_hits(key):
        by_case = {r["case_id"]: set(r["pred"]) & set(r["gold"]) for r in groups[key]}
        return np.array(
            [
                [sum(reg_of[(cid, g)] == reg for g in by_case[cid]) for reg in REGISTERS]
                for cid in case_ids
            ]
        )

    tech, lay = REGISTERS.index("technical"), REGISTERS.index("lay")
    register = {}
    for key in sorted(groups):
        h = reg_hits(key)
        register[key] = {
            "recall": cm.group_recall(h, totals, idx, list(REGISTERS)),
            "technical_minus_lay": cm.recall_diff(h, h, totals, idx, tech, lay),
        }
    for m in MODELS:
        if f"{m}/A" not in groups:
            continue
        ha, hb, hc = (reg_hits(f"{m}/{a}") for a in LLM_ARMS)
        register[f"{m}/between_arms"] = {
            reg: {
                "A-B": cm.recall_diff(ha, hb, totals, idx, j, j),
                "C-A": cm.recall_diff(hc, ha, totals, idx, j, j),
            }
            for j, reg in enumerate(REGISTERS)
        }

    comparisons = {}
    for m in MODELS:
        if f"{m}/A" not in groups:
            continue
        pairs = {"A-B": ("A", "B"), "C-A": ("C", "A")}
        comp = {
            k: cm.paired_diff(counts_of(f"{m}/{a}"), counts_of(f"{m}/{b}"), idx)
            for k, (a, b) in pairs.items()
        }
        for a in LLM_ARMS:
            comp[f"{a}-baseline"] = cm.paired_diff(
                counts_of(f"{m}/{a}"), counts_of("none/baseline"), idx
            )
        comparisons[m] = comp
    models = list(MODELS)
    if all(f"{m}/A" in groups for m in models):
        comparisons["models_exploratory"] = {
            f"{arm}: {models[1]}-{models[0]}": cm.paired_diff(
                counts_of(f"{models[1]}/{arm}"), counts_of(f"{models[0]}/{arm}"), idx
            )
            for arm in LLM_ARMS
        }
    return {
        "n_cases": len(cases),
        "n_gold_terms": int(sum(len(g) for g in cases["gold"])),
        "n_negated_terms": int(sum(len(n) for n in cases["negated"])),
        "headline": "micro-F1, exact HPO id match; per-case sets",
        "bootstrap": {"unit": "case", "n_boot": N_BOOT, "seed": SEED, "intervals": "percentile"},
        "arms": arms,
        "comparisons": comparisons,
        "register": register,
    }


def errors_table(records, ont: Ontology, pt_map: dict, cases) -> pd.DataFrame:
    phrase = {c.case_id: c.phrases for c in cases.itertuples()}
    rows = []
    for r in records:
        pred, gold, neg = set(r["pred"]), set(r["gold"]), set(r["negated"])
        fp, fn = pred - gold, gold - pred
        near = dict(cm.near_miss_pairs(fp, fn, ont))
        swap = dict(cm.swap_pairs(fp, fn, ont))
        partner = {**{g: p for p, g in near.items()}, **{g: p for p, g in swap.items()}}
        if r["arm"] == "baseline":
            src = {}
            for s in r["segments"]:
                if s["score"] >= r["tau"]:
                    src.setdefault(s["top1"], []).append(s["text"])
            cands = set()
        else:
            src = {}
            for f in r["findings"]:
                if f["selected"]:
                    src.setdefault(f["selected"], []).append(f["text"])
            cands = set().union(*[set(f["candidates"]) for f in r["findings"]])
        base = {"model": r["model"], "arm": r["arm"], "case_id": r["case_id"]}
        for p in sorted(fp):
            rows.append(
                {
                    **base,
                    "type": "FP",
                    "hpo_id": p,
                    "label_en": ont.terms[p].label,
                    "label_pt": pt_map.get(p, ""),
                    "category": cm.fp_category(p, gold, neg, ont, frozenset(r.get("dropped", []))),
                    "near_miss_of": near.get(p, ""),
                    "hand_foot_swap_of": swap.get(p, ""),
                    "paired_with_fp": "",
                    "retrievable": "",
                    "text": " | ".join(src.get(p, [])),
                }
            )
        for g in sorted(fn):
            rows.append(
                {
                    **base,
                    "type": "FN",
                    "hpo_id": g,
                    "label_en": ont.terms[g].label,
                    "label_pt": pt_map.get(g, ""),
                    "category": "",
                    "near_miss_of": "",
                    "hand_foot_swap_of": "",
                    "text": phrase[r["case_id"]].get(g, ""),
                    "retrievable": (g in cands) if r["arm"] != "baseline" else "",
                    "paired_with_fp": partner.get(g, ""),
                }
            )
    cols = ["model", "arm", "case_id", "type", "hpo_id", "label_en", "label_pt", "category"]
    cols += ["near_miss_of", "hand_foot_swap_of", "paired_with_fp", "retrievable", "text"]
    return pd.DataFrame(rows, columns=cols).sort_values(
        ["model", "arm", "case_id", "type", "hpo_id"]
    )


# ---------------------------------------------------------------- hypotheses (full run)


def _as_bool(v):
    """numpy booleans -> bool, also inside a result dict, so the output is plain JSON."""
    if isinstance(v, dict):
        return {k: bool(x) if k == "confirmed" else x for k, x in v.items()}
    return bool(v)


def evaluate_hypotheses(m: dict) -> dict:
    """Criteria copied from results/exp03/PREREG.md (written before any result)."""
    arms, comp = m["arms"], m["comparisons"]
    base = arms["none/baseline"]
    out: dict = {}

    def per(f) -> dict:
        return {k: _as_bool(f(k)) for k in MODELS}

    def h1(k):
        d = comp[k]["A-B"]
        return {"diff": d["diff"], "ci97_5": d["ci97_5"], "confirmed": d["ci97_5"][0] > -0.03}

    def h2(k):
        d = comp[k]["C-A"]
        return {
            "diff": d["diff"],
            "ci95": d["ci95"],
            "confirmed": d["ci95"][0] > 0 and d["diff"] <= 0.05,
        }

    def h3(k):
        d = comp[k]["A-baseline"]
        return {
            "diff": d["diff"],
            "ci95": d["ci95"],
            "confirmed": d["diff"] >= 0.05 and d["ci95"][0] > 0,
        }

    def h4(k):
        a = arms[f"{k}/A"]["negation_fp"]["rate"]
        b = base["negation_fp"]["rate"]
        return {"A_rate": a, "baseline_rate": b, "confirmed": a <= 0.10 and b >= 0.25}

    def h5(k):
        a = arms[f"{k}/A"]
        return {
            "ceiling": a["retrieval_ceiling_recall"],
            "selection_loss": a["selection_loss"],
            "confirmed": a["retrieval_ceiling_recall"] >= 0.75 and a["selection_loss"] >= 0.10,
        }

    for name, f in (
        ("H1_A_noninferior_to_B_margin_0.03", h1),
        ("H2_C_better_than_A_gain_le_0.05", h2),
        ("H3_A_beats_baseline_by_0.05", h3),
        ("H4_negation_A_le_0.10_baseline_ge_0.25", h4),
        ("H5_ceiling_ge_0.75_selection_loss_ge_0.10", h5),
    ):
        res = per(f)
        out[name] = {
            "per_model": res,
            "confirmed_both_models": all(v["confirmed"] for v in res.values()),
        }

    def a(k):
        return arms[f"{k}/A"]

    exp = {
        "E1_A_f1_in_0.35_0.65": per(lambda k: 0.35 <= a(k)["micro"]["f1"] <= 0.65),
        "E2_near_miss_ge_0.10_of_fp": per(
            lambda k: (a(k)["near_miss"]["share_of_fp"] or 0) >= 0.10
        ),
        "E3_hand_foot_le_0.02_of_fp": per(
            lambda k: (a(k)["hand_foot_swap"]["share_of_fp"] or 0) <= 0.02
        ),
        "E4_time": per(
            lambda k: (
                a(k)["seconds_per_case"]["median"] <= 30
                and arms[f"{k}/B"]["seconds_per_case"]["median"]
                >= 1.5 * a(k)["seconds_per_case"]["median"]
            )
        ),
        "E5_pt_label_strata": per(
            lambda k: (
                a(k)["recall_by_stratum"]["has_pt_label"]["True"]["recall"]
                > a(k)["recall_by_stratum"]["has_pt_label"]["False"]["recall"]
                and (
                    arms[f"{k}/C"]["recall_by_stratum"]["has_pt_label"]["True"]["recall"]
                    - a(k)["recall_by_stratum"]["has_pt_label"]["True"]["recall"]
                )
                > (
                    arms[f"{k}/C"]["recall_by_stratum"]["has_pt_label"]["False"]["recall"]
                    - a(k)["recall_by_stratum"]["has_pt_label"]["False"]["recall"]
                )
            )
        ),
    }
    reg = m["register"]

    def tml(key: str) -> dict:
        return reg[key]["technical_minus_lay"]

    def h6(k):
        keys = [f"{k}/{arm}" for arm in LLM_ARMS] + ["none/baseline"]
        per_arm = {key: tml(key) for key in keys}
        ok = all(v["ci95"] is not None and v["ci95"][0] > 0 for v in per_arm.values())
        return {"per_arm": per_arm, "confirmed": ok}

    res = per(h6)
    out["H6_lay_harder_than_technical"] = {
        "per_model": res,
        "confirmed_both_models": all(v["confirmed"] for v in res.values()),
    }

    def between(k, reg_name, pair) -> float:
        return reg[f"{k}/between_arms"][reg_name][pair]["diff"] or 0.0  # None: empty group

    exp["E6_A_vs_B_gap_larger_in_lay"] = per(
        lambda k: abs(between(k, "lay", "A-B")) > abs(between(k, "technical", "A-B"))
    )
    exp["E7_C_vs_A_gain_larger_in_technical"] = per(
        lambda k: between(k, "technical", "C-A") > between(k, "lay", "C-A")
    )
    exp["E8_baseline_drop_larger_than_A"] = per(
        lambda k: (tml("none/baseline")["diff"] or 0.0) > (tml(f"{k}/A")["diff"] or 0.0)
    )
    return {"hypotheses": out, "expectations": exp}


# ---------------------------------------------------------------- run


def load_prompts() -> dict[str, Prompt]:
    return {step: Prompt.load(ROOT / "prompts" / stem) for step, stem in PROMPTS.items()}


def check_frozen(prompts: dict[str, Prompt]) -> float:
    if not FROZEN.exists():
        sys.exit(
            "frozen.json missing: run the pilot, then --freeze, and commit before the full run."
        )
    fz = json.loads(FROZEN.read_text(encoding="utf-8"))
    for step, p in prompts.items():
        want = fz["prompts"][step]
        if want["stem"] != PROMPTS[step] or want["sha256"] != p.sha256:
            sys.exit(f"Prompt {step!r} differs from frozen.json; the full run uses frozen prompts.")
    if fz["models"] != MODELS:
        sys.exit("MODELS differ from frozen.json.")
    gen = Prompt.load(ROOT / "prompts" / GENERATOR_PROMPT)
    if fz["generator_prompt"] != {"stem": GENERATOR_PROMPT, "sha256": gen.sha256}:
        sys.exit("Generator prompt differs from frozen.json.")
    return float(fz["baseline_tau"])


def freeze() -> None:
    th = json.loads((OUT / "pilot" / "threshold.json").read_text(encoding="utf-8"))
    prompts = load_prompts()
    write_json(
        FROZEN,
        {
            "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "pilot_config_git": json.loads(
                (OUT / "pilot" / "config.json").read_text(encoding="utf-8")
            )["git"],
            "baseline_tau": th["tau"],
            "prompts": {s: {"stem": PROMPTS[s], "sha256": p.sha256} for s, p in prompts.items()},
            "generator_prompt": {
                "stem": GENERATOR_PROMPT,
                "sha256": Prompt.load(ROOT / "prompts" / GENERATOR_PROMPT).sha256,
            },
            "models": MODELS,
        },
    )
    print(f"Wrote {FROZEN}; commit it before the full run.")


def preflight() -> dict:
    try:
        ver = ollama.version()
    except OSError as e:
        sys.exit(f"Ollama server not reachable at {ollama.base_url()}: {e}")
    info = {"ollama_version": ver, "host": ollama.base_url(), "models": {}}
    for key, tag in MODELS.items():
        dg = ollama.digest(tag)
        if dg is None:
            sys.exit(f"Model {tag} not pulled: ollama pull {tag}")
        details = ollama.show(tag).get("details", {})
        info["models"][key] = {"tag": tag, "digest": dg, "details": details}
    return info


def check_prompt_examples(ont: Ontology) -> list[dict]:
    """No drawn case (pilot, full, reserve) may contain an extraction prompt example term."""
    sample = pd.read_csv(OUT / "sample.csv", dtype=str, keep_default_na=False)
    case_terms = {
        r.case_id: set(filter(None, f"{r.observed}|{r.excluded}".split("|")))
        for r in sample.itertuples()
    }
    clashes = example_term_clashes(case_terms, ont)
    if clashes:
        sys.exit(f"Extraction prompt example terms occur in drawn cases: {clashes}")
    return clashes


def run(args, ont, cases, gen_sha, out_dir) -> None:
    prompts = load_prompts()
    check_prompt_examples(ont)
    tau = check_frozen(prompts) if args.set == "full" else None
    pre = preflight()
    device = embed.resolve_device(args.device)
    indexes, pt_map = build_indexes(ont)
    labels_en = {i: ont.terms[i].label for i in indexes["en"].ids}
    cache = CallCache(out_dir / "ollama_calls.jsonl.gz")
    stages: dict = {"gpu_at_start": gpu.info()}
    t_run = time.perf_counter()

    with gpu.PeakMemory() as pk, Encoder(device) as enc:
        t0 = time.perf_counter()
        emb_bi, cached = embed.encode_cached(
            enc.model, EMBED_MODEL, indexes["bi"].texts, f"exp03-idx-bi_hpo-{ont.version}"
        )
        emb = {"bi": emb_bi, "en": emb_bi[subindex_rows(indexes["bi"], indexes["en"])]}
        segs, per_seg = baseline_segments(cases, enc, emb["en"], indexes["en"])
        oracle = oracle_spans(cases, enc, emb["en"], indexes["en"])
        stages["embed_index_baseline"] = {
            "seconds": round(time.perf_counter() - t0, 1),
            "index_from_cache": cached,
            "truncated_index_texts": embed.count_truncated(enc.model, indexes["bi"].texts),
        }
    stages["embed_index_baseline"]["peak_vram_mib"] = pk.peak_mib

    if args.set == "pilot":
        th = choose_tau(cases, segs)
        write_json(out_dir / "threshold.json", th)
        tau = th["tau"]
    records = baseline_records(cases, segs, tau, per_seg)

    for model_key in args.models:
        digest = pre["models"][model_key]["digest"]
        tag = MODELS[model_key]
        print(f"[{model_key}] stage 1: translate + extract")
        with gpu.PeakMemory() as pk:
            t0 = time.perf_counter()
            ext = stage_extract(cases, model_key, digest, prompts, cache)
            loaded = [m for m in ollama.ps() if m["name"] == tag]
            ollama.unload(tag)
        stages[f"{model_key}/extract"] = {
            "seconds": round(time.perf_counter() - t0, 1),
            "peak_vram_mib": pk.peak_mib,
            "ollama_ps": [{k: m.get(k) for k in ("size", "size_vram")} for m in loaded],
        }
        print(f"[{model_key}] stage 2: retrieve")
        with gpu.PeakMemory() as pk, Encoder(device) as enc:
            t0 = time.perf_counter()
            ret = stage_retrieve(ext, enc, emb, indexes)
        stages[f"{model_key}/retrieve"] = {
            "seconds": round(time.perf_counter() - t0, 1),
            "peak_vram_mib": pk.peak_mib,
        }
        print(f"[{model_key}] stage 3: select")
        with gpu.PeakMemory() as pk:
            t0 = time.perf_counter()
            sel = stage_select(ret, model_key, digest, prompts["select"], labels_en, cache)
            loaded = [m for m in ollama.ps() if m["name"] == tag]
            ollama.unload(tag)
        stages[f"{model_key}/select"] = {
            "seconds": round(time.perf_counter() - t0, 1),
            "peak_vram_mib": pk.peak_mib,
            "ollama_ps": [{k: m.get(k) for k in ("size", "size_vram")} for m in loaded],
        }
        records += assemble(cases, model_key, ext, ret, sel)

    with (out_dir / "predictions.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    cov = gold_covariates(cases, ont, pt_map)
    metrics = compute_metrics(records, cases, ont, pt_map, cov)
    metrics["oracle_spans_bge_m3_en_index"] = oracle
    metrics["baseline_tau"] = tau
    write_json(out_dir / "metrics.json", metrics)
    errors_table(records, ont, pt_map, cases).to_csv(out_dir / "errors.csv", index=False)
    if args.set == "full":
        write_json(out_dir / "hypotheses.json", evaluate_hypotheses(metrics))

    cfg = base_config("exp03_extraction", SEED)
    cfg.update(
        {
            "set": args.set,
            "hpo_version_in_file": ont.version,
            "n_cases": len(cases),
            "vignettes": {"generator_model": GENERATOR_MODEL, "generator_prompt_sha256": gen_sha},
            "ollama": pre,
            "llm_options": {
                "temperature": 0,
                "seed": SEED,
                "num_ctx": NUM_CTX,
                "num_predict": NUM_PREDICT,
            },
            "prompts": {s: {"stem": PROMPTS[s], "sha256": p.sha256} for s, p in prompts.items()},
            "retrieval": {
                "model": EMBED_MODEL,
                "revision": embed.model_revision(EMBED_MODEL),
                "max_seq_length": MAX_SEQ,
                "topk": TOPK,
                "scope": "active terms under HP:0000118 (HP:0000118 itself excluded)",
                "index_en": {
                    "texts": "label + exact synonyms",
                    "n_texts": len(indexes["en"].texts),
                    "n_ids": len(indexes["en"].ids),
                },
                "index_bi": {
                    "texts": "index_en + official PT labels",
                    "n_texts": len(indexes["bi"].texts),
                    "n_ids": len(indexes["bi"].ids),
                    "n_pt_labels": len(pt_map),
                },
                "encode_device": embed.device_info(device),
            },
            "selector_sees": "finding text + candidate id and English label (all arms)",
            "extract_prompt_example_terms": PROMPT_EXAMPLE_TERMS,
            "items_dropped_no_phrase": int(cases["dropped"].map(len).sum()),
            "baseline": {
                "segmenter": "hpolab.extraction.segments",
                "tau": tau,
                "tau_source": "pilot grid" if args.set == "pilot" else "frozen.json",
            },
            "stages": stages,
            "new_ollama_calls": cache.new,
            "wall_seconds": round(time.perf_counter() - t_run, 1),
        }
    )
    write_json(out_dir / "config.json", cfg)
    print(f"Wrote {out_dir}")


def metrics_only(args, ont, cases, out_dir) -> None:
    records = load_jsonl(out_dir / "predictions.jsonl")
    _, pt_map = build_indexes(ont)
    cov = gold_covariates(cases, ont, pt_map)
    metrics = compute_metrics(records, cases, ont, pt_map, cov)
    old = json.loads((out_dir / "metrics.json").read_text(encoding="utf-8"))
    for k in ("oracle_spans_bge_m3_en_index", "baseline_tau"):
        metrics[k] = old.get(k)
    write_json(out_dir / "metrics.json", metrics)
    errors_table(records, ont, pt_map, cases).to_csv(out_dir / "errors.csv", index=False)
    if args.set == "full":
        write_json(out_dir / "hypotheses.json", evaluate_hypotheses(metrics))
    print(f"Recomputed metrics in {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", required=True, choices=["pilot", "full"])
    parser.add_argument("--models", nargs="+", default=list(MODELS), choices=list(MODELS))
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--freeze", action="store_true", help="write frozen.json from the pilot")
    parser.add_argument("--metrics-only", action="store_true", help="recompute from predictions")
    parser.add_argument("--allow-dirty", action="store_true", help="run on uncommitted code")
    parser.add_argument("--allow-partial", action="store_true", help="fewer vignettes than planned")
    args = parser.parse_args()
    if args.freeze:
        freeze()
        return
    torch.set_num_threads(THREADS)
    if not args.allow_dirty and not args.metrics_only and paths_dirty():
        sys.exit("Refusing to run: src/, experiments/ or prompts/ has uncommitted changes.")
    ont = load_ontology(RAW_DIR / "hp.json")
    cases, gen_sha = load_cases(args.set)
    if len(cases) != N_CASES[args.set] and not args.allow_partial:
        sys.exit(f"{len(cases)} final vignettes for {args.set}, expected {N_CASES[args.set]}.")
    out_dir = OUT / "pilot" if args.set == "pilot" else OUT
    if args.metrics_only:
        metrics_only(args, ont, cases, out_dir)
    else:
        run(args, ont, cases, gen_sha, out_dir)


if __name__ == "__main__":
    main()
