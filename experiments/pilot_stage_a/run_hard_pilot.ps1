# Local pilot of the full pipeline on hard tasks (the Stage B settings), qwen3:14b.
# Start it and leave it; it can be stopped and restarted (finished runs are skipped):
#
#     powershell -ExecutionPolicy Bypass -File experiments\pilot_stage_a\run_hard_pilot.ps1
#
# Three planning instances and three code tasks of the Stage B study sets,
# 2 runs each, 10 generations, main condition; then the rationale
# intervention on the stored prompts; then the two analyses. Nothing here
# was ever solved in one shot by qwen3:14b, so the search really runs:
# about 2 min per planning call and 75 s per code call, up to 115 calls per
# run, so up to 23 h for the planning runs, 14 h for the code runs and 6 h
# for the intervention (less whenever a run succeeds early). Traces go to
# traces\stage_a_hard\, analyses to out\stage_a_hard\.

$ErrorActionPreference = "Stop"
$model = "qwen3:14b"
New-Item -ItemType Directory -Force out\stage_a_hard | Out-Null
Start-Transcript -Path out\stage_a_hard\transcript.txt -Append

$planningIds = "bw07_s6088", "bw07_s5132", "bw07_s0027"
$codeIds = "quixbugs_mergesort_d3_anon", "humanevalfix_040_d3_anon", "humanevalfix_019_d3_anon"

Write-Host "=== 1. planning search: 3 instances x 2 runs x 10 generations"
python -m search.run planning --instances task_sets\planning\stage_b_12.json --task-ids $planningIds --provider ollama --model $model --runs-per-task 2 --max-generations 10 --seed 0 --selection mu_plus_lambda --rationale-channel inherited --self-report 1 --label stageA_hard --output traces\stage_a_hard\planning --skip-existing

Write-Host "=== 2. code-repair search: 3 tasks x 2 runs x 10 generations"
python -m search.run code_repair --tasks task_sets\code_repair\stage_b_12 --task-ids $codeIds --provider ollama --model $model --runs-per-task 2 --max-generations 10 --seed 0 --selection mu_plus_lambda --rationale-channel inherited --self-report 1 --label stageA_hard --output traces\stage_a_hard\code_repair --skip-existing

Write-Host "=== 3. rationale intervention, 5 stored calls per trace, five conditions"
python scripts\environment_rationale_intervention.py "traces\stage_a_hard\planning\*.json" --events-per-trace 5 --provider ollama --model $model --seed 0 --output traces\stage_a_hard\intervention_planning
python scripts\environment_rationale_intervention.py "traces\stage_a_hard\code_repair\*.json" --tasks task_sets\code_repair\stage_b_12 --events-per-trace 5 --provider ollama --model $model --seed 0 --output traces\stage_a_hard\intervention_code

Write-Host "=== 4. analyses (no model calls)"
python scripts\environment_calibration.py "traces\stage_a_hard\planning\*.json" --output-dir out\stage_a_hard\planning_calibration
python scripts\environment_selection_response.py "traces\stage_a_hard\planning\*.json" --output-dir out\stage_a_hard\planning_selection --permutations 1000
python scripts\environment_calibration.py "traces\stage_a_hard\code_repair\*.json" --output-dir out\stage_a_hard\code_calibration
python scripts\environment_selection_response.py "traces\stage_a_hard\code_repair\*.json" --output-dir out\stage_a_hard\code_selection --permutations 1000

Write-Host "=== hard pilot done"
Stop-Transcript
