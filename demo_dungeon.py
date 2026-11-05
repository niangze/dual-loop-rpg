"""演示：地下城探索系统（爬塔循环 + 死亡惩罚）。"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from core.game_state import player, dungeon
from core.models import Player, Monster, DungeonFloor
from core.dungeon import DungeonExplorer


def auto_decide(explorer, floor_number):
    if explorer.player.hp < explorer.player.max_hp * 0.4:
        return "return"
    if floor_number >= 3:
        return "return"
    return "continue"


explorer = DungeonExplorer(player, dungeon, seed=7, battle_verbose=False)
result = explorer.explore(decide=auto_decide, max_floors=5)
print("\n结果：", result)

print("\n" + "=" * 56)
print("场景 2：死亡惩罚（必然战败）")
print("=" * 56)
boss = Monster(monster_id="dragon", name="深渊巨龙", hp=9999, attack=9999, speed=9999)
p2 = Player(name="倒霉蛋", hp=5, max_hp=100, attack=5, speed=8, money=1000)
explorer2 = DungeonExplorer(p2, [DungeonFloor(floor_number=1, monster_pool=[boss])], seed=1)
explorer2.resolve_enemy(explorer2.floor_template())
print("死亡结算后金币：", p2.money, "（应为 500，即一半）")
