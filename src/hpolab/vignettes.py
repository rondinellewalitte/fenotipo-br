"""Exp 03 cases and PT-BR vignettes: eligibility, the per-gene draw, the negated terms shown in
each vignette, the generator's input items, and the automatic leak/coverage check.

Pure functions only (no API, no I/O beyond reading the phenopacket dict) so they can be
unit-tested; experiments/exp03_vignettes.py does the calls and the files.
"""

from __future__ import annotations

import hashlib
import re

import numpy as np
import pandas as pd

from hpolab.data import phenopacket_case
from hpolab.hpo import PHENOTYPIC_ABNORMALITY, Ontology

MIN_TERMS, MAX_TERMS = 3, 15
MAX_NEGATED = 5
GENERATOR_MODEL = "claude-opus-5-5"
GENERATOR_PROMPT = "exp03_vignette_pt_br_v1"  # stem under prompts/

_HPO_ID_RE = re.compile(r"\bHP\s*[:_]?\s*\d{7}\b|\bHPO\b", re.IGNORECASE)
_DISEASE_ID_RE = re.compile(r"\b(OMIM|MONDO|ORPHA|ORPHANET)\s*[:_]", re.IGNORECASE)
_ISO_DURATION_RE = re.compile(r"^P(?:(\d+)Y)?(?:(\d+)M)?(?:(\d+)W)?(?:(\d+)D)?$")
# Words that never occur in Portuguese prose; a few of them signal English text.
ENGLISH_FUNCTION_WORDS = frozenset(
    {"the", "of", "with", "and", "is", "was", "were", "has", "had", "his", "her", "patient"}
)


# ---------------------------------------------------------------- cases


def case_record(member: str, pp: dict, ont: Ontology) -> dict:
    """Observed and excluded terms of one phenopacket as current primary ids under
    HP:0000118, plus sex and age at last encounter. Ids that cannot be resolved are dropped."""
    base = phenopacket_case(member, pp)

    def in_pa(i: str | None) -> bool:
        return i is not None and PHENOTYPIC_ABNORMALITY in ont.ancestors(i)

    observed = {ont.resolve(i) for i in base["observed"]}
    excluded = {
        ont.resolve(f["type"]["id"])
        for f in pp.get("phenotypicFeatures", [])
        if f.get("excluded", False)
    }
    observed = sorted(i for i in observed if in_pa(i))
    subject = pp.get("subject", {})
    age = subject.get("timeAtLastEncounter", {}).get("age", {}).get("iso8601duration")
    return {
        "case_id": base["case_id"],
        "member": base["member"],
        "gene": base["gene"],
        "disease_id": base["disease_id"],
        "sex": subject.get("sex", "UNKNOWN_SEX"),
        "age_iso8601": age or "",
        "observed": observed,
        "excluded": sorted(i for i in excluded if in_pa(i) and i not in observed),
    }


def eligible(cases: pd.DataFrame) -> pd.DataFrame:
    n = cases["observed"].map(len)
    return cases[(n >= MIN_TERMS) & (n <= MAX_TERMS)]


def draw(cases: pd.DataFrame, seed: int, n_pilot: int, n_full: int) -> pd.DataFrame:
    """One case per gene. Genes (sorted, then permuted with `seed`) are assigned in order:
    the first n_pilot to the pilot, the next n_full to the full run, the rest to the
    reserve used for replacements. Within a gene the case is drawn from its eligible cases
    sorted by case_id. Pilot, full and reserve never share a gene or a case."""
    pools = {g: grp.sort_values("case_id") for g, grp in cases.groupby("gene", sort=True)}
    genes = sorted(pools)
    rng = np.random.default_rng(seed)
    rows = []
    for rank, gi in enumerate(rng.permutation(len(genes))):
        pool = pools[genes[gi]]
        pick = pool.iloc[int(rng.integers(len(pool)))].to_dict()
        if rank < n_pilot:
            pick["set"] = "pilot"
        elif rank < n_pilot + n_full:
            pick["set"] = "full"
        else:
            pick["set"] = "reserve"
        pick["draw_rank"] = rank
        pick["n_gene_eligible_cases"] = len(pool)
        rows.append(pick)
    return pd.DataFrame(rows)


def case_rng(seed: int, case_id: str) -> np.random.Generator:
    """Per-case generator: the draw does not depend on the order cases are processed."""
    h = hashlib.sha256(f"{seed}:{case_id}".encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "big"))


def negation_pool(observed: list[str], excluded: list[str], ont: Ontology) -> list[str]:
    """Excluded terms that may be stated as absent: not observed, and neither an ancestor nor
    a descendant of an observed term ('no seizures' next to 'focal seizures' would
    contradict the note)."""
    obs = set(observed)
    return [
        e
        for e in sorted(excluded)
        if e not in obs
        and not (ont.ancestors(e) & obs)
        and not any(e in ont.ancestors(o) for o in obs)
    ]


def pick_negated(
    observed: list[str], excluded: list[str], ont: Ontology, seed: int, case_id: str
) -> list[str]:
    """Up to MAX_NEGATED terms of the negation pool, drawn with a per-case generator."""
    pool = negation_pool(observed, excluded, ont)
    if len(pool) <= MAX_NEGATED:
        return pool
    idx = case_rng(seed, case_id).choice(len(pool), MAX_NEGATED, replace=False)
    return sorted(pool[i] for i in idx)


# ---------------------------------------------------------------- generator input


def age_text(iso: str) -> str:
    """'P5Y3M' -> '5 years 3 months'; '' when absent or not a plain ISO 8601 duration."""
    m = _ISO_DURATION_RE.match(iso or "")
    if not m or not any(m.groups()):
        return ""
    parts = []
    for value, unit in zip(m.groups(), ("year", "month", "week", "day"), strict=True):
        if value and int(value) > 0:
            parts.append(f"{int(value)} {unit}{'s' if int(value) != 1 else ''}")
    return " ".join(parts) if parts else "newborn (0 days)"


SEX_TEXT = {"MALE": "male", "FEMALE": "female"}


def items(observed: list[str], negated: list[str]) -> list[dict]:
    """Numbered items for the generator: present '1'..'n', absent 'N1'..'Nk'. The generator
    sees only item numbers, English labels and definitions; never HPO ids."""
    out = [{"item": str(k), "hpo_id": i, "polarity": "present"} for k, i in enumerate(observed, 1)]
    out += [{"item": f"N{k}", "hpo_id": i, "polarity": "absent"} for k, i in enumerate(negated, 1)]
    return out


def item_lines(item_list: list[dict], ont: Ontology, polarity: str) -> str:
    lines = []
    for it in item_list:
        if it["polarity"] != polarity:
            continue
        term = ont.terms[it["hpo_id"]]
        definition = f" (definition: {term.definition})" if term.definition else ""
        lines.append(f"[{it['item']}] {term.label}{definition}")
    return "\n".join(lines) if lines else "(none)"


# ---------------------------------------------------------------- checks


def _norm(text: str) -> str:
    """Casefolded, whitespace collapsed; accents kept (so 'hematúria' != 'hematuria')."""
    return re.sub(r"\s+", " ", text).strip().casefold()


def _contains_phrase(haystack: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", haystack) is not None


def label_leaks(text: str, labels: list[str], pt_vocab: str) -> list[str]:
    """English labels found verbatim in the text (case-insensitive, accents kept), except
    labels that also occur in an official PT label (`pt_vocab`: all PT labels, normalized,
    one per line), i.e. cognates attested as Portuguese such as 'Ataxia' or 'Glaucoma'."""
    t = _norm(text)
    out = []
    for label in labels:
        lab = _norm(label)
        if lab and _contains_phrase(t, lab) and not _contains_phrase(pt_vocab, lab):
            out.append(label)
    return out


def check_vignette(
    text: str,
    phrases: list[dict],
    item_list: list[dict],
    labels_en: list[str],
    pt_vocab: str,
    gene_symbols: list[str],
) -> dict:
    """Leak and coverage checks. `fail` lists the reasons the vignette is rejected;
    `warn` lists things reported but tolerated."""
    fail, warn = [], []
    if _HPO_ID_RE.search(text):
        fail.append("hpo_id_or_mention")
    if _DISEASE_ID_RE.search(text):
        fail.append("disease_id")
    leaks = label_leaks(text, labels_en, pt_vocab)
    if leaks:
        fail.append("english_label:" + "|".join(leaks))
    genes = [
        g for g in gene_symbols if g and re.search(rf"(?<![\w-]){re.escape(g)}(?![\w-])", text)
    ]
    if genes:
        fail.append("gene_symbol:" + "|".join(genes))
    t = _norm(text)
    by_item: dict[str, list[str]] = {}
    for p in phrases:
        by_item.setdefault(str(p.get("item", "")), []).append(_norm(str(p.get("phrase", ""))))
    expected = {it["item"] for it in item_list}
    missing = sorted(expected - by_item.keys())
    unknown = sorted(by_item.keys() - expected)
    dup = sorted(k for k, v in by_item.items() if len(v) > 1)
    not_in_text = sorted(
        k for k, v in by_item.items() if k in expected and (not v[0] or v[0] not in t)
    )
    if missing:
        fail.append("item_without_phrase:" + "|".join(missing))
    if not_in_text:
        fail.append("phrase_not_in_text:" + "|".join(not_in_text))
    if unknown:
        warn.append("unknown_item:" + "|".join(unknown))
    if dup:
        warn.append("several_phrases_for_item:" + "|".join(dup))
    n_en = sum(1 for w in re.findall(r"[a-z]+", t) if w in ENGLISH_FUNCTION_WORDS)
    if n_en:
        warn.append(f"english_function_words:{n_en}")
    n_words = len(text.split())
    if not 60 <= n_words <= 600:
        warn.append(f"length_words:{n_words}")
    return {"pass": not fail, "fail": fail, "warn": warn, "n_words": n_words}


def final_vignettes(records: list[dict], set_name: str, prompt_sha: str, model: str) -> dict:
    """{case_id: record} of the vignettes used for `set_name`: the latest passing record per
    case made with this generator prompt and model (replacement cases carry the set name of
    the case they replace)."""
    out: dict[str, dict] = {}
    for r in records:
        if (
            r.get("set") == set_name
            and r.get("prompt_sha256") == prompt_sha
            and r.get("model") == model
            and r.get("checks", {}).get("pass")
        ):
            out[r["case_id"]] = r
    return out
