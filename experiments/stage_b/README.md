# Stage B on the cluster (Frontenac): three models, two environments

Everything below runs from the repository root on the cluster, in the same
software setup as the submitted Contexto runs: Slurm, one A30 per job,
node-local Ollama 0.32.1 (`~/.local/bin/ollama`, models in `~/ollama_models`),
`module load python/3.11.5`. Home is `/global/home/hpc6237`.

## Task sets (fixed 2026-09-25 from screening rounds C and D, qwen3:14b)

* `task_sets/planning/stage_b_12.json`: 12 Blocksworld instances of 7 blocks,
  optimal plans 18-24 actions, never solved in 16 direct attempts, evenly
  spaced along the partial-progress ranking of the 21 such instances
  (`scripts/pick_hard_tasks.py task_sets/screens/planning_deep_6to7_qwen3_14b.json --max-rate 0 --spread 12`).
* `task_sets/code_repair/stage_b_12`: 12 anonymised code-repair tasks with 3
  extra defects, never solved in 15 direct repairs: the 4 such QuixBugs
  programs and 8 of the 32 such HumanEvalFix tasks, evenly spaced along the
  hidden-test pass-fraction ranking (`--max-rate 0 --count 4` / `--spread 8`).
* Control subset (6 per environment): every other task of each list
  (positions 0, 2, 4, ...), computed by `submit_stage_b.sh` from the sets.

The chosen ids, the rule and each task's screening row are stored inside the
sets (`selection_rule`, `screen`); the merged screens are in `task_sets/screens/`.

## One-time setup on the cluster

```bash
cd $HOME
git clone <repo url> llm-faithfulness-evolution      # the same way Contexto was cloned here
cd $HOME/llm-faithfulness-evolution
module load python/3.11.5
python -m venv $HOME/venvs/lfe
source $HOME/venvs/lfe/bin/activate
pip install -r requirements.txt                      # requests, numpy, scipy, pytest only; pyarrow is not needed here
cp .env.example .env
python -m pytest -q                                  # 312 passed, 5 skipped (the parquet test skips without pyarrow)
ls $HOME/ollama_models/manifests/registry.ollama.ai/library/    # must list qwen3, gemma4, ministral-3
mkdir -p logs
```

If a model is missing: `export OLLAMA_MODELS=$HOME/ollama_models; ollama serve &` on the
login node, then `ollama pull <tag>` (as for the Contexto runs).

In every shell you submit from:

```bash
module load python/3.11.5 && source $HOME/venvs/lfe/bin/activate
export REPO_DIR=$HOME/llm-faithfulness-evolution VENV=$HOME/venvs/lfe
cd $REPO_DIR
```

## Smoke test first (one task, one run, two generations, about 40 min)

```bash
sbatch --array=0-0 --time=02:00:00 --export=ALL,SEARCH_ENV=planning,MODEL=qwen3:14b,TASK_SET=task_sets/planning/stage_b_12.json,OUTPUT=traces/smoke_cluster/planning,LABEL=smoke,RUNS=1,GENERATIONS=2 infra/slurm/run_search_batch.sh
sbatch --array=0-0 --time=02:00:00 --export=ALL,SEARCH_ENV=code_repair,MODEL=qwen3:14b,TASK_SET=task_sets/code_repair/stage_b_12,OUTPUT=traces/smoke_cluster/code_repair,LABEL=smoke,RUNS=1,GENERATIONS=2 infra/slurm/run_search_batch.sh
squeue -u $USER
tail -n 30 logs/search_<jobid>_0.out            # "===== FINISHED task=... status=0" when done
ls traces/smoke_cluster/planning traces/smoke_cluster/code_repair
```

## Launch

```bash
bash experiments/stage_b/submit_stage_b.sh main       # 6 array jobs x 12 tasks (main condition), each followed by its intervention job
bash experiments/stage_b/submit_stage_b.sh controls   # 24 array jobs x 6 tasks + 6 intervention jobs (prospective)
squeue -u $USER
```

Partitions: Slurm routes a job by its time limit (`--time=02:00:00` went to
`gpubase_6hrs`; the 16 h search jobs and the 1-day Contexto jobs go to the
24 h GPU partition), so no `--partition` flag is passed.

Main condition per task: 2 runs, 10 generations, (mu + lambda) selection,
inherited rationale, self-report on; about 115 calls per run when nothing is
solved (planning 80-120 s per call with qwen3:14b, code 30-80 s), so an
array task takes up to 8 h (planning) or 5 h (code). Jobs that hit the 16 h
limit are resubmitted with the same command; finished runs are skipped.

Output layout: `traces/stage_b/<model>/<environment>_<condition>/` holds the
trace files (one per run), `summary_<task>.json` per array task and the
Ollama metadata; `<environment>_intervention/run<k>/` holds the intervention
outputs for run index k.

## After the jobs

Completeness check first (every expected trace, per-task summary and
intervention output; per-run outcomes; parsed-report and failed-call counts;
exit code 1 while anything is missing):

```bash
python scripts/check_stage_b.py                     # traces/stage_b, 2 runs per task
```

Then the two analyses per model and environment, and one archive for the
Windows machine:

```bash
for m in qwen3_14b gemma4_12b ministral3_14b; do for e in planning code_repair; do
  python scripts/environment_calibration.py "traces/stage_b/$m/${e}_main/*.json" --output-dir out/stage_b/$m/${e}_calibration
  python scripts/environment_selection_response.py "traces/stage_b/$m/${e}_main/*.json" --output-dir out/stage_b/$m/${e}_selection --permutations 1000
done; done
```

```bash
tar czf $HOME/stage_b_$(date +%F).tgz traces/stage_b out/stage_b logs experiments/stage_b/submitted_jobs.txt
ls -lh $HOME/stage_b_*.tgz
```

On Windows (PowerShell, from the repository root; `_incoming\` is git-ignored,
and the archive's paths are relative to the repository root, so the traces
land in `traces\stage_b\` and the analyses in `out\stage_b\`):

```
New-Item -ItemType Directory -Force _incoming | Out-Null
scp hpc6237@<login host>:stage_b_<date>.tgz _incoming\
tar -xzf _incoming\stage_b_<date>.tgz
python scripts\check_stage_b.py
```
