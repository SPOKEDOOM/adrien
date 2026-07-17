from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient

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
        self._draw_stabilization_wave(painter, scene)
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

    def _draw_stabilization_wave(self, painter: QPainter, scene: Scene) -> None:
        progress = scene.energy_wave_progress
        if not scene.energy_wave_triggered or progress <= 0.0 or progress >= 1.0:
            return
        eased = 1.0 - pow(1.0 - progress, 3)
        radius = scene.config.core_base_radius * (1.15 + eased * 3.0)
        color = QColor(scene.config.ring_color)
        color.setAlpha(int(48 * (1.0 - progress) ** 2 * scene.visibility))
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(color, 1.4))
        painter.drawEllipse(QPointF(scene.center_x, scene.center_y), radius, radius)
