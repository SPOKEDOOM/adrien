from __future__ import annotations

import random
from dataclasses import dataclass, field

from app.rendering.config import RendererConfig
from app.rendering.particle import Particle
from app.rendering.profiles import ANIMATION_PROFILES, AnimationProfile
from app.rendering.state import PresenceState


@dataclass(slots=True)
class Scene:
    """Mutable world state consumed by Presence renderers."""

    config: RendererConfig = field(default_factory=RendererConfig)
    viewport_width: int = 0
    viewport_height: int = 0
    elapsed_seconds: float = 0.0
    presence_state: PresenceState = PresenceState.BOOTING
    target_state: PresenceState = PresenceState.READY
    visibility: float = 0.0
    materialization_progress: float = 0.0
    dissolve_progress: float = 0.0
    core_radius: float = 0.0
    core_alpha: float = 0.0
    core_deformation: float = 0.0
    core_energy_angle: float = 0.0
    bloom_radius: float = 0.0
    halo_radius: float = 0.0
    glow_intensity: float = 0.0
    ring_assembly: float = 0.0
    ring_angles: list[float] = field(default_factory=list)
    ring_opacities: list[float] = field(default_factory=list)
    particles: list[Particle] = field(default_factory=list)
    rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self) -> None:
        self.core_radius = self.config.core_base_radius
        self.bloom_radius = self.core_radius * self.config.glow_radius_multiplier
        self.halo_radius = self.core_radius * self.config.halo_radius_multiplier
        self.ring_angles = [0.0 for _ in self.config.ring_offsets]
        self.ring_opacities = [0.0 for _ in self.config.ring_offsets]
        self.begin_materialization(PresenceState.READY)

    @property
    def center_x(self) -> float:
        return self.viewport_width / 2.0

    @property
    def center_y(self) -> float:
        return self.viewport_height / 2.0

    def set_viewport(self, width: int, height: int) -> None:
        self.viewport_width = max(0, width)
        self.viewport_height = max(0, height)

    @property
    def profile(self) -> AnimationProfile:
        return ANIMATION_PROFILES[self.presence_state]

    @property
    def is_materializing(self) -> bool:
        return self.presence_state is PresenceState.MATERIALIZING

    @property
    def is_dissolving(self) -> bool:
        return self.presence_state is PresenceState.DISSOLVING

    def begin_materialization(self, target_state: PresenceState = PresenceState.READY) -> None:
        self.presence_state = PresenceState.MATERIALIZING
        self.target_state = target_state
        self.visibility = 0.0
        self.materialization_progress = 0.0
        self.dissolve_progress = 0.0
        self.core_alpha = 0.0
        self.glow_intensity = 0.0
        self.ring_assembly = 0.0
        self.particles.clear()

    def begin_dissolve(self) -> None:
        self.presence_state = PresenceState.DISSOLVING
        self.target_state = PresenceState.IDLE
        self.dissolve_progress = 0.0

        for particle in self.particles:
            particle.retire()

    def set_state(self, state: PresenceState) -> None:
        if state is PresenceState.MATERIALIZING:
            self.begin_materialization()
            return

        if state is PresenceState.DISSOLVING:
            self.begin_dissolve()
            return

        self.presence_state = state
        self.target_state = state

    def desired_particle_count(self) -> int:
        profile = self.profile
        density = profile.particle_density * self.visibility

        if self.is_materializing:
            density *= max(0.15, self.materialization_progress)

        if self.is_dissolving:
            density *= max(0.0, 1.0 - self.dissolve_progress)

        return int(self.config.particle_count * density)

    def spawn_particle(self, materializing: bool = False) -> None:
        self.particles.append(Particle.create(self.config, self.rng, materializing))
