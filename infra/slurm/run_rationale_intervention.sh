#!/bin/bash
#SBATCH --job-name=rationale-intervention
#SBATCH --gres=gpu:a30:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=1-00:00:00
#SBATCH --array=0-9%10
#SBATCH --output=logs/rationale_intervention_%A_%a.out
#SBATCH --error=logs/rationale_intervention_%A_%a.err

set -euo pipefail

# Cluster-specific paths were replaced by variables when this script was migrated
# from the Contexto repository (original: the author's HPC home directory).
CONTEXTO_REPO_DIR="${CONTEXTO_REPO_DIR:?set CONTEXTO_REPO_DIR to the repository checkout}"
CONTEXTO_VENV="${CONTEXTO_VENV:?set CONTEXTO_VENV to the virtualenv directory}"
cd "$CONTEXTO_REPO_DIR"

module load python/3.11.5
source "$CONTEXTO_VENV/bin/activate"

export PATH="$HOME/.local/bin:$PATH"
export OLLAMA_MODELS="$HOME/ollama_models"

export RANK_CACHE_DIR=data/rank_cache_A1
export RANK_CACHE_ENABLED=1

GAMES=(1303 1307 1319 1327 1335 1352 1364 1365 1372 1384)
GAME=${GAMES[$SLURM_ARRAY_TASK_ID]}

mkdir -p logs
mkdir -p "traces/rationale_intervention/${GAME}"

PORT=$((20000 + (SLURM_JOB_ID + SLURM_ARRAY_TASK_ID) % 20000))

export OLLAMA_HOST="127.0.0.1:${PORT}"
export OLLAMA_BASE_URL="http://127.0.0.1:${PORT}/v1"
export OLLAMA_KEEP_ALIVE=12h
export OLLAMA_REQUEST_TIMEOUT_SECONDS=900

OLLAMA_LOG="logs/ollama_rationale_intervention_game${GAME}_${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.log"
METADATA="traces/rationale_intervention/${GAME}/ollama_metadata_job${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}.txt"

echo "===== RATIONALE INTERVENTION JOB ====="
echo "Job ID: $SLURM_JOB_ID"
echo "Array task: $SLURM_ARRAY_TASK_ID"
echo "Game: $GAME"
echo "Host: $(hostname)"
echo "Date: $(date)"
echo "OLLAMA_BASE_URL=$OLLAMA_BASE_URL"
echo "RANK_CACHE_DIR=$RANK_CACHE_DIR"
echo "RANK_CACHE_ENABLED=$RANK_CACHE_ENABLED"

echo "Python: $(which python)"
python --version
python -c "import numpy; print('NumPy:', numpy.__version__)"

nvidia-smi || true

ollama serve > "$OLLAMA_LOG" 2>&1 &
OLLAMA_PID=$!

cleanup() {
    kill "$OLLAMA_PID" 2>/dev/null || true
}
trap cleanup EXIT

READY=0
for attempt in $(seq 1 24); do
    if ollama list >/dev/null 2>&1; then
        READY=1
        break
    fi
    sleep 5
done

if [ "$READY" -ne 1 ]; then
    echo "ERROR: Ollama failed to start."
    exit 1
fi

{
    echo "Job ID: $SLURM_JOB_ID"
    echo "Array task: $SLURM_ARRAY_TASK_ID"
    echo "Game: $GAME"
    echo "Host: $(hostname)"
    echo "Date: $(date)"
    echo
    echo "===== nvidia-smi ====="
    nvidia-smi
    echo
    echo "===== ollama --version ====="
    ollama --version
    echo
    echo "===== ollama list ====="
    ollama list
} > "$METADATA"

echo "===== START INTERVENTION RUN ====="

python scripts/rationale_intervention_run.py \
  "traces/rq1_A1/ea_llm_self_adaptive_api_${GAME}_run*_*.json" \
  --events-per-trace 40 \
  --seed 0 \
  --output "traces/rationale_intervention/${GAME}"

STATUS=$?

echo "===== FINISHED ====="
echo "Game: $GAME"
echo "Exit status: $STATUS"
echo "Date: $(date)"

exit "$STATUS"
