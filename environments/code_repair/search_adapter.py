"""Code repair as an environment of the shared search loop (``ea_code_operators``).

Candidates are programs (``{"program": "<python source>"}``); the sandboxed
runner grades them on the development tests (fitness = failing development
tests, compile failure = ``dev_total + 1``) and on the hidden tests (success
= all hidden tests pass). The prospective channel is the diagnosis call whose
text goes into the slot of the operator prompt; the corrective hint names the
first failing development case and its expected value.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
from typing import Any

from search.individual import Individual

from . import prompts as code_prompts
from .evaluation import OUTCOME_BUCKETS, CodeEvaluation, evaluate_program, fitness, realized_bucket, success
from .operators import OPERATORS, CodeOperator, build_operator_prompt
from .prompts import (
    assert_prompt_has_no_hidden_test_content,
    build_diagnosis_prompt,
    corrective_hint_block,
    diagnosis_block,
)
from .runner import DEFAULT_MEMORY_MB, DEFAULT_TIMEOUT_S
from .tasks import Task

ENVIRONMENT_NAME = "code_repair"
METHOD_NAME = "ea_code_operators"
INITIAL_PROMPT = (
    "Return only JSON, no markdown or explanation.\n"
    "You are repairing a Python function. The environment runs tests on every candidate you return.\n"
    "\n"
    "Task specification:\n"
    "{task_prompt}\n"
    "\n"
    "Starting program (it fails at least one development test):\n"
    "```python\n"
    "{seeded_program}\n"
    "```\n"
    "\n"
    "Development test results for the starting program:\n"
    "{dev_feedback}\n"
    "\nReturn a repaired version of the function."
) + code_prompts._OUTPUT_FORMAT + code_prompts.CODE_SELF_REPORT_BLOCK

_TEMPLATE_NAMES = (
    "CODE_SELF_REPORT_BLOCK",
    "_CANDIDATE_CONTEXT",
    "_OUTPUT_FORMAT",
    "S_MUTATION_PROMPT",
    "M_MUTATION_PROMPT",
    "ML_MUTATION_PROMPT",
    "L_MUTATION_PROMPT",
    "DIAGNOSIS_PROMPT",
    "REPAIR_FROM_DIAGNOSIS_PROMPT",
    "NO_FAILING_CASE_FOCUS",
)


def prompt_fingerprint(trace_format_version: int) -> str:
    """Short hash of the code-repair prompt templates (same construction as Contexto's)."""
    parts = [f"{name}={getattr(code_prompts, name)}" for name in _TEMPLATE_NAMES]
    parts.append(f"INITIAL_PROMPT={INITIAL_PROMPT}")
    parts.append(f"TRACE_SCHEMA_VERSION={trace_format_version}")
    parts.append(f"PREDICTED_BUCKETS={','.join(OUTCOME_BUCKETS)}")
    return hashlib.sha256("\n---\n".join(parts).encode("utf-8")).hexdigest()[:16]


class CodeRepairSearchEnvironment:
    """One code-repair task for the shared loop."""

    name = ENVIRONMENT_NAME
    method = METHOD_NAME
    buckets = tuple(OUTCOME_BUCKETS)
    operators = tuple(operator.value for operator in OPERATORS)

    def __init__(self, task: Task, *, timeout_s: float = DEFAULT_TIMEOUT_S, memory_mb: int | None = DEFAULT_MEMORY_MB) -> None:
        self.task = task
        self.task_id = task.id
        self.timeout_s = timeout_s
        self.memory_mb = memory_mb
        self.seeded_evaluation = self.evaluate(task.seeded_source)

    # ------------------------------------------------------------ records

    def task_record(self) -> dict[str, Any]:
        return {
            "environment": self.name,
            "task_id": self.task.id,
            "entry_point": self.task.entry_point,
            "source": self.task.source,
            "n_dev_tests": len(self.task.dev_tests),
            "n_hidden_tests": len(self.task.hidden_tests),
            "float_tolerance": self.task.float_tolerance,
            "seeded_dev_passed": self.seeded_evaluation.dev_passed,
            "seeded_hidden_passed": self.seeded_evaluation.hidden_passed,
            "runner_timeout_s": self.timeout_s,
        }

    def prompt_fingerprint(self, trace_format_version: int) -> str:
        return prompt_fingerprint(trace_format_version)

    # ------------------------------------------------------------ prompts

    def initial_prompt(self, *, self_report: bool) -> str:
        prompt = INITIAL_PROMPT.format(
            task_prompt=self.task.prompt.strip(),
            seeded_program=self.task.seeded_source.strip("\n"),
            dev_feedback=code_prompts.render_dev_feedback(self.seeded_evaluation, self.task.entry_point),
            entry_point=self.task.entry_point,
        )
        if not self_report:
            prompt = prompt.replace(code_prompts.CODE_SELF_REPORT_BLOCK, "")
        self.check_prompt(prompt)
        return prompt

    def operator_prompt(self, operator: str, parent: Individual, rationale_block: str, *, self_report: bool) -> str:
        prompt = build_operator_prompt(CodeOperator(operator), self.task, parent.candidate, parent.evaluation, rationale_block)
        if not self_report:
            prompt = prompt.replace(code_prompts.CODE_SELF_REPORT_BLOCK, "")
        return prompt

    def prospective_prompt(self, parent: Individual) -> str:
        return build_diagnosis_prompt(self.task, parent.candidate, parent.evaluation)

    def prospective_text(self, response: Any) -> str:
        if isinstance(response, dict) and isinstance(response.get("diagnosis"), str):
            return " ".join(response["diagnosis"].split())
        return ""

    def prospective_block(self, text: str) -> str:
        return diagnosis_block(text)

    def corrective_hint_block(self, parent: Individual) -> str:
        cases = parent.evaluation.failing_dev_cases if parent.evaluation is not None else []
        if not cases:
            return ""
        return corrective_hint_block(self.task.entry_point, cases[0])

    def check_prompt(self, prompt: str) -> None:
        assert_prompt_has_no_hidden_test_content(prompt, self.task)

    # --------------------------------------------------------- candidates

    def parse_candidate(self, response: Any) -> tuple[Any, str] | None:
        if not isinstance(response, dict):
            return None
        program = response.get("program")
        if not isinstance(program, str) or not program.strip():
            return None
        program = _strip_fences(program)
        return (program, program.strip("\n") + "\n")

    def evaluate(self, candidate: Any) -> CodeEvaluation:
        return evaluate_program(self.task, candidate, self.timeout_s, self.memory_mb)

    def outcome(self, evaluation: CodeEvaluation) -> dict[str, Any]:
        record = evaluation.to_dict()
        record.pop("dev_run", None)
        record.pop("hidden_run", None)
        return {
            "valid": evaluation.valid,
            "success": success(evaluation),
            "score": fitness(evaluation),
            "progress": evaluation.progress,
            "bucket": realized_bucket(evaluation),
            "details": record,
        }

    def distance(self, text_a: str, text_b: str) -> float:
        return program_distance(text_a, text_b)


def _strip_fences(program: str) -> str:
    text = program.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return text


def _syntax_tokens(source: str) -> list[str]:
    """Node-type / name tokens of the syntax tree, or the source tokens if it does not parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source.split()
    tokens: list[str] = []
    for node in ast.walk(tree):
        label = type(node).__name__
        if isinstance(node, ast.Name):
            label += ":" + node.id
        elif isinstance(node, ast.Constant):
            label += ":" + repr(node.value)[:20]
        elif isinstance(node, ast.Attribute):
            label += ":" + node.attr
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            label += ":" + node.name
        tokens.append(label)
    return tokens


def program_distance(source_a: str, source_b: str) -> float:
    """1 - similarity of the two programs' syntax-tree token sequences (``difflib`` ratio)."""
    tokens_a = _syntax_tokens(source_a)
    tokens_b = _syntax_tokens(source_b)
    if not tokens_a and not tokens_b:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(None, tokens_a, tokens_b, autojunk=False).ratio()


__all__ = ["CodeRepairSearchEnvironment", "program_distance", "prompt_fingerprint", "METHOD_NAME", "INITIAL_PROMPT"]
