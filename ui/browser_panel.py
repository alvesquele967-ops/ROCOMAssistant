# -*- coding: utf-8 -*-
'''
竹雨ROCOM小助手 - 内置浏览器面板
方案：启动 Edge --app 模式，通过 Win32 SetParent 嵌入到 Tkinter Frame
延迟启动：仅在点击Wiki选项卡或手动点击"启动浏览器"时才打开Edge
'''
import tkinter as tk
from tkinter import ttk
import subprocess
import time
import os
import sys

from ui.theme import (
    PRIMARY, PRIMARY_HOVER,
    FONT_BODY, FONT_SMALL, FONT_HEADING,
    PAD_X,
)

DEFAULT_URL = "https://wiki.biligame.com/rocom/%E9%A6%96%E9%A1%B5"

# ── Win32 API ──
import ctypes
from ctypes import wintypes, POINTER, byref, c_int, c_long

user32 = ctypes.WinDLL('user32')
kernel32 = ctypes.WinDLL('kernel32')

SetParent = user32.SetParent
SetParent.argtypes = [wintypes.HWND, wintypes.HWND]; SetParent.restype = wintypes.HWND
SetWindowLongW = user32.SetWindowLongW
SetWindowLongW.argtypes = [wintypes.HWND, c_int, c_long]; SetWindowLongW.restype = c_long
GetWindowLongW = user32.GetWindowLongW
GetWindowLongW.argtypes = [wintypes.HWND, c_int]; GetWindowLongW.restype = c_long
SetWindowPos = user32.SetWindowPos
SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, c_int, c_int, c_int, c_int, wintypes.UINT]; SetWindowPos.restype = wintypes.BOOL
EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]; EnumWindows.restype = wintypes.BOOL
GetWindowThreadProcessId = user32.GetWindowThreadProcessId
GetWindowThreadProcessId.argtypes = [wintypes.HWND, POINTER(wintypes.DWORD)]; GetWindowThreadProcessId.restype = wintypes.DWORD
GetClassNameW = user32.GetClassNameW
GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, c_int]; GetClassNameW.restype = c_int

# 常量
GWL_STYLE = -16
WS_CAPTION = 0x00C00000; WS_THICKFRAME = 0x00040000; WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000; WS_MAXIMIZEBOX = 0x00010000
SWP_NOZORDER = 0x0004; SWP_FRAMECHANGED = 0x0020


def _find_edge_hwnd(pid, timeout=8.0):
    """通过PID查找Edge浏览器窗口句柄"""
    found = []
    @EnumWindowsProc
    def _enum(hwnd, lparam):
        proc_id = wintypes.DWORD()
        GetWindowThreadProcessId(hwnd, byref(proc_id))
        if proc_id.value == pid:
            buf = ctypes.create_unicode_buffer(256)
            GetClassNameW(hwnd, buf, 256)
            if buf.value in ("Chrome_WidgetWin_1", "MozillaWindowClass"):
                found.append(hwnd)
        return True
    start = time.time()
    while time.time() - start < timeout:
        found.clear()
        EnumWindows(_enum, 0)
        if found:
            best = None; best_area = 0
            for h in found:
                r = wintypes.RECT(); user32.GetWindowRect(h, byref(r))
                area = (r.right - r.left) * (r.bottom - r.top)
                if area > best_area: best_area = area; best = h
            if best: return best
        time.sleep(0.3)
    return None


class BrowserPanel(ttk.Frame):
    """内置 Edge 浏览器面板 - 延迟启动版"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self._edge_process = None
        self._edge_hwnd = None
        self._hosting_frame = None
        self._embedded = False
        self._started = False
        self._launching = False
        self._restart_btn = None
        self._launch_btn_frame = None
        self.status_var = tk.StringVar(value="浏览器未启动")
        self.url_var = tk.StringVar()
        self._current_url = None
        self._build_ui()
        # 不再自动启动！等待用户手动点击或切换选项卡

    # ── 公开 API ──
    def navigate_to(self, url):
        """外部调用：导航到指定 URL"""
        self._navigate(url)

    def start_browser(self):
        """外部调用：启动浏览器（如果尚未启动）"""
        if not self._started and not self._launching:
            self._launch_edge()

    def is_embedded(self):
        return self._embedded

    def _build_ui(self):
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=PAD_X, pady=5)
        ttk.Label(header, text="内置浏览器", font=FONT_HEADING).pack(side=tk.LEFT)
        ttk.Label(header, text="Edge 内核 · Wiki", font=FONT_SMALL, foreground="gray").pack(side=tk.LEFT, padx=10)

        # 导航栏
        nav_frame = ttk.Frame(self)
        nav_frame.pack(fill=tk.X, padx=PAD_X, pady=(0, 4))
        bo = {"font": FONT_SMALL, "bg": PRIMARY, "fg": "white",
              "activebackground": PRIMARY_HOVER, "activeforeground": "white",
              "relief": tk.FLAT, "cursor": "hand2", "borderwidth": 0, "padx": 6, "pady": 2}
        
        tk.Button(nav_frame, text="Home", command=self._go_home, **bo).pack(side=tk.LEFT, padx=1)
        tk.Button(nav_frame, text="刷新", command=self._refresh, **bo).pack(side=tk.LEFT, padx=1)
        
        # 重启浏览器按钮
        self._restart_btn = tk.Button(nav_frame, text="重启浏览器", command=self._restart_browser,
                                       font=FONT_SMALL, bg="#E67E22", fg="white",
                                       activebackground="#D35400", activeforeground="white",
                                       relief=tk.FLAT, cursor="hand2", borderwidth=0, padx=6, pady=2)
        # 初始隐藏，浏览器启动后再显示
        # self._restart_btn.pack(side=tk.LEFT, padx=1)  -- 延迟到_do_embed时显示

        self.url_var.set(DEFAULT_URL)
        ue = ttk.Entry(nav_frame, textvariable=self.url_var, font=("Microsoft YaHei", 9))
        ue.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        ue.bind("<Return>", lambda e: self._navigate(self.url_var.get().strip()))
        tk.Button(nav_frame, text="Go", command=lambda: self._navigate(self.url_var.get().strip()), **bo).pack(side=tk.RIGHT, padx=1)

        # 覆盖层（浏览器未启动时显示启动按钮）
        self._overlay = tk.Frame(self, bg="white")
        self._overlay.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=(0, 5))
        
        # 启动浏览器大按钮
        self._launch_btn_frame = tk.Frame(self._overlay, bg="white")
        self._launch_btn_frame.pack(expand=True)
        tk.Label(self._launch_btn_frame, text="🌐", font=("Microsoft YaHei", 48),
                 bg="white", fg="#636E72").pack()
        tk.Label(self._launch_btn_frame, text="Wiki 内置浏览器", font=("Microsoft YaHei", 16, "bold"),
                 bg="white", fg="#2C3E50").pack(pady=(5, 3))
        tk.Label(self._launch_btn_frame, text="点击下方按钮启动 Edge 浏览器访问 Wiki",
                 font=("Microsoft YaHei", 10), bg="white", fg="#636E72").pack(pady=(0, 15))
        tk.Label(self._launch_btn_frame, text="⚠ 请勿频繁重启，每次启动都会访问网站",
                 font=("Microsoft YaHei", 8), bg="white", fg="#E67E22").pack(pady=(0, 10))
        tk.Button(self._launch_btn_frame, text="🚀 启动浏览器", font=("Microsoft YaHei", 12, "bold"),
                  bg="#27AE60", fg="white", activebackground="#219A52", activeforeground="white",
                  relief=tk.FLAT, cursor="hand2", borderwidth=0, padx=30, pady=10,
                  command=self._launch_edge).pack()

        # 嵌入用的宿主 Frame
        self._hosting_frame = tk.Frame(self, bg="white")
        self._hosting_frame.bind("<Configure>", self._on_resize)

        # 底部状态栏
        status = ttk.Frame(self)
        status.pack(fill=tk.X, padx=PAD_X, pady=(0, 3))
        ttk.Label(status, textvariable=self.status_var, font=("Microsoft YaHei", 8), foreground="gray").pack(side=tk.LEFT)
        tk.Label(status, text="抖音：takesitaame", font=("Microsoft YaHei", 8), fg="#999999", bg="#EAECEE").pack(side=tk.RIGHT)

    # ── Edge 启动、嵌入、重启 ──
    def _launch_edge(self):
        """启动 Edge 浏览器"""
        if self._launching:
            return
        self._launching = True
        self._started = True
        self.status_var.set("正在启动 Edge 浏览器 ...")
        edge_exe = self._find_edge_exe()
        if not edge_exe:
            self.status_var.set("错误：未找到 Microsoft Edge")
            self._launching = False
            return

        try:
            # 持久化 profile 目录，cookie 不会丢失
            profile_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources', 'edge_profile')
            os.makedirs(profile_dir, exist_ok=True)
            self._edge_process = subprocess.Popen(
                [edge_exe, f"--app={DEFAULT_URL}", f"--user-data-dir={profile_dir}",
                 "--new-window", "--no-first-run", "--window-size=800,600"],
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
            )
            self.status_var.set("正在嵌入 Edge 窗口 ...")
            self.after(500, self._try_embed)
        except Exception as e:
            self.status_var.set(f"启动失败: {e}")
            self._launching = False

    def _try_embed(self):
        if self._embedded:
            self._launching = False
            return
        hwnd = _find_edge_hwnd(self._edge_process.pid, timeout=5.0)
        if hwnd:
            self._edge_hwnd = hwnd
            self._do_embed()
        else:
            if self._edge_process and self._edge_process.poll() is not None:
                self.status_var.set("Edge 进程已退出，请点击重启浏览器")
                self._launching = False
                return
            self.status_var.set("等待 Edge 窗口 ...")
            self.after(500, self._try_embed)

    def _do_embed(self):
        try:
            hwnd = self._edge_hwnd
            parent_hwnd = self._hosting_frame.winfo_id()
            style = GetWindowLongW(hwnd, GWL_STYLE)
            style &= ~(WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
            SetWindowLongW(hwnd, GWL_STYLE, style)
            SetParent(hwnd, wintypes.HWND(parent_hwnd))
            # 隐藏覆盖层，显示宿主 Frame
            self._overlay.pack_forget()
            self._hosting_frame.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=(0, 5))
            self.after(200, self._resize_edge)
            self._embedded = True
            self._launching = False
            self._current_url = DEFAULT_URL
            self.status_var.set("就绪")
            # 显示重启按钮
            if self._restart_btn:
                self._restart_btn.pack(side=tk.LEFT, padx=1)
        except Exception as e:
            self.status_var.set(f"嵌入失败: {e}")
            self._launching = False

    def _restart_browser(self):
        """关闭并重新启动浏览器"""
        self._kill_edge()
        self._embedded = False
        self._edge_hwnd = None
        self._started = False
        # 隐藏宿主 Frame，显示覆盖层
        self._hosting_frame.pack_forget()
        # 隐藏重启按钮
        if self._restart_btn:
            self._restart_btn.pack_forget()
        # 重建覆盖层
        self._overlay = tk.Frame(self, bg="white")
        self._overlay.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=(0, 5))
        self._launch_btn_frame = tk.Frame(self._overlay, bg="white")
        self._launch_btn_frame.pack(expand=True)
        tk.Label(self._launch_btn_frame, text="🌐", font=("Microsoft YaHei", 48),
                 bg="white", fg="#636E72").pack()
        tk.Label(self._launch_btn_frame, text="Wiki 内置浏览器", font=("Microsoft YaHei", 16, "bold"),
                 bg="white", fg="#2C3E50").pack(pady=(5, 3))
        tk.Label(self._launch_btn_frame, text="浏览器已关闭，点击重新启动",
                 font=("Microsoft YaHei", 10), bg="white", fg="#636E72").pack(pady=(0, 15))
        tk.Label(self._launch_btn_frame, text="⚠ 请勿频繁重启，每次启动都会访问网站",
                 font=("Microsoft YaHei", 8), bg="white", fg="#E67E22").pack(pady=(0, 10))
        tk.Button(self._launch_btn_frame, text="🚀 重新启动浏览器", font=("Microsoft YaHei", 12, "bold"),
                  bg="#27AE60", fg="white", activebackground="#219A52", activeforeground="white",
                  relief=tk.FLAT, cursor="hand2", borderwidth=0, padx=30, pady=10,
                  command=self._launch_edge).pack()
        self.status_var.set("浏览器已关闭")
        # 启动新浏览器
        self._launch_edge()

    def _resize_edge(self):
        if self._edge_hwnd:
            w = max(self._hosting_frame.winfo_width(), 100)
            h = max(self._hosting_frame.winfo_height(), 100)
            SetWindowPos(self._edge_hwnd, None, 0, 0, w, h, SWP_NOZORDER | SWP_FRAMECHANGED)

    def _on_resize(self, event):
        if self._embedded:
            self.after(50, self._resize_edge)

    # ── 导航 ──
    def _navigate(self, url):
        if not url:
            return
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        self.url_var.set(url)
        if self._embedded and self._edge_process and self._edge_process.poll() is None:
            self._current_url = url
            self._kill_edge()
            self._embedded = False
            self._edge_hwnd = None
            self._hosting_frame.pack_forget()
            # 隐藏重启按钮
            if self._restart_btn:
                self._restart_btn.pack_forget()
            # 显示切换中覆盖层
            self._overlay = tk.Frame(self, bg="white")
            self._overlay.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=(0, 5))
            self._launch_btn_frame = tk.Frame(self._overlay, bg="white")
            self._launch_btn_frame.pack(expand=True)
            tk.Label(self._launch_btn_frame, text="🔄", font=("Microsoft YaHei", 48),
                     bg="white", fg="#636E72").pack()
            tk.Label(self._launch_btn_frame, text="正在切换页面 ...", font=("Microsoft YaHei", 12),
                     bg="white", fg="#636E72").pack(expand=True)
            
            profile_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources', 'edge_profile')
            edge_exe = self._find_edge_exe()
            self._edge_process = subprocess.Popen(
                [edge_exe, f"--app={url}", f"--user-data-dir={profile_dir}",
                 "--new-window", "--no-first-run", "--window-size=800,600"],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self.after(500, self._try_embed)
        elif not self._embedded:
            # 浏览器还没启动，先启动
            self._current_url = url
            self._launch_edge()

    def _find_edge_exe(self):
        for p in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                   r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]:
            if os.path.exists(p):
                return p
        return r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

    def _kill_edge(self):
        if self._edge_process:
            try:
                self._edge_process.terminate()
                self._edge_process.wait(timeout=5)
            except:
                try:
                    self._edge_process.kill()
                except:
                    pass

    def _go_home(self):
        self._navigate(DEFAULT_URL)

    def _refresh(self):
        if self._embedded and self._current_url:
            self._navigate(self._current_url)

    def destroy(self):
        self._kill_edge()
        super().destroy()
