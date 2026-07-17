from __future__ import annotations

import math

from app.rendering.config import RendererConfig
from app.rendering.scene import Scene
from app.rendering.materialization_controller import MaterializationPhase


class AnimationEngine:
    """Advances Presence scene state without doing any drawing."""

    def __init__(self, config: RendererConfig | None = None):
        self.config = config or RendererConfig()

    def tick(self, scene: Scene, delta_seconds: float) -> None:
        bounded_delta = min(max(delta_seconds, 0.0), 0.1)

        scene.transition_controller.update(bounded_delta)
        if scene.is_materializing:
            scene.materialization_controller.update(bounded_delta)
        scene.elapsed_seconds += bounded_delta
        self._animate_lifecycle(scene, bounded_delta)
        self._animate_core(scene, bounded_delta)
        self._animate_rings(scene, bounded_delta)
        self._animate_particles(scene, bounded_delta)
        self._manage_particle_population(scene)

    def _animate_lifecycle(self, scene: Scene, delta_seconds: float) -> None:
        if scene.is_materializing:
            controller = scene.materialization_controller
            phase_progress = self._ease_out_cubic(controller.phase_progress)
            scene.visibility = self._ease_out_cubic(controller.progress)

            if controller.phase is MaterializationPhase.FADE_IN:
                scene.core_alpha = 0.0
                scene.glow_intensity = 0.08 * phase_progress
                scene.ring_assembly = 0.0
            elif controller.phase is MaterializationPhase.CONVERGENCE:
                scene.core_alpha = 0.08 * phase_progress
                scene.glow_intensity = scene.profile.glow_intensity * (
                    0.12 + 0.34 * phase_progress
                )
                scene.ring_assembly = 0.0
            elif controller.phase is MaterializationPhase.CORE_FORMATION:
                formation_pulse = math.sin(math.pi * self._clamp((phase_progress - 0.68) / 0.32, 0.0, 1.0))
                scene.core_alpha = min(1.0, 0.08 + 0.86 * phase_progress + 0.09 * formation_pulse)
                scene.glow_intensity = scene.profile.glow_intensity * (
                    0.46 + 0.44 * phase_progress
                )
                scene.ring_assembly = phase_progress
            else:
                scene.core_alpha = 0.94 + 0.06 * phase_progress
                scene.glow_intensity = scene.profile.glow_intensity * (
                    0.9 + 0.1 * phase_progress
                )
                scene.ring_assembly = 1.0
                if phase_progress >= 0.18 and not scene.energy_wave_triggered:
                    scene.energy_wave_triggered = True
                if scene.energy_wave_triggered:
                    scene.energy_wave_progress = self._clamp((phase_progress - 0.18) / 0.72, 0.0, 1.0)
            return

        target_visibility = 1.0
        scene.visibility = self._approach(scene.visibility, target_visibility, delta_seconds * 1.4)
        target_core_alpha = min(1.0, scene.visibility * scene.profile.core_intensity)
        scene.core_alpha = self._approach(scene.core_alpha, target_core_alpha, delta_seconds * 1.8)
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
        radius = (
            self.config.core_base_radius
            * scene.core_alpha
            * profile.core_size_multiplier
        )
        radius += pulse * self.config.core_pulse_amplitude * profile.pulse_strength
        radius += breath * self.config.core_breath_amplitude
        outward_wave = max(0.0, math.sin(scene.elapsed_seconds * 4.4))
        radius += outward_wave * 12.0 * profile.outward_pulse_strength
        radius += profile.entry_core_pulse * scene.transition_controller.entry_accent
        radius += profile.entry_outward_pulse * scene.transition_controller.entry_accent

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
            layer_multiplier = 1.0
            if index >= self.config.inner_ring_count:
                layer_multiplier = profile.outer_ring_speed_multiplier
            layer_multiplier += (
                profile.entry_ring_boost * scene.transition_controller.entry_accent
            )
            scene.ring_angles[index] = (
                scene.ring_angles[index]
                + speed
                * profile.ring_speed_multiplier
                * layer_multiplier
                * delta_seconds
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
            if scene.is_materializing:
                stagger = index * 0.09
                reveal = self._clamp(
                    (scene.ring_assembly - stagger) / max(0.1, 1.0 - stagger),
                    0.0,
                    1.0,
                )
                overshoot = 1.04 + (index % 2) * 0.025
                scene.ring_reveals[index] = self._ease_out_cubic(reveal) * overshoot
            else:
                scene.ring_reveals[index] = self._approach(
                    scene.ring_reveals[index], 1.0, delta_seconds * 2.2
                )

    def _animate_particles(self, scene: Scene, delta_seconds: float) -> None:
        for particle in scene.particles:
            particle.age += delta_seconds
            if scene.is_materializing:
                particle.remember_trail()
            organic_wobble = math.sin(
                scene.elapsed_seconds * particle.orbit_wobble_speed + particle.phase
            )
            particle.angle_degrees += (
                (particle.angular_velocity + organic_wobble * 4.5)
                * scene.profile.particle_speed_multiplier
                * delta_seconds
            )

            radius_multiplier = scene.profile.particle_radius_multiplier
            attraction_strength = scene.profile.particle_attraction_strength
            if scene.is_materializing:
                controller = scene.materialization_controller
                phase_progress = controller.phase_progress
                if controller.phase is MaterializationPhase.FADE_IN:
                    radius_multiplier = 1.35
                    attraction_strength = 0.25
                elif controller.phase is MaterializationPhase.CONVERGENCE:
                    radius, angle = particle.curved_position(phase_progress)
                    particle.orbit_radius = radius
                    particle.angle_degrees = angle
                    radius_multiplier = 1.0
                    attraction_strength = 0.0
                elif controller.phase is MaterializationPhase.CORE_FORMATION:
                    radius_multiplier = 0.53 + 0.19 * phase_progress
                    attraction_strength = 2.0 + (particle.phase % 1.2)
                else:
                    radius_multiplier = 0.72 + 0.28 * phase_progress
                    attraction_strength = 2.2 * (1.0 - phase_progress) + 0.35
                    if phase_progress >= 0.92:
                        particle.clear_trail()
            target_radius = particle.target_radius * radius_multiplier
            if (
                attraction_strength > 0.0
                or radius_multiplier != 1.0
            ):
                particle.orbit_radius = self._approach(
                    particle.orbit_radius,
                    target_radius,
                    delta_seconds * max(0.2, attraction_strength),
                )
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
                particle.target_opacity
                * scene.visibility
                * scene.profile.particle_opacity_multiplier,
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
