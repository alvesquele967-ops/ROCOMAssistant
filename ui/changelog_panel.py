"""
竹雨ROCOM小助手 - 更新日志面板
读取 changelog.json 并展示
"""

import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
from ui.theme import (
    BG_CARD, BG_APP, PRIMARY, PRIMARY_HOVER,
    TEXT_SECONDARY, TEXT_HINT,
    FONT_BODY, FONT_SMALL, FONT_CAPTION,
    PAD_X,
)

CHANGELOG_FILE = Path(__file__).parent.parent / "changelog.json"


class ChangelogPanel(ttk.Frame):
    """更新日志面板"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._build_ui()
        # 抖音标签（页脚）
        douyin_label = tk.Label(
            self,
            text="抖音：takesitaame",
            font=("Microsoft YaHei", 8),
            fg="#999999",
            bg="#EAECEE",  # 抖音页脚标签背景
        )
        douyin_label.pack(side=tk.BOTTOM, pady=(4, 2))

        self._load_changelog()

    def _build_ui(self):
        # 顶部标题栏
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=(8, 0))

        ttk.Label(
            header, text="更新日志",
            font=("Microsoft YaHei", 14, "bold"),
        ).pack(side=tk.LEFT)

        refresh_btn = tk.Button(
            header, text="刷新",
            font=FONT_SMALL,
            bg=PRIMARY, fg="white",
            activebackground=PRIMARY_HOVER,
            relief=tk.FLAT, cursor="hand2",
            borderwidth=0, padx=12, pady=3,
            command=self._load_changelog,
        )
        refresh_btn.pack(side=tk.RIGHT)

        ttk.Label(
            header,
            text=f"数据文件：{CHANGELOG_FILE}",
            font=("Microsoft YaHei", 8),
            foreground=TEXT_HINT,
        ).pack(side=tk.RIGHT, padx=(0, 10))

        # 分隔线
        sep = ttk.Separator(self, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, padx=10, pady=5)

        # 可滚动的 Canvas 作为内容区域
        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 8))

        self.canvas = tk.Canvas(
            canvas_frame,
            bg=BG_APP,
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw",
        )

        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮滚动
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        # 自适应宽度
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _load_changelog(self):
        """加载并渲染 changelog.json"""
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        if not CHANGELOG_FILE.exists():
            empty_label = ttk.Label(
                self.scrollable_frame,
                text=f"未找到 changelog.json\n请手动创建：{CHANGELOG_FILE}",
                font=FONT_SMALL,
                foreground=TEXT_HINT,
                justify=tk.CENTER,
            )
            empty_label.pack(pady=40)
            return

        try:
            with open(CHANGELOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            error_label = ttk.Label(
                self.scrollable_frame,
                text=f"changelog.json 解析失败：{e}",
                font=FONT_SMALL,
                foreground="#FF6B6B",
                justify=tk.CENTER,
            )
            error_label.pack(pady=40)
            return

        entries = data.get("entries", [])
        if not entries:
            ttk.Label(
                self.scrollable_frame,
                text="暂无更新日志",
                font=FONT_SMALL,
                foreground=TEXT_HINT,
            ).pack(pady=40)
            return

        for entry in entries:
            # 版本卡片
            card = tk.Frame(
                self.scrollable_frame,
                bg=BG_CARD,
                highlightbackground="#E0E0E0",
                highlightthickness=1,
            )
            card.pack(fill=tk.X, pady=(0, 10), padx=0)

            # 版本标题行
            title_row = tk.Frame(card, bg=BG_CARD)
            title_row.pack(fill=tk.X, padx=12, pady=(10, 4))

            version_label = tk.Label(
                title_row,
                text=entry.get("version", ""),
                font=("Microsoft YaHei", 12, "bold"),
                fg=PRIMARY,
                bg=BG_CARD,
            )
            version_label.pack(side=tk.LEFT)

            date_label = tk.Label(
                title_row,
                text=entry.get("date", ""),
                font=FONT_SMALL,
                fg=TEXT_SECONDARY,
                bg=BG_CARD,
            )
            date_label.pack(side=tk.RIGHT)

            # 变更列表
            changes = entry.get("changes", [])
            if changes:
                changes_frame = tk.Frame(card, bg=BG_CARD)
                changes_frame.pack(fill=tk.X, padx=12, pady=(0, 10))

                for change in changes:
                    change_row = tk.Frame(changes_frame, bg=BG_CARD)
                    change_row.pack(fill=tk.X, pady=1)

                    bullet = tk.Label(
                        change_row,
                        text="•",
                        font=FONT_BODY,
                        fg="#636E72",
                        bg=BG_CARD,
                        width=2,
                    )
                    bullet.pack(side=tk.LEFT)

                    change_label = tk.Label(
                        change_row,
                        text=change,
                        font=FONT_SMALL,
                        fg="#2D3436",
                        bg=BG_CARD,
                        anchor=tk.W,
                        justify=tk.LEFT,
                        wraplength=800,
                    )
                    change_label.pack(side=tk.LEFT, fill=tk.X, expand=True)