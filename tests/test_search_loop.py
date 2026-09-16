"""Tests for the shared search loop (planning and code repair) with scripted models. No network."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from contexto_solver.logger import Logger
from environments.code_repair.search_adapter import CodeRepairSearchEnvironment, program_distance
from environments.code_repair.tasks import load_task
from environments.planning.blocksworld import bfs_optimal_plan, generate_instance
from environments.planning.search_adapter import PlanningSearchEnvironment, plan_distance
from search.analysis import bucket_order_for, extract_candidates, metrics_with_splits, survivor_labels
from search.loop import EvolutionarySearch
from search.model import ScriptedModel
from search.reports import parse_bucket, parse_report, report_error
from search.settings import SearchSettings

CODE_TASK = Path(__file__).resolve().parents[1] / "environments" / "code_repair" / "tasks" / "count_peaks"


def planning_env(n_blocks: int = 4, seed: int = 7) -> tuple[PlanningSearchEnvironment, list[str]]:
    instance = generate_instance(n_blocks, seed)
    search = bfs_optimal_plan(instance.initial_state, instance.goal)
    optimal = [str(action) for action in search.plan]
    return PlanningSearchEnvironment(instance, optimal_length=search.length), optimal


def planning_responder(optimal: list[str], solve_probability: float, seed: int = 0, closeness=None):
    rng = random.Random(seed)

    def respond(prompt: str):
        if "Do not write the plan yet" in prompt:
            return {"strategy": "Clear the top blocks, then build the goal tower from the bottom."}
        if "Parent plan" in prompt and rng.random() < solve_probability:
            plan = list(optimal)
        else:
            plan = optimal[: max(1, len(optimal) - rng.randint(1, 3))]
        return {
            "plan": plan,
            "basis_words": ["clear", "table"],
            "reason": "Move the blocking blocks to the table first.",
            "predicted_bucket": "partial",
            "predicted_closeness": closeness if closeness is not None else round(rng.uniform(0.1, 0.9), 2),
        }

    return respond


def run_planning(channel="inherited", selection="mu_plus_lambda", max_generations=3, solve_probability=0.0, seed=1, **kwargs):
    env, optimal = planning_env()
    model = ScriptedModel(planning_responder(optimal, solve_probability, seed=seed, **kwargs))
    settings = SearchSettings(rationale_channel=channel, selection=selection, max_generations=max_generations, random_seed=seed)
    search = EvolutionarySearch(env, model, settings, run_label="test")
    return search, search.run(), model


class TestSettings:
    def test_defaults_are_the_harmonised_population(self):
        settings = SearchSettings()
        assert (settings.initial_population, settings.survivors, settings.offspring_per_parent) == (15, 5, 2)
        assert settings.offspring_per_generation == 10 and settings.pool_is_constant

    def test_invalid_choices_are_rejected(self):
        with pytest.raises(ValueError):
            SearchSettings(selection="tophalf")
        with pytest.raises(ValueError):
            SearchSettings(rationale_channel="diagnostic")

    def test_from_env_reads_overrides(self, monkeypatch):
        monkeypatch.setenv("RATIONALE_CHANNEL", "prospective")
        monkeypatch.setenv("SELECTION", "random")
        settings = SearchSettings.from_env(max_generations=2)
        assert settings.rationale_channel == "prospective" and settings.selection == "random" and settings.max_generations == 2

    def test_empty_random_seed_means_zero(self, monkeypatch):
        monkeypatch.setenv("RANDOM_SEED", "")
        assert SearchSettings.from_env().random_seed == 0

    def test_self_report_is_on_unless_switched_off(self, monkeypatch):
        monkeypatch.delenv("SELF_REPORT", raising=False)
        assert SearchSettings.from_env().self_report is True
        monkeypatch.setenv("SELF_REPORT", "0")
        assert SearchSettings.from_env().self_report is False
        monkeypatch.setenv("SELF_REPORT", "1")
        assert SearchSettings.from_env(self_report=False).self_report is False


class TestReports:
    def test_parse_bucket_is_tolerant(self):
        assert parse_bucket("All Pass", ("all_pass", "most_pass")) == "all_pass"
        assert parse_bucket("all-pass", ("all_pass",)) == "all_pass"
        assert parse_bucket("complete", ("complete", "partial", "invalid")) == "complete"
        assert parse_bucket("top100", ("complete", "partial", "invalid")) is None

    def test_parse_report_and_error(self):
        report = parse_report({"plan": [], "predicted_closeness": 1.4, "predicted_bucket": "partial", "basis_words": ["a"], "reason": "r"}, ("complete", "partial", "invalid"))
        assert report["predicted_closeness"] == 1.0 and report["predicted_closeness_clamped"]
        assert report["predicted_bucket"] == "partial" and not report["self_report_parse_failed"]
        assert report_error(report, True) == 0.0 and report_error(report, False) == 1.0
        assert parse_report("not json at all", ("complete",))["self_report_parse_failed"]
        assert report_error(None, True) is None


class TestLoop:
    def test_population_bookkeeping_and_events(self):
        search, result, model = run_planning(max_generations=3)
        events = result.trace
        names = [event["event"] for event in events]
        assert names[0] == "RUN_CONFIG" and names.count("INITIAL_CANDIDATE") == 15 and names[-1] == "FAILED"
        selects = [event for event in events if event["event"] == "SELECT"]
        assert len(selects) == 3
        for select in selects:
            details = select["details"]
            assert details["pool_size"] == 15  # 5 survivors + 10 children, and 15 at generation 0
            assert len(details["kept"]) == 5 and len(details["discarded"]) == 10
            assert details["selection"] == "mu_plus_lambda"
            assert details["kept"] == details["kept_ids"]
        assert names.count("OPERATOR_SAMPLED") == 30
        assert result.n_candidates == 45 and model.calls == 45
        config = events[0]["details"]
        assert config["environment"] == "planning" and config["method"] == "ea_plan_operators"
        assert config["prompt_fingerprint"] and config["trace_format_version"] == 4
        assert config["rationale_inheritance"] is True and config["operators"] == ["s_mutation", "m_mutation", "ml_mutation", "l_mutation"]
        assert "optimal_plan_length" in config["task"]
        json.dumps(events)  # everything serialises

    def test_survivors_are_the_best_and_retired_never_return(self):
        search, result, _ = run_planning(max_generations=3)
        events = result.trace
        by_id = {}
        for event in events:
            if event["event"] in ("INITIAL_CANDIDATE", "OPERATOR_SAMPLED"):
                by_id[event["details"]["child_id"]] = event["details"]
        retired: set[str] = set()
        for event in events:
            if event["event"] != "SELECT":
                continue
            details = event["details"]
            kept_fitness = [by_id[i]["fitness"] for i in details["kept"]]
            discarded_fitness = [by_id[i]["fitness"] for i in details["discarded"]]
            assert max(kept_fitness) <= min(discarded_fitness)
            assert not (set(details["kept"]) & retired)
            retired |= set(details["discarded"])
        assert len(search.retired) == 30 and all(individual.status == "retired" for individual in search.retired)

    def test_duplicates_are_graded_once_but_stay_individuals(self):
        env, optimal = planning_env()
        calls = {"evaluate": 0}
        original = env.evaluate

        def counting_evaluate(candidate):
            calls["evaluate"] += 1
            return original(candidate)

        env.evaluate = counting_evaluate  # type: ignore[assignment]
        model = ScriptedModel(planning_responder(optimal, 0.0, seed=3))
        result = EvolutionarySearch(env, model, SearchSettings(max_generations=1, random_seed=0)).run()
        candidates = [e["details"] for e in result.trace if e["event"] in ("INITIAL_CANDIDATE", "OPERATOR_SAMPLED")]
        distinct = {c["candidate_key"] for c in candidates}
        assert calls["evaluate"] == len(distinct) < len(candidates)
        duplicates = [c for c in candidates if c["duplicate_of"]]
        assert duplicates and all(c["entered_pool"] for c in candidates)
        first_ids = {c["candidate_key"]: c["child_id"] for c in reversed(candidates)}
        for c in duplicates:
            assert c["duplicate_of"] == first_ids[c["candidate_key"]]
            assert c["fitness"] == next(o["fitness"] for o in candidates if o["child_id"] == c["duplicate_of"])

    def test_stops_after_the_generation_with_the_first_success(self):
        search, result, _ = run_planning(max_generations=10, solve_probability=1.0)
        assert result.solved and result.generations == 1 and result.first_success_generation == 1
        assert result.trace[-1]["event"] == "SOLVED" and result.trace[-1]["details"]["best"]["success"]
        # the whole generation is completed, not cut at the first success
        assert sum(1 for e in result.trace if e["event"] == "OPERATOR_SAMPLED") == 10
        assert sum(1 for e in result.trace if e["event"] == "INITIAL_CANDIDATE") == 15

    def test_initial_population_is_always_completed(self):
        env, optimal = planning_env()
        model = ScriptedModel(lambda prompt: {"plan": optimal, "basis_words": [], "reason": "", "predicted_bucket": "complete", "predicted_closeness": 0.9})
        result = EvolutionarySearch(env, model, SearchSettings(max_generations=5)).run()
        assert result.solved and result.first_success_generation == 0 and result.generations == 0
        assert model.calls == 15 and sum(1 for e in result.trace if e["event"] == "INITIAL_CANDIDATE") == 15

    def test_stop_at_success_off_runs_every_generation(self):
        env, optimal = planning_env()
        model = ScriptedModel(lambda prompt: {"plan": optimal, "basis_words": [], "reason": "", "predicted_bucket": "complete", "predicted_closeness": 0.9})
        result = EvolutionarySearch(env, model, SearchSettings(max_generations=3, stop_at_success=False)).run()
        assert result.solved and result.first_success_generation == 0 and result.generations == 3
        assert result.trace[-1]["event"] == "SOLVED" and result.trace[-1]["details"]["first_success_generation"] == 0
        assert sum(1 for e in result.trace if e["event"] == "SELECT") == 3

    def test_random_selection_is_seed_stable_and_ignores_fitness(self):
        _, first, _ = run_planning(selection="random", max_generations=2, seed=5)
        _, second, _ = run_planning(selection="random", max_generations=2, seed=5)
        kept_first = [e["details"]["kept"] for e in first.trace if e["event"] == "SELECT"]
        kept_second = [e["details"]["kept"] for e in second.trace if e["event"] == "SELECT"]
        assert kept_first == kept_second
        assert all(len(kept) == 5 for kept in kept_first)

    def test_report_rewarded_selection_prefers_accurate_reports(self):
        env, optimal = planning_env()
        rng = random.Random(0)

        def respond(prompt):
            plan = optimal[:-1]  # never succeeds
            return {"plan": plan, "basis_words": [], "reason": "r", "predicted_bucket": "partial",
                    "predicted_closeness": rng.choice([0.05, 0.5, 0.95])}

        result = EvolutionarySearch(env, ScriptedModel(respond), SearchSettings(selection="report_rewarded", max_generations=1)).run()
        by_id = {e["details"]["child_id"]: e["details"] for e in result.trace if e["event"] == "INITIAL_CANDIDATE"}
        select = next(e["details"] for e in result.trace if e["event"] == "SELECT")
        kept_errors = [by_id[i]["self_report"]["predicted_closeness"] for i in select["kept"]]
        discarded_errors = [by_id[i]["self_report"]["predicted_closeness"] for i in select["discarded"]]
        assert max(kept_errors) <= min(discarded_errors)  # nobody succeeds, so the smallest closeness is the most accurate
        assert select["selection"] == "report_rewarded"

    def test_rationale_channels_fill_the_slot(self):
        _, inherited, _ = run_planning("inherited", max_generations=1)
        child = next(e["details"] for e in inherited.trace if e["event"] == "OPERATOR_SAMPLED")
        assert child["rationale"]["channel"] == "inherited"
        assert "prior rationale" in child["rationale"]["text"] and child["rationale"]["text"] in child["prompt"]
        assert child["self_report"]["injected_rationale_hash"] == child["rationale"]["hash"]

        _, prospective, model = run_planning("prospective", max_generations=1)
        child = next(e["details"] for e in prospective.trace if e["event"] == "OPERATOR_SAMPLED")
        assert child["rationale"]["channel"] == "prospective" and "Strategy written before this plan" in child["prompt"]
        assert child["prospective"]["text"].startswith("Clear the top blocks")
        assert model.calls == 15 + 2 * 10  # one strategy call per mutation child

        _, hint, _ = run_planning("corrective_hint", max_generations=1)
        child = next(e["details"] for e in hint.trace if e["event"] == "OPERATOR_SAMPLED")
        assert child["rationale"]["channel"] == "corrective_hint"
        assert child["rationale"]["text"] == "" or "Corrective hint" in child["prompt"]

        _, none, _ = run_planning("none", max_generations=1)
        child = next(e["details"] for e in none.trace if e["event"] == "OPERATOR_SAMPLED")
        assert child["rationale"] == {"channel": "none", "text": "", "hash": None}
        assert "prior rationale" not in child["prompt"]

    def test_parse_failures_are_logged_and_kept_out_of_the_pool(self):
        env, optimal = planning_env()
        counter = {"n": 0}

        def respond(prompt):
            counter["n"] += 1
            if counter["n"] % 3 == 0:
                return "this is not json"
            return {"plan": optimal[:-2], "basis_words": [], "reason": "", "predicted_bucket": "partial", "predicted_closeness": 0.3}

        result = EvolutionarySearch(env, ScriptedModel(respond), SearchSettings(max_generations=1)).run()
        failures = [e for e in result.trace if e["event"] == "MODEL_CALL_FAILED"]
        assert failures
        initial = [e["details"] for e in result.trace if e["event"] == "INITIAL_CANDIDATE"]
        assert sum(1 for c in initial if not c["parse_ok"]) == 5
        assert all(not c["entered_pool"] and c["fitness"] is None for c in initial if not c["parse_ok"])
        select = next(e["details"] for e in result.trace if e["event"] == "SELECT")
        assert select["pool_size"] == 10


class TestCodeAdapter:
    def test_prompts_and_grading(self):
        task = load_task(CODE_TASK)
        env = CodeRepairSearchEnvironment(task)
        prompt = env.initial_prompt(self_report=True)
        assert "Starting program" in prompt and prompt.endswith(env.task.prompt[:0] + prompt[-10:])
        for case in task.hidden_tests:
            assert repr(list(case.args)) not in prompt
        parsed = env.parse_candidate({"program": "```python\n" + task.reference_source + "```"})
        assert parsed is not None
        program, text = parsed
        assert "```" not in program
        outcome = env.outcome(env.evaluate(program))
        assert outcome["success"] and outcome["score"] == 0.0 and outcome["bucket"] == "all_pass"
        assert env.parse_candidate({"program": ""}) is None and env.parse_candidate({"plan": []}) is None
        assert program_distance(task.reference_source, task.reference_source) == 0.0
        assert 0.0 < program_distance(task.reference_source, task.seeded_source) < 1.0
        assert env.prospective_block("The loop bound is off.").startswith("\nDiagnosis written before this repair")

    def test_scripted_run_on_code(self):
        task = load_task(CODE_TASK)
        env = CodeRepairSearchEnvironment(task)
        rng = random.Random(1)

        def respond(prompt):
            if "Do not write code" in prompt:
                return {"diagnosis": "Off by one."}
            program = task.reference_source if ("Parent program" in prompt and rng.random() < 0.5) else task.seeded_source
            return {"program": program, "basis_words": ["peak"], "reason": "r", "predicted_bucket": "most_pass", "predicted_closeness": 0.6}

        result = EvolutionarySearch(env, ScriptedModel(respond), SearchSettings(rationale_channel="prospective", max_generations=3)).run()
        assert result.solved
        config = result.trace[0]["details"]
        assert config["method"] == "ea_code_operators" and config["task"]["n_hidden_tests"] == len(task.hidden_tests)
        child = next(e["details"] for e in result.trace if e["event"] == "OPERATOR_SAMPLED")
        assert "Diagnosis written before this repair" in child["prompt"]
        assert child["outcome"]["details"]["dev_total"] == len(task.dev_tests)


class TestPlanDistance:
    def test_plan_distance(self):
        assert plan_distance(["(a)", "(b)"], ["(a)", "(b)"]) == 0.0
        assert plan_distance(["(a)", "(b)"], ["(a)", "(c)"]) == pytest.approx(1 - 1 / 3)
        assert plan_distance([], []) == 0.0


class TestAnalysis:
    def test_candidate_records_and_survivor_labels(self):
        _, result, _ = run_planning(max_generations=2)
        records = extract_candidates(result.trace, "t.json")
        assert len(records) == 15 + 20
        labels = survivor_labels(result.trace)
        initial = [r for r in records if r.source_event == "INITIAL_CANDIDATE"]
        assert all(r.survived is not None for r in initial)
        assert sum(1 for r in initial if r.survived) == 5
        final_children = [r for r in records if r.source_event == "OPERATOR_SAMPLED" and r.generation == 2]
        assert all(r.survived is None for r in final_children)  # never judged by a SELECT
        first_children = [r for r in records if r.source_event == "OPERATOR_SAMPLED" and r.generation == 1]
        assert all(r.survived is not None and r.survival_generation == 2 for r in first_children)
        order = bucket_order_for(records)
        metrics = metrics_with_splits(records, order)
        assert metrics["overall"]["count"] == 35 and metrics["overall"]["brier"]["n"] == 35
        assert set(metrics["splits"]["operator"]) >= {"initial"}
        assert metrics["overall"]["buckets"]["order"] == ["complete", "partial", "invalid"]
        assert labels[first_children[0].child_id][1] == 2
