"""Editable symbolic calculation configuration.

可编辑的符号计算配置。

This file contains named config groups. Each group packages:
1. Initial values
2. Recursion flows

这个文件用于定义“配置组”。每个配置组打包两类内容:
1. 初始值
2. 递归流程规则

Polynomial calculation terms are still defined here as reusable EdgeOperation
objects, but a config does not store them separately. Flows reference the terms
they need through ``CalculationFlow.operations``.

多项式计算项仍作为可复用的 EdgeOperation 定义在这里，但配置组不再单独保存
它们；递归流程通过 ``CalculationFlow.operations`` 引用需要执行的计算项。

If you need a new graph predicate, edge predicate, or graph transform, define it
in ``graph_symbolic_tools.py`` first, then reference it here.

如果需要新的图形状判断、边判断或图操作，请先在 ``graph_symbolic_tools.py`` 中
定义函数，再在本文件中引用。
"""

from __future__ import annotations

from graph_symbolic import (
    CalculationFlow,
    EdgeOperation,
    InitialValueRule,
    SymbolicCalculationConfig,
)
from graph_symbolic_tools import (
    always_use_flow,
    contract_selected_edge,
    delete_selected_edge,
    edge_is_loop,
    edgeless_value,
    graph_has_parallel_edge_to,
    is_edgeless_graph,
    to_empty_graph,
)


# ---------------------------------------------------------------------------
# 1. Initial values shared by config groups
# 1. 多个配置组可共用的初始值
# ---------------------------------------------------------------------------
#
# InitialValueRule defines graph shapes that stop recursion.
# InitialValueRule 用来定义“不再递归、直接给值”的图形状。
#
# Fields / 字段:
#
# key:
#   Unique identifier used in debugging and step records.
#   唯一标识，用于调试和步骤记录。
#
# title:
#   Human-readable name.
#   给人看的名称。
#
# when(graph):
#   Predicate that returns True when this initial value applies.
#   判断当前图是否适用这个初始值，返回 True 或 False。
#
# value:
#   Polynomial value. It may be:
#   多项式值，可以写成:
#       Polynomial object / Polynomial 对象
#       integer / 整数
#       "a", "b", or "h" / 变量字符串
#       lambda graph: ... / 根据图动态计算的函数
#
# shape_key:
#   A label for the graph shape. Different initial shapes should use different
#   shape_key values. Duplicate shape_key values are rejected.
#   图形状标签。不同初始形状应使用不同 shape_key，重复会报错。

STANDARD_INITIAL_VALUE_RULES = (
    InitialValueRule(
        key="edgeless",
        title="Edgeless graph / 无边图",
        when=is_edgeless_graph,
        value=edgeless_value,
        shape_key="all-edgeless-graphs",
        description="For n isolated vertices, f(G)=h^n. / n 个孤立点时 f(G)=h^n。",
    ),
)


# Example: add another initial value
# 示例: 添加另一个初始值
#
# from graph_symbolic import Polynomial
# from graph_symbolic_tools import has_single_vertex
#
# CUSTOM_INITIAL_VALUE_RULES = (
#     InitialValueRule(
#         key="single_vertex",
#         title="Single vertex / 单点图",
#         when=has_single_vertex,
#         value=Polynomial.symbol("h"),
#         shape_key="single-vertex-graph",
#         description="One vertex has value h. / 单点图取值为 h。",
#     ),
#     ... existing rules ...
# )


# ---------------------------------------------------------------------------
# 2. Polynomial calculation terms shared by config groups
# 2. 多个配置组可共用的多项式计算项
# ---------------------------------------------------------------------------
#
# EdgeOperation defines one term in a recurrence.
# EdgeOperation 定义递归公式中的一项。
#
# Meaning / 含义:
#   operation contribution = coefficient * f(transform(graph, edge))
#   该项贡献 = coefficient * f(transform(graph, edge))
#
# Fields / 字段:
#
# key:
#   Unique operation id inside one flow.
#   在一个流程内唯一的操作标识。
#
# coefficient:
#   Multiplier applied to the child polynomial:
#       contribution = coefficient * f(transform(graph, edge))
#   乘在子图多项式前的系数:
#       该项贡献 = coefficient * f(transform(graph, edge))
#
#   Supported forms / 支持写法:
#
#   1) Unit coefficient / 单位系数
#       coefficient=1
#       coefficient="1"
#       coefficient=None
#      These all mean f(next_graph).
#      这些都表示直接取 f(next_graph)，不额外乘变量。
#
#   2) Integer constants / 整数常数
#       coefficient=0
#       coefficient=2
#       coefficient=-1
#       coefficient="2"
#      Example: coefficient=0 means this term contributes 0.
#      例: coefficient=0 表示这一项贡献为 0。
#      The child graph is still computed, so transform should still be valid.
#      子图仍会被计算，所以 transform 仍应返回合法图。
#
#   3) Single variable / 单个变量
#       coefficient="a"
#       coefficient="b"
#       coefficient="h"
#       coefficient=Polynomial.symbol("a")
#      String variables must be names from VARIABLE_ORDER in graph_symbolic.py.
#      字符串变量必须来自 graph_symbolic.py 中的 VARIABLE_ORDER。
#
#   4) Custom monomial / 自定义单项式
#       coefficient=Polynomial.monomial(2, a=1, h=1)   # 2ah
#       coefficient=Polynomial.monomial(-1, b=2)       # -b^2
#
#   5) Custom multi-term polynomial / 自定义多项式
#       coefficient=Polynomial.symbol("a").add(Polynomial.symbol("b"))  # a+b
#      Strings like "a+b" or "2a" are not parsed.
#      字符串 "a+b" 或 "2a" 不会被解析，请用 Polynomial 写。
#
#   6) Dynamic coefficient / 动态系数
#       coefficient=lambda graph, edge: "a" if edge.source != edge.target else 0
#      The function receives the current SymbolicGraph and selected SymbolicEdge.
#      函数参数是当前图 graph 和选中边 edge。
#      It may return any supported form above.
#      返回值可以是上面任意一种支持写法。
#
# transform(graph, edge):
#   Function that returns the next graph.
#   返回下一张图的函数。

DELETE_EDGE = EdgeOperation(
    key="delete",
    title="Delete / 删除",
    coefficient="a",
    transform=delete_selected_edge,
    description="a * f(G-e) / 删除选中边后乘以 a",
)

DELETE_EDGE_SAME = EdgeOperation(
    key="delete",
    title="Same Be Delete / 删除",
    coefficient="1",
    transform=delete_selected_edge,
    description="1 * f(G-e) / 删除选中边后乘以 1",
)

CONTRACT_EDGE = EdgeOperation(
    key="contract",
    title="Contract / 收缩",
    coefficient="b",
    transform=contract_selected_edge,
    description="b * f(G/e) / 收缩选中边后乘以 b",
)

ZERO_EDGE = EdgeOperation(
    key="to empty grap",
    title="become empty graph, value to 0",
    coefficient=0,
    transform=to_empty_graph,
    description="0", 
)


STANDARD_EDGE_OPERATIONS = (
    DELETE_EDGE,
    CONTRACT_EDGE,
)


# Example: define a custom calculation term
# 示例: 定义一个自定义计算项
#
# from graph_symbolic import Polynomial
# CUSTOM_DELETE = EdgeOperation(
#     key="custom_delete",
#     title="Custom delete / 自定义删除",
#     coefficient=Polynomial.monomial(2, a=1, h=1),  # 2ah
#     transform=delete_selected_edge,
#     description="2ah * f(G-e)",
# )


# ---------------------------------------------------------------------------
# 3. Recursion flows
# 3. 递归流程规则
# ---------------------------------------------------------------------------
#
# CalculationFlow decides which operations are used in a situation.
# CalculationFlow 决定某种情况下执行哪些计算项。
#
# Flows are checked from top to bottom. The first matching flow is used.
# 流程从上到下匹配，第一条匹配成功的流程会被使用。
#
# Fields / 字段:
#
# when(graph, edge):
#   Edge predicate for choosing this flow.
#   用于选择流程的边判断函数。
#
# operations:
#   Tuple of EdgeOperation objects. Their contributions are added.
#   EdgeOperation 元组，所有项的贡献会相加。

STANDARD_DELETE_CONTRACT_FLOWS = (
    CalculationFlow(
        key="default_delete_contract",
        title="Default delete-contract / 默认删除-收缩",
        when=always_use_flow,
        operations=STANDARD_EDGE_OPERATIONS,
        description="Use a*f(G-e) + b*f(G/e). / 使用 a*f(G-e) + b*f(G/e)。",
    ),
)


LOOP_DELETE_ONLY_FLOWS = (
    CalculationFlow(
        key="loop_delete_only",
        title="Loop delete only / 自环只删除",
        when=edge_is_loop,
        operations=(DELETE_EDGE,),
        description="For loops, use only a*f(G-e). / 自环只使用删除项。",
    ),
    CalculationFlow(
        key="default_delete_contract",
        title="Default delete-contract / 默认删除-收缩",
        when=always_use_flow,
        operations=STANDARD_EDGE_OPERATIONS,
        description="Use a*f(G-e) + b*f(G/e). / 使用 a*f(G-e) + b*f(G/e)。",
    ),
)

DELETE_PARALLEL_EDGE_AND_LOOP_ZERO_FLOWS = (
    CalculationFlow(
        key="loop_delete_only",
        title="Loop delete only / 自环只删除",
        when=edge_is_loop,
        operations=(ZERO_EDGE,),
        description="For loops, use only 0). / 自环归零,返回0。",
    ),
    CalculationFlow(
        key="delete_parallel_edg",
        title="delete parallel edge / 重边删除",
        when=graph_has_parallel_edge_to,
        operations=(DELETE_EDGE_SAME,),
        description="For parallel, use only 1*f(G-e). / 重边只使用删除项。",
    ),
      CalculationFlow(
        key="default_delete_contract",
        title="Default delete-contract / 默认删除-收缩",
        when=always_use_flow,
        operations=STANDARD_EDGE_OPERATIONS,
        description="Use a*f(G-e) + b*f(G/e). / 使用 a*f(G-e) + b*f(G/e)。",
    ),
)


# ---------------------------------------------------------------------------
# 4. Config groups and registry
# 4. 配置组与注册表
# ---------------------------------------------------------------------------
#
# SymbolicCalculationConfig packages initial values and recursion flows.
# EdgeOperation objects live inside each flow's operations tuple.
# SymbolicCalculationConfig 打包初始值与递归流程。
# EdgeOperation 对象由各个 flow 的 operations 字段引用。
#
# Fields / 字段:
#
# key:
#   Config name used by DeletionContractionCalculator(config_key=...).
#   配置名，用于 DeletionContractionCalculator(config_key=...)。
#
# initial_value_rules:
#   InitialValueRule tuple used by this config.
#   本配置使用的初始值规则。
#
# calculation_flows:
#   Ordered CalculationFlow tuple used by this config.
#   本配置使用的有序递归流程。

DEFAULT_SYMBOLIC_CONFIG = SymbolicCalculationConfig(
    key="default",
    title="Default delete-contract / 默认删除-收缩",
    initial_value_rules=STANDARD_INITIAL_VALUE_RULES,
    calculation_flows=STANDARD_DELETE_CONTRACT_FLOWS,
    description="Default rule: f(G)=a*f(G-e)+b*f(G/e).",
)


LOOP_DELETE_ONLY_CONFIG = SymbolicCalculationConfig(
    key="loop_delete_only",
    title="Loop delete only / 自环只删除",
    initial_value_rules=STANDARD_INITIAL_VALUE_RULES,
    calculation_flows=LOOP_DELETE_ONLY_FLOWS,
    description="Loops use only deletion; other edges use delete-contract.",
)


DELETE_PARALLEL_EDGE_AND_LOOP_ZERO_CONFIG = SymbolicCalculationConfig(
    key="no_paralle_edge_and_loop_zero",
    title="delete paralle edge and become zero when loop / 重边时删除, 有环直接为0",
    initial_value_rules=STANDARD_INITIAL_VALUE_RULES,
    calculation_flows=DELETE_PARALLEL_EDGE_AND_LOOP_ZERO_FLOWS,
    description="Default rule: f(G)=a*f(G-e)+b*f(G/e). When e is paralle, f(G)=f(G-e); when e is loop, f(G) = 0",
)


# Register every config that should be selectable by name.
# 把所有可以按名称选择的配置都注册在这里。
SYMBOLIC_CONFIGS = {
    DEFAULT_SYMBOLIC_CONFIG.key: DEFAULT_SYMBOLIC_CONFIG,
    LOOP_DELETE_ONLY_CONFIG.key: LOOP_DELETE_ONLY_CONFIG,
    DELETE_PARALLEL_EDGE_AND_LOOP_ZERO_CONFIG.key : DELETE_PARALLEL_EDGE_AND_LOOP_ZERO_CONFIG,
}


# Backward-compatible aliases for existing imports.
# 兼容旧代码继续导入这些默认名称。
DEFAULT_INITIAL_VALUE_RULES = DEFAULT_SYMBOLIC_CONFIG.initial_value_rules
DEFAULT_EDGE_OPERATIONS = DEFAULT_SYMBOLIC_CONFIG.edge_operations
DEFAULT_CALCULATION_FLOWS = DEFAULT_SYMBOLIC_CONFIG.calculation_flows


# Example: add and register your own config group
# 示例: 新增并注册你自己的配置组
#
# MY_CONFIG = SymbolicCalculationConfig(
#     key="my_config",
#     title="My config / 我的配置",
#     initial_value_rules=STANDARD_INITIAL_VALUE_RULES,
#     calculation_flows=STANDARD_DELETE_CONTRACT_FLOWS,
# )
#
# SYMBOLIC_CONFIGS[MY_CONFIG.key] = MY_CONFIG
#
# Then use:
# 然后这样使用:
#
# calculator = DeletionContractionCalculator(config_key="my_config")
