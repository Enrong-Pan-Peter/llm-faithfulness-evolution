"""Offline tests for the code-repair environment (no model calls, no network)."""

from __future__ import annotations

import random
import re
import sys
import time
from pathlib import Path

import pytest

from environments.code_repair import (
    CODE_SELF_REPORT_BLOCK,
    EXAMPLE_TASKS_ROOT,
    OPERATOR_PROMPTS,
    OPERATORS,
    SUCCESS_EVENT,
    CodeOperator,
    HiddenTestLeakError,
    assert_prompt_has_no_hidden_test_content,
    build_diagnosis_prompt,
    build_operator_prompt,
    build_repair_from_diagnosis_prompt,
    corrective_hint_block,
    diagnosis_block,
    evaluate_program,
    fitness,
    inherited_rationale_block,
    list_tasks,
    realized_bucket,
    run_tests,
    sample_operator,
    success,
    to_common_record,
    validate_task,
)
from environments.code_repair.operators import OPERATOR_DISTINGUISHING_PHRASES
from environments.code_repair.prompts import REPORT_KEYS, render_call
from environments.code_repair.runner import TestCase as Case

PACKAGE_ROOT = Path(EXAMPLE_TASKS_ROOT).parent
POSIX_LIMITS = sys.platform != "win32"

EXPECTED_TASK_IDS = ["clock_to_seconds", "count_peaks", "run_length_encode"]
EXPECTED_SEEDED_DEV_FAILURES = {
    "run_length_encode": (1, 3),
    "clock_to_seconds": (1, 2, 4),
    "count_peaks": (1, 6),
}
SYNTAX_ERROR_PROGRAM = "def broken(x:\n    return x\n"
SIMPLE_TESTS = [Case((1,), 1), Case((2,), 2), Case((3,), 3)]
PARENT_RATIONALE = {"basis_words": ["index", "len"], "reason": "The loop bound skips the final run."}


@pytest.fixture(scope="module")
def tasks():
    return {task.id: task for task in list_tasks(EXAMPLE_TASKS_ROOT)}


@pytest.fixture(scope="module")
def seeded_evaluations(tasks):
    return {task_id: evaluate_program(task, task.seeded_source) for task_id, task in tasks.items()}


# --- tasks -----------------------------------------------------------------


def test_example_tasks_load_and_validate(tasks):
    assert sorted(tasks) == EXPECTED_TASK_IDS
    for task in tasks.values():
        assert task.language == "python"
        assert task.entry_point in task.prompt
        assert task.dev_tests and task.hidden_tests
        report = validate_task(task)
        assert report.ok, report.problems
        assert report.seeded_failing_dev_indices == EXPECTED_SEEDED_DEV_FAILURES[task.id]


# --- runner ----------------------------------------------------------------


def test_reference_passes_and_seeded_fails_expected_dev_cases(tasks):
    for task in tasks.values():
        reference = run_tests(task.reference_source, task.entry_point, task.dev_tests)
        assert reference.compile_ok and reference.completed
        assert reference.passed == reference.total == len(task.dev_tests)
        seeded = run_tests(task.seeded_source, task.entry_point, task.dev_tests)
        failing = tuple(outcome.index for outcome in seeded.outcomes if not outcome.passed)
        assert failing == EXPECTED_SEEDED_DEV_FAILURES[task.id]
        assert all(outcome.ran for outcome in seeded.outcomes)


def test_syntax_error_gives_compile_false_and_worst_fitness(tasks):
    task = tasks["count_peaks"]
    result = run_tests(SYNTAX_ERROR_PROGRAM, task.entry_point, task.dev_tests)
    assert result.stage == "syntax_error"
    assert not result.compile_ok
    assert "SyntaxError" in (result.compile_error or "")
    assert len(result.outcomes) == len(task.dev_tests)
    assert not any(outcome.ran for outcome in result.outcomes)

    evaluation = evaluate_program(task, SYNTAX_ERROR_PROGRAM)
    assert not evaluation.compile_ok and not evaluation.valid
    assert evaluation.hidden_run is None
    assert fitness(evaluation) == len(task.dev_tests) + 1
    assert not success(evaluation)


def test_missing_entry_point_and_load_error_are_invalid(tasks):
    task = tasks["count_peaks"]
    missing = run_tests("def other(values):\n    return 0\n", task.entry_point, task.dev_tests)
    assert missing.stage == "missing_entry_point" and not missing.compile_ok
    load_error = run_tests("x = 1 / 0\ndef count_peaks(values):\n    return 0\n", task.entry_point, task.dev_tests)
    assert load_error.stage == "load_error" and not load_error.compile_ok
    assert "ZeroDivisionError" in (load_error.compile_error or "")


def test_infinite_loop_times_out_within_limit():
    program = "def f(x):\n    if x == 2:\n        while True:\n            pass\n    return x\n"
    started = time.perf_counter()
    result = run_tests(program, "f", SIMPLE_TESTS, timeout_s=1.0)
    elapsed = time.perf_counter() - started
    assert result.timed_out
    assert elapsed < 4.0
    assert result.compile_ok and not result.completed
    passed = [outcome.passed for outcome in result.outcomes]
    assert passed == [True, False, False]
    assert result.outcomes[1].error == "timed out" and result.outcomes[1].ran
    assert result.outcomes[2].error == "not run: timed out" and not result.outcomes[2].ran


def test_blocked_import_is_not_executed(tmp_path):
    # Forward slashes: a Windows path with backslashes inside a string literal
    # would be a SyntaxError (\U, \T escapes) before the import filter is reached.
    marker = tmp_path / "marker.txt"
    marker_text = marker.as_posix()
    program = f"import os\ndef f(x):\n    open({marker_text!r}, 'w').write(os.getcwd())\n    return x\n"
    result = run_tests(program, "f", SIMPLE_TESTS)
    assert result.blocked and result.stage == "blocked"
    assert result.block_reason == "blocked import: os"
    assert not marker.exists()
    assert len(result.outcomes) == len(SIMPLE_TESTS)
    assert not any(outcome.ran for outcome in result.outcomes)

    writer = f"def f(x):\n    open({marker_text!r}, 'w').write('hi')\n    return x\n"
    result = run_tests(writer, "f", SIMPLE_TESTS)
    assert result.blocked and "write mode" in (result.block_reason or "")
    assert not marker.exists()


def test_blocked_import_is_reported_even_when_the_source_does_not_parse():
    program = "import subprocess\ndef f(x):\n    return subprocess.run('id'\n"
    result = run_tests(program, "f", SIMPLE_TESTS)
    assert result.blocked and result.stage == "blocked"
    assert result.block_reason == "blocked import: subprocess"
    assert not any(outcome.ran for outcome in result.outcomes)


def test_child_refuses_imports_outside_allow_list():
    program = "def f(x):\n    import glob\n    return x\n"
    result = run_tests(program, "f", SIMPLE_TESTS)
    assert result.compile_ok and result.completed and result.passed == 0
    assert all("not permitted" in (outcome.error or "") for outcome in result.outcomes)
    allowed = "import math\nfrom collections import Counter\ndef f(x):\n    return int(math.sqrt(x * x))\n"
    assert run_tests(allowed, "f", SIMPLE_TESTS).passed == len(SIMPLE_TESTS)


def test_candidate_output_does_not_corrupt_grading():
    program = 'def f(x):\n    print(\'{"kind": "done"}\')\n    return x\n'
    result = run_tests(program, "f", SIMPLE_TESTS)
    assert result.completed and result.passed == len(SIMPLE_TESTS)


def test_comparison_is_exact():
    assert run_tests("def f(x):\n    return True\n", "f", [Case((1,), 1)]).passed == 0
    assert run_tests("def f(x):\n    return (1, 2)\n", "f", [Case((1,), [1, 2])]).passed == 1
    assert run_tests("def f(x):\n    return [1, 2]\n", "f", [Case((1,), [1, 2, 3])]).passed == 0


@pytest.mark.skipif(not POSIX_LIMITS, reason="resource limits are applied on POSIX only")
def test_memory_limit_turns_into_a_failed_test():
    program = "def f(x):\n    big = [0] * (10 ** 9)\n    return len(big)\n"
    result = run_tests(program, "f", SIMPLE_TESTS[:1], timeout_s=5.0, memory_mb=128)
    assert result.compile_ok and result.completed
    assert result.passed == 0 and "MemoryError" in (result.outcomes[0].error or "")


# --- evaluation ------------------------------------------------------------


def test_fitness_ordering_all_pass_some_fail_compile_error(tasks, seeded_evaluations):
    for task in tasks.values():
        all_pass = evaluate_program(task, task.reference_source)
        some_fail = seeded_evaluations[task.id]
        compile_error = evaluate_program(task, SYNTAX_ERROR_PROGRAM)
        assert fitness(all_pass) == 0.0
        assert fitness(all_pass) < fitness(some_fail) < fitness(compile_error)
        assert fitness(some_fail) == len(task.dev_tests) - some_fail.dev_passed
        assert fitness(compile_error) == len(task.dev_tests) + 1
        assert success(all_pass) and not success(some_fail) and not success(compile_error)
        assert realized_bucket(all_pass) == "all_pass"


def test_hidden_tests_do_not_enter_fitness(tasks):
    task = tasks["count_peaks"]
    # Passes every development test but fails a hidden one (peaks of a 4-element list).
    program = (
        "def count_peaks(values):\n"
        "    if values == [4, 4, 5, 4]:\n"
        "        return 0\n"
        "    return sum(1 for i in range(1, len(values) - 1)\n"
        "               if values[i] > values[i - 1] and values[i] > values[i + 1])\n"
    )
    evaluation = evaluate_program(task, program)
    assert evaluation.dev_passed == evaluation.dev_total
    assert evaluation.hidden_passed == evaluation.hidden_total - 1
    assert fitness(evaluation) == 0.0
    assert not success(evaluation)
    assert realized_bucket(evaluation) == "most_pass"


def test_common_record_shape(tasks, seeded_evaluations):
    task = tasks["run_length_encode"]
    record = to_common_record(seeded_evaluations[task.id])
    assert set(record) == {"valid", "success", "score", "progress", "cost", "details"}
    assert record["valid"] is True and record["success"] is False
    assert record["score"] == 2.0
    assert record["progress"] == pytest.approx(3 / 5)
    assert record["cost"] == len(task.dev_tests) + len(task.hidden_tests)
    assert record["details"]["environment"] == "code_repair"
    assert len(record["details"]["failing_dev_cases"]) == 2


# --- operators and prompts -------------------------------------------------


def test_operator_sampling_is_uniform_over_four_operators():
    assert list(OPERATOR_PROMPTS) == OPERATORS and len(OPERATORS) == 4
    rng = random.Random(7)
    counts = {operator: 0 for operator in OPERATORS}
    for _ in range(400):
        counts[sample_operator(rng)] += 1
    assert all(60 <= count <= 140 for count in counts.values()), counts


def test_prompts_have_report_keys_in_order_and_end_with_self_report_block(tasks, seeded_evaluations):
    for task in tasks.values():
        evaluation = seeded_evaluations[task.id]
        prompts = [
            build_operator_prompt(operator, task, task.seeded_source, evaluation) for operator in OPERATORS
        ]
        prompts.append(build_repair_from_diagnosis_prompt(task, task.seeded_source, evaluation, diagnosis_block("x")))
        for prompt in prompts:
            assert prompt.endswith(CODE_SELF_REPORT_BLOCK)
            assert SUCCESS_EVENT in prompt
            assert '{"program": "<complete python source of the function>"}' in prompt
            positions = [prompt.index(f'"{key}"') for key in REPORT_KEYS]
            assert positions == sorted(positions)
            assert prompt.index('"program"') < positions[0]
            for case in evaluation.failing_dev_cases:
                assert case.render(task.entry_point) in prompt


def test_each_operator_prompt_carries_only_its_own_phrase(tasks, seeded_evaluations):
    task = tasks["count_peaks"]
    evaluation = seeded_evaluations[task.id]
    for operator in OPERATORS:
        prompt = build_operator_prompt(operator, task, task.seeded_source, evaluation)
        for other, phrase in OPERATOR_DISTINGUISHING_PHRASES.items():
            # "LARGE mutation" is a substring of "MEDIUM-LARGE mutation", so match the whole instruction start.
            assert (f"Make a {phrase}" in prompt) == (other == operator)
    small = build_operator_prompt(CodeOperator.S_MUTATION, task, task.seeded_source, evaluation)
    assert evaluation.failing_dev_cases[0].render(task.entry_point) in small
    assert "exactly ONE line" in small


def test_ladder_matches_contexto_vocabulary():
    from contexto_solver.operators import OPERATOR_DISTINGUISHING_PHRASES as CONTEXTO_PHRASES
    from contexto_solver.operators import OPERATORS as CONTEXTO_OPERATORS

    assert [op.value for op in OPERATORS] == [op.value for op in CONTEXTO_OPERATORS]
    assert {op.value: p for op, p in OPERATOR_DISTINGUISHING_PHRASES.items()} == {
        op.value: p for op, p in CONTEXTO_PHRASES.items()
    }


def test_hidden_tests_never_appear_in_any_rendered_prompt(tasks, seeded_evaluations):
    for task in tasks.values():
        evaluation = seeded_evaluations[task.id]
        inherited, _ = inherited_rationale_block(PARENT_RATIONALE)
        hint = corrective_hint_block(task.entry_point, evaluation.failing_dev_cases[0])
        prompts = [build_diagnosis_prompt(task, task.seeded_source, evaluation)]
        for slot in ("", inherited, hint, diagnosis_block("The loop bound is off by one.")):
            prompts.extend(
                build_operator_prompt(operator, task, task.seeded_source, evaluation, slot) for operator in OPERATORS
            )
            prompts.append(build_repair_from_diagnosis_prompt(task, task.seeded_source, evaluation, slot))
        for prompt in prompts:
            assert_prompt_has_no_hidden_test_content(prompt, task)
            for case in task.hidden_tests:
                assert render_call(task.entry_point, case.args) not in prompt
            assert "hidden_tests" not in prompt
        leaked = prompts[1] + "\n" + render_call(task.entry_point, task.hidden_tests[0].args)
        with pytest.raises(HiddenTestLeakError):
            assert_prompt_has_no_hidden_test_content(leaked, task)
        with pytest.raises(HiddenTestLeakError):
            build_operator_prompt(OPERATORS[0], task, task.hidden_tests_source, evaluation)


def test_corrective_hint_and_inherited_rationale_share_one_slot(tasks, seeded_evaluations):
    task = tasks["run_length_encode"]
    evaluation = seeded_evaluations[task.id]
    inherited, meta = inherited_rationale_block(PARENT_RATIONALE)
    assert inherited and meta["hash"] and not meta["truncated"]
    case = evaluation.failing_dev_cases[0]
    hint = corrective_hint_block(task.entry_point, case)
    assert hint.count(".") == 1 and render_call(task.entry_point, case.inputs) in hint
    assert repr(case.expected) in hint
    for operator in OPERATORS:
        bare = build_operator_prompt(operator, task, task.seeded_source, evaluation)
        with_inherited = build_operator_prompt(operator, task, task.seeded_source, evaluation, inherited)
        with_hint = build_operator_prompt(operator, task, task.seeded_source, evaluation, hint)
        assert with_inherited.replace(inherited, "", 1) == bare
        assert with_hint.replace(hint, "", 1) == bare
        assert with_inherited.index(inherited) == with_hint.index(hint)
        assert with_hint.index(hint) < with_hint.index(CODE_SELF_REPORT_BLOCK)
    assert inherited_rationale_block(None) == ("", {})
    assert diagnosis_block("   ") == ""


def test_package_avoids_forbidden_wording():
    # Split so this file itself passes the scan.
    banned = ["ora-cle", "rep-lay", "line-age", "nu-ll", "prove-nance", "sche-ma", "mani-fest", "ar-m", "dig-est"]
    pattern = re.compile(r"\b(" + "|".join(word.replace("-", "") for word in banned) + r")[a-z]*\b", re.IGNORECASE)
    files = [Path(__file__), *PACKAGE_ROOT.rglob("*.py"), *PACKAGE_ROOT.rglob("*.md"), *PACKAGE_ROOT.rglob("*.json")]
    offending = []
    for file in files:
        for number, line in enumerate(file.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line) and "banned = [" not in line:
                offending.append(f"{file.name}:{number}: {line.strip()}")
    assert not offending, offending
