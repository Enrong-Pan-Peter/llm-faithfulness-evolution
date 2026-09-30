"""End-to-end checks of the shared-loop command line and the three analysis scripts (scripted model, no network)."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import (  # noqa: E402
    assemble_task_subset,
    check_stage_b,
    environment_calibration,
    environment_rationale_intervention,
    environment_selection_response,
    merge_screens,
    pick_hard_tasks,
    planning_direct_solve_check,
)
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


def test_planning_direct_solve_check(tmp_path):
    instance_id = json.loads(PILOT.read_text())["instances"][0]["instance_id"]
    planning_direct_solve_check.main([
        "--instances", str(PILOT), "--task-ids", instance_id, "--provider", "scripted", "--samples", "2",
        "--output", str(tmp_path / "dsc"),
    ])
    summary = json.loads((tmp_path / "dsc" / "direct_solve_check.json").read_text())
    assert summary["n_instances"] == 1 and summary["rows"][0]["samples"] == 2
    assert summary["rows"][0]["band"] in ("easy", "medium", "hard")


def test_skip_existing_and_summary_name(planning_traces, capsys):
    instance_id = json.loads(PILOT.read_text())["instances"][0]["instance_id"]
    before = sorted(planning_traces.glob("ea_plan_operators_*.json"))
    search_run.main([
        "planning", "--instances", str(PILOT), "--task-ids", instance_id, "--provider", "scripted",
        "--runs-per-task", "2", "--max-generations", "3", "--output", str(planning_traces),
        "--skip-existing", "--summary-name", f"summary_{instance_id}.json",
    ])
    assert sorted(planning_traces.glob("ea_plan_operators_*.json")) == before  # nothing re-run
    summary = json.loads((planning_traces / f"summary_{instance_id}.json").read_text())
    assert summary["skipped_existing"] == 2 and summary["runs"] == []
    assert "skipped" in capsys.readouterr().out


def test_pick_hard_tasks_per_group(tmp_path, capsys):
    rows = [
        {"instance_id": "a", "solve_rate": 0.0, "mean_progress": 0.2, "optimal_plan_length": 18},
        {"instance_id": "b", "solve_rate": 0.0, "mean_progress": 0.6, "optimal_plan_length": 18},
        {"instance_id": "c", "solve_rate": 0.5, "mean_progress": 0.9, "optimal_plan_length": 18},
        {"instance_id": "d", "solve_rate": 0.0, "mean_progress": 0.1, "optimal_plan_length": 20},
    ]
    summary = tmp_path / "s.json"
    summary.write_text(json.dumps({"rows": rows}))
    pick_hard_tasks.main([str(summary), "--max-rate", "0", "--group-key", "optimal_plan_length", "--per-group", "1"])
    assert capsys.readouterr().out.split() == ["b", "d"]
    pick_hard_tasks.main([str(summary), "--max-rate", "0", "--count", "2"])
    assert capsys.readouterr().out.split() == ["b", "a"]


def test_assemble_task_subset(tmp_path):
    ids = [record["instance_id"] for record in json.loads(PILOT.read_text())["instances"][:2]]
    out = tmp_path / "subset.json"
    assemble_task_subset.main(["planning", "--sources", str(PILOT), "--ids", *ids, "--rule", "first two", "--output", str(out)])
    data = json.loads(out.read_text())
    assert [r["instance_id"] for r in data["instances"]] == ids and data["selection_rule"] == "first two"
    envs = search_run.load_planning_environments(out, None)
    assert [e.task_id for e in envs] == ids and all(e.expansion_cap is None for e in envs)  # exact length known -> exact fitness
    code_out = tmp_path / "code_subset"
    assemble_task_subset.main(["code_repair", "--sources", str(QUIXBUGS), "--ids", "quixbugs_gcd", "--output", str(code_out)])
    index = json.loads((code_out / "index.json").read_text())
    assert index["n_tasks"] == 1 and (code_out / "quixbugs_gcd" / "task.json").is_file()
    with pytest.raises(SystemExit):
        assemble_task_subset.main(["code_repair", "--sources", str(QUIXBUGS), "--ids", "nope", "--output", str(code_out)])


def test_goal_count_fitness_for_instances_without_exact_length(tmp_path):
    record = dict(json.loads(PILOT.read_text())["instances"][0])
    record["optimal_plan_length"] = None
    path = tmp_path / "unsolved.json"
    path.write_text(json.dumps({"instances": [record]}))
    env = search_run.load_planning_environments(path, None)[0]
    assert env.expansion_cap == 0 and env.optimal_length is None


def test_pick_spread_and_merge_screens(tmp_path, capsys):
    first = {"rows": [
        {"instance_id": "a", "samples": 6, "parsed": 6, "solved": 0, "solve_rate": 0.0, "band": "hard", "mean_progress": 0.9},
        {"instance_id": "b", "samples": 6, "parsed": 6, "solved": 0, "solve_rate": 0.0, "band": "hard", "mean_progress": 0.5},
        {"instance_id": "c", "samples": 6, "parsed": 6, "solved": 0, "solve_rate": 0.0, "band": "hard", "mean_progress": 0.1},
        {"instance_id": "d", "samples": 6, "parsed": 6, "solved": 3, "solve_rate": 0.5, "band": "medium", "mean_progress": 0.7},
    ]}
    second = {"rows": [
        {"instance_id": "a", "samples": 15, "parsed": 15, "solved": 3, "solve_rate": 0.2, "band": "medium", "mean_progress": 0.6},
        {"instance_id": "b", "samples": 15, "parsed": 15, "solved": 0, "solve_rate": 0.0, "band": "hard", "mean_progress": 0.5},
        {"instance_id": "c", "samples": 15, "parsed": 15, "solved": 0, "solve_rate": 0.0, "band": "hard", "mean_progress": 0.3},
    ]}
    (tmp_path / "c.json").write_text(json.dumps(first))
    (tmp_path / "d.json").write_text(json.dumps(second))
    merge_screens.main([str(tmp_path / "c.json"), str(tmp_path / "d.json"), "--output", str(tmp_path / "m.json")])
    merged = json.loads((tmp_path / "m.json").read_text())
    rows = {row["instance_id"]: row for row in merged["rows"]}
    assert rows["a"]["samples"] == 21 and rows["a"]["solved"] == 3 and abs(rows["a"]["solve_rate"] - 3 / 21) < 1e-9
    assert abs(rows["a"]["mean_progress"] - (0.9 * 6 + 0.6 * 15) / 21) < 1e-9 and rows["a"]["band"] == "hard"
    assert rows["d"]["samples"] == 6 and merged["never_solved"] == ["b", "c"]
    capsys.readouterr()
    pick_hard_tasks.main([str(tmp_path / "m.json"), "--max-rate", "0", "--spread", "2"])
    assert capsys.readouterr().out.split() == ["b", "c"]
    pick_hard_tasks.main([str(tmp_path / "m.json"), "--spread", "3"])
    assert capsys.readouterr().out.split() == ["b", "a", "d"]  # ranking b, c, a, d -> positions 0, 2, 3


def test_check_stage_b_reports_gaps_and_completeness(tmp_path, capsys):
    root = tmp_path / "stage_b"
    cond = root / "qwen3_14b" / "planning_main"
    instance_id = json.loads(PILOT.read_text())["instances"][0]["instance_id"]
    search_run.main([
        "planning", "--instances", str(PILOT), "--task-ids", instance_id, "--provider", "scripted",
        "--runs-per-task", "2", "--max-generations", "1", "--output", str(cond), "--summary-name", f"summary_{instance_id}.json",
    ])
    assert check_stage_b.main(["--root", str(root), "--runs", "2"]) == 1  # 1 of 12 study tasks: a gap
    out = capsys.readouterr().out
    assert "only 1 of 12 tasks" in out and f"{instance_id}" in out and "with parsed report" in out
    control = root / "qwen3_14b" / "planning_random_selection"
    search_run.main([
        "planning", "--instances", str(PILOT), "--task-ids", instance_id, "--provider", "scripted",
        "--runs-per-task", "2", "--max-generations", "1", "--output", str(control), "--summary-name", f"summary_{instance_id}.json",
    ])
    (cond / f"summary_{instance_id}.json").unlink()
    check_stage_b.main(["--root", str(root), "--runs", "2"])
    out = capsys.readouterr().out
    assert "has no summary_" in out and "planning_random_selection: 2 runs on 1 tasks" in out
