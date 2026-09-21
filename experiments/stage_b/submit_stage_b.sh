#!/bin/bash
# Submit the Stage B jobs (three models x two environments) in priority order.
#
#     export REPO_DIR=$HOME/llm-faithfulness-evolution VENV=$HOME/venvs/lfe
#     bash experiments/stage_b/submit_stage_b.sh main        # main condition + its interventions (queued after it)
#     bash experiments/stage_b/submit_stage_b.sh controls    # random / report-rewarded selection, no report, prospective
#
# Job ids are appended to experiments/stage_b/submitted_jobs.txt. Every job
# skips runs whose traces exist, so resubmitting the same phase after a time
# limit or a node failure only redoes the unfinished runs.

set -euo pipefail
PHASE="${1:?main or controls}"
cd "${REPO_DIR:?set REPO_DIR}"
mkdir -p logs traces/stage_b
LOG=experiments/stage_b/submitted_jobs.txt

MODELS=("qwen3:14b" "gemma4:12b" "ministral-3:14b")
slug() { echo "$1" | tr ':' '_' | tr -d '-'; }          # qwen3:14b -> qwen3_14b, ministral-3:14b -> ministral3_14b
ctx()  { if [ "$1" = "ministral-3:14b" ]; then echo 8192; else echo ""; fi; }

set_for() { if [ "$1" = "planning" ]; then echo task_sets/planning/stage_b_12.json; else echo task_sets/code_repair/stage_b_12; fi; }

# every other task of the study lists: the control subset (6 per environment)
PLANNING_CONTROL_IDS="bw07_s6088 bw07_s7850 bw07_s5132 bw07_s0027 bw07_s5845 bw07_s2129"
CODE_CONTROL_IDS="quixbugs_mergesort_d3_anon quixbugs_hanoi_d3_anon humanevalfix_074_d3_anon humanevalfix_072_d3_anon humanevalfix_069_d3_anon humanevalfix_000_d3_anon"

submit_search() {   # env model output label selection channel self_report [task_ids]
    local env=$1 model=$2 output=$3 label=$4 selection=$5 channel=$6 report=$7 ids="${8:-}"
    local array="0-11%12"; [ -n "$ids" ] && array="0-5%6"
    local jid
    jid=$(sbatch --parsable --array="$array" \
        --export=ALL,ENVIRONMENT="$env",MODEL="$model",TASK_SET="$(set_for "$env")",OUTPUT="$output",LABEL="$label",SELECTION="$selection",RATIONALE_CHANNEL="$channel",SELF_REPORT="$report",TASK_IDS="$ids",CONTEXT_LENGTH="$(ctx "$model")" \
        infra/slurm/run_search_batch.sh)
    echo "$(date +%F_%T) $jid search $env $model $label" | tee -a "$LOG"
    echo "$jid"
}

submit_intervention() {   # env model traces output after_jobid
    local env=$1 model=$2 traces=$3 output=$4 after=$5
    local taskset=""; [ "$env" = "code_repair" ] && taskset="$(set_for "$env")"
    local jid
    jid=$(sbatch --parsable --dependency=afterany:"$after" \
        --export=ALL,ENVIRONMENT="$env",MODEL="$model",TRACES="$traces",TASK_SET="$taskset",OUTPUT="$output",EVENTS=10,CONTEXT_LENGTH="$(ctx "$model")" \
        infra/slurm/run_intervention_batch.sh)
    echo "$(date +%F_%T) $jid intervention $env $model (after $after)" | tee -a "$LOG"
}

for model in "${MODELS[@]}"; do
    s=$(slug "$model")
    for env in planning code_repair; do
        base="traces/stage_b/$s/$env"
        case "$PHASE" in
            main)
                jid=$(submit_search "$env" "$model" "${base}_main" "stageB_main" mu_plus_lambda inherited 1 | tail -1)
                submit_intervention "$env" "$model" "${base}_main" "${base}_intervention" "$jid"
                ;;
            controls)
                ids="$PLANNING_CONTROL_IDS"; [ "$env" = "code_repair" ] && ids="$CODE_CONTROL_IDS"
                submit_search "$env" "$model" "${base}_random_selection" "stageB_random" random inherited 1 "$ids" >/dev/null
                submit_search "$env" "$model" "${base}_report_rewarded" "stageB_report_rewarded" report_rewarded inherited 1 "$ids" >/dev/null
                submit_search "$env" "$model" "${base}_noreport" "stageB_noreport" mu_plus_lambda inherited 0 "$ids" >/dev/null
                jid=$(submit_search "$env" "$model" "${base}_prospective" "stageB_prospective" mu_plus_lambda prospective 1 "$ids" | tail -1)
                submit_intervention "$env" "$model" "${base}_prospective" "${base}_intervention_prospective" "$jid"
                ;;
            *) echo "unknown phase $PHASE"; exit 1 ;;
        esac
    done
done
echo "submitted; watch with: squeue -u \$USER"
