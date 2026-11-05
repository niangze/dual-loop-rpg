"""原型控制器：串联 core 各系统，供 pygame 场景驱动。"""
import copy
import random
from typing import List

from core.models import Monster, Player, NPC, DungeonFloor, Skill, Companion
from core.dialogue import generate_dialogue, player_status_label
from core.battle import BattleSystem, NORMAL_ATTACK
from core.save_load import save_game, load_game
from .items import (
    make_item, make_skill, apply_affix,
    SHOP_STOCK, LOOT_POOL, LOOT_WEIGHTS, ITEM_TEMPLATES,
)
from .story import AILIN_EVENTS, CONFESSION_BEATS, CONFESSION_CHOICES


# 地下城探索事件权重
DUNGEON_EVENT_WEIGHTS = {
    "enemy": 0.34,
    "chest": 0.14,
    "trap": 0.14,
    "adventurer": 0.18,
    "wounded": 0.10,
    "entrance": 0.10,
}

# 第 1 层专用权重：不刷敌对冒险者
FLOOR1_EVENT_WEIGHTS = {
    "enemy": 0.45,
    "chest": 0.18,
    "trap": 0.18,
    "wounded": 0.12,
    "entrance": 0.07,
}

# 伙伴定位
COMPANION_STATS = {
    "豪爽": dict(hp=70, attack=14, speed=6, defense=2, max_mp=20, behavior="heavy"),
    "温柔": dict(hp=50, attack=9, speed=7, defense=1, max_mp=50, behavior="heal"),
    "神秘": dict(hp=45, attack=11, speed=8, defense=1, max_mp=45, behavior="aoe"),
}

# 伙伴技能表：behavior -> 技能等级(1-3) -> 参数
COMPANION_SKILL_TABLE = {
    "heavy": {
        1: dict(name="重击", multiplier=1.6, mp_cost=5, aoe=False),
        2: dict(name="破甲重击", multiplier=1.9, mp_cost=8, aoe=False),
        3: dict(name="毁灭重击", multiplier=2.4, mp_cost=14, aoe=False),
    },
    "heal": {
        1: dict(name="治愈术", heal=25, mp_cost=10, aoe=False),
        2: dict(name="治愈术·强", heal=45, mp_cost=16, aoe=False),
        3: dict(name="群体治愈", heal=35, mp_cost=26, aoe=True),
    },
    "aoe": {
        1: dict(name="诅咒", multiplier=0.7, mp_cost=10, aoe=True),
        2: dict(name="深渊诅咒", multiplier=0.9, mp_cost=15, aoe=True),
        3: dict(name="湮灭", multiplier=1.2, mp_cost=22, aoe=True),
    },
}

# 艾琳技能等级 ≥2 解锁「补蓝术」
MANA_RESTORE = dict(name="补蓝术", mp_restore=20, mp_cost=8)
# 伙伴技能升级费用（从当前等级升到下一级）
COMPANION_SKILL_UPGRADE_COST = {1: 80, 2: 160}

# 委托板模板（短期目标）
QUEST_TEMPLATES = [
    dict(type="kill", need=3, desc="讨伐 3 只怪物", gold=80, exp=40),
    dict(type="kill", need=5, desc="讨伐 5 只怪物", gold=140, exp=70),
    dict(type="depth", need=3, desc="抵达地下城第 3 层", gold=120, exp=60),
    dict(type="gold", need=100, desc="带回 100 金币", gold=50, exp=90),
    dict(type="honor", need=1, desc="帮助 1 名伤员", gold=60, exp=40),
]

# 每日事件（让世界有变化）
TODAY_EVENTS = [
    dict(id="calm", name="平静的一天", desc="没有什么特别的。"),
    dict(id="market", name="集市日", desc="今日物价偏低。"),
    dict(id="festival", name="冒险者节", desc="今日经验收益 +20%。"),
    dict(id="raid", name="魔物躁动", desc="地下城金币 +20%，但怪物更凶。"),
]

# 敌人特殊技（按 monster_id）
ENEMY_SPECIALS = {
    "goblin": dict(name="投掷石子", mult=1.6, chance=0.30),
    "wolf": dict(name="撕咬", mult=1.8, chance=0.25),
    "spider": dict(name="毒液喷吐", mult=1.3, chance=0.35),
    "ghost": dict(name="怨灵尖啸", mult=1.5, chance=0.30),
    "skeleton": dict(name="骨刺", mult=1.6, chance=0.30),
    "troll": dict(name="巨力横扫", mult=1.9, chance=0.30),
    "demon": dict(name="深渊爆发", mult=1.5, chance=0.35, aoe=True),
}


class GameController:
    """双循环状态：日常 ↔ 地下城。"""

    def __init__(self, player: Player, npcs, dungeon):
        self.player = player
        self.npcs = npcs
        self.dungeon = dungeon
        self.max_action_points = 3
        self.action_points = self.max_action_points
        self.day = 1
        self.lodging_cost = 20
        self.floor = 1
        self.pending_gold = 0
        self.pending_exp = 0
        self.earned_gold = 0
        self.current_enemies: List[Monster] = []
        self.companions: List[Companion] = []
        self.companion_behaviors: dict = {}
        self.max_companions = 2
        self.rooms_explored = 0
        self.rooms_per_floor = 4
        self.max_skills = 3
        self.last_message = ""
        self.last_event_msg = ""
        # 市场行情：每日漂移 + 单品需求
        self.market_day = 0
        self.market_shift = 0.0
        self.item_demand = {}
        # 委托板（短期目标）
        self.quests = [self._new_quest() for _ in range(3)]
        # 每日事件
        self.today_event = None
        self._roll_today_event()

    # ---- 委托板 ----
    def _new_quest(self):
        q = dict(random.choice(QUEST_TEMPLATES))
        q["progress"] = 0
        return q

    def _track_quest(self, qtype, amount=1):
        for q in self.quests:
            if q["type"] != qtype or q["progress"] >= q["need"]:
                continue
            if qtype == "depth":
                q["progress"] = min(q["need"], max(q["progress"], self.floor))
            else:
                q["progress"] = min(q["need"], q["progress"] + amount)

    def claim_quest(self, idx):
        q = self.quests[idx]
        if q["progress"] < q["need"]:
            return f"委托「{q['desc']}」尚未完成（{q['progress']}/{q['need']}）"
        self.player.money += q["gold"]
        leveled = self.player.gain_exp(q["exp"])
        self.quests[idx] = self._new_quest()
        extra = f"，升级 {leveled} 次" if leveled else ""
        return f"完成委托「{q['desc']}」：金币 +{q['gold']}，经验 +{q['exp']}{extra}"

    # ---- 日常 ----
    def chat(self, idx):
        npc = self.npcs[idx]
        dlg = generate_dialogue(npc, self.player)
        self.action_points -= 1
        npc.change_favorability(2)
        return dlg

    def rest(self):
        if self.action_points <= 0:
            return "行动点不足"
        self.action_points -= 1
        heal, mp_gain = 30, 15
        self.player.hp = min(self.player.max_hp, self.player.hp + heal)
        self.player.mp = min(self.player.max_mp, self.player.mp + mp_gain)
        return (f"在房间小憩，回复 {heal} HP / {mp_gain} MP"
                f"（当前 HP {self.player.hp}/{self.player.max_hp}，MP {self.player.mp}/{self.player.max_mp}）")

    def train(self):
        if self.action_points <= 0:
            return "行动点不足"
        self.action_points -= 1
        stat = random.choice(["attack", "defense", "speed"])
        if stat == "attack":
            self.player.attack += 1
            return f"刻苦锻炼，攻击 +1（当前 {self.player.attack}）"
        if stat == "defense":
            self.player.defense += 1
            return f"扛击训练，防御 +1（当前 {self.player.defense}）"
        self.player.speed += 1
        return f"敏捷训练，速度 +1（当前 {self.player.speed}）"

    def work(self):
        if self.action_points <= 0:
            return "行动点不足"
        self.action_points -= 1
        gold = 30
        self.player.money += gold
        return f"打零工赚了 {gold} 金币（当前 {self.player.money}）"

    # ---- 物品 / 装备 / 技能书 ----
    def use_item(self, item):
        return self.use_item_on(self.player, item)

    def use_item_on(self, target, item):
        if item.item_type != "消耗品":
            return "这不是可使用的消耗品"
        name = getattr(target, "name", "目标")
        need = False
        if item.heal_hp > 0 and target.hp < target.max_hp:
            need = True
        if item.heal_mp > 0 and target.mp < target.max_mp:
            need = True
        if not need:
            return f"{name} 的 HP/MP 已满，无需使用 {item.name}"
        target.hp = min(target.max_hp, target.hp + item.heal_hp)
        target.mp = min(target.max_mp, target.mp + item.heal_mp)
        self.player.remove_item(item.item_id, 1)
        return f"对 {name} 使用 {item.name}（HP {target.hp}/{target.max_hp}，MP {target.mp}/{target.max_mp}）"

    def _apply_equip_bonus(self, item, sign):
        self.player.attack += sign * item.attack_bonus
        self.player.defense += sign * item.defense_bonus
        self.player.speed += sign * item.speed_bonus
        self.player.max_hp += sign * item.hp_bonus
        self.player.hp = min(self.player.max_hp, self.player.hp + sign * item.hp_bonus)
        self.player.max_mp += sign * item.mp_bonus
        self.player.mp = min(self.player.max_mp, self.player.mp + sign * item.mp_bonus)
        self.player.crit_chance += sign * item.crit_bonus
        self.player.lifesteal += sign * item.lifesteal_bonus
        self.player.dodge += sign * item.dodge_bonus
        self.player.cdr += sign * item.cdr_bonus
        self.player.mp_regen += sign * item.mp_regen_bonus
        self.player.poison += sign * item.poison_bonus

    def equip_item(self, item):
        if item.item_type != "装备":
            return "这不是可装备的物品"
        slot = item.equip_slot or "weapon"
        if slot in self.player.equipment and self.player.equipment[slot].item_id == item.item_id:
            return f"{item.name} 已经装备在身上了，无需重复装备"
        if slot in self.player.equipment:
            old = self.player.equipment[slot]
            self._apply_equip_bonus(old, -1)
            self.player.add_item(old)
        if not self.player.remove_item(item.item_id, 1):
            return "背包里没有该装备"
        new_item = copy.copy(item)
        new_item.quantity = 1
        self.player.equipment[slot] = new_item
        self._apply_equip_bonus(new_item, +1)
        return f"装备 {new_item.name}（攻击 {self.player.attack} / 防御 {self.player.defense} / 速度 {self.player.speed}）"

    def unequip_item(self, slot):
        if slot not in self.player.equipment:
            return "该槽位没有装备"
        item = self.player.equipment.pop(slot)
        self._apply_equip_bonus(item, -1)
        self.player.add_item(item)
        return f"卸下 {item.name}"

    def learn_skill(self, item):
        if item.item_type != "技能书":
            return "这不是技能书"
        if len(self.player.skills) >= self.max_skills:
            return f"技能栏已满（最多 {self.max_skills} 个消耗 MP 的技能）"
        skill = make_skill(item.skill_id)
        if any(s.skill_id == skill.skill_id for s in self.player.skills):
            return "你已经学会这个技能了"
        self.player.skills.append(skill)
        self.player.remove_item(item.item_id, 1)
        return f"学会了技能：{skill.name}（{skill.description}）"

    def forget_skill(self, item, skill_id):
        """使用技能遗忘书：忘掉一个技能（普攻不可遗忘）。"""
        if item.item_type != "遗忘书":
            return "这不是遗忘书"
        skill = next((s for s in self.player.skills if s.skill_id == skill_id), None)
        if skill is None or skill_id == "normal":
            return "不能遗忘这个技能"
        self.player.skills = [s for s in self.player.skills if s.skill_id != skill_id]
        self.player.remove_item(item.item_id, 1)
        return f"你遗忘了技能「{skill.name}」，空出一个技能槽（当前 {len(self.player.skills)}/{self.max_skills}）"

    def wear_outfit(self, item):
        """换上服装（外观，不影响战斗属性）。"""
        if item.item_type != "服装":
            return "这不是服装"
        self.player.outfit = item.name
        self.player.naked = False
        self.player.remove_item(item.item_id, 1)
        return f"你换上了「{item.name}」。"

    # ---- 商店（动态价格） ----
    def buy_multiplier(self):
        """荣誉/恶名对买入价的影响。"""
        if self.player.honor > 0:
            return 0.9
        if self.player.honor < 0:
            return 1.2
        return 1.0

    def sell_multiplier(self):
        """荣誉/恶名对卖出价的影响。"""
        if self.player.honor > 0:
            return 1.2
        if self.player.honor < 0:
            return 0.8
        return 1.0

    def _market_factor(self):
        """每日市场行情漂移（-15% ~ +15%），换日时刷新。"""
        if self.market_day != self.day:
            self.market_day = self.day
            self.market_shift = random.uniform(-0.15, 0.15)
        return 1 + self.market_shift

    def demand_of(self, item_id):
        return self.item_demand.get(item_id, 1.0)

    def _bump_demand(self, item_id, delta):
        self.item_demand[item_id] = max(0.6, min(1.8, self.demand_of(item_id) + delta))

    def buy_price(self, item_id):
        base = ITEM_TEMPLATES[item_id].get("price", 0)
        return max(1, round(base * self.buy_multiplier() * self._market_factor() * self.demand_of(item_id)))

    def sell_price(self, item):
        return max(1, round(item.price * 0.5 * self.sell_multiplier()
                            * self._market_factor() * self.demand_of(item.item_id)))

    def price_breakdown(self, item_id):
        """给 UI 用：拆解当前价格因素。"""
        base = ITEM_TEMPLATES[item_id].get("price", 0)
        return {
            "base": base,
            "honor": self.buy_multiplier(),
            "market": self._market_factor(),
            "demand": self.demand_of(item_id),
            "buy": self.buy_price(item_id),
        }

    def buy(self, item_id):
        price = self.buy_price(item_id)
        if self.player.money < price:
            return f"金币不足（需要 {price}）"
        self.player.money -= price
        item = make_item(item_id)
        if item.item_type == "装备" and random.random() < 0.4:
            apply_affix(item)
        self.player.add_item(item)
        # 买的人多了，需求上升 -> 下次更贵
        self._bump_demand(item_id, 0.10)
        tag = f"（{item.affix_desc}）" if item.affix_desc else ""
        return f"购买 {item.name}{tag}，花费 {price} 金币（剩余 {self.player.money}）"

    def sell(self, item_id, count=1):
        item = next((i for i in self.player.inventory if i.item_id == item_id), None)
        if item is None:
            return "背包里没有该物品"
        price = self.sell_price(item)
        self.player.money += price
        self.player.remove_item(item_id, count)
        # 卖的人多了，供给上升 -> 下次更便宜
        self._bump_demand(item_id, -0.08)
        return f"出售 {item.name}，获得 {price} 金币（剩余 {self.player.money}）"

    def stroll(self):
        """城市逛街：随机街头事件。"""
        event = random.choices(
            ["discount", "pickpocket", "rumor", "busker", "vendor", "brawl", "stray", "nothing"],
            weights=[2, 2, 2, 1, 2, 1, 1, 3])[0]
        if event == "discount":
            self.market_day = self.day
            self.market_shift = -0.2
            return "街上正好在搞促销，今日物价大降！"
        if event == "pickpocket":
            lost = min(20, self.player.money)
            self.player.money -= lost
            return f"遇到扒手，丢了 {lost} 金币……"
        if event == "rumor":
            self.player.honor += 1
            return "你听路人说起你的传闻，名声 +1。"
        if event == "busker":
            gain = random.randint(5, 15)
            self.player.money += gain
            return f"你给卖艺的捧场，反而被塞了 {gain} 金币。"
        if event == "vendor":
            item = make_item(random.choice(["potion", "mana_potion", "skillbook_forget"]))
            self.player.add_item(item)
            return f"街边小贩塞给你「{item.name}」：「拿着，缘分。」"
        if event == "brawl":
            self.player.hp = max(1, self.player.hp - 10)
            self.player.honor += 2
            return "你拉开街头斗殴的两人，被推搡了几下（HP -10，荣誉 +2）"
        if event == "stray":
            self.player.hp = min(self.player.max_hp, self.player.hp + 5)
            return "一只流浪猫蹭了蹭你的裤腿，你心情不错（HP +5）"
        return "你在街上溜达了一圈，什么也没发生。"

    def confess(self):
        if self.player.honor >= 0:
            return "你问心无愧，无需忏悔"
        cost = 50
        if self.player.money < cost:
            return f"忏悔需要 {cost} 金币的香火钱（当前 {self.player.money}）"
        self.player.money -= cost
        self.player.honor = 0
        return f"你在修道院虔诚忏悔，洗清了恶名（-{cost} 金币，荣誉值归零）"

    # ---- 感情线 ----
    @staticmethod
    def romance_stage(r: int) -> str:
        if r >= 60:
            return "恋人"
        if r >= 30:
            return "心动"
        if r >= 10:
            return "暧昧"
        return "未开始"

    def date_npc(self, npc):
        if not npc.romanceable:
            return f"{npc.name} 是能一起喝酒的哥们，不是你约会对象。"
        if npc.favorability < 50:
            return f"你和{npc.name}还不够熟（好感需 ≥50）"
        npc.romance = min(100, npc.romance + 8)
        npc.favorability = min(100, npc.favorability + 3)
        stage = self.romance_stage(npc.romance)
        return f"与{npc.name}度过愉快时光（感情 +8 / 好感 +3，阶段：{stage}）"

    # ---- 艾琳感情线（剧情事件 + 告白） ----
    def ailin(self):
        return self.npcs[0]

    def ailin_event_ready(self):
        """返回下一个可触发的艾琳剧情事件（一次性）。"""
        npc = self.ailin()
        if npc.route:
            return None
        for ev in AILIN_EVENTS:
            if ev["memory"] in npc.memory:
                continue
            if npc.romance >= ev["need_romance"]:
                return ev
        return None

    def apply_ailin_event(self, ev):
        npc = self.ailin()
        npc.remember(ev["memory"])
        npc.romance = min(100, npc.romance + ev["romance"])
        npc.favorability = min(100, npc.favorability + ev["favor"])
        return f"【{ev['memory']}】感情 +{ev['romance']} / 好感 +{ev['favor']}"

    def ailin_confession_ready(self):
        npc = self.ailin()
        return (not npc.route and "告白前夜" in npc.memory
                and npc.romance >= 90 and npc.favorability >= 80)

    def apply_confession_ending(self, choice):
        npc = self.ailin()
        if choice == "good":
            npc.route = "恋人"
            npc.romance = 100
            npc.remember("与艾琳告白·恋人")
            self.last_message = "艾琳沉默了很久，然后，轻轻握住了你的手。（GOOD END · 恋人）"
        elif choice == "true":
            npc.route = "并肩"
            npc.romance = 100
            npc.remember("与艾琳告白·并肩")
            self.last_message = "她愣了一下，反而笑了：「……嗯，至少你没骗我。」（TRUE END · 并肩）"
        else:
            npc.route = "错过"
            npc.romance = max(0, npc.romance - 30)
            npc.remember("与艾琳告白·错过")
            self.last_message = "她松开手：「……我明白了。」（NORMAL END · 错过）"
        return self.last_message

    # ---- 组队伙伴 ----
    def companion_names(self):
        return {c.name for c in self.companions}

    def recruit_companion(self, npc_index=None):
        if len(self.companions) >= self.max_companions:
            return f"队伍已满（最多 {self.max_companions} 名伙伴）"
        if npc_index is None:
            for i, npc in enumerate(self.npcs):
                if npc.name not in self.companion_names() and npc.favorability >= 40:
                    npc_index = i
                    break
            if npc_index is None:
                return "没有可招募的伙伴（好感需 ≥40）"
        npc = self.npcs[npc_index]
        if npc.name in self.companion_names():
            return f"{npc.name} 已经在队伍里了"
        if npc.favorability < 40:
            return f"{npc.name} 还不想跟你冒险（好感需 ≥40，当前 {npc.favorability}）"
        role = npc.personality_tags[0] if npc.personality_tags else "豪爽"
        stats = COMPANION_STATS.get(role, COMPANION_STATS["豪爽"])
        bonus = npc.favorability // 20
        comp = Companion(
            name=npc.name,
            max_hp=stats["hp"] + bonus * 5, hp=stats["hp"] + bonus * 5,
            attack=stats["attack"] + bonus, speed=stats["speed"], defense=stats["defense"],
            max_mp=stats["max_mp"], mp=stats["max_mp"], behavior=stats["behavior"],
        )
        self.companions.append(comp)
        self.companion_behaviors[npc.name] = stats["behavior"]
        return f"{npc.name} 加入了队伍！（HP {comp.hp} / 攻 {comp.attack}）"

    def dismiss_companions(self):
        self.companions = []
        self.companion_behaviors = {}

    def companion_by_name(self, name):
        return next((c for c in self.companions if c.name == name), None)

    def companion_skill(self, comp):
        table = COMPANION_SKILL_TABLE.get(comp.behavior, COMPANION_SKILL_TABLE["heavy"])
        return table.get(comp.skill_level, table[1])

    def companion_skill_name(self, comp):
        return self.companion_skill(comp)["name"]

    def upgrade_companion(self, name):
        """花金币升级伙伴技能（最高 Lv3）。艾琳升到 Lv2 解锁补蓝术。"""
        comp = self.companion_by_name(name)
        if comp is None:
            return "队伍里没有这名伙伴"
        if comp.skill_level >= 3:
            return f"{comp.name} 的技能已经满级（Lv3）"
        cost = COMPANION_SKILL_UPGRADE_COST.get(comp.skill_level, 999)
        if self.player.money < cost:
            return f"金币不足（升级需要 {cost}，当前 {self.player.money}）"
        self.player.money -= cost
        comp.skill_level += 1
        skill = self.companion_skill(comp)
        extra = ""
        if comp.behavior == "heal" and comp.skill_level == 2:
            extra = "，并解锁了【补蓝术】"
        return f"{comp.name} 的技能升级为「{skill['name']}」Lv{comp.skill_level}{extra}（-{cost} 金币）"

    # ---- 夜晚 / 住宿 ----
    def _street_night(self):
        event = random.choices(["robbed", "cold", "lucky", "calm"], weights=[2, 2, 1, 3])[0]
        if event == "robbed":
            self.player.hp = max(1, self.player.hp - 15)
            return "露宿街头，被流浪汉袭击！HP -15（没睡好，MP 未恢复）"
        if event == "cold":
            self.player.hp = max(1, self.player.hp - 10)
            self.player.mp = min(self.player.max_mp, self.player.mp + self.player.max_mp // 5)
            return "露宿街头，夜里受寒！HP -10（勉强回了点 MP）"
        if event == "lucky":
            self.player.money += 5
            self.player.mp = min(self.player.max_mp, self.player.mp + self.player.max_mp // 4)
            return "露宿街头，却在角落捡到 5 金币（睡了个好觉，MP 小回复）"
        self.player.mp = min(self.player.max_mp, self.player.mp + self.player.max_mp // 4)
        return "露宿街头，勉强熬过一夜（MP 小回复）"

    def _pay_lodging(self):
        if self.player.honor < 0:
            return "恶名在外，酒馆拒绝让你入住！" + " " + self._street_night()
        if self.player.money >= self.lodging_cost:
            self.player.money -= self.lodging_cost
            self.player.mp = self.player.max_mp
            return f"在酒馆过夜，住宿费 -{self.lodging_cost} 金币（MP 回满）"
        self.player.money = 0
        return self._street_night()

    def _roll_today_event(self):
        ev = random.choice(TODAY_EVENTS)
        self.today_event = ev
        if ev["id"] == "market":
            self.market_day = self.day
            self.market_shift = -0.10
        return ev

    def _advance_day(self):
        text = self._pay_lodging()
        self.day += 1
        self.action_points = self.max_action_points
        ev = self._roll_today_event()
        text += f"；今日：{ev['name']}（{ev['desc']}）"
        return text

    def end_day(self):
        msg = self._advance_day()
        self.last_message = msg
        return msg

    # ---- 地下城 ----
    def start_dungeon(self):
        self.floor = 1
        self.rooms_explored = 0
        self.pending_gold = 0
        self.pending_exp = 0
        self.earned_gold = 0

    def depth_multiplier(self) -> float:
        # 越深越强，但收益也越高（对应「继续 vs 回城」的风险回报）
        return 1.2 ** (self.floor - 1)

    def floor_template(self) -> DungeonFloor:
        if self.floor <= len(self.dungeon):
            return self.dungeon[self.floor - 1]
        return self.dungeon[-1]

    def _scale(self, m: Monster) -> Monster:
        k = self.depth_multiplier()
        return Monster(monster_id=m.monster_id, name=m.name,
                       hp=max(1, round(m.hp * k)), attack=max(1, round(m.attack * k)),
                       speed=max(1, round(m.speed * k)), exp_reward=m.exp_reward,
                       money_reward=m.money_reward, defense=m.defense)

    def prepare_encounter(self) -> List[Monster]:
        template = random.choice(self.floor_template().monster_pool)
        self.current_enemies = [self._scale(template)]
        return self.current_enemies

    def prepare_adventurer_ambush(self) -> List[Monster]:
        base = [
            Monster(monster_id="rogue", name="敌对冒险者·盗贼",
                    hp=35, attack=8, speed=7, exp_reward=25, money_reward=45),
            Monster(monster_id="blade", name="敌对冒险者·剑客",
                    hp=45, attack=10, speed=5, exp_reward=30, money_reward=55),
        ]
        self.current_enemies = [self._scale(m) for m in base]
        return self.current_enemies

    def on_win(self, enemies: List[Monster]):
        gold = 0
        for m in enemies:
            self.pending_gold += m.money_reward
            self.pending_exp += m.exp_reward
            self.earned_gold += m.money_reward
            gold += m.money_reward
        # 每日事件：魔物躁动 → 金币 +20%
        if self.today_event and self.today_event["id"] == "raid":
            bonus = sum(round(m.money_reward * 0.2) for m in enemies)
            self.pending_gold += bonus
            self.earned_gold += bonus
            gold += bonus
        self._track_quest("kill", len(enemies))
        self._track_quest("gold", gold)
        item = self._roll_loot_item(0.35)
        return [item] if item else []

    def explore_room(self) -> str:
        self._track_quest("depth")
        if self.rooms_explored >= self.rooms_per_floor:
            self.descend()
            return "descend"
        self.rooms_explored += 1
        return self.roll_room_event()

    def descend(self):
        self.floor += 1
        self.rooms_explored = 0

    def roll_room_event(self) -> str:
        weights = FLOOR1_EVENT_WEIGHTS if self.floor < 2 else DUNGEON_EVENT_WEIGHTS
        kinds = list(weights)
        w = [weights[k] for k in kinds]
        return random.choices(kinds, weights=w)[0]

    def _roll_loot_item(self, chance=0.35):
        if random.random() > chance:
            return None
        item_id = random.choices(LOOT_POOL, weights=LOOT_WEIGHTS)[0]
        item = make_item(item_id)
        if item.item_type == "装备":
            apply_affix(item)
        self.player.add_item(item)
        return item

    def resolve_wounded(self, choice: str) -> str:
        if choice == "help":
            if random.random() < 0.2:
                self.player.hp = max(1, self.player.hp - 30)
                return "你扶起他，他却从背后捅了你一刀！HP -30"
            gold, exp = 30, 20
            self.pending_gold += gold
            self.pending_exp += exp
            self.earned_gold += gold
            self.player.honor += 5
            self._track_quest("honor", 1)
            return f"你帮他包扎伤口，他塞给你 {gold} 金币作为谢礼（经验 +{exp}，荣誉 +5）"
        if choice == "rob":
            gold, exp = 120, 30
            self.pending_gold += gold
            self.pending_exp += exp
            self.earned_gold += gold
            self.player.honor -= 20
            return f"你杀人夺宝，搜刮到 {gold} 金币（经验 +{exp}，恶名 +20）"
        return "你选择无视，转身离开。"

    def apply_chest(self):
        gold = random.randint(10, 30)
        self.pending_gold += gold
        self.earned_gold += gold
        self._track_quest("gold", gold)
        item = self._roll_loot_item(0.6)
        return gold, item

    def apply_trap(self):
        dmg = random.randint(8, 15)
        self.player.hp = max(0, self.player.hp - dmg)
        return dmg, self.player.hp <= 0

    def return_to_town(self):
        gold, exp = self.pending_gold, self.pending_exp
        # 每日事件：冒险者节 → 经验 +20%
        if self.today_event and self.today_event["id"] == "festival":
            exp = round(exp * 1.2)
        self.player.money += gold
        leveled = self.player.gain_exp(exp)
        tags = [f"深入地下城第{self.floor}层"]
        if self.earned_gold > 0:
            tags.append("满载而归")
        for npc in self.npcs:
            for t in tags:
                npc.remember(t)
        self.pending_gold = 0
        self.pending_exp = 0
        self.floor = 1
        self.rooms_explored = 0
        lodging = self._advance_day()
        partner = ""
        if self.companions:
            names = "、".join(c.name for c in self.companions)
            partner = f"；伙伴 {names} 已离队"
            self.dismiss_companions()
        self.last_message = f"回城结算：金币 +{gold}，经验 +{exp}；{lodging}{partner}"
        return gold, exp, leveled, tags

    def on_death(self):
        lost = self.player.money - self.player.money // 2
        self.player.money //= 2
        self.player.hp = max(1, self.player.max_hp // 5)
        for npc in self.npcs:
            npc.remember("铩羽而归")
        # 风险：战败还会丢掉一件背包物品
        lost_item = None
        if self.player.inventory:
            idx = random.randrange(len(self.player.inventory))
            lost_item = self.player.inventory.pop(idx)
        self.floor = 1
        self.rooms_explored = 0
        lodging = self._advance_day()
        partner = ""
        if self.companions:
            names = "、".join(c.name for c in self.companions)
            partner = f"；伙伴 {names} 也受了重伤，已离队"
            self.dismiss_companions()
        item_txt = f"，还弄丢了「{lost_item.name}」" if lost_item else ""
        self.last_message = f"战败：金币损失 {lost}，剩余 {self.player.money}{item_txt}；{lodging}{partner}"
        return lost

    # ---- 存档读档 ----
    def save(self, path):
        save_game(path, self.player, self.npcs, self.dungeon, meta={
            "day": self.day,
            "action_points": self.action_points,
            "quests": self.quests,
            "market_day": self.market_day,
            "market_shift": self.market_shift,
            "item_demand": self.item_demand,
            "today_event": self.today_event,
        })

    def load(self, path):
        p, n, d, meta = load_game(path)
        self.player, self.npcs, self.dungeon = p, n, d
        self.day = meta.get("day", 1)
        self.action_points = meta.get("action_points", self.max_action_points)
        self.quests = meta.get("quests", self.quests)
        self.market_day = meta.get("market_day", 0)
        self.market_shift = meta.get("market_shift", 0.0)
        self.item_demand = meta.get("item_demand", {})
        self.today_event = meta.get("today_event", self.today_event)


class BattleController:
    """交互式战斗（多敌人、多队友）。"""

    def __init__(self, player: Player, monsters: List[Monster],
                 allies: List[Companion] = None, ally_behaviors: dict = None):
        self.player_obj = player
        self.companion_objs = allies or []
        self.monster_objs = monsters
        self.ally_behaviors = ally_behaviors or {}
        self.battle = BattleSystem(player, monsters, allies=allies, verbose=False)
        self.battle.start()
        self.round = 0
        self.order = []
        self.order_idx = 0
        self.current_actor = None
        self.awaiting_player = False
        self.ally_acting = False
        self.enemy_acting = False
        self.over = False
        self.enemy_timer = 0.0
        self.ally_timer = 0.0
        self.begin_round()

    def sync_to_player(self):
        self.player_obj.hp = self.battle.player.hp
        self.player_obj.mp = self.battle.player.mp

    def sync_to_companions(self, companions):
        for comp, fighter in zip(companions, self.battle.allies):
            comp.hp = fighter.hp
            comp.mp = fighter.mp

    @property
    def player(self):
        return self.battle.player

    @property
    def allies(self):
        return self.battle.allies

    @property
    def enemies(self):
        return self.battle.enemies

    def alive_enemies(self):
        return [e for e in self.battle.enemies if e.is_alive]

    def player_side_alive(self):
        return self.battle.player_side_alive()

    def begin_round(self):
        if self.over:
            return
        self.round += 1
        if self.round > 1:
            self.battle.tick_poison()
            self.battle.check_end()
            if self.battle.over:
                self.over = True
                return
            p = self.battle.player
            if p.mp_regen > 0 and p.is_alive:
                before = p.mp
                p.mp = min(p.max_mp, p.mp + p.mp_regen)
                if p.mp != before:
                    self.battle._log(f"{p.name} 回蓝 +{p.mp - before}（{p.mp}/{p.max_mp}）")
        self.order = [f for f in self.battle.turn_order() if f.is_alive]
        self.order_idx = 0
        self.advance()

    def advance(self):
        if self.over:
            return
        while self.order_idx < len(self.order) and not self.order[self.order_idx].is_alive:
            self.order_idx += 1
        if self.order_idx >= len(self.order):
            self.begin_round()
            return
        actor = self.order[self.order_idx]
        actor.tick_cooldowns()
        self.current_actor = actor
        if actor.side == "player":
            if actor is self.battle.player:
                self.awaiting_player = True
            else:
                self.awaiting_player = False
                self.ally_acting = True
                self.ally_timer = 0.0
        else:
            self.awaiting_player = False
            self.enemy_acting = True
            self.enemy_timer = 0.0

    def player_act(self, skill, target_index=0):
        if not self.awaiting_player or self.over:
            return
        alive = self.alive_enemies()
        if not alive:
            return
        enemies = self.battle.enemies
        if 0 <= target_index < len(enemies) and enemies[target_index].is_alive:
            target = enemies[target_index]
        else:
            target = alive[0]
        self.battle.perform_action(self.player, target, skill, targets=alive)
        self.awaiting_player = False
        self.battle.check_end()
        if self.battle.over:
            self.over = True
            return
        self.order_idx += 1
        self.advance()

    def _ally_take_turn(self):
        ally = self.current_actor
        behavior = self.ally_behaviors.get(ally.name, "normal")
        comp = next((c for c in self.companion_objs if c.name == ally.name), None)
        level = comp.skill_level if comp else 1
        table = COMPANION_SKILL_TABLE.get(behavior, COMPANION_SKILL_TABLE["heavy"])
        skill = table.get(level, table[1])
        enemies = self.alive_enemies()

        if behavior == "heal":
            others = [f for f in self.player_side_alive() if f is not ally]
            hurt = [f for f in others if f.hp < f.max_hp]
            badly_hurt = [f for f in others if f.hp < f.max_hp * 0.5]
            need_mp = [f for f in others if f.max_mp > 0 and f.mp < f.max_mp * 0.4]
            # 补蓝：技能 Lv2+ 解锁；没人危急时，给最缺蓝的队友回蓝
            if level >= 2 and not badly_hurt and need_mp:
                if ally.mp >= MANA_RESTORE["mp_cost"]:
                    ally.mp -= MANA_RESTORE["mp_cost"]
                    target = min(need_mp, key=lambda f: f.mp / max(1, f.max_mp))
                    target.mp = min(target.max_mp, target.mp + MANA_RESTORE["mp_restore"])
                    self.battle._log(f"{ally.name} 施放【补蓝术】，{target.name} 回复 {MANA_RESTORE['mp_restore']} MP")
                    return
            if hurt:
                if ally.mp < skill["mp_cost"]:
                    self.battle._log(f"{ally.name} 蓝量不足，无法施放【{skill['name']}】，选择防御")
                    return
                ally.mp -= skill["mp_cost"]
                if skill.get("aoe"):
                    for f in hurt:
                        f.hp = min(f.max_hp, f.hp + skill["heal"])
                    self.battle._log(f"{ally.name} 施放【{skill['name']}】，全队回复 {skill['heal']} HP")
                else:
                    target = min(hurt, key=lambda f: f.hp / max(1, f.max_hp))
                    target.hp = min(target.max_hp, target.hp + skill["heal"])
                    self.battle._log(f"{ally.name} 施放【{skill['name']}】，{target.name} 回复 {skill['heal']} HP")
                return
            self.battle._log(f"{ally.name} 见全队状态良好，选择防御")
            return
        elif behavior == "aoe" and enemies:
            if ally.mp < skill["mp_cost"]:
                self.battle._log(f"{ally.name} 蓝量不足，无法施放【{skill['name']}】，选择防御")
                return
            cast = Skill(skill_id="curse", name=skill["name"], multiplier=skill["multiplier"],
                         mp_cost=skill["mp_cost"], aoe=True)
            self.battle.perform_action(ally, enemies[0], cast, targets=enemies)
            return
        elif behavior == "heavy" and enemies:
            if ally.mp < skill["mp_cost"]:
                self.battle.perform_action(ally, enemies[0], NORMAL_ATTACK)
                return
            cast = Skill(skill_id="heavy", name=skill["name"], multiplier=skill["multiplier"],
                         mp_cost=skill["mp_cost"])
            self.battle.perform_action(ally, enemies[0], cast)
            return
        if enemies:
            self.battle.perform_action(ally, enemies[0], NORMAL_ATTACK)

    def _enemy_target(self):
        side = self.player_side_alive()
        if not side:
            return None
        healers = [f for f in side if self.ally_behaviors.get(f.name) == "heal"]
        if healers and random.random() < 0.6:
            return random.choice(healers)
        return random.choice(side)

    def _enemy_special(self):
        """按 monster_id 触发敌人特殊技（提高战斗深度）。"""
        if self.current_actor not in self.battle.enemies:
            return None
        idx = self.battle.enemies.index(self.current_actor)
        if idx >= len(self.monster_objs):
            return None
        spec = ENEMY_SPECIALS.get(self.monster_objs[idx].monster_id)
        if spec and random.random() < spec["chance"]:
            self.battle._log(f"{self.current_actor.name} 使出【{spec['name']}】！")
            return spec
        return None

    def update(self, dt):
        if self.ally_acting and not self.over and self.current_actor is not None:
            self.ally_timer += dt
            if self.ally_timer >= 0.6:
                self.ally_acting = False
                self._ally_take_turn()
                self.battle.check_end()
                if self.battle.over:
                    self.over = True
                    return
                self.order_idx += 1
                self.advance()
        elif self.enemy_acting and not self.over and self.current_actor is not None:
            self.enemy_timer += dt
            if self.enemy_timer >= 0.6:
                self.enemy_acting = False
                target = self._enemy_target()
                if target is not None:
                    spec = self._enemy_special()
                    if spec:
                        skill = Skill(skill_id="special", name=spec["name"],
                                      multiplier=spec["mult"], mp_cost=0,
                                      aoe=spec.get("aoe", False))
                        targets = self.player_side_alive() if spec.get("aoe") else None
                        self.battle.perform_action(self.current_actor, target, skill, targets=targets)
                    else:
                        self.battle.perform_action(self.current_actor, target, NORMAL_ATTACK)
                self.battle.check_end()
                if self.battle.over:
                    self.over = True
                    return
                self.order_idx += 1
                self.advance()

    def usable_actions(self):
        return self.battle.usable_actions(self.player) if self.awaiting_player else []

    def log_lines(self, n=9):
        return self.battle.log[-n:]

    @property
    def winner(self):
        return self.battle.winner
