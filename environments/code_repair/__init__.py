"""Code-repair environment: an LLM mutation operator repairs a seeded Python function.

Offline pieces only: task loading and validation (``tasks``), isolated test
execution (``runner``), grading and fitness (``evaluation``), operators
(``operators``), prompt templates (``prompts``), benchmark loaders
(``benchmarks``) and the adapter for the shared loop (``search_adapter``).
No model calls live here; see ``README.md``.
"""

from .evaluation import (
    CodeEvaluation,
    FailingCase,
    evaluate_program,
    fitness,
    realized_bucket,
    success,
    to_common_record,
)
from .operators import (
    OPERATOR_PROMPTS,
    OPERATORS,
    CodeOperator,
    build_operator_prompt,
    sample_operator,
)
from .prompts import (
    CODE_SELF_REPORT_BLOCK,
    SUCCESS_EVENT,
    HiddenTestLeakError,
    assert_prompt_has_no_hidden_test_content,
    build_diagnosis_prompt,
    build_repair_from_diagnosis_prompt,
    corrective_hint_block,
    diagnosis_block,
    inherited_rationale_block,
)
from .runner import RunResult, TestCase, TestOutcome, run_tests, scan_program
from .tasks import (
    EXAMPLE_TASKS_ROOT,
    Task,
    TaskFormatError,
    TaskValidationReport,
    list_tasks,
    load_task,
    validate_task,
)

__all__ = [
    "CODE_SELF_REPORT_BLOCK",
    "EXAMPLE_TASKS_ROOT",
    "OPERATORS",
    "OPERATOR_PROMPTS",
    "SUCCESS_EVENT",
    "CodeEvaluation",
    "CodeOperator",
    "FailingCase",
    "HiddenTestLeakError",
    "RunResult",
    "Task",
    "TaskFormatError",
    "TaskValidationReport",
    "TestCase",
    "TestOutcome",
    "assert_prompt_has_no_hidden_test_content",
    "build_diagnosis_prompt",
    "build_operator_prompt",
    "build_repair_from_diagnosis_prompt",
    "corrective_hint_block",
    "diagnosis_block",
    "evaluate_program",
    "fitness",
    "inherited_rationale_block",
    "list_tasks",
    "load_task",
    "realized_bucket",
    "run_tests",
    "sample_operator",
    "scan_program",
    "success",
    "to_common_record",
    "validate_task",
]
