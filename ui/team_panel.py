"""
竹雨ROCOM小助手 - 配队编辑UI（重构版）
支持精灵搜索选择、技能选择(4个)、性格修正、弱点分析
"""

import tkinter as tk
import os
import threading
import time
from tkinter import ttk, messagebox, filedialog, simpledialog
import json
import re
from core.type_data import (
    get_pet, search_pets, get_all_pet_names, get_all_pets,
    get_skill, get_all_skill_names,
    get_effectiveness, get_type_info, ALL_TYPES,
    NATURES, NATURE_NAMES,
    get_pet_image_path, get_skill_image_path,
)
from core.team_manager import TeamManager
from ui.theme import (
    TYPE_COLORS, PRIMARY, PRIMARY_HOVER, SUCCESS, SUCCESS_HOVER,
    DANGER, DANGER_HOVER, WARNING,
    BG_CARD, BG_APP, TEXT_SECONDARY, TEXT_HINT,
    FONT_BODY, FONT_SMALL, FONT_CAPTION,
    PAD_X,
)
from core.bloodline_data import get_bloodlines_for_pet, get_bloodline_desc, ALL_BLOODLINES

try:
    from PIL import Image
except ImportError:
    Image = None


def _parse_game_team_code(text):
    """解析游戏内阵容码格式，返回字典或 None。

    格式说明:
        ### 队伍名
        # 魔法：魔法名
        # 宠物名：血脉、{技能1、技能2、技能3、技能4}
        (底部的乱码行如 B~Gu-... 自动忽略)
    """
    lines = text.strip().split('\n')
    result = {"name": "", "magic": "", "pets": []}

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith('###'):
            # 队伍名
            result["name"] = line[3:].strip()
        elif re.match(r'^#\s*魔法[：:]', line):
            # 魔法：# 魔法：魔法名 或 #魔法：魔法名
            if '：' in line:
                magic = line.split('：', 1)[-1].strip()
            elif ':' in line:
                magic = line.split(':', 1)[-1].strip()
            else:
                continue
            if magic:
                result["magic"] = magic
        elif line.startswith('#') and '：' in line:
            # 宠物信息：# 宠物名：血脉、{技能1、技能2、技能3、技能4}
            content = line[1:].strip()  # 去掉开头的 #
            if '：' not in content:
                continue
            parts = content.split('：', 1)
            pet_name = parts[0].strip()
            rest = parts[1].strip()

            bloodline = "无"
            skills = []

            if '{' in rest and '}' in rest:
                # 血脉在 { 之前，技能在 {} 内
                bl_part = rest.split('{', 1)[0].strip().rstrip('、').rstrip(',')
                if bl_part:
                    bloodline = bl_part
                sk_part = rest.split('{', 1)[1].split('}', 1)[0]
                skills = [s.strip() for s in sk_part.split('、') if s.strip()]
            else:
                bloodline = rest.strip()

            result["pets"].append({
                "name": pet_name,
                "bloodline": bloodline,
                "skills": skills,
            })
        # 其他行（如 B~Gu-... 乱码）自动忽略

    if not result["pets"]:
        return None
    if not result["name"]:
        result["name"] = "导入配队"
    return result


class TeamPanel(ttk.Frame):
    """配队编辑面板"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.manager = TeamManager()
        self.current_team_idx = -1
        self.current_member_idx = -1
        self._skill_photo_refs = []  # 技能图标 PhotoImage 引用防止 GC
        # 自动加载已保存的Wiki配队
        try:
            from core.wiki_team_fetcher import import_wiki_teams_to_manager
            imported = import_wiki_teams_to_manager(self.manager)
            # 修复已有wiki配队的技能数据（之前字段名错误导致全是?）
            if imported == 0:
                self._repair_wiki_team_skills()
        except Exception:
            pass
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

        self._refresh_team_list()

    # ── UI构建 ─────────────────────────────────────────────────────
    def _build_ui(self):
        # 主布局：左侧配队列表 + 右侧编辑区
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 左侧配队列表
        left_frame = ttk.LabelFrame(main_frame, text="配队列表", padding=5)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))

        self.team_listbox = tk.Listbox(
            left_frame, font=("Microsoft YaHei", 10),
            width=16, height=18, selectmode=tk.SINGLE,
        )
        self.team_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.team_listbox.bind("<<ListboxSelect>>", self._on_team_select)

        # === Wiki配队功能区 ===
        wiki_frame = ttk.LabelFrame(left_frame, text="Wiki配队 ▼", padding=3)

        wiki_warning = tk.Label(wiki_frame, text="⚠ 请勿频繁点击，间隔至少10秒以免触发网站安全策略",
                               font=("Microsoft YaHei", 7), fg="#E67E22", anchor=tk.W)
        wiki_warning.pack(fill=tk.X, pady=(0, 2))
        wiki_frame.pack(fill=tk.X, pady=(5, 0))

        wiki_btn_row1 = ttk.Frame(wiki_frame)
        wiki_btn_row1.pack(fill=tk.X, pady=1)
        tk.Button(wiki_btn_row1, text="网络全量获取", font=("Microsoft YaHei", 8),
                  bg="#8E44AD", fg="white", relief=tk.FLAT, cursor="hand2",
                  command=self._wiki_fetch_all).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
        tk.Button(wiki_btn_row1, text="随机配队", font=("Microsoft YaHei", 8),
                  bg="#9B59B6", fg="white", relief=tk.FLAT, cursor="hand2",
                  command=self._wiki_random_team).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

        wiki_btn_row2 = ttk.Frame(wiki_frame)
        wiki_btn_row2.pack(fill=tk.X, pady=1)
        tk.Button(wiki_btn_row2, text="按精灵选配队", font=("Microsoft YaHei", 8),
                  bg="#3498DB", fg="white", relief=tk.FLAT, cursor="hand2",
                  command=self._wiki_search_by_pet).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)
        tk.Button(wiki_btn_row2, text="删除网络配队", font=("Microsoft YaHei", 8),
                  bg="#E74C3C", fg="white", relief=tk.FLAT, cursor="hand2",
                  command=self._wiki_delete_all).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

        self._wiki_progress_var = tk.StringVar(value="")
        # 启动时自动导入已有的Wiki配队
        self.after(500, self._auto_import_wiki)
        self._wiki_progress_label = tk.Label(wiki_frame, textvariable=self._wiki_progress_var,
                                             font=("Microsoft YaHei", 7), fg="#999999", anchor=tk.W)
        self._wiki_progress_label.pack(fill=tk.X, pady=(2, 0))





        team_btn_frame = ttk.Frame(left_frame)
        team_btn_frame.pack(fill=tk.X, pady=3)
        for text, color, cmd in [
            ("新建", "#27AE60", self._create_team),
            ("删除", "#E74C3C", self._delete_team),
            ("导出", "#4A90D9", self._export_team),
            ("导入", "#4A90D9", self._import_team),
        ]:
            tk.Button(team_btn_frame, text=text, font=("Microsoft YaHei", 9),
                      bg=color, fg="white", relief=tk.FLAT, cursor="hand2",
                      command=cmd).pack(fill=tk.X, pady=1)

        # 右侧
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))

        # 阵容码显示行（配队列表右侧上方）
        code_frame = ttk.Frame(right_frame)
        code_frame.pack(fill=tk.X, pady=(0, 3))

        ttk.Label(code_frame, text="阵容码：", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.team_code_var = tk.StringVar(value="")
        code_entry = ttk.Entry(
            code_frame, textvariable=self.team_code_var,
            font=("Microsoft YaHei", 9), width=55,
        )
        code_entry.pack(side=tk.LEFT, padx=3)

        tk.Button(
            code_frame, text="复制", bg="#4A90D9", fg="white",
            font=("Microsoft YaHei", 9), relief=tk.FLAT, cursor="hand2",
            command=self._copy_team_code,
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            code_frame, text="导出图片", bg="#8E44AD", fg="white",
            font=("Microsoft YaHei", 9), relief=tk.FLAT, cursor="hand2",
            command=self._export_team_image,
        ).pack(side=tk.LEFT, padx=2)

        # 游戏内配队码输入行
        game_code_frame = ttk.Frame(right_frame)
        game_code_frame.pack(fill=tk.X, pady=(0, 3))

        ttk.Label(game_code_frame, text="游戏内配队码：", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        self.game_code_var = tk.StringVar(value="")
        game_code_entry = ttk.Entry(
            game_code_frame, textvariable=self.game_code_var,
            font=("Microsoft YaHei", 9), width=40,
        )
        game_code_entry.pack(side=tk.LEFT, padx=3)

        tk.Button(
            game_code_frame, text="保存", bg="#27AE60", fg="white",
            font=("Microsoft YaHei", 9), relief=tk.FLAT, cursor="hand2",
            command=self._save_game_code,
        ).pack(side=tk.LEFT, padx=2)

        # 魔法显示行
        magic_frame = ttk.Frame(right_frame)
        magic_frame.pack(fill=tk.X, pady=(0, 3))
        self.magic_label = tk.Label(
            magic_frame, text="魔法：未选择",
            font=("Microsoft YaHei", 9, "bold"), fg="#5B7FFF",
            anchor=tk.W, justify=tk.LEFT, wraplength=550
        )
        self.magic_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)

        # 上方：精灵列表
        member_top = ttk.Frame(right_frame)
        member_top.pack(fill=tk.BOTH, expand=True)

        member_frame = ttk.LabelFrame(member_top, text="队伍精灵", padding=5)
        member_frame.pack(fill=tk.BOTH, expand=True)

        self.member_rows = []  # 每行 (frame, img_label, text_label, photo_ref, index)
        self.selected_member_row = -1
        self.member_row_bg = "#F5F6FA"
        self.member_row_sel_bg = "#D6E4F0"

        # 精灵列表 (可滚动行，图片+文字对齐)
        member_list_container = ttk.Frame(member_frame)
        member_list_container.pack(fill=tk.BOTH, expand=True)

        self.member_canvas = tk.Canvas(member_list_container, bg="#F5F6FA", highlightthickness=0)
        self.member_scrollbar = ttk.Scrollbar(member_list_container, orient=tk.VERTICAL, command=self.member_canvas.yview)
        self.member_rows_frame = ttk.Frame(self.member_canvas)

        self.member_rows_frame.bind("<Configure>", lambda e: self.member_canvas.configure(scrollregion=self.member_canvas.bbox("all")))
        self.member_canvas.create_window((0, 0), window=self.member_rows_frame, anchor="nw")
        self.member_canvas.configure(yscrollcommand=self.member_scrollbar.set)

        self.member_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.member_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        # 鼠标滚轮支持
        self.member_canvas.bind("<Enter>", lambda e: self.member_canvas.bind_all("<MouseWheel>", lambda ev: self.member_canvas.yview_scroll(int(-1*(ev.delta/120)), "units")))
        self.member_canvas.bind("<Leave>", lambda e: self.member_canvas.unbind_all("<MouseWheel>"))

        member_btn = ttk.Frame(member_frame)
        member_btn.pack(fill=tk.X, pady=3)
        for text, color, hover_color, cmd in [
            ("添加精灵", SUCCESS, SUCCESS_HOVER, self._add_member),
            ("编辑精灵", WARNING, "#D68910", self._edit_member),
            ("删除精灵", DANGER, DANGER_HOVER, self._remove_member),
            ("弱点分析", "#8E44AD", "#7D3C98", self._analyze_weakness),
            ("导入阵容码", "#E67E22", "#CA6F1E", self._import_team_code),
            ("魔法", "#9B59B6", "#8E44AD", self._select_magic),
        ]:
            tk.Button(member_btn, text=text, font=FONT_SMALL,
                      bg=color, fg="white",
                      activebackground=hover_color,
                      relief=tk.FLAT, cursor="hand2",
                      borderwidth=0, padx=8, pady=3,
                      command=cmd).pack(side=tk.LEFT, padx=2)

        # 下方：精灵详情 + 雷达图
        bottom_frame = ttk.Frame(right_frame)
        bottom_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # 详情 + 雷达图水平排列
        detail_radar_frame = ttk.Frame(bottom_frame)
        detail_radar_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 3))

        self._build_detail_panel(detail_radar_frame)
        self._build_radar_canvas(detail_radar_frame)

    def _build_detail_panel(self, parent):
        detail_frame = ttk.LabelFrame(parent, text="精灵详情", padding=5)
        detail_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.member_image_label = tk.Label(
            detail_frame,
            bg=BG_CARD,
        )
        self.member_image_label.pack(pady=(0, 3))
        self._member_photo_ref = None

        # 详情文本 + 滚动条
        detail_text_frame = ttk.Frame(detail_frame)
        detail_text_frame.pack(fill=tk.BOTH, expand=True)

        self.member_detail = tk.Text(
            detail_text_frame, font=("Microsoft YaHei", 10),
            height=12, state=tk.DISABLED,
        )
        detail_scrollbar = ttk.Scrollbar(detail_text_frame, orient=tk.VERTICAL,
                                         command=self.member_detail.yview)
        self.member_detail.configure(yscrollcommand=detail_scrollbar.set)
        self.member_detail.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _build_radar_canvas(self, parent):
        """种族值六维雷达图 Canvas"""
        radar_frame = ttk.LabelFrame(parent, text="种族值雷达图", padding=3)
        radar_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))

        self.radar_canvas = tk.Canvas(
            radar_frame,
            width=250, height=250,
            bg="#F5F6FA",
            highlightthickness=0,
        )
        self.radar_canvas.pack(fill=tk.BOTH, expand=True)
        self._draw_radar_chart({})

    def _refresh_team_list(self):
        self.team_listbox.delete(0, tk.END)
        for i, t in enumerate(self.manager.teams):
            tag = " [网络]" if t.get("source") == "wiki" else ""
            self.team_listbox.insert(tk.END, f"[{i}] {t.get('name', '未命名')}{tag}")

    def _refresh_member_list(self):
        for row_frame, _, _, _, _ in self.member_rows:
            row_frame.destroy()
        self.member_rows.clear()
        self.selected_member_row = -1
        team = self.manager.get_team(self.current_team_idx)
        if not team:
            return
        for i, m in enumerate(team.get("members", [])):
            attrs = m.get("attributes", [])
            attr_str = "/".join(attrs) if attrs else "?"
            nature = m.get("nature", "")
            boosts = m.get("boosts", [])
            boost_str = "[" + ",".join(b for b in boosts if b != "无") + "] " if boosts and any(b != "无" for b in boosts) else ""
            skills = m.get("skills", [])
            skill_str = " → ".join(s.get("name", "?") for s in skills) if skills else "无技能"
            text = f"[{i}] {boost_str}{m['name']} | {attr_str} | {m.get('bloodline','无')} | {nature} | {skill_str}"
            # 创建行 Frame
            row_frame = tk.Frame(self.member_rows_frame, bg=self.member_row_bg, cursor="hand2")
            row_frame.pack(fill=tk.X, pady=1, padx=2)

            # 精灵小图
            img_label = tk.Label(row_frame, bg=self.member_row_bg)
            img_label.pack(side=tk.LEFT, padx=(4, 8), pady=2)

            img_path = get_pet_image_path(m.get("name", ""))
            photo_ref = None
            if img_path and os.path.exists(img_path):
                try:
                    from PIL import Image, ImageTk
                    pil_img = Image.open(img_path).resize((44, 44), Image.LANCZOS)
                    photo_ref = ImageTk.PhotoImage(pil_img)
                    img_label.configure(image=photo_ref, bg=self.member_row_bg)
                except Exception:
                    pass

            # 文字标签
            text_label = tk.Label(row_frame, text=text, font=("Microsoft YaHei", 10),
                                  bg=self.member_row_bg, anchor=tk.W, justify=tk.LEFT)
            text_label.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=2)

            # 绑定点击事件
            def make_handler(idx):
                return lambda e: self._on_row_click(idx)
            row_frame.bind("<Button-1>", make_handler(i))
            img_label.bind("<Button-1>", make_handler(i))
            text_label.bind("<Button-1>", make_handler(i))

            self.member_rows.append((row_frame, img_label, text_label, photo_ref, i))
        self.member_canvas.configure(scrollregion=self.member_canvas.bbox("all"))

    def _on_row_click(self, idx):
        """处理行点击 - 高亮选中行"""
        self.current_member_idx = idx
        # 取消旧高亮
        for row_frame, img_label, text_label, _, _ in self.member_rows:
            row_frame.configure(bg=self.member_row_bg)
            img_label.configure(bg=self.member_row_bg)
            text_label.configure(bg=self.member_row_bg)
        # 设置新高亮
        if idx < len(self.member_rows):
            rf, il, tl, _, _ = self.member_rows[idx]
            rf.configure(bg=self.member_row_sel_bg)
            il.configure(bg=self.member_row_sel_bg)
            tl.configure(bg=self.member_row_sel_bg)
            self.selected_member_row = idx
        team = self.manager.get_team(self.current_team_idx)
        members = team.get("members", [])
        if idx < len(members):
            self._show_detail(members[idx])
    # ── 事件处理 ─────────────────────────────────────────────────────
    def _on_team_select(self, event):
        sel = self.team_listbox.curselection()
        if not sel:
            return
        idx = self.team_listbox.get(sel[0])
        self.current_team_idx = int(idx.split("]")[0].strip("["))
        self.current_member_idx = -1
        self._refresh_member_list()
        self._clear_detail()
        self._update_team_code_display()
        self._update_game_code_display()
        team = self.manager.get_team(self.current_team_idx)
        magic = team.get("magic", "") if team else ""
        # 显示配队完整信息（有wiki字段就显示）
        info_parts = []
        info_parts.append(f"魔法：{magic}" if magic else "魔法：无")
        if team:
            author = team.get("wiki_author", "") or team.get("author", "")
            if author:
                info_parts.append(f"作者：{author}")
            wtype = team.get("wiki_type", "") or team.get("type", "")
            if wtype:
                info_parts.append(f"类型：{wtype.upper()}")
            wdate = team.get("wiki_date", "") or team.get("date", "")
            if wdate:
                info_parts.append(f"日期：{wdate}")
            wdesc = team.get("wiki_desc", "") or team.get("description", "")
            if wdesc:
                short_desc = wdesc[:40] + "..." if len(wdesc) > 40 else wdesc
                info_parts.append(" | 介绍：" + short_desc)
        self.magic_label.configure(text=" | ".join(info_parts))

    # _on_member_select 已由 _on_row_click 替代

    def _clear_detail(self):
        self.member_detail.configure(state=tk.NORMAL)
        self.member_detail.delete(1.0, tk.END)

    def _show_detail(self, member):
        self.member_detail.configure(state=tk.NORMAL)
        self.member_detail.delete(1.0, tk.END)

        # 精灵图片
        name = member.get("name", "")
        img_path = get_pet_image_path(name)
        if img_path:
            try:
                img = tk.PhotoImage(file=img_path)
                w, h = img.width(), img.height()
                if w > 140:
                    ratio = max(1, w // 140 + 1)
                    img = img.subsample(ratio, ratio)
                self.member_image_label.configure(image=img, bg=BG_CARD)
                self._member_photo_ref = img
            except Exception:
                self.member_image_label.configure(image="", bg=BG_CARD)
                self._member_photo_ref = None
        else:
            self.member_image_label.configure(image="", bg=BG_CARD)
            self._member_photo_ref = None

        attrs = member.get("attributes", [])
        stats = member.get("stats", {})
        ability = member.get("ability", {})
        nature = member.get("nature", "无")
        skills = member.get("skills", [])

        # 带形态后缀的精灵（非"本来的样子"）不显示种族值
        has_form = bool(re.search(r'[（(][^)）]*[)）]', member.get('name', '')))
        is_original = '本来的样子' in member.get('name', '')
        skip_stats = has_form and not is_original

        prefix_lines = [
            f"精灵：{member.get('name', '?')}  No.{member.get('no', '?')}",
            f"属性：{'/'.join(attrs)}",
            f"性格：{nature}  ({self.manager.get_nature_description(nature)})",
            f"特性：{ability.get('name', '?')} - {ability.get('description', '?')}",
        ]
        if not skip_stats:
            prefix_lines += [
                f"种族值：HP{stats.get('hp','?')} 物攻{stats.get('atk','?')} 魔攻{stats.get('sp_atk','?')}",
                f"        物防{stats.get('def','?')} 魔防{stats.get('sp_def','?')} 速度{stats.get('spd','?')}",
                f"总和：{stats.get('total','?')}",
            ]
        prefix_lines += [
            "",
            "技能配置：",
        ]
        self.member_detail.insert(tk.END, "\n".join(prefix_lines))

        # 技能列表（带图标嵌入）
        suffix_lines = []
        for i, sk in enumerate(skills):
            if isinstance(sk, dict):
                sk_name = sk.get("name", "?")
                sk_line = f"  {i+1}. {sk_name} [{sk.get('attribute','?')}|{sk.get('category','?')}|威力{sk.get('power','?')}|能耗{sk.get('cost','?')}]"
            else:
                sk_name = sk
                sk_line = f"  {i+1}. {sk}"

            # 嵌入技能图标
            img_path = get_skill_image_path(sk_name)
            if img_path:
                try:
                    photo = tk.PhotoImage(file=img_path)
                    if photo.width() > 24:
                        ratio = max(1, photo.width() // 24)
                        photo = photo.subsample(ratio, ratio)
                    self._skill_photo_refs.append(photo)
                    self.member_detail.insert(tk.END, "\n")
                    self.member_detail.image_create(tk.END, image=photo)
                    self.member_detail.insert(tk.END, sk_line)
                except Exception:
                    self.member_detail.insert(tk.END, "\n" + sk_line)
            else:
                self.member_detail.insert(tk.END, "\n" + sk_line)

        # 从精灵数据中补充血脉技能、技能石、可学技能石
        pet = get_pet(member.get("name", ""))
        if pet:
            bloodline_list = pet.get("bloodline_skills", [])
            quest_stones = pet.get("quest_stones", [])
            learnable = pet.get("learnable_stones", [])
            all_extra = []
            for s in bloodline_list:
                if isinstance(s, dict):
                    all_extra.append(f"[血脉] {s.get('name','')} [{s.get('attribute','')}|{s.get('category','')}|威力{s.get('power','?')}|能耗{s.get('cost','?')}]")
                else:
                    all_extra.append(f"[血脉] {s}")
            for s in quest_stones:
                if isinstance(s, dict):
                    all_extra.append(f"[技能石] {s.get('name','')} [{s.get('attribute','')}|{s.get('category','')}|威力{s.get('power','?')}|能耗{s.get('cost','?')}]")
                else:
                    all_extra.append(f"[技能石] {s}")
            for s in learnable:
                if isinstance(s, dict):
                    all_extra.append(f"[可学] {s.get('name','')} [{s.get('attribute','')}|{s.get('category','')}|威力{s.get('power','?')}|能耗{s.get('cost','?')}]")
                else:
                    all_extra.append(f"[可学] {s}")
            if all_extra:
                suffix_lines.append("")
                suffix_lines.append("精灵可学技能：")
                suffix_lines.extend(f"  {x}" for x in all_extra)

        bloodline = member.get("bloodline", "无")
        note = member.get("note", "").strip() or "无"
        boosts = member.get("boosts", [])
        boost_str = "、".join(b for b in boosts if b != "无") or "无"
        suffix_lines.extend([
            "",
            f"第三血脉：{bloodline}",
            f"备注：{note}",
            f"属性加成：{boost_str}",
        ])

        self.member_detail.insert(tk.END, "\n".join(suffix_lines))
        self.member_detail.configure(state=tk.DISABLED)

        # 更新雷达图
        self._draw_radar_chart(member.get("stats", {}))

    # ── 配队操作 ─────────────────────────────────────────────────────
    def _create_team(self):
        dialog = tk.Toplevel(self)
        dialog.title("新建配队")
        dialog.geometry("400x460")
        dialog.resizable(False, False)
        dialog.transient(self)

        ttk.Label(dialog, text="配队名称：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(15, 5))
        name_entry = ttk.Entry(dialog, font=("Microsoft YaHei", 11), width=30)
        name_entry.pack(padx=10, pady=5)
        name_entry.focus()

        ttk.Label(dialog, text="作者（选填）：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(5, 2))
        author_entry = ttk.Entry(dialog, font=("Microsoft YaHei", 11), width=30)
        author_entry.pack(padx=10, pady=5)

        ttk.Label(dialog, text="日期（选填，如2026-06-02）：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(5, 2))
        date_entry = ttk.Entry(dialog, font=("Microsoft YaHei", 11), width=30)
        date_entry.pack(padx=10, pady=5)

        ttk.Label(dialog, text="类型（选填，如PVP/PVE）：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(5, 2))
        type_entry = ttk.Entry(dialog, font=("Microsoft YaHei", 11), width=30)
        type_entry.pack(padx=10, pady=5)

        ttk.Label(dialog, text="介绍（选填）：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(5, 2))
        intro_entry = ttk.Entry(dialog, font=("Microsoft YaHei", 11), width=30)
        intro_entry.pack(padx=10, pady=5)

        def do_create():
            name = name_entry.get().strip()
            if not name:
                messagebox.showwarning("提示", "请输入配队名称")
                return
            author = author_entry.get().strip()
            date_val = date_entry.get().strip()
            type_val = type_entry.get().strip()
            intro_val = intro_entry.get().strip()
            team = self.manager.add_team(name)
            if author:
                team["author"] = author
            if date_val:
                team["date"] = date_val
            if type_val:
                team["type"] = type_val
            if intro_val:
                team["description"] = intro_val
            if author or date_val or type_val or intro_val:
                self.manager._save()
            self._refresh_team_list()
            dialog.destroy()

        tk.Button(dialog, text="创建", font=("Microsoft YaHei", 10),
                  bg="#27AE60", fg="white", relief=tk.FLAT,
                  command=do_create).pack(pady=10)

    def _delete_team(self):
        if self.current_team_idx < 0:
            messagebox.showwarning("提示", "请先选择一个配队")
            return
        team = self.manager.get_team(self.current_team_idx)
        if messagebox.askyesno("确认删除", f"确定删除配队「{team.get('name','')}」吗？"):
            wiki_id = team.get("wiki_id", "")
            self.manager.remove_team(self.current_team_idx)
            # 同步删除Wiki JSON中的数据
            if wiki_id:
                try:
                    from core.wiki_team_fetcher import load_teams, save_teams
                    wiki_teams = load_teams()
                    wiki_teams = [t for t in wiki_teams if t.get("wiki_id") != wiki_id]
                    save_teams(wiki_teams)
                except Exception:
                    pass
            self.current_team_idx = -1
            self.current_member_idx = -1
            self._refresh_team_list()
            for row_frame, _, _, _, _ in self.member_rows:
                row_frame.destroy()
            self.member_rows.clear()
            self._clear_detail()
            self._update_team_code_display()
            self._update_game_code_display()

    def _export_team(self):
        if self.current_team_idx < 0:
            messagebox.showwarning("提示", "请先选择一个配队")
            return
        team = self.manager.get_team(self.current_team_idx)
        fp = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON文件", "*.json")],
            initialfile=f"{team.get('name','team')}.json"
        )
        if fp:
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(team, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("导出成功", f"已导出到：\n{fp}")

    def _export_team_image(self):
        if self.current_team_idx < 0:
            messagebox.showwarning("提示", "请先选择一个配队")
            return
        team = self.manager.get_team(self.current_team_idx)
        members = team.get("members", [])
        if len(members) > 6:
            messagebox.showwarning("无法生成", "配队内精灵超过6只，请调整精灵数量后再试")
            return
        if len(members) == 0:
            messagebox.showwarning("无法生成", "配队内没有精灵")
            return
        team_name = team.get("name", "team")
        fp = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG图片", "*.png"), ("JPEG图片", "*.jpg")],
            initialfile=f"{team_name}_配队图.png"
        )
        if not fp:
            return
        try:
            from PIL import ImageDraw, ImageFont
        except ImportError:
            messagebox.showerror("错误", "缺少PIL库，无法生成图片")
            return
        font_paths = [
            "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf",
        ]
        font_path = None
        for fp_font in font_paths:
            if os.path.exists(fp_font):
                font_path = fp_font
                break
        if not font_path:
            messagebox.showerror("错误", "未找到中文字体")
            return
        card_w = 240
        card_h = 200
        cols = min(len(members), 3)
        rows = (len(members) + cols - 1) // cols
        header_h = 180
        img_w = cols * card_w + (cols + 1) * 10
        img_h = header_h + rows * card_h + (rows + 1) * 10
        img = Image.new("RGB", (img_w, img_h), "#F5F6FA")
        draw = ImageDraw.Draw(img)
        try:
            font_title = ImageFont.truetype(font_path, 28)
            font_info = ImageFont.truetype(font_path, 16)
            font_small = ImageFont.truetype(font_path, 13)
            font_tiny = ImageFont.truetype(font_path, 11)
        except Exception:
            font_title = ImageFont.load_default()
            font_info = font_title
            font_small = font_title
            font_tiny = font_title
        y = 15
        draw.text((20, y), team_name, fill="#2C3E50", font=font_title)
        y += 38
        info_lines = []
        author = team.get("wiki_author", "") or team.get("author", "") or team.get("author", "")
        if author:
            info_lines.append(f"作者：{author}")
        wtype = team.get("wiki_type", "")
        if wtype:
            info_lines.append(f"类型：{wtype.upper()}")
        wdate = team.get("wiki_date", "") or team.get("date", "")
        if wdate:
            info_lines.append(f"日期：{wdate}")
        magic = team.get("magic", "")
        if magic:
            info_lines.append(f"魔法：{magic}")
        for line in info_lines:
            draw.text((20, y), line, fill="#555555", font=font_info)
            y += 22
        wdesc = team.get("wiki_desc", "") or team.get("description", "")
        if wdesc:
            desc_show = wdesc[:80] + "..." if len(wdesc) > 80 else wdesc
            draw.text((20, y), f"介绍：{desc_show}", fill="#777777", font=font_small)
            y += 20
        pet_start_y = header_h
        for idx, member in enumerate(members):
            col = idx % cols
            row_idx = idx // cols
            cx = 10 + col * (card_w + 10)
            cy = pet_start_y + row_idx * (card_h + 10)
            draw.rectangle([cx, cy, cx + card_w, cy + card_h], fill="white", outline="#DDDDDD")
            card_y = cy + 8
            pet_name = member.get("name", "???")
            img_path = get_pet_image_path(pet_name)
            pet_img = None
            if img_path and os.path.exists(img_path):
                try:
                    pet_img = Image.open(img_path).resize((56, 56), Image.LANCZOS)
                    if pet_img.mode == "RGBA":
                        bg = Image.new("RGBA", pet_img.size, "white")
                        pet_img = Image.alpha_composite(bg, pet_img).convert("RGB")
                    elif pet_img.mode != "RGB":
                        pet_img = pet_img.convert("RGB")
                    img.paste(pet_img, (cx + 10, card_y))
                except Exception:
                    pet_img = None
            text_x = cx + 10 + (62 if pet_img else 0)
            draw.text((text_x, card_y), f"#{idx+1} {pet_name}", fill="#2C3E50", font=font_info)
            card_y += 22
            bloodline = member.get("bloodline", "无")
            draw.text((text_x, card_y), f"血脉：{bloodline}", fill="#555555", font=font_small)
            card_y += 18
            attrs = member.get("attributes", [])
            attr_str = "/".join(attrs) if attrs else "?"
            draw.text((text_x, card_y), f"属性：{attr_str}", fill="#555555", font=font_small)
            card_y += 18
            nature = member.get("nature", "")
            draw.text((text_x, card_y), f"性格：{nature or '无'}", fill="#555555", font=font_small)
            card_y += 18
            boosts = member.get("boosts", [])
            boost_str = ",".join(b for b in boosts if b != "无") if boosts else "无"
            draw.text((text_x, card_y), f"个体值：{boost_str}", fill="#555555", font=font_small)
            card_y += 18
            skill_y = cy + 8 + max(62 if pet_img else 0, 90)
            draw.text((cx + 10, skill_y), "技能：", fill="#2C3E50", font=font_small)
            skills = member.get("skills", [])
            if skills:
                sl_y = skill_y + 18
                for sk in skills:
                    sn = sk.get("name", "?")
                    sp = sk.get("power", "?")
                    se = sk.get("cost", "?")
                    st = sk.get("attribute", "?")
                    stext = f"{sn}[{st}|威力{sp}|能耗{se}]"
                    draw.text((cx + 12, sl_y), stext, fill="#444444", font=font_tiny)
                    sl_y += 16
            else:
                draw.text((cx + 12, skill_y + 18), "无技能", fill="#999999", font=font_tiny)
        try:
            img.save(fp)
            messagebox.showinfo("导出成功", f"配队图片已保存到：\n{fp}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _import_team(self):
        fp = filedialog.askopenfilename(filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")])
        if fp:
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    team = json.load(f)
                self.manager.teams.append(team)
                self.manager._save()
                self._refresh_team_list()
                self._update_team_code_display()
                messagebox.showinfo("导入成功", f"已导入配队「{team.get('name','?')}」")
            except Exception as e:
                messagebox.showerror("导入失败", str(e))

    # ── 精灵操作 ─────────────────────────────────────────────────────
    def _add_member(self):
        if self.current_team_idx < 0:
            messagebox.showwarning("提示", "请先选择或创建一个配队")
            return
        self._member_edit_dialog("添加精灵")

    def _edit_member(self):
        if self.current_team_idx < 0 or self.current_member_idx < 0:
            messagebox.showwarning("提示", "请先选择一个精灵")
            return
        self._member_edit_dialog("编辑精灵", edit_mode=True)

    def _remove_member(self):
        if self.current_team_idx < 0 or self.current_member_idx < 0:
            messagebox.showwarning("提示", "请先选择一个精灵")
            return
        self.manager.remove_member(self.current_team_idx, self.current_member_idx)
        self.current_member_idx = -1
        self._refresh_member_list()
        self._clear_detail()
        self._update_team_code_display()

    def _member_edit_dialog(self, title, edit_mode=False):
        dialog = tk.Toplevel(self)
        dialog.title(title)
        dialog.geometry("520x600")
        dialog.resizable(False, False)
        dialog.transient(self)

        member_data = {}
        if edit_mode:
            team = self.manager.get_team(self.current_team_idx)
            members = team.get("members", [])
            if self.current_member_idx < len(members):
                member_data = members[self.current_member_idx]

        # 精灵名称 + 搜索
        name_var = tk.StringVar(value=member_data.get("name", ""))
        row1 = ttk.Frame(dialog)
        row1.pack(fill=tk.X, padx=10, pady=(10, 2))
        ttk.Label(row1, text="精灵名称：", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        name_entry = ttk.Entry(row1, textvariable=name_var, font=("Microsoft YaHei", 10), width=30)
        name_entry.pack(side=tk.LEFT, padx=5)

        tk.Button(row1, text="搜索图鉴", bg="#4A90D9", fg="white",
                  font=("Microsoft YaHei", 9), relief=tk.FLAT, cursor="hand2",
                  command=lambda: self._pet_search_dialog(name_var, dialog)).pack(side=tk.LEFT, padx=5)

        # 性格（带修正说明）
        NATURE_DISPLAY = []
        for n in NATURE_NAMES:
            mods = NATURES.get(n, {})
            if mods:
                parts = []
                for k, v in mods.items():
                    if v > 1:
                        parts.append(f"{k}↑")
                    else:
                        parts.append(f"{k}↓")
                NATURE_DISPLAY.append(f"{n} ({', '.join(parts)})")
            else:
                NATURE_DISPLAY.append(f"{n} (无修正)")

        default_nature = member_data.get("nature", "实干")
        default_nature_display = default_nature
        for nd in NATURE_DISPLAY:
            if nd.startswith(default_nature + " ("):
                default_nature_display = nd
                break

        nature_var = tk.StringVar(value=default_nature_display)
        row2 = ttk.Frame(dialog)
        row2.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row2, text="性格：", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        nature_cb = ttk.Combobox(row2, textvariable=nature_var, values=NATURE_DISPLAY,
                                 font=("Microsoft YaHei", 9), width=22, state="readonly")
        nature_cb.pack(side=tk.LEFT, padx=5)

        # 血脉选择
        bloodline_var = tk.StringVar(value=member_data.get("bloodline", "无"))
        row_bl = ttk.Frame(dialog)
        row_bl.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(row_bl, text="第三血脉：", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        def refresh_bloodlines(*args):
            bloodline_cb["values"] = ALL_BLOODLINES

        bloodline_cb = ttk.Combobox(row_bl, textvariable=bloodline_var,
                                     font=("Microsoft YaHei", 9), width=15, state="readonly")
        bloodline_cb.pack(side=tk.LEFT, padx=5)
        ttk.Label(row_bl, text=get_bloodline_desc(bloodline_var.get()),
                  font=("Microsoft YaHei", 8)).pack(side=tk.LEFT, padx=5)
        name_var.trace_add("write", refresh_bloodlines)
        # 初始填充
        refresh_bloodlines()

        # 属性加成（3个可选）
        boost_frame = ttk.Frame(dialog)
        boost_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(boost_frame, text="属性加成：", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        BOOST_OPTIONS = ["无", "HP", "物攻", "魔攻", "物防", "魔防", "速度"]
        existing_boosts = member_data.get("boosts", ["无", "无", "无"])
        boost_vars = []
        for i in range(3):
            bv = tk.StringVar(value=existing_boosts[i] if i < len(existing_boosts) else "无")
            boost_vars.append(bv)
            ttk.Combobox(boost_frame, textvariable=bv, values=BOOST_OPTIONS,
                         font=("Microsoft YaHei", 9), width=6, state="readonly").pack(side=tk.LEFT, padx=2)

        # 技能选择 (4个ComboBox)
        skill_frame = ttk.LabelFrame(dialog, text="技能配置（从精灵可学技能中选择）", padding=5)
        skill_frame.pack(fill=tk.X, padx=10, pady=5)

        # 技能搜索框
        search_row = ttk.Frame(skill_frame)
        search_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(search_row, text="搜索：", font=("Microsoft YaHei", 9), width=8).pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_row, textvariable=search_var, font=("Microsoft YaHei", 9), width=28)
        search_entry.pack(side=tk.LEFT, padx=5)
        ttk.Label(search_row, text="(输入关键词过滤技能)", font=("Microsoft YaHei", 8),
                  foreground=TEXT_HINT).pack(side=tk.LEFT, padx=3)

        existing_skills = member_data.get("skills", [])
        skill_vars = []
        skill_cbs = []
        skill_icon_labels = []    # 四个槽位的图标 Label
        skill_icon_photos = [None, None, None, None]  # 图标 PhotoImage 引用
        _all_skill_values = []    # 全部技能值列表（搜索前保存）

        def _update_skill_icon(idx, skill_name):
            """更新指定槽位的技能图标"""
            if idx >= len(skill_icon_labels):
                return
            lbl = skill_icon_labels[idx]
            img_path = get_skill_image_path(skill_name) if skill_name else None
            if img_path:
                try:
                    photo = tk.PhotoImage(file=img_path)
                    if photo.width() > 24:
                        ratio = max(1, photo.width() // 24)
                        photo = photo.subsample(ratio, ratio)
                    lbl.configure(image=photo)
                    skill_icon_photos[idx] = photo
                except Exception:
                    lbl.configure(image="")
                    skill_icon_photos[idx] = None
            else:
                lbl.configure(image="")
                skill_icon_photos[idx] = None

        def _extract_skill_name(selected):
            """从格式化字符串提取纯技能名"""
            if not selected:
                return ""
            raw_name = selected.split(" [")[0].strip()
            for prefix in ("[血脉] ", "[技能石] ", "[可学] "):
                if raw_name.startswith(prefix):
                    raw_name = raw_name[len(prefix):]
                    break
            return raw_name

        for i in range(4):
            row = ttk.Frame(skill_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=f"技能{i+1}：", font=("Microsoft YaHei", 9), width=8).pack(side=tk.LEFT)

            # 技能图标
            icon_lbl = tk.Label(row, bg="#EAECEE", width=3, height=1)
            icon_lbl.pack(side=tk.LEFT, padx=(0, 3))
            skill_icon_labels.append(icon_lbl)

            default = existing_skills[i].get("name", "") if i < len(existing_skills) else ""
            var = tk.StringVar(value=default)
            skill_vars.append(var)
            cb = ttk.Combobox(row, textvariable=var, font=("Microsoft YaHei", 9), width=30)
            cb.pack(side=tk.LEFT, padx=5)
            skill_cbs.append(cb)

            # 选项变更时更新图标
            def _make_on_skill_change(idx):
                def _on_change(*args):
                    skill_name = _extract_skill_name(skill_vars[idx].get().strip())
                    _update_skill_icon(idx, skill_name)
                return _on_change
            var.trace_add("write", _make_on_skill_change(i))

        # 搜索过滤函数
        def _apply_skill_filter(*args):
            keyword = search_var.get().strip().lower()
            if not _all_skill_values:
                return
            if not keyword:
                for cb in skill_cbs:
                    cb["values"] = _all_skill_values
                return
            filtered = [v for v in _all_skill_values if keyword in v.lower()]
            for cb in skill_cbs:
                cb["values"] = filtered if filtered else ["(无匹配技能)"]

        search_var.trace_add("write", _apply_skill_filter)

        # 技能列表刷新按钮
        def refresh_skill_list():
            nonlocal _all_skill_values
            pet_name = name_var.get().strip()
            pet = get_pet(pet_name)
            if not pet:
                # 模糊匹配：遍历 _pets_list 找包含关键字的
                from core.type_data import get_all_pets
                all_pets = get_all_pets()
                pet_name_lower = pet_name.lower()
                for p in all_pets:
                    if pet_name_lower in p.get("name", "").lower():
                        pet = p
                        break
            if pet:
                formatted = []
                for s in pet.get("skills", []):
                    if isinstance(s, dict):
                        formatted.append(f"{s.get('name','')} [{s.get('attribute','')} {s.get('category','')} 威力{s.get('power',0)} 能耗{s.get('cost',0)}]")
                    else:
                        formatted.append(f"{s} [? ? 威力? 能耗?]")
                for s in pet.get("bloodline_skills", []):
                    if isinstance(s, dict):
                        formatted.append(f"[血脉] {s.get('name','')} [{s.get('attribute','')} {s.get('category','')} 威力{s.get('power',0)} 能耗{s.get('cost',0)}]")
                    else:
                        formatted.append(f"[血脉] {s} [? ? 威力? 能耗?]")
                for s in pet.get("quest_stones", []):
                    if isinstance(s, dict):
                        formatted.append(f"[技能石] {s.get('name','')} [{s.get('attribute','')} {s.get('category','')} 威力{s.get('power',0)} 能耗{s.get('cost',0)}]")
                    else:
                        formatted.append(f"[技能石] {s} [? ? 威力? 能耗?]")
                for s in pet.get("learnable_stones", []):
                    if isinstance(s, dict):
                        formatted.append(f"[可学] {s.get('name','')} [{s.get('attribute','')} {s.get('category','')} 威力{s.get('power',0)} 能耗{s.get('cost',0)}]")
                    else:
                        formatted.append(f"[可学] {s} [? ? 威力? 能耗?]")
                _all_skill_values = formatted if formatted else ["(无可用技能)"]
            else:
                _all_skill_values = get_all_skill_names()
            _apply_skill_filter()

        def network_search_pet():
            """从 Wiki 网络搜索精灵并加入临时缓存"""
            pet_name = name_var.get().strip()
            if not pet_name:
                return
            try:
                from core.wiki_scraper import fetch_single_pet
                import tkinter.messagebox as _mb
                pet = fetch_single_pet(pet_name)
                if pet:
                    from core.type_data import add_temp_pet
                    add_temp_pet(pet)
                    _mb.showinfo("成功", f"已获取「{pet_name}」数据！")
                    refresh_skill_list()
                else:
                    _mb.showwarning("未找到", f"Wiki 中未找到精灵「{pet_name}」")
            except Exception as e:
                import tkinter.messagebox as _mb
                _mb.showerror("错误", f"网络搜索失败: {e}")

        tk.Button(skill_frame, text="刷新技能列表", bg="#3498DB", fg="white",
                  font=("Microsoft YaHei", 9), relief=tk.FLAT, cursor="hand2",
                  command=refresh_skill_list).pack(pady=3)

        # 名称变更时自动刷新技能列表
        name_var.trace_add("write", lambda *a: refresh_skill_list())

        tk.Button(skill_frame, text="网络搜索", bg="#E67E22", fg="white",
                  font=("Microsoft YaHei", 9), relief=tk.FLAT, cursor="hand2",
                  command=network_search_pet).pack(pady=3)

        # 备注
        note_frame = ttk.Frame(dialog)
        note_frame.pack(fill=tk.X, padx=10, pady=5)
        ttk.Label(note_frame, text="备注：", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        note_var = tk.StringVar(value=member_data.get("note", ""))
        ttk.Entry(note_frame, textvariable=note_var, font=("Microsoft YaHei", 9),
                  width=45).pack(side=tk.LEFT, padx=5)

        def do_save():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("提示", "请输入精灵名称")
                return

            pet = get_pet(name)
            if pet:
                m = {
                    "name": pet["name"],
                    "no": pet.get("no"),
                    "form": pet.get("form"),
                    "region_form": pet.get("region_form"),
                    "attributes": pet.get("attributes", []),
                    "stats": pet.get("stats", {}),
                    "ability": pet.get("ability", {}),
                    "nature": nature_var.get().split(" (")[0],
                    "note": note_var.get().strip(),
                    "bloodline": bloodline_var.get(),
                    "boosts": [bv.get() for bv in boost_vars],
                    "skills": [],
                }

                # 解析技能选择
                pet_skills = pet.get("skills", [])
                bloodline_skills = pet.get("bloodline_skills", [])
                quest_stones = pet.get("quest_stones", [])
                learnable_stones = pet.get("learnable_stones", [])
                for sv in skill_vars:
                    selected = sv.get().strip()
                    if selected:
                        # 从格式化字符串中提取技能名（去掉[...]及前缀）
                        raw_name = selected.split(" [")[0].strip()
                        skill_name = raw_name
                        for prefix in ("[血脉] ", "[技能石] ", "[可学] "):
                            if raw_name.startswith(prefix):
                                skill_name = raw_name[len(prefix):]
                                break
                        # 从三个来源中查找
                        found = False
                        for ps in pet_skills:
                            if ps.get("name") == skill_name:
                                m["skills"].append(ps)
                                found = True
                                break
                        if not found:
                            for ps in bloodline_skills:
                                if isinstance(ps, dict) and ps.get("name") == skill_name:
                                    m["skills"].append(ps)
                                    found = True
                                    break
                                elif isinstance(ps, str) and ps == skill_name:
                                    m["skills"].append({"name": ps, "attribute": "?", "category": "?", "power": 0, "cost": 0})
                                    found = True
                                    break
                        if not found:
                            for ps in quest_stones:
                                if isinstance(ps, dict) and ps.get("name") == skill_name:
                                    m["skills"].append(ps)
                                    found = True
                                    break
                                elif isinstance(ps, str) and ps == skill_name:
                                    m["skills"].append({"name": ps, "attribute": "?", "category": "?", "power": 0, "cost": 0})
                                    found = True
                                    break
                        if not found:
                            for ps in learnable_stones:
                                if isinstance(ps, dict) and ps.get("name") == skill_name:
                                    m["skills"].append(ps)
                                    found = True
                                    break
                                elif isinstance(ps, str) and ps == skill_name:
                                    m["skills"].append({"name": ps, "attribute": "?", "category": "?", "power": 0, "cost": 0})
                                    found = True
                                    break
                        if not found:
                            # 可能是全局技能名
                            gs = get_skill(skill_name)
                            if gs:
                                m["skills"].append({
                                    "name": skill_name,
                                    "attribute": gs.get("属性", "?"),
                                    "category": gs.get("类型", "?"),
                                    "power": int(gs.get("威力", 0)),
                                    "cost": int(gs.get("耗能", 0)),
                                })
            else:
                m = {
                    "name": name,
                    "attributes": [],
                    "stats": {},
                    "ability": {},
                    "nature": nature_var.get().split(" (")[0],
                    "note": note_var.get().strip(),
                    "bloodline": bloodline_var.get(),
                    "boosts": [bv.get() for bv in boost_vars],
                    "skills": [],
                }

            if edit_mode:
                self.manager.remove_member(self.current_team_idx, self.current_member_idx)
                self.manager.add_member(self.current_team_idx, m)
            else:
                self.manager.add_member(self.current_team_idx, m)

            self._refresh_member_list()
            self._update_team_code_display()
            dialog.destroy()

        tk.Button(dialog, text="保存", font=("Microsoft YaHei", 11, "bold"),
                  bg="#27AE60", fg="white", relief=tk.FLAT, cursor="hand2",
                  command=do_save).pack(pady=10)

        # 如果是编辑模式，预填充技能列表
        if edit_mode:
            refresh_skill_list()
            # 回填技能选中值：将纯技能名匹配为格式化字符串
            if existing_skills:
                for i, cb in enumerate(skill_cbs):
                    if i < len(existing_skills):
                        sk_name = existing_skills[i].get("name", "")
                        if sk_name and cb["values"]:
                            for val in cb["values"]:
                                if val.split(" [")[0].strip() == sk_name:
                                    skill_vars[i].set(val)
                                    break

    def _pet_search_dialog(self, target_var, parent_dialog):
        """精灵搜索对话框（支持形态区分）"""
        dialog = tk.Toplevel(self)
        dialog.title("搜索精灵")
        dialog.geometry("550x400")
        dialog.transient(parent_dialog)

        search_frame = ttk.Frame(dialog)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(search_frame, text="关键词：", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)
        kw_var = tk.StringVar()
        kw_entry = ttk.Entry(search_frame, textvariable=kw_var, font=("Microsoft YaHei", 10), width=30)
        kw_entry.pack(side=tk.LEFT, padx=5)

        result_listbox = tk.Listbox(dialog, font=("Microsoft YaHei", 10), width=70, height=15)
        result_listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 构建显示列表：同名多形态时显示形态区分
        all_pets = get_all_pets()
        display_map = {}  # display_str → (name, form)
        for p in all_pets:
            name = p.get("name", "")
            form = p.get("form") or ""
            region = p.get("region_form") or ""
            if not name:
                continue
            if region:
                display_str = f"{name} [{form}] [{region}]"
            elif form:
                display_str = f"{name} [{form}]"
            else:
                display_str = name
            # 仅保留第一个出现的（或覆盖）
            if display_str not in display_map:
                display_map[display_str] = (name, form)
        sorted_displays = sorted(display_map.keys())

        for d in sorted_displays:
            result_listbox.insert(tk.END, d)

        def do_search(*args):
            kw = kw_var.get().strip().lower()
            result_listbox.delete(0, tk.END)
            matches = [d for d in sorted_displays if kw in d.lower()] if kw else sorted_displays
            for n in matches[:100]:
                result_listbox.insert(tk.END, n)

        kw_var.trace_add("write", do_search)
        kw_entry.focus()

        def do_select():
            sel = result_listbox.curselection()
            if sel:
                display_str = result_listbox.get(sel[0])
                name, form = display_map.get(display_str, (display_str, None))
                target_var.set(name)
                # 存储选中的形态信息
                target_var._selected_form = form
                dialog.destroy()

        tk.Button(search_frame, text="搜索", bg="#4A90D9", fg="white",
                  font=("Microsoft YaHei", 9), relief=tk.FLAT,
                  command=do_search).pack(side=tk.LEFT, padx=5)

        tk.Button(dialog, text="选择", bg="#27AE60", fg="white",
                  font=("Microsoft YaHei", 10, "bold"), relief=tk.FLAT,
                  command=do_select).pack(pady=5)

        result_listbox.bind("<Double-Button-1>", lambda e: do_select())

    # ── 弱点分析 ─────────────────────────────────────────────────────
    def _analyze_weakness(self):
        if self.current_team_idx < 0:
            messagebox.showwarning("提示", "请先选择一个配队")
            return
        team = self.manager.get_team(self.current_team_idx)
        members = team.get("members", [])
        if not members:
            messagebox.showwarning("提示", "配队为空")
            return

        # 收集所有精灵属性
        all_types = []
        for m in members:
            attrs = m.get("attributes", [])
            if attrs:
                all_types.append(attrs)

        # 统计弱点
        weakness_count = {}
        for atk_type in ALL_TYPES:
            count = 0
            for defend_types in all_types:
                eff = get_effectiveness(atk_type, defend_types)
                if eff >= 2:
                    count += 1
            if count > 0:
                weakness_count[atk_type] = count

        dialog = tk.Toplevel(self)
        dialog.title(f"配队弱点分析 - {team.get('name','')}")
        dialog.geometry("500x400")
        dialog.transient(self)

        text = tk.Text(dialog, font=("Microsoft YaHei", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text.insert(tk.END, f"配队：{team.get('name','')}\n")
        text.insert(tk.END, f"精灵数：{len(members)}\n")
        text.insert(tk.END, "─" * 50 + "\n\n")

        text.insert(tk.END, "属性弱点统计（数字=被多少只精灵克制）：\n\n")
        sorted_weak = sorted(weakness_count.items(), key=lambda x: -x[1])
        for t, count in sorted_weak:
            bar = "█" * count
            text.insert(tk.END, f"  {t:4s} : {bar} ({count}只)\n")

        total = len(members)
        gaps = [t for t, c in sorted_weak if c >= total // 2]
        if gaps:
            text.insert(tk.END, f"\n⚠ 严重弱点：{'、'.join(gaps)} 克制半数以上精灵，建议调整\n")

        text.configure(state=tk.DISABLED)

    def _select_magic(self):
        """选择配队魔法"""
        if self.current_team_idx < 0:
            messagebox.showwarning("提示", "请先选择一个配队")
            return

        current_magic = self.manager.get_team_magic(self.current_team_idx)
        magics = ["进化之力", "愿力冲击"]

        dialog = tk.Toplevel(self)
        dialog.title("选择魔法")
        dialog.geometry("250x160")
        dialog.resizable(False, False)
        dialog.transient(self)

        ttk.Label(dialog, text="请选择配队魔法：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(15, 10))

        selected_var = tk.StringVar(value=current_magic)

        for m in magics:
            ttk.Radiobutton(
                dialog, text=m, variable=selected_var, value=m,
            ).pack(anchor=tk.W, padx=30, pady=3)

        def do_select():
            magic = selected_var.get()
            self.manager.set_team_magic(self.current_team_idx, magic)
            self._refresh_team_list()
            self.magic_label.configure(text=f"魔法：{magic}" if magic else "魔法：未选择")
            dialog.destroy()

        tk.Button(dialog, text="确定", font=("Microsoft YaHei", 10),
                  bg="#27AE60", fg="white", relief=tk.FLAT, cursor="hand2",
                  command=do_select).pack(pady=10)

    def _import_team_code(self):
        """导入阵容码（自动识别 ROCOM 码 或 游戏内明文格式）"""
        dialog = tk.Toplevel(self)
        dialog.title("导入阵容码")
        dialog.geometry("580x550")
        dialog.resizable(False, False)
        dialog.transient(self)

        ttk.Label(dialog, text="粘贴阵容码（支持 ROCOM 码 / 游戏内明文格式）：",
                  font=("Microsoft YaHei", 10)).pack(padx=10, pady=(15, 5))

        # 文本输入框
        code_text = tk.Text(dialog, font=("Microsoft YaHei", 10), width=60, height=6)
        code_text.pack(padx=10, pady=5)
        code_text.focus()

        # 预览区域
        preview_frame = ttk.LabelFrame(dialog, text="解析预览", padding=5)
        preview_var = tk.StringVar(value="")
        preview_label = ttk.Label(
            preview_frame, textvariable=preview_var,
            font=("Microsoft YaHei", 9), justify=tk.LEFT, anchor=tk.W,
            wraplength=540
        )
        preview_label.pack(anchor=tk.W, fill=tk.X)
        preview_frame.pack(padx=10, pady=(5, 0), fill=tk.X)

        def do_parse():
            code = code_text.get("1.0", tk.END).strip()
            if not code:
                preview_var.set("(请输入阵容码)")
                dialog._parsed = None
                dialog._is_rocom = False
                return

            # ── ROCOM 码检测 ──
            if code.startswith("ROCOM:"):
                try:
                    import base64
                    b64 = code[6:]
                    json_str = base64.b64decode(b64).decode("utf-8")
                    compact = json.loads(json_str)
                    lines = [f"队伍名: {compact.get('name', '导入配队')}"]
                    members = compact.get("members", [])
                    lines.append(f"精灵: {len(members)} 只")
                    lines.append("")
                    for cm in members:
                        skills_str = '、'.join(cm.get('sk', [])) if cm.get('sk') else '(无技能)'
                        lines.append(f"  {cm.get('n', '?')}  |  {cm.get('nt', '实干')}")
                        lines.append(f"    血脉: {cm.get('bl', '无')}  |  技能: {skills_str}")
                    preview_var.set('\n'.join(lines))
                    dialog._parsed = compact
                    dialog._is_rocom = True
                except Exception as e:
                    preview_var.set(f"(ROCOM码解析失败: {e})")
                    dialog._parsed = None
                    dialog._is_rocom = False
                return

            # ── 游戏内明文格式 ──
            dialog._is_rocom = False
            parsed = _parse_game_team_code(code)
            if parsed:
                lines = [f"队伍名: {parsed['name']}"]
                if parsed['magic']:
                    lines.append(f"魔法: {parsed['magic']}")
                lines.append(f"精灵: {len(parsed['pets'])} 只")
                lines.append("")
                for p in parsed['pets']:
                    skills_str = '、'.join(p['skills']) if p['skills'] else '(无技能)'
                    lines.append(f"  {p['name']}  |  {p['bloodline']}")
                    lines.append(f"    技能: {skills_str}")
                preview_var.set('\n'.join(lines))
                dialog._parsed = parsed
            else:
                preview_var.set("(无法解析阵容码，请检查格式)")
                dialog._parsed = None

        def do_import():
            parsed = getattr(dialog, '_parsed', None)
            is_rocom = getattr(dialog, '_is_rocom', False)
            if not parsed:
                messagebox.showwarning("提示", "请先点击「解析预览」确认阵容码正确")
                return

            if is_rocom:
                # ROCOM 码：直接使用 manager.import_team_from_code
                code = code_text.get("1.0", tk.END).strip()
                team = self.manager.import_team_from_code(code)
                if team:
                    self._refresh_team_list()
                    new_idx = len(self.manager.teams) - 1
                    self.current_team_idx = new_idx
                    self.team_listbox.selection_clear(0, tk.END)
                    self.team_listbox.selection_set(new_idx)
                    self.team_listbox.see(new_idx)
                    self._refresh_member_list()
                    self._update_team_code_display()
                    self._update_game_code_display()
                    magic = team.get("magic", "")
                    self.magic_label.configure(text=f"魔法：{magic}" if magic else "魔法：未选择")
                    messagebox.showinfo("导入成功", f"已创建配队「{team.get('name', '')}」")
                else:
                    messagebox.showerror("导入失败", "ROCOM码解析失败")
            else:
                # 游戏内明文格式
                code = code_text.get("1.0", tk.END).strip()
                team = self.manager.create_team_from_game_code(parsed)
                if team:
                    team["game_code"] = code
                    self.manager._save()
                    self._refresh_team_list()
                    new_idx = len(self.manager.teams) - 1
                    self.current_team_idx = new_idx
                    self.team_listbox.selection_clear(0, tk.END)
                    self.team_listbox.selection_set(new_idx)
                    self.team_listbox.see(new_idx)
                    self._refresh_member_list()
                    self._update_team_code_display()
                    self._update_game_code_display()
                    magic = team.get("magic", "")
                    self.magic_label.configure(text=f"魔法：{magic}" if magic else "魔法：未选择")
                    messagebox.showinfo("导入成功", f"已创建配队「{team.get('name', '')}」")
                else:
                    messagebox.showerror("导入失败", "创建配队失败")
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="解析预览", font=("Microsoft YaHei", 10),
                  bg="#4A90D9", fg="white", relief=tk.FLAT, cursor="hand2",
                  command=do_parse).pack(side=tk.LEFT, padx=5)

        tk.Button(btn_frame, text="确认导入", font=("Microsoft YaHei", 10),
                  bg="#27AE60", fg="white", relief=tk.FLAT, cursor="hand2",
                  command=do_import).pack(side=tk.LEFT, padx=5)

    def _copy_team_code(self):
        """复制阵容码到剪贴板"""
        code = self.team_code_var.get()
        if code:
            self.clipboard_clear()
            self.clipboard_append(code)
            messagebox.showinfo("已复制", "阵容码已复制到剪贴板")

    def _update_team_code_display(self):
        """更新阵容码显示"""
        if self.current_team_idx >= 0:
            code = self.manager.generate_team_code(self.current_team_idx)
            self.team_code_var.set(code)
        else:
            self.team_code_var.set("")

    def _update_game_code_display(self):
        """更新游戏内配队码显示"""
        if self.current_team_idx >= 0:
            team = self.manager.get_team(self.current_team_idx)
            self.game_code_var.set(team.get("game_code", "") if team else "")
        else:
            self.game_code_var.set("")

    def _save_game_code(self):
        """保存游戏内配队码到当前配队"""
        if self.current_team_idx < 0:
            messagebox.showwarning("提示", "请先选择或创建一个配队")
            return
        team = self.manager.get_team(self.current_team_idx)
        if team:
            team["game_code"] = self.game_code_var.get()
            self.manager._save()
            messagebox.showinfo("已保存", "游戏内配队码已保存")

    # ── 雷达图绘制 ─────────────────────────────────────────────────
    # === Wiki配队功能方法 ===

    def _show_fetch_options(self, title, msg, max_count):
        """显示获取选项弹窗：取消 / 继续(全量) / 我只需要N个
        返回: (action, count)  action: 'cancel'/'all'/'number'
        """
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.geometry("420x250")
        dlg.resizable(False, False)
        dlg.configure(bg="#F5F6FA")
        dlg.transient(self)
        dlg.grab_set()
        # 居中
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - 420) // 2
        y = self.winfo_rooty() + (self.winfo_height() - 250) // 2
        dlg.geometry(f"+{x}+{y}")
        result = {"action": "cancel", "count": 0}

        tk.Label(dlg, text=msg, font=("Microsoft YaHei", 10),
                 bg="#F5F6FA", fg="#2C3E50", justify=tk.LEFT, wraplength=380
                 ).pack(pady=(15, 10), padx=20, anchor=tk.W)

        # 数量输入行
        count_frame = tk.Frame(dlg, bg="#F5F6FA")
        count_frame.pack(pady=(0, 10))
        tk.Label(count_frame, text="获取数量：", font=("Microsoft YaHei", 9),
                 bg="#F5F6FA").pack(side=tk.LEFT)
        count_var = tk.StringVar(value="10")
        count_entry = tk.Entry(count_frame, textvariable=count_var,
                               font=("Microsoft YaHei", 10), width=8, justify=tk.CENTER)
        count_entry.pack(side=tk.LEFT, padx=5)
        tk.Label(count_frame, text=f"(最多{max_count})", font=("Microsoft YaHei", 8),
                 bg="#F5F6FA", fg="#999").pack(side=tk.LEFT)

        btn_frame = tk.Frame(dlg, bg="#F5F6FA")
        btn_frame.pack(pady=(5, 15))

        def do_cancel():
            result["action"] = "cancel"
            dlg.destroy()

        def do_all():
            result["action"] = "all"
            dlg.destroy()

        def do_number():
            try:
                n = int(count_var.get().strip())
                if n <= 0:
                    messagebox.showwarning("提示", "请输入大于0的数字", parent=dlg)
                    return
                result["action"] = "number"
                result["count"] = n
                dlg.destroy()
            except ValueError:
                messagebox.showwarning("提示", "请输入有效数字", parent=dlg)

        btn_style = {"font": ("Microsoft YaHei", 9), "relief": tk.FLAT,
                     "cursor": "hand2", "borderwidth": 0, "padx": 12, "pady": 5}

        tk.Button(btn_frame, text="取消", bg="#95A5A6", fg="white",
                  activebackground="#7F8C8D", command=do_cancel,
                  **btn_style).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="我只需要~个", bg="#3498DB", fg="white",
                  activebackground="#2980B9", command=do_number,
                  **btn_style).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="继续(全量)", bg="#27AE60", fg="white",
                  activebackground="#219A52", command=do_all,
                  **btn_style).pack(side=tk.LEFT, padx=4)

        dlg.wait_window()
        return result["action"], result["count"]

    def _repair_wiki_team_skills(self):
        INDIVIDUAL_MAP = {
            "生命": "HP", "物攻": "物攻", "魔攻": "魔攻",
            "物防": "物防", "魔防": "魔防", "速度": "速度",
        }

        from core.type_data import get_skill
        from core.wiki_team_fetcher import load_teams as load_wiki_teams
        skill_fixed = 0
        meta_fixed = 0

        # 读取原始wiki数据用于修复元数据
        wiki_data = {}
        try:
            raw_teams = load_wiki_teams()
            for wt in raw_teams:
                wiki_data[wt.get("wiki_id", "")] = wt
        except Exception:
            pass

        for t in self.manager.teams:
            if t.get("source") != "wiki":
                continue

            # 修复技能数据
            for m in t.get("members", []):
                for sk in m.get("skills", []):
                    if sk.get("attribute") == "?" and sk.get("power") == 0:
                        gs = get_skill(sk.get("name", ""))
                        if gs:
                            sk["attribute"] = gs.get("attribute", "?")
                            sk["category"] = gs.get("category", "?")
                            power_str = str(gs.get("power", "0"))
                            cost_str = str(gs.get("cost", "0"))
                            sk["power"] = int(power_str) if power_str.replace("-", "").isdigit() else 0
                            sk["cost"] = int(cost_str) if cost_str.replace("-", "").isdigit() else 0
                            skill_fixed += 1

                # 修复boosts（个体值）
                if not m.get("boosts") or all(b == "无" for b in m.get("boosts", [])):
                    individual = ""
                    wiki_id = t.get("wiki_id", "")
                    if wiki_id and wiki_id in wiki_data:
                        wt = wiki_data[wiki_id]
                        for wm in wt.get("members", []):
                            if wm.get("name") == m.get("name"):
                                individual = wm.get("individual", "")
                                break
                    if individual:
                        boosts = []
                        for part in individual.replace("，", ",").split(","):
                            part = part.strip()
                            if part in INDIVIDUAL_MAP:
                                boosts.append(INDIVIDUAL_MAP[part])
                            elif part:
                                boosts.append(part)
                        while len(boosts) < 3:
                            boosts.append("无")
                        m["boosts"] = boosts[:3]
                        meta_fixed += 1

            # 修复团队元数据
            wiki_id = t.get("wiki_id", "")
            if wiki_id and wiki_id in wiki_data:
                wt = wiki_data[wiki_id]
                if not t.get("wiki_author") and wt.get("author"):
                    t["wiki_author"] = wt["author"]
                    meta_fixed += 1
                if not t.get("wiki_date") and wt.get("date"):
                    t["wiki_date"] = wt["date"]
                    meta_fixed += 1
                if not t.get("wiki_type") and wt.get("type"):
                    t["wiki_type"] = wt["type"]
                    meta_fixed += 1
                if not t.get("wiki_desc") and wt.get("description"):
                    t["wiki_desc"] = wt["description"]
                    meta_fixed += 1

        if skill_fixed > 0 or meta_fixed > 0:
            self.manager._save()

    def _wiki_update_progress(self, msg):
        """更新Wiki进度显示"""
        self._wiki_progress_var.set(msg)
        self.update_idletasks()

    def _wiki_show_result(self, imported_count, was_interrupted, error_msg, extra_info=""):
        """显示Wiki获取结果弹窗"""
        if was_interrupted and error_msg:
            self._refresh_team_list()
            messagebox.showwarning("获取中断 - 反爬协议触发",
                f"已导入 {imported_count} 个配队到本地。\n\n但获取被中断：\n{error_msg}\n\n已下载的配队已保存，重启软件或稍后重试即可。")
        else:
            self._refresh_team_list()
            messagebox.showinfo("完成", f"成功导入 {imported_count} 个Wiki配队！{extra_info}")


    def _auto_import_wiki(self):
        """启动时自动导入Wiki JSON中已有的配队"""
        try:
            from core.wiki_team_fetcher import import_wiki_teams_to_manager
            imported = import_wiki_teams_to_manager(self.manager)
            if imported > 0:
                self._refresh_team_list()
        except Exception:
            pass
    def _wiki_fetch_all(self):
        """网络全量获取所有Wiki配队"""
        try:
            from core.wiki_team_fetcher import get_total_team_count, get_loaded_count
            total = get_total_team_count()
            existing = get_loaded_count()
        except Exception:
            total = 200

        ask_msg = f"Wiki共有约 {total} 个配队。\n全量获取预计需要 {total * 3 // 60} 分钟左右。\n\n"
        if existing > 0:
            ask_msg += f"检测到已有 {existing} 条已保存配队。\n"

        # 三选弹窗
        action, count = self._show_fetch_options("网络全量获取", ask_msg, total)
        if action == "cancel":
            return

        if action == "number":
            if count > total:
                messagebox.showwarning("超出范围", f"最多只有 {total} 个配队，已自动调整为 {total}")
                count = total
            if count <= 0:
                return

        def run():
            try:
                from core.wiki_team_fetcher import fetch_all_teams, fetch_n_teams, import_wiki_teams_to_manager, delete_all_wiki_teams
                self.after(0, self._wiki_update_progress, "正在获取Wiki配队列表...")
                # 清除旧数据（全新获取）
                # delete_all_wiki_teams() disabled - no auto-delete
                # 也清除manager中的wiki配队
                # 不删除已有配队，import_wiki_teams_to_manager 会自动去重
                # self.manager._save()

                if action == "number":
                    teams, interrupted, err = fetch_n_teams(count,
                        progress_callback=lambda c, t, m: self.after(0, self._wiki_update_progress, m),
                        )
                else:
                    teams, interrupted, err = fetch_all_teams(
                        progress_callback=lambda c, t, m: self.after(0, self._wiki_update_progress, m),
                        )

                imported = import_wiki_teams_to_manager(self.manager)
                self.after(0, self._wiki_update_progress, "")
                self.after(0, lambda: self._wiki_show_result(imported, interrupted, err))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.after(0, self._wiki_update_progress, "")
                self.after(0, lambda: messagebox.showerror("失败", f"获取失败: {e}"))
        threading.Thread(target=run, daemon=True).start()

    def _wiki_random_team(self):
        """随机获取一个Wiki配队"""
        def run():
            try:
                from core.wiki_team_fetcher import fetch_random_team, import_wiki_teams_to_manager
                self.after(0, self._wiki_update_progress, "正在随机获取Wiki配队...")
                team, err = fetch_random_team()
                if team:
                    imported = import_wiki_teams_to_manager(self.manager)
                    self.after(0, self._wiki_update_progress, "")
                    self.after(0, self._refresh_team_list)
                    self.after(0, lambda: messagebox.showinfo("随机配队",
                        f"已获取配队：{team.get('title', '未知')}\n作者：{team.get('author', '未知')}\n类型：{team.get('type', '')}"))
                else:
                    self.after(0, self._wiki_update_progress, "")
                    self.after(0, lambda: messagebox.showerror("失败", f"获取随机配队失败\n{err}"))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.after(0, self._wiki_update_progress, "")
                self.after(0, lambda: messagebox.showerror("失败", f"获取失败: {e}"))
        threading.Thread(target=run, daemon=True).start()

    def _wiki_search_by_pet(self):
        """按精灵名称搜索Wiki配队"""
        pet_name = simpledialog.askstring("按精灵选配队", "请输入精灵名称（支持模糊匹配）：", parent=self)
        if not pet_name or not pet_name.strip():
            return
        pet_name = pet_name.strip()

        # 询问获取数量
        action, count = self._show_fetch_options(
            "按精灵选配队",
            f"搜索含 '{pet_name}' 的配队，\n逐个比对预计需要较长时间。\n\n要获取多少个匹配的配队？",
            999  # 不限制
        )
        if action == "cancel":
            return

        def run():
            try:
                from core.wiki_team_fetcher import search_teams_by_pet, search_teams_by_pet_n, import_wiki_teams_to_manager
                self.after(0, self._wiki_update_progress, f"正在搜索含 '{pet_name}' 的配队...")

                if action == "number":
                    matched, interrupted, err = search_teams_by_pet_n(
                        pet_name, count,
                        progress_callback=lambda c, t, m: self.after(0, self._wiki_update_progress, m),
                                            )
                else:
                    matched, interrupted, err = search_teams_by_pet(
                        pet_name,
                        progress_callback=lambda c, t, m: self.after(0, self._wiki_update_progress, m),
                                            )

                imported = import_wiki_teams_to_manager(self.manager)
                self.after(0, self._wiki_update_progress, "")
                self.after(0, self._refresh_team_list)
                if interrupted:
                    self.after(0, lambda: messagebox.showwarning("搜索中断",
                        f"找到 {len(matched)} 个含 '{pet_name}' 的配队，\n导入 {imported} 个。\n\n但被反爬中断：{err}"))
                else:
                    self.after(0, lambda: messagebox.showinfo("搜索结果",
                        f"找到 {len(matched)} 个包含 '{pet_name}' 的配队，\n导入 {imported} 个！"))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.after(0, self._wiki_update_progress, "")
                self.after(0, lambda: messagebox.showerror("失败", f"搜索失败: {e}"))
        threading.Thread(target=run, daemon=True).start()

    def _wiki_delete_all(self):
        """删除所有网络获取的配队"""
        if not messagebox.askyesno("确认", "确定删除所有网络获取的配队吗？"):
            return
        self.manager.teams = [t for t in self.manager.teams if t.get("source") != "wiki"]
        self.manager._save()
        try:
            from core.wiki_team_fetcher import save_teams
            save_teams([])
        except Exception:
            pass
        self._refresh_team_list()
        self._clear_detail()
        messagebox.showinfo("完成", "已删除所有网络配队")


    def _draw_radar_chart(self, stats):
        """在Canvas上绘制种族值六维雷达图"""
        canvas = self.radar_canvas
        canvas.delete("all")

        # 六个维度：绕圆逆时针排列（顶→左上→左下→底→右下→右上）
        dimensions = [
            ("生命", "hp"),      # 90° 顶部
            ("物攻", "atk"),     # 150° 左上
            ("物防", "def"),     # 210° 左下
            ("速度", "spd"),     # 270° 底部
            ("魔防", "sp_def"),  # 330° 右下
            ("魔攻", "sp_atk"),  # 30° 右上
        ]
        n = len(dimensions)
        max_val = 200  # 归一化最大值

        w = 250
        h = 250
        cx = w // 2
        cy = h // 2
        radius = 85  # 外圈半径

        import math

        # 自定义角度：绕圆逆时针（从顶部90°开始）
        angles_deg = [90, 150, 210, 270, 330, 30]

        def hex_point_from_angle(angle_deg, r):
            angle = math.radians(angle_deg - 90)
            x = cx + r * math.cos(angle)
            y = cy + r * math.sin(angle)
            return x, y

        # 绘制背景网格（3层：50% / 75% / 100%）
        for level in [0.5, 0.75, 1.0]:
            r = radius * level
            points = []
            for i in range(n):
                points.extend(hex_point_from_angle(angles_deg[i], r))
            canvas.create_polygon(points, outline="#CCCCCC", fill="", width=1)

        # 绘制轴线
        for i in range(n):
            x, y = hex_point_from_angle(angles_deg[i], radius)
            canvas.create_line(cx, cy, x, y, fill="#DDDDDD", width=1)

        # 绘制实际种族值多边形（蓝色半透明）
        if stats:
            data_points = []
            for i, (label, key) in enumerate(dimensions):
                val = stats.get(key, 0)
                r = min(radius * (val / max_val), radius)
                x, y = hex_point_from_angle(angles_deg[i], r)
                data_points.extend([x, y])
            if len(data_points) >= 6:
                canvas.create_polygon(data_points, fill="#4A90D9", outline="#2C5F8A", width=2, stipple="")

        # 顶点标注（手动指定偏移）
        offsets = [
            (0, -5),   # HP 顶部
            (-3, 0),   # 物攻 左上
            (-3, 0),   # 物防 左下
            (0, 5),    # 速度 底部
            (3, 0),    # 魔防 右下
            (3, 0),    # 魔攻 右上
        ]
        for i, (label, key) in enumerate(dimensions):
            val = stats.get(key, 0) if stats else 0
            x, y = hex_point_from_angle(angles_deg[i], radius + 15)
            x += offsets[i][0]
            y += offsets[i][1]
            canvas.create_text(
                x, y,
                text=f"{label}\n{val}",
                font=("Microsoft YaHei", 7),
                fill="#333333",
                justify=tk.CENTER,
            )

        # 中心标签
        total = stats.get("total", "?") if stats else "?"
        canvas.create_text(
            cx, cy,
            text=f"{total}",
            font=("Microsoft YaHei", 9, "bold"),
            fill="#2C3E50",
        )