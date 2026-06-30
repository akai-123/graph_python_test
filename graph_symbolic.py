"""Symbolic edge-operation calculation for Graph Drawer.

This module is intentionally independent from Tkinter.  The UI gives it a
plain graph, and the calculator returns a recursion tree plus a polynomial.

The symbolic process is configured in named groups in
``graph_symbolic_config.py``:

    SymbolicCalculationConfig
        A named package of initial values and recursion flows.

    DEFAULT_INITIAL_VALUE_RULES
        Graph shapes that should stop recursion and return a fixed polynomial.

    DEFAULT_EDGE_OPERATIONS
        Reusable polynomial terms such as ``a * f(G - e)``.

    DEFAULT_CALCULATION_FLOWS
        Ordered cases that decide which operations are used for a graph/edge.

    f(G) = sum(operation.coefficient * f(operation.apply(G, e)))

Predicates and graph transforms used by those rules live in
``graph_symbolic_tools.py``.

The default flow is still deletion and contraction:

    f(G) = a f(G - e) + b f(G / e)

When there are no edges, the base value is ``h ** number_of_vertices``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import re
from typing import Callable


VARIABLE_ORDER = ("a", "b", "h")

__all__ = (
    "VARIABLE_ORDER",
    "SymbolicComputationLimit",
    "Polynomial",
    "SymbolicVertex",
    "SymbolicEdge",
    "SymbolicGraph",
    "InitialValueRule",
    "EdgeOperation",
    "CalculationFlow",
    "SymbolicCalculationConfig",
    "OperationBranch",
    "SymbolicStep",
    "SymbolicResult",
    "DeletionContractionCalculator",
    "DEFAULT_SYMBOLIC_CONFIG",
    "SYMBOLIC_CONFIGS",
    "DEFAULT_INITIAL_VALUE_RULES",
    "DEFAULT_EDGE_OPERATIONS",
    "DEFAULT_CALCULATION_FLOWS",
)


class SymbolicComputationLimit(Exception):
    """Raised when the recursion tree is too large for interactive display."""


class Polynomial:
    """Sparse polynomial in the variables listed in ``VARIABLE_ORDER``.

    Terms are stored as ``{(a_exp, b_exp, h_exp): coefficient}``.  The current
    recurrence only creates non-negative exponents and integer coefficients, so
    this small representation is easier to edit than pulling in a symbolic
    algebra dependency.
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
    def constant(cls, coefficient):
        return cls({(0, 0, 0): int(coefficient)})

    @classmethod
    def one(cls):
        return cls.constant(1)

    @classmethod
    def symbol(cls, symbol):
        return cls.one().multiply_symbol(symbol)

    @classmethod
    def monomial(cls, coefficient=1, **exponents):
        """Build a single-term polynomial, for example ``2*a*h``.

        Use it in an operation coefficient like this:

            coefficient=Polynomial.monomial(2, a=1, h=1)
        """

        powers = [0] * len(VARIABLE_ORDER)
        for name, exponent in exponents.items():
            if name not in VARIABLE_ORDER:
                raise ValueError(
                    f"Unknown symbolic variable {name!r}; add it to VARIABLE_ORDER first."
                )
            powers[VARIABLE_ORDER.index(name)] = int(exponent)
        return cls({tuple(powers): int(coefficient)})

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

    def multiply(self, other):
        """Multiply two sparse polynomials."""

        terms = {}
        for left_powers, left_coefficient in self.terms.items():
            for right_powers, right_coefficient in other.terms.items():
                powers = tuple(
                    left_power + right_power
                    for left_power, right_power in zip(left_powers, right_powers)
                )
                terms[powers] = terms.get(powers, 0) + (
                    left_coefficient * right_coefficient
                )
                if terms[powers] == 0:
                    del terms[powers]
        return Polynomial(terms)

    def multiply_symbol(self, symbol):
        """Multiply by one variable such as ``a``, ``b`` or ``h``."""

        if symbol not in VARIABLE_ORDER:
            raise ValueError(
                f"Unknown symbolic variable {symbol!r}; add it to VARIABLE_ORDER first."
            )

        index = VARIABLE_ORDER.index(symbol)
        terms = {}
        for powers, coefficient in self.terms.items():
            next_powers = list(powers)
            next_powers[index] += 1
            next_powers = tuple(next_powers)
            terms[next_powers] = terms.get(next_powers, 0) + coefficient
        return Polynomial(terms)

    def multiply_optional_symbol(self, symbol):
        """Multiply by ``symbol`` unless it represents coefficient 1."""

        if symbol in (None, "", "1"):
            return self
        return self.multiply(_as_polynomial(symbol))

    def is_zero(self):
        return not self.terms

    def short_string(self, max_len=72):
        text = str(self)
        return text if len(text) <= max_len else text[: max_len - 3] + "..."

    def sympy_string(self):
        """Return a string that can be parsed by ``sympy.sympify``.

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
        evaluated exactly with ``Fraction``.  Symbol names and expression
        strings are treated as symbolic atoms; identical atoms are combined.
        """

        substitutions = substitutions or {}
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
    """Immutable graph snapshot used by the symbolic recurrence."""

    vertices: tuple
    edges: tuple

    def edge_by_id(self, edge_id):
        return next(edge for edge in self.edges if edge.id == edge_id)

    def vertex_by_id(self, vertex_id):
        return next(vertex for vertex in self.vertices if vertex.id == vertex_id)

    def without_edge(self, edge_id):
        """Return ``G - e``: only the selected edge is removed."""

        return SymbolicGraph(
            vertices=self.vertices,
            edges=tuple(edge for edge in self.edges if edge.id != edge_id),
        )

    def delete_edge(self, edge_id):
        """Compatibility alias used by older callers."""

        return self.without_edge(edge_id)

    def with_contracted_edge(self, edge_id):
        """Return ``G / e``.

        The selected edge is removed.  Its endpoints are merged into the source
        vertex, and every edge that pointed at the target is rewired to the
        source.  Other parallel edges are preserved; an edge between the two
        endpoints naturally becomes a loop after the merge.
        """

        edge = self.edge_by_id(edge_id)
        if edge.source == edge.target:
            return self.without_edge(edge_id)

        source = self.vertex_by_id(edge.source)
        target = self.vertex_by_id(edge.target)
        source_members = source.members or (source.label,)
        target_members = target.members or (target.label,)
        source_weight = max(1, len(source_members))
        target_weight = max(1, len(target_members))
        total_weight = source_weight + target_weight
        members = tuple(sorted(source_members + target_members, key=str))
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

    def contract_edge(self, edge_id):
        """Compatibility alias used by older callers."""

        return self.with_contracted_edge(edge_id)

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


GraphTransform = Callable[[SymbolicGraph, SymbolicEdge], SymbolicGraph]
GraphPredicate = Callable[[SymbolicGraph], bool]
EdgePredicate = Callable[[SymbolicGraph, SymbolicEdge], bool]


@dataclass(frozen=True)
class InitialValueRule:
    """A graph shape that stops recursion and returns an initial value.

    ``when`` decides whether the rule matches the current graph.  Rules should
    describe different graph shapes.  The calculator checks this at runtime: if
    two initial rules match the same graph, it raises ``ValueError`` instead of
    silently choosing one.
    """

    key: str
    title: str
    when: GraphPredicate
    value: object
    shape_key: object | None = None
    description: str = ""

    def matches(self, graph):
        return bool(self.when(graph))

    def polynomial(self, graph):
        value = self.value(graph) if callable(self.value) else self.value
        return _as_polynomial(value)


@dataclass(frozen=True)
class EdgeOperation:
    """One reusable polynomial calculation in an edge recurrence.

    ``transform`` describes how vertices and edges change when the operation is
    applied to the chosen edge.  ``coefficient`` describes how the child value is
    multiplied before it contributes to the parent value.

    Example:
        delete:   graph -> G - e, coefficient -> a
        contract: graph -> G / e, coefficient -> b

    ``coefficient`` is normalized to ``Polynomial`` before multiplication.
    Supported forms:

        None, "", "1"               coefficient 1
        0, 1, 2, -1                 integer constants
        "0", "2", "-1"              integer constants written as strings
        "a", "b", "h"               one variable from VARIABLE_ORDER
        Polynomial.symbol("a")      one variable as a Polynomial
        Polynomial.monomial(...)    one custom monomial
        Polynomial(...).add(...)    a custom multi-term polynomial
        lambda graph, edge: ...     dynamic coefficient, returning any form above

    Strings are intentionally simple: "a+b" or "2a" are not parsed. Use
    ``Polynomial`` helpers when the coefficient is more than one variable or
    one integer constant.

    Each operation must make progress, normally by removing the chosen edge, or
    the recursive calculator will eventually hit ``max_steps``.
    """

    key: str
    title: str
    coefficient: object
    transform: GraphTransform
    description: str = ""

    def apply(self, graph, edge):
        return self.transform(graph, edge)

    def coefficient_polynomial(self, graph, edge):
        value = self.coefficient(graph, edge) if callable(self.coefficient) else self.coefficient
        return _as_polynomial(value)

    def contribution(self, polynomial, graph, edge):
        return polynomial.multiply(self.coefficient_polynomial(graph, edge))

    def formula_text(self, polynomial_text, coefficient=None):
        coefficient_text = _coefficient_text(
            coefficient if coefficient is not None else self.coefficient
        )
        if coefficient_text == "1":
            return f"({polynomial_text})"
        return f"{coefficient_text}({polynomial_text})"


@dataclass(frozen=True)
class CalculationFlow:
    """A case that decides which polynomial calculations to run.

    Flows are tested in order.  The first matching flow supplies the operations
    for the current graph and chosen edge.  This supports rules like:

        normal edge: delete + contract
        special edge: contract only
    """

    key: str
    title: str
    when: EdgePredicate
    operations: tuple
    description: str = ""

    def matches(self, graph, edge):
        return bool(self.when(graph, edge))


@dataclass(frozen=True)
class SymbolicCalculationConfig:
    """A named group of symbolic calculation rules.

    A config packages the parts that actually select behavior: initial values
    and recursion flows. Edge operations are referenced by flows, so they are
    exposed only as a derived compatibility property.
    """

    key: str
    title: str
    initial_value_rules: tuple
    calculation_flows: tuple
    description: str = ""

    @property
    def edge_operations(self):
        """Derived operation list for old callers and quick inspection."""

        operations = []
        seen = set()
        for flow in self.calculation_flows:
            for operation in flow.operations:
                if operation.key in seen:
                    continue
                operations.append(operation)
                seen.add(operation.key)
        return tuple(operations)


@dataclass(frozen=True)
class OperationBranch:
    """A realized operation branch for one recursion step."""

    operation: EdgeOperation
    coefficient: Polynomial
    graph: SymbolicGraph
    polynomial: Polynomial
    child: "SymbolicStep"

    @property
    def weighted_polynomial(self):
        return self.polynomial.multiply(self.coefficient)


@dataclass
class SymbolicStep:
    id: int
    depth: int
    graph: SymbolicGraph
    polynomial: Polynomial
    edge: SymbolicEdge | None = None
    initial_rule: InitialValueRule | None = None
    flow: CalculationFlow | None = None
    branches: tuple = field(default_factory=tuple)
    base_case: bool = False
    memo_hit: bool = False

    def branch_for(self, operation_key):
        for branch in self.branches:
            if branch.operation.key == operation_key:
                return branch
        return None

    def _branch_attr(self, operation_key, attribute):
        branch = self.branch_for(operation_key)
        return getattr(branch, attribute) if branch is not None else None

    # Compatibility properties for the existing UI.  New code can use
    # ``branches`` and ``branch_for`` directly.
    @property
    def deleted_graph(self):
        return self._branch_attr("delete", "graph")

    @property
    def contracted_graph(self):
        return self._branch_attr("contract", "graph")

    @property
    def deleted_polynomial(self):
        return self._branch_attr("delete", "polynomial")

    @property
    def contracted_polynomial(self):
        return self._branch_attr("contract", "polynomial")

    @property
    def delete_child(self):
        return self._branch_attr("delete", "child")

    @property
    def contract_child(self):
        return self._branch_attr("contract", "child")


@dataclass
class SymbolicResult:
    root: SymbolicStep
    polynomial: Polynomial
    steps: list


class DeletionContractionCalculator:
    """Build the full configured symbolic recursion tree for a graph."""

    def __init__(
        self,
        max_steps=120000,
        use_memo=False,
        config=None,
        config_key=None,
        edge_operations=None,
        initial_value_rules=None,
        calculation_flows=None,
    ):
        self.max_steps = int(max_steps)
        self.use_memo = bool(use_memo)
        selected_config = _resolve_symbolic_config(config=config, config_key=config_key)
        self.config = selected_config
        self.initial_value_rules = tuple(
            initial_value_rules or selected_config.initial_value_rules
        )

        if edge_operations is not None and calculation_flows is not None:
            raise ValueError("Use either edge_operations or calculation_flows, not both.")
        if calculation_flows is not None:
            self.calculation_flows = tuple(calculation_flows)
        elif edge_operations is not None:
            from graph_symbolic_tools import always_use_flow

            self.calculation_flows = (
                CalculationFlow(
                    key="custom_edge_operations",
                    title="Custom edge operations",
                    when=always_use_flow,
                    operations=tuple(edge_operations),
                    description="Compatibility wrapper for edge_operations.",
                ),
            )
        else:
            self.calculation_flows = selected_config.calculation_flows

        self.edge_operations = tuple(
            operation
            for flow in self.calculation_flows
            for operation in flow.operations
        )
        self._validate_configuration()

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
                f"Recursion exceeded {self.max_steps} steps. "
                "Try fewer edges or enable memoization for exploratory use."
            )

        initial_rule = self._initial_rule_for(graph)
        if initial_rule is not None:
            polynomial = initial_rule.polynomial(graph)
            step = self._new_step(
                depth,
                graph,
                polynomial,
                initial_rule=initial_rule,
                base_case=True,
            )
            if self.use_memo:
                self._memo[graph.canonical_key()] = polynomial
            return step

        key = graph.canonical_key()
        if self.use_memo and key in self._memo:
            polynomial = self._memo[key]
            return self._new_step(depth, graph, polynomial, memo_hit=True)

        if not graph.edges:
            raise ValueError(
                "No initial value rule matched an edgeless graph. "
                "Add an InitialValueRule for this terminal shape."
            )

        step_id = self._reserve_step_id()
        edge = self._choose_edge(graph)
        flow = self._flow_for(graph, edge)
        branches = []
        polynomial = Polynomial.zero()

        for operation in flow.operations:
            coefficient = operation.coefficient_polynomial(graph, edge)
            next_graph = operation.apply(graph, edge)
            child = self._compute(next_graph, depth + 1)
            branch = OperationBranch(
                operation=operation,
                coefficient=coefficient,
                graph=next_graph,
                polynomial=child.polynomial,
                child=child,
            )
            branches.append(branch)
            polynomial = polynomial.add(branch.weighted_polynomial)

        step = self._new_step(
            depth,
            graph,
            polynomial,
            step_id=step_id,
            edge=edge,
            flow=flow,
            branches=tuple(branches),
        )
        if self.use_memo:
            self._memo[key] = polynomial
        return step

    def _validate_configuration(self):
        if not self.initial_value_rules:
            raise ValueError("At least one initial value rule is required.")
        if not self.calculation_flows:
            raise ValueError("At least one calculation flow is required.")

        _raise_for_duplicate_keys(
            self.initial_value_rules,
            "Initial value rule keys must be unique.",
        )
        _raise_for_duplicate_shape_keys(self.initial_value_rules)
        _raise_for_duplicate_keys(
            self.calculation_flows,
            "Calculation flow keys must be unique.",
        )

        for flow in self.calculation_flows:
            if not flow.operations:
                raise ValueError(f"Calculation flow {flow.key!r} has no operations.")
            _raise_for_duplicate_keys(
                flow.operations,
                f"Operation keys in flow {flow.key!r} must be unique.",
            )

    def _initial_rule_for(self, graph):
        matches = [rule for rule in self.initial_value_rules if rule.matches(graph)]
        if len(matches) > 1:
            names = ", ".join(rule.key for rule in matches)
            raise ValueError(
                "Initial value rules overlap for the same graph: "
                f"{names}. Make their graph shapes mutually exclusive."
            )
        return matches[0] if matches else None

    def _flow_for(self, graph, edge):
        for flow in self.calculation_flows:
            if flow.matches(graph, edge):
                return flow
        raise ValueError(
            f"No calculation flow matched edge {edge.label!r}. "
            "Add a CalculationFlow or a final catch-all flow."
        )

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


_DEFAULT_CONFIG_NAMES = {
    "DEFAULT_SYMBOLIC_CONFIG",
    "SYMBOLIC_CONFIGS",
    "DEFAULT_INITIAL_VALUE_RULES",
    "DEFAULT_EDGE_OPERATIONS",
    "DEFAULT_CALCULATION_FLOWS",
}


def _load_symbolic_config_registry():
    """Load editable config objects without creating an import cycle."""

    from graph_symbolic_config import DEFAULT_SYMBOLIC_CONFIG, SYMBOLIC_CONFIGS

    return DEFAULT_SYMBOLIC_CONFIG, SYMBOLIC_CONFIGS


def _load_default_symbolic_config():
    """Load the default config's three rule groups for compatibility."""

    default_config, _ = _load_symbolic_config_registry()

    return (
        default_config.initial_value_rules,
        default_config.edge_operations,
        default_config.calculation_flows,
    )


def _resolve_symbolic_config(config=None, config_key=None):
    if config is not None and config_key is not None:
        raise ValueError("Use either config or config_key, not both.")

    default_config, configs = _load_symbolic_config_registry()
    if config is None and config_key is None:
        return default_config

    if config is not None:
        if isinstance(config, str):
            config_key = config
        elif isinstance(config, SymbolicCalculationConfig):
            return config
        else:
            raise TypeError(
                "config must be a SymbolicCalculationConfig object or a config key string."
            )

    try:
        return configs[config_key]
    except KeyError as exc:
        available = ", ".join(sorted(configs))
        raise ValueError(
            f"Unknown symbolic config {config_key!r}. Available configs: {available}."
        ) from exc


def __getattr__(name):
    """Lazy compatibility exports for the moved default configuration."""

    if name not in _DEFAULT_CONFIG_NAMES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    default_config, configs = _load_symbolic_config_registry()
    initial_value_rules, edge_operations, calculation_flows = (
        _load_default_symbolic_config()
    )
    defaults = {
        "DEFAULT_SYMBOLIC_CONFIG": default_config,
        "SYMBOLIC_CONFIGS": configs,
        "DEFAULT_INITIAL_VALUE_RULES": initial_value_rules,
        "DEFAULT_EDGE_OPERATIONS": edge_operations,
        "DEFAULT_CALCULATION_FLOWS": calculation_flows,
    }
    globals().update(defaults)
    return defaults[name]


def _as_polynomial(value):
    """Normalize a small coefficient/value declaration into ``Polynomial``."""

    if isinstance(value, Polynomial):
        return value
    if value in (None, "", "1"):
        return Polynomial.one()
    if isinstance(value, int):
        return Polynomial.constant(value)
    if isinstance(value, str):
        text = value.strip()
        if text in ("", "1"):
            return Polynomial.one()
        if text == "0":
            return Polynomial.zero()
        try:
            return Polynomial.constant(int(text))
        except ValueError:
            pass
        if text in VARIABLE_ORDER:
            return Polynomial.symbol(text)
        raise ValueError(
            f"Cannot parse polynomial value {value!r}. "
            "Use an integer, a variable from VARIABLE_ORDER, or a Polynomial."
        )
    raise TypeError(f"Cannot convert {value!r} to Polynomial.")


def _coefficient_text(value):
    if callable(value):
        return "coef"
    return str(_as_polynomial(value))


def _raise_for_duplicate_keys(items, message):
    seen = set()
    for item in items:
        if item.key in seen:
            raise ValueError(f"{message} Duplicate key: {item.key!r}.")
        seen.add(item.key)


def _raise_for_duplicate_shape_keys(initial_value_rules):
    seen = {}
    for rule in initial_value_rules:
        if rule.shape_key is None:
            continue
        if rule.shape_key in seen:
            raise ValueError(
                "Initial value rules must describe different graph shapes. "
                f"Duplicate shape_key {rule.shape_key!r} appears in "
                f"{seen[rule.shape_key]!r} and {rule.key!r}."
            )
        seen[rule.shape_key] = rule.key


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
