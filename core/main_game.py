"""
主控状态机 —— 双循环大统一。

状态：DAILY_LIFE（日常）↔ DUNGEON（地下城）。
"""
from __future__ import annotations

import random
from enum import Enum
from typing import Callable, List, Optional, Tuple

from .models import Player, NPC, DungeonFloor
from .dialogue import generate_dialogue
from .dungeon import DungeonExplorer
from .save_load import save_game, load_game


class GameState(Enum):
    DAILY_LIFE = "daily_life"
    DUNGEON = "dungeon"


DailyDecide = Callable[["MainGame"], Tuple[str, int]]
DungeonDecide = Callable[[DungeonExplorer, int], str]


class MainGame:
    def __init__(self, player: Player, npcs: List[NPC], dungeon: List[DungeonFloor],
                 seed: Optional[int] = None, max_action_points: int = 3) -> None:
        self.player = player
        self.npcs = npcs
        self.dungeon = dungeon
        self.rng = random.Random(seed)
        self.max_action_points = max_action_points
        self.action_points = max_action_points
        self.day = 1
        self.state = GameState.DAILY_LIFE
        self.last_result: Optional[DungeonExplorer] = None
        self.log: List[str] = []

    def _log(self, msg: str) -> None:
        self.log.append(msg)
        print(msg)

    # ---- 日常 ----
    def chat(self, npc_index: int) -> None:
        npc = self.npcs[npc_index]
        dlg = generate_dialogue(npc, self.player)
        self.action_points -= 1
        npc.change_favorability(2)
        self._log(f"[聊天] {dlg.speaker}（{dlg.emotion}）：{dlg.text}")
        self._log(f"        好感 +2（{npc.favorability}）｜行动点 -1（剩 {self.action_points}）")

    def enter_dungeon(self) -> None:
        self.state = GameState.DUNGEON
        self._log(">>> 进入地下城……")

    def dungeon_phase(self, decide: Optional[DungeonDecide] = None) -> None:
        explorer = DungeonExplorer(self.player, self.dungeon, rng=self.rng, battle_verbose=False)
        explorer.explore(decide=decide)
        self.last_result = explorer
        self.transfer_dungeon_result(explorer)

    # ---- 数据传递：地下城 -> 日常/NPC ----
    def transfer_dungeon_result(self, explorer: DungeonExplorer) -> None:
        tags = explorer.produce_memory_tags()
        for npc in self.npcs:
            for tag in tags:
                npc.remember(tag)
        self.state = GameState.DAILY_LIFE
        self.day += 1
        self.action_points = self.max_action_points
        self._log(f"<<< 回城。当前 Rank：{self.player.rank.value}，记忆标签已传递给 NPC：{tags}")
        self._log(f"    第 {self.day} 天开始，行动点重置为 {self.action_points}")

    # ---- 主循环 ----
    def run(self, daily_decide: DailyDecide,
            dungeon_decide: Optional[DungeonDecide] = None,
            max_days: Optional[int] = None) -> None:
        while max_days is None or self.day <= max_days:
            if self.state == GameState.DAILY_LIFE:
                self._log(f"\n=== 第 {self.day} 天（行动点 {self.action_points}）===")
                while self.state == GameState.DAILY_LIFE:
                    if self.action_points <= 0:
                        self._log("行动点耗尽，前往地下城")
                        self.enter_dungeon()
                        break
                    action = daily_decide(self)
                    kind = action[0]
                    if kind == "dungeon":
                        self.enter_dungeon()
                        break
                    if kind == "chat":
                        self.chat(action[1])
                        continue
                    raise ValueError(f"未知日常动作：{action}")
            elif self.state == GameState.DUNGEON:
                self.dungeon_phase(decide=dungeon_decide)

    # ---- 存档/读档 ----
    def save(self, path: str) -> None:
        meta = {"day": self.day, "action_points": self.action_points,
                "state": self.state.value, "max_action_points": self.max_action_points}
        save_game(path, self.player, self.npcs, self.dungeon, meta)
        self._log(f"💾 已存档到 {path}")

    @classmethod
    def load(cls, path: str, seed: Optional[int] = None) -> "MainGame":
        player, npcs, dungeon, meta = load_game(path)
        game = cls(player, npcs, dungeon, seed=seed,
                   max_action_points=meta.get("max_action_points", 3))
        game.day = meta.get("day", 1)
        game.action_points = meta.get("action_points", game.max_action_points)
        game.state = GameState(meta.get("state", GameState.DAILY_LIFE.value))
        return game
