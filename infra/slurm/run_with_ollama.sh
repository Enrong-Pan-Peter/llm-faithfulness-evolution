#!/bin/bash
#SBATCH --job-name=with-ollama
#SBATCH --gres=gpu:a30:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=06:00:00
#SBATCH --output=logs/with_ollama_%j.out
#SBATCH --error=logs/with_ollama_%j.err

# Run one command (a screening script, a one-off batch) next to a node-local
# Ollama, the same preamble as the batch jobs. The command is passed in CMD
# and sees OLLAMA_BASE_URL; MODEL must already be pulled into OLLAMA_MODELS.
#
#   sbatch --export=ALL,MODEL=gemma4:12b,CMD="python scripts/planning_direct_solve_check.py --instances task_sets/planning/deep_8.json --provider ollama --model gemma4:12b --samples 8 --output out/screen_cluster/gemma4_deep_8" infra/slurm/run_with_ollama.sh
#
#   CONTEXT_LENGTH optional OLLAMA_CONTEXT_LENGTH (8192 for ministral-3:14b)

set -euo pipefail

REPO_DIR="${REPO_DIR:?set REPO_DIR to the llm-faithfulness-evolution checkout}"
VENV="${VENV:?set VENV to the virtualenv directory}"
cd "$REPO_DIR"

module load python/3.11.5
source "$VENV/bin/activate"

export PATH="$HOME/.local/bin:$PATH"
export OLLAMA_MODELS="${OLLAMA_MODELS:-$HOME/ollama_models}"

MODEL="${MODEL:?Ollama model tag}"
CMD="${CMD:?command to run}"

mkdir -p logs

PORT=$((20000 + SLURM_JOB_ID % 20000))
export OLLAMA_HOST="127.0.0.1:${PORT}"
export OLLAMA_BASE_URL="http://127.0.0.1:${PORT}/v1"
export OLLAMA_KEEP_ALIVE=12h
export OLLAMA_REQUEST_TIMEOUT_SECONDS=900
if [ -n "${CONTEXT_LENGTH:-}" ]; then export OLLAMA_CONTEXT_LENGTH="$CONTEXT_LENGTH"; fi

echo "===== WITH-OLLAMA JOB ====="
echo "Job ID: $SLURM_JOB_ID  host: $(hostname)  date: $(date)"
echo "model=$MODEL OLLAMA_BASE_URL=$OLLAMA_BASE_URL OLLAMA_CONTEXT_LENGTH=${OLLAMA_CONTEXT_LENGTH:-default}"
echo "command: $CMD"
python --version
nvidia-smi || true

ollama serve > "logs/ollama_with_ollama_${SLURM_JOB_ID}.log" 2>&1 &
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
    echo "ERROR: model $MODEL is not in $OLLAMA_MODELS."
    exit 1
fi
ollama --version
ollama list

echo "===== START ====="
bash -c "$CMD"
STATUS=$?
echo "===== FINISHED status=$STATUS date=$(date) ====="
exit "$STATUS"
