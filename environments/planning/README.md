# Planning environment (Blocksworld)

Offline pieces of the second study environment from
`docs/three_environment_extension_plan.md` (sections 2, 4, 5): a formal
Blocksworld problem is rendered in controlled natural language, the model
returns a canonical action list, and an exact checker grades it. Nothing here
calls a model.

## What is here

| Module | Contents |
| --- | --- |
| `blocksworld.py` | State (`frozenset` of predicate tuples), the four IPC "4ops" actions with `apply(state, action)` raising `InvalidAction` with the failing precondition, a strict parser for `(unstack b c)`-style plans (one per line or a JSON list; whitespace and case are the only tolerance), goals as sets of `on`/`ontable` predicates (partial goals allowed), a seeded instance generator with stable ids such as `bw06_s0017`, an exact breadth-first reference solver with an expansion cap, the classic "blocks that must move" lower bound, natural-language and PDDL rendering, and the 4ops domain text as `BLOCKSWORLD_DOMAIN_PDDL`. |
| `evaluation.py` | `evaluate_plan(instance, plan) -> PlanEvaluation` (parse status, executable prefix, first invalid action and reason, reached state, goal predicates satisfied, goal completion, exact remaining distance), the fitness functions, `success`, `outcome_bucket`, and `to_common_record` producing the shared record `{"valid", "success", "score", "progress", "cost", "details"}`. |
| `operators.py` | The four mutation operators as a step-size ladder with the Contexto names (`s_mutation` = change one action, `m_mutation` = re-plan a window of at most four actions around the failure, `ml_mutation` = keep the executable prefix and re-plan the rest, `l_mutation` = new plan from a new strategy), uniform `sample_operator(rng)`, and `build_operator_prompt`. No adaptive probabilities. |
| `prompts.py` | Templates for the initial plan, one per operator, the prospective strategy call and the plan-from-strategy call, the corrective-hint block, checker-feedback rendering, the planning self-report block, and `assert_no_hidden_information`. |

Every candidate prompt demands `{"plan": [...]}` followed by the same four
self-report keys as Contexto (`basis_words`, `reason`, `predicted_bucket`,
`predicted_closeness`), with the success event stated as "the plan executes
from the initial state without an invalid action and reaches every goal
condition". The inherited parent rationale is rendered by
`contexto_solver.self_report.rationale_inheritance_block` (reused, not
re-implemented) and the corrective hint by `corrective_hint_block`; both go
into the one `{rationale_block}` slot so the two conditions differ only there.

## Fitness (lower is better)

`fitness(evaluation)` returns `fitness_exact` when the exact search finished
under its cap, else `fitness_goal_count`:

- `fitness_exact = remaining_distance + tie_break`, where `remaining_distance`
  is the breadth-first distance from the state reached after the executable
  prefix to the goal;
- `fitness_goal_count = unsatisfied_goal_predicates + tie_break`;
- both are exactly `0.0` when the plan succeeds (every action executed and
  every goal predicate holds at the end).

`tie_break = (2 * invalid + 1 / (1 + executable_prefix_length)) / 4` lies in
`(0, 0.75]`, so it never reorders candidates whose integer primary terms
differ. Within one primary level a plan that executes completely beats one
with an invalid action or a parse failure, and then a longer executable prefix
wins. A plan whose prefix reaches the goal but which then contains an invalid
action is not a success; only the tie-break separates it from a solution.

The exact search exhausts the six-block state space (about 7,000 states) in
under 0.1 s and the seven-block space (about 66,000 states) in about 1.3 s; at
eight blocks the default cap of 300,000 expansions can take several seconds
per evaluation, so pass a smaller `expansion_cap` (or `0` to skip the exact
term) when grading many large candidates.

## Search loop

`search_adapter.py` (`PlanningSearchEnvironment`, method name
`ea_plan_operators`) plugs one instance into the shared loop in `search/`:
initial prompt, operator prompts with the rationale slot, the strategy call
of the prospective channel, the corrective hint, response parsing
(`{"plan": [...]}` plus the four report keys), exact grading, the common
outcome record and the plan distance used by the intervention analysis. Run
with `python -m search.run planning --instances task_sets/planning/pilot_3to5.json ...`.

## What is not here

- No external PDDL validator. `render_problem_pddl` and
  `BLOCKSWORLD_DOMAIN_PDDL` exist so VAL or a similar tool can be added later
  as an independent check of `apply`.
- No crossover operator (the brief says to omit it unless compatibility can be
  checked exactly).
- Difficulty bands are not frozen; `optimal_plan_length` and
  `move_count_bound` provide the labels the pilot needs to choose them.
