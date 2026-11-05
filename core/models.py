"""
RPG 核心数据结构定义 —— 「日常 + 地下城」双循环。

三大核心模型：Player / NPC / DungeonFloor，以及支撑类型。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# 枚举
# ---------------------------------------------------------------------------
class Rank(Enum):
    """玩家当前状态 Rank（成长/身份等级，从低到高）。"""
    BRONZE = "青铜"
    IRON = "黑铁"
    STEEL = "钢铁"
    SILVER = "白银"
    GOLD = "黄金"
    PLATINUM = "白金"
    DIAMOND = "钻石"
    LEGEND = "传说"


def rank_for_level(level: int) -> Rank:
    """按等级映射 Rank，供升级时自动晋升。"""
    if level >= 10:
        return Rank.LEGEND
    if level >= 8:
        return Rank.DIAMOND
    if level >= 6:
        return Rank.PLATINUM
    if level >= 4:
        return Rank.GOLD
    if level >= 3:
        return Rank.SILVER
    if level >= 2:
        return Rank.IRON
    return Rank.BRONZE


# ---------------------------------------------------------------------------
# 支撑类型
# ---------------------------------------------------------------------------
@dataclass
class Item:
    """背包里的物品（消耗品 / 装备 / 技能书 / 材料）。"""
    item_id: str
    name: str
    item_type: str = "消耗品"
    quantity: int = 1
    description: str = ""
    price: int = 0
    heal_hp: int = 0
    heal_mp: int = 0
    attack_bonus: int = 0
    defense_bonus: int = 0
    speed_bonus: int = 0
    hp_bonus: int = 0
    mp_bonus: int = 0
    crit_bonus: float = 0.0
    lifesteal_bonus: float = 0.0
    dodge_bonus: float = 0.0
    cdr_bonus: float = 0.0
    mp_regen_bonus: int = 0
    poison_bonus: float = 0.0
    equip_slot: str = ""
    skill_id: str = ""
    affix_desc: str = ""


@dataclass
class Monster:
    """地下城里的怪物。"""
    monster_id: str
    name: str
    hp: int
    attack: int
    speed: int
    exp_reward: int = 0
    money_reward: int = 0
    defense: int = 0


@dataclass
class DropEntry:
    """掉落表里的一项。"""
    item_id: str
    name: str
    weight: int = 100
    min_count: int = 1
    max_count: int = 1


@dataclass
class Skill:
    """战斗技能（也用于统一「普攻」动作）。"""
    skill_id: str
    name: str
    multiplier: float = 1.0
    mp_cost: int = 0
    cooldown: int = 0
    description: str = ""
    crit_chance: float = 0.0
    aoe: bool = False
    fizzle_chance: float = 0.0


# ---------------------------------------------------------------------------
# 核心结构 1：玩家
# ---------------------------------------------------------------------------
@dataclass
class Player:
    """玩家。"""
    name: str = "冒险者"
    hp: int = 100
    max_hp: int = 100
    attack: int = 10
    speed: int = 8
    mp: int = 50
    max_mp: int = 50
    defense: int = 0
    crit_chance: float = 0.0
    lifesteal: float = 0.0
    dodge: float = 0.0
    cdr: float = 0.0
    mp_regen: int = 0
    poison: float = 0.0
    naked: bool = False
    outfit: str = "日常服"
    rank: Rank = Rank.BRONZE
    money: int = 0
    honor: int = 0
    exp: int = 0
    level: int = 1
    inventory: List[Item] = field(default_factory=list)
    skills: List[Skill] = field(default_factory=list)
    equipment: Dict[str, Item] = field(default_factory=dict)

    def add_item(self, item: Item) -> None:
        for existing in self.inventory:
            if existing.item_id == item.item_id:
                existing.quantity += item.quantity
                return
        self.inventory.append(item)

    def remove_item(self, item_id: str, count: int = 1) -> bool:
        for existing in self.inventory:
            if existing.item_id == item_id:
                if existing.quantity >= count:
                    existing.quantity -= count
                    if existing.quantity == 0:
                        self.inventory.remove(existing)
                    return True
                return False
        return False

    def gain_exp(self, amount: int) -> int:
        """增加经验，按等级阈值自动升级并晋升 Rank，返回升级次数。"""
        if amount <= 0:
            return 0
        self.exp += amount
        leveled = 0
        while self.exp >= self.level * 100:
            self.exp -= self.level * 100
            self.level += 1
            self.max_hp += 10
            self.hp = min(self.max_hp, self.hp + 10)
            self.attack += 2
            leveled += 1
        self.rank = rank_for_level(self.level)
        return leveled


# ---------------------------------------------------------------------------
# 核心结构 2：NPC
# ---------------------------------------------------------------------------
@dataclass
class NPC:
    """NPC（日常循环里的角色）。"""
    name: str
    personality_tags: List[str] = field(default_factory=list)
    favorability: int = 0
    memory: List[str] = field(default_factory=list)
    romance: int = 0
    gender: str = "女"
    romanceable: bool = True
    route: str = ""

    def change_favorability(self, delta: int) -> int:
        """调整好感度（自动夹在 0-100），返回实际变化量。"""
        before = self.favorability
        self.favorability = max(0, min(100, self.favorability + delta))
        return self.favorability - before

    def remember(self, event: str) -> None:
        if event not in self.memory:
            self.memory.append(event)


# ---------------------------------------------------------------------------
# 核心结构 3：地下城层
# ---------------------------------------------------------------------------
@dataclass
class DungeonFloor:
    """地下城的某一层。"""
    floor_number: int
    monster_pool: List[Monster] = field(default_factory=list)
    drop_table: List[DropEntry] = field(default_factory=list)
    cleared: bool = False


# ---------------------------------------------------------------------------
# 组队伙伴（带独立 HP/MP，跨战斗保留）
# ---------------------------------------------------------------------------
@dataclass
class Companion:
    """可入队的伙伴。"""
    name: str
    max_hp: int
    hp: int
    attack: int
    speed: int
    defense: int = 0
    max_mp: int = 30
    mp: int = 30
    behavior: str = "normal"
    skill_level: int = 1
