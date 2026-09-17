"""Extra defects for benchmark programs (mutation operators on the syntax tree).

A public benchmark task with one defect is memorised by current models: the
pilot showed qwen3:14b repairing 23 of 28 QuixBugs programs in every direct
attempt. Injecting ``k`` further defects with the classic mutation-testing
operators makes the repair a search problem again while the specification,
the tests and the reference stay those of the benchmark. Operators:

* comparison swap (``<`` <-> ``<=``, ``>`` <-> ``>=``, ``==`` <-> ``!=``);
* arithmetic swap (``+`` <-> ``-``, ``*`` <-> ``//``, ``%`` -> ``//``);
* boolean swap (``and`` <-> ``or``), negation removed (``not x`` -> ``x``);
* off-by-one on a small integer constant (``n`` -> ``n + 1``);
* off-by-one on an index (``a[i]`` -> ``a[i + 1]`` when the index is a name);
* ``break`` <-> ``continue``.

Each single mutation is kept only if it is *killed* by the task's tests when
applied alone to the reference (the program still loads and fails at least
one development or hidden test), and the combined program must load and fail
at least one development test. The mutated program is re-rendered from the
syntax tree (``ast.unparse``), so its formatting is normalised.
"""

from __future__ import annotations

import ast
import copy
import random
from dataclasses import dataclass
from typing import Any, Sequence

from ..runner import DEFAULT_MEMORY_MB, DEFAULT_TIMEOUT_S, TestCase, run_tests

COMPARE_SWAPS: dict[type, type] = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}
BINOP_SWAPS: dict[type, type] = {ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.FloorDiv, ast.FloorDiv: ast.Mult, ast.Mod: ast.FloorDiv}
BOOL_SWAPS: dict[type, type] = {ast.And: ast.Or, ast.Or: ast.And}


@dataclass(frozen=True)
class Site:
    index: int  # position in pre-order traversal
    kind: str
    description: str


def _preorder(tree: ast.AST) -> list[ast.AST]:
    nodes: list[ast.AST] = []

    def visit(node: ast.AST) -> None:
        nodes.append(node)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return nodes


def mutation_sites(source: str) -> list[Site]:
    """Every place one of the operators applies, in a stable order."""
    tree = ast.parse(source)
    sites: list[Site] = []
    for index, node in enumerate(_preorder(tree)):
        line = getattr(node, "lineno", "?")
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in COMPARE_SWAPS:
            sites.append(Site(index, "compare", f"line {line}: comparison {type(node.ops[0]).__name__} -> {COMPARE_SWAPS[type(node.ops[0])].__name__}"))
        elif isinstance(node, ast.BinOp) and type(node.op) in BINOP_SWAPS:
            sites.append(Site(index, "binop", f"line {line}: operator {type(node.op).__name__} -> {BINOP_SWAPS[type(node.op)].__name__}"))
        elif isinstance(node, ast.BoolOp) and type(node.op) in BOOL_SWAPS:
            sites.append(Site(index, "boolop", f"line {line}: {type(node.op).__name__} -> {BOOL_SWAPS[type(node.op)].__name__}"))
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            sites.append(Site(index, "drop_not", f"line {line}: 'not' removed"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool) and abs(node.value) <= 100:
            sites.append(Site(index, "constant", f"line {line}: constant {node.value} changed by one"))
        elif isinstance(node, ast.Break):
            sites.append(Site(index, "break", f"line {line}: break -> continue"))
        elif isinstance(node, ast.Continue):
            sites.append(Site(index, "continue", f"line {line}: continue -> break"))
        elif isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Name) and isinstance(node.ctx, ast.Load):
            sites.append(Site(index, "index", f"line {line}: index {node.slice.id} shifted by one"))
    return sites


class _Mutator(ast.NodeTransformer):
    def __init__(self, targets: dict[int, str]) -> None:
        self.targets = targets
        self.counter = -1
        self.applied: list[int] = []

    def visit(self, node: ast.AST) -> Any:
        self.counter += 1
        index = self.counter
        kind = self.targets.get(index)
        # children first would change the numbering; number in pre-order like the site scan
        replacement = self._mutate(node, kind) if kind else node
        if kind:
            self.applied.append(index)
        if replacement is node:
            return self.generic_visit(node)
        # visit the children of the replacement while keeping the pre-order count of the original subtree
        self.generic_visit(node)
        return replacement

    def _mutate(self, node: ast.AST, kind: str) -> ast.AST:
        if kind == "compare" and isinstance(node, ast.Compare):
            node.ops = [COMPARE_SWAPS[type(node.ops[0])]()]
        elif kind == "binop" and isinstance(node, ast.BinOp):
            node.op = BINOP_SWAPS[type(node.op)]()
        elif kind == "boolop" and isinstance(node, ast.BoolOp):
            node.op = BOOL_SWAPS[type(node.op)]()
        elif kind == "drop_not" and isinstance(node, ast.UnaryOp):
            return ast.copy_location(node.operand, node)
        elif kind == "constant" and isinstance(node, ast.Constant):
            node.value = node.value + 1
        elif kind == "break":
            return ast.copy_location(ast.Continue(), node)
        elif kind == "continue":
            return ast.copy_location(ast.Break(), node)
        elif kind == "index" and isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Name):
            node.slice = ast.copy_location(ast.BinOp(left=node.slice, op=ast.Add(), right=ast.Constant(value=1)), node.slice)
        return node


def apply_mutations(source: str, sites: Sequence[Site]) -> str:
    """Return ``source`` with the mutations of ``sites`` applied (re-rendered)."""
    tree = ast.parse(source)
    mutator = _Mutator({site.index: site.kind for site in sites})
    tree = mutator.visit(tree)
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def _killed(program: str, entry_point: str, tests: Sequence[TestCase], tolerance: float, timeout_s: float, memory_mb: int | None) -> bool:
    """True when the program loads and fails at least one test."""
    result = run_tests(program, entry_point, tests, timeout_s, memory_mb, float_tolerance=tolerance)
    return result.compile_ok and result.passed < result.total


def inject_defects(
    reference: str,
    seeded: str,
    entry_point: str,
    dev_tests: Sequence[TestCase],
    hidden_tests: Sequence[TestCase],
    k: int,
    rng: random.Random,
    *,
    float_tolerance: float = 0.0,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    memory_mb: int | None = DEFAULT_MEMORY_MB,
    max_tries: int = 60,
) -> tuple[str, list[str]] | None:
    """``k`` extra defects on top of ``seeded``; ``None`` when no valid combination was found.

    Candidate sites are drawn from the seeded program; a site is accepted when
    the same mutation applied alone to the reference is killed by the tests,
    and the accumulated program still loads and fails at least one development
    test. Returns the mutated program and the descriptions of the mutations.
    """
    all_tests = list(dev_tests) + list(hidden_tests)
    sites = mutation_sites(seeded)
    rng.shuffle(sites)
    chosen: list[Site] = []
    current = seeded
    tries = 0
    for site in sites:
        if len(chosen) == k or tries >= max_tries:
            break
        tries += 1
        reference_sites = mutation_sites(reference)
        # the same operator at the same pre-order index only makes sense when both programs share it
        matching = [s for s in reference_sites if s.index == site.index and s.kind == site.kind]
        if matching and not _killed(apply_mutations(reference, matching), entry_point, all_tests, float_tolerance, timeout_s, memory_mb):
            continue
        candidate = apply_mutations(seeded, chosen + [site])
        if candidate == current:
            continue
        result = run_tests(candidate, entry_point, list(dev_tests), timeout_s, memory_mb, float_tolerance=float_tolerance)
        if not result.compile_ok or result.passed == result.total:
            continue
        chosen.append(site)
        current = candidate
    if len(chosen) < k:
        return None
    return current, [site.description for site in chosen]
