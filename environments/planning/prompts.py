"""Prompt templates for the Blocksworld planning environment (no model calls).

Every candidate prompt asks for JSON of the form ``{"plan": ["(unstack b c)",
...]}`` and then, in the same object, the four self-report keys used by the
Contexto environment in the same order: ``basis_words``, ``reason``,
``predicted_bucket``, ``predicted_closeness``. The success event is stated
verbatim as ``SUCCESS_EVENT`` in every candidate prompt and in the self-report
block.

Slot layout of a mutation prompt (``build_mutation_prompt``)::

    problem -> action rules -> parent plan -> checker feedback ->
    {rationale_block} -> operator instruction -> output format -> self-report

The ``rationale_block`` slot is the single insertion point for the rationale
channel. It takes either the inherited parent rationale
(``contexto_solver.self_report.rationale_inheritance_block``, reused as is), a
corrective hint (``corrective_hint_block``, the control that checks the channel
can influence the model at all), a replacement text for a rationale
intervention, or the empty string. The prospective channel uses two templates:
``STRATEGY_PROMPT`` (one call writes a short strategy) and
``PLAN_FROM_STRATEGY_PROMPT`` (the next call plans from it).

The templates never mention the optimal plan length, the reference plan, or the
exact remaining distance; ``assert_no_hidden_information`` checks a rendered
prompt for those.
"""

from __future__ import annotations

import json
import re
from typing import Any, Sequence

from contexto_solver.self_report import rationale_inheritance_block

from .blocksworld import (
    Action,
    Instance,
    render_goal_natural_language,
    render_state_natural_language,
)
from .evaluation import OUTCOME_BUCKETS, PlanEvaluation

SUCCESS_EVENT = (
    "the plan executes from the initial state without an invalid action and reaches every goal condition"
)

PREDICTED_BUCKETS = OUTCOME_BUCKETS
SELF_REPORT_KEYS = ("basis_words", "reason", "predicted_bucket", "predicted_closeness")

# Appended LAST to every candidate prompt via the ``{self_report_block}`` slot.
# Same four keys and order as the Contexto block; the buckets and the chance
# question are restated for the planning success event.
SELF_REPORT_BLOCK = (
    '\nIn the SAME JSON object, also include these four keys, in this order: '
    '"basis_words" (a list of words taken from the problem, rules, or feedback above '
    'that your plan relied on), "reason" (a one or two sentence explanation), '
    '"predicted_bucket" (exactly one of "complete", "partial", or "invalid", estimating '
    'how your plan will be graded: "complete" = ' + SUCCESS_EVENT + ', "partial" = the '
    'plan executes without an invalid action but leaves at least one goal condition '
    'unmet, "invalid" = the plan contains an action whose preconditions do not hold), '
    'and "predicted_closeness" (a number from 0 to 1 giving your estimated chance that '
    + SUCCESS_EVENT + ', where 1 means you are certain).'
)

ACTION_RULES = """Actions (write each exactly in this form, one block name per argument):
- (pick-up x): requires block x on the table, x clear, and the hand empty. Afterwards the hand holds x.
- (put-down x): requires the hand to hold x. Afterwards x is on the table, x is clear, and the hand is empty.
- (stack x y): requires the hand to hold x and block y clear. Afterwards x is on y, x is clear, y is not clear, and the hand is empty.
- (unstack x y): requires x on y, x clear, and the hand empty. Afterwards the hand holds x and y is clear.
The hand holds at most one block. A block is clear when nothing is on it and it is not held. Only clear blocks can be picked up or unstacked."""

OUTPUT_FORMAT = (
    'Return only JSON, no markdown or explanation, of the form '
    '{"plan": ["(unstack b c)", "(put-down b)"]} where "plan" lists the actions in execution order.'
)

INITIAL_PLAN_PROMPT = """Return only JSON, no markdown or explanation.
You are solving a Blocksworld planning problem.
{problem}

{action_rules}

Success means {success_event}.
Write a complete plan that takes the initial state to the goal.
{output_format}{self_report_block}"""

_MUTATION_TEMPLATE = """Return only JSON, no markdown or explanation.
You are improving a candidate plan for a Blocksworld planning problem.
{problem}

{action_rules}

Parent plan (one action per line):
{parent_plan}

{feedback}{rationale_block}

Operator: {operator_instruction}
Success means {success_event}.
{output_format}{self_report_block}"""

# The four operators form a ladder from the smallest to the largest change to
# the parent plan, mirroring the Contexto ladder (SMALL / MEDIUM / MEDIUM-LARGE
# / LARGE). Each template states what must stay fixed and what may change.

S_MUTATION_PROMPT = _MUTATION_TEMPLATE.replace(
    "{operator_instruction}",
    "Make a SMALL mutation: change exactly ONE action of the parent plan and keep every other action "
    "exactly as it is, in the same order. If the checker found an invalid action, the action you change "
    "is that first invalid action: replace it with one action whose preconditions hold in the state reached "
    "before it, or delete it. If the checker found no invalid action, change one action or add one action "
    "at the end so the plan gets closer to the goal. The returned plan must differ from the parent in at "
    "most one action.",
)

M_MUTATION_PROMPT = _MUTATION_TEMPLATE.replace(
    "{operator_instruction}",
    "Make a MEDIUM mutation: re-plan only the few actions around the failure. Keep the parent plan "
    "unchanged except for a short window of at most four consecutive actions that contains the first "
    "invalid action (or, if the plan has no invalid action, the point where it stops making progress "
    "towards the goal); rewrite that window so its actions execute from the state before it and the "
    "actions after the window still execute. Do not rewrite the rest of the plan.",
)

ML_MUTATION_PROMPT = _MUTATION_TEMPLATE.replace(
    "{operator_instruction}",
    "Make a MEDIUM-LARGE mutation: keep the executable prefix of the parent plan exactly as it is "
    "(every action up to but not including the first invalid action, or the whole plan if it has no "
    "invalid action) and re-plan everything after it from the state reached by that prefix, so that the "
    "whole plan reaches every goal condition. The prefix must not be edited or reordered.",
)

L_MUTATION_PROMPT = _MUTATION_TEMPLATE.replace(
    "{operator_instruction}",
    "Make a LARGE mutation: ignore the parent plan's ordering and write a complete new plan from a "
    "different high-level strategy: decide which blocks must be moved out of the way first, which "
    "tower to build first, and in what order to place blocks so each placement's preconditions hold. "
    "Describe the new strategy in your reason.",
)

STRATEGY_PROMPT = """Return only JSON, no markdown or explanation.
You are preparing to solve a Blocksworld planning problem. Do not write the plan yet.
{problem}

{action_rules}
{parent_block}
Write a strategy of two or three sentences: which blocks must be moved out of the way, which tower to build first, and in what order blocks should be placed so that every action's preconditions hold.
Return JSON of the form {{"strategy": "two or three sentences"}}."""

PLAN_FROM_STRATEGY_PROMPT = """Return only JSON, no markdown or explanation.
You are solving a Blocksworld planning problem by following a given strategy.
{problem}

{action_rules}
{parent_block}
Strategy to follow:
{strategy}

Write the complete plan that carries out this strategy from the initial state to the goal.
Success means {success_event}.
{output_format}{self_report_block}"""

EMPTY_PLAN_TEXT = "(no actions)"

HIDDEN_INFORMATION_PHRASES = (
    "optimal",
    "shortest",
    "reference plan",
    "reference solution",
    "minimum number of actions",
    "minimal plan",
    "fewest actions",
    "remaining distance",
    "distance to the goal",
    "lower bound",
)

_HIDDEN_LENGTH_PATTERNS = (
    r"(?:optimal|shortest|minimum|minimal|fewest|best)[^\n.]{{0,60}}\b{n}\b",
    r"\b{n}\b[^\n.]{{0,20}}\b(?:actions?|steps?|moves?)\b[^\n.]{{0,40}}"
    r"\b(?:suffice|sufficient|enough|needed|required|necessary)\b",
    r"\b(?:solved|solvable|reachable|completed|done|finished)\b[^\n.]{{0,30}}\bin\s+{n}\s+(?:actions?|steps?|moves?)\b",
)


# --------------------------------------------------------------------------- #
# Rendering helpers
# --------------------------------------------------------------------------- #


def self_report_block(enabled: bool) -> str:
    """The planning self-report block, or ``""`` when the flag is off."""
    return SELF_REPORT_BLOCK if enabled else ""


def render_problem(instance: Instance) -> str:
    """The problem in controlled natural language: blocks, initial state, goal."""
    return (
        f"Blocks: {', '.join(instance.blocks)}.\n"
        f"Initial state: {render_state_natural_language(instance.initial_state)}\n"
        f"Goal (every condition must hold at the end; blocks not mentioned may be anywhere): "
        f"{render_goal_natural_language(instance.goal)}"
    )


def render_plan_lines(plan: Sequence[Action]) -> str:
    """Canonical actions one per line, or ``EMPTY_PLAN_TEXT`` for an empty plan."""
    return "\n".join(str(action) for action in plan) if plan else EMPTY_PLAN_TEXT


def render_checker_feedback(evaluation: PlanEvaluation) -> str:
    """The exact checker feedback shown to the operator.

    Deliberately excludes the remaining distance and any fitness value; only
    the parse status, executable prefix, first invalid action and its reason,
    the reached state, and the goal predicate counts are shown.
    """
    lines = ["Checker feedback on the parent plan:"]
    if evaluation.parse_ok:
        lines.append("- Parse: ok.")
    else:
        lines.append(f"- Parse: failed ({evaluation.parse_error}); the plan was graded as empty.")
    lines.append(
        f"- Executable prefix: {evaluation.executable_prefix_length} of {evaluation.plan_length} "
        "actions executed without error."
    )
    if evaluation.first_invalid_action is None:
        lines.append("- First invalid action: none.")
    else:
        lines.append(
            f"- First invalid action: {evaluation.first_invalid_action} at position "
            f"{evaluation.executable_prefix_length + 1}: {evaluation.first_invalid_reason}."
        )
    lines.append(f"- State after the executable prefix: {render_state_natural_language(evaluation.reached_state)}")
    lines.append(
        f"- Goal conditions satisfied after the executable prefix: {evaluation.goal_predicates_satisfied} "
        f"of {evaluation.goal_predicates_total}."
    )
    if evaluation.unsatisfied_goal_predicates:
        unmet = render_goal_natural_language(frozenset(evaluation.unsatisfied_goal_predicates))
        lines.append(f"- Goal conditions not yet satisfied: {unmet}")
    else:
        lines.append("- Goal conditions not yet satisfied: none.")
    return "\n".join(lines)


def inherited_rationale_block(parent_rationale: dict[str, Any] | None) -> str:
    """The parent's ``basis_words``/``reason`` rendered for the ``{rationale_block}`` slot.

    Delegates to ``contexto_solver.self_report.rationale_inheritance_block`` so
    the planning and Contexto environments inject byte-identical text for the
    same parent rationale; only the block text is returned. Empty when the
    parent has no rationale.
    """
    block, _ = rationale_inheritance_block(parent_rationale)
    return block


def corrective_hint_block(evaluation: PlanEvaluation) -> str:
    """One sentence naming the first invalid action and the precondition it violates.

    Rendered for the same ``{rationale_block}`` slot as
    ``inherited_rationale_block`` (leading newline included) so the two
    conditions differ only in the text inserted there. Empty when the parent
    plan has no invalid action and no parse failure.
    """
    if not evaluation.parse_ok:
        return f"\nCorrective hint: the parent plan could not be parsed ({evaluation.parse_error}); every action must be written exactly as (name block) or (name block block)."
    if evaluation.first_invalid_action is None:
        return ""
    return (
        f"\nCorrective hint: action {evaluation.first_invalid_action} at position "
        f"{evaluation.executable_prefix_length + 1} is invalid because {evaluation.first_invalid_reason}; "
        "change that action or the actions before it."
    )


def _parent_block(parent_plan: Sequence[Action] | None, evaluation: PlanEvaluation | None) -> str:
    if parent_plan is None:
        return ""
    block = f"\nParent plan (one action per line):\n{render_plan_lines(parent_plan)}\n"
    if evaluation is not None:
        block += f"\n{render_checker_feedback(evaluation)}\n"
    return block


# --------------------------------------------------------------------------- #
# Prompt builders
# --------------------------------------------------------------------------- #


def build_initial_plan_prompt(instance: Instance, *, self_report: bool = True) -> str:
    """Prompt (a): propose a plan from the natural-language problem and action syntax."""
    return INITIAL_PLAN_PROMPT.format(
        problem=render_problem(instance),
        action_rules=ACTION_RULES,
        success_event=SUCCESS_EVENT,
        output_format=OUTPUT_FORMAT,
        self_report_block=self_report_block(self_report),
    )


def build_mutation_prompt(
    template: str,
    instance: Instance,
    parent_plan: Sequence[Action],
    evaluation: PlanEvaluation,
    *,
    rationale_block: str = "",
    self_report: bool = True,
) -> str:
    """Prompt (b): render one operator template with the parent plan and checker feedback.

    ``rationale_block`` is inserted verbatim into the single rationale slot; pass
    the inherited-rationale text, ``corrective_hint_block(evaluation)``, a
    replacement text, or ``""``.
    """
    return template.format(
        problem=render_problem(instance),
        action_rules=ACTION_RULES,
        parent_plan=render_plan_lines(parent_plan),
        feedback=render_checker_feedback(evaluation),
        rationale_block=rationale_block,
        success_event=SUCCESS_EVENT,
        output_format=OUTPUT_FORMAT,
        self_report_block=self_report_block(self_report),
    )


def build_strategy_prompt(
    instance: Instance,
    *,
    parent_plan: Sequence[Action] | None = None,
    evaluation: PlanEvaluation | None = None,
) -> str:
    """Prompt (c, first call): write a two-or-three-sentence strategy, no plan yet."""
    return STRATEGY_PROMPT.format(
        problem=render_problem(instance),
        action_rules=ACTION_RULES,
        parent_block=_parent_block(parent_plan, evaluation),
    )


def build_plan_from_strategy_prompt(
    instance: Instance,
    strategy: str,
    *,
    parent_plan: Sequence[Action] | None = None,
    evaluation: PlanEvaluation | None = None,
    self_report: bool = True,
) -> str:
    """Prompt (c, second call): generate or repair a plan that follows the strategy."""
    return PLAN_FROM_STRATEGY_PROMPT.format(
        problem=render_problem(instance),
        action_rules=ACTION_RULES,
        parent_block=_parent_block(parent_plan, evaluation),
        strategy=strategy.strip(),
        success_event=SUCCESS_EVENT,
        output_format=OUTPUT_FORMAT,
        self_report_block=self_report_block(self_report),
    )


# --------------------------------------------------------------------------- #
# Hidden-information guard
# --------------------------------------------------------------------------- #


def assert_no_hidden_information(
    prompt: str,
    *,
    optimal_length: int | None = None,
    reference_plan: Sequence[Action] | None = None,
    parent_plan: Sequence[Action] | None = None,
) -> None:
    """Raise ``AssertionError`` if a rendered prompt leaks solver-side information.

    The goal is allowed. Forbidden: any of ``HIDDEN_INFORMATION_PHRASES``; the
    optimal length stated as such (``optimal_length`` given); the reference
    plan appearing as a contiguous sequence (``reference_plan`` given). When
    the parent plan legitimately equals the reference plan, pass
    ``parent_plan`` so that one occurrence is not counted as a leak.

    Callers pass the prompt with the rationale slot removed: the slot holds
    text the model wrote (an inherited reason, a prospective strategy), which
    cannot leak solver-side facts but may well contain words like "optimal".
    """
    lowered = prompt.lower()
    for phrase in HIDDEN_INFORMATION_PHRASES:
        if phrase in lowered:
            raise AssertionError(f"prompt contains hidden-information phrase {phrase!r}")
    if optimal_length is not None:
        for pattern in _HIDDEN_LENGTH_PATTERNS:
            if re.search(pattern.format(n=optimal_length), lowered):
                raise AssertionError(f"prompt appears to state the optimal plan length {optimal_length}")
    if reference_plan:
        reference_lines = [str(action) for action in reference_plan]
        line_rendering = "\n".join(reference_lines)
        allowance = {
            line_rendering: 0,
            ", ".join(reference_lines): 0,
            " ".join(reference_lines): 0,
            json.dumps(reference_lines): 0,
        }
        if parent_plan is not None and [str(action) for action in parent_plan] == reference_lines:
            allowance[line_rendering] = 1
        for rendering, allowed in allowance.items():
            if prompt.count(rendering) > allowed:
                raise AssertionError("prompt contains the reference plan")
