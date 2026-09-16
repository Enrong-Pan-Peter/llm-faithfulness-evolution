"""Reading the shared-loop traces for the three analyses (planning and code repair).

One ``CandidateRecord`` per self-reported candidate (``INITIAL_CANDIDATE`` and
``OPERATOR_SAMPLED`` events), with the exact outcome the environment graded:
``success`` (the binary event ``predicted_closeness`` forecasts), ``progress``
(a continuous progress measure in ``[0, 1]``), ``fitness`` and the realised
``bucket`` in the environment's own vocabulary. Survivor labels come from the
``SELECT`` events by id (no name matching is needed in these traces).

Calibration metrics reuse the Contexto array-based functions
(``contexto_solver.calibration.metrics``) so Brier, ECE, reliability bins and
AUROC are computed identically across environments; the rank-based pieces
(Spearman against rank, top-10/100/500 buckets) are replaced by Spearman
against ``progress`` and the environment's ordered buckets.
"""

from __future__ import annotations

import csv
import glob
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import numpy as np
from scipy import stats

from contexto_solver.calibration.metrics import auroc_from_arrays, brier_from_arrays, reliability_from_arrays

BUCKET_ORDERS: dict[str, tuple[str, ...]] = {
    "planning": ("complete", "partial", "invalid"),
    "code_repair": ("all_pass", "most_pass", "some_pass", "none_pass"),
}

CANDIDATE_COLUMNS = [
    "trace_file", "environment", "method", "task_id", "run_index", "run_label", "llm_model", "prompt_fingerprint",
    "selection", "rationale_channel", "generation", "source_event", "origin", "operator", "child_id", "parent_id",
    "parent_fitness", "parent_progress", "rationale_hash", "rationale_present", "predicted_closeness",
    "predicted_closeness_clamped", "predicted_bucket", "self_report_parse_failed", "basis_words_count",
    "parse_ok", "valid", "success", "progress", "fitness", "realized_bucket", "duplicate_of", "survived",
    "survival_generation",
]


@dataclass
class CandidateRecord:
    trace_file: str
    environment: str | None
    method: str | None
    task_id: str | None
    run_index: Any
    run_label: str | None
    llm_model: str | None
    prompt_fingerprint: str | None
    selection: str | None
    rationale_channel: str | None
    generation: int
    source_event: str
    origin: str | None
    operator: str | None
    child_id: str
    parent_id: str | None
    parent_fitness: float | None
    parent_progress: float | None
    rationale_hash: str | None
    rationale_present: bool
    predicted_closeness: float | None
    predicted_closeness_clamped: bool
    predicted_bucket: str | None
    self_report_parse_failed: bool
    basis_words_count: int
    parse_ok: bool
    valid: bool
    success: bool
    progress: float | None
    fitness: float | None
    realized_bucket: str | None
    duplicate_of: str | None
    survived: bool | None = None  # None: never faced a SELECT (final generation) or not in the pool
    survival_generation: int | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    def binary_error(self) -> float | None:
        if self.predicted_closeness is None:
            return None
        return abs(self.predicted_closeness - (1.0 if self.success else 0.0))

    def bucket_distance(self, order: Sequence[str]) -> int | None:
        if self.predicted_bucket is None or self.realized_bucket is None:
            return None
        if self.predicted_bucket not in order or self.realized_bucket not in order:
            return None
        return abs(order.index(self.predicted_bucket) - order.index(self.realized_bucket))

    def row(self) -> dict[str, Any]:
        return {column: getattr(self, column) for column in CANDIDATE_COLUMNS}


# --------------------------------------------------------------------- reading


def load_trace(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} is not a trace (expected a JSON list of events)")
    return data


def expand_paths(patterns: Sequence[str]) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        matches = sorted(glob.glob(pattern))
        paths.extend(matches if matches else [pattern])
    return [path for path in dict.fromkeys(paths) if not path.endswith("summary.json")]


def run_config(events: list[dict[str, Any]]) -> dict[str, Any]:
    for event in events:
        if event.get("event") == "RUN_CONFIG":
            return event.get("details", {}) or {}
    return {}


def survivor_labels(events: list[dict[str, Any]]) -> dict[str, tuple[bool, int]]:
    """``child_id -> (survived, generation of the first SELECT that judged it)``."""
    labels: dict[str, tuple[bool, int]] = {}
    for event in events:
        if event.get("event") != "SELECT":
            continue
        details = event.get("details", {}) or {}
        generation = int(event.get("generation", 0))
        for child_id in details.get("kept", []):
            labels.setdefault(str(child_id), (True, generation))
        for child_id in details.get("discarded", []):
            labels.setdefault(str(child_id), (False, generation))
    return labels


def extract_candidates(events: list[dict[str, Any]], trace_file: str = "") -> list[CandidateRecord]:
    config = run_config(events)
    labels = survivor_labels(events)
    records: list[CandidateRecord] = []
    for event in events:
        name = event.get("event")
        if name not in ("INITIAL_CANDIDATE", "OPERATOR_SAMPLED"):
            continue
        details = event.get("details", {}) or {}
        report = details.get("self_report") or {}
        outcome = details.get("outcome") or {}
        rationale = details.get("rationale") or {}
        basis = (report.get("rationale") or {}).get("basis_words") if isinstance(report.get("rationale"), dict) else None
        child_id = str(details.get("child_id"))
        survived, survival_generation = labels.get(child_id, (None, None))
        records.append(
            CandidateRecord(
                trace_file=trace_file,
                environment=config.get("environment"),
                method=config.get("method"),
                task_id=config.get("task_id"),
                run_index=config.get("run_index"),
                run_label=config.get("run_label"),
                llm_model=config.get("llm_model"),
                prompt_fingerprint=config.get("prompt_fingerprint"),
                selection=config.get("selection"),
                rationale_channel=config.get("rationale_channel"),
                generation=int(event.get("generation", 0)),
                source_event=str(name),
                origin=details.get("origin"),
                operator=details.get("sampled_op"),
                child_id=child_id,
                parent_id=details.get("parent_id"),
                parent_fitness=_float_or_none(details.get("parent_fitness")),
                parent_progress=_float_or_none(details.get("parent_progress")),
                rationale_hash=rationale.get("hash"),
                rationale_present=bool(rationale.get("text")),
                predicted_closeness=_float_or_none(report.get("predicted_closeness")),
                predicted_closeness_clamped=bool(report.get("predicted_closeness_clamped")),
                predicted_bucket=report.get("predicted_bucket"),
                self_report_parse_failed=bool(report.get("self_report_parse_failed", True)),
                basis_words_count=len(basis) if isinstance(basis, list) else 0,
                parse_ok=bool(details.get("parse_ok")),
                valid=bool(outcome.get("valid")),
                success=bool(outcome.get("success")),
                progress=_float_or_none(outcome.get("progress")),
                fitness=_float_or_none(details.get("fitness")),
                realized_bucket=outcome.get("bucket"),
                duplicate_of=details.get("duplicate_of"),
                survived=survived,
                survival_generation=survival_generation,
                raw=details,
            )
        )
    return records


def read_traces(patterns: Sequence[str]) -> tuple[list[CandidateRecord], list[dict[str, Any]]]:
    """Candidates and run configs of every trace matching ``patterns``."""
    records: list[CandidateRecord] = []
    configs: list[dict[str, Any]] = []
    for path in expand_paths(patterns):
        events = load_trace(path)
        configs.append({"trace_file": Path(path).name, **run_config(events)})
        records.extend(extract_candidates(events, Path(path).name))
    return records, configs


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


# ----------------------------------------------------------------- calibration


def _arrays(records: Iterable[CandidateRecord]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    scores, labels, progress = [], [], []
    for record in records:
        if record.predicted_closeness is None or not record.parse_ok:
            continue
        scores.append(record.predicted_closeness)
        labels.append(1 if record.success else 0)
        progress.append(record.progress if record.progress is not None else 0.0)
    return np.asarray(scores, dtype=float), np.asarray(labels, dtype=int), np.asarray(progress, dtype=float)


def bucket_metrics(records: Iterable[CandidateRecord], order: Sequence[str]) -> dict[str, Any]:
    """Accuracy, confusion matrix and mean signed error over the environment's ordered buckets.

    Buckets are ordered best to worst (``order[0]`` is success); signed error is
    ``ordinal(predicted) - ordinal(realized)``, negative = over-optimistic.
    """
    confusion = {p: {r: 0 for r in order} for p in order}
    signed: list[int] = []
    correct = total = 0
    for record in records:
        predicted, realized = record.predicted_bucket, record.realized_bucket
        if predicted not in order or realized not in order or not record.parse_ok:
            continue
        total += 1
        confusion[predicted][realized] += 1
        correct += predicted == realized
        signed.append(order.index(predicted) - order.index(realized))
    return {
        "n": total,
        "accuracy": (correct / total) if total else None,
        "confusion": confusion,
        "mean_signed_bucket_error": (sum(signed) / len(signed)) if signed else None,
        "off_by_one_rate": (sum(1 for value in signed if abs(value) == 1) / total) if total else None,
        "order": list(order),
    }


def spearman_progress(records: Iterable[CandidateRecord]) -> dict[str, Any]:
    """Spearman rho between predicted_closeness and progress (positive = well ordered)."""
    scores, _, progress = _arrays(records)
    n = int(scores.size)
    if n < 2 or len(set(scores.tolist())) < 2 or len(set(progress.tolist())) < 2:
        return {"rho": None, "pvalue": None, "n": n}
    rho, pvalue = stats.spearmanr(scores, progress)
    return {"rho": float(rho), "pvalue": float(pvalue), "n": n}


def metrics_summary(records: Sequence[CandidateRecord], order: Sequence[str]) -> dict[str, Any]:
    records = list(records)
    scores, labels, _ = _arrays(records)
    return {
        "count": len(records),
        "with_report": int(scores.size),
        "success_rate": float(labels.mean()) if labels.size else None,
        "mean_predicted_closeness": float(scores.mean()) if scores.size else None,
        "brier": brier_from_arrays(scores, labels),
        "reliability": reliability_from_arrays(scores, labels),
        "auroc": auroc_from_arrays(scores, labels),
        "spearman_progress": spearman_progress(records),
        "buckets": bucket_metrics(records, order),
    }


def _parent_progress_bin(value: float | None) -> str:
    if value is None:
        return "no_parent"
    if value >= 0.999:
        return "1.0"
    if value >= 0.66:
        return "0.66-0.99"
    if value >= 0.33:
        return "0.33-0.66"
    return "0-0.33"


SPLIT_KEYS: dict[str, Callable[[CandidateRecord], Any]] = {
    "operator": lambda r: r.operator or r.origin,
    "generation": lambda r: r.generation,
    "origin": lambda r: r.source_event,
    "rationale_channel": lambda r: r.rationale_channel,
    "parent_progress_bin": lambda r: _parent_progress_bin(r.parent_progress),
    "task": lambda r: r.task_id,
    "model": lambda r: r.llm_model,
}


def metrics_with_splits(records: Sequence[CandidateRecord], order: Sequence[str], splits: Sequence[str] = tuple(SPLIT_KEYS)) -> dict[str, Any]:
    records = list(records)
    result: dict[str, Any] = {"overall": metrics_summary(records, order), "splits": {}}
    for split in splits:
        key = SPLIT_KEYS[split]
        groups: dict[Any, list[CandidateRecord]] = {}
        for record in records:
            groups.setdefault(key(record), []).append(record)
        result["splits"][split] = {
            str(label): metrics_summary(members, order)
            for label, members in sorted(groups.items(), key=lambda item: (item[0] is None, str(item[0])))
        }
    return result


def write_candidates_csv(path: str | Path, records: Iterable[CandidateRecord]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CANDIDATE_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow(record.row())
    return path


def bucket_order_for(records: Sequence[CandidateRecord], environment: str | None = None) -> tuple[str, ...]:
    name = environment or next((record.environment for record in records if record.environment), None)
    if name not in BUCKET_ORDERS:
        raise ValueError(f"unknown environment {name!r}; expected one of {sorted(BUCKET_ORDERS)}")
    return BUCKET_ORDERS[name]
