"""
竹雨ROCOM小助手 - 技能图鉴面板
搜索技能、查看详情、技能石来源追踪
"""

import tkinter as tk
from tkinter import ttk
from core.type_data import get_all_skills, get_all_pets, get_skill_image_path
from ui.theme import (
    TYPE_COLORS, PRIMARY, PRIMARY_HOVER, WARNING,
    BG_CARD, TEXT_SECONDARY, TEXT_HINT,
    FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_CAPTION,
    PAD_X,
)


class SkillPediaPanel(ttk.Frame):
    """技能图鉴面板"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.all_skills = get_all_skills()
        self.all_pets = get_all_pets()
        # 构建技能石来源映射
        self._stone_sources = {}
        for pet in self.all_pets:
            for stone in pet.get("quest_stones", []):
                if isinstance(stone, dict):
                    sname = stone.get("name", "")
                else:
                    sname = str(stone) if stone else ""
                if sname:
                    if sname not in self._stone_sources:
                        self._stone_sources[sname] = []
                    self._stone_sources[sname].append(pet.get("name", "?"))

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
        # ── 顶部：搜索栏 ──
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=PAD_X, pady=6)

        ttk.Label(top_frame, text="搜索：", font=FONT_BODY).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(
            top_frame, textvariable=self.search_var,
            font=FONT_BODY, width=18,
        )
        search_entry.pack(side=tk.LEFT, padx=4)
        search_entry.bind("<KeyRelease>", self._do_filter)

        ttk.Label(top_frame, text="属性：", font=FONT_BODY).pack(side=tk.LEFT, padx=(8, 0))
        self.attr_var = tk.StringVar(value="全部")
        attributes = ["全部", "普通", "草", "火", "水", "光", "地", "冰", "龙",
                       "电", "毒", "虫", "武", "翼", "萌", "幽", "恶", "幻", "机械"]
        attr_cb = ttk.Combobox(
            top_frame, textvariable=self.attr_var, values=attributes,
            font=FONT_BODY, width=6, state="readonly",
        )
        attr_cb.pack(side=tk.LEFT, padx=3)
        attr_cb.bind("<<ComboboxSelected>>", lambda e: self._do_filter())

        ttk.Label(top_frame, text="类型：", font=FONT_BODY).pack(side=tk.LEFT, padx=(8, 0))
        self.cat_var = tk.StringVar(value="全部")
        cat_cb = ttk.Combobox(
            top_frame, textvariable=self.cat_var,
            values=["全部", "状态", "物攻", "魔攻", "防御"],
            font=FONT_BODY, width=6, state="readonly",
        )
        cat_cb.pack(side=tk.LEFT, padx=3)
        cat_cb.bind("<<ComboboxSelected>>", lambda e: self._do_filter())

        tk.Button(
            top_frame, text="网络搜索",
            font=FONT_SMALL,
            bg=WARNING, fg="white",
            relief=tk.FLAT, cursor="hand2",
            activebackground="#D68910",
            borderwidth=0, padx=10, pady=3,
            command=self._network_search,
        ).pack(side=tk.LEFT, padx=(8, 0))

        # ── 中间：左右分栏 ──
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=(0, 6))

        # 左侧：技能列表
        left_frame = ttk.LabelFrame(main_frame, text="技能列表", padding=4)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 4))

        self.skill_listbox = tk.Listbox(
            left_frame,
            font=FONT_SMALL,
            width=38, height=22,
            selectmode=tk.SINGLE,
            bg=BG_CARD,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
        )
        self.skill_listbox.pack(fill=tk.BOTH, expand=True, pady=2)
        self.skill_listbox.bind("<<ListboxSelect>>", self._on_skill_select)

        # 右侧：技能详情
        self.detail_frame = ttk.LabelFrame(main_frame, text="技能详情", padding=8)
        self.detail_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.skill_name_label = ttk.Label(
            self.detail_frame,
            text="请选择一个技能",
            font=FONT_HEADING,
        )
        self.skill_name_label.pack(anchor=tk.W, pady=(0, 6))

        # 技能图片
        self.skill_image_label = tk.Label(
            self.detail_frame,
            bg=BG_CARD,
        )
        self.skill_image_label.pack(anchor=tk.W, pady=(0, 6))
        self._skill_photo_ref = None

        # 标签行
        self.tag_frame = ttk.Frame(self.detail_frame)
        self.tag_frame.pack(fill=tk.X, pady=(0, 6))

        # 效果
        ttk.Label(self.detail_frame, text="效果：", font=FONT_BODY).pack(anchor=tk.W)
        self.effect_label = ttk.Label(
            self.detail_frame,
            text="",
            font=FONT_BODY,
            wraplength=350,
        )
        self.effect_label.pack(anchor=tk.W, pady=(2, 6))

        # 描述
        ttk.Label(self.detail_frame, text="描述：", font=FONT_BODY).pack(anchor=tk.W)
        self.desc_label = ttk.Label(
            self.detail_frame,
            text="",
            font=FONT_BODY,
            wraplength=350,
        )
        self.desc_label.pack(anchor=tk.W, pady=(2, 6))

        # 技能石来源
        self.stone_frame = ttk.LabelFrame(self.detail_frame, text="技能石来源", padding=5)

        self.stone_text = tk.Text(
            self.stone_frame,
            font=FONT_BODY,
            height=5,
            state=tk.DISABLED,
            bg=BG_CARD,
            relief=tk.FLAT,
            borderwidth=0,
            padx=6, pady=4,
        )
        self.stone_text.pack(fill=tk.BOTH, expand=True)

        # 初始加载
        self._do_filter()

    def _do_filter(self, event=None):
        kw = self.search_var.get().strip().lower()
        attr_filter = self.attr_var.get()
        cat_filter = self.cat_var.get()

        self.skill_listbox.delete(0, tk.END)
        filtered = []

        cat_map = {"物理": "物攻", "魔法": "魔攻", "变化": "状态"}

        for sk in self.all_skills:
            name = sk.get("name", "")
            attr = sk.get("attribute", "")
            cat = sk.get("category", "")

            # 关键词过滤
            if kw and kw not in name.lower():
                continue
            # 属性过滤
            if attr_filter != "全部" and attr != attr_filter:
                continue
            # 类型过滤（映射后对比）
            mapped_cat = cat_map.get(cat, cat)
            if cat_filter != "全部" and mapped_cat != cat_filter:
                continue

            filtered.append(sk)

        for sk in filtered:
            name = sk.get("name", "?")
            attr = sk.get("attribute", "?")
            cat = sk.get("category", "?")
            mapped_cat = cat_map.get(cat, cat)
            power = sk.get("power", "?")
            cost = sk.get("cost", "?")
            display = f"{name:12s} | {attr:4s} | {mapped_cat:4s} | 威力{str(power):>4s} | 能耗{str(cost):>4s}"
            self.skill_listbox.insert(tk.END, display)

        self.skill_listbox.insert(tk.END, f"共 {len(filtered)} 个技能")

    def _on_skill_select(self, event):
        sel = self.skill_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        display = self.skill_listbox.get(idx)
        if display.startswith("共 "):
            return

        # 从显示中提取技能名
        skill_name = display.split(" | ")[0].strip()

        skill = None
        for sk in self.all_skills:
            if sk.get("name") == skill_name:
                skill = sk
                break

        if not skill:
            return

        self._show_detail(skill)

    def _show_detail(self, skill):
        name = skill.get("name", "?")
        attr = skill.get("attribute", "?")
        cat = skill.get("category", "?")
        power = skill.get("power", "?")
        cost = skill.get("cost", "?")
        effect = skill.get("effect", "")
        desc = skill.get("description", "")

        # 技能名
        self.skill_name_label.configure(text=name)

        # 技能图片
        img_path = get_skill_image_path(name)
        if img_path:
            try:
                img = tk.PhotoImage(file=img_path)
                self.skill_image_label.configure(image=img, bg=BG_CARD)
                self._skill_photo_ref = img  # 保持引用
            except Exception:
                self.skill_image_label.configure(image="", bg=BG_CARD)
                self._skill_photo_ref = None
        else:
            self.skill_image_label.configure(image="", bg=BG_CARD)
            self._skill_photo_ref = None

        # 清空标签行
        for w in self.tag_frame.winfo_children():
            w.destroy()

        # 属性颜色（使用主题色板）
        type_colors = TYPE_COLORS

        cat_map = {"物理": "物攻", "魔法": "魔攻", "变化": "状态"}
        tags_data = [
            (f" {attr} ", type_colors.get(attr, "#999999"), "white"),
            (f" {cat_map.get(cat, cat)} ", "#3498DB", "white"),
            (f" 威力 {power} ", "#F39C12", "white"),
            (f" 能耗 {cost} ", "#E74C3C", "white"),
        ]

        for text, bg, fg in tags_data:
            lbl = tk.Label(
                self.tag_frame,
                text=text,
                font=("Microsoft YaHei", 10, "bold"),
                bg=bg, fg=fg,
                relief=tk.FLAT,
            )
            lbl.pack(side=tk.LEFT, padx=2)

        # 效果
        self.effect_label.configure(text=effect if effect else "(无)")

        # 描述
        self.desc_label.configure(text=desc if desc else "(无)")

        # 技能石来源
        sources = self._stone_sources.get(name, [])
        self.stone_text.configure(state=tk.NORMAL)
        self.stone_text.delete(1.0, tk.END)
        if sources:
            self.stone_text.insert(tk.END, "技能石技能\n")
            self.stone_text.insert(tk.END, f"获取来源精灵：{'、'.join(sources)}")
            self.stone_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        else:
            self.stone_frame.pack_forget()
        self.stone_text.configure(state=tk.DISABLED)

    def _network_search(self):
        """从 Wiki 网络搜索技能"""
        kw = self.search_var.get().strip()
        if not kw:
            return
        try:
            from core.wiki_scraper import _fetch_category_members, _fetch_wikitext, _parse_skill_wikitext
            import tkinter.messagebox as _mb
            import time

            # 获取技能页列表
            skill_pages = _fetch_category_members("Category:技能", None, None)
            if not skill_pages:
                _mb.showwarning("未找到", "无法获取技能页列表")
                return

            # 按名称匹配
            found_skill = None
            for title, pageid in skill_pages:
                if kw in title:
                    wikitext = _fetch_wikitext(title)
                    skill_data = _parse_skill_wikitext(wikitext)
                    if skill_data:
                        sname = skill_data.get("技能名", "")
                        if kw.lower() in sname.lower() or kw.lower() in title.lower():
                            found_skill = skill_data
                            break
                    time.sleep(0.3)

            if found_skill:
                # 按 name 去重，避免 set() 无法 hash dict
                seen_names = set()
                deduped = []
                for sk in self.all_skills + [found_skill]:
                    n = sk.get("技能名") or sk.get("name", "")
                    if n and n not in seen_names:
                        seen_names.add(n)
                        deduped.append(sk)
                self.all_skills = deduped
                _FIELD_MAP = {
                    "技能名": "name", "属性": "attribute", "类型": "category",
                    "耗能": "cost", "威力": "power", "效果": "effect", "描述": "description",
                }
                normalized = {}
                for cn_key, en_key in _FIELD_MAP.items():
                    if cn_key in found_skill:
                        normalized[en_key] = found_skill[cn_key]
                for k, v in found_skill.items():
                    if k not in _FIELD_MAP:
                        normalized[k] = v
                replaced = False
                for i, sk in enumerate(self.all_skills):
                    if isinstance(sk, dict) and sk.get("name") == normalized.get("name"):
                        self.all_skills[i] = normalized
                        replaced = True
                        break
                if not replaced:
                    self.all_skills.append(normalized)
                self._do_filter()
                _mb.showinfo("成功", f"已从 Wiki 获取技能「{kw}」！")
            else:
                _mb.showwarning("未找到", f"Wiki 中未找到技能「{kw}」")
        except Exception as e:
            import tkinter.messagebox as _mb
            _mb.showerror("错误", f"网络搜索失败: {e}")