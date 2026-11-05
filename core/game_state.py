"""
全局游戏状态 —— 三大核心结构的全局单例。

    from core.game_state import player, npcs, dungeon
"""
from __future__ import annotations

from typing import List

from .models import (
    Rank, Item, Monster, DropEntry, Player, NPC, DungeonFloor, Skill,
)


# ---------------------------------------------------------------------------
# 全局玩家
# ---------------------------------------------------------------------------
player = Player(
    name="冒险者",
    hp=100,
    max_hp=100,
    attack=10,
    speed=8,
    mp=50,
    max_mp=50,
    rank=Rank.BRONZE,
    money=500,
    inventory=[
        Item(item_id="potion", name="初级药水", item_type="消耗品",
             quantity=3, description="恢复 30 点生命", price=25, heal_hp=30),
        Item(item_id="iron_sword", name="铁剑", item_type="装备",
             quantity=1, description="攻击 +5", price=120,
             equip_slot="weapon", attack_bonus=5),
    ],
    skills=[
        Skill(skill_id="fireball", name="火球术", multiplier=2.0,
              mp_cost=10, cooldown=0, description="凝聚火焰，造成 2 倍攻击伤害"),
        Skill(skill_id="heavy_slash", name="重斩", multiplier=1.6,
              mp_cost=5, cooldown=2, description="蓄力一击，冷却 2 回合"),
    ],
)


# ---------------------------------------------------------------------------
# 全局 NPC 列表
# ---------------------------------------------------------------------------
npcs: List[NPC] = [
    NPC(
        name="艾琳",
        personality_tags=["温柔", "酒馆老板娘"],
        favorability=30,
        memory=["初次见面"],
        gender="女",
        romanceable=True,
    ),
    NPC(
        name="古德",
        personality_tags=["豪爽", "铁匠"],
        favorability=0,
        memory=[],
        gender="男",
        romanceable=False,
    ),
    NPC(
        name="露娜",
        personality_tags=["神秘", "占卜师"],
        favorability=15,
        memory=["帮忙找回水晶球"],
        gender="女",
        romanceable=True,
    ),
]


# ---------------------------------------------------------------------------
# 全局地下城
# ---------------------------------------------------------------------------
dungeon: List[DungeonFloor] = [
    DungeonFloor(
        floor_number=1,
        monster_pool=[
            Monster(monster_id="slime", name="史莱姆",
                    hp=30, attack=5, speed=3, exp_reward=10, money_reward=5),
            Monster(monster_id="bat", name="蝙蝠",
                    hp=20, attack=6, speed=6, exp_reward=8, money_reward=4),
        ],
        drop_table=[
            DropEntry(item_id="potion", name="初级药水", weight=60, min_count=1, max_count=1),
            DropEntry(item_id="copper", name="铜币", weight=40, min_count=5, max_count=15),
        ],
        cleared=False,
    ),
    DungeonFloor(
        floor_number=2,
        monster_pool=[
            Monster(monster_id="goblin", name="哥布林",
                    hp=45, attack=8, speed=5, exp_reward=18, money_reward=10),
            Monster(monster_id="wolf", name="野狼",
                    hp=40, attack=10, speed=8, exp_reward=16, money_reward=8),
        ],
        drop_table=[
            DropEntry(item_id="potion", name="中级药水", weight=40, min_count=1, max_count=2),
            DropEntry(item_id="silver", name="银币", weight=50, min_count=3, max_count=10),
            DropEntry(item_id="wolf_pelt", name="狼皮", weight=10, min_count=1, max_count=1),
        ],
        cleared=False,
    ),
    DungeonFloor(
        floor_number=3,
        monster_pool=[
            Monster(monster_id="spider", name="毒蜘蛛",
                    hp=55, attack=12, speed=7, exp_reward=26, money_reward=14),
            Monster(monster_id="ghost", name="幽灵",
                    hp=50, attack=14, speed=11, exp_reward=28, money_reward=15),
            Monster(monster_id="skeleton", name="骷髅兵",
                    hp=70, attack=13, speed=5, exp_reward=30, money_reward=16),
        ],
        drop_table=[
            DropEntry(item_id="potion", name="中级药水", weight=40, min_count=1, max_count=2),
            DropEntry(item_id="silver", name="银币", weight=40, min_count=5, max_count=15),
            DropEntry(item_id="skillbook_frost", name="寒冰术·书", weight=10, min_count=1, max_count=1),
        ],
        cleared=False,
    ),
    DungeonFloor(
        floor_number=4,
        monster_pool=[
            Monster(monster_id="troll", name="巨魔",
                    hp=120, attack=18, speed=4, exp_reward=50, money_reward=30, defense=3),
            Monster(monster_id="demon", name="深渊恶魔",
                    hp=160, attack=24, speed=8, exp_reward=80, money_reward=60, defense=5),
        ],
        drop_table=[
            DropEntry(item_id="potion", name="中级药水", weight=30, min_count=2, max_count=3),
            DropEntry(item_id="gold_coin", name="金币", weight=50, min_count=20, max_count=40),
            DropEntry(item_id="skillbook_pierce", name="破甲斩·书", weight=10, min_count=1, max_count=1),
        ],
        cleared=False,
    ),
]
