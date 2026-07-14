"""
竹雨ROCOM小助手 - 精灵图鉴爬虫
使用 Playwright 无头浏览器爬取官方图鉴实时数据
https://static.gamecenter.qq.com/xgame/roco-kingdom/compendium/
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime

# ── 路径 ──────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).parent.parent
_RESOURCES = _BASE_DIR / "resources"
_OUTPUT_PATH = _RESOURCES / "scraped_pets.json"

COMPENDIUM_URL = (
    "https://static.gamecenter.qq.com/xgame/roco-kingdom/compendium/"
)

# 属性名标准化映射
ATTR_MAP = {
    "火": "火", "水": "水", "草": "草", "冰": "冰", "龙": "龙",
    "暗": "暗", "光": "光", "机械": "机械", "电": "电", "毒": "毒",
    "虫": "虫", "武": "武", "翼": "翼", "萌": "萌", "幽": "幽",
    "恶": "恶", "幻": "幻", "地": "地", "普通": "普通",
    "火系": "火", "水系": "水", "草系": "草", "冰系": "冰", "龙系": "龙",
    "光系": "光", "机械系": "机械", "电系": "电", "毒系": "毒",
    "虫系": "虫", "武系": "武", "翼系": "翼", "萌系": "萌", "幽系": "幽",
    "恶系": "恶", "幻系": "幻", "地系": "地", "普通系": "普通",
}


def _normalize_attr(raw: str) -> str:
    """将属性文本标准化为短名"""
    raw = raw.strip()
    return ATTR_MAP.get(raw, raw)


def _extract_skill_name_from_src(src: str) -> str:
    """从技能图标 src 提取技能名，如 a/s/猛烈撞击.png → 猛烈撞击"""
    if not src:
        return ""
    filename = src.rsplit("/", 1)[-1]
    if "." in filename:
        filename = filename.rsplit(".", 1)[0]
    return filename.strip()


def _get_cached_time() -> str:
    """获取上次缓存的爬取时间"""
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
    """返回缓存状态信息"""
    return {
        "exists": _OUTPUT_PATH.exists(),
        "time": _get_cached_time(),
        "count": _get_cached_count(),
    }


def main(progress_callback=None):
    """
    执行爬取主流程。
    progress_callback(phase, message, current, total) 可选的进度回调。
    返回 (success: bool, message: str)。
    """
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

    if not _OUTPUT_PATH.parent.exists():
        _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if progress_callback:
        progress_callback("init", "正在启动浏览器...", 0, 0)

    all_pets = []
    all_skills = {}  # name → skill_dict
    total = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            # ── 步骤 1: 打开页面 ──
            if progress_callback:
                progress_callback("load", "正在加载官方图鉴页面...", 0, 0)
            page.goto(COMPENDIUM_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)  # 等待 React 渲染

            # ── 步骤 2: 获取精灵总数 ──
            total = page.evaluate("""() => {
                const text = document.body.innerText || '';
                const m = text.match(/共\\s*(\\d+)\\s*只精灵/);
                return m ? parseInt(m[1]) : 0;
            }""")

            if total <= 0:
                # 兜底：数卡片数量
                total = page.evaluate("""() => {
                    const cards = document.querySelectorAll('[class*="card"], [class*="Card"], [class*="sprite"], [class*="Sprite"], ._3w5u, ._6x91');
                    return cards.length;
                }""")
                if total <= 0:
                    return False, "无法识别页面中的精灵总数，请检查页面是否正常加载"

            if progress_callback:
                progress_callback(
                    "start", f"共检测到 {total} 只精灵，开始逐只爬取...", 0, total
                )

            # ── 步骤 3: 逐只爬取 ──
            for idx in range(1, total + 1):
                try:
                    # 打开详情面板
                    open_ok = page.evaluate(f"""(idx) => {{
                        try {{
                            if (typeof _od === 'function') {{
                                _od(idx);
                                return true;
                            }}
                            // 兜底：尝试点击第 idx 个卡片
                            const cards = document.querySelectorAll('._3w5u, ._6x91, [class*="spriteCard"]');
                            if (cards[idx - 1]) {{
                                cards[idx - 1].click();
                                return true;
                            }}
                        }} catch(e) {{}}
                        return false;
                    }}""", idx)

                    if not open_ok:
                        if progress_callback:
                            progress_callback(
                                "skip",
                                f"[{idx}/{total}] 无法打开详情",
                                idx,
                                total,
                            )
                        continue

                    page.wait_for_timeout(1200)

                    # 等待技能列表出现
                    try:
                        page.wait_for_selector("#_sk3_0", timeout=6000)
                    except PlaywrightTimeout:
                        # 尝试关闭并跳过
                        page.evaluate("try { closeDetail?.() } catch(e) {}")
                        page.wait_for_timeout(300)
                        if progress_callback:
                            progress_callback(
                                "skip",
                                f"[{idx}/{total}] 无详情面板",
                                idx,
                                total,
                            )
                        continue

                    # ── 提取数据 ──
                    data = page.evaluate("""() => {
                        const result = {
                            name: '',
                            no: 0,
                            attributes: [],
                            stats: { hp: 0, atk: 0, sp_atk: 0, def: 0, sp_def: 0, spd: 0, total: 0 },
                            ability: { name: '', description: '' },
                            skills: []
                        };

                        // 精灵名称
                        const nameEl = document.querySelector('._2d54');
                        if (nameEl) result.name = nameEl.textContent.trim();

                        // 编号：从正文中的 NO.xxx 提取
                        const bodyText = document.body.innerText || '';
                        const noMatch = bodyText.match(/NO\\.(\\d+)/);
                        if (noMatch) result.no = parseInt(noMatch[1]);

                        // 属性：从详情面板中的属性图标 img[title] 提取
                        const allImgs = document.querySelectorAll('img[title]');
                        const attrs = [];
                        const attrNames = ['火','水','草','冰','龙','暗','光','机械','电','毒','虫','武','翼','萌','幽','恶','幻','地','普通'];
                        allImgs.forEach(img => {
                            const t = (img.getAttribute('title') || '').trim();
                            if (t && attrNames.includes(t)) {
                                attrs.push(t);
                            }
                        });
                        result.attributes = [...new Set(attrs)];

                        // 种族值六维
                        const statLabels = ['hp','atk','sp_atk','def','sp_def','spd'];
                        const cnLabels = ['HP','物攻','魔攻','物防','魔防','速度',
                                          '生命','攻击','特攻','防御','特防','敏捷',
                                          '体力','物攻','魔攻','物防','魔防','速度'];
                        const fullText = document.body.innerText || '';

                        // 尝试正则匹配 "HP 120 物攻 80 ..." 模式
                        const hpMatch = fullText.match(/(?:HP|生命|体力)\\s*(\\d+)/i);
                        const atkMatch = fullText.match(/(?:物攻|攻击)\\s*(\\d+)/);
                        const spaMatch = fullText.match(/(?:魔攻|特攻)\\s*(\\d+)/);
                        const defMatch = fullText.match(/(?:物防|防御)\\s*(\\d+)/);
                        const spdMatch1 = fullText.match(/(?:魔防|特防)\\s*(\\d+)/);
                        const spdMatch2 = fullText.match(/(?:速度)\\s*(\\d+)/);

                        if (hpMatch) result.stats.hp = parseInt(hpMatch[1]);
                        if (atkMatch) result.stats.atk = parseInt(atkMatch[1]);
                        if (spaMatch) result.stats.sp_atk = parseInt(spaMatch[1]);
                        if (defMatch) result.stats.def = parseInt(defMatch[1]);
                        if (spdMatch1) result.stats.sp_def = parseInt(spdMatch1[1]);
                        if (spdMatch2) result.stats.spd = parseInt(spdMatch2[1]);

                        // total
                        const vals = [result.stats.hp, result.stats.atk, result.stats.sp_atk,
                                      result.stats.def, result.stats.sp_def, result.stats.spd];
                        result.stats.total = vals.reduce((a, b) => a + b, 0);

                        // 特性
                        const abilityMatch = fullText.match(/特性[：:]\\s*(.+)/);
                        if (abilityMatch) {
                            result.ability.name = abilityMatch[1].trim();
                            result.ability.description = abilityMatch[1].trim();
                        }

                        // 技能列表
                        const skillContainer = document.querySelector('#_sk3_0');
                        if (skillContainer) {
                            const skillItems = skillContainer.querySelectorAll('.i7p5');
                            skillItems.forEach(item => {
                                const img = item.querySelector('img');
                                let skillName = '';
                                if (img) {
                                    const src = img.getAttribute('src') || '';
                                    skillName = (src.split('/').pop() || '').split('.')[0] || '';
                                }

                                // 属性图标
                                let attrIcon = item.querySelector('img[title]');
                                let attribute = attrIcon ? (attrIcon.getAttribute('title') || '').trim() : '?';

                                // LV
                                const lvEl = item.querySelector('._uzfk');
                                const lvMatch = lvEl ? lvEl.textContent.match(/LV\\s*(\\d+)/) : null;
                                const level = lvMatch ? parseInt(lvMatch[1]) : 0;

                                // 从 item 文本中提取威力、魔力
                                const itemText = item.textContent || '';
                                const powerMatch = itemText.match(/威力\\s*(\\d+)/);
                                const power = powerMatch ? parseInt(powerMatch[1]) : 0;
                                const costMatch = itemText.match(/(?:★|魔力)\\s*(\\d+)/);
                                const cost = costMatch ? parseInt(costMatch[1]) : 0;

                                // 效果描述
                                const effectEl = item.querySelector('._8ut0');
                                const description = effectEl ? effectEl.textContent.trim() : '';

                                result.skills.push({
                                    name: skillName,
                                    attribute: attribute,
                                    category: '?',
                                    power: power,
                                    cost: cost,
                                    level: level,
                                    description: description
                                });
                            });
                        }

                        return result;
                    }""")

                    # 标准化属性名
                    data["attributes"] = [
                        _normalize_attr(a) for a in data.get("attributes", [])
                    ]
                    for sk in data.get("skills", []):
                        sk["attribute"] = _normalize_attr(sk.get("attribute", "?"))

                    all_pets.append(data)

                    # 收集全局技能表
                    for sk in data.get("skills", []):
                        sname = sk.get("name", "")
                        if sname and sname not in all_skills:
                            all_skills[sname] = {
                                "技能名": sname,
                                "属性": sk.get("attribute", "?"),
                                "类型": sk.get("category", "?"),
                                "威力": str(sk.get("power", 0)),
                                "耗能": str(sk.get("cost", 0)),
                            }

                    if progress_callback:
                        progress_callback(
                            "progress",
                            f"[{idx}/{total}] {data.get('name', '?')} - {len(data.get('skills', []))} 技能",
                            idx,
                            total,
                        )

                    # 关闭详情面板
                    page.evaluate("try { closeDetail?.() } catch(e) {}")
                    page.wait_for_timeout(500)

                except Exception as e:
                    page.evaluate("try { closeDetail?.() } catch(e) {}")
                    page.wait_for_timeout(300)
                    if progress_callback:
                        progress_callback(
                            "skip",
                            f"[{idx}/{total}] 异常: {e}",
                            idx,
                            total,
                        )
                    continue

            # ── 步骤 4: 保存 ──
            if progress_callback:
                progress_callback("save", "正在保存数据...", total, total)

            output = {
                "pets": all_pets,
                "skills": list(all_skills.values()),
                "meta": {
                    "total": len(all_pets),
                    "scraped_at": datetime.now().isoformat(),
                    "source_url": COMPENDIUM_URL,
                },
            }

            with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(output, f, ensure_ascii=False, indent=2)

            return True, f"爬取完成！共 {len(all_pets)} 只精灵，{len(all_skills)} 个技能"

        except Exception as e:
            return False, f"爬取出错: {e}"
        finally:
            browser.close()


if __name__ == "__main__":
    ok, msg = main()
    print(msg)
    sys.exit(0 if ok else 1)