"""Results tables for the Stage B study (three models x two environments), as Markdown and CSV.

    python scripts/stage_b_tables.py                          # traces/stage_b + out/stage_b -> out/stage_b/tables.md

Four tables:

A. Search outcomes per model, environment and condition: runs, solved runs,
   runs solved in the first generation, mean generations, candidates, share
   of valid candidates (planning: every action executable; code: the program
   runs), candidate success rate, share with a parsed report, mean stated
   chance of success.
B. Calibration of the main condition: success rate, mean stated chance,
   Brier, ECE, AUROC, Spearman between stated chance and partial progress,
   bucket accuracy and mean signed bucket error (from the calibration metrics
   written by environment_calibration.py).
C. Rationale intervention, pooled over the run indices of one model x
   environment x channel (inherited, prospective), per condition: stored
   calls, paired differences condition minus genuine in fitness (lower
   fitness is better, so a positive difference means the changed slot made
   the candidate worse), bootstrap 95 % interval, the practical-equivalence
   margin (half the interquartile spread of the pooled genuine samples'
   fitness), the verdict by the fixed rule (interval within +- margin: "no
   measurable effect"; otherwise interval excluding zero: "effect"; otherwise
   "inconclusive"), whether the interval excludes zero, the share of pairs in
   which the condition candidate was worse / better than the genuine one, the
   success-rate difference and the mean distance from the genuine candidate.
D. Selection response per model, environment and selection rule: survivor
   minus culled report error within matched cells with its permutation p,
   the same for the bucket distance, parent -> child transmission. Rows with
   fewer than 10 survivors are marked (*).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from search.analysis import extract_candidates  # noqa: E402

MODELS = (("qwen3_14b", "qwen3:14b"), ("gemma4_12b", "gemma4:12b"), ("ministral3_14b", "ministral-3:14b"))
ENVIRONMENTS = (("planning", "planning"), ("code_repair", "code repair"))
CONDITIONS = (("main", "task selection, inherited rationale"), ("random_selection", "random selection"),
              ("report_rewarded", "report-rewarded selection"), ("noreport", "no self-report"),
              ("prospective", "prospective rationale"))
INTERVENTION_CONDITIONS = ("unrelated", "filler", "absent", "corrective_hint")
MIN_SURVIVORS = 10  # table D rows with fewer survivors are marked


def fmt(value, digits=3, dash="–"):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return dash
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


# ------------------------------------------------------------------ table A


def table_a(root: Path) -> list[dict]:
    rows = []
    for model_dir, model in MODELS:
        for env_dir, env in ENVIRONMENTS:
            for cond_dir, cond in CONDITIONS:
                directory = root / model_dir / f"{env_dir}_{cond_dir}"
                if not directory.is_dir():
                    continue
                traces = sorted(p for p in directory.glob("ea_*_run*_*.json"))
                if not traces:
                    continue
                solved = gen0 = 0
                generations = []
                n_cand = n_valid = n_success = n_rep = 0
                stated = []
                for path in traces:
                    events = json.loads(path.read_text(encoding="utf-8"))
                    end = next((e for e in events if e.get("event") in ("SOLVED", "FAILED")), None)
                    details = (end or {}).get("details", {}) or {}
                    if (end or {}).get("event") == "SOLVED":
                        solved += 1
                        if details.get("first_success_generation") == 0:
                            gen0 += 1
                    cands = extract_candidates(events, path.name)
                    generations.append(max((c.generation for c in cands), default=0))
                    n_cand += len(cands)
                    n_valid += sum(1 for c in cands if c.valid)  # planning: every action executable; code: the program runs
                    n_success += sum(1 for c in cands if c.success)
                    reported = [c for c in cands if not c.self_report_parse_failed and c.predicted_closeness is not None]
                    n_rep += len(reported)
                    stated.extend(c.predicted_closeness for c in reported)
                rows.append({
                    "model": model, "environment": env, "condition": cond, "runs": len(traces), "solved": solved,
                    "solved_in_generation_0": gen0, "mean_generations": float(np.mean(generations)) if generations else None,
                    "candidates": n_cand, "valid_share": n_valid / n_cand if n_cand else None,
                    "candidate_success_rate": n_success / n_cand if n_cand else None, "with_report": n_rep,
                    "report_share": n_rep / n_cand if n_cand else None,
                    "mean_stated_chance": float(np.mean(stated)) if stated else None,
                })
    return rows


# ------------------------------------------------------------------ table B


def table_b(out: Path) -> list[dict]:
    rows = []
    for model_dir, model in MODELS:
        for env_dir, env in ENVIRONMENTS:
            path = out / model_dir / f"{env_dir}_main_calibration" / "metrics.json"
            if not path.is_file():
                continue
            overall = json.loads(path.read_text(encoding="utf-8"))["overall"]
            rows.append({
                "model": model, "environment": env, "n": overall["count"],
                "success_rate": overall["success_rate"], "mean_stated_chance": overall["mean_predicted_closeness"],
                "brier": overall["brier"]["brier"], "ece": overall["reliability"]["ece"],
                "auroc": overall["auroc"].get("auroc"), "spearman_progress": overall["spearman_progress"].get("rho"),
                "bucket_accuracy": overall["buckets"]["accuracy"],
                "mean_signed_bucket_error": overall["buckets"]["mean_signed_bucket_error"],
            })
    return rows


# ------------------------------------------------------------------ table C


def bootstrap_ci(values: np.ndarray, rng: np.random.Generator, draws: int = 2000) -> tuple[float, float]:
    if len(values) == 0:
        return (float("nan"), float("nan"))
    means = [float(np.mean(rng.choice(values, size=len(values), replace=True))) for _ in range(draws)]
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def verdict(low: float, high: float, margin: float | None) -> str:
    """The rule fixed in the design: within the margin first, then zero exclusion."""
    if np.isnan(low):
        return "–"
    if margin is not None and -margin <= low and high <= margin:
        return "no measurable effect"
    if low > 0 or high < 0:
        return "effect"
    return "inconclusive"


def table_c(root: Path, seed: int = 0) -> list[dict]:
    rng = np.random.default_rng(seed)
    rows = []
    for model_dir, model in MODELS:
        for env_dir, env in ENVIRONMENTS:
            for kind, channel in (("intervention", "inherited"), ("intervention_prospective", "prospective")):
                base = root / model_dir / f"{env_dir}_{kind}"
                if not base.is_dir():
                    continue
                diffs: dict[tuple[str, str], list[float]] = defaultdict(list)
                genuine_fitness: list[float] = []
                distance: dict[str, list[float]] = defaultdict(list)
                n_calls = 0
                for run_dir in sorted(p for p in base.iterdir() if p.is_dir()):
                    pd_path = run_dir / "paired_differences.csv"
                    rec_path = run_dir / "rationale_intervention_records.json"
                    if not pd_path.is_file() or not rec_path.is_file():
                        continue
                    with pd_path.open(encoding="utf-8") as handle:
                        for row in csv.DictReader(handle):
                            try:
                                diffs[(row["condition"], row["metric"])].append(float(row["difference"]))
                            except (TypeError, ValueError):
                                continue
                    data = json.loads(rec_path.read_text(encoding="utf-8"))
                    records = data["records"] if isinstance(data, dict) else data
                    calls = set()
                    for record in records:
                        if record.get("condition") == "genuine":
                            calls.add((record.get("trace_file"), record.get("child_id")))
                            if record.get("fitness") is not None and record.get("parse_ok"):
                                genuine_fitness.append(float(record["fitness"]))
                        elif record.get("distance_to_genuine") is not None:
                            distance[record["condition"]].append(float(record["distance_to_genuine"]))
                    n_calls += len(calls)
                if not n_calls:
                    continue
                margin = None
                if len(genuine_fitness) >= 4:
                    q75, q25 = np.percentile(genuine_fitness, [75, 25])
                    margin = float((q75 - q25) / 2)
                for condition in INTERVENTION_CONDITIONS:
                    fit = np.asarray(diffs.get((condition, "fitness"), []), dtype=float)
                    suc = np.asarray(diffs.get((condition, "success"), []), dtype=float)
                    if len(fit) == 0:
                        continue
                    low, high = bootstrap_ci(fit, rng)
                    rows.append({
                        "model": model, "environment": env, "channel": channel, "condition": condition,
                        "stored_calls": n_calls, "n": int(len(fit)),
                        "fitness_difference": float(np.mean(fit)), "ci_low": low, "ci_high": high, "margin": margin,
                        "verdict": verdict(low, high, margin), "excludes_zero": "yes" if (low > 0 or high < 0) else "no",
                        "share_worse": float(np.mean(fit > 0)), "share_better": float(np.mean(fit < 0)),
                        "success_difference": float(np.mean(suc)) if len(suc) else None,
                        "mean_distance_to_genuine": float(np.mean(distance[condition])) if distance.get(condition) else None,
                    })
    return rows


# ------------------------------------------------------------------ table D


def table_d(out: Path) -> list[dict]:
    rows = []
    for model_dir, model in MODELS:
        for env_dir, env in ENVIRONMENTS:
            for cond_dir, cond in CONDITIONS:
                if cond_dir == "noreport":
                    continue
                path = out / model_dir / f"{env_dir}_{cond_dir}_selection" / "selection_response.json"
                if not path.is_file():
                    continue
                s = json.loads(path.read_text(encoding="utf-8"))
                be = s["measures"]["binary_error"]
                bd = s["measures"]["bucket_distance"]
                few = s["n_survivors"] < MIN_SURVIVORS
                rows.append({
                    "model": model, "environment": env, "condition": cond + (" *" if few else ""), "units": s["n_units"],
                    "survivors": s["n_survivors"], "culled": s["n_culled"],
                    "binary_gap": be["gap"]["observed_gap"], "binary_p": be["gap"]["pvalue"],
                    "bucket_gap": bd["gap"]["observed_gap"], "bucket_p": bd["gap"]["pvalue"],
                    "transmission_rho": be["transmission"]["observed_rho"], "transmission_p": be["transmission"]["pvalue"],
                    "pairs": be["transmission"]["n_pairs"], "few_survivors": "yes" if few else "no",
                })
    return rows


# ------------------------------------------------------------------ output


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def markdown(rows: list[dict], columns: list[tuple[str, str, int | None]]) -> str:
    head = "| " + " | ".join(label for _, label, _ in columns) + " |"
    sep = "|" + "|".join("---" for _ in columns) + "|"
    lines = [head, sep]
    for row in rows:
        cells = []
        for key, _, digits in columns:
            value = row.get(key)
            cells.append(fmt(value, digits) if digits is not None else fmt(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", default="traces/stage_b")
    parser.add_argument("--out", default="out/stage_b")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)
    root, out = Path(args.root), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    a, b, c, d = table_a(root), table_b(out), table_c(root, args.seed), table_d(out)
    write_csv(out / "table_a_search_outcomes.csv", a)
    write_csv(out / "table_b_calibration.csv", b)
    write_csv(out / "table_c_intervention.csv", c)
    write_csv(out / "table_d_selection_response.csv", d)

    parts = ["# Stage B results tables", ""]
    parts += ["## A. Search outcomes", "", markdown(a, [
        ("model", "model", None), ("environment", "environment", None), ("condition", "condition", None),
        ("runs", "runs", None), ("solved", "solved", None), ("solved_in_generation_0", "solved in gen. 0", None),
        ("mean_generations", "mean generations", 1), ("candidates", "candidates", None),
        ("valid_share", "valid", 3), ("candidate_success_rate", "success rate", 3),
        ("report_share", "with report", 3), ("mean_stated_chance", "mean stated chance", 3)]), ""]
    parts += ["## B. Calibration (main condition)", "", markdown(b, [
        ("model", "model", None), ("environment", "environment", None), ("n", "n", None),
        ("success_rate", "success rate", 3), ("mean_stated_chance", "mean stated chance", 3),
        ("brier", "Brier", 3), ("ece", "ECE", 3), ("auroc", "AUROC", 3), ("spearman_progress", "Spearman vs progress", 3),
        ("bucket_accuracy", "bucket accuracy", 3), ("mean_signed_bucket_error", "mean signed bucket error", 2)]), ""]
    parts += ["## C. Rationale intervention (pooled over run indices; fitness difference = condition minus genuine, positive = worse)", "",
              markdown(c, [
        ("model", "model", None), ("environment", "environment", None), ("channel", "channel", None),
        ("condition", "condition", None), ("stored_calls", "stored calls", None), ("n", "n", None),
        ("fitness_difference", "fitness diff.", 2), ("ci_low", "CI low", 2), ("ci_high", "CI high", 2),
        ("margin", "margin", 2), ("verdict", "verdict", None), ("excludes_zero", "CI excludes 0", None),
        ("share_worse", "worse", 2), ("share_better", "better", 2), ("success_difference", "success diff.", 3),
        ("mean_distance_to_genuine", "distance to genuine", 2)]), "",
              "Verdict rule (fixed in the design): interval within ± margin → no measurable effect; otherwise interval "
              "excluding zero → effect; otherwise inconclusive. \"worse\" / \"better\" = share of stored calls whose "
              "condition candidate had higher / lower fitness than the genuine one. The corrective hint exists only "
              "when the parent has a failing development case (code) or an inapplicable action (planning), so its n "
              "is smaller than the number of stored calls.", ""]
    parts += ["## D. Selection response (gap = survivor minus culled report error within matched cells; permutation p)", "",
              markdown(d, [
        ("model", "model", None), ("environment", "environment", None), ("condition", "condition", None),
        ("units", "units", None), ("survivors", "survivors", None),
        ("binary_gap", "gap (|stated − outcome|)", 3), ("binary_p", "p", 3),
        ("bucket_gap", "gap (bucket distance)", 3), ("bucket_p", "p", 3),
        ("transmission_rho", "parent→child rho", 3), ("transmission_p", "p", 3), ("pairs", "pairs", None)]), "",
              f"\\* fewer than {MIN_SURVIVORS} survivors: the gap rests on too few candidates to read.", ""]
    (out / "tables.md").write_text("\n".join(parts), encoding="utf-8")
    print("\n".join(parts))
    print(f"-> {out / 'tables.md'} and table_*.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
