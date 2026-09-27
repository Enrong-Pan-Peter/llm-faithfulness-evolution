# One-shot screening results used to choose the study sets

Merged with `scripts/merge_screens.py` from the rounds run on the RTX 3090
with qwen3:14b (`out/screen_c`, `out/screen_d`; the `out/` directory itself
is not versioned):

* `planning_deep_6to7_qwen3_14b.json`: the 41 instances of `planning/deep_6to7.json`,
  16 direct attempts each (6 in round C, 10 more in round D for the 31 never solved in C);
  21 never solved.
* `humanevalfix_d3_anon_qwen3_14b.json`: the 115 tasks of `code_repair/humanevalfix_d3_anon`,
  5 direct repairs each plus 10 more for every task never solved in those 5; 32 never solved.
* `quixbugs_d3_anon_qwen3_14b.json`: the 25 tasks of `code_repair/quixbugs_d3_anon`, 15 direct
  repairs each for the 4 never solved in the first 5; 4 never solved.

`scripts/pick_hard_tasks.py <file> --max-rate 0 --spread N` reproduces the
study lists; the chosen rows are copied into `planning/stage_b_12.json` and
`code_repair/stage_b_12/index.json` under `screen`.
