# Difficulty screening, fourth round: confirm the never-solved tasks with more
# attempts and screen the rest of HumanEvalFix. Start it and leave it (about
# 22 hours; the code part is done after about 12):
#
#     powershell -ExecutionPolicy Bypass -File experiments\pilot_stage_a\run_screen_d.ps1
#
# Why: the hard pilot showed that 5-6 direct attempts cannot tell a task the
# model never solves from one it solves 10-15 % of the time, and the latter
# is solved outright by a 15-candidate first generation (10 of 12 pilot runs
# ended at generation 0 or 1). This round adds 10 attempts to every task
# that was never solved in round C and screens the 75 HumanEvalFix_d3_anon
# tasks that round C did not reach (5 attempts each), so the study sets can
# be chosen among tasks with 0 solves in 15-16 attempts, spread from
# near-solvable to deep. Results go to out\screen_d\; merge with round C by
#
#     python scripts\merge_screens.py out\screen_c\...\memorization_check.json out\screen_d\...\memorization_check.json --output ...

$ErrorActionPreference = "Stop"
$model = "qwen3:14b"
New-Item -ItemType Directory -Force out\screen_d | Out-Null
Start-Transcript -Path out\screen_d\transcript.txt -Append

Write-Host "=== 1. HumanEvalFix_d3_anon, the 75 tasks after the first 40, x 5 direct repairs (about 7.5 h)"
$restIds = (Get-ChildItem task_sets\code_repair\humanevalfix_d3_anon -Directory | Select-Object -Skip 40 | ForEach-Object { $_.Name })
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\humanevalfix_d3_anon --task-ids $restIds --provider ollama --model $model --samples 5 --output out\screen_d\memorization_humanevalfix_d3_anon_rest

Write-Host "=== 2. never-solved code tasks of rounds C and D, x 10 more direct repairs (about 4-9 h)"
$hefIds = (python scripts\pick_hard_tasks.py out\screen_c\memorization_humanevalfix_d3_anon\memorization_check.json --max-rate 0 --count 100).Split(" ")
$hefIds += (python scripts\pick_hard_tasks.py out\screen_d\memorization_humanevalfix_d3_anon_rest\memorization_check.json --max-rate 0 --count 100).Split(" ")
$qbIds = (python scripts\pick_hard_tasks.py out\screen_c\memorization_quixbugs_d3_anon\memorization_check.json --max-rate 0 --count 100).Split(" ")
Write-Host "    HumanEvalFix never solved so far: $($hefIds.Count); QuixBugs: $($qbIds.Count)"
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\humanevalfix_d3_anon --task-ids $hefIds --provider ollama --model $model --samples 10 --output out\screen_d\memorization_humanevalfix_d3_anon_confirm
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\quixbugs_d3_anon --task-ids $qbIds --provider ollama --model $model --samples 10 --output out\screen_d\memorization_quixbugs_d3_anon_confirm

Write-Host "=== 3. never-solved deep planning instances of round C, x 10 more direct attempts (about 10 h)"
$pIds = (python scripts\pick_hard_tasks.py out\screen_c\planning_deep_6to7\direct_solve_check.json --max-rate 0 --count 100).Split(" ")
Write-Host "    planning instances never solved so far: $($pIds.Count)"
python scripts\planning_direct_solve_check.py --instances task_sets\planning\deep_6to7.json --task-ids $pIds --provider ollama --model $model --samples 10 --output out\screen_d\planning_deep_6to7_confirm

Write-Host "=== screening done"
Stop-Transcript
