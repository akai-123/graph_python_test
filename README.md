# Graph Drawer

一个轻量级的 Python 图论绘制工具，用于:

- 拖动绘制顶点与边，支持有向/无向边、重边和自环
- 拖动顶点观察不同平面布局，保持连接关系
- 节点标签可显示在点内或点旁，点旁标签会随节点移动并带有对应引线
- 可一键显示默认标签：点按 `1, 2, 3...`，边按 `a, b, c...`
- 拖动画出文本框添加文字，并可拖动文字移动位置
- 通过框选批量选择点、边、区域和文字，右键统一修改颜色、标签颜色、字号、大小、线宽、线型等样式
- 区域支持自由绘制、矩形、圆形、椭圆和三角形，并可在样式页签设置颜色和透明度
- 添加阴影区域、文字标注与标记
- 背景可切换为空白、网格或坐标轴，并可设置网格间距、坐标轴比例尺和原点
- 导出 PNG、PDF 图像
- 预览、复制或保存 TikZ 代码插入 LaTeX 文档
- 查看并导出邻接矩阵与关联矩阵
- 对当前图执行符号递归计算，并查看删除/收缩等操作步骤

## 运行方式

```bash
pip install -r requirements.txt
python graph_drawer.py
```

## 使用说明

- 使用顶部工具栏切换选择、点、边、文字、区域、移动、删除模式
- 在“文字”模式下拖动画出文本框，输入后按 `Ctrl+Enter` 完成，按 `Esc` 取消
- 在“选择”模式下拖动画框选择多个对象，右键打开样式菜单进行批量修改
- 可在右侧“样式”页签或右键样式窗口切换节点标签位置
- 可在右侧“样式”页签设置点标签、边标签的颜色和字号
- 区域工具默认自由绘制，也可在“样式”页签切换为矩形、圆形、椭圆或三角形后拖拽创建
- 顶部“显示标签”开启后会补齐默认点/边标签
- 矩阵页签可选择是否显示行列标签，邻接矩阵使用点标签，关联矩阵使用点与边标签
- 重边会自动弯曲分开显示，自环会显示为节点旁的环形边；选择/移动模式下拖动已有边可以手动调整弯曲程度
- 选择对象后可按 `Delete` 删除；在选择模式下按住点片刻可直接拖动移动
- 双击节点、边、区域可编辑标签，双击文字可重新编辑文字内容
- 使用右侧“矩阵”页签刷新或保存矩阵，使用“导出”页签预览 TikZ，再选择复制到剪贴板或保存为 `.tex`
- 使用右侧“符号计算”页签选择配置组并计算当前图的递归多项式，在步骤窗口中查看当前图、操作后的图和对应多项式

## 符号计算

符号计算分为三层文件:

- `graph_symbolic.py`: 计算引擎，定义 `Polynomial`、`SymbolicGraph`、`InitialValueRule`、`EdgeOperation`、`CalculationFlow` 和 `DeletionContractionCalculator`
- `graph_symbolic_config.py`: 可自定义配置组，集中放初始值、多项式计算项、递归流程和配置注册表
- `graph_symbolic_tools.py`: 可复用工具，集中放图初始状态判断、边判断和图操作

界面层只负责把当前画布转换为 `SymbolicGraph`，再调用 `DeletionContractionCalculator`。默认规则为:

```text
无边图且有 n 个点: f(G) = h^n
有边图选择一条边 e: f(G) = a f(G-e) + b f(G/e)
```

计算器会生成完整步骤树。每个非初始步骤会记录当前图、选中的边、命中的计算流程、每个分支操作后的图，以及该分支的子多项式。

### 配置组

`graph_symbolic_config.py` 用 `SymbolicCalculationConfig` 把一整套符号计算规则封装成配置组。一组配置包含:

- `initial_value_rules`: 初始值规则
- `calculation_flows`: 递归流程规则

`EdgeOperation` 不作为配置组字段单独传入，因为每个 `CalculationFlow.operations` 已经明确引用了要执行的计算项。配置对象上的 `edge_operations` 只是从流程中推导出的兼容属性，通常不需要手动设置。

可按名称注册多组配置:

```python
DEFAULT_SYMBOLIC_CONFIG = SymbolicCalculationConfig(
    key="default",
    title="Default delete-contract / 默认删除-收缩",
    initial_value_rules=STANDARD_INITIAL_VALUE_RULES,
    calculation_flows=STANDARD_DELETE_CONTRACT_FLOWS,
)

SYMBOLIC_CONFIGS = {
    DEFAULT_SYMBOLIC_CONFIG.key: DEFAULT_SYMBOLIC_CONFIG,
}
```

使用时可以按配置名选择:

```python
calculator = DeletionContractionCalculator(config_key="default")
```

也可以直接传入配置对象:

```python
calculator = DeletionContractionCalculator(config=DEFAULT_SYMBOLIC_CONFIG)
```

当前示例里还注册了 `loop_delete_only`，它会让自环只执行删除分支，其它边仍执行默认删除-收缩:

```python
calculator = DeletionContractionCalculator(config_key="loop_delete_only")
```

如果要新增一套自己的规则，推荐复制一个现有 `SymbolicCalculationConfig`，改 `key`、`title`、初始值规则和递归流程，再加入 `SYMBOLIC_CONFIGS`。

### 初始值规则

初始值规则通常先定义成一个 tuple，再放入某个 `SymbolicCalculationConfig.initial_value_rules`。判断函数通常写在 `graph_symbolic_tools.py` 中。

```python
STANDARD_INITIAL_VALUE_RULES = (
    InitialValueRule(
        key="edgeless",
        title="Edgeless graph",
        when=is_edgeless_graph,
        value=edgeless_value,
        shape_key="all-edgeless-graphs",
        description="For a graph with n isolated vertices, f(G)=h^n.",
    ),
)
```

- `when(graph)` 判断当前图是否属于这个初始形状。
- `value` 可以是 `Polynomial`、整数、变量字符串，也可以是 `lambda graph: ...`。
- `shape_key` 用来标记图形状类型，不同初始规则应使用不同的 `shape_key`。
- 如果两个初始规则同时匹配同一张图，计算器会抛出 `ValueError`，避免同一形状出现两个初始值。

添加新的初始值时，先在 `graph_symbolic_tools.py` 写判断函数，再把规则加入配置组使用的初始值 tuple。比如复制 `STANDARD_INITIAL_VALUE_RULES` 形成 `MY_INITIAL_VALUE_RULES`，然后放进 `SymbolicCalculationConfig(initial_value_rules=MY_INITIAL_VALUE_RULES, ...)`。

### 多项式计算项

单个递归计算项用 `EdgeOperation` 描述“对选中边做什么图操作，以及子图多项式乘什么系数”。图操作函数通常写在 `graph_symbolic_tools.py` 中。多个计算项可以组成一个 tuple，供 `CalculationFlow.operations` 引用。

```python
EdgeOperation(
    key="delete",
    title="Delete",
    coefficient="a",
    transform=delete_selected_edge,
)

EdgeOperation(
    key="contract",
    title="Contract",
    coefficient="b",
    transform=contract_selected_edge,
)
```

`coefficient` 会先转换成 `Polynomial`，再乘到子图多项式上。支持这些写法:

- `1`、`"1"`、`None`: 系数为 1，即直接使用子图多项式。
- `0`、`2`、`-1`、`"2"`: 整数常数。`coefficient=0` 表示这一项贡献为 0，但子图仍会计算，所以 `transform` 仍要合法。
- `"a"`、`"b"`、`"h"`: 单个变量，变量名必须来自 `VARIABLE_ORDER`。
- `Polynomial.symbol("a")`: 用 `Polynomial` 写单个变量。
- `Polynomial.monomial(2, a=1, h=1)`: 自定义单项式，例如 `2ah`。
- `Polynomial.symbol("a").add(Polynomial.symbol("b"))`: 自定义多项式，例如 `a+b`。
- `lambda graph, edge: ...`: 动态系数，函数接收当前图和选中边，返回上面任意一种形式。

字符串不会解析复杂表达式，所以不要写 `"a+b"` 或 `"2a"`；这种情况请使用 `Polynomial` 方法。

`transform(graph, edge)` 必须返回新的 `SymbolicGraph`。通常它要删除或收缩当前边，保证递归会继续接近某个初始值。

### 递归流程规则

不同情况下执行哪些计算项用 `CalculationFlow` 描述。流程按顺序匹配，第一条 `when(graph, edge)` 为真的流程会被使用。边判断函数通常写在 `graph_symbolic_tools.py` 中。流程 tuple 放入配置组的 `calculation_flows`。

```python
STANDARD_DELETE_CONTRACT_FLOWS = (
    CalculationFlow(
        key="default_delete_contract",
        title="Default delete-contract",
        when=always_use_flow,
        operations=STANDARD_EDGE_OPERATIONS,
    ),
)
```

流程的 `operations` 可以只放一个计算项，也可以放多个。多个计算项会相加:

```text
f(G) = operation_1_contribution + operation_2_contribution + ...
```

例如，可以把自环作为特殊情况，只执行删除分支；其它边仍执行删除加收缩:

```python
delete_operation = STANDARD_EDGE_OPERATIONS[0]

LOOP_DELETE_ONLY_FLOWS = (
    CalculationFlow(
        key="loop_delete_only",
        title="Loop delete only",
        when=edge_is_loop,
        operations=(delete_operation,),
    ),
    CalculationFlow(
        key="default_delete_contract",
        title="Default delete-contract",
        when=always_use_flow,
        operations=STANDARD_EDGE_OPERATIONS,
    ),
)
```

因为流程按顺序匹配，特殊情况要放在默认 `when=True` 之前。

## 依赖

- Python 3.8+
- Pillow
