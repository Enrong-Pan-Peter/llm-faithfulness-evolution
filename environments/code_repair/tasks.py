"""Task format and loader for the code-repair environment.

A task is a directory with five files:

``task.json``
    ``{"id": ..., "entry_point": ..., "prompt": ..., "language": "python"}``.
    ``prompt`` is the natural-language specification plus the function
    signature shown to the model; ``entry_point`` is the function name.
    Optional keys: ``float_tolerance`` (absolute tolerance for comparing
    numbers, default 0 = exact) and ``source`` (where the task came from:
    benchmark name, original id, bug type; recorded in run records, never
    shown to the model).
``reference.py``
    A correct solution. Never shown to the model.
``seeded.py``
    The imperfect starting program the search begins from. It must fail at
    least one development test.
``dev_tests.py``
    Development tests the model may see (as failing cases in prompts).
``hidden_tests.py``
    Held-out tests that decide success. Never shown to the model.

Both test files use one format: a single module-level literal

    TESTS = [
        (("aaab",), "a3b1"),   # (tuple of positional arguments, expected return value)
        ((3, [1, 2]), 6),
    ]

The file is parsed with :mod:`ast` and read with :func:`ast.literal_eval`; it is
never executed, so only Python literals are allowed. Every value must be
JSON-transportable (``None``, bool, int, finite float, str, lists/tuples of
these, dicts with string keys) because test cases travel to the test-runner
child as JSON. Tuples are compared as lists by the runner.
"""

from __future__ import annotations

import ast
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .runner import DEFAULT_MEMORY_MB, DEFAULT_TIMEOUT_S, RunResult, TestCase, run_tests


TASK_FILE = "task.json"
REFERENCE_FILE = "reference.py"
SEEDED_FILE = "seeded.py"
DEV_TESTS_FILE = "dev_tests.py"
HIDDEN_TESTS_FILE = "hidden_tests.py"
TESTS_NAME = "TESTS"
REQUIRED_TASK_KEYS = ("id", "entry_point", "prompt", "language")

# The three example tasks shipped with the package (offline tests only).
EXAMPLE_TASKS_ROOT = Path(__file__).resolve().parent / "tasks"


class TaskFormatError(ValueError):
    """A task directory or test file does not follow the documented format."""


@dataclass(frozen=True)
class Task:
    """One loaded code-repair task."""

    id: str
    entry_point: str
    prompt: str
    language: str
    path: Path
    reference_source: str
    seeded_source: str
    dev_tests: tuple[TestCase, ...]
    hidden_tests: tuple[TestCase, ...]
    hidden_tests_source: str
    float_tolerance: float = 0.0
    source: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskValidationReport:
    """Outcome of :func:`validate_task`; ``ok`` is true when ``problems`` is empty."""

    task_id: str
    problems: tuple[str, ...]
    reference_dev: RunResult
    reference_hidden: RunResult
    seeded_dev: RunResult

    @property
    def ok(self) -> bool:
        """True when the task satisfies every validation rule."""
        return not self.problems

    @property
    def seeded_failing_dev_indices(self) -> tuple[int, ...]:
        """Indices of the development tests the seeded program fails."""
        return tuple(outcome.index for outcome in self.seeded_dev.outcomes if not outcome.passed)


def load_tests_file(path: Path | str) -> tuple[TestCase, ...]:
    """Parse a ``dev_tests.py``/``hidden_tests.py`` file without executing it."""
    path = Path(path)
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        raise TaskFormatError(f"{path}: cannot parse test file: {exc}") from exc
    literal = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == TESTS_NAME for target in node.targets
        ):
            literal = node.value
    if literal is None:
        raise TaskFormatError(f"{path}: no module-level '{TESTS_NAME} = [...]' assignment")
    try:
        raw = ast.literal_eval(literal)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError) as exc:
        raise TaskFormatError(f"{path}: {TESTS_NAME} must be a literal: {exc}") from exc
    if not isinstance(raw, (list, tuple)):
        raise TaskFormatError(f"{path}: {TESTS_NAME} must be a list")
    cases: list[TestCase] = []
    for index, entry in enumerate(raw):
        where = f"{path}: {TESTS_NAME}[{index}]"
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            raise TaskFormatError(f"{where} must be a (arguments, expected) pair")
        args, expected = entry
        if not isinstance(args, (list, tuple)):
            raise TaskFormatError(f"{where}: arguments must be a tuple")
        _check_transportable(args, f"{where} arguments")
        _check_transportable(expected, f"{where} expected value")
        cases.append(TestCase(args=tuple(args), expected=expected))
    return tuple(cases)


def _check_transportable(value: Any, where: str) -> None:
    """Reject values that would not survive the JSON trip to the runner child."""
    if value is None or isinstance(value, (bool, int, str)):
        return
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise TaskFormatError(f"{where}: non-finite floats are not supported")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _check_transportable(item, where)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TaskFormatError(f"{where}: dict keys must be strings")
            _check_transportable(item, where)
        return
    raise TaskFormatError(f"{where}: unsupported value type {type(value).__name__}")


def load_task(path: Path | str) -> Task:
    """Load and structurally check the task stored in directory ``path``."""
    path = Path(path)
    if not path.is_dir():
        raise TaskFormatError(f"{path}: not a task directory")
    for name in (TASK_FILE, REFERENCE_FILE, SEEDED_FILE, DEV_TESTS_FILE, HIDDEN_TESTS_FILE):
        if not (path / name).is_file():
            raise TaskFormatError(f"{path}: missing {name}")
    try:
        meta = json.loads((path / TASK_FILE).read_text(encoding="utf-8"))
    except ValueError as exc:
        raise TaskFormatError(f"{path / TASK_FILE}: invalid JSON: {exc}") from exc
    if not isinstance(meta, dict):
        raise TaskFormatError(f"{path / TASK_FILE}: top level must be an object")
    for key in REQUIRED_TASK_KEYS:
        if not isinstance(meta.get(key), str) or not meta[key].strip():
            raise TaskFormatError(f"{path / TASK_FILE}: '{key}' must be a non-empty string")
    if meta["language"] != "python":
        raise TaskFormatError(f"{path / TASK_FILE}: only language 'python' is supported")
    if not meta["entry_point"].isidentifier():
        raise TaskFormatError(f"{path / TASK_FILE}: entry_point must be a Python identifier")
    tolerance = meta.get("float_tolerance", 0.0)
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or tolerance < 0:
        raise TaskFormatError(f"{path / TASK_FILE}: float_tolerance must be a non-negative number")
    source = meta.get("source", {})
    if not isinstance(source, dict):
        raise TaskFormatError(f"{path / TASK_FILE}: source must be an object")
    dev_tests = load_tests_file(path / DEV_TESTS_FILE)
    hidden_tests = load_tests_file(path / HIDDEN_TESTS_FILE)
    if not dev_tests or not hidden_tests:
        raise TaskFormatError(f"{path}: development and hidden test lists must be non-empty")
    return Task(
        id=meta["id"],
        entry_point=meta["entry_point"],
        prompt=meta["prompt"],
        language=meta["language"],
        path=path,
        reference_source=(path / REFERENCE_FILE).read_text(encoding="utf-8"),
        seeded_source=(path / SEEDED_FILE).read_text(encoding="utf-8"),
        dev_tests=dev_tests,
        hidden_tests=hidden_tests,
        hidden_tests_source=(path / HIDDEN_TESTS_FILE).read_text(encoding="utf-8"),
        float_tolerance=float(tolerance),
        source=dict(source),
    )


def list_tasks(root: Path | str) -> list[Task]:
    """Load every task directory directly under ``root``, sorted by task id."""
    root = Path(root)
    tasks = [load_task(child) for child in sorted(root.iterdir()) if (child / TASK_FILE).is_file()]
    return sorted(tasks, key=lambda task: task.id)


def validate_task(
    task: Task,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    memory_mb: int | None = DEFAULT_MEMORY_MB,
) -> TaskValidationReport:
    """Check the task's programs against its tests by running them.

    Rules: the reference passes every development and hidden test, the seeded
    program loads and fails at least one development test, and no hidden test
    repeats the arguments of a development test (otherwise a prompt could show
    hidden-test content legitimately).
    """
    problems: list[str] = []
    tolerance = task.float_tolerance
    reference_dev = run_tests(
        task.reference_source, task.entry_point, task.dev_tests, timeout_s, memory_mb, float_tolerance=tolerance
    )
    reference_hidden = run_tests(
        task.reference_source, task.entry_point, task.hidden_tests, timeout_s, memory_mb, float_tolerance=tolerance
    )
    seeded_dev = run_tests(
        task.seeded_source, task.entry_point, task.dev_tests, timeout_s, memory_mb, float_tolerance=tolerance
    )

    for label, result in (("development", reference_dev), ("hidden", reference_hidden)):
        if not result.compile_ok:
            problems.append(f"reference does not load on {label} tests: {result.compile_error or result.block_reason}")
        for outcome in result.outcomes:
            if not outcome.passed:
                problems.append(f"reference fails {label} test {outcome.index}: {outcome.error or outcome.got}")
    if not seeded_dev.compile_ok:
        problems.append(f"seeded program does not load: {seeded_dev.compile_error or seeded_dev.block_reason}")
    elif seeded_dev.passed == seeded_dev.total:
        problems.append("seeded program passes every development test; it must fail at least one")

    dev_args = {json.dumps(list(case.args), sort_keys=True) for case in task.dev_tests}
    for index, case in enumerate(task.hidden_tests):
        if json.dumps(list(case.args), sort_keys=True) in dev_args:
            problems.append(f"hidden test {index} repeats the arguments of a development test")

    return TaskValidationReport(
        task_id=task.id,
        problems=tuple(problems),
        reference_dev=reference_dev,
        reference_hidden=reference_hidden,
        seeded_dev=seeded_dev,
    )
