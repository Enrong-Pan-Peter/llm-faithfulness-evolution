# Code-repair environment

The second environment of the framework (after Contexto). An LLM mutation
operator is shown an imperfect Python function together with the development
tests it fails, and proposes a repaired function plus the same four-key
self-report used in Contexto (`basis_words`, `reason`, `predicted_bucket`,
`predicted_closeness`). The environment grades every candidate exactly by
running tests. Fitness comes from *development* tests the model may see;
the binary success event, "the program passes every hidden test", comes from
*hidden* tests the model never sees. Everything in this package works offline:
no model calls, no network. `search_adapter.py` (`CodeRepairSearchEnvironment`,
method name `ea_code_operators`) plugs one task into the shared loop in
`search/`; `benchmarks/` turns QuixBugs and HumanEvalFix into task
directories (see `task_sets/code_repair/README.md`).

## Layout

| Module | Purpose |
| --- | --- |
| `tasks.py` | Task directory format, `load_task`, `list_tasks`, `validate_task` |
| `runner.py` | `run_tests`: executes a candidate in an isolated child process |
| `evaluation.py` | `evaluate_program`, `fitness`, `success`, `to_common_record` |
| `operators.py` | The four operators as a step-size ladder with the Contexto names (`s_mutation` = change one line for the first failing case, `m_mutation` = rewrite the branch/loop at fault, `ml_mutation` = replace the core keeping the signature and passing cases, `l_mutation` = rewrite the whole function from the specification), uniform `sample_operator(rng)`, `build_operator_prompt` |
| `prompts.py` | Prompt templates, the diagnostic-first pair, the rationale slot helpers, the hidden-test leak guard |
| `tasks/` | Three example tasks used by the offline tests |

## Task format

A task is a directory with `task.json` (`id`, `entry_point`, `prompt`,
`language: "python"`), `reference.py` (correct, never shown), `seeded.py`
(the imperfect starting program; must fail at least one development test),
`dev_tests.py` and `hidden_tests.py`. Both test files define one literal:

```python
TESTS = [
    (("aaab",), "a3b1"),   # (tuple of positional arguments, expected return value)
]
```

The files are parsed with `ast.literal_eval`, never executed, and every value
must be JSON-transportable (tuples are compared as lists; dict keys must be
strings; sets are not supported). `validate_task` runs the reference on both
test sets and the seeded program on the development set and reports problems
(reference failure, seeded program passing everything, a hidden test that
repeats a development input).

The three example tasks (`run_length_encode`, `clock_to_seconds`,
`count_peaks`) are original and deliberately small; each seeded program has
one plausible bug (an off-by-one loop bound, a missing input shape, a wrong
comparison operator). They exist so the package can be tested offline. The
study tasks will come from a time-filtered public benchmark, as the design
brief recommends; the importer for that is not part of this package.

## Fitness

`fitness(evaluation)` is the number of failing development tests, so lower is
better (rank 1 is best in Contexto and the same direction is kept here). A
program that is blocked by the static filter, has a syntax error, raises
while loading, or does not define the entry point scores `dev_total + 1`, one
worse than a program that loads and fails every development test. Tests that
time out or never run count as failing. Hidden tests never enter fitness;
they only decide `success(evaluation)`, which is `all_hidden_passed`.
`progress` in the common record is `dev_passed / dev_total`.

The common evaluation record (`to_common_record`) is the shape every
environment will emit:

```python
{"valid": bool, "success": bool, "score": float, "progress": float, "cost": int, "details": {...}}
```

`valid` is "loaded and not blocked", `score` is the fitness, `cost` is the
number of test executions the candidate consumed (development and hidden),
and `details` is the full `CodeEvaluation` including both raw run records.

`realized_bucket(evaluation)` maps the hidden pass fraction to the same
vocabulary the model is asked to predict (`all_pass`, `most_pass`,
`some_pass`, `none_pass`).

## Runner isolation and its limits

`run_tests` writes a self-contained child script into a temporary directory
and starts it with `python -I -S -X utf8` (environment variables and user
site ignored, no `site` module, script directory not on `sys.path`), an empty
working directory, a minimal environment (locale only), the payload on stdin
and results as JSON lines on stdout. The child imports nothing from this
repository. Inside the child, `import` is limited to an allow-list of pure
standard-library modules and `open`, `exec`, `eval`, `compile`, `input` and a
few others are removed from the candidate's builtins. On POSIX the child gets
CPU-time, address-space (`memory_mb`), file-size and process-count limits
through `resource`; on Windows those limits are skipped. The parent enforces
a hard wall-clock limit (`timeout_s`, whole run including interpreter
start-up) and kills the child; tests that finished before the kill keep their
results.

Before any process starts, `scan_program` refuses source that imports
obviously dangerous modules (`os`, `subprocess`, `socket`, `shutil`, `sys`,
`ctypes`, ...), calls `exec`/`eval`/`compile`/`__import__`, opens a file with
a write mode, or touches introspection attributes such as `__subclasses__`.
A refused program is recorded as `blocked` with the reason and is never
executed. This is a coarse filter and none of the layers above is a security
boundary; there is no network namespace, no filesystem sandbox and no
protection against a determined adversary. The runner is meant for model
output produced during a research run on a machine the researcher controls.

## Prompts

Every candidate prompt has one skeleton: task specification, parent program,
development feedback (failing cases as `call expected X but got Y`), the
operator instruction, one `{rationale_block}` slot, the output-format
paragraph (which demands `{"program": "<complete python source>"}` and
states the success event), and finally the self-report block. The slot is the
only place where non-feedback information enters. It is filled by

* `inherited_rationale_block(parent_rationale)`, which reuses the Contexto
  renderer so both environments inherit rationale in the same words;
* `diagnosis_block(diagnosis)`, the prospective channel: `build_diagnosis_prompt`
  asks for a short diagnosis without code, and
  `build_repair_from_diagnosis_prompt` repairs with that diagnosis in the slot;
* `corrective_hint_block(entry_point, case)`, the mechanism control: one
  sentence naming one failing development input and its expected output.

The rationale-intervention conditions (genuine, unrelated, filler, none) are
different strings in that slot with nothing else moving.
`assert_prompt_has_no_hidden_test_content` is called by every builder and
raises if a hidden call, a hidden `(arguments, expected)` pair, or an entry
line of `hidden_tests.py` appears in the rendered prompt.

## Not here

* No model calls: nothing in this package talks to Ollama or any API; the
  shared loop (`search/`) makes the calls through the Contexto client.
* No crossover operator.
