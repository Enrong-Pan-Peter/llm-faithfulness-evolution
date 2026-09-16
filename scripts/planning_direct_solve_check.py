"""How often does the model solve each planning instance in one shot (no search)?

Asks the model ``--samples`` times per instance for a plan from the initial
prompt of the search (the same prompt generation 0 uses), grades every plan
exactly, and writes per-instance solve rates, mean progress and mean fitness.
Instances the model solves in (almost) every attempt are too easy for a search
study: the run would end in generation 0. Use the table to pick the pilot and
study instances (suggested bands: easy >= 0.8, medium 0.2-0.8, hard < 0.2).

Usage (PowerShell):

    python scripts/planning_direct_solve_check.py --instances task_sets/planning/study_3to7.json `
        --provider ollama --model qwen3:14b --samples 3 --output out/pilot_a/planning_direct_solve
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
from search.model import ModelClient, ScriptedModel  # noqa: E402
from search.run import load_planning_environments, scripted_responder  # noqa: E402


def band(solve_rate: float) -> str:
    if solve_rate >= 0.8:
        return "easy"
    if solve_rate >= 0.2:
        return "medium"
    return "hard"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--instances", required=True, nargs="+", help="one or more instance-set JSON files")
    parser.add_argument("--task-ids", nargs="*", default=None)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--provider", default=app_config.LLM_PROVIDER)
    parser.add_argument("--model", default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    environments = []
    for path in args.instances:
        environments.extend(load_planning_environments(Path(path), args.task_ids))
    if not environments:
        raise SystemExit("no instances selected")
    model_name = args.model or app_config.OLLAMA_MODEL
    rows: list[dict[str, Any]] = []
    for index, environment in enumerate(environments):
        model: Any = ScriptedModel(scripted_responder(environment, args.seed + index)) if args.provider == "scripted" else ModelClient(args.provider, model_name)
        prompt = environment.initial_prompt(self_report=False)
        environment.check_prompt(prompt)
        solved = parsed_ok = 0
        progress: list[float] = []
        fitness: list[float] = []
        lengths: list[int] = []
        for _ in range(args.samples):
            parsed, raw, error = model.complete_json(prompt)
            candidate = environment.parse_candidate(parsed) if parsed is not None else None
            if candidate is None:
                continue
            parsed_ok += 1
            outcome = environment.outcome(environment.evaluate(candidate[0]))
            solved += bool(outcome["success"])
            progress.append(float(outcome["progress"]))
            fitness.append(float(outcome["score"]))
            lengths.append(len(candidate[1].splitlines()))
        rate = solved / args.samples
        rows.append(
            {
                "instance_id": environment.task_id,
                "n_blocks": environment.instance.n_blocks,
                "optimal_plan_length": environment.optimal_length,
                "samples": args.samples,
                "parsed": parsed_ok,
                "solved": solved,
                "solve_rate": rate,
                "band": band(rate),
                "mean_progress": (sum(progress) / len(progress)) if progress else None,
                "mean_fitness": (sum(fitness) / len(fitness)) if fitness else None,
                "mean_plan_length": (sum(lengths) / len(lengths)) if lengths else None,
            }
        )
        print(f"[{index + 1}/{len(environments)}] {environment.task_id} ({environment.instance.n_blocks} blocks, optimal {environment.optimal_length}): solved {solved}/{args.samples}")

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "direct_solve_check.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "provider": args.provider,
        "model": model_name if args.provider != "scripted" else "scripted",
        "samples": args.samples,
        "n_instances": len(rows),
        "bands": {name: [row["instance_id"] for row in rows if row["band"] == name] for name in ("easy", "medium", "hard")},
        "rows": rows,
    }
    (output / "direct_solve_check.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    counts = {name: len(ids) for name, ids in summary["bands"].items()}
    print(f"bands: {counts} -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
