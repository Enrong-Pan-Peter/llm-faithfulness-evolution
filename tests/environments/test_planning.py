"""Tests for the offline Blocksworld planning environment."""

from __future__ import annotations

import itertools
import json
import random
import unittest

import numpy as np

from contexto_solver.self_report import rationale_inheritance_block
from environments.planning import blocksworld as bw
from environments.planning.blocksworld import (
    BLOCKSWORLD_DOMAIN_PDDL,
    Action,
    Instance,
    InvalidAction,
    apply,
    bfs_optimal_plan,
    generate_instance,
    generate_instance_set,
    goal_complete,
    goal_satisfied_count,
    goal_violations,
    is_consistent_state,
    move_count_bound,
    optimal_plan_length,
    parse_action,
    parse_plan,
    render_problem_pddl,
    state_from_towers,
    state_violations,
    successors,
)
from environments.planning.evaluation import (
    OUTCOME_BUCKETS,
    PlanEvaluation,
    evaluate_plan,
    fitness,
    fitness_exact,
    fitness_goal_count,
    outcome_bucket,
    progress,
    success,
    tie_break,
    to_common_record,
)
from environments.planning.operators import (
    N_OPERATORS,
    OPERATOR_DISTINGUISHING_PHRASES,
    OPERATOR_PROMPTS,
    OPERATORS,
    PlanningOperator,
    build_operator_prompt,
    sample_operator,
)
from environments.planning.prompts import (
    PREDICTED_BUCKETS,
    SELF_REPORT_BLOCK,
    SELF_REPORT_KEYS,
    SUCCESS_EVENT,
    assert_no_hidden_information,
    build_initial_plan_prompt,
    build_plan_from_strategy_prompt,
    build_strategy_prompt,
    corrective_hint_block,
    inherited_rationale_block,
    render_checker_feedback,
)

# Hand-built instance: tower a-b-c (c on top) must become c-b-a (a on top).
THREE_INITIAL = state_from_towers([["a", "b", "c"]])
THREE_GOAL = frozenset({bw.on("a", "b"), bw.on("b", "c"), bw.ontable("c")})
THREE = Instance(THREE_INITIAL, THREE_GOAL, 3, 0, "hand3")
THREE_OPTIMAL = [
    "(unstack c b)",
    "(put-down c)",
    "(unstack b a)",
    "(stack b c)",
    "(pick-up a)",
    "(stack a b)",
]
THREE_OPTIMAL_LENGTH = 6
THREE_INVALID = ["(unstack c b)", "(put-down c)", "(stack b a)"]


def _actions(texts: list[str]) -> list[Action]:
    return [parse_action(text) for text in texts]


def _synthetic_evaluation(*, unsatisfied: int, prefix: int, valid: bool, complete: bool = False) -> PlanEvaluation:
    total = 5
    return PlanEvaluation(
        instance_id="synthetic",
        n_blocks=5,
        parse_ok=True,
        parse_error=None,
        plan_length=prefix if valid else prefix + 1,
        executable_prefix_length=prefix,
        first_invalid_action=None if valid else "(pick-up a)",
        first_invalid_reason=None if valid else "precondition clear(a) does not hold",
        reached_state=THREE_INITIAL,
        goal_predicates_total=total,
        goal_predicates_satisfied=total - unsatisfied,
        goal_complete=complete,
        remaining_distance=None,
        unsatisfied_goal_predicates=(),
    )


class ParserTests(unittest.TestCase):
    def test_accepts_canonical_lines_with_whitespace_and_case(self) -> None:
        text = "(unstack b c)\n  (put-down b) \n\n(PICK-UP A)\n(stack a   b)\n"
        parsed = parse_plan(text)
        self.assertTrue(parsed.ok)
        self.assertEqual(
            [str(action) for action in parsed.actions],
            ["(unstack b c)", "(put-down b)", "(pick-up a)", "(stack a b)"],
        )

    def test_accepts_json_list_and_python_list(self) -> None:
        for source in ('["(unstack b c)", "(put-down b)"]', ["(unstack b c)", "(put-down b)"]):
            parsed = parse_plan(source)
            self.assertTrue(parsed.ok, source)
            self.assertEqual(len(parsed.actions), 2)

    def test_empty_plan_parses(self) -> None:
        self.assertTrue(parse_plan("").ok)
        self.assertEqual(parse_plan([]).actions, ())

    def test_rejects_malformed_entries_and_reports_position(self) -> None:
        cases = {
            "(unstack b c d)": "arity",
            "unstack b c": "no parentheses",
            "(stack a, b)": "comma",
            "(move a b)": "unknown name",
            "(pick-up)": "missing argument",
            "(stack a b) (pick-up c)": "two actions on one line",
            "(stack a b);": "trailing token",
        }
        for bad, label in cases.items():
            parsed = parse_plan(f"(unstack b c)\n{bad}\n(put-down b)")
            self.assertFalse(parsed.ok, label)
            self.assertEqual(parsed.error_position, 2, label)
            self.assertEqual(len(parsed.actions), 1, label)
            self.assertIsNotNone(parsed.error)

    def test_rejects_bad_json_and_non_string_entries(self) -> None:
        self.assertFalse(parse_plan('["(pick-up a)",').ok)
        self.assertFalse(parse_plan("[1, 2]").ok)
        self.assertFalse(parse_plan([1, 2]).ok)

    def test_parse_action_raises(self) -> None:
        with self.assertRaises(bw.PlanParseError):
            parse_action("(pick-up a b)")


class PreconditionTests(unittest.TestCase):
    def setUp(self) -> None:
        # Towers: a-b (b on a), c alone; hand empty.
        self.state = state_from_towers([["a", "b"], ["c"]])

    def _reason(self, state: bw.State, action: str) -> str:
        with self.assertRaises(InvalidAction) as context:
            apply(state, parse_action(action))
        return context.exception.reason

    def test_pick_up(self) -> None:
        picked = apply(self.state, parse_action("(pick-up c)"))
        self.assertIn(bw.holding("c"), picked)
        self.assertNotIn(bw.handempty(), picked)
        self.assertNotIn(bw.ontable("c"), picked)
        self.assertIn("ontable(b)", self._reason(self.state, "(pick-up b)"))
        self.assertIn("clear(a)", self._reason(self.state, "(pick-up a)"))
        holding_c = state_from_towers([["a"], ["b"]], held="c")
        self.assertIn("handempty", self._reason(holding_c, "(pick-up a)"))

    def test_put_down(self) -> None:
        self.assertIn("holding(c)", self._reason(self.state, "(put-down c)"))
        held = apply(self.state, parse_action("(pick-up c)"))
        self.assertEqual(apply(held, parse_action("(put-down c)")), self.state)

    def test_stack(self) -> None:
        held = apply(self.state, parse_action("(pick-up c)"))
        stacked = apply(held, parse_action("(stack c b)"))
        self.assertIn(bw.on("c", "b"), stacked)
        self.assertNotIn(bw.clear("b"), stacked)
        self.assertIn(bw.clear("c"), stacked)
        self.assertIn(bw.handempty(), stacked)
        self.assertIn("holding(c)", self._reason(self.state, "(stack c b)"))
        self.assertIn("clear(a)", self._reason(held, "(stack c a)"))

    def test_unstack(self) -> None:
        unstacked = apply(self.state, parse_action("(unstack b a)"))
        self.assertIn(bw.holding("b"), unstacked)
        self.assertIn(bw.clear("a"), unstacked)
        self.assertNotIn(bw.on("b", "a"), unstacked)
        self.assertIn("on(a,b)", self._reason(self.state, "(unstack a b)"))
        self.assertIn("clear(b)", self._reason(THREE_INITIAL, "(unstack b a)"))
        holding_c = state_from_towers([["a", "b"]], held="c")
        self.assertIn("handempty", self._reason(holding_c, "(unstack b a)"))

    def test_unknown_block_and_self_stack(self) -> None:
        self.assertIn("does not exist", self._reason(self.state, "(pick-up z)"))
        held = apply(self.state, parse_action("(pick-up c)"))
        self.assertIn("itself", self._reason(held, "(stack c c)"))

    def test_successors_agree_with_apply(self) -> None:
        rng = random.Random(3)
        for _ in range(40):
            instance = generate_instance(rng.randint(2, 6), rng.randint(0, 999))
            state = instance.initial_state
            for _ in range(rng.randint(0, 6)):
                options = successors(state)
                state = rng.choice(options)[1]
            self.assertEqual(state_violations(state), [])
            applicable = {}
            for action, next_state in successors(state):
                self.assertEqual(apply(state, action), next_state)
                applicable[str(action)] = next_state
            blocks = instance.blocks
            grounded = [Action(name, (x,)) for name in (bw.PICK_UP, bw.PUT_DOWN) for x in blocks]
            grounded += [
                Action(name, (x, y)) for name in (bw.STACK, bw.UNSTACK) for x in blocks for y in blocks if x != y
            ]
            for action in grounded:
                if str(action) in applicable:
                    continue
                with self.assertRaises(InvalidAction):
                    apply(state, action)


class ReferenceSolverTests(unittest.TestCase):
    def test_hand_built_instance_optimal_length(self) -> None:
        result = bfs_optimal_plan(THREE_INITIAL, THREE_GOAL)
        self.assertEqual(result.length, THREE_OPTIMAL_LENGTH)
        self.assertFalse(result.cap_reached)
        self.assertEqual(optimal_plan_length(THREE_INITIAL, THREE_GOAL), THREE_OPTIMAL_LENGTH)
        state = THREE_INITIAL
        for action in result.plan:
            state = apply(state, action)
        self.assertTrue(goal_complete(state, THREE_GOAL))

    def test_cap_returns_none(self) -> None:
        result = bfs_optimal_plan(THREE_INITIAL, THREE_GOAL, expansion_cap=1)
        self.assertIsNone(result.plan)
        self.assertTrue(result.cap_reached)
        self.assertIsNone(optimal_plan_length(THREE_INITIAL, THREE_GOAL, expansion_cap=1))

    def test_already_satisfied_goal_has_length_zero(self) -> None:
        self.assertEqual(optimal_plan_length(THREE_INITIAL, frozenset({bw.ontable("a")})), 0)

    def test_generated_instances_solve_and_bound_holds(self) -> None:
        for instance in generate_instance_set([2, 3, 4, 5, 6], 3, seed=7):
            result = bfs_optimal_plan(instance.initial_state, instance.goal)
            self.assertIsNotNone(result.plan, instance.instance_id)
            bound = move_count_bound(instance.initial_state, instance.goal)
            self.assertGreaterEqual(bound.blocks_to_move, 1)
            self.assertLessEqual(bound.actions_lower_bound, result.length, instance.instance_id)
            self.assertEqual(bound.actions_lower_bound, 2 * bound.blocks_to_move)

    def test_move_count_bound_counts_blocks_above_a_wrong_block(self) -> None:
        # b must move (goal: b on the table); a sits on b so it must move too.
        state = state_from_towers([["c", "b", "a"]])
        goal = frozenset({bw.ontable("b")})
        bound = move_count_bound(state, goal)
        self.assertEqual(bound.blocks_to_move, 2)
        self.assertEqual(bound.actions_lower_bound, 4)
        self.assertEqual(optimal_plan_length(state, goal), 4)

    def test_move_count_bound_with_held_block(self) -> None:
        held = state_from_towers([["a"], ["b"]], held="c")
        constrained = move_count_bound(held, frozenset({bw.on("c", "a")}))
        self.assertEqual((constrained.blocks_to_move, constrained.actions_lower_bound), (1, 1))
        unconstrained = move_count_bound(held, frozenset({bw.on("a", "b")}))
        self.assertEqual((unconstrained.blocks_to_move, unconstrained.actions_lower_bound), (1, 3))
        satisfied = move_count_bound(held, frozenset({bw.ontable("a")}))
        self.assertEqual((satisfied.blocks_to_move, satisfied.actions_lower_bound), (0, 0))


class EvaluationTests(unittest.TestCase):
    def test_optimal_plan_is_complete_with_fitness_zero(self) -> None:
        evaluation = evaluate_plan(THREE, THREE_OPTIMAL)
        self.assertTrue(evaluation.parse_ok)
        self.assertTrue(evaluation.valid)
        self.assertTrue(evaluation.goal_complete)
        self.assertTrue(success(evaluation))
        self.assertEqual(evaluation.executable_prefix_length, THREE_OPTIMAL_LENGTH)
        self.assertEqual(evaluation.plan_length, THREE_OPTIMAL_LENGTH)
        self.assertEqual(evaluation.remaining_distance, 0)
        self.assertEqual(fitness(evaluation), 0.0)
        self.assertEqual(fitness_exact(evaluation), 0.0)
        self.assertEqual(fitness_goal_count(evaluation), 0.0)
        self.assertEqual(outcome_bucket(evaluation), "complete")
        self.assertEqual(progress(evaluation), 1.0)

    def test_accepts_action_objects_and_text(self) -> None:
        as_objects = evaluate_plan(THREE, _actions(THREE_OPTIMAL))
        as_text = evaluate_plan(THREE, "\n".join(THREE_OPTIMAL))
        self.assertEqual(as_objects, as_text)

    def test_invalid_plan_reports_prefix_and_reason(self) -> None:
        evaluation = evaluate_plan(THREE, THREE_INVALID)
        self.assertTrue(evaluation.parse_ok)
        self.assertFalse(evaluation.valid)
        self.assertEqual(evaluation.executable_prefix_length, 2)
        self.assertEqual(evaluation.first_invalid_action, "(stack b a)")
        self.assertIn("holding(b)", evaluation.first_invalid_reason)
        self.assertEqual(evaluation.plan_length, 3)
        self.assertEqual(evaluation.goal_predicates_total, 3)
        self.assertEqual(evaluation.goal_predicates_satisfied, 1)
        self.assertEqual(evaluation.remaining_distance, 4)
        self.assertFalse(evaluation.goal_complete)
        self.assertEqual(outcome_bucket(evaluation), "invalid")

    def test_prefix_reaching_goal_then_invalid_action_is_not_success(self) -> None:
        evaluation = evaluate_plan(THREE, THREE_OPTIMAL + ["(pick-up c)"])
        self.assertEqual(evaluation.goal_predicates_satisfied, 3)
        self.assertEqual(evaluation.remaining_distance, 0)
        self.assertFalse(evaluation.goal_complete)
        self.assertFalse(success(evaluation))
        self.assertGreater(fitness(evaluation), 0.0)
        self.assertLess(fitness(evaluation), 1.0)

    def test_parse_failure_is_graded_as_empty_plan(self) -> None:
        evaluation = evaluate_plan(THREE, "(unstack c b)\nnonsense")
        self.assertFalse(evaluation.parse_ok)
        self.assertIn("nonsense", evaluation.parse_error)
        self.assertFalse(evaluation.valid)
        self.assertEqual(evaluation.executable_prefix_length, 0)
        self.assertEqual(evaluation.reached_state, THREE_INITIAL)
        self.assertEqual(outcome_bucket(evaluation), "invalid")

    def test_partial_goal_counts(self) -> None:
        partial_goal = frozenset({bw.on("b", "c"), bw.ontable("c"), bw.ontable("a")})
        instance = Instance(THREE_INITIAL, partial_goal, 3, 0, "partial3")
        self.assertEqual(goal_satisfied_count(THREE_INITIAL, partial_goal), 1)
        evaluation = evaluate_plan(instance, THREE_OPTIMAL[:4])
        self.assertTrue(evaluation.valid)
        self.assertEqual(evaluation.goal_predicates_satisfied, 3)
        self.assertTrue(evaluation.goal_complete)
        halfway = evaluate_plan(instance, THREE_OPTIMAL[:2])
        self.assertEqual(halfway.goal_predicates_satisfied, 2)
        self.assertEqual(halfway.unsatisfied_goal_predicates, (bw.on("b", "c"),))
        self.assertEqual(outcome_bucket(halfway), "partial")

    def test_expansion_cap_zero_skips_exact_distance(self) -> None:
        evaluation = evaluate_plan(THREE, THREE_INVALID, expansion_cap=0)
        self.assertIsNone(evaluation.remaining_distance)
        self.assertIsNone(fitness_exact(evaluation))
        self.assertEqual(fitness(evaluation), fitness_goal_count(evaluation))

    def test_common_record_shape_and_json(self) -> None:
        record = to_common_record(evaluate_plan(THREE, THREE_INVALID))
        self.assertEqual(set(record), {"valid", "success", "score", "progress", "cost", "details"})
        self.assertFalse(record["valid"])
        self.assertFalse(record["success"])
        self.assertEqual(record["cost"], 1)
        self.assertAlmostEqual(record["progress"], 1 / 3)
        self.assertEqual(record["details"]["outcome_bucket"], "invalid")
        json.dumps(record)


class FitnessOrderingTests(unittest.TestCase):
    def test_complete_beats_partial_beats_invalid_prefix(self) -> None:
        complete = evaluate_plan(THREE, THREE_OPTIMAL)
        partial = evaluate_plan(THREE, THREE_OPTIMAL[:2])
        invalid = evaluate_plan(THREE, THREE_OPTIMAL[:2] + ["(stack b a)"])
        self.assertEqual(partial.reached_state, invalid.reached_state)
        for score in (fitness, fitness_exact, fitness_goal_count):
            self.assertLess(score(complete), score(partial), score.__name__)
            self.assertLess(score(partial), score(invalid), score.__name__)

    def test_tie_break_never_flips_primary_term(self) -> None:
        for unsatisfied, prefix, valid in itertools.product(range(0, 6), range(0, 60, 7), (True, False)):
            evaluation = _synthetic_evaluation(unsatisfied=unsatisfied, prefix=prefix, valid=valid)
            secondary = tie_break(evaluation)
            self.assertGreater(secondary, 0.0)
            self.assertLess(secondary, 1.0)
            score = fitness_goal_count(evaluation)
            self.assertGreater(score, unsatisfied)
            self.assertLess(score, unsatisfied + 1)
        complete = _synthetic_evaluation(unsatisfied=0, prefix=3, valid=True, complete=True)
        self.assertEqual(fitness_goal_count(complete), 0.0)

    def test_tie_break_prefers_valid_then_longer_prefix(self) -> None:
        short_valid = _synthetic_evaluation(unsatisfied=2, prefix=1, valid=True)
        long_valid = _synthetic_evaluation(unsatisfied=2, prefix=9, valid=True)
        long_invalid = _synthetic_evaluation(unsatisfied=2, prefix=9, valid=False)
        self.assertLess(fitness_goal_count(long_valid), fitness_goal_count(short_valid))
        self.assertLess(fitness_goal_count(short_valid), fitness_goal_count(long_invalid))


class GeneratorTests(unittest.TestCase):
    def test_same_seed_same_instance(self) -> None:
        first, second = generate_instance(6, 17), generate_instance(6, 17)
        self.assertEqual(first, second)
        self.assertEqual(first.instance_id, "bw06_s0017")
        self.assertNotEqual(first.initial_state, generate_instance(6, 18).initial_state)

    def test_generated_states_and_goals_are_legal(self) -> None:
        for n_blocks in range(2, 9):
            for seed in range(6):
                instance = generate_instance(n_blocks, seed)
                self.assertTrue(is_consistent_state(instance.initial_state), instance.instance_id)
                self.assertEqual(state_violations(instance.initial_state), [], instance.instance_id)
                self.assertEqual(goal_violations(instance.goal, instance.blocks), [], instance.instance_id)
                self.assertIn(bw.handempty(), instance.initial_state)
                self.assertEqual(len(instance.blocks), n_blocks)
                self.assertEqual({predicate[1] for predicate in instance.goal}, set(instance.blocks))
                self.assertFalse(goal_complete(instance.initial_state, instance.goal), instance.instance_id)

    def test_partial_goal_is_a_proper_unsatisfied_subset(self) -> None:
        for seed in range(10):
            full = generate_instance(5, seed)
            partial = generate_instance(5, seed, full_goal=False)
            self.assertEqual(partial.initial_state, full.initial_state)
            self.assertTrue(partial.goal < full.goal)
            self.assertFalse(goal_complete(partial.initial_state, partial.goal))
            self.assertEqual(partial.instance_id, f"bw05_s{seed:04d}_partial")

    def test_instance_set_is_deterministic_with_stable_ids(self) -> None:
        first = generate_instance_set([4, 6], 3, seed=1)
        second = generate_instance_set([4, 6], 3, seed=1)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)
        ids = [instance.instance_id for instance in first]
        self.assertEqual(len(set(ids)), 6)
        for instance in first:
            self.assertRegex(instance.instance_id, rf"^bw0{instance.n_blocks}_s\d{{4}}$")

    def test_instance_round_trips_through_dict(self) -> None:
        instance = generate_instance(4, 5)
        self.assertEqual(Instance.from_dict(json.loads(json.dumps(instance.to_dict()))), instance)

    def test_rejects_too_few_blocks(self) -> None:
        with self.assertRaises(ValueError):
            generate_instance(1, 0)


class RenderingTests(unittest.TestCase):
    def test_natural_language_state_and_goal(self) -> None:
        text = bw.render_state_natural_language(THREE_INITIAL)
        self.assertEqual(
            text,
            "Block a is on the table. Block b is on block a. Block c is on block b. Block c is clear. The hand is empty.",
        )
        self.assertEqual(
            bw.render_goal_natural_language(THREE_GOAL),
            "Block a must be on block b. Block b must be on block c. Block c must be on the table.",
        )
        held = bw.render_state_natural_language(state_from_towers([["a"], ["b"]], held="c"))
        self.assertIn("Blocks a and b are clear.", held)
        self.assertIn("The hand is holding block c.", held)

    def test_pddl_export(self) -> None:
        problem = render_problem_pddl(THREE)
        self.assertIn("(define (problem hand3)", problem)
        self.assertIn("(:objects a b c)", problem)
        self.assertIn("(:init (clear c) (handempty) (on b a) (on c b) (ontable a))", problem)
        self.assertIn("(:goal (and (on a b) (on b c) (ontable c)))", problem)
        self.assertIn("(define (domain blocksworld-4ops)", BLOCKSWORLD_DOMAIN_PDDL)
        for name in bw.ACTION_NAMES:
            self.assertIn(f"(:action {name}", BLOCKSWORLD_DOMAIN_PDDL)

    def test_state_invariant_check_catches_inconsistency(self) -> None:
        broken = THREE_INITIAL | {bw.clear("a")}
        self.assertTrue(any("clear(a)" in violation for violation in state_violations(broken)))
        self.assertTrue(state_violations(THREE_INITIAL - {bw.handempty()}))


class PromptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parent_plan = _actions(THREE_INVALID)
        self.evaluation = evaluate_plan(THREE, self.parent_plan)
        self.reference = bfs_optimal_plan(THREE_INITIAL, THREE_GOAL).plan

    def _assert_candidate_prompt(self, prompt: str) -> None:
        self.assertTrue(prompt.endswith(SELF_REPORT_BLOCK))
        self.assertIn('{"plan": [', prompt)
        self.assertIn(SUCCESS_EVENT, prompt)
        self.assertLess(prompt.index('"plan"'), prompt.index('"basis_words"'))
        positions = [prompt.index(f'"{key}"') for key in SELF_REPORT_KEYS]
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("probability", prompt.lower())

    def test_self_report_block_names_every_bucket_and_the_success_event(self) -> None:
        self.assertEqual(PREDICTED_BUCKETS, OUTCOME_BUCKETS)
        for bucket in PREDICTED_BUCKETS:
            self.assertIn(f'"{bucket}"', SELF_REPORT_BLOCK)
        self.assertEqual(SELF_REPORT_BLOCK.count(SUCCESS_EVENT), 2)
        self.assertTrue(SELF_REPORT_BLOCK.startswith("\n"))

    def test_initial_prompt(self) -> None:
        prompt = build_initial_plan_prompt(THREE)
        self._assert_candidate_prompt(prompt)
        self.assertIn("Block c is on block b.", prompt)
        self.assertIn("(pick-up x)", prompt)
        self.assertNotIn("basis_words", build_initial_plan_prompt(THREE, self_report=False))

    def test_every_operator_prompt(self) -> None:
        self.assertEqual(set(OPERATOR_PROMPTS), set(OPERATORS))
        self.assertEqual(N_OPERATORS, 4)
        for operator in OPERATORS:
            prompt = build_operator_prompt(operator, THREE, self.parent_plan, self.evaluation)
            self._assert_candidate_prompt(prompt)
            self.assertIn(OPERATOR_DISTINGUISHING_PHRASES[operator], prompt)
            self.assertIn("(stack b a)", prompt)
            self.assertIn("Executable prefix: 2 of 3", prompt)
            self.assertIn("Goal conditions satisfied after the executable prefix: 1 of 3", prompt)
            self.assertNotIn("distance", prompt.lower())
            assert_no_hidden_information(
                prompt, optimal_length=THREE_OPTIMAL_LENGTH, reference_plan=self.reference
            )

    def test_hint_and_inherited_rationale_share_the_slot(self) -> None:
        parent_rationale = {"basis_words": ["unstack", "clear"], "reason": "Free b first."}
        rationale = inherited_rationale_block(parent_rationale)
        self.assertEqual(rationale, rationale_inheritance_block(parent_rationale)[0])
        self.assertIn("Free b first.", rationale)
        self.assertEqual(inherited_rationale_block(None), "")
        hint = corrective_hint_block(self.evaluation)
        self.assertIn("(stack b a)", hint)
        self.assertIn("holding(b)", hint)
        operator = PlanningOperator.S_MUTATION
        empty = build_operator_prompt(operator, THREE, self.parent_plan, self.evaluation)
        with_rationale = build_operator_prompt(
            operator, THREE, self.parent_plan, self.evaluation, rationale_block=rationale
        )
        with_hint = build_operator_prompt(operator, THREE, self.parent_plan, self.evaluation, rationale_block=hint)
        self.assertEqual(with_rationale.replace(rationale, "", 1), empty)
        self.assertEqual(with_hint.replace(hint, "", 1), empty)
        self.assertEqual(with_rationale.index(rationale), with_hint.index(hint))
        feedback = render_checker_feedback(self.evaluation)
        self.assertLess(with_hint.index(feedback), with_hint.index(hint))
        self.assertLess(with_hint.index(hint), with_hint.index(OPERATOR_DISTINGUISHING_PHRASES[operator]))

    def test_hint_is_empty_for_a_valid_parent(self) -> None:
        valid = evaluate_plan(THREE, THREE_OPTIMAL[:2])
        self.assertEqual(corrective_hint_block(valid), "")
        unparsable = evaluate_plan(THREE, "garbage")
        self.assertIn("could not be parsed", corrective_hint_block(unparsable))

    def test_strategy_prompts(self) -> None:
        strategy_prompt = build_strategy_prompt(THREE, parent_plan=self.parent_plan, evaluation=self.evaluation)
        self.assertIn('{"strategy": "two or three sentences"}', strategy_prompt)
        self.assertNotIn("basis_words", strategy_prompt)
        self.assertIn("Executable prefix: 2 of 3", strategy_prompt)
        fresh = build_strategy_prompt(THREE)
        self.assertNotIn("Parent plan", fresh)
        plan_prompt = build_plan_from_strategy_prompt(THREE, "Clear a first, then build c-b-a.")
        self._assert_candidate_prompt(plan_prompt)
        self.assertIn("Clear a first, then build c-b-a.", plan_prompt)
        assert_no_hidden_information(plan_prompt, optimal_length=THREE_OPTIMAL_LENGTH, reference_plan=self.reference)

    def test_hidden_information_guard(self) -> None:
        prompt = build_initial_plan_prompt(THREE)
        assert_no_hidden_information(prompt, optimal_length=THREE_OPTIMAL_LENGTH, reference_plan=self.reference)
        with self.assertRaises(AssertionError):
            assert_no_hidden_information(prompt + "\nThe optimal plan has 6 actions.")
        with self.assertRaises(AssertionError):
            assert_no_hidden_information(
                prompt + "\nThis problem can be solved in 6 actions.", optimal_length=THREE_OPTIMAL_LENGTH
            )
        with self.assertRaises(AssertionError):
            assert_no_hidden_information(prompt + "\n" + json.dumps(THREE_OPTIMAL), reference_plan=self.reference)
        with self.assertRaises(AssertionError):
            assert_no_hidden_information(prompt + "\n" + "\n".join(THREE_OPTIMAL), reference_plan=self.reference)

    def test_hidden_information_guard_allows_parent_equal_to_reference(self) -> None:
        optimal_evaluation = evaluate_plan(THREE, self.reference)
        prompt = build_operator_prompt(PlanningOperator.ML_MUTATION, THREE, self.reference, optimal_evaluation)
        with self.assertRaises(AssertionError):
            assert_no_hidden_information(prompt, reference_plan=self.reference)
        assert_no_hidden_information(prompt, reference_plan=self.reference, parent_plan=self.reference)


class OperatorSamplingTests(unittest.TestCase):
    def test_uniform_sampling_with_numpy_and_random(self) -> None:
        for rng in (np.random.default_rng(0), random.Random(0)):
            draws = [sample_operator(rng) for _ in range(400)]
            counts = {operator: draws.count(operator) for operator in OPERATORS}
            self.assertEqual(set(counts), set(OPERATORS))
            for count in counts.values():
                self.assertGreater(count, 50)

    def test_sampling_from_candidates(self) -> None:
        rng = random.Random(1)
        pool = [PlanningOperator.L_MUTATION]
        self.assertEqual(sample_operator(rng, pool), PlanningOperator.L_MUTATION)
        with self.assertRaises(ValueError):
            sample_operator(rng, [])

    def test_ladder_matches_contexto_vocabulary(self) -> None:
        from contexto_solver.operators import OPERATOR_DISTINGUISHING_PHRASES as CONTEXTO_PHRASES
        from contexto_solver.operators import OPERATORS as CONTEXTO_OPERATORS

        self.assertEqual([op.value for op in OPERATORS], [op.value for op in CONTEXTO_OPERATORS])
        self.assertEqual(
            {op.value: phrase for op, phrase in OPERATOR_DISTINGUISHING_PHRASES.items()},
            {op.value: phrase for op, phrase in CONTEXTO_PHRASES.items()},
        )

    def test_ladder_prompts_state_what_stays_fixed(self) -> None:
        invalid = evaluate_plan(THREE, THREE_INVALID)
        small = build_operator_prompt(PlanningOperator.S_MUTATION, THREE, THREE_INVALID, invalid)
        self.assertIn("exactly ONE action", small)
        medium = build_operator_prompt(PlanningOperator.M_MUTATION, THREE, THREE_INVALID, invalid)
        self.assertIn("at most four consecutive actions", medium)
        medium_large = build_operator_prompt(PlanningOperator.ML_MUTATION, THREE, THREE_INVALID, invalid)
        self.assertIn("keep the executable prefix", medium_large)
        large = build_operator_prompt(PlanningOperator.L_MUTATION, THREE, THREE_INVALID, invalid)
        self.assertIn("different high-level strategy", large)

if __name__ == "__main__":
    unittest.main()
