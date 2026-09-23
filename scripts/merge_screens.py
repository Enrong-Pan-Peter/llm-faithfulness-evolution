"""Merge several one-shot screening files of the same tasks into one.

A task screened in two rounds (6 attempts, then 15 more) gets one row with 21
attempts: counts are added, means are weighted by the number of parsed
samples. Rows of tasks that appear in only some files are kept as they are.
Reads and writes the format of ``planning_direct_solve_check.py`` /
``code_repair_memorization_check.py``, so the result feeds
``pick_hard_tasks.py`` directly.

    python scripts/merge_screens.py out/screen_c/planning_deep_6to7/direct_solve_check.json `
        out/screen_d/planning_deep_6to7/direct_solve_check.json --output out/screen_merged/planning_deep_6to7.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

COUNT_FIELDS = ("samples", "parsed", "solved")
MEAN_FIELDS = ("mean_progress", "mean_fitness", "mean_plan_length", "mean_hidden_pass_fraction")


def merge_rows(row_lists: list[list[dict]]) -> list[dict]:
    merged: dict[str, dict] = {}
    for rows in row_lists:
        for row in rows:
            key = row.get("instance_id") or row.get("task_id")
            if key not in merged:
                merged[key] = dict(row)
                continue
            current = merged[key]
            weight_old = current.get("parsed", current.get("samples", 0)) or 0
            weight_new = row.get("parsed", row.get("samples", 0)) or 0
            for field in MEAN_FIELDS:
                if current.get(field) is not None and row.get(field) is not None and weight_old + weight_new > 0:
                    current[field] = (current[field] * weight_old + row[field] * weight_new) / (weight_old + weight_new)
                elif current.get(field) is None and row.get(field) is not None:
                    current[field] = row[field]
            for field in COUNT_FIELDS:
                current[field] = (current.get(field) or 0) + (row.get(field) or 0)
            current["solve_rate"] = current["solved"] / current["samples"] if current["samples"] else 0.0
            if "band" in current:
                current["band"] = _band(current["solve_rate"])
    return list(merged.values())


def _band(rate: float) -> str:
    return "easy" if rate >= 0.8 else ("hard" if rate < 0.2 else "medium")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", help="direct_solve_check.json or memorization_check.json files")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    documents = [json.loads(Path(path).read_text(encoding="utf-8")) for path in args.files]
    rows = merge_rows([document["rows"] for document in documents])
    never = [row.get("instance_id") or row.get("task_id") for row in rows if row["solved"] == 0]
    always = [row.get("instance_id") or row.get("task_id") for row in rows if row["samples"] and row["solved"] == row["samples"]]
    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "merged_from": [str(path) for path in args.files],
        "provider": documents[0].get("provider"),
        "model": documents[0].get("model"),
        "samples": "per row",
        "n_rows": len(rows),
        "never_solved": never,
        "always_solved": always,
        "rows": rows,
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{len(rows)} rows ({len(never)} never solved, {len(always)} always solved) -> {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
