"""Shared pieces of the benchmark loaders: the split rule, task-directory writer, report.

The development/hidden split (``split_cases``) is deterministic and the same
for every benchmark:

1. Test cases are deduplicated by their arguments.
2. A case whose rendered call appears in the task prompt (a docstring
   example) goes to the development set: the model sees it anyway.
3. A case whose rendered ``call expected value`` line is longer than
   ``max_dev_case_chars`` goes to the hidden set: it would bloat prompts.
4. The remaining cases are split by whether the seeded (buggy) program
   passes them. Failing cases alternate development, hidden, development, ...
   starting with development, so at least one failing case is visible to the
   model; passing cases alternate starting with hidden, so the hidden set
   also contains cases the seeded program already passes.
5. Extra inputs from a second source (EvalPlus) are hidden only.

A task is rejected when the seeded program fails no development case, when
the hidden set is empty, or when ``validate_task`` finds a problem.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from ..evaluation import render_call
from ..runner import DEFAULT_MEMORY_MB, DEFAULT_TIMEOUT_S, TestCase, run_tests
from ..tasks import (
    DEV_TESTS_FILE,
    HIDDEN_TESTS_FILE,
    REFERENCE_FILE,
    SEEDED_FILE,
    TASK_FILE,
    load_task,
    validate_task,
)

DEFAULT_MAX_DEV_CASE_CHARS = 400


@dataclass(frozen=True)
class SplitRule:
    """Parameters of the split; recorded in every ``index.json``."""

    max_dev_case_chars: int = DEFAULT_MAX_DEV_CASE_CHARS
    seed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"max_dev_case_chars": self.max_dev_case_chars, "seed": self.seed}


@dataclass
class BuiltTask:
    """Everything needed to write one task directory."""

    id: str
    entry_point: str
    prompt: str
    reference_source: str
    seeded_source: str
    dev_tests: list[TestCase]
    hidden_tests: list[TestCase]
    float_tolerance: float = 0.0
    source: dict[str, Any] = field(default_factory=dict)
    split_notes: dict[str, Any] = field(default_factory=dict)


@dataclass
class BuildReport:
    """What a loader built and what it rejected, with reasons."""

    benchmark: str
    output_root: Path
    built: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "output_root": str(self.output_root),
            "n_built": len(self.built),
            "n_rejected": len(self.rejected),
            "built": self.built,
            "rejected": self.rejected,
        }


def _args_key(args: Sequence[Any]) -> str:
    return json.dumps(list(args), sort_keys=True, default=str)


def dedupe_cases(cases: Sequence[TestCase]) -> list[TestCase]:
    """Drop cases that repeat the arguments of an earlier case."""
    seen: set[str] = set()
    kept: list[TestCase] = []
    for case in cases:
        key = _args_key(case.args)
        if key in seen:
            continue
        seen.add(key)
        kept.append(case)
    return kept


def split_cases(
    cases: Sequence[TestCase],
    seeded_source: str,
    entry_point: str,
    prompt: str,
    *,
    rule: SplitRule = SplitRule(),
    float_tolerance: float = 0.0,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    memory_mb: int | None = DEFAULT_MEMORY_MB,
) -> tuple[list[TestCase], list[TestCase], dict[str, Any]]:
    """Split ``cases`` into (development, hidden) per the module rule.

    Returns the two lists and a dictionary of notes (which cases were forced
    where, and how many of each the seeded program fails).
    """
    cases = dedupe_cases(cases)
    seeded = run_tests(seeded_source, entry_point, cases, timeout_s, memory_mb, float_tolerance=float_tolerance)
    passed = {outcome.index: outcome.passed for outcome in seeded.outcomes}

    dev: list[TestCase] = []
    hidden: list[TestCase] = []
    forced_dev: list[int] = []
    forced_hidden: list[int] = []
    failing_free: list[tuple[int, TestCase]] = []
    passing_free: list[tuple[int, TestCase]] = []
    for index, case in enumerate(cases):
        call = render_call(entry_point, case.args)
        if call in prompt:
            dev.append(case)
            forced_dev.append(index)
        elif len(f"{call} expected {case.expected!r}") > rule.max_dev_case_chars:
            hidden.append(case)
            forced_hidden.append(index)
        elif passed.get(index, False):
            passing_free.append((index, case))
        else:
            failing_free.append((index, case))

    for position, (_, case) in enumerate(failing_free):
        (dev if position % 2 == 0 else hidden).append(case)
    for position, (_, case) in enumerate(passing_free):
        (hidden if position % 2 == 0 else dev).append(case)

    notes = {
        "n_cases": len(cases),
        "seeded_loaded": seeded.compile_ok,
        "seeded_failing": sum(1 for value in passed.values() if not value),
        "forced_dev_by_prompt_example": forced_dev,
        "forced_hidden_by_length": forced_hidden,
        "n_dev": len(dev),
        "n_hidden": len(hidden),
    }
    return dev, hidden, notes


def feasible_cases(
    reference_source: str,
    entry_point: str,
    cases: Sequence[TestCase],
    *,
    float_tolerance: float = 0.0,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    memory_mb: int | None = DEFAULT_MEMORY_MB,
) -> tuple[list[TestCase], list[dict[str, Any]]]:
    """Keep the cases the reference passes within the runner's limits, one child per case.

    Benchmarks sometimes ship a case their own reference cannot finish under a
    small time or memory budget (QuixBugs' naive Levenshtein on long strings,
    a knapsack with a huge capacity). Such cases would make the task fail
    validation, so they are dropped here and reported.
    """
    kept: list[TestCase] = []
    dropped: list[dict[str, Any]] = []
    for case in cases:
        result = run_tests(
            reference_source, entry_point, [case], timeout_s, memory_mb, float_tolerance=float_tolerance
        )
        outcome = result.outcomes[0] if result.outcomes else None
        if outcome is not None and outcome.passed:
            kept.append(case)
        else:
            reason = outcome.error if outcome is not None and outcome.error else (result.compile_error or "reference output differs")
            dropped.append({"args": list(case.args), "reason": reason})
    return kept, dropped


def render_tests_file(cases: Sequence[TestCase], header: str) -> str:
    """Render the ``TESTS = [...]`` literal file used by the task format."""
    lines = [f"# {line}" for line in header.splitlines()]
    lines.append("TESTS = [")
    for case in cases:
        lines.append(f"    ({_literal(tuple(case.args))}, {_literal(case.expected)}),")
    lines.append("]")
    return "\n".join(lines) + "\n"


def _literal(value: Any) -> str:
    """``repr`` for the JSON-transportable values the format allows (tuples kept as tuples)."""
    if isinstance(value, tuple):
        inner = ", ".join(_literal(item) for item in value)
        return f"({inner},)" if len(value) == 1 else f"({inner})"
    if isinstance(value, list):
        return "[" + ", ".join(_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_literal(k)}: {_literal(v)}" for k, v in value.items()) + "}"
    return repr(value)


def write_task_dir(task: BuiltTask, root: Path) -> Path:
    """Write ``task`` as a task directory under ``root`` and return its path."""
    path = root / task.id
    path.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {
        "id": task.id,
        "entry_point": task.entry_point,
        "language": "python",
        "prompt": task.prompt,
    }
    if task.float_tolerance:
        meta["float_tolerance"] = task.float_tolerance
    if task.source:
        meta["source"] = task.source
    (path / TASK_FILE).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (path / REFERENCE_FILE).write_text(_ensure_newline(task.reference_source), encoding="utf-8")
    (path / SEEDED_FILE).write_text(_ensure_newline(task.seeded_source), encoding="utf-8")
    (path / DEV_TESTS_FILE).write_text(
        render_tests_file(
            task.dev_tests,
            "Development tests: (tuple of positional arguments, expected return value).\n"
            "This file is parsed as literals, never executed. The model may see these.",
        ),
        encoding="utf-8",
    )
    (path / HIDDEN_TESTS_FILE).write_text(
        render_tests_file(
            task.hidden_tests,
            "Hidden tests: (tuple of positional arguments, expected return value).\n"
            "Never shown to the model; these decide success.",
        ),
        encoding="utf-8",
    )
    return path


def _ensure_newline(text: str) -> str:
    return text if text.endswith("\n") else text + "\n"


def keep_prompt_examples_out_of_hidden(built: BuiltTask) -> int:
    """Move hidden cases whose call appears in the prompt to the development set.

    Extra hidden inputs (EvalPlus) can coincide with a docstring example; a
    prompt that mentions a hidden call would trip the leak guard at run time.
    Returns the number of cases moved.
    """
    dev_keys = {_args_key(case.args) for case in built.dev_tests}
    kept: list[TestCase] = []
    moved = 0
    for case in built.hidden_tests:
        if render_call(built.entry_point, case.args) in built.prompt or repr((tuple(case.args), case.expected)) in built.prompt:
            moved += 1
            if _args_key(case.args) not in dev_keys:
                built.dev_tests.append(case)
                dev_keys.add(_args_key(case.args))
        else:
            kept.append(case)
    built.hidden_tests = kept
    return moved


def add_extra_defects(
    built: BuiltTask,
    k: int,
    seed: int,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    memory_mb: int | None = DEFAULT_MEMORY_MB,
) -> bool:
    """Inject ``k`` further defects into the seeded program (see ``defects``); False when impossible."""
    from .defects import inject_defects

    rng = random.Random(f"{seed}:{built.id}")
    result = inject_defects(
        built.reference_source, built.seeded_source, built.entry_point, built.dev_tests, built.hidden_tests, k, rng,
        float_tolerance=built.float_tolerance, timeout_s=timeout_s, memory_mb=memory_mb,
    )
    if result is None:
        return False
    built.seeded_source, descriptions = result
    built.id = f"{built.id}_d{k}"
    built.source["extra_defects"] = descriptions
    built.source["extra_defects_seed"] = seed
    return True


def finish_task(
    built: BuiltTask,
    root: Path,
    report: BuildReport,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    memory_mb: int | None = DEFAULT_MEMORY_MB,
    extra_defects: int = 0,
    defect_seed: int = 0,
) -> bool:
    """Write, reload and validate ``built``; record it in ``report``; remove it if rejected."""
    moved = keep_prompt_examples_out_of_hidden(built)
    if moved:
        built.split_notes["moved_to_dev_because_in_prompt"] = moved
    if extra_defects > 0 and not add_extra_defects(built, extra_defects, defect_seed, timeout_s=timeout_s, memory_mb=memory_mb):
        report.rejected.append({"id": built.id, "reason": f"could not inject {extra_defects} extra defects", **built.split_notes})
        return False
    if not built.hidden_tests:
        report.rejected.append({"id": built.id, "reason": "no hidden tests after the split", **built.split_notes})
        return False
    if not built.dev_tests:
        report.rejected.append({"id": built.id, "reason": "no development tests after the split", **built.split_notes})
        return False
    path = write_task_dir(built, root)
    try:
        task = load_task(path)
        validation = validate_task(task, timeout_s, memory_mb)
    except Exception as exc:  # a malformed task must never stop the batch
        _remove_task_dir(path)
        report.rejected.append({"id": built.id, "reason": f"could not load: {exc}", **built.split_notes})
        return False
    if not validation.ok:
        _remove_task_dir(path)
        report.rejected.append({"id": built.id, "reason": "; ".join(validation.problems), **built.split_notes})
        return False
    report.built.append(
        {
            "id": built.id,
            "entry_point": built.entry_point,
            "n_dev": len(built.dev_tests),
            "n_hidden": len(built.hidden_tests),
            "seeded_dev_failing": len(validation.seeded_failing_dev_indices),
            "float_tolerance": built.float_tolerance,
            "source": built.source,
            **built.split_notes,
        }
    )
    return True


def _remove_task_dir(path: Path) -> None:
    for child in path.iterdir():
        child.unlink()
    path.rmdir()


def write_index(report: BuildReport, rule: SplitRule, extra: dict[str, Any] | None = None) -> Path:
    """Write ``index.json`` (built tasks + split rule) and ``rejected.json`` under the output root."""
    report.output_root.mkdir(parents=True, exist_ok=True)
    index = {
        "benchmark": report.benchmark,
        "split_rule": rule.to_dict(),
        "n_tasks": len(report.built),
        "tasks": report.built,
    }
    if extra:
        index.update(extra)
    index_path = report.output_root / "index.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (report.output_root / "rejected.json").write_text(
        json.dumps({"benchmark": report.benchmark, "rejected": report.rejected}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return index_path
