from __future__ import annotations

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
        painter.save()
        painter.setPen(Qt.NoPen)
        self._draw_soft_ambient_glow(painter, scene, center)
        self._draw_halo(painter, scene, center)
        self._draw_outer_glow(painter, scene, center)
        self._draw_inner_glow(painter, scene, center)
        painter.restore()

    def _draw_soft_ambient_glow(
        self,
        painter: QPainter,
        scene: Scene,
        center: QPointF,
    ) -> None:
        radius = max(scene.halo_radius, 1.0)
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(
            0.0,
            self.with_alpha(
                self.config.halo_color,
                int(34 * scene.visibility * scene.glow_intensity),
            ),
        )
        gradient.setColorAt(
            0.48,
            self.with_alpha(
                self.config.glow_color,
                int(16 * scene.visibility * scene.glow_intensity),
            ),
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
    ) -> None:
        radius = max(scene.halo_radius * 0.72, 1.0)
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(
            0.0,
            self.with_alpha(
                self.config.halo_color,
                int(52 * scene.visibility * scene.glow_intensity),
            ),
        )
        gradient.setColorAt(
            0.45,
            self.with_alpha(
                self.config.halo_color,
                int(24 * scene.visibility * scene.glow_intensity),
            ),
        )
        gradient.setColorAt(1.0, self.with_alpha(self.config.halo_color, 0))

        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)

    def _draw_outer_glow(
        self,
        painter: QPainter,
        scene: Scene,
        center: QPointF,
    ) -> None:
        radius = max(scene.bloom_radius, 1.0)
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(
            0.0,
            self.with_alpha(
                self.config.glow_color,
                int(92 * scene.visibility * scene.glow_intensity),
            ),
        )
        gradient.setColorAt(
            0.45,
            self.with_alpha(
                self.config.glow_color,
                int(38 * scene.visibility * scene.glow_intensity),
            ),
        )
        gradient.setColorAt(1.0, self.with_alpha(self.config.glow_color, 0))

        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)

    def _draw_inner_glow(
        self,
        painter: QPainter,
        scene: Scene,
        center: QPointF,
    ) -> None:
        radius = max(scene.core_radius * 1.45, 1.0)
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(
            0.0,
            self.with_alpha(
                self.config.core_inner_color,
                int(138 * scene.core_alpha * scene.glow_intensity),
            ),
        )
        gradient.setColorAt(
            0.56,
            self.with_alpha(
                self.config.glow_color,
                int(64 * scene.core_alpha * scene.glow_intensity),
            ),
        )
        gradient.setColorAt(1.0, self.with_alpha(self.config.glow_color, 0))

        painter.setBrush(gradient)
        painter.drawEllipse(center, radius, radius)
