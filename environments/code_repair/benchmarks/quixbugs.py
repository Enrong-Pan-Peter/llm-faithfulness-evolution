"""QuixBugs (Python) to task directories.

QuixBugs (Lin et al., 2017; github.com/jkoppel/QuixBugs, MIT) ships 40 small
Python programs, each with exactly one defect on one line, a corrected
version, and test cases. This loader uses the programs that have JSON test
cases (``json_testcases/<name>.json``, one ``[arguments, expected]`` per
line); the graph programs whose tests build ``Node`` objects are left out.

Per program:

* ``seeded.py``     — the buggy function from ``python_programs/<name>.py``
  (module-level imports kept, the trailing specification string removed);
* ``reference.py``  — the function from ``correct_python_programs/<name>.py``
  (its trailing string of alternative solutions removed);
* the prompt        — the function signature with the specification string as
  its docstring, exactly the text QuixBugs gives;
* tests             — the JSON cases, split by ``common.split_cases``.

Only ``sqrt`` compares floats loosely: QuixBugs grades it within the
``epsilon`` argument, so the task's ``float_tolerance`` is the largest
epsilon among its cases. Cases the corrected program cannot finish within
the runner's time and memory limits (the exponential ``levenshtein`` on long
strings, ``knapsack`` with a huge capacity) are dropped and listed in the
index under ``dropped_infeasible_for_reference``.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from ..runner import DEFAULT_MEMORY_MB, DEFAULT_TIMEOUT_S, TestCase
from .common import BuildReport, BuiltTask, SplitRule, feasible_cases, finish_task, split_cases, write_index

BENCHMARK = "quixbugs"
PROGRAMS_DIR = "python_programs"
CORRECT_DIR = "correct_python_programs"
CASES_DIR = "json_testcases"
LOOSE_FLOAT_PROGRAMS = ("sqrt",)


class QuixBugsFormatError(ValueError):
    """A QuixBugs file does not look as expected."""


def list_programs(root: Path) -> list[str]:
    """Names of the programs that have JSON test cases, sorted."""
    root = Path(root)
    cases_dir = root / CASES_DIR
    if not cases_dir.is_dir():
        raise QuixBugsFormatError(f"{root}: no {CASES_DIR}/ directory (is this a QuixBugs checkout?)")
    names = []
    for path in sorted(cases_dir.glob("*.json")):
        name = path.stem
        if (root / PROGRAMS_DIR / f"{name}.py").is_file() and (root / CORRECT_DIR / f"{name}.py").is_file():
            names.append(name)
    return names


def read_cases(path: Path) -> list[TestCase]:
    """Read one ``json_testcases`` file: one ``[arguments, expected]`` JSON per line."""
    cases: list[TestCase] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError as exc:
            raise QuixBugsFormatError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
        if not isinstance(entry, list) or len(entry) != 2 or not isinstance(entry[0], list):
            raise QuixBugsFormatError(f"{path}:{line_number}: expected [arguments, expected]")
        cases.append(TestCase(args=tuple(entry[0]), expected=entry[1]))
    return cases


def split_program_source(source: str, name: str) -> tuple[str, str, str]:
    """Return (function source with module imports, signature line, specification text).

    The specification is the module-level string that follows the function in
    the buggy file (absent in the corrected file, where a trailing string holds
    alternative solutions and is dropped).
    """
    tree = ast.parse(source)
    imports: list[str] = []
    function: ast.FunctionDef | None = None
    spec = ""
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append(ast.get_source_segment(source, node) or "")
        elif isinstance(node, ast.FunctionDef) and node.name == name and function is None:
            function = node
        elif (
            function is not None
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and not spec
        ):
            spec = node.value.value
    if function is None:
        raise QuixBugsFormatError(f"no function named {name!r} in the program")
    body = ast.get_source_segment(source, function) or ""
    pieces = [line for line in imports if line]
    pieces.append(body)
    signature = f"def {name}({ast.unparse(function.args)}):"
    return "\n".join(pieces).rstrip("\n") + "\n", signature, spec.strip("\n")


def build_prompt(signature: str, spec: str) -> str:
    """The signature with the QuixBugs specification as its docstring."""
    doc_lines = spec.splitlines() or ["(no specification text)"]
    indented = "\n".join(f"    {line}" if line.strip() else "" for line in doc_lines)
    return f'Implement the function below.\n\n{signature}\n    """\n{indented}\n    """\n'


def build_quixbugs_tasks(
    quixbugs_root: Path | str,
    output_root: Path | str,
    *,
    rule: SplitRule = SplitRule(),
    names: list[str] | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    memory_mb: int | None = DEFAULT_MEMORY_MB,
    extra_defects: int = 0,
    defect_seed: int = 0,
    anonymize: bool = False,
) -> BuildReport:
    """Convert every eligible QuixBugs program (or ``names``) into task directories."""
    root = Path(quixbugs_root)
    output_root = Path(output_root)
    report = BuildReport(BENCHMARK, output_root)
    for name in names or list_programs(root):
        try:
            built = _build_one(root, name, rule, timeout_s, memory_mb)
        except (QuixBugsFormatError, SyntaxError, OSError) as exc:
            report.rejected.append({"id": f"{BENCHMARK}_{name}", "reason": str(exc)})
            continue
        finish_task(
            built, output_root, report, timeout_s=timeout_s, memory_mb=memory_mb,
            extra_defects=extra_defects, defect_seed=defect_seed, anonymize=anonymize,
        )
    write_index(report, rule, {"source_root": str(root), "extra_defects": extra_defects, "defect_seed": defect_seed, "anonymized": anonymize})
    return report


def _build_one(root: Path, name: str, rule: SplitRule, timeout_s: float, memory_mb: int | None) -> BuiltTask:
    buggy_source = (root / PROGRAMS_DIR / f"{name}.py").read_text(encoding="utf-8")
    correct_source = (root / CORRECT_DIR / f"{name}.py").read_text(encoding="utf-8")
    seeded, signature, spec = split_program_source(buggy_source, name)
    reference, _, _ = split_program_source(correct_source, name)
    if not spec:
        raise QuixBugsFormatError(f"{name}: no specification string in the buggy program")
    prompt = build_prompt(signature, spec)
    cases = read_cases(root / CASES_DIR / f"{name}.json")
    tolerance = 0.0
    if name in LOOSE_FLOAT_PROGRAMS:
        tolerance = max(float(case.args[-1]) for case in cases)
    cases, dropped = feasible_cases(
        reference, name, cases, float_tolerance=tolerance, timeout_s=timeout_s, memory_mb=memory_mb
    )
    if not cases:
        raise QuixBugsFormatError(f"{name}: the reference passes none of the cases within the runner's limits")
    dev, hidden, notes = split_cases(
        cases, seeded, name, prompt, rule=rule, float_tolerance=tolerance, timeout_s=timeout_s, memory_mb=memory_mb
    )
    notes["dropped_infeasible_for_reference"] = dropped
    source: dict[str, Any] = {
        "benchmark": BENCHMARK,
        "original_id": name,
        "defect": "one-line defect (QuixBugs)",
        "license": "MIT",
    }
    return BuiltTask(
        id=f"{BENCHMARK}_{name}",
        entry_point=name,
        prompt=prompt,
        reference_source=reference,
        seeded_source=seeded,
        dev_tests=dev,
        hidden_tests=hidden,
        float_tolerance=tolerance,
        source=source,
        split_notes=notes,
    )
