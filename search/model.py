"""Model calls for the shared loop.

``ModelClient`` wraps ``contexto_solver.llm_client.LLMClient`` so the planning
and code environments use exactly the Contexto serving path (same endpoint,
temperature 0.8, JSON-object response format, the same retry rule) and the
same serving record (``contexto_solver.serving.serving_info``). Every call
returns ``(parsed_json_or_None, raw_text, error_or_None)`` and never raises
for a bad completion, so one failed call costs one candidate, not the run.

``ScriptedModel`` answers from a user function for offline tests and the
smoke test (``--provider scripted``): no network, deterministic.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from contexto_solver import config as app_config
from contexto_solver.llm_client import LLMClient
from contexto_solver.serving import serving_info


class ModelClient:
    """Calls through the Contexto client; records call counts and failures."""

    def __init__(self, provider: str, model: str, api_key: str = "") -> None:
        self.provider = provider
        self.model = model
        self.client = LLMClient(provider, api_key or app_config.LLM_API_KEY, model)
        self.calls = 0
        self.failures = 0

    def serving_record(self) -> dict[str, Any]:
        return serving_info(self.provider, self.model, app_config.OLLAMA_BASE_URL)

    def complete_json(self, prompt: str) -> tuple[Any, str | None, str | None]:
        self.calls += 1
        try:
            parsed, raw = self.client.complete_json_prompt_with_raw(prompt)
        except Exception as exc:  # network errors, invalid JSON after retries
            self.failures += 1
            return None, None, f"{type(exc).__name__}: {exc}"
        return parsed, raw, None


class ScriptedModel:
    """A stand-in model: ``respond(prompt) -> str | dict`` decides every answer."""

    def __init__(self, respond: Callable[[str], Any], model: str = "scripted") -> None:
        self.provider = "scripted"
        self.model = model
        self.respond = respond
        self.calls = 0
        self.failures = 0
        self.prompts: list[str] = []

    def serving_record(self) -> dict[str, Any]:
        return {"provider": "scripted", "model": self.model, "note": "no model server; scripted responses"}

    def complete_json(self, prompt: str) -> tuple[Any, str | None, str | None]:
        self.calls += 1
        self.prompts.append(prompt)
        try:
            answer = self.respond(prompt)
        except Exception as exc:
            self.failures += 1
            return None, None, f"{type(exc).__name__}: {exc}"
        if isinstance(answer, str):
            try:
                return json.loads(answer), answer, None
            except ValueError:
                self.failures += 1
                return None, answer, "scripted response is not JSON"
        return answer, json.dumps(answer), None
