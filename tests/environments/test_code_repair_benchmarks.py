"""Tests for the QuixBugs and HumanEvalFix loaders (offline; small fixtures)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from environments.code_repair.benchmarks import SplitRule, build_humanevalfix_tasks, build_quixbugs_tasks, split_cases
from environments.code_repair.benchmarks.humanevalfix import extract_assert_inputs
from environments.code_repair.benchmarks.quixbugs import build_prompt, split_program_source
from environments.code_repair.evaluation import evaluate_program
from environments.code_repair.runner import TestCase as Case
from environments.code_repair.tasks import list_tasks, load_task, validate_task

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "benchmarks"
PACK = FIXTURES / "humanevalpack_python_subset.jsonl"
PLUS = FIXTURES / "HumanEvalPlus_subset.jsonl.gz"

BUGGY_GCD = '''def gcd(a, b):
    if b == 0:
        return a
    else:
        return gcd(a % b, b)


"""
Input:
    a: A nonnegative int
    b: A nonnegative int

Greatest Common Divisor

Output:
    The greatest int that divides evenly into a and b

Example:
    >>> gcd(35, 21)
    7
"""
'''

CORRECT_GCD = '''
def gcd(a, b):
    if b == 0:
        return a
    else:
        return gcd(b, a % b)
'''

GCD_CASES = [
    "[[13, 13], 13]",
    "[[37, 600], 1]",
    "[[20, 100], 20]",
    "[[624129, 2061517], 18913]",
    "[[3, 12], 3]",
    "[[35, 21], 7]",
]

BUGGY_SIEVE = '''import string

def sieve(max):
    primes = []
    for n in range(2, max + 1):
        if any(n % p > 0 for p in primes):
            primes.append(n)
    return primes

"""
Sieve of Eratosthenes

Output:
    A list containing all primes up to and including max
"""
'''

CORRECT_SIEVE = '''
def sieve(max):
    primes = []
    for n in range(2, max + 1):
        if all(n % p > 0 for p in primes):
            primes.append(n)
    return primes

"""
def sieve(max):
    return [n for n in range(2, max + 1) if all(n % p for p in range(2, n))]
"""
'''

SIEVE_CASES = ["[[1], []]", "[[2], [2]]", "[[4], [2, 3]]", "[[7], [2, 3, 5, 7]]", "[[20], [2, 3, 5, 7, 11, 13, 17, 19]]", "[[50], [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]]"]


def _fake_quixbugs(root: Path) -> Path:
    (root / "python_programs").mkdir(parents=True)
    (root / "correct_python_programs").mkdir()
    (root / "json_testcases").mkdir()
    (root / "python_programs" / "gcd.py").write_text(BUGGY_GCD)
    (root / "correct_python_programs" / "gcd.py").write_text(CORRECT_GCD)
    (root / "json_testcases" / "gcd.json").write_text("\n".join(GCD_CASES) + "\n")
    (root / "python_programs" / "sieve.py").write_text(BUGGY_SIEVE)
    (root / "correct_python_programs" / "sieve.py").write_text(CORRECT_SIEVE)
    (root / "json_testcases" / "sieve.json").write_text("\n".join(SIEVE_CASES) + "\n")
    # a program without JSON cases must be ignored
    (root / "python_programs" / "detect_cycle.py").write_text("def detect_cycle(node):\n    return False\n")
    (root / "correct_python_programs" / "detect_cycle.py").write_text("def detect_cycle(node):\n    return False\n")
    return root


def test_split_program_source_keeps_imports_and_drops_trailing_strings():
    seeded, signature, spec = split_program_source(BUGGY_SIEVE, "sieve")
    assert seeded.startswith("import string\n")
    assert "Sieve of Eratosthenes" not in seeded
    assert signature == "def sieve(max):"
    assert spec.startswith("Sieve of Eratosthenes")
    reference, _, spec_correct = split_program_source(CORRECT_SIEVE, "sieve")
    assert "range(2, n)" not in reference  # the alternative solutions string is dropped from the program
    prompt = build_prompt(signature, spec)
    assert prompt.startswith("Implement the function below.\n\ndef sieve(max):\n")
    assert "    A list containing all primes" in prompt


def test_quixbugs_build_validates_and_indexes(tmp_path):
    root = _fake_quixbugs(tmp_path / "QuixBugs")
    output = tmp_path / "tasks"
    report = build_quixbugs_tasks(root, output)
    assert [entry["id"] for entry in report.built] == ["quixbugs_gcd", "quixbugs_sieve"]
    assert report.rejected == []
    index = json.loads((output / "index.json").read_text())
    assert index["benchmark"] == "quixbugs" and index["n_tasks"] == 2
    assert index["split_rule"] == SplitRule().to_dict()
    assert (output / "rejected.json").is_file()

    tasks = {task.id: task for task in list_tasks(output)}
    gcd = tasks["quixbugs_gcd"]
    assert gcd.source["benchmark"] == "quixbugs" and gcd.source["original_id"] == "gcd"
    assert "gcd(35, 21)" in gcd.prompt
    # the docstring example is a development test, never a hidden one
    assert any(case.args == (35, 21) for case in gcd.dev_tests)
    assert not any(case.args == (35, 21) for case in gcd.hidden_tests)
    assert validate_task(gcd).ok
    seeded = evaluate_program(gcd, gcd.seeded_source)
    assert seeded.dev_passed < seeded.dev_total
    reference = evaluate_program(gcd, gcd.reference_source)
    assert reference.all_hidden_passed
    gcd_entry = next(entry for entry in report.built if entry["id"] == "quixbugs_gcd")
    assert gcd_entry["n_dev"] + gcd_entry["n_hidden"] == len(GCD_CASES)
    assert gcd_entry["seeded_dev_failing"] >= 1
    assert gcd_entry["dropped_infeasible_for_reference"] == []


def test_quixbugs_only_and_missing_root(tmp_path):
    root = _fake_quixbugs(tmp_path / "QuixBugs")
    report = build_quixbugs_tasks(root, tmp_path / "tasks", names=["sieve"])
    assert [entry["id"] for entry in report.built] == ["quixbugs_sieve"]
    with pytest.raises(ValueError):
        build_quixbugs_tasks(tmp_path / "nowhere", tmp_path / "tasks2")


def test_split_cases_rule():
    program = "def f(x):\n    return x if x < 3 else -1\n"  # fails for x >= 3
    cases = [Case((i,), i) for i in range(8)] + [Case((1,), 1)]  # duplicate of (1,)
    prompt = "def f(x):\n    >>> f(5)\n    5\n"
    dev, hidden, notes = split_cases(cases, program, "f", prompt)
    assert notes["n_cases"] == 8  # duplicate dropped
    assert notes["forced_dev_by_prompt_example"] == [5]
    assert any(case.args == (5,) for case in dev)
    dev_args = {case.args for case in dev}
    hidden_args = {case.args for case in hidden}
    assert dev_args.isdisjoint(hidden_args)
    assert dev_args | hidden_args == {(i,) for i in range(8)}
    # failing cases (3..7 minus the forced 5) alternate starting with development
    failing_free = [(3,), (4,), (6,), (7,)]
    assert [args in dev_args for args in failing_free] == [True, False, True, False]
    # passing cases (0, 1, 2) alternate starting with hidden
    assert [args in hidden_args for args in [(0,), (1,), (2,)]] == [True, False, True]
    long_case = Case(("x" * 500,), "y")
    _, hidden_long, notes_long = split_cases([long_case, Case((9,), -1)], program, "f", prompt)
    assert notes_long["forced_hidden_by_length"] == [0]
    assert long_case in hidden_long


def test_humanevalfix_build_with_evalplus(tmp_path):
    output = tmp_path / "hef"
    report = build_humanevalfix_tasks(PACK, output, evalplus_path=PLUS, max_plus_hidden=5)
    assert [entry["id"] for entry in report.built] == ["humanevalfix_002", "humanevalfix_012"]
    assert len(report.rejected) == 1 and report.rejected[0]["id"] == "humanevalfix_000"
    assert "passes every development test" in report.rejected[0]["reason"]

    truncate = load_task(output / "humanevalfix_002")
    assert truncate.entry_point == "truncate_number"
    assert truncate.float_tolerance == pytest.approx(1e-6)  # EvalPlus atol
    assert truncate.source["bug_type"] == "excess logic" and truncate.source["humaneval_id"] == "HumanEval/2"
    assert truncate.prompt.startswith("Implement the function below.\n\ndef truncate_number")
    assert ">>> truncate_number(3.5)" in truncate.prompt
    assert any(case.args == (3.5,) for case in truncate.dev_tests)
    assert not any(case.args == (3.5,) for case in truncate.hidden_tests)
    entry = next(entry for entry in report.built if entry["id"] == "humanevalfix_002")
    assert entry["plus_hidden_added"] == 5
    assert len(truncate.hidden_tests) == entry["n_hidden"] >= 5
    assert not truncate.seeded_source.startswith("\n")
    assert truncate.seeded_source.startswith("def truncate_number(number: float) -> float:\n")
    assert validate_task(truncate).ok
    assert evaluate_program(truncate, truncate.reference_source).all_hidden_passed
    assert not evaluate_program(truncate, truncate.seeded_source).all_hidden_passed

    longest = load_task(output / "humanevalfix_012")
    assert longest.float_tolerance == 0.0
    assert longest.reference_source.startswith("from typing import List, Optional\n")


def test_humanevalfix_reads_the_hub_parquet_file(tmp_path):
    pytest.importorskip("pyarrow")
    parquet = FIXTURES / "humanevalpack_python_subset.parquet"
    report = build_humanevalfix_tasks(parquet, tmp_path / "hef", evalplus_path=PLUS, max_plus_hidden=3, numbers=[2])
    assert [entry["id"] for entry in report.built] == ["humanevalfix_002"]


def test_humanevalfix_build_without_evalplus_falls_back_to_assert_inputs(tmp_path):
    report = build_humanevalfix_tasks(PACK, tmp_path / "hef", numbers=[2, 12])
    assert [entry["id"] for entry in report.built] == ["humanevalfix_002", "humanevalfix_012"]
    for entry in report.built:
        assert entry["plus_hidden_added"] == 0
        assert entry["n_dev"] >= 1 and entry["n_hidden"] >= 1


def test_plus_inputs_that_appear_in_the_prompt_are_moved_to_development():
    from environments.code_repair.benchmarks.common import BuiltTask, keep_prompt_examples_out_of_hidden

    built = BuiltTask(
        id="t", entry_point="f", prompt="Examples:\n    >>> f(1, 4)\n    True\n",
        reference_source="def f(a, b):\n    return True\n", seeded_source="def f(a, b):\n    return False\n",
        dev_tests=[Case((2, 3), True)], hidden_tests=[Case((1, 4), True), Case((5, 6), True)],
    )
    assert keep_prompt_examples_out_of_hidden(built) == 1
    assert [case.args for case in built.hidden_tests] == [(5, 6)]
    assert [case.args for case in built.dev_tests] == [(2, 3), (1, 4)]


def test_extract_assert_inputs():
    test_source = (
        "def check(candidate):\n"
        "    assert candidate([1, 2], 3) == [3]\n"
        "    assert abs(candidate(1.5) - 0.5) < 1e-6\n"
        "    assert candidate('a', k=2) == 'x'\n"  # keyword call: skipped
        "    assert candidate(x) == 1\n"  # non-literal: skipped
        "    assert True\n"
        "    assert math.isclose(candidate(2.0), 4.0)\n"
    )
    assert extract_assert_inputs(test_source, "f") == [[[1, 2], 3], [1.5], [2.0]]
    assert extract_assert_inputs("def check(f):\n    assert f(7) == 7\n", "f") == [[7]]
    assert extract_assert_inputs("this is not python", "f") == []


def test_extra_defects_make_a_harder_seeded_program():
    import random

    from environments.code_repair.benchmarks.defects import apply_mutations, inject_defects, mutation_sites

    task = load_task(Path(__file__).resolve().parents[2] / "environments" / "code_repair" / "tasks" / "count_peaks")
    sites = mutation_sites(task.seeded_source)
    assert len(sites) >= 5 and {site.kind for site in sites} & {"compare", "binop", "constant"}
    mutated = apply_mutations(task.seeded_source, sites[:1])
    assert mutated != task.seeded_source
    result = inject_defects(task.reference_source, task.seeded_source, task.entry_point, task.dev_tests, task.hidden_tests, 2, random.Random(0))
    assert result is not None
    program, descriptions = result
    assert len(descriptions) == 2 and program != task.seeded_source
    evaluation = evaluate_program(task, program)
    assert evaluation.compile_ok and evaluation.dev_passed < evaluation.dev_total
    # the reference is untouched by the injector
    assert evaluate_program(task, task.reference_source).all_hidden_passed


def test_build_with_extra_defects_renames_tasks(tmp_path):
    root = _fake_quixbugs(tmp_path / "QuixBugs")
    report = build_quixbugs_tasks(root, tmp_path / "tasks", names=["sieve"], extra_defects=1, defect_seed=3)
    assert [entry["id"] for entry in report.built] == ["quixbugs_sieve_d1"]
    task = load_task(tmp_path / "tasks" / "quixbugs_sieve_d1")
    assert len(task.source["extra_defects"]) == 1 and task.source["extra_defects_seed"] == 3
    assert validate_task(task).ok


# ----------------------------------------------------------------- anonymised variants

PROGRAM_WITH_NAMES = '''import math
from collections import Counter

def total(values, scale=1):
    """Sum scaled values."""
    return sum(v * scale for v in values)

def pick_best(items, key=None):
    """Recursive helper with a nested function, a comprehension and a keyword call."""
    def score(item):
        try:
            return math.sqrt(total(item, scale=2))
        except ValueError as err:
            return float("-inf")
    counts = Counter(len(item) for item in items)
    best = max(items, key=key or score)
    return [best, counts.most_common(1)[0][0]]
'''


def test_anonymize_renames_every_bound_name_and_keeps_behaviour():
    from environments.code_repair.benchmarks.anonymize import anonymize_programs, anonymous_signature

    renamed, same, mapping = anonymize_programs(PROGRAM_WITH_NAMES, PROGRAM_WITH_NAMES, "pick_best")
    assert renamed == same
    assert mapping.names["pick_best"] == "solve" and mapping.names["total"] == "helper_1" and mapping.names["score"] == "helper_2"
    for old in ("values", "scale", "items", "item", "err", "counts", "best", "pick_best", "total", "score"):
        assert old not in renamed.replace("most_common", "")  # bound names are gone
    assert "max(v4, key=v5 or helper_2)" in renamed  # keyword of a builtin call untouched, the parameter renamed
    assert "import math" in renamed and "from collections import Counter" in renamed
    assert "math.sqrt" in renamed and "most_common" in renamed and "Counter" in renamed  # library names untouched
    assert '"""' not in renamed  # docstrings removed
    assert "helper_1(v" in renamed and "v2=2" in renamed  # keyword argument of a renamed function follows its parameter
    assert anonymous_signature(renamed) == "def solve(v4, v5=None):"
    scope_old: dict = {}
    scope_new: dict = {}
    exec(PROGRAM_WITH_NAMES, scope_old)
    exec(renamed, scope_new)
    assert scope_new["solve"]([[1, 2], [3]]) == scope_old["pick_best"]([[1, 2], [3]])


def test_build_anonymized_tasks(tmp_path):
    root = _fake_quixbugs(tmp_path / "QuixBugs")
    report = build_quixbugs_tasks(root, tmp_path / "tasks", extra_defects=1, defect_seed=3, anonymize=True)
    assert sorted(entry["id"] for entry in report.built) == ["quixbugs_gcd_d1_anon", "quixbugs_sieve_d1_anon"]
    task = load_task(tmp_path / "tasks" / "quixbugs_sieve_d1_anon")
    assert task.entry_point == "solve"
    assert task.prompt.startswith("Repair the function below.\n\ndef solve(v1):")
    assert "specification" in task.prompt and "sieve" not in task.prompt
    assert "sieve" not in task.seeded_source and "sieve" not in task.reference_source
    assert task.source["anonymized"]["original_entry_point"] == "sieve"
    assert len(task.source["extra_defects"]) == 1
    assert validate_task(task).ok
    index = json.loads((tmp_path / "tasks" / "index.json").read_text())
    assert index["anonymized"] is True
