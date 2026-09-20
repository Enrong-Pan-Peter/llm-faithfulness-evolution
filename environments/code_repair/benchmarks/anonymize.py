"""Rename identifiers so a memorised benchmark program is no longer recognisable by name.

Public benchmarks are solved by recall: given ``def mergesort(arr)`` and a
docstring, a model writes merge sort from memory and the seeded defects never
matter. The anonymised variant of a task removes every hint except the code
and its tests:

* the entry point becomes ``solve``; other functions ``helper_1``,
  ``helper_2``, ... and classes ``Type1``, ... in order of definition;
* every parameter, local, loop or comprehension variable, ``global`` /
  ``nonlocal`` name and ``except ... as`` name becomes ``v1``, ``v2``, ... in
  order of first appearance;
* docstrings are removed (comments disappear with the re-rendering);
* the task prompt states the signature and says that the behaviour is
  defined by the tests alone.

Imported names, attribute names, builtins and keyword names of calls to
library functions are left as they are (keyword arguments of calls to a
renamed function are renamed with its parameters). One mapping is built from
the reference and the seeded program together and applied to both, so the
two stay aligned line by line. The result is checked by ``validate_task`` as
for every other task; a program the renaming breaks (a local that shadows a
builtin used elsewhere, say) is rejected by the build.
"""

from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass, field

ANONYMOUS_ENTRY_POINT = "solve"
ID_SUFFIX = "_anon"
_BUILTINS = frozenset(dir(builtins))


@dataclass
class RenameMap:
    """Old name to new name, plus the parameter names of every renamed function."""

    names: dict[str, str] = field(default_factory=dict)
    function_params: dict[str, set[str]] = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.names)


class _Collector(ast.NodeVisitor):
    """Gather bound names in source order and the names imports bring in."""

    def __init__(self) -> None:
        self.functions: list[str] = []
        self.classes: list[str] = []
        self.variables: list[str] = []
        self.imported: set[str] = set()
        self.params: dict[str, set[str]] = {}
        self._seen: set[str] = set()

    def _variable(self, name: str) -> None:
        if name not in self._seen:
            self._seen.add(name)
            self.variables.append(name)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imported.add((alias.asname or alias.name).split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.imported.add(alias.asname or alias.name)

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if node.name not in self.functions:
            self.functions.append(node.name)
        params = set()
        for arg in _all_args(node.args):
            params.add(arg.arg)
            self._variable(arg.arg)
        self.params.setdefault(node.name, set()).update(params)
        self.generic_visit(node)

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for arg in _all_args(node.args):
            self._variable(arg.arg)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node.name not in self.classes:
            self.classes.append(node.name)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self._variable(node.id)

    def visit_Global(self, node: ast.Global) -> None:
        for name in node.names:
            self._variable(name)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        for name in node.names:
            self._variable(name)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self._variable(node.name)
        self.generic_visit(node)


def _all_args(args: ast.arguments) -> list[ast.arg]:
    found = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
    if args.vararg:
        found.append(args.vararg)
    if args.kwarg:
        found.append(args.kwarg)
    return found


def build_rename_map(sources: list[str], entry_point: str) -> RenameMap:
    """One consistent mapping for all ``sources`` (first source decides the order)."""
    collectors = []
    for source in sources:
        collector = _Collector()
        collector.visit(ast.parse(source))
        collectors.append(collector)
    imported = set().union(*(c.imported for c in collectors))
    mapping = RenameMap()
    functions: list[str] = []
    classes: list[str] = []
    variables: list[str] = []
    for collector in collectors:
        functions += [name for name in collector.functions if name not in functions]
        classes += [name for name in collector.classes if name not in classes]
        variables += [name for name in collector.variables if name not in variables]
    if entry_point not in functions:
        raise ValueError(f"no function named {entry_point!r} to anonymise")
    helper_index = 0
    for name in functions:
        if name in imported:
            continue
        if name == entry_point:
            mapping.names[name] = ANONYMOUS_ENTRY_POINT
        else:
            helper_index += 1
            mapping.names[name] = f"helper_{helper_index}"
    for index, name in enumerate(classes, start=1):
        if name not in imported:
            mapping.names[name] = f"Type{index}"
    variable_index = 0
    for name in variables:
        if name in mapping.names or name in imported or name.startswith("__"):
            continue
        variable_index += 1
        mapping.names[name] = f"v{variable_index}"
    for collector in collectors:
        for function, params in collector.params.items():
            if function in mapping.names:
                mapping.function_params.setdefault(function, set()).update(params)
    return mapping


class _Renamer(ast.NodeTransformer):
    def __init__(self, mapping: RenameMap) -> None:
        self.mapping = mapping

    def _new(self, name: str) -> str:
        return self.mapping.names.get(name, name)

    def _strip_docstring(self, body: list[ast.stmt]) -> list[ast.stmt]:
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body = body[1:]
        return body or [ast.Pass()]

    def visit_Module(self, node: ast.Module) -> ast.Module:
        self.generic_visit(node)
        node.body = self._strip_docstring(node.body)
        return node

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.AST:
        node.name = self._new(node.name)
        self.generic_visit(node)
        node.body = self._strip_docstring(node.body)
        return node

    visit_FunctionDef = _function
    visit_AsyncFunctionDef = _function

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        node.name = self._new(node.name)
        self.generic_visit(node)
        node.body = self._strip_docstring(node.body)
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:
        node.arg = self._new(node.arg)
        self.generic_visit(node)
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        node.id = self._new(node.id)
        return node

    def visit_Global(self, node: ast.Global) -> ast.AST:
        node.names = [self._new(name) for name in node.names]
        return node

    def visit_Nonlocal(self, node: ast.Nonlocal) -> ast.AST:
        node.names = [self._new(name) for name in node.names]
        return node

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> ast.AST:
        if node.name:
            node.name = self._new(node.name)
        self.generic_visit(node)
        return node

    def visit_Call(self, node: ast.Call) -> ast.AST:
        callee = node.func.id if isinstance(node.func, ast.Name) else None
        params = self.mapping.function_params.get(callee, set()) if callee else set()
        for keyword in node.keywords:
            if keyword.arg and keyword.arg in params:
                keyword.arg = self._new(keyword.arg)
        self.generic_visit(node)
        return node


def apply_rename_map(source: str, mapping: RenameMap) -> str:
    """Re-render ``source`` with the mapping applied and docstrings removed."""
    tree = _Renamer(mapping).visit(ast.parse(source))
    ast.fix_missing_locations(tree)
    return ast.unparse(tree) + "\n"


def anonymize_programs(reference: str, seeded: str, entry_point: str) -> tuple[str, str, RenameMap]:
    """Rename both programs with one mapping; returns (reference, seeded, mapping)."""
    mapping = build_rename_map([reference, seeded], entry_point)
    return apply_rename_map(reference, mapping), apply_rename_map(seeded, mapping), mapping


def anonymous_signature(source: str, entry_point: str = ANONYMOUS_ENTRY_POINT) -> str:
    """The ``def solve(...)`` line of the renamed program (annotations kept)."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == entry_point:
            returns = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            return f"def {entry_point}({ast.unparse(node.args)}){returns}:"
    raise ValueError(f"no function named {entry_point!r}")


def anonymous_prompt(signature: str) -> str:
    """Task text for a renamed program: signature only, behaviour defined by the tests."""
    return (
        "Repair the function below.\n\n"
        f"{signature}\n"
        "    ...\n\n"
        "There is no written specification. The intended behaviour of the function is "
        "defined by its tests alone: the development tests shown with each program are "
        "examples of it, and the hidden tests check the same behaviour on other inputs. "
        "Keep the function name and signature.\n"
    )
