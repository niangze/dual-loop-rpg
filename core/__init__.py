"""core 包：RPG 核心数据结构、玩法与全局状态。"""

from .models import (
    Rank, rank_for_level, Item, Monster, DropEntry,
    Player, NPC, DungeonFloor, Skill, Companion,
)

from .dialogue import (
    generate_dialogue, player_status_label, favorability_tier, has_memory,
    Dialogue, DialogueUI, ConsoleDialogueUI, PERSONALITY_HANDLERS,
)

from .battle import (
    NORMAL_ATTACK, Fighter, fighter_from_player, fighter_from_monster,
    BattleSystem, default_player_ai,
)

from .dungeon import (
    EVENT_WEIGHTS, DungeonExplorer,
)

from .save_load import save_game, load_game

from .main_game import GameState, MainGame

__all__ = [
    "Rank", "rank_for_level", "Item", "Monster", "DropEntry",
    "Player", "NPC", "DungeonFloor", "Skill", "Companion",
    "generate_dialogue", "player_status_label", "favorability_tier", "has_memory",
    "Dialogue", "DialogueUI", "ConsoleDialogueUI", "PERSONALITY_HANDLERS",
    "NORMAL_ATTACK", "Fighter", "fighter_from_player", "fighter_from_monster",
    "BattleSystem", "default_player_ai",
    "EVENT_WEIGHTS", "DungeonExplorer",
    "save_game", "load_game",
    "GameState", "MainGame",
]
