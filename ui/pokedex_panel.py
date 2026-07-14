"""
竹雨ROCOM小助手 - 精灵图鉴面板
搜索精灵、查看种族值、技能、血脉、特性
"""

import tkinter as tk
from tkinter import ttk
from core.type_data import get_all_pets, search_pets, get_pet, get_pet_image_path, get_skill_image_path, ALL_TYPES
from ui.theme import (
    TYPE_COLORS, RADAR_TYPE_COLORS,
    PRIMARY, PRIMARY_HOVER, SUCCESS, DANGER, WARNING,
    BG_CARD, BG_APP, BG_SIDEBAR, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_HINT,
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_CAPTION,
    PAD_X, GAP,
)


class PokedexPanel(ttk.Frame):
    """精灵图鉴面板"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.all_pets = get_all_pets()
        self.active_type = None  # None = 全部, 否则为属性名如 "火"
        self._skill_photo_refs = []  # 技能图标 PhotoImage 引用防止 GC
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

        self._refresh_pet_list()

    def _build_ui(self):
        # ── 左侧：搜索 + 精灵列表 ──
        left_frame = ttk.Frame(self)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(PAD_X, 4), pady=6)

        ttk.Label(
            left_frame, text="精灵图鉴",
            font=FONT_HEADING,
        ).pack(anchor=tk.W, pady=(0, 4))

        # 搜索框
        search_frame = ttk.Frame(left_frame)
        search_frame.pack(fill=tk.X, pady=(0, 3))

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(
            search_frame, textvariable=self.search_var,
            font=FONT_BODY, width=18,
        )
        search_entry.pack(side=tk.LEFT, padx=(0, 3))
        search_entry.bind("<KeyRelease>", self._on_search)

        tk.Button(
            search_frame, text="搜索",
            font=FONT_SMALL,
            bg=PRIMARY, fg="white",
            relief=tk.FLAT, cursor="hand2",
            activebackground=PRIMARY_HOVER,
            borderwidth=0, padx=10, pady=3,
            command=self._do_search,
        ).pack(side=tk.LEFT, padx=1)

        tk.Button(
            search_frame, text="网络搜索",
            font=FONT_SMALL,
            bg=WARNING, fg="white",
            relief=tk.FLAT, cursor="hand2",
            borderwidth=0, padx=8, pady=3,
            command=self._network_search,
        ).pack(side=tk.LEFT, padx=1)

        # 属性筛选按钮栏
        type_filter_frame = ttk.Frame(left_frame)
        type_filter_frame.pack(fill=tk.X, pady=(0, 3))

        self.type_buttons = {}
        # 「全部」按钮
        all_btn = tk.Button(
            type_filter_frame, text="全部",
            font=FONT_CAPTION,
            bg=PRIMARY, fg="white",
            relief=tk.FLAT, cursor="hand2",
            borderwidth=0, padx=6, pady=1,
            command=lambda: self._set_type_filter(None),
        )
        all_btn.pack(side=tk.LEFT, padx=1)
        self.type_buttons[None] = all_btn

        # 各属性按钮（分行显示，每行最多9个）
        row_frame = None
        for idx, atype in enumerate(ALL_TYPES):
            if idx % 9 == 0:
                row_frame = ttk.Frame(type_filter_frame)
                row_frame.pack(fill=tk.X, pady=1)
            color = TYPE_COLORS.get(atype, "#888888")
            btn = tk.Button(
                row_frame, text=atype,
                font=FONT_CAPTION,
                bg=color, fg="white",
                relief=tk.FLAT, cursor="hand2",
                borderwidth=0, padx=6, pady=1,
                command=lambda t=atype: self._set_type_filter(t),
            )
            btn.pack(side=tk.LEFT, padx=1)
            self.type_buttons[atype] = btn

        # 精灵列表
        list_frame = ttk.LabelFrame(left_frame, text="精灵列表", padding=4)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.pet_listbox = tk.Listbox(
            list_frame,
            font=FONT_BODY,
            width=22, height=28,
            selectmode=tk.SINGLE,
            bg=BG_CARD,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
        )
        self.pet_listbox.pack(fill=tk.BOTH, expand=True, pady=2)
        self.pet_listbox.bind("<<ListboxSelect>>", self._on_pet_select)

        # 计数标签
        self.count_var = tk.StringVar(value="")
        ttk.Label(
            left_frame, textvariable=self.count_var,
            font=FONT_CAPTION, foreground=TEXT_HINT,
        ).pack(anchor=tk.W, pady=(2, 0))

        # ── 右侧：精灵详情 ──
        right_frame = ttk.Frame(self)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=6)

        detail_canvas = tk.Canvas(right_frame, bg=BG_APP, highlightthickness=0)
        detail_scrollbar = ttk.Scrollbar(
            right_frame, orient=tk.VERTICAL, command=detail_canvas.yview
        )
        self.detail_frame = ttk.Frame(detail_canvas)

        self.detail_frame.bind(
            "<Configure>",
            lambda e: detail_canvas.configure(scrollregion=detail_canvas.bbox("all")),
        )
        detail_canvas.create_window((0, 0), window=self.detail_frame, anchor=tk.NW)
        detail_canvas.configure(yscrollcommand=detail_scrollbar.set)

        detail_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮支持
        def _on_mousewheel(event):
            detail_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        detail_canvas.bind("<Enter>", lambda e: detail_canvas.bind_all("<MouseWheel>", _on_mousewheel))
        detail_canvas.bind("<Leave>", lambda e: detail_canvas.unbind_all("<MouseWheel>"))

    # ── 列表刷新 ──
    def _filter_pets(self, pets):
        """按当前选中的属性筛选精灵列表"""
        if self.active_type is None:
            return pets
        return [p for p in pets if self.active_type in p.get("attributes", [])]

    def _refresh_pet_list(self):
        self.pet_listbox.delete(0, tk.END)
        filtered = self._filter_pets(self.all_pets)
        for pet in filtered:
            attrs = pet.get("attributes", [])
            attr_str = "/".join(attrs) if attrs else "?"
            name = pet.get("name", "?")
            form = pet.get("form") or ""
            region = pet.get("region_form") or ""
            if region:
                display = f"{name} - {form} [{region}]  [{attr_str}]"
            elif form:
                display = f"{name} - {form}  [{attr_str}]"
            else:
                display = f"{name}  [{attr_str}]"
            self.pet_listbox.insert(tk.END, display)
        self.count_var.set(f"共 {len(filtered)} 只精灵{'' if self.active_type is None else '（' + self.active_type + '）'}")

    def _on_search(self, event):
        self._do_search()

    def _set_type_filter(self, atype):
        """设置属性筛选并刷新列表"""
        self.active_type = atype
        # 更新按钮高亮状态
        for t, btn in self.type_buttons.items():
            if t == atype:
                btn.config(relief=tk.SUNKEN)
            else:
                btn.config(relief=tk.FLAT)
        self._do_search()

    def _do_search(self):
        kw = self.search_var.get().strip()
        if kw:
            results = search_pets(kw, limit=200)
        else:
            results = self.all_pets

        results = self._filter_pets(results)

        self.pet_listbox.delete(0, tk.END)
        for pet in results:
            attrs = pet.get("attributes", [])
            attr_str = "/".join(attrs) if attrs else "?"
            name = pet.get("name", "?")
            form = pet.get("form") or ""
            region = pet.get("region_form") or ""
            if region:
                display = f"{name} - {form} [{region}]  [{attr_str}]"
            elif form:
                display = f"{name} - {form}  [{attr_str}]"
            else:
                display = f"{name}  [{attr_str}]"
            self.pet_listbox.insert(tk.END, display)
        self.count_var.set(f"搜索结果：{len(results)} 只")

    def _network_search(self):
        """从 Wiki 网络搜索精灵并加入临时缓存"""
        kw = self.search_var.get().strip()
        if not kw:
            return
        try:
            from core.wiki_scraper import fetch_single_pet
            import tkinter.messagebox as _mb
            pet = fetch_single_pet(kw)
            if pet:
                from core.type_data import add_temp_pet, reload
                add_temp_pet(pet)
                reload()
                self.all_pets = get_all_pets()
                # 直接遍历 self.all_pets 筛选（含临时缓存），不用 search_pets
                self.search_var.set(kw)
                self._do_search_with_temp()
                _mb.showinfo("成功", f"已从 Wiki 获取「{kw}」数据！")
            else:
                _mb.showwarning("未找到", f"Wiki 中未找到精灵「{kw}」")
        except Exception as e:
            import tkinter.messagebox as _mb
            _mb.showerror("错误", f"网络搜索失败: {e}")

    def _do_search_with_temp(self):
        """搜索含临时缓存的完整列表"""
        kw = self.search_var.get().strip()
        self.pet_listbox.delete(0, tk.END)
        kw_lower = kw.lower()
        found = False
        all_candidates = self._filter_pets(self.all_pets) if self.active_type else self.all_pets
        for pet in all_candidates:
            if kw_lower in pet.get("name", "").lower():
                if self.active_type and self.active_type not in pet.get("attributes", []):
                    continue
                attrs = pet.get("attributes", [])
                attr_str = "/".join(attrs) if attrs else "?"
                name = pet.get("name", "?")
                form = pet.get("form") or ""
                region = pet.get("region_form") or ""
                if region:
                    display = f"{name} - {form} [{region}]  [{attr_str}]"
                elif form:
                    display = f"{name} - {form}  [{attr_str}]"
                else:
                    display = f"{name}  [{attr_str}]"
                self.pet_listbox.insert(tk.END, display)
                found = True
        if not found:
            self.search_var.set("")
            self._refresh_pet_list()
        display_count = sum(1 for _ in self.pet_listbox.get(0, tk.END))
        total = len(self.all_pets)
        if found:
            self.count_var.set(f"搜索结果：{display_count} 只")
        else:
            self.count_var.set(f"共 {len(self._filter_pets(self.all_pets))} 只精灵{'' if self.active_type is None else '（' + self.active_type + '）'}")

    # ── 精灵选择 ──
    def _on_pet_select(self, event):
        sel = self.pet_listbox.curselection()
        if not sel:
            return

        idx = sel[0]
        display = self.pet_listbox.get(idx)
        # 从显示文本提取精灵名和形态："name - form [region]  [attr]" 或 "name  [attr]"
        pet_name = display.split("  [")[0].strip()
        # 尝试解析形态
        form = None
        if " - " in pet_name:
            parts = pet_name.split(" - ", 1)
            pet_name = parts[0].strip()
            form_str = parts[1].strip()
            # form_str 可能是 "原始形态 [海神球形态]"，提取第一个空格前作为 form
            if " [" in form_str:
                form = form_str.split(" [")[0].strip()
            else:
                form = form_str
        pet = get_pet(pet_name, form=form)
        if pet:
            self._show_detail(pet)

    def _show_detail(self, pet):
        # 清空详情区
        for widget in self.detail_frame.winfo_children():
            widget.destroy()
        self._photo_refs = []

        name = pet.get("name", "?")
        attrs = pet.get("attributes", [])
        attr_str = "/".join(attrs) if attrs else "?"
        no = pet.get("no", "")
        form = pet.get("form", "")
        region_form = pet.get("region_form", "")
        stage = pet.get("stage", "")
        pet_type = pet.get("pet_type", "")

        # ── 名称 & 编号 ──
        name_frame = ttk.Frame(self.detail_frame)
        name_frame.pack(fill=tk.X, padx=PAD_X, pady=(4, 2))

        ttk.Label(
            name_frame, text=name,
            font=("Microsoft YaHei", 15, "bold"),
        ).pack(side=tk.LEFT)

        if no:
            ttk.Label(
                name_frame, text=f"No.{no}",
                font=FONT_BODY, foreground=TEXT_HINT,
            ).pack(side=tk.LEFT, padx=10)

        # ── 精灵图片 ──
        img_path = get_pet_image_path(name)
        if img_path:
            try:
                img = tk.PhotoImage(file=img_path)
                # 限制最大宽度 200px，按比例缩放
                w, h = img.width(), img.height()
                if w > 200:
                    ratio = max(1, w // 200 + 1)
                    img = img.subsample(ratio, ratio)
                photo_ref = img  # 保持引用防止被GC
                img_frame = ttk.Frame(self.detail_frame)
                img_frame.pack(fill=tk.X, padx=PAD_X, pady=3)
                tk.Label(img_frame, image=photo_ref, bg=BG_APP).pack()
                # 保存引用到实例，防止被回收
                if not hasattr(self, '_photo_refs'):
                    self._photo_refs = []
                self._photo_refs.append(photo_ref)
            except Exception:
                pass  # 图片加载失败则跳过

        # ── 形态/阶段/类型信息行 ──
        meta_parts = []
        if form:
            meta_parts.append(f"形态: {form}")
        if region_form:
            meta_parts.append(f"地区形态: {region_form}")
        if stage:
            meta_parts.append(f"阶段: {stage}")
        if pet_type:
            meta_parts.append(f"类型: {pet_type}")
        if meta_parts:
            meta_frame = ttk.Frame(self.detail_frame)
            meta_frame.pack(fill=tk.X, padx=PAD_X, pady=2)
            ttk.Label(
                meta_frame, text="  |  ".join(meta_parts),
                font=FONT_SMALL, foreground=TEXT_SECONDARY,
            ).pack(anchor=tk.W)

        # ── 属性标签 ──
        attr_frame = ttk.Frame(self.detail_frame)
        attr_frame.pack(fill=tk.X, padx=PAD_X, pady=2)

        ttk.Label(
            attr_frame, text="属性：",
            font=FONT_BODY,
        ).pack(side=tk.LEFT)

        for attr in attrs:
            bg = TYPE_COLORS.get(attr, "#999999")
            lbl = tk.Label(
                attr_frame,
                text=f" {attr} ",
                font=("Microsoft YaHei", 10, "bold"),
                bg=bg, fg="white",
                relief=tk.FLAT,
            )
            lbl.pack(side=tk.LEFT, padx=2)

        # ── 种族值（含雷达图） ──
        stats = pet.get("stats", {})
        stats_outer = ttk.LabelFrame(self.detail_frame, text="种族值", padding=6)
        stats_outer.pack(fill=tk.X, padx=PAD_X, pady=(6, 2))

        # 左右布局：左侧文字数值，右侧雷达图
        stats_row = ttk.Frame(stats_outer)
        stats_row.pack(fill=tk.X)

        # 左侧文字
        stats_text_frame = ttk.Frame(stats_row)
        stats_text_frame.pack(side=tk.LEFT, padx=(0, 10))

        stat_labels = [
            ("HP", "hp"), ("物攻", "atk"), ("魔攻", "sp_atk"),
            ("物防", "def"), ("魔防", "sp_def"), ("速度", "spd"),
            ("总和", "total"),
        ]

        for i, (label, key) in enumerate(stat_labels):
            val = stats.get(key, "?")
            row = i // 2
            col = i % 2

            stat_cell = ttk.Frame(stats_text_frame)
            stat_cell.grid(row=row, column=col, padx=8, pady=3, sticky=tk.W)

            ttk.Label(
                stat_cell, text=label,
                font=FONT_SMALL, foreground=TEXT_HINT,
            ).pack(side=tk.LEFT)
            ttk.Label(
                stat_cell, text=f" {val}",
                font=("Microsoft YaHei", 10, "bold"),
            ).pack(side=tk.LEFT)

        # 右侧雷达图
        main_attr = attrs[0] if attrs else None
        self._draw_radar_chart(stats_row, stats, main_attr or "普通")

        # ── 特性 ──
        ability = pet.get("ability", {})
        if ability and ability.get("name"):
            ab_frame = ttk.LabelFrame(self.detail_frame, text="特性", padding=8)
            ab_frame.pack(fill=tk.X, padx=8, pady=3)

            if isinstance(ability, dict):
                ab_name = ability.get("name", "")
                ab_desc = ability.get("description", "")
                ttk.Label(
                    ab_frame, text=f"{ab_name}：{ab_desc}",
                    font=("Microsoft YaHei", 10), wraplength=400,
                ).pack(anchor=tk.W)

        # ── 可学技能 ──
        skills = pet.get("skills", [])
        if skills:
            self._build_skill_section("可学技能", skills)

        # ── 血脉技能 ──
        bloodline_skills = pet.get("bloodline_skills", [])
        if bloodline_skills:
            self._build_skill_section("血脉技能", bloodline_skills)

        # ── 技能石 ──
        quest_stones = pet.get("quest_stones", [])
        valid_stones = [s for s in quest_stones if isinstance(s, dict)]
        if valid_stones:
            self._build_skill_section("课题技能石", valid_stones)

        # ── 可学技能石 ──
        learnable_stones = pet.get("learnable_stones", [])
        valid_learnable = [s for s in learnable_stones if isinstance(s, dict)]
        if valid_learnable:
            self._build_skill_section("可学技能石", valid_learnable)

    def _draw_radar_chart(self, parent, stats, attr_type):
        """绘制种族值六维雷达图"""
        import math

        W = 250
        H = 250
        cx = W / 2
        cy = H / 2
        r = 100  # 最大半径

        canvas = tk.Canvas(parent, width=W, height=H, bg="#FFFFFF", highlightthickness=0)
        canvas.pack()

        # 维度定义（绕圆逆时针排列：顶→左上→左下→底→右下→右上）
        dims = [
            ("HP", stats.get("hp", 0)),          # 90° 顶部
            ("物攻", stats.get("atk", 0)),        # 150° 左上
            ("物防", stats.get("def", 0)),        # 210° 左下
            ("速度", stats.get("spd", 0)),        # 270° 底部
            ("魔防", stats.get("sp_def", 0)),     # 330° 右下
            ("魔攻", stats.get("sp_atk", 0)),     # 30° 右上
        ]

        max_val = max(max(v for _, v in dims), 1)
        # 取整到 50
        max_val = ((max_val - 1) // 50 + 1) * 50
        if max_val < 100:
            max_val = 100

        n = len(dims)
        angles = [
            math.pi / 2,        # 90° 顶部
            5 * math.pi / 6,    # 150° 左上
            7 * math.pi / 6,    # 210° 左下
            3 * math.pi / 2,    # 270° 底部
            11 * math.pi / 6,   # 330° 右下
            math.pi / 6,        # 30° 右上
        ]

        def point(i, v):
            ratio = v / max_val
            x = cx + r * ratio * math.cos(angles[i])
            y = cy - r * ratio * math.sin(angles[i])
            return x, y

        # 灰色网格
        levels = 4
        for lv in range(1, levels + 1):
            pts = []
            ratio = lv / levels
            for i in range(n):
                x = cx + r * ratio * math.cos(angles[i])
                y = cy - r * ratio * math.sin(angles[i])
                pts.extend([x, y])
            canvas.create_polygon(pts, outline="#D5D8DC", fill="", width=1)

        # 轴线
        for i in range(n):
            x = cx + r * math.cos(angles[i])
            y = cy - r * math.sin(angles[i])
            canvas.create_line(cx, cy, x, y, fill="#D5D8DC", width=1)

        # 属性颜色
        fill_color = RADAR_TYPE_COLORS.get(attr_type, "#9B59B6")

        # 数据多边形
        data_pts = []
        for i, (name, val) in enumerate(dims):
            x, y = point(i, val)
            data_pts.extend([x, y])
        canvas.create_polygon(data_pts, outline=fill_color, fill=fill_color, width=2, stipple="gray50")
        # 数据点
        for i, (name, val) in enumerate(dims):
            x, y = point(i, val)
            canvas.create_oval(x-3, y-3, x+3, y+3, fill=fill_color, outline="")

        # 顶点标注
        for i, (name, val) in enumerate(dims):
            x, y = point(i, max_val)
            # 偏移标签避免重叠
            angle = angles[i]
            dx = 12 * math.cos(angle)
            dy = -12 * math.sin(angle)
            canvas.create_text(
                x + dx, y + dy,
                text=f"{name}\n{val}",
                font=("Microsoft YaHei", 7),
                fill="#2C3E50",
                anchor="center",
            )

    def _build_skill_section(self, title, skills):
        """构建技能列表区域"""
        skill_frame = ttk.LabelFrame(self.detail_frame, text=f"{title}（{len(skills)}个）", padding=8)
        skill_frame.pack(fill=tk.X, padx=8, pady=3)

        # 表头
        headers = ["技能名", "属性", "类型", "威力", "耗能"]
        widths = [14, 6, 4, 5, 5]

        header_frame = ttk.Frame(skill_frame)
        header_frame.pack(fill=tk.X, pady=(0, 3))

        for header, width in zip(headers, widths):
            ttk.Label(
                header_frame, text=header,
                font=("Microsoft YaHei", 8, "bold"),
                foreground="#7F8C8D", width=width, anchor=tk.CENTER,
            ).pack(side=tk.LEFT, padx=1)

        ttk.Separator(skill_frame, orient=tk.HORIZONTAL).pack(fill=tk.X)

        for sk in skills:
            if not isinstance(sk, dict):
                continue
            row_frame = ttk.Frame(skill_frame)
            row_frame.pack(fill=tk.X, pady=1)

            name = sk.get("name", "?")
            attr = sk.get("attribute", "?")
            cat = sk.get("category", "?")
            power = sk.get("power", "?")
            cost = sk.get("cost", "?")

            # 技能图标
            icon_label = tk.Label(row_frame, bg=BG_APP)
            img_path = get_skill_image_path(name)
            if img_path:
                try:
                    photo = tk.PhotoImage(file=img_path)
                    if photo.width() > 24:
                        ratio = max(1, photo.width() // 24)
                        photo = photo.subsample(ratio, ratio)
                    icon_label.configure(image=photo)
                    self._skill_photo_refs.append(photo)
                except Exception:
                    pass
            icon_label.pack(side=tk.LEFT, padx=1)

            values = [name, attr, cat, str(power), str(cost)]
            for val, w in zip(values, widths):
                ttk.Label(
                    row_frame, text=val,
                    font=("Microsoft YaHei", 9),
                    width=w, anchor=tk.CENTER,
                ).pack(side=tk.LEFT, padx=1)