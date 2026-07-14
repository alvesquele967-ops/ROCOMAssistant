"""
竹雨ROCOM小助手 - Wiki配队获取器
通过 BiliGame Wiki API 获取精灵阵容数据
支持反爬检测(567)、断点续传、部分保存
"""

import json
import re
import time
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import random
from pathlib import Path

BASE_API = "https://wiki.biligame.com/rocom/api.php"
BASE_RAW = "https://wiki.biligame.com/rocom/index.php?action=raw"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
class PauseRequested(Exception):
    """用户请求暂停时抛出"""
    pass

DELAY = 2.5

# Cookie 持久化 - 维持会话降低被检测风险
_cookie_jar = http.cookiejar.CookieJar()
_cookie_processor = urllib.request.HTTPCookieProcessor(_cookie_jar)
_opener = urllib.request.build_opener(_cookie_processor)
SEARCH_DELAY = 0.8

_TEAM_FILE = Path(__file__).parent.parent / "resources" / "wiki_teams.json"


class AntiBotException(Exception):
    """反爬协议触发异常"""
    def __init__(self, status_code, message="触发了网站反爬协议(HTTP 567)"):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


def _http_get(url, timeout=15, referer=None):
    """HTTP GET 请求，检测反爬状态码，带 Cookie 持久化"""
    req_headers = dict(HEADERS)
    if referer:
        req_headers["Referer"] = referer
    # 额外浏览器指纹头
    req_headers["Sec-Fetch-Site"] = "same-origin"
    req_headers["Sec-Fetch-Mode"] = "navigate"
    req_headers["Sec-Fetch-Dest"] = "document"
    
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with _opener.open(req, timeout=timeout) as resp:
            status = resp.getcode()
            if status == 567:
                raise AntiBotException(567, "触发了网站反爬协议(HTTP 567)，请求被腾讯云EdgeOne拦截")
            body = resp.read().decode("utf-8")
            if not body or len(body.strip()) == 0:
                raise Exception("服务器返回了空响应，可能触发了反爬保护")
            return body
    except urllib.error.HTTPError as e:
        if e.code == 567:
            reason = str(e.reason) if e.reason else "请求被拒绝"
            raise AntiBotException(567, f"触发了网站反爬协议(HTTP {e.code}): {reason}")
        reason = str(e.reason) if e.reason else "未知原因"
        raise Exception(f"HTTP错误 {e.code}: {reason} (URL: {url[:80]})")
    except urllib.error.URLError as e:
        reason = str(e.reason) if e.reason else str(e)
        raise Exception(f"网络连接失败: {reason}")


def search_team_pages():
    """搜索所有精灵阵容页面标题"""
    all_titles = []
    sr_offset = 0
    while True:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": "精灵阵容",
            "format": "json",
            "srlimit": 500,
            "sroffset": sr_offset,
        }
        url = BASE_API + "?" + urllib.parse.urlencode(params)
        data = json.loads(_http_get(url))
        results = data.get("query", {}).get("search", [])
        if not results:
            break
        for r in results:
            title = r["title"]
            if title.startswith("精灵阵容/") and len(title) > 6:
                all_titles.append(title)
        sr_offset += len(results)
        if sr_offset >= data.get("query", {}).get("searchinfo", {}).get("totalhits", 0):
            break
        time.sleep(max(0.2, SEARCH_DELAY + random.uniform(-0.2, 0.2)))
    return all_titles


def fetch_team_wikitext(title):
    """获取单个页面的wikitext - 尝试 parse API 再回退到 raw"""
    # 方案1: 用 parse API (有时比 raw 更难触发反爬)
    encoded = urllib.parse.quote(title)
    referer = "https://wiki.biligame.com/rocom/" + encoded
    parse_url = BASE_API + "?action=parse&page=" + encoded + "&prop=wikitext&format=json"
    try:
        data = json.loads(_http_get(parse_url, referer=referer))
        wikitext = (data.get("parse", {}) or {}).get("wikitext", {}) or {}
        result = wikitext.get("*", "")
        if result:
            return result
    except AntiBotException:
        raise
    except Exception:
        pass
    
    # 方案2: 回退到 action=raw
    raw_url = BASE_RAW + "&title=" + encoded
    return _http_get(raw_url, referer=referer)


def parse_team_template(wikitext):
    """解析 {{精灵阵容|...}} 模板为结构化字典"""
    if not wikitext or "精灵阵容" not in wikitext:
        return None
    match = re.search(r"\{\{精灵阵容(.*?)\}\}", wikitext, re.DOTALL)
    if not match:
        return None
    content = match.group(1)
    team = {}
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        line = line[1:]
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        team[key.strip()] = value.strip()

    members = []
    for i in range(1, 7):
        name_key = "阵容精灵%d" % i
        if name_key not in team:
            break
        pet_name = team.get(name_key, "")
        if not pet_name:
            break
        member = {
            "name": pet_name,
            "bloodline": team.get("阵容精灵%d血脉" % i, "无"),
            "nature": team.get("阵容精灵%d性格" % i, "实干"),
            "individual": team.get("阵容精灵%d个体值" % i, ""),
            "skills": [],
        }
        for s in range(1, 5):
            skill = team.get("阵容精灵%d技能%d" % (i, s), "")
            if skill:
                member["skills"].append({"name": skill})
        members.append(member)

    return {
        "title": team.get("阵容标题", "未知配队"),
        "magic": team.get("阵容血脉魔法", ""),
        "type": team.get("阵容类型", "pvp"),
        "description": team.get("阵容介绍", ""),
        "author": team.get("阵容作者", "未知"),
        "date": team.get("阵容上传日期", ""),
        "wiki_id": team.get("阵容编号", ""),
        "members": members,
    }


def fetch_all_teams(progress_callback=None, pause_check=None):
    """全量获取所有Wiki配队
    返回: (teams_list, was_interrupted, error_message)
    - was_interrupted: True 表示被反爬中断但已保存部分数据
    - error_message: 错误描述
    """
    titles = search_team_pages()
    total = len(titles)
    teams = []
    was_interrupted = False
    error_message = ""

    if progress_callback:
        progress_callback(0, total, "发现 %d 个Wiki配队，开始获取..." % total)

    for i, title in enumerate(titles):
        try:
            wikitext = fetch_team_wikitext(title)
            parsed = parse_team_template(wikitext)
            if parsed:
                parsed["source"] = "wiki"
                parsed["page_title"] = title
                base_name = parsed["title"]
                existing_names = {t["title"] for t in teams}
                final_name = base_name
                counter = 1
                while final_name in existing_names:
                    final_name = "%s(%d)" % (base_name, counter)
                    counter += 1
                parsed["title"] = final_name
                teams.append(parsed)

                # 每5条自动保存一次
                save_teams(teams)  # 每条都保存，确保暂停时数据不丢

            if pause_check:
                pause_check()
            label = parsed["title"] if parsed else "失败: " + title
            if progress_callback:
                progress_callback(i + 1, total, "[%d/%d] %s" % (i + 1, total, label))
            time.sleep(max(0.5, DELAY + random.uniform(-0.8, 0.8)))

        except AntiBotException as e:
            was_interrupted = True
            error_message = str(e)
            if progress_callback:
                progress_callback(i + 1, total, "!!! 反爬拦截: %s (已保存 %d 条)" % (e, len(teams)))
            # 保存已获取的数据
            if teams:
                save_teams(teams)
            break

        except PauseRequested:
            was_interrupted = True
            error_message = "用户暂停"
            if progress_callback:
                progress_callback(i + 1, total, "已暂停 (已保存 %d 个)" % len(teams))
            if teams:
                save_teams(teams)
            break

        except Exception as e:
            if pause_check:
                pause_check()
            if progress_callback:
                progress_callback(i + 1, total, "[%d/%d] 出错: %s" % (i + 1, total, str(e)))
            time.sleep(max(0.5, DELAY + random.uniform(-0.8, 0.8)))

    # 最终保存
    if teams:
        save_teams(teams)
    return teams, was_interrupted, error_message


def fetch_all_teams_resume(progress_callback=None, pause_check=None):
    """从上次中断处继续获取
    返回: (teams_list, was_interrupted, error_message)
    """
    titles = search_team_pages()
    existing = load_teams()
    existing_ids = {t.get("wiki_id", "") for t in existing}
    remaining = [t for t in titles if not any(e.get("page_title") == t for e in existing)]

    if not remaining:
        if progress_callback:
            progress_callback(len(titles), len(titles), "所有配队已获取完毕！")
        return existing, False, ""

    total_new = len(remaining)
    if progress_callback:
        progress_callback(0, total_new, "继续获取剩余 %d 个配队..." % total_new)

    was_interrupted = False
    error_message = ""
    teams = list(existing)

    for i, title in enumerate(remaining):
        try:
            wikitext = fetch_team_wikitext(title)
            parsed = parse_team_template(wikitext)
            if parsed:
                parsed["source"] = "wiki"
                parsed["page_title"] = title
                base_name = parsed["title"]
                existing_names = {t["title"] for t in teams}
                final_name = base_name
                counter = 1
                while final_name in existing_names:
                    final_name = "%s(%d)" % (base_name, counter)
                    counter += 1
                parsed["title"] = final_name
                teams.append(parsed)

                save_teams(teams)  # 每条都保存，确保暂停时数据不丢

            label = parsed["title"] if parsed else "失败: " + title
            if progress_callback:
                progress_callback(i + 1, total_new, "[%d/%d] %s" % (i + 1, total_new, label))
            time.sleep(max(0.5, DELAY + random.uniform(-0.8, 0.8)))

        except AntiBotException as e:
            was_interrupted = True
            error_message = str(e)
            if progress_callback:
                progress_callback(i + 1, total_new, "!!! 反爬拦截: %s (已保存 %d 条)" % (e, len(teams)))
            if teams:
                save_teams(teams)
            break

        except Exception as e:
            if progress_callback:
                progress_callback(i + 1, total_new, "[%d/%d] 出错: %s" % (i + 1, total_new, str(e)))
            time.sleep(max(0.5, DELAY + random.uniform(-0.8, 0.8)))

    if teams:
        save_teams(teams)
    return teams, was_interrupted, error_message


def fetch_random_team():
    """随机获取一个Wiki配队"""
    titles = search_team_pages()
    if not titles:
        return None, "没有找到配队页面"
    title = random.choice(titles)
    try:
        wikitext = fetch_team_wikitext(title)
        parsed = parse_team_template(wikitext)
        if parsed:
            parsed["source"] = "wiki"
            parsed["page_title"] = title
            existing = load_teams()
            existing.append(parsed)
            save_teams(existing)
            return parsed, ""
        else:
            return None, f"无法解析配队模板 (页面: {title})"
    except AntiBotException as e:
        return None, str(e)
    except Exception as e:
        return None, f"获取失败: {e}"


def search_teams_by_pet(pet_name, progress_callback=None, pause_check=None):
    """根据精灵模糊名字搜索配队
    返回: (matched_list, was_interrupted, error_message)
    """
    titles = search_team_pages()
    total = len(titles)
    matched = []
    was_interrupted = False
    error_message = ""

    if progress_callback:
        progress_callback(0, total, "搜索含 '%s' 的配队..." % pet_name)

    for i, title in enumerate(titles):
        try:
            wikitext = fetch_team_wikitext(title)
            if pause_check:
                pause_check()
            if pet_name not in wikitext:
                if progress_callback:
                    progress_callback(i + 1, total, "[%d/%d] 跳过" % (i + 1, total))
                time.sleep(max(0.3, (DELAY * 0.5) + random.uniform(-0.3, 0.3)))
                continue

            parsed = parse_team_template(wikitext)
            if not parsed:
                if progress_callback:
                    progress_callback(i + 1, total, "[%d/%d] 解析失败" % (i + 1, total))
                if pause_check:
                    pause_check()
                time.sleep(max(0.3, (DELAY * 0.5) + random.uniform(-0.3, 0.3)))
                continue

            member_names = [m["name"] for m in parsed.get("members", [])]
            if any(pet_name in mn for mn in member_names):
                parsed["source"] = "wiki"
                parsed["page_title"] = title
                existing = load_teams()
                existing_ids = {t.get("wiki_id", "") for t in existing}
                if parsed.get("wiki_id") not in existing_ids:
                    existing_names = {t["title"] for t in existing}
                    base_name = parsed["title"]
                    final_name = base_name
                    counter = 1
                    while final_name in existing_names:
                        final_name = "%s(%d)" % (base_name, counter)
                        counter += 1
                    parsed["title"] = final_name
                    existing.append(parsed)
                    save_teams(existing)
                matched.append(parsed)

            if pause_check:
                pause_check()
            if progress_callback:
                progress_callback(i + 1, total, "[%d/%d] %s" % (i + 1, total, "匹配" if parsed else "跳过"))
            time.sleep(max(0.5, DELAY + random.uniform(-0.8, 0.8)))

        except AntiBotException as e:
            was_interrupted = True
            error_message = str(e)
            if progress_callback:
                progress_callback(i + 1, total, "!!! 反爬拦截: %s (已匹配 %d 条)" % (e, len(matched)))
            break

        except PauseRequested:
            was_interrupted = True
            error_message = "用户暂停"
            if progress_callback:
                progress_callback(i + 1, total, "已暂停 (已匹配 %d 个)" % len(matched))
            break

        except Exception as e:
            if progress_callback:
                progress_callback(i + 1, total, "[%d/%d] 错误: %s" % (i + 1, total, str(e)))
            time.sleep(max(0.5, DELAY + random.uniform(-0.8, 0.8)))

    return matched, was_interrupted, error_message


def save_teams(teams):
    """保存Wiki配队到本地JSON"""
    _TEAM_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_TEAM_FILE, "w", encoding="utf-8") as f:
        json.dump(teams, f, ensure_ascii=False, indent=2)


def load_teams():
    """从本地JSON加载Wiki配队"""
    if not _TEAM_FILE.exists():
        return []
    try:
        with open(_TEAM_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def get_loaded_count():
    """获取已保存的配队数量"""
    teams = load_teams()
    return len(teams)


def get_total_team_count():
    """获取Wiki上配队页面总数（仅搜索，不下载）"""
    titles = search_team_pages()
    return len(titles)


def fetch_n_teams(n, progress_callback=None, pause_check=None):
    """获取指定数量的Wiki配队（随机选取）
    返回: (teams_list, was_interrupted, error_message)
    """
    titles = search_team_pages()
    total_available = len(titles)
    if n > total_available:
        n = total_available

    # 随机选取 n 个
    selected = random.sample(titles, min(n, total_available))

    teams = []
    was_interrupted = False
    error_message = ""

    if progress_callback:
        progress_callback(0, n, "随机获取 %d/%d 个配队..." % (n, total_available))

    for i, title in enumerate(selected):
        try:
            wikitext = fetch_team_wikitext(title)
            parsed = parse_team_template(wikitext)
            if parsed:
                parsed["source"] = "wiki"
                parsed["page_title"] = title
                base_name = parsed["title"]
                existing_names = {t["title"] for t in teams}
                final_name = base_name
                counter = 1
                while final_name in existing_names:
                    final_name = "%s(%d)" % (base_name, counter)
                    counter += 1
                parsed["title"] = final_name
                teams.append(parsed)
                save_teams(teams)  # 每条都保存，确保暂停时数据不丢

            label = parsed["title"] if parsed else "失败: " + title
            if progress_callback:
                progress_callback(i + 1, n, "[%d/%d] %s" % (i + 1, n, label))
            if pause_check:
                pause_check()
            time.sleep(DELAY)

        except AntiBotException as e:
            was_interrupted = True
            error_message = str(e)
            if progress_callback:
                progress_callback(i + 1, n, "!!! 反爬拦截: %s (已保存 %d 条)" % (e, len(teams)))
            if teams:
                save_teams(teams)
            break

        except PauseRequested:
            was_interrupted = True
            error_message = "用户暂停"
            if progress_callback:
                progress_callback(i + 1, total, "已暂停 (已获取 %d 个)" % len(teams))
            if teams:
                save_teams(teams)
            break

        except Exception as e:
            if progress_callback:
                progress_callback(i + 1, n, "[%d/%d] 出错: %s" % (i + 1, n, str(e)))
            time.sleep(DELAY)

    if teams:
        save_teams(teams)
    return teams, was_interrupted, error_message


def search_teams_by_pet_n(pet_name, n, progress_callback=None, pause_check=None):
    """根据精灵名称搜索配队，最多获取n个匹配结果
    返回: (matched_list, was_interrupted, error_message)
    """
    titles = search_team_pages()
    total = len(titles)
    matched = []
    was_interrupted = False
    error_message = ""

    if progress_callback:
        progress_callback(0, total, "搜索含 '%s' 的配队(最多%d个)..." % (pet_name, n))

    for i, title in enumerate(titles):
        if len(matched) >= n:
            break
        try:
            wikitext = fetch_team_wikitext(title)
            if pet_name not in wikitext:
                if progress_callback:
                    progress_callback(i + 1, total, "[%d/%d] 跳过 (已匹配%d/%d)" % (i + 1, total, len(matched), n))
                if pause_check:
                    pause_check()
                time.sleep(DELAY * 0.5)
                continue

            parsed = parse_team_template(wikitext)
            if not parsed:
                if progress_callback:
                    progress_callback(i + 1, total, "[%d/%d] 解析失败" % (i + 1, total))
                time.sleep(DELAY * 0.5)
                continue

            member_names = [m["name"] for m in parsed.get("members", [])]
            if any(pet_name in mn for mn in member_names):
                parsed["source"] = "wiki"
                parsed["page_title"] = title
                matched.append(parsed)
                # 每匹配到就保存
                existing = load_teams()
                existing_ids = {t.get("wiki_id", "") for t in existing}
                if parsed.get("wiki_id") not in existing_ids:
                    existing_names = {t["title"] for t in existing}
                    base_name = parsed["title"]
                    final_name = base_name
                    counter = 1
                    while final_name in existing_names:
                        final_name = "%s(%d)" % (base_name, counter)
                        counter += 1
                    parsed["title"] = final_name
                    existing.append(parsed)
                    save_teams(existing)

            if progress_callback:
                progress_callback(i + 1, total, "[%d/%d] %s (已匹配%d/%d)" % (i + 1, total, "匹配" if parsed else "跳过", len(matched), n))
            if pause_check:
                pause_check()
            time.sleep(DELAY)

        except AntiBotException as e:
            was_interrupted = True
            error_message = str(e)
            if progress_callback:
                progress_callback(i + 1, total, "!!! 反爬拦截: %s" % e)
            break

        except PauseRequested:
            was_interrupted = True
            error_message = "用户暂停"
            if progress_callback:
                progress_callback(i + 1, total, "已暂停 (已匹配 %d 个)" % len(matched))
            break

        except Exception as e:
            if progress_callback:
                progress_callback(i + 1, total, "[%d/%d] 错误: %s" % (i + 1, total, str(e)))
            time.sleep(DELAY)

    return matched, was_interrupted, error_message


def delete_all_wiki_teams():
    """删除所有网络获取的配队"""
    if _TEAM_FILE.exists():
        _TEAM_FILE.unlink()
    return True


def import_wiki_teams_to_manager(manager):
    """将已保存的Wiki配队导入到TeamManager
    包含完整的作者、日期、类型、介绍等信息
    """
    teams = load_teams()
    imported = 0
    for wt in teams:
        wiki_id = wt.get("wiki_id", "")
        already = False
        for t in manager.teams:
            if t.get("source") == "wiki" and t.get("wiki_id") == wiki_id:
                already = True
                break
        if already:
            continue

        members = []
        for m in wt.get("members", []):
            pet_name = m.get("name", "")
            from core.type_data import get_pet, get_skill
            pet = get_pet(pet_name)

            skills = []
            for sk in m.get("skills", []):
                sk_name = sk.get("name", "")
                gs = get_skill(sk_name)
                if gs:
                    skills.append({
                        "name": sk_name,
                        "attribute": gs.get("attribute", "?"),
                        "category": gs.get("category", "?"),
                        "power": int(gs.get("power", 0)) if str(gs.get("power", "0")).replace("-","").isdigit() else 0,
                        "cost": int(gs.get("cost", 0)) if str(gs.get("cost", "0")).replace("-","").isdigit() else 0,
                    })
                else:
                    skills.append({"name": sk_name, "attribute": "?", "category": "?", "power": 0, "cost": 0})

            # 转换个体值为boosts格式（生命→HP等）
            INDIVIDUAL_MAP = {
                "生命": "HP", "物攻": "物攻", "魔攻": "魔攻",
                "物防": "物防", "魔防": "魔防", "速度": "速度",
            }
            individual_str = m.get("individual", "")
            boosts = []
            if individual_str:
                for part in individual_str.replace("，", ",").split(","):
                    part = part.strip()
                    if part in INDIVIDUAL_MAP:
                        boosts.append(INDIVIDUAL_MAP[part])
                    elif part:
                        boosts.append(part)
            # 补齐到3个
            while len(boosts) < 3:
                boosts.append("无")
            boosts = boosts[:3]

            # bloodline: Wiki的"血脉"对应软件内的"第三血脉"
            member = {
                "name": pet_name,
                "nature": m.get("nature", "实干"),
                "bloodline": m.get("bloodline", "无"),
                "skills": skills,
                "boosts": boosts,
                "note": "个体: " + m.get("individual", "") if m.get("individual") else "",
            }
            if pet:
                member["attributes"] = pet.get("attributes", [])
                member["stats"] = pet.get("stats", {})
                member["no"] = pet.get("no")
                member["ability"] = pet.get("ability", {})
            else:
                member["attributes"] = []
                member["stats"] = {}
                member["ability"] = {}
            members.append(member)

        # 构建团队名称，包含作者和日期信息
        display_name = wt.get("title", "Wiki配队")
        extra_info = wt.get("author", "")
        if extra_info:
            display_name = "%s (@%s)" % (display_name, extra_info)

        team = {
            "name": display_name,
            "members": members,
            "magic": wt.get("magic", ""),
            "source": "wiki",
            "wiki_id": wt.get("wiki_id", ""),
            # 额外Wiki信息
            "wiki_author": wt.get("author", ""),
            "wiki_date": wt.get("date", ""),
            "wiki_type": wt.get("type", ""),
            "wiki_desc": wt.get("description", ""),
        }
        manager.teams.append(team)
        imported += 1

    if imported > 0:
        manager._save()
    return imported
