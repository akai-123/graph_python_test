import copy
import math
import os
import re
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

from graph_export import MatrixBuilder, TikzExporter
from graph_symbolic import (
    DeletionContractionCalculator,
    SYMBOLIC_CONFIGS,
    SymbolicComputationLimit,
    SymbolicEdge,
    SymbolicGraph,
    SymbolicVertex,
)
from graph_model import (
    BACKGROUND_MODES,
    EDGE_STYLES,
    BackgroundSettings,
    CANVAS_DEFAULT_HEIGHT,
    CANVAS_DEFAULT_WIDTH,
    DEFAULT_AXIS_ORIGIN_X,
    DEFAULT_AXIS_ORIGIN_Y,
    DEFAULT_AXIS_SCALE,
    DEFAULT_BACKGROUND_MODE,
    DEFAULT_EDGE_COLOR,
    DEFAULT_EDGE_LABEL_COLOR,
    DEFAULT_EDGE_LABEL_SIZE,
    DEFAULT_EDGE_STYLE,
    DEFAULT_EDGE_WIDTH,
    DEFAULT_NODE_COLOR,
    DEFAULT_NODE_LABEL_COLOR,
    DEFAULT_NODE_LABEL_POSITION,
    DEFAULT_NODE_LABEL_SIZE,
    DEFAULT_NODE_OUTLINE_COLOR,
    DEFAULT_PENCIL_COLOR,
    DEFAULT_PENCIL_WIDTH,
    DEFAULT_REGION_SHAPE,
    DEFAULT_SHADOW_ALPHA,
    DEFAULT_SHADOW_COLOR,
    DEFAULT_TEXT_COLOR,
    DEFAULT_TEXT_HEIGHT,
    DEFAULT_TEXT_SIZE,
    DEFAULT_TEXT_WIDTH,
    Edge,
    MIN_AXIS_SCALE,
    NODE_RADIUS,
    Node,
    NODE_LABEL_POSITIONS,
    PencilStroke,
    Region,
    REGION_SHAPES,
    STIPPLE_PATTERNS,
    TextLabel,
)

try:
    from PIL import Image, ImageGrab
except ImportError:
    Image = None
    ImageGrab = None


MODE_OPTIONS = (
    ("选择", "select"),
    ("点", "vertex"),
    ("边", "edge"),
    ("文字", "text"),
    ("区域", "doodle"),
    ("铅笔", "pencil"),
    ("移动", "move"),
    ("删除", "delete"),
)

MODE_HINTS = {
    "select": "拖动画框选择；按住点片刻可直接移动，右键可批量修改样式。",
    "vertex": "点击空白处添加点。",
    "edge": "从一个点拖到另一个点创建边。",
    "text": "拖动画出文本框，输入后 Ctrl+Enter 完成。",
    "doodle": "拖动创建阴影区域。",
    "pencil": "按住拖动在图中自由绘制笔迹。",
    "move": "拖动点或文字移动位置。",
    "delete": "点击对象删除。",
}

EDGE_DASH_PATTERNS = {
    "solid": None,
    "dashed": (8, 4),
    "dotted": (2, 4),
    "dashdot": (8, 4, 2, 4),
}

EDGE_STYLE_LABEL_BY_VALUE = dict(EDGE_STYLES)
EDGE_STYLE_VALUE_BY_LABEL = {label: value for value, label in EDGE_STYLES}
NODE_LABEL_POSITION_LABEL_BY_VALUE = dict(NODE_LABEL_POSITIONS)
NODE_LABEL_POSITION_VALUE_BY_LABEL = {label: value for value, label in NODE_LABEL_POSITIONS}
REGION_SHAPE_LABEL_BY_VALUE = dict(REGION_SHAPES)
REGION_SHAPE_VALUE_BY_LABEL = {label: value for value, label in REGION_SHAPES}

SELECTION_COLOR = "#2563eb"


class GraphDrawer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Graph Drawer")
        self.root.geometry("1280x780")
        self.root.minsize(980, 640)
        self.root.configure(bg="#f6f7fb")

        self.nodes = []
        self.edges = []
        self.regions = []
        self.texts = []
        self.pencil_strokes = []
        self.history = []
        self.selection = set()

        self.current_edge_start = None
        self.current_doodle = None
        self.current_pencil_stroke = None
        self.current_drag_kind = None
        self.current_drag_object = None
        self.drag_origin = None
        self.current_text_box = None
        self.current_selection_box = None
        self.current_region_box = None
        self.active_text_editor = None

        self.node_color = DEFAULT_NODE_COLOR
        self.node_outline_color = DEFAULT_NODE_OUTLINE_COLOR
        self.node_label_color = DEFAULT_NODE_LABEL_COLOR
        self.edge_color = DEFAULT_EDGE_COLOR
        self.edge_label_color = DEFAULT_EDGE_LABEL_COLOR
        self.text_color = DEFAULT_TEXT_COLOR
        self.shadow_color = DEFAULT_SHADOW_COLOR
        self.shadow_alpha = DEFAULT_SHADOW_ALPHA
        self.pencil_color = DEFAULT_PENCIL_COLOR

        self.background = tk.StringVar(value=DEFAULT_BACKGROUND_MODE)
        self.axis_scale = tk.StringVar(value=str(DEFAULT_AXIS_SCALE))
        self.axis_origin_x = tk.StringVar(value=str(DEFAULT_AXIS_ORIGIN_X))
        self.axis_origin_y = tk.StringVar(value=str(DEFAULT_AXIS_ORIGIN_Y))
        self.mode = tk.StringVar(value="select")
        self.directed = tk.BooleanVar(value=False)
        self.node_radius = tk.StringVar(value=str(NODE_RADIUS))
        self.node_label_position = tk.StringVar(value=NODE_LABEL_POSITION_LABEL_BY_VALUE[DEFAULT_NODE_LABEL_POSITION])
        self.node_label_size = tk.StringVar(value=str(DEFAULT_NODE_LABEL_SIZE))
        self.edge_width = tk.StringVar(value=str(DEFAULT_EDGE_WIDTH))
        self.edge_style = tk.StringVar(value=EDGE_STYLE_LABEL_BY_VALUE[DEFAULT_EDGE_STYLE])
        self.edge_label_size = tk.StringVar(value=str(DEFAULT_EDGE_LABEL_SIZE))
        self.text_size = tk.StringVar(value=str(DEFAULT_TEXT_SIZE))
        self.pencil_width = tk.StringVar(value=str(DEFAULT_PENCIL_WIDTH))
        self.region_alpha = tk.StringVar(value=str(DEFAULT_SHADOW_ALPHA))
        self.region_shape = tk.StringVar(value=REGION_SHAPE_LABEL_BY_VALUE[DEFAULT_REGION_SHAPE])
        self.show_node_labels = tk.BooleanVar(value=False)
        self.show_edge_labels = tk.BooleanVar(value=False)
        self.matrix_show_labels = tk.BooleanVar(value=True)
        self.status_text = tk.StringVar(value="")
        self.symbolic_config_keys = tuple(sorted(SYMBOLIC_CONFIGS))
        default_symbolic_config = "default" if "default" in self.symbolic_config_keys else self.symbolic_config_keys[0]
        self.symbolic_config = tk.StringVar(value=default_symbolic_config)
        self.symbolic_result = None
        self.symbolic_step_by_id = {}
        self.symbolic_selected_step = None
        self.symbolic_ui = {}
        self.pending_select_move_target = None
        self.pending_select_move_origin = None
        self.pending_select_move_latest = None
        self.pending_select_move_after_id = None

        self._configure_styles()
        self._build_ui()
        self._bind_events()
        self._bind_variable_traces()
        self._save_history()
        self._update_status()
        self.draw_canvas()

    def _configure_styles(self):
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        base_bg = "#f6f7fb"
        surface = "#ffffff"
        soft_surface = "#fbfcfe"
        text = "#1f2937"
        muted = "#6b7280"
        border = "#d9e0ea"
        accent = "#2563eb"

        style.configure(".", font=("Segoe UI", 9), background=base_bg, foreground=text)
        style.configure("Toolbar.TFrame", background=base_bg)
        style.configure("Panel.TFrame", background=soft_surface)
        style.configure("Section.TLabelframe", background=base_bg, bordercolor=border, relief=tk.FLAT)
        style.configure("Section.TLabelframe.Label", background=base_bg, foreground=text, font=("Segoe UI", 9, "bold"))
        style.configure("Status.TLabel", background=surface, foreground=muted)
        style.configure("TButton", background=surface, foreground=text, bordercolor=border, focusthickness=0, padding=(8, 4))
        style.map("TButton", background=[("active", "#eef4ff")], bordercolor=[("active", accent)])
        style.configure("TRadiobutton", background=base_bg, foreground=text, padding=(2, 2))
        style.configure("TCheckbutton", background=base_bg, foreground=text)
        style.configure("TLabel", background=base_bg, foreground=text)
        style.configure("TEntry", fieldbackground=surface, bordercolor=border, lightcolor=border, darkcolor=border)
        style.configure("TCombobox", fieldbackground=surface, bordercolor=border, arrowcolor=muted)
        style.configure("TNotebook", background=base_bg, borderwidth=0)
        style.configure("TNotebook.Tab", background="#e9edf5", foreground=muted, padding=(14, 7))
        style.map("TNotebook.Tab", background=[("selected", surface)], foreground=[("selected", text)])

    def _build_ui(self):
        self._build_toolbar(self.root)

        main_frame = ttk.Frame(self.root, padding=(14, 0, 14, 14), style="Toolbar.TFrame")
        main_frame.pack(fill=tk.BOTH, expand=True)

        canvas_area = ttk.Frame(main_frame, style="Toolbar.TFrame")
        canvas_area.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(
            canvas_area,
            background="#ffffff",
            highlightthickness=1,
            highlightbackground="#dce3ee",
            relief=tk.FLAT,
            width=CANVAS_DEFAULT_WIDTH,
            height=CANVAS_DEFAULT_HEIGHT,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.status_label = ttk.Label(
            canvas_area,
            textvariable=self.status_text,
            style="Status.TLabel",
            padding=(10, 5),
            anchor=tk.W,
        )
        self.status_label.pack(fill=tk.X, pady=(6, 0))

        side_panel = ttk.Notebook(main_frame, width=300)
        side_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(14, 0))
        side_panel.pack_propagate(False)
        self._build_style_tab(side_panel)
        self._build_background_tab(side_panel)
        self._build_export_tab(side_panel)
        self._build_matrix_tab(side_panel)
        self._build_symbolic_tab(side_panel)

    def _build_toolbar(self, parent):
        toolbar = ttk.Frame(parent, padding=(14, 12), style="Toolbar.TFrame")
        toolbar.pack(fill=tk.X)

        title_frame = ttk.Frame(toolbar, style="Toolbar.TFrame")
        title_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14))
        ttk.Label(title_frame, text="Graph Drawer", font=("Segoe UI", 13, "bold"), background="#f6f7fb", foreground="#111827").pack(anchor=tk.W)
        ttk.Label(title_frame, text="绘图与图论标注", font=("Segoe UI", 8), background="#f6f7fb", foreground="#6b7280").pack(anchor=tk.W)

        mode_frame = ttk.Labelframe(toolbar, text="工具", style="Section.TLabelframe", padding=(10, 8))
        mode_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        for label, value in MODE_OPTIONS:
            ttk.Radiobutton(
                mode_frame,
                text=label,
                value=value,
                variable=self.mode,
                command=self._update_status,
            ).pack(side=tk.LEFT, padx=(0, 8))

        action_frame = ttk.Labelframe(toolbar, text="常用", style="Section.TLabelframe", padding=(10, 8))
        action_frame.pack(side=tk.RIGHT, fill=tk.Y)
        ttk.Checkbutton(action_frame, text="点标签", variable=self.show_node_labels, command=self.draw_canvas).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Checkbutton(action_frame, text="边标签", variable=self.show_edge_labels, command=self.draw_canvas).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(action_frame, text="撤销", width=7, command=self.undo).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(action_frame, text="删除所选", command=self.delete_selection).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(action_frame, text="TikZ", width=7, command=self.export_tikz).pack(side=tk.LEFT)

    def _add_color_control(self, parent, label, color, command):
        swatch = tk.Label(
            parent,
            width=2,
            height=1,
            bg=color,
            relief=tk.SOLID,
            bd=1,
            cursor="hand2",
        )
        swatch.pack(side=tk.LEFT, padx=(0, 3))
        swatch.bind("<Button-1>", lambda event: command())
        ttk.Button(parent, text=label, width=5, command=command).pack(side=tk.LEFT, padx=(0, 6))
        return swatch

    def _update_color_swatch(self, swatch, color):
        if swatch is not None and swatch.winfo_exists():
            swatch.configure(bg=color)

    def _build_style_tab(self, notebook):
        outer = ttk.Frame(notebook, padding=0, style="Panel.TFrame")
        notebook.add(outer, text="样式")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        style_canvas = tk.Canvas(outer, width=276, height=520, highlightthickness=0, bg="#fbfcfe")
        style_scroll = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=style_canvas.yview)
        style_canvas.configure(yscrollcommand=style_scroll.set)
        style_canvas.grid(row=0, column=0, sticky=tk.NSEW)
        style_scroll.grid(row=0, column=1, sticky=tk.NS)

        tab = ttk.Frame(style_canvas, padding=12, style="Panel.TFrame")
        content_window = style_canvas.create_window((0, 0), window=tab, anchor=tk.NW)
        tab.bind(
            "<Configure>",
            lambda event: style_canvas.configure(scrollregion=style_canvas.bbox("all")),
        )
        style_canvas.bind(
            "<Configure>",
            lambda event: style_canvas.itemconfigure(content_window, width=event.width),
        )
        tab.columnconfigure(0, weight=1)

        node_frame = ttk.Labelframe(tab, text="点", style="Section.TLabelframe", padding=10)
        node_frame.grid(row=0, column=0, sticky=tk.EW, pady=(0, 10))
        node_frame.columnconfigure(1, weight=1)
        self.node_fill_swatch = self._add_color_row(node_frame, 0, "内部颜色", self.node_color, self.choose_node_color)
        self.node_outline_swatch = self._add_color_row(node_frame, 1, "边缘颜色", self.node_outline_color, self.choose_node_outline_color)
        self.node_label_swatch = self._add_color_row(node_frame, 2, "标签颜色", self.node_label_color, self.choose_node_label_color)
        ttk.Label(node_frame, text="点大小").grid(row=3, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(node_frame, from_=6, to=60, width=8, textvariable=self.node_radius).grid(row=3, column=1, sticky=tk.W, pady=4)
        ttk.Label(node_frame, text="标签字号").grid(row=4, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(node_frame, from_=6, to=48, width=8, textvariable=self.node_label_size).grid(row=4, column=1, sticky=tk.W, pady=4)
        ttk.Label(node_frame, text="标签位置").grid(row=5, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(
            node_frame,
            width=8,
            state="readonly",
            textvariable=self.node_label_position,
            values=[label for _, label in NODE_LABEL_POSITIONS],
        ).grid(row=5, column=1, sticky=tk.W, pady=4)

        edge_frame = ttk.Labelframe(tab, text="边", style="Section.TLabelframe", padding=10)
        edge_frame.grid(row=1, column=0, sticky=tk.EW, pady=(0, 10))
        edge_frame.columnconfigure(1, weight=1)
        self.edge_swatch = self._add_color_row(edge_frame, 0, "颜色", self.edge_color, self.choose_edge_color)
        self.edge_label_swatch = self._add_color_row(edge_frame, 1, "标签颜色", self.edge_label_color, self.choose_edge_label_color)
        ttk.Label(edge_frame, text="线宽").grid(row=2, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(edge_frame, from_=1, to=12, increment=0.5, width=8, textvariable=self.edge_width).grid(row=2, column=1, sticky=tk.W, pady=4)
        ttk.Label(edge_frame, text="标签字号").grid(row=3, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(edge_frame, from_=6, to=48, width=8, textvariable=self.edge_label_size).grid(row=3, column=1, sticky=tk.W, pady=4)
        ttk.Label(edge_frame, text="线型").grid(row=4, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(
            edge_frame,
            width=8,
            state="readonly",
            textvariable=self.edge_style,
            values=[label for _, label in EDGE_STYLES],
        ).grid(row=4, column=1, sticky=tk.W, pady=4)
        ttk.Checkbutton(edge_frame, text="有向边", variable=self.directed).grid(row=5, column=1, sticky=tk.W, pady=(4, 0))

        text_frame = ttk.Labelframe(tab, text="文字", style="Section.TLabelframe", padding=10)
        text_frame.grid(row=2, column=0, sticky=tk.EW, pady=(0, 10))
        text_frame.columnconfigure(1, weight=1)
        self.text_swatch = self._add_color_row(text_frame, 0, "颜色", self.text_color, self.choose_text_color)
        ttk.Label(text_frame, text="字号").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(text_frame, from_=8, to=48, width=8, textvariable=self.text_size).grid(row=1, column=1, sticky=tk.W, pady=4)

        pencil_frame = ttk.Labelframe(tab, text="铅笔", style="Section.TLabelframe", padding=10)
        pencil_frame.grid(row=3, column=0, sticky=tk.EW, pady=(0, 10))
        pencil_frame.columnconfigure(1, weight=1)
        self.pencil_swatch = self._add_color_row(pencil_frame, 0, "颜色", self.pencil_color, self.choose_pencil_color)
        ttk.Label(pencil_frame, text="线宽").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(pencil_frame, from_=1, to=16, increment=0.5, width=8, textvariable=self.pencil_width).grid(row=1, column=1, sticky=tk.W, pady=4)

        region_frame = ttk.Labelframe(tab, text="区域", style="Section.TLabelframe", padding=10)
        region_frame.grid(row=4, column=0, sticky=tk.EW)
        region_frame.columnconfigure(1, weight=1)
        self.region_swatch = self._add_color_row(region_frame, 0, "颜色", self.shadow_color, self.choose_shadow_color)
        ttk.Label(region_frame, text="透明度").grid(row=1, column=0, sticky=tk.W, pady=4)
        ttk.Spinbox(region_frame, from_=0.1, to=0.8, increment=0.05, width=8, textvariable=self.region_alpha).grid(row=1, column=1, sticky=tk.W, pady=4)
        ttk.Label(region_frame, text="形状").grid(row=2, column=0, sticky=tk.W, pady=4)
        ttk.Combobox(
            region_frame,
            width=8,
            state="readonly",
            textvariable=self.region_shape,
            values=[label for _, label in REGION_SHAPES],
        ).grid(row=2, column=1, sticky=tk.W, pady=4)

    def _add_color_row(self, parent, row, label, color, command):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky=tk.W, pady=4)
        color_frame = ttk.Frame(parent, style="Panel.TFrame")
        color_frame.grid(row=row, column=1, sticky=tk.W, pady=4)
        swatch = tk.Label(color_frame, width=3, height=1, bg=color, relief=tk.SOLID, bd=1, cursor="hand2")
        swatch.pack(side=tk.LEFT, padx=(0, 6))
        swatch.bind("<Button-1>", lambda event: command())
        ttk.Button(color_frame, text="选择", width=6, command=command).pack(side=tk.LEFT)
        return swatch

    def _build_background_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=14, style="Panel.TFrame")
        notebook.add(tab, text="背景")

        ttk.Label(tab, text="背景类型").grid(row=0, column=0, sticky=tk.W, pady=(0, 4))
        mode_frame = ttk.Frame(tab, style="Panel.TFrame")
        mode_frame.grid(row=1, column=0, sticky=tk.EW, pady=(0, 12))
        for value, label in BACKGROUND_MODES:
            ttk.Radiobutton(
                mode_frame,
                text=label,
                value=value,
                variable=self.background,
                command=self.draw_canvas,
            ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(tab, text="间距 / 比例尺").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(tab, textvariable=self.axis_scale).grid(row=3, column=0, sticky=tk.EW, pady=(3, 10))

        origin_frame = ttk.Frame(tab, style="Panel.TFrame")
        origin_frame.grid(row=4, column=0, sticky=tk.EW)
        ttk.Label(origin_frame, text="原点 X").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(origin_frame, width=8, textvariable=self.axis_origin_x).grid(row=0, column=1, sticky=tk.W, padx=(6, 16))
        ttk.Label(origin_frame, text="Y").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(origin_frame, width=8, textvariable=self.axis_origin_y).grid(row=0, column=3, sticky=tk.W, padx=(6, 0))

        ttk.Button(tab, text="应用背景设置", command=self.apply_background_settings).grid(row=5, column=0, sticky=tk.EW, pady=(14, 0))
        tab.columnconfigure(0, weight=1)

    def _build_export_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=14, style="Panel.TFrame")
        notebook.add(tab, text="导出")

        buttons = [
            ("导出 PNG", lambda: self.export_image("png")),
            ("导出 PDF", lambda: self.export_image("pdf")),
            ("TikZ 预览 / 复制", self.export_tikz),
        ]
        for row, (label, command) in enumerate(buttons):
            ttk.Button(tab, text=label, command=command).grid(row=row, column=0, sticky=tk.EW, pady=4)
        tab.columnconfigure(0, weight=1)

    def _build_matrix_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=10, style="Panel.TFrame")
        notebook.add(tab, text="矩阵")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)

        action_bar = ttk.Frame(tab, style="Panel.TFrame")
        action_bar.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))
        ttk.Button(action_bar, text="刷新显示", command=self.show_matrices).pack(side=tk.LEFT)
        ttk.Button(action_bar, text="保存矩阵", command=self.export_matrices).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Checkbutton(
            action_bar,
            text="行列标签",
            variable=self.matrix_show_labels,
            command=self.show_matrices,
        ).pack(side=tk.RIGHT)

        matrix_frame = ttk.Frame(tab, style="Panel.TFrame")
        matrix_frame.grid(row=1, column=0, sticky=tk.NSEW)
        matrix_frame.columnconfigure(0, weight=1)
        matrix_frame.rowconfigure(0, weight=1)
        self.matrix_text = tk.Text(matrix_frame, width=32, height=24, wrap=tk.NONE, relief=tk.FLAT, bg="#ffffff")
        y_scroll = ttk.Scrollbar(matrix_frame, orient=tk.VERTICAL, command=self.matrix_text.yview)
        x_scroll = ttk.Scrollbar(matrix_frame, orient=tk.HORIZONTAL, command=self.matrix_text.xview)
        self.matrix_text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.matrix_text.grid(row=0, column=0, sticky=tk.NSEW)
        y_scroll.grid(row=0, column=1, sticky=tk.NS)
        x_scroll.grid(row=1, column=0, sticky=tk.EW)
        self.matrix_text.insert(tk.END, "点击 [刷新显示] 以查看当前图的邻接矩阵与关联矩阵。")

    def _build_symbolic_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=12, style="Panel.TFrame")
        notebook.add(tab, text="符号计算")
        tab.columnconfigure(0, weight=1)

        ttk.Label(
            tab,
            text="按所选配置组对当前图 G 执行符号递归，计算 f(G)。",
            wraplength=250,
            justify=tk.LEFT,
        ).grid(row=0, column=0, sticky=tk.EW, pady=(0, 10))
        ttk.Label(tab, text="配置组").grid(row=1, column=0, sticky=tk.W)
        ttk.Combobox(
            tab,
            textvariable=self.symbolic_config,
            values=self.symbolic_config_keys,
            state="readonly",
        ).grid(row=2, column=0, sticky=tk.EW, pady=(2, 8))
        ttk.Button(tab, text="计算 f(G)", command=self.open_symbolic_calculator).grid(row=3, column=0, sticky=tk.EW, pady=4)
        ttk.Button(tab, text="重新计算并打开步骤窗口", command=self.open_symbolic_calculator).grid(row=4, column=0, sticky=tk.EW, pady=4)

        hint = (
            "配置组来自 graph_symbolic_config.py；步骤窗口会按当前配置中的操作项显示子图。"
        )
        ttk.Label(tab, text=hint, wraplength=250, justify=tk.LEFT, foreground="#6b7280").grid(row=5, column=0, sticky=tk.EW, pady=(12, 0))

    def open_symbolic_calculator(self):
        graph = self._symbolic_graph_from_current()
        config_key = self.symbolic_config.get()
        try:
            calculator = DeletionContractionCalculator(
                max_steps=120000,
                use_memo=False,
                config_key=config_key,
            )
            result = calculator.calculate(graph)
        except SymbolicComputationLimit as exc:
            messagebox.showwarning("符号计算过大", str(exc), parent=self.root)
            return
        except ValueError as exc:
            messagebox.showwarning("符号计算配置错误", str(exc), parent=self.root)
            return

        self.symbolic_result = result
        self.symbolic_step_by_id = {step.id: step for step in result.steps}
        self.symbolic_selected_step = result.root
        self._open_symbolic_result_window(result)

    def _symbolic_graph_from_current(self):
        vertices = []
        for index, node in enumerate(self.nodes):
            label = node.label.strip() if getattr(node, "label", "") else str(index + 1)
            vertices.append(
                SymbolicVertex(
                    id=node.id,
                    label=label,
                    x=float(node.x),
                    y=float(node.y),
                    members=(label,),
                )
            )

        edges = []
        for index, edge in enumerate(self.edges):
            label = edge.label.strip() if getattr(edge, "label", "") else self._edge_auto_label(index)
            edges.append(
                SymbolicEdge(
                    id=edge.id,
                    source=edge.source,
                    target=edge.target,
                    label=label,
                )
            )
        return SymbolicGraph(vertices=tuple(vertices), edges=tuple(edges))

    def _open_symbolic_result_window(self, result):
        old_window = self.symbolic_ui.get("window")
        if old_window is not None and old_window.winfo_exists():
            old_window.destroy()

        dialog = tk.Toplevel(self.root)
        dialog.title("符号计算 f(G)")
        dialog.geometry("1120x760")
        dialog.transient(self.root)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        paned = ttk.Panedwindow(dialog, orient=tk.HORIZONTAL)
        paned.grid(row=0, column=0, sticky=tk.NSEW)

        left = ttk.Frame(paned, padding=10)
        right = ttk.Frame(paned, padding=10)
        paned.add(left, weight=0)
        paned.add(right, weight=1)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        ttk.Label(left, text="递归步骤", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, 6))
        tree_frame = ttk.Frame(left)
        tree_frame.grid(row=1, column=0, sticky=tk.NSEW)
        tree_frame.columnconfigure(0, weight=1)
        tree_frame.rowconfigure(0, weight=1)
        tree = ttk.Treeview(tree_frame, columns=("edge", "poly"), show="tree headings", height=28)
        tree.heading("#0", text="步骤")
        tree.heading("edge", text="选边")
        tree.heading("poly", text="f")
        tree.column("#0", width=120, stretch=True)
        tree.column("edge", width=56, anchor=tk.CENTER, stretch=False)
        tree.column("poly", width=160, stretch=True)
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.grid(row=0, column=0, sticky=tk.NSEW)
        tree_scroll.grid(row=0, column=1, sticky=tk.NS)

        ttk.Label(
            left,
            text=f"总步骤：{len(result.steps)}",
            foreground="#6b7280",
        ).grid(row=2, column=0, sticky=tk.W, pady=(8, 0))

        final_text = tk.Text(right, height=5, wrap=tk.WORD, relief=tk.FLAT, bg="#ffffff")
        final_text.grid(row=0, column=0, sticky=tk.EW, pady=(0, 8))

        visual_frame = ttk.Frame(right)
        visual_frame.grid(row=1, column=0, sticky=tk.NSEW)
        max_branch_count = max((len(step.branches) for step in result.steps), default=0)
        panel_count = max(1, 1 + max_branch_count)
        for column in range(panel_count):
            visual_frame.columnconfigure(column, weight=1)
        visual_frame.rowconfigure(1, weight=1)

        panel_width = 250 if panel_count <= 3 else 190
        canvases = []
        canvas_labels = []
        for column in range(panel_count):
            label = ttk.Label(visual_frame, text="", font=("Segoe UI", 9, "bold"))
            label.grid(row=0, column=column, sticky=tk.W)
            canvas = tk.Canvas(
                visual_frame,
                width=panel_width,
                height=220,
                bg="#ffffff",
                highlightthickness=1,
                highlightbackground="#d9e0ea",
            )
            canvas.grid(row=1, column=column, sticky=tk.NSEW, padx=(0 if column == 0 else 8, 0), pady=(4, 8))
            canvas_labels.append(label)
            canvases.append(canvas)

        poly_text = tk.Text(visual_frame, height=9, wrap=tk.WORD, relief=tk.FLAT, bg="#ffffff")
        poly_text.grid(row=2, column=0, columnspan=panel_count, sticky=tk.EW)

        substitution = ttk.Labelframe(right, text="代入计算", padding=8)
        substitution.grid(row=2, column=0, sticky=tk.EW, pady=(8, 0))
        for column in range(8):
            substitution.columnconfigure(column, weight=1 if column == 7 else 0)
        a_var = tk.StringVar()
        b_var = tk.StringVar()
        h_var = tk.StringVar()
        ttk.Label(substitution, text="a=").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(substitution, width=10, textvariable=a_var).grid(row=0, column=1, sticky=tk.W, padx=(2, 10))
        ttk.Label(substitution, text="b=").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(substitution, width=10, textvariable=b_var).grid(row=0, column=3, sticky=tk.W, padx=(2, 10))
        ttk.Label(substitution, text="h=").grid(row=0, column=4, sticky=tk.W)
        ttk.Entry(substitution, width=10, textvariable=h_var).grid(row=0, column=5, sticky=tk.W, padx=(2, 10))
        ttk.Button(substitution, text="计算", command=self._evaluate_symbolic_substitution).grid(row=0, column=6, sticky=tk.W)
        ttk.Button(substitution, text="清空", command=self._clear_symbolic_substitution).grid(row=0, column=7, sticky=tk.W, padx=(8, 0))
        substitution_text = tk.Text(substitution, height=5, wrap=tk.WORD, relief=tk.FLAT, bg="#ffffff")
        substitution_text.grid(row=1, column=0, columnspan=8, sticky=tk.EW, pady=(8, 0))

        export_bar = ttk.Frame(right)
        export_bar.grid(row=3, column=0, sticky=tk.EW, pady=(10, 0))
        ttk.Button(export_bar, text="导出当前步骤 PNG", command=lambda: self._export_symbolic_image("png")).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(export_bar, text="导出当前步骤 PDF", command=lambda: self._export_symbolic_image("pdf")).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(export_bar, text="TikZ 预览 / 复制", command=self._export_symbolic_tikz).pack(side=tk.LEFT)

        self.symbolic_ui = {
            "window": dialog,
            "tree": tree,
            "final_text": final_text,
            "canvas_labels": canvas_labels,
            "canvases": canvases,
            "panel_count": panel_count,
            "poly_text": poly_text,
            "visual_frame": visual_frame,
            "export_widget": right,
            "a_var": a_var,
            "b_var": b_var,
            "h_var": h_var,
            "substitution_text": substitution_text,
        }

        self._populate_symbolic_tree(tree, result.root)
        tree.bind("<<TreeviewSelect>>", self._on_symbolic_tree_select)
        tree.selection_set(str(result.root.id))
        tree.focus(str(result.root.id))
        self._render_symbolic_step(result.root)

    def _populate_symbolic_tree(self, tree, step, parent="", incoming_branch=None):
        if step.base_case:
            text = f"步骤 {step.id}: 基础"
            edge_text = "-"
        elif step.memo_hit:
            text = f"步骤 {step.id}: 复用"
            edge_text = "-"
        else:
            text = f"步骤 {step.id}: 展开"
            edge_text = step.edge.label
        if incoming_branch is not None:
            text = f"{self._symbolic_operation_title(incoming_branch.operation)} -> {text}"

        iid = str(step.id)
        tree.insert(parent, tk.END, iid=iid, text=text, values=(edge_text, step.polynomial.short_string()))
        if step.depth < 2:
            tree.item(iid, open=True)
        for branch in step.branches:
            self._populate_symbolic_tree(tree, branch.child, iid, incoming_branch=branch)

    def _on_symbolic_tree_select(self, event=None):
        tree = self.symbolic_ui.get("tree")
        if tree is None:
            return
        selection = tree.selection()
        if not selection:
            return
        step = self.symbolic_step_by_id.get(int(selection[0]))
        if step is None:
            return
        self.symbolic_selected_step = step
        self._render_symbolic_step(step)

    def _render_symbolic_step(self, step):
        if not self.symbolic_ui:
            return

        final_text = (
            f"最终化简结果：f(G) = {self.symbolic_result.polynomial}\n"
            f"SymPy：{self.symbolic_result.polynomial.sympy_string()}\n"
            f"当前步骤：f(G_step) = {step.polynomial}\n"
            f"当前步骤 SymPy：{step.polynomial.sympy_string()}"
        )
        self._set_text_widget(self.symbolic_ui["final_text"], final_text)

        canvas_labels = self.symbolic_ui["canvas_labels"]
        canvases = self.symbolic_ui["canvases"]
        highlight_id = step.edge.id if step.edge is not None else None
        panels = [("当前 G", step.graph, highlight_id)]
        panels.extend(
            (
                self._symbolic_branch_panel_title(branch),
                branch.graph,
                None,
            )
            for branch in step.branches
        )
        for index, (label, canvas) in enumerate(zip(canvas_labels, canvases)):
            if index < len(panels):
                title, graph, panel_highlight_id = panels[index]
                label.configure(text=title)
                label.grid()
                canvas.grid()
                self._draw_symbolic_graph_canvas(
                    canvas,
                    graph,
                    highlight_edge_id=panel_highlight_id,
                )
            else:
                label.grid_remove()
                canvas.grid_remove()

        self._set_text_widget(self.symbolic_ui["poly_text"], self._symbolic_step_text(step))
        self._evaluate_symbolic_substitution()

    def _symbolic_step_text(self, step):
        if step.base_case:
            rule = step.initial_rule
            rule_title = rule.title if rule is not None else "基础规则"
            return (
                f"基础情形：命中 {rule_title}。\n"
                f"f(G) = {step.polynomial}\n"
                f"SymPy：{step.polynomial.sympy_string()}"
            )
        if step.memo_hit:
            return (
                f"该图结构已计算过，直接复用：\n"
                f"f(G) = {step.polynomial}\n"
                f"SymPy：{step.polynomial.sympy_string()}"
            )
        lines = [
            f"选择边 e = {step.edge.label}，连接 {self._symbolic_vertex_label(step.graph, step.edge.source)} "
            f"与 {self._symbolic_vertex_label(step.graph, step.edge.target)}。"
        ]
        if step.flow is not None:
            lines.append(f"命中流程：{step.flow.title} ({step.flow.key})")
        for branch in step.branches:
            operation_title = self._symbolic_operation_title(branch.operation)
            contribution = branch.weighted_polynomial
            lines.extend(
                [
                    "",
                    f"{operation_title}：子图 f = {branch.polynomial}",
                    f"{operation_title} 系数：{branch.coefficient}",
                    f"{operation_title} 贡献：{contribution}",
                    f"{operation_title} SymPy：{branch.polynomial.sympy_string()}",
                ]
            )
        formula = self._symbolic_step_formula_text(step)
        lines.extend(
            [
                "",
                f"因此：f(G) = {formula} = {step.polynomial}",
                f"因此 SymPy：{step.polynomial.sympy_string()}",
            ]
        )
        return "\n".join(lines)

    def _symbolic_operation_title(self, operation):
        title = getattr(operation, "title", "") or getattr(operation, "key", "")
        return title or "操作"

    def _symbolic_branch_panel_title(self, branch):
        operation_title = self._symbolic_operation_title(branch.operation)
        return f"{operation_title}: {branch.coefficient}·f"

    def _symbolic_branch_formula_text(self, branch):
        return branch.operation.formula_text(str(branch.polynomial), branch.coefficient)

    def _symbolic_step_formula_text(self, step):
        if not step.branches:
            return str(step.polynomial)
        return " + ".join(self._symbolic_branch_formula_text(branch) for branch in step.branches)

    def _symbolic_vertex_label(self, graph, vertex_id):
        try:
            return graph.vertex_by_id(vertex_id).label
        except StopIteration:
            return str(vertex_id)

    def _evaluate_symbolic_substitution(self):
        if not self.symbolic_ui or self.symbolic_selected_step is None:
            return
        substitutions = {
            "a": self.symbolic_ui["a_var"].get(),
            "b": self.symbolic_ui["b_var"].get(),
            "h": self.symbolic_ui["h_var"].get(),
        }
        final_value = self.symbolic_result.polynomial.substitute(substitutions)
        step = self.symbolic_selected_step
        lines = [
            f"最终结果代入：{final_value}",
            f"当前步骤 f(G) 代入：{step.polynomial.substitute(substitutions)}",
        ]
        for branch in step.branches:
            operation_title = self._symbolic_operation_title(branch.operation)
            child_value = branch.polynomial.substitute(substitutions)
            contribution_value = branch.weighted_polynomial.substitute(substitutions)
            lines.append(f"{operation_title} 子图代入：{child_value}")
            lines.append(f"{operation_title} 贡献代入：{contribution_value}")
        text = "\n".join(lines)
        self._set_text_widget(self.symbolic_ui["substitution_text"], text)

    def _clear_symbolic_substitution(self):
        if not self.symbolic_ui:
            return
        self.symbolic_ui["a_var"].set("")
        self.symbolic_ui["b_var"].set("")
        self.symbolic_ui["h_var"].set("")
        self._evaluate_symbolic_substitution()

    def _set_text_widget(self, widget, text):
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state=tk.DISABLED)

    def _draw_symbolic_graph_canvas(self, canvas, graph, highlight_edge_id=None):
        canvas.delete("all")
        width = int(canvas.winfo_width() or canvas["width"])
        height = int(canvas.winfo_height() or canvas["height"])
        if graph is None:
            canvas.create_text(width / 2, height / 2, text="无", fill="#9ca3af", font=("Segoe UI", 12))
            return
        if not graph.vertices and not graph.edges:
            canvas.create_text(width / 2, height / 2, text="空图", fill="#9ca3af", font=("Segoe UI", 12))
            return

        positions = self._symbolic_canvas_positions(graph, width, height)
        edge_groups = self._symbolic_edge_group_indices(graph.edges)
        for edge in graph.edges:
            source = positions.get(edge.source)
            target = positions.get(edge.target)
            if source is None or target is None:
                continue
            is_highlighted = edge.id == highlight_edge_id
            color = "#dc2626" if is_highlighted else "#4b5563"
            line_width = 3 if is_highlighted else 1.7
            group_index, group_count = edge_groups.get(edge.id, (0, 1))
            self._draw_symbolic_canvas_edge(canvas, source, target, edge, color, line_width, group_index, group_count)

        for vertex in graph.vertices:
            x, y = positions[vertex.id]
            canvas.create_oval(x - 9, y - 9, x + 9, y + 9, fill="#ffffff", outline="#111827", width=1.6)
            canvas.create_text(x, y - 18, text=vertex.label, fill="#111827", font=("Segoe UI", 9, "bold"))

    def _draw_symbolic_canvas_edge(self, canvas, source, target, edge, color, line_width, group_index, group_count):
        x0, y0 = source
        x1, y1 = target
        if edge.source == edge.target:
            grow = group_index * 12
            canvas.create_oval(
                x0 + 5 + grow,
                y0 - 35 - grow,
                x0 + 42 + grow,
                y0 + 2 + grow,
                outline=color,
                width=line_width,
            )
            canvas.create_text(
                x0 + 43 + grow,
                y0 - 29 - grow,
                text=edge.label,
                fill=color,
                font=("Cambria", 9, "italic"),
            )
            return

        dx = x1 - x0
        dy = y1 - y0
        distance = math.hypot(dx, dy) or 1
        nx = -dy / distance
        ny = dx / distance
        offset = self._parallel_edge_offset(group_index, group_count, 22)
        if abs(offset) > 0.01:
            mx = (x0 + x1) / 2 + nx * offset
            my = (y0 + y1) / 2 + ny * offset
            canvas.create_line(x0, y0, mx, my, x1, y1, fill=color, width=line_width, smooth=True, splinesteps=16)
            label_x, label_y = mx + nx * 12, my + ny * 12
        else:
            canvas.create_line(x0, y0, x1, y1, fill=color, width=line_width)
            label_x, label_y = (x0 + x1) / 2 + nx * 12, (y0 + y1) / 2 + ny * 12
        canvas.create_text(label_x, label_y, text=edge.label, fill=color, font=("Cambria", 9, "italic"))

    def _symbolic_canvas_positions(self, graph, width, height):
        if not graph.vertices:
            return {}
        xs = [vertex.x for vertex in graph.vertices]
        ys = [vertex.y for vertex in graph.vertices]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(1.0, max_x - min_x)
        span_y = max(1.0, max_y - min_y)
        margin = 38
        positions = {}
        for vertex in graph.vertices:
            if len(graph.vertices) == 1:
                x = width / 2
                y = height / 2
            else:
                x = margin + (vertex.x - min_x) / span_x * max(1, width - margin * 2)
                y = margin + (vertex.y - min_y) / span_y * max(1, height - margin * 2)
            positions[vertex.id] = (x, y)
        return positions

    def _symbolic_edge_group_indices(self, edges):
        groups = {}
        for edge in edges:
            key = tuple(sorted((edge.source, edge.target))) if edge.source != edge.target else ("loop", edge.source)
            groups.setdefault(key, []).append(edge)
        indices = {}
        for members in groups.values():
            for index, edge in enumerate(sorted(members, key=lambda item: item.id)):
                indices[edge.id] = (index, len(members))
        return indices

    def _export_symbolic_image(self, fmt):
        if ImageGrab is None:
            messagebox.showwarning("缺少依赖", "导出图片需要安装 Pillow。")
            return
        frame = self.symbolic_ui.get("export_widget") or self.symbolic_ui.get("visual_frame")
        if frame is None or not frame.winfo_exists():
            return
        path = filedialog.asksaveasfilename(
            parent=self.symbolic_ui.get("window"),
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("所有文件", "*.*")],
        )
        if not path:
            return
        frame.update_idletasks()
        bbox = (
            frame.winfo_rootx(),
            frame.winfo_rooty(),
            frame.winfo_rootx() + frame.winfo_width(),
            frame.winfo_rooty() + frame.winfo_height(),
        )
        try:
            image = ImageGrab.grab(bbox)
            if fmt.lower() == "png":
                image.save(path, "PNG")
            else:
                image.save(path, "PDF", resolution=300)
            messagebox.showinfo("导出成功", f"已导出 {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("导出失败", f"图片导出失败：{exc}")

    def _export_symbolic_tikz(self):
        if self.symbolic_selected_step is None:
            return
        tikz = self._symbolic_step_tikz(self.symbolic_selected_step)
        dialog = tk.Toplevel(self.symbolic_ui.get("window") or self.root)
        dialog.title("符号计算 TikZ")
        dialog.geometry("820x560")
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        text_widget = tk.Text(dialog, wrap=tk.NONE, undo=True, font=("Consolas", 10), bg="#fbfbfb", relief=tk.FLAT)
        y_scroll = ttk.Scrollbar(dialog, orient=tk.VERTICAL, command=text_widget.yview)
        x_scroll = ttk.Scrollbar(dialog, orient=tk.HORIZONTAL, command=text_widget.xview)
        text_widget.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        text_widget.grid(row=0, column=0, sticky=tk.NSEW, padx=(12, 0), pady=(12, 0))
        y_scroll.grid(row=0, column=1, sticky=tk.NS, pady=(12, 0))
        x_scroll.grid(row=1, column=0, sticky=tk.EW, padx=(12, 0))
        text_widget.insert("1.0", tikz)

        button_frame = ttk.Frame(dialog, padding=12)
        button_frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW)
        ttk.Button(button_frame, text="复制到剪贴板", command=lambda: self._copy_tikz_from_widget(text_widget)).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="保存为 .tex", command=lambda: self._save_tikz_from_widget(text_widget)).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(button_frame, text="关闭", command=dialog.destroy).pack(side=tk.RIGHT)

    def _symbolic_step_tikz(self, step):
        lines = [
            "% Symbolic operation step generated by Graph Drawer",
            "\\begin{tikzpicture}[x=1cm, y=1cm]",
            (
                "\\node[anchor=west, font=\\small\\bfseries] at (0,0.45) "
                f"{{Final: $f(G)={self._latex_polynomial(str(self.symbolic_result.polynomial))}$}};"
            ),
            (
                "\\node[anchor=west, font=\\scriptsize\\ttfamily] at (0,0.15) "
                f"{{SymPy: {self._latex_escape_tikz(self.symbolic_result.polynomial.sympy_string())}}};"
            ),
        ]
        panels = [
            ("Current $G$", step.graph, step.edge.id if step.edge else None, step.polynomial),
        ]
        panels.extend(
            (
                self._latex_escape_tikz(self._symbolic_branch_panel_title(branch)),
                branch.graph,
                None,
                branch.polynomial,
            )
            for branch in step.branches
        )
        for index, (title, graph, highlight_edge_id, polynomial) in enumerate(panels):
            x_shift = index * 5.1
            lines.append(f"\\begin{{scope}}[shift={{({self._fmt_tikz(x_shift)},0)}}]")
            lines.append(f"\\node[font=\\small\\bfseries] at (1.8,0) {{{title}}};")
            if graph is None:
                lines.append("\\node[font=\\small, color=gray] at (1.8,-1.8) {N/A};")
            elif not graph.vertices and not graph.edges:
                lines.append("\\node[font=\\small, color=gray] at (1.8,-1.8) {Empty graph};")
            else:
                lines.extend(self._symbolic_graph_tikz_lines(graph, highlight_edge_id))
            if polynomial is not None:
                lines.append(
                    "\\node[anchor=north west, text width=4.5cm, font=\\scriptsize] "
                    f"at (0,-3.8) {{$f={self._latex_polynomial(str(polynomial))}$}};"
                )
                lines.append(
                    "\\node[anchor=north west, text width=4.5cm, font=\\tiny\\ttfamily] "
                    f"at (0,-4.18) {{SymPy: {self._latex_escape_tikz(polynomial.sympy_string())}}};"
                )
            lines.append("\\end{scope}")
        if step.edge is not None:
            formula = self._latex_polynomial(self._symbolic_step_formula_text(step))
            lines.append(
                "\\node[anchor=west, font=\\scriptsize] at (0,-4.85) "
                f"{{Chosen edge: ${self._latex_escape_tikz(step.edge.label)}$, "
                f"$f(G)={formula}={self._latex_polynomial(str(step.polynomial))}$}};"
            )
            lines.append(
                "\\node[anchor=west, font=\\tiny\\ttfamily] at (0,-5.18) "
                f"{{SymPy: {self._latex_escape_tikz(step.polynomial.sympy_string())}}};"
            )
        lines.append("\\end{tikzpicture}")
        return "\n".join(lines)

    def _symbolic_graph_tikz_lines(self, graph, highlight_edge_id=None):
        positions = self._symbolic_tikz_positions(graph)
        edge_groups = self._symbolic_edge_group_indices(graph.edges)
        lines = []
        for edge in graph.edges:
            source = positions.get(edge.source)
            target = positions.get(edge.target)
            if source is None or target is None:
                continue
            color = "red!75!black" if edge.id == highlight_edge_id else "gray!70!black"
            width = "0.9pt" if edge.id == highlight_edge_id else "0.55pt"
            group_index, group_count = edge_groups.get(edge.id, (0, 1))
            if edge.source == edge.target:
                x, y = source
                grow = group_index * 0.16
                radius = 0.25 + group_index * 0.06
                lines.append(
                    f"\\draw[draw={color}, line width={width}] "
                    f"({self._fmt_tikz(x + 0.22 + grow)},{self._fmt_tikz(y + 0.14 + grow)}) "
                    f"circle[radius={self._fmt_tikz(radius)}];"
                )
                lines.append(
                    f"\\node[font=\\tiny, text={color}] at ({self._fmt_tikz(x + 0.52 + grow)},{self._fmt_tikz(y + 0.42 + grow)}) "
                    f"{{{self._latex_escape_tikz(edge.label)}}};"
                )
                continue

            x0, y0 = source
            x1, y1 = target
            offset = self._parallel_edge_offset(group_index, group_count, 0.32)
            if abs(offset) > 0.01:
                dx = x1 - x0
                dy = y1 - y0
                distance = math.hypot(dx, dy) or 1
                nx = -dy / distance
                ny = dx / distance
                mx = (x0 + x1) / 2 + nx * offset
                my = (y0 + y1) / 2 + ny * offset
                lines.append(
                    f"\\draw[draw={color}, line width={width}] "
                    f"({self._fmt_tikz(x0)},{self._fmt_tikz(y0)}) .. controls "
                    f"({self._fmt_tikz(mx)},{self._fmt_tikz(my)}) .. "
                    f"({self._fmt_tikz(x1)},{self._fmt_tikz(y1)});"
                )
                label_x, label_y = mx, my + 0.16
            else:
                lines.append(
                    f"\\draw[draw={color}, line width={width}] "
                    f"({self._fmt_tikz(x0)},{self._fmt_tikz(y0)}) -- ({self._fmt_tikz(x1)},{self._fmt_tikz(y1)});"
                )
                label_x, label_y = (x0 + x1) / 2, (y0 + y1) / 2 + 0.16
            lines.append(
                f"\\node[font=\\tiny, text={color}, fill=white, inner sep=0.5pt] "
                f"at ({self._fmt_tikz(label_x)},{self._fmt_tikz(label_y)}) "
                f"{{{self._latex_escape_tikz(edge.label)}}};"
            )

        for vertex in graph.vertices:
            x, y = positions[vertex.id]
            lines.append(
                f"\\node[circle, draw=black, fill=white, inner sep=1pt, minimum size=8pt, font=\\tiny] "
                f"at ({self._fmt_tikz(x)},{self._fmt_tikz(y)}) {{{self._latex_escape_tikz(vertex.label)}}};"
            )
        return lines

    def _symbolic_tikz_positions(self, graph):
        if not graph.vertices:
            return {}
        xs = [vertex.x for vertex in graph.vertices]
        ys = [vertex.y for vertex in graph.vertices]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(1.0, max_x - min_x)
        span_y = max(1.0, max_y - min_y)
        positions = {}
        for vertex in graph.vertices:
            if len(graph.vertices) == 1:
                x, y = 1.8, -1.75
            else:
                x = 0.35 + (vertex.x - min_x) / span_x * 3.1
                y = -0.65 - (vertex.y - min_y) / span_y * 2.35
            positions[vertex.id] = (x, y)
        return positions

    def _latex_polynomial(self, text):
        return self._latex_escape_tikz(text).replace("\\^", "^")

    def _latex_escape_tikz(self, value):
        text = str(value)
        replacements = {
            "\\": r"\textbackslash{}",
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
        }
        escaped = "".join(replacements.get(char, char) for char in text)
        return self._reformat_tikz_powers(escaped)

    def _reformat_tikz_powers(self, text):
        return re.sub(r"\^(\d+)", r"^{\1}", text)

    def _fmt_tikz(self, value):
        text = f"{value:.3f}".rstrip("0").rstrip(".")
        return text if text and text != "-0" else "0"

    def _bind_events(self):
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_context_menu)
        self.canvas.bind("<Configure>", lambda event: self.draw_canvas())
        self.root.bind_all("<Delete>", self.on_delete_key)
        self.root.bind_all("<Control-z>", self.on_undo_key)
        self.root.bind_all("<Escape>", self.on_escape_key)

    def _bind_variable_traces(self):
        self.node_label_position.trace_add("write", self._on_node_label_position_changed)

    def _on_node_label_position_changed(self, *args):
        position = self._current_node_label_position()
        selected_node_ids = {object_id for kind, object_id in self.selection if kind == "node"}
        target_nodes = [
            node
            for node in self.nodes
            if not selected_node_ids or node.id in selected_node_ids
        ]
        if not target_nodes:
            self.draw_canvas()
            return

        changed = [
            node
            for node in target_nodes
            if getattr(node, "label_position", DEFAULT_NODE_LABEL_POSITION) != position
        ]
        if not changed:
            self.draw_canvas()
            return

        self._save_history()
        for node in changed:
            node.label_position = position
        self.draw_canvas()

    def choose_node_color(self):
        color = colorchooser.askcolor(title="选择点内部颜色", initialcolor=self.node_color)[1]
        if color:
            self.node_color = color
            self._update_color_swatch(self.node_fill_swatch, color)

    def choose_node_outline_color(self):
        color = colorchooser.askcolor(title="选择点边缘颜色", initialcolor=self.node_outline_color)[1]
        if color:
            self.node_outline_color = color
            self._update_color_swatch(self.node_outline_swatch, color)

    def choose_node_label_color(self):
        color = colorchooser.askcolor(title="选择点标签颜色", initialcolor=self.node_label_color)[1]
        if color:
            self.node_label_color = color
            self._update_color_swatch(self.node_label_swatch, color)

    def choose_edge_color(self):
        color = colorchooser.askcolor(title="选择边颜色", initialcolor=self.edge_color)[1]
        if color:
            self.edge_color = color
            self._update_color_swatch(self.edge_swatch, color)

    def choose_edge_label_color(self):
        color = colorchooser.askcolor(title="选择边标签颜色", initialcolor=self.edge_label_color)[1]
        if color:
            self.edge_label_color = color
            self._update_color_swatch(self.edge_label_swatch, color)

    def choose_text_color(self):
        color = colorchooser.askcolor(title="选择文本颜色", initialcolor=self.text_color)[1]
        if color:
            self.text_color = color
            self._update_color_swatch(self.text_swatch, color)

    def choose_pencil_color(self):
        color = colorchooser.askcolor(title="选择铅笔颜色", initialcolor=self.pencil_color)[1]
        if color:
            self.pencil_color = color
            self._update_color_swatch(self.pencil_swatch, color)

    def choose_shadow_color(self):
        color = colorchooser.askcolor(title="选择区域颜色", initialcolor=self.shadow_color)[1]
        if color:
            self.shadow_color = color
            self._update_color_swatch(self.region_swatch, color)

    def update_shadow_alpha(self, value):
        try:
            self.shadow_alpha = float(value)
            self.region_alpha.set(str(round(self.shadow_alpha, 2)))
        except ValueError:
            self.shadow_alpha = DEFAULT_SHADOW_ALPHA
            self.region_alpha.set(str(DEFAULT_SHADOW_ALPHA))

    def apply_background_settings(self):
        if self._get_background_settings(show_error=True) is None:
            return
        self.draw_canvas()

    def _get_background_settings(self, show_error=False):
        try:
            scale = float(self.axis_scale.get())
            origin_x = int(float(self.axis_origin_x.get()))
            origin_y = int(float(self.axis_origin_y.get()))
        except (tk.TclError, TypeError, ValueError):
            if show_error:
                messagebox.showwarning("坐标设置无效", "比例尺和原点需要填写数字。")
            return None

        if scale < MIN_AXIS_SCALE:
            if show_error:
                messagebox.showwarning("坐标设置无效", f"比例尺至少需要为 {int(MIN_AXIS_SCALE)} 像素/单位。")
            return None

        return BackgroundSettings(
            mode=self.background.get(),
            axis_scale=scale,
            axis_origin_x=origin_x,
            axis_origin_y=origin_y,
        )

    def _current_background_settings(self):
        settings = self._get_background_settings(show_error=False)
        if settings is not None:
            return settings
        return BackgroundSettings(mode=self.background.get())

    def on_canvas_click(self, event):
        if self.active_text_editor is not None:
            return

        self.canvas.focus_set()
        x, y = event.x, event.y
        mode = self.mode.get()

        if mode == "vertex":
            if self._find_node(x, y) is None:
                self._save_history()
                self._add_node(x, y)
                self.selection.clear()
        elif mode == "edge":
            hit_node = self._find_node(x, y)
            if hit_node is not None:
                self.current_edge_start = hit_node.id
        elif mode == "move":
            self._begin_move(x, y)
        elif mode == "text":
            self.selection.clear()
            self.current_text_box = (x, y, x, y)
        elif mode == "doodle":
            self.selection.clear()
            if self._current_region_shape() == "free":
                self.current_doodle = [x, y]
            else:
                self.current_region_box = (x, y, x, y)
        elif mode == "pencil":
            self.selection.clear()
            self.current_pencil_stroke = [x, y]
        elif mode == "delete":
            if self._delete_object(x, y):
                self.draw_canvas()
            return
        elif mode == "select":
            self._begin_selection(x, y)

        self.draw_canvas()

    def on_canvas_drag(self, event):
        x, y = event.x, event.y
        mode = self.mode.get()

        if mode == "move" and self.current_drag_kind is not None:
            self._update_move(x, y)
        elif mode == "edge" and self.current_edge_start is not None:
            self.draw_canvas(temp_line=(self.current_edge_start, x, y))
        elif mode == "doodle" and self.current_doodle is not None:
            self.current_doodle.extend([x, y])
            self.draw_canvas(temp_doodle=self.current_doodle)
        elif mode == "doodle" and self.current_region_box is not None:
            x0, y0, _, _ = self.current_region_box
            self.current_region_box = (x0, y0, x, y)
            self.draw_canvas(temp_region_box=self.current_region_box)
        elif mode == "pencil" and self.current_pencil_stroke is not None:
            self.current_pencil_stroke.extend([x, y])
            self.draw_canvas(temp_pencil=self.current_pencil_stroke)
        elif mode == "text" and self.current_text_box is not None:
            x0, y0, _, _ = self.current_text_box
            self.current_text_box = (x0, y0, x, y)
            self.draw_canvas(temp_text_box=self.current_text_box)
        elif mode == "select" and self.current_drag_kind is not None:
            self._update_move(x, y)
        elif mode == "select" and self.pending_select_move_target is not None:
            self.pending_select_move_latest = (x, y)
        elif mode == "select" and self.current_selection_box is not None:
            x0, y0, _, _ = self.current_selection_box
            self.current_selection_box = (x0, y0, x, y)
            self.draw_canvas(temp_selection_box=self.current_selection_box)

    def on_canvas_release(self, event):
        x, y = event.x, event.y
        mode = self.mode.get()

        if mode == "edge" and self.current_edge_start is not None:
            target_node = self._find_node(x, y)
            if target_node:
                self._save_history()
                self._add_edge(self.current_edge_start, target_node.id)
            self.current_edge_start = None
        elif mode == "doodle" and self.current_doodle is not None:
            if len(self.current_doodle) >= 6:
                self._save_history()
                self._add_region(self.current_doodle.copy())
            self.current_doodle = None
        elif mode == "doodle" and self.current_region_box is not None:
            box = self.current_region_box
            self.current_region_box = None
            points = self._region_points_from_box(box, self._current_region_shape())
            if points:
                self._save_history()
                self._add_region(points)
        elif mode == "pencil" and self.current_pencil_stroke is not None:
            if len(self.current_pencil_stroke) >= 4:
                self._save_history()
                self._add_pencil_stroke(self.current_pencil_stroke.copy())
            self.current_pencil_stroke = None
        elif mode == "move":
            self._finish_move()
        elif mode == "text" and self.current_text_box is not None:
            box = self.current_text_box
            self.current_text_box = None
            self.draw_canvas()
            self._open_text_editor_for_box(box)
            return
        elif mode == "select" and self.current_drag_kind is not None:
            self._finish_move()
        elif mode == "select" and self.current_selection_box is not None:
            x0, y0, x1, y1 = self.current_selection_box
            self.current_selection_box = None
            if abs(x1 - x0) > 4 or abs(y1 - y0) > 4:
                self.selection = self._objects_in_rect(x0, y0, x1, y1)

        self._cancel_pending_select_move()
        self._update_status()
        self.draw_canvas()

    def on_double_click(self, event):
        if self.active_text_editor is not None:
            return

        x, y = event.x, event.y
        target = self._find_object(x, y)
        if target is None:
            return

        kind, object_id = target
        obj = self._get_object(target)
        if obj is None:
            return

        if kind == "text":
            self._open_text_editor_for_existing(obj)
            return

        title = {"node": "节点标签", "edge": "边标签", "region": "区域标签"}.get(kind, "标签")
        prompt = {"node": "输入节点标签：", "edge": "输入边标签：", "region": "输入区域标签："}.get(kind, "输入标签：")
        text = simpledialog.askstring(title, prompt, initialvalue=getattr(obj, "label", ""))
        if text is not None and text.strip() != getattr(obj, "label", ""):
            self._save_history()
            obj.label = text.strip()
            self.draw_canvas()

    def on_context_menu(self, event):
        if self.active_text_editor is not None:
            self._commit_active_text_editor()

        x, y = event.x, event.y
        target = self._find_object(x, y)
        if target is not None and target not in self.selection:
            self.selection = {target}
            self.draw_canvas()

        targets = self._selected_targets()
        menu = tk.Menu(self.root, tearoff=False)
        if targets:
            style_label = "批量样式..." if len(targets) > 1 else "样式..."
            color_label = "批量改颜色..." if len(targets) > 1 else "改颜色..."
            menu.add_command(label=style_label, command=lambda: self._open_style_dialog(targets))
            menu.add_command(label=color_label, command=lambda: self._choose_color_for_targets(targets))
            if len(targets) == 1 and targets[0][0][0] in {"node", "edge", "region", "text"}:
                menu.add_command(label="编辑标签 / 文字...", command=lambda: self._edit_single_target(targets[0][0]))
            menu.add_separator()
            menu.add_command(label="删除所选", command=lambda: self._delete_targets([key for key, _ in targets]))
        else:
            menu.add_command(label="没有选中对象", state=tk.DISABLED)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def on_delete_key(self, event=None):
        if self.active_text_editor is not None:
            return
        if self.selection:
            self.delete_selection()
            return
        x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
        if self._delete_object(x, y):
            self.draw_canvas()

    def on_undo_key(self, event=None):
        if self.active_text_editor is not None:
            return
        self.undo()

    def on_escape_key(self, event=None):
        if self.active_text_editor is not None:
            self._cancel_active_text_editor()
            return
        self._cancel_pending_select_move()
        self.selection.clear()
        self.current_text_box = None
        self.current_selection_box = None
        self.current_region_box = None
        self.current_pencil_stroke = None
        self.draw_canvas()
        self._update_status()

    def _begin_selection(self, x, y):
        target = self._find_object(x, y)
        if target is not None:
            if target not in self.selection:
                self.selection = {target}
            self.current_selection_box = None
            if target[0] == "edge":
                self._begin_move(x, y, target=target)
            elif target[0] in {"node", "text", "pencil"}:
                self._schedule_select_move(target, x, y)
            return
        self.selection.clear()
        self.current_selection_box = (x, y, x, y)

    def _schedule_select_move(self, target, x, y):
        self._cancel_pending_select_move()
        self.pending_select_move_target = target
        self.pending_select_move_origin = (x, y)
        self.pending_select_move_latest = (x, y)
        self.pending_select_move_after_id = self.root.after(260, self._activate_pending_select_move)

    def _activate_pending_select_move(self):
        self.pending_select_move_after_id = None
        if self.mode.get() != "select" or self.pending_select_move_target is None:
            return
        x, y = self.pending_select_move_origin
        latest_x, latest_y = self.pending_select_move_latest
        self._begin_move(x, y, target=self.pending_select_move_target)
        if self.current_drag_kind is not None:
            self._update_move(latest_x, latest_y)
            self._update_status()

    def _cancel_pending_select_move(self):
        if self.pending_select_move_after_id is not None:
            self.root.after_cancel(self.pending_select_move_after_id)
        self.pending_select_move_after_id = None
        self.pending_select_move_target = None
        self.pending_select_move_origin = None
        self.pending_select_move_latest = None

    def _begin_move(self, x, y, target=None):
        if target is None:
            target = self._find_object(x, y)
        if target is None:
            return

        if target in self.selection and len(self.selection) > 1:
            snapshots = {}
            selected_targets = self._selected_targets()
            selected_kinds = {key[0] for key, _ in selected_targets}
            adjust_selected_edges = selected_kinds <= {"edge"}
            for key, obj in selected_targets:
                if key[0] in {"node", "text"}:
                    snapshots[key] = (obj.x, obj.y)
                elif key[0] == "region":
                    snapshots[key] = obj.points.copy()
                elif key[0] == "pencil":
                    snapshots[key] = obj.points.copy()
                elif key[0] == "edge" and adjust_selected_edges:
                    basis = self._edge_drag_basis(obj)
                    if basis is not None:
                        snapshots[key] = {
                            "offset": self._edge_drag_offset(obj),
                            "basis": basis,
                        }
            self._save_history()
            self.current_drag_kind = "selection"
            self.current_drag_object = snapshots
            self.drag_origin = (x, y)
            return

        kind, _ = target
        if kind not in {"node", "text", "edge", "pencil"}:
            return

        obj = self._get_object(target)
        if obj is None:
            return
        if kind == "edge":
            basis = self._edge_drag_basis(obj)
            if basis is None:
                return
            self._save_history()
            self.current_drag_kind = "edge"
            self.current_drag_object = obj
            self.drag_origin = (x, y, self._edge_drag_offset(obj), basis)
            self.selection = {target}
            return
        if kind == "pencil":
            self._save_history()
            self.current_drag_kind = "pencil"
            self.current_drag_object = obj
            self.drag_origin = (obj.points.copy(), x, y)
            self.selection = {target}
            return

        self._save_history()
        self.current_drag_kind = kind
        self.current_drag_object = obj
        self.drag_origin = (obj.x, obj.y, x, y)
        self.selection = {target}

    def _update_move(self, x, y):
        if self.current_drag_kind == "selection":
            start_x, start_y = self.drag_origin
            dx = x - start_x
            dy = y - start_y
            for key, snapshot in self.current_drag_object.items():
                obj = self._get_object(key)
                if obj is None:
                    continue
                if key[0] in {"node", "text"}:
                    obj.x = snapshot[0] + dx
                    obj.y = snapshot[1] + dy
                elif key[0] == "region":
                    obj.points = [
                        value + (dx if index % 2 == 0 else dy)
                        for index, value in enumerate(snapshot)
                    ]
                elif key[0] == "pencil":
                    obj.points = [
                        value + (dx if index % 2 == 0 else dy)
                        for index, value in enumerate(snapshot)
                    ]
                elif key[0] == "edge":
                    movement = self._edge_offset_delta(dx, dy, snapshot["basis"])
                    obj.curve_offset = self._clamp_edge_curve_offset(
                        snapshot["offset"] + movement,
                        snapshot["basis"],
                    )
            self.draw_canvas()
            return

        if self.current_drag_object is None or self.drag_origin is None:
            return

        if self.current_drag_kind == "edge":
            start_mouse_x, start_mouse_y, start_offset, basis = self.drag_origin
            dx = x - start_mouse_x
            dy = y - start_mouse_y
            self.current_drag_object.curve_offset = self._clamp_edge_curve_offset(
                start_offset + self._edge_offset_delta(dx, dy, basis),
                basis,
            )
            self.draw_canvas()
            return

        if self.current_drag_kind == "pencil":
            start_points, start_mouse_x, start_mouse_y = self.drag_origin
            dx = x - start_mouse_x
            dy = y - start_mouse_y
            self.current_drag_object.points = [
                value + (dx if index % 2 == 0 else dy)
                for index, value in enumerate(start_points)
            ]
            self.draw_canvas()
            return

        start_obj_x, start_obj_y, start_mouse_x, start_mouse_y = self.drag_origin
        self.current_drag_object.x = start_obj_x + (x - start_mouse_x)
        self.current_drag_object.y = start_obj_y + (y - start_mouse_y)
        self.draw_canvas()

    def _finish_move(self):
        if self.current_drag_kind is None:
            return

        moved = True
        if self.current_drag_kind in {"node", "text"} and self.current_drag_object is not None:
            start_obj_x, start_obj_y, _, _ = self.drag_origin
            moved = (self.current_drag_object.x, self.current_drag_object.y) != (start_obj_x, start_obj_y)
        elif self.current_drag_kind == "edge" and self.current_drag_object is not None:
            _, _, start_offset, _ = self.drag_origin
            moved = self._edge_drag_offset(self.current_drag_object) != start_offset
        elif self.current_drag_kind == "pencil" and self.current_drag_object is not None:
            start_points, _, _ = self.drag_origin
            moved = self.current_drag_object.points != start_points
        elif self.current_drag_kind == "selection":
            start_x, start_y = self.drag_origin
            pointer_x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
            pointer_y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()
            moved = (pointer_x, pointer_y) != (start_x, start_y)

        if not moved and self.history:
            self.history.pop()

        self.current_drag_kind = None
        self.current_drag_object = None
        self.drag_origin = None

    def _open_text_editor_for_box(self, box):
        x0, y0, x1, y1 = box
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))
        width = max(60, int(right - left))
        height = max(32, int(bottom - top))
        if width < 80 and height < 40:
            width = DEFAULT_TEXT_WIDTH
            height = DEFAULT_TEXT_HEIGHT
        self._start_text_editor(left, top, width, height, initial_text="", target=None)

    def _open_text_editor_for_existing(self, text_label):
        self._start_text_editor(
            text_label.x,
            text_label.y,
            text_label.width,
            text_label.height,
            initial_text=text_label.text,
            target=text_label,
        )

    def _start_text_editor(self, x, y, width, height, initial_text="", target=None):
        if self.active_text_editor is not None:
            self._commit_active_text_editor()

        self.draw_canvas()
        font_size = target.font_size if target is not None else self._current_text_size()
        color = target.color if target is not None else self.text_color
        editor = tk.Text(
            self.canvas,
            wrap=tk.WORD,
            font=("Segoe UI", font_size),
            fg=color,
            bg="#fffdf7",
            bd=1,
            relief=tk.SOLID,
            padx=5,
            pady=4,
            undo=True,
        )
        editor.insert("1.0", initial_text)
        window_id = self.canvas.create_window(
            x,
            y,
            anchor=tk.NW,
            window=editor,
            width=width,
            height=height,
        )
        self.active_text_editor = {
            "window_id": window_id,
            "widget": editor,
            "target": target,
            "x": int(x),
            "y": int(y),
            "width": int(width),
            "height": int(height),
            "font_size": int(font_size),
            "color": color,
        }
        editor.bind("<Control-Return>", lambda event: self._commit_active_text_editor())
        editor.bind("<Escape>", lambda event: self._cancel_active_text_editor())
        editor.bind("<FocusOut>", lambda event: self.root.after(80, self._commit_active_text_editor))
        editor.focus_set()

    def _commit_active_text_editor(self):
        if self.active_text_editor is None:
            return "break"

        editor_state = self.active_text_editor
        editor = editor_state["widget"]
        if not editor.winfo_exists():
            self.active_text_editor = None
            return "break"

        text = editor.get("1.0", tk.END).strip()
        target = editor_state["target"]
        self.canvas.delete(editor_state["window_id"])
        self.active_text_editor = None

        if target is None:
            if text:
                self._save_history()
                self.texts.append(
                    TextLabel(
                        x=editor_state["x"],
                        y=editor_state["y"],
                        text=text,
                        color=editor_state["color"],
                        font_size=editor_state["font_size"],
                        width=editor_state["width"],
                        height=editor_state["height"],
                        id=self._next_text_id(),
                    )
                )
        elif text:
            if text != target.text:
                self._save_history()
                target.text = text

        self.draw_canvas()
        return "break"

    def _cancel_active_text_editor(self):
        if self.active_text_editor is None:
            return "break"
        self.canvas.delete(self.active_text_editor["window_id"])
        self.active_text_editor = None
        self.draw_canvas()
        return "break"

    def _add_node(self, x, y):
        self.nodes.append(
            Node(
                id=self._next_node_id(),
                x=x,
                y=y,
                color=self.node_color,
                radius=self._current_node_radius(),
                outline_color=self.node_outline_color,
                label_position=self._current_node_label_position(),
                label_color=self.node_label_color,
                label_size=self._current_node_label_size(),
            )
        )

    def _add_edge(self, source, target):
        self.edges.append(
            Edge(
                source=source,
                target=target,
                color=self.edge_color,
                directed=self.directed.get(),
                width=self._current_edge_width(),
                style=self._current_edge_style(),
                id=self._next_edge_id(),
                label_color=self.edge_label_color,
                label_size=self._current_edge_label_size(),
            )
        )

    def _add_region(self, points):
        self.regions.append(
            Region(
                points=points,
                color=self.shadow_color,
                alpha=self._current_region_alpha(),
                id=self._next_region_id(),
            )
        )

    def _add_pencil_stroke(self, points):
        self.pencil_strokes.append(
            PencilStroke(
                points=points,
                color=self.pencil_color,
                width=self._current_pencil_width(),
                id=self._next_pencil_id(),
            )
        )

    def _region_points_from_box(self, box, shape):
        x0, y0, x1, y1 = box
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))
        if right - left < 6 or bottom - top < 6:
            return []

        if shape == "rectangle":
            return [left, top, right, top, right, bottom, left, bottom]
        if shape == "triangle":
            return [(left + right) / 2, top, right, bottom, left, bottom]
        if shape in {"circle", "ellipse"}:
            cx = (left + right) / 2
            cy = (top + bottom) / 2
            if shape == "circle":
                radius = min(right - left, bottom - top) / 2
                rx = radius
                ry = radius
            else:
                rx = (right - left) / 2
                ry = (bottom - top) / 2
            points = []
            steps = 48 if shape == "circle" else 40
            for step in range(steps):
                angle = 2 * math.pi * step / steps
                points.extend([cx + math.cos(angle) * rx, cy + math.sin(angle) * ry])
            return points
        return []

    def _next_node_id(self):
        return max((node.id for node in self.nodes), default=0) + 1

    def _next_edge_id(self):
        return max((edge.id for edge in self.edges), default=0) + 1

    def _next_region_id(self):
        return max((region.id for region in self.regions), default=0) + 1

    def _next_text_id(self):
        return max((text.id for text in self.texts), default=0) + 1

    def _next_pencil_id(self):
        return max((stroke.id for stroke in self.pencil_strokes), default=0) + 1

    def _find_node(self, x, y):
        for node in reversed(self.nodes):
            radius = getattr(node, "radius", NODE_RADIUS)
            if math.hypot(node.x - x, node.y - y) <= radius + 4:
                return node
            if self._node_label_contains_point(node, x, y):
                return node
        return None

    def _node_label_contains_point(self, node, x, y):
        if not self._node_label_text(node) or getattr(node, "label_position", DEFAULT_NODE_LABEL_POSITION) != "beside":
            return False
        x0, y0, x1, y1 = self._node_side_label_bbox(node)
        return x0 <= x <= x1 and y0 <= y <= y1

    def _node_side_label_bbox(self, node):
        label_x, label_y = self._node_label_anchor(node)
        font_size = getattr(node, "label_size", DEFAULT_NODE_LABEL_SIZE)
        width = max(24, len(self._node_label_text(node)) * font_size * 0.75 + 6)
        height = max(18, font_size + 6)
        return label_x - 2, label_y - height / 2, label_x + width, label_y + height / 2

    def _find_edge(self, x, y):
        for edge in reversed(self.edges):
            if self._edge_contains_point(edge, x, y):
                return edge
        return None

    def _find_text_label(self, x, y):
        for text in reversed(self.texts):
            x0, y0, x1, y1 = self._text_bbox(text)
            if x0 - 4 <= x <= x1 + 4 and y0 - 4 <= y <= y1 + 4:
                return text
        return None

    def _find_region(self, x, y):
        for region in reversed(self.regions):
            if self._point_in_polygon(x, y, region.points):
                return region
        return None

    def _find_pencil_stroke(self, x, y):
        for stroke in reversed(self.pencil_strokes):
            points = self._pencil_points(stroke)
            if len(points) < 2:
                continue
            tolerance = max(8, getattr(stroke, "width", DEFAULT_PENCIL_WIDTH) + 5)
            if self._distance_to_polyline(x, y, points) <= tolerance:
                return stroke
        return None

    def _find_object(self, x, y):
        node = self._find_node(x, y)
        if node is not None:
            return ("node", node.id)
        text = self._find_text_label(x, y)
        if text is not None:
            return ("text", text.id)
        edge = self._find_edge(x, y)
        if edge is not None:
            return ("edge", edge.id)
        stroke = self._find_pencil_stroke(x, y)
        if stroke is not None:
            return ("pencil", stroke.id)
        region = self._find_region(x, y)
        if region is not None:
            return ("region", region.id)
        return None

    def _edge_contains_point(self, edge, x, y):
        source = self._find_node_by_id(edge.source)
        target = self._find_node_by_id(edge.target)
        if not source or not target:
            return False
        samples = self._edge_sample_points(edge, source, target)
        if len(samples) < 2:
            return False
        tolerance = max(8, getattr(edge, "width", DEFAULT_EDGE_WIDTH) + 5)
        return self._distance_to_polyline(x, y, samples) <= tolerance

    def _distance_to_polyline(self, x, y, points):
        best = float("inf")
        for index in range(len(points) - 1):
            x0, y0 = points[index]
            x1, y1 = points[index + 1]
            dx = x1 - x0
            dy = y1 - y0
            if dx == 0 and dy == 0:
                best = min(best, math.hypot(x - x0, y - y0))
                continue
            projection = ((x - x0) * dx + (y - y0) * dy) / (dx * dx + dy * dy)
            projection = max(0, min(1, projection))
            closest_x = x0 + projection * dx
            closest_y = y0 + projection * dy
            best = min(best, math.hypot(closest_x - x, closest_y - y))
        return best

    def _pencil_points(self, stroke):
        return [
            (stroke.points[index], stroke.points[index + 1])
            for index in range(0, len(stroke.points) - 1, 2)
        ]

    def _find_node_by_id(self, node_id):
        return next((node for node in self.nodes if node.id == node_id), None)

    def _find_edge_by_id(self, edge_id):
        return next((edge for edge in self.edges if edge.id == edge_id), None)

    def _find_region_by_id(self, region_id):
        return next((region for region in self.regions if region.id == region_id), None)

    def _find_text_by_id(self, text_id):
        return next((text for text in self.texts if text.id == text_id), None)

    def _find_pencil_by_id(self, pencil_id):
        return next((stroke for stroke in self.pencil_strokes if stroke.id == pencil_id), None)

    def _get_object(self, key):
        kind, object_id = key
        if kind == "node":
            return self._find_node_by_id(object_id)
        if kind == "edge":
            return self._find_edge_by_id(object_id)
        if kind == "region":
            return self._find_region_by_id(object_id)
        if kind == "text":
            return self._find_text_by_id(object_id)
        if kind == "pencil":
            return self._find_pencil_by_id(object_id)
        return None

    def _selected_targets(self):
        targets = []
        for key in sorted(self.selection):
            obj = self._get_object(key)
            if obj is not None:
                targets.append((key, obj))
        return targets

    def _objects_in_rect(self, x0, y0, x1, y1):
        left, right = sorted((x0, x1))
        top, bottom = sorted((y0, y1))
        selection = set()

        for node in self.nodes:
            if self._point_in_rect(node.x, node.y, left, top, right, bottom):
                selection.add(("node", node.id))

        for text in self.texts:
            if self._rects_intersect(self._text_bbox(text), (left, top, right, bottom)):
                selection.add(("text", text.id))

        for stroke in self.pencil_strokes:
            if any(self._point_in_rect(px, py, left, top, right, bottom) for px, py in self._pencil_points(stroke)):
                selection.add(("pencil", stroke.id))

        for edge in self.edges:
            source = self._find_node_by_id(edge.source)
            target = self._find_node_by_id(edge.target)
            if source is None or target is None:
                continue
            samples = self._edge_sample_points(edge, source, target)
            if any(self._point_in_rect(px, py, left, top, right, bottom) for px, py in samples):
                selection.add(("edge", edge.id))

        for region in self.regions:
            xs = region.points[::2]
            ys = region.points[1::2]
            if not xs or not ys:
                continue
            centroid = (sum(xs) / len(xs), sum(ys) / len(ys))
            if self._point_in_rect(centroid[0], centroid[1], left, top, right, bottom):
                selection.add(("region", region.id))
                continue
            for i in range(0, len(region.points), 2):
                if self._point_in_rect(region.points[i], region.points[i + 1], left, top, right, bottom):
                    selection.add(("region", region.id))
                    break

        return selection

    def _point_in_rect(self, x, y, left, top, right, bottom):
        return left <= x <= right and top <= y <= bottom

    def _rects_intersect(self, a, b):
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        return ax0 <= bx1 and ax1 >= bx0 and ay0 <= by1 and ay1 >= by0

    def _text_bbox(self, text):
        return (text.x, text.y, text.x + text.width, text.y + text.height)

    def _delete_object(self, x, y):
        target = self._find_object(x, y)
        if target is None:
            return False
        self._delete_targets([target])
        return True

    def delete_selection(self):
        if not self.selection:
            return
        self._delete_targets(list(self.selection))

    def _delete_targets(self, keys):
        if not keys:
            return
        self._save_history()
        node_ids = {object_id for kind, object_id in keys if kind == "node"}
        edge_ids = {object_id for kind, object_id in keys if kind == "edge"}
        region_ids = {object_id for kind, object_id in keys if kind == "region"}
        text_ids = {object_id for kind, object_id in keys if kind == "text"}
        pencil_ids = {object_id for kind, object_id in keys if kind == "pencil"}

        self.nodes = [node for node in self.nodes if node.id not in node_ids]
        self.edges = [
            edge
            for edge in self.edges
            if edge.id not in edge_ids and edge.source not in node_ids and edge.target not in node_ids
        ]
        self.regions = [region for region in self.regions if region.id not in region_ids]
        self.texts = [text for text in self.texts if text.id not in text_ids]
        self.pencil_strokes = [stroke for stroke in self.pencil_strokes if stroke.id not in pencil_ids]
        self.selection.clear()
        self.draw_canvas()
        self._update_status()

    def undo(self):
        if not self.history:
            messagebox.showinfo("撤销", "没有可撤销的操作。")
            return
        state = self.history.pop()
        if len(state) == 5:
            self.nodes, self.edges, self.regions, self.texts, self.pencil_strokes = state
        else:
            self.nodes, self.edges, self.regions, self.texts = state
            self.pencil_strokes = []
        self.selection.clear()
        self.draw_canvas()
        self._update_status()

    def _save_history(self):
        self.history.append(
            (
                copy.deepcopy(self.nodes),
                copy.deepcopy(self.edges),
                copy.deepcopy(self.regions),
                copy.deepcopy(self.texts),
                copy.deepcopy(self.pencil_strokes),
            )
        )

    def draw_canvas(
        self,
        temp_line=None,
        temp_doodle=None,
        temp_region_box=None,
        temp_pencil=None,
        temp_text_box=None,
        temp_selection_box=None,
    ):
        if self.active_text_editor is not None:
            return

        self.canvas.delete("all")
        self._draw_background()
        for region in self.regions:
            self._draw_region(region)
        for stroke in self.pencil_strokes:
            self._draw_pencil_stroke(stroke)
        if temp_pencil is not None and len(temp_pencil) >= 4:
            self._draw_pencil_points(
                temp_pencil,
                self.pencil_color,
                self._current_pencil_width(),
            )
        for edge in self.edges:
            self._draw_edge(edge)
        if temp_line is not None:
            start_id, x, y = temp_line
            start_node = self._find_node_by_id(start_id)
            if start_node:
                self._draw_line(
                    start_node.x,
                    start_node.y,
                    x,
                    y,
                    self.edge_color,
                    width=self._current_edge_width(),
                    directed=self.directed.get(),
                    style=self._current_edge_style(),
                    dashed=True,
                )
        if temp_doodle is not None and len(temp_doodle) >= 4:
            self.canvas.create_line(*temp_doodle, fill=self.shadow_color, width=3, capstyle=tk.ROUND, smooth=True)
        if temp_region_box is not None:
            self._draw_region_shape_preview(temp_region_box, self._current_region_shape())
        for node in self.nodes:
            self._draw_node(node)
        for text in self.texts:
            self._draw_text_label(text)
        if temp_text_box is not None:
            self._draw_temp_box(temp_text_box, "#f2a51a", "文本框")
        if temp_selection_box is not None:
            self._draw_temp_box(temp_selection_box, SELECTION_COLOR, "选择")
        self._draw_selection_outline()

    def _draw_background(self):
        settings = self._current_background_settings()
        if settings.mode == "grid":
            self._draw_grid(settings)
        elif settings.mode == "axes":
            self._draw_axes(settings)

    def _draw_grid(self, settings):
        width = int(self.canvas.winfo_width() or CANVAS_DEFAULT_WIDTH)
        height = int(self.canvas.winfo_height() or CANVAS_DEFAULT_HEIGHT)
        step = int(round(settings.normalized_scale()))
        for x in range(0, width + 1, step):
            self.canvas.create_line(x, 0, x, height, fill="#ececec")
        for y in range(0, height + 1, step):
            self.canvas.create_line(0, y, width, y, fill="#ececec")

    def _draw_axes(self, settings):
        width = int(self.canvas.winfo_width() or CANVAS_DEFAULT_WIDTH)
        height = int(self.canvas.winfo_height() or CANVAS_DEFAULT_HEIGHT)
        scale = settings.normalized_scale()
        ox = settings.axis_origin_x
        oy = settings.axis_origin_y

        if 0 <= oy <= height:
            self.canvas.create_line(0, oy, width, oy, fill="#999999", width=2, arrow=tk.LAST)
        if 0 <= ox <= width:
            self.canvas.create_line(ox, height, ox, 0, fill="#999999", width=2, arrow=tk.LAST)

        self._draw_x_axis_ticks(width, height, ox, oy, scale)
        self._draw_y_axis_ticks(width, height, ox, oy, scale)
        if 0 <= ox <= width and 0 <= oy <= height:
            self.canvas.create_text(ox + 12, oy + 12, text="O", fill="#333333", font=("Segoe UI", 9, "bold"))

    def _draw_x_axis_ticks(self, width, height, ox, oy, scale):
        if not 0 <= oy <= height:
            return
        start = math.ceil((0 - ox) / scale)
        end = math.floor((width - ox) / scale)
        for unit in self._limited_tick_range(start, end):
            x = round(ox + unit * scale)
            self.canvas.create_line(x, oy - 5, x, oy + 5, fill="#999999")
            if unit != 0:
                self.canvas.create_text(x, oy + 14, text=str(unit), fill="#666666", font=("Segoe UI", 8))

    def _draw_y_axis_ticks(self, width, height, ox, oy, scale):
        if not 0 <= ox <= width:
            return
        start = math.ceil((oy - height) / scale)
        end = math.floor(oy / scale)
        for unit in self._limited_tick_range(start, end):
            y = round(oy - unit * scale)
            self.canvas.create_line(ox - 5, y, ox + 5, y, fill="#999999")
            if unit != 0:
                self.canvas.create_text(ox + 14, y, text=str(unit), fill="#666666", font=("Segoe UI", 8), anchor=tk.W)

    def _limited_tick_range(self, start, end):
        count = max(0, end - start + 1)
        if count == 0:
            return []
        stride = max(1, math.ceil(count / 80))
        return range(start, end + 1, stride)

    def _draw_node(self, node):
        radius = getattr(node, "radius", NODE_RADIUS)
        outline_color = getattr(node, "outline_color", DEFAULT_NODE_OUTLINE_COLOR)
        label_text = self._node_label_text(node)
        self.canvas.create_oval(
            node.x - radius,
            node.y - radius,
            node.x + radius,
            node.y + radius,
            fill=node.color,
            outline=outline_color,
            width=1.6,
        )
        if label_text:
            label_position = getattr(node, "label_position", DEFAULT_NODE_LABEL_POSITION)
            if label_position == "beside":
                self._draw_node_side_label(node, label_text, radius)
            else:
                self.canvas.create_text(
                    node.x,
                    node.y,
                    text=label_text,
                    fill=self._effective_node_label_color(node),
                    font=("Segoe UI", getattr(node, "label_size", DEFAULT_NODE_LABEL_SIZE), "bold"),
                )

    def _draw_node_side_label(self, node, label_text, radius):
        label_x, label_y = self._node_label_anchor(node)
        self.canvas.create_text(
            label_x,
            label_y,
            text=label_text,
            fill=self._effective_node_label_color(node, side_label=True),
            font=("Segoe UI Semibold", getattr(node, "label_size", DEFAULT_NODE_LABEL_SIZE), "bold"),
            anchor=tk.W,
        )

    def _node_label_anchor(self, node):
        radius = getattr(node, "radius", NODE_RADIUS)
        return node.x + radius + 8, node.y - radius - 8

    def _effective_node_label_color(self, node, side_label=False):
        color = getattr(node, "label_color", DEFAULT_NODE_LABEL_COLOR)
        if side_label and color.lower() == "#ffffff":
            return "#1f2937"
        return color

    def _draw_edge(self, edge):
        source = self._find_node_by_id(edge.source)
        target = self._find_node_by_id(edge.target)
        if source is None or target is None:
            return
        geometry = self._edge_geometry(edge, source, target)
        self._draw_edge_path(geometry, edge.color, edge.width, edge.directed, edge.style)
        label_text = self._edge_label_text(edge)
        if label_text:
            self._draw_edge_label(edge, geometry, label_text)

    def _edge_drag_basis(self, edge):
        source = self._find_node_by_id(edge.source)
        target = self._find_node_by_id(edge.target)
        if source is None or target is None:
            return None
        if source.id == target.id:
            unit = math.sqrt(0.5)
            return {
                "kind": "loop",
                "normal": (unit, -unit),
                "limit": 220,
            }

        x0, y0, x1, y1 = self._edge_display_points(source, target, edge.directed)
        dx = x1 - x0
        dy = y1 - y0
        distance = math.hypot(dx, dy)
        if distance == 0:
            return None
        return {
            "kind": "edge",
            "normal": (-dy / distance, dx / distance),
            "limit": max(80, min(360, distance * 0.85)),
        }

    def _edge_drag_offset(self, edge):
        manual_offset = getattr(edge, "curve_offset", None)
        if edge.source == edge.target:
            return float(manual_offset or 0)
        return float(self._edge_curve_offset(edge))

    def _edge_offset_delta(self, dx, dy, basis):
        nx, ny = basis["normal"]
        return dx * nx + dy * ny

    def _clamp_edge_curve_offset(self, offset, basis):
        if basis["kind"] == "loop":
            return max(-18, min(basis["limit"], offset))
        return max(-basis["limit"], min(basis["limit"], offset))

    def _edge_geometry(self, edge, source, target):
        if source.id == target.id:
            return self._loop_edge_geometry(edge, source)

        x0, y0, x1, y1 = self._edge_display_points(source, target, edge.directed)
        offset = self._edge_curve_offset(edge)
        if abs(offset) < 0.01:
            return {
                "kind": "line",
                "points": [(x0, y0), (x1, y1)],
                "offset": 0,
            }

        dx = x1 - x0
        dy = y1 - y0
        distance = math.hypot(dx, dy)
        if distance == 0:
            return {
                "kind": "line",
                "points": [(x0, y0), (x1, y1)],
                "offset": 0,
            }
        nx = -dy / distance
        ny = dx / distance
        endpoint_shift = self._parallel_edge_endpoint_shift(offset)
        if endpoint_shift:
            x0 += nx * endpoint_shift
            y0 += ny * endpoint_shift
            x1 += nx * endpoint_shift
            y1 += ny * endpoint_shift
        cx = (x0 + x1) / 2 + nx * offset
        cy = (y0 + y1) / 2 + ny * offset
        return {
            "kind": "quadratic",
            "points": [(x0, y0), (cx, cy), (x1, y1)],
            "offset": offset,
            "normal": (nx, ny),
        }

    def _loop_edge_geometry(self, edge, node):
        radius = getattr(node, "radius", NODE_RADIUS)
        index = self._edge_variant_index(edge)
        manual_offset = getattr(edge, "curve_offset", None)
        grow = index * 18 + (manual_offset or 0)
        grow = max(-18, min(220, grow))
        points = [
            (node.x + radius * 0.2, node.y - radius - 1),
            (node.x + radius + 26 + grow, node.y - radius - 34 - grow),
            (node.x + radius + 48 + grow, node.y + radius + 12 + grow),
            (node.x + radius + 1, node.y + radius * 0.15),
        ]
        return {
            "kind": "loop",
            "points": points,
            "offset": 0,
            "loop_index": index,
        }

    def _edge_display_points(self, source, target, directed):
        dx = target.x - source.x
        dy = target.y - source.y
        distance = math.hypot(dx, dy)
        if distance == 0:
            return source.x, source.y, target.x, target.y
        ux = dx / distance
        uy = dy / distance
        start_offset = getattr(source, "radius", NODE_RADIUS) + 2
        end_offset = getattr(target, "radius", NODE_RADIUS) + (2 if directed else 2)
        if distance <= start_offset + end_offset + 4:
            start_offset = min(start_offset, distance * 0.35)
            end_offset = min(end_offset, distance * 0.35)
        return (
            source.x + ux * start_offset,
            source.y + uy * start_offset,
            target.x - ux * end_offset,
            target.y - uy * end_offset,
        )

    def _draw_edge_label(self, edge, geometry, label):
        label_x, label_y = self._edge_label_position(edge, geometry)
        self.canvas.create_text(
            label_x,
            label_y,
            text=label,
            fill=getattr(edge, "label_color", DEFAULT_EDGE_LABEL_COLOR),
            font=("Cambria", getattr(edge, "label_size", DEFAULT_EDGE_LABEL_SIZE), "italic"),
        )

    def _edge_label_position(self, edge, geometry):
        label_size = getattr(edge, "label_size", DEFAULT_EDGE_LABEL_SIZE)
        width = getattr(edge, "width", DEFAULT_EDGE_WIDTH)
        if geometry["kind"] == "loop":
            points = geometry["points"]
            max_x = max(point[0] for point in points)
            min_y = min(point[1] for point in points)
            return max_x + 8, min_y + label_size

        points = geometry["points"]
        if geometry["kind"] == "quadratic":
            x0, y0 = points[0]
            cx, cy = points[1]
            x1, y1 = points[2]
            mx = 0.25 * x0 + 0.5 * cx + 0.25 * x1
            my = 0.25 * y0 + 0.5 * cy + 0.25 * y1
            nx, ny = geometry.get("normal", (0, -1))
            side = 1 if geometry.get("offset", 0) >= 0 else -1
            offset = max(18, label_size + width * 2.5)
            return mx + nx * side * offset, my + ny * side * offset

        x0, y0 = points[0]
        x1, y1 = points[-1]
        dx = x1 - x0
        dy = y1 - y0
        distance = math.hypot(dx, dy)
        if distance == 0:
            nx, ny = 0, -1
        else:
            nx, ny = -dy / distance, dx / distance
            if ny > 0:
                nx, ny = -nx, -ny
        offset = max(18, label_size + width * 2.5)
        return (x0 + x1) / 2 + nx * offset, (y0 + y1) / 2 + ny * offset

    def _draw_edge_path(self, geometry, color, width, directed, style, dashed=False):
        dash = (4, 2) if dashed else EDGE_DASH_PATTERNS.get(style)
        flat_points = []
        for x, y in geometry["points"]:
            flat_points.extend([x, y])
        self.canvas.create_line(
            *flat_points,
            fill=color,
            width=width,
            arrow=tk.LAST if directed else tk.NONE,
            arrowshape=(13, 16, 7),
            dash=dash,
            smooth=geometry["kind"] in {"quadratic", "loop"},
            splinesteps=24,
        )

    def _edge_sample_points(self, edge, source, target):
        geometry = self._edge_geometry(edge, source, target)
        points = geometry["points"]
        if geometry["kind"] == "quadratic":
            p0, control, p1 = points
            samples = []
            for step in range(25):
                t = step / 24
                one_minus = 1 - t
                x = one_minus * one_minus * p0[0] + 2 * one_minus * t * control[0] + t * t * p1[0]
                y = one_minus * one_minus * p0[1] + 2 * one_minus * t * control[1] + t * t * p1[1]
                samples.append((x, y))
            return samples
        if geometry["kind"] == "loop":
            return self._catmull_rom_samples(points, samples_per_segment=12)
        return points

    def _catmull_rom_samples(self, points, samples_per_segment=12):
        if len(points) < 2:
            return points
        padded = [points[0]] + points + [points[-1]]
        samples = []
        for index in range(1, len(padded) - 2):
            p0 = padded[index - 1]
            p1 = padded[index]
            p2 = padded[index + 1]
            p3 = padded[index + 2]
            for step in range(samples_per_segment):
                t = step / samples_per_segment
                t2 = t * t
                t3 = t2 * t
                x = 0.5 * (
                    (2 * p1[0])
                    + (-p0[0] + p2[0]) * t
                    + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                    + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
                )
                y = 0.5 * (
                    (2 * p1[1])
                    + (-p0[1] + p2[1]) * t
                    + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                    + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
                )
                samples.append((x, y))
        samples.append(points[-1])
        return samples

    def _edge_curve_offset(self, edge):
        manual_offset = getattr(edge, "curve_offset", None)
        members = self._edge_group_members(edge)
        if manual_offset is not None and not (
            len(members) > 1 and abs(float(manual_offset)) < 0.01
        ):
            return manual_offset
        if len(members) <= 1:
            return 0
        index = members.index(edge)
        return self._parallel_edge_offset(index, len(members), 28)

    def _parallel_edge_offset(self, index, count, spacing):
        """Return a non-zero offset for each edge in a parallel-edge group."""

        if count <= 1:
            return 0
        magnitude = index // 2 + 1
        sign = -1 if index % 2 == 0 else 1
        return sign * magnitude * spacing

    def _parallel_edge_endpoint_shift(self, offset):
        if abs(offset) < 0.01:
            return 0
        sign = 1 if offset > 0 else -1
        return sign * min(11, max(5, abs(offset) * 0.18))

    def _edge_variant_index(self, edge):
        members = self._edge_group_members(edge)
        return members.index(edge) if edge in members else 0

    def _edge_group_members(self, edge):
        key = self._edge_group_key(edge)
        return [candidate for candidate in self.edges if self._edge_group_key(candidate) == key]

    def _edge_group_key(self, edge):
        if edge.source == edge.target:
            return ("loop", edge.source)
        return ("pair", min(edge.source, edge.target), max(edge.source, edge.target))

    def _draw_line(self, x0, y0, x1, y1, color, width=DEFAULT_EDGE_WIDTH, directed=False, style=DEFAULT_EDGE_STYLE, dashed=False):
        dash = (4, 2) if dashed else EDGE_DASH_PATTERNS.get(style)
        self.canvas.create_line(
            x0,
            y0,
            x1,
            y1,
            fill=color,
            width=width,
            arrow=tk.LAST if directed else tk.NONE,
            arrowshape=(14, 18, 8),
            dash=dash,
        )

    def _draw_region(self, region):
        if len(region.points) < 6:
            return
        stipple = self._alpha_to_stipple(region.alpha)
        self.canvas.create_polygon(region.points, fill=region.color, outline="", stipple=stipple)
        if region.label:
            xs = region.points[::2]
            ys = region.points[1::2]
            if xs and ys:
                self.canvas.create_text(
                    sum(xs) / len(xs),
                    sum(ys) / len(ys),
                    text=region.label,
                    fill="#333333",
                    font=("Segoe UI", 10, "bold"),
                )

    def _draw_pencil_stroke(self, stroke):
        self._draw_pencil_points(
            stroke.points,
            getattr(stroke, "color", DEFAULT_PENCIL_COLOR),
            getattr(stroke, "width", DEFAULT_PENCIL_WIDTH),
        )

    def _draw_pencil_points(self, points, color, width, dashed=False):
        if len(points) < 4:
            return
        self.canvas.create_line(
            *points,
            fill=color,
            width=width,
            capstyle=tk.ROUND,
            joinstyle=tk.ROUND,
            smooth=True,
            splinesteps=12,
            dash=(4, 3) if dashed else None,
        )

    def _draw_text_label(self, text):
        self.canvas.create_text(
            text.x,
            text.y,
            text=text.text,
            fill=text.color,
            font=("Segoe UI", text.font_size),
            anchor=tk.NW,
            width=max(20, text.width - 8),
        )

    def _draw_temp_box(self, box, color, label):
        x0, y0, x1, y1 = box
        self.canvas.create_rectangle(x0, y0, x1, y1, outline=color, width=1.6, dash=(5, 3))
        if abs(x1 - x0) > 45 and abs(y1 - y0) > 20:
            self.canvas.create_text(min(x0, x1) + 6, min(y0, y1) + 6, text=label, anchor=tk.NW, fill=color, font=("Segoe UI", 9))

    def _draw_region_shape_preview(self, box, shape):
        x0, y0, x1, y1 = box
        if shape == "circle":
            cx = (x0 + x1) / 2
            cy = (y0 + y1) / 2
            radius = min(abs(x1 - x0), abs(y1 - y0)) / 2
            self.canvas.create_oval(cx - radius, cy - radius, cx + radius, cy + radius, outline=self.shadow_color, width=1.8, dash=(5, 3))
        elif shape == "ellipse":
            self.canvas.create_oval(x0, y0, x1, y1, outline=self.shadow_color, width=1.8, dash=(5, 3))
        elif shape == "triangle":
            points = self._region_points_from_box(box, "triangle")
            if points:
                self.canvas.create_line(*points, points[0], points[1], fill=self.shadow_color, width=1.8, dash=(5, 3))
        else:
            self._draw_temp_box(box, self.shadow_color, "区域")

    def _draw_selection_outline(self):
        for key, obj in self._selected_targets():
            if key[0] == "node":
                radius = getattr(obj, "radius", NODE_RADIUS) + 5
                self.canvas.create_oval(
                    obj.x - radius,
                    obj.y - radius,
                    obj.x + radius,
                    obj.y + radius,
                    outline=SELECTION_COLOR,
                    width=2,
                    dash=(4, 3),
                )
            elif key[0] == "edge":
                source = self._find_node_by_id(obj.source)
                target = self._find_node_by_id(obj.target)
                if source and target:
                    self._draw_edge_path(
                        self._edge_geometry(obj, source, target),
                        SELECTION_COLOR,
                        max(obj.width + 3, 4),
                        False,
                        obj.style,
                        dashed=True,
                    )
            elif key[0] == "text":
                self.canvas.create_rectangle(*self._text_bbox(obj), outline=SELECTION_COLOR, width=2, dash=(4, 3))
            elif key[0] == "region" and len(obj.points) >= 6:
                self.canvas.create_polygon(obj.points, fill="", outline=SELECTION_COLOR, width=2, dash=(4, 3))
            elif key[0] == "pencil":
                self._draw_pencil_points(
                    obj.points,
                    SELECTION_COLOR,
                    max(getattr(obj, "width", DEFAULT_PENCIL_WIDTH) + 3, 4),
                    dashed=True,
                )

    def _alpha_to_stipple(self, alpha):
        keys = sorted(STIPPLE_PATTERNS.keys())
        for key in keys:
            if alpha <= key:
                return STIPPLE_PATTERNS[key]
        return STIPPLE_PATTERNS[keys[-1]]

    def _open_style_dialog(self, targets):
        targets = [(key, obj) for key, obj in targets if obj is not None]
        if not targets:
            return

        kinds = {key[0] for key, _ in targets}
        dialog = tk.Toplevel(self.root)
        dialog.title("批量样式" if len(targets) > 1 else "样式")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        frame = ttk.Frame(dialog, padding=14)
        frame.pack(fill=tk.BOTH, expand=True)

        row = 0
        color_var = tk.StringVar(value=self._common_value([getattr(obj, "color", "") for _, obj in targets]) or "")
        color_label = "颜色 / 点内部" if "node" in kinds else "颜色"
        ttk.Label(frame, text=color_label).grid(row=row, column=0, sticky=tk.W, pady=4)
        ttk.Entry(frame, textvariable=color_var, width=16).grid(row=row, column=1, sticky=tk.EW, pady=4)
        ttk.Button(frame, text="选择", command=lambda: self._pick_color_into(color_var)).grid(row=row, column=2, padx=(8, 0), pady=4)
        row += 1

        node_radius_var = tk.StringVar(value="")
        node_outline_color_var = tk.StringVar(value="")
        node_label_position_var = tk.StringVar(value=NODE_LABEL_POSITION_LABEL_BY_VALUE[DEFAULT_NODE_LABEL_POSITION])
        node_label_color_var = tk.StringVar(value="")
        node_label_size_var = tk.StringVar(value="")
        if "node" in kinds:
            node_values = [str(obj.radius) for key, obj in targets if key[0] == "node"]
            outline_values = [getattr(obj, "outline_color", DEFAULT_NODE_OUTLINE_COLOR) for key, obj in targets if key[0] == "node"]
            label_color_values = [getattr(obj, "label_color", DEFAULT_NODE_LABEL_COLOR) for key, obj in targets if key[0] == "node"]
            label_size_values = [str(getattr(obj, "label_size", DEFAULT_NODE_LABEL_SIZE)) for key, obj in targets if key[0] == "node"]
            label_position_values = [
                getattr(obj, "label_position", DEFAULT_NODE_LABEL_POSITION)
                for key, obj in targets
                if key[0] == "node"
            ]
            node_outline_color_var.set(self._common_value(outline_values) or self.node_outline_color)
            ttk.Label(frame, text="点边缘颜色").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Entry(frame, textvariable=node_outline_color_var, width=16).grid(row=row, column=1, sticky=tk.EW, pady=4)
            ttk.Button(frame, text="选择", command=lambda: self._pick_color_into(node_outline_color_var)).grid(row=row, column=2, padx=(8, 0), pady=4)
            row += 1
            node_label_color_var.set(self._common_value(label_color_values) or self.node_label_color)
            ttk.Label(frame, text="点标签颜色").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Entry(frame, textvariable=node_label_color_var, width=16).grid(row=row, column=1, sticky=tk.EW, pady=4)
            ttk.Button(frame, text="选择", command=lambda: self._pick_color_into(node_label_color_var)).grid(row=row, column=2, padx=(8, 0), pady=4)
            row += 1
            node_radius_var.set(self._common_value(node_values) or str(self._current_node_radius()))
            ttk.Label(frame, text="点大小").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Spinbox(frame, from_=6, to=80, width=8, textvariable=node_radius_var).grid(row=row, column=1, sticky=tk.W, pady=4)
            row += 1
            node_label_size_var.set(self._common_value(label_size_values) or str(self._current_node_label_size()))
            ttk.Label(frame, text="点标签字号").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Spinbox(frame, from_=6, to=64, width=8, textvariable=node_label_size_var).grid(row=row, column=1, sticky=tk.W, pady=4)
            row += 1
            common_label_position = self._common_value(label_position_values) or DEFAULT_NODE_LABEL_POSITION
            node_label_position_var.set(NODE_LABEL_POSITION_LABEL_BY_VALUE.get(common_label_position, NODE_LABEL_POSITION_LABEL_BY_VALUE[DEFAULT_NODE_LABEL_POSITION]))
            ttk.Label(frame, text="标签位置").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Combobox(
                frame,
                state="readonly",
                width=8,
                textvariable=node_label_position_var,
                values=[label for _, label in NODE_LABEL_POSITIONS],
            ).grid(row=row, column=1, sticky=tk.W, pady=4)
            row += 1

        edge_width_var = tk.StringVar(value="")
        edge_style_var = tk.StringVar(value=EDGE_STYLE_LABEL_BY_VALUE[DEFAULT_EDGE_STYLE])
        edge_directed_var = tk.BooleanVar(value=False)
        edge_label_color_var = tk.StringVar(value="")
        edge_label_size_var = tk.StringVar(value="")
        if "edge" in kinds:
            width_values = [str(obj.width) for key, obj in targets if key[0] == "edge"]
            style_values = [obj.style for key, obj in targets if key[0] == "edge"]
            directed_values = [obj.directed for key, obj in targets if key[0] == "edge"]
            label_color_values = [getattr(obj, "label_color", DEFAULT_EDGE_LABEL_COLOR) for key, obj in targets if key[0] == "edge"]
            label_size_values = [str(getattr(obj, "label_size", DEFAULT_EDGE_LABEL_SIZE)) for key, obj in targets if key[0] == "edge"]
            edge_width_var.set(self._common_value(width_values) or str(self._current_edge_width()))
            edge_style_var.set(EDGE_STYLE_LABEL_BY_VALUE.get(self._common_value(style_values), self.edge_style.get()))
            edge_directed_var.set(self._common_value(directed_values) if self._common_value(directed_values) is not None else self.directed.get())
            edge_label_color_var.set(self._common_value(label_color_values) or self.edge_label_color)
            ttk.Label(frame, text="边标签颜色").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Entry(frame, textvariable=edge_label_color_var, width=16).grid(row=row, column=1, sticky=tk.EW, pady=4)
            ttk.Button(frame, text="选择", command=lambda: self._pick_color_into(edge_label_color_var)).grid(row=row, column=2, padx=(8, 0), pady=4)
            row += 1
            ttk.Label(frame, text="线宽").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Spinbox(frame, from_=1, to=16, increment=0.5, width=8, textvariable=edge_width_var).grid(row=row, column=1, sticky=tk.W, pady=4)
            row += 1
            edge_label_size_var.set(self._common_value(label_size_values) or str(self._current_edge_label_size()))
            ttk.Label(frame, text="边标签字号").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Spinbox(frame, from_=6, to=64, width=8, textvariable=edge_label_size_var).grid(row=row, column=1, sticky=tk.W, pady=4)
            row += 1
            ttk.Label(frame, text="线型").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Combobox(
                frame,
                state="readonly",
                width=10,
                textvariable=edge_style_var,
                values=[label for _, label in EDGE_STYLES],
            ).grid(row=row, column=1, sticky=tk.W, pady=4)
            row += 1
            ttk.Checkbutton(frame, text="有向边", variable=edge_directed_var).grid(row=row, column=1, sticky=tk.W, pady=4)
            row += 1

        text_size_var = tk.StringVar(value="")
        text_width_var = tk.StringVar(value="")
        text_height_var = tk.StringVar(value="")
        if "text" in kinds:
            text_objects = [obj for key, obj in targets if key[0] == "text"]
            text_size_var.set(self._common_value([str(obj.font_size) for obj in text_objects]) or str(self._current_text_size()))
            text_width_var.set(self._common_value([str(obj.width) for obj in text_objects]) or str(DEFAULT_TEXT_WIDTH))
            text_height_var.set(self._common_value([str(obj.height) for obj in text_objects]) or str(DEFAULT_TEXT_HEIGHT))
            ttk.Label(frame, text="文字字号").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Spinbox(frame, from_=8, to=64, width=8, textvariable=text_size_var).grid(row=row, column=1, sticky=tk.W, pady=4)
            row += 1
            ttk.Label(frame, text="文本框宽").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Spinbox(frame, from_=40, to=800, width=8, textvariable=text_width_var).grid(row=row, column=1, sticky=tk.W, pady=4)
            row += 1
            ttk.Label(frame, text="文本框高").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Spinbox(frame, from_=24, to=500, width=8, textvariable=text_height_var).grid(row=row, column=1, sticky=tk.W, pady=4)
            row += 1

        pencil_width_var = tk.StringVar(value="")
        if "pencil" in kinds:
            width_values = [str(getattr(obj, "width", DEFAULT_PENCIL_WIDTH)) for key, obj in targets if key[0] == "pencil"]
            pencil_width_var.set(self._common_value(width_values) or str(self._current_pencil_width()))
            ttk.Label(frame, text="铅笔线宽").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Spinbox(frame, from_=1, to=24, increment=0.5, width=8, textvariable=pencil_width_var).grid(row=row, column=1, sticky=tk.W, pady=4)
            row += 1

        region_alpha_var = tk.StringVar(value="")
        if "region" in kinds:
            alpha_values = [str(obj.alpha) for key, obj in targets if key[0] == "region"]
            region_alpha_var.set(self._common_value(alpha_values) or str(self.shadow_alpha))
            ttk.Label(frame, text="区域透明度").grid(row=row, column=0, sticky=tk.W, pady=4)
            ttk.Spinbox(frame, from_=0.1, to=0.8, increment=0.05, width=8, textvariable=region_alpha_var).grid(row=row, column=1, sticky=tk.W, pady=4)
            row += 1

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=row, column=0, columnspan=3, sticky=tk.EW, pady=(12, 0))
        ttk.Button(button_frame, text="取消", command=dialog.destroy).pack(side=tk.RIGHT)
        ttk.Button(
            button_frame,
            text="应用",
            command=lambda: self._apply_style_dialog(
                dialog,
                targets,
                color_var,
                node_outline_color_var,
                node_label_position_var,
                node_label_color_var,
                node_label_size_var,
                node_radius_var,
                edge_width_var,
                edge_style_var,
                edge_directed_var,
                edge_label_color_var,
                edge_label_size_var,
                text_size_var,
                text_width_var,
                text_height_var,
                pencil_width_var,
                region_alpha_var,
            ),
        ).pack(side=tk.RIGHT, padx=(0, 8))

        frame.columnconfigure(1, weight=1)
        dialog.wait_visibility()
        dialog.grab_set()

    def _apply_style_dialog(
        self,
        dialog,
        targets,
        color_var,
        node_outline_color_var,
        node_label_position_var,
        node_label_color_var,
        node_label_size_var,
        node_radius_var,
        edge_width_var,
        edge_style_var,
        edge_directed_var,
        edge_label_color_var,
        edge_label_size_var,
        text_size_var,
        text_width_var,
        text_height_var,
        pencil_width_var,
        region_alpha_var,
    ):
        try:
            node_radius = self._parse_number(node_radius_var.get(), NODE_RADIUS, 4, 120, int)
            node_label_size = self._parse_number(node_label_size_var.get(), DEFAULT_NODE_LABEL_SIZE, 6, 96, int)
            edge_width = self._parse_number(edge_width_var.get(), DEFAULT_EDGE_WIDTH, 0.5, 24, float)
            edge_label_size = self._parse_number(edge_label_size_var.get(), DEFAULT_EDGE_LABEL_SIZE, 6, 96, int)
            text_size = self._parse_number(text_size_var.get(), DEFAULT_TEXT_SIZE, 6, 96, int)
            text_width = self._parse_number(text_width_var.get(), DEFAULT_TEXT_WIDTH, 20, 1200, int)
            text_height = self._parse_number(text_height_var.get(), DEFAULT_TEXT_HEIGHT, 20, 900, int)
            pencil_width = self._parse_number(pencil_width_var.get(), DEFAULT_PENCIL_WIDTH, 1, 24, float)
            region_alpha = self._parse_number(region_alpha_var.get(), DEFAULT_SHADOW_ALPHA, 0.05, 0.95, float)
        except ValueError:
            messagebox.showwarning("样式无效", "大小、粗细和透明度需要填写有效数字。", parent=dialog)
            return

        color = color_var.get().strip()
        node_outline_color = node_outline_color_var.get().strip()
        node_label_color = node_label_color_var.get().strip()
        edge_label_color = edge_label_color_var.get().strip()
        node_label_position = NODE_LABEL_POSITION_VALUE_BY_LABEL.get(
            node_label_position_var.get(),
            node_label_position_var.get(),
        )
        if node_label_position not in NODE_LABEL_POSITION_LABEL_BY_VALUE:
            node_label_position = DEFAULT_NODE_LABEL_POSITION
        style = EDGE_STYLE_VALUE_BY_LABEL.get(edge_style_var.get(), edge_style_var.get())

        self._save_history()
        for key, obj in targets:
            if color and hasattr(obj, "color"):
                obj.color = color
            if key[0] == "node":
                obj.radius = node_radius
                if node_outline_color:
                    obj.outline_color = node_outline_color
                obj.label_position = node_label_position
                if node_label_color:
                    obj.label_color = node_label_color
                obj.label_size = node_label_size
            elif key[0] == "edge":
                obj.width = edge_width
                obj.style = style if style in EDGE_DASH_PATTERNS else DEFAULT_EDGE_STYLE
                obj.directed = edge_directed_var.get()
                if edge_label_color:
                    obj.label_color = edge_label_color
                obj.label_size = edge_label_size
            elif key[0] == "text":
                obj.font_size = text_size
                obj.width = text_width
                obj.height = text_height
            elif key[0] == "pencil":
                obj.width = pencil_width
            elif key[0] == "region":
                obj.alpha = region_alpha

        dialog.destroy()
        self.draw_canvas()

    def _pick_color_into(self, color_var):
        color = colorchooser.askcolor(title="选择颜色", initialcolor=color_var.get() or "#333333")[1]
        if color:
            color_var.set(color)

    def _choose_color_for_targets(self, targets):
        initial = self._common_value([getattr(obj, "color", "") for _, obj in targets]) or "#333333"
        color = colorchooser.askcolor(title="选择颜色", initialcolor=initial)[1]
        if not color:
            return
        self._save_history()
        for _, obj in targets:
            if hasattr(obj, "color"):
                obj.color = color
        self.draw_canvas()

    def _edit_single_target(self, key):
        obj = self._get_object(key)
        if obj is None:
            return
        kind = key[0]
        if kind == "text":
            self._open_text_editor_for_existing(obj)
            return

        title = {"node": "节点标签", "edge": "边标签", "region": "区域标签"}.get(kind, "标签")
        prompt = {"node": "输入节点标签：", "edge": "输入边标签：", "region": "输入区域标签："}.get(kind, "输入标签：")
        text = simpledialog.askstring(title, prompt, initialvalue=getattr(obj, "label", ""))
        if text is not None and text.strip() != getattr(obj, "label", ""):
            self._save_history()
            obj.label = text.strip()
            self.draw_canvas()

    def _common_value(self, values):
        if not values:
            return None
        first = values[0]
        if all(value == first for value in values):
            return first
        return None

    def _parse_number(self, value, default, minimum, maximum, cast):
        if value == "":
            number = default
        else:
            number = cast(float(value))
        return max(minimum, min(maximum, number))

    def export_image(self, fmt):
        if Image is None or ImageGrab is None:
            messagebox.showwarning("缺少依赖", "导出功能需要安装 Pillow。请执行: pip install Pillow")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("所有文件", "*.*")],
        )
        if not path:
            return

        self.root.update_idletasks()
        bbox = (
            self.root.winfo_rootx() + self.canvas.winfo_x(),
            self.root.winfo_rooty() + self.canvas.winfo_y(),
            self.root.winfo_rootx() + self.canvas.winfo_x() + self.canvas.winfo_width(),
            self.root.winfo_rooty() + self.canvas.winfo_y() + self.canvas.winfo_height(),
        )
        try:
            image = ImageGrab.grab(bbox)
            if fmt.lower() == "png":
                image.save(path, "PNG")
            else:
                image.save(path, "PDF", resolution=300)
            messagebox.showinfo("导出成功", f"已导出文件: {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror("导出失败", f"图像导出失败：{exc}")

    def export_tikz(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("TikZ 预览 / 复制")
        dialog.geometry("820x560")
        dialog.transient(self.root)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        text_frame = ttk.Frame(dialog, padding=(12, 12, 12, 0))
        text_frame.grid(row=0, column=0, sticky=tk.NSEW)
        text_frame.columnconfigure(0, weight=1)
        text_frame.rowconfigure(0, weight=1)

        text_widget = tk.Text(text_frame, wrap=tk.NONE, undo=True, font=("Consolas", 10), bg="#fbfbfb", relief=tk.FLAT)
        y_scroll = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        x_scroll = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=text_widget.xview)
        text_widget.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        text_widget.grid(row=0, column=0, sticky=tk.NSEW)
        y_scroll.grid(row=0, column=1, sticky=tk.NS)
        x_scroll.grid(row=1, column=0, sticky=tk.EW)
        text_widget.insert("1.0", self._generate_tikz())

        button_frame = ttk.Frame(dialog, padding=12)
        button_frame.grid(row=1, column=0, sticky=tk.EW)
        ttk.Button(button_frame, text="复制到剪贴板", command=lambda: self._copy_tikz_from_widget(text_widget)).pack(side=tk.LEFT)
        ttk.Button(button_frame, text="保存为 .tex", command=lambda: self._save_tikz_from_widget(text_widget)).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(button_frame, text="关闭", command=dialog.destroy).pack(side=tk.RIGHT)
        text_widget.focus_set()

    def _copy_tikz_from_widget(self, text_widget):
        self._copy_text_to_clipboard(text_widget.get("1.0", tk.END).rstrip())
        messagebox.showinfo("复制成功", "TikZ 代码已复制到剪贴板。")

    def _copy_text_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)

    def _save_tikz_from_widget(self, text_widget):
        path = filedialog.asksaveasfilename(
            parent=text_widget.winfo_toplevel(),
            defaultextension=".tex",
            filetypes=[("TikZ 代码", "*.tex"), ("文本文件", "*.txt")],
        )
        if not path:
            return
        tikz = text_widget.get("1.0", tk.END).rstrip() + "\n"
        with open(path, "w", encoding="utf-8") as f:
            f.write(tikz)
        messagebox.showinfo("导出成功", f"TikZ 已保存至 {os.path.basename(path)}")

    def export_matrices(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
        )
        if not path:
            return
        adjacency, incidence = self._build_matrices()
        adjacency_text, incidence_text = self._matrix_text_sections(adjacency, incidence)
        with open(path, "w", encoding="utf-8") as f:
            f.write("邻接矩阵:\n")
            f.write(adjacency_text)
            f.write("\n关联矩阵:\n")
            f.write(incidence_text)
        messagebox.showinfo("导出成功", f"矩阵已保存至 {os.path.basename(path)}")

    def show_matrices(self):
        adjacency, incidence = self._build_matrices()
        adjacency_text, incidence_text = self._matrix_text_sections(adjacency, incidence)
        content = "邻接矩阵:\n" + adjacency_text
        content += "\n关联矩阵:\n" + incidence_text
        self.matrix_text.delete("1.0", tk.END)
        self.matrix_text.insert(tk.END, content)

    def _build_matrices(self):
        return MatrixBuilder.build(self.nodes, self.edges)

    def _format_matrix(self, matrix):
        return MatrixBuilder.format(matrix)

    def _matrix_text_sections(self, adjacency, incidence):
        if not self.matrix_show_labels.get():
            return self._format_matrix(adjacency), self._format_matrix(incidence)

        node_labels = [self._node_matrix_label(node) for node in self.nodes]
        edge_labels = [self._edge_matrix_label(edge) for edge in self.edges]
        return (
            self._format_labeled_matrix(adjacency, node_labels, node_labels),
            self._format_labeled_matrix(incidence, node_labels, edge_labels),
        )

    def _format_labeled_matrix(self, matrix, row_labels, col_labels):
        header = [""] + col_labels
        rows = ["\t".join(header)]
        for label, row in zip(row_labels, matrix):
            rows.append("\t".join([label] + [str(value) for value in row]))
        return "\n".join(rows)

    def _generate_tikz(self):
        width = int(self.canvas.winfo_width() or CANVAS_DEFAULT_WIDTH)
        height = int(self.canvas.winfo_height() or CANVAS_DEFAULT_HEIGHT)
        exporter = TikzExporter(
            self.nodes,
            self.edges,
            self.regions,
            self.texts,
            self._current_background_settings(),
            width,
            height,
            pencil_strokes=self.pencil_strokes,
            show_node_labels=self.show_node_labels.get(),
            show_edge_labels=self.show_edge_labels.get(),
        )
        return exporter.generate()

    def _current_node_radius(self):
        return self._parse_number(self.node_radius.get(), NODE_RADIUS, 4, 120, int)

    def _current_node_label_position(self):
        position = NODE_LABEL_POSITION_VALUE_BY_LABEL.get(
            self.node_label_position.get(),
            self.node_label_position.get(),
        )
        return position if position in NODE_LABEL_POSITION_LABEL_BY_VALUE else DEFAULT_NODE_LABEL_POSITION

    def _current_node_label_size(self):
        return self._parse_number(self.node_label_size.get(), DEFAULT_NODE_LABEL_SIZE, 6, 96, int)

    def _node_label_text(self, node):
        if node.label:
            return node.label
        if self.show_node_labels.get():
            try:
                return str(self.nodes.index(node) + 1)
            except ValueError:
                return str(node.id)
        return ""

    def _edge_label_text(self, edge):
        if edge.label:
            return edge.label
        if self.show_edge_labels.get():
            try:
                return self._edge_auto_label(self.edges.index(edge))
            except ValueError:
                return self._edge_auto_label(max(0, edge.id - 1))
        return ""

    def _node_matrix_label(self, node):
        return node.label or str(self.nodes.index(node) + 1)

    def _edge_matrix_label(self, edge):
        return edge.label or self._edge_auto_label(self.edges.index(edge))

    def _edge_auto_label(self, index):
        label = ""
        value = index
        while True:
            label = chr(ord("a") + value % 26) + label
            value = value // 26 - 1
            if value < 0:
                return label

    def _current_edge_width(self):
        return self._parse_number(self.edge_width.get(), DEFAULT_EDGE_WIDTH, 0.5, 24, float)

    def _current_edge_label_size(self):
        return self._parse_number(self.edge_label_size.get(), DEFAULT_EDGE_LABEL_SIZE, 6, 96, int)

    def _current_edge_style(self):
        style = EDGE_STYLE_VALUE_BY_LABEL.get(self.edge_style.get(), self.edge_style.get())
        return style if style in EDGE_DASH_PATTERNS else DEFAULT_EDGE_STYLE

    def _current_text_size(self):
        return self._parse_number(self.text_size.get(), DEFAULT_TEXT_SIZE, 6, 96, int)

    def _current_pencil_width(self):
        return self._parse_number(self.pencil_width.get(), DEFAULT_PENCIL_WIDTH, 1, 24, float)

    def _current_region_alpha(self):
        return self._parse_number(self.region_alpha.get(), DEFAULT_SHADOW_ALPHA, 0.05, 0.95, float)

    def _current_region_shape(self):
        shape = REGION_SHAPE_VALUE_BY_LABEL.get(self.region_shape.get(), self.region_shape.get())
        return shape if shape in REGION_SHAPE_LABEL_BY_VALUE else DEFAULT_REGION_SHAPE

    def _point_in_polygon(self, x, y, poly):
        inside = False
        px = x
        py = y
        for i in range(0, len(poly), 2):
            x1, y1 = poly[i], poly[i + 1]
            x2, y2 = poly[(i + 2) % len(poly)], poly[(i + 3) % len(poly)]
            if ((y1 > py) != (y2 > py)) and (px < (x2 - x1) * (py - y1) / (y2 - y1 + 1e-6) + x1):
                inside = not inside
        return inside

    def _update_status(self):
        selected_count = len(self.selection)
        suffix = f" 当前选中 {selected_count} 个对象。" if selected_count else ""
        self.status_text.set(f"{MODE_HINTS.get(self.mode.get(), '')}{suffix}")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    GraphDrawer().run()
