# Stage B on the cluster: three models, two environments

Everything below runs from the repository root on the cluster. Same software
as the submitted Contexto runs (Slurm, one A30 per job, node-local Ollama,
`module load python/3.11.5`).

## Task sets (fixed 2026-09-21 from screening round C, qwen3:14b)

* `task_sets/planning/stage_b_12.json`: 12 Blocksworld instances of 7 blocks,
  optimal plans 18-24 actions, never solved in 6 direct attempts; three per
  optimal length with the highest partial progress
  (`scripts/pick_hard_tasks.py out/screen_c/planning_deep_6to7/direct_solve_check.json --max-rate 0 --group-key optimal_plan_length --per-group 3`).
* `task_sets/code_repair/stage_b_12`: 12 anonymised code-repair tasks with 3
  extra defects, never solved in 5 direct repairs: the 4 such QuixBugs
  programs and the 8 such HumanEvalFix tasks with the highest hidden-test pass
  fraction (`pick_hard_tasks.py ... --max-rate 0 --count 4` / `--count 8`).
* Control subset (6 per environment): every other task of the study list.

The chosen ids and the rule are stored inside each set (`selection_rule`).

## One-time setup on the cluster

```bash
cd $HOME && git clone <repo url> llm-faithfulness-evolution      # or git pull in the existing checkout
cd llm-faithfulness-evolution
module load python/3.11.5
python -m venv $HOME/venvs/lfe && source $HOME/venvs/lfe/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m pytest -q                                              # 308 passed, 4 skipped
export OLLAMA_MODELS=$HOME/ollama_models                         # on a node with network access:
ollama pull qwen3:14b && ollama pull gemma4:12b && ollama pull ministral-3:14b
ollama list
```

Then, in every shell you submit from:

```bash
export REPO_DIR=$HOME/llm-faithfulness-evolution VENV=$HOME/venvs/lfe
```

## Launch

```bash
bash experiments/stage_b/submit_stage_b.sh main       # 6 array jobs x 12 tasks (main condition), each followed by its intervention job
bash experiments/stage_b/submit_stage_b.sh controls   # 24 array jobs x 6 tasks + 6 intervention jobs (prospective)
squeue -u $USER
```

Main condition per task: 2 runs, 10 generations, (mu + lambda) selection,
inherited rationale, self-report on; about 115 calls per run when nothing is
solved (planning about 2 min per call with qwen3:14b, code about 75 s), so an
array task takes up to 8 h (planning) or 5 h (code). Jobs that hit the 16 h
limit are resubmitted with the same command; finished runs are skipped.

Output layout: `traces/stage_b/<model>/<environment>_<condition>/` holds the
trace files (one per run), `summary_<task>.json` per array task and the
Ollama metadata; `<environment>_intervention/run<k>/` holds the intervention
outputs for run index k.

## After the jobs

```bash
for m in qwen3_14b gemma4_12b ministral3_14b; do for e in planning code_repair; do
  python scripts/environment_calibration.py "traces/stage_b/$m/${e}_main/*.json" --output-dir out/stage_b/$m/${e}_calibration
  python scripts/environment_selection_response.py "traces/stage_b/$m/${e}_main/*.json" --output-dir out/stage_b/$m/${e}_selection --permutations 1000
done; done
```

Copy `traces/stage_b` and `out/stage_b` back to the Windows machine for the
paper analyses (both directories are git-ignored).
