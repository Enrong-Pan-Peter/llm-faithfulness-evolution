"""End-to-end checks of the shared-loop command line and the three analysis scripts (scripted model, no network)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import environment_calibration, environment_rationale_intervention, environment_selection_response  # noqa: E402
from search import run as search_run  # noqa: E402

PILOT = ROOT / "task_sets" / "planning" / "pilot_3to5.json"
QUIXBUGS = ROOT / "task_sets" / "code_repair" / "quixbugs"


@pytest.fixture(scope="module")
def planning_traces(tmp_path_factory) -> Path:
    output = tmp_path_factory.mktemp("planning_traces")
    instance_id = json.loads(PILOT.read_text())["instances"][0]["instance_id"]
    search_run.main([
        "planning", "--instances", str(PILOT), "--task-ids", instance_id, "--provider", "scripted",
        "--runs-per-task", "2", "--max-generations", "3", "--output", str(output), "--label", "test",
    ])
    return output


@pytest.fixture(scope="module")
def code_traces(tmp_path_factory) -> Path:
    output = tmp_path_factory.mktemp("code_traces")
    search_run.main([
        "code_repair", "--tasks", str(QUIXBUGS), "--task-ids", "quixbugs_gcd", "--provider", "scripted",
        "--runs-per-task", "1", "--max-generations", "2", "--rationale-channel", "prospective", "--output", str(output),
    ])
    return output


def test_run_writes_traces_and_summary(planning_traces):
    summary = json.loads((planning_traces / "summary.json").read_text())
    assert summary["environment"] == "planning" and summary["runs_per_task"] == 2 and summary["n_tasks"] == 1
    assert summary["aggregate"]["n_runs"] == 2 and summary["settings"]["initial_population"] == 15
    traces = sorted(planning_traces.glob("ea_plan_operators_*.json"))
    assert len(traces) == 2
    events = json.loads(traces[0].read_text())
    assert events[0]["event"] == "RUN_CONFIG" and events[0]["details"]["run_label"] == "test"
    assert {row["seed"] for row in summary["runs"]} == {0, 1}


def test_calibration_script(planning_traces, tmp_path):
    output = tmp_path / "cal"
    environment_calibration.main([str(planning_traces / "*.json"), "--output-dir", str(output)])
    metrics = json.loads((output / "metrics.json").read_text())
    assert metrics["n_traces"] == 2 and metrics["bucket_order"] == ["complete", "partial", "invalid"]
    assert metrics["overall"]["with_report"] > 0 and "operator" in metrics["splits"]
    with (output / "candidates.csv").open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows and {"child_id", "success", "predicted_closeness", "survived"} <= set(rows[0])
    assert (output / "report.md").read_text().startswith("# Calibration")


def test_selection_response_script(planning_traces, tmp_path):
    output = tmp_path / "sel"
    environment_selection_response.main([str(planning_traces / "*.json"), "--output-dir", str(output), "--permutations", "50"])
    result = json.loads((output / "selection_response.json").read_text())
    assert result["n_units"] > 0 and result["selection_settings"] == ["mu_plus_lambda"]
    assert set(result["measures"]) == {"binary_error", "bucket_distance"}
    gap = result["measures"]["binary_error"]["gap"]
    assert gap["n_pool"] == result["n_units"]
    assert (output / "units.csv").is_file()


def test_intervention_script_planning(planning_traces, tmp_path):
    output = tmp_path / "int"
    environment_rationale_intervention.main([
        str(planning_traces / "*.json"), "--events-per-trace", "2", "--provider", "scripted", "--output", str(output),
    ])
    result = json.loads((output / "rationale_intervention_records.json").read_text())
    assert result["n_calls"] == 4
    conditions = {record["condition"] for record in result["records"]}
    assert {"genuine", "filler", "absent"} <= conditions
    genuine = [record for record in result["records"] if record["condition"] == "genuine"]
    assert all(record["parse_ok"] for record in genuine)
    assert all(record["distance_to_parent"] is not None for record in genuine)
    assert (output / "paired_differences.csv").is_file() and (output / "summary.json").is_file()
    assert "conditions" in result["summary"]


def test_intervention_script_code(code_traces, tmp_path):
    output = tmp_path / "int_code"
    environment_rationale_intervention.main([
        str(code_traces / "*.json"), "--tasks", str(QUIXBUGS), "--events-per-trace", "2", "--provider", "scripted",
        "--output", str(output),
    ])
    result = json.loads((output / "rationale_intervention_records.json").read_text())
    assert result["n_calls"] >= 1
    assert all(record["channel"] == "prospective" for record in result["records"])
    hints = [record for record in result["records"] if record["condition"] == "corrective_hint"]
    assert hints and all("Corrective hint" in record["slot_text"] for record in hints)


def test_code_run_summary(code_traces):
    summary = json.loads((code_traces / "summary.json").read_text())
    assert summary["environment"] == "code_repair" and summary["settings"]["rationale_channel"] == "prospective"
    events = json.loads(sorted(code_traces.glob("ea_code_operators_*.json"))[0].read_text())
    assert events[0]["details"]["task"]["source"]["benchmark"] == "quixbugs"
