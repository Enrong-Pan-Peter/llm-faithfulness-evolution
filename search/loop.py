"""The shared (mu + lambda) search over one task.

Generation 0 asks the model for ``initial_population`` fresh candidates. Each
later generation selects ``survivors`` from the current pool (parents and
offspring together), retires the rest for good, and gives every survivor
``offspring_per_parent`` mutation children, each from an operator drawn
uniformly from the environment's S/M/ML/L ladder. Fitness is fixed at birth.
The run stops after the first generation in which a candidate meets the
environment's success event (generation 0 and every later generation are
always completed, so each run yields at least 15 graded, self-reported
candidates), or after ``max_generations``. With ``stop_at_success`` off the
search runs every generation regardless; ``SOLVED`` then reports the first
generation with a success.

Every distinct candidate text is graded once: a repeat proposal reuses the
stored grade and records ``duplicate_of``, but stays an individual of its own
(its self-report is its own). Nothing is excluded in the prompt.

Trace events (same shapes as the Contexto traces where the fields overlap):
``RUN_CONFIG``, ``INITIAL_CANDIDATE`` (one per generation-0 candidate),
``SELECT`` (``kept`` / ``discarded`` ids, ``elite``, ``survivors``,
``pool_size``, ``selection``, ``retired_total``), ``OPERATOR_SAMPLED`` (one per
mutation child: ``parent_id``, ``child_id``, ``sampled_op``, ``operator_mix``,
``method``, ``self_report``, plus ``outcome``, ``rationale``, ``prompt`` and
``raw_response`` so the rationale intervention can re-run the exact prompt),
``MODEL_CALL_FAILED``, and ``SOLVED`` / ``FAILED``.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import numpy as np

from contexto_solver import config as app_config
from contexto_solver.logger import Logger
from contexto_solver.self_report import hash_injection_text, rationale_inheritance_block

from .environment import SearchEnvironment, candidate_summary
from .individual import Individual
from .reports import parse_report, report_error
from .settings import SearchSettings

TRACE_FORMAT_VERSION = app_config.TRACE_FORMAT_VERSION
WORST_FITNESS = float("inf")


@dataclass
class SearchResult:
    solved: bool
    first_success_generation: int | None
    generations: int
    best: Individual | None
    n_candidates: int
    model_calls: int
    model_failures: int
    trace: list[dict[str, Any]]


class EvolutionarySearch:
    """One run of the shared loop on one environment/task."""

    def __init__(
        self,
        environment: SearchEnvironment,
        model: Any,
        settings: SearchSettings,
        *,
        run_label: str = "",
        run_index: int = 0,
        logger: Logger | None = None,
    ) -> None:
        self.environment = environment
        self.model = model
        self.settings = settings
        self.run_label = run_label
        self.run_index = run_index
        self.logger = logger or Logger()
        self.rng = np.random.default_rng(settings.random_seed)
        self.generation = 0
        self.pool: list[Individual] = []
        self.retired: list[Individual] = []
        self.everyone: list[Individual] = []
        self.grade_cache: dict[str, tuple[Any, dict[str, Any], str]] = {}
        self._next_number = 0

    # ------------------------------------------------------------------ run

    def run(self) -> SearchResult:
        self._log_run_config()
        first_success: int | None = 0 if self._initial_population() else None
        while self.generation < self.settings.max_generations and not (
            first_success is not None and self.settings.stop_at_success
        ):
            self.generation += 1
            self._select()
            if self._mutate() and first_success is None:
                first_success = self.generation
        solved = first_success is not None
        best = self.best_individual()
        summary = candidate_summary(self.everyone)
        summary.update(
            {
                "generations": self.generation,
                "first_success_generation": first_success,
                "stop_at_success": self.settings.stop_at_success,
                "best": best.summary() if best else None,
                "model_calls": self.model.calls,
                "model_failures": self.model.failures,
                "pool_size": len(self.pool),
                "retired_total": len(self.retired),
            }
        )
        self.logger.log(self.generation, "SOLVED" if solved else "FAILED", summary)
        return SearchResult(
            solved=solved,
            first_success_generation=first_success,
            generations=self.generation,
            best=best,
            n_candidates=len(self.everyone),
            model_calls=self.model.calls,
            model_failures=self.model.failures,
            trace=self.logger.trace,
        )

    def best_individual(self) -> Individual | None:
        graded = [individual for individual in self.everyone if math.isfinite(individual.fitness)]
        if not graded:
            return None
        return min(graded, key=lambda individual: (not individual.success, individual.fitness, individual.generation))

    # ------------------------------------------------------------ run config

    def _log_run_config(self) -> None:
        settings = self.settings
        environment = self.environment
        self.logger.log(
            0,
            "RUN_CONFIG",
            {
                "environment": environment.name,
                "method": environment.method,
                "solver": "search.loop",
                "task_id": environment.task_id,
                "task": environment.task_record(),
                "run_label": self.run_label,
                "run_index": self.run_index,
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "llm_provider": getattr(self.model, "provider", None),
                "llm_model": getattr(self.model, "model", None),
                "serving": self.model.serving_record(),
                "prompt_fingerprint": environment.prompt_fingerprint(TRACE_FORMAT_VERSION),
                "trace_format_version": TRACE_FORMAT_VERSION,
                "self_report": settings.self_report,
                "rationale_channel": settings.rationale_channel,
                "rationale_inheritance": settings.rationale_channel == "inherited",
                "selection": settings.selection,
                "initial_population": settings.initial_population,
                "survivors": settings.survivors,
                "max_active_hypotheses": settings.survivors,
                "offspring_per_parent": settings.offspring_per_parent,
                "offspring_per_generation": settings.offspring_per_generation,
                "crossover_children": 0,
                "pool_is_constant": settings.pool_is_constant,
                "operator_mix": settings.operator_mix,
                "operators": list(environment.operators),
                "max_generations": settings.max_generations,
                "random_seed": settings.random_seed,
                "settings": settings.to_dict(),
            },
        )

    # ------------------------------------------------------- generation zero

    def _initial_population(self) -> bool:
        """Propose the whole initial population; True when any candidate succeeded."""
        prompt = self.environment.initial_prompt(self_report=self.settings.self_report)
        self.environment.check_prompt(prompt)
        succeeded = False
        for _ in range(self.settings.initial_population):
            parsed, raw, error = self.model.complete_json(prompt)
            child = self._make_individual(
                parsed, raw, error, prompt, origin="initial", operator=None, parent=None,
                rationale={"channel": "none", "text": "", "hash": None}, prospective=None,
            )
            self.logger.log(0, "INITIAL_CANDIDATE", {**child.event_details(), "method": self.environment.method})
            succeeded = succeeded or child.success
        return succeeded

    # -------------------------------------------------------------- selection

    def _selection_key(self, individual: Individual) -> tuple[float, ...]:
        if self.settings.selection == "report_rewarded":
            error = report_error(individual.self_report, individual.success)
            return (1.0 if error is None else error, individual.fitness)
        return (individual.fitness,)

    def _select(self) -> None:
        pool = list(self.pool)  # insertion order = birth order; sorts below are stable
        keep_count = min(self.settings.survivors, len(pool))
        if self.settings.selection == "random":
            chosen = sorted(self.rng.choice(len(pool), size=keep_count, replace=False).tolist()) if pool else []
            kept = [pool[index] for index in chosen]
        else:
            kept = sorted(pool, key=self._selection_key)[:keep_count]
        kept_ids = {individual.individual_id for individual in kept}
        discarded = [individual for individual in pool if individual.individual_id not in kept_ids]
        for individual in kept:
            individual.status = "active"
        for individual in discarded:
            individual.status = "retired"
        self.retired.extend(discarded)
        self.pool = [individual for individual in pool if individual.individual_id in kept_ids]
        elite = min(kept, key=lambda individual: individual.fitness) if kept else None
        self.logger.log(
            self.generation,
            "SELECT",
            {
                "kept": [individual.individual_id for individual in kept],
                "discarded": [individual.individual_id for individual in discarded],
                "kept_ids": [individual.individual_id for individual in kept],
                "discarded_ids": [individual.individual_id for individual in discarded],
                "kept_fitness": [_json_number(individual.fitness) for individual in kept],
                "discarded_fitness": [_json_number(individual.fitness) for individual in discarded],
                "elite": elite.individual_id if elite else None,
                "max_active_hypotheses": self.settings.survivors,
                "survivors": self.settings.survivors,
                "pool_size": len(pool),
                "selection": self.settings.selection,
                "retired_total": len(self.retired),
                "best_fitness": _json_number(elite.fitness) if elite else None,
                "best_progress": elite.progress if elite else None,
            },
        )

    # -------------------------------------------------------------- variation

    def _sample_operator(self) -> str:
        operators = self.environment.operators
        return operators[int(self.rng.integers(len(operators)))]

    def _rationale_slot(self, parent: Individual) -> tuple[str, dict[str, Any], dict[str, Any] | None]:
        """The text for the slot, its record, and the prospective call record (if any)."""
        channel = self.settings.rationale_channel
        if channel == "inherited":
            parent_rationale = (parent.self_report or {}).get("rationale")
            block, meta = rationale_inheritance_block(parent_rationale)
            record = {
                "channel": "inherited",
                "text": block,
                "hash": meta.get("hash"),
                "truncated": bool(meta.get("truncated")),
                "source_id": parent.individual_id,
            }
            return block, record, None
        if channel == "corrective_hint":
            block = self.environment.corrective_hint_block(parent)
            return block, {"channel": "corrective_hint", "text": block, "hash": _hash_or_none(block)}, None
        if channel == "prospective":
            prompt = self.environment.prospective_prompt(parent)
            self.environment.check_prompt(prompt)
            parsed, raw, error = self.model.complete_json(prompt)
            text = self.environment.prospective_text(parsed) if parsed is not None else ""
            block = self.environment.prospective_block(text) if text else ""
            prospective = {"prompt": prompt, "raw_response": raw, "text": text, "error": error}
            if error:
                self.logger.log(self.generation, "MODEL_CALL_FAILED", {"stage": "prospective", "error": error})
            record = {"channel": "prospective", "text": block, "hash": _hash_or_none(block), "source_id": parent.individual_id}
            return block, record, prospective
        return "", {"channel": "none", "text": "", "hash": None}, None

    def _mutate(self) -> bool:
        """Give every survivor its children (the whole generation); True when any child succeeded."""
        succeeded = False
        parents = sorted(self.pool, key=lambda individual: individual.fitness)
        for parent in parents:
            for _ in range(self.settings.offspring_per_parent):
                operator = self._sample_operator()
                block, rationale, prospective = self._rationale_slot(parent)
                prompt = self.environment.operator_prompt(operator, parent, block, self_report=self.settings.self_report)
                # The slot text is written by the model (inherited reason, prospective strategy),
                # so it cannot leak solver-side facts; the guard checks everything around it.
                self.environment.check_prompt(prompt.replace(block, "", 1) if block else prompt)
                parsed, raw, error = self.model.complete_json(prompt)
                child = self._make_individual(
                    parsed, raw, error, prompt, origin=f"mutation_{operator}", operator=operator, parent=parent,
                    rationale=rationale, prospective=prospective,
                )
                details = child.event_details()
                details.update({"operator_mix": self.settings.operator_mix, "method": self.environment.method})
                self.logger.log(self.generation, "OPERATOR_SAMPLED", details)
                succeeded = succeeded or child.success
        return succeeded

    # --------------------------------------------------------- individuals

    def _new_id(self) -> str:
        self._next_number += 1
        return f"g{self.generation:02d}-{self._next_number:04d}"

    def _make_individual(
        self,
        parsed: Any,
        raw: str | None,
        error: str | None,
        prompt: str,
        *,
        origin: str,
        operator: str | None,
        parent: Individual | None,
        rationale: dict[str, Any],
        prospective: dict[str, Any] | None,
    ) -> Individual:
        individual_id = self._new_id()
        if error:
            self.logger.log(self.generation, "MODEL_CALL_FAILED", {"stage": origin, "child_id": individual_id, "error": error})
        parsed_candidate = self.environment.parse_candidate(parsed) if parsed is not None else None
        report = parse_report(parsed, self.environment.buckets, raw) if parsed is not None else parse_report(None, self.environment.buckets, raw)
        if rationale.get("channel") == "inherited" and rationale.get("hash"):
            report["injected_rationale_hash"] = rationale["hash"]
            report["rationale_truncated"] = bool(rationale.get("truncated"))

        if parsed_candidate is None:
            individual = Individual(
                individual_id=individual_id,
                generation=self.generation,
                origin=origin,
                operator=operator,
                parent_id=parent.individual_id if parent else None,
                parent_fitness=_json_number(parent.fitness) if parent else None,
                parent_progress=parent.progress if parent else None,
                candidate=None,
                candidate_text="",
                candidate_key="",
                fitness=WORST_FITNESS,
                outcome={"valid": False, "success": False, "score": None, "progress": 0.0, "bucket": None, "details": {"parse_failed": True}},
                evaluation=None,
                self_report=report,
                rationale=rationale,
                prompt=prompt,
                raw_response=raw,
                parse_ok=False,
                entered_pool=False,
                prospective=prospective,
            )
            self.everyone.append(individual)
            return individual

        candidate, text = parsed_candidate
        key = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
        duplicate_of: str | None = None
        if key in self.grade_cache:
            evaluation, outcome, duplicate_of = self.grade_cache[key]
        else:
            evaluation = self.environment.evaluate(candidate)
            outcome = self.environment.outcome(evaluation)
            self.grade_cache[key] = (evaluation, outcome, individual_id)
        score = outcome.get("score")
        fitness = float(score) if isinstance(score, (int, float)) and math.isfinite(float(score)) else WORST_FITNESS
        individual = Individual(
            individual_id=individual_id,
            generation=self.generation,
            origin=origin,
            operator=operator,
            parent_id=parent.individual_id if parent else None,
            parent_fitness=_json_number(parent.fitness) if parent else None,
            parent_progress=parent.progress if parent else None,
            candidate=candidate,
            candidate_text=text,
            candidate_key=key,
            fitness=fitness,
            outcome=outcome,
            evaluation=evaluation,
            self_report=report,
            rationale=rationale,
            prompt=prompt,
            raw_response=raw,
            parse_ok=True,
            duplicate_of=duplicate_of,
            entered_pool=True,
            prospective=prospective,
        )
        self.everyone.append(individual)
        self.pool.append(individual)
        return individual


def _json_number(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return float(value)


def _hash_or_none(text: str) -> str | None:
    return hash_injection_text(text) if text else None
