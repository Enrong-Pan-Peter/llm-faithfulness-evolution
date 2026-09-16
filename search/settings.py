"""Settings of the shared loop, read from the same environment variables as Contexto.

``INITIAL_POPULATION``, ``SURVIVORS``, ``OFFSPRING_PER_PARENT``, ``SELECTION``
and ``MAX_GENERATIONS`` come from ``contexto_solver.config`` so one ``.env``
drives all three environments. ``SELF_REPORT`` defaults to on here (the
Contexto default is off for the legacy no-report condition); set
``SELF_REPORT=0`` or ``--self-report 0`` for a no-report run. Two settings are new:

* ``RATIONALE_CHANNEL``: what fills the rationale slot of every mutation prompt
  (``inherited`` = the parent's stored basis words and reason, as in Contexto;
  ``prospective`` = a strategy / diagnosis written by a separate call before
  the candidate call; ``corrective_hint`` = one sentence of exact feedback, the
  control; ``none`` = empty slot);
* ``STOP_AT_SUCCESS`` (default 1): stop after the first generation that
  contains a successful candidate; 0 runs every generation regardless.
* ``SELECTION=report_rewarded``: the positive control for the selection
  question. Survivors are the individuals whose self-report agreed best with
  their outcome (smallest |predicted_closeness - 1{success}|; an unparsed
  report counts as the worst error), ties broken by fitness.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

from contexto_solver import config as app_config

from .environment import RATIONALE_CHANNELS

SELECTION_CHOICES = ("mu_plus_lambda", "random", "report_rewarded")


def _env_choice(name: str, default: str, choices: tuple[str, ...]) -> str:
    value = os.getenv(name, default).strip().lower()
    if value not in choices:
        raise ValueError(f"{name}={value!r} is not one of {choices}")
    return value


@dataclass(frozen=True)
class SearchSettings:
    initial_population: int = 15
    survivors: int = 5
    offspring_per_parent: int = 2
    selection: str = "mu_plus_lambda"
    self_report: bool = True
    rationale_channel: str = "inherited"
    max_generations: int = 10
    random_seed: int = 0
    operator_mix: str = "fixed_uniform"
    stop_at_success: bool = True

    def __post_init__(self) -> None:
        if self.selection not in SELECTION_CHOICES:
            raise ValueError(f"selection={self.selection!r} is not one of {SELECTION_CHOICES}")
        if self.rationale_channel not in RATIONALE_CHANNELS:
            raise ValueError(f"rationale_channel={self.rationale_channel!r} is not one of {RATIONALE_CHANNELS}")
        if self.initial_population < 1 or self.survivors < 1 or self.offspring_per_parent < 1:
            raise ValueError("initial_population, survivors and offspring_per_parent must be >= 1")
        if self.max_generations < 0:
            raise ValueError("max_generations must be >= 0")

    @property
    def offspring_per_generation(self) -> int:
        return self.survivors * self.offspring_per_parent

    @property
    def pool_is_constant(self) -> bool:
        return self.initial_population == self.survivors + self.offspring_per_generation

    def to_dict(self) -> dict:
        record = asdict(self)
        record["offspring_per_generation"] = self.offspring_per_generation
        record["pool_is_constant"] = self.pool_is_constant
        return record

    def to_dict_for_init(self) -> dict:
        """The constructor fields only (for ``SearchSettings(**...)``)."""
        return asdict(self)

    def with_seed(self, random_seed: int) -> "SearchSettings":
        return SearchSettings(**{**asdict(self), "random_seed": random_seed})

    @classmethod
    def from_env(cls, **overrides) -> "SearchSettings":
        """Settings from the environment (``.env``), with keyword overrides."""
        values = dict(
            initial_population=app_config.INITIAL_POPULATION,
            survivors=app_config.SURVIVORS,
            offspring_per_parent=app_config.OFFSPRING_PER_PARENT,
            selection=_env_choice("SELECTION", "mu_plus_lambda", SELECTION_CHOICES),
            self_report=os.getenv("SELF_REPORT", "1").strip().lower() not in ("0", "false", "no", "off", ""),
            rationale_channel=_env_choice("RATIONALE_CHANNEL", "inherited", RATIONALE_CHANNELS),
            max_generations=app_config.MAX_GENERATIONS,
            random_seed=int(os.getenv("RANDOM_SEED", "").strip() or "0"),
            stop_at_success=os.getenv("STOP_AT_SUCCESS", "1").strip().lower() not in ("0", "false", "no", "off"),
        )
        values.update({key: value for key, value in overrides.items() if value is not None})
        return cls(**values)
