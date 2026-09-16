"""Blocksworld planning as an environment of the shared search loop (``ea_plan_operators``).

Candidates are plans (``{"plan": ["(unstack b c)", ...]}``); the checker grades
them exactly. Fitness is ``evaluation.fitness`` (remaining distance when the
exact search fits in its budget, else unsatisfied goal predicates, plus the
validity tie-break); success is ``goal_complete``. The prospective channel is
the strategy call (``STRATEGY_PROMPT``) whose text goes into the slot of the
operator prompt; the corrective hint names the first invalid action.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Sequence

from search.individual import Individual

from . import prompts as planning_prompts
from .blocksworld import Action, Instance, parse_plan
from .evaluation import OUTCOME_BUCKETS, PlanEvaluation, evaluate_plan, fitness, outcome_bucket, progress, success
from .operators import OPERATORS, PlanningOperator, build_operator_prompt
from .prompts import (
    SELF_REPORT_BLOCK,
    assert_no_hidden_information,
    build_initial_plan_prompt,
    build_strategy_prompt,
    corrective_hint_block,
    render_plan_lines,
)

ENVIRONMENT_NAME = "planning"
METHOD_NAME = "ea_plan_operators"
STRATEGY_MAX_CHARS = 600

_TEMPLATE_NAMES = (
    "SELF_REPORT_BLOCK",
    "ACTION_RULES",
    "OUTPUT_FORMAT",
    "INITIAL_PLAN_PROMPT",
    "S_MUTATION_PROMPT",
    "M_MUTATION_PROMPT",
    "ML_MUTATION_PROMPT",
    "L_MUTATION_PROMPT",
    "STRATEGY_PROMPT",
    "PLAN_FROM_STRATEGY_PROMPT",
)


def prompt_fingerprint(trace_format_version: int) -> str:
    """Short hash of the planning prompt templates (same construction as Contexto's)."""
    parts = [f"{name}={getattr(planning_prompts, name)}" for name in _TEMPLATE_NAMES]
    parts.append(f"TRACE_SCHEMA_VERSION={trace_format_version}")
    parts.append(f"PREDICTED_BUCKETS={','.join(OUTCOME_BUCKETS)}")
    return hashlib.sha256("\n---\n".join(parts).encode("utf-8")).hexdigest()[:16]


class PlanningSearchEnvironment:
    """One Blocksworld instance for the shared loop."""

    name = ENVIRONMENT_NAME
    method = METHOD_NAME
    buckets = tuple(OUTCOME_BUCKETS)
    operators = tuple(operator.value for operator in OPERATORS)

    def __init__(self, instance: Instance, *, expansion_cap: int | None = None, optimal_length: int | None = None) -> None:
        self.instance = instance
        self.task_id = instance.instance_id
        self.expansion_cap = expansion_cap
        self.optimal_length = optimal_length

    # ------------------------------------------------------------ records

    def task_record(self) -> dict[str, Any]:
        record = self.instance.to_dict()
        record["environment"] = self.name
        record["blocks"] = list(self.instance.blocks)
        record["goal_predicates"] = len(self.instance.goal)
        record["optimal_plan_length"] = self.optimal_length  # solver-side fact; never enters a prompt
        return record

    def prompt_fingerprint(self, trace_format_version: int) -> str:
        return prompt_fingerprint(trace_format_version)

    # ------------------------------------------------------------ prompts

    def initial_prompt(self, *, self_report: bool) -> str:
        return build_initial_plan_prompt(self.instance, self_report=self_report)

    def operator_prompt(self, operator: str, parent: Individual, rationale_block: str, *, self_report: bool) -> str:
        return build_operator_prompt(
            PlanningOperator(operator), self.instance, _actions(parent.candidate), parent.evaluation,
            rationale_block=rationale_block, self_report=self_report,
        )

    def prospective_prompt(self, parent: Individual) -> str:
        return build_strategy_prompt(self.instance, parent_plan=_actions(parent.candidate), evaluation=parent.evaluation)

    def prospective_text(self, response: Any) -> str:
        if isinstance(response, dict):
            text = response.get("strategy")
            if isinstance(text, str):
                return " ".join(text.split())[:STRATEGY_MAX_CHARS]
        return ""

    def prospective_block(self, text: str) -> str:
        text = " ".join(text.split())
        return f"\nStrategy written before this plan (follow it): {json.dumps(text)}." if text else ""

    def corrective_hint_block(self, parent: Individual) -> str:
        return corrective_hint_block(parent.evaluation)

    def check_prompt(self, prompt: str) -> None:
        assert_no_hidden_information(prompt, optimal_length=self.optimal_length)

    # --------------------------------------------------------- candidates

    def parse_candidate(self, response: Any) -> tuple[Any, str] | None:
        if not isinstance(response, dict):
            return None
        plan = response.get("plan")
        if isinstance(plan, str):
            entries: Any = plan
        elif isinstance(plan, list) and all(isinstance(item, str) for item in plan):
            entries = plan
        else:
            return None
        parsed = parse_plan(entries)
        if not parsed.ok:
            # Keep the text so the checker grades it as a parse failure (empty plan).
            text = plan if isinstance(plan, str) else "\n".join(plan)
            return (text, text.strip() or "(unparsable)")
        actions: tuple[Action, ...] = tuple(parsed.actions)
        return (actions, render_plan_lines(actions))

    def evaluate(self, candidate: Any) -> PlanEvaluation:
        if self.expansion_cap is None:
            return evaluate_plan(self.instance, candidate)
        return evaluate_plan(self.instance, candidate, expansion_cap=self.expansion_cap)

    def outcome(self, evaluation: PlanEvaluation) -> dict[str, Any]:
        return {
            "valid": evaluation.valid,
            "success": success(evaluation),
            "score": fitness(evaluation),
            "progress": progress(evaluation),
            "bucket": outcome_bucket(evaluation),
            "details": evaluation.to_dict(),
        }

    def distance(self, text_a: str, text_b: str) -> float:
        return plan_distance(text_a.splitlines(), text_b.splitlines())


def _actions(candidate: Any) -> tuple[Action, ...]:
    """The parent's actions; for an unparsable parent, the actions parsed before the error."""
    if isinstance(candidate, tuple):
        return candidate
    if candidate is None:
        return ()
    return tuple(parse_plan(candidate).actions)


def plan_distance(plan_a: Sequence[str], plan_b: Sequence[str]) -> float:
    """1 - Jaccard overlap of (position, action) pairs; 0 for identical plans, 1 for disjoint."""
    pairs_a = {(index, line.strip()) for index, line in enumerate(plan_a) if line.strip()}
    pairs_b = {(index, line.strip()) for index, line in enumerate(plan_b) if line.strip()}
    if not pairs_a and not pairs_b:
        return 0.0
    return 1.0 - len(pairs_a & pairs_b) / len(pairs_a | pairs_b)


__all__ = ["PlanningSearchEnvironment", "plan_distance", "prompt_fingerprint", "METHOD_NAME", "SELF_REPORT_BLOCK"]
