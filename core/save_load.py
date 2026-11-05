"""
存档 / 读档系统：把 player / npcs / dungeon（及 meta）序列化成 JSON 落盘。
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Dict, List, Tuple

from .models import (
    Rank, Item, Monster, DropEntry, Player, NPC, DungeonFloor, Skill,
)


# ---------------------------------------------------------------------------
# 序列化
# ---------------------------------------------------------------------------
def player_to_dict(p: Player) -> dict:
    d = asdict(p)
    d["rank"] = p.rank.value if isinstance(p.rank, Rank) else p.rank
    return d


def npc_to_dict(n: NPC) -> dict:
    return asdict(n)


def floor_to_dict(f: DungeonFloor) -> dict:
    return asdict(f)


# ---------------------------------------------------------------------------
# 反序列化
# ---------------------------------------------------------------------------
def player_from_dict(d: dict) -> Player:
    d = dict(d)
    d["rank"] = Rank(d["rank"]) if isinstance(d["rank"], str) else d["rank"]
    d["inventory"] = [Item(**i) for i in d.get("inventory", [])]
    d["skills"] = [Skill(**s) for s in d.get("skills", [])]
    d["equipment"] = {k: Item(**v) for k, v in (d.get("equipment") or {}).items()}
    return Player(**d)


def npc_from_dict(d: dict) -> NPC:
    return NPC(**d)


def floor_from_dict(d: dict) -> DungeonFloor:
    d = dict(d)
    d["monster_pool"] = [Monster(**m) for m in d.get("monster_pool", [])]
    d["drop_table"] = [DropEntry(**e) for e in d.get("drop_table", [])]
    return DungeonFloor(**d)


# ---------------------------------------------------------------------------
# 对外接口
# ---------------------------------------------------------------------------
def save_game(path: str, player: Player, npcs: List[NPC],
              dungeon: List[DungeonFloor], meta: Dict = None) -> None:
    data = {
        "player": player_to_dict(player),
        "npcs": [npc_to_dict(n) for n in npcs],
        "dungeon": [floor_to_dict(f) for f in dungeon],
        "meta": meta or {},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_game(path: str) -> Tuple[Player, List[NPC], List[DungeonFloor], Dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    player = player_from_dict(data["player"])
    npcs = [npc_from_dict(n) for n in data["npcs"]]
    dungeon = [floor_from_dict(x) for x in data["dungeon"]]
    return player, npcs, dungeon, data.get("meta", {})
