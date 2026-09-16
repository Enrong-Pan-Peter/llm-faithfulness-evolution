# Stage A pilot on the local RTX 3090, in one go. Start it from the repository
# root with the virtual environment active and Ollama serving qwen3:14b:
#
#     powershell -ExecutionPolicy Bypass -File experiments\pilot_stage_a\run_pilot_a.ps1
#
# Everything runs one after another on the single GPU (roughly 25-35 hours at
# 40 s per model call); each step writes its own files, so it can be stopped
# with Ctrl-C at any point and restarted from a later step by commenting out
# the finished ones. Traces go to traces\pilot_a\, analyses to out\pilot_a\.

$ErrorActionPreference = "Stop"
$env:RATIONALE_CHANNEL = "inherited"
$model = "qwen3:14b"
New-Item -ItemType Directory -Force out\pilot_a | Out-Null
Start-Transcript -Path out\pilot_a\transcript.txt -Append

# The five hard planning instances of the one-shot difficulty check (0 of 3
# direct solves, highest partial progress): 5-7 blocks, optimal plans 10-14.
$planningIds = "bw05_s1553", "bw05_s1390", "bw06_s2594", "bw07_s0588", "bw06_s8225"
$instanceSets = "task_sets\planning\pilot_3to5.json", "task_sets\planning\pilot_hard_5to8.json"

Write-Host "=== 1. planning search: 5 instances x 2 runs x 5 generations (about 7 h)"
python -m search.run planning --instances $instanceSets --task-ids $planningIds --provider ollama --model $model --runs-per-task 2 --max-generations 5 --seed 0 --label pilotA_planning --output traces\pilot_a\planning
python scripts\environment_calibration.py "traces\pilot_a\planning\*.json" --output-dir out\pilot_a\planning_calibration
python scripts\environment_selection_response.py "traces\pilot_a\planning\*.json" --output-dir out\pilot_a\planning_selection --permutations 1000

Write-Host "=== 2. QuixBugs memorisation check: 28 tasks x 5 direct repairs (about 1.5 h)"
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\quixbugs --provider ollama --model $model --samples 5 --output out\pilot_a\memorization_quixbugs_repair

Write-Host "=== 3. code-repair search on the five least-memorised QuixBugs tasks (about 7 h)"
$codeIds = (python scripts\pick_hard_tasks.py out\pilot_a\memorization_quixbugs_repair\memorization_check.json --count 5).Split(" ")
Write-Host "code tasks: $codeIds"
python -m search.run code_repair --tasks task_sets\code_repair\quixbugs --task-ids $codeIds --provider ollama --model $model --runs-per-task 2 --max-generations 5 --seed 0 --label pilotA_code --output traces\pilot_a\code_repair
python scripts\environment_calibration.py "traces\pilot_a\code_repair\*.json" --output-dir out\pilot_a\code_calibration
python scripts\environment_selection_response.py "traces\pilot_a\code_repair\*.json" --output-dir out\pilot_a\code_selection --permutations 1000

Write-Host "=== 4. rationale intervention re-runs, 4 stored calls per trace, five conditions (about 4 h)"
python scripts\environment_rationale_intervention.py "traces\pilot_a\planning\*.json" --events-per-trace 4 --provider ollama --model $model --seed 0 --output traces\pilot_a\intervention_planning
python scripts\environment_rationale_intervention.py "traces\pilot_a\code_repair\*.json" --tasks task_sets\code_repair\quixbugs --events-per-trace 4 --provider ollama --model $model --seed 0 --output traces\pilot_a\intervention_code

Write-Host "=== 5. prospective channel on two planning instances (about 4 h)"
$env:RATIONALE_CHANNEL = "prospective"
python -m search.run planning --instances $instanceSets --task-ids bw05_s1553 bw06_s2594 --provider ollama --model $model --runs-per-task 2 --max-generations 5 --seed 10 --label pilotA_planning_prospective --output traces\pilot_a\planning_prospective
python scripts\environment_rationale_intervention.py "traces\pilot_a\planning_prospective\*.json" --events-per-trace 4 --provider ollama --model $model --seed 0 --output traces\pilot_a\intervention_planning_prospective
$env:RATIONALE_CHANNEL = "inherited"

Write-Host "=== 6. controls on one instance: random selection, report-rewarded selection, no reports (about 4 h)"
python -m search.run planning --instances $instanceSets --task-ids bw06_s2594 --provider ollama --model $model --runs-per-task 2 --max-generations 5 --seed 20 --selection random --label pilotA_random --output traces\pilot_a\planning_random_selection
python -m search.run planning --instances $instanceSets --task-ids bw06_s2594 --provider ollama --model $model --runs-per-task 2 --max-generations 5 --seed 30 --selection report_rewarded --label pilotA_report_rewarded --output traces\pilot_a\planning_report_rewarded
python -m search.run planning --instances $instanceSets --task-ids bw06_s2594 --provider ollama --model $model --runs-per-task 2 --max-generations 5 --seed 40 --self-report 0 --label pilotA_noreport --output traces\pilot_a\planning_noreport

Write-Host "=== 7. HumanEvalFix memorisation check, 3 direct repairs per task (about 5 h)"
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\humanevalfix --provider ollama --model $model --samples 3 --output out\pilot_a\memorization_humanevalfix_repair

Write-Host "=== Stage A done"
Stop-Transcript
