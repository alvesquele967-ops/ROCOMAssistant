"""
竹雨ROCOM小助手 - 使用须知面板（主界面常驻标签页）
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


class NotesPanel(ttk.Frame):
    """使用须知面板（常驻标签页）"""

    def __init__(self, parent):
        super().__init__(parent)
        self._build_ui()

    def _load_config(self):
        """从配置文件读取 skip_startup_warning，返回勾选状态（True=显示弹窗）"""
        if os.path.exists(_CONFIG_PATH):
            try:
                with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                # skip_startup_warning 为 true 时不勾选（即不弹窗），false 或不存在时勾选
                return not cfg.get("skip_startup_warning", False)
            except:
                pass
        return True  # 配置文件不存在或读取失败，默认勾选

    def _on_check_changed(self):
        """勾选状态变化时实时写入配置文件"""
        checked = self.show_popup_var.get()
        value = not checked  # 勾选 → 显示弹窗 → skip_startup_warning = false
        try:
            config_dir = os.path.dirname(_CONFIG_PATH)
            os.makedirs(config_dir, exist_ok=True)
            with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump({"skip_startup_warning": value}, f, ensure_ascii=False)
        except:
            pass

    def _build_ui(self):
        # --- 说明文本区域（带滚动条，灰色背景） ---
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

        # --- 底部控制栏 ---
        bottom = ttk.Frame(self)
        bottom.pack(fill=tk.X, padx=12, pady=12)

        # 左侧标题
        title_label = ttk.Label(bottom, text="启动设置", font=("Microsoft YaHei", 9, "bold"))
        title_label.pack(side=tk.LEFT)

        # 右侧勾选框
        initial_state = self._load_config()
        self.show_popup_var = tk.BooleanVar(value=initial_state)
        cb = ttk.Checkbutton(
            bottom,
            text="打开软件时显示使用须知弹窗",
            variable=self.show_popup_var,
            command=self._on_check_changed,
        )
        cb.pack(side=tk.RIGHT)