"""Parity checks between this repository and the submitted Contexto study.

These tests pin the facts that make the migrated code a faithful carrier of the
submitted experiments:

1. the prompt fingerprint recorded in every submitted trace (``bd9f2858283673a2``)
   is reproduced by the prompt templates in this tree;
2. the prompt templates printed in the paper appendix are byte-identical to the
   templates in ``contexto_solver/llm_client.py``;
3. the trace-format-3 fixtures (one self-report-on run, one self-report-off run,
   one rationale-intervention output subset) load through the three analysis entry
   points and carry the expected RUN_CONFIG facts;
4. a reporting-enabled prompt ends with the self-report block and a
   reporting-disabled run records no self report at all.

No network, no LLM, no writes outside a temporary directory.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contexto_solver import config, llm_client  # noqa: E402
from contexto_solver.calibration.metrics import metrics_summary, realized_rank  # noqa: E402
from contexto_solver.calibration.reader import extract_individuals, load_trace, run_config  # noqa: E402
from contexto_solver.self_report import SELF_REPORT_BLOCK, SUBMITTED_STUDY_PROMPT_FINGERPRINT, prompt_fingerprint  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "traces"
A1 = FIXTURES / "A1_qwen_ea_selfreport_game1303_run1.json"
A3 = FIXTURES / "A3_qwen_ea_noreport_game1372_run3.json"
INTERVENTION = FIXTURES / "rationale_intervention_records_game1303_subset.json"
PROMPT_APPENDIX = ROOT / "docs" / "prompts" / "submitted_prompt_templates.txt"

SUBMITTED_FINGERPRINT = SUBMITTED_STUDY_PROMPT_FINGERPRINT
SUBMITTED_FORMAT = 3


def _parse_prompt_appendix(path: Path) -> dict[str, str]:
    """``NAME_PROMPT`` / ``SELF_REPORT_BLOCK`` header lines separate blocks."""
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if re.fullmatch(r"[A-Z_]+_PROMPT|SELF_REPORT_BLOCK", line):
            current = line
            blocks[current] = []
            continue
        if current is not None:
            blocks[current].append(line)
    return {name: "\n".join(lines).strip("\n") for name, lines in blocks.items()}


def _rendered_template(template: str) -> str:
    """The appendix prints templates as rendered text: ``str.format`` brace
    escapes (``{{`` / ``}}``) appear as single braces."""
    return template.replace("{{", "{").replace("}}", "}").strip("\n")


def _squash(text: str) -> str:
    return " ".join(text.split())


class PromptFingerprintTests(unittest.TestCase):
    def test_fingerprint_matches_every_submitted_trace(self) -> None:
        # the prompt text is unchanged since the study: with the study's trace
        # format number the fingerprint reproduces exactly
        self.assertEqual(prompt_fingerprint(trace_format_version=3), SUBMITTED_FINGERPRINT)
        self.assertEqual(SUBMITTED_FINGERPRINT, "bd9f2858283673a2")

    def test_fixture_traces_carry_the_submitted_fingerprint_and_format(self) -> None:
        for path in (A1, A3):
            with self.subTest(trace=path.name):
                cfg = run_config(load_trace(path))
                self.assertEqual(cfg.prompt_fingerprint, SUBMITTED_FINGERPRINT)
                self.assertEqual(cfg.trace_format_version, SUBMITTED_FORMAT)
                self.assertEqual(cfg.method, "ea_llm_self_adaptive")  # name written by the submitted study
                self.assertEqual(cfg.sigma_mode, "frozen_uniform")

    def test_trace_format_advanced_once(self) -> None:
        self.assertEqual(config.TRACE_FORMAT_VERSION, SUBMITTED_FORMAT + 1)


class PromptAppendixParityTests(unittest.TestCase):
    def test_appendix_templates_match_code(self) -> None:
        appendix = _parse_prompt_appendix(PROMPT_APPENDIX)
        expected_names = {
            "S_MUTATION_PROMPT",
            "M_MUTATION_PROMPT",
            "ML_MUTATION_PROMPT",
            "L_MUTATION_PROMPT",
            "CROSSOVER_PROMPT",
            "NEXT_GUESS_PROMPT",
        }
        self.assertEqual(set(appendix), expected_names | {"SELF_REPORT_BLOCK"})
        for name in sorted(expected_names):
            with self.subTest(prompt=name):
                self.assertEqual(appendix[name], _rendered_template(getattr(llm_client, name)))
        # The appendix wraps the single-line self-report block for readability;
        # compare modulo whitespace.
        self.assertEqual(_squash(appendix["SELF_REPORT_BLOCK"]), _squash(SELF_REPORT_BLOCK))


class FixtureLoadsThroughAnalysisTests(unittest.TestCase):
    def test_calibration_reader_and_metrics_on_self_report_run(self) -> None:
        events = load_trace(A1)
        cfg = run_config(events)
        self.assertTrue(cfg.self_report)
        self.assertTrue(cfg.rationale_inheritance)
        individuals = extract_individuals(events, trace_file=A1.name)
        self.assertEqual(len(individuals), 24)
        # The paper's report target: the first proposed word that received a rank.
        ranks = [realized_rank(ind, which="first_proposed") for ind in individuals]
        self.assertTrue(all(r is None or r >= 1 for r in ranks))
        summary = metrics_summary(individuals, which="first_proposed")
        self.assertEqual(summary["count"], 24)
        self.assertEqual(summary["which_realized"], "first_proposed")
        self.assertIn("spearman", summary)
        self.assertIn("buckets", summary)
        self.assertIn("reliability", summary)

    def test_reporting_disabled_run_has_no_self_reports(self) -> None:
        events = load_trace(A3)
        cfg = run_config(events)
        self.assertFalse(cfg.self_report)
        self.assertFalse(cfg.rationale_inheritance)
        sampled = [e for e in events if e["event"] == "OPERATOR_SAMPLED"]
        self.assertGreater(len(sampled), 0)
        for event in sampled:
            self.assertNotIn("self_report", event["details"])
        self.assertEqual(extract_individuals(events, trace_file=A3.name), [])

    def test_reporting_enabled_prompt_ends_with_self_report_block(self) -> None:
        events = load_trace(A1)
        sampled = [e for e in events if e["event"] == "OPERATOR_SAMPLED"]
        prompts = [e["details"]["self_report"]["self_report_prompt"] for e in sampled]
        self.assertTrue(prompts)
        for prompt in prompts:
            self.assertTrue(prompt.rstrip().endswith(SELF_REPORT_BLOCK.rstrip()))

    def test_selection_response_extracts_survivor_labels(self) -> None:
        from scripts.selection_response_analysis import extract_survivor_records

        events = load_trace(A1)
        individuals, diagnostics = extract_survivor_records(events, A1.name)
        self.assertGreater(len(individuals), 0)
        self.assertIsInstance(diagnostics, dict)
        selects = [e for e in events if e["event"] == "SELECT"]
        self.assertEqual(len(selects), 4)
        for event in selects:
            self.assertIn("kept", event["details"])
            self.assertIn("discarded", event["details"])
            # submitted traces: the tophalf path logs no selection_mode key
            self.assertNotIn("selection_mode", event["details"])

    def test_intervention_records_group_into_complete_four_condition_events(self) -> None:
        from scripts.rationale_intervention_analysis import group_by_event, load_intervention_records, paired_differences

        records = load_intervention_records([str(INTERVENTION)])
        self.assertEqual(len(records), 32)
        events = group_by_event(records)
        self.assertEqual(len(events), 8)
        for key, conditions in events.items():
            self.assertEqual(set(conditions), {"genuine", "wrong", "filler", "absent"}, key)
        diffs = paired_differences(events)
        self.assertTrue(diffs)
        payload = json.loads(INTERVENTION.read_text(encoding="utf-8"))
        self.assertEqual(payload["metadata"]["arms"], ["genuine", "wrong", "filler", "absent"])
        # the output re-runs A1 events of game 1303; the first event comes from the A1 fixture run
        self.assertTrue(all(r["game_number"] == 1303 for r in records))
        self.assertEqual(records[0]["trace_file"], A1.name.replace("A1_qwen_ea_selfreport_game1303_run1", "ea_llm_self_adaptive_api_1303_run1_20260721_233700"))


if __name__ == "__main__":
    unittest.main()
