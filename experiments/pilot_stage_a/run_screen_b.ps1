# Difficulty screening, second round. Start it and leave it (about 9 hours):
#
#     powershell -ExecutionPolicy Bypass -File experiments\pilot_stage_a\run_screen_b.ps1
#
# Why: in the first pilot the model solved almost every task in generation 0
# (15 direct attempts), so the search never ran. This round measures one-shot
# solve rates on harder material: deep Blocksworld instances (5-10 blocks,
# plans of 14+ actions) and benchmark programs with extra injected defects.
# Results go to out\screen_b\.

$ErrorActionPreference = "Stop"
$model = "qwen3:14b"
New-Item -ItemType Directory -Force out\screen_b | Out-Null
Start-Transcript -Path out\screen_b\transcript.txt -Append

Write-Host "=== 0. rebuild the code task sets (no GPU, a few minutes)"
python scripts\build_code_repair_tasks.py humanevalfix --source data\benchmarks\humanevalpack_python.parquet --evalplus data\benchmarks\HumanEvalPlus.jsonl.gz --output task_sets\code_repair\humanevalfix
python scripts\build_code_repair_tasks.py quixbugs --source data\benchmarks\QuixBugs --output task_sets\code_repair\quixbugs_d3 --extra-defects 3
python scripts\build_code_repair_tasks.py quixbugs --source data\benchmarks\QuixBugs --output task_sets\code_repair\quixbugs_d5 --extra-defects 5
python scripts\build_code_repair_tasks.py humanevalfix --source data\benchmarks\humanevalpack_python.parquet --evalplus data\benchmarks\HumanEvalPlus.jsonl.gz --output task_sets\code_repair\humanevalfix_d3 --extra-defects 3

Write-Host "=== 1. planning: 39 deep instances x 8 direct attempts (about 4 h)"
python scripts\planning_direct_solve_check.py --instances task_sets\planning\screen_5to10.json --provider ollama --model $model --samples 8 --output out\screen_b\planning_screen_5to10

Write-Host "=== 2. QuixBugs with 3 and 5 extra defects x 5 direct repairs (about 2.5 h)"
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\quixbugs_d3 --provider ollama --model $model --samples 5 --output out\screen_b\memorization_quixbugs_d3
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\quixbugs_d5 --provider ollama --model $model --samples 5 --output out\screen_b\memorization_quixbugs_d5

Write-Host "=== 3. HumanEvalFix with 3 extra defects, first 40 tasks x 5 direct repairs (about 2.5 h)"
$hefIds = (Get-ChildItem task_sets\code_repair\humanevalfix_d3 -Directory | Select-Object -First 40 | ForEach-Object { $_.Name })
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\humanevalfix_d3 --task-ids $hefIds --provider ollama --model $model --samples 5 --output out\screen_b\memorization_humanevalfix_d3

Write-Host "=== screening done"
Stop-Transcript
