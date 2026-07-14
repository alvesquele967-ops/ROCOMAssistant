"""
竹雨ROCOM小助手 - 属性克制数据（重构版）
从 sprites.json 动态加载真实精灵/属性数据，兜底使用硬编码表
"""

import json
import csv
import os
import atexit
import re
from pathlib import Path
from collections import defaultdict

# ── 路径 ──────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent
_RESOURCES = _BASE_DIR / "resources"
_SPRITES_PATH = _RESOURCES / "sprites.json"
_SKILLS_PATH = _RESOURCES / "skills_all.csv"
_SCRAPED_PATH = _RESOURCES / "scraped_pets.json"
_TEMP_CACHE_PATH = _RESOURCES / "temp_scraped_pets.json"

# ── 属性列表（18种）─────────────────────────────────────────────────
ALL_TYPES = [
    "普通", "草", "火", "水", "光", "地", "冰", "龙",
    "电", "毒", "虫", "武", "翼", "萌", "幽", "恶", "幻", "机械"
]

# ── 临时缓存 ──────────────────────────────────────────────────────────
_temp_cache = {"pets": [], "skills": []}

def _load_temp_cache():
    global _temp_cache
    if _TEMP_CACHE_PATH.exists():
        try:
            with open(_TEMP_CACHE_PATH, "r", encoding="utf-8") as f:
                _temp_cache = json.load(f)
        except:
            _temp_cache = {"pets": [], "skills": []}

def _save_temp_cache():
    _RESOURCES.mkdir(parents=True, exist_ok=True)
    with open(_TEMP_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(_temp_cache, f, ensure_ascii=False, indent=2)

def add_temp_pet(pet_data):
    """添加单个精灵到临时缓存（含技能规范化）"""
    _ensure_loaded()
    _load_temp_cache()
    pets = _temp_cache.get("pets", [])
    title = pet_data.get("title", "")

    # ── 技能字符串→dict 规范化（与 _ensure_loaded 中逻辑一致）──
    pet = dict(pet_data)  # 浅拷贝，避免修改原数据

    # 主技能
    raw_skills = pet.get("skills", [])
    converted = []
    for s in raw_skills:
        if isinstance(s, str):
            sd = _skills_by_name.get(s)
            converted.append(sd if sd else s)
        else:
            converted.append(s)
    pet["skills"] = converted

    # 血脉技能
    raw_bl = pet.get("bloodline_skills", [])
    converted_bl = []
    for s in raw_bl:
        if isinstance(s, str):
            sd = _skills_by_name.get(s)
            converted_bl.append(sd if sd else s)
        else:
            converted_bl.append(s)
    pet["bloodline_skills"] = converted_bl

    # 课题技能石
    stone = pet.get("quest_stone")
    quest_stones = []
    if stone and isinstance(stone, str) and stone.strip() not in ("", "-", "null"):
        for s in stone.split(","):
            s = s.strip()
            if s and s not in ("", "-", "null"):
                sd = _skills_by_name.get(s)
                quest_stones.append(sd if sd else s)
    pet["quest_stones"] = quest_stones

    # 可学技能石
    raw_learnable = pet.get("learnable_stones", [])
    converted_ls = []
    if raw_learnable:
        for s in raw_learnable:
            if isinstance(s, str):
                sd = _skills_by_name.get(s)
                converted_ls.append(sd if sd else s)
            else:
                converted_ls.append(s)
    pet["learnable_stones"] = converted_ls

    # ── 写入临时缓存 ──
    pets = [p for p in pets if p.get("title") != title]
    pets.append(pet)
    _temp_cache["pets"] = pets
    _save_temp_cache()

def clear_temp_cache():
    """清理临时缓存"""
    if _TEMP_CACHE_PATH.exists():
        try:
            os.remove(_TEMP_CACHE_PATH)
        except:
            pass

atexit.register(clear_temp_cache)

# ── 兜底硬编码克制表 ──────────────────────────────────────────────────
_TYPE_RELATIONS_HARD = {
    "普通": {"attack_2x": [], "attack_half": ["地","幽","机械"], "defend_2x": ["武"], "defend_half": ["幽"], "immune_from": []},
    "草": {"attack_2x": ["水","光","地"], "attack_half": ["火","龙","毒","虫","翼","机械"], "defend_2x": ["火","冰","毒","虫","翼"], "defend_half": ["水","地","电","光"], "immune_from": []},
    "火": {"attack_2x": ["草","冰","虫","机械"], "attack_half": ["水","地","龙"], "defend_2x": ["水","地"], "defend_half": ["草","冰","虫","萌","机械"], "immune_from": []},
    "水": {"attack_2x": ["火","地","机械"], "attack_half": ["草","冰","龙"], "defend_2x": ["草","电"], "defend_half": ["火","机械"], "immune_from": []},
    "光": {"attack_2x": ["幽","恶"], "attack_half": ["草","冰"], "defend_2x": ["草","幽"], "defend_half": ["恶","幻"], "immune_from": []},
    "地": {"attack_2x": ["火","冰","电","毒"], "attack_half": ["草","武"], "defend_2x": ["草","水","冰","武","机械"], "defend_half": ["普通","火","电","毒","翼"], "immune_from": []},
    "冰": {"attack_2x": ["草","地","龙","翼"], "attack_half": ["火","冰","机械"], "defend_2x": ["火","地","武","机械"], "defend_half": ["水","光","冰"], "immune_from": []},
    "龙": {"attack_2x": ["龙"], "attack_half": ["机械"], "defend_2x": ["冰","龙","萌"], "defend_half": ["草","火","水","电","翼"], "immune_from": []},
    "电": {"attack_2x": ["水","翼"], "attack_half": ["草","地","龙","电"], "defend_2x": ["地"], "defend_half": ["电","翼","机械"], "immune_from": []},
    "毒": {"attack_2x": ["草","萌"], "attack_half": ["地","毒","幽","机械"], "defend_2x": ["地","恶","幻"], "defend_half": ["草","毒","虫","武","萌"], "immune_from": []},
    "虫": {"attack_2x": ["草","恶","幻"], "attack_half": ["火","毒","武","翼","萌","幽","机械"], "defend_2x": ["火","翼"], "defend_half": ["草","武"], "immune_from": []},
    "武": {"attack_2x": ["普通","地","冰","恶","机械"], "attack_half": ["毒","虫","翼","萌","幽","幻"], "defend_2x": ["翼","萌","幻"], "defend_half": ["地","虫","恶"], "immune_from": []},
    "翼": {"attack_2x": ["草","虫","武"], "attack_half": ["地","龙","电","机械"], "defend_2x": ["冰","电"], "defend_half": ["草","虫","武"], "immune_from": []},
    "萌": {"attack_2x": ["龙","武","恶"], "attack_half": ["火","毒","机械"], "defend_2x": ["毒","恶","机械"], "defend_half": ["虫","武"], "immune_from": []},
    "幽": {"attack_2x": ["光","幽","幻"], "attack_half": ["普通","恶"], "defend_2x": ["光","幽","恶"], "defend_half": ["普通","毒","虫","武"], "immune_from": []},
    "恶": {"attack_2x": ["毒","萌","幽"], "attack_half": ["光","武","恶"], "defend_2x": ["光","虫","武","萌"], "defend_half": ["幽","恶"], "immune_from": []},
    "幻": {"attack_2x": ["毒","武"], "attack_half": ["幽","幻"], "defend_2x": ["虫","幽"], "defend_half": ["光","武","恶"], "immune_from": []},
    "机械": {"attack_2x": ["地","冰","萌"], "attack_half": ["火","水","电","机械"], "defend_2x": ["火","水","武"], "defend_half": ["普通","草","冰","龙","毒","虫","翼","萌","机械","幻"], "immune_from": []},
}

_SPECIAL_RULES = {
    "双向克制": [("光","幽"), ("萌","恶")],
    "龙系特殊": "龙打龙2倍，龙被龙/冰/萌2倍；龙抵抗草/火/水/电/翼",
    "机械肉盾": "只被火/水/武克制，抵抗10种属性（肉盾首选）",
    "普通系": "无克制，仅被武系克制，抵抗幽系",
}

# 性格修正表
NATURES = {
    "沉默": {"生命": 1.1, "物攻": 0.9},
    "平和": {"生命": 1.1, "魔攻": 0.9},
    "忧郁": {"生命": 1.1, "物防": 0.9},
    "粗心": {"生命": 1.1, "魔防": 0.9},
    "踏实": {"生命": 1.1, "速度": 0.9},
    "大胆": {"物攻": 1.1, "物防": 0.9},
    "调皮": {"物攻": 1.1, "魔防": 0.9},
    "勇敢": {"物攻": 1.1, "速度": 0.9},
    "逞强": {"物攻": 1.1, "生命": 0.9},
    "固执": {"物攻": 1.1, "魔攻": 0.9},
    "聪明": {"魔攻": 1.1, "物攻": 0.9},
    "专注": {"魔攻": 1.1, "物防": 0.9},
    "偏执": {"魔攻": 1.1, "魔防": 0.9},
    "冷静": {"魔攻": 1.1, "速度": 0.9},
    "理性": {"魔攻": 1.1, "生命": 0.9},
    "胆小": {"速度": 1.1, "物攻": 0.9},
    "开朗": {"速度": 1.1, "魔攻": 0.9},
    "急躁": {"速度": 1.1, "物防": 0.9},
    "莽撞": {"速度": 1.1, "魔防": 0.9},
    "热情": {"速度": 1.1, "生命": 0.9},
    "稳重": {"物防": 1.1, "物攻": 0.9},
    "天真": {"物防": 1.1, "魔攻": 0.9},
    "悠闲": {"物防": 1.1, "速度": 0.9},
    "懒散": {"物防": 1.1, "魔防": 0.9},
    "坦率": {"物防": 1.1, "生命": 0.9},
    "警惕": {"魔防": 1.1, "物攻": 0.9},
    "害羞": {"魔防": 1.1, "魔攻": 0.9},
    "温顺": {"魔防": 1.1, "物防": 0.9},
    "慎重": {"魔防": 1.1, "速度": 0.9},
    "焦虑": {"魔防": 1.1, "生命": 0.9},
}
NATURE_NAMES = [
    "沉默", "平和", "忧郁", "粗心", "踏实",
    "大胆", "调皮", "勇敢", "逞强", "固执",
    "聪明", "专注", "偏执", "冷静", "理性",
    "胆小", "开朗", "急躁", "莽撞", "热情",
    "稳重", "天真", "悠闲", "懒散", "坦率",
    "警惕", "害羞", "温顺", "慎重", "焦虑",
]

# ── 内存缓存 ──────────────────────────────────────────────────────────
_pets_by_name = {}
_pets_list = []
_skills_by_name = {}
_skills_list = []
_type_matchup_cache = None
_loaded = False


def _ensure_loaded():
    global _loaded, _pets_by_name, _pets_list, _skills_by_name, _skills_list
    if _loaded:
        return

    # 优先从爬取的实时数据加载
    if _SCRAPED_PATH.exists():
        with open(_SCRAPED_PATH, "r", encoding="utf-8") as f:
            scraped = json.load(f)

        # 先加载技能数据到 _skills_by_name（后续做技能名→dict 映射时需要）
        # 同时做字段名归一化：Wiki 爬虫用中文键名，team_panel 用英文键名
        _FIELD_MAP = {
            "技能名": "name", "属性": "attribute", "类型": "category",
            "耗能": "cost", "威力": "power", "效果": "effect", "描述": "description",
            "技能版本": "skill_version",
        }
        skills_data = scraped.get("skills", [])
        for row in skills_data:
            normalized = {}
            for cn_key, en_key in _FIELD_MAP.items():
                if cn_key in row:
                    normalized[en_key] = row[cn_key]
            # 保留原始中文键名作为兜底
            for k, v in row.items():
                if k not in _FIELD_MAP:
                    normalized[k] = v
            name = normalized.get("name", "").strip()
            if name:
                _skills_by_name[name] = normalized
        _skills_list = list(_skills_by_name.values())

        # 加载精灵数据，并将每个精灵的 skills（字符串列表）转换为技能 dict 列表
        _pets_list = scraped.get("pets", [])
        for p in _pets_list:
            name = p.get("name", "")
            if name:
                _pets_by_name.setdefault(name, []).append(p)
            # 技能名→技能dict 转换
            raw_skills = p.get("skills", [])
            converted = []
            for s in raw_skills:
                if isinstance(s, str):
                    skill_dict = _skills_by_name.get(s)
                    if skill_dict:
                        converted.append(skill_dict)
                    else:
                        # 兜底：找不到对应技能 dict 时保留原字符串
                        converted.append(s)
                else:
                    # 已经是 dict，保持不变
                    converted.append(s)
            p["skills"] = converted

            # 血脉技能转换
            raw_bloodline = p.get("bloodline_skills", [])
            converted_bl = []
            for s in raw_bloodline:
                if isinstance(s, str):
                    sd = _skills_by_name.get(s)
                    converted_bl.append(sd if sd else s)
                else:
                    converted_bl.append(s)
            p["bloodline_skills"] = converted_bl

            # 课题技能石转换（逗号分隔解析）
            stone = p.get("quest_stone")
            quest_stones = []
            if stone and isinstance(stone, str) and stone.strip() not in ("", "-", "null"):
                for s in stone.split(","):
                    s = s.strip()
                    if s and s not in ("", "-", "null"):
                        sd = _skills_by_name.get(s)
                        quest_stones.append(sd if sd else s)
            p["quest_stones"] = quest_stones

            # 可学技能石转换
            raw_learnable = p.get("learnable_stones", [])
            converted_ls = []
            if raw_learnable:
                for s in raw_learnable:
                    if isinstance(s, str):
                        sd = _skills_by_name.get(s)
                        converted_ls.append(sd if sd else s)
                    else:
                        converted_ls.append(s)
            p["learnable_stones"] = converted_ls
        _loaded = True
        return

    # 兜底：从原始静态文件加载
    if _SPRITES_PATH.exists():
        with open(_SPRITES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        _pets_list = data
        for p in data:
            name = p.get("name", "")
            if name:
                _pets_by_name.setdefault(name, []).append(p)
    if _SKILLS_PATH.exists():
        _FIELD_MAP = {
            "技能名": "name", "属性": "attribute", "类型": "category",
            "耗能": "cost", "威力": "power", "效果": "effect", "描述": "description",
            "技能版本": "skill_version",
        }
        with open(_SKILLS_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("技能名", "").strip()
                if not name:
                    continue
                normalized = {}
                for cn_key, en_key in _FIELD_MAP.items():
                    if cn_key in row:
                        normalized[en_key] = row[cn_key]
                for k, v in row.items():
                    if k not in _FIELD_MAP:
                        normalized[k] = v
                _skills_by_name[name] = normalized
        _skills_list = list(_skills_by_name.values())
    _loaded = True


def reload():
    """强制清除缓存并重新加载数据（配合爬虫刷新使用）"""
    global _loaded, _pets_by_name, _pets_list, _skills_by_name, _skills_list
    _loaded = False
    _pets_by_name = {}
    _pets_list = []
    _skills_by_name = {}
    _skills_list = []
    _ensure_loaded()


def _build_type_matchup():
    global _type_matchup_cache
    if _type_matchup_cache is not None:
        return _type_matchup_cache
    _type_matchup_cache = dict(_TYPE_RELATIONS_HARD)
    return _type_matchup_cache


# ── 精灵 API ─────────────────────────────────────────────────────────
def get_pets_by_name(name: str) -> list:
    """返回指定名称的所有形态精灵列表"""
    _ensure_loaded()
    return _pets_by_name.get(name, [])

def get_pet(name: str, form: str = None):
    """精确匹配精灵：form 可选（不传则返回第一个）"""
    _ensure_loaded()
    candidates = _pets_by_name.get(name, [])
    if not candidates:
        # 尝试去掉括号内的形态描述
        base_name = re.sub(r'[（(][^)）]*[)）]', '', name).strip()
        if base_name and base_name != name:
            candidates = _pets_by_name.get(base_name, [])
            if candidates:
                name = base_name
    if not candidates:
        # 查临时缓存
        _load_temp_cache()
        for pet in _temp_cache.get("pets", []):
            if pet.get("name") == name:
                return pet
            # 查 forms 列表
            for alt in pet.get("forms", []):
                if alt.get("name") == name:
                    return alt
        return None
    if form is None:
        return candidates[0]
    # 按 form 精确匹配
    for p in candidates:
        if p.get("form") == form:
            return p
    return candidates[0]

def search_pets(keyword: str, limit: int = 30):
    _ensure_loaded()
    kw = keyword.lower()
    results = []
    for p in _pets_list:
        if kw in p.get("name", "").lower():
            results.append(p)
            if len(results) >= limit:
                break
    return results

def get_all_pets():
    _ensure_loaded()
    _load_temp_cache()
    result = list(_pets_list)
    temp_pets = _temp_cache.get("pets", [])
    existing_titles = {p.get("title") for p in result}
    for p in temp_pets:
        if p.get("title") not in existing_titles:
            result.append(p)
    return result

def get_all_pet_names():
    _ensure_loaded()
    # 去重：不同形态的同名精灵只保留一个名
    return sorted(_pets_by_name.keys())


# ── 技能 API ─────────────────────────────────────────────────────────
def get_skill(name: str):
    _ensure_loaded()
    return _skills_by_name.get(name)

def search_skills(keyword: str, limit: int = 30):
    _ensure_loaded()
    kw = keyword.lower()
    results = []
    for row in _skills_list:
        if kw in row.get("技能名", "").lower():
            results.append(row)
            if len(results) >= limit:
                break
    return results

def get_all_skills():
    _ensure_loaded()
    return list(_skills_list)

def get_all_skill_names():
    _ensure_loaded()
    return sorted(_skills_by_name.keys())


# ── 属性克制 API ─────────────────────────────────────────────────────
def get_effectiveness(attack_type: str, defend_types):
    if not isinstance(defend_types, list):
        defend_types = [defend_types]
    defend_types = [t for t in defend_types if t]
    mu = _build_type_matchup()
    multiplier = 1.0
    for d in defend_types:
        a_rel = mu.get(attack_type) or _TYPE_RELATIONS_HARD.get(attack_type, {})
        if d in a_rel.get("immune_from", []):
            return 0.0
        if d in a_rel.get("attack_2x", []):
            multiplier *= 2.0
        elif d in a_rel.get("attack_half", []):
            multiplier *= 0.5
    return round(multiplier, 2)


def get_type_info(type_name: str):
    mu = _build_type_matchup()
    rel = mu.get(type_name) or _TYPE_RELATIONS_HARD.get(type_name, {})
    return {
        "name": type_name,
        "克制": rel.get("attack_2x", []),
        "抵抗": rel.get("attack_half", []),
        "被克制": rel.get("defend_2x", []),
        "被抵抗": rel.get("defend_half", []),
        "免疫": rel.get("immune_from", []),
    }


# ── 图片路径辅助 ──────────────────────────────────────────────────────

_IMAGES_DIR = _RESOURCES / "images"


def get_pet_image_path(name: str):
    """获取精灵图片路径，不存在返回 None。带形态后缀的自动回退基础形态"""
    p = _IMAGES_DIR / "pets" / f"{name}.png"
    if p.is_file():
        return str(p)
    # 尝试去掉括号内的形态描述，如 "寒音蛇（本来的样子）" -> "寒音蛇"
    base = re.sub(r'[（(][^)）]*[)）]', '', name).strip()
    if base and base != name:
        p2 = _IMAGES_DIR / "pets" / f"{base}.png"
        if p2.is_file():
            return str(p2)
    return None


def get_skill_image_path(name: str):
    """获取技能图片路径，不存在返回 None"""
    p = _IMAGES_DIR / "skills" / f"{name}.png"
    return str(p) if p.is_file() else None


def get_all_type_relations():
    return {t: get_type_info(t) for t in ALL_TYPES}


TYPE_RELATIONS = _TYPE_RELATIONS_HARD
SPECIAL_RULES = _SPECIAL_RULES.copy()
DAMAGE_FORMULA = {
    "formula": "(攻击 - 防御) × 威力 / 50 × 克制系数 × 随机(0.85~1.0)",
    "min_random": 0.85,
    "max_random": 1.0,
    "power_divisor": 50,
    "max_stat_bonus": 60,
}