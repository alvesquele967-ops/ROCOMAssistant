"""
竹雨ROCOM小助手 - 启动入口
支持直接运行 python main.py
"""

import sys
import os

# 确保项目根目录在 sys.path 中
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from ui.main_window import run

if __name__ == "__main__":
    run()