"""演示：日常 NPC 对话系统 —— 性格 × 好感 × 记忆 × 玩家状态。"""
import sys
sys.stdout.reconfigure(encoding="utf-8")

from core.game_state import player, npcs
from core.models import NPC, Player, Rank
from core.dialogue import generate_dialogue, ConsoleDialogueUI

ui = ConsoleDialogueUI()


def show(npc, p, title=""):
    if title:
        print("\n" + "=" * 52)
        print(title)
        print("=" * 52)
    ui.show(generate_dialogue(npc, p))


if __name__ == "__main__":
    big = Player(name="冒险者", rank=Rank.PLATINUM)
    rookie = Player(name="冒险者", rank=Rank.BRONZE)

    show(NPC(name="凛", personality_tags=["傲娇"], favorability=55, memory=["被救过"]), big,
         "【原文示例】傲娇 + 被救过 + 大佬")
    show(NPC(name="凛", personality_tags=["傲娇"], favorability=55, memory=["被救过"]), rookie,
         "【对照】傲娇 + 被救过 + 新手")
    show(NPC(name="艾琳", personality_tags=["温柔"], favorability=80, memory=["被救过"]), big,
         "【温柔·感激】")
    show(NPC(name="古德", personality_tags=["豪爽"], favorability=50, memory=["一起喝过酒"]), big,
         "【豪爽·喝酒】")
    show(NPC(name="露娜", personality_tags=["神秘"], favorability=40, memory=["帮忙找回水晶球"]), big,
         "【神秘·水晶球】")

    print("\n" + "=" * 52)
    print("全局 NPC 与全局玩家实测")
    print("=" * 52)
    for npc in npcs:
        show(npc, player)
