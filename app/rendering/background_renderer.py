from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QLinearGradient, QPainter, QRadialGradient

from app.rendering.config import RendererConfig
from app.rendering.renderer import Renderer
from app.rendering.scene import Scene


class BackgroundRenderer(Renderer):
    """Draws the deep field behind the Presence Engine."""

    def __init__(self, config: RendererConfig):
        super().__init__(config)

    def render(self, painter: QPainter, scene: Scene) -> None:
        painter.save()
        self._draw_base_gradient(painter, scene)
        self._draw_energy_field(painter, scene)
        painter.restore()

    def _draw_base_gradient(self, painter: QPainter, scene: Scene) -> None:
        gradient = QLinearGradient(0.0, 0.0, 0.0, float(scene.viewport_height))
        gradient.setColorAt(0.0, self.config.background_top_color)
        gradient.setColorAt(0.54, self.config.background_color)
        gradient.setColorAt(1.0, self.config.background_bottom_color)

        painter.fillRect(
            0,
            0,
            scene.viewport_width,
            scene.viewport_height,
            gradient,
        )

    def _draw_energy_field(self, painter: QPainter, scene: Scene) -> None:
        radius = max(scene.viewport_width, scene.viewport_height) * 0.58
        center = QPointF(scene.center_x, scene.center_y)

        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(
            0.0,
            self.with_alpha(
                self.config.glow_color,
                int(34 * scene.visibility * scene.glow_intensity),
            ),
        )
        gradient.setColorAt(
            0.42,
            self.with_alpha(
                self.config.secondary_ring_color,
                int(13 * scene.visibility * scene.glow_intensity),
            ),
        )
        gradient.setColorAt(1.0, self.with_alpha(self.config.glow_color, 0))

        painter.fillRect(
            0,
            0,
            scene.viewport_width,
            scene.viewport_height,
            gradient,
        )
