"""HumanEvalFix (HumanEvalPack, Python) to task directories.

HumanEvalPack (Muennighoff et al., 2023; ``bigcode/humanevalpack`` on the
Hugging Face hub, MIT) adds to each of the 164 HumanEval problems a
``buggy_solution``: the canonical solution with one human-inserted bug, tagged
with ``bug_type`` (missing logic, excess logic, value/operator/variable/
function misuse) and ``failure_symptoms`` (incorrect output, stack overflow,
infinite loop). Rows are read from the Python split as published on the hub
(``python/test-00000-of-00001.parquet``; a ``.jsonl`` / ``.jsonl.gz`` export
of the same rows also works) with the fields ``task_id``, ``prompt``, ``declaration``,
``canonical_solution``, ``buggy_solution``, ``bug_type``,
``failure_symptoms``, ``entry_point``, ``test``, ``example_test``, ...).

Per problem:

* ``seeded.py``    — ``declaration`` + ``buggy_solution``;
* ``reference.py`` — ``declaration`` + ``canonical_solution``;
* the prompt       — the HumanEval prompt (signature + docstring with its
  examples);
* tests            — the original HumanEval test inputs (taken from EvalPlus's
  ``base_input`` when an EvalPlus file is given, otherwise extracted from the
  ``assert`` statements of ``test``), with expected outputs computed by running
  the reference in the sandboxed runner, split by ``common.split_cases``;
  plus, when an EvalPlus file is given, up to ``max_plus_hidden`` inputs
  sampled from HumanEval+ (``plus_input``) as extra hidden tests.

EvalPlus (Liu et al., 2023) publishes ``HumanEvalPlus.jsonl.gz`` on GitHub
(``evalplus/humanevalplus_release``); its ``atol`` becomes the task's
``float_tolerance``.
"""

from __future__ import annotations

import ast
import gzip
import json
import random
from pathlib import Path
from typing import Any, Iterable

from ..runner import DEFAULT_MEMORY_MB, DEFAULT_TIMEOUT_S, MISSING, TestCase, reference_outputs
from .common import BuildReport, BuiltTask, SplitRule, dedupe_cases, finish_task, split_cases, write_index

BENCHMARK = "humanevalfix"
DEFAULT_MAX_PLUS_HIDDEN = 20
MAX_INPUT_JSON_CHARS = 2000
SMALL_FLOAT_TOLERANCE = 1e-9
REQUIRED_PACK_KEYS = ("task_id", "prompt", "declaration", "canonical_solution", "buggy_solution", "entry_point")


class HumanEvalFixFormatError(ValueError):
    """A benchmark file does not look as expected."""


def _open_text(path: Path):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    """Read a ``.jsonl``, ``.jsonl.gz`` or ``.parquet`` file into a list of dictionaries."""
    path = Path(path)
    if path.suffix == ".parquet":
        return _read_parquet(path)
    rows: list[dict[str, Any]] = []
    with _open_text(path) as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise HumanEvalFixFormatError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(row, dict):
                raise HumanEvalFixFormatError(f"{path}:{line_number}: expected an object")
            rows.append(row)
    return rows


def _read_parquet(path: Path) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as parquet  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise HumanEvalFixFormatError(
            f"{path}: reading parquet needs the pyarrow package (pip install pyarrow)"
        ) from exc
    table = parquet.read_table(path)
    rows = table.to_pylist()
    for row in rows:
        for key, value in list(row.items()):
            if isinstance(value, bytes):
                row[key] = value.decode("utf-8")
    return rows


def task_number(task_id: str) -> int:
    """``"Python/12"`` or ``"HumanEval/12"`` -> ``12``."""
    try:
        return int(str(task_id).rsplit("/", 1)[-1])
    except ValueError as exc:
        raise HumanEvalFixFormatError(f"cannot read a task number from {task_id!r}") from exc


def read_humanevalpack(path: Path | str) -> list[dict[str, Any]]:
    """Rows of the HumanEvalPack Python split, checked for the fields the loader needs."""
    rows = read_jsonl(path)
    for row in rows:
        for key in REQUIRED_PACK_KEYS:
            if not isinstance(row.get(key), str):
                raise HumanEvalFixFormatError(f"{path}: row {row.get('task_id')!r} lacks a string field {key!r}")
    return rows


def read_evalplus(path: Path | str) -> dict[int, dict[str, Any]]:
    """HumanEval+ rows keyed by task number."""
    rows = read_jsonl(path)
    by_number: dict[int, dict[str, Any]] = {}
    for row in rows:
        if "task_id" not in row or "plus_input" not in row or "base_input" not in row:
            raise HumanEvalFixFormatError(f"{path}: row {row.get('task_id')!r} is not an EvalPlus HumanEval+ row")
        by_number[task_number(row["task_id"])] = row
    return by_number


def extract_assert_inputs(test_source: str, entry_point: str) -> list[list[Any]]:
    """Inputs of ``assert <entry_point>(<literals>) == ...`` statements in ``test_source``.

    Fallback when no EvalPlus file is given. Only calls whose arguments are
    all literals are used; the expected side is ignored because expected
    outputs are recomputed from the reference.
    """
    try:
        tree = ast.parse(test_source)
    except SyntaxError:
        return []
    names = {entry_point, "candidate"}
    inputs: list[list[Any]] = []

    def call_args(node: ast.AST) -> list[Any] | None:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names and not node.keywords:
            try:
                return [ast.literal_eval(argument) for argument in node.args]
            except (ValueError, SyntaxError):
                return None
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assert):
            continue
        test = node.test
        candidates: list[ast.AST] = []
        if isinstance(test, ast.Compare):
            candidates.append(test.left)
            if isinstance(test.left, ast.Call) and isinstance(test.left.func, ast.Name) and test.left.func.id == "abs":
                inner = test.left.args[0] if test.left.args else None
                if isinstance(inner, ast.BinOp):
                    candidates.append(inner.left)
        elif isinstance(test, ast.Call):
            candidates.append(test)
            candidates.extend(test.args)
        for candidate in candidates:
            arguments = call_args(candidate)
            if arguments is not None:
                inputs.append(arguments)
                break
    return inputs


def _json_ok(value: Any) -> bool:
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return False
    return True


def _cases_from_reference(
    reference: str,
    entry_point: str,
    inputs: Iterable[list[Any]],
    timeout_s: float,
    memory_mb: int | None,
) -> tuple[list[TestCase], list[dict[str, Any]]]:
    """Run the reference on ``inputs``; return the usable cases and the dropped inputs."""
    usable_inputs = [list(args) for args in inputs if _json_ok(args) and len(json.dumps(args)) <= MAX_INPUT_JSON_CHARS]
    if not usable_inputs:
        return [], []
    _, values = reference_outputs(reference, entry_point, usable_inputs, timeout_s, memory_mb)
    cases: list[TestCase] = []
    dropped: list[dict[str, Any]] = []
    for args, value in zip(usable_inputs, values):
        if value is MISSING:
            dropped.append({"args": args, "reason": "reference raised, timed out, or returned a non-JSON value"})
        else:
            cases.append(TestCase(args=tuple(args), expected=value))
    return cases, dropped


def _has_float(value: Any) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, (list, tuple)):
        return any(_has_float(item) for item in value)
    if isinstance(value, dict):
        return any(_has_float(item) for item in value.values())
    return False


def build_humanevalfix_tasks(
    humanevalpack_path: Path | str,
    output_root: Path | str,
    *,
    evalplus_path: Path | str | None = None,
    max_plus_hidden: int = DEFAULT_MAX_PLUS_HIDDEN,
    rule: SplitRule = SplitRule(),
    numbers: list[int] | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    memory_mb: int | None = DEFAULT_MEMORY_MB,
    extra_defects: int = 0,
    defect_seed: int = 0,
) -> BuildReport:
    """Convert HumanEvalFix problems (all, or ``numbers``) into task directories."""
    output_root = Path(output_root)
    report = BuildReport(BENCHMARK, output_root)
    pack_rows = read_humanevalpack(humanevalpack_path)
    plus_rows = read_evalplus(evalplus_path) if evalplus_path else {}
    wanted = set(numbers) if numbers is not None else None
    for row in sorted(pack_rows, key=lambda item: task_number(item["task_id"])):
        number = task_number(row["task_id"])
        if wanted is not None and number not in wanted:
            continue
        task_id = f"{BENCHMARK}_{number:03d}"
        try:
            built = _build_one(row, number, plus_rows.get(number), max_plus_hidden, rule, timeout_s, memory_mb)
        except (HumanEvalFixFormatError, SyntaxError, OSError) as exc:
            report.rejected.append({"id": task_id, "reason": str(exc)})
            continue
        if built is None:
            report.rejected.append({"id": task_id, "reason": "no usable test inputs (reference produced no JSON outputs)"})
            continue
        finish_task(
            built, output_root, report, timeout_s=timeout_s, memory_mb=memory_mb,
            extra_defects=extra_defects, defect_seed=defect_seed,
        )
    extra = {
        "humanevalpack_path": str(humanevalpack_path),
        "evalplus_path": None if evalplus_path is None else str(evalplus_path),
        "max_plus_hidden": max_plus_hidden if evalplus_path else 0,
        "extra_defects": extra_defects,
        "defect_seed": defect_seed,
    }
    write_index(report, rule, extra)
    return report


def _build_one(
    row: dict[str, Any],
    number: int,
    plus_row: dict[str, Any] | None,
    max_plus_hidden: int,
    rule: SplitRule,
    timeout_s: float,
    memory_mb: int | None,
) -> BuiltTask | None:
    entry_point = row["entry_point"]
    declaration = row["declaration"]
    reference = _join(declaration, row["canonical_solution"])
    seeded = _join(declaration, row["buggy_solution"])
    prompt = "Implement the function below.\n\n" + row["prompt"].strip("\n") + "\n"

    if plus_row is not None:
        base_inputs = plus_row["base_input"]
        tolerance = float(plus_row.get("atol") or 0.0)
    else:
        base_inputs = extract_assert_inputs(row.get("test", ""), entry_point)
        tolerance = 0.0
    base_cases, dropped = _cases_from_reference(reference, entry_point, base_inputs, timeout_s, memory_mb)
    base_cases = dedupe_cases(base_cases)
    if not base_cases:
        return None
    if tolerance == 0.0 and any(_has_float(case.expected) for case in base_cases):
        tolerance = SMALL_FLOAT_TOLERANCE

    dev, hidden, notes = split_cases(
        base_cases, seeded, entry_point, prompt, rule=rule, float_tolerance=tolerance,
        timeout_s=timeout_s, memory_mb=memory_mb,
    )
    notes["dropped_base_inputs"] = len(dropped)

    plus_added = 0
    if plus_row is not None and max_plus_hidden > 0:
        known = {json.dumps(list(case.args), sort_keys=True, default=str) for case in base_cases}
        pool = [args for args in plus_row["plus_input"] if json.dumps(list(args), sort_keys=True, default=str) not in known]
        rng = random.Random(rule.seed * 1000 + number)
        rng.shuffle(pool)
        plus_cases, _ = _cases_from_reference(reference, entry_point, pool[: max_plus_hidden * 3], timeout_s, memory_mb)
        plus_cases = dedupe_cases(plus_cases)[:max_plus_hidden]
        hidden.extend(plus_cases)
        plus_added = len(plus_cases)
    notes["plus_hidden_added"] = plus_added
    notes["n_hidden"] = len(hidden)

    source: dict[str, Any] = {
        "benchmark": BENCHMARK,
        "original_id": row["task_id"],
        "humaneval_id": f"HumanEval/{number}",
        "bug_type": row.get("bug_type"),
        "failure_symptoms": row.get("failure_symptoms"),
        "license": "MIT",
        "extra_hidden_inputs": "EvalPlus HumanEval+" if plus_added else None,
    }
    return BuiltTask(
        id=f"{BENCHMARK}_{number:03d}",
        entry_point=entry_point,
        prompt=prompt,
        reference_source=reference,
        seeded_source=seeded,
        dev_tests=dev,
        hidden_tests=hidden,
        float_tolerance=tolerance,
        source=source,
        split_notes=notes,
    )


def _join(declaration: str, body: str) -> str:
    """``declaration`` (imports + ``def`` line) followed by the indented ``body``."""
    declaration = declaration.strip("\n") + "\n"
    return declaration + body.strip("\n") + "\n"
