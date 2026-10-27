"""References of the manuscript, each one checked against Crossref (and PubMed, when indexed).

Only DOIs registered with Crossref enter: --fetch queries the Crossref API for every DOI below,
stops if the registered title does not contain the expected fragment, looks the DOI up in
PubMed for its PMID, and writes the cache that build_manuscript.py reads (it never goes to
the network):

    paper/refs.json   Crossref metadata used to format the reference list, plus the PMID
    paper/refs.bib    BibTeX as Crossref transforms it, with the citation keys below

    uv run python paper/refs.py --fetch
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REFS_JSON, REFS_BIB = HERE / "refs.json", HERE / "refs.bib"
USER_AGENT = "fenotipo-br-refcheck (https://github.com/rondinellewalitte/fenotipo-br)"
# (citation key, DOI, fragment that the Crossref title must contain, case-insensitive)
REFS = [
    ("gargano2024", "10.1093/nar/gkad1005", "Human Phenotype Ontology in 2024"),
    ("kohler2021", "10.1093/nar/gkaa1043", "Human Phenotype Ontology in 2021"),
    ("vasilevsky2018", "10.1038/s41588-018-0096-x", "Plain-language medical vocabulary"),
    ("robinson2012", "10.1002/humu.22080", "Deep phenotyping for precision medicine"),
    ("jacobsen2022", "10.1038/s41587-022-01357-4", "phenopacket schema"),
    ("danis2025", "10.1016/j.xhgg.2024.100371", "corpus of GA4GH phenopackets"),
    ("nguengangwakap2020", "10.1038/s41431-019-0508-0", "prevalence of rare diseases"),
    ("felix2022", "10.1186/s13023-022-02254-4", "Brazilian Rare Diseases Network"),
    ("smedley2015", "10.1038/nprot.2015.124", "Exomiser"),
    ("robinson2020", "10.1016/j.ajhg.2020.06.021", "likelihood ratio"),
    ("deisseroth2019", "10.1038/s41436-018-0381-1", "ClinPhen"),
    ("luo2021", "10.1093/bioinformatics/btab019", "PhenoTagger"),
    ("groza2024", "10.1186/s12911-024-02439-w", "GPT models for phenotype concept recognition"),
    ("garcia2025", "10.1186/s13073-025-01521-w", "retrieval-augmented generation"),
    ("reese2026", "10.1038/s41431-026-02054-5", "Systematic benchmarking"),
    ("neveol2018", "10.1186/s13326-018-0179-8", "languages other than English"),
    ("oliveira2022", "10.1186/s13326-022-00269-1", "SemClinBr"),
    ("schneider2020", "10.18653/v1/2020.clinicalnlp-1.7", "BioBERTpt"),
    ("chen2024", "10.18653/v1/2024.findings-acl.137", "M3-Embedding"),
    ("reimers2020", "10.18653/v1/2020.emnlp-main.365", "Multilingual using Knowledge Distillation"),
    ("sainz2023", "10.18653/v1/2023.findings-emnlp.722", "Data Contamination"),
    ("cohen1960", "10.1177/001316446002000104", "coefficient of agreement"),
    ("mcnemar1947", "10.1007/bf02295996", "Correlated Proportions"),
    ("efron1993", "10.1007/978-1-4899-4541-9", "Introduction to the Bootstrap"),
]


def get(url: str, accept: str = "application/json") -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def year_of(msg: dict) -> int:
    for field in ("published-print", "issued", "published-online"):
        parts = msg.get(field, {}).get("date-parts", [[None]])[0]
        if parts and parts[0]:
            return int(parts[0])
    raise ValueError(f"no year for {msg.get('DOI')}")


def pmid_of(doi: str) -> str | None:
    term = urllib.parse.quote(f"{doi}[doi]")
    url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&retmode=json&term={term}"
    ids = json.loads(get(url))["esearchresult"]["idlist"]
    return ids[0] if len(ids) == 1 else None


def fetch() -> None:
    out, bib = {}, []
    for key, doi, fragment in REFS:
        msg = json.loads(get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}"))[
            "message"
        ]
        title = " ".join((msg.get("title") or [""])[0].split())
        if fragment.lower() not in title.lower():
            raise SystemExit(f"{key}: Crossref title {title!r} lacks {fragment!r}")
        text = get(
            f"https://api.crossref.org/works/{urllib.parse.quote(doi)}/transform/application/x-bibtex"
        ).decode("utf-8")
        text = re.sub(r"^@(\w+)\{[^,]*,", rf"@\1{{{key},", text.strip(), count=1)
        bib.append(text)
        time.sleep(0.4)  # NCBI asks for at most 3 requests per second without a key
        out[key] = {
            "doi": msg["DOI"].lower(),
            "type": msg.get("type"),
            "title": title,
            "authors": [
                {"family": a.get("family") or a.get("name"), "given": a.get("given", "")}
                for a in msg.get("author", [])
            ],
            "editors": [
                {"family": a.get("family") or a.get("name"), "given": a.get("given", "")}
                for a in msg.get("editor", [])
            ],
            "container": " ".join((msg.get("container-title") or [""])[0].split()),
            "short_container": (msg.get("short-container-title") or [""])[0],
            "publisher": msg.get("publisher"),
            "year": year_of(msg),
            "volume": msg.get("volume"),
            "issue": msg.get("issue"),
            "page": msg.get("page") or msg.get("article-number"),
            "pmid": pmid_of(doi),
            "checked": {"crossref_title_contains": fragment, "source": "api.crossref.org"},
        }
        print(f"{key}: {out[key]['year']} {title[:70]} (PMID {out[key]['pmid']})")
        time.sleep(0.4)
    meta = {"fetched_at": datetime.now(UTC).isoformat(timespec="seconds"), "refs": out}
    REFS_JSON.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REFS_BIB.write_text("\n\n".join(bib) + "\n", encoding="utf-8")
    print(f"-> {REFS_JSON}, {REFS_BIB} ({len(out)} references)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", help="query Crossref and PubMed")
    args = parser.parse_args()
    if args.fetch:
        fetch()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
