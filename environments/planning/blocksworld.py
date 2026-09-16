"""Classic 4-operator Blocksworld: states, actions, parsing, rendering, generation.

The domain is the IPC-2000 ``BLOCKS`` domain with four operators (``pick-up``,
``put-down``, ``stack``, ``unstack``) and five predicates (``on``, ``ontable``,
``clear``, ``handempty``, ``holding``). A state is a ``frozenset`` of predicate
tuples such as ``("on", "a", "b")`` so it is hashable and can be used directly
as a search node. A goal is a ``frozenset`` restricted to ``on`` and ``ontable``
predicates; partial goals (not every block constrained) are allowed.

Reference solver: ``bfs_optimal_plan`` is an exact breadth-first search over the
explicit state graph, with a visited table so every state is expanded at most
once and an expansion cap so it never runs away on large instances. It is exact
whenever it returns a plan. ``move_count_bound`` is the classic linear-time
"blocks that must move" count; it is only a lower bound and is intended for
instances too large for the exact search.
"""

from __future__ import annotations

import json
import random
import re
from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

Predicate = tuple[str, ...]
State = frozenset[Predicate]
Goal = frozenset[Predicate]

ON = "on"
ONTABLE = "ontable"
CLEAR = "clear"
HANDEMPTY = "handempty"
HOLDING = "holding"

PREDICATE_ARITY: dict[str, int] = {ON: 2, ONTABLE: 1, CLEAR: 1, HANDEMPTY: 0, HOLDING: 1}
GOAL_PREDICATE_NAMES = (ON, ONTABLE)

PICK_UP = "pick-up"
PUT_DOWN = "put-down"
STACK = "stack"
UNSTACK = "unstack"

ACTION_ARITY: dict[str, int] = {PICK_UP: 1, PUT_DOWN: 1, STACK: 2, UNSTACK: 2}
ACTION_NAMES = tuple(ACTION_ARITY)

DEFAULT_EXPANSION_CAP = 300_000
MIN_BLOCKS = 2
INSTANCE_SEED_SPACE = 10_000

BLOCKSWORLD_DOMAIN_PDDL = """(define (domain blocksworld-4ops)
  (:requirements :strips)
  (:predicates (on ?x ?y) (ontable ?x) (clear ?x) (handempty) (holding ?x))

  (:action pick-up
    :parameters (?x)
    :precondition (and (clear ?x) (ontable ?x) (handempty))
    :effect (and (not (ontable ?x)) (not (clear ?x)) (not (handempty)) (holding ?x)))

  (:action put-down
    :parameters (?x)
    :precondition (holding ?x)
    :effect (and (not (holding ?x)) (clear ?x) (handempty) (ontable ?x)))

  (:action stack
    :parameters (?x ?y)
    :precondition (and (holding ?x) (clear ?y))
    :effect (and (not (holding ?x)) (not (clear ?y)) (clear ?x) (handempty) (on ?x ?y)))

  (:action unstack
    :parameters (?x ?y)
    :precondition (and (on ?x ?y) (clear ?x) (handempty))
    :effect (and (holding ?x) (clear ?y) (not (clear ?x)) (not (handempty)) (not (on ?x ?y)))))
"""


# --------------------------------------------------------------------------- #
# Predicates and states
# --------------------------------------------------------------------------- #


def on(above: str, below: str) -> Predicate:
    """``on(above, below)``: block ``above`` rests directly on block ``below``."""
    return (ON, above, below)


def ontable(block: str) -> Predicate:
    """``ontable(block)``: the block rests directly on the table."""
    return (ONTABLE, block)


def clear(block: str) -> Predicate:
    """``clear(block)``: no block is on top of it and it is not held."""
    return (CLEAR, block)


def handempty() -> Predicate:
    """``handempty``: the hand holds nothing."""
    return (HANDEMPTY,)


def holding(block: str) -> Predicate:
    """``holding(block)``: the hand holds the block."""
    return (HOLDING, block)


def predicate_text(predicate: Predicate) -> str:
    """Render a predicate as ``on(a,b)`` / ``handempty``."""
    name, *args = predicate
    return f"{name}({','.join(args)})" if args else name


def predicate_pddl(predicate: Predicate) -> str:
    """Render a predicate as a PDDL atom such as ``(on a b)``."""
    return f"({' '.join(predicate)})"


def state_from_towers(towers: Sequence[Sequence[str]], held: str | None = None) -> State:
    """Build a consistent state from towers listed bottom-to-top.

    ``held`` names a block carried by the hand; it must not appear in any tower.
    Raises ``ValueError`` on empty towers or repeated block names.
    """
    predicates: set[Predicate] = set()
    seen: set[str] = set()
    for tower in towers:
        if not tower:
            raise ValueError("A tower must contain at least one block.")
        for block in tower:
            if block in seen:
                raise ValueError(f"Block {block!r} appears more than once.")
            seen.add(block)
        predicates.add(ontable(tower[0]))
        for below, above in zip(tower, tower[1:]):
            predicates.add(on(above, below))
        predicates.add(clear(tower[-1]))
    if held is None:
        predicates.add(handempty())
    else:
        if held in seen:
            raise ValueError(f"Held block {held!r} also appears in a tower.")
        predicates.add(holding(held))
    return frozenset(predicates)


def blocks_in_state(state: State) -> frozenset[str]:
    """Every block name mentioned by any predicate of the state."""
    return frozenset(arg for predicate in state for arg in predicate[1:])


def held_block(state: State) -> str | None:
    """The block the hand is holding, or ``None`` when the hand is empty."""
    for predicate in state:
        if predicate[0] == HOLDING:
            return predicate[1]
    return None


def towers_from_state(state: State) -> list[list[str]]:
    """Towers listed bottom-to-top, ordered by their bottom block name.

    Assumes a consistent state (see ``state_violations``); the held block, if
    any, is not part of any tower.
    """
    above_of = {predicate[2]: predicate[1] for predicate in state if predicate[0] == ON}
    towers: list[list[str]] = []
    for bottom in sorted(predicate[1] for predicate in state if predicate[0] == ONTABLE):
        tower = [bottom]
        while tower[-1] in above_of:
            tower.append(above_of[tower[-1]])
        towers.append(tower)
    return towers


def state_violations(state: State) -> list[str]:
    """Return a list of invariant violations; an empty list means consistent.

    Invariants: known predicate names with the right arity; exactly one of
    ``handempty`` / a single ``holding``; every block has exactly one position
    (on the table, on one block, or held); at most one block rests on any block;
    ``clear(x)`` holds exactly when nothing is on ``x`` and ``x`` is not held;
    every tower is rooted at the table (no cycles).
    """
    violations: list[str] = []
    for predicate in state:
        name = predicate[0]
        if name not in PREDICATE_ARITY:
            violations.append(f"unknown predicate {name!r}")
        elif len(predicate) - 1 != PREDICATE_ARITY[name]:
            violations.append(f"wrong arity for {predicate_text(predicate)}")
    if violations:
        return violations

    held = [predicate[1] for predicate in state if predicate[0] == HOLDING]
    hand_empty = handempty() in state
    if len(held) > 1:
        violations.append(f"more than one block is held: {sorted(held)}")
    if hand_empty == bool(held):
        violations.append("exactly one of handempty / holding(x) must hold")

    blocks = blocks_in_state(state)
    below_of: dict[str, str] = {}
    supporters: dict[str, list[str]] = {}
    for predicate in state:
        if predicate[0] == ON:
            above, below = predicate[1], predicate[2]
            supporters.setdefault(below, []).append(above)
            below_of[above] = below
    for block in sorted(blocks):
        positions = (
            (1 if ontable(block) in state else 0)
            + sum(1 for predicate in state if predicate[0] == ON and predicate[1] == block)
            + (1 if block in held else 0)
        )
        if positions != 1:
            violations.append(f"block {block} has {positions} positions (expected exactly 1)")
        on_top = supporters.get(block, [])
        if len(on_top) > 1:
            violations.append(f"more than one block rests on {block}: {sorted(on_top)}")
        should_be_clear = not on_top and block not in held
        if (clear(block) in state) != should_be_clear:
            violations.append(f"clear({block}) is {'missing' if should_be_clear else 'wrongly present'}")
        visited: set[str] = set()
        cursor = block
        while cursor in below_of:
            if cursor in visited:
                violations.append(f"cycle in the tower containing {block}")
                break
            visited.add(cursor)
            cursor = below_of[cursor]
    return violations


def is_consistent_state(state: State) -> bool:
    """``True`` when ``state_violations`` finds nothing."""
    return not state_violations(state)


# --------------------------------------------------------------------------- #
# Actions
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Action:
    """A grounded action such as ``(unstack b c)``; ``str(action)`` is canonical."""

    name: str
    args: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.name not in ACTION_ARITY:
            raise ValueError(f"Unknown action name {self.name!r}; expected one of {ACTION_NAMES}.")
        if len(self.args) != ACTION_ARITY[self.name]:
            raise ValueError(f"{self.name} takes {ACTION_ARITY[self.name]} argument(s), got {self.args!r}.")

    def __str__(self) -> str:
        return f"({self.name} {' '.join(self.args)})"


class InvalidAction(Exception):
    """Raised by ``apply`` when an action's preconditions do not hold."""

    def __init__(self, action: Action, reason: str) -> None:
        super().__init__(f"{action} is invalid: {reason}")
        self.action = action
        self.reason = reason


def _explain_missing(state: State, predicate: Predicate) -> str:
    """Describe why a precondition fails, in the checker's plain vocabulary."""
    name = predicate[0]
    held = held_block(state)
    if name == HANDEMPTY:
        return f"the hand is holding block {held}"
    if name == HOLDING:
        return "the hand is empty" if held is None else f"the hand is holding block {held}, not {predicate[1]}"
    block = predicate[1]
    if name == CLEAR:
        if block == held:
            return f"block {block} is being held"
        for other in state:
            if other[0] == ON and other[2] == block:
                return f"block {other[1]} is on block {block}"
        return f"block {block} is not clear"
    for other in state:
        if other[0] == ON and other[1] == block:
            return f"block {block} is on block {other[2]}"
    if ontable(block) in state:
        return f"block {block} is on the table"
    if block == held:
        return f"block {block} is being held"
    return f"block {block} is not where the action expects"


def _require(state: State, action: Action, *preconditions: Predicate) -> None:
    for predicate in preconditions:
        if predicate not in state:
            raise InvalidAction(
                action,
                f"precondition {predicate_text(predicate)} does not hold ({_explain_missing(state, predicate)})",
            )


def apply(state: State, action: Action) -> State:
    """Apply one action and return the successor state.

    Raises ``InvalidAction`` naming the first failing precondition. Every block
    named by the action must exist in the state.
    """
    known = blocks_in_state(state)
    for block in action.args:
        if block not in known:
            raise InvalidAction(action, f"block {block} does not exist in this problem")
    if len(action.args) == 2 and action.args[0] == action.args[1]:
        raise InvalidAction(action, "a block cannot be stacked on or unstacked from itself")

    if action.name == PICK_UP:
        (block,) = action.args
        _require(state, action, clear(block), ontable(block), handempty())
        return (state - {ontable(block), clear(block), handempty()}) | {holding(block)}
    if action.name == PUT_DOWN:
        (block,) = action.args
        _require(state, action, holding(block))
        return (state - {holding(block)}) | {ontable(block), clear(block), handempty()}
    if action.name == STACK:
        above, below = action.args
        _require(state, action, holding(above), clear(below))
        return (state - {holding(above), clear(below)}) | {on(above, below), clear(above), handempty()}
    above, below = action.args
    _require(state, action, on(above, below), clear(above), handempty())
    return (state - {on(above, below), clear(above), handempty()}) | {holding(above), clear(below)}


def successors(state: State) -> list[tuple[Action, State]]:
    """All applicable actions with their successor states (for search).

    Assumes a consistent state. Equivalent to trying ``apply`` with every
    grounded action but only enumerates the applicable ones.
    """
    held = held_block(state)
    clear_blocks = sorted(predicate[1] for predicate in state if predicate[0] == CLEAR)
    result: list[tuple[Action, State]] = []
    if held is None:
        below_of = {predicate[1]: predicate[2] for predicate in state if predicate[0] == ON}
        for block in clear_blocks:
            if block in below_of:
                below = below_of[block]
                next_state = (state - {on(block, below), clear(block), handempty()}) | {holding(block), clear(below)}
                result.append((Action(UNSTACK, (block, below)), next_state))
            else:
                next_state = (state - {ontable(block), clear(block), handempty()}) | {holding(block)}
                result.append((Action(PICK_UP, (block,)), next_state))
        return result
    result.append((Action(PUT_DOWN, (held,)), (state - {holding(held)}) | {ontable(held), clear(held), handempty()}))
    for below in clear_blocks:
        next_state = (state - {holding(held), clear(below)}) | {on(held, below), clear(held), handempty()}
        result.append((Action(STACK, (held, below)), next_state))
    return result


# --------------------------------------------------------------------------- #
# Plan parsing
# --------------------------------------------------------------------------- #

_ACTION_PATTERN = re.compile(
    r"\(\s*([A-Za-z][A-Za-z-]*)\s+([A-Za-z][A-Za-z0-9_]*)(?:\s+([A-Za-z][A-Za-z0-9_]*))?\s*\)"
)


class PlanParseError(ValueError):
    """Raised by ``parse_action`` for text that is not one canonical action."""


def parse_action(text: str) -> Action:
    """Parse exactly one canonical action such as ``"(unstack b c)"``.

    Surrounding whitespace is ignored and names are case-insensitive; anything
    else (missing parentheses, commas, extra tokens, unknown names, wrong
    arity) raises ``PlanParseError``.
    """
    match = _ACTION_PATTERN.fullmatch(text.strip())
    if match is None:
        raise PlanParseError(f"not a canonical action: {text.strip()!r}")
    name = match.group(1).lower()
    args = tuple(group.lower() for group in match.groups()[1:] if group is not None)
    if name not in ACTION_ARITY:
        raise PlanParseError(f"unknown action name {name!r} in {text.strip()!r}")
    if len(args) != ACTION_ARITY[name]:
        raise PlanParseError(f"{name} takes {ACTION_ARITY[name]} argument(s): {text.strip()!r}")
    return Action(name, args)


@dataclass(frozen=True)
class ParsedPlan:
    """Result of ``parse_plan``: the actions parsed before the first error."""

    actions: tuple[Action, ...]
    error: str | None = None
    error_position: int | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


def _plan_entries(source: str | Sequence[str]) -> list[str] | str:
    """Split the source into one-action strings, or return an error message."""
    if not isinstance(source, str):
        entries = list(source)
        if not all(isinstance(entry, str) for entry in entries):
            return "plan entries must all be strings"
        return entries
    text = source.strip()
    if text.startswith("["):
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError as error:
            return f"could not decode the JSON list: {error.msg}"
        if not isinstance(decoded, list) or not all(isinstance(entry, str) for entry in decoded):
            return "the JSON list must contain only strings"
        return decoded
    return [line for line in text.splitlines() if line.strip()]


def parse_plan(source: str | Sequence[str]) -> ParsedPlan:
    """Parse a plan given as one action per line, a JSON list, or a list of strings.

    Blank lines are ignored. On the first unparsable entry the result carries
    ``error`` and its 1-based ``error_position`` together with the actions
    parsed before it. An empty source parses to an empty plan.
    """
    entries = _plan_entries(source)
    if isinstance(entries, str):
        return ParsedPlan((), entries, None)
    actions: list[Action] = []
    for position, entry in enumerate(entries, start=1):
        try:
            actions.append(parse_action(entry))
        except PlanParseError as error:
            return ParsedPlan(tuple(actions), str(error), position)
    return ParsedPlan(tuple(actions))


# --------------------------------------------------------------------------- #
# Goals
# --------------------------------------------------------------------------- #


def make_goal(predicates: Iterable[Predicate]) -> Goal:
    """Build a goal from ``on`` / ``ontable`` predicates; other kinds are rejected."""
    goal = frozenset(predicates)
    for predicate in goal:
        if predicate[0] not in GOAL_PREDICATE_NAMES or len(predicate) - 1 != PREDICATE_ARITY[predicate[0]]:
            raise ValueError(f"goal predicates must be on(x,y) or ontable(x); got {predicate_text(predicate)}")
    if not goal:
        raise ValueError("a goal needs at least one predicate")
    return goal


def goal_from_towers(towers: Sequence[Sequence[str]]) -> Goal:
    """A fully specified goal: every block's position in the given towers."""
    return make_goal(predicate for predicate in state_from_towers(towers) if predicate[0] in GOAL_PREDICATE_NAMES)


def goal_violations(goal: Goal, blocks: Iterable[str] | None = None) -> list[str]:
    """Structural problems that make a goal unreachable; empty when the goal is sound.

    Checks unknown blocks (when ``blocks`` is given), a block on itself, two
    positions for one block, two blocks on the same block, and cycles.
    """
    violations: list[str] = []
    known = None if blocks is None else frozenset(blocks)
    below_of: dict[str, str] = {}
    supporters: dict[str, list[str]] = {}
    positions: dict[str, int] = {}
    for predicate in goal:
        for block in predicate[1:]:
            if known is not None and block not in known:
                violations.append(f"unknown block {block} in {predicate_text(predicate)}")
        positions[predicate[1]] = positions.get(predicate[1], 0) + 1
        if predicate[0] == ON:
            if predicate[1] == predicate[2]:
                violations.append(f"block {predicate[1]} cannot be on itself")
            below_of[predicate[1]] = predicate[2]
            supporters.setdefault(predicate[2], []).append(predicate[1])
    for block, count in sorted(positions.items()):
        if count > 1:
            violations.append(f"block {block} is given {count} positions")
    for block, on_top in sorted(supporters.items()):
        if len(on_top) > 1:
            violations.append(f"blocks {sorted(on_top)} cannot all be on {block}")
    for start in sorted(below_of):
        seen: set[str] = set()
        cursor = start
        while cursor in below_of:
            if cursor in seen:
                violations.append(f"cycle through block {start}")
                break
            seen.add(cursor)
            cursor = below_of[cursor]
    return violations


def goal_satisfied_count(state: State, goal: Goal) -> int:
    """Number of goal predicates that hold in the state."""
    return sum(1 for predicate in goal if predicate in state)


def goal_complete(state: State, goal: Goal) -> bool:
    """``True`` when every goal predicate holds in the state."""
    return goal <= state


# --------------------------------------------------------------------------- #
# Instances and generation
# --------------------------------------------------------------------------- #


def make_instance_id(n_blocks: int, seed: int, full_goal: bool = True) -> str:
    """Stable id such as ``bw06_s0017`` (``_partial`` suffix for partial goals)."""
    return f"bw{n_blocks:02d}_s{seed:04d}" + ("" if full_goal else "_partial")


@dataclass(frozen=True)
class Instance:
    """One planning problem: an initial state, a goal, and how it was generated."""

    initial_state: State
    goal: Goal
    n_blocks: int
    seed: int
    instance_id: str = ""

    def __post_init__(self) -> None:
        if not self.instance_id:
            object.__setattr__(self, "instance_id", make_instance_id(self.n_blocks, self.seed))

    @property
    def blocks(self) -> tuple[str, ...]:
        return tuple(sorted(blocks_in_state(self.initial_state)))

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready run record of the instance (predicates as token lists)."""
        return {
            "instance_id": self.instance_id,
            "n_blocks": self.n_blocks,
            "seed": self.seed,
            "initial_state": sorted(list(predicate) for predicate in self.initial_state),
            "goal": sorted(list(predicate) for predicate in self.goal),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Instance":
        return cls(
            initial_state=frozenset(tuple(predicate) for predicate in data["initial_state"]),
            goal=make_goal(tuple(predicate) for predicate in data["goal"]),
            n_blocks=int(data["n_blocks"]),
            seed=int(data["seed"]),
            instance_id=str(data.get("instance_id", "")),
        )


def block_names(n_blocks: int) -> tuple[str, ...]:
    """``a``..``z`` for up to 26 blocks, ``b1``..``bN`` beyond that."""
    if n_blocks <= 26:
        return tuple(chr(ord("a") + index) for index in range(n_blocks))
    return tuple(f"b{index + 1}" for index in range(n_blocks))


def random_towers(blocks: Sequence[str], rng: random.Random) -> list[list[str]]:
    """A random ordered partition of the blocks into non-empty towers."""
    order = list(blocks)
    rng.shuffle(order)
    n_towers = rng.randint(1, len(order))
    cuts = sorted(rng.sample(range(1, len(order)), n_towers - 1))
    bounds = [0, *cuts, len(order)]
    return [order[start:end] for start, end in zip(bounds, bounds[1:])]


def generate_instance(n_blocks: int, rng_seed: int, *, full_goal: bool = True) -> Instance:
    """Deterministically generate one instance from ``(n_blocks, rng_seed)``.

    The initial state is a random tower configuration with the hand empty. The
    goal is a random configuration that differs from the initial one; with
    ``full_goal`` (the default) every block's position is specified, otherwise
    a random proper subset of those predicates is kept, always including at
    least one that the initial state does not already satisfy.
    """
    if n_blocks < MIN_BLOCKS:
        raise ValueError(f"n_blocks must be at least {MIN_BLOCKS}")
    rng = random.Random(rng_seed)
    blocks = block_names(n_blocks)
    initial_state = state_from_towers(random_towers(blocks, rng))
    while True:
        full = goal_from_towers(random_towers(blocks, rng))
        if not goal_complete(initial_state, full):
            break
    if full_goal:
        goal = full
    else:
        unmet = sorted(predicate for predicate in full if predicate not in initial_state)
        size = rng.randint(1, n_blocks - 1)
        chosen = [rng.choice(unmet)]
        pool = sorted(predicate for predicate in full if predicate != chosen[0])
        chosen.extend(rng.sample(pool, size - 1))
        goal = make_goal(chosen)
    return Instance(initial_state, goal, n_blocks, rng_seed, make_instance_id(n_blocks, rng_seed, full_goal))


def generate_instance_set(
    n_blocks_list: Sequence[int],
    per_size: int,
    seed: int,
    *,
    full_goal: bool = True,
) -> list[Instance]:
    """``per_size`` instances for each block count, with stable ids.

    A master generator seeded with ``seed`` draws distinct per-instance seeds
    in ``[0, INSTANCE_SEED_SPACE)`` for each size; each instance is then fully
    determined by ``generate_instance(n_blocks, instance_seed)``.
    """
    if per_size > INSTANCE_SEED_SPACE:
        raise ValueError(f"per_size cannot exceed {INSTANCE_SEED_SPACE}")
    master = random.Random(seed)
    instances: list[Instance] = []
    for n_blocks in n_blocks_list:
        for instance_seed in master.sample(range(INSTANCE_SEED_SPACE), per_size):
            instances.append(generate_instance(n_blocks, instance_seed, full_goal=full_goal))
    return instances


# --------------------------------------------------------------------------- #
# Reference solver and lower bound
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SearchResult:
    """Outcome of ``bfs_optimal_plan``.

    ``plan`` is an optimal action sequence, or ``None`` when the search stopped
    at the expansion cap (``cap_reached``) or exhausted the reachable states
    without meeting the goal (only possible for an unsound goal).
    """

    plan: tuple[Action, ...] | None
    expanded: int
    cap_reached: bool

    @property
    def length(self) -> int | None:
        return None if self.plan is None else len(self.plan)


def bfs_optimal_plan(initial: State, goal: Goal, *, expansion_cap: int = DEFAULT_EXPANSION_CAP) -> SearchResult:
    """Exact breadth-first search for a shortest plan.

    Every state is expanded at most once (visited table). Unit action costs make
    breadth-first order optimal, so the returned plan, when present, has the
    minimum length. ``expansion_cap`` bounds the number of expanded states; for
    six or fewer blocks the whole state space is far below the default cap.
    """
    if goal_complete(initial, goal):
        return SearchResult((), 0, False)
    parents: dict[State, tuple[State, Action] | None] = {initial: None}
    queue: deque[State] = deque([initial])
    expanded = 0
    while queue:
        if expanded >= expansion_cap:
            return SearchResult(None, expanded, True)
        state = queue.popleft()
        expanded += 1
        for action, next_state in successors(state):
            if next_state in parents:
                continue
            parents[next_state] = (state, action)
            if goal_complete(next_state, goal):
                return SearchResult(_reconstruct(parents, next_state), expanded, False)
            queue.append(next_state)
    return SearchResult(None, expanded, False)


def _reconstruct(parents: dict[State, tuple[State, Action] | None], final: State) -> tuple[Action, ...]:
    actions: list[Action] = []
    cursor = final
    while True:
        link = parents[cursor]
        if link is None:
            break
        cursor, action = link
        actions.append(action)
    actions.reverse()
    return tuple(actions)


def optimal_plan_length(initial: State, goal: Goal, *, expansion_cap: int = DEFAULT_EXPANSION_CAP) -> int | None:
    """Exact optimal plan length, or ``None`` when the search hit the cap."""
    return bfs_optimal_plan(initial, goal, expansion_cap=expansion_cap).length


@dataclass(frozen=True)
class MoveCountBound:
    """Lower bounds from the classic "blocks that must move" count.

    ``blocks_to_move`` is a lower bound on the number of block moves; a block
    must move when its goal position differs from its current one, when it is
    held while having a goal position, or when it rests on a block that must
    move. ``actions_lower_bound`` converts moves into 4-operator actions: two
    per block that has to be lifted and placed, one for a held block that only
    has to be placed. Neither number is exact; use ``bfs_optimal_plan`` for that.
    """

    blocks_to_move: int
    actions_lower_bound: int


def move_count_bound(state: State, goal: Goal) -> MoveCountBound:
    """Linear-time lower bound on the remaining plan length (see ``MoveCountBound``)."""
    below_now = {predicate[1]: predicate[2] for predicate in state if predicate[0] == ON}
    table_now = {predicate[1] for predicate in state if predicate[0] == ONTABLE}
    goal_below = {predicate[1]: predicate[2] for predicate in goal if predicate[0] == ON}
    goal_table = {predicate[1] for predicate in goal if predicate[0] == ONTABLE}
    held = held_block(state)
    memo: dict[str, bool] = {}

    def must_move(block: str) -> bool:
        if block in memo:
            return memo[block]
        if block == held:
            result = block in goal_below or block in goal_table
        elif block in goal_below and below_now.get(block) != goal_below[block]:
            result = True
        elif block in goal_table and block not in table_now:
            result = True
        elif block in below_now:
            result = must_move(below_now[block])
        else:
            result = False
        memo[block] = result
        return result

    moving = [block for block in sorted(blocks_in_state(state)) if must_move(block)]
    lifted = sum(1 for block in moving if block != held)
    hand_actions = 0
    if held is not None and (held in moving or lifted > 0):
        hand_actions = 1
    return MoveCountBound(len(moving), 2 * lifted + hand_actions)


# --------------------------------------------------------------------------- #
# Rendering: controlled natural language and PDDL
# --------------------------------------------------------------------------- #


def _list_blocks(blocks: Sequence[str]) -> str:
    if len(blocks) == 1:
        return f"block {blocks[0]}"
    if len(blocks) == 2:
        return f"blocks {blocks[0]} and {blocks[1]}"
    return "blocks " + ", ".join(blocks[:-1]) + f", and {blocks[-1]}"


def render_state_natural_language(state: State) -> str:
    """One sentence per fact, tower by tower, then clear blocks, then the hand."""
    sentences: list[str] = []
    for tower in towers_from_state(state):
        sentences.append(f"Block {tower[0]} is on the table.")
        for below, above in zip(tower, tower[1:]):
            sentences.append(f"Block {above} is on block {below}.")
    clear_blocks = sorted(predicate[1] for predicate in state if predicate[0] == CLEAR)
    if clear_blocks:
        verb = "is" if len(clear_blocks) == 1 else "are"
        listed = _list_blocks(clear_blocks)
        sentences.append(f"{listed[0].upper()}{listed[1:]} {verb} clear.")
    held = held_block(state)
    sentences.append("The hand is empty." if held is None else f"The hand is holding block {held}.")
    return " ".join(sentences)


def render_goal_natural_language(goal: Goal) -> str:
    """One ``must`` sentence per goal predicate, ordered by block name."""
    sentences: list[str] = []
    for predicate in sorted(goal, key=lambda item: (item[1], item[0])):
        if predicate[0] == ON:
            sentences.append(f"Block {predicate[1]} must be on block {predicate[2]}.")
        else:
            sentences.append(f"Block {predicate[1]} must be on the table.")
    return " ".join(sentences)


def render_state_pddl(state: State) -> str:
    """Space-separated PDDL atoms in a stable order."""
    return " ".join(predicate_pddl(predicate) for predicate in sorted(state))


def render_goal_pddl(goal: Goal) -> str:
    """A PDDL ``(and ...)`` goal formula in a stable order."""
    return "(and " + " ".join(predicate_pddl(predicate) for predicate in sorted(goal)) + ")"


def render_problem_pddl(instance: Instance) -> str:
    """A PDDL problem file for ``BLOCKSWORLD_DOMAIN_PDDL`` (for external validators)."""
    return (
        f"(define (problem {instance.instance_id})\n"
        "  (:domain blocksworld-4ops)\n"
        f"  (:objects {' '.join(instance.blocks)})\n"
        f"  (:init {render_state_pddl(instance.initial_state)})\n"
        f"  (:goal {render_goal_pddl(instance.goal)})\n"
        ")\n"
    )
