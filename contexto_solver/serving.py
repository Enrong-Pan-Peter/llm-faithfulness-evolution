"""Best-effort description of the model server, written into every run record.

The submitted study did not record the Ollama version or the exact model
version in its traces (they had to be recovered from job logs afterwards). This
module asks the server once per run and records what it answers; every field is
``None`` when the server cannot be reached or a provider other than Ollama is
used, so a run never fails because of it.
"""

from __future__ import annotations

from typing import Any

import requests

#: Decoding settings hard-wired in :mod:`contexto_solver.llm_client`.
DECODING_SETTINGS: dict[str, Any] = {
    "temperature": 0.8,
    "response_format": "json_object",
    "top_p": "provider default",
    "top_k": "provider default",
    "model_seed": None,
}


def _ollama_root(base_url: str) -> str:
    root = base_url.rstrip("/")
    if root.endswith("/v1"):
        root = root[: -len("/v1")]
    return root


def ollama_serving_info(base_url: str, model: str, timeout_s: float = 5.0) -> dict[str, Any]:
    """Return the Ollama server version and the pulled model's version id.

    ``model_version_id`` is the 12-character id that ``ollama list`` shows,
    which changes whenever the model weights or template change.
    """
    root = _ollama_root(base_url)
    info: dict[str, Any] = {
        "provider": "ollama",
        "server_url": root,
        "server_version": None,
        "model": model,
        "model_version_id": None,
        "model_size_bytes": None,
        "model_parameter_size": None,
        "model_quantization": None,
    }
    try:
        version = requests.get(f"{root}/api/version", timeout=timeout_s).json()
        info["server_version"] = version.get("version")
    except Exception:  # noqa: BLE001 - informational only
        pass
    try:
        tags = requests.get(f"{root}/api/tags", timeout=timeout_s).json()
        wanted = model if ":" in model else f"{model}:latest"
        for entry in tags.get("models", []):
            if entry.get("name") in {model, wanted}:
                digest = entry.get("digest") or ""
                info["model_version_id"] = digest[:12] or None
                info["model_size_bytes"] = entry.get("size")
                details = entry.get("details") or {}
                info["model_parameter_size"] = details.get("parameter_size")
                info["model_quantization"] = details.get("quantization_level")
                break
    except Exception:  # noqa: BLE001 - informational only
        pass
    return info


def serving_info(provider: str, model: str, ollama_base_url: str) -> dict[str, Any]:
    """Serving description for any provider; only Ollama is queried."""
    if provider == "ollama":
        info = ollama_serving_info(ollama_base_url, model)
    else:
        info = {
            "provider": provider,
            "server_url": None,
            "server_version": None,
            "model": model,
            "model_version_id": None,
            "model_size_bytes": None,
            "model_parameter_size": None,
            "model_quantization": None,
        }
    info["decoding"] = dict(DECODING_SETTINGS)
    return info
