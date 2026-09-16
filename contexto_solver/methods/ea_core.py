"""Shared EA+LLM solver core."""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..hypothesis import Hypothesis
from ..llm_client import LLMClient
from ..logger import Logger
from ..self_report import (
    apply_self_report_to_hypothesis,
    rationale_inheritance_block,
    resolve_self_report,
    self_report_block,
)
from .base import Game


@dataclass
class EALLMConfig:
    max_generations: int
    candidates_per_hypothesis: int
    initial_categories: int
    starter_words_per_category: int
    mutations_per_generation: int
    max_active_hypotheses: int
    trace_dir: str
    run_label: str
    llm_workers: int = 4
    local_search_rank_threshold: int = 100
    # calibration operator self-report instrumentation. Only read by the operator-based
    # methods (ea_semantic_operators_legacy, ea_llm_map_elites); logged-only, never used
    # in selection, fitness, or sigma adaptation.
    self_report: bool = False
    # calibration parent-rationale inheritance (logged-only). When on, s/m/ml/l mutations
    # and ea_llm specialize append the parent's prior rationale to the prompt.
    rationale_inheritance: bool = False


class BaseEALLMMethod:
    def __init__(self, game: Game, llm_client: LLMClient, logger: Logger, config: EALLMConfig) -> None:
        self.game = game
        self.llm_client = llm_client
        self.logger = logger
        self.config = config
        self.hypotheses: list[Hypothesis] = []
        self.invalid_guesses: set[str] = set()
        self.generation = 0

    # --- calibration self-report instrumentation (logged-only; shared by every EA mode) ---

    def _self_report_block(self) -> str:
        """The appended self-report request block, or "" when the flag is off."""
        return self_report_block(self.config.self_report)

    def _rationale_inheritance_for_parent(self, parent: Hypothesis) -> tuple[str, dict[str, Any]]:
        """Parent-rationale suffix for eligible operators, or ("", {})."""
        if not self.config.rationale_inheritance:
            return "", {}
        return rationale_inheritance_block(parent.rationale)

    def _self_report_context(self) -> str:
        """Words the operator saw (guessed + invalid), for the follow-up prompt."""
        return json.dumps(sorted(self._known_words()))

    def _attach_self_report(
        self,
        child: Hypothesis,
        source: Any,
        raw: str | None,
        rendered_prompt: str | None,
        proposed_word: str | None,
        inheritance_meta: dict[str, Any] | None = None,
    ) -> None:
        """Resolve and attach the logged-only self-report via the shared layer."""
        record = resolve_self_report(
            self.llm_client,
            source=source,
            raw=raw,
            context=self._self_report_context(),
            proposed_word=proposed_word,
            rendered_prompt=rendered_prompt,
        )
        if inheritance_meta:
            if inheritance_meta.get("hash"):
                record["injected_rationale_hash"] = inheritance_meta["hash"]
            record["rationale_truncated"] = bool(inheritance_meta.get("truncated"))
        apply_self_report_to_hypothesis(child, record)

    def _complete_proposal(self, prompt: str) -> tuple[Any, str | None]:
        """Issue an operator/mutation proposal call, capturing raw text only when
        the self-report flag is on.

        Single routing point for the flag-gated raw capture so every operator
        path shares identical request behavior. With the flag off this is exactly
        ``complete_json_prompt`` (no raw), keeping behavior byte-identical.
        """
        if self.config.self_report:
            return self.llm_client.complete_json_prompt_with_raw(prompt)
        return self.llm_client.complete_json_prompt(prompt), None

    def _crossover_request(
        self, parent_a: Hypothesis, parent_b: Hypothesis
    ) -> tuple[Any, str | None, str | None]:
        """Issue the crossover proposal call, capturing the rendered prompt and raw
        text only when the self-report flag is on.

        Single routing point shared by every EA mode's crossover. With the flag
        off this is exactly one ``crossover`` call (no prompt build, no raw),
        keeping behavior byte-identical.
        """
        block = self._self_report_block()
        if self.config.self_report:
            rendered_prompt = self.llm_client.build_crossover_prompt(
                parent_a.category_name,
                parent_b.category_name,
                parent_a.words_tried,
                parent_b.words_tried,
                block,
            )
            category, raw = self.llm_client.crossover(
                parent_a.category_name,
                parent_b.category_name,
                parent_a.words_tried,
                parent_b.words_tried,
                self_report_block=block,
                return_raw=True,
            )
            return category, raw, rendered_prompt
        category = self.llm_client.crossover(
            parent_a.category_name,
            parent_b.category_name,
            parent_a.words_tried,
            parent_b.words_tried,
        )
        return category, None, None

    def initialize(self) -> bool:
        categories = self.llm_client.generate_initial_categories(
            n=self.config.initial_categories,
            starter_words=self.config.starter_words_per_category,
        )
        for category in categories:
            hypothesis = self._hypothesis_from_category(category, origin="init")
            self.hypotheses.append(hypothesis)
            for word in _words_from_category(category):
                self._guess_and_update(word, hypothesis)
                if self.game.is_solved():
                    self._log_solved()
                    return True

        if not self.game.is_solved() and not self.hypotheses:
            raise RuntimeError(
                "EA+LLM initialization produced an empty hypothesis population: "
                f"none of the {len(categories)} initial categories were usable. "
                "Refusing to run empty generations."
            )

        self.logger.log(
            self.generation,
            "INIT",
            {
                "hypotheses": [hypothesis.to_dict() for hypothesis in self.hypotheses],
                "best_word": self.best_word,
                "best_rank": self.best_rank,
                "total_guesses": self.game.total_guesses(),
            },
        )
        return self.game.is_solved()

    def run_generation(self) -> bool:
        self.generation += 1
        self._cap_active_hypotheses()
        self._evaluate_candidates(self._generate_candidates())
        if self.game.is_solved():
            self._log_solved()
            return True
        self._local_search()
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
        self._cap_active_hypotheses()

        if self._after_generation_update():
            return True
        return False

    def _local_search(self) -> None:
        """Local search around the best word; disabled in every migrated method."""
        return None

    def _mutate(self) -> None:
        raise NotImplementedError("subclasses define their mutation step")

    def _crossover(self) -> None:
        raise NotImplementedError("subclasses define their crossover step")

    def _after_generation_update(self) -> bool:
        """Run method-specific logic after normal EA generation updates.

        Hooks may mutate shared solver state (add hypotheses, log events,
        update internal trackers). The return value signals only whether
        the solve loop should terminate.

        Returns True only when the hook solves the game and the loop should
        stop immediately. Returns False to continue normally.
        """
        return False

    def solve(self, max_generations: int | None = None) -> dict[str, Any]:
        generation_limit = max_generations or self.config.max_generations
        solved = self.initialize()
        self._after_initialize()
        self._print_generation_summary()
        while not solved and self.generation < generation_limit:
            solved = self.run_generation()
            self._print_generation_summary()

        if not solved:
            self.logger.log(
                self.generation,
                "FAILED",
                {
                    "best_word": self.best_word,
                    "best_rank": self.best_rank,
                    "total_guesses": self.game.total_guesses(),
                },
            )

        trace_path = self._save_trace()
        return {
            "solved": solved,
            "answer": self.best_word if solved else None,
            "best_word": self.best_word,
            "best_rank": self.best_rank,
            "total_guesses": self.game.total_guesses(),
            "generations": self.generation,
            "trace_path": str(trace_path),
        }

    def _after_initialize(self) -> None:
        """Run method-specific setup after initial hypotheses are evaluated."""

    def _generate_candidates(self) -> list[tuple[Hypothesis, str]]:
        candidates: list[tuple[Hypothesis, str]] = []
        planned_words = self._known_words()
        planned_word_families = _word_families(planned_words)
        active_hypotheses = self._active_hypotheses()
        max_workers = min(max(1, self.config.llm_workers), max(1, len(active_hypotheses)))

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                (
                    hypothesis,
                    executor.submit(
                        self.llm_client.propose_words,
                        hypothesis,
                        hypothesis.words_tried,
                        self.invalid_guesses,
                        self.config.candidates_per_hypothesis,
                        self.game.guesses if hasattr(self.game, "guesses") else None,
                    ),
                )
                for hypothesis in active_hypotheses
            ]
            proposed_words = []
            for hypothesis, future in futures:
                try:
                    proposed_words.append((hypothesis, future.result()))
                except Exception as exc:
                    raise

        raw_count = 0
        rejected_invalid = 0
        rejected_duplicate = 0
        for hypothesis, words in proposed_words:
            for word in words:
                raw_count += 1
                cleaned_word = _clean_word(word)
                if not cleaned_word:
                    rejected_invalid += 1
                    continue
                if cleaned_word in planned_words or _word_family(cleaned_word) in planned_word_families:
                    rejected_duplicate += 1
                    continue
                planned_words.add(cleaned_word)
                planned_word_families.add(_word_family(cleaned_word))
                candidates.append((hypothesis, cleaned_word))

        self.logger.log(
            self.generation,
            "CANDIDATES",
            {"count": len(candidates), "candidates": [{"hypothesis": h.category_name, "word": w} for h, w in candidates]},
        )
        return candidates

    def _evaluate_candidates(self, candidates: list[tuple[Hypothesis, str]]) -> None:
        for hypothesis, word in candidates:
            self._guess_and_update(word, hypothesis)
            if self.game.is_solved():
                return

    def _guess_and_update(self, word: str, hypothesis: Hypothesis) -> int:
        rank = self.game.guess(word)
        if rank == -1:
            self.invalid_guesses.add(word)
            self.logger.log(self.generation, "SKIP_INVALID_GUESS", {"word": word, "hypothesis": hypothesis.category_name})
            return rank

        hypothesis.update(word, rank)
        best_word, best_rank = self.game.best_so_far()
        self.logger.log(
            self.generation,
            "GUESS",
            {
                "word": word,
                "rank": rank,
                "hypothesis": hypothesis.category_name,
                "best_word": best_word,
                "best_rank": best_rank,
                "total_guesses": self.game.total_guesses(),
            },
        )
        return rank

    def _select(self) -> None:
        ranked = sorted(self.hypotheses, key=lambda hypothesis: hypothesis.best_rank)
        keep_count = min(max(1, len(ranked) // 2), self.config.max_active_hypotheses)
        kept = set(id(hypothesis) for hypothesis in ranked[:keep_count])
        elite = ranked[0] if ranked else None
        if elite is not None:
            kept.add(id(elite))
        for hypothesis in self.hypotheses:
            hypothesis.status = "active" if id(hypothesis) in kept else "dormant"

        self.logger.log(
            self.generation,
            "SELECT",
            {
                "kept": [hypothesis.category_name for hypothesis in ranked[:keep_count]],
                "discarded": [hypothesis.category_name for hypothesis in ranked[keep_count:]],
                "elite": elite.category_name if elite else None,
                "max_active_hypotheses": self.config.max_active_hypotheses,
                "best_word": self.best_word,
                "best_rank": self.best_rank,
                "total_guesses": self.game.total_guesses(),
            },
        )


    def _deduplicate_hypotheses(self) -> None:
        kept: list[Hypothesis] = []
        merged_events: list[dict[str, Any]] = []

        for hypothesis in sorted(self.hypotheses, key=lambda item: item.best_rank):
            duplicate = next((existing for existing in kept if _are_duplicate_hypotheses(existing, hypothesis)), None)
            if duplicate is None:
                kept.append(hypothesis)
                continue

            survivor, discarded = (
                (duplicate, hypothesis)
                if duplicate.best_rank <= hypothesis.best_rank
                else (hypothesis, duplicate)
            )
            survivor.words_tried.update(discarded.words_tried)
            survivor.status = "active" if survivor.status == "active" or discarded.status == "active" else "dormant"
            if survivor is hypothesis:
                kept.remove(duplicate)
                kept.append(survivor)

            merged_events.append(
                {
                    "survivor": survivor.category_name,
                    "discarded": discarded.category_name,
                    "survivor_best_rank": survivor.best_rank,
                    "discarded_best_rank": discarded.best_rank,
                }
            )

        self.hypotheses = kept
        if merged_events:
            self._cap_active_hypotheses()
            self.logger.log(
                self.generation,
                "DEDUPLICATE",
                {
                    "merged": merged_events,
                    "remaining_hypotheses": len(self.hypotheses),
                    "active_hypotheses": len(self._active_hypotheses()),
                    "best_word": self.best_word,
                    "best_rank": self.best_rank,
                    "total_guesses": self.game.total_guesses(),
                },
            )

    def _cap_active_hypotheses(self) -> None:
        active = sorted(self._active_hypotheses(), key=lambda hypothesis: hypothesis.best_rank)
        allowed = set(id(hypothesis) for hypothesis in active[: self.config.max_active_hypotheses])
        for hypothesis in active:
            if id(hypothesis) not in allowed:
                hypothesis.status = "dormant"



    def _new_clean_words(self, words: list[str]) -> list[str]:
        known_words = self._known_words()
        known_word_families = _word_families(known_words)
        accepted: list[str] = []
        for word in words:
            cleaned_word = _clean_word(word)
            if not cleaned_word or cleaned_word in known_words or _word_family(cleaned_word) in known_word_families:
                continue
            known_words.add(cleaned_word)
            known_word_families.add(_word_family(cleaned_word))
            accepted.append(cleaned_word)
        return accepted

    def _known_words(self) -> set[str]:
        known = set(self.invalid_guesses)
        if hasattr(self.game, "guesses"):
            known.update(self.game.guesses)
        return known

    def _best_hypothesis(self) -> Hypothesis | None:
        if not self.hypotheses:
            return None
        return min(self.hypotheses, key=lambda hypothesis: hypothesis.best_rank)

    def _active_hypotheses(self) -> list[Hypothesis]:
        return [hypothesis for hypothesis in self.hypotheses if hypothesis.status == "active"]

    def _hypothesis_from_category(
        self,
        category: dict[str, Any],
        parent: str | None = None,
        origin: str = "init",
        parent_id: str | None = None,
        sigma: Any = None,
    ) -> Hypothesis:
        kwargs = {"sigma": sigma} if sigma is not None else {}
        return Hypothesis(
            category_name=str(category.get("name", "unnamed category")),
            description=str(category.get("description", "")),
            parent=parent,
            parent_id=parent_id,
            origin=origin,
            **kwargs,
        )

    def _log_solved(self) -> None:
        self.logger.log(
            self.generation,
            "SOLVED",
            {
                "answer": self.best_word,
                "rank": self.best_rank,
                "total_guesses": self.game.total_guesses(),
            },
        )

    def _save_trace(self) -> Path:
        self.logger.log_network_metrics(self.generation, self.game)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.logger.save(Path(self.config.trace_dir) / f"{self.config.run_label}_{timestamp}.json")

    def _print_generation_summary(self) -> None:
        print(f"Generation {self.generation}: best word={self.best_word}, best rank={self.best_rank}")

    @property
    def best_word(self) -> str | None:
        return self.game.best_so_far()[0]

    @property
    def best_rank(self) -> int | None:
        return self.game.best_so_far()[1]


def _words_from_category(category: dict[str, Any]) -> list[str]:
    words = category.get("words", [])
    if not isinstance(words, list):
        return []
    return [cleaned for word in words if (cleaned := _clean_word(word))]


def _coerce_word_list(words: Any) -> list[str]:
    if not isinstance(words, list):
        return []
    return [str(word) for word in words]


def _clean_word(word: Any) -> str:
    cleaned_word = str(word).lower().strip()
    if not re.fullmatch(r"[a-z]+", cleaned_word):
        return ""
    return cleaned_word


def _word_families(words: set[str]) -> set[str]:
    return {_word_family(word) for word in words}


def _word_family(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return f"{word[:-3]}y"
    if len(word) > 3 and word.endswith("es") and word[-3] in {"s", "x", "z"}:
        return word[:-2]
    if len(word) > 4 and word.endswith("ches"):
        return word[:-2]
    if len(word) > 4 and word.endswith("shes"):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _are_duplicate_hypotheses(a: Hypothesis, b: Hypothesis) -> bool:
    shared_words = set(a.words_tried) & set(b.words_tried)
    if len(shared_words) >= 2:
        return True

    a_name = a.category_name.lower().strip()
    b_name = b.category_name.lower().strip()
    if not a_name or not b_name:
        return False
    if a_name in b_name or b_name in a_name:
        return True

    a_words = set(a_name.split())
    b_words = set(b_name.split())
    if not a_words or not b_words:
        return False
    jaccard = len(a_words & b_words) / len(a_words | b_words)
    if jaccard > 0.6:
        return True
    return len(a_words ^ b_words) <= 1





