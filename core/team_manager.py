"""
竹雨ROCOM小助手 - 配队管理器（重构版）
支持精灵搜索选择、技能选择、性格修正、弱点分析、阵容码导入导出
"""

import json
import base64
from pathlib import Path
from core.type_data import (
    get_pet, search_pets, get_all_pet_names,
    get_skill, search_skills, get_all_skill_names,
    get_effectiveness, get_type_info, ALL_TYPES,
    NATURES, NATURE_NAMES
)
from core.bloodline_data import get_bloodlines_for_pet, get_bloodline_desc

_TEAM_FILE = Path(__file__).parent.parent / "teams.json"


class TeamManager:
    def __init__(self):
        self.teams = []
        self.current_team_index = -1
        self._load()

    def _load(self):
        if _TEAM_FILE.exists():
            try:
                with open(_TEAM_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.teams = data.get("teams", [])
            except Exception:
                self.teams = []

    def _save(self):
        with open(_TEAM_FILE, "w", encoding="utf-8") as f:
            json.dump({"teams": self.teams}, f, ensure_ascii=False, indent=2)

    def add_team(self, team_name, members=None):
        team = {"name": team_name, "members": members or []}
        self.teams.append(team)
        self._save()
        return team

    def remove_team(self, index):
        if 0 <= index < len(self.teams):
            self.teams.pop(index)
            self._save()

    def get_team(self, index):
        if 0 <= index < len(self.teams):
            return self.teams[index]
        return None

    def add_member(self, team_index, member_data):
        team = self.get_team(team_index)
        if team:
            pet = get_pet(member_data["name"])
            if pet:
                member_data["attributes"] = pet.get("attributes", [])
                member_data["stats"] = pet.get("stats", {})
                member_data["no"] = pet.get("no")
                member_data["ability"] = pet.get("ability", {})
            if "bloodline" not in member_data:
                member_data["bloodline"] = "无"
            team["members"].append(member_data)
            self._save()

    def remove_member(self, team_index, member_index):
        team = self.get_team(team_index)
        if team and 0 <= member_index < len(team["members"]):
            team["members"].pop(member_index)
            self._save()

    def update_member(self, team_index, member_index, key, value):
        team = self.get_team(team_index)
        if team and 0 <= member_index < len(team["members"]):
            team["members"][member_index][key] = value
            self._save()

    def set_team_magic(self, team_index, magic):
        """设置配队的魔法"""
        team = self.get_team(team_index)
        if team:
            team["magic"] = magic
            self._save()

    def get_team_magic(self, team_index):
        """获取配队的魔法"""
        team = self.get_team(team_index)
        if team:
            return team.get("magic", "")
        return ""

    def search_pets(self, keyword):
        return search_pets(keyword)

    def search_skills_for_pet(self, pet_name):
        pet = get_pet(pet_name)
        if not pet:
            return []
        return sorted(pet.get("skills", []), key=lambda s: s.get("level", 0))

    def apply_nature(self, stats, nature_name):
        modifiers = NATURES.get(nature_name, {})
        result = dict(stats)
        stat_map = {"物攻": "atk", "魔攻": "sp_atk", "物防": "def", "魔防": "sp_def", "速度": "spd", "生命": "hp"}
        for key, mult in modifiers.items():
            s_key = stat_map.get(key)
            if s_key and s_key in result:
                result[s_key] = round(result[s_key] * mult)
        return result

    def get_nature_description(self, nature_name):
        modifiers = NATURES.get(nature_name, {})
        if not modifiers:
            return "无修正"
        desc = []
        for k, v in modifiers.items():
            if v > 1:
                desc.append(f"{k}+{int((v-1)*100)}%")
            else:
                desc.append(f"{k}-{int((1-v)*100)}%")
        return "、".join(desc)

    def analyze_weakness(self, pet_name_or_types):
        if isinstance(pet_name_or_types, str):
            pet = get_pet(pet_name_or_types)
            types = pet.get("attributes", []) if pet else [pet_name_or_types]
        else:
            types = pet_name_or_types

        weaknesses = {}
        resistances = {}
        for t in ALL_TYPES:
            eff = get_effectiveness(t, types)
            if eff >= 2:
                weaknesses[t] = eff
            elif 0 < eff <= 0.5:
                resistances[t] = eff

        return {
            "属性": types,
            "弱点（受到2x）": weaknesses,
            "抵抗（受到0.5x）": resistances,
        }

    def get_all_names(self):
        return get_all_pet_names()

    def get_all_skill_names(self):
        return get_all_skill_names()

    def get_nature_names(self):
        return NATURE_NAMES

    @staticmethod
    def get_type_info(name):
        return get_type_info(name)

    # ── 阵容码功能 ─────────────────────────────────────────────────

    def create_team_from_game_code(self, parsed_data):
        """从游戏阵容码解析结果创建配队并保存，返回创建的 team"""
        team_name = parsed_data.get("name", "导入配队")
        magic = parsed_data.get("magic", "")
        pet_entries = parsed_data.get("pets", [])

        members = []
        for entry in pet_entries:
            pet_name = entry.get("name", "")
            bloodline = entry.get("bloodline", "无")
            skill_names = entry.get("skills", [])

            # 查找精灵（精确匹配 → 模糊匹配）
            pet = get_pet(pet_name)
            matched_name = pet_name
            if not pet:
                candidates = search_pets(pet_name)
                if candidates:
                    matched_name = candidates[0].get("name", pet_name)
                    pet = candidates[0]

            # 技能匹配
            skills = []
            for sk_name in skill_names:
                found = None
                if pet:
                    for ps in pet.get("skills", []):
                        if ps.get("name") == sk_name:
                            found = dict(ps)
                            break
                if not found:
                    gs = get_skill(sk_name)
                    if gs:
                        found = {
                            "name": sk_name,
                            "attribute": gs.get("属性", "?"),
                            "category": gs.get("类型", "?"),
                            "power": int(gs.get("威力", 0)),
                            "cost": int(gs.get("耗能", 0)),
                        }
                    else:
                        found = {"name": sk_name, "attribute": "?", "category": "?", "power": 0, "cost": 0}
                skills.append(found)

            member = {
                "name": matched_name,
                "nature": "实干",
                "bloodline": bloodline,
                "skills": skills,
                "note": "",
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

        team = {"name": team_name, "members": members}
        if magic:
            team["magic"] = magic
        self.teams.append(team)
        self._save()
        return team

    def generate_team_code(self, team_index):
        """将指定配队编码为阵容码字符串，格式: ROCOM:base64"""
        team = self.get_team(team_index)
        if not team:
            return ""

        compact = {
            "name": team.get("name", ""),
            "members": [],
        }
        magic = team.get("magic", "")
        if magic:
            compact["mg"] = magic
        game_code = team.get("game_code", "")
        if game_code:
            compact["gc"] = game_code
        # Wiki元数据
        source = team.get("source", "")
        if source:
            compact["src"] = source
        wiki_id = team.get("wiki_id", "")
        if wiki_id:
            compact["wid"] = wiki_id
        author_val = team.get("wiki_author", "") or team.get("author", "")
        if author_val:
            compact["wa"] = author_val
        date_val = team.get("wiki_date", "") or team.get("date", "")
        if date_val:
            compact["wd"] = date_val
        type_val = team.get("wiki_type", "") or team.get("type", "")
        if type_val:
            compact["wt"] = type_val
        desc_val = team.get("wiki_desc", "") or team.get("description", "")
        if desc_val:
            compact["wds"] = desc_val
        for m in team.get("members", []):
            compact["members"].append({
                "n": m.get("name", ""),
                "nt": m.get("nature", ""),
                "bl": m.get("bloodline", "无"),
                "bo": m.get("boosts", ["无", "无", "无"]),
                "sk": [s.get("name", "") for s in m.get("skills", [])],
                "no": m.get("note", ""),
            })

        json_str = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        b64 = base64.b64encode(json_str.encode("utf-8")).decode("ascii")
        return f"ROCOM:{b64}"

    def import_team_from_code(self, code_str):
        """解析阵容码字符串，还原为配队dict并添加到teams，返回team或None"""
        if not code_str or not code_str.startswith("ROCOM:"):
            return None

        try:
            b64 = code_str[6:]
            json_str = base64.b64decode(b64).decode("utf-8")
            compact = json.loads(json_str)
        except Exception:
            return None

        members = []
        for cm in compact.get("members", []):
            pet_name = cm.get("n", "")
            pet = get_pet(pet_name)

            skills = []
            for sk_name in cm.get("sk", []):
                found = None
                if pet:
                    for ps in pet.get("skills", []):
                        if ps.get("name") == sk_name:
                            found = dict(ps)
                            break
                if not found:
                    gs = get_skill(sk_name)
                    if gs:
                        found = {
                            "name": sk_name,
                            "attribute": gs.get("属性", "?"),
                            "category": gs.get("类型", "?"),
                            "power": int(gs.get("威力", 0)),
                            "cost": int(gs.get("耗能", 0)),
                        }
                    else:
                        found = {"name": sk_name, "attribute": "?", "category": "?", "power": 0, "cost": 0}
                skills.append(found)

            member = {
                "name": pet_name,
                "nature": cm.get("nt", "实干"),
                "bloodline": cm.get("bl", "无"),
                "boosts": cm.get("bo", ["无", "无", "无"]),
                "skills": skills,
                "note": cm.get("no", ""),
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

        team = {
            "name": compact.get("name", "导入配队"),
            "members": members,
        }
        # 恢复Wiki元数据
        src = compact.get("src", "")
        if src:
            team["source"] = src
        wid = compact.get("wid", "")
        if wid:
            team["wiki_id"] = wid
        wa = compact.get("wa", "")
        if wa:
            team["wiki_author"] = wa
            team["author"] = wa
        wd = compact.get("wd", "")
        if wd:
            team["wiki_date"] = wd
            team["date"] = wd
        wt = compact.get("wt", "")
        if wt:
            team["wiki_type"] = wt
            team["type"] = wt
        wds = compact.get("wds", "")
        if wds:
            team["wiki_desc"] = wds
            team["description"] = wds
        magic = compact.get("mg", "")
        if magic:
            team["magic"] = magic
        game_code = compact.get("gc", "")
        if game_code:
            team["game_code"] = game_code
        self.teams.append(team)
        self._save()
        return team