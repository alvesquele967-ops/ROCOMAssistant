"""
竹雨ROCOM小助手 - 主窗口 v2.5
自定义图片标签栏 + 美化UI
"""

import tkinter as tk
from tkinter import ttk
from pathlib import Path
from ui.theme import configure_ttk, BG_APP, BG_DARK, PRIMARY, DANGER, TEXT_HINT, FONT_SMALL, FONT_CAPTION, FONT_BODY
from ui.type_chart import TypeChartFrame
from ui.team_panel import TeamPanel
from ui.pokedex_panel import PokedexPanel
from ui.skill_pedia_panel import SkillPediaPanel
from ui.news_panel import NewsPanel
from ui.toolbar_panel import ToolbarPanel
from ui.settings_panel import SettingsPanel
from ui.changelog_panel import ChangelogPanel
from ui.damage_calc_panel import DamageCalcPanel
from ui.notes_panel import NotesPanel
from ui.browser_panel import BrowserPanel
from ui.startup_popup import check_and_show as show_startup_popup

# 标签页配置: (图片文件名, 显示文字, 面板类)
TAB_CONFIG = [
    ("属性克制.png", "属性克制", TypeChartFrame),
    ("伤害计算.png", "伤害计算", DamageCalcPanel),
    ("配队管理.png", "配队管理", TeamPanel),
    ("图鉴.png", "图鉴", PokedexPanel),
    ("技能图鉴.png", "技能图鉴", SkillPediaPanel),
    ("资讯.png", "资讯", NewsPanel),
    ("工具栏.png", "工具栏", ToolbarPanel),
    ("WiKi.png", "Wiki", BrowserPanel),
    ("设置.png", "设置", SettingsPanel),
    ("更新日志.png", "更新日志", ChangelogPanel),
    ("使用须知.png", "使用须知", NotesPanel),
]

# 颜色方案
TABBAR_BG = "#1a1a2e"        # 标签栏深色背景
TAB_BG = "#1a1a2e"            # 标签默认背景
TAB_ACTIVE_BG = "#16213e"     # 激活标签背景  
TAB_HOVER_BG = "#0f3460"      # 悬停背景
TAB_ACTIVE_ACCENT = "#e94560" # 激活标签底部强调线
TAB_TEXT = "#a0a0b0"          # 默认文字
TAB_TEXT_ACTIVE = "#ffffff"   # 激活文字
TAB_ICON_SIZE = 28             # 图标尺寸


class MainWindow:
    """主窗口"""

    def __init__(self, root):
        self.root = root
        self.root.title("竹雨ROCOM小助手 v2.5")
        self.root.geometry("1200x800")

        # 设置窗口图标
        try:
            import sys

            # 收集所有可能的搜索路径
            search_dirs = []
            if getattr(sys, "frozen", False):
                search_dirs.append(Path(sys.executable).parent)
                # PyInstaller onefile: sys._MEIPASS 是解压后的临时目录
                if hasattr(sys, "_MEIPASS"):
                    search_dirs.append(Path(sys._MEIPASS))
            else:
                base = Path(__file__).parent.parent
                search_dirs.extend([
                    base,
                    base / "dist",
                    base / "resources",
                ])

            # 找到图标文件
            ico_file = None
            png_file = None
            for d in search_dirs:
                if not ico_file:
                    p = d / "图标.ico"
                    if p.exists():
                        ico_file = p
                if not png_file:
                    p = d / "图标.png"
                    if p.exists():
                        png_file = p

            # Windows: 用 iconbitmap 设置 .ico
            if ico_file:
                self.root.iconbitmap(default=str(ico_file))
            elif png_file:
                # 尝试用 .png
                try:
                    self.root.iconbitmap(default=str(png_file))
                except Exception:
                    # 回退：用 iconphoto 加载 png
                    try:
                        from PIL import Image, ImageTk
                        img = Image.open(str(png_file))
                        photo = ImageTk.PhotoImage(img)
                        self.root.iconphoto(True, photo)
                        self._icon_photo = photo  # 保持引用防止被 GC
                    except Exception:
                        pass
        except Exception:
            pass
        self.root.minsize(1000, 700)
        self.root.configure(bg=BG_APP)

        configure_ttk()
        
        # 加载图标
        self._tab_icons = {}   # filename -> PhotoImage
        self._tab_photos = []  # 保持引用防止GC
        self._load_icons()
        
        # 构建界面
        self._build_tab_bar()
        self._build_panels()
        self._build_statusbar()
        
        # 默认显示第一个面板
        self._active_tab_index = 0
        self._show_panel(0)
        self._highlight_tab(0)
        
        # 启动弹窗
        self.root.after(100, lambda: show_startup_popup(self.root))

    def _get_icon_dir(self):
        """获取图标目录路径"""
        import sys
        # 始终从代码文件位置推断资源路径，支持复制到任意文件夹
        # 处理 PyInstaller 打包后的临时目录
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).parent.parent

        candidates = [
            base / "resources" / "images" / "uii",
            base / "dist" / "resources" / "images" / "uii",
            base.parent / "resources" / "images" / "uii",
        ]
        for p in candidates:
            if p.exists():
                return p
        # 最后尝试相对于当前工作目录
        cwd_path = Path("resources") / "images" / "uii"
        if cwd_path.exists():
            return cwd_path
        # 实在找不到就返回第一个候选，让后续代码报清晰的错误
        return candidates[0]

    def _load_icons(self):
        """加载并缩放所有标签图标"""
        icon_dir = self._get_icon_dir()
        try:
            from PIL import Image, ImageTk
            for filename, _, _ in TAB_CONFIG:
                img_path = icon_dir / filename
                if img_path.exists():
                    img = Image.open(img_path)
                    # 缩放到图标尺寸，保持比例
                    img = img.resize((TAB_ICON_SIZE, TAB_ICON_SIZE), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                    self._tab_icons[filename] = photo
                    self._tab_photos.append(photo)
        except ImportError:
            # 如果没有PIL，使用tkinter自带缩放
            for filename, _, _ in TAB_CONFIG:
                img_path = icon_dir / filename
                if img_path.exists():
                    photo = tk.PhotoImage(file=str(img_path))
                    # subsample 降采样
                    factor = max(1, photo.width() // TAB_ICON_SIZE)
                    photo = photo.subsample(factor, factor)
                    self._tab_icons[filename] = photo
                    self._tab_photos.append(photo)

    def _build_tab_bar(self):
        """构建顶部图片标签栏"""
        self.tab_bar = tk.Frame(self.root, bg=TABBAR_BG, height=58)
        self.tab_bar.pack(fill=tk.X, side=tk.TOP)
        self.tab_bar.pack_propagate(False)
        
        # 标签容器
        tab_container = tk.Frame(self.tab_bar, bg=TABBAR_BG)
        tab_container.pack(fill=tk.X, padx=4, pady=3)
        
        self._tab_frames = []
        self._tab_labels = []
        
        for i, (filename, text, _) in enumerate(TAB_CONFIG):
            # 单个标签 Frame
            tab_frame = tk.Frame(tab_container, bg=TAB_BG, cursor="hand2",
                                 width=86, height=50)
            tab_frame.pack(side=tk.LEFT, padx=1, pady=1)
            tab_frame.pack_propagate(False)
            
            # 图标
            icon = self._tab_icons.get(filename)
            if icon:
                icon_label = tk.Label(tab_frame, image=icon, bg=TAB_BG,
                                     cursor="hand2")
                icon_label.pack(pady=(4, 0))
                # 绑定点击
                icon_label.bind("<Button-1>", lambda e, idx=i: self._on_tab_click(idx))
            else:
                # 图标缺失时用文字占位
                placeholder = tk.Label(tab_frame, text=text[:2], bg=TAB_BG,
                                      fg=TAB_TEXT, font=("Microsoft YaHei", 12, "bold"),
                                      cursor="hand2")
                placeholder.pack(pady=(4, 0))
                placeholder.bind("<Button-1>", lambda e, idx=i: self._on_tab_click(idx))
            
            # 文字标签
            text_label = tk.Label(tab_frame, text=text, bg=TAB_BG, fg=TAB_TEXT,
                                 font=("Microsoft YaHei", 8), cursor="hand2")
            text_label.pack()
            
            # 整框绑定点击和悬停
            for widget in (tab_frame, text_label):
                widget.bind("<Button-1>", lambda e, idx=i: self._on_tab_click(idx))
                widget.bind("<Enter>", lambda e, f=tab_frame, t=text_label, idx=i: self._on_tab_hover(f, t, idx, True))
                widget.bind("<Leave>", lambda e, f=tab_frame, t=text_label, idx=i: self._on_tab_hover(f, t, idx, False))
            
            self._tab_frames.append(tab_frame)
            self._tab_labels.append(text_label)

    def _on_tab_hover(self, frame, label, index, entering):
        """标签悬停效果"""
        if index == self._active_tab_index:
            return  # 不改变激活标签
        if entering:
            frame.configure(bg=TAB_HOVER_BG)
            label.configure(bg=TAB_HOVER_BG)
            # 递归更新子组件
            for child in frame.winfo_children():
                try:
                    child.configure(bg=TAB_HOVER_BG)
                except:
                    pass
        else:
            frame.configure(bg=TAB_BG)
            label.configure(bg=TAB_BG)
            for child in frame.winfo_children():
                try:
                    child.configure(bg=TAB_BG)
                except:
                    pass

    def _on_tab_click(self, index):
        """标签点击事件"""
        if index == self._active_tab_index:
            return
        self._show_panel(index)
        self._highlight_tab(index)

    def _highlight_tab(self, index):
        """高亮指定标签"""
        for i, (frame, label) in enumerate(zip(self._tab_frames, self._tab_labels)):
            if i == index:
                frame.configure(bg=TAB_ACTIVE_BG, highlightbackground=TAB_ACTIVE_ACCENT,
                              highlightthickness=2, highlightcolor=TAB_ACTIVE_ACCENT)
                label.configure(bg=TAB_ACTIVE_BG, fg=TAB_TEXT_ACTIVE)
                for child in frame.winfo_children():
                    try:
                        child.configure(bg=TAB_ACTIVE_BG)
                    except:
                        pass
            else:
                frame.configure(bg=TAB_BG, highlightthickness=0)
                label.configure(bg=TAB_BG, fg=TAB_TEXT)
                for child in frame.winfo_children():
                    try:
                        child.configure(bg=TAB_BG)
                    except:
                        pass
        self._active_tab_index = index

    def _build_panels(self):
        """构建所有内容面板"""
        self.panel_container = tk.Frame(self.root, bg=BG_APP)
        self.panel_container.pack(fill=tk.BOTH, expand=True)
        
        self._panels = []
        self._panel_kwargs = {}
        
        for i, (_, text, panel_class) in enumerate(TAB_CONFIG):
            kwargs = {}
            # 工具栏和资讯需要导航回调
            if text == "工具栏":
                kwargs["navigate_callback"] = self._navigate_to_browser
            elif text == "资讯":
                kwargs["navigate_callback"] = self._navigate_to_browser
            
            panel = panel_class(self.panel_container, **kwargs)
            self._panels.append(panel)
    
    def _show_panel(self, index):
        """显示指定面板，隐藏其他"""
        for i, panel in enumerate(self._panels):
            if i == index:
                panel.pack(fill=tk.BOTH, expand=True)
            else:
                panel.pack_forget()
        self._active_tab_index = index
        
        # 切换到Wiki标签时自动启动浏览器
        if TAB_CONFIG[index][1] == "Wiki":
            try:
                panel.start_browser()
            except:
                pass

    def _build_statusbar(self):
        """底部状态栏"""
        status_frame = tk.Frame(self.root, bg=BG_DARK, height=28)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)
        status_frame.pack_propagate(False)

        self.topmost_var = tk.BooleanVar(value=False)
        topmost_btn = tk.Checkbutton(
            status_frame,
            text=" 窗口置顶",
            variable=self.topmost_var,
            command=self._toggle_topmost,
            bg=BG_DARK, fg="#DFE6E9",
            selectcolor=BG_DARK,
            activebackground="#2D3436",
            font=FONT_SMALL,
            cursor="hand2",
        )
        topmost_btn.pack(side=tk.LEFT, padx=10)

        version_label = tk.Label(
            status_frame,
            text="抖音：takesitaame  |  竹雨ROCOM小助手 v2.5  |  数据: BiliGame Wiki",
            bg=BG_DARK, fg=TEXT_HINT,
            font=FONT_CAPTION,
        )
        version_label.pack(side=tk.RIGHT, padx=12)

        close_btn = tk.Button(
            status_frame,
            text=" ✕ ",
            command=self.root.destroy,
            bg=BG_DARK, fg=DANGER,
            font=FONT_BODY,
            relief=tk.FLAT,
            cursor="hand2",
            activebackground=BG_DARK,
            activeforeground="#FF4444",
            borderwidth=0,
        )
        close_btn.pack(side=tk.RIGHT, padx=2)

    def _navigate_to_browser(self, url):
        """切换到浏览器面板并导航到指定 URL"""
        for i, (_, text, _) in enumerate(TAB_CONFIG):
            if text == "Wiki":
                self._on_tab_click(i)
                break
        self._panels[i].navigate_to(url)

    def _toggle_topmost(self):
        self.root.attributes("-topmost", self.topmost_var.get())


def run():
    root = tk.Tk()
    app = MainWindow(root)
    root.mainloop()


if __name__ == "__main__":
    run()
