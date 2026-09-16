"""Mutation operators for the planning environment (uniform sampling, no adaptation).

The four operators form the same SMALL / MEDIUM / MEDIUM-LARGE / LARGE ladder
as the Contexto search (``contexto_solver.operators``) and use the same enum
values (``s_mutation`` ... ``l_mutation``), so operator-level analyses read one
vocabulary across environments. What the steps mean for a plan:

* ``s_mutation``  — change exactly one action (the first invalid one if any).
* ``m_mutation``  — re-plan a short window (at most four actions) around the failure.
* ``ml_mutation`` — keep the executable prefix, re-plan everything after it.
* ``l_mutation``  — write a new plan from a new strategy.

Operator probabilities are fixed and uniform; nothing here adapts them, and
every operator applies to every parent (the templates say what to do when the
parent has no invalid action).
"""

from __future__ import annotations

import random
from enum import Enum
from typing import Sequence

import numpy as np

from .blocksworld import Action, Instance
from .evaluation import PlanEvaluation
from .prompts import (
    L_MUTATION_PROMPT,
    M_MUTATION_PROMPT,
    ML_MUTATION_PROMPT,
    S_MUTATION_PROMPT,
    build_mutation_prompt,
)


class PlanningOperator(str, Enum):
    S_MUTATION = "s_mutation"
    M_MUTATION = "m_mutation"
    ML_MUTATION = "ml_mutation"
    L_MUTATION = "l_mutation"


OPERATORS = [
    PlanningOperator.S_MUTATION,
    PlanningOperator.M_MUTATION,
    PlanningOperator.ML_MUTATION,
    PlanningOperator.L_MUTATION,
]
N_OPERATORS = len(OPERATORS)

OPERATOR_PROMPTS: dict[PlanningOperator, str] = {
    PlanningOperator.S_MUTATION: S_MUTATION_PROMPT,
    PlanningOperator.M_MUTATION: M_MUTATION_PROMPT,
    PlanningOperator.ML_MUTATION: ML_MUTATION_PROMPT,
    PlanningOperator.L_MUTATION: L_MUTATION_PROMPT,
}

OPERATOR_DESCRIPTIONS: dict[PlanningOperator, str] = {
    PlanningOperator.S_MUTATION: "change exactly one action (the first invalid action if there is one)",
    PlanningOperator.M_MUTATION: "re-plan a window of at most four actions around the failure",
    PlanningOperator.ML_MUTATION: "keep the executable prefix and re-plan everything after it",
    PlanningOperator.L_MUTATION: "write a new plan from a new strategy",
}

# The phrase that identifies each rendered operator prompt (for trace checks);
# same phrases as the Contexto ladder.
OPERATOR_DISTINGUISHING_PHRASES: dict[PlanningOperator, str] = {
    PlanningOperator.S_MUTATION: "SMALL mutation",
    PlanningOperator.M_MUTATION: "MEDIUM mutation",
    PlanningOperator.ML_MUTATION: "MEDIUM-LARGE mutation",
    PlanningOperator.L_MUTATION: "LARGE mutation",
}


def sample_operator(
    rng: np.random.Generator | random.Random,
    candidates: Sequence[PlanningOperator] | None = None,
) -> PlanningOperator:
    """Draw one operator uniformly from ``candidates`` (default: all four)."""
    pool = list(OPERATORS if candidates is None else candidates)
    if not pool:
        raise ValueError("candidates must not be empty")
    if isinstance(rng, np.random.Generator):
        index = int(rng.integers(len(pool)))
    else:
        index = rng.randrange(len(pool))
    return pool[index]


def build_operator_prompt(
    operator: PlanningOperator,
    instance: Instance,
    parent_plan: Sequence[Action],
    evaluation: PlanEvaluation,
    *,
    rationale_block: str = "",
    self_report: bool = True,
) -> str:
    """Render the prompt for ``operator`` (see ``prompts.build_mutation_prompt``)."""
    return build_mutation_prompt(
        OPERATOR_PROMPTS[operator],
        instance,
        parent_plan,
        evaluation,
        rationale_block=rationale_block,
        self_report=self_report,
    )
