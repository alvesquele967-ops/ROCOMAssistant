"""
竹雨ROCOM小助手 - 工具栏面板
快捷应用（本地.exe）+ exe直达文件夹 + 网址链接
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
from pathlib import Path
from ui.theme import (
    PRIMARY, PRIMARY_HOVER,
    FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_CAPTION,
    PAD_X, BG_CARD,
)


_CONFIG_PATH = Path(__file__).parent.parent / "resources" / "toolbar_config.json"
_EXE_FOLDER = Path(__file__).parent.parent / "exe直达"

_DEFAULT_URLS = [
    {
        "type": "url",
        "name": "洛克王国世界 Wiki",
        "url": "https://wiki.biligame.com/rocom",
        "note": "BWIKI百科",
    },
    {
        "type": "url",
        "name": "洛克王国世界官网",
        "url": "https://rocom.qq.com/main/",
        "note": "官方网站",
    },
]


class ToolbarPanel(ttk.Frame):
    """工具栏面板"""

    def __init__(self, parent, **kwargs):
        self.navigate_callback = kwargs.pop("navigate_callback", None)
        super().__init__(parent, **kwargs)
        self.config = self._load_config()
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

        self._app_raw = []
        self._exe_raw = []
        self._url_raw = []
        self._refresh_all()

    def _load_config(self):
        if _CONFIG_PATH.exists():
            try:
                with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"apps": [], "urls": list(_DEFAULT_URLS)}

    def _save_config(self):
        _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def _build_ui(self):
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=PAD_X, pady=5)

        ttk.Label(
            header, text="工具箱",
            font=FONT_HEADING,
        ).pack(side=tk.LEFT)

        ttk.Label(
            header, text="快捷应用 & exe直达 & 常用链接",
            font=FONT_SMALL, foreground="gray",
        ).pack(side=tk.LEFT, padx=10)

        # ── 区域一：快捷应用（手动添加）──
        app_frame = ttk.LabelFrame(self, text="快捷应用", padding=8)
        app_frame.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=5)

        app_btn_frame = ttk.Frame(app_frame)
        app_btn_frame.pack(fill=tk.X, pady=(0, 5))

        tk.Button(
            app_btn_frame, text="+ 添加应用",
            font=FONT_BODY,
            bg=PRIMARY, fg="white",
            activebackground=PRIMARY_HOVER,
            relief=tk.FLAT, cursor="hand2",
            borderwidth=0, padx=12, pady=3,
            command=self._add_app,
        ).pack(side=tk.LEFT, padx=2)

        self.app_search_var = tk.StringVar()
        app_search_entry = ttk.Entry(
            app_frame, textvariable=self.app_search_var,
            font=("Microsoft YaHei", 9), width=20,
        )
        app_search_entry.pack(fill=tk.X, pady=(0, 2))
        self._app_search_placeholder = True
        self.app_search_var.set("搜索应用名称...")
        app_search_entry.bind("<FocusIn>", lambda e: self._on_search_focus_in(self.app_search_var, "搜索应用名称..."))
        app_search_entry.bind("<FocusOut>", lambda e: self._on_search_focus_out(self.app_search_var, "搜索应用名称..."))

        self.app_listbox = tk.Listbox(
            app_frame,
            font=FONT_BODY,
            height=5,
            selectmode=tk.SINGLE,
            bg=BG_CARD,
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.app_listbox.pack(fill=tk.BOTH, expand=True, pady=3)
        self.app_listbox.bind("<Double-Button-1>", self._launch_app)
        self.app_listbox.bind("<Button-3>", self._app_context_menu)
        self.app_search_var.trace_add("write", lambda *a: self._filter_apps())

        # ── 区域二：exe直达（文件夹扫描）──
        exe_frame = ttk.LabelFrame(self, text="exe直达", padding=8)
        exe_frame.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=5)

        exe_btn_frame = ttk.Frame(exe_frame)
        exe_btn_frame.pack(fill=tk.X, pady=(0, 5))

        tk.Button(
            exe_btn_frame, text="打开文件夹",
            font=FONT_BODY,
            bg="#9B59B6", fg="white",
            activebackground="#8E44AD",
            relief=tk.FLAT, cursor="hand2",
            borderwidth=0, padx=12, pady=3,
            command=self._open_exe_folder,
        ).pack(side=tk.LEFT, padx=2)

        ttk.Label(
            exe_btn_frame,
            text=f"将 .exe/.lnk 放入此文件夹自动显示",
            font=FONT_CAPTION, foreground="gray",
        ).pack(side=tk.LEFT, padx=10)

        self.exe_search_var = tk.StringVar()
        exe_search_entry = ttk.Entry(
            exe_frame, textvariable=self.exe_search_var,
            font=("Microsoft YaHei", 9), width=20,
        )
        exe_search_entry.pack(fill=tk.X, pady=(0, 2))
        self._exe_search_placeholder = True
        self.exe_search_var.set("搜索文件名...")
        exe_search_entry.bind("<FocusIn>", lambda e: self._on_search_focus_in(self.exe_search_var, "搜索文件名..."))
        exe_search_entry.bind("<FocusOut>", lambda e: self._on_search_focus_out(self.exe_search_var, "搜索文件名..."))

        self.exe_listbox = tk.Listbox(
            exe_frame,
            font=FONT_BODY,
            height=5,
            selectmode=tk.SINGLE,
            bg=BG_CARD,
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.exe_listbox.pack(fill=tk.BOTH, expand=True, pady=3)
        self.exe_listbox.bind("<Double-Button-1>", self._launch_exe)
        self.exe_listbox.bind("<Button-3>", self._exe_context_menu)
        self.exe_search_var.trace_add("write", lambda *a: self._filter_exes())

        # ── 区域三：网址链接 ──
        url_frame = ttk.LabelFrame(self, text="网址链接", padding=8)
        url_frame.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=5)

        url_btn_frame = ttk.Frame(url_frame)
        url_btn_frame.pack(fill=tk.X, pady=(0, 5))

        tk.Button(
            url_btn_frame, text="+ 添加链接",
            font=FONT_BODY,
            bg="#27AE60", fg="white",
            activebackground="#219A52",
            relief=tk.FLAT, cursor="hand2",
            borderwidth=0, padx=12, pady=3,
            command=self._add_url,
        ).pack(side=tk.LEFT, padx=2)

        self.url_search_var = tk.StringVar()
        url_search_entry = ttk.Entry(
            url_frame, textvariable=self.url_search_var,
            font=("Microsoft YaHei", 9), width=20,
        )
        url_search_entry.pack(fill=tk.X, pady=(0, 2))
        self._url_search_placeholder = True
        self.url_search_var.set("搜索链接名称...")
        url_search_entry.bind("<FocusIn>", lambda e: self._on_search_focus_in(self.url_search_var, "搜索链接名称..."))
        url_search_entry.bind("<FocusOut>", lambda e: self._on_search_focus_out(self.url_search_var, "搜索链接名称..."))

        self.url_listbox = tk.Listbox(
            url_frame,
            font=FONT_BODY,
            height=5,
            selectmode=tk.SINGLE,
            bg=BG_CARD,
            relief=tk.FLAT,
            borderwidth=0,
        )
        self.url_listbox.pack(fill=tk.BOTH, expand=True, pady=3)
        self.url_listbox.bind("<Double-Button-1>", self._open_url)
        self.url_listbox.bind("<Button-3>", self._url_context_menu)
        self.url_search_var.trace_add("write", lambda *a: self._filter_urls())

    # ── 刷新列表 ──
    def _refresh_all(self):
        self._refresh_apps()
        self._refresh_exe_folder()
        self._refresh_urls()

    def _refresh_apps(self):
        self._app_raw = list(self.config.get("apps", []))
        self._filter_apps()

    def _refresh_exe_folder(self):
        self._exe_raw = self._get_exe_files()
        self._filter_exes()

    def _refresh_urls(self):
        self._url_raw = list(self.config.get("urls", []))
        self._filter_urls()

    def _filter_apps(self):
        query = self.app_search_var.get().strip()
        if query == "搜索应用名称...":
            query = ""
        self.app_listbox.delete(0, tk.END)
        for item in self._app_raw:
            name = item.get("name", "")
            note = item.get("note", "")
            if not query or query.lower() in name.lower() or query.lower() in note.lower():
                display = name
                if note:
                    display += f"  ({note})"
                self.app_listbox.insert(tk.END, display)

    def _filter_exes(self):
        query = self.exe_search_var.get().strip()
        if query == "搜索文件名...":
            query = ""
        self.exe_listbox.delete(0, tk.END)
        for f in self._exe_raw:
            name = f.name
            note = self._get_exe_note(str(f.resolve()))
            if not query or query.lower() in name.lower() or query.lower() in note.lower():
                display = name
                if note:
                    display += f"  ({note})"
                self.exe_listbox.insert(tk.END, display)

    def _filter_urls(self):
        query = self.url_search_var.get().strip()
        if query == "搜索链接名称...":
            query = ""
        self.url_listbox.delete(0, tk.END)
        for item in self._url_raw:
            name = item.get("name", "")
            note = item.get("note", "")
            if not query or query.lower() in name.lower() or query.lower() in note.lower():
                display = name
                if note:
                    display += f"  ({note})"
                self.url_listbox.insert(tk.END, display)

    def _on_search_focus_in(self, var, placeholder):
        if var.get() == placeholder:
            var.set("")

    def _on_search_focus_out(self, var, placeholder):
        if not var.get().strip():
            var.set(placeholder)

    def _find_app_index_by_display(self, display):
        for i, item in enumerate(self._app_raw):
            name = item.get("name", "")
            note = item.get("note", "")
            d = name
            if note:
                d += f"  ({note})"
            if d == display:
                return i
        return -1

    def _find_exe_index_by_display(self, display):
        for i, f in enumerate(self._exe_raw):
            note = self._get_exe_note(str(f.resolve()))
            d = f.name
            if note:
                d += f"  ({note})"
            if d == display:
                return i
        return -1

    def _find_url_index_by_display(self, display):
        for i, item in enumerate(self._url_raw):
            name = item.get("name", "")
            note = item.get("note", "")
            d = name
            if note:
                d += f"  ({note})"
            if d == display:
                return i
        return -1

    # ════════════════════════════════════════════════════════════════
    # ── 快捷应用（手动添加）──
    # ════════════════════════════════════════════════════════════════
    def _add_app(self):
        dialog = tk.Toplevel(self)
        dialog.title("添加快捷应用")
        dialog.geometry("450x280")
        dialog.resizable(False, False)
        dialog.transient(self)

        ttk.Label(dialog, text="选择 .exe 文件：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(10, 2))

        path_var = tk.StringVar()
        path_entry = ttk.Entry(dialog, textvariable=path_var, font=("Microsoft YaHei", 9), width=50)
        path_entry.pack(padx=10, pady=2)

        def browse():
            fp = filedialog.askopenfilename(filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")])
            if fp:
                path_var.set(fp)

        tk.Button(
            dialog, text="浏览...", bg="#4A90D9", fg="white",
            font=("Microsoft YaHei", 9), relief=tk.FLAT, cursor="hand2",
            command=browse,
        ).pack(pady=2)

        ttk.Label(dialog, text="名称：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(5, 2))
        name_var = tk.StringVar()
        name_entry = ttk.Entry(dialog, textvariable=name_var, font=("Microsoft YaHei", 10), width=30)
        name_entry.pack(padx=10, pady=2)

        ttk.Label(dialog, text="备注：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=2)
        note_var = tk.StringVar()
        note_entry = ttk.Entry(dialog, textvariable=note_var, font=("Microsoft YaHei", 10), width=30)
        note_entry.pack(padx=10, pady=2)

        def do_add():
            fp = path_var.get().strip()
            name = name_var.get().strip()
            if not fp:
                messagebox.showwarning("提示", "请选择应用文件")
                return
            if not name:
                name = Path(fp).stem

            try:
                rel_path = os.path.relpath(fp, start=Path(__file__).parent.parent)
            except ValueError:
                rel_path = fp

            self.config.setdefault("apps", []).append({
                "type": "app",
                "path": rel_path,
                "name": name,
                "note": note_var.get().strip(),
            })
            self._save_config()
            self._refresh_apps()
            dialog.destroy()

        tk.Button(
            dialog, text="添加", bg="#27AE60", fg="white",
            font=("Microsoft YaHei", 10, "bold"), relief=tk.FLAT, cursor="hand2",
            command=do_add,
        ).pack(pady=10)

    def _launch_app(self, event):
        sel = self.app_listbox.curselection()
        if not sel:
            return
        display = self.app_listbox.get(sel[0])
        for item in self._app_raw:
            name = item.get("name", "")
            note = item.get("note", "")
            d = name
            if note:
                d += f"  ({note})"
            if d == display:
                fp = item.get("path", "")
                if not os.path.isabs(fp):
                    fp = os.path.join(Path(__file__).parent.parent, fp)
                if os.path.exists(fp):
                    os.startfile(fp)
                else:
                    messagebox.showwarning("提示", f"文件不存在：\n{fp}")
                return

    def _app_context_menu(self, event):
        sel = self.app_listbox.curselection()
        if not sel:
            return
        display = self.app_listbox.get(sel[0])
        real_idx = self._find_app_index_by_display(display)
        if real_idx < 0:
            return

        menu = tk.Menu(self, tearoff=0, font=("Microsoft YaHei", 9))
        menu.add_command(label="打开", command=lambda i=real_idx: self._launch_app_by_index(i))
        menu.add_command(label="编辑", command=lambda i=real_idx: self._edit_app(i))
        menu.add_command(label="删除", command=lambda i=real_idx: self._delete_app(i))
        menu.post(event.x_root, event.y_root)

    def _launch_app_by_index(self, idx):
        apps = self.config.get("apps", [])
        if idx >= len(apps):
            return
        item = apps[idx]
        fp = item.get("path", "")
        if not os.path.isabs(fp):
            fp = os.path.join(Path(__file__).parent.parent, fp)
        if os.path.exists(fp):
            os.startfile(fp)
        else:
            messagebox.showwarning("提示", f"文件不存在：\n{fp}")

    def _edit_app(self, idx):
        apps = self.config.get("apps", [])
        if idx >= len(apps):
            return
        item = apps[idx]

        dialog = tk.Toplevel(self)
        dialog.title("编辑快捷应用")
        dialog.geometry("450x280")
        dialog.resizable(False, False)
        dialog.transient(self)

        ttk.Label(dialog, text="路径：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(10, 2))
        path_var = tk.StringVar(value=item.get("path", ""))
        path_entry = ttk.Entry(dialog, textvariable=path_var, font=("Microsoft YaHei", 9), width=50)
        path_entry.pack(padx=10, pady=2)

        def browse():
            fp = filedialog.askopenfilename(filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")])
            if fp:
                try:
                    rel_path = os.path.relpath(fp, start=Path(__file__).parent.parent)
                except ValueError:
                    rel_path = fp
                path_var.set(rel_path)

        tk.Button(
            dialog, text="浏览...", bg="#4A90D9", fg="white",
            font=("Microsoft YaHei", 9), relief=tk.FLAT, cursor="hand2",
            command=browse,
        ).pack(pady=2)

        ttk.Label(dialog, text="名称：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(5, 2))
        name_var = tk.StringVar(value=item.get("name", ""))
        ttk.Entry(dialog, textvariable=name_var, font=("Microsoft YaHei", 10), width=30).pack(padx=10, pady=2)

        ttk.Label(dialog, text="备注：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=2)
        note_var = tk.StringVar(value=item.get("note", ""))
        ttk.Entry(dialog, textvariable=note_var, font=("Microsoft YaHei", 10), width=30).pack(padx=10, pady=2)

        def do_save():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("提示", "请输入名称")
                return
            apps[idx]["path"] = path_var.get().strip()
            apps[idx]["name"] = name
            apps[idx]["note"] = note_var.get().strip()
            self._save_config()
            self._refresh_apps()
            dialog.destroy()

        tk.Button(
            dialog, text="保存", bg="#27AE60", fg="white",
            font=("Microsoft YaHei", 10, "bold"), relief=tk.FLAT, cursor="hand2",
            command=do_save,
        ).pack(side=tk.BOTTOM, pady=10)

    def _delete_app(self, idx):
        apps = self.config.get("apps", [])
        if idx >= len(apps):
            return
        item = apps[idx]
        if messagebox.askyesno("确认删除", f"确定删除「{item.get('name','')}」吗？"):
            apps.pop(idx)
            self._save_config()
            self._refresh_apps()

    # ════════════════════════════════════════════════════════════════
    # ── exe直达（文件夹扫描）──
    # ════════════════════════════════════════════════════════════════
    def _open_exe_folder(self):
        _EXE_FOLDER.mkdir(parents=True, exist_ok=True)
        os.startfile(str(_EXE_FOLDER.resolve()))

    def _launch_exe(self, event):
        sel = self.exe_listbox.curselection()
        if not sel:
            return
        display = self.exe_listbox.get(sel[0])
        for f in self._exe_raw:
            note = self._get_exe_note(str(f.resolve()))
            d = f.name
            if note:
                d += f"  ({note})"
            if d == display:
                fp = str(f.resolve())
                if os.path.exists(fp):
                    os.startfile(fp)
                else:
                    messagebox.showwarning("提示", f"文件不存在：\n{fp}")
                return

    def _exe_context_menu(self, event):
        sel = self.exe_listbox.curselection()
        if not sel:
            return
        display = self.exe_listbox.get(sel[0])
        real_idx = self._find_exe_index_by_display(display)
        if real_idx < 0:
            return

        menu = tk.Menu(self, tearoff=0, font=("Microsoft YaHei", 9))
        menu.add_command(label="打开", command=lambda i=real_idx: self._launch_exe_by_index(i))
        menu.add_command(label="编辑备注", command=lambda i=real_idx: self._edit_exe(i))
        menu.add_command(label="删除文件", command=lambda i=real_idx: self._delete_exe(i))
        menu.post(event.x_root, event.y_root)

    def _launch_exe_by_index(self, idx):
        files = self._get_exe_files()
        if idx >= len(files):
            return
        fp = str(files[idx].resolve())
        if os.path.exists(fp):
            os.startfile(fp)
        else:
            messagebox.showwarning("提示", f"文件不存在：\n{fp}")

    def _get_exe_files(self):
        _EXE_FOLDER.mkdir(parents=True, exist_ok=True)
        return sorted([f for f in _EXE_FOLDER.iterdir() if f.is_file()])

    def _get_exe_note(self, abs_path):
        for item in self.config.get("exe_notes", []):
            if item.get("path", "") == abs_path:
                return item.get("note", "")
        return ""

    def _set_exe_note(self, abs_path, note):
        notes = self.config.setdefault("exe_notes", [])
        for item in notes:
            if item.get("path", "") == abs_path:
                item["note"] = note
                self._save_config()
                return
        notes.append({"path": abs_path, "note": note})
        self._save_config()

    def _edit_exe(self, idx):
        files = self._get_exe_files()
        if idx >= len(files):
            return
        fp = str(files[idx].resolve())
        current_note = self._get_exe_note(fp)

        dialog = tk.Toplevel(self)
        dialog.title("编辑备注")
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.transient(self)

        ttk.Label(dialog, text=f"文件：{files[idx].name}", font=("Microsoft YaHei", 9)).pack(padx=10, pady=(10, 5))
        ttk.Label(dialog, text="备注：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=2)
        note_var = tk.StringVar(value=current_note)
        ttk.Entry(dialog, textvariable=note_var, font=("Microsoft YaHei", 10), width=30).pack(padx=10, pady=2)

        def do_save():
            self._set_exe_note(fp, note_var.get().strip())
            self._refresh_exe_folder()
            dialog.destroy()

        tk.Button(
            dialog, text="保存", bg="#27AE60", fg="white",
            font=("Microsoft YaHei", 10, "bold"), relief=tk.FLAT, cursor="hand2",
            command=do_save,
        ).pack(side=tk.BOTTOM, pady=10)

    def _delete_exe(self, idx):
        files = self._get_exe_files()
        if idx >= len(files):
            return
        f = files[idx]
        abs_path = str(f.resolve())
        if messagebox.askyesno("确认删除", f"确定删除「{f.name}」吗？\n文件将移至回收站。"):
            try:
                import send2trash
                send2trash.send2trash(abs_path)
            except ImportError:
                os.remove(abs_path)
            # 清理备注
            self.config["exe_notes"] = [
                item for item in self.config.get("exe_notes", [])
                if item.get("path", "") != abs_path
            ]
            self._save_config()
            self._refresh_exe_folder()

    # ════════════════════════════════════════════════════════════════
    # ── 网址链接操作 ──
    # ════════════════════════════════════════════════════════════════
    def _add_url(self):
        dialog = tk.Toplevel(self)
        dialog.title("添加网址链接")
        dialog.geometry("450x250")
        dialog.resizable(False, False)
        dialog.transient(self)

        ttk.Label(dialog, text="URL：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(10, 2))
        url_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=url_var, font=("Microsoft YaHei", 9), width=50).pack(padx=10, pady=2)

        ttk.Label(dialog, text="名称：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(5, 2))
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, font=("Microsoft YaHei", 10), width=30).pack(padx=10, pady=2)

        ttk.Label(dialog, text="备注：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=2)
        note_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=note_var, font=("Microsoft YaHei", 10), width=30).pack(padx=10, pady=2)

        def do_add():
            url = url_var.get().strip()
            name = name_var.get().strip()
            if not url:
                messagebox.showwarning("提示", "请输入URL")
                return
            if not name:
                messagebox.showwarning("提示", "请输入名称")
                return

            self.config.setdefault("urls", []).append({
                "type": "url",
                "url": url,
                "name": name,
                "note": note_var.get().strip(),
            })
            self._save_config()
            self._refresh_urls()
            dialog.destroy()

        tk.Button(
            dialog, text="添加", bg="#27AE60", fg="white",
            font=("Microsoft YaHei", 10, "bold"), relief=tk.FLAT, cursor="hand2",
            command=do_add,
        ).pack(side=tk.BOTTOM, pady=10)

    def _open_url(self, event):
        sel = self.url_listbox.curselection()
        if not sel:
            return
        display = self.url_listbox.get(sel[0])
        for item in self._url_raw:
            name = item.get("name", "")
            note = item.get("note", "")
            d = name
            if note:
                d += f"  ({note})"
            if d == display:
                url = item.get("url", "")
                if url:
                    self._open_link(url)
                return

    def _url_context_menu(self, event):
        sel = self.url_listbox.curselection()
        if not sel:
            return
        display = self.url_listbox.get(sel[0])
        real_idx = self._find_url_index_by_display(display)
        if real_idx < 0:
            return

        menu = tk.Menu(self, tearoff=0, font=("Microsoft YaHei", 9))
        menu.add_command(label="打开", command=lambda i=real_idx: self._open_url_by_index(i))
        menu.add_command(label="复制URL", command=lambda i=real_idx: self._copy_url(i))
        menu.add_command(label="编辑", command=lambda i=real_idx: self._edit_url(i))
        menu.add_command(label="删除", command=lambda i=real_idx: self._delete_url(i))
        menu.post(event.x_root, event.y_root)

    def _open_url_by_index(self, idx):
        urls = self.config.get("urls", [])
        if idx >= len(urls):
            return
        url = urls[idx].get("url", "")
        if url:
            os.startfile(url)


    def _open_link(self, url):
        if self.navigate_callback:
            self.navigate_callback(url)
        else:
            os.startfile(url)

    def _copy_url(self, idx):
        urls = self.config.get("urls", [])
        if idx >= len(urls):
            return
        url = urls[idx].get("url", "")
        self.clipboard_clear()
        self.clipboard_append(url)
        messagebox.showinfo("已复制", f"URL已复制到剪贴板\n{url}")

    def _edit_url(self, idx):
        urls = self.config.get("urls", [])
        if idx >= len(urls):
            return
        item = urls[idx]

        dialog = tk.Toplevel(self)
        dialog.title("编辑网址链接")
        dialog.geometry("450x250")
        dialog.resizable(False, False)
        dialog.transient(self)

        ttk.Label(dialog, text="URL：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(10, 2))
        url_var = tk.StringVar(value=item.get("url", ""))
        ttk.Entry(dialog, textvariable=url_var, font=("Microsoft YaHei", 9), width=50).pack(padx=10, pady=2)

        ttk.Label(dialog, text="名称：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=(5, 2))
        name_var = tk.StringVar(value=item.get("name", ""))
        ttk.Entry(dialog, textvariable=name_var, font=("Microsoft YaHei", 10), width=30).pack(padx=10, pady=2)

        ttk.Label(dialog, text="备注：", font=("Microsoft YaHei", 10)).pack(padx=10, pady=2)
        note_var = tk.StringVar(value=item.get("note", ""))
        ttk.Entry(dialog, textvariable=note_var, font=("Microsoft YaHei", 10), width=30).pack(padx=10, pady=2)

        def do_save():
            name = name_var.get().strip()
            if not name:
                messagebox.showwarning("提示", "请输入名称")
                return
            urls[idx]["url"] = url_var.get().strip()
            urls[idx]["name"] = name
            urls[idx]["note"] = note_var.get().strip()
            self._save_config()
            self._refresh_urls()
            dialog.destroy()

        tk.Button(
            dialog, text="保存", bg="#27AE60", fg="white",
            font=("Microsoft YaHei", 10, "bold"), relief=tk.FLAT, cursor="hand2",
            command=do_save,
        ).pack(side=tk.BOTTOM, pady=10)

    def _delete_url(self, idx):
        urls = self.config.get("urls", [])
        if idx >= len(urls):
            return
        item = urls[idx]

        if messagebox.askyesno("确认删除", f"确定删除「{item.get('name','')}」吗？"):
            urls.pop(idx)
            self._save_config()
            self._refresh_urls()