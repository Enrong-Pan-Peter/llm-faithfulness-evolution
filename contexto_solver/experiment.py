"""Batch runner for Contexto experiments against the hosted game.

One invocation runs ``--runs-per-target`` repeats for each game number, strictly
one after another (the public game service is rate limited and every game shares
one rank cache). Repeat ``k`` uses search seed ``--random-seed + k``; the model
itself is unseeded. Each run writes its own trace file and a ``RUN_CONFIG``
event with every setting that matters, then the batch summary JSON/CSV is
refreshed. ``--resume`` skips (game, repeat) pairs already present in the
summary.

Methods:

* ``ea_semantic_operators``          the harmonised evolutionary search (new experiments)
* ``ea_semantic_operators_legacy``   the submitted study's search, verbatim
* ``direct_llm_only_sequential``     one guess per generation, no population

Example (one game, five repeats, the harmonised search with reports on):

    SELF_REPORT=1 RATIONALE_INHERITANCE=1 python -m contexto_solver.experiment \\
        --method ea_semantic_operators --provider ollama --ollama-model qwen3:14b \\
        --game-numbers 1303 --runs-per-target 5 --random-seed 0 --max-generations 50 \\
        --output traces/pilot/ea_semantic_operators_game1303.json
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config
from .game_api import ContextoAPI
from .llm_client import LLMClient
from .logger import Logger
from .methods.direct_llm_only_sequential import DirectLLMOnlySequentialConfig, DirectLLMOnlySequentialMethod
from .methods.ea_semantic_operators import EASemanticOperatorsConfig, EASemanticOperatorsMethod
from .methods.ea_semantic_operators_legacy import (
    EASemanticOperatorsLegacyConfig,
    EASemanticOperatorsLegacyMethod,
)
from .self_report import prompt_fingerprint
from .serving import serving_info

METHODS = ("ea_semantic_operators", "ea_semantic_operators_legacy", "direct_llm_only_sequential")
EA_METHODS = {"ea_semantic_operators", "ea_semantic_operators_legacy"}


def main() -> None:
    args = _parse_args()
    run_batch(args)


# ---------------------------------------------------------------------- batch


def run_batch(args: argparse.Namespace) -> list[dict[str, Any]]:
    game_numbers = _parse_game_numbers(args.game_numbers)
    if not game_numbers:
        raise ValueError("Provide at least one game number with --game-numbers.")
    if args.method not in METHODS:
        raise ValueError(f"--method must be one of {METHODS}")

    llm_provider = args.provider or config.LLM_PROVIDER
    llm_model = _model_for_provider(llm_provider, args.model, args.ollama_model)
    serving = serving_info(llm_provider, llm_model, config.OLLAMA_BASE_URL)

    output_path = Path(args.output or f"traces/{args.method}_api_summary.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = _load_existing_rows(output_path) if args.resume else []
    completed = {(row.get("game_number"), row.get("run_index")) for row in rows}
    for run_index in range(args.runs_per_target):
        for game_number in game_numbers:
            if (game_number, run_index) in completed:
                continue
            try:
                rows.append(_run_one(game_number, run_index, args, llm_provider, llm_model, serving))
            except Exception as exc:  # noqa: BLE001 - a failed run is recorded, the batch continues
                error_message = f"{type(exc).__name__}: {exc}"
                print(f"Run failed for game_number={game_number} run_index={run_index}: {error_message}")
                rows.append(_result_row(game_number, run_index, args, llm_provider, llm_model, result=None, error=error_message))
            _write_summary(output_path, args, game_numbers, rows, llm_provider, llm_model, serving)

    _write_summary(output_path, args, game_numbers, rows, llm_provider, llm_model, serving)
    print(f"Wrote JSON summary: {output_path}")
    print(f"Wrote CSV summary: {output_path.with_suffix('.csv')}")
    print(json.dumps(_aggregate(rows), indent=2))
    return rows


def _run_one(
    game_number: int,
    run_index: int,
    args: argparse.Namespace,
    llm_provider: str,
    llm_model: str,
    serving: dict[str, Any],
) -> dict[str, Any]:
    game = ContextoAPI(game_number=game_number, base_url=config.API_BASE_URL, rate_limit=config.API_RATE_LIMIT)
    logger = Logger()
    run_label = f"{args.method}_api_{game_number}_run{run_index + 1}"
    logger.log(-1, "RUN_CONFIG", run_settings(args, game_number, run_index, llm_provider, llm_model, serving))

    llm_client = LLMClient(
        provider=llm_provider,
        api_key=args.api_key or _api_key_for_provider(llm_provider),
        model=llm_model,
    )
    solver = build_method(args.method, game, llm_client, logger, run_label, args, run_index)
    result = solver.solve()
    return _result_row(game_number, run_index, args, llm_provider, llm_model, result=result, error=None)


# ------------------------------------------------------------------ settings


def run_settings(
    args: argparse.Namespace,
    game_number: int,
    run_index: int,
    llm_provider: str,
    llm_model: str,
    serving: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Everything a reader needs to know about one run (the ``RUN_CONFIG`` event)."""
    is_ea = args.method in EA_METHODS
    is_legacy = args.method == "ea_semantic_operators_legacy"
    settings: dict[str, Any] = {
        "trace_format_version": config.TRACE_FORMAT_VERSION,
        "prompt_fingerprint": prompt_fingerprint(),
        "environment": "contexto",
        "game": "api",
        "solver": "llm",
        "method": args.method,
        "mode": "api",
        "target": None,
        "game_number": game_number,
        "run_index": run_index,
        "random_seed": _run_seed(args.random_seed, run_index),
        "max_generations": args.max_generations,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
        "llm_workers": args.llm_workers if is_ea else None,
        "serving": serving or {},
        "self_report": config.SELF_REPORT,
        "rationale_inheritance": config.RATIONALE_INHERITANCE if is_ea else False,
        "rank_cache_enabled": config.RANK_CACHE_ENABLED,
        "api_base_url": config.API_BASE_URL,
        "api_rate_limit": config.API_RATE_LIMIT,
    }
    if args.method == "ea_semantic_operators":
        settings.update(
            {
                "initial_population": config.INITIAL_POPULATION,
                "survivors": config.SURVIVORS,
                "offspring_per_parent": config.OFFSPRING_PER_PARENT,
                "crossover_children": config.CROSSOVER_CHILDREN,
                "offspring_per_generation": config.SURVIVORS * config.OFFSPRING_PER_PARENT + config.CROSSOVER_CHILDREN,
                "pool_size_constant": config.INITIAL_POPULATION
                == config.SURVIVORS + config.SURVIVORS * config.OFFSPRING_PER_PARENT + config.CROSSOVER_CHILDREN,
                "words_per_individual": config.WORDS_PER_INDIVIDUAL,
                "parent_refresh": config.PARENT_REFRESH,
                "parent_refresh_words": config.PARENT_REFRESH_WORDS if config.PARENT_REFRESH else None,
                "selection": config.SELECTION,
                "operator_mix": config.OPERATOR_MIX,
            }
        )
    elif is_legacy:
        settings.update(
            {
                "initial_population": config.LEGACY_INITIAL_POPULATION,
                "survivors": config.LEGACY_SURVIVORS,
                "active_cap": config.LEGACY_ACTIVE_CAP,
                "offspring_per_parent": 1,
                "crossover_children": 1,
                "words_per_individual": config.WORDS_PER_INDIVIDUAL,
                "parent_refresh": True,
                "parent_refresh_words": config.PARENT_REFRESH_WORDS,
                "selection": config.LEGACY_SELECTION,
                "operator_mix": config.OPERATOR_MIX,
                # names written by the submitted study, for readers that look for them
                "self_adaptive_selection_mode": config.LEGACY_SELECTION,
                "self_adaptive_sigma_mode": "frozen_uniform",
                "max_active_hypotheses": config.LEGACY_SURVIVORS,
                "self_adaptive_mu": config.LEGACY_ACTIVE_CAP,
            }
        )
    else:  # direct baseline
        settings.update({"guess_budget": args.max_generations})
    return settings


def build_method(
    method: str,
    game: Any,
    llm_client: LLMClient,
    logger: Logger,
    run_label: str,
    args: argparse.Namespace,
    run_index: int = 0,
):
    run_seed = _run_seed(args.random_seed, run_index)
    if method == "direct_llm_only_sequential":
        return DirectLLMOnlySequentialMethod(
            game,
            llm_client,
            logger,
            DirectLLMOnlySequentialConfig(
                max_generations=args.max_generations,
                trace_dir=config.TRACE_DIR,
                run_label=run_label,
                self_report=config.SELF_REPORT,
            ),
        )

    shared = {
        "max_generations": args.max_generations,
        "candidates_per_hypothesis": config.PARENT_REFRESH_WORDS,
        "starter_words_per_category": config.WORDS_PER_INDIVIDUAL,
        "mutations_per_generation": 0,
        "trace_dir": config.TRACE_DIR,
        "run_label": run_label,
        "llm_workers": args.llm_workers,
        "local_search_rank_threshold": config.LOCAL_SEARCH_RANK_THRESHOLD,
        "self_report": config.SELF_REPORT,
        "rationale_inheritance": config.RATIONALE_INHERITANCE,
    }
    if method == "ea_semantic_operators":
        return EASemanticOperatorsMethod(
            game,
            llm_client,
            logger,
            EASemanticOperatorsConfig(
                initial_categories=config.INITIAL_POPULATION,
                max_active_hypotheses=config.SURVIVORS,
                survivors=config.SURVIVORS,
                offspring_per_parent=config.OFFSPRING_PER_PARENT,
                crossover_children=config.CROSSOVER_CHILDREN,
                parent_refresh=config.PARENT_REFRESH,
                selection=config.SELECTION,
                random_seed=run_seed,
                **shared,
            ),
        )
    if method == "ea_semantic_operators_legacy":
        return EASemanticOperatorsLegacyMethod(
            game,
            llm_client,
            logger,
            EASemanticOperatorsLegacyConfig(
                initial_categories=config.LEGACY_INITIAL_POPULATION,
                max_active_hypotheses=config.LEGACY_SURVIVORS,
                active_cap=config.LEGACY_ACTIVE_CAP,
                selection_mode=config.LEGACY_SELECTION,
                random_seed=run_seed,
                **shared,
            ),
        )
    raise ValueError(f"Unknown method: {method}")


# ------------------------------------------------------------------- outputs


def _result_row(
    game_number: int,
    run_index: int,
    args: argparse.Namespace,
    llm_provider: str,
    llm_model: str,
    result: dict[str, Any] | None,
    error: str | None,
) -> dict[str, Any]:
    result = result or {}
    return {
        "method": args.method,
        "game": "api",
        "game_number": game_number,
        "run_index": run_index,
        "random_seed": _run_seed(args.random_seed, run_index),
        "solved": result.get("solved", False),
        "answer": result.get("answer"),
        "best_word": result.get("best_word"),
        "best_rank": result.get("best_rank"),
        "total_guesses": result.get("total_guesses"),
        "generations": result.get("generations"),
        "trace_path": result.get("trace_path"),
        "self_report": config.SELF_REPORT,
        "error": error,
        "llm_provider": llm_provider,
        "llm_model": llm_model,
    }


def _write_summary(
    output_path: Path,
    args: argparse.Namespace,
    game_numbers: list[int],
    rows: list[dict[str, Any]],
    llm_provider: str,
    llm_model: str,
    serving: dict[str, Any],
) -> None:
    summary = {
        "metadata": {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "method": args.method,
            "game": "api",
            "game_numbers": game_numbers,
            "runs_per_target": args.runs_per_target,
            "random_seed": args.random_seed,
            "max_generations": args.max_generations,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "serving": serving,
            "trace_format_version": config.TRACE_FORMAT_VERSION,
            "prompt_fingerprint": prompt_fingerprint(),
            "self_report": config.SELF_REPORT,
            "rationale_inheritance": config.RATIONALE_INHERITANCE,
            "settings": run_settings(args, game_numbers[0], 0, llm_provider, llm_model, serving),
        },
        "aggregate": _aggregate(rows),
        "runs": rows,
    }
    output_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    _write_csv(output_path.with_suffix(".csv"), rows)


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    finished = [row for row in rows if row.get("error") is None]
    solved = [row for row in finished if row.get("solved")]
    ranks = [row["best_rank"] for row in finished if row.get("best_rank") is not None]
    return {
        "total_runs": len(rows),
        "failed_runs": len(rows) - len(finished),
        "solved_runs": len(solved),
        "solve_rate": (len(solved) / len(finished)) if finished else None,
        "average_guesses_solved": (
            sum(row["total_guesses"] for row in solved) / len(solved) if solved else None
        ),
        "average_best_rank": (sum(ranks) / len(ranks)) if ranks else None,
        "average_generations": (
            sum(row["generations"] for row in finished if row.get("generations") is not None) / len(finished)
            if finished
            else None
        ),
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_existing_rows(output_path: Path) -> list[dict[str, Any]]:
    if not output_path.exists():
        return []
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    rows = payload.get("runs") if isinstance(payload, dict) else None
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


# ------------------------------------------------------------------- helpers


def _parse_game_numbers(raw: str | None) -> list[int]:
    if not raw:
        return []
    return [int(piece) for piece in raw.replace(",", " ").split() if piece.strip()]


def _run_seed(seed: int | None, run_index: int) -> int | None:
    return None if seed is None else seed + run_index


def _api_key_for_provider(provider: str) -> str:
    if provider == "ollama":
        return "ollama"
    if provider == "anthropic":
        return config.ANTHROPIC_API_KEY
    return config.LLM_API_KEY


def _model_for_provider(provider: str, cli_model: str | None, cli_ollama_model: str | None) -> str:
    if provider == "ollama":
        return cli_ollama_model or cli_model or config.OLLAMA_MODEL
    return cli_model or config.LLM_MODEL


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run batch Contexto experiments against the hosted game.")
    parser.add_argument("--game-numbers", required=True, help="Comma/space-separated Contexto game numbers.")
    parser.add_argument("--method", choices=METHODS, default="ea_semantic_operators")
    parser.add_argument("--max-generations", type=int, default=config.MAX_GENERATIONS)
    parser.add_argument("--runs-per-target", type=int, default=1, help="Repeats per game number.")
    parser.add_argument("--random-seed", type=int, help="Search seed of repeat 0; repeat k uses seed + k.")
    parser.add_argument("--llm-workers", type=int, default=config.LLM_WORKERS)
    parser.add_argument("--provider", choices=["openai", "anthropic", "ollama"])
    parser.add_argument("--model")
    parser.add_argument("--ollama-model", help=f"Ollama tag; the study used {', '.join(config.STUDY_OLLAMA_MODELS)}.")
    parser.add_argument("--api-key")
    parser.add_argument("--output", help="Path of the JSON batch summary (CSV written beside it).")
    parser.add_argument("--resume", action="store_true", help="Skip (game, repeat) pairs already in the summary.")
    return parser.parse_args()


if __name__ == "__main__":
    main()
