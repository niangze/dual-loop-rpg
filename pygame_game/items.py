"""物品 / 技能 / 商店 / 掉落 / 词条 数据表。"""
import random

from core.models import Item, Skill

# 物品模板：item_id -> Item 字段
ITEM_TEMPLATES = {
    "potion": dict(name="初级药水", item_type="消耗品", price=25, heal_hp=30,
                   description="恢复 30 HP"),
    "mana_potion": dict(name="魔力药水", item_type="消耗品", price=30, heal_mp=20,
                        description="恢复 20 MP"),
    # 装备（5 个槽位）
    "iron_sword": dict(name="铁剑", item_type="装备", equip_slot="weapon", attack_bonus=5,
                       price=120, description="攻击 +5"),
    "leather_armor": dict(name="皮甲", item_type="装备", equip_slot="armor", defense_bonus=3,
                          price=100, description="防御 +3"),
    "swift_boots": dict(name="疾风靴", item_type="装备", equip_slot="boots", speed_bonus=2,
                        price=150, description="速度 +2"),
    "amulet": dict(name="守护护符", item_type="装备", equip_slot="accessory", hp_bonus=15,
                   price=130, description="生命上限 +15"),
    "iron_ring": dict(name="铁戒指", item_type="装备", equip_slot="ring", attack_bonus=2,
                      price=90, description="攻击 +2"),
    # 技能书
    "skillbook_frost": dict(name="寒冰术·书", item_type="技能书", skill_id="frost", price=200,
                            description="习得寒冰术（群攻）"),
    "skillbook_pierce": dict(name="破甲斩·书", item_type="技能书", skill_id="pierce", price=250,
                             description="习得破甲斩（40% 致命一击）"),
    # 遗忘书（消耗品：忘掉一个技能，空出技能槽）
    "skillbook_forget": dict(name="技能遗忘书", item_type="遗忘书", price=150,
                             description="遗忘一个技能，空出技能槽（普攻不可遗忘）"),
    # 服装（外观，不影响战斗属性）
    "outfit_casual": dict(name="日常服", item_type="服装", price=0,
                          description="你平时穿的衣服"),
    "outfit_adventurer": dict(name="冒险者装", item_type="服装", price=120,
                              description="便于行动的冒险者装束"),
    "outfit_noble": dict(name="华服", item_type="服装", price=300,
                         description="体面的华服，显得很有身份"),
    "outfit_apron": dict(name="酒馆围裙", item_type="服装", price=60,
                         description="艾琳同款围裙（？）"),
}

# 装备槽位（顺序即展示顺序）
EQUIP_SLOTS = [
    ("weapon", "武器"),
    ("armor", "护甲"),
    ("boots", "靴子"),
    ("accessory", "饰品"),
    ("ring", "戒指"),
]

# 词条池：（属性键, 数值, 描述）
AFFIX_POOL = [
    ("attack", 2, "攻击+2"),
    ("defense", 1, "防御+1"),
    ("speed", 1, "速度+1"),
    ("hp_bonus", 10, "生命+10"),
    ("mp_bonus", 10, "蓝量+10"),
    ("crit", 0.05, "暴击率+5%"),
    ("lifesteal", 0.10, "吸血10%"),
    ("dodge", 0.05, "闪避5%"),
    ("cdr", 0.10, "冷却-10%"),
    ("mp_regen", 3, "回蓝+3/回合"),
    ("poison", 5, "毒伤+5"),
]

# 技能模板：skill_id -> Skill
SKILL_TEMPLATES = {
    "frost": Skill(skill_id="frost", name="寒冰术", multiplier=1.2, mp_cost=15, cooldown=0,
                   aoe=True, description="对全体敌人造成伤害"),
    "pierce": Skill(skill_id="pierce", name="破甲斩", multiplier=2.2, mp_cost=20, cooldown=0,
                    crit_chance=0.4, description="40% 概率造成致命一击"),
}

# 商店货架（全量，兼容旧逻辑）
SHOP_STOCK = [
    "potion", "mana_potion", "iron_sword", "leather_armor", "swift_boots",
    "amulet", "iron_ring", "skillbook_frost", "skillbook_pierce",
    "skillbook_forget", "outfit_adventurer", "outfit_noble", "outfit_apron",
]

# 商店分类：店名 -> 货架
SHOP_CATEGORIES = {
    "武器店": ["iron_sword"],
    "防具店": ["leather_armor", "swift_boots", "amulet"],
    "饰品店": ["iron_ring"],
    "药水店": ["potion", "mana_potion"],
    "技能书店": ["skillbook_frost", "skillbook_pierce", "skillbook_forget"],
    "服装店": ["outfit_adventurer", "outfit_noble", "outfit_apron"],
    "杂货铺": ["potion", "iron_ring", "swift_boots", "skillbook_forget"],
}

# 随机掉落池（权重）
LOOT_POOL = ["potion", "mana_potion", "iron_sword", "leather_armor",
             "skillbook_frost", "skillbook_pierce"]
LOOT_WEIGHTS = [4, 3, 2, 2, 1, 1]


def make_item(item_id: str, quantity: int = 1) -> Item:
    t = ITEM_TEMPLATES[item_id]
    return Item(item_id=item_id, quantity=quantity, **t)


def make_skill(skill_id: str) -> Skill:
    return SKILL_TEMPLATES[skill_id]


def apply_affix(item: Item) -> Item:
    """给装备随机附加一条词条（把加成烤进属性里，词条文字存 affix_desc）。"""
    stat, value, desc = random.choice(AFFIX_POOL)
    if stat == "attack":
        item.attack_bonus += value
    elif stat == "defense":
        item.defense_bonus += value
    elif stat == "speed":
        item.speed_bonus += value
    elif stat == "hp_bonus":
        item.hp_bonus += value
    elif stat == "mp_bonus":
        item.mp_bonus += value
    elif stat == "crit":
        item.crit_bonus += value
    elif stat == "lifesteal":
        item.lifesteal_bonus += value
    elif stat == "dodge":
        item.dodge_bonus += value
    elif stat == "cdr":
        item.cdr_bonus += value
    elif stat == "mp_regen":
        item.mp_regen_bonus += value
    elif stat == "poison":
        item.poison_bonus += value
    item.affix_desc = f"词条：{desc}"
    return item
