"""Grading a candidate program on a task and turning the result into fitness.

Fitness (lower is better, matching the Contexto convention where rank 1 is
best) is the number of failing development tests; a program that is blocked
by the static filter, does not compile, fails while loading, or does not
define the entry point receives ``dev_total + 1`` so it always ranks below any
program that loads. Hidden tests never enter fitness; they only decide the
binary success event ``all_hidden_passed`` that the model's self-report is
scored against.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .runner import DEFAULT_MEMORY_MB, DEFAULT_TIMEOUT_S, RunResult, run_tests
from .tasks import Task


ENVIRONMENT_NAME = "code_repair"
MAX_FAILING_DEV_CASES = 5

# Ordinal outcome buckets over the hidden-test pass fraction. The model is
# asked to predict one of these; ``realized_bucket`` computes the actual one.
OUTCOME_BUCKETS: tuple[str, ...] = ("all_pass", "most_pass", "some_pass", "none_pass")


def render_call(entry_point: str, args: tuple[Any, ...] | list[Any]) -> str:
    """Render ``entry_point(arg1, arg2, ...)`` with ``repr`` arguments."""
    return f"{entry_point}({', '.join(repr(arg) for arg in args)})"


@dataclass(frozen=True)
class FailingCase:
    """One failing development test, in the form prompts show it.

    ``got`` is the runner's preview text of the returned value; it is ``None``
    when the call raised, timed out, or never ran, in which case ``error``
    holds the runner's description.
    """

    inputs: tuple[Any, ...]
    expected: Any
    got: str | None
    error: str | None

    def render(self, entry_point: str) -> str:
        """One line: call, expected value, and what happened instead."""
        call = render_call(entry_point, self.inputs)
        if self.error is None:
            return f"{call} expected {self.expected!r} but got {self.got}"
        if self.error.startswith(("timed out", "not run")):
            return f"{call} expected {self.expected!r} but {self.error}"
        return f"{call} expected {self.expected!r} but raised {self.error}"

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy."""
        return {
            "inputs": list(self.inputs),
            "expected": self.expected,
            "got": self.got,
            "error": self.error,
        }


@dataclass
class CodeEvaluation:
    """Exact environment feedback for one candidate program on one task."""

    task_id: str
    blocked: bool
    block_reason: str | None
    compile_ok: bool
    compile_error: str | None
    dev_passed: int
    dev_total: int
    hidden_passed: int
    hidden_total: int
    all_hidden_passed: bool
    dev_timed_out: bool
    hidden_timed_out: bool
    wall_time_s: float
    executions: int
    failing_dev_count: int
    failing_dev_cases: list[FailingCase] = field(default_factory=list)
    dev_run: dict[str, Any] | None = None
    hidden_run: dict[str, Any] | None = None

    @property
    def valid(self) -> bool:
        """True when the program loaded and was not blocked."""
        return self.compile_ok and not self.blocked

    @property
    def timed_out(self) -> bool:
        """True when either test run hit the time limit."""
        return self.dev_timed_out or self.hidden_timed_out

    @property
    def progress(self) -> float:
        """Fraction of development tests passed, in ``[0, 1]``."""
        return self.dev_passed / self.dev_total if self.dev_total else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy (includes both raw run records)."""
        return {
            "task_id": self.task_id,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "compile_ok": self.compile_ok,
            "compile_error": self.compile_error,
            "dev_passed": self.dev_passed,
            "dev_total": self.dev_total,
            "hidden_passed": self.hidden_passed,
            "hidden_total": self.hidden_total,
            "all_hidden_passed": self.all_hidden_passed,
            "timed_out": self.timed_out,
            "dev_timed_out": self.dev_timed_out,
            "hidden_timed_out": self.hidden_timed_out,
            "wall_time_s": self.wall_time_s,
            "executions": self.executions,
            "failing_dev_count": self.failing_dev_count,
            "failing_dev_cases": [case.to_dict() for case in self.failing_dev_cases],
            "dev_run": self.dev_run,
            "hidden_run": self.hidden_run,
        }


def evaluate_program(
    task: Task,
    program_source: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    memory_mb: int | None = DEFAULT_MEMORY_MB,
    max_failing_cases: int = MAX_FAILING_DEV_CASES,
) -> CodeEvaluation:
    """Run the development and hidden tests and summarise the result.

    The two test sets run in separate child processes so a hang inside one
    development test cannot hide the hidden-test outcome. The hidden run is
    skipped when the development run already shows the program does not load.
    """
    dev = run_tests(
        program_source, task.entry_point, task.dev_tests, timeout_s, memory_mb, float_tolerance=task.float_tolerance
    )
    hidden: RunResult | None = None
    if dev.compile_ok:
        hidden = run_tests(
            program_source, task.entry_point, task.hidden_tests, timeout_s, memory_mb,
            float_tolerance=task.float_tolerance,
        )

    failing = [
        FailingCase(
            inputs=tuple(case.args),
            expected=case.expected,
            got=outcome.got,
            error=outcome.error,
        )
        for case, outcome in zip(task.dev_tests, dev.outcomes)
        if not outcome.passed
    ]
    hidden_passed = hidden.passed if hidden is not None else 0
    hidden_total = len(task.hidden_tests)
    return CodeEvaluation(
        task_id=task.id,
        blocked=dev.blocked,
        block_reason=dev.block_reason,
        compile_ok=dev.compile_ok,
        compile_error=dev.compile_error,
        dev_passed=dev.passed,
        dev_total=len(task.dev_tests),
        hidden_passed=hidden_passed,
        hidden_total=hidden_total,
        all_hidden_passed=hidden is not None and hidden_total > 0 and hidden_passed == hidden_total,
        dev_timed_out=dev.timed_out,
        hidden_timed_out=hidden.timed_out if hidden is not None else False,
        wall_time_s=dev.wall_time_s + (hidden.wall_time_s if hidden is not None else 0.0),
        executions=dev.executions + (hidden.executions if hidden is not None else 0),
        failing_dev_count=len(failing),
        failing_dev_cases=failing[:max_failing_cases],
        dev_run=dev.to_dict(),
        hidden_run=hidden.to_dict() if hidden is not None else None,
    )


def fitness(evaluation: CodeEvaluation) -> float:
    """Number of failing development tests; lower is better.

    Invalid programs (blocked, syntax error, load error, missing entry point)
    score ``dev_total + 1``, below every program that loads. Tests that timed
    out or never ran count as failing. Hidden tests never enter this value.
    """
    if not evaluation.valid:
        return float(evaluation.dev_total + 1)
    return float(evaluation.dev_total - evaluation.dev_passed)


def success(evaluation: CodeEvaluation) -> bool:
    """The success event: the program passes every hidden test."""
    return evaluation.all_hidden_passed


def realized_bucket(evaluation: CodeEvaluation) -> str:
    """Map the hidden-test pass fraction to one of ``OUTCOME_BUCKETS``.

    ``all_pass``: every hidden test; ``most_pass``: at least half but not all;
    ``some_pass``: at least one but fewer than half; ``none_pass``: none.
    """
    if evaluation.all_hidden_passed:
        return "all_pass"
    if evaluation.hidden_passed * 2 >= evaluation.hidden_total and evaluation.hidden_passed > 0:
        return "most_pass"
    if evaluation.hidden_passed > 0:
        return "some_pass"
    return "none_pass"


def to_common_record(evaluation: CodeEvaluation) -> dict[str, Any]:
    """The evaluation record shape shared by every environment.

    ``valid``: loaded and not blocked; ``success``: the binary success event;
    ``score``: fitness, lower is better; ``progress``: development pass
    fraction in ``[0, 1]``; ``cost``: number of test executions; ``details``:
    the full evaluation.
    """
    return {
        "valid": evaluation.valid,
        "success": success(evaluation),
        "score": fitness(evaluation),
        "progress": evaluation.progress,
        "cost": evaluation.executions,
        "details": {"environment": ENVIRONMENT_NAME, **evaluation.to_dict()},
    }
