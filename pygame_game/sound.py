"""程序化音效（无素材）：用正弦波合成简单的打击/治疗音。"""
import array
import math

import pygame

_enabled = False
_sounds = {}


def init():
    global _enabled
    try:
        pygame.mixer.init(frequency=22050, size=-16, channels=1)
        _enabled = True
    except Exception:
        _enabled = False


def _tone(freq, duration, volume):
    sr = 22050
    n = int(sr * duration)
    buf = array.array(
        "h",
        [int(32767 * volume * math.sin(2 * math.pi * freq * i / sr)) for i in range(n)],
    )
    return pygame.mixer.Sound(buffer=buf)


def play(name):
    if not _enabled:
        return
    # 优先真实音效素材
    from . import assets
    real = assets.sfx(name)
    if real is not None:
        try:
            real.play()
            return
        except Exception:
            pass
    specs = {
        "hit": (220, 0.06, 0.20),
        "crit": (560, 0.11, 0.28),
        "heal": (660, 0.10, 0.18),
        "hurt": (140, 0.11, 0.24),
        "victory": (880, 0.18, 0.26),
    }
    freq, dur, vol = specs.get(name, (440, 0.06, 0.16))
    if name not in _sounds:
        _sounds[name] = _tone(freq, dur, vol)
    try:
        _sounds[name].play()
    except Exception:
        pass
