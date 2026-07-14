"""
竹雨ROCOM小助手 - 伤害计算器面板（ROCOM版 完整重写）
公式来源：抖音博主 欣梦（简化版）

面板公式（欣梦 ROCOM）：
  生命：[(种族值+0.5×个体值)×(0.5+0.02×等级)+等级+10]×(1+性格)+成长值
  其他：[(种族值+0.5×个体值)×(0.5+0.01×等级)+10]×(1+性格)+成长值

  个体值 = 初始个体值(7~10) × ceil(等级/10)，仅3个指定属性生效
  生命成长值 = 成长星级 × 20
  其他成长值 = 成长星级 × 10
  正面性格影响 = 10% + 成长星级 × 2%
  负面性格影响固定为 -10%
  等级上限：60（ROCOM）

伤害公式（ROCOM）：
  (攻击 ÷ 防御) × 0.9 × 威力 × 克制系数 × 随机(0.85~1.0)
"""

import tkinter as tk
from tkinter import ttk, messagebox
import random
import math

from core.type_data import (
    ALL_TYPES, NATURES, NATURE_NAMES,
    get_pet, get_all_pets, add_temp_pet,
    get_effectiveness,
)
from ui.theme import (
    PRIMARY, SUCCESS, DANGER,
    SUCCESS_DARK, DANGER_DARK,
    BG_CARD, TEXT_PRIMARY, TEXT_SECONDARY,
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_CAPTION,
    PAD_X,
)

# ── 常量 ──────────────────────────────────────────────────────────
_MAX_LEVEL = 60

# 属性映射
_STAT_DISPLAY = ["生命", "物攻", "魔攻", "物防", "魔防", "速度"]
_STAT_KEYS    = ["hp",   "atk",  "spa",  "def",  "spd",  "spe"]
_STAT_CN_TO_KEY = {"生命": "hp", "物攻": "atk", "魔攻": "spa",
                   "物防": "def", "魔防": "spd", "速度": "spe"}
_STAT_KEY_TO_CN = {"hp": "生命", "atk": "物攻", "spa": "魔攻",
                   "def": "物防", "spd": "魔防", "spe": "速度"}

# 默认种族值（迪莫）
_DEFAULT_SPECIES = {"hp": 120, "atk": 80, "spa": 80, "def": 105, "spd": 105, "spe": 92}


# ── 性格标签 ──────────────────────────────────────────────────────

def _build_nature_labels():
    """从 type_data.NATURES 构建 30 种性格的下拉标签"""
    labels = []
    mapping = {}  # label → 纯名称
    for name in NATURE_NAMES:
        mods = NATURES.get(name, {})
        if not mods:
            labels.append(name)
            mapping[name] = name
            continue
        parts = []
        for cn_stat, mult in mods.items():
            if mult > 1.0:
                parts.append(f"{cn_stat}↑")
            else:
                parts.append(f"{cn_stat}↓")
        label = f"{name}（{' '.join(parts)}）"
        labels.append(label)
        mapping[label] = name
    return labels, mapping


_NATURE_LABELS, _NATURE_NAME_MAP = _build_nature_labels()
_DEFAULT_NATURE_LABEL = _NATURE_LABELS[0] if _NATURE_LABELS else ""


# ── 精灵显示数据 ──────────────────────────────────────────────────

def _load_pet_displays():
    """从 type_data 加载所有精灵的显示名列表及映射"""
    displays = []
    mapping = {}  # display_str → pet_dict
    for p in get_all_pets():
        name = p.get("name", "")
        if not name:
            continue
        form = p.get("form")
        region = p.get("region_form")
        if region:
            d = f"{name} [{form}] [{region}]"
        elif form:
            d = f"{name} [{form}]"
        else:
            d = name
        displays.append(d)
        mapping[d] = p
    displays.sort()
    return displays, mapping


_ALL_PET_DISPLAYS, _PET_DISPLAY_MAP = _load_pet_displays()


def _reload_pet_displays():
    """重新加载精灵列表（网络搜索后调用）"""
    global _ALL_PET_DISPLAYS, _PET_DISPLAY_MAP
    _ALL_PET_DISPLAYS, _PET_DISPLAY_MAP = _load_pet_displays()


# ══════════════════════════════════════════════════════════════════════
# DamageCalcPanel
# ══════════════════════════════════════════════════════════════════════

class DamageCalcPanel(ttk.Frame):
    """伤害计算器面板 — ROCOM 公式完整版"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._cached_stats = {}
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


    # ── UI 构建 ────────────────────────────────────────────────────

    def _build_ui(self):
        # 标题行
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, padx=PAD_X, pady=(6, 2))
        ttk.Label(title_frame, text="伤害计算器", font=FONT_TITLE).pack(side=tk.LEFT)
        ttk.Label(
            title_frame,
            text="面板：欣梦公式  |  伤害：ROCOM  |  满级 60",
            font=FONT_SMALL, foreground=TEXT_SECONDARY,
        ).pack(side=tk.RIGHT)

        # ═══ 顶部两栏 ═══
        top = ttk.Frame(self)
        top.pack(fill=tk.X, padx=PAD_X, pady=4)

        # 左栏：精灵 / 等级 / 星级 / 个体 / 性格
        left = ttk.LabelFrame(top, text="精灵参数", padding=10)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        self._build_left(left)

        # 右栏：攻击属性 / 技能类型 / 技能威力 / 防御属性
        right = ttk.LabelFrame(top, text="伤害参数", padding=10)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        self._build_right(right)

        # ═══ 底部结果区 ═══
        self.result_text = tk.Text(
            self, font=FONT_BODY, wrap=tk.WORD,
            state=tk.DISABLED, bg=BG_CARD, relief=tk.FLAT,
            borderwidth=1, padx=10, pady=8,
        )
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=(4, 6))

    # ── 左栏 ──────────────────────────────────────────────────────

    def _build_left(self, parent):
        # ── 精灵搜索 Combobox ──
        pet_row = ttk.Frame(parent)
        pet_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(pet_row, text="精灵：", font=FONT_BODY, width=7).pack(side=tk.LEFT)

        self.pet_var = tk.StringVar()
        self.pet_combo = ttk.Combobox(
            pet_row, textvariable=self.pet_var,
            values=_ALL_PET_DISPLAYS, font=FONT_BODY, width=22,
        )
        self.pet_combo.pack(side=tk.LEFT, padx=4)
        self.pet_combo.bind("<KeyRelease>", self._on_pet_filter)
        self.pet_combo.bind("<<ComboboxSelected>>", self._on_pet_select)
        self.pet_combo.bind("<Return>", self._on_pet_select)

        # 网络搜索 + 刷新按钮
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=(2, 6))
        tk.Button(btn_frame, text="网络搜索", bg="#E67E22", fg="white",
                  font=("Microsoft YaHei", 9), relief=tk.FLAT, cursor="hand2",
                  command=self._network_search_pet).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(btn_frame, text="刷新列表", bg="#3498DB", fg="white",
                  font=("Microsoft YaHei", 9), relief=tk.FLAT, cursor="hand2",
                  command=self._refresh_pet_list).pack(side=tk.LEFT)

        # 种族值 3×2 网格
        ttk.Label(parent, text="种族值", font=FONT_HEADING).pack(anchor=tk.W, pady=(0, 2))
        self.species_entries = {}
        grid = ttk.Frame(parent)
        grid.pack(fill=tk.X)
        for i, (dname, key) in enumerate(zip(_STAT_DISPLAY, _STAT_KEYS)):
            sub = ttk.Frame(grid)
            sub.grid(row=i // 3, column=i % 3, padx=2, pady=2, sticky="ew")
            ttk.Label(sub, text=dname, font=FONT_CAPTION, width=4,
                      anchor=tk.CENTER).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(_DEFAULT_SPECIES.get(key, 0)))
            ttk.Entry(sub, textvariable=var, width=7, font=FONT_BODY,
                      justify=tk.CENTER).pack(side=tk.LEFT, padx=2)
            self.species_entries[key] = var
        for ci in range(3):
            grid.columnconfigure(ci, weight=1)

        # 属性提示
        self.pet_attr_label = ttk.Label(
            parent, text="属性：光", font=FONT_CAPTION, foreground=TEXT_SECONDARY
        )
        self.pet_attr_label.pack(anchor=tk.W, pady=(3, 6))

        # ── 参数行 1：等级 + 星级 ──
        r1 = ttk.Frame(parent)
        r1.pack(fill=tk.X, pady=2)
        ttk.Label(r1, text="等级：", font=FONT_BODY, width=7).pack(side=tk.LEFT)
        self.level_var = tk.StringVar(value="50")
        ttk.Spinbox(r1, textvariable=self.level_var, from_=1, to=_MAX_LEVEL,
                    width=5, font=FONT_BODY).pack(side=tk.LEFT)
        ttk.Label(r1, text="（1~60）", font=FONT_CAPTION,
                  foreground=TEXT_SECONDARY).pack(side=tk.LEFT, padx=(2, 16))

        ttk.Label(r1, text="星级：", font=FONT_BODY, width=6).pack(side=tk.LEFT)
        self.star_var = tk.StringVar(value="3")
        ttk.Spinbox(r1, textvariable=self.star_var, from_=1, to=5,
                    width=4, font=FONT_BODY).pack(side=tk.LEFT)
        ttk.Label(r1, text="（1~5）", font=FONT_CAPTION,
                  foreground=TEXT_SECONDARY).pack(side=tk.LEFT)

        # ── 初始个体值（三属性） ──
        ttk.Label(parent, text="初始个体值", font=FONT_HEADING).pack(anchor=tk.W, pady=(6, 2))
        self.iv_stats = []     # 每个元素: spinbox_var
        self.iv_combos = []
        _DEFAULT_IV_SELECTIONS = ["生命", "物攻", "物防"]
        for idx, default_stat in enumerate(_DEFAULT_IV_SELECTIONS):
            iv_row = ttk.Frame(parent)
            iv_row.pack(fill=tk.X, pady=1)
            ttk.Label(iv_row, text=f"属性{idx+1}：", font=FONT_BODY, width=7).pack(side=tk.LEFT)
            combo = ttk.Combobox(
                iv_row, values=_STAT_DISPLAY, state="readonly",
                font=FONT_BODY, width=6,
            )
            combo.set(default_stat)
            combo.pack(side=tk.LEFT, padx=4)
            spin_var = tk.StringVar(value="10")
            ttk.Spinbox(iv_row, textvariable=spin_var, from_=7, to=10,
                        width=4, font=FONT_BODY).pack(side=tk.LEFT, padx=2)
            ttk.Label(iv_row, text="（7~10）", font=FONT_CAPTION,
                      foreground=TEXT_SECONDARY).pack(side=tk.LEFT)
            self.iv_stats.append(spin_var)
            self.iv_combos.append(combo)

        # ── 性格 ──
        nat_row = ttk.Frame(parent)
        nat_row.pack(fill=tk.X, pady=2)
        ttk.Label(nat_row, text="性格：", font=FONT_BODY, width=7).pack(side=tk.LEFT)
        self.nature_var = tk.StringVar(value=_DEFAULT_NATURE_LABEL)
        self.nature_combo = ttk.Combobox(
            nat_row, textvariable=self.nature_var,
            values=_NATURE_LABELS, state="readonly",
            font=FONT_BODY, width=20,
        )
        self.nature_combo.pack(side=tk.LEFT)

        # 计算面板按钮
        ttk.Button(
            parent, text="计算面板", command=self._calc_stats, width=12
        ).pack(pady=(8, 0))

    # ── 右栏 ──────────────────────────────────────────────────────

    def _build_right(self, parent):
        # ── 攻击方 ──
        atk_lf = ttk.LabelFrame(parent, text="攻击方", padding=8)
        atk_lf.pack(fill=tk.X, pady=(0, 8))

        ag = ttk.Frame(atk_lf)
        ag.pack(fill=tk.X)

        ttk.Label(ag, text="攻击属性：", font=FONT_BODY).grid(
            row=0, column=0, sticky=tk.W, pady=3)
        self.atk_type_var = tk.StringVar(value="普通")
        ttk.Combobox(
            ag, textvariable=self.atk_type_var,
            values=ALL_TYPES, state="readonly", font=FONT_BODY, width=8,
        ).grid(row=0, column=1, sticky=tk.W, pady=3, padx=(0, 12))

        ttk.Label(ag, text="技能类型：", font=FONT_BODY).grid(
            row=0, column=2, sticky=tk.W, pady=3)
        self.skill_cat_var = tk.StringVar(value="物攻")
        ttk.Combobox(
            ag, textvariable=self.skill_cat_var,
            values=["物攻", "魔攻"], state="readonly", font=FONT_BODY, width=6,
        ).grid(row=0, column=3, sticky=tk.W, pady=3)

        ttk.Label(ag, text="技能威力：", font=FONT_BODY).grid(
            row=1, column=0, sticky=tk.W, pady=3)
        self.power_var = tk.StringVar(value="80")
        ttk.Entry(ag, textvariable=self.power_var, width=7,
                  font=FONT_BODY, justify=tk.CENTER).grid(
            row=1, column=1, sticky=tk.W, pady=3)

        ttk.Label(ag, text="攻击力：", font=FONT_BODY).grid(
            row=1, column=2, sticky=tk.W, pady=3)
        self.atk_val_var = tk.StringVar(value="150")
        ttk.Entry(ag, textvariable=self.atk_val_var, width=7,
                  font=FONT_BODY, justify=tk.CENTER).grid(
            row=1, column=3, sticky=tk.W, pady=3)

        # ── 防御方 ──
        def_lf = ttk.LabelFrame(parent, text="防御方", padding=8)
        def_lf.pack(fill=tk.X)

        dg = ttk.Frame(def_lf)
        dg.pack(fill=tk.X)

        ttk.Label(dg, text="主属性：", font=FONT_BODY).grid(
            row=0, column=0, sticky=tk.W, pady=3)
        self.def_t1_var = tk.StringVar(value="普通")
        ttk.Combobox(
            dg, textvariable=self.def_t1_var,
            values=ALL_TYPES, state="readonly", font=FONT_BODY, width=8,
        ).grid(row=0, column=1, sticky=tk.W, pady=3, padx=(0, 12))

        ttk.Label(dg, text="副属性：", font=FONT_BODY).grid(
            row=0, column=2, sticky=tk.W, pady=3)
        self.def_t2_var = tk.StringVar(value="（无）")
        ttk.Combobox(
            dg, textvariable=self.def_t2_var,
            values=["（无）"] + ALL_TYPES, state="readonly", font=FONT_BODY, width=8,
        ).grid(row=0, column=3, sticky=tk.W, pady=3)

        ttk.Label(dg, text="防御力：", font=FONT_BODY).grid(
            row=1, column=0, sticky=tk.W, pady=3)
        self.def_val_var = tk.StringVar(value="120")
        ttk.Entry(dg, textvariable=self.def_val_var, width=7,
                  font=FONT_BODY, justify=tk.CENTER).grid(
            row=1, column=1, sticky=tk.W, pady=3)

        note = ttk.Label(dg, text="（物攻→物防 / 魔攻→魔防）",
                         font=FONT_CAPTION, foreground=TEXT_SECONDARY)
        note.grid(row=1, column=2, columnspan=2, sticky=tk.W, pady=3, padx=(12, 0))

        # 计算伤害按钮
        ttk.Button(
            parent, text="计算伤害", command=self._calc_damage, width=12
        ).pack(pady=(8, 0))

    # ── 精灵搜索 ──────────────────────────────────────────────────

    def _on_pet_filter(self, event=None):
        """键入关键词时实时过滤下拉列表"""
        if event and event.keysym in ("Up", "Down", "Left", "Right",
                                       "Return", "Tab", "Escape"):
            return
        kw = self.pet_var.get().strip().lower()
        if not kw:
            self.pet_combo["values"] = _ALL_PET_DISPLAYS
        else:
            filtered = [d for d in _ALL_PET_DISPLAYS if kw in d.lower()]
            self.pet_combo["values"] = filtered[:50]

    def _on_pet_select(self, event=None):
        """选中精灵后自动填入种族值和属性"""
        display = self.pet_var.get().strip()
        if not display:
            return

        pet = _PET_DISPLAY_MAP.get(display)
        if not pet:
            vals = self.pet_combo["values"]
            if vals:
                pet = _PET_DISPLAY_MAP.get(vals[0])
                if pet:
                    self.pet_var.set(vals[0])

        if not pet:
            return

        st = pet.get("stats", {})
        attr = pet.get("attributes", [])

        # Wiki爬取数据使用 sp_atk/sp_def/spd(速度) 键名，需映射到内部键名
        _INTERNAL_TO_WIKI = {"spa": "sp_atk", "spd": "sp_def", "spe": "spd"}

        # 填入种族值
        for key in _STAT_KEYS:
            wiki_key = _INTERNAL_TO_WIKI.get(key, key)
            val = st.get(wiki_key)
            if val is None:
                val = st.get(key)  # 兼容旧 sprites.json 键名
            if val is None:
                val = _DEFAULT_SPECIES.get(key, 0)
            self.species_entries[key].set(str(val))

        # 属性提示
        if attr:
            self.pet_attr_label.configure(text=f"属性：{' / '.join(attr)}")
        else:
            self.pet_attr_label.configure(text="")

        # 尝试填入初始个体值到第一行
        base_iv = pet.get("initial_iv") or pet.get("base_iv") or 10
        if self.iv_stats:
            self.iv_stats[0].set(str(base_iv))

    def _network_search_pet(self):
        """从 Wiki 网络搜索精灵并加入临时缓存"""
        pet_name = self.pet_var.get().strip()
        if not pet_name:
            messagebox.showwarning("提示", "请先在「精灵」输入框中输入精灵名称")
            return
        try:
            from core.wiki_scraper import fetch_single_pet
            pet = fetch_single_pet(pet_name)
            if pet:
                add_temp_pet(pet)
                _reload_pet_displays()
                self._refresh_pet_list()
                # 匹配正确的显示名（含形态后缀），确保 _PET_DISPLAY_MAP 能命中
                real_name = pet.get("name", pet.get("title", pet_name))
                display = self._find_display_str(real_name)
                if display:
                    self.pet_var.set(display)
                else:
                    self.pet_var.set(real_name)
                self._on_pet_select()
                messagebox.showinfo("成功", f"已获取「{pet_name}」数据！")
            else:
                messagebox.showwarning("未找到", f"Wiki 中未找到精灵「{pet_name}」")
        except Exception as e:
            messagebox.showerror("错误", f"网络搜索失败: {e}")

    def _find_display_str(self, name):
        """根据精灵名在 _ALL_PET_DISPLAYS 中查找匹配的显示名"""
        for d in _ALL_PET_DISPLAYS:
            if d == name or d.startswith(name + " ["):
                return d
        return None

    def _refresh_pet_list(self):
        """刷新下拉列表"""
        self.pet_combo["values"] = _ALL_PET_DISPLAYS

    # ── 数值 ──────────────────────────────────────────────────────

    def _num(self, var, default=0):
        try:
            return float(var.get())
        except (ValueError, tk.TclError):
            return default

    # ══════════════════════════════════════════════════════════════════
    # 面板计算（欣梦 ROCOM 公式）
    # ══════════════════════════════════════════════════════════════════

    def _calc_stats(self):
        level = self._num(self.level_var, 50)
        star  = self._num(self.star_var, 3)

        if level < 1 or level > _MAX_LEVEL:
            messagebox.showwarning("参数错误", f"等级需在 1~{_MAX_LEVEL} 之间")
            return

        # 个体值：仅选中的3个属性生效，每10级加1次
        iv_mult = math.ceil(level / 10)
        iv_values = {}
        for i in range(3):
            stat_cn = self.iv_combos[i].get()
            key = _STAT_CN_TO_KEY.get(stat_cn)
            init_iv = self._num(self.iv_stats[i], 10)
            if key:
                iv_values[key] = init_iv * iv_mult
        # 未选中的属性个体值为 0
        for key in _STAT_KEYS:
            if key not in iv_values:
                iv_values[key] = 0

        # 性格解析
        nat_label = self.nature_var.get()
        nat_name = _NATURE_NAME_MAP.get(nat_label, "")
        nature_mods = NATURES.get(nat_name, {})

        # 性格效果 → 内部 key
        nature_effects = {}
        for cn_stat, mult in nature_mods.items():
            key = _STAT_CN_TO_KEY.get(cn_stat)
            if not key:
                continue
            if mult > 1.0:
                nature_effects[key] = 0.10 + star * 0.02    # 正面 = 10% + 星级×2%
            else:
                nature_effects[key] = -0.10                  # 负面 = -10%

        # 种族值
        species = {}
        for key in _STAT_KEYS:
            species[key] = self._num(
                self.species_entries.get(key, tk.StringVar()),
                _DEFAULT_SPECIES.get(key, 0)
            )

        # ── 套用公式 ──
        results = {}
        details = {}

        for key in _STAT_KEYS:
            sp = species[key]

            if key == "hp":
                # 生命：[(种族值+0.5×个体值)×(0.5+0.02×等级)+等级+10]×(1+性格)+成长值
                raw = (sp + 0.5 * iv_values[key]) * (0.5 + 0.02 * level) + level + 10
                growth = star * 20
            else:
                # 其他：[(种族值+0.5×个体值)×(0.5+0.01×等级)+10]×(1+性格)+成长值
                raw = (sp + 0.5 * iv_values[key]) * (0.5 + 0.01 * level) + 10
                growth = star * 10

            ne = nature_effects.get(key, 0.0)
            final = raw * (1.0 + ne) + growth
            results[key] = round(final)
            details[key] = {
                "raw": round(raw, 1), "growth": int(growth),
                "nature": ne, "final": round(final),
            }

        self._cached_stats = results

        # 自动填入伤害参数
        cat = self.skill_cat_var.get()
        atk_key = "atk" if cat == "物攻" else "spa"
        def_key = "def" if cat == "物攻" else "spd"
        self.atk_val_var.set(str(results[atk_key]))
        self.def_val_var.set(str(results[def_key]))

        # 展示
        self._display_stats(results, details, species, level, star, iv_values, nat_label)

    def _display_stats(self, results, details, species, level, star, iv_values, nat_label):
        rt = self.result_text
        rt.configure(state=tk.NORMAL)
        rt.delete(1.0, tk.END)

        rt.insert(tk.END, "═══ 面板计算结果 ═══\n", "section")
        rt.insert(tk.END,
                  f"Lv.{int(level)}  ⋆{int(star)}星  "
                  f"性格：{nat_label}\n\n",
                  "info")

        for display, key in zip(_STAT_DISPLAY, _STAT_KEYS):
            sp = species[key]
            final = results[key]
            d = details[key]

            tag = "normal"
            if d["nature"] > 0:
                tag = "up"
            elif d["nature"] < 0:
                tag = "down"

            rt.insert(tk.END, f"  {display}：", "label")
            rt.insert(tk.END, f"种族{int(sp)} → ", "normal")
            rt.insert(tk.END, f"{int(final)}", tag)

            parts = []
            if d["growth"] > 0:
                parts.append(f"成长+{d['growth']}")
            if d["nature"] != 0:
                parts.append(f"性格{d['nature']:+.0%}")
            if iv_values.get(key, 0) > 0:
                parts.append(f"个体+{int(iv_values[key])}")
            suffix = f"  （{'，'.join(parts)}）" if parts else ""
            rt.insert(tk.END, suffix + "\n", "info")

        # 攻击 / 防御对应提示
        cat = self.skill_cat_var.get()
        atk_l = "物攻" if cat == "物攻" else "魔攻"
        def_l = "物防" if cat == "物攻" else "魔防"
        rt.insert(tk.END,
                  f"\n伤害参数已自动填入：{atk_l}={results['atk' if cat == '物攻' else 'spa']}  "
                  f"{def_l}={results['def' if cat == '物攻' else 'spd']}\n",
                  "hint")

        # ── 标签 ──
        rt.tag_configure("section", font=("Microsoft YaHei", 12, "bold"),
                         foreground=PRIMARY)
        rt.tag_configure("info", font=FONT_CAPTION, foreground=TEXT_SECONDARY)
        rt.tag_configure("hint", font=FONT_CAPTION, foreground=TEXT_SECONDARY)
        rt.tag_configure("label", font=FONT_HEADING)
        rt.tag_configure("up", foreground=SUCCESS_DARK, font=FONT_HEADING)
        rt.tag_configure("down", foreground=DANGER, font=FONT_HEADING)
        rt.tag_configure("normal", font=FONT_BODY)
        rt.configure(state=tk.DISABLED)

    # ══════════════════════════════════════════════════════════════════
    # 伤害计算（ROCOM 公式）
    # ══════════════════════════════════════════════════════════════════

    def _calc_damage(self):
        atk_val = self._num(self.atk_val_var, 150)
        def_val = self._num(self.def_val_var, 120)
        power   = self._num(self.power_var, 80)

        if power <= 0:
            self._show_err("技能威力必须大于 0")
            return
        if def_val <= 0:
            self._show_err("防御力必须大于 0")
            return

        cat = self.skill_cat_var.get()
        atk_label = "物攻" if cat == "物攻" else "魔攻"
        def_label = "物防" if cat == "物攻" else "魔防"

        # ── 属性克制 ──
        atk_type = self.atk_type_var.get()
        dt1 = self.def_t1_var.get()
        dt2 = self.def_t2_var.get()
        if dt2 == "（无）":
            dt2 = ""

        defend_types = [dt1]
        if dt2 and dt2 != dt1:
            defend_types.append(dt2)

        effectiveness = 1.0
        immune = False
        for dt in defend_types:
            eff = get_effectiveness(atk_type, [dt])
            if eff == 0.0:
                immune = True
                break
            effectiveness *= eff
        effectiveness = round(effectiveness, 2)

        # ── ROCOM 公式：(攻击÷防御)×0.9×威力×克制系数×随机(0.85~1.0) ──
        base = (atk_val / def_val) * 0.9 * power
        rand_f = round(random.uniform(0.85, 1.0), 2)
        final_dmg = max(1, round(base * effectiveness * rand_f))

        def_label_cn = "·".join(defend_types)

        rt = self.result_text
        rt.configure(state=tk.NORMAL)
        rt.delete(1.0, tk.END)

        rt.insert(tk.END, "═══ 伤害计算结果 ═══\n", "section")
        rt.insert(tk.END,
                  f"{atk_label} {atk_val}  vs  {def_label} {def_val}  "
                  f"威力 {int(power)}\n", "info")
        rt.insert(tk.END,
                  f"攻击：{atk_type}系  →  防御：{def_label_cn}\n\n", "info")

        if immune:
            rt.insert(tk.END, "结果：免疫！伤害 = 0\n", "immune")
        else:
            if effectiveness >= 4:
                eff_str = "四倍克制！"
                eff_tag = "bad"
            elif effectiveness >= 2:
                eff_str = f"克制 ×{effectiveness}"
                eff_tag = "good"
            elif effectiveness <= 0.49:
                eff_str = f"被严重抵抗 ×{effectiveness}"
                eff_tag = "bad"
            elif effectiveness < 1.0:
                eff_str = f"抵抗 ×{effectiveness}"
                eff_tag = "bad"
            else:
                eff_str = "无克制关系"
                eff_tag = "normal"

            rt.insert(tk.END, f"│ 属性关系：{eff_str}\n", eff_tag)
            rt.insert(tk.END,
                      f"│ 攻防比：{atk_val} ÷ {def_val} = {atk_val / def_val:.2f}\n")
            rt.insert(tk.END,
                      f"│ 基础伤害：({atk_val}÷{def_val})×0.9×{int(power)} = {base:.1f}\n")
            rt.insert(tk.END, f"│ 克制系数：×{effectiveness}\n")
            rt.insert(tk.END, f"│ 随机系数：×{rand_f}（0.85~1.0）\n")
            rt.insert(tk.END,
                      f"└─ 最终伤害：{final_dmg}\n", "final")

        # ── 标签 ──
        rt.tag_configure("section", font=("Microsoft YaHei", 12, "bold"),
                         foreground=PRIMARY)
        rt.tag_configure("info", font=FONT_CAPTION, foreground=TEXT_SECONDARY)
        rt.tag_configure("good", foreground=SUCCESS_DARK)
        rt.tag_configure("bad", foreground=DANGER)
        rt.tag_configure("immune", foreground="#8E44AD", font=FONT_HEADING)
        rt.tag_configure("final", font=("Microsoft YaHei", 12, "bold"),
                         foreground=PRIMARY)
        rt.tag_configure("normal", font=FONT_BODY)
        rt.configure(state=tk.DISABLED)

    def _show_err(self, msg):
        rt = self.result_text
        rt.configure(state=tk.NORMAL)
        rt.delete(1.0, tk.END)
        rt.insert(tk.END, f"错误：{msg}", "bad")
        rt.tag_configure("bad", foreground=DANGER, font=FONT_HEADING)
        rt.configure(state=tk.DISABLED)