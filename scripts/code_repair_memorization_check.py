"""How much of a code-repair task set can the model solve by direct prompting (no search)?

QuixBugs and HumanEval are public and old; a model may have memorised them.
This script asks the model, ``--samples`` times per task, either to repair the
seeded program given the specification and the failing development cases
(``--mode repair``: exactly the generation-0 prompt of the search) or to write
the function from the specification alone (``--mode spec``: no program shown),
grades every answer on the hidden tests, and writes per-task solve rates.
Tasks solved in (almost) every sample are easy or memorised for that model;
the pilot decides how to treat them (usable for calibration and the rationale
intervention, uninformative for selection).

Usage (PowerShell):

    python scripts/code_repair_memorization_check.py --tasks task_sets/code_repair/quixbugs `
        --provider ollama --model qwen3:14b --samples 5 --output out/memorization/quixbugs_qwen
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contexto_solver import config as app_config  # noqa: E402
from environments.code_repair import prompts as code_prompts  # noqa: E402
from environments.code_repair.search_adapter import CodeRepairSearchEnvironment  # noqa: E402
from environments.code_repair.tasks import list_tasks  # noqa: E402
from search.model import ModelClient, ScriptedModel  # noqa: E402
from search.run import scripted_responder  # noqa: E402

SPEC_PROMPT = (
    "Return only JSON, no markdown or explanation.\n"
    "Write a correct Python implementation of the function specified below.\n"
    "\n"
    "Task specification:\n"
    "{task_prompt}\n"
) + code_prompts._OUTPUT_FORMAT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--task-ids", nargs="*", default=None)
    parser.add_argument("--mode", choices=("repair", "spec"), default="repair")
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--provider", default=app_config.LLM_PROVIDER)
    parser.add_argument("--model", default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    wanted = set(args.task_ids) if args.task_ids else None
    tasks = [task for task in list_tasks(args.tasks) if wanted is None or task.id in wanted]
    if not tasks:
        raise SystemExit("no tasks selected")
    model_name = args.model or app_config.OLLAMA_MODEL
    rows: list[dict[str, Any]] = []
    for index, task in enumerate(tasks):
        environment = CodeRepairSearchEnvironment(task)
        model: Any = ScriptedModel(scripted_responder(environment, args.seed + index)) if args.provider == "scripted" else ModelClient(args.provider, model_name)
        if args.mode == "repair":
            prompt = environment.initial_prompt(self_report=False)
        else:
            prompt = SPEC_PROMPT.format(task_prompt=task.prompt.strip(), entry_point=task.entry_point)
            environment.check_prompt(prompt)
        solved = 0
        parsed_ok = 0
        hidden_fractions: list[float] = []
        for _ in range(args.samples):
            parsed, raw, error = model.complete_json(prompt)
            candidate = environment.parse_candidate(parsed) if parsed is not None else None
            if candidate is None:
                continue
            parsed_ok += 1
            evaluation = environment.evaluate(candidate[0])
            solved += bool(evaluation.all_hidden_passed)
            hidden_fractions.append(evaluation.hidden_passed / evaluation.hidden_total if evaluation.hidden_total else 0.0)
        rows.append(
            {
                "task_id": task.id,
                "benchmark": task.source.get("benchmark"),
                "mode": args.mode,
                "samples": args.samples,
                "parsed": parsed_ok,
                "solved": solved,
                "solve_rate": solved / args.samples,
                "mean_hidden_pass_fraction": (sum(hidden_fractions) / len(hidden_fractions)) if hidden_fractions else None,
                "seeded_hidden_passed": environment.seeded_evaluation.hidden_passed,
                "n_hidden": len(task.hidden_tests),
            }
        )
        print(f"[{index + 1}/{len(tasks)}] {task.id}: solved {solved}/{args.samples}")

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "memorization_check.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "provider": args.provider,
        "model": model_name if args.provider != "scripted" else "scripted",
        "mode": args.mode,
        "samples": args.samples,
        "n_tasks": len(rows),
        "always_solved": [row["task_id"] for row in rows if row["solved"] == args.samples],
        "never_solved": [row["task_id"] for row in rows if row["solved"] == 0],
        "mean_solve_rate": sum(row["solve_rate"] for row in rows) / len(rows),
        "rows": rows,
    }
    (output / "memorization_check.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"mean solve rate {summary['mean_solve_rate']:.2f}; always solved: {len(summary['always_solved'])}, never solved: {len(summary['never_solved'])} -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
