"""演示：回合制战斗系统（单场战斗模拟）。"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from core.game_state import player, dungeon
from core.models import Player, Monster
from core.battle import BattleSystem, NORMAL_ATTACK, default_player_ai


def banner(t):
    print("\n" + "=" * 56)
    print(t)
    print("=" * 56)


banner("场景 1：默认 AI 自动战斗（速度排序 + 技能 + 普攻）")
slime = dungeon[0].monster_pool[0]
battle = BattleSystem(player, [slime])
print("\n结果：", battle.run(player_ai=default_player_ai))

banner("场景 2：自定义策略（手动指定动作）")
goblin = Monster(monster_id="goblin", name="哥布林", hp=60, attack=8, speed=5)
p = Player(name="冒险者", hp=100, max_hp=100, attack=10, speed=8, mp=20, max_mp=20,
           skills=[])
b2 = BattleSystem(p, [goblin])
print("\n结果：", b2.run(player_ai=lambda b, a, t: NORMAL_ATTACK))
