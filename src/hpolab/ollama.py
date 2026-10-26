"""Minimal Ollama HTTP client (stdlib only) for local, reproducible LLM calls.

Every call is non-streaming, uses explicit options (temperature, seed, num_ctx, num_predict)
and returns Ollama's timing fields, so experiments can log seconds per call. The server
address comes from OLLAMA_HOST (default 127.0.0.1:11434); model files live wherever the
server's OLLAMA_MODELS points, which is not this code's concern.
"""

from __future__ import annotations

import json
import os
import urllib.request

DEFAULT_HOST = "127.0.0.1:11434"
TIMEOUT_S = 600


def base_url(host: str | None = None) -> str:
    host = (host or os.environ.get("OLLAMA_HOST") or DEFAULT_HOST).strip().rstrip("/")
    if host.startswith("0.0.0.0"):  # server bind address, not a client target
        host = "127.0.0.1" + host[len("0.0.0.0") :]
    if not host.startswith(("http://", "https://")):
        host = "http://" + host
    if host.count(":") == 1:  # no port given
        host += ":11434"
    return host


def _request(path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url() + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.load(resp)


def version() -> str:
    return _request("/api/version")["version"]


def tags() -> list[dict]:
    """Locally available models: name, digest (full sha256), size, details."""
    return _request("/api/tags")["models"]


def digest(model: str) -> str | None:
    return next((m["digest"] for m in tags() if m["name"] == model), None)


def show(model: str) -> dict:
    """Model card: details (family, parameter_size, quantization_level), template, etc."""
    return _request("/api/show", {"model": model})


def ps() -> list[dict]:
    """Loaded models with size and size_vram (bytes on the GPU)."""
    return _request("/api/ps")["models"]


def chat_payload(
    model: str,
    system: str,
    user: str,
    options: dict,
    fmt: dict | None = None,
    keep_alive: str | int = "30m",
) -> dict:
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        "stream": False,
        "options": dict(options),
        "keep_alive": keep_alive,
    }
    if fmt is not None:
        payload["format"] = fmt
    return payload


def chat(model: str, system: str, user: str, options: dict, fmt: dict | None = None) -> dict:
    """One chat turn. Returns content, done_reason and the timing/token fields (ns, counts)."""
    r = _request("/api/chat", chat_payload(model, system, user, options, fmt))
    return {
        "content": r["message"]["content"],
        "done_reason": r.get("done_reason"),
        **{
            k: r.get(k)
            for k in (
                "total_duration",
                "load_duration",
                "prompt_eval_count",
                "prompt_eval_duration",
                "eval_count",
                "eval_duration",
            )
        },
    }


def unload(model: str) -> None:
    """Free the model's VRAM now instead of waiting for keep_alive to expire."""
    _request("/api/generate", {"model": model, "keep_alive": 0})
