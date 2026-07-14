"""
竹雨ROCOM小助手 - Wiki爬虫（BiliGame Wiki API 精灵与技能数据）
使用 urllib（标准库），不依赖第三方库

API: https://wiki.biligame.com/rocom/api.php
- action=query&list=categorymembers&cmtitle=Category:精灵 → 精灵页列表（分页）
- action=query&list=categorymembers&cmtitle=Category:技能 → 技能页列表（分页）
- action=parse&page=<title>&prop=wikitext → 页面 wikitext
"""

import json
import time
import re
import os
import http.cookiejar
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from datetime import datetime

# ── 路径 ──────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent
_RESOURCES = _BASE_DIR / "resources"
_OUTPUT_PATH = _RESOURCES / "scraped_pets.json"
_PET_IMG_DIR = _RESOURCES / "images" / "pets"
_SKILL_IMG_DIR = _RESOURCES / "images" / "skills"

# ── 常量 ──────────────────────────────────────────────────────────────
API_URL = "https://wiki.biligame.com/rocom/api.php"
BASE_URL = "https://wiki.biligame.com/rocom/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)
DELAY = 0.5  # 请求间延时（秒）
REQUEST_TIMEOUT = 30  # 单次请求超时（秒）
CATEGORY_LIMIT = 500  # 每页获取数量
MAX_RETRIES = 3  # 单次请求最大重试次数
RETRY_BACKOFF = 2.0  # 重试退避基数（秒）

# ── 全局 opener（带 Cookie 支持） ──
_cookie_jar = http.cookiejar.CookieJar()
_OPENER = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(_cookie_jar)
)
_OPENER_WARMED = False


def _warmup():
    """预热：先访问一次 Wiki 首页获取 Cookie"""
    global _OPENER_WARMED
    if _OPENER_WARMED:
        return
    warm_req = urllib.request.Request(BASE_URL)
    warm_req.add_header("User-Agent", USER_AGENT)
    warm_req.add_header("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
    warm_req.add_header("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.5")
    try:
        _OPENER.open(warm_req, timeout=REQUEST_TIMEOUT)
    except Exception:
        pass
    _OPENER_WARMED = True


# ── 工具函数 ──────────────────────────────────────────────────────────
def _api_call(params: dict) -> dict:
    """调用 Wiki API，返回 JSON 解码后的 dict。带重试和完整浏览器头。"""
    _warmup()

    query_string = urllib.parse.urlencode(params)
    url = f"{API_URL}?{query_string}"

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url)
        req.add_header("User-Agent", USER_AGENT)
        req.add_header("Accept", "application/json, text/javascript, */*; q=0.01")
        req.add_header("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.5")
        req.add_header("Referer", BASE_URL)
        req.add_header("Origin", "https://wiki.biligame.com")
        req.add_header("Connection", "keep-alive")
        req.add_header("Cache-Control", "no-cache")

        try:
            with _OPENER.open(req, timeout=REQUEST_TIMEOUT) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            last_error = RuntimeError(f"API 请求失败: HTTP {e.code} ({e.reason})")
        except urllib.error.URLError as e:
            last_error = RuntimeError(f"API 请求失败: {e}")
        except json.JSONDecodeError as e:
            last_error = RuntimeError(f"API 返回解析失败: {e}")

        if attempt < MAX_RETRIES:
            sleep_time = RETRY_BACKOFF ** attempt
            time.sleep(sleep_time)

    raise last_error


def _fetch_category_members(category: str, progress_callback=None,
                            phase_label: str = "") -> list:
    """
    获取指定分类下的所有页面（处理分页）。
    返回 [(title, pageid), ...] 列表。
    """
    all_pages = []
    cmcontinue = None

    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmlimit": str(CATEGORY_LIMIT),
            "format": "json",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        data = _api_call(params)
        query_data = data.get("query", {})
        members = query_data.get("categorymembers", [])

        for m in members:
            title = m.get("title", "")
            pageid = m.get("pageid", 0)
            if title:
                all_pages.append((title, pageid))

        # 检查是否有更多页
        continue_data = data.get("continue", {})
        cmcontinue = continue_data.get("cmcontinue")
        if not cmcontinue:
            break

        if progress_callback:
            progress_callback(
                phase_label,
                f"获取{category}列表...（已获取 {len(all_pages)} 页）",
                len(all_pages), 0,
            )
        time.sleep(DELAY)

    return all_pages


def _fetch_wikitext(page_title: str) -> str:
    """获取指定页面的 wikitext"""
    params = {
        "action": "parse",
        "page": page_title,
        "prop": "wikitext",
        "format": "json",
    }
    data = _api_call(params)
    parse_data = data.get("parse", {})
    wikitext_data = parse_data.get("wikitext", {})
    result = wikitext_data.get("*", "")
    return result


# ── 模板解析 ──────────────────────────────────────────────────────────
def _parse_template(wikitext: str, template_name: str) -> dict:
    """
    解析 Wiki 模板 {{模板名 ... }}。
    返回字段名→值的 dict。

    处理逻辑：
    1. 正则匹配 {{模板名\n...}}
    2. 按 \n| 分割各字段
    3. 每字段按首个 = 分割键值
    4. 去除首尾空白
    """
    pattern = (
        re.escape("{{" + template_name) +
        r"\s*\n(.*?)" +
        re.escape("}}")
    )
    match = re.search(pattern, wikitext, re.DOTALL)
    if not match:
        return {}

    content = match.group(1)
    # 去除开头的 |
    if content.startswith("|"):
        content = content[1:]

    # 按 \n| 分割字段条目
    raw_entries = re.split(r"\n\|", content)
    result = {}

    for entry in raw_entries:
        # 跳过空条目
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            continue
        # 按首个 = 分割键值
        eq_idx = entry.index("=")
        key = entry[:eq_idx].strip()
        value = entry[eq_idx + 1:].strip()
        result[key] = value

    return result


# ── 图片爬取 ──────────────────────────────────────────────────────────


def _get_page_images(page_title: str) -> list:
    """
    通过 action=parse&prop=images 获取页面所有图片文件名（含模板嵌入的图片）。
    返回裸文件名列表（如 ['页面_宠物_立绘_喵喵_1.png', ...]）。
    自动剥离 MediaWiki 可能返回的 "File:" 前缀。
    """
    params = {
        "action": "parse",
        "page": page_title,
        "prop": "images",
        "format": "json",
    }
    try:
        data = _api_call(params)
        raw_images = data.get("parse", {}).get("images", [])
        cleaned = []
        for img in raw_images:
            # 剥离可能的 "File:" 前缀（部分 MediaWiki 版本会返回完整 File: 标题）
            if img.startswith("File:"):
                img = img[5:]
            cleaned.append(img)
        return cleaned
    except Exception:
        return []


def _download_by_name_patterns(item_name: str, category: str, img_dir: Path) -> list:
    """
    _get_page_images 返回空时的降级方案：直接按常见命名模式构造 File 页面标题并下载。
    """
    import re as _re

    if category == "pet":
        patterns = [
            # Wiki 实际使用格式（优先级最高）
            f"页面_宠物_立绘_{item_name}_1.png",
            f"页面 宠物 立绘 {item_name} 1.png",
            # 通用回退
            f"{item_name}.png",
            f"{item_name} 立绘.png",
            f"{item_name}_立绘.png",
            f"宠物_立绘_{item_name}.png",
            f"宠物 立绘 {item_name}.png",
        ]
    else:
        # 技能：技能图标
        patterns = [
            f"技能图标 {item_name}.png",
            f"技能图标_{item_name}.png",
            f"{item_name}.png",
        ]

    local_paths = []
    safe_item = _re.sub(r'[\\/:*?"<>|]', "_", item_name)

    for i, pattern in enumerate(patterns):
        url = _get_image_url(pattern)
        if not url:
            continue
        ext = os.path.splitext(pattern)[1] or ".png"
        if i == 0:
            save_path = img_dir / f"{safe_item}{ext}"
        else:
            save_path = img_dir / f"{safe_item}_{i+1}{ext}"

        if save_path.exists():
            local_paths.append(str(save_path.resolve()))
            continue

        if _download_image(url, save_path):
            local_paths.append(str(save_path.resolve()))
            break  # 成功下载一张后停止
        time.sleep(0.3)

    return local_paths


def _crawl_images_for_page(page_title: str, category: str, item_name: str) -> list:
    """
    爬取页面上所有相关图片。
    category: "pet" → 筛选「立绘」图；"skill" → 筛选「技能图标」图
    item_name: 精灵名或技能名
    返回本地绝对路径列表
    """
    all_images = _get_page_images(page_title)
    img_dir = _PET_IMG_DIR if category == "pet" else _SKILL_IMG_DIR

    if not all_images:
        return []

    if category == "pet":
        # 仅严格筛选：包含 item_name 且含「立绘」
        targets = [f for f in all_images if "立绘" in f and item_name in f]
        if not targets:
            return []
    else:
        # 仅严格筛选：包含 item_name 且含「技能图标」
        targets = [f for f in all_images if "技能图标" in f and item_name in f]
        if not targets:
            return []

    local_paths = []
    for i, fname in enumerate(targets[:5]):
        # parse API 返回下划线格式，File 页面用空格格式
        file_title = fname.replace("_", " ")
        url = _get_image_url(file_title)
        if not url:
            continue

        safe_item = re.sub(r'[\\/:*?"<>|]', "_", item_name)
        ext = os.path.splitext(fname)[1] or ".png"
        if i == 0:
            save_path = img_dir / f"{safe_item}{ext}"
        else:
            save_path = img_dir / f"{safe_item}_{i+1}{ext}"

        if _download_image(url, save_path):
            local_paths.append(str(save_path.resolve()))
        time.sleep(0.3)

    return local_paths


def _get_image_url(file_name: str):
    """通过 API 获取图片文件的直链 URL。先尝试空格格式（Wiki File 页面常用），
    失败则 fallback 为下划线格式。自动处理可能传入的 File: 前缀。"""
    # 剥离调用方可能传入的 "File:" 前缀
    clean_name = file_name[5:] if file_name.startswith("File:") else file_name

    # 生成候选：空格格式 + 下划线格式
    candidates = [clean_name]
    alt = clean_name.replace(" ", "_")
    if alt != clean_name:
        candidates.append(alt)
    # 反向候选：如果原名已是下划线格式，也尝试空格格式
    if "_" in clean_name and " " not in clean_name:
        candidates.append(clean_name.replace("_", " "))

    for file_title in candidates:
        params = {
            "action": "query",
            "prop": "imageinfo",
            "titles": f"File:{file_title}",
            "iiprop": "url",
            "format": "json",
        }
        try:
            data = _api_call(params)
            pages = data.get("query", {}).get("pages", {})
            for pid, page in pages.items():
                if int(pid) < 0:
                    continue
                ii = page.get("imageinfo", [])
                if ii:
                    return ii[0].get("url")
        except Exception:
            pass
    return None


def _download_image(url: str, save_path: Path) -> bool:
    """从 URL 下载图片到本地，跳过已存在的文件"""
    if save_path.exists():
        return True
    save_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", USER_AGENT)
        req.add_header("Referer", BASE_URL)
        with _OPENER.open(req, timeout=REQUEST_TIMEOUT) as resp:
            data = resp.read()
        if data.startswith(b"<"):
            return False
        save_path.write_bytes(data)
        return True
    except Exception:
        return False


def _parse_pet_wikitext(wikitext: str, title: str = "") -> dict:
    """从精灵页面 wikitext 解析精灵数据（title 为 Wiki 页面标题）"""
    fields = _parse_template(wikitext, "精灵信息")
    if not fields:
        return {}

    name = fields.get("精灵名称", "").strip()
    if not name:
        return {}

    # ── 属性 ──
    main_attr = fields.get("主属性", "").strip()
    sec_attr = fields.get("2属性", "").strip()
    attributes = []
    if main_attr:
        attributes.append(main_attr)
    if sec_attr:
        attributes.append(sec_attr)

    # ── 种族值 ──
    def _parse_int(raw, default=0):
        try:
            return int(raw.strip())
        except (ValueError, AttributeError):
            return default

    hp = _parse_int(fields.get("生命", "0"))
    atk = _parse_int(fields.get("物攻", "0"))
    sp_atk = _parse_int(fields.get("魔攻", "0"))
    defense = _parse_int(fields.get("物防", "0"))
    sp_def = _parse_int(fields.get("魔防", "0"))
    spd = _parse_int(fields.get("速度", "0"))
    total = hp + atk + sp_atk + defense + sp_def + spd

    # ── 技能（逗号分隔，过滤空） ──
    raw_skills = fields.get("技能", "")
    skills = [s.strip() for s in raw_skills.split(",") if s.strip()]

    # ── 血脉技能 ──
    raw_bloodline = fields.get("血脉技能", "")
    bloodline_skills = [s.strip() for s in raw_bloodline.split(",") if s.strip()]

    # ── 技能解锁等级 ──
    raw_unlock = fields.get("技能解锁等级", "")
    skill_unlock_levels = [s.strip() for s in raw_unlock.split(",") if s.strip()]

    # ── 特性 ──
    ability_name = fields.get("特性", "").strip()
    ability_desc = fields.get("特性描述", "").strip()

    # ── 体型 ──
    raw_body = fields.get("体型", "")
    body_parts = [s.strip() for s in raw_body.split(",") if s.strip()]

    # ── 重量 ──
    raw_weight = fields.get("重量", "")
    weight_parts = [s.strip() for s in raw_weight.split(",") if s.strip()]

    # ── 图鉴课题 ──
    quest = fields.get("图鉴课题", "").strip()
    quest_lines = [line.strip() for line in quest.split("\n") if line.strip()] if quest else []

    pet = {
        "name": name,
        "attributes": attributes,
        "stats": {
            "hp": hp,
            "atk": atk,
            "sp_atk": sp_atk,
            "def": defense,
            "sp_def": sp_def,
            "spd": spd,
            "total": total,
        },
        "skills": skills,
        "bloodline_skills": bloodline_skills,
        "ability": {
            "name": ability_name,
            "description": ability_desc,
        },
        # 模板原始字段保留
        "form": fields.get("精灵形态", "").strip() or None,
        "stage": fields.get("精灵阶段", "").strip() or None,
        "pet_type": fields.get("精灵类型", "").strip() or None,
        "pet_desc": fields.get("精灵描述", "").strip() or None,
        "base_name": fields.get("精灵初阶名称", "").strip() or None,
        "body_size": body_parts,
        "weight": weight_parts,
        "quest": quest_lines,
        "quest_stone": fields.get("课题技能石", "").strip() or None,
        "has_shiny": bool(fields.get("是否有异色", "").strip()),
        "skill_unlock_levels": skill_unlock_levels,
        "url": f"https://wiki.biligame.com/rocom/{urllib.parse.quote(name)}",
        # ── 新增字段 ──
        "learnable_stones": [
            s.strip() for s in fields.get("可学技能石", "").split(",") if s.strip()
        ],
        "region_form": fields.get("地区形态名称", "").strip() or None,
        "title": title if title else name,
    }

    return pet


def _parse_skill_wikitext(wikitext: str) -> dict:
    """从技能页面 wikitext 解析技能数据，返回与 CSV 兼容的 dict"""
    fields = _parse_template(wikitext, "技能信息")
    if not fields:
        return {}

    name = fields.get("技能名称", "").strip()
    if not name:
        return {}

    return {
        "技能名": name,
        "属性": fields.get("属性", "").strip(),
        "类型": fields.get("技能类别", "").strip(),
        "耗能": fields.get("耗能", "").strip(),
        "威力": fields.get("威力", "").strip(),
        "效果": fields.get("效果", "").strip(),
        "描述": fields.get("描述", "").strip(),
        "技能版本": fields.get("技能版本", "").strip(),
    }


# ── 缓存信息 ──────────────────────────────────────────────────────────
def _get_cached_time() -> str:
    """获取缓存文件的修改时间"""
    if _OUTPUT_PATH.exists():
        try:
            ts = _OUTPUT_PATH.stat().st_mtime
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return "从未"


def _get_cached_count() -> int:
    """获取缓存中的精灵数量"""
    if _OUTPUT_PATH.exists():
        try:
            with open(_OUTPUT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return len(data.get("pets", []))
        except Exception:
            pass
    return 0


def get_cache_info() -> dict:
    """返回缓存状态信息，供 settings_panel 调用"""
    info = {
        "exists": _OUTPUT_PATH.exists(),
        "time": _get_cached_time(),
        "count": _get_cached_count(),
    }
    # 也统计技能数量
    if _OUTPUT_PATH.exists():
        try:
            with open(_OUTPUT_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            info["skill_count"] = len(data.get("skills", []))
        except Exception:
            info["skill_count"] = 0
    return info


# ── 主爬取流程 ────────────────────────────────────────────────────────
def main(progress_callback=None, force=True):
    """
    执行 Wiki 爬取流程（默认全量模式）。

    参数:
        progress_callback(phase, message, current, total):
            可选进度回调。phase: "init"|"pet_list"|"pet"|"skill_list"|"skill"|"save"
        force:
            True 时全量爬取，忽略已有缓存；False 时只爬取新增精灵/技能

    返回:
        (success: bool, message: str)
    """
    _RESOURCES.mkdir(parents=True, exist_ok=True)

    try:
        # ── 增量模式：读取已有数据 ──
        existing_pets = []
        existing_skills = []
        existing_titles = set()
        existing_skill_names = set()

        if not force and _OUTPUT_PATH.exists():
            with open(_OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            existing_pets = existing_data.get("pets", [])
            existing_skills = existing_data.get("skills", [])
            existing_titles = {p.get("title", "") for p in existing_pets if p.get("title")}
            existing_skill_names = {s.get("技能名", "") for s in existing_skills if s.get("技能名")}

        # ── 步骤 1: 获取精灵页列表 ──
        if progress_callback:
            progress_callback("init", "正在获取精灵页列表...", 0, 0)

        pet_pages = _fetch_category_members(
            "Category:精灵", progress_callback, "pet_list"
        )

        if not pet_pages:
            return False, "未能获取到精灵页面列表"

        # 增量过滤：排除已爬取的精灵（按 title 去重）
        if not force and existing_titles:
            new_pet_count = len(pet_pages)
            pet_pages = [
                (title, pageid) for title, pageid in pet_pages
                if title not in existing_titles
            ]
            if progress_callback:
                progress_callback(
                    "pet_list",
                    f"增量模式：共 {new_pet_count} 只精灵，其中 {len(pet_pages)} 只新增待爬取",
                    len(pet_pages), len(pet_pages),
                )
        else:
            if progress_callback:
                progress_callback(
                    "pet_list",
                    f"获取到 {len(pet_pages)} 个精灵页面，开始逐只爬取...",
                    len(pet_pages), len(pet_pages),
                )

        # ── 步骤 2: 逐只爬取精灵数据 ──
        all_pets = []
        pet_total = len(pet_pages)

        for i, (title, _pageid) in enumerate(pet_pages):
            current = i + 1
            try:
                wikitext = _fetch_wikitext(title)
                pet_data = _parse_pet_wikitext(wikitext, title)
                if pet_data:
                    # 爬取图片
                    pet_name = pet_data.get("name", title)
                    image_paths = _crawl_images_for_page(title, "pet", pet_name)
                    pet_data["image_paths"] = image_paths
                    all_pets.append(pet_data)

                if progress_callback:
                    pet_name = pet_data.get("name", title) if pet_data else title
                    progress_callback(
                        "pet",
                        f"精灵 [{current}/{pet_total}] {pet_name}",
                        current, pet_total,
                    )
            except Exception as e:
                if progress_callback:
                    progress_callback(
                        "pet",
                        f"精灵 [{current}/{pet_total}] {title} (跳过: {e})",
                        current, pet_total,
                    )
            time.sleep(DELAY)

        # ── 步骤 3: 获取技能页列表 ──
        if progress_callback:
            progress_callback("skill_list", "正在获取技能页列表...", 0, 0)

        skill_pages = _fetch_category_members(
            "Category:技能", progress_callback, "skill_list"
        )

        # 增量过滤：排除已爬取的技能
        if not force and existing_skill_names:
            new_skill_count = len(skill_pages)
            skill_pages = [
                (title, pageid) for title, pageid in skill_pages
                if title not in existing_skill_names
            ]
            if progress_callback:
                progress_callback(
                    "skill_list",
                    f"增量模式：共 {new_skill_count} 个技能，其中 {len(skill_pages)} 个新增待爬取",
                    len(skill_pages), len(skill_pages),
                )
        else:
            if progress_callback:
                progress_callback(
                    "skill_list",
                    f"获取到 {len(skill_pages)} 个技能页面，开始逐一获取...",
                    len(skill_pages), len(skill_pages),
                )

        # ── 步骤 4: 逐一获取技能数据 ──
        all_skills = []
        skill_seen = set()
        skill_total = len(skill_pages)

        for i, (title, _pageid) in enumerate(skill_pages):
            current = i + 1
            try:
                wikitext = _fetch_wikitext(title)
                skill_data = _parse_skill_wikitext(wikitext)
                if skill_data:
                    sname = skill_data.get("技能名", "")
                    if sname and sname not in skill_seen:
                        skill_seen.add(sname)
                        # 爬取图片
                        image_paths = _crawl_images_for_page(title, "skill", sname)
                        skill_data["image_paths"] = image_paths
                        all_skills.append(skill_data)

                if progress_callback:
                    progress_callback(
                        "skill",
                        f"技能 [{current}/{skill_total}] {title}",
                        current, skill_total,
                    )
            except Exception as e:
                if progress_callback:
                    progress_callback(
                        "skill",
                        f"技能 [{current}/{skill_total}] {title} (跳过: {e})",
                        current, skill_total,
                    )
            time.sleep(DELAY)

        # ── 无新增内容 ──
        if not all_pets and not all_skills:
            msg = "数据已是最新"
            if progress_callback:
                progress_callback("save", msg, 0, 0)
            return True, msg

        # ── 合并已有数据 ──
        if not force:
            # 按 title 去重合并精灵：已有 + 新增，新增覆盖已有同 title
            merged_pets = {}
            for p in existing_pets:
                t = p.get("title", "")
                if t:
                    merged_pets[t] = p
            for p in all_pets:
                t = p.get("title", "")
                if t:
                    merged_pets[t] = p  # 新增覆盖已有
            all_pets = list(merged_pets.values())
            # 技能去重：已有技能 + 新增技能，按技能名去重
            merged_skills = {s.get("技能名", ""): s for s in existing_skills}
            for s in all_skills:
                sname = s.get("技能名", "")
                if sname:
                    merged_skills[sname] = s
            all_skills = list(merged_skills.values())

        # ── 步骤 5: 保存 ──
        if progress_callback:
            progress_callback("save", "正在保存数据...", 0, 0)

        output = {
            "updated_at": datetime.now().isoformat(),
            "pets": all_pets,
            "skills": all_skills,
            "meta": {
                "pet_count": len(all_pets),
                "skill_count": len(all_skills),
                "source": "BiliGame Wiki API (wiki.biligame.com/rocom)",
            },
        }

        with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        new_pet_str = f"新增 {len(all_pets) - len(existing_pets)} 只精灵" if not force and existing_pets else f"共 {len(all_pets)} 只精灵"
        new_skill_str = f"新增 {len(all_skills) - len(existing_skills)} 个技能" if not force and existing_skills else f"共 {len(all_skills)} 个技能"
        msg = f"爬取完成！{new_pet_str}，{new_skill_str}"
        if progress_callback:
            progress_callback("save", msg, 0, 0)

        return True, msg

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"爬取出错: {e}"


def main_limited(max_pets, progress_callback=None):
    """
    只爬后 max_pets 只精灵，保留已有技能数据。
    覆盖已有数据中对应精灵的旧条目（按 title 匹配替换），技能不变。

    参数:
        max_pets: 爬取的精灵数量上限（从列表末尾取）
        progress_callback: 同 main()
    返回:
        (success: bool, message: str)
    """
    _RESOURCES.mkdir(parents=True, exist_ok=True)

    try:
        # 读取已有数据
        existing_pets = []
        existing_skills = []
        if _OUTPUT_PATH.exists():
            with open(_OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            existing_pets = existing_data.get("pets", [])
            existing_skills = existing_data.get("skills", [])

        # ── 步骤 1: 获取精灵页列表 ──
        if progress_callback:
            progress_callback("init", "正在获取精灵页列表...", 0, 0)

        pet_pages = _fetch_category_members(
            "Category:精灵", progress_callback, "pet_list"
        )
        if not pet_pages:
            return False, "未能获取到精灵页面列表"

        # 截取后 max_pets 只
        pet_pages = pet_pages[-max_pets:]
        if progress_callback:
            progress_callback(
                "pet_list",
                f"爬取后 {len(pet_pages)} 只精灵，开始逐只爬取...",
                len(pet_pages), len(pet_pages),
            )

        # ── 步骤 2: 逐只爬取精灵数据 ──
        all_pets = []
        pet_total = len(pet_pages)

        for i, (title, _pageid) in enumerate(pet_pages):
            current = i + 1
            try:
                wikitext = _fetch_wikitext(title)
                pet_data = _parse_pet_wikitext(wikitext, title)
                if pet_data:
                    pet_name = pet_data.get("name", title)
                    image_paths = _crawl_images_for_page(title, "pet", pet_name)
                    pet_data["image_paths"] = image_paths
                    all_pets.append(pet_data)
                if progress_callback:
                    pet_name = pet_data.get("name", title) if pet_data else title
                    progress_callback(
                        "pet",
                        f"精灵 [{current}/{pet_total}] {pet_name}",
                        current, pet_total,
                    )
            except Exception as e:
                if progress_callback:
                    progress_callback(
                        "pet",
                        f"精灵 [{current}/{pet_total}] {title} (跳过: {e})",
                        current, pet_total,
                    )
            time.sleep(DELAY)

        # ── 合并：已有精灵中未被覆盖的保留，已覆盖的替换 ──
        new_titles = {p.get("title", "") for p in all_pets if p.get("title")}
        # 保留已有中未被覆盖的
        kept_pets = [p for p in existing_pets if p.get("title") not in new_titles]
        all_pets = kept_pets + all_pets

        # 技能直接用已有数据
        all_skills = existing_skills

        # ── 步骤 5: 保存 ──
        if progress_callback:
            progress_callback("save", "正在保存数据...", 0, 0)

        output = {
            "updated_at": datetime.now().isoformat(),
            "pets": all_pets,
            "skills": all_skills,
            "meta": {
                "pet_count": len(all_pets),
                "skill_count": len(all_skills),
                "source": "BiliGame Wiki API (wiki.biligame.com/rocom)",
            },
        }
        with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        msg = f"爬取完成！共 {len(all_pets)} 只精灵，{len(all_skills)} 个技能"
        if progress_callback:
            progress_callback("save", msg, 0, 0)
        return True, msg

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"爬取出错: {e}"


def main_selected(selected_names, progress_callback=None):
    """
    只爬 selected_names 中的精灵 + 所有技能（全量）。
    覆盖已有数据中对应精灵的旧条目（按 title 匹配替换），技能全量覆盖。

    参数:
        selected_names: 精灵名或页面标题列表
        progress_callback: 同 main()
    返回:
        (success: bool, message: str)
    """
    _RESOURCES.mkdir(parents=True, exist_ok=True)

    try:
        name_set = set(n.strip() for n in selected_names if n.strip())
        if not name_set:
            return False, "未指定要爬取的精灵名称"

        # 读取已有数据
        existing_pets = []
        existing_skills = []
        if _OUTPUT_PATH.exists():
            with open(_OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            existing_pets = existing_data.get("pets", [])
            existing_skills = existing_data.get("skills", [])

        # ── 步骤 1: 获取精灵页列表 ──
        if progress_callback:
            progress_callback("init", "正在获取精灵页列表...", 0, 0)

        pet_pages = _fetch_category_members(
            "Category:精灵", progress_callback, "pet_list"
        )
        if not pet_pages:
            return False, "未能获取到精灵页面列表"

        # 过滤出匹配的精灵（按 title 或 name 匹配）
        matched_pages = []
        for title, pageid in pet_pages:
            # 尝试从 title 提取精灵名（Wiki 标题可能是 "精灵名" 或带前缀的）
            for sel_name in name_set:
                if sel_name in title:
                    matched_pages.append((title, pageid))
                    break

        if not matched_pages:
            return False, f"未找到匹配的精灵页面（搜索: {', '.join(sorted(name_set))}）"

        pet_pages = matched_pages
        if progress_callback:
            progress_callback(
                "pet_list",
                f"匹配到 {len(pet_pages)} 只精灵，开始逐只爬取...",
                len(pet_pages), len(pet_pages),
            )

        # ── 步骤 2: 逐只爬取精灵数据 ──
        all_pets = []
        pet_total = len(pet_pages)

        for i, (title, _pageid) in enumerate(pet_pages):
            current = i + 1
            try:
                wikitext = _fetch_wikitext(title)
                pet_data = _parse_pet_wikitext(wikitext, title)
                if pet_data:
                    all_pets.append(pet_data)
                if progress_callback:
                    pet_name = pet_data.get("name", title) if pet_data else title
                    progress_callback(
                        "pet",
                        f"精灵 [{current}/{pet_total}] {pet_name}",
                        current, pet_total,
                    )
            except Exception as e:
                if progress_callback:
                    progress_callback(
                        "pet",
                        f"精灵 [{current}/{pet_total}] {title} (跳过: {e})",
                        current, pet_total,
                    )
            time.sleep(DELAY)

        # ── 步骤 3: 获取技能页列表 ──
        if progress_callback:
            progress_callback("skill_list", "正在获取技能页列表...", 0, 0)

        skill_pages = _fetch_category_members(
            "Category:技能", progress_callback, "skill_list"
        )
        if progress_callback:
            progress_callback(
                "skill_list",
                f"获取到 {len(skill_pages)} 个技能页面，开始逐一获取...",
                len(skill_pages), len(skill_pages),
            )

        # ── 步骤 4: 逐一获取技能数据 ──
        all_skills = []
        skill_seen = set()
        skill_total = len(skill_pages)

        for i, (title, _pageid) in enumerate(skill_pages):
            current = i + 1
            try:
                wikitext = _fetch_wikitext(title)
                skill_data = _parse_skill_wikitext(wikitext)
                if skill_data:
                    sname = skill_data.get("技能名", "")
                    if sname and sname not in skill_seen:
                        skill_seen.add(sname)
                        all_skills.append(skill_data)
                if progress_callback:
                    progress_callback(
                        "skill",
                        f"技能 [{current}/{skill_total}] {title}",
                        current, skill_total,
                    )
            except Exception as e:
                if progress_callback:
                    progress_callback(
                        "skill",
                        f"技能 [{current}/{skill_total}] {title} (跳过: {e})",
                        current, skill_total,
                    )
            time.sleep(DELAY)

        # ── 合并：已有精灵中未被覆盖的保留 ──
        new_titles = {p.get("title", "") for p in all_pets if p.get("title")}
        kept_pets = [p for p in existing_pets if p.get("title") not in new_titles]
        all_pets = kept_pets + all_pets

        # 技能全量覆盖
        merged_skills = {s.get("技能名", ""): s for s in existing_skills}
        for s in all_skills:
            sname = s.get("技能名", "")
            if sname:
                merged_skills[sname] = s
        all_skills = list(merged_skills.values())

        # ── 步骤 5: 保存 ──
        if progress_callback:
            progress_callback("save", "正在保存数据...", 0, 0)

        output = {
            "updated_at": datetime.now().isoformat(),
            "pets": all_pets,
            "skills": all_skills,
            "meta": {
                "pet_count": len(all_pets),
                "skill_count": len(all_skills),
                "source": "BiliGame Wiki API (wiki.biligame.com/rocom)",
            },
        }
        with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        msg = f"爬取完成！共 {len(all_pets)} 只精灵，{len(all_skills)} 个技能（自选 {len(all_pets) - len(kept_pets)} 只）"
        if progress_callback:
            progress_callback("save", msg, 0, 0)
        return True, msg

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"爬取出错: {e}"


def main_skills_only(progress_callback=None, force=False):
    """
    单独爬取所有技能页。从已有 scraped_pets.json 读精灵数据，skills 部分全量替换。
    完成后保存合并结果。

    参数:
        progress_callback: 进度回调
        force: True=全量爬取，False=增量（只爬新增技能）

    返回:
        (success: bool, message: str)
    """
    _RESOURCES.mkdir(parents=True, exist_ok=True)

    try:
        # 读取已有精灵数据 + 已有技能名（增量去重用）
        existing_pets = []
        existing_skills = []
        existing_skill_names = set()
        if _OUTPUT_PATH.exists():
            with open(_OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            existing_pets = existing_data.get("pets", [])
            existing_skills = existing_data.get("skills", [])
            if not force:
                existing_skill_names = {s.get("技能名", "") for s in existing_skills if s.get("技能名")}

        # ── 获取技能页列表 ──
        if progress_callback:
            progress_callback("init", "正在获取技能页列表...", 0, 0)

        skill_pages = _fetch_category_members(
            "Category:技能", progress_callback, "skill_list"
        )
        if not skill_pages:
            return False, "未能获取到技能页面列表"

        # 增量过滤
        if not force and existing_skill_names:
            all_count = len(skill_pages)
            skill_pages = [
                (title, pageid) for title, pageid in skill_pages
                if title not in existing_skill_names
            ]
            if progress_callback:
                progress_callback(
                    "skill_list",
                    f"增量模式：共 {all_count} 个技能，{len(skill_pages)} 个新增待爬取",
                    len(skill_pages), len(skill_pages),
                )
            if not skill_pages:
                return True, f"数据已是最新！所有 {all_count} 个技能均无变化。"

        if not force and progress_callback:
            pass  # 已在上方输出
        elif progress_callback:
            progress_callback(
                "skill_list",
                f"全量模式：获取到 {len(skill_pages)} 个技能页面，开始逐一获取...",
                len(skill_pages), len(skill_pages),
            )

        # ── 逐一获取技能数据 ──
        all_skills = []
        skill_seen = set()
        skill_total = len(skill_pages)

        for i, (title, _pageid) in enumerate(skill_pages):
            current = i + 1
            try:
                wikitext = _fetch_wikitext(title)
                skill_data = _parse_skill_wikitext(wikitext)
                if skill_data:
                    sname = skill_data.get("技能名", "")
                    if sname and sname not in skill_seen:
                        skill_seen.add(sname)
                        all_skills.append(skill_data)
                if progress_callback:
                    progress_callback(
                        "skill",
                        f"技能 [{current}/{skill_total}] {title}",
                        current, skill_total,
                    )
            except Exception as e:
                if progress_callback:
                    progress_callback(
                        "skill",
                        f"技能 [{current}/{skill_total}] {title} (跳过: {e})",
                        current, skill_total,
                    )
            time.sleep(DELAY)

        # ── 保存 ──
        if progress_callback:
            progress_callback("save", "正在保存数据...", 0, 0)

        # 增量模式：合并新技能到已有技能
        if not force and existing_skills:
            skill_by_name = {s.get("技能名", ""): s for s in existing_skills if s.get("技能名")}
            for new_skill in all_skills:
                skill_by_name[new_skill.get("技能名", "")] = new_skill
            all_skills = list(skill_by_name.values())

        output = {
            "updated_at": datetime.now().isoformat(),
            "pets": existing_pets,
            "skills": all_skills,
            "meta": {
                "pet_count": len(existing_pets),
                "skill_count": len(all_skills),
                "source": "BiliGame Wiki API (wiki.biligame.com/rocom)",
            },
        }
        with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        msg = f"技能刷新完成！共 {len(all_skills)} 个技能（精灵数据保持不变）"
        if progress_callback:
            progress_callback("save", msg, 0, 0)
        return True, msg

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"技能爬取出错: {e}"


def main_pets_only(progress_callback=None, force=False):
    """
    单独爬取所有精灵页。从已有 scraped_pets.json 读技能数据，pets 部分全量替换。

    参数:
        progress_callback: 进度回调
        force: True=全量爬取，False=增量（只爬新增精灵）

    返回:
        (success: bool, message: str)
    """
    _RESOURCES.mkdir(parents=True, exist_ok=True)

    try:
        # 读取已有技能数据 + 已有精灵标题（增量去重用）
        existing_skills = []
        existing_pets = []
        existing_titles = set()
        if _OUTPUT_PATH.exists():
            with open(_OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            existing_skills = existing_data.get("skills", [])
            existing_pets = existing_data.get("pets", [])
            if not force:
                existing_titles = {p.get("title", "") for p in existing_pets if p.get("title")}

        # ── 获取精灵页列表 ──
        if progress_callback:
            progress_callback("init", "正在获取精灵页列表...", 0, 0)

        pet_pages = _fetch_category_members(
            "Category:精灵", progress_callback, "pet_list"
        )
        if not pet_pages:
            return False, "未能获取到精灵页面列表"

        # 增量过滤
        if not force and existing_titles:
            all_count = len(pet_pages)
            pet_pages = [
                (title, pageid) for title, pageid in pet_pages
                if title not in existing_titles
            ]
            if progress_callback:
                progress_callback(
                    "pet_list",
                    f"增量模式：共 {all_count} 只精灵，{len(pet_pages)} 只新增待爬取",
                    len(pet_pages), len(pet_pages),
                )
            if not pet_pages:
                return True, f"数据已是最新！所有 {all_count} 只精灵均无变化。"

        if not force and progress_callback:
            pass  # 已在上方输出
        elif progress_callback:
            progress_callback(
                "pet_list",
                f"全量模式：获取到 {len(pet_pages)} 个精灵页面，开始逐只爬取...",
                len(pet_pages), len(pet_pages),
            )

        # ── 逐只爬取精灵数据 ──
        all_pets = []
        pet_total = len(pet_pages)

        for i, (title, _pageid) in enumerate(pet_pages):
            current = i + 1
            try:
                wikitext = _fetch_wikitext(title)
                pet_data = _parse_pet_wikitext(wikitext, title)
                if pet_data:
                    # 爬取图片
                    pet_name = pet_data.get("name", title)
                    image_paths = _crawl_images_for_page(title, "pet", pet_name)
                    pet_data["image_paths"] = image_paths
                    all_pets.append(pet_data)
                if progress_callback:
                    pet_name = pet_data.get("name", title) if pet_data else title
                    progress_callback(
                        "pet",
                        f"精灵 [{current}/{pet_total}] {pet_name}",
                        current, pet_total,
                    )
            except Exception as e:
                if progress_callback:
                    progress_callback(
                        "pet",
                        f"精灵 [{current}/{pet_total}] {title} (跳过: {e})",
                        current, pet_total,
                    )
            time.sleep(DELAY)

        # ── 保存 ──
        if progress_callback:
            progress_callback("save", "正在保存数据...", 0, 0)

        # 增量模式：合并新数据到已有数据
        if not force and existing_pets:
            # 保留已有精灵，用新爬的替换同名精灵
            existing_by_title = {p.get("title", ""): p for p in existing_pets if p.get("title")}
            for new_pet in all_pets:
                existing_by_title[new_pet.get("title", "")] = new_pet
            all_pets = list(existing_by_title.values())

        # 全量模式：保留已有有效图片路径（避免因 Wiki 图片暂不可用而丢失已下载图片）
        if force and existing_pets:
            existing_by_name = {}
            for p in existing_pets:
                name = p.get("name", "")
                imgs = p.get("image_paths", [])
                if name and imgs:
                    existing_by_name[name] = [ip for ip in imgs if os.path.exists(ip)]
            for pet in all_pets:
                name = pet.get("name", "")
                if not pet.get("image_paths") and name in existing_by_name:
                    valid = existing_by_name[name]
                    if valid:
                        pet["image_paths"] = valid

        output = {
            "updated_at": datetime.now().isoformat(),
            "pets": all_pets,
            "skills": existing_skills,
            "meta": {
                "pet_count": len(all_pets),
                "skill_count": len(existing_skills),
                "source": "BiliGame Wiki API (wiki.biligame.com/rocom)",
            },
        }
        with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        msg = f"精灵刷新完成！共 {len(all_pets)} 只精灵（技能数据保持不变）"
        if progress_callback:
            progress_callback("save", msg, 0, 0)
        return True, msg

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"精灵爬取出错: {e}"


def main_selected_skills(skill_names, progress_callback=None):
    """
    只爬取指定技能名列表的技能页面。精灵数据保持不变。

    参数:
        skill_names: 技能名列表（逗号分隔的字符串或列表）
        progress_callback: 同 main()
    返回:
        (success: bool, message: str)
    """
    _RESOURCES.mkdir(parents=True, exist_ok=True)

    try:
        if isinstance(skill_names, str):
            name_set = set(s.strip() for s in skill_names.split(",") if s.strip())
        else:
            name_set = set(s.strip() for s in skill_names if s.strip())

        if not name_set:
            return False, "未指定要爬取的技能名称"

        # 读取已有数据（精灵保持不变）
        existing_pets = []
        existing_skills = []
        if _OUTPUT_PATH.exists():
            with open(_OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing_data = json.load(f)
            existing_pets = existing_data.get("pets", [])
            existing_skills = existing_data.get("skills", [])

        # ── 获取技能页列表 ──
        if progress_callback:
            progress_callback("init", "正在获取技能页列表...", 0, 0)

        skill_pages = _fetch_category_members(
            "Category:技能", progress_callback, "skill_list"
        )
        if not skill_pages:
            return False, "未能获取到技能页面列表"

        # 过滤出匹配的技能
        matched_pages = []
        for title, pageid in skill_pages:
            for sel_name in name_set:
                if sel_name in title:
                    matched_pages.append((title, pageid))
                    break

        if not matched_pages:
            return False, f"未找到匹配的技能页面（搜索: {', '.join(sorted(name_set))}）"

        skill_pages = matched_pages
        if progress_callback:
            progress_callback(
                "skill_list",
                f"匹配到 {len(skill_pages)} 个技能页面，开始逐一获取...",
                len(skill_pages), len(skill_pages),
            )

        # ── 逐一获取技能数据 ──
        all_skills = []
        skill_seen = set()
        skill_total = len(skill_pages)

        for i, (title, _pageid) in enumerate(skill_pages):
            current = i + 1
            try:
                wikitext = _fetch_wikitext(title)
                skill_data = _parse_skill_wikitext(wikitext)
                if skill_data:
                    sname = skill_data.get("技能名", "")
                    if sname and sname not in skill_seen:
                        skill_seen.add(sname)
                        all_skills.append(skill_data)
                if progress_callback:
                    progress_callback(
                        "skill",
                        f"技能 [{current}/{skill_total}] {title}",
                        current, skill_total,
                    )
            except Exception as e:
                if progress_callback:
                    progress_callback(
                        "skill",
                        f"技能 [{current}/{skill_total}] {title} (跳过: {e})",
                        current, skill_total,
                    )
            time.sleep(DELAY)

        # ── 合并技能：已有技能中被替换的更新，其余保留 ──
        new_skill_names = {s.get("技能名", "") for s in all_skills if s.get("技能名")}
        kept_skills = [s for s in existing_skills if s.get("技能名") not in new_skill_names]
        all_skills = kept_skills + all_skills

        # ── 保存 ──
        if progress_callback:
            progress_callback("save", "正在保存数据...", 0, 0)

        output = {
            "updated_at": datetime.now().isoformat(),
            "pets": existing_pets,
            "skills": all_skills,
            "meta": {
                "pet_count": len(existing_pets),
                "skill_count": len(all_skills),
                "source": "BiliGame Wiki API (wiki.biligame.com/rocom)",
            },
        }
        with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        msg = f"技能刷新完成！共 {len(all_skills)} 个技能（自选更新 {len(all_skills) - len(kept_skills)} 个）"
        if progress_callback:
            progress_callback("save", msg, 0, 0)
        return True, msg

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"技能爬取出错: {e}"


def quick_refresh(progress_callback=None):
    """
    快速刷新入口 - main 的别名（增量模式）。
    """
    return main(progress_callback=progress_callback)


def force_refresh(progress_callback=None):
    """
    强制全量刷新入口 - 供 settings_panel 的"强制全量刷新"按钮调用。
    忽略已有缓存，全量重新爬取所有精灵和技能。
    """
    return main(progress_callback=progress_callback, force=True)


def fetch_single_pet(name, progress_callback=None):
    """
    按名称爬取单个精灵数据。
    参数:
        name: 精灵名称
        progress_callback: 进度回调
    返回:
        pet dict 或 None
    """
    try:
        if progress_callback:
            progress_callback("init", f"正在搜索精灵「{name}」...", 0, 0)

        # 获取所有精灵页面
        pet_pages = _fetch_category_members("Category:精灵", None, None)
        if not pet_pages:
            return None

        # 按名称匹配
        for title, pageid in pet_pages:
            if name in title:
                if progress_callback:
                    progress_callback("pet", f"正在获取「{name}」数据...", 0, 0)

                wikitext = _fetch_wikitext(title)
                pet_data = _parse_pet_wikitext(wikitext, title)
                if pet_data:
                    # 爬取图片
                    pet_name = pet_data.get("name", title)
                    image_paths = _crawl_images_for_page(title, "pet", pet_name)
                    pet_data["image_paths"] = image_paths
                    if progress_callback:
                        progress_callback("pet", f"已获取「{name}」", 1, 1)
                    return pet_data

        return None
    except Exception:
        import traceback
        traceback.print_exc()
        return None


def delete_cache() -> tuple:
    """删除缓存的 scraped_pets.json 和所有图片。返回 (success, message)。"""
    import os, glob

    removed = []
    errors = []

    # 删除主数据文件
    if _OUTPUT_PATH.exists():
        try:
            _OUTPUT_PATH.unlink()
            removed.append(str(_OUTPUT_PATH))
        except Exception as e:
            errors.append(f"数据文件: {e}")

    # 删除精灵图片
    if _PET_IMG_DIR.exists():
        for f in _PET_IMG_DIR.iterdir():
            try:
                f.unlink()
                removed.append(str(f))
            except Exception as e:
                errors.append(f"图片 {f.name}: {e}")

    # 删除技能图片
    if _SKILL_IMG_DIR.exists():
        for f in _SKILL_IMG_DIR.iterdir():
            try:
                f.unlink()
                removed.append(str(f))
            except Exception as e:
                errors.append(f"图片 {f.name}: {e}")

    if not removed and not errors:
        return True, "没有需要删除的缓存数据。"
    if errors:
        return False, f"已删除 {len(removed)} 个文件，但有 {len(errors)} 个错误: {'; '.join(errors[:3])}"
    return True, f"已删除 {len(removed)} 个缓存文件（数据 + 图片）"


def main_images_only(progress_callback=None, mode="all"):
    """
    仅下载精灵和技能图片（基于已有的 scraped_pets.json 数据）。
    不重新爬取数据，只补全缺失的图片。

    mode: "all"（默认，精灵+技能）/ "pets"（仅精灵）/ "skills"（仅技能）


    返回:
        (success: bool, message: str)
    """
    _PET_IMG_DIR.mkdir(parents=True, exist_ok=True)
    _SKILL_IMG_DIR.mkdir(parents=True, exist_ok=True)

    try:
        if not _OUTPUT_PATH.exists():
            return False, "尚未爬取过数据，请先刷新精灵或技能数据。"

        with open(_OUTPUT_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        pets = data.get("pets", [])
        pet_total = len(pets)
        pet_downloaded = 0
        pet_skipped = 0
        # ── 精灵图片处理 ──
        if mode in ("all", "pets"):
            # ── 获取精灵页列表用于匹配 ──
            if progress_callback:
                progress_callback("init", "正在获取精灵页列表...", 0, 0)

            pet_pages = _fetch_category_members(
                "Category:精灵", progress_callback, "pet_list"
            )
            # 建立 name → title 映射
            name_to_title = {}
            if pet_pages:
                for title, pageid in pet_pages:
                    name_to_title[title] = title

            for i, pet in enumerate(pets):
                pet_name = pet.get("name", "")
                current = i + 1

                # 找到对应的页面标题（优先精确匹配，其次模糊匹配）
                page_title = pet.get("title", pet_name) or pet_name

                # 检查是否已有图片
                existing = pet.get("image_paths", [])
                if existing:
                    existing_valid = [p for p in existing if os.path.exists(p)]
                    if existing_valid:
                        pet_skipped += 1
                        if progress_callback:
                            progress_callback(
                                "pet",
                                f"图片 [{current}/{pet_total}] {pet_name} (已有，跳过)",
                                current, pet_total,
                            )
                        continue

                # 磁盘级别比对
                    safe_item = re.sub(r'[\\/:*?"<>|]', '_', pet_name)
                    disk_files = sorted(
                    list(_PET_IMG_DIR.glob(f"{safe_item}.*"))
                    + list(_PET_IMG_DIR.glob(f"{safe_item}_*.*"))
                    )
                    if disk_files:
                        pet["image_paths"] = [str(f.resolve()) for f in disk_files]
                        pet_skipped += 1
                        if progress_callback:
                            progress_callback(
                                "pet",
                                f"图片 [{current}/{pet_total}] {pet_name} (磁盘已有，跳过)",
                                current, pet_total,
                            )
                        continue

                if progress_callback:
                    progress_callback(
                        "pet",
                        f"图片 [{current}/{pet_total}] {pet_name}",
                        current, pet_total,
                    )

                try:
                    image_paths = _crawl_images_for_page(page_title, "pet", pet_name)
                    pet["image_paths"] = image_paths
                    if image_paths:
                        pet_downloaded += 1
                except Exception:
                    pass
                time.sleep(DELAY)

        # ── 技能图片处理 ──
        if mode in ("all", "skills"):
            skills = data.get("skills", [])
            skill_total = len(skills)
            skill_downloaded = 0
            skill_skipped = 0

            if skill_total > 0:
                if progress_callback:
                    progress_callback("init", "正在获取技能页列表...", 0, 0)

                skill_pages = _fetch_category_members(
                    "Category:技能", progress_callback, "skill_list"
                )
                skill_name_to_title = {}
                if skill_pages:
                    for title, pageid in skill_pages:
                        skill_name_to_title[title] = title

                for i, skill in enumerate(skills):
                    skill_name = skill.get("技能名", skill.get("name", ""))
                    current = i + 1

                    page_title = skill.get("title", skill_name) or skill_name

                    # 检查 image_paths 字段
                    existing = skill.get("image_paths", [])
                    if existing:
                        existing_valid = [p for p in existing if os.path.exists(p)]
                        if existing_valid:
                            skill_skipped += 1
                            if progress_callback:
                                progress_callback(
                                    "skill",
                                    f"技能图片 [{current}/{skill_total}] {skill_name} (已有，跳过)",
                                    current, skill_total,
                                )
                            continue

                    # 磁盘级别比对
                    safe_item = re.sub(r'[\\/:*?"<>|]', '_', skill_name)
                    disk_files = sorted(
                        list(_SKILL_IMG_DIR.glob(f"{safe_item}.*"))
                        + list(_SKILL_IMG_DIR.glob(f"{safe_item}_*.*"))
                    )
                    if disk_files:
                        skill["image_paths"] = [str(f.resolve()) for f in disk_files]
                        skill_skipped += 1
                        if progress_callback:
                            progress_callback(
                                "skill",
                                f"技能图片 [{current}/{skill_total}] {skill_name} (磁盘已有，跳过)",
                                current, skill_total,
                            )
                        continue

                    if progress_callback:
                        progress_callback(
                            "skill",
                            f"技能图片 [{current}/{skill_total}] {skill_name}",
                            current, skill_total,
                        )

                    try:
                        image_paths = _crawl_images_for_page(page_title, "skill", skill_name)
                        skill["image_paths"] = image_paths
                        if image_paths:
                            skill_downloaded += 1
                    except Exception:
                        pass
                    time.sleep(DELAY)

        # 保存更新后的数据
        with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


        # 根据 mode 生成消息
        parts = []
        total_count = 0
        if mode in ("all", "pets"):
            parts.append(f"精灵: {pet_downloaded} 只新下载, {pet_skipped} 只已有")
            total_count += pet_total
        if mode in ("all", "skills"):
            parts.append(f"技能: {skill_downloaded} 个新下载, {skill_skipped} 个已有")
            total_count += skill_total
        msg = "图片下载完成！" + " | ".join(parts)
        if progress_callback:
            progress_callback(
                "save",
                msg,
                total_count, total_count,
            )

        return True, msg

    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, f"图片下载出错: {e}"


if __name__ == "__main__":
    ok, msg = main()
    print(msg)