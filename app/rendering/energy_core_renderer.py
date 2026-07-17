from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QRadialGradient

from app.rendering.config import RendererConfig
from app.rendering.renderer import Renderer
from app.rendering.scene import Scene


class EnergyCoreRenderer(Renderer):
    """Draws the breathing, deforming energy core."""

    def __init__(self, config: RendererConfig):
        super().__init__(config)
        self._unit_points = tuple(
            (math.tau * step) / config.core_shape_points
            for step in range(config.core_shape_points + 1)
        )

    def render(self, painter: QPainter, scene: Scene) -> None:
        if scene.core_alpha <= 0.0:
            return

        painter.save()
        painter.setOpacity(scene.core_alpha)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self._core_gradient(scene))
        painter.drawPath(self._core_path(scene))
        painter.restore()

    def _core_gradient(self, scene: Scene) -> QRadialGradient:
        center = QPointF(scene.center_x, scene.center_y)
        gradient = QRadialGradient(center, scene.core_radius * 1.14)
        gradient.setColorAt(0.0, self.config.core_inner_color)
        gradient.setColorAt(0.35, self.config.core_mid_color)
        gradient.setColorAt(0.72, self.config.core_outer_color)
        gradient.setColorAt(1.0, self.with_alpha(self.config.core_outer_color, 32))
        return gradient

    def _core_path(self, scene: Scene) -> QPainterPath:
        base_radius = scene.core_radius
        deformation = scene.core_deformation
        path = QPainterPath()

        for step, theta in enumerate(self._unit_points):
            radius = self._deformed_radius(base_radius, deformation, theta, scene)
            point = QPointF(
                scene.center_x + math.cos(theta) * radius,
                scene.center_y + math.sin(theta) * radius,
            )

            if step == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)

        path.closeSubpath()
        return path

    def _deformed_radius(
        self,
        base_radius: float,
        deformation: float,
        theta: float,
        scene: Scene,
    ) -> float:
        primary_wave = math.sin(theta * 3.0 + scene.core_energy_angle)
        secondary_wave = math.cos(theta * 5.0 - scene.elapsed_seconds * 1.7)
        return base_radius + deformation * (primary_wave * 0.72 + secondary_wave * 0.28)
