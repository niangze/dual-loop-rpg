"""
战斗系统 —— 宝可梦式回合制。

核心类：BattleSystem。支持多敌人、多队友、暴击/闪避/吸血/中毒/冷却缩减。
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .models import Companion, Monster, Player, Skill


# 普攻：统一动作接口的「伪技能」
NORMAL_ATTACK = Skill(skill_id="normal", name="普攻", multiplier=1.0,
                      mp_cost=0, cooldown=0, description="普通攻击")


# ---------------------------------------------------------------------------
# 战斗单元
# ---------------------------------------------------------------------------
@dataclass
class Fighter:
    """战斗中的一方（对 Player / Monster / Companion 的统一快照）。"""
    name: str
    hp: int
    max_hp: int
    attack: int
    speed: int
    mp: int = 0
    max_mp: int = 0
    defense: int = 0
    crit_chance: float = 0.0
    lifesteal: float = 0.0
    dodge: float = 0.0
    cdr: float = 0.0
    mp_regen: int = 0
    poison: float = 0.0
    poison_turns: int = 0
    skills: List[Skill] = field(default_factory=list)
    side: str = "enemy"                      # "player" / "enemy"
    cooldowns: Dict[str, int] = field(default_factory=dict)

    @property
    def is_alive(self) -> bool:
        return self.hp > 0

    def take_damage(self, dmg: int) -> None:
        self.hp = max(0, self.hp - dmg)

    def spend_mp(self, cost: int) -> None:
        self.mp = max(0, self.mp - cost)

    def tick_cooldowns(self) -> None:
        for sid in list(self.cooldowns):
            if self.cooldowns[sid] > 0:
                self.cooldowns[sid] -= 1

    def can_use(self, skill: Skill) -> bool:
        return skill.mp_cost <= self.mp and self.cooldowns.get(skill.skill_id, 0) <= 0


def fighter_from_player(p: Player) -> Fighter:
    return Fighter(
        name=p.name, hp=p.hp, max_hp=p.max_hp, attack=p.attack, speed=p.speed,
        mp=p.mp, max_mp=p.max_mp, defense=p.defense,
        crit_chance=p.crit_chance, lifesteal=p.lifesteal, dodge=p.dodge,
        cdr=p.cdr, mp_regen=p.mp_regen, poison=p.poison,
        skills=list(p.skills), side="player",
    )


def fighter_from_monster(m: Monster) -> Fighter:
    return Fighter(name=m.name, hp=m.hp, max_hp=m.hp, attack=m.attack,
                   speed=m.speed, defense=m.defense, side="enemy")


def fighter_from_ally(m: Monster) -> Fighter:
    return Fighter(name=m.name, hp=m.hp, max_hp=m.hp, attack=m.attack,
                   speed=m.speed, defense=m.defense, side="player")


def fighter_from_companion(c: Companion) -> Fighter:
    """把 Companion 转换成玩家方的 Fighter（带当前 HP/MP，跨战斗保留）。"""
    return Fighter(name=c.name, hp=c.hp, max_hp=c.max_hp, attack=c.attack,
                   speed=c.speed, defense=c.defense, mp=c.mp, max_mp=c.max_mp,
                   side="player")


# ---------------------------------------------------------------------------
# 战斗系统
# ---------------------------------------------------------------------------
class BattleSystem:
    def __init__(self, player: Player, enemies: List[Monster],
                 allies: List = None, verbose: bool = True) -> None:
        self.player = fighter_from_player(player)
        self.enemies = [fighter_from_monster(m) for m in enemies]
        # allies 可以是 Monster 或 Companion
        self.allies = [self._ally_fighter(m) for m in (allies or [])]
        self.log: List[str] = []
        self.turn = 0
        self.over = False
        self.winner: Optional[str] = None
        self.verbose = verbose

    @staticmethod
    def _ally_fighter(m) -> Fighter:
        if isinstance(m, Companion):
            return fighter_from_companion(m)
        return fighter_from_ally(m)

    def _log(self, msg: str) -> None:
        self.log.append(msg)
        if self.verbose:
            print(msg)

    # ---- 状态 ----
    def alive_enemies(self) -> List[Fighter]:
        return [f for f in self.enemies if f.is_alive]

    def alive_allies(self) -> List[Fighter]:
        return [f for f in self.allies if f.is_alive]

    def player_side(self) -> List[Fighter]:
        return [self.player] + self.allies

    def player_side_alive(self) -> List[Fighter]:
        return [f for f in self.player_side() if f.is_alive]

    def turn_order(self) -> List[Fighter]:
        fighters = self.player_side() + self.enemies
        return sorted(fighters, key=lambda f: (-f.speed, 0 if f.side == "player" else 1))

    # ---- 动作 ----
    def usable_actions(self, fighter: Fighter) -> List[Skill]:
        actions = [NORMAL_ATTACK]
        actions += [s for s in fighter.skills if fighter.can_use(s)]
        return actions

    def damage(self, attacker: Fighter, skill: Skill, defense: int = 0, crit: bool = False) -> int:
        raw = max(1, round(attacker.attack * skill.multiplier) - defense)
        if crit:
            # 暴击流：暴击率 ≥40% 时，暴击伤害从 1.8x 提到 2.2x
            mult = 2.2 if attacker.crit_chance >= 0.40 else 1.8
            raw = round(raw * mult)
        return max(1, raw)

    def perform_action(self, actor: Fighter, target: Fighter, skill: Skill,
                       targets: Optional[List[Fighter]] = None) -> None:
        if not actor.can_use(skill):
            self._log(f"{actor.name} 无法使用「{skill.name}」（蓝量或冷却不足），改为普攻")
            skill = NORMAL_ATTACK

        actor.spend_mp(skill.mp_cost)
        if skill.cooldown > 0:
            effective_cd = max(0, round(skill.cooldown * (1 - actor.cdr)))
            actor.cooldowns[skill.skill_id] = effective_cd

        action_name = "普攻" if skill.skill_id == "normal" else skill.name

        if skill.fizzle_chance > 0 and random.random() < skill.fizzle_chance:
            self._log(f"{actor.name}使用{action_name}，但技能失败了！白白浪费了机会")
            return

        total_crit = skill.crit_chance + actor.crit_chance
        crit = total_crit > 0 and random.random() < total_crit
        crit_tag = "（致命一击！）" if crit else ""

        hit_targets = [t for t in (targets if (skill.aoe and targets) else [target]) if t.is_alive]
        for t in hit_targets:
            if t.dodge > 0 and random.random() < t.dodge:
                self._log(f"{t.name} 闪避了 {actor.name} 的攻击！")
                # 闪避流：闪避率 ≥30% 时，闪避后顺势反击 50% 攻击
                if t.dodge >= 0.30 and t.is_alive and actor.is_alive:
                    counter = max(1, round(t.attack * 0.5))
                    actor.take_damage(counter)
                    self._log(f"  {t.name} 顺势反击，{actor.name} 受到 {counter} 点伤害！")
                continue
            dmg = self.damage(actor, skill, t.defense, crit)
            t.take_damage(dmg)
            self._log(f"{actor.name}使用{action_name}，{t.name}受到{dmg}点伤害{crit_tag}")
            if actor.lifesteal > 0:
                # 吸血流：吸血率 ≥30% 时，吸血量 ×1.5
                heal = max(1, round(dmg * actor.lifesteal))
                if actor.lifesteal >= 0.30:
                    heal = round(heal * 1.5)
                actor.hp = min(actor.max_hp, actor.hp + heal)
                self._log(f"  {actor.name} 吸血回复 {heal} HP")
            if actor.poison > 0 and t.is_alive:
                t.poison = actor.poison
                # 毒流：毒伤 ≥10 时，中毒持续 5 回合而非 3
                t.poison_turns = 5 if actor.poison >= 10 else 3
                self._log(f"  {t.name} 中毒了！（每回合 -{int(actor.poison)} HP）")
        if len(hit_targets) == 1 and hit_targets[0].is_alive:
            self._log(f"  {hit_targets[0].name} 剩余 HP：{hit_targets[0].hp}/{hit_targets[0].max_hp}")

    def tick_poison(self) -> None:
        for f in self.player_side() + self.enemies:
            if f.is_alive and f.poison_turns > 0:
                dmg = max(1, int(f.poison))
                f.hp = max(0, f.hp - dmg)
                f.poison_turns -= 1
                self._log(f"{f.name} 中毒发作，受到 {dmg} 点伤害（剩余 {f.poison_turns} 回合）")

    # ---- 结束判定 ----
    def check_end(self) -> None:
        if not self.player_side_alive():
            self.over = True
            self.winner = "enemy"
            self._log("战斗结束：队伍全灭，挑战失败！")
        elif not self.alive_enemies():
            self.over = True
            self.winner = "player"
            self._log("战斗结束：敌人全灭，胜利！")

    def start(self) -> None:
        allies_txt = "、".join(f"{a.name}(HP {a.hp})" for a in self.allies)
        self._log(f"战斗开始：{self.player.name}（HP {self.player.hp}）"
                  + (f" 伙伴 {allies_txt}" if allies_txt else "")
                  + f" vs {'、'.join(f'{e.name}(HP {e.hp})' for e in self.enemies)}")
        self._log(f"出手顺序按速度：{' > '.join(f'{f.name}({f.speed})' for f in self.turn_order())}")

    # ---- 自动战斗 ----
    def run(self, player_ai: Optional[Callable] = None, max_turns: int = 50) -> str:
        if player_ai is None:
            player_ai = default_player_ai
        self.start()
        while not self.over and self.turn < max_turns:
            self.turn += 1
            self._log(f"--- 第 {self.turn} 回合 ---")
            for actor in self.turn_order():
                if self.over:
                    break
                actor.tick_cooldowns()
                targets = self.alive_enemies() if actor.side == "player" else [self.player]
                if not targets:
                    self.check_end()
                    break
                target = targets[0]
                if actor.side == "player":
                    skill = player_ai(self, actor, targets)
                else:
                    skill = NORMAL_ATTACK
                self.perform_action(actor, target, skill, targets=targets)
                self.check_end()
        if not self.over:
            self._log(f"战斗超过 {max_turns} 回合仍未分出胜负，强制结束")
        return self.result()

    def result(self) -> str:
        if self.winner == "player":
            return f"胜利：{self.player.name} 剩余 HP {self.player.hp}/{self.player.max_hp}"
        if self.winner == "enemy":
            return f"失败：敌人剩余 {'、'.join(f'{e.name} HP {e.hp}' for e in self.alive_enemies())}"
        return "战斗未结束"

    def apply_to_units(self, player: Player, monsters: List[Monster]) -> None:
        player.hp = self.player.hp
        player.mp = self.player.mp
        for m, f in zip(monsters, self.enemies):
            m.hp = f.hp


def default_player_ai(battle: BattleSystem, player: Fighter, enemies: List[Fighter]) -> Skill:
    usable = battle.usable_actions(player)
    for skill in usable:
        if skill.skill_id != "normal":
            return skill
    return NORMAL_ATTACK
