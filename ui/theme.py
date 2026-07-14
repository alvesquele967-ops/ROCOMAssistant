"""
竹雨ROCOM小助手 - 全局主题
集中管理颜色 / 字体 / ttk 样式 / 通用小组件
"""

import tkinter as tk
from tkinter import ttk

# ═══════════════════════════════════════════════════════════════════════
# 色板
# ═══════════════════════════════════════════════════════════════════════

PRIMARY = "#5B7FFF"       # 主色 (柔和蓝紫)
PRIMARY_HOVER = "#4A6AE8"
PRIMARY_DARK = "#3D5AD4"

SUCCESS = "#00B894"       # 成功绿
SUCCESS_HOVER = "#00A381"
SUCCESS_DARK = "#008F6E"

DANGER = "#FF6B6B"        # 危险红
DANGER_HOVER = "#EE5A5A"
DANGER_DARK = "#E04A4A"

WARNING = "#FDCB6E"       # 警告黄
WARNING_HOVER = "#F0B800"

INFO = "#74B9FF"          # 信息蓝
INFO_HOVER = "#5AA8F0"

NEUTRAL = "#636E72"       # 中灰
NEUTRAL_LIGHT = "#B2BEC3"
NEUTRAL_DARK = "#2D3436"

BG_APP = "#F0F2F5"        # 应用底
BG_CARD = "#FFFFFF"       # 卡片白
BG_SIDEBAR = "#F8F9FA"    # 侧栏底
BG_DARK = "#1E272E"       # 深底（状态栏）

TEXT_PRIMARY = "#2D3436"   # 主文字
TEXT_SECONDARY = "#636E72" # 次文字
TEXT_HINT = "#B2BEC3"      # 占位/提示

BORDER = "#DFE6E9"         # 边框

# 属性色（保持原版精灵配色）
TYPE_COLORS = {
    "普通": "#A8A878", "草": "#78C850", "火": "#F08030", "水": "#6890F0",
    "光": "#F8D030", "地": "#E0C068", "冰": "#98D8D8", "龙": "#7038F8",
    "电": "#F8D030", "毒": "#A040A0", "虫": "#A8B820", "武": "#C03028",
    "翼": "#A890F0", "萌": "#EE99AC", "幽": "#705898", "恶": "#705848",
    "幻": "#B8A038", "机械": "#B8B8D0",
}

# 雷达图属性色
RADAR_TYPE_COLORS = {
    "火": "#E74C3C", "水": "#3498DB", "草": "#27AE60", "电": "#F1C40F",
    "冰": "#85C1E9", "普通": "#A8A878", "地": "#E0C068", "龙": "#7038F8",
    "毒": "#A040A0", "虫": "#A8B820", "武": "#C03028", "翼": "#A890F0",
    "萌": "#EE99AC", "幽": "#705898", "恶": "#705848", "光": "#F8D030",
    "幻": "#B8A038", "机械": "#B8B8D0",
}

# ═══════════════════════════════════════════════════════════════════════
# 字体
# ═══════════════════════════════════════════════════════════════════════

FONT_FAMILY = "Microsoft YaHei"

FONT_TITLE = (FONT_FAMILY, 14, "bold")
FONT_HEADING = (FONT_FAMILY, 11, "bold")
FONT_BODY = (FONT_FAMILY, 10)
FONT_SMALL = (FONT_FAMILY, 9)
FONT_CAPTION = (FONT_FAMILY, 8)

# ═══════════════════════════════════════════════════════════════════════
# 间距
# ═══════════════════════════════════════════════════════════════════════

PAD_X = 10
PAD_Y = 6
PAD_CARD = 12   # 卡片内边距
GAP = 4         # 元素间小间距

# ═══════════════════════════════════════════════════════════════════════
# ttk 样式
# ═══════════════════════════════════════════════════════════════════════

def configure_ttk():
    """全局 ttk 样式配置，在创建 Tk 窗口后调用"""
    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")

    # Notebook
    style.configure(
        "TNotebook",
        background=BG_APP,
        borderwidth=0,
    )
    style.configure(
        "TNotebook.Tab",
        background=BG_SIDEBAR,
        foreground=TEXT_PRIMARY,
        font=FONT_BODY,
        padding=(14, 6),
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", PRIMARY), ("active", "#E8EBF0")],
        foreground=[("selected", "#FFFFFF")],
    )

    # LabelFrame
    style.configure(
        "TLabelframe",
        background=BG_CARD,
        borderwidth=1,
        relief="solid",
    )
    style.configure(
        "TLabelframe.Label",
        background=BG_CARD,
        foreground=TEXT_PRIMARY,
        font=FONT_HEADING,
    )

    # Frame
    style.configure("TFrame", background=BG_APP)

    # Label
    style.configure("TLabel", background=BG_APP, foreground=TEXT_PRIMARY, font=FONT_BODY)
    style.configure("Title.TLabel", font=FONT_TITLE, foreground=TEXT_PRIMARY)
    style.configure("Heading.TLabel", font=FONT_HEADING, foreground=TEXT_PRIMARY)
    style.configure("Hint.TLabel", font=FONT_SMALL, foreground=TEXT_HINT)

    # Entry
    style.configure(
        "TEntry",
        fieldbackground=BG_CARD,
        borderwidth=1,
        relief="solid",
        padding=6,
    )

    # Scrollbar
    style.configure(
        "TScrollbar",
        background=BG_SIDEBAR,
        troughcolor=BG_APP,
        borderwidth=0,
        arrowsize=14,
        arrowcolor=TEXT_HINT,
    )


# ═══════════════════════════════════════════════════════════════════════
# 通用小组件工厂
# ═══════════════════════════════════════════════════════════════════════

class StyledButton(tk.Button):
    """统一样式的按钮"""
    COLORS = {
        "primary": (PRIMARY, PRIMARY_HOVER, "#FFFFFF"),
        "success": (SUCCESS, SUCCESS_HOVER, "#FFFFFF"),
        "danger": (DANGER, DANGER_HOVER, "#FFFFFF"),
        "warning": (WARNING, WARNING_HOVER, TEXT_PRIMARY),
        "neutral": (NEUTRAL, NEUTRAL_LIGHT, "#FFFFFF"),
    }

    def __init__(self, parent, text="", variant="primary", size="normal", **kwargs):
        bg, hover_bg, fg = self.COLORS.get(variant, self.COLORS["primary"])
        font_map = {"small": FONT_SMALL, "normal": FONT_BODY, "large": FONT_HEADING}
        font = font_map.get(size, FONT_BODY)
        pad_map = {"small": (6, 2), "normal": (10, 4), "large": (14, 6)}
        padx, pady = pad_map.get(size, (10, 4))

        kwargs.setdefault("text", text)
        kwargs.setdefault("bg", bg)
        kwargs.setdefault("fg", fg)
        kwargs.setdefault("font", font)
        kwargs.setdefault("relief", tk.FLAT)
        kwargs.setdefault("cursor", "hand2")
        kwargs.setdefault("padx", padx)
        kwargs.setdefault("pady", pady)
        kwargs.setdefault("activebackground", hover_bg)
        kwargs.setdefault("activeforeground", fg)
        kwargs.setdefault("borderwidth", 0)
        super().__init__(parent, **kwargs)
        self._hover_bg = hover_bg
        self._bg = bg
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, _e):
        if self["state"] == "normal":
            self.configure(bg=self._hover_bg)

    def _on_leave(self, _e):
        if self["state"] == "normal":
            self.configure(bg=self._bg)


def section_header(parent, text, **kwargs):
    """统一的区块标题"""
    frame = ttk.Frame(parent)
    frame.pack(fill=tk.X, padx=PAD_X, pady=(PAD_Y + 2, 2))
    ttk.Label(frame, text=text, style="Heading.TLabel").pack(side=tk.LEFT)


def make_card(parent, **pack_kw):
    """创建白底卡片容器。用 ttk.Frame 包一层 tk.Frame 来获得白底"""
    outer = ttk.Frame(parent)
    inner = tk.Frame(outer, bg=BG_CARD, highlightbackground=BORDER, highlightthickness=1)
    inner.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=2)
    outer.pack(**pack_kw)
    return inner