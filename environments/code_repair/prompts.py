"""Prompt templates for the code-repair operators.

Every candidate prompt has the same skeleton: task specification, parent
program, development-test feedback, the operator instruction, a
``{rationale_block}`` slot, the output-format paragraph (which states the
success event), and finally ``CODE_SELF_REPORT_BLOCK``. The slot is the single
place where information that is *not* environment feedback can enter the
prompt. Three things can fill it, each rendered by a helper below:

* the parent's self-report rationale (``inherited_rationale_block``), which
  reuses the Contexto renderer so both environments inherit rationale in the
  same words;
* a diagnosis written by an earlier model call (``diagnosis_block``), the
  prospective channel of the diagnostic-first pair;
* a corrective hint naming one failing development case and its expected
  output (``corrective_hint_block``), the mechanism control that checks
  whether the slot can influence the model at all.

The rationale-intervention conditions (genuine, unrelated, filler, none) are
just different strings placed in that slot; nothing else in the prompt moves.

The self-report keys and their order (``basis_words``, ``reason``,
``predicted_bucket``, ``predicted_closeness``) are the same as in the Contexto
environment; only the bucket vocabulary and the success event are restated
for code. The rationale is requested after the candidate, so within one
completion it is post-hoc, exactly as in Contexto.
"""

from __future__ import annotations

import json
from typing import Any

from contexto_solver.self_report import rationale_inheritance_block

from .evaluation import CodeEvaluation, FailingCase, render_call
from .tasks import Task


SUCCESS_EVENT = "the program passes every hidden test"
REPORT_KEYS: tuple[str, ...] = ("basis_words", "reason", "predicted_bucket", "predicted_closeness")
DIAGNOSIS_MAX_CHARS = 600

CODE_SELF_REPORT_BLOCK = (
    '\nIn the SAME JSON object, also include these four keys, in this order: '
    '"basis_words" (a list of words or identifiers taken from the context above that '
    'your change relied on), "reason" (a one or two sentence explanation, at most 60 '
    'words, of why the returned program should be correct), "predicted_bucket" (exactly '
    'one of "all_pass", "most_pass", "some_pass", or "none_pass", estimating how many of '
    'the hidden tests the returned program will pass: "all_pass" = every hidden test, '
    '"most_pass" = at least half but not all, "some_pass" = at least one but fewer than '
    'half, "none_pass" = none), and "predicted_closeness" (a number from 0 to 1 giving '
    'your estimated chance that ' + SUCCESS_EVENT + ', where 1 means you are certain '
    'that it does).'
)

_CANDIDATE_CONTEXT = (
    "Return only JSON, no markdown or explanation.\n"
    "You are one mutation step of an evolutionary search that repairs a Python function. "
    "The environment runs tests on every candidate you return.\n"
    "\n"
    "Task specification:\n"
    "{task_prompt}\n"
    "\n"
    "Parent program:\n"
    "```python\n"
    "{parent_program}\n"
    "```\n"
    "\n"
    "Development test results for the parent program:\n"
    "{dev_feedback}\n"
)

_OUTPUT_FORMAT = (
    '\nReturn a JSON object whose key "program" holds the complete Python source of the '
    'function {entry_point} (any imports included, nothing else), keeping the name and '
    'signature from the specification: {{"program": "<complete python source of the '
    'function>"}}. Success means that ' + SUCCESS_EVENT + '. The hidden tests are '
    'separate from the development tests shown above and are never revealed.'
)

# The four operators form a ladder from the smallest to the largest change to
# the parent program, mirroring the Contexto ladder (SMALL / MEDIUM /
# MEDIUM-LARGE / LARGE). Each template states what must stay fixed.

S_MUTATION_PROMPT = _CANDIDATE_CONTEXT + (
    "\nMake a SMALL mutation: change exactly ONE line of the parent program (edit one "
    "statement, or insert or delete one line) so that this case is handled correctly: "
    "{focus_case} Every other line must stay exactly as it is."
    "{rationale_block}"
) + _OUTPUT_FORMAT + CODE_SELF_REPORT_BLOCK

M_MUTATION_PROMPT = _CANDIDATE_CONTEXT + (
    "\nMake a MEDIUM mutation: find the one branch, loop or expression of the parent program "
    "that is responsible for the failing development cases and rewrite only that block. "
    "Keep the function's overall approach, its other blocks and the cases that already "
    "pass unchanged."
    "{rationale_block}"
) + _OUTPUT_FORMAT + CODE_SELF_REPORT_BLOCK

ML_MUTATION_PROMPT = _CANDIDATE_CONTEXT + (
    "\nMake a MEDIUM-LARGE mutation: replace the algorithmic core of the parent program "
    "(the loop, recursion, formula or data structure that does the main work) with a "
    "different approach that satisfies the specification. Keep the function name and "
    "signature, the surrounding input handling and output shape, and the behaviour on the "
    "cases that already pass."
    "{rationale_block}"
) + _OUTPUT_FORMAT + CODE_SELF_REPORT_BLOCK

L_MUTATION_PROMPT = _CANDIDATE_CONTEXT + (
    "\nMake a LARGE mutation: ignore the parent program's approach and rewrite the whole "
    "function from the specification, keeping only the function name and signature. "
    "Describe the new approach in your reason."
    "{rationale_block}"
) + _OUTPUT_FORMAT + CODE_SELF_REPORT_BLOCK

# Diagnostic-first pair: the first call writes a diagnosis (no code), the
# second repairs with that diagnosis placed in the rationale slot.
DIAGNOSIS_PROMPT = _CANDIDATE_CONTEXT + (
    "\nDo not write code. Write a short diagnosis of why the parent program fails the "
    "development tests: name the faulty statement or the missing case and the kind of "
    "input it mishandles. Use at most three sentences.\n"
    'Return only JSON with exactly one key: {{"diagnosis": "<at most three sentences>"}}'
)

REPAIR_FROM_DIAGNOSIS_PROMPT = _CANDIDATE_CONTEXT + (
    "\nOperator: REPAIR FROM DIAGNOSIS. If a diagnosis of the parent program is supplied "
    "below, use it to decide what to change; then return the repaired function."
    "{rationale_block}"
) + _OUTPUT_FORMAT + CODE_SELF_REPORT_BLOCK

NO_FAILING_CASE_FOCUS = (
    "no development case currently fails, so pick one plausible boundary input the "
    "development tests do not cover (empty input, a single element, or the largest or "
    "smallest value the specification allows) and make sure the program handles it."
)


class HiddenTestLeakError(AssertionError):
    """A rendered prompt contains hidden-test content."""


def render_dev_feedback(evaluation: CodeEvaluation, entry_point: str) -> str:
    """Describe the parent's development-test outcome using only permitted feedback."""
    if evaluation.blocked:
        return f"The parent program was not run: {evaluation.block_reason}."
    if not evaluation.compile_ok:
        return f"The parent program does not load: {evaluation.compile_error}"
    lines = [f"The parent passes {evaluation.dev_passed} of {evaluation.dev_total} development tests."]
    if evaluation.failing_dev_cases:
        lines.append("Failing development cases (call, expected value, actual outcome):")
        lines.extend(f"- {case.render(entry_point)}" for case in evaluation.failing_dev_cases)
        omitted = evaluation.failing_dev_count - len(evaluation.failing_dev_cases)
        if omitted > 0:
            lines.append(f"- ... and {omitted} more failing development cases not shown")
    if evaluation.dev_timed_out:
        lines.append("The development run hit the time limit.")
    return "\n".join(lines)


def focus_case_text(evaluation: CodeEvaluation, entry_point: str) -> str:
    """The single case the SMALL mutation concentrates on (first failing development case)."""
    if evaluation.failing_dev_cases:
        return f"the development case {evaluation.failing_dev_cases[0].render(entry_point)}."
    return NO_FAILING_CASE_FOCUS


def build_candidate_prompt(
    template: str,
    task: Task,
    parent_program: str,
    parent_evaluation: CodeEvaluation,
    rationale_block: str = "",
) -> str:
    """Render a candidate-producing prompt and check it for hidden-test content."""
    prompt = template.format(
        task_prompt=task.prompt.strip(),
        parent_program=parent_program.strip("\n"),
        dev_feedback=render_dev_feedback(parent_evaluation, task.entry_point),
        entry_point=task.entry_point,
        rationale_block=rationale_block,
        focus_case=focus_case_text(parent_evaluation, task.entry_point),
    )
    assert_prompt_has_no_hidden_test_content(prompt, task)
    return prompt


def build_diagnosis_prompt(task: Task, parent_program: str, parent_evaluation: CodeEvaluation) -> str:
    """First call of the diagnostic-first pair: ask for a short diagnosis, no code."""
    prompt = DIAGNOSIS_PROMPT.format(
        task_prompt=task.prompt.strip(),
        parent_program=parent_program.strip("\n"),
        dev_feedback=render_dev_feedback(parent_evaluation, task.entry_point),
    )
    assert_prompt_has_no_hidden_test_content(prompt, task)
    return prompt


def build_repair_from_diagnosis_prompt(
    task: Task,
    parent_program: str,
    parent_evaluation: CodeEvaluation,
    rationale_block: str,
) -> str:
    """Second call of the pair: repair with the diagnosis (or a control) in the slot."""
    return build_candidate_prompt(
        REPAIR_FROM_DIAGNOSIS_PROMPT, task, parent_program, parent_evaluation, rationale_block
    )


def inherited_rationale_block(parent_rationale: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    """Render the parent's self-report rationale for the slot.

    Delegates to the Contexto renderer, so truncation limits, wording and the
    returned metadata (text hash, truncation flag) are identical across
    environments. Returns ``("", {})`` when there is nothing to inherit.
    """
    return rationale_inheritance_block(parent_rationale)


def diagnosis_block(diagnosis: str, max_chars: int = DIAGNOSIS_MAX_CHARS) -> str:
    """Render a diagnosis from an earlier call for the slot (empty text gives "")."""
    text = " ".join(diagnosis.split())
    if not text:
        return ""
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "..."
    return f"\nDiagnosis written before this repair: {json.dumps(text)}."


def corrective_hint_block(entry_point: str, case: FailingCase) -> str:
    """One sentence naming one failing development input and its expected output."""
    return f"\nCorrective hint: the call {render_call(entry_point, case.inputs)} must return {case.expected!r}."


def hidden_test_fingerprints(task: Task) -> tuple[str, ...]:
    """Strings whose presence in a prompt means hidden-test content leaked.

    For each hidden case: the rendered call and the ``(arguments, expected)``
    pair; plus every entry line of ``hidden_tests.py`` (lines starting with
    ``(``), so a verbatim copy of the file is caught too.
    """
    marks: list[str] = []
    for case in task.hidden_tests:
        marks.append(render_call(task.entry_point, case.args))
        marks.append(repr((tuple(case.args), case.expected)))
    for line in task.hidden_tests_source.splitlines():
        stripped = line.strip()
        if stripped.startswith("("):
            marks.append(stripped)
    return tuple(dict.fromkeys(marks))


def assert_prompt_has_no_hidden_test_content(prompt: str, task: Task) -> None:
    """Raise ``HiddenTestLeakError`` if any hidden-test fingerprint appears in ``prompt``."""
    for mark in hidden_test_fingerprints(task):
        if mark in prompt:
            raise HiddenTestLeakError(f"prompt for task {task.id!r} contains hidden-test content: {mark!r}")
