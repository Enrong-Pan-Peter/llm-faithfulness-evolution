"""Generate a Blocksworld instance set for the planning environment.

Usage (PowerShell):

    python scripts/build_planning_instances.py --sizes 3 4 5 --per-size 5 --seed 0 `
        --output task_sets/planning/pilot_3to5.json

Every instance is fully determined by its block count and per-instance seed
(``environments.planning.blocksworld.generate_instance``); the file records the
initial state, the goal, the optimal plan length (breadth-first search) and the
move-count lower bound so a run can check plans without re-solving. Instances
whose optimal search exceeds the expansion cap, or whose optimal plan is
shorter than ``--min-optimal-length`` (default 4: one block move is not a
planning problem), are dropped and listed. ``--per-size`` counts generated
instances per size, before dropping.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from environments.planning.blocksworld import (  # noqa: E402
    DEFAULT_EXPANSION_CAP,
    bfs_optimal_plan,
    generate_instance_set,
    move_count_bound,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sizes", type=int, nargs="+", required=True, help="block counts, e.g. 3 4 5")
    parser.add_argument("--per-size", type=int, default=5)
    parser.add_argument("--seed", type=int, default=0, help="master seed of the set")
    parser.add_argument("--expansion-cap", type=int, default=DEFAULT_EXPANSION_CAP)
    parser.add_argument("--min-optimal-length", type=int, default=4, help="drop instances solvable in fewer actions")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    instances = generate_instance_set(args.sizes, args.per_size, args.seed)
    records = []
    dropped = []
    for instance in instances:
        search = bfs_optimal_plan(instance.initial_state, instance.goal, expansion_cap=args.expansion_cap)
        if search.plan is None:
            dropped.append({"instance_id": instance.instance_id, "reason": "optimal search exceeded the expansion cap"})
            continue
        if search.length is not None and search.length < args.min_optimal_length:
            dropped.append({"instance_id": instance.instance_id, "reason": f"optimal plan shorter than {args.min_optimal_length} actions"})
            continue
        bound = move_count_bound(instance.initial_state, instance.goal)
        record = instance.to_dict()
        record["optimal_plan_length"] = search.length
        record["blocks_to_move"] = bound.blocks_to_move
        record["actions_lower_bound"] = bound.actions_lower_bound
        records.append(record)
    output = {
        "sizes": args.sizes,
        "per_size": args.per_size,
        "seed": args.seed,
        "expansion_cap": args.expansion_cap,
        "min_optimal_length": args.min_optimal_length,
        "n_instances": len(records),
        "instances": records,
        "dropped": dropped,
    }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    lengths = [record["optimal_plan_length"] for record in records]
    print(f"{len(records)} instances -> {path} (optimal plan length {min(lengths)}..{max(lengths)}); dropped {len(dropped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
