"""
竹雨ROCOM小助手 - 属性克制速查UI
"""

import tkinter as tk
from tkinter import ttk, messagebox
from core.type_data import (
    ALL_TYPES, TYPE_RELATIONS, get_effectiveness,
    get_type_info, SPECIAL_RULES
)
from ui.theme import (
    TYPE_COLORS, PRIMARY, PRIMARY_HOVER, SUCCESS, DANGER, SUCCESS_DARK, DANGER_DARK,
    WARNING, BG_CARD, BG_APP, TEXT_PRIMARY, TEXT_SECONDARY, BORDER,
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_CAPTION,
    PAD_X,
)


class TypeChartFrame(ttk.Frame):
    """属性克制速查面板"""

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


    def _build_ui(self):
        # 顶部标题
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, padx=PAD_X, pady=(6, 2))
        ttk.Label(
            title_frame, text="属性克制速查",
            font=FONT_TITLE,
        ).pack(side=tk.LEFT)

        ttk.Label(
            title_frame, text="选择主/副属性查看组合克制  |  单击查看单属性详情",
            font=FONT_SMALL, foreground=TEXT_SECONDARY,
        ).pack(side=tk.RIGHT)

        # ── 双属性选择器 ──
        dual_frame = ttk.Frame(self)
        dual_frame.pack(fill=tk.X, padx=PAD_X, pady=(2, 0))

        ttk.Label(dual_frame, text="主属性：", font=FONT_BODY).pack(side=tk.LEFT, padx=(0, 4))
        self.primary_var = tk.StringVar(value="")
        self.primary_combo = ttk.Combobox(
            dual_frame, textvariable=self.primary_var,
            values=ALL_TYPES, state="readonly",
            font=FONT_BODY, width=8,
        )
        self.primary_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.primary_combo.bind("<<ComboboxSelected>>", lambda e: self._on_dual_select())

        ttk.Label(dual_frame, text="副属性：", font=FONT_BODY).pack(side=tk.LEFT, padx=(0, 4))
        self.secondary_var = tk.StringVar(value="")
        self.secondary_combo = ttk.Combobox(
            dual_frame, textvariable=self.secondary_var,
            values=["（无）"] + ALL_TYPES, state="readonly",
            font=FONT_BODY, width=8,
        )
        self.secondary_combo.pack(side=tk.LEFT, padx=(0, 12))
        self.secondary_combo.bind("<<ComboboxSelected>>", lambda e: self._on_dual_select())

        ttk.Button(
            dual_frame, text="清除",
            command=self._clear_dual,
            width=5,
        ).pack(side=tk.LEFT)

        self.dual_status_label = ttk.Label(
            dual_frame, text="",
            font=FONT_SMALL, foreground=TEXT_SECONDARY,
        )
        self.dual_status_label.pack(side=tk.RIGHT)

        # 属性按钮网格
        grid_frame = ttk.Frame(self)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=4)

        self.type_buttons = {}
        cols = 6
        for i, type_name in enumerate(ALL_TYPES):
            row = i // cols
            col = i % cols
            bg = TYPE_COLORS.get(type_name, "#999999")
            btn = tk.Button(
                grid_frame,
                text=type_name,
                font=("Microsoft YaHei", 10, "bold"),
                width=8, height=2,
                bg=bg, fg="white",
                activebackground=PRIMARY_HOVER,
                relief=tk.FLAT,
                cursor="hand2",
                borderwidth=0,
                command=lambda t=type_name: self._show_type_detail(t),
            )
            btn.grid(row=row, column=col, padx=2, pady=2, sticky="nsew")
            self.type_buttons[type_name] = btn

        for i in range(cols):
            grid_frame.columnconfigure(i, weight=1)

        # 详情显示区域
        detail_frame = ttk.LabelFrame(self, text="属性详情", padding=10)
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=4)

        self.detail_text = tk.Text(
            detail_frame,
            font=FONT_BODY,
            wrap=tk.WORD,
            height=12,
            state=tk.DISABLED,
            bg=BG_CARD,
            relief=tk.FLAT,
            borderwidth=0,
            padx=8, pady=6,
        )
        self.detail_text.pack(fill=tk.BOTH, expand=True)

        # 特殊规则
        rules_frame = ttk.LabelFrame(self, text="特殊规则", padding=10)
        rules_frame.pack(fill=tk.X, padx=PAD_X, pady=4)

        rules_text = tk.Text(
            rules_frame,
            font=("Microsoft YaHei", 9),
            wrap=tk.WORD,
            height=6,
            state=tk.DISABLED,
            bg=BG_CARD,
            relief=tk.FLAT,
            borderwidth=0,
            padx=8, pady=6,
        )
        rules_text.pack(fill=tk.BOTH, expand=True)

        rules_text.configure(state=tk.NORMAL)
        rules_text.insert(tk.END, "核心规则：克制=2倍伤害 | 抵抗=0.5倍伤害 | 无关系=1倍伤害\n")
        rules_text.insert(tk.END, "双属性叠加：双克制=4倍 | 双抵抗=0.25倍 | 一克一抗=1倍\n\n")
        rules_text.insert(tk.END, "【双向克制】光↔幽、萌↔恶（互相打2倍）\n")
        rules_text.insert(tk.END, "【龙系特殊】龙打龙2倍，龙被龙/冰/萌2倍；龙抵抗草/火/水/电/飞\n")
        rules_text.insert(tk.END, "【机械肉盾】只被火/水/武克制，抵抗10种属性\n")
        rules_text.insert(tk.END, "【普通系】无克制，仅被武系克制，抵抗幽系\n")
        rules_text.configure(state=tk.DISABLED)

    def _show_type_detail(self, type_name):
        """显示属性详情"""
        info = get_type_info(type_name)
        self.detail_text.configure(state=tk.NORMAL)
        self.detail_text.delete(1.0, tk.END)

        self.detail_text.insert(tk.END, f"【{type_name}系】\n\n", "title")

        self.detail_text.insert(tk.END, "▶ 攻击克制（造成2倍伤害）：", "label")
        self.detail_text.insert(
            tk.END,
            "、".join(info["克制"]) if info["克制"] else "无",
            "good"
        )
        self.detail_text.insert(tk.END, "\n\n")

        self.detail_text.insert(tk.END, "▶ 攻击抵抗（造成0.5倍伤害）：", "label")
        self.detail_text.insert(
            tk.END,
            "、".join(info["抵抗"]) if info["抵抗"] else "无",
            "bad"
        )
        self.detail_text.insert(tk.END, "\n\n")

        self.detail_text.insert(tk.END, "▶ 被克制（受到2倍伤害）：", "label")
        self.detail_text.insert(
            tk.END,
            "、".join(info["被克制"]) if info["被克制"] else "无",
            "bad"
        )
        self.detail_text.insert(tk.END, "\n\n")

        self.detail_text.insert(tk.END, "▶ 被抵抗（受到0.5倍伤害）：", "label")
        self.detail_text.insert(
            tk.END,
            "、".join(info["被抵抗"]) if info["被抵抗"] else "无",
            "good"
        )
        self.detail_text.insert(tk.END, "\n")

        self.detail_text.tag_configure("title", font=("Microsoft YaHei", 12, "bold"))
        self.detail_text.tag_configure("label", font=FONT_HEADING)
        self.detail_text.tag_configure("good", foreground=SUCCESS_DARK)
        self.detail_text.tag_configure("bad", foreground=DANGER)
        self.detail_text.tag_configure("immune", foreground="#8E44AD", font=FONT_HEADING)

        self.detail_text.configure(state=tk.DISABLED)

        # 高亮当前选中的按钮
        for t, btn in self.type_buttons.items():
            native_bg = TYPE_COLORS.get(t, "#999999")
            if t == type_name:
                btn.configure(bg=DANGER_DARK, activebackground=DANGER)
            else:
                btn.configure(bg=native_bg, activebackground=PRIMARY_HOVER)

    # ── 双属性选择 ──────────────────────────────────────────────────

    def _clear_dual(self):
        self.primary_var.set("")
        self.secondary_var.set("")
        self.dual_status_label.configure(text="")
        # 重置按钮颜色
        for t, btn in self.type_buttons.items():
            btn.configure(bg=TYPE_COLORS.get(t, "#999999"), activebackground=PRIMARY_HOVER)

    def _on_dual_select(self):
        p = self.primary_var.get()
        s = self.secondary_var.get()
        if s == "（无）":
            s = ""
        if not p:
            self.dual_status_label.configure(text="请选择主属性")
            return
        types = [p]
        if s and s != p:
            types.append(s)
        self._show_dual_detail(types)
        # 高亮按钮
        for t, btn in self.type_buttons.items():
            base = TYPE_COLORS.get(t, "#999999")
            if t == p:
                btn.configure(bg="#E74C3C", activebackground="#C0392B")
            elif t == s and s:
                btn.configure(bg="#3498DB", activebackground="#2980B9")
            else:
                btn.configure(bg=base, activebackground=PRIMARY_HOVER)

    def _show_dual_detail(self, defend_types):
        """展示双属性精灵的攻防克制关系"""
        from core.type_data import _build_type_matchup
        mu = _build_type_matchup()

        label = "·".join(defend_types) if len(defend_types) == 2 else defend_types[0]
        self.dual_status_label.configure(text=f"当前精灵属性：{label}")

        # 计算每个攻击属性对当前双属性的克制系数
        atk_result = {"4x": [], "2x": [], "1x": [], "0.5x": [], "0.25x": []}
        for atk_type in ALL_TYPES:
            mul = 1.0
            for dt in defend_types:
                a_rel = mu.get(atk_type) or {}
                if dt in a_rel.get("attack_2x", []):
                    mul *= 2.0
                elif dt in a_rel.get("attack_half", []):
                    mul *= 0.5
            if mul >= 4:
                atk_result["4x"].append(atk_type)
            elif mul >= 2:
                atk_result["2x"].append(atk_type)
            elif mul >= 1:
                atk_result["1x"].append(atk_type)
            elif mul >= 0.5:
                atk_result["0.5x"].append(atk_type)
            else:
                atk_result["0.25x"].append(atk_type)

        # 计算此精灵攻击其他属性时的效果（两属性取最优）
        def_result = {"2x": set(), "0.5x": set(), "0x": set()}
        for atk_t in defend_types:
            a_rel = mu.get(atk_t) or {}
            for t in a_rel.get("attack_2x", []):
                def_result["2x"].add(t)
            for t in a_rel.get("attack_half", []):
                def_result["0.5x"].add(t)

        self.detail_text.configure(state=tk.NORMAL)
        self.detail_text.delete(1.0, tk.END)

        # 防守面：什么属性打它
        self.detail_text.insert(tk.END, f"【{label}】防守面\n\n", "title")
        self.detail_text.insert(tk.END, "受到攻击时的伤害倍率：\n", "label")

        for key, label_text, tag in [
            ("4x", "4倍弱点（致命）：", "bad4"),
            ("2x", "2倍弱点：", "bad"),
            ("0.25x", "0.25倍抵抗（极抗）：", "good4"),
            ("0.5x", "0.5倍抵抗：", "good"),
            ("1x", "1倍（正常）：", "normal"),
        ]:
            if atk_result[key]:
                self.detail_text.insert(tk.END, f"▶ {label_text}", "label")
                self.detail_text.insert(tk.END, "、".join(atk_result[key]), tag)
                self.detail_text.insert(tk.END, "\n")

        # 攻击面：它打什么克制
        self.detail_text.insert(tk.END, f"\n【{label}】攻击面\n\n", "title")
        self.detail_text.insert(tk.END, "选择攻击属性时对各系的克制效果：\n", "label")

        for atk_t in defend_types:
            a_rel = mu.get(atk_t) or {}
            to_2x = a_rel.get("attack_2x", [])
            to_half = a_rel.get("attack_half", [])
            self.detail_text.insert(tk.END, f"▶ {atk_t}系技能 克制：", "label")
            self.detail_text.insert(tk.END, "、".join(to_2x) if to_2x else "无", "good")
            self.detail_text.insert(tk.END, " | 抵抗：")
            self.detail_text.insert(tk.END, "、".join(to_half) if to_half else "无", "bad")
            self.detail_text.insert(tk.END, "\n")

        # 标签
        self.detail_text.tag_configure("title", font=("Microsoft YaHei", 12, "bold"))
        self.detail_text.tag_configure("label", font=FONT_HEADING)
        self.detail_text.tag_configure("good", foreground=SUCCESS_DARK)
        self.detail_text.tag_configure("good4", foreground="#27AE60", font=FONT_HEADING)
        self.detail_text.tag_configure("bad", foreground=DANGER)
        self.detail_text.tag_configure("bad4", foreground="#E74C3C", font=FONT_HEADING)
        self.detail_text.tag_configure("immune", foreground="#8E44AD", font=FONT_HEADING)
        self.detail_text.tag_configure("normal", foreground=TEXT_SECONDARY)

        self.detail_text.configure(state=tk.DISABLED)