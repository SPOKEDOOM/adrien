from __future__ import annotations

from dataclasses import dataclass

from app.rendering.state import PresenceState


@dataclass(frozen=True, slots=True)
class AnimationProfile:
    """State-specific visual behavior for the Presence Engine."""

    rotation_speed: float
    particle_density: float
    pulse_strength: float
    glow_intensity: float
    ring_intensity: float
    ring_speed_multiplier: float
    deformation_strength: float
    particle_speed_multiplier: float
    breathing_speed: float


ANIMATION_PROFILES: dict[PresenceState, AnimationProfile] = {
    PresenceState.BOOTING: AnimationProfile(
        rotation_speed=0.72,
        particle_density=0.42,
        pulse_strength=0.65,
        glow_intensity=0.62,
        ring_intensity=0.48,
        ring_speed_multiplier=0.62,
        deformation_strength=0.38,
        particle_speed_multiplier=0.72,
        breathing_speed=0.75,
    ),
    PresenceState.READY: AnimationProfile(
        rotation_speed=1.0,
        particle_density=0.78,
        pulse_strength=0.82,
        glow_intensity=0.86,
        ring_intensity=0.78,
        ring_speed_multiplier=1.0,
        deformation_strength=0.5,
        particle_speed_multiplier=1.0,
        breathing_speed=0.9,
    ),
    PresenceState.LISTENING: AnimationProfile(
        rotation_speed=1.18,
        particle_density=0.95,
        pulse_strength=1.05,
        glow_intensity=1.08,
        ring_intensity=0.9,
        ring_speed_multiplier=1.16,
        deformation_strength=0.72,
        particle_speed_multiplier=1.12,
        breathing_speed=1.25,
    ),
    PresenceState.THINKING: AnimationProfile(
        rotation_speed=1.55,
        particle_density=1.0,
        pulse_strength=0.92,
        glow_intensity=0.98,
        ring_intensity=1.0,
        ring_speed_multiplier=1.42,
        deformation_strength=0.82,
        particle_speed_multiplier=1.35,
        breathing_speed=1.05,
    ),
    PresenceState.PROCESSING: AnimationProfile(
        rotation_speed=1.9,
        particle_density=1.0,
        pulse_strength=1.18,
        glow_intensity=1.2,
        ring_intensity=1.0,
        ring_speed_multiplier=1.8,
        deformation_strength=1.0,
        particle_speed_multiplier=1.55,
        breathing_speed=1.45,
    ),
    PresenceState.SPEAKING: AnimationProfile(
        rotation_speed=1.28,
        particle_density=0.9,
        pulse_strength=1.28,
        glow_intensity=1.16,
        ring_intensity=0.86,
        ring_speed_multiplier=1.1,
        deformation_strength=0.92,
        particle_speed_multiplier=1.2,
        breathing_speed=1.75,
    ),
    PresenceState.IDLE: AnimationProfile(
        rotation_speed=0.62,
        particle_density=0.58,
        pulse_strength=0.52,
        glow_intensity=0.64,
        ring_intensity=0.52,
        ring_speed_multiplier=0.55,
        deformation_strength=0.32,
        particle_speed_multiplier=0.66,
        breathing_speed=0.55,
    ),
    PresenceState.ERROR: AnimationProfile(
        rotation_speed=0.35,
        particle_density=0.72,
        pulse_strength=1.45,
        glow_intensity=1.25,
        ring_intensity=0.95,
        ring_speed_multiplier=-0.45,
        deformation_strength=1.3,
        particle_speed_multiplier=1.85,
        breathing_speed=2.1,
    ),
    PresenceState.MATERIALIZING: AnimationProfile(
        rotation_speed=1.35,
        particle_density=1.0,
        pulse_strength=1.1,
        glow_intensity=1.0,
        ring_intensity=1.0,
        ring_speed_multiplier=1.25,
        deformation_strength=0.95,
        particle_speed_multiplier=1.25,
        breathing_speed=1.4,
    ),
    PresenceState.DISSOLVING: AnimationProfile(
        rotation_speed=0.95,
        particle_density=0.85,
        pulse_strength=0.9,
        glow_intensity=0.74,
        ring_intensity=0.7,
        ring_speed_multiplier=-0.9,
        deformation_strength=1.1,
        particle_speed_multiplier=1.7,
        breathing_speed=1.25,
    ),
}
