"""Run metadata for results/expNN/config.json: code version, data versions, libraries."""

from __future__ import annotations

import platform
import subprocess
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version

from hpolab.data import ROOT, load_manifest

LIBS = ("numpy", "pandas", "rapidfuzz", "torch", "sentence-transformers", "transformers")


def git_info() -> dict:
    def run(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()

    try:
        return {"commit": run("rev-parse", "HEAD"), "dirty": bool(run("status", "--porcelain"))}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"commit": None, "dirty": None}


def lib_versions() -> dict:
    out = {}
    for lib in LIBS:
        try:
            out[lib] = version(lib)
        except PackageNotFoundError:
            out[lib] = None
    return out


def base_config(experiment: str, seed: int) -> dict:
    manifest = load_manifest()
    return {
        "experiment": experiment,
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seed": seed,
        "git": git_info(),
        "data": {
            name: {k: e.get(k) for k in ("release_tag", "url", "sha256")}
            for name, e in manifest.items()
        },
        "hpo_release": manifest.get("hp.json", {}).get("release_tag"),
        "phenopacket_store_release": manifest.get("all_phenopackets.zip", {}).get("release_tag"),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "cpu": platform.processor(),
        "libs": lib_versions(),
    }
