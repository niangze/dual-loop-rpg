"""主题 / 配置：窗口尺寸、颜色、字体、占位精灵。"""
import os

import pygame

WIDTH, HEIGHT = 1280, 720
TILE = 32
FPS = 60
TITLE = "双循环 RPG · Pygame 原型"

# 颜色
BG_TOWN = (44, 38, 54)
BG_DUNGEON = (26, 28, 38)
BG_BATTLE = (22, 24, 34)
PANEL = (40, 42, 58)
PANEL_LIGHT = (64, 66, 88)
BORDER = (120, 122, 150)
TEXT = (235, 236, 242)
TEXT_DIM = (165, 168, 185)
ACCENT = (245, 196, 96)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
HP_COLOR = (224, 78, 78)
MP_COLOR = (90, 140, 245)
GOLD_COLOR = (240, 205, 100)
GREEN = (116, 205, 128)
RED = (235, 90, 90)
BLUE = (90, 140, 245)

# 中文字体候选
_FONT_CANDIDATES = [
    "assets/fonts/main.ttf",
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/msyhbd.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
    "C:/Windows/Fonts/Deng.ttf",
]

_font_cache = {}


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key in _font_cache:
        return _font_cache[key]
    font = None
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            font = pygame.font.Font(path, size)
            break
    if font is None:
        font = pygame.font.Font(None, size)
    if bold:
        font.set_bold(True)
    _font_cache[key] = font
    return font


_sprite_cache = {}


def make_sprite(color, size: int = TILE) -> pygame.Surface:
    key = (color, size)
    if key in _sprite_cache:
        return _sprite_cache[key]
    surf = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(surf, color, (2, 2, size - 4, size - 4), border_radius=5)
    lighter = tuple(min(255, c + 45) for c in color)
    pygame.draw.rect(surf, lighter, (5, 5, size - 10, size - 10), border_radius=4)
    darker = tuple(max(0, c - 70) for c in color)
    pygame.draw.rect(surf, darker, (0, 0, size, size), 2, border_radius=6)
    _sprite_cache[key] = surf
    return surf


def sprite_scaled(color, size: int) -> pygame.Surface:
    return pygame.transform.scale(make_sprite(color, TILE), (size, size))
