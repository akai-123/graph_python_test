from dataclasses import dataclass, field
from typing import Optional


CANVAS_DEFAULT_WIDTH = 880
CANVAS_DEFAULT_HEIGHT = 700
NODE_RADIUS = 5

DEFAULT_NODE_COLOR = "#000000"
DEFAULT_NODE_OUTLINE_COLOR = "#20252b"
DEFAULT_NODE_LABEL_POSITION = "inside"
DEFAULT_NODE_LABEL_COLOR = "#ffffff"
DEFAULT_NODE_LABEL_SIZE = 11
DEFAULT_EDGE_COLOR = "#333333"
DEFAULT_EDGE_LABEL_COLOR = "#333333"
DEFAULT_EDGE_LABEL_SIZE = 10
DEFAULT_TEXT_COLOR = "#222222"
DEFAULT_SHADOW_COLOR = "#90caf9"
DEFAULT_SHADOW_ALPHA = 0.35
DEFAULT_REGION_SHAPE = "free"
DEFAULT_EDGE_WIDTH = 2.6
DEFAULT_EDGE_STYLE = "solid"
DEFAULT_TEXT_SIZE = 12
DEFAULT_TEXT_WIDTH = 180
DEFAULT_TEXT_HEIGHT = 54
DEFAULT_PENCIL_COLOR = "#e11d48"
DEFAULT_PENCIL_WIDTH = 2.2

DEFAULT_BACKGROUND_MODE = "none"
DEFAULT_AXIS_SCALE = 40.0
DEFAULT_AXIS_ORIGIN_X = 80
DEFAULT_AXIS_ORIGIN_Y = 620
MIN_AXIS_SCALE = 8.0

BACKGROUND_MODES = (
    ("none", "空白"),
    ("grid", "网格"),
    ("axes", "坐标轴"),
)

NODE_LABEL_POSITIONS = (
    ("inside", "点内"),
    ("beside", "旁边"),
)

REGION_SHAPES = (
    ("free", "自由"),
    ("rectangle", "矩形"),
    ("circle", "圆形"),
    ("ellipse", "椭圆"),
    ("triangle", "三角形"),
)

EDGE_STYLES = (
    ("solid", "实线"),
    ("dashed", "虚线"),
    ("dotted", "点线"),
    ("dashdot", "点划线"),
)

STIPPLE_PATTERNS = {
    0.15: "gray75",
    0.3: "gray50",
    0.5: "gray25",
    0.75: "gray12",
}


@dataclass
class Node:
    id: int
    x: int
    y: int
    color: str = DEFAULT_NODE_COLOR
    label: str = field(default_factory=lambda: "")
    radius: int = NODE_RADIUS
    outline_color: str = DEFAULT_NODE_OUTLINE_COLOR
    label_position: str = DEFAULT_NODE_LABEL_POSITION
    label_color: str = DEFAULT_NODE_LABEL_COLOR
    label_size: int = DEFAULT_NODE_LABEL_SIZE


@dataclass
class Edge:
    source: int
    target: int
    color: str = DEFAULT_EDGE_COLOR
    directed: bool = False
    label: str = field(default_factory=lambda: "")
    width: float = DEFAULT_EDGE_WIDTH
    style: str = DEFAULT_EDGE_STYLE
    id: int = 0
    label_color: str = DEFAULT_EDGE_LABEL_COLOR
    label_size: int = DEFAULT_EDGE_LABEL_SIZE
    curve_offset: Optional[float] = None


@dataclass
class Region:
    points: list
    color: str
    alpha: float
    label: str = field(default_factory=lambda: "")
    id: int = 0


@dataclass
class TextLabel:
    x: int
    y: int
    text: str
    color: str = DEFAULT_TEXT_COLOR
    font_size: int = DEFAULT_TEXT_SIZE
    width: int = DEFAULT_TEXT_WIDTH
    height: int = DEFAULT_TEXT_HEIGHT
    id: int = 0


@dataclass
class PencilStroke:
    points: list
    color: str = DEFAULT_PENCIL_COLOR
    width: float = DEFAULT_PENCIL_WIDTH
    id: int = 0


@dataclass
class BackgroundSettings:
    mode: str = DEFAULT_BACKGROUND_MODE
    axis_scale: float = DEFAULT_AXIS_SCALE
    axis_origin_x: int = DEFAULT_AXIS_ORIGIN_X
    axis_origin_y: int = DEFAULT_AXIS_ORIGIN_Y

    def normalized_scale(self):
        return max(MIN_AXIS_SCALE, float(self.axis_scale))

    def canvas_to_units(self, x, y):
        scale = self.normalized_scale()
        return (
            (x - self.axis_origin_x) / scale,
            (self.axis_origin_y - y) / scale,
        )
