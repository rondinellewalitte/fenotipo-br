"""Exp 01: PT -> HPO term normalization against an English-only index.

Queries: official PT labels of active HPO terms (hpo.pt_labels). Gold: their HPO id.
Index: English label + synonyms of every active term; no PT text goes into the index.
Main index = label + exact synonyms; ablation index = all synonym scopes.
Main scope = queries whose gold is under HP:0000118; the rest is a separate row.
Top-k uses the pessimistic rank: a tie with another id never counts as a hit.

    uv run python experiments/exp01_normalization.py --pilot   # 200 queries + time estimate
    uv run python experiments/exp01_normalization.py           # full run (clean git tree)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import numpy as np
import pandas as pd
import torch
from rapidfuzz import fuzz

from hpolab import embed
from hpolab.data import RAW_DIR, ROOT
from hpolab.hpo import (
    PHENOTYPIC_ABNORMALITY,
    Ontology,
    index_entries,
    load_babelon,
    load_ontology,
    pt_labels,
)
from hpolab.metrics import branch_summaries, holm, mcnemar, subset_summaries
from hpolab.provenance import base_config
from hpolab.retrieval import TermIndex, fold, ids_at_top, lexical_scores, rank_gold, text_key

SEED = 42
PILOT_N = 200
PILOT_INDEX_SAMPLE = 2000
TOPK = 10
CHUNK = 256
MAX_SEQ = 128
THREADS = 8
N_ERRORS = 200
OUT = ROOT / "results" / "exp01"

INDEXES = {
    "exact": ("exact",),
    "all_scopes": ("exact", "related", "broad", "narrow"),
}
MAIN_INDEX = "exact"
UNION_INDEX = "all_scopes"  # superset of every other index; embeddings are computed on it

LEXICAL = {
    "lexical_token_sort": {
        "scorer": "rapidfuzz.fuzz.token_sort_ratio",
        "preprocess": "casefold, strip accents, non-alphanumerics -> space (retrieval.fold)",
    }
}
# Prefix scheme fixed before any result was seen. e5 model card: "Use 'query: ' prefix
# for symmetric tasks such as semantic similarity, bitext mining, paraphrase retrieval."
EMBEDDINGS = {
    "e5-base": {
        "model": "intfloat/multilingual-e5-base",
        "query_prefix": "query: ",
        "index_prefix": "query: ",
        "note": "primary e5 scheme (symmetric task, per model card)",
    },
    "e5-base_qp": {
        "model": "intfloat/multilingual-e5-base",
        "query_prefix": "query: ",
        "index_prefix": "passage: ",
        "note": "variant: asymmetric retrieval prefixes",
    },
    "mpnet-multi": {
        "model": "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        "query_prefix": "",
        "index_prefix": "",
    },
    "bge-m3": {"model": "BAAI/bge-m3", "query_prefix": "", "index_prefix": ""},
}

# Pre-registered paired comparisons (results/exp01/PREREG.md): exact McNemar on top-1
# hits, main index and scope, Holm-adjusted over this list.
PRIMARY_COMPARISONS = [
    ("e5-base", "mpnet-multi"),
    ("mpnet-multi", "lexical_token_sort"),
    ("e5-base", "lexical_token_sort"),
    ("bge-m3", "e5-base"),
]

ScoreFn = Callable[[slice], np.ndarray]


def build_queries(ont: Ontology) -> pd.DataFrame:
    q = pt_labels(load_babelon(RAW_DIR / "hp-pt.babelon.tsv"), ont)
    own = {
        t.id: [fold(t.label)] + [fold(s.text) for s in t.synonyms if s.scope == "exact"]
        for t in ont.terms.values()
    }
    folded = q["pt_label"].map(fold)
    q["in_pa"] = q["hpo_id"].map(lambda i: PHENOTYPIC_ABNORMALITY in ont.ancestors(i))
    q["branches"] = q["hpo_id"].map(lambda i: "|".join(sorted(ont.top_branches(i))))
    q["identical"] = [f in own[i] for f, i in zip(folded, q["hpo_id"], strict=True)]
    q["surface_sim"] = [
        round(max(fuzz.ratio(f, e) for e in own[i]), 1)
        for f, i in zip(folded, q["hpo_id"], strict=True)
    ]
    return q.sort_values("hpo_id").reset_index(drop=True)


def near_miss(
    id_scores: np.ndarray, ranks: dict, gold_pos: np.ndarray, index: TermIndex, ont: Ontology
) -> np.ndarray:
    """Gold strictly below the top, and every id at the top score is a direct
    is_a parent or child of the gold id."""
    out = np.zeros(len(gold_pos), dtype=bool)
    for q in np.flatnonzero(ranks["rank_opt"] > 1):
        gold = index.ids[gold_pos[q]]
        out[q] = all(ont.is_neighbor(index.ids[t], gold) for t in ids_at_top(id_scores[q]))
    return out


def rank_method(score_fn: ScoreFn, gold_pos: np.ndarray, index: TermIndex, ont: Ontology) -> dict:
    parts = []
    for start in range(0, len(gold_pos), CHUNK):
        sl = slice(start, min(start + CHUNK, len(gold_pos)))
        id_scores = index.id_scores(score_fn(sl))
        r = rank_gold(id_scores, gold_pos[sl], TOPK)
        r["near_miss"] = near_miss(id_scores, r, gold_pos[sl], index, ont)
        parts.append(r)
    return {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}


def rank_rows(
    method: str, index_name: str, queries: pd.DataFrame, index: TermIndex, r: dict
) -> pd.DataFrame:
    cols = ["hpo_id", "pt_label", "en_label", "in_pa", "branches", "identical", "stale"]
    df = queries[[*cols, "surface_sim"]].copy()
    df.insert(0, "index", index_name)
    df.insert(0, "method", method)
    for k in ("rank_opt", "rank_pess", "gold_score", "top_score", "n_top", "near_miss"):
        df[k] = r[k]
    df["top_ids"] = ["|".join(index.ids[j] for j in row) for row in r["top_idx"]]
    df["top_scores"] = ["|".join(f"{s:.4f}" for s in row) for row in r["top_scores"]]
    return df


def gold_positions(queries: pd.DataFrame, index: TermIndex) -> np.ndarray:
    return np.array([index.id_pos[i] for i in queries["hpo_id"]], dtype=np.int64)


def lexical_fn(queries: pd.DataFrame, index: TermIndex) -> ScoreFn:
    q = [fold(t) for t in queries["pt_label"]]
    choices = [fold(t) for t in index.texts]
    return lambda sl: lexical_scores(q[sl], choices)


def subindex_rows(union: TermIndex, index: TermIndex) -> np.ndarray:
    """Row of each `index` string inside the union index (same text_key)."""
    row_of = {text_key(t): i for i, t in enumerate(union.texts)}
    return np.array([row_of[text_key(t)] for t in index.texts], dtype=np.int64)


def build_indexes(ont: Ontology) -> dict[str, TermIndex]:
    return {name: TermIndex.build(index_entries(ont, scopes)) for name, scopes in INDEXES.items()}


def index_info(indexes: dict[str, TermIndex]) -> dict:
    return {
        name: {
            "scopes": ["label", *INDEXES[name]],
            "n_texts": len(idx.texts),
            "n_ids": len(idx.ids),
            "n_texts_mapping_to_several_ids": idx.n_ambiguous_texts(),
        }
        for name, idx in indexes.items()
    }


def experiment_config(ont: Ontology, queries: pd.DataFrame, indexes: dict, device: str) -> dict:
    cfg = base_config("exp01_normalization", SEED)
    cfg.update(
        {
            "hpo_version_in_file": ont.version,
            "queries": {
                "source": "hp-pt.babelon.tsv",
                "filter": "predicate_id == rdfs:label, translation_status == OFFICIAL, "
                "non-empty, subject is an active HP term (hpo.pt_labels)",
                "n_total": len(queries),
                "n_main_under_HP:0000118": int(queries["in_pa"].sum()),
                "n_outside_HP:0000118": int((~queries["in_pa"]).sum()),
                "n_main_identical": int((queries["in_pa"] & queries["identical"]).sum()),
                "n_main_stale": int((queries["in_pa"] & queries["stale"]).sum()),
                "identical_definition": "fold(pt_label) equals fold() of the gold term's "
                "English label or one of its exact synonyms",
            },
            "index": {"main": MAIN_INDEX, "variants": index_info(indexes), "language": "en"},
            "ranking": {
                "unit": "unique HPO id, score = max over its strings",
                "ties": "pessimistic rank for top-k; optimistic reported separately",
                "near_miss": "gold strictly below top, and all top-scoring ids are direct "
                "is_a parent/child of gold; reported separately, never added to top-k",
                "topk_saved": TOPK,
            },
            "lexical": LEXICAL,
            "embeddings": {
                name: {**spec, "revision": embed.model_revision(spec["model"])}
                for name, spec in EMBEDDINGS.items()
            },
            "max_seq_length": MAX_SEQ,
            "encode_device": embed.device_info(device),
            "torch_threads": THREADS,
        }
    )
    return cfg


def free_model_memory(device: str) -> None:
    if device == "cuda":
        torch.cuda.empty_cache()


def write_json(path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- pilot


def pilot(ont: Ontology, queries: pd.DataFrame, indexes: dict[str, TermIndex], device: str) -> None:
    rng = np.random.default_rng(SEED)
    main = queries[queries["in_pa"]]
    sample = main.iloc[np.sort(rng.choice(len(main), PILOT_N, replace=False))]
    sample = sample.reset_index(drop=True)
    out = OUT / "pilot"
    timing: dict = {"n_queries_full": len(queries), "lexical": {}, "embeddings": {}}
    metrics: dict = {"note": f"pilot: {PILOT_N} random main-scope queries, seed {SEED}"}

    # Lexical end to end on the full indexes
    for name, index in indexes.items():
        t0 = time.perf_counter()
        r = rank_method(lexical_fn(sample, index), gold_positions(sample, index), index, ont)
        dt = time.perf_counter() - t0
        df = rank_rows("lexical_token_sort", name, sample, index, r)
        metrics.setdefault("lexical_token_sort", {})[name] = subset_summaries(df)
        timing["lexical"][name] = {
            "seconds_pilot": round(dt, 2),
            "est_seconds_full": round(dt / PILOT_N * len(queries), 1),
        }
        print(f"[lexical/{name}] {dt:.1f}s  top1={metrics['lexical_token_sort'][name]['main']}")

    # Embeddings: time a sample of index strings + the pilot queries; sanity-rank the
    # pilot queries against a mini index (sampled strings + gold strings). Mini-index
    # numbers only check the code path; they are not comparable to the full run.
    union = indexes[UNION_INDEX]
    gold_rows = [r for r, ids in enumerate(union.text_ids) if set(ids) & set(sample["hpo_id"])]
    rows = np.union1d(rng.choice(len(union.texts), PILOT_INDEX_SAMPLE, replace=False), gold_rows)
    mini = TermIndex.build((union.texts[r], t) for r in rows for t in union.text_ids[r])
    mini_gold = gold_positions(sample, mini)
    n_union = len(union.texts)

    by_model: dict[str, list[str]] = {}
    for name, spec in EMBEDDINGS.items():
        by_model.setdefault(spec["model"], []).append(name)
    for model_id, names in by_model.items():
        t0 = time.perf_counter()
        model = embed.load_model(model_id, MAX_SEQ, device)
        load_s = time.perf_counter() - t0
        embed.encode(model, ["query: warm up"] * 32)
        q_done: dict[str, float] = {}
        for name in names:
            spec = EMBEDDINGS[name]
            texts = [spec["index_prefix"] + t for t in mini.texts]
            t0 = time.perf_counter()
            P = embed.encode(model, texts)
            idx_rate = len(texts) / (time.perf_counter() - t0)
            qp = spec["query_prefix"]
            t0 = time.perf_counter()
            Q = embed.encode(model, [qp + t for t in sample["pt_label"]])
            q_rate = PILOT_N / (time.perf_counter() - t0)
            r = rank_method(lambda sl, Q=Q, P=P: Q[sl] @ P.T, mini_gold, mini, ont)
            sanity = rank_rows(name, "mini", sample, mini, r)
            est_index = n_union / idx_rate
            est_query = 0.0 if qp in q_done else len(queries) / q_rate
            q_done[qp] = q_rate
            timing["embeddings"][name] = {
                "model": model_id,
                "revision": embed.model_revision(model_id),
                "load_seconds_incl_download_if_first": round(load_s, 1),
                "index_strings_per_s": round(idx_rate, 1),
                "query_strings_per_s": round(q_rate, 1),
                "est_seconds_full": round(est_index + est_query, 1),
                "truncated_in_mini_index": embed.count_truncated(model, texts),
            }
            metrics[f"sanity_mini_index/{name}"] = {
                "n_mini_texts": len(mini.texts),
                "n_mini_ids": len(mini.ids),
                **subset_summaries(sanity)["main"],
            }
            est = est_index + est_query
            print(f"[{name}] load {load_s:.0f}s, {idx_rate:.0f} str/s, est full {est:.0f}s")
        del model
        free_model_memory(device)

    total = sum(v["est_seconds_full"] for v in timing["lexical"].values())
    total += sum(v["est_seconds_full"] for v in timing["embeddings"].values())
    timing["est_seconds_full_total"] = round(total, 1)
    timing["est_minutes_full_total"] = round(total / 60, 1)
    timing["n_union_index_texts"] = n_union
    cfg = experiment_config(ont, queries, indexes, device)
    cfg["pilot"] = {"n_queries": PILOT_N, "index_sample": PILOT_INDEX_SAMPLE}
    write_json(out / "config.json", cfg)
    write_json(out / "metrics.json", metrics)
    write_json(out / "timing.json", timing)
    print(f"Estimated full run: {timing['est_minutes_full_total']} min -> {out / 'timing.json'}")


# ---------------------------------------------------------------- full run


def errors_table(ranks: pd.DataFrame, ont: Ontology) -> pd.DataFrame:
    """Per method, main index and scope: the N_ERRORS worst misses (gold outside the
    top-10, sorted by pessimistic gold rank, worst first)."""
    sel = ranks[(ranks["index"] == MAIN_INDEX) & ranks["in_pa"] & (ranks["rank_pess"] > TOPK)]
    worst = (
        sel.sort_values(["method", "rank_pess", "hpo_id"], ascending=[True, False, True])
        .groupby("method", sort=True)
        .head(N_ERRORS)
        .copy()
    )
    tops = worst["top_ids"].str.split("|")
    scores = worst["top_scores"].str.split("|")
    for k in range(3):
        worst[f"pred{k + 1}_id"] = tops.str[k]
        worst[f"pred{k + 1}_label"] = worst[f"pred{k + 1}_id"].map(lambda i: ont.terms[i].label)
        worst[f"pred{k + 1}_score"] = scores.str[k].astype(float)
    keep = ["method", "hpo_id", "pt_label", "en_label", "branches", "identical", "stale"]
    keep += ["surface_sim", "rank_pess", "gold_score", "near_miss"]
    keep += [f"pred{k}_{f}" for k in (1, 2, 3) for f in ("id", "label", "score")]
    return worst[keep].reset_index(drop=True)


def paired_top1(ranks: pd.DataFrame) -> dict:
    sel = ranks[(ranks["index"] == MAIN_INDEX) & ranks["in_pa"]]
    hits = {
        m: g.sort_values("hpo_id")["rank_pess"].to_numpy() == 1
        for m, g in sel.groupby("method", sort=True)
    }
    tests = {
        f"{a} vs {b}": mcnemar(hits[a], hits[b])
        for a, b in PRIMARY_COMPARISONS
        if a in hits and b in hits
    }
    adjusted = holm({k: v["p_value"] for k, v in tests.items()})
    for k, v in tests.items():
        v["p_holm"] = adjusted[k]
    return tests


def full_run(
    ont: Ontology,
    queries: pd.DataFrame,
    indexes: dict[str, TermIndex],
    skip: list[str],
    device: str,
) -> None:
    cfg = experiment_config(ont, queries, indexes, device)
    cfg["skipped_methods"] = skip
    timings: dict = {}
    frames = []
    for method in LEXICAL:
        for name, index in indexes.items():
            t0 = time.perf_counter()
            r = rank_method(lexical_fn(queries, index), gold_positions(queries, index), index, ont)
            frames.append(rank_rows(method, name, queries, index, r))
            timings[f"{method}/{name}"] = round(time.perf_counter() - t0, 1)
            print(f"[{method}/{name}] {timings[f'{method}/{name}']}s")

    union = indexes[UNION_INDEX]
    rows_in_union = {name: subindex_rows(union, idx) for name, idx in indexes.items()}
    models: dict = {}
    embeddings = {m: s for m, s in EMBEDDINGS.items() if m not in skip}
    for method, spec in embeddings.items():
        t0 = time.perf_counter()
        model = models.get(spec["model"])
        if model is None:
            models.clear()
            free_model_memory(device)
            model = models[spec["model"]] = embed.load_model(spec["model"], MAX_SEQ, device)
        q_texts = [spec["query_prefix"] + t for t in queries["pt_label"]]
        p_texts = [spec["index_prefix"] + t for t in union.texts]
        Q, q_cached = embed.encode_cached(model, spec["model"], q_texts, f"ptq_hpo-{ont.version}")
        P_union, p_cached = embed.encode_cached(
            model, spec["model"], p_texts, f"idx-{UNION_INDEX}_hpo-{ont.version}"
        )
        cfg["embeddings"][method].update(
            {
                "revision": embed.model_revision(spec["model"]),
                "dim": int(Q.shape[1]),
                "truncated_index_texts": embed.count_truncated(model, p_texts),
                "truncated_queries": embed.count_truncated(model, q_texts),
                "from_cache": {"queries": q_cached, "index": p_cached},
            }
        )
        for name, index in indexes.items():
            P = P_union[rows_in_union[name]]
            r = rank_method(
                lambda sl, Q=Q, P=P: Q[sl] @ P.T, gold_positions(queries, index), index, ont
            )
            frames.append(rank_rows(method, name, queries, index, r))
        timings[method] = round(time.perf_counter() - t0, 1)
        print(f"[{method}] {timings[method]}s")

    ranks = pd.concat(frames, ignore_index=True)
    branch_labels = {b: ont.terms[b].label for b in ont.children[PHENOTYPIC_ABNORMALITY]}
    methods = [*LEXICAL, *embeddings]
    metrics = {
        "primary": {
            "index": MAIN_INDEX,
            "subset": "main (gold under HP:0000118)",
            "headline": "top-k with pessimistic ties",
        },
        "results": {
            m: {
                name: subset_summaries(ranks[(ranks["method"] == m) & (ranks["index"] == name)])
                for name in indexes
            }
            for m in methods
        },
        "by_branch": {
            m: branch_summaries(
                ranks[(ranks["method"] == m) & (ranks["index"] == MAIN_INDEX)], branch_labels
            )
            for m in methods
        },
        "paired_top1_mcnemar": paired_top1(ranks),
    }
    cfg["timings_seconds"] = timings
    OUT.mkdir(parents=True, exist_ok=True)
    ranks.to_csv(OUT / "ranks.csv.gz", index=False, float_format="%.4f")
    errors_table(ranks, ont).to_csv(OUT / "errors.csv", index=False, float_format="%.4f")
    write_json(OUT / "metrics.json", metrics)
    write_json(OUT / "config.json", cfg)
    print(f"Wrote {OUT}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", action="store_true", help="200 queries + time estimate")
    parser.add_argument("--allow-dirty", action="store_true", help="full run on uncommitted code")
    parser.add_argument(
        "--skip", nargs="*", default=[], choices=list(EMBEDDINGS), help="embedding methods to skip"
    )
    parser.add_argument("--device", default="cuda", choices=["cuda", "cpu"])
    args = parser.parse_args()
    torch.set_num_threads(THREADS)
    device = embed.resolve_device(args.device)
    if not args.pilot and not args.allow_dirty and base_config("x", SEED)["git"]["dirty"]:
        sys.exit("Refusing full run: git tree is dirty. Commit first (or --allow-dirty).")
    ont = load_ontology(RAW_DIR / "hp.json")
    queries = build_queries(ont)
    indexes = build_indexes(ont)
    if args.pilot:
        pilot(ont, queries, indexes, device)
    else:
        full_run(ont, queries, indexes, args.skip, device)


if __name__ == "__main__":
    main()
