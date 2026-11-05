"""
Pygame 可视化原型入口。

运行方式（在 rpg 目录下）：
    python run_game.py
自检：
    python run_game.py --smoke
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.game_state import player, npcs, dungeon
from pygame_game.app import App, smoke_test


def main():
    base = (copy.deepcopy(player), copy.deepcopy(npcs), copy.deepcopy(dungeon))
    if "--smoke" in sys.argv:
        smoke_test(base)
        return
    App(base).run()


if __name__ == "__main__":
    main()
