"""Rationale intervention for planning / code-repair traces: re-run stored prompts with only the slot changed.

For sampled mutation calls whose stored prompt carried a rationale in its slot
(``RATIONALE_CHANNEL`` = ``inherited`` or ``prospective``), the exact stored
prompt is re-run under five conditions that differ only in the slot text:

- ``genuine``          the stored prompt, byte-identical;
- ``unrelated``        the slot text of a different task's call (same channel);
- ``filler``           a neutral sentence of comparable length in the same block skeleton;
- ``absent``           the slot removed;
- ``corrective_hint``  the environment's exact hint about the parent (first invalid
                       action / first failing development case), the control that
                       checks whether the slot can move the model at all.

Every condition is one fresh model call per sample, run-matched decoding
(the Contexto client). Each returned candidate is graded by the environment
and recorded with its outcome, its distance to the parent candidate and its
distance to the genuine sample(s) of the same call. Outputs: one JSON record
per (call, condition, sample), a per-call paired-differences CSV against the
genuine sample, and a summary with bootstrap intervals and the
practical-equivalence margin (half the interquartile spread of the genuine
samples' score).

Usage (PowerShell):

    python scripts/environment_rationale_intervention.py "traces/pilot/planning/*.json" `
        --events-per-trace 10 --provider ollama --model qwen3:14b --seed 0 --output traces/intervention/planning
    python scripts/environment_rationale_intervention.py "traces/pilot/code_repair/*.json" `
        --tasks task_sets/code_repair/quixbugs --events-per-trace 10 --provider ollama --output traces/intervention/code
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from contexto_solver import config as app_config  # noqa: E402
from search.analysis import expand_paths, load_trace, run_config  # noqa: E402
from search.model import ModelClient, ScriptedModel  # noqa: E402
from search.reports import parse_report  # noqa: E402
from search.run import scripted_responder  # noqa: E402

CONDITIONS = ("genuine", "unrelated", "filler", "absent", "corrective_hint")
FILLER_SENTENCES = (
    "This step follows the general approach used so far and keeps the overall structure the same.",
    "The change is meant to be consistent with the earlier reasoning and the information given above.",
    "Proceed carefully and keep the parts that already work while adjusting the rest as needed.",
    "The plan is to make a careful adjustment that respects the rules and the feedback shown above.",
)


@dataclass
class StoredCall:
    trace_file: str
    environment: str
    task_id: str
    task: dict[str, Any]
    child_id: str
    parent_id: str
    parent_text: str
    generation: int
    operator: str | None
    channel: str
    slot_text: str
    prompt: str
    genuine_outcome: dict[str, Any]


# --------------------------------------------------------------- environments


def build_environment(call: StoredCall, tasks_root: Path | None) -> Any:
    if call.environment == "planning":
        from environments.planning.blocksworld import Instance
        from environments.planning.search_adapter import PlanningSearchEnvironment

        return PlanningSearchEnvironment(Instance.from_dict(call.task), optimal_length=call.task.get("optimal_plan_length"))
    if call.environment == "code_repair":
        from environments.code_repair.search_adapter import CodeRepairSearchEnvironment
        from environments.code_repair.tasks import load_task

        if tasks_root is None:
            raise SystemExit("code_repair traces need --tasks <task set directory>")
        return CodeRepairSearchEnvironment(load_task(Path(tasks_root) / call.task_id), timeout_s=call.task.get("runner_timeout_s", 5.0))
    raise SystemExit(f"unknown environment {call.environment!r}")


# ---------------------------------------------------------------- extraction


def extract_calls(events: list[dict[str, Any]], trace_file: str) -> list[StoredCall]:
    config = run_config(events)
    by_id: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("event") in ("INITIAL_CANDIDATE", "OPERATOR_SAMPLED"):
            details = event.get("details", {}) or {}
            by_id[str(details.get("child_id"))] = details
    calls: list[StoredCall] = []
    for event in events:
        if event.get("event") != "OPERATOR_SAMPLED":
            continue
        details = event.get("details", {}) or {}
        rationale = details.get("rationale") or {}
        text = rationale.get("text") or ""
        prompt = details.get("prompt") or ""
        if not text or rationale.get("channel") not in ("inherited", "prospective") or prompt.count(text) != 1:
            continue
        parent = by_id.get(str(details.get("parent_id")))
        if parent is None or not parent.get("parse_ok"):
            continue
        calls.append(
            StoredCall(
                trace_file=trace_file,
                environment=str(config.get("environment")),
                task_id=str(config.get("task_id")),
                task=config.get("task") or {},
                child_id=str(details.get("child_id")),
                parent_id=str(details.get("parent_id")),
                parent_text=str(parent.get("candidate_text") or ""),
                generation=int(event.get("generation", 0)),
                operator=details.get("sampled_op"),
                channel=str(rationale.get("channel")),
                slot_text=text,
                prompt=prompt,
                genuine_outcome=details.get("outcome") or {},
            )
        )
    return calls


def sample_calls(calls: list[StoredCall], n: int, rng: random.Random) -> list[StoredCall]:
    """Up to ``n`` calls spread over generations (round-robin over generation groups)."""
    by_generation: dict[int, list[StoredCall]] = {}
    for call in calls:
        by_generation.setdefault(call.generation, []).append(call)
    for group in by_generation.values():
        rng.shuffle(group)
    chosen: list[StoredCall] = []
    while len(chosen) < n and any(by_generation.values()):
        for generation in sorted(by_generation):
            if by_generation[generation] and len(chosen) < n:
                chosen.append(by_generation[generation].pop())
    return chosen


# ------------------------------------------------------------------ prompts


def filler_text(call: StoredCall, rng: random.Random) -> str:
    """Same block skeleton as the stored slot text, neutral content of similar length."""
    target = max(40, len(call.slot_text) - 60)
    sentence = rng.choice(FILLER_SENTENCES)
    body = sentence
    while len(body) < target:
        body += " " + rng.choice(FILLER_SENTENCES)
    body = body[:target].rsplit(" ", 1)[0].rstrip(".,;") + "."
    if call.channel == "inherited":
        return f"\nThe parent hypothesis's prior rationale (for context only; do not copy blindly): basis_words=[], reason={json.dumps(body)}."
    if call.environment == "planning":
        return f"\nStrategy written before this plan (follow it): {json.dumps(body)}."
    return f"\nDiagnosis written before this repair: {json.dumps(body)}."


def condition_slots(call: StoredCall, environment: Any, donors: list[StoredCall], rng: random.Random, parent: Any) -> dict[str, str | None]:
    """The slot text of every condition (``None`` when a condition is not available for this call)."""
    slots: dict[str, str | None] = {"genuine": call.slot_text}
    unrelated = [donor for donor in donors if donor.task_id != call.task_id and donor.channel == call.channel] or [
        donor for donor in donors if donor.parent_id != call.parent_id and donor.channel == call.channel and donor.slot_text != call.slot_text
    ]
    slots["unrelated"] = rng.choice(unrelated).slot_text if unrelated else None
    slots["filler"] = filler_text(call, rng)
    slots["absent"] = ""
    hint = environment.corrective_hint_block(parent)
    slots["corrective_hint"] = hint if hint else None
    return slots


def condition_prompt(call: StoredCall, environment: Any, slot: str) -> str:
    prompt = call.prompt.replace(call.slot_text, slot, 1)
    if slot == call.slot_text:
        assert prompt == call.prompt
    environment.check_prompt(prompt)
    return prompt


# ------------------------------------------------------------------ running


def run_intervention(args: argparse.Namespace) -> dict[str, Any]:
    rng = random.Random(args.seed)
    calls: list[StoredCall] = []
    for path in expand_paths(args.traces):
        events = load_trace(path)
        calls.extend(sample_calls(extract_calls(events, Path(path).name), args.events_per_trace, rng))
    if not calls:
        raise SystemExit("no eligible stored calls (need traces run with RATIONALE_CHANNEL=inherited or prospective)")
    tasks_root = Path(args.tasks) if args.tasks else None
    environments: dict[str, Any] = {}
    parents: dict[tuple[str, str], Any] = {}
    records: list[dict[str, Any]] = []
    model = None
    if args.provider != "scripted":
        model = ModelClient(args.provider, args.model or app_config.OLLAMA_MODEL)

    for index, call in enumerate(calls):
        environment = environments.get(call.task_id)
        if environment is None:
            environment = environments[call.task_id] = build_environment(call, tasks_root)
        parent_key = (call.trace_file, call.parent_id)
        if parent_key not in parents:
            parents[parent_key] = _rebuild_parent(environment, call)
        parent = parents[parent_key]
        if args.provider == "scripted":
            model = ScriptedModel(scripted_responder(environment, args.seed + index))
        slots = condition_slots(call, environment, calls, rng, parent)
        genuine_texts: list[str] = []
        for condition in CONDITIONS:
            slot = slots.get(condition)
            if slot is None:
                continue
            prompt = condition_prompt(call, environment, slot)
            for sample in range(args.samples_per_condition):
                parsed, raw, error = model.complete_json(prompt)
                record = _grade(environment, call, condition, sample, prompt, slot, parsed, raw, error, genuine_texts)
                if condition == "genuine" and record["candidate_text"]:
                    genuine_texts.append(record["candidate_text"])
                records.append(record)
        print(f"[{index + 1}/{len(calls)}] {call.trace_file} {call.child_id}: done")

    summary = summarize(records)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "provider": args.provider,
        "model": getattr(model, "model", None),
        "seed": args.seed,
        "events_per_trace": args.events_per_trace,
        "samples_per_condition": args.samples_per_condition,
        "n_calls": len(calls),
        "n_records": len(records),
        "summary": summary,
        "records": records,
    }


def _rebuild_parent(environment: Any, call: StoredCall) -> Any:
    from search.individual import Individual

    parsed = environment.parse_candidate({"plan": call.parent_text.splitlines()} if call.environment == "planning" else {"program": call.parent_text})
    candidate, text = parsed if parsed else (None, call.parent_text)
    evaluation = environment.evaluate(candidate if candidate is not None else call.parent_text)
    outcome = environment.outcome(evaluation)
    return Individual(
        individual_id=call.parent_id, generation=call.generation - 1, origin="rebuilt", operator=None, parent_id=None,
        parent_fitness=None, parent_progress=None, candidate=candidate, candidate_text=text, candidate_key="",
        fitness=float(outcome["score"]), outcome=outcome, evaluation=evaluation, self_report={}, rationale={},
        prompt="", raw_response=None, parse_ok=parsed is not None,
    )


def _grade(environment: Any, call: StoredCall, condition: str, sample: int, prompt: str, slot: str, parsed: Any, raw: str | None, error: str | None, genuine_texts: list[str]) -> dict[str, Any]:
    parsed_candidate = environment.parse_candidate(parsed) if parsed is not None else None
    report = parse_report(parsed, environment.buckets, raw)
    record: dict[str, Any] = {
        "trace_file": call.trace_file,
        "environment": call.environment,
        "task_id": call.task_id,
        "child_id": call.child_id,
        "parent_id": call.parent_id,
        "generation": call.generation,
        "operator": call.operator,
        "channel": call.channel,
        "condition": condition,
        "sample": sample,
        "prompt_chars": len(prompt),
        "slot_text": slot,
        "raw_response": raw,
        "error": error,
        "parse_ok": parsed_candidate is not None,
        "candidate_text": "",
        "success": None,
        "progress": None,
        "fitness": None,
        "bucket": None,
        "distance_to_parent": None,
        "distance_to_genuine": None,
        "predicted_closeness": report.get("predicted_closeness"),
        "predicted_bucket": report.get("predicted_bucket"),
        "stored_genuine_success": call.genuine_outcome.get("success"),
        "stored_genuine_fitness": call.genuine_outcome.get("score"),
    }
    if parsed_candidate is None:
        return record
    candidate, text = parsed_candidate
    outcome = environment.outcome(environment.evaluate(candidate))
    record.update(
        {
            "candidate_text": text,
            "success": bool(outcome["success"]),
            "progress": outcome.get("progress"),
            "fitness": outcome.get("score"),
            "bucket": outcome.get("bucket"),
            "distance_to_parent": environment.distance(text, call.parent_text),
            "distance_to_genuine": (float(np.mean([environment.distance(text, other) for other in genuine_texts])) if genuine_texts else None),
        }
    )
    return record


# ------------------------------------------------------------------ summary


def paired_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per stored call: each condition's first sample against the genuine first sample."""
    by_call: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for record in records:
        if record["sample"] != 0 or not record["parse_ok"]:
            continue
        by_call.setdefault((record["trace_file"], record["child_id"]), {})[record["condition"]] = record
    rows = []
    for (trace_file, child_id), conditions in by_call.items():
        genuine = conditions.get("genuine")
        if genuine is None:
            continue
        for condition, record in conditions.items():
            if condition == "genuine":
                continue
            for metric in ("success", "progress", "fitness", "distance_to_parent"):
                if genuine.get(metric) is None or record.get(metric) is None:
                    continue
                rows.append(
                    {
                        "trace_file": trace_file,
                        "child_id": child_id,
                        "condition": condition,
                        "metric": metric,
                        "genuine_value": float(genuine[metric]),
                        "condition_value": float(record[metric]),
                        "difference": float(record[metric]) - float(genuine[metric]),
                    }
                )
    return rows


def summarize(records: list[dict[str, Any]], bootstrap: int = 2000, seed: int = 0) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    rows = paired_rows(records)
    genuine_scores = [record["fitness"] for record in records if record["condition"] == "genuine" and record["fitness"] is not None]
    margin = None
    if len(genuine_scores) >= 4:
        q1, q3 = np.percentile(genuine_scores, [25, 75])
        margin = float(q3 - q1) / 2.0
    summary: dict[str, Any] = {"practical_equivalence_margin_fitness": margin, "n_paired_rows": len(rows), "conditions": {}}
    for condition in CONDITIONS[1:]:
        block: dict[str, Any] = {}
        for metric in ("success", "progress", "fitness", "distance_to_parent"):
            differences = np.asarray([row["difference"] for row in rows if row["condition"] == condition and row["metric"] == metric], dtype=float)
            if differences.size == 0:
                block[metric] = {"n": 0}
                continue
            means = [float(rng.choice(differences, size=differences.size, replace=True).mean()) for _ in range(bootstrap)]
            lower, upper = np.percentile(means, [2.5, 97.5])
            entry = {"n": int(differences.size), "mean_difference": float(differences.mean()), "ci95": [float(lower), float(upper)]}
            if metric == "fitness" and margin is not None:
                entry["within_margin"] = bool(-margin <= lower and upper <= margin)
            block[metric] = entry
        summary["conditions"][condition] = block
    return summary


def write_outputs(result: dict[str, Any], output_dir: str | Path) -> Path:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "rationale_intervention_records.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    rows = paired_rows(result["records"])
    with (output / "paired_differences.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["trace_file", "child_id", "condition", "metric", "genuine_value", "condition_value", "difference"])
        writer.writeheader()
        writer.writerows(rows)
    (output / "summary.json").write_text(json.dumps(result["summary"], indent=2), encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("traces", nargs="+")
    parser.add_argument("--tasks", default=None, help="code_repair: the task set directory the traces were run on")
    parser.add_argument("--events-per-trace", type=int, default=10)
    parser.add_argument("--samples-per-condition", type=int, default=1)
    parser.add_argument("--provider", default=app_config.LLM_PROVIDER)
    parser.add_argument("--model", default=None)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = run_intervention(args)
    output = write_outputs(result, args.output)
    for condition, block in result["summary"]["conditions"].items():
        success = block.get("success", {})
        fitness = block.get("fitness", {})
        print(f"{condition}: success difference {_fmt(success.get('mean_difference'))} (n = {success.get('n', 0)}); "
              f"fitness difference {_fmt(fitness.get('mean_difference'))} CI {fitness.get('ci95')}")
    print(f"margin (half IQR of genuine fitness): {_fmt(result['summary']['practical_equivalence_margin_fitness'])} -> {output}")
    return 0


def _fmt(value) -> str:
    return "-" if value is None else f"{value:.3f}"


if __name__ == "__main__":
    sys.exit(main())
