from __future__ import annotations

from dataclasses import dataclass

from app.core.presence_state import PresenceState


@dataclass(frozen=True, slots=True)
class AnimationProfile:
    """All visual tuning associated with one operational state."""

    rotation_speed: float
    particle_density: float
    pulse_strength: float
    glow_intensity: float
    ring_intensity: float
    ring_speed_multiplier: float
    deformation_strength: float
    particle_speed_multiplier: float
    breathing_speed: float
    particle_opacity_multiplier: float
    particle_attraction_strength: float
    core_intensity: float
    highlight_intensity: float
    core_size_multiplier: float
    glow_pulse_depth: float
    outer_ring_speed_multiplier: float
    particle_radius_multiplier: float
    outward_pulse_strength: float


def _profile(**values: float) -> AnimationProfile:
    defaults = dict(
        rotation_speed=1.0, particle_density=0.78, pulse_strength=0.82,
        glow_intensity=0.86, ring_intensity=0.78, ring_speed_multiplier=1.0,
        deformation_strength=0.5, particle_speed_multiplier=1.0,
        breathing_speed=0.9, particle_opacity_multiplier=1.0,
        particle_attraction_strength=0.0, core_intensity=1.0,
        highlight_intensity=1.0,
        core_size_multiplier=1.0, glow_pulse_depth=0.08,
        outer_ring_speed_multiplier=1.0, particle_radius_multiplier=1.0,
        outward_pulse_strength=0.0,
    )
    defaults.update(values)
    return AnimationProfile(**defaults)


ANIMATION_PROFILES: dict[PresenceState, AnimationProfile] = {
    PresenceState.BOOTING: _profile(
        rotation_speed=0.55, particle_density=0.32, pulse_strength=0.48,
        glow_intensity=0.42, ring_intensity=0.38, ring_speed_multiplier=0.48,
        particle_speed_multiplier=0.55, breathing_speed=0.6,
        particle_opacity_multiplier=0.55, core_intensity=0.62,
        highlight_intensity=0.4, core_size_multiplier=0.82,
        glow_pulse_depth=0.04, outer_ring_speed_multiplier=0.55,
    ),
    PresenceState.MATERIALIZING: _profile(
        rotation_speed=1.25, particle_density=1.0, pulse_strength=1.05,
        glow_intensity=1.08, ring_intensity=1.0, ring_speed_multiplier=1.2,
        deformation_strength=0.85, particle_speed_multiplier=1.3,
        breathing_speed=1.35, particle_attraction_strength=2.9,
        core_intensity=1.18, highlight_intensity=1.1,
        core_size_multiplier=1.08, glow_pulse_depth=0.16,
        outer_ring_speed_multiplier=1.25, particle_radius_multiplier=0.72,
    ),
    PresenceState.READY: _profile(
        glow_intensity=0.78, ring_intensity=0.72, pulse_strength=0.72,
        breathing_speed=0.72, glow_pulse_depth=0.06,
    ),
    PresenceState.LISTENING: _profile(
        rotation_speed=1.16, particle_density=0.9, pulse_strength=1.08,
        glow_intensity=1.06, ring_intensity=0.9, ring_speed_multiplier=1.3,
        deformation_strength=0.68, particle_speed_multiplier=1.1,
        breathing_speed=1.35, particle_opacity_multiplier=1.08,
        core_intensity=1.12, highlight_intensity=1.25,
        core_size_multiplier=1.14, glow_pulse_depth=0.24,
        outer_ring_speed_multiplier=1.65,
    ),
    PresenceState.THINKING: _profile(
        rotation_speed=1.5, particle_density=0.96, pulse_strength=0.94,
        glow_intensity=0.98, ring_intensity=1.0, ring_speed_multiplier=1.52,
        deformation_strength=0.88, particle_speed_multiplier=1.28,
        breathing_speed=1.12, particle_attraction_strength=1.15,
        core_intensity=1.2, highlight_intensity=1.18,
        core_size_multiplier=1.06, glow_pulse_depth=0.12,
        outer_ring_speed_multiplier=1.45, particle_radius_multiplier=0.62,
    ),
    PresenceState.RESPONDING: _profile(
        rotation_speed=1.3, particle_density=0.92, pulse_strength=1.3,
        glow_intensity=1.15, ring_intensity=0.9, ring_speed_multiplier=1.12,
        deformation_strength=0.9, particle_speed_multiplier=1.18,
        breathing_speed=1.75, particle_opacity_multiplier=1.12,
        core_intensity=1.28, highlight_intensity=1.85,
        core_size_multiplier=1.1, glow_pulse_depth=0.2,
        outer_ring_speed_multiplier=1.25, outward_pulse_strength=1.0,
    ),
    PresenceState.SLEEP: _profile(
        rotation_speed=0.35, particle_density=0.34, pulse_strength=0.35,
        glow_intensity=0.3, ring_intensity=0.28, ring_speed_multiplier=0.22,
        deformation_strength=0.25, particle_speed_multiplier=0.3,
        breathing_speed=0.42, particle_opacity_multiplier=0.42,
        core_intensity=0.42, highlight_intensity=0.16,
        core_size_multiplier=0.78, glow_pulse_depth=0.025,
        outer_ring_speed_multiplier=0.16, particle_radius_multiplier=1.08,
    ),
}


def profile_for(state: PresenceState) -> AnimationProfile:
    return ANIMATION_PROFILES[state]
