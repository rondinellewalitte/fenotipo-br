"""String index over HPO terms and ranking of HPO ids from string-level scores.

Ranking is over unique HPO ids: a term's score is the max over its strings. Ties are
resolved pessimistically for scoring (gold rank = number of ids scoring >= gold), so a
tie never counts as a hit. Id order is used only to display the top-k.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np
from rapidfuzz import fuzz, process, utils


def text_key(text: str) -> str:
    """Dedup key for index strings: trimmed, whitespace collapsed, casefolded."""
    return re.sub(r"\s+", " ", text.strip()).casefold()


def fold(text: str) -> str:
    """Lexical form: casefolded, accents stripped, non-alphanumerics -> single space."""
    nfkd = unicodedata.normalize("NFKD", text.casefold())
    stripped = utils.default_process("".join(c for c in nfkd if not unicodedata.combining(c)))
    return re.sub(r"\s+", " ", stripped)


@dataclass
class TermIndex:
    texts: list[str]  # one row per unique string (by text_key)
    text_ids: list[tuple[str, ...]]  # HPO ids each string belongs to
    ids: list[str]  # unique HPO ids, sorted
    id_pos: dict[str, int]
    pair_text: np.ndarray  # string row of each (string, id) pair, pairs sorted by id
    id_starts: np.ndarray  # first pair of each id, for np.maximum.reduceat

    @classmethod
    def build(cls, entries: Iterable[tuple[str, str]]) -> TermIndex:
        texts: list[str] = []
        text_ids: list[list[str]] = []
        row_of: dict[str, int] = {}
        for text, tid in entries:
            key = text_key(text)
            if not key:
                continue
            row = row_of.get(key)
            if row is None:
                row = row_of[key] = len(texts)
                texts.append(text.strip())
                text_ids.append([])
            if tid not in text_ids[row]:
                text_ids[row].append(tid)
        ids = sorted({t for row in text_ids for t in row})
        id_pos = {t: i for i, t in enumerate(ids)}
        pairs = sorted((id_pos[t], r) for r, row in enumerate(text_ids) for t in row)
        pair_id = np.array([p[0] for p in pairs], dtype=np.int64)
        pair_text = np.array([p[1] for p in pairs], dtype=np.int64)
        id_starts = np.flatnonzero(np.r_[True, pair_id[1:] != pair_id[:-1]])
        return cls(texts, [tuple(r) for r in text_ids], ids, id_pos, pair_text, id_starts)

    def n_ambiguous_texts(self) -> int:
        return sum(1 for ids in self.text_ids if len(ids) > 1)

    def id_scores(self, text_scores: np.ndarray) -> np.ndarray:
        """(n_queries, n_texts) string scores -> (n_queries, n_ids) max score per id."""
        return np.maximum.reduceat(text_scores[:, self.pair_text], self.id_starts, axis=1)


def rank_gold(id_scores: np.ndarray, gold_pos: np.ndarray, k: int = 10) -> dict[str, np.ndarray]:
    """Rank of the gold id per query, optimistic and pessimistic, plus the display top-k.

    rank_opt  = 1 + #ids scoring strictly above gold
    rank_pess = #ids scoring >= gold (gold included): ties count against the hit
    """
    rows = np.arange(len(gold_pos))
    gold = id_scores[rows, gold_pos]
    rank_opt = (id_scores > gold[:, None]).sum(axis=1) + 1
    rank_pess = (id_scores >= gold[:, None]).sum(axis=1)
    order = np.argsort(-id_scores, axis=1, kind="stable")[:, :k]
    top = id_scores[rows, order[:, 0]]
    return {
        "rank_opt": rank_opt,
        "rank_pess": rank_pess,
        "gold_score": gold,
        "top_score": top,
        "n_top": (id_scores == top[:, None]).sum(axis=1),
        "top_idx": order,
        "top_scores": np.take_along_axis(id_scores, order, axis=1),
    }


def ids_at_top(id_scores_row: np.ndarray) -> np.ndarray:
    """Positions of every id sharing the maximum score."""
    return np.flatnonzero(id_scores_row == id_scores_row.max())


def lexical_scores(
    queries: list[str], choices: list[str], scorer=fuzz.token_sort_ratio
) -> np.ndarray:
    """(n_queries, n_choices) rapidfuzz scores in [0, 100]; inputs must be pre-folded."""
    return process.cdist(queries, choices, scorer=scorer, dtype=np.float32, workers=-1)
