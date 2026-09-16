"""Loaders that turn public bug-repair benchmarks into this package's task format.

* ``quixbugs``: the 40 Python programs of QuixBugs (one defect each), using
  the programs that ship with JSON test cases (the graph programs need
  ``Node`` objects and are left out).
* ``humanevalfix``: the 164 HumanEvalFix problems of HumanEvalPack (a human
  inserted bug in every HumanEval canonical solution), with the original
  HumanEval test inputs and, optionally, extra hidden inputs from EvalPlus's
  HumanEval+.

Both loaders write ordinary task directories (``task.json``, ``reference.py``,
``seeded.py``, ``dev_tests.py``, ``hidden_tests.py``) plus an ``index.json``
describing the split, and reject tasks that fail ``validate_task``. The
development/hidden split rule is in ``common.split_cases``.
"""

from .common import BuildReport, BuiltTask, SplitRule, split_cases, write_task_dir
from .humanevalfix import build_humanevalfix_tasks
from .quixbugs import build_quixbugs_tasks

__all__ = [
    "BuildReport",
    "BuiltTask",
    "SplitRule",
    "build_humanevalfix_tasks",
    "build_quixbugs_tasks",
    "split_cases",
    "write_task_dir",
]
