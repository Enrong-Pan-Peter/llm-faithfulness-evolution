# Submitted Contexto experiments (2026)

The exact configuration of the 215 runs behind *Self-Reports Are Not Verification* (submitted 2026-08-31), assembled 2026-09-09 from the raw traces and batch logs of `github.com/Enrong-Pan-Peter/Contexto` at `2baaed1`.

| File | What it is |
| --- | --- |
| `env/_common.env` | settings shared by every condition |
| `env/A1_qwen_ea_selfreport.env` … `selection response_random_selection_control.env`, `rationale intervention_rationale intervention.env` | per-condition environment blocks (export before launching) with the per-game command in the header |
| `batch_command_sheet.md` | the run sheet written for the cluster before the batch (verbatim, with a preface on what changed later) |
| `run_settings_by_run.csv` | one row per per-run trace: condition, game, run index, seed, model, flags, whether `selection_mode` was logged, RUN_CONFIG timestamp, check value |
| `raw_data_file_list.json` | check values of all 215 per-run traces, 43 batch summaries and the rationale intervention/pilot outputs (236 MB, kept in the Contexto repository) |
| `frozen_analysis_file_list.json` | check values of the 105 files of `final_batch_outputs_20260817_1` (107 MB, kept in the paper workspace) |
| `expected_summary.json` | the headline numbers of the paper, transcribed from `final_batch_report_2026-08-17.md` |
| `final_batch_report_2026-08-17.md` | the authoritative results document (rev 2, 2026-08-19) |

Before analysing a checkout of the raw data, verify it:

```
python - <<'PY'
import hashlib, json, pathlib, sys
m = json.load(open("experiments/contexto/submitted_2026/raw_data_file_list.json"))
root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".")   # Contexto repository root
bad = [f["path"] for f in m["files"] if hashlib.check value((root / f["path"]).read_bytes()).hexmodel version id() != f["check value"]]
print("mismatched or missing:", bad or "none")
PY
```

Record-keeping caveats that apply to these runs (details in `docs/where_the_data_is_and_what_happened.md`): the batch spans a solver-code boundary on 2026-07-22 that changed rank-cache transient-failure handling (A1, A2, A3 and half of A4 ran before it; only A2's cache contained poisoned entries, repaired afterwards); `RUN_CONFIG` does not record the binding survivor cap (5) or any serving metadata; the prompt hash `bd9f2858283673a2` identifies prompt text, not code revision.
