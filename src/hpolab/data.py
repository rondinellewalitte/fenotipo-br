"""Download raw data into data/raw/ and record provenance in data/raw/MANIFEST.json.

Run: uv run python -m hpolab.data [--force]

Release tags are resolved through the GitHub API at run time, and asset names are
checked against the release's asset list before downloading.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import urllib.request
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
MANIFEST = RAW_DIR / "MANIFEST.json"

HPO_REPO = "obophenotype/human-phenotype-ontology"
HPO_ASSETS = ("hp.json", "phenotype.hpoa")
HPO_PT_PATH = "src/translations/hp-pt.babelon.tsv"

PPKT_REPO = "monarch-initiative/phenopacket-store"
PPKT_ASSET = "all_phenopackets.zip"

USER_AGENT = "hpolab/0.1 (research; github.com/rondinellewalitte)"


def _request(url: str) -> urllib.request.Request:
    headers = {"User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith("https://api.github.com/"):
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def latest_release(repo: str) -> dict:
    """Return the GitHub API payload for the latest release of `repo`."""
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    with urllib.request.urlopen(_request(url), timeout=60) as resp:
        return json.load(resp)


def asset_url(release: dict, name: str) -> str:
    """Return the download URL of asset `name`; fail loudly if the release lacks it."""
    assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
    if name not in assets:
        raise LookupError(
            f"Asset {name!r} not in release {release.get('tag_name')}; available: {sorted(assets)}"
        )
    return assets[name]


def download(url: str, dest: Path) -> tuple[str, int]:
    """Stream `url` to `dest`; return (sha256, size in bytes)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    sha = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(_request(url), timeout=300) as resp, tmp.open("wb") as fh:
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
            sha.update(chunk)
            size += len(chunk)
    tmp.replace(dest)
    return sha.hexdigest(), size


def sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(1 << 20):
            sha.update(chunk)
    return sha.hexdigest()


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fetch(
    name: str, url: str, repo: str, release: dict, manifest: dict, force: bool = False
) -> dict:
    """Download one file unless it is already present with a matching manifest entry."""
    dest = RAW_DIR / name
    tag = release["tag_name"]
    entry = manifest.get(name)
    if (
        not force
        and dest.exists()
        and entry
        and entry.get("release_tag") == tag
        and entry.get("sha256") == sha256_file(dest)
    ):
        print(f"[skip] {name} ({tag}) already present")
        return entry
    print(f"[get ] {name} <- {url}")
    sha, size = download(url, dest)
    entry = {
        "url": url,
        "source_repo": repo,
        "release_tag": tag,
        "release_published_at": release.get("published_at"),
        "downloaded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sha256": sha,
        "size_bytes": size,
    }
    manifest[name] = entry
    save_manifest(manifest)
    return entry


def download_hpo(manifest: dict, force: bool = False) -> None:
    """hp.json and phenotype.hpoa from the latest HPO release, and the PT
    translation table from the same git tag so all three match."""
    release = latest_release(HPO_REPO)
    for name in HPO_ASSETS:
        fetch(name, asset_url(release, name), HPO_REPO, release, manifest, force)
    tag = release["tag_name"]
    pt_url = f"https://raw.githubusercontent.com/{HPO_REPO}/{tag}/{HPO_PT_PATH}"
    fetch(Path(HPO_PT_PATH).name, pt_url, HPO_REPO, release, manifest, force)


def download_phenopacket_store(manifest: dict, force: bool = False) -> None:
    release = latest_release(PPKT_REPO)
    fetch(PPKT_ASSET, asset_url(release, PPKT_ASSET), PPKT_REPO, release, manifest, force)


def iter_phenopackets(zip_path: Path = RAW_DIR / PPKT_ASSET) -> Iterator[tuple[str, dict]]:
    """Yield (zip member name, phenopacket dict) for every .json in the store zip.
    Read in place; nothing is extracted to disk."""
    with zipfile.ZipFile(zip_path) as zf:
        for name in sorted(zf.namelist()):
            if name.endswith(".json"):
                yield name, json.loads(zf.read(name))


def manifest_versions() -> dict[str, str]:
    """{file name: release tag} from MANIFEST.json, for experiment configs."""
    return {name: e["release_tag"] for name, e in load_manifest().items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download even if present")
    args = parser.parse_args()
    manifest = load_manifest()
    download_hpo(manifest, args.force)
    download_phenopacket_store(manifest, args.force)
    print(f"Manifest: {MANIFEST}")


if __name__ == "__main__":
    main()
