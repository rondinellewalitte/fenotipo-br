"""Sentence-transformers encoding (CPU or CUDA) with an on-disk cache in data/processed/emb/.

Cache key: model id + revision + max_seq_length + sha256 of the exact (prefixed) texts.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np

from hpolab.data import PROCESSED_DIR

EMB_DIR = PROCESSED_DIR / "emb"


def load_model(name: str, max_seq_length: int = 128, device: str = "cpu"):
    """fp32 weights on `device` (no fp16: keeps numerics comparable to CPU runs)."""
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(name, device=device)
    model.max_seq_length = max_seq_length
    return model


def resolve_device(requested: str) -> str:
    """Fail instead of silently falling back to CPU when CUDA is requested."""
    import torch

    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA requested but torch.cuda.is_available() is False")
    return requested


def device_info(device: str) -> dict:
    import torch

    info = {"device": device, "dtype": "float32", "torch_cuda": torch.version.cuda}
    if device == "cuda":
        props = torch.cuda.get_device_properties(0)
        info.update(
            {
                "gpu": props.name,
                "gpu_memory_gib": round(props.total_memory / 2**30, 2),
                "compute_capability": f"{props.major}.{props.minor}",
                "cudnn": torch.backends.cudnn.version(),
            }
        )
    return info


def model_revision(name: str) -> str | None:
    """Commit hash of the locally cached snapshot of `name`."""
    from huggingface_hub import try_to_load_from_cache

    path = try_to_load_from_cache(name, "config.json")
    if not isinstance(path, str):
        return None
    m = re.search(r"snapshots[\\/]([0-9a-f]{40})", path)
    return m.group(1) if m else None


def count_truncated(model, texts: list[str]) -> int:
    """Number of texts longer than the model's max_seq_length in tokens."""
    enc = model.tokenizer(texts, add_special_tokens=True)["input_ids"]
    return sum(1 for ids in enc if len(ids) > model.max_seq_length)


def encode(model, texts: list[str], batch_size: int = 64) -> np.ndarray:
    """L2-normalized float32 embeddings (dot product = cosine)."""
    emb = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return emb.astype(np.float32, copy=False)


def cache_path(
    model_name: str, revision: str | None, max_seq: int, texts: list[str], tag: str
) -> Path:
    sha = hashlib.sha256()
    sha.update(f"{model_name}\n{revision}\n{max_seq}\n".encode())
    for t in texts:
        sha.update(t.encode("utf-8") + b"\x00")
    slug = model_name.replace("/", "__")
    return EMB_DIR / f"{slug}__{tag}__{sha.hexdigest()[:16]}.npy"


def encode_cached(model, model_name: str, texts: list[str], tag: str) -> tuple[np.ndarray, bool]:
    """Encode `texts` (already prefixed) or load them from cache. Returns (emb, from_cache)."""
    path = cache_path(model_name, model_revision(model_name), model.max_seq_length, texts, tag)
    if path.exists():
        emb = np.load(path)
        if emb.shape[0] == len(texts):
            return emb, True
    emb = encode(model, texts)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, emb)
    return emb, False
