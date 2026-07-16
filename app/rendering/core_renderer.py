from __future__ import annotations

from PySide6.QtGui import QPainter

from app.rendering.background_renderer import BackgroundRenderer
from app.rendering.config import RendererConfig
from app.rendering.energy_core_renderer import EnergyCoreRenderer
from app.rendering.glow_renderer import GlowRenderer
from app.rendering.highlight_renderer import HighlightRenderer
from app.rendering.particle_renderer import ParticleRenderer
from app.rendering.post_effect_renderer import PostEffectRenderer
from app.rendering.ring_renderer import RingRenderer
from app.rendering.scene import Scene


class CoreRenderer:
    """Coordinates all Presence Engine render passes."""

    def __init__(self, config: RendererConfig | None = None):
        self.config = config or RendererConfig()
        self.background_renderer = BackgroundRenderer(self.config)
        self.glow_renderer = GlowRenderer(self.config)
        self.particle_renderer = ParticleRenderer(self.config)
        self.energy_core_renderer = EnergyCoreRenderer(self.config)
        self.ring_renderer = RingRenderer(self.config)
        self.highlight_renderer = HighlightRenderer(self.config)
        self.post_effect_renderer = PostEffectRenderer(self.config)

    def render(self, painter: QPainter, scene: Scene) -> None:
        painter.save()

        self.background_renderer.render(painter, scene)
        self.glow_renderer.render(painter, scene)
        self.particle_renderer.render(painter, scene)
        self.energy_core_renderer.render(painter, scene)
        self.ring_renderer.render_inner_rings(painter, scene)
        self.ring_renderer.render_outer_rings(painter, scene)
        self.highlight_renderer.render(painter, scene)
        self.post_effect_renderer.render(painter, scene)

        painter.restore()
