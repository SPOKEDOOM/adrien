from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QRadialGradient

from app.rendering.config import RendererConfig
from app.rendering.renderer import Renderer
from app.rendering.scene import Scene


class GlowRenderer(Renderer):
    """Draws layered bloom around the Presence core."""

    def __init__(self, config: RendererConfig):
        super().__init__(config)

    def render(self, painter: QPainter, scene: Scene) -> None:
        if scene.visibility <= 0.0:
            return

        center = QPointF(scene.center_x, scene.center_y)
        glow_intensity = scene.glow_intensity * self._breathing_factor(scene)
        painter.save()
        painter.setPen(Qt.NoPen)
        self._draw_soft_ambient_glow(painter, scene, center, glow_intensity)
        self._draw_halo(painter, scene, center, glow_intensity)
        self._draw_outer_glow(painter, scene, center, glow_intensity)
        self._draw_inner_glow(painter, scene, center, glow_intensity)
        painter.restore()

    def _draw_soft_ambient_glow(
        self,
        painter: QPainter,
        scene: Scene,
        center: QPointF,
        glow_intensity: float,
    ) -> None:
        radius = max(scene.halo_radius, 1.0)
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(
            0.0,
            self.with_alpha(
                self.config.halo_color,
                int(28 * scene.visibility * glow_intensity),
            ),
        )
        gradient.setColorAt(
            0.42,
            self.with_alpha(
                self.config.glow_color,
                int(18 * scene.visibility * glow_intensity),
            ),
        )
        gradient.setColorAt(
            0.76,
            self.with_alpha(self.config.secondary_ring_color, int(7 * scene.visibility)),
        )
        gradient.setColorAt(1.0, self.with_alpha(self.config.halo_color, 0))

        painter.fillRect(
            0,
            0,
            scene.viewport_width,
            scene.viewport_height,
            gradient,
        )

    def _draw_halo(
        self,
        painter: QPainter,
        scene: Scene,
        center: QPointF,
        glow_intensity: float,
    ) -> None:
        radius = max(scene.halo_radius * 0.72, 1.0)
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(
            0.0,
            self.with_alpha(
                self.config.halo_color,
                int(42 * scene.visibility * glow_intensity),
            ),
        )
        gradient.setColorAt(
            0.38,
            self.with_alpha(
                self.config.secondary_ring_color,
                int(22 * scene.visibility * glow_intensity),
            ),
        )
        gradient.setColorAt(0.72, self.with_alpha(self.config.glow_color, int(8 * scene.visibility)))
        gradient.setColorAt(1.0, self.with_alpha(self.config.halo_color, 0))

        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)

    def _draw_outer_glow(
        self,
        painter: QPainter,
        scene: Scene,
        center: QPointF,
        glow_intensity: float,
    ) -> None:
        radius = max(scene.bloom_radius, 1.0)
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(
            0.0,
            self.with_alpha(
                self.config.glow_color,
                int(74 * scene.visibility * glow_intensity),
            ),
        )
        gradient.setColorAt(
            0.36,
            self.with_alpha(
                self.config.glow_color,
                int(34 * scene.visibility * glow_intensity),
            ),
        )
        gradient.setColorAt(0.7, self.with_alpha(self.config.halo_color, int(10 * scene.visibility)))
        gradient.setColorAt(1.0, self.with_alpha(self.config.glow_color, 0))

        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)

    def _draw_inner_glow(
        self,
        painter: QPainter,
        scene: Scene,
        center: QPointF,
        glow_intensity: float,
    ) -> None:
        radius = max(scene.core_radius * 1.45, 1.0)
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(
            0.0,
            self.with_alpha(
                self.config.core_inner_color,
                int(118 * scene.core_alpha * glow_intensity),
            ),
        )
        gradient.setColorAt(
            0.56,
            self.with_alpha(
                self.config.glow_color,
                int(56 * scene.core_alpha * glow_intensity),
            ),
        )
        gradient.setColorAt(1.0, self.with_alpha(self.config.glow_color, 0))

        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)

    @staticmethod
    def _breathing_factor(scene: Scene) -> float:
        speed = scene.profile.breathing_speed
        depth = scene.profile.glow_pulse_depth
        return (1.0 - depth) + math.sin(scene.elapsed_seconds * 1.15 * speed) * depth
