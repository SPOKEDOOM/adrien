from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtGui import QColor


@dataclass(frozen=True, slots=True)
class RendererConfig:
    """Visual tuning for the ADRIEN Presence Engine."""

    background_top_color: QColor = field(default_factory=lambda: QColor("#151922"))
    background_color: QColor = field(default_factory=lambda: QColor("#101216"))
    background_bottom_color: QColor = field(default_factory=lambda: QColor("#07090d"))
    core_inner_color: QColor = field(default_factory=lambda: QColor(210, 255, 255))
    core_mid_color: QColor = field(default_factory=lambda: QColor(0, 220, 255))
    core_outer_color: QColor = field(default_factory=lambda: QColor(0, 34, 78))
    glow_color: QColor = field(default_factory=lambda: QColor(0, 220, 255))
    halo_color: QColor = field(default_factory=lambda: QColor(32, 120, 255))
    ring_color: QColor = field(default_factory=lambda: QColor(72, 235, 255))
    secondary_ring_color: QColor = field(default_factory=lambda: QColor(70, 145, 255))
    particle_color: QColor = field(default_factory=lambda: QColor(170, 245, 255))

    core_base_radius: float = 54.0
    core_pulse_amplitude: float = 6.0
    core_pulse_speed: float = 2.2
    core_breath_amplitude: float = 3.5
    core_breath_speed: float = 0.72
    core_deformation_amplitude: float = 4.2
    core_shape_points: int = 96
    glow_radius_multiplier: float = 2.65
    halo_radius_multiplier: float = 4.6

    particle_count: int = 720
    particle_min_radius: float = 82.0
    particle_max_radius: float = 285.0
    particle_min_size: float = 1.0
    particle_max_size: float = 3.8
    particle_min_alpha: int = 34
    particle_max_alpha: int = 185
    particle_min_lifetime: float = 5.0
    particle_max_lifetime: float = 15.0
    particle_spawn_radius_multiplier: float = 1.18
    particle_fade_speed: float = 2.8

    ring_offsets: tuple[float, ...] = (18.0, 32.0, 49.0, 70.0, 96.0)
    ring_widths: tuple[float, ...] = (3.4, 2.4, 1.8, 1.3, 0.9)
    ring_arc_spans: tuple[int, ...] = (218, 92, 156, 64, 124)
    ring_rotation_speeds: tuple[float, ...] = (42.0, -66.0, 24.0, -18.0, 9.0)
    ring_opacities: tuple[float, ...] = (0.92, 0.72, 0.62, 0.44, 0.32)
    inner_ring_count: int = 3

    dissolve_duration: float = 2.4
