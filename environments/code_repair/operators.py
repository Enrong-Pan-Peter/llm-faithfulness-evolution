"""Mutation operators for the code-repair environment.

The four operators form the same SMALL / MEDIUM / MEDIUM-LARGE / LARGE ladder
as the Contexto search (``contexto_solver.operators``) and use the same enum
values (``s_mutation`` ... ``l_mutation``), so operator-level analyses read one
vocabulary across environments. What the steps mean for a program:

* ``s_mutation``  — change exactly one line, aimed at the first failing case.
* ``m_mutation``  — rewrite the one branch, loop or expression at fault.
* ``ml_mutation`` — replace the algorithmic core, keep signature and passing cases.
* ``l_mutation``  — rewrite the whole function from the specification.

Sampling is uniform; there are no adaptive operator probabilities.
"""

from __future__ import annotations

import random
from enum import Enum

import numpy as np

from .evaluation import CodeEvaluation
from .prompts import (
    L_MUTATION_PROMPT,
    M_MUTATION_PROMPT,
    ML_MUTATION_PROMPT,
    S_MUTATION_PROMPT,
    build_candidate_prompt,
)
from .tasks import Task


class CodeOperator(str, Enum):
    S_MUTATION = "s_mutation"
    M_MUTATION = "m_mutation"
    ML_MUTATION = "ml_mutation"
    L_MUTATION = "l_mutation"


OPERATORS: list[CodeOperator] = [
    CodeOperator.S_MUTATION,
    CodeOperator.M_MUTATION,
    CodeOperator.ML_MUTATION,
    CodeOperator.L_MUTATION,
]
N_OPERATORS = len(OPERATORS)

OPERATOR_PROMPTS: dict[CodeOperator, str] = {
    CodeOperator.S_MUTATION: S_MUTATION_PROMPT,
    CodeOperator.M_MUTATION: M_MUTATION_PROMPT,
    CodeOperator.ML_MUTATION: ML_MUTATION_PROMPT,
    CodeOperator.L_MUTATION: L_MUTATION_PROMPT,
}

OPERATOR_DESCRIPTIONS: dict[CodeOperator, str] = {
    CodeOperator.S_MUTATION: "change exactly one line, aimed at the first failing development case",
    CodeOperator.M_MUTATION: "rewrite the one branch, loop or expression at fault",
    CodeOperator.ML_MUTATION: "replace the algorithmic core, keeping the signature and passing cases",
    CodeOperator.L_MUTATION: "rewrite the whole function from the specification",
}

# Same phrases as the Contexto ladder.
OPERATOR_DISTINGUISHING_PHRASES: dict[CodeOperator, str] = {
    CodeOperator.S_MUTATION: "SMALL mutation",
    CodeOperator.M_MUTATION: "MEDIUM mutation",
    CodeOperator.ML_MUTATION: "MEDIUM-LARGE mutation",
    CodeOperator.L_MUTATION: "LARGE mutation",
}


def sample_operator(rng: random.Random | np.random.Generator) -> CodeOperator:
    """Draw one operator uniformly at random."""
    if isinstance(rng, np.random.Generator):
        return OPERATORS[int(rng.integers(len(OPERATORS)))]
    return rng.choice(OPERATORS)


def build_operator_prompt(
    operator: CodeOperator,
    task: Task,
    parent_program: str,
    parent_evaluation: CodeEvaluation,
    rationale_block: str = "",
) -> str:
    """Render the prompt for ``operator`` applied to ``parent_program``.

    ``rationale_block`` fills the single slot shared by the inherited
    rationale, the corrective hint and the diagnosis (see ``prompts``).
    """
    return build_candidate_prompt(
        OPERATOR_PROMPTS[operator], task, parent_program, parent_evaluation, rationale_block
    )
