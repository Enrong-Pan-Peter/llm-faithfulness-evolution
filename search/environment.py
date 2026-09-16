"""What an environment must provide to the shared loop.

An environment wraps one task (one Blocksworld instance, one code-repair
task). The loop never looks inside candidates: it asks the environment to
render prompts, parse a model response into a candidate, grade it, and
describe the grade in the common outcome record. The environment also owns
the two texts that can fill the single rationale slot of a mutation prompt
besides the inherited rationale: the prospective text (a strategy for plans,
a diagnosis for programs, written by a separate call before the candidate
call) and the corrective hint (one sentence of exact feedback, the control).
"""

from __future__ import annotations

from typing import Any, Protocol, Sequence

from .individual import Individual

RATIONALE_CHANNELS = ("none", "inherited", "prospective", "corrective_hint")


class SearchEnvironment(Protocol):
    """Interface implemented by ``environments/<name>/search_adapter.py``."""

    name: str
    method: str
    task_id: str
    buckets: tuple[str, ...]
    operators: tuple[str, ...]

    def task_record(self) -> dict[str, Any]:
        """Public description of the task for RUN_CONFIG (no hidden information)."""

    def prompt_fingerprint(self, trace_format_version: int) -> str:
        """Short hash of every prompt template this environment renders."""

    def initial_prompt(self, *, self_report: bool) -> str:
        """Prompt that asks for a fresh candidate (generation 0)."""

    def operator_prompt(self, operator: str, parent: Individual, rationale_block: str, *, self_report: bool) -> str:
        """Prompt of one mutation operator applied to ``parent`` with ``rationale_block`` in the slot."""

    def prospective_prompt(self, parent: Individual) -> str:
        """First call of the prospective channel (strategy / diagnosis; no candidate)."""

    def prospective_text(self, response: Any) -> str:
        """The strategy / diagnosis text out of the first call's parsed response."""

    def prospective_block(self, text: str) -> str:
        """Render a prospective text for the slot (leading newline included)."""

    def corrective_hint_block(self, parent: Individual) -> str:
        """The corrective hint for ``parent`` rendered for the slot (may be empty)."""

    def parse_candidate(self, response: Any) -> tuple[Any, str] | None:
        """``(candidate, canonical_text)`` from a parsed response, or ``None``."""

    def evaluate(self, candidate: Any) -> Any:
        """Grade a candidate exactly."""

    def outcome(self, evaluation: Any) -> dict[str, Any]:
        """Common record: ``valid``, ``success``, ``score`` (fitness, lower is better), ``progress``, ``bucket``, ``details``."""

    def distance(self, text_a: str, text_b: str) -> float:
        """Distance between two candidate texts in ``[0, 1]`` (for the intervention analysis)."""

    def check_prompt(self, prompt: str) -> None:
        """Raise if a rendered prompt leaks hidden information."""


def candidate_summary(individuals: Sequence[Individual]) -> dict[str, Any]:
    """Counts used by SOLVED / FAILED events."""
    return {
        "n_candidates": len(individuals),
        "n_valid": sum(1 for individual in individuals if individual.outcome.get("valid")),
        "n_success": sum(1 for individual in individuals if individual.success),
        "n_duplicates": sum(1 for individual in individuals if individual.duplicate_of),
        "n_parse_failures": sum(1 for individual in individuals if not individual.parse_ok),
    }
