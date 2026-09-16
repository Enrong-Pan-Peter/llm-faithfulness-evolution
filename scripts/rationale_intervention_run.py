"""Rationale-intervention runner: re-runs stored mutation prompts with only the rationale changed (run tool, not analysis).

Re-runs stored mutation prompts from instrumented A1-style traces with the
parent-rationale inheritance block swapped across four arms:

- ``genuine``: the stored block, byte-identical;
- ``wrong``: same block head (prefix + basis_words JSON byte-identical), only the
  reason JSON value replaced with a fixed seeded wrong-relation template that
  cites the real parent words;
- ``filler``: same block skeleton with ``basis_words=[]`` and a fixed generic
  sentence of comparable length (no parent-derived tokens);
- ``absent``: block removed entirely (remove-and-check).
- ``corrective_hint`` (added for the extended study; run with
  ``--conditions corrective_hint``): the same slot carries one sentence of
  exact game feedback instead of the rationale, naming a word that the
  game's own ranks show to be among the closest words to the target and
  that the stored prompt does not already contain. This is the control that
  checks whether text in the slot can move the model at all.

Each arm is one fresh LLM call with run-matched decoding (the same
``LLMClient`` code path as the original runs: temperature 0.8, json_object,
5-attempt JSON-validity retry; NO self-report follow-up call - missing fields
stay null). The first proposed word of each arm is graded through the existing
rank-cache read-through path (``ContextoAPI.guess``).

This script calls Ollama and (on cache misses) the Contexto API. It runs only
when invoked explicitly. Input traces are never modified. ``--dry-run`` swaps
in deterministic mocks (no network) for tests.

Usage (PowerShell):

    python scripts/rationale_intervention_run.py traces/rq1_A1/ea_llm_self_adaptive_api_*.json `
        --events-per-trace 40 --seed 0 --output traces/rationale_intervention_batch1
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import json
import random
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from contexto_solver import config as app_config
from contexto_solver.methods.ea_core import _words_from_category
from contexto_solver.operators import Operator, assert_prompt_has_no_sigma_leak
from contexto_solver.calibration.reader import load_trace, run_config
from contexto_solver.self_report import (
    SELF_REPORT_BLOCK,
    empty_self_report,
    hash_injection_text,
    parse_self_report,
)
from scripts.rationale_intervention_templates import filler_reason, wrong_content_reason

ARMS = ("genuine", "wrong", "filler", "absent")
ALL_CONDITIONS = ARMS + ("corrective_hint",)
HINT_MAX_RANK = 10
HINT_FALLBACK_MAX_RANK = 50
BLOCK_PREFIX = "\nThe parent hypothesis's prior rationale"
BASIS_MARKER = "basis_words="
REASON_SEPARATOR = ", reason="


@dataclass
class InterventionEvent:
    """One eligible stored mutation call, decomposed for block surgery."""

    trace_file: str
    game_number: int | None
    llm_provider: str | None
    llm_model: str | None
    prompt_fingerprint: str | None
    child_id: str
    generation: int
    parent_id: str | None
    parent_rank: int | None
    sampled_op: str | None
    sigma_snapshot: list[float] | None
    stored_prompt: str
    base_prompt: str  # stored prompt minus inheritance block minus SELF_REPORT_BLOCK
    genuine_block: str
    block_head: str  # prefix + basis_words JSON, byte-identical for the wrong arm
    genuine_reason: str
    basis_words: list[str] = field(default_factory=list)
    hint_word: str | None = None
    hint_rank: int | None = None


# --- extraction ---------------------------------------------------------------


def corrective_hint_word(events: list[dict[str, Any]], prompt: str) -> tuple[str | None, int | None]:
    """The best-ranked word the trace graded (rank 2..10, else 2..50) that the prompt does not mention.

    Rank 1 (the target itself) is never used. ``(None, None)`` when the trace
    holds no such word; the condition is then skipped for that event.
    """
    ranked: dict[str, int] = {}
    for event in events:
        if event.get("event") != "GUESS":
            continue
        details = event.get("details", {}) or {}
        word, rank = details.get("word"), details.get("rank")
        if isinstance(word, str) and isinstance(rank, int) and rank >= 2:
            ranked[word] = min(rank, ranked.get(word, rank))
    lowered = prompt.lower()
    for limit in (HINT_MAX_RANK, HINT_FALLBACK_MAX_RANK):
        candidates = [(rank, word) for word, rank in ranked.items() if rank <= limit and word.lower() not in lowered]
        if candidates:
            rank, word = min(candidates)
            return word, rank
    return None, None


def corrective_hint_block(word: str, rank: int) -> str:
    """The hint rendered for the rationale slot (leading newline, like the inheritance block)."""
    return (
        f"\nCorrective hint from the game's own feedback: the word {json.dumps(word)} is one of the "
        f"{rank} closest words to the hidden target; propose words closely related to it."
    )


def decompose_block(block: str) -> tuple[str, str, list[str]] | None:
    """Split an inheritance block into (head, reason, basis_words); None if malformed."""
    separator_index = block.find(REASON_SEPARATOR)
    if separator_index == -1 or not block.endswith("."):
        return None
    head = block[:separator_index]
    reason_json = block[separator_index + len(REASON_SEPARATOR) : -1]
    basis_index = head.find(BASIS_MARKER)
    if basis_index == -1:
        return None
    try:
        reason = json.loads(reason_json)
        basis_words = json.loads(head[basis_index + len(BASIS_MARKER) :])
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(reason, str) or not isinstance(basis_words, list):
        return None
    # Round-trip check: surgery must be able to rebuild the block byte-identically.
    if head + REASON_SEPARATOR + json.dumps(reason) + "." != block:
        return None
    return head, reason, [str(word) for word in basis_words]


def extract_events(events: list[dict[str, Any]], trace_file: str) -> tuple[list[InterventionEvent], dict[str, int]]:
    """All eligible intervention events in a trace, plus skip-reason counts.

    Eligible: OPERATOR_SAMPLED records whose self-report carries a non-null
    ``injected_rationale_hash`` (the inheritance block fired) and whose stored
    prompt decomposes cleanly and hash-verifies against that hash.
    """
    trace_config = run_config(events)
    if not trace_config.self_report or not trace_config.rationale_inheritance:
        raise ValueError(
            f"{trace_file}: not an inheritance-instrumented trace "
            f"(self_report={trace_config.self_report}, "
            f"rationale_inheritance={trace_config.rationale_inheritance})."
        )
    raw_config = trace_config.raw
    skips: dict[str, int] = {}

    def skip(reason: str) -> None:
        skips[reason] = skips.get(reason, 0) + 1

    extracted: list[InterventionEvent] = []
    for event in events:
        if event.get("event") != "OPERATOR_SAMPLED":
            continue
        details = event.get("details", {}) or {}
        report = details.get("self_report")
        if not isinstance(report, dict):
            continue
        injected_hash = report.get("injected_rationale_hash")
        if not injected_hash:
            continue  # inheritance did not fire; not eligible by design
        prompt = report.get("self_report_prompt")
        if not isinstance(prompt, str) or not prompt:
            skip("missing_prompt")
            continue
        if not prompt.endswith(SELF_REPORT_BLOCK):
            skip("missing_self_report_block")
            continue
        base_plus_block = prompt[: -len(SELF_REPORT_BLOCK)]
        block_index = base_plus_block.rfind(BLOCK_PREFIX)
        if block_index == -1:
            skip("missing_inheritance_block")
            continue
        block = base_plus_block[block_index:]
        if hash_injection_text(block) != injected_hash:
            skip("hash_mismatch")
            continue
        decomposed = decompose_block(block)
        if decomposed is None:
            skip("block_decompose_failed")
            continue
        head, reason, basis_words = decomposed
        hint_word, hint_rank = corrective_hint_word(events, prompt)
        extracted.append(
            InterventionEvent(
                trace_file=trace_file,
                game_number=trace_config.game_number,
                llm_provider=raw_config.get("llm_provider"),
                llm_model=raw_config.get("llm_model"),
                prompt_fingerprint=trace_config.prompt_fingerprint,
                child_id=str(details.get("child_id")),
                generation=int(event.get("generation", -1)),
                parent_id=details.get("parent_id"),
                parent_rank=details.get("parent_rank") if isinstance(details.get("parent_rank"), int) else None,
                sampled_op=details.get("sampled_op"),
                sigma_snapshot=details.get("sigma_snapshot"),
                stored_prompt=prompt,
                base_prompt=base_plus_block[:block_index],
                genuine_block=block,
                block_head=head,
                genuine_reason=reason,
                basis_words=basis_words,
                hint_word=hint_word,
                hint_rank=hint_rank,
            )
        )
    return extracted, skips


# --- sampling -----------------------------------------------------------------


def sample_stratified(events: list[InterventionEvent], n: int, rng: random.Random) -> list[InterventionEvent]:
    """Seeded sample of up to ``n`` events, stratified across generations.

    Round-robin over generation pools (each shuffled with ``rng``) so every
    generation with eligible events is represented before any is exhausted.
    Returns all events (trace order) when ``n >= len(events)``.
    """
    if n >= len(events):
        return list(events)
    pools: dict[int, list[InterventionEvent]] = {}
    for event in events:
        pools.setdefault(event.generation, []).append(event)
    for generation in pools:
        rng.shuffle(pools[generation])
    ordered_generations = sorted(pools)
    sampled: list[InterventionEvent] = []
    while len(sampled) < n:
        progressed = False
        for generation in ordered_generations:
            if pools[generation]:
                sampled.append(pools[generation].pop())
                progressed = True
                if len(sampled) == n:
                    break
        if not progressed:
            break
    return sampled


# --- arm construction ----------------------------------------------------------


def build_arm_prompts(event: InterventionEvent, seed: int) -> dict[str, str]:
    """The four arm prompts for one event, identical except the inheritance block."""
    event_rng = random.Random(f"{seed}:{event.trace_file}:{event.child_id}")
    wrong_block = (
        event.block_head
        + REASON_SEPARATOR
        + json.dumps(wrong_content_reason(event.basis_words, event_rng))
        + "."
    )
    filler_head = event.genuine_block[: event.genuine_block.find(BASIS_MARKER) + len(BASIS_MARKER)] + "[]"
    target_chars = len(event.genuine_block) - len(filler_head) - len(REASON_SEPARATOR) - 3  # quotes + '.'
    filler_block = filler_head + REASON_SEPARATOR + json.dumps(filler_reason(target_chars)) + "."

    prompts = {
        "genuine": event.base_prompt + event.genuine_block + SELF_REPORT_BLOCK,
        "wrong": event.base_prompt + wrong_block + SELF_REPORT_BLOCK,
        "filler": event.base_prompt + filler_block + SELF_REPORT_BLOCK,
        "absent": event.base_prompt + SELF_REPORT_BLOCK,
    }
    if event.hint_word is not None and event.hint_rank is not None:
        prompts["corrective_hint"] = (
            event.base_prompt + corrective_hint_block(event.hint_word, event.hint_rank) + SELF_REPORT_BLOCK
        )
    assert prompts["genuine"] == event.stored_prompt, "genuine condition must be byte-identical to the stored prompt"

    # Same admissibility guard the solver ran on the genuine prompt at run time.
    if event.sampled_op and event.sigma_snapshot:
        operator = Operator(event.sampled_op)
        sigma = np.asarray(event.sigma_snapshot, dtype=np.float64)
        for prompt in prompts.values():
            assert_prompt_has_no_sigma_leak(prompt, sigma, operator)
    return prompts


# --- LLM call + parse (retry-then-null; no follow-up) ---------------------------


def intervention_call(client: Any, prompt: str) -> dict[str, Any]:
    """One arm call: parse the proposal word and self-report; nulls on failure.

    Matches the run path's JSON-validity retry (inside the client); a persistent
    JSON failure (``ValueError``) becomes a parse-failed record. Connectivity
    errors propagate (fail fast). No self-report follow-up call is issued.
    """
    try:
        parsed, raw = client.complete_json_prompt_with_raw(prompt)
    except ValueError as exc:
        record = dict(empty_self_report())
        record.update(
            {
                "llm_parse_failed": True,
                "llm_error": str(exc),
                "proposed_word": None,
                "proposed_words": [],
                "raw_response": None,
            }
        )
        return record

    words = _words_from_category(parsed) if isinstance(parsed, dict) else []
    report = parse_self_report(parsed if isinstance(parsed, dict) else raw)
    report.update(
        {
            "llm_parse_failed": False,
            "llm_error": None,
            "proposed_word": words[0] if words else None,
            "proposed_words": words,
            "raw_response": raw,
        }
    )
    return report


# --- grading -------------------------------------------------------------------


class RankCacheGrader:
    """Grades words through the existing rank-cache read-through path."""

    def __init__(self) -> None:
        self._apis: dict[int, Any] = {}

    def grade(self, game_number: int, word: str) -> tuple[int | None, bool]:
        """(realized_rank, invalid) for ``word`` in ``game_number``."""
        from contexto_solver.game_api import ContextoAPI

        api = self._apis.get(game_number)
        if api is None:
            api = ContextoAPI(
                game_number=game_number,
                base_url=app_config.API_BASE_URL,
                rate_limit=app_config.API_RATE_LIMIT,
            )
            self._apis[game_number] = api
        rank = api.guess(word)
        if rank == -1:
            return None, True
        return rank, False


class MockGrader:
    """Deterministic offline grader for --dry-run and tests."""

    def grade(self, game_number: int, word: str) -> tuple[int | None, bool]:
        digest = hashlib.sha256(f"{game_number}:{word}".encode("utf-8")).hexdigest()
        if word.startswith("zz"):
            return None, True
        return int(digest[:6], 16) % 900 + 1, False


class MockLLMClient:
    """Deterministic offline LLM stand-in for --dry-run and tests."""

    def complete_json_prompt_with_raw(self, prompt: str) -> tuple[dict[str, Any], str]:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        def letters(chunk: str) -> str:
            # hex -> letters a..p so words pass the solver's [a-z]+ cleaner
            return "".join(chr(ord("a") + int(char, 16)) for char in chunk)

        payload = {
            "name": f"mock direction {digest[:6]}",
            "description": "mock",
            "words": ["word" + letters(digest[:4]), "word" + letters(digest[4:8]), "word" + letters(digest[8:12])],
            "basis_words": ["mock"],
            "reason": "mock reason",
            "predicted_bucket": ("top10", "top100", "top500", "beyond")[int(digest[12], 16) % 4],
            "predicted_closeness": (int(digest[13:16], 16) % 1000) / 1000.0,
        }
        return payload, json.dumps(payload)


# --- record assembly -----------------------------------------------------------

CSV_COLUMNS = [
    "trace_file",
    "game_number",
    "child_id",
    "generation",
    "parent_id",
    "parent_rank",
    "sampled_op",
    "arm",
    "hint_word",
    "hint_rank",
    "prompt_sha256",
    "prompt_chars",
    "llm_parse_failed",
    "proposed_word",
    "proposed_words",
    "proposed_word_invalid",
    "realized_rank",
    "predicted_closeness",
    "predicted_closeness_clamped",
    "predicted_bucket",
    "self_report_parse_failed",
    "basis_words_count",
    "reason_chars",
]


def _arm_record(event: InterventionEvent, arm: str, prompt: str, call: dict[str, Any], realized: tuple[int | None, bool]) -> dict[str, Any]:
    rationale = call.get("rationale") or {}
    basis_words = rationale.get("basis_words") or []
    reason = rationale.get("reason") or ""
    realized_rank, invalid = realized
    return {
        "trace_file": event.trace_file,
        "game_number": event.game_number,
        "child_id": event.child_id,
        "generation": event.generation,
        "parent_id": event.parent_id,
        "parent_rank": event.parent_rank,
        "sampled_op": event.sampled_op,
        "arm": arm,
        "hint_word": event.hint_word if arm == "corrective_hint" else None,
        "hint_rank": event.hint_rank if arm == "corrective_hint" else None,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "prompt_chars": len(prompt),
        "llm_parse_failed": bool(call.get("llm_parse_failed")),
        "llm_error": call.get("llm_error"),
        "proposed_word": call.get("proposed_word"),
        "proposed_words": list(call.get("proposed_words") or []),
        "proposed_word_invalid": invalid,
        "realized_rank": realized_rank,
        "predicted_closeness": call.get("predicted_closeness"),
        "predicted_closeness_clamped": bool(call.get("predicted_closeness_clamped")),
        "predicted_bucket": call.get("predicted_bucket"),
        "self_report_parse_failed": bool(call.get("self_report_parse_failed")),
        "rationale": call.get("rationale"),
        "basis_words_count": len(basis_words),
        "reason_chars": len(reason),
        "raw_response": call.get("raw_response"),
    }


# --- main flow -------------------------------------------------------------------


def run_intervention(
    trace_paths: list[str],
    *,
    events_per_trace: int,
    seed: int,
    client_factory: Callable[[str | None, str | None], Any],
    grader: Any,
    conditions: tuple[str, ...] = ARMS,
) -> dict[str, Any]:
    """Re-run sampled events from each trace; returns {metadata, records}."""
    records: list[dict[str, Any]] = []
    skipped_conditions = 0
    per_trace_meta: list[dict[str, Any]] = []
    clients: dict[tuple[str | None, str | None], Any] = {}

    for path in trace_paths:
        trace_file = Path(path).name
        events = load_trace(path)
        eligible, skips = extract_events(events, trace_file)
        trace_config = run_config(events)
        if trace_config.game != "api" or trace_config.game_number is None:
            raise ValueError(f"{trace_file}: intervention grading requires an api trace with a game_number.")

        rng = random.Random(f"{seed}:{trace_file}")
        sampled = sample_stratified(eligible, events_per_trace, rng)
        per_trace_meta.append(
            {
                "trace_file": trace_file,
                "game_number": trace_config.game_number,
                "llm_model": trace_config.raw.get("llm_model"),
                "llm_provider": trace_config.raw.get("llm_provider"),
                "prompt_fingerprint": trace_config.prompt_fingerprint,
                "eligible_events": len(eligible),
                "sampled_events": len(sampled),
                "shortfall": max(0, events_per_trace - len(eligible)),
                "skipped": skips,
            }
        )

        for event in sampled:
            client_key = (event.llm_provider, event.llm_model)
            client = clients.get(client_key)
            if client is None:
                client = client_factory(event.llm_provider, event.llm_model)
                clients[client_key] = client
            prompts = build_arm_prompts(event, seed)
            for arm in conditions:
                if arm not in prompts:
                    skipped_conditions += 1
                    continue
                call = intervention_call(client, prompts[arm])
                word = call.get("proposed_word")
                realized = grader.grade(event.game_number, word) if word else (None, False)
                records.append(_arm_record(event, arm, prompts[arm], call, realized))

    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "seed": seed,
        "events_per_trace": events_per_trace,
        "arms": list(conditions),
        "conditions": list(conditions),
        "skipped_conditions": skipped_conditions,
        "traces": per_trace_meta,
        "total_events": sum(m["sampled_events"] for m in per_trace_meta),
        "total_records": len(records),
    }
    return {"metadata": metadata, "records": records}


def write_outputs(result: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "rationale_intervention_records.json"
    json_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    csv_path = out_dir / "rationale_intervention_records.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for record in result["records"]:
            row = dict(record)
            row["proposed_words"] = ";".join(row.get("proposed_words") or [])
            writer.writerow(row)
    return json_path, csv_path


def _expand_paths(patterns: list[str]) -> list[str]:
    paths: list[str] = []
    for pattern in patterns:
        matches = glob.glob(pattern)
        if matches:
            paths.extend(sorted(matches))
        elif Path(pattern).exists():
            paths.append(pattern)
    return list(dict.fromkeys(paths))


def _real_client_factory(provider: str | None, model: str | None) -> Any:
    from contexto_solver.llm_client import LLMClient

    if not provider or not model:
        raise ValueError("Trace RUN_CONFIG must carry llm_provider and llm_model for the intervention run.")
    return LLMClient(provider=provider, api_key="", model=model)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rationale intervention: re-run stored prompts with the rationale swapped (calls Ollama + rank cache/API).")
    parser.add_argument("traces", nargs="+", help="A1-style raw trace JSON path(s) or glob(s).")
    parser.add_argument("--events-per-trace", type=int, default=40, help="Sampled events per trace (default 40).")
    parser.add_argument("--seed", type=int, default=0, help="Sampling/template seed (default 0).")
    parser.add_argument("--output", default=None, help="Output directory (default traces/rationale_intervention_<timestamp>).")
    parser.add_argument("--dry-run", action="store_true", help="Deterministic mocks; no network.")
    parser.add_argument(
        "--conditions", nargs="+", choices=ALL_CONDITIONS, default=list(ARMS),
        help="Conditions to run (default: the four of the submitted study; add corrective_hint for the control).",
    )
    args = parser.parse_args()
    conditions = tuple(args.conditions)

    paths = _expand_paths(args.traces)
    if not paths:
        raise SystemExit("No trace files matched the given path(s).")
    output_dir = args.output or f"{app_config.TRACE_DIR}/rationale_intervention_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    if args.dry_run:
        result = run_intervention(
            paths,
            events_per_trace=args.events_per_trace,
            seed=args.seed,
            client_factory=lambda provider, model: MockLLMClient(),
            grader=MockGrader(),
            conditions=conditions,
        )
    else:
        result = run_intervention(
            paths,
            events_per_trace=args.events_per_trace,
            seed=args.seed,
            client_factory=_real_client_factory,
            grader=RankCacheGrader(),
            conditions=conditions,
        )

    json_path, csv_path = write_outputs(result, output_dir)
    metadata = result["metadata"]
    print(f"Traces: {len(metadata['traces'])}  events: {metadata['total_events']}  records: {metadata['total_records']}  conditions: {', '.join(metadata['conditions'])}")
    if metadata["skipped_conditions"]:
        print(f"  {metadata['skipped_conditions']} event/condition pairs skipped (no usable corrective hint in the trace)")
    for trace_meta in metadata["traces"]:
        print(
            f"  - {trace_meta['trace_file']}: eligible={trace_meta['eligible_events']} "
            f"sampled={trace_meta['sampled_events']} shortfall={trace_meta['shortfall']} "
            f"skipped={trace_meta['skipped'] or '{}'}"
        )
    print(f"Wrote {json_path}")
    print(f"Wrote {csv_path}")


if __name__ == "__main__":
    main()
