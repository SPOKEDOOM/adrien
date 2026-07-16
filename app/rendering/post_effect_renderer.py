from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter, QRadialGradient

from app.rendering.config import RendererConfig
from app.rendering.renderer import Renderer
from app.rendering.scene import Scene


class PostEffectRenderer(Renderer):
    """Draws final screen-space Presence effects."""

    def __init__(self, config: RendererConfig):
        super().__init__(config)

    def render(self, painter: QPainter, scene: Scene) -> None:
        painter.save()
        self._draw_soft_vignette(painter, scene)
        painter.restore()

    def _draw_soft_vignette(self, painter: QPainter, scene: Scene) -> None:
        radius = max(scene.viewport_width, scene.viewport_height) * 0.72
        center = QPointF(scene.center_x, scene.center_y)
        gradient = QRadialGradient(center, radius)

        gradient.setColorAt(0.0, self.with_alpha(self.config.background_color, 0))
        gradient.setColorAt(0.68, self.with_alpha(self.config.background_color, 18))
        gradient.setColorAt(1.0, self.with_alpha(self.config.background_bottom_color, 118))

        painter.fillRect(
            0,
            0,
            scene.viewport_width,
            scene.viewport_height,
            gradient,
        )
