"""Print what happened in one or more trace files, one line per candidate.

    python scripts/trace_glance.py "traces/stage_b/gemma4_12b/planning_main/*bw07_s6519_run0_*.json"
    python scripts/trace_glance.py traces/stage_b/qwen3_14b/code_repair_main/*hanoi*_run0_*.json --limit 20

Shows the run settings (model, task, selection, channel), then for every
candidate: generation, origin/operator, parse status, the environment's
grade (planning: plan length, executable prefix, goal predicates satisfied,
goal complete; code: development and hidden tests passed), the stated chance
of success and the predicted bucket. Use it to eyeball a surprising batch,
for example a model that solves every instance at generation 0.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from search.analysis import run_config  # noqa: E402


def glance(path: Path, limit: int | None) -> None:
    events = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(events, list):
        print(f"=== {path.name}: not a trace file (skipped)")
        return
    config = run_config(events) or {}
    print(f"=== {path.name}")
    print(f"    model={config.get('llm_model')} task={config.get('task_id')} selection={config.get('selection')} "
          f"channel={config.get('rationale_channel')} label={config.get('run_label')}")
    end = next((e for e in events if e.get("event") in ("SOLVED", "FAILED")), None)
    print(f"    end: {(end or {}).get('event')} {json.dumps((end or {}).get('details', {}))[:200]}")
    shown = 0
    for event in events:
        if event.get("event") not in ("INITIAL_CANDIDATE", "OPERATOR_SAMPLED"):
            continue
        details = event.get("details", {}) or {}
        outcome = details.get("outcome") or {}
        grade = outcome.get("details") or {}
        report = details.get("self_report") or {}
        if "plan_length" in grade:
            grade_text = (f"plan={grade.get('plan_length')} prefix={grade.get('executable_prefix_length')} "
                          f"goals={grade.get('goal_predicates_satisfied')}/{grade.get('goal_predicates_total')} "
                          f"complete={grade.get('goal_complete')} parse={grade.get('parse_ok')}")
        else:
            grade_text = " ".join(f"{k}={v}" for k, v in grade.items() if not isinstance(v, (list, dict)))[:160]
        print(f"    g{event.get('generation', 0):<2} {str(details.get('origin') or details.get('sampled_op') or ''):<12} "
              f"success={outcome.get('success')!s:<5} score={outcome.get('score')!s:<8} {grade_text} | "
              f"stated={report.get('predicted_closeness')} bucket={report.get('predicted_bucket')}")
        shown += 1
        if limit and shown >= limit:
            print("    ...")
            break
    invalid = sum(1 for e in events if e.get("event") == "MODEL_CALL_FAILED")
    print(f"    candidates shown: {shown}; failed model calls: {invalid}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("traces", nargs="+", help="trace files or glob patterns")
    parser.add_argument("--limit", type=int, default=None, help="candidates to show per trace")
    args = parser.parse_args(argv)
    paths: list[Path] = []
    for pattern in args.traces:
        matches = sorted(glob.glob(pattern))
        paths.extend(Path(m) for m in matches) if matches else paths.append(Path(pattern))
    for path in paths:
        if not path.is_file():
            print(f"=== {path}: not found")
            continue
        glance(path, args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
