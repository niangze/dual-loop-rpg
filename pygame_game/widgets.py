"""UI 组件：按钮、进度条、面板、文本绘制。"""
import pygame

from . import theme


def draw_text(surface, text, pos, size=20, color=None, bold=False,
              center=False, right=False):
    color = color or theme.TEXT
    font = theme.get_font(size, bold)
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    elif right:
        rect.topright = pos
    else:
        rect.topleft = pos
    surface.blit(img, rect)
    return rect


class Button:
    """可点击按钮。"""

    def __init__(self, rect, label, on_click=None, enabled=True, color=None):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.on_click = on_click
        self.enabled = enabled
        self.color = color or theme.PANEL_LIGHT
        self.hover = False

    def handle_event(self, event):
        if not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.on_click:
                    self.on_click()
                return True
        return False

    def draw(self, surface):
        c = self.color
        if not self.enabled:
            c = tuple(max(0, x - 60) for x in c)
        elif self.hover:
            c = tuple(min(255, x + 25) for x in c)
        pygame.draw.rect(surface, c, self.rect, border_radius=8)
        pygame.draw.rect(surface, theme.BORDER, self.rect, 2, border_radius=8)
        draw_text(surface, self.label, self.rect.center, 22,
                  theme.TEXT if self.enabled else theme.TEXT_DIM, center=True)


class Bar:
    """进度条（血条/蓝条）。"""

    def __init__(self, rect, value, max_value, color):
        self.rect = pygame.Rect(rect)
        self.value = value
        self.max_value = max_value
        self.color = color

    def set(self, value, max_value):
        self.value = value
        self.max_value = max_value

    def draw(self, surface, label=""):
        pygame.draw.rect(surface, (30, 32, 44), self.rect, border_radius=5)
        ratio = max(0.0, min(1.0, self.value / self.max_value)) if self.max_value > 0 else 0.0
        fill = self.rect.copy()
        fill.width = int(fill.width * ratio)
        pygame.draw.rect(surface, self.color, fill, border_radius=5)
        pygame.draw.rect(surface, theme.BORDER, self.rect, 1, border_radius=5)
        if label:
            draw_text(surface, label, self.rect.center, 15, theme.WHITE, center=True)


class Panel:
    """半透明面板。"""

    def __init__(self, rect, color=None):
        self.rect = pygame.Rect(rect)
        self.color = color or theme.PANEL

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect, border_radius=10)
        pygame.draw.rect(surface, theme.BORDER, self.rect, 2, border_radius=10)
