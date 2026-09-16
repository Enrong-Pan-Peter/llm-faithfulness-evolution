"""Calibration of self-reports in planning / code-repair traces (offline).

Reads shared-loop traces, writes one row per self-reported candidate
(``candidates.csv``), calibration metrics overall and by operator, generation,
origin, rationale channel, parent progress, task and model (``metrics.json``),
and a short ``report.md``. The positive event is the environment's success
event (goal reached / all hidden tests pass), which is what
``predicted_closeness`` forecasts.

Usage (PowerShell):

    python scripts/environment_calibration.py "traces/pilot/planning/*.json" --output-dir out/pilot/planning_calibration
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from search.analysis import bucket_order_for, metrics_with_splits, read_traces, write_candidates_csv  # noqa: E402


def render_report(metrics: dict, configs: list[dict], n_records: int) -> str:
    overall = metrics["overall"]
    fingerprints = sorted({str(config.get("prompt_fingerprint")) for config in configs})
    lines = [
        "# Calibration of self-reports",
        "",
        f"Traces: {len(configs)}; candidates with a report: {overall['with_report']} of {n_records}.",
        f"Prompt fingerprints: {', '.join(fingerprints)}" + (" (MIXED: do not pool without care)" if len(fingerprints) > 1 else ""),
        "",
        f"* success rate: {_fmt(overall['success_rate'])}; mean predicted closeness: {_fmt(overall['mean_predicted_closeness'])}",
        f"* Brier: {_fmt(overall['brier']['brier'])} (n = {overall['brier']['n']})",
        f"* ECE: {_fmt(overall['reliability']['ece'])}",
        f"* AUROC: {_fmt(overall['auroc']['auroc'])} (positives {overall['auroc']['n_pos']}, negatives {overall['auroc']['n_neg']})",
        f"* Spearman (closeness vs progress): {_fmt(overall['spearman_progress']['rho'])} (n = {overall['spearman_progress']['n']})",
        f"* bucket accuracy: {_fmt(overall['buckets']['accuracy'])}; mean signed bucket error: {_fmt(overall['buckets']['mean_signed_bucket_error'])} (negative = over-optimistic)",
        "",
        "## By operator",
        "",
        "| operator | n | success rate | mean closeness | Brier | ECE | AUROC |",
        "|---|---|---|---|---|---|---|",
    ]
    for label, group in metrics["splits"]["operator"].items():
        lines.append(
            f"| {label} | {group['with_report']} | {_fmt(group['success_rate'])} | {_fmt(group['mean_predicted_closeness'])} | "
            f"{_fmt(group['brier']['brier'])} | {_fmt(group['reliability']['ece'])} | {_fmt(group['auroc']['auroc'])} |"
        )
    lines += ["", "## By generation", "", "| generation | n | success rate | mean closeness | Brier |", "|---|---|---|---|---|"]
    for label, group in metrics["splits"]["generation"].items():
        lines.append(f"| {label} | {group['with_report']} | {_fmt(group['success_rate'])} | {_fmt(group['mean_predicted_closeness'])} | {_fmt(group['brier']['brier'])} |")
    return "\n".join(lines) + "\n"


def _fmt(value) -> str:
    return "-" if value is None else f"{value:.3f}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("traces", nargs="+", help="trace files or glob patterns")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--exclude-duplicates", action="store_true", help="drop candidates whose grade was a reused duplicate")
    args = parser.parse_args(argv)

    records, configs = read_traces(args.traces)
    if not records:
        raise SystemExit("no candidate records found")
    if args.exclude_duplicates:
        records = [record for record in records if not record.duplicate_of]
    order = bucket_order_for(records)
    metrics = metrics_with_splits(records, order)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_candidates_csv(output / "candidates.csv", records)
    (output / "metrics.json").write_text(json.dumps({"n_traces": len(configs), "bucket_order": list(order), **metrics}, indent=2), encoding="utf-8")
    (output / "report.md").write_text(render_report(metrics, configs, len(records)), encoding="utf-8")
    overall = metrics["overall"]
    print(f"{len(records)} candidates from {len(configs)} traces -> {output}")
    print(f"Brier {_fmt(overall['brier']['brier'])}, ECE {_fmt(overall['reliability']['ece'])}, AUROC {_fmt(overall['auroc']['auroc'])}, success rate {_fmt(overall['success_rate'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
