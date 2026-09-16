# Stage A pilot (local RTX 3090, qwen3:14b)

Purpose: check that the planning and code-repair pipelines produce traces in the
expected shape and that the numbers move in the expected directions, before
anything is ported to the cluster. Nothing here is a study result. Everything
below is PowerShell, run from the repository root with the virtual environment
active and Ollama serving `qwen3:14b` (`ollama list` shows it; `.env` has
`OLLAMA_BASE_URL=http://localhost:11434/v1`).

Self-reports: the loop reports unless `SELF_REPORT=0` is set in `.env` or
`--self-report 0` is given. Check the first `summary.json` shows
`"self_report": true` before running anything long.

Advance to the cluster only if (1) at least 90 % of model outputs parse
(`model_failures` and `parse_ok` in `summary.json` / the traces), (2) both
success and partial progress occur in each environment, (3) every grade can be
recomputed from the trace (`candidate_text` + task record), (4) the
`serving` block of `RUN_CONFIG` is filled, and (5) the corrective-hint
condition changes candidates in at least some intervention re-runs.

## 0. Offline check first (no model; a minute)

```
python -m pytest
python -m search.run planning --instances task_sets\planning\pilot_3to5.json --task-ids bw03_s6890 --provider scripted --runs-per-task 1 --max-generations 2 --output traces\smoke\planning
python -m search.run code_repair --tasks task_sets\code_repair\quixbugs --task-ids quixbugs_gcd --provider scripted --runs-per-task 1 --max-generations 2 --output traces\smoke\code_repair
python scripts\environment_calibration.py "traces\smoke\planning\*.json" --output-dir out\smoke\planning_calibration
```

(`bw03_s6890` is the first instance of the pilot set; any id from
`task_sets\planning\pilot_3to5.json` works.)

## 1. Planning: find instances the model cannot solve in one shot, then search

qwen3:14b solved every 3-block pilot instance at the first attempt (the first
batch ended in generation 0 with one candidate each), so the pilot instances
must come from a one-shot difficulty check. Three attempts per instance on the
two sets (43 instances, about 130 calls, 1–2 hours):

```
python scripts\planning_direct_solve_check.py --instances task_sets\planning\pilot_3to5.json task_sets\planning\pilot_hard_5to8.json --provider ollama --model qwen3:14b --samples 3 --output out\pilot_a\planning_direct_solve
Get-Content out\pilot_a\planning_direct_solve\direct_solve_check.csv
```

Pick five instances from the `medium` band (solve rate 0.2–0.8; fall back to
`hard` ones with the highest mean progress) and put their ids in the command
below. Two runs each, five generations; a generation is 10 candidate calls, so
at 20–60 s per call one run is 25–60 minutes and the batch several hours:

```
$env:RATIONALE_CHANNEL="inherited"
python -m search.run planning --instances task_sets\planning\pilot_3to5.json task_sets\planning\pilot_hard_5to8.json `
  --task-ids <five ids from the medium band> `
  --provider ollama --model qwen3:14b --runs-per-task 2 --max-generations 5 --seed 0 `
  --label pilotA_planning --output traces\pilot_a\planning
```

Every generation is completed before the run stops (a run always yields the 15
initial candidates, and the generation in which the first success appears is
finished); `--stop-at-success 0` runs all generations regardless. Look at the
first trace before the batch ends:

```
python scripts\environment_calibration.py "traces\pilot_a\planning\*.json" --output-dir out\pilot_a\planning_calibration
Get-Content out\pilot_a\planning_calibration\report.md
```

Then the prospective channel on two of the instances (this is the channel the
paper's cross-environment prediction is about):

```
$env:RATIONALE_CHANNEL="prospective"
python -m search.run planning --instances task_sets\planning\pilot_3to5.json task_sets\planning\pilot_hard_5to8.json --task-ids <two of the five ids> `
  --provider ollama --model qwen3:14b --runs-per-task 2 --max-generations 5 --seed 10 `
  --label pilotA_planning_prospective --output traces\pilot_a\planning_prospective
```

## 2. Code repair, five QuixBugs tasks, two runs each, five generations

```
$env:RATIONALE_CHANNEL="inherited"
python -m search.run code_repair --tasks task_sets\code_repair\quixbugs `
  --task-ids quixbugs_gcd quixbugs_sieve quixbugs_bucketsort quixbugs_kth quixbugs_next_palindrome `
  --provider ollama --model qwen3:14b --runs-per-task 2 --max-generations 5 --seed 0 `
  --label pilotA_code --output traces\pilot_a\code_repair
```

And the memorisation check on the whole QuixBugs set (28 tasks x 5 direct
repair attempts, about 30 minutes), then the same from the specification only:

```
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\quixbugs --provider ollama --model qwen3:14b --samples 5 --output out\pilot_a\memorization_quixbugs_repair
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\quixbugs --provider ollama --model qwen3:14b --samples 5 --mode spec --output out\pilot_a\memorization_quixbugs_spec
```

HumanEvalFix has to be built first (see `task_sets\code_repair\README.md`);
then repeat both commands with `--tasks task_sets\code_repair\humanevalfix`.

## 3. The three analyses on the pilot traces

```
python scripts\environment_calibration.py "traces\pilot_a\planning\*.json" --output-dir out\pilot_a\planning_calibration
python scripts\environment_calibration.py "traces\pilot_a\code_repair\*.json" --output-dir out\pilot_a\code_calibration
python scripts\environment_selection_response.py "traces\pilot_a\planning\*.json" --output-dir out\pilot_a\planning_selection --permutations 1000
python scripts\environment_selection_response.py "traces\pilot_a\code_repair\*.json" --output-dir out\pilot_a\code_selection --permutations 1000
```

Rationale intervention on a handful of stored calls (each call = up to five
conditions = five model calls; 4 calls per trace x 10 traces x 5 = 200 calls,
about an hour):

```
python scripts\environment_rationale_intervention.py "traces\pilot_a\planning\*.json" --events-per-trace 4 --provider ollama --model qwen3:14b --seed 0 --output traces\pilot_a\intervention_planning
python scripts\environment_rationale_intervention.py "traces\pilot_a\code_repair\*.json" --tasks task_sets\code_repair\quixbugs --events-per-trace 4 --provider ollama --model qwen3:14b --seed 0 --output traces\pilot_a\intervention_code
Get-Content traces\pilot_a\intervention_planning\summary.json
```

What to look for: the `corrective_hint` condition should move `fitness` and
`distance_to_parent` relative to `genuine` (the channel is alive); `absent`
and `filler` are the natural-rationale conditions.

## 4. Controls, one instance each (only if 1–3 look right)

```
python -m search.run planning --instances task_sets\planning\pilot_3to5.json task_sets\planning\pilot_hard_5to8.json --task-ids <one of the five ids> --provider ollama --model qwen3:14b --runs-per-task 2 --max-generations 5 --seed 20 --selection random --label pilotA_random --output traces\pilot_a\planning_random_selection
python -m search.run planning --instances task_sets\planning\pilot_3to5.json task_sets\planning\pilot_hard_5to8.json --task-ids <one of the five ids> --provider ollama --model qwen3:14b --runs-per-task 2 --max-generations 5 --seed 30 --selection report_rewarded --label pilotA_report_rewarded --output traces\pilot_a\planning_report_rewarded
python -m search.run planning --instances task_sets\planning\pilot_3to5.json task_sets\planning\pilot_hard_5to8.json --task-ids <one of the five ids> --provider ollama --model qwen3:14b --runs-per-task 2 --max-generations 5 --seed 40 --self-report 0 --label pilotA_noreport --output traces\pilot_a\planning_noreport
```

## 5. Contexto additions (no re-run of the submitted batches)

The corrective-hint condition on the stored qwen prompts of the submitted
study (needs the A1 traces and the rank cache from the Contexto repository, as
in `experiments\contexto\submitted_2026\env\rationale_intervention.env`):

```
python scripts\rationale_intervention_run.py "traces\rq1_A1\*.json" --events-per-trace 40 --seed 0 --conditions corrective_hint --output traces\rationale_intervention_hint
```

The report-rewarded positive control, three games x five seeds, with the
same three games under ordinary (mu + lambda) selection as its matched
baseline (the harmonised method, not the legacy one, since the rule lives
there; both batches share population settings, so they compare directly):

```
$env:SELF_REPORT="1"; $env:RATIONALE_INHERITANCE="1"; $env:SELECTION="report_rewarded"
python -m contexto_solver.experiment --method ea_semantic_operators --provider ollama --ollama-model qwen3:14b --game-numbers 1303 1327 1372 --runs-per-target 5 --random-seed 0 --max-generations 30 --output traces\report_rewarded\contexto_report_rewarded.json
$env:SELECTION="mu_plus_lambda"
python -m contexto_solver.experiment --method ea_semantic_operators --provider ollama --ollama-model qwen3:14b --game-numbers 1303 1327 1372 --runs-per-target 5 --random-seed 0 --max-generations 30 --output traces\report_rewarded\contexto_mu_plus_lambda.json
```

## What the trace files contain

One JSON list of events per run: `RUN_CONFIG` (environment, task, model,
serving, every setting, prompt fingerprint), `INITIAL_CANDIDATE` x 15,
then per generation `SELECT` (kept / discarded ids, pool size 15) and
`OPERATOR_SAMPLED` x 10 (parent, operator, the full prompt, the raw response,
the parsed report, the rationale slot text, the exact outcome), and finally
`SOLVED` or `FAILED`. `summary.json` in the output directory has one row per run.
