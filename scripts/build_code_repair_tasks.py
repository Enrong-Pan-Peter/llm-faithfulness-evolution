"""Build code-repair task sets from QuixBugs and HumanEvalFix.

Usage (PowerShell; see task_sets/code_repair/README.md for the downloads):

    python scripts/build_code_repair_tasks.py quixbugs `
        --source data/benchmarks/QuixBugs --output task_sets/code_repair/quixbugs

    python scripts/build_code_repair_tasks.py humanevalfix `
        --source data/benchmarks/humanevalpack_python.jsonl `
        --evalplus data/benchmarks/HumanEvalPlus.jsonl.gz `
        --output task_sets/code_repair/humanevalfix

``--extra-defects k`` injects ``k`` further defects into every seeded program
(mutation operators on the syntax tree, see ``benchmarks/defects.py``) for a
harder variant of a memorised benchmark; task ids get a ``_d<k>`` suffix.
``--anonymize`` renames every identifier (entry point ``solve``, variables
``v1``, ``v2``, ...), drops docstrings and replaces the specification by a
tests-only prompt (see ``benchmarks/anonymize.py``); ids get ``_anon``.

Every task is validated (reference passes all tests, seeded program loads and
fails at least one development test, no hidden test repeats a development
input) and the outcome is written to ``index.json`` / ``rejected.json`` in the
output directory. ``--only`` restricts the build to some tasks (QuixBugs
program names or HumanEval numbers) for a quick check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from environments.code_repair.benchmarks import SplitRule, build_humanevalfix_tasks, build_quixbugs_tasks  # noqa: E402
from environments.code_repair.benchmarks.common import DEFAULT_MAX_DEV_CASE_CHARS  # noqa: E402
from environments.code_repair.benchmarks.humanevalfix import DEFAULT_MAX_PLUS_HIDDEN  # noqa: E402
from environments.code_repair.runner import DEFAULT_MEMORY_MB, DEFAULT_TIMEOUT_S  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("benchmark", choices=("quixbugs", "humanevalfix"))
    parser.add_argument("--source", required=True, help="QuixBugs checkout directory, or the HumanEvalPack python jsonl file")
    parser.add_argument("--output", required=True, help="directory that receives one sub-directory per task")
    parser.add_argument("--evalplus", default=None, help="HumanEvalPlus.jsonl(.gz) for extra hidden inputs (humanevalfix only)")
    parser.add_argument("--max-plus-hidden", type=int, default=DEFAULT_MAX_PLUS_HIDDEN, help="extra hidden inputs per task from HumanEval+")
    parser.add_argument("--max-dev-case-chars", type=int, default=DEFAULT_MAX_DEV_CASE_CHARS, help="longer cases are hidden only")
    parser.add_argument("--seed", type=int, default=0, help="seed of the split (sampling of HumanEval+ inputs)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="runner time limit per program run, seconds")
    parser.add_argument("--memory-mb", type=int, default=DEFAULT_MEMORY_MB, help="runner memory limit (POSIX only)")
    parser.add_argument("--only", nargs="*", default=None, help="QuixBugs program names or HumanEval numbers to build")
    parser.add_argument("--extra-defects", type=int, default=0, help="inject this many further defects into every seeded program (task ids get a _d<k> suffix)")
    parser.add_argument("--defect-seed", type=int, default=0)
    parser.add_argument("--anonymize", action="store_true", help="rename identifiers and use a tests-only prompt (task ids get an _anon suffix)")
    args = parser.parse_args(argv)

    rule = SplitRule(max_dev_case_chars=args.max_dev_case_chars, seed=args.seed)
    if args.benchmark == "quixbugs":
        report = build_quixbugs_tasks(
            args.source, args.output, rule=rule, names=args.only or None,
            timeout_s=args.timeout, memory_mb=args.memory_mb,
            extra_defects=args.extra_defects, defect_seed=args.defect_seed, anonymize=args.anonymize,
        )
    else:
        numbers = [int(value) for value in args.only] if args.only else None
        report = build_humanevalfix_tasks(
            args.source, args.output, evalplus_path=args.evalplus, max_plus_hidden=args.max_plus_hidden,
            rule=rule, numbers=numbers, timeout_s=args.timeout, memory_mb=args.memory_mb,
            extra_defects=args.extra_defects, defect_seed=args.defect_seed, anonymize=args.anonymize,
        )

    print(f"{report.benchmark}: built {len(report.built)} tasks, rejected {len(report.rejected)} -> {report.output_root}")
    for entry in report.rejected:
        print(f"  rejected {entry['id']}: {entry['reason'][:160]}")
    if report.built:
        hidden = sorted(entry["n_hidden"] for entry in report.built)
        dev = sorted(entry["n_dev"] for entry in report.built)
        print(f"  development tests per task: min {dev[0]}, median {dev[len(dev) // 2]}, max {dev[-1]}")
        print(f"  hidden tests per task:      min {hidden[0]}, median {hidden[len(hidden) // 2]}, max {hidden[-1]}")
    print(f"  index: {Path(report.output_root) / 'index.json'}")
    return 0 if report.built else 1


if __name__ == "__main__":
    sys.exit(main())
