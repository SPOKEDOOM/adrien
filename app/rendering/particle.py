from __future__ import annotations

import random
from dataclasses import dataclass

from app.rendering.config import RendererConfig


@dataclass(slots=True)
class Particle:
    """A single ambient energy particle in the Presence scene."""

    orbit_radius: float
    target_radius: float
    angle_degrees: float
    size: float
    angular_velocity: float
    radial_velocity: float
    opacity: float
    target_opacity: float
    age: float
    lifetime: float
    phase: float
    drift_speed: float
    drift_amplitude: float
    twinkle_speed: float
    fade_speed: float
    depth: float
    size_phase: float
    orbit_wobble_speed: float
    materialization_start_radius: float = 0.0
    materialization_start_angle: float = 0.0
    materialization_control_radius: float = 0.0
    materialization_control_angle: float = 0.0
    materialization_delay: float = 0.0
    materialization_duration: float = 1.0
    depth_layer: int = 1
    trail_radius_1: float | None = None
    trail_angle_1: float | None = None
    trail_radius_2: float | None = None
    trail_angle_2: float | None = None

    @classmethod
    def create(
        cls,
        config: RendererConfig,
        rng: random.Random,
        materializing: bool = False,
    ) -> Particle:
        target_radius = rng.uniform(
            config.particle_min_radius,
            config.particle_max_radius,
        )
        spawn_radius = target_radius

        if materializing:
            spawn_radius = rng.uniform(
                config.particle_max_radius,
                config.particle_max_radius * config.particle_spawn_radius_multiplier,
            )

        return cls(
            orbit_radius=spawn_radius,
            target_radius=target_radius,
            angle_degrees=rng.uniform(0.0, 360.0),
            size=rng.uniform(config.particle_min_size, config.particle_max_size),
            angular_velocity=rng.uniform(-26.0, 36.0),
            radial_velocity=rng.uniform(-4.0, 6.0),
            opacity=0.0 if materializing else rng.uniform(0.16, 0.72),
            target_opacity=rng.uniform(0.42, 1.0),
            age=0.0,
            lifetime=rng.uniform(config.particle_min_lifetime, config.particle_max_lifetime),
            phase=rng.uniform(0.0, 6.283185307179586),
            drift_speed=rng.uniform(0.7, 2.4),
            drift_amplitude=rng.uniform(2.0, 10.0),
            twinkle_speed=rng.uniform(1.5, 4.2),
            fade_speed=config.particle_fade_speed * rng.uniform(0.7, 1.35),
            depth=rng.uniform(0.72, 1.24),
            size_phase=rng.uniform(0.0, 6.283185307179586),
            orbit_wobble_speed=rng.uniform(0.35, 1.2),
        )

    def configure_materialization(self, rng: random.Random) -> None:
        """Cache one stable curved path and arrival window for this run."""
        self.depth_layer = rng.choices((0, 1, 2), weights=(0.34, 0.46, 0.20), k=1)[0]
        self.depth = (0.72, 0.98, 1.24)[self.depth_layer] * rng.uniform(0.94, 1.06)
        self.materialization_start_radius = self.orbit_radius
        self.materialization_start_angle = self.angle_degrees
        spiral = rng.uniform(-76.0, 76.0) * (0.75 + self.depth_layer * 0.18)
        self.materialization_control_angle = self.angle_degrees + spiral
        self.materialization_control_radius = max(
            self.target_radius,
            (self.orbit_radius + self.target_radius) * 0.5 + rng.uniform(-32.0, 42.0),
        )
        wave = rng.randrange(3)
        self.materialization_delay = 0.06 + wave * 0.14 + rng.uniform(0.0, 0.11)
        self.materialization_duration = rng.uniform(0.62, 0.94) + (2 - self.depth_layer) * 0.07
        self.clear_trail()

    def curved_progress(self, convergence_progress: float) -> float:
        local = (convergence_progress - self.materialization_delay) / self.materialization_duration
        local = max(0.0, min(1.0, local))
        # Smoothstep variants remain deterministic and make arrival less mechanical.
        exponent = (1.8, 2.1, 2.4)[self.depth_layer]
        eased = 1.0 - pow(1.0 - local, exponent)
        return eased

    def curved_position(self, convergence_progress: float) -> tuple[float, float]:
        t = self.curved_progress(convergence_progress)
        inverse = 1.0 - t
        radius = (
            inverse * inverse * self.materialization_start_radius
            + 2.0 * inverse * t * self.materialization_control_radius
            + t * t * self.target_radius * 0.53
        )
        angle = (
            inverse * inverse * self.materialization_start_angle
            + 2.0 * inverse * t * self.materialization_control_angle
            + t * t * (self.materialization_start_angle + self.angular_velocity * 0.18)
        )
        return radius, angle

    def remember_trail(self) -> None:
        self.trail_radius_2, self.trail_angle_2 = self.trail_radius_1, self.trail_angle_1
        self.trail_radius_1, self.trail_angle_1 = self.orbit_radius, self.angle_degrees

    def clear_trail(self) -> None:
        self.trail_radius_1 = self.trail_angle_1 = None
        self.trail_radius_2 = self.trail_angle_2 = None

    @property
    def life_progress(self) -> float:
        if self.lifetime <= 0.0:
            return 1.0

        return min(1.0, self.age / self.lifetime)

    @property
    def expired(self) -> bool:
        is_retired = self.target_opacity <= 0.0 and self.opacity <= 0.04
        reached_lifetime = self.age >= self.lifetime and self.opacity <= 0.04
        return is_retired or reached_lifetime

    def retire(self) -> None:
        self.target_opacity = 0.0

    def reset(
        self,
        config: RendererConfig,
        rng: random.Random,
        materializing: bool = False,
    ) -> None:
        fresh_particle = self.create(config, rng, materializing)
        self.orbit_radius = fresh_particle.orbit_radius
        self.target_radius = fresh_particle.target_radius
        self.angle_degrees = fresh_particle.angle_degrees
        self.size = fresh_particle.size
        self.angular_velocity = fresh_particle.angular_velocity
        self.radial_velocity = fresh_particle.radial_velocity
        self.opacity = fresh_particle.opacity
        self.target_opacity = fresh_particle.target_opacity
        self.age = fresh_particle.age
        self.lifetime = fresh_particle.lifetime
        self.phase = fresh_particle.phase
        self.drift_speed = fresh_particle.drift_speed
        self.drift_amplitude = fresh_particle.drift_amplitude
        self.twinkle_speed = fresh_particle.twinkle_speed
        self.fade_speed = fresh_particle.fade_speed
        self.depth = fresh_particle.depth
        self.size_phase = fresh_particle.size_phase
        self.orbit_wobble_speed = fresh_particle.orbit_wobble_speed
        self.clear_trail()
