"""Symbolic deletion-contraction calculation for Graph Drawer.

The UI layer uses this module as a small, self-contained engine.  It keeps no
Tkinter state: graph states, recursion steps, and polynomial arithmetic are all
plain Python objects so the algorithm can be tested or reused independently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import re


VARIABLE_ORDER = ("a", "b", "h")


class SymbolicComputationLimit(Exception):
    """Raised when the recursion tree is too large for interactive display."""


class Polynomial:
    """Sparse polynomial in a, b and h with integer coefficients.

    Terms are stored as {(a_exp, b_exp, h_exp): coefficient}.  The
    deletion-contraction recurrence only creates non-negative exponents and
    integer coefficients, so this compact representation is enough and avoids a
    heavyweight symbolic dependency.
    """

    def __init__(self, terms=None):
        self.terms = {}
        for powers, coefficient in (terms or {}).items():
            coefficient = int(coefficient)
            if coefficient:
                self.terms[tuple(int(power) for power in powers)] = coefficient

    @classmethod
    def zero(cls):
        return cls()

    @classmethod
    def h_power(cls, exponent):
        return cls({(0, 0, max(0, int(exponent))): 1})

    def add(self, other):
        terms = dict(self.terms)
        for powers, coefficient in other.terms.items():
            terms[powers] = terms.get(powers, 0) + coefficient
            if terms[powers] == 0:
                del terms[powers]
        return Polynomial(terms)

    def multiply_symbol(self, symbol):
        index = VARIABLE_ORDER.index(symbol)
        terms = {}
        for powers, coefficient in self.terms.items():
            next_powers = list(powers)
            next_powers[index] += 1
            terms[tuple(next_powers)] = terms.get(tuple(next_powers), 0) + coefficient
        return Polynomial(terms)

    def is_zero(self):
        return not self.terms

    def short_string(self, max_len=72):
        text = str(self)
        return text if len(text) <= max_len else text[: max_len - 1] + "…"

    def sympy_string(self):
        """Return a string that can be parsed by sympy.sympify.

        The display form intentionally omits multiplication signs, but SymPy
        needs explicit operators such as ``a*h**2``.
        """

        if not self.terms:
            return "0"
        parts = []
        for powers, coefficient in self._sorted_terms():
            monomial = _format_sympy_monomial(powers)
            if monomial:
                if coefficient == 1:
                    parts.append(monomial)
                elif coefficient == -1:
                    parts.append("-" + monomial)
                else:
                    parts.append(f"{coefficient}*{monomial}")
            else:
                parts.append(str(coefficient))
        return _join_signed(parts)

    def substitute(self, substitutions):
        """Substitute values for a, b, h and simplify what can be combined.

        Empty substitutions keep the original variable.  Numeric values are
        evaluated exactly with Fraction.  Symbol names and expression strings are
        treated as symbolic atoms; identical atoms are combined.
        """

        parsed = {
            name: _parse_substitution(substitutions.get(name, ""), name)
            for name in VARIABLE_ORDER
        }
        terms = {}
        for powers, coefficient in self.terms.items():
            coeff = Fraction(coefficient, 1)
            symbolic_powers = {}
            for name, exponent in zip(VARIABLE_ORDER, powers):
                kind, value = parsed[name]
                if exponent == 0:
                    continue
                if kind == "number":
                    coeff *= value ** exponent
                else:
                    symbolic_powers[value] = symbolic_powers.get(value, 0) + exponent

            key = tuple(sorted(symbolic_powers.items()))
            terms[key] = terms.get(key, Fraction(0, 1)) + coeff
            if terms[key] == 0:
                del terms[key]

        return _format_general_terms(terms)

    def __str__(self):
        if not self.terms:
            return "0"
        parts = []
        for powers, coefficient in self._sorted_terms():
            monomial = _format_monomial(powers)
            if monomial:
                if coefficient == 1:
                    parts.append(monomial)
                elif coefficient == -1:
                    parts.append("-" + monomial)
                else:
                    parts.append(f"{coefficient}{monomial}")
            else:
                parts.append(str(coefficient))
        return _join_signed(parts)

    def _sorted_terms(self):
        return sorted(
            self.terms.items(),
            key=lambda item: (-sum(item[0]), -item[0][0], -item[0][1], -item[0][2]),
        )


@dataclass(frozen=True)
class SymbolicVertex:
    id: int
    label: str
    x: float
    y: float
    members: tuple = field(default_factory=tuple)


@dataclass(frozen=True)
class SymbolicEdge:
    id: int
    source: int
    target: int
    label: str


@dataclass(frozen=True)
class SymbolicGraph:
    vertices: tuple
    edges: tuple

    def edge_by_id(self, edge_id):
        return next(edge for edge in self.edges if edge.id == edge_id)

    def vertex_by_id(self, vertex_id):
        return next(vertex for vertex in self.vertices if vertex.id == vertex_id)

    def delete_edge(self, edge_id):
        return SymbolicGraph(
            vertices=self.vertices,
            edges=tuple(edge for edge in self.edges if edge.id != edge_id),
        )

    def contract_edge(self, edge_id):
        edge = self.edge_by_id(edge_id)
        if edge.source == edge.target:
            return self.delete_edge(edge_id)

        source = self.vertex_by_id(edge.source)
        target = self.vertex_by_id(edge.target)
        source_weight = max(1, len(source.members))
        target_weight = max(1, len(target.members))
        total_weight = source_weight + target_weight
        members = tuple(sorted(source.members + target.members, key=str))
        merged = SymbolicVertex(
            id=source.id,
            label=_merged_label(members),
            x=(source.x * source_weight + target.x * target_weight) / total_weight,
            y=(source.y * source_weight + target.y * target_weight) / total_weight,
            members=members,
        )

        vertices = []
        for vertex in self.vertices:
            if vertex.id == target.id:
                continue
            vertices.append(merged if vertex.id == source.id else vertex)

        edges = []
        for candidate in self.edges:
            if candidate.id == edge_id:
                continue
            next_source = source.id if candidate.source == target.id else candidate.source
            next_target = source.id if candidate.target == target.id else candidate.target
            edges.append(
                SymbolicEdge(
                    id=candidate.id,
                    source=next_source,
                    target=next_target,
                    label=candidate.label,
                )
            )
        return SymbolicGraph(vertices=tuple(vertices), edges=tuple(edges))

    def canonical_key(self):
        """Canonical key for optional memoization, preserving multi-edges."""

        vertex_ids = sorted(vertex.id for vertex in self.vertices)
        index_by_id = {vertex_id: index for index, vertex_id in enumerate(vertex_ids)}
        edge_pairs = []
        for edge in self.edges:
            source = index_by_id[edge.source]
            target = index_by_id[edge.target]
            edge_pairs.append(tuple(sorted((source, target))))
        return len(vertex_ids), tuple(sorted(edge_pairs))


@dataclass
class SymbolicStep:
    id: int
    depth: int
    graph: SymbolicGraph
    polynomial: Polynomial
    edge: SymbolicEdge | None = None
    deleted_graph: SymbolicGraph | None = None
    contracted_graph: SymbolicGraph | None = None
    deleted_polynomial: Polynomial | None = None
    contracted_polynomial: Polynomial | None = None
    delete_child: "SymbolicStep | None" = None
    contract_child: "SymbolicStep | None" = None
    base_case: bool = False
    memo_hit: bool = False


@dataclass
class SymbolicResult:
    root: SymbolicStep
    polynomial: Polynomial
    steps: list


class DeletionContractionCalculator:
    """Build the full deletion-contraction step tree for a graph."""

    def __init__(self, max_steps=12000, use_memo=False):
        self.max_steps = int(max_steps)
        self.use_memo = bool(use_memo)
        self._next_step_id = 1
        self._allocated_steps = 0
        self._steps = []
        self._memo = {}

    def calculate(self, graph):
        self._next_step_id = 1
        self._allocated_steps = 0
        self._steps = []
        self._memo = {}
        root = self._compute(graph, depth=0)
        return SymbolicResult(root=root, polynomial=root.polynomial, steps=self._steps)

    def _compute(self, graph, depth):
        if self._allocated_steps >= self.max_steps:
            raise SymbolicComputationLimit(
                f"递归步骤超过 {self.max_steps} 步，建议先减少边数或开启更小的图再计算。"
            )

        key = graph.canonical_key()
        if self.use_memo and key in self._memo:
            polynomial = self._memo[key]
            step = self._new_step(depth, graph, polynomial, memo_hit=True)
            return step

        if not graph.edges:
            polynomial = Polynomial.h_power(len(graph.vertices))
            step = self._new_step(depth, graph, polynomial, base_case=True)
            if self.use_memo:
                self._memo[key] = polynomial
            return step

        step_id = self._reserve_step_id()
        edge = self._choose_edge(graph)
        deleted_graph = graph.delete_edge(edge.id)
        contracted_graph = graph.contract_edge(edge.id)
        delete_child = self._compute(deleted_graph, depth + 1)
        contract_child = self._compute(contracted_graph, depth + 1)
        polynomial = (
            delete_child.polynomial.multiply_symbol("a")
            .add(contract_child.polynomial.multiply_symbol("b"))
        )
        step = self._new_step(
            depth,
            graph,
            polynomial,
            step_id=step_id,
            edge=edge,
            deleted_graph=deleted_graph,
            contracted_graph=contracted_graph,
            deleted_polynomial=delete_child.polynomial,
            contracted_polynomial=contract_child.polynomial,
            delete_child=delete_child,
            contract_child=contract_child,
        )
        if self.use_memo:
            self._memo[key] = polynomial
        return step

    def _choose_edge(self, graph):
        return sorted(graph.edges, key=lambda edge: (edge.id, edge.label))[0]

    def _reserve_step_id(self):
        step_id = self._next_step_id
        self._next_step_id += 1
        self._allocated_steps += 1
        return step_id

    def _new_step(self, depth, graph, polynomial, step_id=None, **kwargs):
        if step_id is None:
            step_id = self._reserve_step_id()
        step = SymbolicStep(
            id=step_id,
            depth=depth,
            graph=graph,
            polynomial=polynomial,
            **kwargs,
        )
        self._steps.append(step)
        return step


def _format_monomial(powers):
    pieces = []
    for name, exponent in zip(VARIABLE_ORDER, powers):
        if exponent == 0:
            continue
        pieces.append(name if exponent == 1 else f"{name}^{exponent}")
    return "".join(pieces)


def _format_sympy_monomial(powers):
    pieces = []
    for name, exponent in zip(VARIABLE_ORDER, powers):
        if exponent == 0:
            continue
        pieces.append(name if exponent == 1 else f"{name}**{exponent}")
    return "*".join(pieces)


def _join_signed(parts):
    if not parts:
        return "0"
    text = parts[0]
    for part in parts[1:]:
        if part.startswith("-"):
            text += " - " + part[1:]
        else:
            text += " + " + part
    return text


def _parse_substitution(value, default_name):
    value = str(value).strip()
    if not value:
        return "symbol", default_name
    try:
        return "number", Fraction(value)
    except ValueError:
        return "symbol", _symbol_atom(value)


def _symbol_atom(value):
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", value):
        return value
    if value.startswith("(") and value.endswith(")"):
        return value
    return f"({value})"


def _format_general_terms(terms):
    if not terms:
        return "0"
    parts = []
    for powers, coefficient in sorted(
        terms.items(),
        key=lambda item: (-sum(power for _, power in item[0]), item[0]),
    ):
        monomial = _format_general_monomial(powers)
        coefficient_text = _format_fraction(coefficient)
        if monomial:
            if coefficient == 1:
                parts.append(monomial)
            elif coefficient == -1:
                parts.append("-" + monomial)
            else:
                parts.append(f"{coefficient_text}{monomial}")
        else:
            parts.append(coefficient_text)
    return _join_signed(parts)


def _format_general_monomial(powers):
    pieces = []
    for atom, exponent in powers:
        pieces.append(atom if exponent == 1 else f"{atom}^{exponent}")
    return "".join(pieces)


def _format_fraction(value):
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _merged_label(members):
    if len(members) == 1:
        return str(members[0])
    return "{" + ",".join(str(member) for member in members) + "}"
