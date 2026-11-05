"""
日常系统 —— NPC 对话生成逻辑（记忆 + 性格 + 好感度 + 荣誉值 + 感情线）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from .models import NPC, Player, Rank


# ---------------------------------------------------------------------------
# 玩家状态：Rank -> 状态标签
# ---------------------------------------------------------------------------
_RANK_STATUS: Dict[Rank, str] = {
    Rank.BRONZE: "新手",
    Rank.IRON: "新手",
    Rank.STEEL: "新手",
    Rank.SILVER: "老手",
    Rank.GOLD: "老手",
    Rank.PLATINUM: "大佬",
    Rank.DIAMOND: "大佬",
    Rank.LEGEND: "大佬",
}


def player_status_label(player: Player) -> str:
    return _RANK_STATUS.get(player.rank, "新手")


def favorability_tier(favorability: int) -> str:
    if favorability < 30:
        return "冷淡"
    if favorability < 70:
        return "友好"
    return "亲密"


def has_memory(npc: NPC, *keywords: str) -> bool:
    return any(any(k in m for k in keywords) for m in npc.memory)


# ---------------------------------------------------------------------------
# 对话结果 + UI 接口
# ---------------------------------------------------------------------------
@dataclass
class Dialogue:
    speaker: str
    text: str
    emotion: str
    player_status: str
    favorability: int
    tier: str
    options: List[str] = field(default_factory=list)


class DialogueUI(ABC):
    @abstractmethod
    def show(self, dlg: Dialogue) -> None:
        ...


class ConsoleDialogueUI(DialogueUI):
    def show(self, dlg: Dialogue) -> None:
        head = f"{dlg.speaker}｜{dlg.emotion}｜好感 {dlg.favorability}（{dlg.tier}）｜你：{dlg.player_status}"
        print("┌──────────────────────────────────────────────┐")
        print(f"│ {head}")
        print("├──────────────────────────────────────────────┤")
        print(f"│ {dlg.text}")
        print("└──────────────────────────────────────────────┘")
        if dlg.options:
            opts = "  ".join(f"[{i}] {o}" for i, o in enumerate(dlg.options, 1))
            print(f"  {opts}")


@dataclass
class DialogueContext:
    npc: NPC
    player: Player
    status: str
    tier: str
    topic: Optional[str] = None


PersonalityHandler = Callable[[DialogueContext], Tuple[str, str]]


# ---------------------------------------------------------------------------
# 性格处理器
# ---------------------------------------------------------------------------
def _tsundere(ctx: DialogueContext) -> Tuple[str, str]:
    if has_memory(ctx.npc, "被救过"):
        if ctx.status == "大佬":
            return "哼，别以为你变强了我就得听你的……上次的事，谢、谢了。", "傲娇"
        return "上、上次才不是因为你救了我才……总之你还差得远呢！", "傲娇"
    if has_memory(ctx.npc, "一起喝过酒"):
        return "上次喝酒我才没醉！……你别到处乱说。", "傲娇"
    if ctx.tier == "冷淡":
        return "……你来干嘛？我可没空理你。", "冷漠"
    if ctx.tier == "友好":
        return "哼，只是刚好路过而已，别想太多。", "傲娇"
    return "才、才不是特意等你的！……不过，见到你也不坏。", "害羞"


def _gentle(ctx: DialogueContext) -> Tuple[str, str]:
    if has_memory(ctx.npc, "被救过"):
        return "那次真是多亏了你，我一直都记在心里。", "感激"
    if has_memory(ctx.npc, "一起喝过酒"):
        return "下次再一起喝一杯吧，不过要适量哦。", "温柔"
    if ctx.tier == "冷淡":
        return "你好，需要点什么吗？", "温和"
    if ctx.tier == "友好":
        return "你来啦，今天也辛苦了。", "温柔"
    return "看到你平安回来，我就放心了。", "安心"


def _bold(ctx: DialogueContext) -> Tuple[str, str]:
    if has_memory(ctx.npc, "被救过"):
        return "我欠你一条命，以后有事尽管开口！", "豪迈"
    if has_memory(ctx.npc, "一起喝过酒"):
        return "哈哈，上次那顿酒喝得痛快，今晚再续！", "豪迈"
    if ctx.tier == "冷淡":
        return "哟，新来的？进来坐，别拘束！", "爽朗"
    if ctx.tier == "友好":
        return "哈哈，是你啊！今天想打造点什么？", "爽朗"
    return "兄弟！你可算来了，走，喝酒去！", "豪迈"


def _mysterious(ctx: DialogueContext) -> Tuple[str, str]:
    if has_memory(ctx.npc, "帮忙找回水晶球"):
        return "多亏你找回它，我才能看清你的星轨……", "神秘"
    if ctx.tier == "冷淡":
        return "命运之线……你我还未到交汇之时。", "神秘"
    if ctx.tier == "友好":
        return "水晶球告诉我，你今天会有不错的际遇。", "神秘"
    return "我在你的未来里，看到了危险与荣光并存。", "神秘"


def _generic(ctx: DialogueContext) -> Tuple[str, str]:
    if ctx.tier == "冷淡":
        return "……", "沉默"
    if ctx.tier == "友好":
        return "你好啊，旅行者。", "微笑"
    return "又见面了，见到你真好。", "微笑"


# 各性格对「地下城战果记忆」的回应口吻
_DUNGEON_FLAVOR: Dict[str, str] = {
    "傲娇": "哼，你在下面闯成什么样……我才不关心呢。",
    "温柔": "你在下面辛苦了，先歇一歇吧。",
    "豪爽": "哈哈，快说说下面那帮家伙的战果！",
    "神秘": "我在你的星轨里看到了地下城的影子……",
}


def _dungeon_reaction(ctx: DialogueContext) -> Optional[Tuple[str, str]]:
    if not has_memory(ctx.npc, "深入地下城", "满载而归", "铩羽而归"):
        return None
    flavor = _DUNGEON_FLAVOR.get(ctx.npc.personality_tags[0], "你从地下城回来了，跟我说说吧。")
    if has_memory(ctx.npc, "铩羽而归"):
        body = f"{flavor} 下次准备充分再去，安全第一。"
    elif has_memory(ctx.npc, "满载而归") and ctx.status == "大佬":
        body = f"{flavor} 不愧是{ctx.status}，收获不小吧。"
    elif has_memory(ctx.npc, "满载而归"):
        body = f"{flavor} 看来这次收获不小。"
    else:
        body = f"{flavor} 你能平安回来就好。"
    return body, "关心"


def _reputation_reaction(ctx: DialogueContext) -> Optional[Tuple[str, str]]:
    honor = ctx.player.honor
    if honor > 0:
        return "听说你最近在行侠仗义？城里人可都敬重你呢。", "敬重"
    if honor < 0:
        return "……最近有些不好的传闻，是你吧？离我远点。", "警惕"
    return None


def _romance_reaction(ctx: DialogueContext) -> Optional[Tuple[str, str]]:
    if not ctx.npc.romanceable:
        return None
    r = ctx.npc.romance
    if r >= 60:
        return f"{ctx.npc.name}握住你的手，眼里带着笑意：「今天也要平安回来。」", "爱慕"
    if r >= 30:
        return f"{ctx.npc.name}别过脸去，耳根有点红：「你、你要小心点。」", "心动"
    if r >= 10:
        return f"{ctx.npc.name}似乎有话想说，又咽了回去，只轻轻笑了一下。", "羞涩"
    return None


def _naked_reaction(ctx: DialogueContext) -> Optional[Tuple[str, str]]:
    """玩家外观反应：脱光（男性 NPC 是哥们式嫌弃/调侃），或穿了特殊服装。"""
    if ctx.player.naked:
        if ctx.npc.gender == "男":
            tag = ctx.npc.personality_tags[0] if ctx.npc.personality_tags else ""
            lines = {
                "豪爽": f"{ctx.npc.name}嫌弃地摆手：「喂喂，哥们，你光着身子干啥？快穿上，别在这儿耍流氓。」",
                "傲娇": f"{ctx.npc.name}一脸无语：「你、你有病吧？谁要看你啊，快把衣服穿回去！」",
                "神秘": f"{ctx.npc.name}皱了皱眉：「……星轨里没写你会裸奔。把衣服穿上。」",
            }
            return lines.get(tag, "……兄弟，先把衣服穿回去吧，怪冷的。"), "嫌弃"
        return f"{ctx.npc.name}脸一红，别转过头去：「你、你怎么光着身子就来了……」", "害羞"

    outfit = ctx.player.outfit
    if outfit and outfit != "日常服":
        tag = ctx.npc.personality_tags[0] if ctx.npc.personality_tags else ""
        lines = {
            "温柔": f"{ctx.npc.name}打量了你一眼，笑着说：「{outfit}……很精神呢。」",
            "豪爽": f"{ctx.npc.name}吹了声口哨：「哟，{outfit}？人模狗样的！」",
            "傲娇": f"{ctx.npc.name}别开视线：「哼，{outfit}……勉强还行吧。」",
            "神秘": f"{ctx.npc.name}若有所思：「{outfit}……今天的你，星轨不太一样。」",
        }
        return lines.get(tag, f"{ctx.npc.name}看了看你的{outfit}：「挺好看的。」"), "欣赏"
    return None


PERSONALITY_HANDLERS: Dict[str, PersonalityHandler] = {
    "傲娇": _tsundere,
    "温柔": _gentle,
    "豪爽": _bold,
    "神秘": _mysterious,
}


def _pick_handler(tags: List[str]) -> PersonalityHandler:
    for tag in tags:
        if tag in PERSONALITY_HANDLERS:
            return PERSONALITY_HANDLERS[tag]
    return _generic


# ---------------------------------------------------------------------------
# 可回复选项
# ---------------------------------------------------------------------------
def _reply_options(npc: NPC, tier: str) -> List[str]:
    options = ["聊点别的"]
    if npc.favorability >= 30:
        options.append("送你个小礼物")
    if npc.favorability >= 70:
        options.append("约你一起冒险")
    if npc.romanceable and npc.favorability >= 50:
        options.append("约会")
    return options


# ---------------------------------------------------------------------------
# 核心入口
# ---------------------------------------------------------------------------
def generate_dialogue(npc: NPC, player: Player, topic: Optional[str] = None) -> Dialogue:
    status = player_status_label(player)
    tier = favorability_tier(npc.favorability)
    handler = _pick_handler(npc.personality_tags)
    ctx = DialogueContext(npc=npc, player=player, status=status, tier=tier, topic=topic)

    text, emotion = (_naked_reaction(ctx)
                     or _romance_reaction(ctx)
                     or _reputation_reaction(ctx)
                     or _dungeon_reaction(ctx)
                     or handler(ctx))
    return Dialogue(
        speaker=npc.name,
        text=text,
        emotion=emotion,
        player_status=status,
        favorability=npc.favorability,
        tier=tier,
        options=_reply_options(npc, tier),
    )
