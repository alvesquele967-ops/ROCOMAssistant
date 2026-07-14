""" 
竹雨ROCOM小助手 - 设置面板
提供精灵图鉴数据刷新功能（通过 BiliWiki API）
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from ui.theme import (
    PRIMARY, SUCCESS, SUCCESS_HOVER,
    DANGER, DANGER_HOVER,
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL,
    PAD_X, BG_CARD, TEXT_SECONDARY,
)


class SettingsPanel(ttk.Frame):
    """设置面板"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._scraping = False
        self._buttons = []
        self._build_ui()
        douyin_label = tk.Label(
            self, text="抖音：takesitaame",
            font=("Microsoft YaHei", 8), fg="#999999", bg="#EAECEE",
        )
        douyin_label.pack(side=tk.BOTTOM, pady=(4, 2))
        self._refresh_status()

    def _add_button(self, parent, text, bg, hover_bg, command, **pack_kw):
        btn = tk.Button(
            parent, text=text, font=FONT_BODY,
            bg=bg, fg="white", activebackground=hover_bg,
            relief=tk.FLAT, cursor="hand2", borderwidth=0, padx=16, pady=6,
            command=command,
        )
        btn.pack(**pack_kw)
        self._buttons.append(btn)
        return btn

    def _build_ui(self):
        container = ttk.Frame(self, padding=20)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="设置", font=FONT_TITLE).pack(anchor=tk.W, pady=(0, 15))

        cache_frame = ttk.LabelFrame(container, text="精灵图鉴数据缓存", padding=15)
        cache_frame.pack(fill=tk.X, pady=(0, 15))

        self.status_var = tk.StringVar(value="正在检测...")
        ttk.Label(cache_frame, textvariable=self.status_var, font=FONT_BODY).pack(anchor=tk.W, pady=(0, 5))

        self.count_var = tk.StringVar(value="")
        ttk.Label(cache_frame, textvariable=self.count_var, font=FONT_BODY).pack(anchor=tk.W, pady=(0, 5))

        self.img_status_var = tk.StringVar(value="")
        ttk.Label(cache_frame, textvariable=self.img_status_var, font=FONT_BODY).pack(anchor=tk.W, pady=(0, 10))

        btn_row = ttk.Frame(cache_frame)
        btn_row.pack(anchor=tk.W, fill=tk.X, pady=(0, 8))
        self._add_button(btn_row, "刷新精灵数据", SUCCESS, SUCCESS_HOVER,
                         lambda: self._start_task("pets"), side=tk.LEFT, padx=(0, 8))
        self._add_button(btn_row, "刷新技能数据", SUCCESS, SUCCESS_HOVER,
                         lambda: self._start_task("skills"), side=tk.LEFT, padx=(0, 8))
        self._add_button(btn_row, "下载图片", PRIMARY, "#4A6FEF",
                         lambda: self._start_task("images"), side=tk.LEFT, padx=(0, 8))
        self._add_button(btn_row, "删除缓存数据", DANGER, DANGER_HOVER,
                         self._delete_cache, side=tk.LEFT)

        btn_row2 = ttk.Frame(cache_frame)
        btn_row2.pack(anchor=tk.W, fill=tk.X, pady=(8, 8))
        self._add_button(btn_row2, "精灵图像更新", "#E67E22", "#D35400",
                         lambda: self._start_task("pet_image_update"), side=tk.LEFT, padx=(0, 8))
        self._add_button(btn_row2, "技能图像更新", "#E67E22", "#D35400",
                         lambda: self._start_task("skill_image_update"), side=tk.LEFT, padx=(0, 8))
        self._add_button(btn_row2, "宠物技能增量更新", "#E67E22", "#D35400",
                         lambda: self._start_task("pet_skill_update"), side=tk.LEFT)

        self.progress_var = tk.StringVar(value="")
        self.progress_label = ttk.Label(
            cache_frame, textvariable=self.progress_var, font=FONT_SMALL, foreground=TEXT_SECONDARY,
        )
        self.progress_label.pack(anchor=tk.W, pady=(5, 0))

        info_frame = ttk.LabelFrame(container, text="说明", padding=15)
        info_frame.pack(fill=tk.X)
        info_text = (
            "数据来源：BiliGame Wiki API（wiki.biligame.com/rocom）\n"
            "Category:精灵 + Category:技能 分类下的全部 Wiki 页面。\n\n"
            "• 刷新精灵数据：全量重新爬取所有精灵信息（含立绘图片）\n"
            "• 刷新技能数据：全量重新爬取所有技能信息\n"
            "• 精灵图像更新：基于已有数据补全缺失的精灵图片\n"
            "• 技能图像更新：基于已有数据补全缺失的技能图片\n"
            "• 宠物技能增量更新：增量比对 Wiki，仅爬取新增精灵和技能\n"
            "• 下载图片：基于已有数据补全缺失的精灵图片\n"
            "• 删除缓存数据：清除所有缓存数据和图片\n\n"
            "刷新后，配队管理和伤害计算将自动使用最新数据。"
        )
        ttk.Label(info_frame, text=info_text, font=FONT_SMALL, foreground=TEXT_SECONDARY,
                  justify=tk.LEFT).pack(anchor=tk.W)

    def _refresh_status(self):
        try:
            from core.scraper import _OUTPUT_PATH
            if _OUTPUT_PATH.exists():
                mtime = _OUTPUT_PATH.stat().st_mtime
                import datetime
                dt = datetime.datetime.fromtimestamp(mtime)
                self.status_var.set(f"数据状态：已缓存")
                self.count_var.set(f"上次更新：{dt.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                self.status_var.set("数据状态：未缓存")
                self.count_var.set("使用内置静态数据")
        except Exception:
            self.status_var.set("数据状态：检测失败")
            self.count_var.set("")

        try:
            from core.wiki_scraper import _PET_IMG_DIR, _SKILL_IMG_DIR
            pet_count = len(list(_PET_IMG_DIR.glob("*.*"))) if _PET_IMG_DIR.exists() else 0
            skill_count = len(list(_SKILL_IMG_DIR.glob("*.*"))) if _SKILL_IMG_DIR.exists() else 0
            self.img_status_var.set(f"图片状态：{pet_count} 张精灵图, {skill_count} 张技能图")
        except Exception:
            self.img_status_var.set("图片状态：检测失败")

    def _set_buttons_state(self, state):
        for btn in self._buttons:
            btn.config(state=state)

    def _start_task(self, task_type):
        if self._scraping:
            return

        labels = {
            "pets": ("刷新精灵数据", "将从 BiliGame Wiki 全量重新爬取\n所有精灵信息（含宠物立绘）。\n预计 15~30 分钟。\n\n确定继续？"),
            "skills": ("刷新技能数据", "将从 BiliGame Wiki 全量重新爬取\n所有技能信息。\n预计 5~15 分钟。\n\n确定继续？"),
            "images": ("下载图片", "将基于已有数据下载缺失的精灵图片，\n不重新爬取数据。\n预计 5~10 分钟。\n\n确定继续？"),
            "pet_image_update": ("精灵图像更新", "将基于已有数据下载缺失的精灵图片，\n不重新爬取精灵数据。\n预计 1~2 分钟。\n\n确定继续？"),
            "skill_image_update": ("技能图像更新", "将基于已有数据下载缺失的技能图片，\n不重新爬取技能数据。\n预计 1~2 分钟。\n\n确定继续？"),
            "pet_skill_update": ("宠物技能增量更新", "将比对 Wiki API 最新数据，仅爬取新增的\n精灵和技能（增量模式，不含图片）。\n预计 5~20 秒。\n\n确定继续？"),
        }
        title, msg = labels.get(task_type, (task_type, "确定继续？"))

        if not messagebox.askyesno(title, msg):
            return

        self._scraping = True
        self._set_buttons_state(tk.DISABLED)
        self.progress_var.set("正在连接 Wiki API...")
        self.update_idletasks()
        self._current_task = task_type

        thread = threading.Thread(target=self._run_task, args=(task_type,), daemon=True)
        thread.start()

    def _run_task(self, task_type):
        try:
            if task_type == "pets":
                from core.wiki_scraper import main_pets_only as func
                extra_kw = {"force": True}
            elif task_type == "skills":
                from core.wiki_scraper import main_skills_only as func
                extra_kw = {"force": True}
            elif task_type in ("images", "image_update"):
                from core.wiki_scraper import main_images_only as func
                extra_kw = {}
            elif task_type == "pet_image_update":
                from core.wiki_scraper import main_images_only as func
                extra_kw = {"mode": "pets"}
            elif task_type == "skill_image_update":
                from core.wiki_scraper import main_images_only as func
                extra_kw = {"mode": "skills"}
            elif task_type == "pet_skill_update":
                from core.wiki_scraper import main_pets_only, main_skills_only

                def on_progress(phase, message, current, total):
                    self.after(0, self._update_progress, message)

                ok1, msg1 = main_pets_only(progress_callback=on_progress, force=False)
                ok2, msg2 = main_skills_only(progress_callback=on_progress, force=False)
                combined = f"{msg1}\n{msg2}"
                self.after(0, self._task_done, ok1 and ok2, combined)
                return
            else:
                raise ValueError(f"未知任务类型: {task_type}")

            def on_progress(phase, message, current, total):
                self.after(0, self._update_progress, message)

            ok, msg = func(progress_callback=on_progress, **extra_kw)
            self.after(0, self._task_done, ok, msg)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.after(0, self._task_done, False, f"执行异常: {e}")

    def _delete_cache(self):
        if self._scraping:
            return
        if not messagebox.askyesno("删除缓存数据", "将删除所有缓存的精灵/技能数据和图片。\n程序将回退使用内置静态数据。\n\n确定删除？"):
            return
        self._scraping = True
        self._set_buttons_state(tk.DISABLED)
        self.progress_var.set("正在删除...")
        self.update_idletasks()
        try:
            from core.wiki_scraper import delete_cache
            ok, msg = delete_cache()
            self.after(0, self._delete_done, ok, msg)
        except Exception as e:
            self.after(0, self._delete_done, False, f"删除失败: {e}")

    def _delete_done(self, success, message):
        self._scraping = False
        self._set_buttons_state(tk.NORMAL)
        self._refresh_status()
        self.progress_var.set("")
        self.update_idletasks()
        try:
            from core import type_data
            type_data.reload()
        except Exception:
            pass
        if success:
            messagebox.showinfo("删除成功", message)
        else:
            messagebox.showerror("删除失败", message)

    def _update_progress(self, message):
        self.progress_var.set(message)
        self.update_idletasks()

    def _task_done(self, success, message):
        self._scraping = False
        self._set_buttons_state(tk.NORMAL)
        self._refresh_status()
        if success:
            try:
                from core import type_data
                type_data.reload()
            except Exception:
                pass
            self.progress_var.set("")
            self.update_idletasks()
            messagebox.showinfo("操作完成", message)
        else:
            self.progress_var.set(message)
            self.update_idletasks()
            messagebox.showerror("操作失败", message)

