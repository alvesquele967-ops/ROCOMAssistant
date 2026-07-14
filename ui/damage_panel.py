"""
竹雨ROCOM小助手 - 伤害倍率计算UI
"""

import tkinter as tk
from tkinter import ttk
from core.type_data import ALL_TYPES
from core.damage_calc import DamageCalculator


class DamagePanel(ttk.Frame):
    """伤害计算面板"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.calculator = DamageCalculator()
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
        # 标题
        ttk.Label(
            self, text="伤害倍率计算",
            font=("Microsoft YaHei", 14, "bold")
        ).pack(padx=10, pady=5, anchor=tk.W)

        # 公式说明
        ttk.Label(
            self,
            text="World版公式：(攻击-防御) × 威力/50 × 克制系数 × 随机(0.85~1.0)",
            font=("Microsoft YaHei", 9),
            foreground="gray"
        ).pack(padx=10, pady=(0, 10), anchor=tk.W)

        # 输入区域
        input_frame = ttk.LabelFrame(self, text="参数输入", padding=10)
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        # 使用grid布局
        self.entries = {}

        fields = [
            ("攻击力：", "attack", "100", 0),
            ("防御力：", "defense", "80", 1),
            ("技能威力：", "power", "50", 2),
        ]

        for label, key, default, row in fields:
            ttk.Label(input_frame, text=label, font=("Microsoft YaHei", 10)).grid(
                row=row, column=0, sticky=tk.E, padx=5, pady=3
            )
            entry = ttk.Entry(input_frame, width=15, font=("Microsoft YaHei", 10))
            entry.insert(0, default)
            entry.grid(row=row, column=1, sticky=tk.W, padx=5, pady=3)
            self.entries[key] = entry

        # 攻击属性选择
        ttk.Label(input_frame, text="攻击属性：", font=("Microsoft YaHei", 10)).grid(
            row=0, column=2, sticky=tk.E, padx=5, pady=3
        )
        self.atk_type_combo = ttk.Combobox(
            input_frame, values=ALL_TYPES,
            font=("Microsoft YaHei", 10), state="readonly", width=8
        )
        self.atk_type_combo.set("火")
        self.atk_type_combo.grid(row=0, column=3, sticky=tk.W, padx=5, pady=3)

        # 防御属性选择（双属性）
        ttk.Label(input_frame, text="防御属性1：", font=("Microsoft YaHei", 10)).grid(
            row=1, column=2, sticky=tk.E, padx=5, pady=3
        )
        self.def_type1_combo = ttk.Combobox(
            input_frame, values=ALL_TYPES,
            font=("Microsoft YaHei", 10), state="readonly", width=8
        )
        self.def_type1_combo.set("草")
        self.def_type1_combo.grid(row=1, column=3, sticky=tk.W, padx=5, pady=3)

        ttk.Label(input_frame, text="防御属性2：", font=("Microsoft YaHei", 10)).grid(
            row=2, column=2, sticky=tk.E, padx=5, pady=3
        )
        self.def_type2_combo = ttk.Combobox(
            input_frame, values=["（无）"] + ALL_TYPES,
            font=("Microsoft YaHei", 10), state="readonly", width=8
        )
        self.def_type2_combo.set("（无）")
        self.def_type2_combo.grid(row=2, column=3, sticky=tk.W, padx=5, pady=3)

        # 计算按钮
        btn_frame = ttk.Frame(input_frame)
        btn_frame.grid(row=3, column=0, columnspan=4, pady=10)

        tk.Button(
            btn_frame, text="计算伤害",
            font=("Microsoft YaHei", 11, "bold"),
            bg="#27AE60", fg="white",
            width=12, height=1,
            relief=tk.FLAT, cursor="hand2",
            command=self._calculate_damage,
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame, text="模拟100次",
            font=("Microsoft YaHei", 11),
            bg="#4A90D9", fg="white",
            width=12, height=1,
            relief=tk.FLAT, cursor="hand2",
            command=self._simulate_battle,
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            btn_frame, text="清空结果",
            font=("Microsoft YaHei", 11),
            bg="#95A5A6", fg="white",
            width=12, height=1,
            relief=tk.FLAT, cursor="hand2",
            command=self._clear_result,
        ).pack(side=tk.LEFT, padx=5)

        # 结果展示
        result_frame = ttk.LabelFrame(self, text="计算结果", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.result_text = tk.Text(
            result_frame,
            font=("Microsoft YaHei", 11),
            wrap=tk.WORD,
            height=10,
            state=tk.DISABLED,
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)

        # 配置文本标签
        self.result_text.tag_configure("title", font=("Microsoft YaHei", 13, "bold"))
        self.result_text.tag_configure("good", foreground="#27AE60", font=("Microsoft YaHei", 12, "bold"))
        self.result_text.tag_configure("bad", foreground="#E74C3C", font=("Microsoft YaHei", 12, "bold"))
        self.result_text.tag_configure("normal", foreground="#3498DB")
        self.result_text.tag_configure("label", font=("Microsoft YaHei", 10, "bold"))
        self.result_text.tag_configure("divider", foreground="gray")

    def _get_inputs(self):
        """获取所有输入参数"""
        try:
            attack = float(self.entries["attack"].get())
            defense = float(self.entries["defense"].get())
            power = float(self.entries["power"].get())
        except ValueError:
            return None, None, None, None, None

        atk_type = self.atk_type_combo.get()
        def_type1 = self.def_type1_combo.get()
        def_type2 = self.def_type2_combo.get()

        defend_types = [def_type1]
        if def_type2 != "（无）":
            defend_types.append(def_type2)

        return attack, defense, power, atk_type, defend_types

    def _calculate_damage(self):
        """计算单次伤害"""
        attack, defense, power, atk_type, defend_types = self._get_inputs()
        if attack is None:
            return

        result = self.calculator.get_damage_breakdown(
            attack, defense, power, atk_type, defend_types
        )

        self._clear_result()
        self.result_text.configure(state=tk.NORMAL)

        # 标题
        self.result_text.insert(tk.END, f"{atk_type}系 → {','.join(defend_types)}系\n\n", "title")

        # 伤害结果
        eff = result["克制系数"]
        if eff >= 2:
            tag = "good"
        elif eff <= 0.5:
            tag = "bad"
        else:
            tag = "normal"

        self.result_text.insert(tk.END, f"  最终伤害：{result['最终伤害']}\n", tag)
        self.result_text.insert(tk.END, f"  克制系数：×{eff}\n")
        self.result_text.insert(tk.END, f"  克制关系：{result['克制关系']}\n")
        self.result_text.insert(tk.END, f"  基础伤害：{result['基础伤害']}\n")
        self.result_text.insert(tk.END, f"  随机系数：{result['本次随机']}（范围{result['随机范围']}）\n")
        self.result_text.insert(tk.END, "─" * 50 + "\n", "divider")
        self.result_text.insert(
            tk.END,
            f"  攻({result['攻击力']}) - 防({result['防御力']}) × "
            f"威力({result['技能威力']})/50 × 克制({eff}) × 随机({result['本次随机']})\n"
        )

        self.result_text.configure(state=tk.DISABLED)

    def _simulate_battle(self):
        """模拟100次战斗"""
        attack, defense, power, atk_type, defend_types = self._get_inputs()
        if attack is None:
            return

        attacker = {"攻击力": attack, "属性": atk_type}
        defender = {"防御力": defense, "属性": defend_types}
        result = self.calculator.simulate_battle(attacker, defender, power, 100)

        self._clear_result()
        self.result_text.configure(state=tk.NORMAL)

        self.result_text.insert(tk.END, f"【模拟100次战斗统计】\n\n", "title")
        self.result_text.insert(
            tk.END,
            f"  {atk_type}系(攻{attack}) → {','.join(defend_types)}系(防{defense})  威力{power}\n\n"
        )
        self.result_text.insert(tk.END, f"  平均伤害：{result['average_damage']}\n")
        self.result_text.insert(tk.END, f"  中位伤害：{result['median_damage']}\n")
        self.result_text.insert(tk.END, f"  最低伤害：{result['min_damage']}\n")
        self.result_text.insert(tk.END, f"  最高伤害：{result['max_damage']}\n")
        self.result_text.insert(
            tk.END,
            f"  25%~75%区间：{result['damage_range_25_75'][0]} ~ "
            f"{result['damage_range_25_75'][1]}\n"
        )

        self.result_text.configure(state=tk.DISABLED)

    def _clear_result(self):
        """清空结果"""
        self.result_text.configure(state=tk.NORMAL)
        self.result_text.delete(1.0, tk.END)
        self.result_text.configure(state=tk.DISABLED)