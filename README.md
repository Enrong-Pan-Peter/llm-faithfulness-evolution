# llm-faithfulness-evolution

Evaluating the self-reports of LLM search operators against exact environment feedback. An LLM proposes candidates inside an evolutionary search loop and, in the same completion, reports its confidence and a rationale; the environment grades every candidate exactly. Three questions, kept separate:

* **Calibration** — does the stated confidence agree with the environment outcome?
* **Rationale intervention** — does a rationale change later candidates? Tested by re-running the exact stored prompt with only the rationale swapped (genuine / unrelated / filler / absent) plus a corrective-hint control.
* **Selection response** — does selecting on task performance change reporting quality, and does report accuracy pass from parent to offspring? With a random-selection control and a report-rewarded positive control.

Environments: **Contexto** (hidden-word game, exact similarity rank per guess; the submitted study, its own search in `contexto_solver`), **Blocksworld planning** (exact plan checker) and **code repair** (sandboxed tests on QuixBugs and HumanEvalFix tasks). The two newer environments share one search loop (`search/`) with the harmonised population settings and one trace format. See `docs/experiment_design_aamas.md` for the study design (docs are kept out of git) and `experiments/pilot_stage_a/README.md` for the pilot command sheet.

## Layout

```
contexto_solver/          Contexto environment: search core, game client, prompts, self-reports, calibration library
  methods/                ea_semantic_operators.py (new experiments), ea_semantic_operators_legacy.py (submitted study,
                          verbatim), direct_llm_only_sequential.py (direct baseline)
  calibration/            trace reader, per-report records, calibration metrics, GloVe comparison, cross-run report
  experiment.py           batch runner (python -m contexto_solver.experiment)
search/                   shared loop for planning and code repair: settings, (mu + lambda) loop, model wrapper,
                          trace reading for the analyses, command line (python -m search.run)
environments/planning/    Blocksworld: generator, exact checker, fitness, S/M/ML/L operators, prompts, search adapter
environments/code_repair/ task format, sandboxed test runner, fitness, S/M/ML/L operators, prompts, search adapter,
                          benchmarks/ (QuixBugs and HumanEvalFix loaders)
task_sets/                planning instance sets (pilot_3to5, study_3to7) and code-repair task sets (quixbugs; build
                          humanevalfix locally, see task_sets/code_repair/README.md)
scripts/                  Contexto: calibration_*, rationale_intervention_*, selection_response_analysis, rank-cache
                          audit/repair, verify_self_reports; new environments: environment_calibration,
                          environment_selection_response, environment_rationale_intervention,
                          build_planning_instances, build_code_repair_tasks, code_repair_memorization_check
tests/                    unit tests, prompt snapshots, trace fixtures from the submitted study, benchmark fixtures
experiments/contexto/submitted_2026/
                          per-condition env files, command sheet, expected headline values, file lists of the raw data
experiments/pilot_stage_a/ command sheet for the local pilot
infra/slurm/              cluster job script for the rationale-intervention runs
```

## Setup (Windows PowerShell; on Linux/WSL use `source .venv/bin/activate`)

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt            # add -r requirements-optional.txt to build HumanEvalFix task sets or draw plots
Copy-Item .env.example .env        # then edit; .env is git-ignored
python -m pytest
```

Running a search needs an Ollama server at `OLLAMA_BASE_URL` (must end in `/v1`) with the model pulled, and outbound HTTPS to the Contexto game service. The analyses read traces only.

## Running Contexto

New experiments (harmonised settings: population 15, 5 survivors, 2 mutation children per survivor, no crossover, fitness fixed at birth, (μ + λ) selection):

```
$env:SELF_REPORT="1"; $env:RATIONALE_INHERITANCE="1"
python -m contexto_solver.experiment --method ea_semantic_operators --provider ollama --ollama-model qwen3:14b `
  --game-numbers 1303 --runs-per-target 5 --random-seed 0 --max-generations 30 `
  --output traces/pilot/ea_semantic_operators_game1303.json
```

Settings are read from the environment (see `.env.example`): `INITIAL_POPULATION`, `SURVIVORS`, `OFFSPRING_PER_PARENT`, `CROSSOVER_CHILDREN`, `PARENT_REFRESH`, `SELECTION` (`mu_plus_lambda` | `random`), `SELF_REPORT`, `RATIONALE_INHERITANCE`.

Reproducing the submitted study: `--method ea_semantic_operators_legacy` with the env files in `experiments/contexto/submitted_2026/env/` (`LEGACY_SELECTION` = `tophalf` | `random`). Direct baseline: `--method direct_llm_only_sequential --max-generations 350` (one guess per generation).

Analysis:

```
python scripts/calibration_table.py   "traces/pilot/ea_semantic_operators_api_*_run*_*.json" --which first_proposed --output out/table.csv
python scripts/calibration_metrics.py "traces/pilot/ea_semantic_operators_api_*_run*_*.json" --which first_proposed --output out/metrics.json
python scripts/calibration_report.py  "traces/pilot/ea_semantic_operators_api_*_run*_*.json" --which first_proposed --output-dir out/report
python scripts/rationale_intervention_run.py "traces/pilot/ea_semantic_operators_api_*_run*_*.json" --events-per-trace 40 --seed 0 --output traces/intervention/pilot
python scripts/rationale_intervention_analysis.py traces/intervention/pilot/rationale_intervention_records.json --output-dir out/intervention
python scripts/selection_response_analysis.py "traces/pilot/ea_semantic_operators_api_*_run*_*.json" --output-dir out/selection
```

Every run record carries the prompt fingerprint; `prompt_fingerprint(trace_format_version=3)` still reproduces the submitted study's value `bd9f2858283673a2`, which the tests check.

## Running planning and code repair

Offline check with a scripted stand-in model (no server), then the same with Ollama:

```
python -m search.run planning --instances task_sets/planning/pilot_3to5.json --task-ids bw03_s6890 --provider scripted --runs-per-task 1 --max-generations 2 --output traces/smoke/planning
python -m search.run planning --instances task_sets/planning/pilot_3to5.json --provider ollama --model qwen3:14b --runs-per-task 5 --max-generations 10 --output traces/pilot/planning
python -m search.run code_repair --tasks task_sets/code_repair/quixbugs --provider ollama --model qwen3:14b --runs-per-task 5 --max-generations 10 --output traces/pilot/code_repair
```

Settings: the population variables above plus `SELECTION` (`mu_plus_lambda` | `random` | `report_rewarded`), `SELF_REPORT`, and `RATIONALE_CHANNEL` (`inherited` | `prospective` | `corrective_hint` | `none`), all overridable on the command line. Analyses:

```
python scripts/environment_calibration.py "traces/pilot/planning/*.json" --output-dir out/planning_calibration
python scripts/environment_selection_response.py "traces/pilot/planning/*.json" --output-dir out/planning_selection --permutations 1000
python scripts/environment_rationale_intervention.py "traces/pilot/planning/*.json" --events-per-trace 10 --provider ollama --output traces/intervention/planning
python scripts/code_repair_memorization_check.py --tasks task_sets/code_repair/quixbugs --provider ollama --samples 5 --output out/memorization_quixbugs
```

## Status

Tests: 295 passed, 4 skipped, all offline. Done: preservation copy of the submitted Contexto code with descriptive names; harmonised population settings and (μ + λ) selection; the `random` and `report_rewarded` selection controls; the corrective-hint intervention condition (Contexto and the new environments); Blocksworld and code-repair environments with S/M/ML/L operator ladders; QuixBugs and HumanEvalFix loaders; the shared search loop with inherited / prospective / corrective-hint rationale channels; the three analyses for the new environments; instance and task sets; the Stage-A pilot command sheet. Not yet run: any model call outside the submitted study.

## License

MIT (see `LICENSE`).
