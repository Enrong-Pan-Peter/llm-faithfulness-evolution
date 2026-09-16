"""Isolated test execution for candidate programs.

``run_tests`` executes a candidate program in a fresh interpreter process and
grades it against explicit ``(arguments, expected)`` test cases. The child
process imports nothing from this repository: the whole child program is the
string ``_CHILD_SCRIPT`` below, which is written into a temporary directory and
started with ``python -I -S`` (ignore environment variables and user site, no
``site`` module, no script directory on ``sys.path``). Test cases travel to the
child as a JSON payload on stdin and results come back as JSON lines on stdout,
one line per test, so a run that is killed mid-way still yields the results of
the tests that finished. The parent never evaluates text taken from the child.

Isolation layers, weakest to strongest:

1. ``scan_program`` is a coarse static filter that refuses to start a process
   for source that imports obviously dangerous modules or opens files for
   writing. It is a convenience guard, not a security boundary.
2. Inside the child, ``import`` is limited to ``DEFAULT_ALLOWED_MODULES`` and a
   few builtins (``open``, ``exec``, ``eval``, ...) are removed from the
   candidate's namespace.
3. On POSIX the child gets CPU-time, address-space, file-size and process
   limits through ``resource`` before it starts (skipped on Windows).
4. The parent enforces a hard wall-clock limit and kills the child.

None of these stops a determined adversary; the runner is meant for model
output produced during a research run on a machine the researcher controls.
"""

from __future__ import annotations

import ast
import json
import math
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

try:  # POSIX only; absent on Windows.
    import resource
except ImportError:  # pragma: no cover - exercised only on Windows
    resource = None  # type: ignore[assignment]


DEFAULT_TIMEOUT_S = 5.0
DEFAULT_MEMORY_MB = 256
DEFAULT_MAX_TEXT_CHARS = 200
CHILD_RECURSION_LIMIT = 5000
STDERR_TAIL_CHARS = 1000

# Modules a candidate may import inside the child. Everything else raises
# ImportError at the import statement.
DEFAULT_ALLOWED_MODULES: frozenset[str] = frozenset(
    {
        "__future__",
        "abc",
        "array",
        "bisect",
        "cmath",
        "collections",
        "contextlib",
        "copy",
        "dataclasses",
        "datetime",
        "decimal",
        "enum",
        "fractions",
        "functools",
        "heapq",
        "itertools",
        "json",
        "math",
        "numbers",
        "operator",
        "random",
        "re",
        "statistics",
        "string",
        "textwrap",
        "typing",
        "unicodedata",
    }
)

# Builtins removed from the candidate's namespace inside the child.
REMOVED_BUILTINS: tuple[str, ...] = (
    "open",
    "exec",
    "eval",
    "compile",
    "input",
    "breakpoint",
    "exit",
    "quit",
    "help",
)

# Static filter vocabulary (see ``scan_program``).
BLOCKED_MODULES: frozenset[str] = frozenset(
    {
        "builtins",
        "ctypes",
        "http",
        "importlib",
        "marshal",
        "multiprocessing",
        "os",
        "pathlib",
        "pickle",
        "requests",
        "resource",
        "shutil",
        "signal",
        "socket",
        "subprocess",
        "sys",
        "threading",
        "urllib",
    }
)
BLOCKED_CALL_NAMES: frozenset[str] = frozenset(
    {"exec", "eval", "compile", "__import__", "breakpoint", "input"}
)
BLOCKED_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "__builtins__",
        "__closure__",
        "__code__",
        "__globals__",
        "__import__",
        "__loader__",
        "__spec__",
        "__subclasses__",
    }
)
_WRITE_MODE_CHARS = "wax+"


@dataclass(frozen=True)
class TestCase:
    """One test: the function is called with ``*args`` and must return ``expected``.

    Both fields must be JSON-transportable (``None``, bool, int, finite float,
    str, lists/tuples of these, dicts with string keys). Tuples arrive in the
    child as lists, and the child compares tuples and lists as equal.
    """

    args: tuple[Any, ...]
    expected: Any


@dataclass(frozen=True)
class TestOutcome:
    """Result of one test case inside a run."""

    index: int
    passed: bool
    ran: bool
    got: str | None
    error: str | None
    time_s: float | None
    value: Any = None
    value_ok: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy (the recorded value is left out)."""
        return {
            "index": self.index,
            "passed": self.passed,
            "ran": self.ran,
            "got": self.got,
            "error": self.error,
            "time_s": self.time_s,
        }


@dataclass
class RunResult:
    """Everything the parent learned from one child run.

    ``stage`` is one of ``"blocked"``, ``"syntax_error"``, ``"load_error"``,
    ``"missing_entry_point"``, ``"no_result"`` or ``"ran"``. ``compile_ok`` is
    true only for ``"ran"``: the source compiled, executed at module level and
    defined a callable named after the entry point. ``outcomes`` always has one
    entry per submitted test; entries for tests that never started have
    ``ran=False``.
    """

    stage: str
    blocked: bool
    block_reason: str | None
    compile_ok: bool
    compile_error: str | None
    timed_out: bool
    completed: bool
    wall_time_s: float
    exit_code: int | None
    stderr_tail: str
    outcomes: list[TestOutcome] = field(default_factory=list)

    @property
    def passed(self) -> int:
        """Number of passing tests."""
        return sum(1 for outcome in self.outcomes if outcome.passed)

    @property
    def total(self) -> int:
        """Number of submitted tests."""
        return len(self.outcomes)

    @property
    def executions(self) -> int:
        """Number of tests the child started executing."""
        return sum(1 for outcome in self.outcomes if outcome.ran)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy for run records."""
        return {
            "stage": self.stage,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "compile_ok": self.compile_ok,
            "compile_error": self.compile_error,
            "timed_out": self.timed_out,
            "completed": self.completed,
            "wall_time_s": self.wall_time_s,
            "exit_code": self.exit_code,
            "stderr_tail": self.stderr_tail,
            "passed": self.passed,
            "total": self.total,
            "executions": self.executions,
            "tests": [outcome.to_dict() for outcome in self.outcomes],
        }


# The complete child program. It must stay independent of this repository.
_CHILD_SCRIPT = r'''
"""Test-runner child: loads one candidate and grades it on the payload's tests."""
import builtins
import json
import reprlib
import sys
import time


class _Sink:
    """Swallows anything the candidate prints so protocol lines stay intact."""

    def write(self, text):
        return len(text)

    def flush(self):
        return None


def _emit(record):
    _PROTOCOL_OUT.write(json.dumps(record) + "\n")
    _PROTOCOL_OUT.flush()


def _clip(text, limit):
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _exception_text(exc, limit):
    return _clip("%s: %s" % (type(exc).__name__, exc), limit)


def _preview(value, limit):
    shortener = reprlib.Repr()
    shortener.maxstring = limit
    shortener.maxother = limit
    shortener.maxlist = shortener.maxtuple = shortener.maxset = shortener.maxdict = 25
    try:
        text = shortener.repr(value)
    except Exception as exc:
        text = "<repr failed: %s>" % type(exc).__name__
    return _clip(text, limit)


_MAX_GENERATOR_ITEMS = 100000


def _normalize(value):
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (str, bytes, bool, int, float)) or value is None:
        return value
    if hasattr(value, "__next__") and hasattr(value, "__iter__"):
        # A generator or iterator: compare what it yields, as a list.
        items = []
        for item in value:
            items.append(_normalize(item))
            if len(items) > _MAX_GENERATOR_ITEMS:
                raise RuntimeError("the function yielded more than %d items" % _MAX_GENERATOR_ITEMS)
        return items
    return value


def _same(left, right, tolerance):
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if left == right:
            return True
        return tolerance > 0 and abs(left - right) <= tolerance
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_same(a, b, tolerance) for a, b in zip(left, right))
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same(left[k], right[k], tolerance) for k in left)
    try:
        return bool(left == right)
    except Exception:
        return False


def _transportable(value):
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError, OverflowError):
        return False
    return True


def _guarded_import(allowed):
    real_import = builtins.__import__

    def guarded(name, globals=None, locals=None, fromlist=(), level=0):
        if level != 0 or name.split(".")[0] not in allowed:
            raise ImportError("import of %r is not permitted in the test runner" % name)
        return real_import(name, globals, locals, fromlist, level)

    return guarded


def main():
    payload = json.loads(sys.stdin.read())
    limit = int(payload["max_text_chars"])
    tolerance = float(payload.get("float_tolerance", 0.0))
    record_values = bool(payload.get("record_values", False))
    sys.setrecursionlimit(int(payload["recursion_limit"]))
    safe_builtins = dict(vars(builtins))
    safe_builtins["__import__"] = _guarded_import(set(payload["allowed_modules"]))
    for name in payload["removed_builtins"]:
        safe_builtins.pop(name, None)
    namespace = {"__name__": "candidate", "__builtins__": safe_builtins}
    try:
        code = compile(payload["program"], "<candidate>", "exec")
    except Exception as exc:
        _emit({"kind": "syntax_error", "error": _exception_text(exc, limit)})
        return
    try:
        exec(code, namespace)
    except BaseException as exc:
        _emit({"kind": "load_error", "error": _exception_text(exc, limit)})
        return
    function = namespace.get(payload["entry_point"])
    if not callable(function):
        _emit({"kind": "missing_entry_point"})
        return
    _emit({"kind": "loaded"})
    for index, case in enumerate(payload["tests"]):
        started = time.perf_counter()
        try:
            got = _normalize(function(*case["args"]))
            passed = _same(got, _normalize(case["expected"]), tolerance)
            record = {"kind": "test", "index": index, "passed": passed,
                      "got": _preview(got, limit), "error": None}
            if record_values and _transportable(got):
                record["value"] = got
                record["value_ok"] = True
        except BaseException as exc:
            record = {"kind": "test", "index": index, "passed": False,
                      "got": None, "error": _exception_text(exc, limit)}
        record["time_s"] = time.perf_counter() - started
        _emit(record)
    _emit({"kind": "done"})


_PROTOCOL_OUT = sys.stdout
sys.stdout = _Sink()
main()
'''


def scan_program(source: str) -> str | None:
    """Return a reason to refuse ``source`` without running it, or ``None``.

    This is a coarse static filter over the syntax tree: blocked module
    imports, calls to ``exec``/``eval``/``compile``/``__import__``, ``open``
    with a write mode (or a mode that is not a literal), and access to a few
    introspection attributes. Source that does not parse gets a line-based
    check of its import statements only (so a blocked import is reported as
    ``blocked`` whatever else is wrong with the source); everything else about
    unparsable source is left to the child, which reports the syntax error.
    This is not a security boundary.
    """
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return _scan_import_lines(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BLOCKED_MODULES:
                    return f"blocked import: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if node.level or root in BLOCKED_MODULES:
                return f"blocked import: from {node.module or '.'}"
        elif isinstance(node, ast.Attribute) and node.attr in BLOCKED_ATTRIBUTES:
            return f"blocked attribute: {node.attr}"
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BLOCKED_CALL_NAMES:
                return f"blocked call: {node.func.id}()"
            if node.func.id == "open" and _opens_for_writing(node):
                return "blocked call: open() with a write mode"
    return None


_IMPORT_LINE = re.compile(r"^\s*(?:import\s+([\w.]+)|from\s+(\.*[\w.]*)\s+import\b)")


def _scan_import_lines(source: str) -> str | None:
    """Line-based import check for source that does not parse."""
    for line in source.splitlines():
        match = _IMPORT_LINE.match(line)
        if match is None:
            continue
        if match.group(1) is not None:
            if match.group(1).split(".")[0] in BLOCKED_MODULES:
                return f"blocked import: {match.group(1)}"
        else:
            module = match.group(2)
            if module.startswith(".") or module.split(".")[0] in BLOCKED_MODULES:
                return f"blocked import: from {module or '.'}"
    return None


def _opens_for_writing(call: ast.Call) -> bool:
    """True when an ``open(...)`` call's mode is not a literal read-only mode."""
    mode_node: ast.expr | None = None
    if len(call.args) >= 2:
        mode_node = call.args[1]
    for keyword in call.keywords:
        if keyword.arg == "mode":
            mode_node = keyword.value
    if mode_node is None:
        return False
    if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
        return any(char in mode_node.value for char in _WRITE_MODE_CHARS)
    return True


def run_tests(
    program_source: str,
    entry_point: str,
    tests: Sequence[TestCase],
    timeout_s: float = DEFAULT_TIMEOUT_S,
    memory_mb: int | None = DEFAULT_MEMORY_MB,
    *,
    allowed_modules: frozenset[str] = DEFAULT_ALLOWED_MODULES,
    max_text_chars: int = DEFAULT_MAX_TEXT_CHARS,
    float_tolerance: float = 0.0,
    record_values: bool = False,
) -> RunResult:
    """Run ``tests`` against ``entry_point`` defined by ``program_source``.

    ``timeout_s`` is the wall-clock budget for the whole run (interpreter
    start-up included); on expiry the child is killed and the tests that did
    not report are marked as failed. ``memory_mb`` bounds the child's address
    space on POSIX and is ignored where ``resource`` is unavailable.
    ``float_tolerance`` is the absolute tolerance used when two numbers are
    compared (0 means exact). A function that returns a generator is graded on
    the list of what it yields. With ``record_values`` the JSON-transportable
    return values come back in ``TestOutcome.value`` (``value_ok`` says whether
    one was recorded); that is how benchmark loaders compute expected outputs
    from a reference solution.
    """
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    started = time.perf_counter()
    reason = scan_program(program_source)
    if reason is not None:
        return RunResult(
            stage="blocked",
            blocked=True,
            block_reason=reason,
            compile_ok=False,
            compile_error=None,
            timed_out=False,
            completed=False,
            wall_time_s=time.perf_counter() - started,
            exit_code=None,
            stderr_tail="",
            outcomes=_unreported_outcomes(len(tests), 0, "not run: blocked"),
        )

    payload = _encode_payload(
        program_source, entry_point, tests, allowed_modules, max_text_chars, float_tolerance, record_values
    )
    stdout, stderr, exit_code, timed_out = _spawn_child(payload, timeout_s, memory_mb)
    wall_time_s = time.perf_counter() - started
    if resource is not None and exit_code is not None and exit_code == -int(signal.SIGXCPU):
        timed_out = True
    return _collect(stdout, stderr, exit_code, timed_out, wall_time_s, len(tests))


def _encode_payload(
    program_source: str,
    entry_point: str,
    tests: Sequence[TestCase],
    allowed_modules: frozenset[str],
    max_text_chars: int,
    float_tolerance: float = 0.0,
    record_values: bool = False,
) -> bytes:
    payload = {
        "program": program_source,
        "entry_point": entry_point,
        "tests": [{"args": list(case.args), "expected": case.expected} for case in tests],
        "allowed_modules": sorted(allowed_modules),
        "removed_builtins": list(REMOVED_BUILTINS),
        "max_text_chars": max_text_chars,
        "recursion_limit": CHILD_RECURSION_LIMIT,
        "float_tolerance": float(float_tolerance),
        "record_values": bool(record_values),
    }
    try:
        return json.dumps(payload, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError(f"test cases must be JSON-transportable: {exc}") from exc


def _child_environment() -> dict[str, str]:
    """Minimal environment for the child: locale only, plus what Windows needs."""
    env = {"LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}
    for key in ("SYSTEMROOT", "SystemRoot"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _limit_setter(timeout_s: float, memory_mb: int | None) -> Callable[[], None]:
    """Build the pre-exec function that applies POSIX resource limits."""
    cpu_seconds = int(math.ceil(timeout_s)) + 1
    address_space = None if memory_mb is None else int(memory_mb) * 1024 * 1024

    def apply_limits() -> None:
        _set_limit(resource.RLIMIT_CPU, cpu_seconds)
        if address_space is not None:
            _set_limit(resource.RLIMIT_AS, address_space)
        _set_limit(resource.RLIMIT_FSIZE, 1024 * 1024)
        _set_limit(resource.RLIMIT_CORE, 0)
        _set_limit(resource.RLIMIT_NPROC, 0)

    return apply_limits


def _set_limit(kind: int, value: int) -> None:
    """Lower one limit to ``value`` (never above the current hard limit)."""
    _, hard = resource.getrlimit(kind)
    if hard != resource.RLIM_INFINITY:
        value = min(value, hard)
    try:
        resource.setrlimit(kind, (value, value))
    except (ValueError, OSError):
        pass


def _spawn_child(
    payload: bytes, timeout_s: float, memory_mb: int | None
) -> tuple[bytes, bytes, int | None, bool]:
    """Start the child, feed it the payload and return (stdout, stderr, exit code, timed out)."""
    with tempfile.TemporaryDirectory(prefix="code_repair_") as temp_dir:
        script_path = Path(temp_dir) / "child_runner.py"
        script_path.write_text(_CHILD_SCRIPT, encoding="utf-8")
        work_dir = Path(temp_dir) / "work"
        work_dir.mkdir()
        command = [sys.executable, "-I", "-S", "-X", "utf8", str(script_path)]
        preexec = _limit_setter(timeout_s, memory_mb) if resource is not None else None
        try:
            completed = subprocess.run(
                command,
                input=payload,
                capture_output=True,
                cwd=str(work_dir),
                env=_child_environment(),
                timeout=timeout_s,
                preexec_fn=preexec,
            )
        except subprocess.TimeoutExpired as exc:
            return exc.stdout or b"", exc.stderr or b"", None, True
        return completed.stdout, completed.stderr, completed.returncode, False


def _collect(
    stdout: bytes,
    stderr: bytes,
    exit_code: int | None,
    timed_out: bool,
    wall_time_s: float,
    n_tests: int,
) -> RunResult:
    """Turn the child's JSON lines into a ``RunResult``."""
    stage = "no_result"
    compile_error: str | None = None
    completed = False
    reported: dict[int, dict[str, Any]] = {}
    for line in stdout.decode("utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict):
            continue
        kind = record.get("kind")
        if kind == "syntax_error":
            stage, compile_error = "syntax_error", str(record.get("error"))
        elif kind == "load_error":
            stage, compile_error = "load_error", f"error while loading the program: {record.get('error')}"
        elif kind == "missing_entry_point":
            stage, compile_error = "missing_entry_point", "the program does not define the entry point"
        elif kind == "loaded":
            stage = "ran"
        elif kind == "test" and isinstance(record.get("index"), int):
            reported[record["index"]] = record
        elif kind == "done":
            completed = True

    stderr_tail = stderr.decode("utf-8", errors="replace")[-STDERR_TAIL_CHARS:]
    if stage == "no_result":
        if timed_out:
            compile_error = "the runner timed out before the program was loaded"
        else:
            compile_error = f"the runner produced no result (exit code {exit_code}): {stderr_tail.strip()}"

    if stage == "ran":
        outcomes = _merge_outcomes(reported, n_tests, timed_out, exit_code)
    else:
        outcomes = _unreported_outcomes(n_tests, 0, f"not run: {stage}")

    return RunResult(
        stage=stage,
        blocked=False,
        block_reason=None,
        compile_ok=stage == "ran",
        compile_error=compile_error,
        timed_out=timed_out,
        completed=completed,
        wall_time_s=wall_time_s,
        exit_code=exit_code,
        stderr_tail=stderr_tail,
        outcomes=outcomes,
    )


def _merge_outcomes(
    reported: dict[int, dict[str, Any]], n_tests: int, timed_out: bool, exit_code: int | None
) -> list[TestOutcome]:
    """Combine reported results with placeholders for tests that never reported."""
    outcomes: list[TestOutcome] = []
    for index in range(n_tests):
        record = reported.get(index)
        if record is None:
            break
        time_s = record.get("time_s")
        outcomes.append(
            TestOutcome(
                index=index,
                passed=bool(record.get("passed")),
                ran=True,
                got=None if record.get("got") is None else str(record["got"]),
                error=None if record.get("error") is None else str(record["error"]),
                time_s=float(time_s) if isinstance(time_s, (int, float)) else None,
                value=record.get("value"),
                value_ok=bool(record.get("value_ok", False)),
            )
        )
    first_missing = len(outcomes)
    if first_missing < n_tests:
        if timed_out:
            outcomes.append(TestOutcome(first_missing, False, True, None, "timed out", None))
            outcomes.extend(_unreported_outcomes(n_tests, first_missing + 1, "not run: timed out"))
        else:
            reason = f"not run: the runner exited with code {exit_code}"
            outcomes.extend(_unreported_outcomes(n_tests, first_missing, reason))
    return outcomes


def _unreported_outcomes(n_tests: int, start: int, reason: str) -> list[TestOutcome]:
    return [TestOutcome(index, False, False, None, reason, None) for index in range(start, n_tests)]


def reference_outputs(
    program_source: str,
    entry_point: str,
    inputs: Sequence[Sequence[Any]],
    timeout_s: float = DEFAULT_TIMEOUT_S,
    memory_mb: int | None = DEFAULT_MEMORY_MB,
    *,
    allowed_modules: frozenset[str] = DEFAULT_ALLOWED_MODULES,
) -> tuple[RunResult, list[Any]]:
    """Run ``program_source`` on ``inputs`` and return its JSON-transportable outputs.

    Used by the benchmark loaders to turn a reference solution plus a list of
    inputs into ``(arguments, expected)`` pairs. The returned list has one
    entry per input: the value, or ``MISSING`` when the call raised, timed
    out, or returned something that cannot travel as JSON.
    """
    cases = [TestCase(args=tuple(args), expected=None) for args in inputs]
    result = run_tests(
        program_source, entry_point, cases, timeout_s, memory_mb,
        allowed_modules=allowed_modules, record_values=True,
    )
    values: list[Any] = []
    for outcome in result.outcomes:
        values.append(outcome.value if (outcome.ran and outcome.error is None and outcome.value_ok) else MISSING)
    return result, values


class _Missing:
    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return "MISSING"


MISSING: Any = _Missing()
