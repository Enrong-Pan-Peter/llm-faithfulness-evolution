"""Assemble a study task set from chosen ids of existing sets.

Planning (a JSON instance set filtered to the ids, header fields kept):

    python scripts/assemble_task_subset.py planning --sources task_sets/planning/deep_6to7.json `
        --ids bw07_s6088 bw07_s1332 --rule "..." --output task_sets/planning/stage_b_12.json

Code repair (task directories copied from one or more sets; ``index.json``
records where each task came from):

    python scripts/assemble_task_subset.py code_repair `
        --sources task_sets/code_repair/quixbugs_d3_anon task_sets/code_repair/humanevalfix_d3_anon `
        --ids quixbugs_mergesort_d3_anon humanevalfix_040_d3_anon --rule "..." --output task_sets/code_repair/stage_b_12

``--rule`` is free text stored with the set: how the ids were chosen (the
screening file and the pick command), so the choice is on record.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def assemble_planning(sources: list[Path], ids: list[str], rule: str, output: Path) -> int:
    wanted = list(dict.fromkeys(ids))
    found: dict[str, dict] = {}
    headers: list[dict] = []
    for path in sources:
        data = json.loads(path.read_text(encoding="utf-8"))
        records = data["instances"] if isinstance(data, dict) else data
        if isinstance(data, dict):
            headers.append({k: v for k, v in data.items() if k not in ("instances", "dropped")})
        for record in records:
            if record["instance_id"] in wanted and record["instance_id"] not in found:
                found[record["instance_id"]] = {**record, "source_set": str(path)}
    missing = [task_id for task_id in wanted if task_id not in found]
    if missing:
        raise SystemExit(f"ids not found in the sources: {' '.join(missing)}")
    result = {
        "subset_of": [str(path) for path in sources],
        "source_headers": headers,
        "selection_rule": rule,
        "n_instances": len(wanted),
        "instances": [found[task_id] for task_id in wanted],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{len(wanted)} instances -> {output}")
    return 0


def assemble_code(sources: list[Path], ids: list[str], rule: str, output: Path) -> int:
    from environments.code_repair.tasks import TASK_FILE, load_task

    wanted = list(dict.fromkeys(ids))
    origin: dict[str, Path] = {}
    for root in sources:
        for child in sorted(root.iterdir()):
            if child.is_dir() and (child / TASK_FILE).is_file() and child.name in wanted and child.name not in origin:
                origin[child.name] = child
    missing = [task_id for task_id in wanted if task_id not in origin]
    if missing:
        raise SystemExit(f"ids not found in the sources: {' '.join(missing)}")
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    for task_id in wanted:
        destination = output / task_id
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(origin[task_id], destination)
        task = load_task(destination)
        entries.append(
            {
                "id": task.id,
                "entry_point": task.entry_point,
                "n_dev": len(task.dev_tests),
                "n_hidden": len(task.hidden_tests),
                "source_set": str(origin[task_id].parent),
                "source": task.source,
            }
        )
    index = {
        "benchmark": "subset",
        "subset_of": [str(path) for path in sources],
        "selection_rule": rule,
        "n_tasks": len(entries),
        "tasks": entries,
    }
    (output / "index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(entries)} tasks -> {output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("environment", choices=("planning", "code_repair"))
    parser.add_argument("--sources", nargs="+", required=True, help="instance set files (planning) or task set directories (code_repair)")
    parser.add_argument("--ids", nargs="+", required=True)
    parser.add_argument("--rule", default="", help="how the ids were chosen, stored with the set")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    sources = [Path(path) for path in args.sources]
    if args.environment == "planning":
        return assemble_planning(sources, args.ids, args.rule, Path(args.output))
    return assemble_code(sources, args.ids, args.rule, Path(args.output))


if __name__ == "__main__":
    sys.exit(main())
