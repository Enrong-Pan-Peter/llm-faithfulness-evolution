"""The per-candidate record of the shared loop."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Individual:
    """One candidate: what was proposed, how it was graded, and where it came from.

    ``fitness`` is the environment's score, lower is better (the analogue of
    Contexto's rank). ``outcome`` is the environment's common record
    (``valid``, ``success``, ``score``, ``progress``, ``bucket``, ``details``).
    ``duplicate_of`` names the earlier individual whose candidate text was
    identical (its grade was reused); ``entered_pool`` is false only for
    responses that carried no usable candidate.
    """

    individual_id: str
    generation: int
    origin: str  # "initial" or "mutation_<operator>"
    operator: str | None
    parent_id: str | None
    parent_fitness: float | None
    parent_progress: float | None
    candidate: Any
    candidate_text: str
    candidate_key: str
    fitness: float
    outcome: dict[str, Any]
    evaluation: Any
    self_report: dict[str, Any]
    rationale: dict[str, Any]
    prompt: str
    raw_response: str | None
    parse_ok: bool
    duplicate_of: str | None = None
    entered_pool: bool = True
    status: str = "active"
    prospective: dict[str, Any] | None = None  # first call of a prospective channel
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return bool(self.outcome.get("success"))

    @property
    def progress(self) -> float:
        value = self.outcome.get("progress")
        return float(value) if isinstance(value, (int, float)) else 0.0

    @property
    def bucket(self) -> str | None:
        return self.outcome.get("bucket")

    def event_details(self) -> dict[str, Any]:
        """The trace record of this individual (used by INITIAL_CANDIDATE / OPERATOR_SAMPLED)."""
        details: dict[str, Any] = {
            "child_id": self.individual_id,
            "parent_id": self.parent_id,
            "parent_fitness": self.parent_fitness,
            "parent_progress": self.parent_progress,
            "sampled_op": self.operator,
            "origin": self.origin,
            "candidate_text": self.candidate_text,
            "candidate_key": self.candidate_key,
            "parse_ok": self.parse_ok,
            "fitness": self.fitness if math.isfinite(self.fitness) else None,
            "outcome": self.outcome,
            "self_report": self.self_report,
            "rationale": self.rationale,
            "prompt": self.prompt,
            "raw_response": self.raw_response,
            "duplicate_of": self.duplicate_of,
            "entered_pool": self.entered_pool,
        }
        if self.prospective is not None:
            details["prospective"] = self.prospective
        details.update(self.extra)
        return details

    def summary(self) -> dict[str, Any]:
        """Short record for SELECT / SOLVED / FAILED events."""
        return {
            "id": self.individual_id,
            "generation": self.generation,
            "origin": self.origin,
            "fitness": self.fitness if math.isfinite(self.fitness) else None,
            "success": self.success,
            "progress": self.progress,
            "bucket": self.bucket,
        }
