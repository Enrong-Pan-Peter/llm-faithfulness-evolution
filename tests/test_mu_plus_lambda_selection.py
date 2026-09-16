"""Tests for ``ea_semantic_operators`` survivor selection ((mu + lambda) and the random control).

Construction-level: no solver runs, no network. The legacy behaviour it departs
from is covered in ``test_legacy_selection.py``.
"""

from __future__ import annotations

import unittest

import numpy as np

from contexto_solver.hypothesis import Hypothesis
from contexto_solver.logger import Logger
from contexto_solver.methods.ea_semantic_operators import EASemanticOperatorsConfig, EASemanticOperatorsMethod
from contexto_solver.methods.ea_semantic_operators_legacy import EASemanticOperatorsLegacyConfig, EASemanticOperatorsLegacyMethod


class _GameStub:
    def __init__(self) -> None:
        self.guesses: dict[str, int] = {}

    def best_so_far(self) -> tuple[str | None, int | None]:
        return ("alpha", 3)

    def total_guesses(self) -> int:
        return len(self.guesses)

    def is_solved(self) -> bool:
        return False


def _config(**overrides) -> EASemanticOperatorsConfig:
    base = dict(
        max_generations=1, candidates_per_hypothesis=3, initial_categories=15, starter_words_per_category=3,
        mutations_per_generation=0, max_active_hypotheses=5, trace_dir="traces", run_label="test",
        survivors=5, offspring_per_parent=2, crossover_children=0, selection="mu_plus_lambda", random_seed=0,
    )
    base.update(overrides)
    return EASemanticOperatorsConfig(**base)


def _populate(method, n_hypotheses: int) -> None:
    method.rng = np.random.default_rng(0)
    method.logger = Logger()
    method.game = _GameStub()
    method.invalid_guesses = set()
    method.generation = 4
    method.hypotheses = []
    for index in range(n_hypotheses):
        hypothesis = Hypothesis(category_name=f"hyp{index}", description="d")
        hypothesis.update(f"word{index}", (index + 1) * 10)  # ranks 10, 20, ..., strictly ordered
        method.game.guesses[f"word{index}"] = (index + 1) * 10
        method.hypotheses.append(hypothesis)


def _new_method(n_hypotheses: int = 15, **overrides) -> EASemanticOperatorsMethod:
    method = EASemanticOperatorsMethod.__new__(EASemanticOperatorsMethod)
    method.config = _config(**overrides)
    method.retired_hypotheses = []
    _populate(method, n_hypotheses)
    return method


def _legacy_method(n_hypotheses: int = 8) -> EASemanticOperatorsLegacyMethod:
    method = EASemanticOperatorsLegacyMethod.__new__(EASemanticOperatorsLegacyMethod)
    method.config = EASemanticOperatorsLegacyConfig(
        max_generations=1, candidates_per_hypothesis=1, initial_categories=1, starter_words_per_category=1,
        mutations_per_generation=1, max_active_hypotheses=5, trace_dir="traces", run_label="test",
        selection_mode="tophalf",
    )
    _populate(method, n_hypotheses)
    return method


def _select_events(logger: Logger) -> list[dict]:
    return [entry for entry in logger.trace if entry["event"] == "SELECT"]


class ConfigTests(unittest.TestCase):
    def test_default_pool_size_is_constant(self) -> None:
        cfg = _config()
        self.assertEqual(cfg.offspring_per_generation, 10)
        self.assertTrue(cfg.pool_is_constant)

    def test_inconsistent_population_is_flagged_not_forbidden(self) -> None:
        cfg = _config(initial_categories=20)
        self.assertFalse(cfg.pool_is_constant)

    def test_selection_name_is_checked(self) -> None:
        with self.assertRaises(ValueError):
            _config(selection="tophalf")
        with self.assertRaises(ValueError):
            _config(selection="survival")


class MuPlusLambdaTests(unittest.TestCase):
    def test_keeps_best_survivors_and_retires_the_rest(self) -> None:
        method = _new_method(15)
        method._select()
        details = _select_events(method.logger)[0]["details"]
        self.assertEqual(details["kept"], [f"hyp{i}" for i in range(5)])
        self.assertEqual(details["discarded"], [f"hyp{i}" for i in range(5, 15)])
        self.assertEqual(details["elite"], "hyp0")
        self.assertEqual(details["selection"], "mu_plus_lambda")
        self.assertEqual(details["pool_size"], 15)
        self.assertEqual(details["retired_total"], 10)
        self.assertEqual([h.category_name for h in method.hypotheses], [f"hyp{i}" for i in range(5)])
        self.assertTrue(all(h.status == "active" for h in method.hypotheses))
        self.assertEqual(len(method.retired_hypotheses), 10)
        self.assertTrue(all(h.status == "retired" for h in method.retired_hypotheses))

    def test_event_keeps_the_fields_the_selection_analysis_reads(self) -> None:
        method = _new_method(15)
        method._select()
        details = _select_events(method.logger)[0]["details"]
        for key in ("kept", "discarded", "kept_ids", "discarded_ids", "elite", "max_active_hypotheses", "best_word", "best_rank", "total_guesses"):
            self.assertIn(key, details)

    def test_small_pool_keeps_everyone(self) -> None:
        method = _new_method(3)
        method._select()
        self.assertEqual(len(method.hypotheses), 3)
        self.assertEqual(method.retired_hypotheses, [])

    def test_retired_never_return_after_a_vacancy(self) -> None:
        """Under the legacy rule a dormant member returns when active members are
        removed (the deduplication-driven returns seen in the submitted traces);
        under (mu + lambda) there is nothing left to return."""
        legacy = _legacy_method(8)
        legacy._select()
        legacy.hypotheses = [h for h in legacy.hypotheses if h.category_name not in {"hyp1", "hyp2"}]
        legacy._select()
        self.assertIn("hyp4", _select_events(legacy.logger)[1]["details"]["kept"])

        strict = _new_method(8)
        strict._select()
        strict.hypotheses = [h for h in strict.hypotheses if h.category_name not in {"hyp1", "hyp2"}]
        strict._select()
        kept_after = _select_events(strict.logger)[1]["details"]["kept"]
        self.assertEqual(kept_after, ["hyp0", "hyp3", "hyp4"][: len(kept_after)])
        self.assertNotIn("hyp5", kept_after)
        self.assertTrue({"hyp5", "hyp6", "hyp7"} <= {h.category_name for h in strict.retired_hypotheses})

    def test_dedup_cannot_reactivate_a_retired_member(self) -> None:
        method = _new_method(15)
        method._select()
        child = Hypothesis(category_name="child of hyp9", description="d")
        child.update("word9", 100)
        child.update("word90", 900)
        method.hypotheses.append(child)
        method._deduplicate_hypotheses()
        self.assertNotIn("hyp9", {h.category_name for h in method.hypotheses})
        self.assertTrue(all(h.status == "retired" for h in method.retired_hypotheses))

    def test_exclusion_set_unaffected_by_retirement(self) -> None:
        method = _new_method(15)
        before = set(method._known_words())
        method._select()
        self.assertEqual(set(method._known_words()), before)


class RandomControlTests(unittest.TestCase):
    def test_same_count_logged_and_seed_stable(self) -> None:
        first = _new_method(15, selection="random")
        first._select()
        second = _new_method(15, selection="random")
        second._select()
        details = _select_events(first.logger)[0]["details"]
        self.assertEqual(details["selection"], "random")
        self.assertEqual(len(details["kept"]), 5)
        self.assertEqual(len(details["kept"]) + len(details["discarded"]), 15)
        self.assertEqual(details["kept"], _select_events(second.logger)[0]["details"]["kept"])
        self.assertEqual(len(first.retired_hypotheses), 10)

    def test_deviates_from_rank_order_sometimes(self) -> None:
        deviated = False
        for seed in range(10):
            method = _new_method(15, selection="random", random_seed=seed)
            method.rng = np.random.default_rng(seed)
            method._select()
            if set(_select_events(method.logger)[0]["details"]["kept"]) != {f"hyp{i}" for i in range(5)}:
                deviated = True
                break
        self.assertTrue(deviated)


class ReportRewardedControlTests(unittest.TestCase):
    def test_keeps_the_most_accurate_reports(self) -> None:
        method = _new_method(15, selection="report_rewarded")
        # ranks are 10, 20, ..., 150: hyp0..hyp9 are within the top 100 (success), hyp10..hyp14 are not
        closeness = {0: 0.1, 1: 0.9, 2: 0.5, 3: 0.95, 4: 0.2, 5: 0.85, 6: 0.3, 7: 0.99, 8: 0.6, 9: 0.4,
                     10: 0.05, 11: 0.9, 12: 0.5, 13: 0.1, 14: None}
        for index, hypothesis in enumerate(method.hypotheses):
            hypothesis.predicted_closeness = closeness[index]
        errors = {h.category_name: EASemanticOperatorsMethod.report_error(h) for h in method.hypotheses}
        method._select()
        details = _select_events(method.logger)[0]["details"]
        self.assertEqual(details["selection"], "report_rewarded")
        self.assertEqual(len(details["kept"]), 5)
        kept_errors = [errors[name] for name in details["kept"]]
        discarded_errors = [errors[name] for name in details["discarded"]]
        self.assertLessEqual(max(kept_errors), min(discarded_errors))
        self.assertEqual(details["kept"][0], "hyp7")  # closeness 0.99, rank 80: error 0.01
        self.assertIn("hyp10", details["kept"])  # closeness 0.05, rank 110: error 0.05
        self.assertNotIn("hyp14", details["kept"])  # no report: worst error
        self.assertEqual(errors["hyp14"], 1.0)

    def test_unknown_selection_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            _config(selection="report_rewarded_v2")


if __name__ == "__main__":
    unittest.main()
