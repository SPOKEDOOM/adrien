from __future__ import annotations

import math

from app.rendering.config import RendererConfig
from app.rendering.scene import Scene
from app.rendering.state import PresenceState


class AnimationEngine:
    """Advances Presence scene state without doing any drawing."""

    def __init__(self, config: RendererConfig | None = None):
        self.config = config or RendererConfig()

    def tick(self, scene: Scene, delta_seconds: float) -> None:
        bounded_delta = min(max(delta_seconds, 0.0), 0.1)

        scene.elapsed_seconds += bounded_delta
        self._animate_lifecycle(scene, bounded_delta)
        self._animate_core(scene, bounded_delta)
        self._animate_rings(scene, bounded_delta)
        self._animate_particles(scene, bounded_delta)
        self._manage_particle_population(scene)

    def _animate_lifecycle(self, scene: Scene, delta_seconds: float) -> None:
        if scene.is_materializing:
            progress = scene.materialization_progress
            progress += delta_seconds / self.config.materialization_duration
            scene.materialization_progress = self._clamp(progress, 0.0, 1.0)
            eased = self._ease_out_cubic(scene.materialization_progress)

            scene.visibility = eased
            scene.core_alpha = self._clamp((eased - 0.18) / 0.82, 0.0, 1.0)
            scene.glow_intensity = self._clamp((eased - 0.08) / 0.92, 0.0, 1.0)
            scene.ring_assembly = self._clamp((eased - 0.34) / 0.66, 0.0, 1.0)

            if scene.materialization_progress >= 1.0:
                scene.set_state(scene.target_state)
                scene.visibility = 1.0
                scene.core_alpha = 1.0
                scene.glow_intensity = scene.profile.glow_intensity
                scene.ring_assembly = 1.0
            return

        if scene.is_dissolving:
            progress = scene.dissolve_progress
            progress += delta_seconds / self.config.dissolve_duration
            scene.dissolve_progress = self._clamp(progress, 0.0, 1.0)
            remaining = 1.0 - self._ease_in_cubic(scene.dissolve_progress)

            scene.visibility = remaining
            scene.core_alpha = remaining
            scene.glow_intensity = remaining
            scene.ring_assembly = remaining

            if scene.dissolve_progress >= 1.0:
                scene.set_state(PresenceState.IDLE)
                scene.visibility = 0.36
                scene.core_alpha = 0.36
                scene.glow_intensity = 0.34
                scene.ring_assembly = 0.22
            return

        target_visibility = 1.0 if scene.presence_state is not PresenceState.IDLE else 0.56
        scene.visibility = self._approach(scene.visibility, target_visibility, delta_seconds * 1.4)
        scene.core_alpha = self._approach(scene.core_alpha, scene.visibility, delta_seconds * 1.8)
        scene.glow_intensity = self._approach(
            scene.glow_intensity,
            scene.profile.glow_intensity,
            delta_seconds * 1.8,
        )
        scene.ring_assembly = self._approach(scene.ring_assembly, 1.0, delta_seconds * 1.6)

    def _animate_core(self, scene: Scene, delta_seconds: float) -> None:
        profile = scene.profile
        pulse = math.sin(scene.elapsed_seconds * self.config.core_pulse_speed)
        breath = math.sin(
            scene.elapsed_seconds
            * self.config.core_breath_speed
            * profile.breathing_speed,
        )
        radius = self.config.core_base_radius * scene.core_alpha
        radius += pulse * self.config.core_pulse_amplitude * profile.pulse_strength
        radius += breath * self.config.core_breath_amplitude

        scene.core_radius = max(0.0, radius)
        scene.core_deformation = (
            self.config.core_deformation_amplitude
            * profile.deformation_strength
            * scene.core_alpha
        )
        scene.core_energy_angle += 0.9 * profile.rotation_speed * delta_seconds
        scene.bloom_radius = radius * self.config.glow_radius_multiplier
        scene.halo_radius = radius * self.config.halo_radius_multiplier

    def _animate_rings(self, scene: Scene, delta_seconds: float) -> None:
        profile = scene.profile

        for index, speed in enumerate(self.config.ring_rotation_speeds):
            scene.ring_angles[index] = (
                scene.ring_angles[index]
                + speed * profile.ring_speed_multiplier * delta_seconds
            ) % 360.0
            target_opacity = (
                self.config.ring_opacities[index]
                * profile.ring_intensity
                * scene.ring_assembly
                * scene.visibility
            )
            scene.ring_opacities[index] = self._approach(
                scene.ring_opacities[index],
                target_opacity,
                delta_seconds * 2.6,
            )

    def _animate_particles(self, scene: Scene, delta_seconds: float) -> None:
        for particle in scene.particles:
            particle.age += delta_seconds
            particle.angle_degrees += (
                particle.angular_velocity
                * scene.profile.particle_speed_multiplier
                * delta_seconds
            )

            if scene.is_materializing:
                particle.orbit_radius = self._approach(
                    particle.orbit_radius,
                    particle.target_radius,
                    delta_seconds * 2.9,
                )
            elif scene.is_dissolving:
                particle.orbit_radius += abs(particle.radial_velocity) * delta_seconds * 5.0
                particle.retire()
            else:
                particle.orbit_radius += particle.radial_velocity * delta_seconds

            if particle.orbit_radius < self.config.particle_min_radius:
                particle.radial_velocity = abs(particle.radial_velocity)

            if particle.orbit_radius > self.config.particle_max_radius:
                particle.radial_velocity = -abs(particle.radial_velocity)

            if particle.age >= particle.lifetime:
                particle.retire()

            particle.opacity = self._approach(
                particle.opacity,
                particle.target_opacity * scene.visibility,
                delta_seconds * particle.fade_speed,
            )

        scene.particles[:] = [particle for particle in scene.particles if not particle.expired]

    def _manage_particle_population(self, scene: Scene) -> None:
        desired_count = scene.desired_particle_count()

        while len(scene.particles) < desired_count:
            scene.spawn_particle(materializing=scene.is_materializing)

        if len(scene.particles) <= desired_count:
            return

        surplus = len(scene.particles) - desired_count

        for particle in scene.particles[-surplus:]:
            particle.retire()

    @staticmethod
    def _approach(current: float, target: float, amount: float) -> float:
        amount = AnimationEngine._clamp(amount, 0.0, 1.0)
        return current + (target - current) * amount

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))

    @staticmethod
    def _ease_out_cubic(value: float) -> float:
        clamped = AnimationEngine._clamp(value, 0.0, 1.0)
        return 1.0 - pow(1.0 - clamped, 3)

    @staticmethod
    def _ease_in_cubic(value: float) -> float:
        clamped = AnimationEngine._clamp(value, 0.0, 1.0)
        return clamped * clamped * clamped
