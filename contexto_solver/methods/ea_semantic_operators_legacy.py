"""The submitted Contexto study's search, kept verbatim (``ea_semantic_operators_legacy``).

Use this only to reproduce the submitted runs. It is the class that produced
every EA run of the submitted paper (there called ``ea_semantic_operators_legacy`` with
``sigma_mode=frozen_uniform``):

* four semantic mutation operators drawn with fixed uniform probability;
* survivor selection ``tophalf``: keep the best min(half of the pool, 5) plus
  the elite; culled individuals stay in the pool as dormant members, so the pool
  ranked at the next selection is every individual created so far (dormant
  members can return only when their frozen rank beats an active one);
* transient active-set cap of 15 between selections;
* parents propose new words every generation (fitness keeps improving);
* one mutation child per surviving parent plus one crossover child;
* ``random`` selection is the submitted control.

New experiments use :mod:`ea_semantic_operators` instead.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np

from ..hypothesis import Hypothesis
from ..operators import OPERATOR_PROMPTS, assert_prompt_has_no_sigma_leak, initial_sigma, sample_operator
from .ea_core import BaseEALLMMethod, EALLMConfig, _words_from_category


LEGACY_SELECTION_CHOICES = ("tophalf", "random")


@dataclass
class EASemanticOperatorsLegacyConfig(EALLMConfig):
    #: transient active-set cap between selections (SELF_ADAPTIVE_MU in the study)
    active_cap: int = 15
    random_seed: int | None = None
    selection_mode: str = "tophalf"

    def __post_init__(self) -> None:
        if self.selection_mode not in LEGACY_SELECTION_CHOICES:
            raise ValueError(f"selection_mode={self.selection_mode!r} is not one of {LEGACY_SELECTION_CHOICES}")

    # names used by the original class body
    @property
    def mu(self) -> int:
        return self.active_cap

    @property
    def disable_local_search(self) -> bool:
        return True


class EASemanticOperatorsLegacyMethod(BaseEALLMMethod):
    config: EASemanticOperatorsLegacyConfig

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.rng = np.random.default_rng(self.config.random_seed)
        self._local_search_disabled_logged = False

    def _after_initialize(self) -> None:
        self._log_sigma_trajectory()

    def _mode_sigma(self, base_sigma: np.ndarray) -> np.ndarray:
        # frozen_uniform: every child carries the fixed uniform operator mix
        return initial_sigma()

    def _select(self) -> None:
        """Survivor selection. Three policies, chosen by ``config.selection_mode``:

        ``tophalf`` (default; the submitted Contexto study): defers to the base
        rank cull, byte-identical to prior behavior. Culled individuals stay in
        ``self.hypotheses`` as ``dormant`` members, so the pool that later
        truncations rank over is the cumulative set of every individual created
        so far. A dormant member can return to ``active`` through
        ``_deduplicate_hypotheses`` (status inheritance on merge, or a rank
        vacancy after a merge deletes an active member).

        ``random`` (selection response control): keeps the same survivor count but draws
        survivors uniformly at random with the run's RNG; no elite guarantee
        (that would reintroduce selection on fitness).
        """
        if self.config.selection_mode != "random":
            super()._select()
            return

        ranked = sorted(self.hypotheses, key=lambda hypothesis: hypothesis.best_rank)
        keep_count = min(max(1, len(ranked) // 2), self.config.max_active_hypotheses)
        chosen = sorted(self.rng.choice(len(ranked), size=keep_count, replace=False).tolist())
        kept_list = [ranked[index] for index in chosen]
        kept_ids = set(id(hypothesis) for hypothesis in kept_list)
        for hypothesis in self.hypotheses:
            hypothesis.status = "active" if id(hypothesis) in kept_ids else "dormant"

        self.logger.log(
            self.generation,
            "SELECT",
            {
                "kept": [hypothesis.category_name for hypothesis in kept_list],
                "discarded": [
                    hypothesis.category_name for hypothesis in ranked if id(hypothesis) not in kept_ids
                ],
                "elite": kept_list[0].category_name if kept_list else None,
                "max_active_hypotheses": self.config.max_active_hypotheses,
                "selection_mode": "random",
                "best_word": self.best_word,
                "best_rank": self.best_rank,
                "total_guesses": self.game.total_guesses(),
            },
        )

    def _mutate(self) -> None:
        parents = sorted(self._active_hypotheses(), key=lambda hypothesis: hypothesis.best_rank)[: self.config.mu]
        children: list[dict[str, Any]] = []

        for parent in parents:
            operator = sample_operator(parent.sigma, self.rng)
            prompt_template = OPERATOR_PROMPTS[operator]
            parent_sigma = parent.sigma.copy()
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
            assert_prompt_has_no_sigma_leak(prompt, parent_sigma, operator)
            category, raw = self._complete_proposal(prompt)
            if not isinstance(category, dict):
                continue

            child_sigma = self._mode_sigma(parent_sigma)
            child = self._hypothesis_from_category(
                category,
                parent=parent.category_name,
                origin=f"self_adaptive_{operator.value}",
                parent_id=parent.hypothesis_id,
                sigma=child_sigma,
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
                "sigma_snapshot": [float(value) for value in parent_sigma],
                "child_sigma": [float(value) for value in child.sigma],
                "child_hypothesis_name": child.category_name,
                "sampled_op": operator.value,
                "method": "self_adaptive",  # kept verbatim: the value written by the submitted study
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

        self.logger.log(
            self.generation,
            "MUTATE",
            {
                "method": "self_adaptive",
                "children": children,
                "best_word": self.best_word,
                "best_rank": self.best_rank,
                "total_guesses": self.game.total_guesses(),
            },
        )

    def _crossover(self) -> None:
        active = sorted(self._active_hypotheses(), key=lambda hypothesis: hypothesis.best_rank)
        if len(active) < 2:
            return

        parent_a, parent_b = active[0], active[1]
        category, raw, rendered_prompt = self._crossover_request(parent_a, parent_b)
        blended_sigma = 0.5 * (parent_a.sigma + parent_b.sigma)
        child_sigma = self._mode_sigma(blended_sigma)
        child = self._hypothesis_from_category(
            category,
            parent=f"{parent_a.category_name}+{parent_b.category_name}",
            origin="crossover",
            sigma=child_sigma,
        )
        self.hypotheses.append(child)
        if self.config.self_report and isinstance(category, dict):
            proposed = _words_from_category(category)
            self._attach_self_report(
                child, category, raw, rendered_prompt, proposed[0] if proposed else None
            )
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
                "parent_a_sigma": [float(value) for value in parent_a.sigma],
                "parent_b_sigma": [float(value) for value in parent_b.sigma],
                "child_sigma_pre_perturbation": [float(value) for value in blended_sigma],
                "child": child.to_dict(),
                "best_word": self.best_word,
                "best_rank": self.best_rank,
                "total_guesses": self.game.total_guesses(),
            },
        )

    def _local_search(self) -> None:
        if not self.config.disable_local_search:
            super()._local_search()
            return

        best_word, best_rank = self.game.best_so_far()
        if (
            self._local_search_disabled_logged
            or best_word is None
            or best_rank is None
            or best_rank >= self.config.local_search_rank_threshold
        ):
            return

        self._local_search_disabled_logged = True
        self.logger.log(
            self.generation,
            "LOCAL_SEARCH_DISABLED",
            {
                "center_word": best_word,
                "center_rank": best_rank,
                "threshold": self.config.local_search_rank_threshold,
                "reason": "self_adaptive_disable_local_search",
            },
        )

    def _after_generation_update(self) -> bool:
        self._log_sigma_trajectory()
        return False

    def _cap_active_hypotheses(self) -> None:
        active = sorted(self._active_hypotheses(), key=lambda hypothesis: hypothesis.best_rank)
        allowed = set(id(hypothesis) for hypothesis in active[: self.config.mu])
        for hypothesis in active:
            if id(hypothesis) not in allowed:
                hypothesis.status = "dormant"

    def _log_sigma_trajectory(self) -> None:
        active = self._active_hypotheses()
        if not active:
            return
        mean_sigma = np.mean(np.vstack([hypothesis.sigma for hypothesis in active]), axis=0)
        self.logger.log_sigma_trajectory(
            self.generation,
            mean_sigma=[float(value) for value in mean_sigma],
            population_size=len(active),
        )


