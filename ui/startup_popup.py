"""
竹雨ROCOM小助手 - 启动弹窗（使用须知）
"""

import tkinter as tk
from tkinter import ttk
import os
import json

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app_config.json")

_NOTE_TEXT = """各位玩家好，本款游戏集成工具箱（竹雨ROCOM小助手）为个人业余制作的免费工具，旨在方便大家查询精灵、技能信息与计算相关数值。
工具基于Python开发并打包为exe，源码完全公开，大家可自行修改、新增、优化功能。工具支持通过洛克王国世界bwiki API实时拉取最新数据，同时也提供本地文件夹、JSON文件存储数据的选项，数据全程自主把控，无隐私上传，请放心使用。
作者抖音：takesitaame，欢迎关注交流。祝各位游戏愉快！

使用注意事项：
1. 数据来源：精灵、技能图鉴数据调用自洛克王国世界bwiki API，支持实时更新；相关计算公式整理自网络公开内容，本人不享有相关版权。
2. 使用规范：本工具禁止商业用途、商业传播、二次售卖，仅可作为个人学习、游戏参考使用。
3. 存储说明：除在线实时获取数据外，工具支持将数据本地存放至文件夹或JSON文件。
4. 免责提示：数据、计算结果仅供参考，一切以游戏官方内容为准；私自修改源码、违规使用所产生的相关问题，由使用者自行承担。"""


def check_and_show(parent_root):
    """检查配置，如需要则显示启动弹窗"""
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            if cfg.get("skip_startup_warning"):
                return
        except:
            pass
    StartupPopup(parent_root)


class StartupPopup(tk.Toplevel):
    """启动须知弹窗"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("洛克王国世界助手 - 使用须知")

        # 居中于父窗口
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_x(), parent.winfo_y()
        w, h = 520, 560
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # 任务栏可见 + 置顶 + 模态
        self.attributes('-toolwindow', False)
        self.attributes('-topmost', True)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        # 说明文本（带滚动条，灰色背景）
        text_frame = ttk.Frame(self)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 0))

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 10),
            bg="#F0F0F0",
            relief=tk.FLAT,
            borderwidth=0,
            padx=10,
            pady=10,
            yscrollcommand=scrollbar.set,
        )
        self.text_widget.pack(fill=tk.BOTH, expand=True)
        self.text_widget.insert(tk.END, _NOTE_TEXT)
        self.text_widget.configure(state=tk.DISABLED)
        scrollbar.config(command=self.text_widget.yview)

        # 底部按钮区
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=12, pady=12)

        self.skip_var = tk.BooleanVar(value=False)
        cb = ttk.Checkbutton(
            bottom,
            text="不再弹出",
            variable=self.skip_var,
        )
        cb.pack(side=tk.LEFT)

        btn = ttk.Button(
            bottom,
            text="我已阅读并进入软件",
            command=self._on_confirm,
        )
        btn.pack(side=tk.RIGHT)

    def _on_confirm(self):
        if self.skip_var.get():
            try:
                config_dir = os.path.dirname(_CONFIG_PATH)
                os.makedirs(config_dir, exist_ok=True)
                with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
                    json.dump({"skip_startup_warning": True}, f, ensure_ascii=False)
            except:
                pass
        self.destroy()