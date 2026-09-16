"""Offline tests for the batch runner (no network, no model).

Covers game-number parsing, input validation, the run-record fields written as
``RUN_CONFIG`` for each method, seed assignment, and method construction.
"""

from __future__ import annotations

import argparse
import unittest

from contexto_solver import config
from contexto_solver import experiment as ex
from contexto_solver.logger import Logger
from contexto_solver.methods.direct_llm_only_sequential import DirectLLMOnlySequentialMethod
from contexto_solver.methods.ea_semantic_operators import EASemanticOperatorsMethod
from contexto_solver.methods.ea_semantic_operators_legacy import EASemanticOperatorsLegacyMethod


def _args(**overrides) -> argparse.Namespace:
    base = dict(
        method="ea_semantic_operators", game_numbers=None, max_generations=10, runs_per_target=1,
        random_seed=0, llm_workers=4, provider="ollama", model=None, ollama_model="qwen3:14b",
        api_key="x", output=None, resume=False,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


class _GameStub:
    guesses: dict[str, int] = {}

    def best_so_far(self):
        return (None, None)

    def total_guesses(self):
        return 0

    def is_solved(self):
        return False


class GameNumberParsingTests(unittest.TestCase):
    def test_parses_commas_and_spaces(self):
        self.assertEqual(ex._parse_game_numbers("1387, 1388 1389"), [1387, 1388, 1389])

    def test_empty(self):
        self.assertEqual(ex._parse_game_numbers(None), [])


class ValidationTests(unittest.TestCase):
    def test_missing_game_numbers(self):
        with self.assertRaises(ValueError):
            ex.run_batch(_args(game_numbers=None))

    def test_unknown_method_rejected(self):
        with self.assertRaises(ValueError):
            ex.run_batch(_args(game_numbers="1387", method="embedding"))


class RunRecordTests(unittest.TestCase):
    def test_new_method_record_fields(self):
        rc = ex.run_settings(_args(game_numbers="1387"), 1387, 0, "ollama", "qwen3:14b", serving={"server_version": "x"})
        self.assertEqual(rc["method"], "ea_semantic_operators")
        self.assertEqual(rc["environment"], "contexto")
        self.assertEqual(rc["game_number"], 1387)
        self.assertEqual(rc["trace_format_version"], config.TRACE_FORMAT_VERSION)
        self.assertTrue(rc["prompt_fingerprint"])
        self.assertEqual(rc["serving"]["server_version"], "x")
        for key in ("initial_population", "survivors", "offspring_per_parent", "crossover_children",
                    "offspring_per_generation", "pool_size_constant", "parent_refresh", "selection", "operator_mix"):
            self.assertIn(key, rc)
        self.assertEqual(rc["operator_mix"], "fixed_uniform")
        self.assertEqual(rc["offspring_per_generation"], config.SURVIVORS * config.OFFSPRING_PER_PARENT + config.CROSSOVER_CHILDREN)

    def test_default_settings_keep_the_pool_size_constant(self):
        rc = ex.run_settings(_args(game_numbers="1387"), 1387, 0, "ollama", "qwen3:14b")
        self.assertTrue(rc["pool_size_constant"])
        self.assertEqual(rc["initial_population"], rc["survivors"] + rc["offspring_per_generation"])

    def test_legacy_record_keeps_the_submitted_study_names(self):
        rc = ex.run_settings(_args(game_numbers="1387", method="ea_semantic_operators_legacy"), 1387, 0, "ollama", "qwen3:14b")
        self.assertEqual(rc["self_adaptive_sigma_mode"], "frozen_uniform")
        self.assertEqual(rc["max_active_hypotheses"], 5)
        self.assertEqual(rc["self_adaptive_mu"], 15)
        self.assertEqual(rc["survivors"], 5)
        self.assertTrue(rc["parent_refresh"])

    def test_direct_record_has_guess_budget(self):
        rc = ex.run_settings(_args(game_numbers="1387", method="direct_llm_only_sequential", max_generations=350), 1387, 0, "ollama", "qwen3:14b")
        self.assertEqual(rc["guess_budget"], 350)
        self.assertNotIn("survivors", rc)


class SeedAssignmentTests(unittest.TestCase):
    def test_run_seed_offsets(self):
        self.assertEqual(ex._run_seed(0, 0), 0)
        self.assertEqual(ex._run_seed(0, 1), 1)
        self.assertEqual(ex._run_seed(10, 2), 12)
        self.assertIsNone(ex._run_seed(None, 1))

    def test_run_record_matches_solver_seed(self):
        args = _args(random_seed=0, game_numbers="1387")
        for run_index in (0, 1):
            logged = ex.run_settings(args, 1387, run_index, "ollama", "qwen3:14b")["random_seed"]
            self.assertEqual(logged, ex._run_seed(args.random_seed, run_index))


class MethodConstructionTests(unittest.TestCase):
    def test_each_method_builds(self):
        for name, cls in (
            ("ea_semantic_operators", EASemanticOperatorsMethod),
            ("ea_semantic_operators_legacy", EASemanticOperatorsLegacyMethod),
            ("direct_llm_only_sequential", DirectLLMOnlySequentialMethod),
        ):
            method = ex.build_method(name, _GameStub(), llm_client=None, logger=Logger(), run_label="t", args=_args(method=name), run_index=2)
            self.assertIsInstance(method, cls)
        new = ex.build_method("ea_semantic_operators", _GameStub(), None, Logger(), "t", _args(), run_index=2)
        self.assertEqual(new.config.survivors, config.SURVIVORS)
        self.assertEqual(new.config.random_seed, 2)


if __name__ == "__main__":
    unittest.main()
