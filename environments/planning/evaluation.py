"""Exact plan evaluation, fitness, and the common evaluation record.

``evaluate_plan`` executes a candidate action list from the instance's initial
state, stops at the first invalid action, and reports what the checker saw:
parse status, the executable prefix, the reached state, goal predicates
satisfied, and (when the exact search finishes under its cap) the remaining
distance from the reached state to the goal.

Fitness convention (LOWER is better, matching Contexto where rank 1 is best):

* ``fitness_exact``: ``remaining_distance + tie_break`` (``0.0`` when the plan
  succeeds). ``None`` when the exact search did not finish under the cap.
* ``fitness_goal_count``: ``unsatisfied_goal_predicates + tie_break`` (``0.0``
  on success). Always available.
* ``fitness``: ``fitness_exact`` when available, else ``fitness_goal_count``.

The tie-break lies in ``(0, 0.75]`` so it can never reorder two candidates
whose integer primary terms differ. Within one primary level it prefers a plan
that executes completely over one that stops at an invalid action, and then a
longer executable prefix. Success is ``goal_complete``: every action executed
and every goal predicate holds at the end. A plan whose executable prefix
happens to satisfy the goal but which then contains an invalid action is not a
success; its primary term is ``0`` and only the tie-break separates it from a
genuine solution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .blocksworld import (
    DEFAULT_EXPANSION_CAP,
    Action,
    Instance,
    InvalidAction,
    Predicate,
    State,
    apply,
    goal_complete,
    goal_satisfied_count,
    optimal_plan_length,
    parse_plan,
    predicate_text,
)

CHECKER_CALL_COST = 1

OUTCOME_COMPLETE = "complete"
OUTCOME_PARTIAL = "partial"
OUTCOME_INVALID = "invalid"
OUTCOME_BUCKETS = (OUTCOME_COMPLETE, OUTCOME_PARTIAL, OUTCOME_INVALID)


@dataclass(frozen=True)
class PlanEvaluation:
    """Everything the checker observed about one candidate plan."""

    instance_id: str
    n_blocks: int
    parse_ok: bool
    parse_error: str | None
    plan_length: int
    executable_prefix_length: int
    first_invalid_action: str | None
    first_invalid_reason: str | None
    reached_state: State
    goal_predicates_total: int
    goal_predicates_satisfied: int
    goal_complete: bool
    remaining_distance: int | None
    unsatisfied_goal_predicates: tuple[Predicate, ...]

    @property
    def valid(self) -> bool:
        """The plan parsed and every action executed."""
        return self.parse_ok and self.first_invalid_action is None

    @property
    def goal_predicates_unsatisfied(self) -> int:
        return self.goal_predicates_total - self.goal_predicates_satisfied

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready record; the reached state is listed as sorted predicate text."""
        return {
            "instance_id": self.instance_id,
            "n_blocks": self.n_blocks,
            "parse_ok": self.parse_ok,
            "parse_error": self.parse_error,
            "plan_length": self.plan_length,
            "executable_prefix_length": self.executable_prefix_length,
            "first_invalid_action": self.first_invalid_action,
            "first_invalid_reason": self.first_invalid_reason,
            "reached_state": sorted(predicate_text(predicate) for predicate in self.reached_state),
            "goal_predicates_total": self.goal_predicates_total,
            "goal_predicates_satisfied": self.goal_predicates_satisfied,
            "goal_complete": self.goal_complete,
            "remaining_distance": self.remaining_distance,
            "unsatisfied_goal_predicates": [predicate_text(predicate) for predicate in self.unsatisfied_goal_predicates],
        }


def _as_actions(plan: str | Sequence[str] | Sequence[Action]) -> tuple[tuple[Action, ...], str | None]:
    """Coerce the candidate to actions; returns ``(actions, parse_error)``."""
    if isinstance(plan, str):
        parsed = parse_plan(plan)
    else:
        items = list(plan)
        if all(isinstance(item, Action) for item in items):
            return tuple(items), None
        parsed = parse_plan([str(item) for item in items])
    if parsed.ok:
        return parsed.actions, None
    position = "" if parsed.error_position is None else f" (entry {parsed.error_position})"
    return (), f"{parsed.error}{position}"


def evaluate_plan(
    instance: Instance,
    plan: str | Sequence[str] | Sequence[Action],
    *,
    expansion_cap: int = DEFAULT_EXPANSION_CAP,
) -> PlanEvaluation:
    """Execute the candidate and grade it exactly.

    ``plan`` may be canonical text (one action per line or a JSON list), a list
    of action strings, or ``Action`` objects. A plan that fails to parse is
    graded as an empty plan with ``parse_ok=False``. ``expansion_cap`` bounds
    the exact remaining-distance search; ``0`` skips it (``remaining_distance``
    becomes ``None`` and ``fitness`` falls back to the goal count).
    """
    actions, parse_error = _as_actions(plan)
    state = instance.initial_state
    prefix = 0
    first_invalid: Action | None = None
    first_reason: str | None = None
    for action in actions:
        try:
            state = apply(state, action)
        except InvalidAction as error:
            first_invalid = action
            first_reason = error.reason
            break
        prefix += 1

    satisfied = goal_satisfied_count(state, instance.goal)
    total = len(instance.goal)
    valid = parse_error is None and first_invalid is None
    complete = valid and goal_complete(state, instance.goal)
    unsatisfied = tuple(sorted(predicate for predicate in instance.goal if predicate not in state))

    remaining: int | None
    if goal_complete(state, instance.goal):
        remaining = 0
    elif expansion_cap > 0:
        remaining = optimal_plan_length(state, instance.goal, expansion_cap=expansion_cap)
    else:
        remaining = None

    return PlanEvaluation(
        instance_id=instance.instance_id,
        n_blocks=instance.n_blocks,
        parse_ok=parse_error is None,
        parse_error=parse_error,
        plan_length=len(actions),
        executable_prefix_length=prefix,
        first_invalid_action=None if first_invalid is None else str(first_invalid),
        first_invalid_reason=first_reason,
        reached_state=state,
        goal_predicates_total=total,
        goal_predicates_satisfied=satisfied,
        goal_complete=complete,
        remaining_distance=remaining,
        unsatisfied_goal_predicates=unsatisfied,
    )


def tie_break(evaluation: PlanEvaluation) -> float:
    """Secondary term in ``(0, 0.75]``: validity first, then a longer executable prefix.

    ``(2 * invalid + 1 / (1 + prefix)) / 4``: a fully executable plan scores in
    ``(0, 0.25]``, a plan with an invalid action or parse failure in
    ``(0.5, 0.75]``; within each band a longer executable prefix is smaller.
    """
    invalid = 0 if evaluation.valid else 1
    return (2 * invalid + 1.0 / (1 + evaluation.executable_prefix_length)) / 4.0


def fitness_goal_count(evaluation: PlanEvaluation) -> float:
    """Unsatisfied goal predicates plus the tie-break; ``0.0`` on success."""
    if evaluation.goal_complete:
        return 0.0
    return evaluation.goal_predicates_unsatisfied + tie_break(evaluation)


def fitness_exact(evaluation: PlanEvaluation) -> float | None:
    """Exact remaining distance plus the tie-break; ``None`` when unavailable."""
    if evaluation.goal_complete:
        return 0.0
    if evaluation.remaining_distance is None:
        return None
    return evaluation.remaining_distance + tie_break(evaluation)


def fitness(evaluation: PlanEvaluation) -> float:
    """Lower is better: ``fitness_exact`` when available, else ``fitness_goal_count``."""
    exact = fitness_exact(evaluation)
    return fitness_goal_count(evaluation) if exact is None else exact


def success(evaluation: PlanEvaluation) -> bool:
    """The success event: every action executed and every goal predicate holds."""
    return evaluation.goal_complete


def progress(evaluation: PlanEvaluation) -> float:
    """Fraction of goal predicates satisfied after the executable prefix, in ``[0, 1]``."""
    if evaluation.goal_predicates_total == 0:
        return 1.0
    return evaluation.goal_predicates_satisfied / evaluation.goal_predicates_total


def outcome_bucket(evaluation: PlanEvaluation) -> str:
    """The realised ordinal bucket the self-report's ``predicted_bucket`` is scored against."""
    if evaluation.goal_complete:
        return OUTCOME_COMPLETE
    if evaluation.valid:
        return OUTCOME_PARTIAL
    return OUTCOME_INVALID


def to_common_record(evaluation: PlanEvaluation) -> dict[str, Any]:
    """The evaluation record shape shared by every environment."""
    return {
        "valid": evaluation.valid,
        "success": success(evaluation),
        "score": fitness(evaluation),
        "progress": progress(evaluation),
        "cost": CHECKER_CALL_COST,
        "details": {
            **evaluation.to_dict(),
            "outcome_bucket": outcome_bucket(evaluation),
            "fitness_exact": fitness_exact(evaluation),
            "fitness_goal_count": fitness_goal_count(evaluation),
        },
    }
