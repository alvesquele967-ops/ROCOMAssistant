"""
竹雨ROCOM小助手 - 官方资讯UI
"""

import tkinter as tk
import os
from tkinter import ttk, messagebox
from core.news_fetcher import NewsFetcher
from ui.theme import (
    PRIMARY, PRIMARY_HOVER, SUCCESS, SUCCESS_HOVER,
    FONT_TITLE, FONT_HEADING, FONT_BODY, FONT_SMALL, FONT_CAPTION,
    PAD_X, BG_CARD, TEXT_HINT,
)


class NewsPanel(ttk.Frame):
    """资讯面板"""

    def __init__(self, parent, **kwargs):
        self.navigate_callback = kwargs.pop("navigate_callback", None)
        super().__init__(parent, **kwargs)
        self.fetcher = NewsFetcher()
        self.all_news = []
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

        self.after(500, self._refresh_news)

    def _build_ui(self):
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=PAD_X, pady=5)

        ttk.Label(header, text="官方资讯", font=FONT_HEADING).pack(side=tk.LEFT)

        tk.Button(
            header, text="刷新资讯",
            font=FONT_BODY, bg=PRIMARY, fg="white",
            activebackground=PRIMARY_HOVER,
            relief=tk.FLAT, cursor="hand2",
            borderwidth=0, padx=12, pady=3,
            command=self._refresh_news,
        ).pack(side=tk.RIGHT, padx=5)

        search_frame = ttk.Frame(self)
        search_frame.pack(fill=tk.X, padx=PAD_X, pady=5)

        ttk.Label(search_frame, text="搜索：", font=FONT_SMALL).pack(side=tk.LEFT)

        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(
            search_frame, textvariable=self.search_var,
            font=FONT_BODY, width=30,
        )
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind("<Return>", lambda e: self._do_search())

        tk.Button(
            search_frame, text="搜索",
            font=FONT_SMALL, bg=SUCCESS, fg="white",
            activebackground=SUCCESS_HOVER,
            relief=tk.FLAT, cursor="hand2",
            borderwidth=0, padx=10, pady=3,
            command=self._do_search,
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            search_frame, text="清除",
            font=FONT_SMALL, bg="#95A5A6", fg="white",
            activebackground="#7F8C8D",
            relief=tk.FLAT, cursor="hand2",
            borderwidth=0, padx=10, pady=3,
            command=self._clear_search,
        ).pack(side=tk.LEFT, padx=2)

        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, padx=PAD_X, pady=3)

        ttk.Label(filter_frame, text="类型：", font=FONT_SMALL).pack(side=tk.LEFT)

        self.filter_var = tk.StringVar(value="全部")
        filter_types = ["全部", "资讯", "公告", "攻略", "讨论"]

        for ft in filter_types:
            tk.Radiobutton(
                filter_frame, text=ft, variable=self.filter_var,
                value=ft, font=FONT_SMALL,
                command=self._apply_filter,
                indicatoron=0, width=8,
                bg="#ECF0F1", selectcolor=PRIMARY,
                fg="black", activeforeground="white",
                relief=tk.FLAT, cursor="hand2",
            ).pack(side=tk.LEFT, padx=1)

        list_frame = ttk.LabelFrame(self, text="资讯列表", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=PAD_X, pady=5)

        self.news_listbox = tk.Listbox(
            list_frame, font=FONT_BODY, selectmode=tk.SINGLE,
            bg=BG_CARD, relief=tk.FLAT, borderwidth=0, highlightthickness=0,
        )
        self.news_listbox.pack(fill=tk.BOTH, expand=True, pady=3)
        self.news_listbox.bind("<<ListboxSelect>>", self._on_news_select)

        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(
            self, textvariable=self.status_var,
            font=FONT_CAPTION, foreground=TEXT_HINT,
        ).pack(side=tk.BOTTOM, fill=tk.X, padx=PAD_X, pady=3)

    def _refresh_news(self):
        self.status_var.set("正在获取最新资讯...")
        self.update()
        try:
            self.all_news = self.fetcher.fetch_all_news(force_refresh=True)
            self._display_news(self.all_news)
            self.status_var.set(f"已更新（{len(self.all_news)} 条）")
        except Exception as e:
            self.status_var.set(f"获取失败: {e}")

    def _display_news(self, news_list):
        self.news_listbox.delete(0, tk.END)
        for item in news_list:
            display = (
                f"[{item.get('type', '未知')}] "
                f"{item.get('date', '????')}  "
                f"{item.get('title', '')}"
            )
            self.news_listbox.insert(tk.END, display)

    def _on_news_select(self, event):
        selection = self.news_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        if idx >= len(self.all_news):
            return

        item = self.all_news[idx]
        url = item.get('url', '')
        if url:
            self._open_link(url)

        dialog = tk.Toplevel(self)
        dialog.title("资讯详情")
        dialog.geometry("600x400")
        dialog.transient(self)

        text = tk.Text(dialog, font=FONT_BODY, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)

        text.insert(tk.END, f"【{item.get('title', '')}】\n\n")
        text.insert(tk.END, f"日期：{item.get('date', '未知')}\n")
        text.insert(tk.END, f"来源：{item.get('source', '未知')}\n")
        text.insert(tk.END, f"类型：{item.get('type', '未知')}\n")

        url_text = item.get('url', '')
        if url_text:
            text.insert(tk.END, "链接：")
            text.insert(tk.END, url_text + "\n", ("link",))
            text.tag_configure("link", foreground="blue", underline=True)
            text.tag_bind("link", "<Button-1>", lambda e, u=url_text: self._open_link(u))
            text.tag_bind("link", "<Enter>", lambda e: text.configure(cursor="hand2"))
            text.tag_bind("link", "<Leave>", lambda e: text.configure(cursor=""))
        else:
            text.insert(tk.END, "链接：无\n")


    def _open_link(self, url):
        if self.navigate_callback:
            self.navigate_callback(url)
        else:
            os.startfile(url)

        text.insert(tk.END, "\n" + "─" * 50 + "\n\n")
        text.insert(tk.END, item.get("description", "暂无详细描述"))
        text.configure(state=tk.DISABLED)

    def _do_search(self):
        keyword = self.search_var.get().strip()
        if not keyword:
            self._refresh_news()
            return
        if not self.all_news:
            self.all_news = self.fetcher.fetch_all_news()

        results = [
            n for n in self.all_news
            if keyword.lower() in n.get("title", "").lower()
            or keyword.lower() in n.get("description", "").lower()
        ]
        self._display_news(results)
        self.status_var.set(f"搜索 '{keyword}'：{len(results)} 条结果")

    def _clear_search(self):
        self.search_var.set("")
        self.filter_var.set("全部")
        self._refresh_news()

    def _apply_filter(self):
        filter_type = self.filter_var.get()
        if filter_type == "全部":
            if self.all_news:
                self._display_news(self.all_news)
            return
        if not self.all_news:
            self.all_news = self.fetcher.fetch_all_news()
        filtered = [n for n in self.all_news if n.get("type") == filter_type]
        self._display_news(filtered)
        self.status_var.set(f"筛选 '{filter_type}'：{len(filtered)} 条")
