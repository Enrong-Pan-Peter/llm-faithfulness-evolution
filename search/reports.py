"""Self-report parsing for the shared loop (same record shape as Contexto).

Every candidate prompt asks, in the same JSON object as the candidate, for
``basis_words``, ``reason``, ``predicted_bucket`` and ``predicted_closeness``
(in that order, exactly as in Contexto). ``predicted_closeness`` is the
model's estimated chance that the environment's success event happens for
the returned candidate; ``predicted_bucket`` is the environment's categorical
companion (``complete / partial / invalid`` for plans, ``all_pass / most_pass
/ some_pass / none_pass`` for programs).

The parsed record has the Contexto keys (``predicted_closeness``,
``predicted_closeness_clamped``, ``predicted_bucket``, ``rationale``,
``self_report_parse_failed``, ``self_report_raw``, ``injected_rationale_hash``,
``rationale_truncated``) so trace readers written for Contexto records keep
working; only the bucket vocabulary is environment-specific.
"""

from __future__ import annotations

from typing import Any, Sequence

from contexto_solver.self_report import (
    _coerce_to_dict,
    _sanitize_basis_words,
    _sanitize_reason,
    clamp_predicted_closeness,
)


def parse_bucket(value: Any, buckets: Sequence[str]) -> str | None:
    """Coerce a bucket value to one of ``buckets`` (case, spaces, ``_``/``-`` ignored)."""
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace(" ", "").replace("-", "_")
    for bucket in buckets:
        if normalized == bucket.lower().replace("-", "_") or normalized == bucket.lower().replace("_", ""):
            return bucket
    return None


def empty_report(raw: str | None = None) -> dict[str, Any]:
    return {
        "predicted_closeness": None,
        "predicted_closeness_clamped": False,
        "predicted_bucket": None,
        "rationale": None,
        "self_report_parse_failed": True,
        "self_report_raw": raw,
        "injected_rationale_hash": None,
        "rationale_truncated": False,
    }


def parse_report(source: Any, buckets: Sequence[str], raw: str | None = None) -> dict[str, Any]:
    """Parse the four report keys from a parsed object or raw text. Never raises."""
    data = _coerce_to_dict(source)
    if data is None:
        return empty_report(raw)
    closeness, clamped = clamp_predicted_closeness(data.get("predicted_closeness"))
    rationale = {
        "basis_words": _sanitize_basis_words(data.get("basis_words")),
        "reason": _sanitize_reason(data.get("reason")),
    }
    parse_failed = closeness is None and not rationale["basis_words"] and not rationale["reason"]
    return {
        "predicted_closeness": closeness,
        "predicted_closeness_clamped": clamped,
        "predicted_bucket": parse_bucket(data.get("predicted_bucket"), buckets),
        "rationale": rationale,
        "self_report_parse_failed": parse_failed,
        "self_report_raw": raw,
        "injected_rationale_hash": None,
        "rationale_truncated": False,
    }


def report_error(report: dict[str, Any] | None, success: bool) -> float | None:
    """|predicted_closeness - 1{success}|, or ``None`` when no closeness was parsed."""
    if not isinstance(report, dict) or report.get("predicted_closeness") is None:
        return None
    return abs(float(report["predicted_closeness"]) - (1.0 if success else 0.0))
