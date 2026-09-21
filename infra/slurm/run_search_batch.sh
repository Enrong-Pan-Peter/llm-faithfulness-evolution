#!/bin/bash
#SBATCH --job-name=search-batch
#SBATCH --gres=gpu:a30:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=16:00:00
#SBATCH --array=0-11%12
#SBATCH --output=logs/search_%A_%a.out
#SBATCH --error=logs/search_%A_%a.err

# One array task = one task of a study set (all its runs, one after another)
# on a node-local Ollama, the same pattern as run_rationale_intervention.sh.
# Everything is chosen through environment variables passed with sbatch
# --export (see experiments/stage_b/README.md for the launch lines):
#
#   ENVIRONMENT       planning | code_repair
#   MODEL             Ollama tag (qwen3:14b, gemma4:12b, ministral-3:14b)
#   TASK_SET          task_sets/planning/stage_b_12.json | task_sets/code_repair/stage_b_12
#   OUTPUT            trace directory (created); one summary_<task>.json per array task
#   RUNS              runs per task (default 2), SEED first seed (default 0)
#   GENERATIONS       default 10
#   SELECTION         mu_plus_lambda (default) | random | report_rewarded
#   RATIONALE_CHANNEL inherited (default) | prospective | corrective_hint | none
#   SELF_REPORT       1 (default) | 0
#   LABEL             free text written into every RUN_CONFIG
#   TASK_IDS          optional: space-separated ids to run instead of the whole set
#                     (the array index then picks from this list)
#   CONTEXT_LENGTH    optional: OLLAMA_CONTEXT_LENGTH for the server (8192 for ministral-3:14b)
#
# The array size must match the number of tasks: 12 for the stage_b_12 sets
# (pass --array=0-5 for six tasks, and so on). Finished runs are skipped
# (--skip-existing), so a job that hit the time limit is simply resubmitted.

set -euo pipefail

REPO_DIR="${REPO_DIR:?set REPO_DIR to the llm-faithfulness-evolution checkout}"
VENV="${VENV:?set VENV to the virtualenv directory}"
cd "$REPO_DIR"

module load python/3.11.5
source "$VENV/bin/activate"

export PATH="$HOME/.local/bin:$PATH"
export OLLAMA_MODELS="${OLLAMA_MODELS:-$HOME/ollama_models}"

ENVIRONMENT="${ENVIRONMENT:?planning or code_repair}"
MODEL="${MODEL:?Ollama model tag}"
TASK_SET="${TASK_SET:?instance set file or task set directory}"
OUTPUT="${OUTPUT:?trace directory}"
RUNS="${RUNS:-2}"
SEED="${SEED:-0}"
GENERATIONS="${GENERATIONS:-10}"
SELECTION="${SELECTION:-mu_plus_lambda}"
RATIONALE_CHANNEL="${RATIONALE_CHANNEL:-inherited}"
SELF_REPORT="${SELF_REPORT:-1}"
LABEL="${LABEL:-stage_b}"

# the task of this array index
if [ -n "${TASK_IDS:-}" ]; then
    read -r -a IDS <<< "$TASK_IDS"
else
    if [ "$ENVIRONMENT" = "planning" ]; then
        mapfile -t IDS < <(python -c "import json,sys; d=json.load(open(sys.argv[1])); print('\n'.join(r['instance_id'] for r in (d['instances'] if isinstance(d,dict) else d)))" "$TASK_SET")
    else
        mapfile -t IDS < <(python -c "import sys,pathlib; print('\n'.join(sorted(p.name for p in pathlib.Path(sys.argv[1]).iterdir() if (p/'task.json').is_file())))" "$TASK_SET")
    fi
fi
if [ "$SLURM_ARRAY_TASK_ID" -ge "${#IDS[@]}" ]; then
    echo "array index $SLURM_ARRAY_TASK_ID beyond the ${#IDS[@]} tasks of $TASK_SET; nothing to do"
    exit 0
fi
TASK="${IDS[$SLURM_ARRAY_TASK_ID]}"

mkdir -p logs "$OUTPUT"

PORT=$((20000 + (SLURM_JOB_ID + SLURM_ARRAY_TASK_ID) % 20000))
export OLLAMA_HOST="127.0.0.1:${PORT}"
export OLLAMA_BASE_URL="http://127.0.0.1:${PORT}/v1"
export OLLAMA_KEEP_ALIVE=12h
export OLLAMA_REQUEST_TIMEOUT_SECONDS=900
if [ -n "${CONTEXT_LENGTH:-}" ]; then export OLLAMA_CONTEXT_LENGTH="$CONTEXT_LENGTH"; fi

OLLAMA_LOG="logs/ollama_search_${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.log"
METADATA="$OUTPUT/ollama_metadata_${TASK}_job${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.txt"

echo "===== SEARCH BATCH JOB ====="
echo "Job ID: $SLURM_JOB_ID  array task: $SLURM_ARRAY_TASK_ID  host: $(hostname)  date: $(date)"
echo "environment=$ENVIRONMENT model=$MODEL task=$TASK set=$TASK_SET"
echo "runs=$RUNS seed=$SEED generations=$GENERATIONS selection=$SELECTION channel=$RATIONALE_CHANNEL self_report=$SELF_REPORT"
echo "OLLAMA_BASE_URL=$OLLAMA_BASE_URL OLLAMA_CONTEXT_LENGTH=${OLLAMA_CONTEXT_LENGTH:-default}"
python --version
nvidia-smi || true

ollama serve > "$OLLAMA_LOG" 2>&1 &
OLLAMA_PID=$!
cleanup() { kill "$OLLAMA_PID" 2>/dev/null || true; }
trap cleanup EXIT

READY=0
for attempt in $(seq 1 24); do
    if ollama list >/dev/null 2>&1; then READY=1; break; fi
    sleep 5
done
if [ "$READY" -ne 1 ]; then echo "ERROR: Ollama failed to start."; exit 1; fi
if ! ollama list | grep -q "^${MODEL}"; then
    echo "ERROR: model $MODEL is not in $OLLAMA_MODELS (run 'ollama pull $MODEL' on a node with network access first)."
    exit 1
fi

{
    echo "Job ID: $SLURM_JOB_ID  array task: $SLURM_ARRAY_TASK_ID  task: $TASK  host: $(hostname)  date: $(date)"
    echo; echo "===== nvidia-smi ====="; nvidia-smi
    echo; echo "===== ollama --version ====="; ollama --version
    echo; echo "===== ollama list ====="; ollama list
    echo; echo "OLLAMA_CONTEXT_LENGTH=${OLLAMA_CONTEXT_LENGTH:-default}"
} > "$METADATA"

if [ "$ENVIRONMENT" = "planning" ]; then
    SET_ARGS=(--instances "$TASK_SET")
else
    SET_ARGS=(--tasks "$TASK_SET")
fi

echo "===== START ====="
python -m search.run "$ENVIRONMENT" "${SET_ARGS[@]}" --task-ids "$TASK" \
    --provider ollama --model "$MODEL" \
    --runs-per-task "$RUNS" --seed "$SEED" --max-generations "$GENERATIONS" \
    --selection "$SELECTION" --rationale-channel "$RATIONALE_CHANNEL" --self-report "$SELF_REPORT" \
    --label "$LABEL" --output "$OUTPUT" --summary-name "summary_${TASK}.json" --skip-existing
STATUS=$?
echo "===== FINISHED task=$TASK status=$STATUS date=$(date) ====="
exit "$STATUS"
