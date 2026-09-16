"""Selection response in planning / code-repair traces (offline).

Same design as ``selection_response_analysis.py`` for Contexto, on the shared-loop
traces. Units are the mutation children (``OPERATOR_SAMPLED``) with a parsed
report. Each child is labelled survivor or culled by the first ``SELECT`` after
its birth (by id; there is no name matching here). Two agreement measures:

- ``binary_error``   = |predicted_closeness - 1{success}|;
- ``bucket_distance`` = |ordinal(predicted_bucket) - ordinal(realized bucket)|
  in the environment's bucket order.

Analyses: the survivor-vs-culled gap within matched cells (generation x parent
progress bin), with a within-cell permutation of the predicted values (outcomes
and labels fixed; B seeded permutations, two-sided empirical p); parent -> child
transmission of the measure along parent_id links against the same permutation
baseline; and the generation trend. Traces of the ``random`` selection control
and the ``report_rewarded`` positive control are analysed the same way; pass
them as separate batches (the run's ``selection`` is echoed in the output).

Usage (PowerShell):

    python scripts/environment_selection_response.py "traces/pilot/planning/*.json" `
        --output-dir out/pilot/planning_selection --seed 0 --permutations 1000
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
from scipy import stats  # noqa: E402

from search.analysis import CandidateRecord, _parent_progress_bin, bucket_order_for, read_traces  # noqa: E402

MEASURES = ("binary_error", "bucket_distance")


def measure_of(record: CandidateRecord, measure: str, order) -> float | None:
    if measure == "binary_error":
        return record.binary_error()
    distance = record.bucket_distance(order)
    return None if distance is None else float(distance)


def units(records: list[CandidateRecord]) -> list[CandidateRecord]:
    """Mutation children with a parsed report and a survivor label."""
    return [
        record
        for record in records
        if record.source_event == "OPERATOR_SAMPLED" and record.parse_ok and record.survived is not None
    ]


def cell_of(record: CandidateRecord) -> tuple[str, int, str]:
    return (record.trace_file, record.generation, _parent_progress_bin(record.parent_progress))


def matched_gap(values: list[tuple[CandidateRecord, float]]) -> tuple[float | None, list[dict[str, Any]]]:
    """Survivor-minus-culled mean difference per parent-progress bin, weighted by bin size."""
    by_bin: dict[str, dict[str, list[float]]] = {}
    for record, value in values:
        label = "survivor" if record.survived else "culled"
        by_bin.setdefault(_parent_progress_bin(record.parent_progress), {"survivor": [], "culled": []})[label].append(value)
    rows = []
    weighted = 0.0
    weight_total = 0
    for bin_label in sorted(by_bin):
        survivors, culled = by_bin[bin_label]["survivor"], by_bin[bin_label]["culled"]
        gap = None
        if survivors and culled:
            gap = float(np.mean(survivors) - np.mean(culled))
            weighted += gap * (len(survivors) + len(culled))
            weight_total += len(survivors) + len(culled)
        rows.append(
            {
                "parent_progress_bin": bin_label,
                "n_survivor": len(survivors),
                "n_culled": len(culled),
                "mean_survivor": float(np.mean(survivors)) if survivors else None,
                "mean_culled": float(np.mean(culled)) if culled else None,
                "gap": gap,
            }
        )
    return (weighted / weight_total if weight_total else None), rows


def permuted_values(pool: list[CandidateRecord], measure: str, order, rng: np.random.Generator) -> list[tuple[CandidateRecord, float]]:
    """Permute predicted values within (trace, generation, parent bin) cells; recompute the measure."""
    cells: dict[tuple, list[int]] = {}
    for index, record in enumerate(pool):
        cells.setdefault(cell_of(record), []).append(index)
    result: list[tuple[CandidateRecord, float]] = [None] * len(pool)  # type: ignore[list-item]
    for members in cells.values():
        shuffled = list(members)
        rng.shuffle(shuffled)
        for target, source in zip(members, shuffled):
            donor, receiver = pool[source], pool[target]
            if measure == "binary_error":
                value = abs(float(donor.predicted_closeness) - (1.0 if receiver.success else 0.0))
            else:
                value = float(abs(order.index(donor.predicted_bucket) - order.index(receiver.realized_bucket)))
            result[target] = (receiver, value)
    return result


def permutation_gap_test(pool: list[CandidateRecord], measure: str, order, permutations: int, rng: np.random.Generator) -> dict[str, Any]:
    observed, rows = matched_gap([(record, measure_of(record, measure, order)) for record in pool])
    if observed is None:
        return {"observed_gap": None, "pvalue": None, "n_pool": len(pool), "permutations": 0, "bins": rows}
    extreme = completed = 0
    for _ in range(permutations):
        gap, _ = matched_gap(permuted_values(pool, measure, order, rng))
        if gap is None:
            continue
        completed += 1
        extreme += abs(gap) >= abs(observed)
    return {
        "observed_gap": observed,
        "pvalue": (1 + extreme) / (1 + completed) if completed else None,
        "n_pool": len(pool),
        "permutations": completed,
        "bins": rows,
    }


def parent_offspring_pairs(records: list[CandidateRecord]) -> list[tuple[CandidateRecord, CandidateRecord]]:
    by_id = {(record.trace_file, record.child_id): record for record in records}
    pairs = []
    for child in records:
        if child.source_event != "OPERATOR_SAMPLED" or not child.parent_id:
            continue
        parent = by_id.get((child.trace_file, child.parent_id))
        if parent is not None:
            pairs.append((parent, child))
    return pairs


def _spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    rho, _ = stats.spearmanr(x, y)
    return None if np.isnan(rho) else float(rho)


def transmission_test(records: list[CandidateRecord], pool: list[CandidateRecord], measure: str, order, permutations: int, rng: np.random.Generator) -> dict[str, Any]:
    pairs = [
        (parent, child)
        for parent, child in parent_offspring_pairs(records)
        if measure_of(parent, measure, order) is not None and measure_of(child, measure, order) is not None
    ]
    observed = _spearman([measure_of(p, measure, order) for p, _ in pairs], [measure_of(c, measure, order) for _, c in pairs])
    if observed is None:
        return {"n_pairs": len(pairs), "observed_rho": None, "pvalue": None, "permutations": 0}
    pool_keys = {(record.trace_file, record.child_id) for record in pool}
    extreme = completed = 0
    for _ in range(permutations):
        permuted = {(record.trace_file, record.child_id): value for record, value in permuted_values(pool, measure, order, rng)}

        def value_of(record: CandidateRecord) -> float:
            key = (record.trace_file, record.child_id)
            return permuted[key] if key in pool_keys else measure_of(record, measure, order)

        rho = _spearman([value_of(p) for p, _ in pairs], [value_of(c) for _, c in pairs])
        if rho is None:
            continue
        completed += 1
        extreme += abs(rho) >= abs(observed)
    return {"n_pairs": len(pairs), "observed_rho": observed, "pvalue": (1 + extreme) / (1 + completed) if completed else None, "permutations": completed}


def generation_trend(pool: list[CandidateRecord], measure: str, order) -> list[dict[str, Any]]:
    groups: dict[tuple[int, str], dict[str, list[float]]] = {}
    for record in pool:
        value = measure_of(record, measure, order)
        if value is None:
            continue
        key = (record.generation, "survivor" if record.survived else "culled")
        groups.setdefault(key, {"values": []})["values"].append(value)
    rows = []
    for (generation, label), group in sorted(groups.items()):
        rows.append({"generation": generation, "label": label, "n": len(group["values"]), "mean": float(np.mean(group["values"]))})
    return rows


def analyze(records: list[CandidateRecord], order, permutations: int, seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    pool = units(records)
    result: dict[str, Any] = {
        "n_records": len(records),
        "n_units": len(pool),
        "n_survivors": sum(1 for record in pool if record.survived),
        "n_culled": sum(1 for record in pool if not record.survived),
        "selection_settings": sorted({str(record.selection) for record in records}),
        "bucket_order": list(order),
        "measures": {},
    }
    for measure in MEASURES:
        measured = [record for record in pool if measure_of(record, measure, order) is not None]
        result["measures"][measure] = {
            "gap": permutation_gap_test(measured, measure, order, permutations, rng),
            "transmission": transmission_test(records, measured, measure, order, permutations, rng),
            "generation_trend": generation_trend(measured, measure, order),
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("traces", nargs="+")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--permutations", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    records, configs = read_traces(args.traces)
    if not records:
        raise SystemExit("no candidate records found")
    order = bucket_order_for(records)
    result = analyze(records, order, args.permutations, args.seed)
    result["n_traces"] = len(configs)
    result["generated_at"] = datetime.now().isoformat(timespec="seconds")
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "selection_response.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with (output / "units.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["trace_file", "child_id", "parent_id", "generation", "operator", "parent_progress", "survived", "predicted_closeness", "success", "binary_error", "bucket_distance"])
        for record in units(records):
            writer.writerow([record.trace_file, record.child_id, record.parent_id, record.generation, record.operator, record.parent_progress, record.survived, record.predicted_closeness, record.success, record.binary_error(), record.bucket_distance(order)])
    for measure, block in result["measures"].items():
        gap, transmission = block["gap"], block["transmission"]
        print(f"{measure}: survivor-culled gap {_fmt(gap['observed_gap'])} (p = {_fmt(gap['pvalue'])}, n = {gap['n_pool']}); "
              f"parent->child rho {_fmt(transmission['observed_rho'])} (p = {_fmt(transmission['pvalue'])}, pairs = {transmission['n_pairs']})")
    print(f"-> {output}")
    return 0


def _fmt(value) -> str:
    return "-" if value is None else f"{value:.3f}"


if __name__ == "__main__":
    sys.exit(main())
