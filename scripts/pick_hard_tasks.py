"""Print the ids of the tasks a model solves least often in one shot.

Reads the JSON written by ``planning_direct_solve_check.py`` or
``code_repair_memorization_check.py`` and prints, space-separated, the ``--count``
ids with the lowest one-shot solve rate (ties: the highest mean progress /
hidden pass fraction first, so instances with a fitness gradient are preferred).

    python scripts/pick_hard_tasks.py out/pilot_a/memorization_quixbugs_repair/memorization_check.json --count 5

``--group-key optimal_plan_length --per-group 3`` picks the same way inside
every group of a row field (three per optimal plan length, say), so a study
set spans the difficulty range instead of clustering at one end.

``--spread 12`` takes the eligible tasks in the same order (lowest solve rate,
then highest progress) and keeps 12 of them evenly spaced along that order,
so the set contains near-solvable and deep tasks alike; the pilot showed that
the highest-progress never-solved tasks are the ones a 15-candidate first
generation tends to solve outright.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _key(row: dict):
    progress = row.get("mean_progress")
    if progress is None:
        progress = row.get("mean_hidden_pass_fraction")
    return (row["solve_rate"], -(progress if progress is not None else 0.0))


def _id(row: dict) -> str:
    return row.get("instance_id") or row.get("task_id")


def pick(rows: list[dict], count: int, max_rate: float) -> list[str]:
    eligible = [row for row in rows if row["solve_rate"] <= max_rate]
    chosen = sorted(eligible, key=_key)[:count]
    return [_id(row) for row in chosen]


def pick_spread(rows: list[dict], count: int, max_rate: float) -> list[str]:
    """``count`` ids evenly spaced along the eligible ranking (first and last included)."""
    eligible = sorted((row for row in rows if row["solve_rate"] <= max_rate), key=_key)
    if len(eligible) <= count:
        return [_id(row) for row in eligible]
    if count == 1:
        return [_id(eligible[0])]
    positions = [round(i * (len(eligible) - 1) / (count - 1)) for i in range(count)]
    return [_id(eligible[position]) for position in positions]


def pick_per_group(rows: list[dict], group_key: str, per_group: int, max_rate: float) -> list[str]:
    """``per_group`` ids per distinct value of ``group_key`` (groups in ascending order)."""
    eligible = [row for row in rows if row["solve_rate"] <= max_rate and row.get(group_key) is not None]
    groups = sorted({row[group_key] for row in eligible}, key=lambda value: (str(type(value)), value))
    chosen: list[str] = []
    for value in groups:
        members = sorted((row for row in eligible if row[group_key] == value), key=_key)[:per_group]
        chosen.extend(_id(row) for row in members)
    return chosen


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("summary", help="direct_solve_check.json or memorization_check.json")
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--max-rate", type=float, default=1.0, help="ignore tasks solved more often than this")
    parser.add_argument("--group-key", default=None, help="row field to group by (e.g. optimal_plan_length, n_blocks)")
    parser.add_argument("--per-group", type=int, default=3, help="ids per group when --group-key is given")
    parser.add_argument("--spread", type=int, default=None, help="keep this many ids evenly spaced along the ranking")
    args = parser.parse_args(argv)
    data = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    if args.group_key:
        ids = pick_per_group(data["rows"], args.group_key, args.per_group, args.max_rate)
    elif args.spread:
        ids = pick_spread(data["rows"], args.spread, args.max_rate)
    else:
        ids = pick(data["rows"], args.count, args.max_rate)
    if not ids:
        raise SystemExit("no task below the requested solve rate")
    print(" ".join(ids))
    return 0


if __name__ == "__main__":
    sys.exit(main())
