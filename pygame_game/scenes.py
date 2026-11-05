"""场景：标题 / 城镇 / 地下城 / 战斗 / 背包 / 商店。"""
import random

import pygame

from . import theme, sound, assets
from .widgets import Button, Bar, Panel, draw_text
from .controller import BattleController, COMPANION_SKILL_UPGRADE_COST
from .story import CONFESSION_BEATS, CONFESSION_CHOICES
from .items import EQUIP_SLOTS
from core.dialogue import generate_dialogue, player_status_label

_NPC_COLORS = [(230, 150, 120), (120, 180, 230), (170, 130, 230), (240, 180, 120)]
_PLAYER_COLOR = theme.BLUE
_MONSTER_COLOR = theme.RED


def _wrap(text, font, max_width):
    lines = []
    for raw in text.split("\n"):
        cur = ""
        for ch in raw:
            if font.size(cur + ch)[0] > max_width and cur:
                lines.append(cur)
                cur = ch
            else:
                cur += ch
        lines.append(cur)
    return lines


class TitleScene:
    def __init__(self, app):
        self.app = app
        self.new_button = Button((theme.WIDTH // 2 - 130, 360, 260, 64), "新游戏", self.on_new)
        self.continue_button = None
        if app.has_save():
            self.continue_button = Button((theme.WIDTH // 2 - 130, 450, 260, 64), "继续（读档）", self.on_continue)

    def on_new(self):
        self.app.new_game()

    def on_continue(self):
        self.app.continue_game()

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            self.on_new()
            return
        self.new_button.handle_event(event)
        if self.continue_button:
            self.continue_button.handle_event(event)

    def update(self, dt):
        pass

    def draw(self, surface):
        surface.fill(theme.BG_TOWN)
        draw_text(surface, "双循环 RPG", (theme.WIDTH // 2, 200), 68, theme.ACCENT, bold=True, center=True)
        draw_text(surface, "日常 × 地下城 原型", (theme.WIDTH // 2, 288), 26, theme.TEXT_DIM, center=True)
        self.new_button.draw(surface)
        if self.continue_button:
            self.continue_button.draw(surface)
        draw_text(surface, "按 Enter 开始", (theme.WIDTH // 2, 560), 20, theme.TEXT_DIM, center=True)


class TownScene:
    """日常：活动 / 聊天 / 背包 / 商店 / 修道院 / 脱衣。"""

    def __init__(self, app):
        self.app = app
        self.c = app.controller
        self.dialog = None
        self.dialog_index = 0
        self.option_buttons = []
        self.smalltalk_remaining = 2
        self.gifts_remaining = 1
        self.dates_remaining = 1
        self.message = self.c.last_message or ""
        self._build()

    def _build(self):
        self.activity_buttons = [
            Button((40, 150, 380, 56), "休息（-1AP 回血30/回蓝15）", self.on_rest),
            Button((40, 216, 380, 56), "锻炼（-1AP 随机属性）", self.on_train),
            Button((40, 282, 380, 56), "打工（-1AP 金币+30）", self.on_work),
        ]
        self._rebuild_npc_buttons()
        self.recruit_button = Button((40, 360, 380, 56), "招募伙伴（好感≥40，最多2人）", self.on_recruit)
        self.naked_button = Button((40, 424, 380, 48), "脱衣 / 穿衣", self.on_naked)
        self.end_day_button = Button((60, 600, 160, 60), "结束当天", self.on_end_day)
        self.dungeon_button = Button((235, 600, 175, 60), "前往地下城", self.on_dungeon)
        self.backpack_button = Button((425, 600, 120, 60), "背包", self.on_backpack)
        self.shop_button = Button((560, 600, 120, 60), "商店", self.on_shop)
        self.confess_button = Button((695, 600, 175, 60), "修道院（忏悔）", self.on_confess)
        self.save_button = Button((1005, 600, 200, 60), "存档", self.on_save)
        self.close_dialog_button = Button((930, 452, 120, 44), "离开", self.on_close_dialog)
        self._rebuild_companion_buttons()

    def _rebuild_companion_buttons(self):
        self.companion_buttons = []
        y = 460
        for comp in self.c.companions:
            if comp.skill_level >= 3:
                btn = Button((960, y, 280, 40), f"{comp.name} 技能 Lv3（满级）", lambda: None)
                btn.enabled = False
            else:
                cost = COMPANION_SKILL_UPGRADE_COST.get(comp.skill_level, 999)
                label = f"{comp.name} 技能 Lv{comp.skill_level} → 升级（{cost}金）"
                btn = Button((960, y, 280, 40), label,
                             lambda n=comp.name: self.on_upgrade_companion(n))
            self.companion_buttons.append(btn)
            y += 48

    def on_upgrade_companion(self, name):
        self.message = self.c.upgrade_companion(name)
        self._rebuild_companion_buttons()

    def _rebuild_npc_buttons(self):
        self.npc_buttons = []
        y = 150
        for i, npc in enumerate(self.c.npcs):
            label = f"{npc.name}  好感 {npc.favorability}  记忆 {len(npc.memory)}"
            self.npc_buttons.append(Button((470, y, 450, 56), label, lambda i=i: self.on_chat(i)))
            y += 66

    def on_chat(self, i):
        if self.c.action_points <= 0:
            self.message = "行动点耗尽，无法聊天"
            return
        # 艾琳剧情 / 告白优先
        if i == 0:
            if self.c.ailin_confession_ready():
                self._start_confession()
                return
            ev = self.c.ailin_event_ready()
            if ev is not None:
                self._start_ailin_event(ev)
                return
        self.dialog_index = i
        self.dialog = self.c.chat(i)
        self.message = ""
        self.smalltalk_remaining = 2
        self.gifts_remaining = 1
        self.dates_remaining = 1
        self._rebuild_dialog_buttons()
        self._rebuild_npc_buttons()

    def _start_ailin_event(self, ev):
        self.c.action_points -= 1

        def finish():
            self.c.last_message = self.c.apply_ailin_event(ev)
            self.app.goto_town()

        self.app.story(ev["beats"], on_finish=finish)

    def _start_confession(self):
        def make_cb(choice):
            def cb():
                self.c.apply_confession_ending(choice)
                self.app.goto_town()
            return cb

        choices = [(label, make_cb(c)) for label, c in CONFESSION_CHOICES]
        self.app.story(CONFESSION_BEATS, choices=choices)

    def _rebuild_dialog_buttons(self):
        self.option_buttons = []
        if not self.dialog:
            return
        x, y = 230, 452
        for i, opt in enumerate(self.dialog.options):
            if opt == "聊点别的" and self.smalltalk_remaining <= 0:
                continue
            if opt == "送你个小礼物" and self.gifts_remaining <= 0:
                continue
            if opt == "约会" and self.dates_remaining <= 0:
                continue
            self.option_buttons.append(Button((x, y, 180, 44), opt, lambda i=i: self.on_option(i)))
            x += 196

    def on_option(self, idx):
        npc = self.c.npcs[self.dialog_index]
        opt = self.dialog.options[idx]
        if "礼物" in opt:
            if self.gifts_remaining <= 0:
                self.message = "已经送过礼物了，改天吧"
            elif self.c.player.money >= 10:
                self.gifts_remaining -= 1
                self.c.player.money -= 10
                delta = npc.change_favorability(5)
                self.message = f"送给{npc.name}礼物，好感 +{delta}（金币 -10）"
            else:
                self.message = "金币不足，买不起礼物"
        elif "冒险" in opt:
            delta = npc.change_favorability(8)
            self.message = f"约{npc.name}一起冒险，好感 +{delta}"
        elif "约会" in opt:
            if self.dates_remaining <= 0:
                self.message = "今天已经陪 TA 很久了，改天吧"
            else:
                self.dates_remaining -= 1
                self.message = self.c.date_npc(npc)
        else:  # 聊点别的
            if self.smalltalk_remaining <= 0:
                self.message = "聊得差不多了，该换个话题了"
            else:
                self.smalltalk_remaining -= 1
                delta = npc.change_favorability(random.randint(-2, 4))
                if delta > 0:
                    self.message = f"你们聊得很投机，好感 +{delta}"
                elif delta < 0:
                    self.message = f"话不投机，好感 {delta}"
                else:
                    self.message = "聊了会儿，没什么感觉"
        self.dialog = generate_dialogue(npc, self.c.player)
        self._rebuild_dialog_buttons()
        self._rebuild_npc_buttons()

    def on_close_dialog(self):
        self.dialog = None
        self.option_buttons = []
        self._rebuild_npc_buttons()

    def on_rest(self):
        self.message = self.c.rest()

    def on_train(self):
        self.message = self.c.train()

    def on_work(self):
        self.message = self.c.work()

    def on_end_day(self):
        self.message = self.c.end_day()

    def on_recruit(self):
        self.message = self.c.recruit_companion()
        self._rebuild_companion_buttons()

    def on_naked(self):
        self.c.player.naked = not self.c.player.naked
        self.message = "你把外衣脱了……" if self.c.player.naked else "你重新穿好衣服。"

    def on_dungeon(self):
        self.c.start_dungeon()
        self.app.goto_dungeon("explore")

    def on_save(self):
        self.c.save(self.app.save_path)
        self.message = "已存档"

    def on_backpack(self):
        self.app.goto_backpack("town")

    def on_shop(self):
        self.app.goto_city()

    def on_confess(self):
        self.message = self.c.confess()

    def handle_event(self, event):
        if self.dialog is not None:
            for b in self.option_buttons:
                b.handle_event(event)
            self.close_dialog_button.handle_event(event)
            return
        for b in self.activity_buttons:
            b.handle_event(event)
        for b in self.npc_buttons:
            b.handle_event(event)
        self.recruit_button.handle_event(event)
        self.naked_button.handle_event(event)
        self.end_day_button.handle_event(event)
        self.dungeon_button.handle_event(event)
        self.backpack_button.handle_event(event)
        self.shop_button.handle_event(event)
        self.confess_button.handle_event(event)
        self.save_button.handle_event(event)
        for b in self.companion_buttons:
            b.handle_event(event)

    def update(self, dt):
        pass

    def draw(self, surface):
        surface.fill(theme.BG_TOWN)
        self._draw_hud(surface)
        draw_text(surface, "今日活动（消耗 1 行动点）", (40, 112), 22, theme.TEXT_DIM)
        for b in self.activity_buttons:
            b.draw(surface)
        self.recruit_button.draw(surface)
        self.naked_button.draw(surface)
        if self.c.companions:
            names = "、".join(c.name for c in self.c.companions)
            draw_text(surface, f"当前伙伴：{names}", (40, 486), 16, theme.GREEN)
        draw_text(surface, "居民（点击交谈，消耗 1 行动点）", (470, 112), 22, theme.TEXT_DIM)
        for b in self.npc_buttons:
            b.draw(surface)
        self._draw_status(surface)
        self.end_day_button.draw(surface)
        self.dungeon_button.draw(surface)
        self.backpack_button.draw(surface)
        self.shop_button.draw(surface)
        self.confess_button.draw(surface)
        self.save_button.draw(surface)
        for b in self.companion_buttons:
            b.draw(surface)
        if self.c.action_points <= 0:
            draw_text(surface, "行动点用完了：可以结束当天休息，或直接前往地下城", (60, 664), 18, theme.ACCENT)
        if self.message:
            draw_text(surface, self.message, (60, 684), 18, theme.ACCENT)
        if self.dialog is not None:
            self._draw_dialog(surface)

    def _draw_hud(self, surface):
        p = self.c.player
        pygame.draw.rect(surface, theme.PANEL, (0, 0, theme.WIDTH, 90))
        pygame.draw.line(surface, theme.BORDER, (0, 90), (theme.WIDTH, 90), 2)
        draw_text(surface, f"第 {self.c.day} 天", (24, 18), 26, bold=True)
        ap_color = theme.ACCENT if self.c.action_points > 0 else theme.RED
        draw_text(surface, f"行动点 {self.c.action_points}/{self.c.max_action_points}", (170, 22), 22, ap_color)
        draw_text(surface, f"金币 {p.money}", (340, 22), 22, theme.GOLD_COLOR)
        draw_text(surface, f"Lv.{p.level}  {p.rank.value}（{player_status_label(p)}）", (520, 22), 20, theme.ACCENT)
        Bar((790, 12, 240, 20), p.hp, p.max_hp, theme.HP_COLOR).draw(surface, f"HP {p.hp}/{p.max_hp}")
        Bar((790, 40, 240, 15), p.mp, p.max_mp, theme.MP_COLOR).draw(surface, f"MP {p.mp}/{p.max_mp}")
        draw_text(surface, f"攻击 {p.attack}  防御 {p.defense}  速度 {p.speed}", (1010, 16), 16, theme.TEXT_DIM)
        honor_text = f"荣誉 {p.honor}" if p.honor != 0 else "荣誉 0（无名之辈）"
        honor_color = theme.GREEN if p.honor > 0 else (theme.RED if p.honor < 0 else theme.TEXT_DIM)
        draw_text(surface, honor_text, (1050, 42), 16, honor_color)
        if self.c.today_event:
            ev = self.c.today_event
            draw_text(surface, f"今日：{ev['name']}（{ev['desc']}）", (24, 66), 15, theme.ACCENT)

    def _draw_status(self, surface):
        p = self.c.player
        Panel((960, 120, 280, 320)).draw(surface)
        x = 980
        draw_text(surface, "状态", (x, 134), 22, bold=True)
        draw_text(surface, f"攻击 {p.attack}", (x, 168), 18)
        draw_text(surface, f"防御 {p.defense}", (x, 192), 18)
        draw_text(surface, f"速度 {p.speed}", (x, 216), 18)
        honor = f"荣誉 {p.honor}" if p.honor != 0 else "荣誉 0"
        hc = theme.GREEN if p.honor > 0 else (theme.RED if p.honor < 0 else theme.TEXT)
        draw_text(surface, honor, (x, 240), 18, hc)
        draw_text(surface, f"背包 {len(p.inventory)} 件", (x, 270), 18)
        draw_text(surface, "技能", (x, 300), 18, theme.TEXT_DIM)
        yy = 324
        for s in p.skills[:3]:
            draw_text(surface, f"· {s.name}", (x, yy), 16, theme.TEXT_DIM)
            yy += 22

    def _draw_dialog(self, surface):
        dlg = self.dialog
        overlay = pygame.Surface((theme.WIDTH, theme.HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))
        surface.blit(overlay, (0, 0))
        Panel((200, 150, 880, 420)).draw(surface)
        color = _NPC_COLORS[self.dialog_index % len(_NPC_COLORS)]
        surface.blit(assets.sprite(f"npcs/{dlg.speaker}", color, 120), (230, 170))
        draw_text(surface, dlg.speaker, (380, 180), 30, bold=True)
        draw_text(surface, f"{dlg.emotion} · 好感 {dlg.favorability} · {dlg.tier} · 你：{dlg.player_status}",
                  (380, 224), 18, theme.TEXT_DIM)
        font = theme.get_font(24)
        y = 300
        for line in _wrap(dlg.text, font, 820)[:4]:
            draw_text(surface, line, (230, y), 24)
            y += 34
        for b in self.option_buttons:
            b.draw(surface)
        if self.message:
            draw_text(surface, self.message, (230, 512), 18, theme.ACCENT)
        self.close_dialog_button.draw(surface)


class DungeonScene:
    """地下城：探索房间 / 遭遇 / 伤员 / 结果。"""

    def __init__(self, app, mode):
        self.app = app
        self.c = app.controller
        self.mode = mode
        if mode == "explore":
            self.c.last_event_msg = ""
            self.explore_button = Button((theme.WIDTH // 2 - 130, 470, 260, 60), "探索房间", self.on_explore)
        elif mode == "encounter":
            self.fight_button = Button((theme.WIDTH // 2 - 100, 500, 200, 60), "开战", self.on_fight)
        elif mode == "wounded":
            self.help_button = Button((240, 430, 220, 60), "帮他", lambda: self.on_wounded("help"))
            self.rob_button = Button((530, 430, 220, 60), "杀人夺宝", lambda: self.on_wounded("rob"))
            self.ignore_button = Button((820, 430, 220, 60), "无视离开", lambda: self.on_wounded("ignore"))
        else:
            self.continue_button = Button((400, 380, 200, 60), "继续探索", self.on_continue)
            self.return_button = Button((680, 380, 200, 60), "回城", self.on_return)
            self.backpack_button = Button((540, 460, 200, 50), "打开背包补给", self.on_open_backpack)

    def on_explore(self):
        event = self.c.explore_room()
        if event == "descend":
            self.c.last_event_msg = f"本层探索完毕，找到入口，下到第 {self.c.floor} 层"
            return
        if event == "entrance":
            self.c.descend()
            self.c.last_event_msg = f"发现下一层入口！直接下到第 {self.c.floor} 层"
            return
        if event == "enemy":
            self.c.prepare_encounter()
            self.c.last_event_msg = "遭遇敌人……"
            self.app.goto_dungeon("encounter")
        elif event == "adventurer":
            self.c.prepare_adventurer_ambush()
            self.c.last_event_msg = "遭遇敌对冒险者！"
            self.app.goto_dungeon("encounter")
        elif event == "wounded":
            self.app.goto_dungeon("wounded")
        elif event == "chest":
            gold, item = self.c.apply_chest()
            msg = f"发现宝箱！获得 {gold} 金币"
            if item:
                msg += f"，还有 {item.name} ×{item.quantity}"
            self.c.last_event_msg = msg
            self.app.goto_dungeon("result")
        else:
            dmg, dead = self.c.apply_trap()
            if dead:
                self.c.on_death()
                self.app.goto_town()
            else:
                self.c.last_event_msg = f"踩中陷阱！受到 {dmg} 点伤害"
                self.app.goto_dungeon("result")

    def on_wounded(self, choice):
        self.c.last_event_msg = self.c.resolve_wounded(choice)
        self.app.goto_dungeon("result")

    def on_fight(self):
        self.app.goto_battle()

    def on_continue(self):
        self.app.goto_dungeon("explore")

    def on_return(self):
        self.c.return_to_town()
        self.app.goto_town()

    def on_open_backpack(self):
        self.app.goto_backpack("dungeon")

    def handle_event(self, event):
        if self.mode == "explore":
            self.explore_button.handle_event(event)
        elif self.mode == "encounter":
            self.fight_button.handle_event(event)
        elif self.mode == "wounded":
            self.help_button.handle_event(event)
            self.rob_button.handle_event(event)
            self.ignore_button.handle_event(event)
        else:
            self.continue_button.handle_event(event)
            self.return_button.handle_event(event)
            self.backpack_button.handle_event(event)

    def update(self, dt):
        pass

    def draw(self, surface):
        surface.fill(theme.BG_DUNGEON)
        draw_text(surface, f"地下城 · 第 {self.c.floor} 层", (theme.WIDTH // 2, 48), 32, bold=True, center=True)
        draw_text(surface, f"怪物属性 ×{self.c.depth_multiplier():.2f}", (theme.WIDTH // 2, 92), 20, theme.TEXT_DIM, center=True)
        if self.mode == "explore":
            self.explore_button.label = (
                "寻找下一层入口" if self.c.rooms_explored >= self.c.rooms_per_floor
                else f"探索房间（{self.c.rooms_explored}/{self.c.rooms_per_floor}）"
            )
            draw_text(surface, "探索中……", (theme.WIDTH // 2, 190), 30, theme.ACCENT, bold=True, center=True)
            draw_text(surface, f"本层已探索房间：{self.c.rooms_explored}/{self.c.rooms_per_floor}",
                      (theme.WIDTH // 2, 260), 22, theme.TEXT_DIM, center=True)
            draw_text(surface, "探索可能遭遇：敌人 / 冒险者 / 伤员 / 宝箱 / 陷阱 / 入口",
                      (theme.WIDTH // 2, 300), 20, theme.TEXT_DIM, center=True)
            if self.c.last_event_msg:
                draw_text(surface, self.c.last_event_msg, (theme.WIDTH // 2, 360), 20, theme.ACCENT, center=True)
            self.explore_button.draw(surface)
        elif self.mode == "encounter":
            draw_text(surface, "遭遇敌人！", (theme.WIDTH // 2, 150), 30, theme.RED, bold=True, center=True)
            self._draw_enemy_preview(surface)
            self.fight_button.draw(surface)
        elif self.mode == "wounded":
            draw_text(surface, "发现受伤的冒险者", (theme.WIDTH // 2, 140), 30, theme.ACCENT, bold=True, center=True)
            surface.blit(assets.sprite("events/wounded", (200, 120, 90), 120), (theme.WIDTH // 2 - 60, 200))
            draw_text(surface, "他倒在血泊中，虚弱地向你伸出手……", (theme.WIDTH // 2, 350), 22, theme.TEXT_DIM, center=True)
            self.help_button.draw(surface)
            self.rob_button.draw(surface)
            self.ignore_button.draw(surface)
            draw_text(surface, "帮他（可能获谢礼，也可能被背刺）", (350, 500), 16, theme.TEXT_DIM, center=True)
            draw_text(surface, "杀人夺宝（大量金币，但恶名）", (640, 500), 16, theme.TEXT_DIM, center=True)
            draw_text(surface, "无视离开（无风险）", (930, 500), 16, theme.TEXT_DIM, center=True)
        else:
            draw_text(surface, "房间探索完毕", (theme.WIDTH // 2, 150), 30, theme.GREEN, bold=True, center=True)
            if self.c.last_event_msg:
                draw_text(surface, self.c.last_event_msg, (theme.WIDTH // 2, 200), 22, theme.ACCENT, center=True)
            draw_text(surface, f"待入账：金币 {self.c.pending_gold}、经验 {self.c.pending_exp}",
                      (theme.WIDTH // 2, 246), 22, center=True)
            draw_text(surface, f"本层已探索 {self.c.rooms_explored}/{self.c.rooms_per_floor} 个房间",
                      (theme.WIDTH // 2, 300), 22, theme.TEXT_DIM, center=True)
            self.continue_button.draw(surface)
            self.return_button.draw(surface)
            self.backpack_button.draw(surface)
            draw_text(surface, "继续探索（房间满 4 个后下一次自动下一层）", (500, 440), 15, theme.TEXT_DIM, center=True)
            draw_text(surface, "回城（保存当前金币与经验）", (780, 440), 15, theme.TEXT_DIM, center=True)
            draw_text(surface, "抉择期间可打开背包补给", (640, 520), 15, theme.ACCENT, center=True)

    def _draw_enemy_preview(self, surface):
        enemies = self.c.current_enemies
        n = len(enemies)
        spacing = 300
        start = theme.WIDTH // 2 - spacing * (n - 1) // 2
        for i, m in enumerate(enemies):
            cx = start + i * spacing
            surface.blit(assets.sprite(f"monsters/{m.monster_id}", _MONSTER_COLOR, 100), (cx - 50, 230))
            draw_text(surface, m.name, (cx, 350), 20, center=True)
            draw_text(surface, f"HP {m.hp} / 攻 {m.attack} / 速 {m.speed}", (cx, 378), 16, theme.TEXT_DIM, center=True)


class BattleScene:
    """回合制战斗界面（多敌人、多队友、点选目标）。"""

    def __init__(self, app):
        self.app = app
        self.controller = app.controller
        self.enemies = self.controller.current_enemies
        allies = self.controller.companions or None
        self.bc = BattleController(self.controller.player, self.enemies, allies=allies,
                                   ally_behaviors=self.controller.companion_behaviors)
        self.action_buttons = []
        self.end_timer = None
        self.target_index = 0
        self.shake = 0.0
        self.prev_player_hp = self.bc.player.hp
        self.floaters = []
        self.flash = {}
        self.prev_hp = {id(f): f.hp for f in
                        self.bc.battle.enemies + [self.bc.battle.player] + self.bc.battle.allies}
        self.rebuild_buttons()

    def rebuild_buttons(self):
        self.action_buttons = []
        if self.bc.awaiting_player and not self.bc.over:
            x, y = 60, 600
            for skill in self.bc.usable_actions():
                label = skill.name if skill.mp_cost == 0 else f"{skill.name} ({skill.mp_cost}MP)"
                self.action_buttons.append(Button((x, y, 190, 56), label, lambda s=skill: self.on_act(s)))
                x += 210

    def on_act(self, skill):
        self.bc.player_act(skill, self.target_index)
        self.rebuild_buttons()

    def _enemy_rects(self):
        centers = self._enemy_centers(len(self.bc.enemies))
        return [pygame.Rect(cx - 120, 110, 240, 200) for cx in centers]

    def handle_event(self, event):
        if self.bc.over:
            return
        if self.bc.awaiting_player and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for i, rect in enumerate(self._enemy_rects()):
                if rect.collidepoint(event.pos) and self.bc.enemies[i].is_alive:
                    self.target_index = i
                    break
        for b in self.action_buttons:
            b.handle_event(event)

    def update(self, dt):
        self.bc.update(dt)
        self._spawn_floaters()
        if self.bc.player.hp < self.prev_player_hp:
            self.shake = 0.25
        self.prev_player_hp = self.bc.player.hp
        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt)
        for fl in self.floaters:
            fl["y"] += fl["vy"] * dt
            fl["timer"] -= dt
        self.floaters = [fl for fl in self.floaters if fl["timer"] > 0]
        for k in list(self.flash):
            self.flash[k] -= dt
            if self.flash[k] <= 0:
                del self.flash[k]
        if self.bc.over:
            if self.end_timer is None:
                self.end_timer = 1.4
            self.end_timer -= dt
            if self.end_timer <= 0:
                self.app.battle_finished(self.bc.winner == "player")
            return
        if self.bc.awaiting_player and not self.action_buttons:
            self.rebuild_buttons()

    def _fighter_pos(self, f):
        if f is self.bc.battle.player:
            return (200, 430)
        if f in self.bc.battle.allies:
            return (400 + self.bc.battle.allies.index(f) * 150, 430)
        if f in self.bc.battle.enemies:
            i = self.bc.battle.enemies.index(f)
            return (self._enemy_centers(len(self.bc.battle.enemies))[i], 180)
        return (theme.WIDTH // 2, 360)

    def _spawn_floaters(self):
        fighters = self.bc.battle.enemies + [self.bc.battle.player] + self.bc.battle.allies
        for f in fighters:
            prev = self.prev_hp.get(id(f), f.hp)
            if f.hp < prev:
                x, y = self._fighter_pos(f)
                dmg = prev - f.hp
                crit = dmg >= 25
                self.floaters.append(dict(
                    text=f"-{dmg}", x=x + random.randint(-24, 24), y=y - 30,
                    color=theme.ACCENT if crit else theme.RED,
                    timer=0.9, vy=-45, size=30 if crit else 24))
                self.flash[id(f)] = 0.15
                if f is self.bc.battle.player:
                    sound.play("hurt")
                else:
                    sound.play("crit" if crit else "hit")
            elif f.hp > prev:
                x, y = self._fighter_pos(f)
                self.floaters.append(dict(
                    text=f"+{f.hp - prev}", x=x, y=y - 30,
                    color=theme.GREEN, timer=0.9, vy=-40, size=22))
                sound.play("heal")
            self.prev_hp[id(f)] = f.hp

    def _enemy_centers(self, n):
        if n == 1:
            return [theme.WIDTH // 2]
        spacing = 300
        start = theme.WIDTH // 2 - spacing * (n - 1) // 2
        return [start + i * spacing for i in range(n)]

    def draw(self, surface):
        surface.fill(theme.BG_BATTLE)
        draw_text(surface, f"地下城 · 第 {self.controller.floor} 层 · 战斗", (theme.WIDTH // 2, 26), 26, bold=True, center=True)
        fighters = self.bc.enemies
        centers = self._enemy_centers(len(fighters))
        for i, fighter in enumerate(fighters):
            cx = centers[i]
            alive = fighter.is_alive
            size = 96 if alive else 64
            color = _MONSTER_COLOR if alive else (90, 82, 82)
            mid = self.bc.monster_objs[i].monster_id if i < len(self.bc.monster_objs) else "unknown"
            surface.blit(assets.sprite(f"monsters/{mid}", color, size), (cx - size // 2, 180 - size // 2))
            if self.flash.get(id(fighter), 0) > 0:
                white = pygame.Surface((size, size), pygame.SRCALPHA)
                white.fill((255, 255, 255, 120))
                surface.blit(white, (cx - size // 2, 180 - size // 2))
            draw_text(surface, fighter.name, (cx, 180 + size // 2 + 18), 20, center=True)
            Bar((cx - 110, 180 + size // 2 + 44, 220, 18), fighter.hp, fighter.max_hp, theme.HP_COLOR) \
                .draw(surface, f"{fighter.hp}/{fighter.max_hp}")
            if i == self.target_index and alive:
                pygame.draw.rect(surface, theme.ACCENT, (cx - 120, 110, 240, 200), 2, border_radius=8)
                draw_text(surface, "▼ 目标", (cx, 100), 15, theme.ACCENT, center=True)
        px, py = 200, 430
        surface.blit(assets.sprite("characters/player", _PLAYER_COLOR, 120), (px - 60, py - 60))
        if self.flash.get(id(self.bc.player), 0) > 0:
            white = pygame.Surface((120, 120), pygame.SRCALPHA)
            white.fill((255, 255, 255, 120))
            surface.blit(white, (px - 60, py - 60))
        draw_text(surface, self.bc.player.name, (px, py + 70), 24, center=True)
        Bar((px - 130, py + 100, 280, 20), self.bc.player.hp, self.bc.player.max_hp, theme.HP_COLOR) \
            .draw(surface, f"HP {self.bc.player.hp}/{self.bc.player.max_hp}")
        Bar((px - 130, py + 128, 280, 16), self.bc.player.mp, self.bc.player.max_mp, theme.MP_COLOR) \
            .draw(surface, f"MP {self.bc.player.mp}/{self.bc.player.max_mp}")
        for ai, ally in enumerate(self.bc.allies[:2]):
            ax = 400 + ai * 150
            ay = 430
            size = 96 if ally.is_alive else 64
            surface.blit(assets.sprite(f"companions/{ally.name}", (140, 200, 140), size), (ax - size // 2, ay - size // 2))
            if self.flash.get(id(ally), 0) > 0:
                white = pygame.Surface((size, size), pygame.SRCALPHA)
                white.fill((255, 255, 255, 120))
                surface.blit(white, (ax - size // 2, ay - size // 2))
            draw_text(surface, f"{ally.name}（伙伴）", (ax, ay + size // 2 + 18), 16, center=True)
            Bar((ax - 105, ay + size // 2 + 42, 210, 16), ally.hp, ally.max_hp, theme.HP_COLOR) \
                .draw(surface, f"{ally.hp}/{ally.max_hp}")
            Bar((ax - 105, ay + size // 2 + 62, 210, 14), ally.mp, ally.max_mp, theme.MP_COLOR) \
                .draw(surface, f"MP {ally.mp}/{ally.max_mp}")
        Panel((theme.WIDTH // 2 + 60, 380, 430, 250)).draw(surface)
        draw_text(surface, "战斗日志", (theme.WIDTH // 2 + 80, 394), 20, theme.TEXT_DIM)
        for i, line in enumerate(self.bc.log_lines(9)):
            draw_text(surface, line, (theme.WIDTH // 2 + 80, 426 + i * 22), 17)
        if self.bc.over:
            msg = "胜利！" if self.bc.winner == "player" else "战败……"
            col = theme.GREEN if self.bc.winner == "player" else theme.RED
            draw_text(surface, msg, (theme.WIDTH // 2, 660), 36, col, bold=True, center=True)
        elif self.bc.awaiting_player:
            draw_text(surface, "你的回合：选择动作", (60, 566), 20, theme.ACCENT)
            draw_text(surface, "点击敌人可切换目标", (60, 540), 15, theme.TEXT_DIM)
            for b in self.action_buttons:
                b.draw(surface)
        elif self.bc.ally_acting:
            act_name = self.bc.current_actor.name if self.bc.current_actor else "伙伴"
            draw_text(surface, f"伙伴 {act_name} 行动中……", (60, 610), 22, theme.TEXT_DIM)
        elif self.bc.enemy_acting:
            act_name = self.bc.current_actor.name if self.bc.current_actor else "敌人"
            draw_text(surface, f"{act_name} 行动中……", (60, 610), 22, theme.TEXT_DIM)
        for fl in self.floaters:
            draw_text(surface, fl["text"], (fl["x"], fl["y"]), fl["size"], fl["color"], bold=True, center=True)
        # 打击反馈：玩家受伤时整帧轻微震动
        if self.shake > 0:
            snap = surface.copy()
            surface.fill(theme.BG_BATTLE)
            surface.blit(snap, (random.randint(-4, 4), random.randint(-3, 3)))


class BackpackScene:
    """背包 + 装备栏：滚动浏览 / 使用 / 装备 / 卸下 / 学习 / 出售 / 给队友用药。"""

    VISIBLE = 6

    def __init__(self, app):
        self.app = app
        self.c = app.controller
        self.message = ""
        self.scroll = 0
        self.item_buttons = []
        self.unequip_buttons = []
        self.target_mode = None
        self.target_buttons = []
        self.forget_mode = None
        self.forget_buttons = []
        self._build()

    def _build(self):
        in_dungeon = self.app.backpack_origin == "dungeon"
        self.item_buttons = []
        self.unequip_buttons = []
        for i, (slot, name) in enumerate(EQUIP_SLOTS):
            y = 170 + i * 60
            if slot in self.c.player.equipment:
                self.unequip_buttons.append(Button((440, y - 4, 120, 40), "卸下",
                                                   lambda s=slot: self.on_unequip(s)))
            else:
                self.unequip_buttons.append(None)
        items = self.c.player.inventory
        self.scroll = max(0, min(self.scroll, max(0, len(items) - self.VISIBLE)))
        for row in range(self.VISIBLE):
            idx = self.scroll + row
            if idx >= len(items):
                break
            item = items[idx]
            y = 170 + row * 56
            label = {"消耗品": "使用", "装备": "装备", "技能书": "学习"}.get(item.item_type, "")
            if label:
                self.item_buttons.append(Button((1050, y - 4, 130, 40), label,
                                                lambda idx=idx: self.on_action(idx)))
            if item.price > 0 and not in_dungeon:
                self.item_buttons.append(Button((950, y - 4, 90, 40), "出售",
                                                lambda idx=idx: self.on_sell(idx)))
        back_label = "返回抉择" if in_dungeon else "返回城镇"
        self.back_button = Button((540, 660, 200, 50), back_label, self.on_back)
        self.target_buttons = []

    def on_action(self, idx):
        item = self.c.player.inventory[idx]
        if item.item_type == "消耗品":
            if self.app.backpack_origin == "dungeon" and self.c.companions:
                self.target_mode = item
                self._build_target_buttons()
                return
            self.message = self.c.use_item(item)
        elif item.item_type == "装备":
            self.message = self.c.equip_item(item)
        elif item.item_type == "技能书":
            self.message = self.c.learn_skill(item)
        elif item.item_type == "遗忘书":
            if not self.c.player.skills:
                self.message = "你没有可遗忘的技能"
            else:
                self.forget_mode = item
                self._build_forget_buttons()
                return
        elif item.item_type == "服装":
            self.message = self.c.wear_outfit(item)
        else:
            self.message = f"{item.name}：{item.description}"
        self._build()

    def _build_forget_buttons(self):
        self.forget_buttons = []
        x = 200
        for skill in self.c.player.skills:
            self.forget_buttons.append(Button((x, 560, 200, 48), skill.name,
                                              lambda sid=skill.skill_id: self.on_forget(sid)))
            x += 220

    def on_forget(self, skill_id):
        item = self.forget_mode
        self.forget_mode = None
        self.message = self.c.forget_skill(item, skill_id)
        self._build()

    def _build_target_buttons(self):
        self.target_buttons = []
        x = 200
        self.target_buttons.append(Button((x, 560, 160, 48), "自己", lambda: self.on_use_on("player")))
        x += 180
        for comp in self.c.companions:
            self.target_buttons.append(Button((x, 560, 200, 48), comp.name,
                                              lambda n=comp.name: self.on_use_on(n)))
            x += 220

    def on_use_on(self, target_name):
        item = self.target_mode
        self.target_mode = None
        if target_name == "player":
            self.message = self.c.use_item_on(self.c.player, item)
        else:
            comp = next((c for c in self.c.companions if c.name == target_name), None)
            if comp:
                self.message = self.c.use_item_on(comp, item)
            else:
                self.message = "找不到该伙伴"
        self._build()

    def on_sell(self, idx):
        item = self.c.player.inventory[idx]
        self.message = self.c.sell(item.item_id)
        self._build()

    def on_unequip(self, slot):
        self.message = self.c.unequip_item(slot)
        self._build()

    def on_back(self):
        if self.app.backpack_origin == "dungeon":
            self.app.goto_dungeon("result")
        else:
            self.app.goto_town()

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            items = self.c.player.inventory
            self.scroll = max(0, min(self.scroll - event.y, max(0, len(items) - self.VISIBLE)))
            self._build()
            return
        if self.target_mode is not None:
            for b in self.target_buttons:
                b.handle_event(event)
            return
        if self.forget_mode is not None:
            for b in self.forget_buttons:
                b.handle_event(event)
            return
        for b in self.item_buttons:
            b.handle_event(event)
        for b in self.unequip_buttons:
            if b:
                b.handle_event(event)
        self.back_button.handle_event(event)

    def update(self, dt):
        pass

    def draw(self, surface):
        p = self.c.player
        in_dungeon = self.app.backpack_origin == "dungeon"
        surface.fill(theme.BG_TOWN)
        title = "背包（地下城补给）" if in_dungeon else "背包 / 装备"
        draw_text(surface, title, (60, 28), 30, bold=True)
        draw_text(surface, f"金币 {p.money}  攻击 {p.attack}  防御 {p.defense}  速度 {p.speed}",
                  (300, 36), 16, theme.TEXT_DIM)
        outfit_txt = "（裸奔中）" if p.naked else f"服装：{p.outfit}"
        draw_text(surface, outfit_txt, (300, 58), 15, theme.TEXT_DIM)
        if in_dungeon:
            draw_text(surface, "地下城中无法出售", (1050, 28), 16, theme.RED)
        Panel((60, 110, 540, 520)).draw(surface)
        draw_text(surface, "装备栏", (80, 124), 22, bold=True)
        for i, (slot, name) in enumerate(EQUIP_SLOTS):
            y = 170 + i * 60
            eq = p.equipment.get(slot)
            draw_text(surface, name, (80, y), 20)
            if eq:
                extra = f"（{eq.affix_desc}）" if eq.affix_desc else ""
                draw_text(surface, f"{eq.name}{extra}", (150, y), 17)
                if self.unequip_buttons[i]:
                    self.unequip_buttons[i].draw(surface)
            else:
                draw_text(surface, "空", (150, y), 17, theme.TEXT_DIM)
        Panel((620, 110, 600, 520)).draw(surface)
        draw_text(surface, "背包", (640, 124), 22, bold=True)
        items = p.inventory
        if not items:
            draw_text(surface, "背包是空的", (640, 180), 20, theme.TEXT_DIM)
        for row in range(self.VISIBLE):
            idx = self.scroll + row
            if idx >= len(items):
                break
            item = items[idx]
            y = 170 + row * 56
            extra = f"  {item.affix_desc}" if item.affix_desc else ""
            draw_text(surface, f"{item.name} ×{item.quantity}", (640, y), 18)
            draw_text(surface, f"{item.item_type}  {item.description}{extra}", (640, y + 22), 14, theme.TEXT_DIM)
        if len(items) > self.VISIBLE:
            draw_text(surface, f"滚轮滚动（{self.scroll + 1}-{min(len(items), self.scroll + self.VISIBLE)}/{len(items)}）",
                      (640, 600), 15, theme.TEXT_DIM)
        for b in self.item_buttons:
            b.draw(surface)
        for b in self.unequip_buttons:
            if b:
                pass
        self.back_button.draw(surface)
        if self.target_mode is not None:
            draw_text(surface, f"对谁使用 {self.target_mode.name}？", (540, 520), 20, theme.ACCENT, center=True)
            for b in self.target_buttons:
                b.draw(surface)
        if self.forget_mode is not None:
            draw_text(surface, "要遗忘哪个技能？（普攻不可遗忘）", (540, 520), 20, theme.ACCENT, center=True)
            for b in self.forget_buttons:
                b.draw(surface)
        if self.message:
            draw_text(surface, self.message, (60, 690), 16, theme.ACCENT)


class ShopScene:
    """商店（分类 + 买卖 + 动态价格）。"""

    def __init__(self, app, category="杂货铺"):
        self.app = app
        self.c = app.controller
        self.category = category
        self.mode = "buy"
        self.message = ""
        self.item_buttons = []
        self._build()

    def _stock(self):
        from .items import SHOP_CATEGORIES
        return SHOP_CATEGORIES.get(self.category, ["potion"])

    def _build(self):
        self.item_buttons = []
        if self.mode == "buy":
            for i, item_id in enumerate(self._stock()[:8]):
                y = 200 + i * 56
                price = self.c.buy_price(item_id)
                self.item_buttons.append(Button((1020, y - 6, 160, 44), f"购买 {price}",
                                                lambda item_id=item_id: self.on_buy(item_id)))
        else:
            items = self.c.player.inventory[:8]
            for i, item in enumerate(items):
                y = 200 + i * 56
                price = self.c.sell_price(item)
                self.item_buttons.append(Button((1020, y - 6, 160, 44), f"卖出 {price}",
                                                lambda item_id=item.item_id: self.on_sell(item_id)))
        self.tab_buy = Button((60, 122, 140, 44), "购买", lambda: self.set_mode("buy"))
        self.tab_sell = Button((210, 122, 140, 44), "出售", lambda: self.set_mode("sell"))
        self.back_button = Button((540, 660, 200, 50), "返回街道", self.on_back)

    def set_mode(self, mode):
        self.mode = mode
        self.message = ""
        self._build()

    def on_buy(self, item_id):
        self.message = self.c.buy(item_id)
        self._build()

    def on_sell(self, item_id):
        self.message = self.c.sell(item_id)
        self._build()

    def on_back(self):
        self.app.goto_city()

    def handle_event(self, event):
        self.tab_buy.handle_event(event)
        self.tab_sell.handle_event(event)
        for b in self.item_buttons:
            b.handle_event(event)
        self.back_button.handle_event(event)

    def update(self, dt):
        pass

    def draw(self, surface):
        from .items import ITEM_TEMPLATES
        p = self.c.player
        surface.fill(theme.BG_TOWN)
        draw_text(surface, self.category, (560, 28), 30, bold=True, center=True)
        draw_text(surface, f"金币 {p.money}", (60, 36), 22, theme.GOLD_COLOR)
        market = self.c._market_factor()
        if market > 1.02:
            tip, tc = f"今日行情偏高 ×{market:.2f}", theme.RED
        elif market < 0.98:
            tip, tc = f"今日行情偏低 ×{market:.2f}", theme.GREEN
        else:
            tip, tc = "今日行情平稳", theme.TEXT_DIM
        draw_text(surface, tip, (400, 36), 18, tc)
        self.tab_buy.draw(surface)
        self.tab_sell.draw(surface)
        draw_text(surface, "价格受：荣誉 / 当日行情 / 供需 影响", (400, 130), 15, theme.TEXT_DIM)
        Panel((60, 180, 1160, 460)).draw(surface)
        if self.mode == "buy":
            y = 200
            for item_id in self._stock():
                t = ITEM_TEMPLATES[item_id]
                bd = self.c.price_breakdown(item_id)
                draw_text(surface, f"{t['name']}  {bd['buy']} 金币", (90, y), 19)
                draw_text(surface, f"{t.get('item_type', '')}  {t.get('description', '')}  "
                                   f"[基价{bd['base']} ×荣誉{bd['honor']:.2f} ×行情{bd['market']:.2f} ×需求{bd['demand']:.2f}]",
                          (90, y + 22), 14, theme.TEXT_DIM)
                y += 56
        else:
            items = p.inventory
            if not items:
                draw_text(surface, "背包是空的", (90, 210), 20, theme.TEXT_DIM)
            y = 200
            for item in items[:8]:
                price = self.c.sell_price(item)
                draw_text(surface, f"{item.name} ×{item.quantity}  卖出 {price} 金币", (90, y), 19)
                draw_text(surface, f"{item.item_type}  {item.description}  [需求系数 {self.c.demand_of(item.item_id):.2f}]",
                          (90, y + 22), 14, theme.TEXT_DIM)
                y += 56
        for b in self.item_buttons:
            b.draw(surface)
        self.back_button.draw(surface)
        if self.message:
            draw_text(surface, self.message, (60, 690), 17, theme.ACCENT)


class CityScene:
    """城市街道：进入各分类商店 + 随便逛逛（随机事件）。"""

    VENUES = [
        ("武器店", 100, 190),
        ("防具店", 360, 190),
        ("饰品店", 620, 190),
        ("药水店", 880, 190),
        ("技能书店", 100, 330),
        ("服装店", 360, 330),
        ("杂货铺", 620, 330),
    ]

    def __init__(self, app):
        self.app = app
        self.c = app.controller
        self.message = ""
        self.venue_buttons = []
        for name, x, y in self.VENUES:
            self.venue_buttons.append(Button((x, y, 220, 100), name,
                                             lambda n=name: self.on_enter(n)))
        self.stroll_button = Button((880, 330, 220, 100), "随便逛逛", self.on_stroll)
        self.quest_button = Button((880, 470, 220, 100), "委托板", self.on_quest)
        self.back_button = Button((540, 660, 200, 50), "回营地", self.on_back)

    def on_quest(self):
        self.app.goto_quest()

    def on_enter(self, name):
        self.app.goto_shop(name)

    def on_stroll(self):
        self.message = self.c.stroll()

    def on_back(self):
        self.app.goto_town()

    def handle_event(self, event):
        for b in self.venue_buttons:
            b.handle_event(event)
        self.stroll_button.handle_event(event)
        self.quest_button.handle_event(event)
        self.back_button.handle_event(event)

    def update(self, dt):
        pass

    def draw(self, surface):
        surface.fill(theme.BG_TOWN)
        draw_text(surface, "城市街道", (60, 28), 30, bold=True)
        draw_text(surface, f"金币 {self.c.player.money}  第 {self.c.day} 天", (260, 36), 20, theme.TEXT_DIM)
        draw_text(surface, "点店铺进去买卖；「随便逛逛」触发街头事件", (60, 110), 18, theme.ACCENT)
        for b in self.venue_buttons:
            b.draw(surface)
        self.stroll_button.draw(surface)
        self.quest_button.draw(surface)
        self.back_button.draw(surface)
        if self.message:
            draw_text(surface, self.message, (60, 690), 17, theme.ACCENT)


class QuestScene:
    """委托板：短期目标 + 领奖。"""

    def __init__(self, app):
        self.app = app
        self.c = app.controller
        self.message = ""
        self.buttons = []
        self._build()

    def _build(self):
        self.buttons = []
        for i, q in enumerate(self.c.quests):
            y = 200 + i * 130
            done = q["progress"] >= q["need"]
            label = f"领取奖励（{q['gold']}金 / {q['exp']}经验）" if done else "进行中"
            self.buttons.append(Button((900, y + 40, 260, 50), label,
                                       lambda i=i: self.on_claim(i)))
        self.back_button = Button((540, 660, 200, 50), "返回街道", self.on_back)

    def on_claim(self, i):
        self.message = self.c.claim_quest(i)
        self._build()

    def on_back(self):
        self.app.goto_city()

    def handle_event(self, event):
        for b in self.buttons:
            b.handle_event(event)
        self.back_button.handle_event(event)

    def update(self, dt):
        pass

    def draw(self, surface):
        surface.fill(theme.BG_TOWN)
        draw_text(surface, "委托板", (60, 28), 30, bold=True)
        draw_text(surface, f"金币 {self.c.player.money}", (180, 36), 20, theme.GOLD_COLOR)
        Panel((60, 110, 1160, 520)).draw(surface)
        for i, q in enumerate(self.c.quests):
            y = 200 + i * 130
            done = q["progress"] >= q["need"]
            color = theme.GREEN if done else theme.TEXT
            draw_text(surface, q["desc"], (90, y), 24, color, bold=True)
            draw_text(surface, f"进度 {q['progress']}/{q['need']}   奖励：{q['gold']} 金币 + {q['exp']} 经验",
                      (90, y + 34), 18, theme.TEXT_DIM)
            Bar((90, y + 66, 640, 18), q["progress"], q["need"],
                theme.GREEN if done else theme.ACCENT).draw(surface)
            if done:
                self.buttons[i].draw(surface)
            else:
                draw_text(surface, "进行中……", (900, y + 50), 18, theme.TEXT_DIM)
        self.back_button.draw(surface)
        if self.message:
            draw_text(surface, self.message, (60, 690), 17, theme.ACCENT)


class StoryScene:
    """通用剧情场景：逐句播放 beats，结束后可选分支或回调。"""

    def __init__(self, app, beats, on_finish=None, choices=None):
        self.app = app
        self.beats = beats
        self.index = 0
        self.on_finish = on_finish
        self.choices = choices or []
        self.choice_buttons = []
        self.next_button = Button((540, 610, 200, 56), "继续", self.on_next)

    def on_next(self):
        self.index += 1
        if self.index >= len(self.beats):
            if self.choices:
                self._build_choices()
            elif self.on_finish:
                self.on_finish()

    def _build_choices(self):
        self.choice_buttons = []
        x = 240
        for label, cb in self.choices:
            self.choice_buttons.append(Button((x, 600, 220, 56), label, cb))
            x += 250

    def handle_event(self, event):
        if self.index < len(self.beats):
            self.next_button.handle_event(event)
        else:
            for b in self.choice_buttons:
                b.handle_event(event)

    def update(self, dt):
        pass

    def draw(self, surface):
        surface.fill(theme.BG_TOWN)
        pygame.draw.rect(surface, theme.PANEL, (100, 80, 1080, 480), border_radius=14)
        pygame.draw.rect(surface, theme.BORDER, (100, 80, 1080, 480), 2, border_radius=14)
        if self.index < len(self.beats):
            speaker, text = self.beats[self.index]
            draw_text(surface, speaker, (140, 110), 28, theme.ACCENT, bold=True)
            draw_text(surface, f"{self.index + 1}/{len(self.beats)}", (1140, 110), 16, theme.TEXT_DIM, right=True)
            font = theme.get_font(24)
            y = 180
            for line in _wrap(text, font, 980):
                draw_text(surface, line, (140, y), 24)
                y += 40
            self.next_button.draw(surface)
        else:
            draw_text(surface, "你要怎么回答？", (140, 110), 28, theme.ACCENT, bold=True)
            for b in self.choice_buttons:
                b.draw(surface)
