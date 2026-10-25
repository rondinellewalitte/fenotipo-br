"""HPO ontology (obographs hp.json) and the official PT translation table (babelon TSV).

Run: uv run python -m hpolab.hpo   (prints a summary of the files in data/raw/)
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import pandas as pd

ROOT_TERM = "HP:0000001"
PHENOTYPIC_ABNORMALITY = "HP:0000118"

_ALT_ID = "http://www.geneontology.org/formats/oboInOwl#hasAlternativeId"
_REPLACED_BY = "http://purl.obolibrary.org/obo/IAO_0100001"
_SCOPES = {
    "hasExactSynonym": "exact",
    "hasRelatedSynonym": "related",
    "hasBroadSynonym": "broad",
    "hasNarrowSynonym": "narrow",
}


@dataclass(frozen=True)
class Synonym:
    text: str
    scope: str  # exact | related | broad | narrow
    type: str | None = None  # e.g. layperson, plural_form, abbreviation


@dataclass(frozen=True)
class Term:
    id: str
    label: str
    synonyms: tuple[Synonym, ...] = ()


@dataclass
class Ontology:
    version: str
    terms: dict[str, Term]  # active (non-obsolete) HP classes only
    parents: dict[str, frozenset[str]]
    children: dict[str, frozenset[str]]
    obsolete: dict[str, str | None]  # obsolete id -> replaced_by (or None)
    alt_ids: dict[str, str]  # alternative id -> primary id
    _anc: dict[str, frozenset[str]] = field(default_factory=dict, repr=False)

    def resolve(self, hpo_id: str) -> str | None:
        """Map an alt/obsolete id to its current primary id; None if unresolvable."""
        seen: set[str] = set()
        cur: str | None = hpo_id
        while cur is not None and cur not in self.terms and cur not in seen:
            seen.add(cur)
            cur = self.alt_ids.get(cur) or self.obsolete.get(cur)
        return cur if cur in self.terms else None

    def ancestors(self, hpo_id: str) -> frozenset[str]:
        """All is_a ancestors, excluding the term itself."""
        if hpo_id not in self._anc:
            out: set[str] = set()
            for p in self.parents.get(hpo_id, ()):
                out.add(p)
                out |= self.ancestors(p)
            self._anc[hpo_id] = frozenset(out)
        return self._anc[hpo_id]

    def top_branches(self, hpo_id: str, root: str = PHENOTYPIC_ABNORMALITY) -> frozenset[str]:
        """Children of `root` that are the term itself or one of its ancestors.
        A term can sit in several branches (polyhierarchy)."""
        lineage = self.ancestors(hpo_id) | {hpo_id}
        return frozenset(c for c in self.children.get(root, ()) if c in lineage)

    def is_neighbor(self, a: str, b: str) -> bool:
        """True if `a` is a direct is_a parent or child of `b`."""
        return a in self.parents.get(b, ()) or a in self.children.get(b, ())

    def is_sibling(self, a: str, b: str) -> bool:
        """True if `a` != `b` and they share at least one direct is_a parent."""
        return a != b and bool(self.parents.get(a, frozenset()) & self.parents.get(b, frozenset()))

    def up_steps(self, hpo_id: str) -> dict[str, int]:
        """Minimum number of is_a steps from the term up to each ancestor (self = 0)."""
        steps, frontier, d = {hpo_id: 0}, [hpo_id], 0
        while frontier:
            d += 1
            nxt = []
            for node in frontier:
                for p in self.parents.get(node, ()):
                    if p not in steps:
                        steps[p] = d
                        nxt.append(p)
            frontier = nxt
        return steps

    def relation(self, a: str, b: str, max_up: int = 2) -> str:
        """First matching category: same, parent_child, sibling, ancestor_descendant,
        close_relative (a common ancestor within `max_up` steps of both), distant."""
        if a == b:
            return "same"
        if self.is_neighbor(a, b):
            return "parent_child"
        if self.is_sibling(a, b):
            return "sibling"
        if a in self.ancestors(b) or b in self.ancestors(a):
            return "ancestor_descendant"
        up_a, up_b = self.up_steps(a), self.up_steps(b)
        if any(up_a[c] <= max_up and up_b[c] <= max_up for c in up_a.keys() & up_b.keys()):
            return "close_relative"
        return "distant"


def iri_to_curie(iri: str) -> str:
    """http://purl.obolibrary.org/obo/HP_0000118 -> HP:0000118"""
    local = iri.rsplit("/", 1)[-1]
    prefix, _, num = local.partition("_")
    return f"{prefix}:{num}"


def _release_date(graph: dict) -> str:
    version = graph.get("meta", {}).get("version", "")
    m = re.search(r"(\d{4}-\d{2}-\d{2})", version)
    return m.group(1) if m else version


def _synonyms(meta: dict) -> tuple[Synonym, ...]:
    out = []
    for s in meta.get("synonyms", []):
        stype = s.get("synonymType")
        out.append(
            Synonym(
                text=s["val"],
                scope=_SCOPES.get(s["pred"], s["pred"]),
                type=stype.rsplit("#", 1)[-1] if stype else None,
            )
        )
    return tuple(out)


def parse_obographs(data: dict) -> Ontology:
    graph = data["graphs"][0]
    terms: dict[str, Term] = {}
    obsolete: dict[str, str | None] = {}
    alt_ids: dict[str, str] = {}
    for node in graph["nodes"]:
        if node.get("type") != "CLASS" or "/HP_" not in node["id"]:
            continue
        cid = iri_to_curie(node["id"])
        meta = node.get("meta", {})
        props = meta.get("basicPropertyValues", [])
        if meta.get("deprecated"):
            repl = [p["val"] for p in props if p["pred"] == _REPLACED_BY]
            obsolete[cid] = repl[0] if repl else None
            continue
        terms[cid] = Term(id=cid, label=node.get("lbl", ""), synonyms=_synonyms(meta))
        for p in props:
            if p["pred"] == _ALT_ID:
                alt_ids[p["val"]] = cid
    parents: dict[str, set[str]] = defaultdict(set)
    children: dict[str, set[str]] = defaultdict(set)
    for e in graph["edges"]:
        if e["pred"] != "is_a":
            continue
        sub, obj = iri_to_curie(e["sub"]), iri_to_curie(e["obj"])
        if sub in terms and obj in terms:
            parents[sub].add(obj)
            children[obj].add(sub)
    return Ontology(
        version=_release_date(graph),
        terms=terms,
        parents={k: frozenset(v) for k, v in parents.items()},
        children={k: frozenset(v) for k, v in children.items()},
        obsolete=obsolete,
        alt_ids=alt_ids,
    )


@cache
def load_ontology(path: Path) -> Ontology:
    with Path(path).open(encoding="utf-8") as fh:
        return parse_obographs(json.load(fh))


def index_entries(ont: Ontology, scopes: tuple[str, ...] = ("exact",)) -> list[tuple[str, str]]:
    """(English text, HPO id) for every active term: its label plus synonyms of `scopes`."""
    out = []
    for tid in sorted(ont.terms):
        term = ont.terms[tid]
        out.append((term.label, tid))
        out.extend((s.text, tid) for s in term.synonyms if s.scope in scopes)
    return out


def load_babelon(path: Path) -> pd.DataFrame:
    """Raw babelon rows, all columns as strings."""
    return pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False, encoding="utf-8")


def pt_labels(babelon: pd.DataFrame, ont: Ontology) -> pd.DataFrame:
    """Official PT labels for active terms.

    Filter: predicate_id == rdfs:label, translation_status == OFFICIAL, non-empty value,
    subject is an active HP term. Column `stale` marks rows whose `source_value` (the
    English label that was translated) differs from the current English label.
    """
    df = babelon[
        (babelon["predicate_id"] == "rdfs:label")
        & (babelon["translation_status"] == "OFFICIAL")
        & (babelon["translation_value"].str.strip() != "")
        & (babelon["subject_id"].isin(ont.terms.keys()))
    ]
    out = pd.DataFrame(
        {
            "hpo_id": df["subject_id"],
            "pt_label": df["translation_value"].str.strip(),
            "source_label": df["source_value"].str.strip(),
        }
    )
    out["en_label"] = out["hpo_id"].map(lambda i: ont.terms[i].label)
    out["stale"] = out["source_label"] != out["en_label"].str.strip()
    return out.drop_duplicates("hpo_id").reset_index(drop=True)


def summary(ont: Ontology, babelon: pd.DataFrame) -> dict:
    labels = babelon[babelon["predicate_id"] == "rdfs:label"]
    pt = pt_labels(babelon, ont)
    in_pa = {t for t in ont.terms if PHENOTYPIC_ABNORMALITY in ont.ancestors(t)}
    return {
        "hpo_version": ont.version,
        "active_terms": len(ont.terms),
        "active_terms_under_HP:0000118": len(in_pa),
        "obsolete_terms": len(ont.obsolete),
        "babelon_rows": len(babelon),
        "babelon_label_rows": len(labels),
        "babelon_label_rows_on_obsolete_terms": int(labels["subject_id"].isin(ont.obsolete).sum()),
        "pt_labels_active": len(pt),
        "pt_labels_active_stale": int(pt["stale"].sum()),
        "pt_labels_under_HP:0000118": int(pt["hpo_id"].isin(in_pa).sum()),
        "pt_coverage_active": round(len(pt) / len(ont.terms), 4),
    }


def main() -> None:
    import argparse

    from hpolab.data import RAW_DIR

    parser = argparse.ArgumentParser(description="Summary of hp.json + PT babelon")
    parser.add_argument("--out", type=Path, help="also write the summary as JSON here")
    args = parser.parse_args()
    ont = load_ontology(RAW_DIR / "hp.json")
    bab = load_babelon(RAW_DIR / "hp-pt.babelon.tsv")
    text = json.dumps(summary(ont, bab), indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
