"""应用主体：主循环 + 场景切换 + 无头烟雾测试。"""
import copy
import os

import pygame

from . import theme, sound, assets
from .controller import GameController
from .scenes import (
    TitleScene, TownScene, DungeonScene, BattleScene, BackpackScene, ShopScene,
    CityScene, StoryScene, QuestScene,
)


class App:
    def __init__(self, base, save_path="save.json"):
        self.base = base  # (player, npcs, dungeon) 全新初始状态
        self.save_path = save_path
        pygame.init()
        sound.init()
        assets.init()
        self.screen = pygame.display.set_mode((theme.WIDTH, theme.HEIGHT))
        pygame.display.set_caption(theme.TITLE)
        self.clock = pygame.time.Clock()
        self.controller = self._new_controller()
        self.scene = None
        self.backpack_origin = "town"
        self.current_bgm = None
        self.goto_title()

    def _new_controller(self):
        p, n, d = self.base
        return GameController(copy.deepcopy(p), copy.deepcopy(n), copy.deepcopy(d))

    def _bgm(self, name):
        if self.current_bgm == name:
            return
        if assets.music(name):
            self.current_bgm = name

    # ---- 场景切换 ----
    def goto_title(self):
        self.scene = TitleScene(self)

    def goto_town(self):
        self._bgm("town")
        self.scene = TownScene(self)

    def goto_dungeon(self, mode):
        self._bgm("dungeon")
        self.scene = DungeonScene(self, mode)

    def goto_battle(self):
        self._bgm("battle")
        self.scene = BattleScene(self)

    def goto_backpack(self, origin="town"):
        self.backpack_origin = origin
        self.scene = BackpackScene(self)

    def goto_city(self):
        self._bgm("town")
        self.scene = CityScene(self)

    def goto_shop(self, category="杂货铺"):
        self.scene = ShopScene(self, category)

    def goto_quest(self):
        self.scene = QuestScene(self)

    def story(self, beats, on_finish=None, choices=None):
        self.scene = StoryScene(self, beats, on_finish=on_finish, choices=choices)

    def battle_finished(self, win):
        bscene = self.scene
        if hasattr(bscene, "bc"):
            bscene.bc.sync_to_player()
            bscene.bc.sync_to_companions(self.controller.companions)
        if win:
            enemies = self.controller.current_enemies
            drops = self.controller.on_win(enemies)
            exp = sum(m.exp_reward for m in enemies)
            gold = sum(m.money_reward for m in enemies)
            msg = f"战斗胜利！获得 {exp} 经验、{gold} 金币"
            if drops:
                msg += "；掉落：" + "、".join(f"{d.name}×{d.quantity}" for d in drops)
            self.controller.last_event_msg = msg
            self.goto_dungeon("result")
        else:
            self.controller.on_death()
            self.goto_town()

    # ---- 存档读档 ----
    def has_save(self):
        return os.path.exists(self.save_path)

    def new_game(self):
        self.controller = self._new_controller()
        self.goto_town()

    def continue_game(self):
        self.controller.load(self.save_path)
        self.goto_town()

    # ---- 主循环 ----
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(theme.FPS) / 1000.0
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                else:
                    self.scene.handle_event(event)
            self.scene.update(dt)
            self.scene.draw(self.screen)
            pygame.display.flip()
        pygame.quit()


def smoke_test(base):
    """无头烟雾测试：绘制各场景、驱动完整战斗，验证无崩溃。"""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    app = App(base, save_path="_smoke_save.json")

    app.goto_title()
    app.scene.draw(app.screen)

    app.new_game()
    app.scene.draw(app.screen)
    app.scene.on_chat(0)
    app.scene.draw(app.screen)
    app.scene.on_option(0)
    app.scene.draw(app.screen)
    app.scene.on_close_dialog()
    app.scene.on_rest()
    app.scene.draw(app.screen)
    app.scene.on_train()
    app.scene.draw(app.screen)
    app.scene.on_work()
    app.scene.draw(app.screen)
    app.scene.on_end_day()
    app.scene.draw(app.screen)

    # 商店 / 背包
    app.goto_shop()
    app.scene.draw(app.screen)
    app.scene.on_buy("potion")
    app.scene.draw(app.screen)
    app.goto_backpack("town")
    app.scene.draw(app.screen)
    if app.scene.item_buttons:
        app.scene.on_action(0)
    app.scene.draw(app.screen)
    app.scene.on_back()

    # 地下城探索（房间制）
    app.controller.start_dungeon()
    app.goto_dungeon("explore")
    app.scene.draw(app.screen)
    app.scene.on_explore()
    app.scene.draw(app.screen)

    # 伤员事件
    app.goto_dungeon("wounded")
    app.scene.draw(app.screen)
    app.scene.on_wounded("help")
    app.scene.draw(app.screen)

    # 强制多敌遭遇战
    app.controller.prepare_adventurer_ambush()
    app.goto_dungeon("encounter")
    app.scene.draw(app.screen)
    app.goto_battle()

    steps = 0
    while isinstance(app.scene, BattleScene) and steps < 500:
        steps += 1
        battle = app.scene
        if battle.bc.awaiting_player:
            assert battle.action_buttons, "玩家回合没有动作按钮（卡死 bug）"
            acts = battle.bc.usable_actions()
            skill = next((a for a in acts if a.skill_id != "normal"), acts[0])
            battle.on_act(skill)
        battle.update(0.05)
        battle.draw(app.screen)

    app.scene.draw(app.screen)
    print(f"SMOKE OK (battle steps={steps}, player hp={app.controller.player.hp}, "
          f"enemies={len(app.controller.current_enemies)}, floor={app.controller.floor}, "
          f"rooms={app.controller.rooms_explored})")
    pygame.quit()
