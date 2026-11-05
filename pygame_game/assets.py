"""素材接入层：从 assets/ 加载图片 / 音频 / 字体，缺失时自动回退。

约定：
- `assets/images/<逻辑名>.png`  → 图片（如 `images/characters/player.png`）
- `assets/audio/sfx/<名>.wav`   → 音效
- `assets/audio/bgm/<名>.ogg`   → 背景音乐
- `assets/fonts/main.ttf`       → 中文字体
- `assets/manifest.json`        → 可选，逻辑名 -> 实际文件映射

所有接口在素材缺失时都会优雅回退，不会报错。
"""
from __future__ import annotations

import json
import os
from typing import Optional

import pygame

from . import theme

_BASE = "assets"
_MANIFEST: dict = {}
_images: dict = {}
_sfx_cache: dict = {}


def init(base_dir: str = "assets") -> None:
    global _BASE, _MANIFEST
    _BASE = base_dir
    path = os.path.join(_BASE, "manifest.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                _MANIFEST = json.load(f)
        except Exception:
            _MANIFEST = {}


def _rel(name: str, kind: str) -> str:
    entry = _MANIFEST.get(name)
    if entry and entry.get(kind):
        return os.path.join(_BASE, entry[kind])
    folder = {"image": "images", "audio": "audio/sfx", "music": "audio/bgm"}[kind]
    ext = "png" if kind == "image" else "wav"
    if kind == "music":
        ext = "ogg"
    return os.path.join(_BASE, folder, name + "." + ext)


def image(name: str, size=None) -> Optional[pygame.Surface]:
    """按逻辑名加载图片，缺失返回 None。"""
    key = (name, size)
    if key in _images:
        return _images[key]
    surf = None
    path = _rel(name, "image")
    if os.path.exists(path):
        try:
            surf = pygame.image.load(path).convert_alpha()
            if size is not None:
                surf = pygame.transform.scale(surf, size)
        except Exception:
            surf = None
    _images[key] = surf
    return surf


def sprite(name: str, color, size: int) -> pygame.Surface:
    """优先图片素材，缺失时用色块占位（保持可运行）。"""
    img = image(name, (size, size))
    if img is not None:
        return img
    return theme.sprite_scaled(color, size)


def sfx(name: str):
    """按名加载音效，缺失返回 None。"""
    if name in _sfx_cache:
        return _sfx_cache[name]
    snd = None
    path = _rel(name, "audio")
    if os.path.exists(path):
        try:
            snd = pygame.mixer.Sound(path)
        except Exception:
            snd = None
    _sfx_cache[name] = snd
    return snd


def music(name: str) -> bool:
    """播放背景音乐，缺失返回 False。"""
    path = _rel(name, "music")
    if not os.path.exists(path):
        return False
    try:
        pygame.mixer.music.load(path)
        pygame.mixer.music.play(-1)
        return True
    except Exception:
        return False


def font_path() -> Optional[str]:
    path = os.path.join(_BASE, "fonts", "main.ttf")
    return path if os.path.exists(path) else None
