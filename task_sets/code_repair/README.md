# Code-repair task sets

Task directories in the format of `environments/code_repair/tasks.py`, built
by `scripts/build_code_repair_tasks.py` from public benchmarks. Each set has
an `index.json` (every task with its development/hidden split notes and the
split rule) and a `rejected.json` (tasks the loader could not use, with the
reason). Nothing here is shown to a model except `task.json`'s `prompt`, the
seeded program and the development tests.

| Set | Source | Tasks | Notes |
|---|---|---|---|
| `quixbugs/` | QuixBugs, Python programs with JSON test cases (MIT) | 28 of 31 | Committed. `is_valid_parenthesization` and `kheapsort` have too few cases for a hidden set once the docstring examples are moved to development; `wrap`'s cases are all too long to show. Two cases the corrected programs cannot finish under the runner limits were dropped (`levenshtein`, `knapsack`), see the index. Hidden sets are small (1 to 7 tests, median 3). |
| `humanevalfix/` | HumanEvalPack (`bigcode/humanevalpack`, python split, MIT) + EvalPlus HumanEval+ extra inputs | build it locally | Not committed here because the Hugging Face hub is not reachable from the machine that built this repository; the build is deterministic given the two files and `--seed`. |

## Building HumanEvalFix (PowerShell)

```
New-Item -ItemType Directory -Force data\benchmarks | Out-Null
Invoke-WebRequest -Uri "https://huggingface.co/datasets/bigcode/humanevalpack/resolve/main/data/python/data/humanevalpack.jsonl" -OutFile data\benchmarks\humanevalpack_python.jsonl
Invoke-WebRequest -Uri "https://github.com/evalplus/humanevalplus_release/releases/download/v0.1.10/HumanEvalPlus.jsonl.gz" -OutFile data\benchmarks\HumanEvalPlus.jsonl.gz
python scripts\build_code_repair_tasks.py humanevalfix --source data\benchmarks\humanevalpack_python.jsonl --evalplus data\benchmarks\HumanEvalPlus.jsonl.gz --output task_sets\code_repair\humanevalfix
```

The build runs every reference and seeded program in the sandboxed runner
(about 1,000 short child processes, a few minutes). Expect a handful of
rejections: problems whose reference needs a module the runner does not allow
(`hashlib`), whose inserted bug no original test detects, or whose outputs
are not JSON values. Everything else lands as `humanevalfix_<nnn>/` with the
original HumanEval number, the bug type and failure symptom recorded under
`source` in `task.json`.

## Rebuilding QuixBugs

```
git clone --depth 1 https://github.com/jkoppel/QuixBugs.git data\benchmarks\QuixBugs
python scripts\build_code_repair_tasks.py quixbugs --source data\benchmarks\QuixBugs --output task_sets\code_repair\quixbugs
```

## Split rule (same for both sets)

Cases are deduplicated by arguments. A case whose call appears in the prompt
(a docstring example) is a development test. A case whose `call expected
value` line is longer than 400 characters is hidden only. The rest are split
by whether the seeded program passes them: failing cases alternate
development, hidden, ... starting with development (so the model always sees
at least one failing case), passing cases alternate starting with hidden.
For HumanEvalFix, up to 20 HumanEval+ inputs per task (sampled with the
seed, arguments not already used) are added to the hidden set, with expected
outputs computed by running the reference in the runner. A task is rejected
when the seeded program fails no development test, the hidden set is empty,
or `validate_task` finds a problem.

## Memorisation check

Both benchmarks are public and old enough to be in any 2025 model's training
data. Before using them for the study, run
`scripts/code_repair_memorization_check.py` (see its docstring): it asks the
model to fix each seeded program directly, without the search, several times,
and reports per-task hidden-test pass rates. Tasks the model repairs almost
every time by direct prompting are easy or memorised; the pilot decides how
to weight them (they are still usable for calibration and the rationale
intervention, but a search that succeeds at generation 0 tells us nothing
about selection).
