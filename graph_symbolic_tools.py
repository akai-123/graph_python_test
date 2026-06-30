"""Reusable graph predicates and graph transforms for symbolic calculation.

符号计算可复用的图判断与图操作工具。

This file is meant to be edited by hand when you want new graph shapes,
edge cases, or edge operations.

如果要添加新的初始图形状、边分类或图操作，优先改这个文件。

Parameter guide / 参数说明:

- graph: ``SymbolicGraph``
  当前递归步骤中的图。它包含 ``graph.vertices`` 和 ``graph.edges``。
  The graph at the current recursion step. It has ``graph.vertices`` and
  ``graph.edges``.

- edge: ``SymbolicEdge``
  当前流程选中的边。它包含 ``edge.id``, ``edge.source``, ``edge.target`` 和
  ``edge.label``。
  The chosen edge for the current flow. It has ``edge.id``, ``edge.source``,
  ``edge.target`` and ``edge.label``.

Editing rules / 修改原则:

- Predicate functions return ``True`` or ``False``.
  判断函数返回 ``True`` 或 ``False``。
- Transform functions return a new ``SymbolicGraph``.
  图操作函数返回新的 ``SymbolicGraph``。
- Do not mutate ``graph.vertices`` or ``graph.edges`` in place.
  不要原地修改 ``graph.vertices`` 或 ``graph.edges``。
"""

from __future__ import annotations

from graph_symbolic import Polynomial, SymbolicEdge, SymbolicGraph


# ---------------------------------------------------------------------------
# Initial graph predicates and values
# 初始图形状判断与初始值
# ---------------------------------------------------------------------------


def is_edgeless_graph(graph: SymbolicGraph) -> bool:
    """Return True when the graph has no edges.

    当图没有任何边时返回 True。

    Parameters / 参数:
        graph: current graph / 当前图。
    """

    return not graph.edges


def edgeless_value(graph: SymbolicGraph) -> Polynomial:
    """Initial value for an edgeless graph: h^n.

    无边图的初始值: h^n。

    Parameters / 参数:
        graph: current edgeless graph / 当前无边图。
        n: ``len(graph.vertices)`` / 点数。
    """

    return Polynomial.h_power(len(graph.vertices))


def has_single_vertex(graph: SymbolicGraph) -> bool:
    """Example predicate: exactly one vertex.

    示例判断: 图中恰好有一个点。

    You can use this in an InitialValueRule if a one-vertex graph should stop
    recursion in your polynomial.

    如果你的多项式把单点图作为初始值，可以在 InitialValueRule 中使用它。
    """

    return len(graph.vertices) == 1


# ---------------------------------------------------------------------------
# Edge predicates for choosing a calculation flow
# 用于选择递归流程的边判断
# ---------------------------------------------------------------------------


def always_use_flow(graph: SymbolicGraph, edge: SymbolicEdge) -> bool:
    """Catch-all flow predicate.

    兜底流程判断，总是返回 True。

    Put flows that use this predicate after special cases.
    使用这个判断的流程应放在特殊情况之后。
    """

    return True


def edge_is_loop(graph: SymbolicGraph, edge: SymbolicEdge) -> bool:
    """Return True when the chosen edge is a loop.

    当选中的边是自环时返回 True。

    A loop has the same source and target vertex.
    自环满足 ``edge.source == edge.target``。
    """

    return edge.source == edge.target


def edge_is_not_loop(graph: SymbolicGraph, edge: SymbolicEdge) -> bool:
    """Return True when the chosen edge connects two different vertices.

    当选中的边连接两个不同顶点时返回 True。
    """

    return edge.source != edge.target


def graph_has_parallel_edge_to(graph: SymbolicGraph, edge: SymbolicEdge) -> bool:
    """Example predicate: another edge joins the same two vertices.

    示例判断: 是否存在另一条边连接同一对端点。

    This treats the graph as undirected for comparison because the symbolic
    calculator currently canonicalizes edge pairs without direction.

    这里按无向边比较端点，因为当前符号计算的规范键不区分方向。
    """

    endpoints = tuple(sorted((edge.source, edge.target)))
    for candidate in graph.edges:
        if candidate.id == edge.id:
            continue
        if tuple(sorted((candidate.source, candidate.target))) == endpoints:
            return True
    return False


# ---------------------------------------------------------------------------
# Edge transforms used by polynomial calculation terms
# 多项式计算项使用的边操作
# ---------------------------------------------------------------------------


def delete_selected_edge(graph: SymbolicGraph, edge: SymbolicEdge) -> SymbolicGraph:
    """Return G - e.

    返回删除选中边后的图 G - e。

    Parameters / 参数:
        graph: current graph / 当前图。
        edge: selected edge to delete / 要删除的选中边。
    """

    return graph.without_edge(edge.id)


def contract_selected_edge(graph: SymbolicGraph, edge: SymbolicEdge) -> SymbolicGraph:
    """Return G / e.

    返回收缩选中边后的图 G / e。

    Contracting a loop is treated as deleting that loop by ``SymbolicGraph``.
    ``SymbolicGraph`` 会把自环收缩视为删除该自环。
    """

    return graph.with_contracted_edge(edge.id)

def to_empty_graph(graph: SymbolicGraph, edge: SymbolicEdge) -> SymbolicGraph:
    """ Return empty graph
    图置为空
    """
    return SymbolicGraph(vertices=(), edges=())


def delete_all_edges_between_endpoints(
    graph: SymbolicGraph, edge: SymbolicEdge
) -> SymbolicGraph:
    """Example transform: delete every edge with the same endpoints.

    示例操作: 删除所有连接同一对端点的边。

    This is useful if your recurrence treats parallel edges as one bundle.
    如果你的递归规则把重边作为一组处理，可以参考这个操作。
    """

    endpoints = tuple(sorted((edge.source, edge.target)))
    return SymbolicGraph(
        vertices=graph.vertices,
        edges=tuple(
            candidate
            for candidate in graph.edges
            if tuple(sorted((candidate.source, candidate.target))) != endpoints
        ),
    )



# Example for adding a new transform / 添加新图操作的示例:
#
# def keep_only_vertices(graph: SymbolicGraph, edge: SymbolicEdge) -> SymbolicGraph:
#     """Delete every edge but keep all vertices.
#     删除所有边，但保留所有顶点。
#     """
#     return SymbolicGraph(vertices=graph.vertices, edges=())
