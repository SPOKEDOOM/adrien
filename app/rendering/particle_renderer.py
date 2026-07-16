from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter

from app.rendering.config import RendererConfig
from app.rendering.particle import Particle
from app.rendering.renderer import Renderer
from app.rendering.scene import Scene


class ParticleRenderer(Renderer):
    """Draws ambient particles orbiting the Presence core."""

    def __init__(self, config: RendererConfig):
        super().__init__(config)

    def render(self, painter: QPainter, scene: Scene) -> None:
        painter.save()
        painter.setPen(Qt.NoPen)

        for particle in scene.particles:
            self._draw_particle(painter, scene, particle)

        painter.restore()

    def _draw_particle(
        self,
        painter: QPainter,
        scene: Scene,
        particle: Particle,
    ) -> None:
        if particle.opacity <= 0.01:
            return

        position = self._position(scene, particle)
        alpha = self._alpha(scene, particle)
        color = QColor(self.config.particle_color)
        color.setAlpha(alpha)

        painter.setBrush(color)
        painter.drawEllipse(position, particle.size, particle.size)

    def _position(self, scene: Scene, particle: Particle) -> QPointF:
        angle = math.radians(particle.angle_degrees)
        drift = math.sin(scene.elapsed_seconds * particle.drift_speed + particle.phase)
        radius = particle.orbit_radius + drift * particle.drift_amplitude

        return QPointF(
            scene.center_x + math.cos(angle) * radius,
            scene.center_y + math.sin(angle) * radius,
        )

    def _alpha(self, scene: Scene, particle: Particle) -> int:
        wave = math.sin(scene.elapsed_seconds * particle.twinkle_speed + particle.phase)
        normalized = (wave + 1.0) / 2.0
        alpha_range = self.config.particle_max_alpha - self.config.particle_min_alpha
        lifecycle_fade = 1.0

        if particle.life_progress > 0.78:
            lifecycle_fade = max(0.0, 1.0 - ((particle.life_progress - 0.78) / 0.22))

        return int(
            (
                self.config.particle_min_alpha
                + alpha_range * normalized * particle.opacity
            )
            * scene.visibility
            * lifecycle_fade
        )
