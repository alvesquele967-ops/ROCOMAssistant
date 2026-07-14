"""
竹雨ROCOM小助手 - 伤害倍率计算（重构版）
World版公式：(攻-防)×威力/50×克制系数×随机(0.85~1.0)
"""

import random
from core.type_data import (
    get_effectiveness, get_pet, get_skill,
    DAMAGE_FORMULA, ALL_TYPES
)


class DamageCalculator:
    """伤害计算器"""

    def __init__(self):
        self.min_random = DAMAGE_FORMULA["min_random"]
        self.max_random = DAMAGE_FORMULA["max_random"]
        self.power_divisor = DAMAGE_FORMULA["power_divisor"]

    def get_damage_breakdown(self, attack_stat, defense_stat, power,
                             attack_type, defend_types, random_factor=None):
        if power <= 0:
            return {"error": "非攻击技能，无法计算伤害"}

        diff = max(0, attack_stat - defense_stat)
        base_damage = diff * power / self.power_divisor

        # 当攻击≤防御时，造成最低伤害1
        if attack_stat <= defense_stat:
            base_damage = 0
            diff = 0

        effectiveness = get_effectiveness(attack_type, defend_types)

        if random_factor is None:
            random_factor = round(random.uniform(self.min_random, self.max_random), 2)

        # 最低伤害为1（刮痧）
        final_damage = max(1, round(base_damage * effectiveness * random_factor))

        if effectiveness >= 2:
            relation_desc = f"克制(x{effectiveness})"
        elif effectiveness == 0:
            relation_desc = "免疫"
        elif effectiveness <= 0.49:
            relation_desc = f"被抵抗(x{effectiveness})"
        elif effectiveness < 1.0:
            relation_desc = f"抵抗(x{effectiveness})"
        else:
            relation_desc = "无克制关系(x1)"

        return {
            "攻击力": attack_stat,
            "防御力": defense_stat,
            "差值": diff,
            "技能威力": power,
            "基础伤害": round(base_damage, 2),
            "克制系数": effectiveness,
            "克制关系": relation_desc,
            "本次随机": random_factor,
            "随机范围": f"{self.min_random}~{self.max_random}",
            "最终伤害": final_damage,
            "攻击属性": attack_type,
            "防御属性": ",".join(defend_types),
        }

    def simulate_battle(self, attacker, defender, power, times=100):
        damages = []
        for _ in range(times):
            result = self.get_damage_breakdown(
                attacker["攻击力"], defender["防御力"], power,
                attacker["属性"], defender["属性"],
            )
            damages.append(result["最终伤害"])

        damages.sort()
        n = len(damages)
        return {
            "average_damage": round(sum(damages) / n, 1),
            "median_damage": damages[n // 2],
            "min_damage": damages[0],
            "max_damage": damages[-1],
            "damage_range_25_75": (
                damages[n // 4],
                damages[3 * n // 4],
            ),
            "all_damages": damages,
        }

    def calc_pet_damage(self, pet_name, skill_name, defend_pet_name=None,
                        defend_types=None, defend_stats=None):
        pet = get_pet(pet_name)
        if not pet:
            return {"error": f"未找到精灵: {pet_name}"}

        skill = get_skill(skill_name)
        if not skill:
            for s in pet.get("skills", []):
                if s.get("name") == skill_name:
                    skill = s
                    break
        if not skill:
            return {"error": f"未找到技能: {skill_name}"}

        skill_attr = skill.get("attribute") or skill.get("属性", "普通")
        skill_power = int(skill.get("power") or skill.get("威力", 0))
        skill_category = skill.get("category") or skill.get("类型", "物攻")

        # 非攻击技能不计算伤害
        if skill_category in ("防御", "状态") or skill_power == 0:
            return {"error": f"「{skill_name}」为非攻击技能，无法计算伤害"}

        stats = pet.get("stats", {})

        # 根据技能类型选择攻击力
        if skill_category == "物攻":
            attack_stat = stats.get("atk", 100)
        elif skill_category == "魔攻":
            attack_stat = stats.get("sp_atk", 100)
        else:
            attack_stat = stats.get("atk", 100)

        # 防御方
        if defend_pet_name:
            d_pet = get_pet(defend_pet_name)
            if d_pet:
                defend_types = d_pet.get("attributes", ["普通"])
                d_stats = d_pet.get("stats", {})
                if skill_category == "物攻":
                    defense_stat = d_stats.get("def", 80)
                else:
                    defense_stat = d_stats.get("sp_def", 80)
            else:
                defense_stat = 80
        elif defend_stats:
            if skill_category == "物攻":
                defense_stat = defend_stats.get("def", 80)
            else:
                defense_stat = defend_stats.get("sp_def", 80)
        else:
            defense_stat = 80

        if defend_types is None:
            defend_types = ["普通"]

        return self.get_damage_breakdown(
            attack_stat, defense_stat, skill_power,
            skill_attr, defend_types
        )