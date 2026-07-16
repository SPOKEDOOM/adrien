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
            lifetime=rng.uniform(
                config.particle_min_lifetime,
                config.particle_max_lifetime,
            ),
            phase=rng.uniform(0.0, 6.283185307179586),
            drift_speed=rng.uniform(0.7, 2.4),
            drift_amplitude=rng.uniform(2.0, 10.0),
            twinkle_speed=rng.uniform(1.5, 4.2),
            fade_speed=config.particle_fade_speed * rng.uniform(0.7, 1.35),
        )

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
