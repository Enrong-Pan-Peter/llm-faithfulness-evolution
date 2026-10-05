"""Completeness and sanity report for a Stage B trace tree (cluster or local copy).

    python scripts/check_stage_b.py                       # reads traces/stage_b
    python scripts/check_stage_b.py --root traces/stage_b --runs 2

For every ``<model>/<environment>_<condition>`` directory: how many of the
expected trace files exist (tasks x runs), per-run outcome (solved, first
success generation, generations run, model calls, failed calls), how many
candidates carry a parsed self-report, and whether every task has its
``summary_<task>.json``. For every ``*_intervention*/run<k>`` directory: the
number of intervention records and of stored calls per condition. The
expected task count comes from the study sets (12) or, for control
directories, from the ids present. Ends with a list of gaps, so an empty
"gaps" section means the batch is complete.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from search.analysis import extract_candidates  # noqa: E402

TRACE_RE = re.compile(r"^(?P<method>ea_(?:plan|code)_operators)_(?P<task>.+)_run(?P<run>\d+)_\d{8}_\d{6}\.json$")
STUDY_TASKS = {"planning": 12, "code_repair": 12}
CONTROL_TASKS = 6  # every other task of the study list (submit_stage_b.sh)
CONTROL_SUFFIXES = ("_random_selection", "_report_rewarded", "_noreport", "_prospective")


def scan_condition(directory: Path, expected_runs: int, expected_tasks: int | None) -> dict:
    traces: dict[tuple[str, int], list[Path]] = defaultdict(list)
    for path in directory.glob("*.json"):
        match = TRACE_RE.match(path.name)
        if match:
            traces[(match.group("task"), int(match.group("run")))].append(path)
    tasks = sorted({task for task, _ in traces})
    rows = []
    n_candidates = n_reports = n_model_failures = 0
    for (task, run), paths in sorted(traces.items()):
        path = sorted(paths)[-1]
        try:
            events = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            rows.append({"task": task, "run": run, "error": f"unreadable trace: {exc}"})
            continue
        candidates = extract_candidates(events, path.name)
        reported = sum(1 for c in candidates if not c.self_report_parse_failed)
        n_candidates += len(candidates)
        n_reports += reported
        failures = sum(1 for e in events if e.get("event") == "MODEL_CALL_FAILED")
        n_model_failures += failures
        end = next((e for e in events if e.get("event") in ("SOLVED", "FAILED")), None)
        details = (end or {}).get("details", {}) or {}
        generations = max((c.generation for c in candidates), default=0)
        rows.append({
            "task": task, "run": run, "solved": (end or {}).get("event") == "SOLVED",
            "first_success_generation": details.get("first_success_generation"),
            "generations": generations, "candidates": len(candidates), "reports": reported,
            "model_failures": failures, "duplicates": len(paths) - 1, "ended": end is not None,
        })
    summaries = {p.name[len("summary_"):-len(".json")] for p in directory.glob("summary_*.json")}
    expected_tasks = expected_tasks or len(tasks)
    gaps = []
    if expected_tasks and len(tasks) < expected_tasks:
        gaps.append(f"{directory}: only {len(tasks)} of {expected_tasks} tasks have traces")
    for task in tasks:
        runs = sorted(run for (t, run) in traces if t == task)
        missing = [k for k in range(expected_runs) if k not in runs]
        if missing:
            gaps.append(f"{directory}: {task} is missing run(s) {missing}")
        if task not in summaries:
            gaps.append(f"{directory}: {task} has no summary_{task}.json (job did not finish cleanly)")
    for row in rows:
        if row.get("error"):
            gaps.append(f"{directory}: {row['task']} run {row['run']}: {row['error']}")
        elif not row["ended"]:
            gaps.append(f"{directory}: {row['task']} run {row['run']} has no SOLVED/FAILED event (truncated)")
    return {"rows": rows, "tasks": tasks, "n_candidates": n_candidates, "n_reports": n_reports,
            "n_model_failures": n_model_failures, "gaps": gaps}


def scan_intervention(directory: Path) -> dict:
    records_path = directory / "rationale_intervention_records.json"
    summary_path = directory / "summary.json"
    if not records_path.is_file():
        return {"records": 0, "conditions": {}, "gap": f"{directory}: no rationale_intervention_records.json"}
    data = json.loads(records_path.read_text(encoding="utf-8"))
    records = data["records"] if isinstance(data, dict) else data
    conditions = Counter(r.get("condition") for r in records)
    errors = sum(1 for r in records if r.get("error"))
    calls = len({(r.get("trace_file"), r.get("child_id")) for r in records})
    gap = None if summary_path.is_file() else f"{directory}: no summary.json"
    return {"records": len(records), "calls": calls, "conditions": dict(conditions), "errors": errors, "gap": gap}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default="traces/stage_b")
    parser.add_argument("--runs", type=int, default=2, help="expected runs per task")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        raise SystemExit(f"{root} does not exist")
    gaps: list[str] = []
    for model_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        print(f"=== {model_dir.name}")
        for cond_dir in sorted(p for p in model_dir.iterdir() if p.is_dir()):
            if "intervention" in cond_dir.name:
                for run_dir in sorted(p for p in cond_dir.iterdir() if p.is_dir()):
                    info = scan_intervention(run_dir)
                    if info.get("gap"):
                        gaps.append(info["gap"])
                    print(f"  {cond_dir.name}/{run_dir.name}: {info['records']} records"
                          + (f" from {info['calls']} stored calls, {info['errors']} failed calls, per condition {info['conditions']}" if info["records"] else ""))
                continue
            environment = "planning" if cond_dir.name.startswith("planning") else "code_repair"
            if cond_dir.name.endswith("_main"):
                expected_tasks = STUDY_TASKS[environment]
            elif cond_dir.name.endswith(CONTROL_SUFFIXES):
                expected_tasks = CONTROL_TASKS
            else:
                expected_tasks = None
            info = scan_condition(cond_dir, args.runs, expected_tasks)
            gaps.extend(info["gaps"])
            rows = [r for r in info["rows"] if not r.get("error")]
            solved = sum(1 for r in rows if r["solved"])
            gen0 = sum(1 for r in rows if r["solved"] and r["first_success_generation"] == 0)
            full = sum(1 for r in rows if not r["solved"])
            mean_gen = sum(r["generations"] for r in rows) / len(rows) if rows else 0.0
            print(f"  {cond_dir.name}: {len(rows)} runs on {len(info['tasks'])} tasks; solved {solved}"
                  f" (at generation 0: {gen0}); unsolved (all generations run): {full}; mean generations {mean_gen:.1f};"
                  f" candidates {info['n_candidates']}, with parsed report {info['n_reports']}; failed model calls {info['n_model_failures']}")
            for r in rows:
                flag = "SOLVED" if r["solved"] else "not solved"
                print(f"      {r['task']:<44} run{r['run']}: {flag:<10} first_success={r['first_success_generation']}"
                      f" gens={r['generations']:>2} cands={r['candidates']:>3} reports={r['reports']:>3} failed_calls={r['model_failures']}")
    print("=== gaps")
    if gaps:
        for gap in gaps:
            print("  " + gap)
    else:
        print("  none: every expected trace, summary and intervention output is present")
    return 1 if gaps else 0


if __name__ == "__main__":
    sys.exit(main())
