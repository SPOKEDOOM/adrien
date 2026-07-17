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
        self._particle_color = QColor(config.particle_color)
        self._alpha_colors = [self._color_with_alpha(alpha) for alpha in range(256)]

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
        size = self._size(scene, particle)
        painter.setBrush(self._alpha_colors[alpha])
        painter.drawEllipse(position, size, size)

    def _position(self, scene: Scene, particle: Particle) -> QPointF:
        angle = math.radians(particle.angle_degrees)
        elapsed = scene.elapsed_seconds
        drift = math.sin(elapsed * particle.drift_speed + particle.phase)
        depth_drift = math.cos(elapsed * particle.orbit_wobble_speed + particle.size_phase)
        radius = (
            particle.orbit_radius
            + drift * particle.drift_amplitude
            + depth_drift * (particle.depth - 1.0) * 9.0
        )

        return QPointF(
            scene.center_x + math.cos(angle) * radius,
            scene.center_y + math.sin(angle) * radius,
        )

    def _alpha(self, scene: Scene, particle: Particle) -> int:
        wave = math.sin(scene.elapsed_seconds * particle.twinkle_speed + particle.phase)
        normalized = (wave + 1.0) / 2.0
        alpha_range = self.config.particle_max_alpha - self.config.particle_min_alpha
        lifecycle_fade = 1.0
        depth_alpha = 0.76 + (particle.depth - 0.72) * 0.34

        if particle.life_progress > 0.78:
            lifecycle_fade = max(0.0, 1.0 - ((particle.life_progress - 0.78) / 0.22))

        return max(0, min(255, int(
            (
                self.config.particle_min_alpha
                + alpha_range * normalized * particle.opacity
            )
            * scene.visibility
            * lifecycle_fade
            * depth_alpha
        )))

    @staticmethod
    def _size(scene: Scene, particle: Particle) -> float:
        size_wave = math.sin(scene.elapsed_seconds * 0.9 + particle.size_phase) * 0.08
        return max(0.35, particle.size * particle.depth * (1.0 + size_wave))

    def _color_with_alpha(self, alpha: int) -> QColor:
        color = QColor(self._particle_color)
        color.setAlpha(alpha)
        return color
