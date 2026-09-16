"""The four semantic mutation operators of the Contexto search and their sampling.

The submitted study drew the operator for every mutation with fixed, uniform
probability (one quarter each). ``Hypothesis.sigma`` still carries that uniform
vector because the trace format records it; nothing adapts it.
"""

from __future__ import annotations

from enum import Enum

import numpy as np

from .llm_client import L_MUTATION_PROMPT, M_MUTATION_PROMPT, ML_MUTATION_PROMPT, S_MUTATION_PROMPT


class Operator(str, Enum):
    S_MUTATION = "s_mutation"
    M_MUTATION = "m_mutation"
    ML_MUTATION = "ml_mutation"
    L_MUTATION = "l_mutation"


OPERATORS = [
    Operator.S_MUTATION,
    Operator.M_MUTATION,
    Operator.ML_MUTATION,
    Operator.L_MUTATION,
]
N_OPERATORS = 4

OPERATOR_PROMPTS: dict[Operator, str] = {
    Operator.S_MUTATION: S_MUTATION_PROMPT,
    Operator.M_MUTATION: M_MUTATION_PROMPT,
    Operator.ML_MUTATION: ML_MUTATION_PROMPT,
    Operator.L_MUTATION: L_MUTATION_PROMPT,
}

OPERATOR_DISTINGUISHING_PHRASES: dict[Operator, str] = {
    Operator.S_MUTATION: "SMALL mutation",
    Operator.M_MUTATION: "MEDIUM mutation",
    Operator.ML_MUTATION: "MEDIUM-LARGE mutation",
    Operator.L_MUTATION: "LARGE mutation",
}


def initial_sigma() -> np.ndarray:
    """The fixed uniform operator probabilities (one quarter each)."""
    return np.full(N_OPERATORS, 1.0 / N_OPERATORS, dtype=np.float64)


def validate_sigma(sigma: np.ndarray) -> np.ndarray:
    sigma = np.asarray(sigma, dtype=np.float64)
    assert sigma.shape == (N_OPERATORS,)
    assert np.isclose(sigma.sum(), 1.0, atol=1e-6)
    return sigma


def sample_operator(sigma: np.ndarray, rng: np.random.Generator) -> Operator:
    """Draw an operator from an explicit probability vector (legacy path)."""
    sigma = validate_sigma(sigma)
    index = rng.choice(N_OPERATORS, p=sigma)
    return OPERATORS[int(index)]


def sample_operator_uniform(rng: np.random.Generator) -> Operator:
    """Draw one of the four operators with equal probability.

    Identical in distribution to ``sample_operator(initial_sigma(), rng)`` and
    consumes the random stream in the same way, so runs with the same seed draw
    the same operator sequence under both functions.
    """
    return sample_operator(initial_sigma(), rng)


def assert_prompt_has_no_sigma_leak(prompt: str, sigma: np.ndarray, operator: Operator) -> None:
    """Fail if a rendered mutation prompt reveals the operator mix or lacks its operator text."""
    phrase = OPERATOR_DISTINGUISHING_PHRASES[operator]
    if phrase not in prompt:
        raise AssertionError(f"Prompt for {operator.value} is missing distinguishing phrase {phrase!r}.")

    lowered = prompt.lower()
    for substring in ("sigma", "σ", "probability"):
        if substring in lowered:
            raise AssertionError(f"Prompt for {operator.value} leaked forbidden substring {substring!r}.")

    for value in validate_sigma(sigma):
        token = f"{value:.2f}"
        if token in prompt:
            raise AssertionError(f"Prompt for {operator.value} leaked sigma numeric literal {token!r}.")
