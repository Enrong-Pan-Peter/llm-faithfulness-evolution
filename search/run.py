"""Command line for the shared loop: batches of runs on planning instances or code-repair tasks.

Examples (PowerShell):

    # offline check of the whole pipeline, no model server needed
    python -m search.run planning --instances task_sets/planning/pilot_3to5.json `
        --provider scripted --runs-per-task 1 --max-generations 3 --output traces/smoke/planning

    # pilot on the local RTX 3090
    python -m search.run planning --instances task_sets/planning/pilot_3to5.json `
        --provider ollama --model qwen3:14b --runs-per-task 5 --max-generations 10 --output traces/pilot/planning

    python -m search.run code_repair --tasks task_sets/code_repair/quixbugs --task-ids quixbugs_gcd quixbugs_sieve `
        --provider ollama --model qwen3:14b --runs-per-task 5 --max-generations 10 --output traces/pilot/code_repair

Population settings come from the environment (``.env``: ``INITIAL_POPULATION``,
``SURVIVORS``, ``OFFSPRING_PER_PARENT``, ``SELECTION``, ``SELF_REPORT``,
``RATIONALE_CHANNEL``) and can be overridden on the command line. Run ``k`` of a
task uses ``--seed + k``. One trace file per run (a JSON list of events, the
Contexto layout) plus ``summary.json`` for the batch.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from contexto_solver import config as app_config  # noqa: E402
from contexto_solver.logger import Logger  # noqa: E402

from .environment import RATIONALE_CHANNELS  # noqa: E402
from .loop import EvolutionarySearch  # noqa: E402
from .model import ModelClient, ScriptedModel  # noqa: E402
from .settings import SELECTION_CHOICES, SearchSettings  # noqa: E402


# ----------------------------------------------------------------- environments


def load_planning_environments(instances_path: Path, task_ids: list[str] | None) -> list[Any]:
    from environments.planning.blocksworld import Instance
    from environments.planning.search_adapter import PlanningSearchEnvironment

    data = json.loads(Path(instances_path).read_text(encoding="utf-8"))
    records = data["instances"] if isinstance(data, dict) else data
    wanted = set(task_ids) if task_ids else None
    environments = []
    for record in records:
        instance = Instance.from_dict(record)
        if wanted is not None and instance.instance_id not in wanted:
            continue
        environments.append(PlanningSearchEnvironment(instance, optimal_length=record.get("optimal_plan_length")))
    return environments


def load_code_environments(tasks_root: Path, task_ids: list[str] | None, timeout_s: float) -> list[Any]:
    from environments.code_repair.search_adapter import CodeRepairSearchEnvironment
    from environments.code_repair.tasks import list_tasks

    wanted = set(task_ids) if task_ids else None
    environments = []
    for task in list_tasks(tasks_root):
        if wanted is not None and task.id not in wanted:
            continue
        environments.append(CodeRepairSearchEnvironment(task, timeout_s=timeout_s))
    return environments


# ------------------------------------------------------------- scripted model


def scripted_responder(environment: Any, seed: int):
    """A deterministic stand-in model for smoke tests (no server).

    Planning: proposes prefixes of the optimal plan, the full plan with
    probability 0.06 on mutation calls. Code: proposes the seeded program or,
    with probability 0.08 on mutation calls, the reference. Reports are random
    numbers, so calibration metrics on scripted runs mean nothing.
    """
    rng = random.Random(seed)
    if environment.name == "planning":
        from environments.planning.blocksworld import bfs_optimal_plan

        search = bfs_optimal_plan(environment.instance.initial_state, environment.instance.goal)
        optimal = [str(action) for action in search.plan] if search.plan else []

        def respond(prompt: str) -> dict[str, Any]:
            if "Do not write the plan yet" in prompt:
                return {"strategy": "Clear the blocks that are in the way, then build the goal tower from the bottom."}
            if "Parent plan" in prompt and rng.random() < 0.06:
                plan = list(optimal)
            else:
                plan = optimal[: max(1, len(optimal) - rng.randint(1, 3))]
            return {
                "plan": plan,
                "basis_words": ["clear", "table"],
                "reason": "Unstack the blocking blocks first, then stack in goal order.",
                "predicted_bucket": "partial",
                "predicted_closeness": round(rng.uniform(0.2, 0.8), 2),
            }

        return respond

    task = environment.task

    def respond_code(prompt: str) -> dict[str, Any]:
        if "Do not write code" in prompt:
            return {"diagnosis": "One boundary of the main loop is off by one."}
        program = task.reference_source if ("Parent program" in prompt and rng.random() < 0.08) else task.seeded_source
        return {
            "program": program,
            "basis_words": [task.entry_point],
            "reason": "Adjusted the loop bound named in the failing case.",
            "predicted_bucket": "most_pass",
            "predicted_closeness": round(rng.uniform(0.2, 0.8), 2),
        }

    return respond_code


# ------------------------------------------------------------------- batches


def run_batch(args: argparse.Namespace) -> dict[str, Any]:
    output_root = Path(args.output)
    output_root.mkdir(parents=True, exist_ok=True)
    if args.environment == "planning":
        environments = load_planning_environments(Path(args.instances), args.task_ids)
    else:
        environments = load_code_environments(Path(args.tasks), args.task_ids, args.runner_timeout)
    if not environments:
        raise SystemExit("no tasks selected")

    overrides = dict(
        initial_population=args.initial_population,
        survivors=args.survivors,
        offspring_per_parent=args.offspring_per_parent,
        selection=args.selection,
        self_report=None if args.self_report is None else bool(args.self_report),
        rationale_channel=args.rationale_channel,
        max_generations=args.max_generations,
    )
    base_settings = SearchSettings.from_env(**overrides)
    model_name = args.model or app_config.OLLAMA_MODEL
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()
    for environment in environments:
        for run_index in range(args.runs_per_task):
            seed = args.seed + run_index
            settings = base_settings.with_seed(seed)
            if args.provider == "scripted":
                model: Any = ScriptedModel(scripted_responder(environment, seed))
            else:
                model = ModelClient(args.provider, model_name)
            logger = Logger()
            search = EvolutionarySearch(environment, model, settings, run_label=args.label, run_index=run_index, logger=logger)
            wall = time.perf_counter()
            result = search.run()
            wall = time.perf_counter() - wall
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            trace_path = output_root / f"{environment.method}_{environment.task_id}_run{run_index}_{stamp}.json"
            logger.save(trace_path)
            row = {
                "environment": environment.name,
                "method": environment.method,
                "task_id": environment.task_id,
                "run_index": run_index,
                "seed": seed,
                "solved": result.solved,
                "generations": result.generations,
                "n_candidates": result.n_candidates,
                "model_calls": result.model_calls,
                "model_failures": result.model_failures,
                "best_fitness": result.best.fitness if result.best and result.best.fitness != float("inf") else None,
                "best_progress": result.best.progress if result.best else None,
                "wall_time_s": round(wall, 2),
                "trace_path": str(trace_path),
            }
            rows.append(row)
            print(
                f"{environment.task_id} run {run_index}: {'solved' if result.solved else 'not solved'} "
                f"in {result.generations} generations, {result.n_candidates} candidates, "
                f"{result.model_calls} model calls ({result.model_failures} failed), {wall:.0f}s"
            )
    summary = {
        "environment": args.environment,
        "label": args.label,
        "provider": args.provider,
        "model": model_name if args.provider != "scripted" else "scripted",
        "settings": base_settings.to_dict(),
        "n_tasks": len(environments),
        "runs_per_task": args.runs_per_task,
        "wall_time_s": round(time.perf_counter() - started, 1),
        "aggregate": _aggregate(rows),
        "runs": rows,
    }
    (output_root / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"summary: {output_root / 'summary.json'}")
    return summary


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    solved = [row for row in rows if row["solved"]]
    return {
        "n_runs": len(rows),
        "solved": len(solved),
        "solve_rate": len(solved) / len(rows),
        "mean_generations": sum(row["generations"] for row in rows) / len(rows),
        "mean_candidates": sum(row["n_candidates"] for row in rows) / len(rows),
        "mean_model_calls": sum(row["model_calls"] for row in rows) / len(rows),
        "model_failures": sum(row["model_failures"] for row in rows),
        "mean_generations_when_solved": (sum(row["generations"] for row in solved) / len(solved)) if solved else None,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("environment", choices=("planning", "code_repair"))
    parser.add_argument("--instances", help="planning: JSON instance set (scripts/build_planning_instances.py)")
    parser.add_argument("--tasks", help="code_repair: directory of task directories (task_sets/code_repair/<set>)")
    parser.add_argument("--task-ids", nargs="*", default=None, help="subset of instance ids / task ids")
    parser.add_argument("--provider", default=app_config.LLM_PROVIDER, help="ollama | openai | anthropic | scripted")
    parser.add_argument("--model", default=None, help="model name (default: OLLAMA_MODEL from .env)")
    parser.add_argument("--runs-per-task", type=int, default=1)
    parser.add_argument("--seed", type=int, default=0, help="seed of run 0; run k uses seed + k")
    parser.add_argument("--label", default="", help="run label written into every RUN_CONFIG")
    parser.add_argument("--output", required=True, help="directory for the trace files and summary.json")
    parser.add_argument("--max-generations", type=int, default=None)
    parser.add_argument("--initial-population", type=int, default=None)
    parser.add_argument("--survivors", type=int, default=None)
    parser.add_argument("--offspring-per-parent", type=int, default=None)
    parser.add_argument("--selection", choices=SELECTION_CHOICES, default=None)
    parser.add_argument("--rationale-channel", choices=RATIONALE_CHANNELS, default=None)
    parser.add_argument("--self-report", type=int, choices=(0, 1), default=None)
    parser.add_argument("--runner-timeout", type=float, default=5.0, help="code_repair: seconds per test run")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.environment == "planning" and not args.instances:
        raise SystemExit("planning needs --instances")
    if args.environment == "code_repair" and not args.tasks:
        raise SystemExit("code_repair needs --tasks")
    run_batch(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
