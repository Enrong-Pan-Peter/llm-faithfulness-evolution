#!/bin/bash
#SBATCH --job-name=intervention-batch
#SBATCH --gres=gpu:a30:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=16:00:00
#SBATCH --array=0-1%2
#SBATCH --output=logs/intervention_%A_%a.out
#SBATCH --error=logs/intervention_%A_%a.err

# Rationale intervention on the stored prompts of a finished search batch.
# The "unrelated" condition borrows slot text from another task's call, so
# one job must see traces of several tasks: array task k takes the traces of
# run index k of every task (run0 files, run1 files, ...), which keeps a job
# at about 12 tasks x EVENTS x 5 conditions calls.
#
#   ENVIRONMENT   planning | code_repair
#   MODEL         the model the traces were run with (re-runs use the same model)
#   TRACES        directory of the search batch (its *_run<k>_*.json files are used)
#   TASK_SET      code_repair only: the task set directory the traces were run on
#   OUTPUT        directory; array task k writes to $OUTPUT/run<k>
#   EVENTS        stored calls sampled per trace (default 10)
#   CONTEXT_LENGTH optional OLLAMA_CONTEXT_LENGTH (8192 for ministral-3:14b)
#
# --array=0-1 for two runs per task; extend it when the batch had more runs.

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
TRACES="${TRACES:?directory of the search traces}"
OUTPUT="${OUTPUT:?output directory}"
EVENTS="${EVENTS:-10}"
RUN_INDEX="$SLURM_ARRAY_TASK_ID"

PATTERN="$TRACES/*_run${RUN_INDEX}_*.json"
if ! compgen -G "$PATTERN" > /dev/null; then
    echo "no traces match $PATTERN; nothing to do"
    exit 0
fi

mkdir -p logs "$OUTPUT/run${RUN_INDEX}"

PORT=$((20000 + (SLURM_JOB_ID + SLURM_ARRAY_TASK_ID) % 20000))
export OLLAMA_HOST="127.0.0.1:${PORT}"
export OLLAMA_BASE_URL="http://127.0.0.1:${PORT}/v1"
export OLLAMA_KEEP_ALIVE=12h
export OLLAMA_REQUEST_TIMEOUT_SECONDS=900
if [ -n "${CONTEXT_LENGTH:-}" ]; then export OLLAMA_CONTEXT_LENGTH="$CONTEXT_LENGTH"; fi

OLLAMA_LOG="logs/ollama_intervention_${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.log"
METADATA="$OUTPUT/run${RUN_INDEX}/ollama_metadata_job${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.txt"

echo "===== INTERVENTION BATCH JOB ====="
echo "Job ID: $SLURM_JOB_ID  array task: $SLURM_ARRAY_TASK_ID  host: $(hostname)  date: $(date)"
echo "environment=$ENVIRONMENT model=$MODEL traces=$PATTERN events=$EVENTS output=$OUTPUT/run${RUN_INDEX}"
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
    echo "Job ID: $SLURM_JOB_ID  array task: $SLURM_ARRAY_TASK_ID  host: $(hostname)  date: $(date)"
    echo; echo "===== nvidia-smi ====="; nvidia-smi
    echo; echo "===== ollama --version ====="; ollama --version
    echo; echo "===== ollama list ====="; ollama list
    echo; echo "OLLAMA_CONTEXT_LENGTH=${OLLAMA_CONTEXT_LENGTH:-default}"
} > "$METADATA"

TASK_ARGS=()
if [ "$ENVIRONMENT" = "code_repair" ]; then
    TASK_ARGS=(--tasks "${TASK_SET:?code_repair needs TASK_SET}")
fi

echo "===== START ====="
python scripts/environment_rationale_intervention.py "$PATTERN" ${TASK_ARGS[@]+"${TASK_ARGS[@]}"} \
    --events-per-trace "$EVENTS" --provider ollama --model "$MODEL" --seed "$RUN_INDEX" \
    --output "$OUTPUT/run${RUN_INDEX}"
STATUS=$?
echo "===== FINISHED status=$STATUS date=$(date) ====="
exit "$STATUS"
