# Difficulty screening, third round. Start it and leave it (about 11 hours):
#
#     powershell -ExecutionPolicy Bypass -File experiments\pilot_stage_a\run_screen_c.ps1
#
# Why: the second round showed that extra injected defects do not stop the
# model on QuixBugs / HumanEvalFix: given the function name and its docstring
# it rewrites the memorised solution (19 of 25 QuixBugs_d3 and 35 of 40
# HumanEvalFix_d3 tasks solved in every direct attempt). This round measures
# one-shot repair rates on the anonymised variants (identifiers renamed to
# solve / v1 / v2 ..., docstrings removed, the tests are the only
# specification), on the same tasks as round two so the two are paired, and
# one-shot solve rates on a fresh set of 6-7 block planning instances whose
# optimal plans are 18-24 actions long (exact remaining-distance fitness
# available for all of them). Results go to out\screen_c\.
#
# Step 0 unpacks the prebuilt anonymised code task sets from
# data\benchmarks\code_task_sets_anon_2026-09-20.zip when that file is present.

$ErrorActionPreference = "Stop"
$model = "qwen3:14b"
New-Item -ItemType Directory -Force out\screen_c | Out-Null
Start-Transcript -Path out\screen_c\transcript.txt -Append

Write-Host "=== 0. unpack the prebuilt anonymised code task sets (seconds)"
$zip = "data\benchmarks\code_task_sets_anon_2026-09-20.zip"
$sets = "quixbugs_anon", "quixbugs_d3_anon", "quixbugs_d5_anon", "humanevalfix_anon", "humanevalfix_d3_anon"
if (Test-Path $zip) {
    foreach ($name in $sets) {
        if (Test-Path "task_sets\code_repair\$name") { Remove-Item -Recurse -Force "task_sets\code_repair\$name" }
    }
    Expand-Archive -Path $zip -DestinationPath task_sets\code_repair -Force
}
foreach ($name in $sets) {
    $n = (Get-ChildItem "task_sets\code_repair\$name" -Directory).Count
    Write-Host "    $name : $n tasks"
}

Write-Host "=== 1. QuixBugs anonymised, original defect only: 28 tasks x 5 direct repairs (about 2 h)"
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\quixbugs_anon --provider ollama --model $model --samples 5 --output out\screen_c\memorization_quixbugs_anon

Write-Host "=== 2. QuixBugs anonymised with 3 extra defects: 25 tasks x 5 (about 2 h)"
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\quixbugs_d3_anon --provider ollama --model $model --samples 5 --output out\screen_c\memorization_quixbugs_d3_anon

Write-Host "=== 3. HumanEvalFix anonymised with 3 extra defects, the same first 40 tasks as round two x 5 (about 3 h)"
$hefIds = (Get-ChildItem task_sets\code_repair\humanevalfix_d3_anon -Directory | Select-Object -First 40 | ForEach-Object { $_.Name })
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\humanevalfix_d3_anon --task-ids $hefIds --provider ollama --model $model --samples 5 --output out\screen_c\memorization_humanevalfix_d3_anon

Write-Host "=== 4. planning: 41 instances of 6-7 blocks, optimal plans 18-24 actions, x 6 direct attempts (about 3.5 h)"
python scripts\planning_direct_solve_check.py --instances task_sets\planning\deep_6to7.json --provider ollama --model $model --samples 6 --output out\screen_c\planning_deep_6to7

Write-Host "=== 5. QuixBugs anonymised with 5 extra defects: 20 tasks x 5 (about 1.5 h)"
python scripts\code_repair_memorization_check.py --tasks task_sets\code_repair\quixbugs_d5_anon --provider ollama --model $model --samples 5 --output out\screen_c\memorization_quixbugs_d5_anon

Write-Host "=== screening done"
Stop-Transcript
