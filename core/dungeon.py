"""
地下城探索系统 —— Roguelike 爬塔循环。

核心类：DungeonExplorer。遇敌调用 BattleSystem；宝箱/陷阱/二选一/死亡惩罚。
"""
from __future__ import annotations

import random
from typing import Callable, Dict, List, Optional

from .models import DungeonFloor, Item, Monster, Player
from .battle import BattleSystem, default_player_ai


EVENT_WEIGHTS: Dict[str, float] = {"enemy": 0.6, "chest": 0.2, "trap": 0.2}

ChoiceCallback = Callable[["DungeonExplorer", int], str]


class DungeonExplorer:
    def __init__(self, player: Player, dungeon: List[DungeonFloor],
                 seed: Optional[int] = None, rng: Optional[random.Random] = None,
                 battle_verbose: bool = False) -> None:
        self.player = player
        self.dungeon = dungeon
        self.rng = rng if rng is not None else random.Random(seed)
        self.battle_verbose = battle_verbose
        self.floor_number: int = 1
        self.pending_gold: int = 0
        self.pending_exp: int = 0
        self.earned_gold: int = 0
        self.earned_exp: int = 0
        self.dead: bool = False
        self.run_over: bool = False
        self.log: List[str] = []

    def _log(self, msg: str) -> None:
        self.log.append(msg)
        print(msg)

    @property
    def depth_multiplier(self) -> float:
        return 1.1 ** (self.floor_number - 1)

    def floor_template(self) -> DungeonFloor:
        if self.floor_number <= len(self.dungeon):
            return self.dungeon[self.floor_number - 1]
        return self.dungeon[-1]

    def scale_monster(self, m: Monster) -> Monster:
        k = self.depth_multiplier
        return Monster(
            monster_id=m.monster_id, name=m.name,
            hp=max(1, round(m.hp * k)), attack=max(1, round(m.attack * k)),
            speed=max(1, round(m.speed * k)), exp_reward=m.exp_reward,
            money_reward=m.money_reward, defense=m.defense,
        )

    def roll_event(self) -> str:
        kinds = list(EVENT_WEIGHTS)
        weights = [EVENT_WEIGHTS[k] for k in kinds]
        return self.rng.choices(kinds, weights=weights)[0]

    def resolve_enemy(self, floor: DungeonFloor) -> None:
        template = self.rng.choice(floor.monster_pool)
        monster = self.scale_monster(template)
        self._log(f"⚔ 遭遇敌人：{monster.name}（HP {monster.hp} / 攻 {monster.attack} / 速 {monster.speed}，深度 ×{self.depth_multiplier:.2f}）")
        battle = BattleSystem(self.player, [monster], verbose=self.battle_verbose)
        battle.run(player_ai=default_player_ai)
        battle.apply_to_units(self.player, [monster])
        if battle.winner == "player":
            self.pending_exp += monster.exp_reward
            self.pending_gold += monster.money_reward
            self.earned_exp += monster.exp_reward
            self.earned_gold += monster.money_reward
            self._log(f"胜利！获得 {monster.exp_reward} 经验、{monster.money_reward} 金币（待入账，回城结算）")
        else:
            self._log(f"{self.player.name} 被 {monster.name} 击败……")
            self.on_death()

    def resolve_chest(self, floor: DungeonFloor) -> None:
        gold = self.rng.randint(10, 30)
        self.pending_gold += gold
        self.earned_gold += gold
        self._log(f"🎁 发现宝箱！获得 {gold} 金币（待入账）")
        if floor.drop_table and self.rng.random() < 0.5:
            drop = self.rng.choices(floor.drop_table, weights=[d.weight for d in floor.drop_table])[0]
            count = self.rng.randint(drop.min_count, drop.max_count)
            self.player.add_item(Item(item_id=drop.item_id, name=drop.name, quantity=count))
            self._log(f"   宝箱里还有：{drop.name} ×{count}")

    def resolve_trap(self) -> None:
        dmg = self.rng.randint(8, 15)
        self.player.hp = max(0, self.player.hp - dmg)
        self._log(f"⚠ 踩中陷阱！受到 {dmg} 点伤害，剩余 HP {self.player.hp}/{self.player.max_hp}")
        if self.player.hp <= 0:
            self._log("陷阱要了命……")
            self.on_death()

    def on_death(self) -> None:
        self.dead = True
        self.run_over = True
        lost = self.player.money - self.player.money // 2
        self.player.money //= 2
        self.pending_gold = 0
        self.pending_exp = 0
        self._log(f"💀 死亡：扣除一半金币（-{lost}），本次所得金币与经验清零，强制回城")
        self._log(f"   回城后金币：{self.player.money}")

    def return_to_town(self) -> None:
        gold, exp = self.pending_gold, self.pending_exp
        self.player.money += gold
        leveled = self.player.gain_exp(exp)
        self.pending_gold = 0
        self.pending_exp = 0
        self.run_over = True
        self._log(f"🏠 安全回城：金币 +{gold}，经验 +{exp}（已入账）")
        if leveled:
            self._log(f"   ↑ 升级 {leveled} 次！Lv.{self.player.level}，HP {self.player.hp}/{self.player.max_hp}，攻击 {self.player.attack}")
        self._log(f"   当前资产：金币 {self.player.money}，经验 {self.player.exp}（Lv.{self.player.level}）")

    def prompt_choice(self, floor_number: int) -> str:
        print(f"\n[二选一] 第 {floor_number} 层已结算，待入账：金币 {self.pending_gold}、经验 {self.pending_exp}")
        print(f"  1. 继续深入第 {floor_number + 1} 层（怪物属性提升 10%）")
        print("  2. 回城（保存当前金币与经验）")
        while True:
            ans = input("请选择 (1/2)：").strip()
            if ans in ("1", "继续", "深入"):
                return "continue"
            if ans in ("2", "回城", "返回"):
                return "return"
            print("输入无效，请输入 1 或 2")

    def explore(self, decide: Optional[ChoiceCallback] = None,
                max_floors: Optional[int] = None) -> str:
        self._log(f"=== 进入地下城：第 {self.floor_number} 层 ===")
        while not self.run_over:
            floor = self.floor_template()
            self._log(f"\n--- 第 {self.floor_number} 层（深度 ×{self.depth_multiplier:.2f}）---")
            event = self.roll_event()
            if event == "enemy":
                self.resolve_enemy(floor)
            elif event == "chest":
                self.resolve_chest(floor)
            else:
                self.resolve_trap()

            if self.run_over:
                break

            if max_floors is not None and self.floor_number >= max_floors:
                self._log(f"已到达第 {max_floors} 层（最深），自动回城")
                self.return_to_town()
                break

            choice = decide(self, self.floor_number) if decide else self.prompt_choice(self.floor_number)
            if choice in ("return", "回城"):
                self.return_to_town()
                break
            self.floor_number += 1
            self._log(f"⬇ 选择继续深入 → 第 {self.floor_number} 层（怪物属性提升 10%）")

        return self.summary()

    def summary(self) -> str:
        if self.dead:
            return (f"死亡回城：到达第 {self.floor_number} 层，"
                    f"剩余金币 {self.player.money}，经验 {self.player.exp}（Lv.{self.player.level}）")
        return (f"安全回城：到达第 {self.floor_number} 层，"
                f"金币 {self.player.money}，经验 {self.player.exp}（Lv.{self.player.level}）")

    def produce_memory_tags(self) -> List[str]:
        tags: List[str] = []
        if self.dead:
            tags.append("铩羽而归")
        else:
            tags.append(f"深入地下城第{self.floor_number}层")
            if self.earned_gold > 0:
                tags.append("满载而归")
        return tags
