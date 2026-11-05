"""演示：主控状态机（MainGame）+ 存档读档。"""
import copy
import sys
sys.stdout.reconfigure(encoding="utf-8")

from core.game_state import player, npcs, dungeon
from core.main_game import MainGame
from core.save_load import load_game


game = MainGame(copy.deepcopy(player), copy.deepcopy(npcs), copy.deepcopy(dungeon),
                seed=7, max_action_points=3)


def daily_decide(g):
    return ("chat", 0) if g.action_points == g.max_action_points else ("dungeon", 0)


def dungeon_decide(explorer, floor_number):
    return "return"


game.run(daily_decide=daily_decide, dungeon_decide=dungeon_decide, max_days=1)
game.save("demo_save.json")

p2, n2, d2, meta2 = load_game("demo_save.json")
print("\n读档还原：", p2.name, "money=", p2.money, "rank=", p2.rank.value,
      "hp=", p2.hp, "level=", p2.level)
print("艾琳记忆：", n2[0].memory, "| meta：", meta2)
