from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPen

from app.rendering.config import RendererConfig
from app.rendering.renderer import Renderer
from app.rendering.scene import Scene


class HighlightRenderer(Renderer):
    """Draws energetic accents that keep the Presence from feeling static."""

    def __init__(self, config: RendererConfig):
        super().__init__(config)

    def render(self, painter: QPainter, scene: Scene) -> None:
        if scene.visibility <= 0.0:
            return

        painter.save()
        painter.translate(scene.center_x, scene.center_y)
        painter.rotate(math.degrees(scene.core_energy_angle) * 0.12)
        self._draw_core_spark(painter, scene)
        self._draw_radial_streaks(painter, scene)
        painter.restore()

    def _draw_core_spark(self, painter: QPainter, scene: Scene) -> None:
        color = self.with_alpha(
            self.config.core_inner_color,
            int(170 * scene.visibility * scene.glow_intensity),
        )
        pen = QPen(color)
        pen.setWidthF(1.2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)

        radius = scene.core_radius * 0.5
        painter.drawLine(QPointF(-radius, 0.0), QPointF(radius, 0.0))
        painter.drawLine(QPointF(0.0, -radius * 0.62), QPointF(0.0, radius * 0.62))

    def _draw_radial_streaks(self, painter: QPainter, scene: Scene) -> None:
        streak_count = 10
        base_radius = scene.core_radius * 1.22
        length = 10.0 + scene.profile.pulse_strength * 8.0

        for index in range(streak_count):
            if (index + int(scene.elapsed_seconds * 4.0)) % 3 == 0:
                continue

            angle = (math.tau * index) / streak_count
            alpha = int(58 * scene.visibility * scene.glow_intensity)
            pen = QPen(self.with_alpha(self.config.glow_color, alpha))
            pen.setWidthF(0.8)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)

            start = QPointF(math.cos(angle) * base_radius, math.sin(angle) * base_radius)
            end_radius = base_radius + length
            end = QPointF(math.cos(angle) * end_radius, math.sin(angle) * end_radius)
            painter.drawLine(start, end)
