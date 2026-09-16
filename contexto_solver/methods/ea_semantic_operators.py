"""Evolutionary Contexto search with four semantic mutation operators (``ea_semantic_operators``).

This is the harmonised search used for new experiments. Compared with the
submitted study (kept verbatim in :mod:`ea_semantic_operators_legacy`):

* survivor selection is classical (mu + lambda): the best ``survivors`` of
  parents + offspring continue, everyone else leaves the search for good;
* the pool has the same size at every selection when
  ``initial_population == survivors + survivors * offspring_per_parent + crossover_children``
  (the default 15 = 5 + 5 * 2 + 0);
* fitness is fixed at birth unless ``parent_refresh`` is on;
* the four mutation operators are drawn with fixed uniform probability; nothing
  adapts;
* the ``random`` selection control keeps the same survivor count but ignores
  fitness; the ``report_rewarded`` positive control keeps the individuals whose
  self-report agreed best with their outcome (see ``config.SELECTION``).

Self-reports and rationale inheritance work exactly as in the submitted study:
the report keys are requested after the candidate in the same completion, and a
mutation prompt may carry the parent's stored basis words and reason. Crossover
never inherits a rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from ..hypothesis import Hypothesis
from ..operators import OPERATOR_PROMPTS, assert_prompt_has_no_sigma_leak, sample_operator_uniform
from .ea_core import BaseEALLMMethod, EALLMConfig, _words_from_category

SELECTION_CHOICES = ("mu_plus_lambda", "random", "report_rewarded")
# predicted_closeness forecasts "best proposed word within the top 100".
REPORT_SUCCESS_RANK = 100


@dataclass
class EASemanticOperatorsConfig(EALLMConfig):
    survivors: int = 5
    offspring_per_parent: int = 2
    crossover_children: int = 0
    parent_refresh: bool = False
    selection: str = "mu_plus_lambda"
    random_seed: int | None = None

    def __post_init__(self) -> None:
        if self.selection not in SELECTION_CHOICES:
            raise ValueError(f"selection={self.selection!r} is not one of {SELECTION_CHOICES}")
        if self.survivors < 1 or self.offspring_per_parent < 0 or self.crossover_children < 0:
            raise ValueError("survivors must be >= 1 and offspring counts >= 0")
        # The base class reads max_active_hypotheses in a few logging paths.
        self.max_active_hypotheses = self.survivors

    @property
    def offspring_per_generation(self) -> int:
        return self.survivors * self.offspring_per_parent + self.crossover_children

    @property
    def pool_is_constant(self) -> bool:
        """True when the selection pool has the same size in every generation."""
        return self.initial_categories == self.survivors + self.offspring_per_generation


class EASemanticOperatorsMethod(BaseEALLMMethod):
    """Contexto evolutionary search with semantic mutation operators and (mu + lambda) selection."""

    config: EASemanticOperatorsConfig

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.rng = np.random.default_rng(self.config.random_seed)
        self.retired_hypotheses: list[Hypothesis] = []

    # ------------------------------------------------------------------ loop

    def run_generation(self) -> bool:
        self.generation += 1
        if self.config.parent_refresh:
            self._evaluate_candidates(self._generate_candidates())
            if self.game.is_solved():
                self._log_solved()
                return True

        self._select()
        self._mutate()
        if self.game.is_solved():
            self._log_solved()
            return True
        self._crossover()
        if self.game.is_solved():
            self._log_solved()
            return True
        self._deduplicate_hypotheses()
        return False

    def _local_search(self) -> None:  # never used by this method
        return None

    def _cap_active_hypotheses(self) -> None:  # the pool is exactly parents + offspring
        return None

    # ------------------------------------------------------------- selection

    @staticmethod
    def report_error(hypothesis: Hypothesis) -> float:
        """|predicted_closeness - 1{best rank <= 100}|; 1.0 when no closeness was parsed."""
        closeness = getattr(hypothesis, "predicted_closeness", None)
        if closeness is None:
            return 1.0
        realized = 1.0 if hypothesis.best_rank <= REPORT_SUCCESS_RANK else 0.0
        return abs(float(closeness) - realized)

    def _select(self) -> None:
        ranked = sorted(self.hypotheses, key=lambda hypothesis: hypothesis.best_rank)
        keep_count = min(self.config.survivors, len(ranked))
        if self.config.selection == "random":
            chosen = sorted(self.rng.choice(len(ranked), size=keep_count, replace=False).tolist())
            kept = [ranked[index] for index in chosen]
        elif self.config.selection == "report_rewarded":
            kept = sorted(ranked, key=lambda hypothesis: (self.report_error(hypothesis), hypothesis.best_rank))[:keep_count]
        else:
            kept = ranked[:keep_count]
        kept_ids = {id(hypothesis) for hypothesis in kept}
        discarded = [hypothesis for hypothesis in ranked if id(hypothesis) not in kept_ids]

        for hypothesis in kept:
            hypothesis.status = "active"
        for hypothesis in discarded:
            hypothesis.status = "retired"
        self.retired_hypotheses.extend(discarded)
        self.hypotheses = list(kept)

        self.logger.log(
            self.generation,
            "SELECT",
            {
                "kept": [hypothesis.category_name for hypothesis in kept],
                "discarded": [hypothesis.category_name for hypothesis in discarded],
                "kept_ids": [hypothesis.hypothesis_id for hypothesis in kept],
                "discarded_ids": [hypothesis.hypothesis_id for hypothesis in discarded],
                "elite": min(kept, key=lambda hypothesis: hypothesis.best_rank).category_name if kept else None,
                "max_active_hypotheses": self.config.survivors,
                "survivors": self.config.survivors,
                "pool_size": len(ranked),
                "selection": self.config.selection,
                "retired_total": len(self.retired_hypotheses),
                "best_word": self.best_word,
                "best_rank": self.best_rank,
                "total_guesses": self.game.total_guesses(),
            },
        )

    # -------------------------------------------------------------- variation

    def _mutate(self) -> None:
        parents = sorted(self._active_hypotheses(), key=lambda hypothesis: hypothesis.best_rank)
        children: list[dict[str, Any]] = []

        for parent in parents:
            for _ in range(self.config.offspring_per_parent):
                operator = sample_operator_uniform(self.rng)
                prompt_template = OPERATOR_PROMPTS[operator]
                inheritance_block, inheritance_meta = self._rationale_inheritance_for_parent(parent)
                prompt = self.llm_client.build_operator_mutation_prompt(
                    prompt_template,
                    parent,
                    self._known_words(),
                    self.invalid_guesses,
                    n=self.config.starter_words_per_category,
                    active_categories=[hypothesis.category_name for hypothesis in self._active_hypotheses()],
                    rationale_inheritance_block=inheritance_block,
                    self_report_block=self._self_report_block(),
                )
                assert_prompt_has_no_sigma_leak(prompt, parent.sigma, operator)
                category, raw = self._complete_proposal(prompt)
                if not isinstance(category, dict):
                    continue

                child = self._hypothesis_from_category(
                    category,
                    parent=parent.category_name,
                    origin=f"mutation_{operator.value}",
                    parent_id=parent.hypothesis_id,
                )
                self.hypotheses.append(child)
                if self.config.self_report:
                    proposed = _words_from_category(category)
                    self._attach_self_report(
                        child,
                        category,
                        raw,
                        prompt,
                        proposed[0] if proposed else None,
                        inheritance_meta=inheritance_meta if inheritance_block else None,
                    )
                children.append(child.to_dict())
                operator_details: dict[str, Any] = {
                    "parent_id": parent.hypothesis_id,
                    "child_id": child.hypothesis_id,
                    "parent_rank": parent.best_rank,
                    "child_hypothesis_name": child.category_name,
                    "sampled_op": operator.value,
                    "operator_mix": "fixed_uniform",
                    "method": "ea_semantic_operators",
                }
                if self.config.self_report:
                    operator_details["self_report"] = child.self_report_dict()
                self.logger.log(self.generation, "OPERATOR_SAMPLED", operator_details)

                for word in _words_from_category(category):
                    if word in self.invalid_guesses:
                        continue
                    self._guess_and_update(word, child)
                    if self.game.is_solved():
                        break
                if self.game.is_solved():
                    break
            if self.game.is_solved():
                break

        self.logger.log(
            self.generation,
            "MUTATE",
            {
                "method": "ea_semantic_operators",
                "children": children,
                "best_word": self.best_word,
                "best_rank": self.best_rank,
                "total_guesses": self.game.total_guesses(),
            },
        )

    def _crossover(self) -> None:
        for _ in range(self.config.crossover_children):
            active = sorted(self._active_hypotheses(), key=lambda hypothesis: hypothesis.best_rank)
            if len(active) < 2:
                return
            parent_a, parent_b = active[0], active[1]
            category, raw, rendered_prompt = self._crossover_request(parent_a, parent_b)
            child = self._hypothesis_from_category(
                category,
                parent=f"{parent_a.category_name}+{parent_b.category_name}",
                origin="crossover",
            )
            self.hypotheses.append(child)
            if self.config.self_report and isinstance(category, dict):
                proposed = _words_from_category(category)
                self._attach_self_report(child, category, raw, rendered_prompt, proposed[0] if proposed else None)
            for word in _words_from_category(category):
                if word in self.invalid_guesses:
                    continue
                self._guess_and_update(word, child)
                if self.game.is_solved():
                    break

            self.logger.log(
                self.generation,
                "CROSSOVER",
                {
                    "parents": [parent_a.category_name, parent_b.category_name],
                    "parent_ids": [parent_a.hypothesis_id, parent_b.hypothesis_id],
                    "parent_ranks": [parent_a.best_rank, parent_b.best_rank],
                    "child": child.to_dict(),
                    "best_word": self.best_word,
                    "best_rank": self.best_rank,
                    "total_guesses": self.game.total_guesses(),
                },
            )
            if self.game.is_solved():
                return
