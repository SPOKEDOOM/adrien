from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from app.rendering.config import RendererConfig
from app.rendering.renderer import Renderer
from app.rendering.scene import Scene


class RingRenderer(Renderer):
    """Draws rotating energy rings around the Presence core."""

    def __init__(self, config: RendererConfig):
        super().__init__(config)

    def render(self, painter: QPainter, scene: Scene) -> None:
        self.render_inner_rings(painter, scene)
        self.render_outer_rings(painter, scene)

    def render_inner_rings(self, painter: QPainter, scene: Scene) -> None:
        self._render_range(painter, scene, 0, self.config.inner_ring_count)

    def render_outer_rings(self, painter: QPainter, scene: Scene) -> None:
        self._render_range(
            painter,
            scene,
            self.config.inner_ring_count,
            len(self.config.ring_offsets),
        )

    def _render_range(
        self,
        painter: QPainter,
        scene: Scene,
        start_index: int,
        stop_index: int,
    ) -> None:
        if scene.visibility <= 0.0:
            return

        painter.save()
        painter.translate(scene.center_x, scene.center_y)
        painter.setBrush(Qt.NoBrush)

        for index in range(start_index, stop_index):
            offset = self.config.ring_offsets[index]
            self._draw_ring(painter, scene, index, offset)

        painter.restore()

    def _draw_ring(
        self,
        painter: QPainter,
        scene: Scene,
        index: int,
        offset: float,
    ) -> None:
        if scene.ring_opacities[index] <= 0.01:
            return

        radius = scene.core_radius + offset
        angle = scene.ring_angles[index]
        arc_span = self.config.ring_arc_spans[index]
        color = self._ring_color(index)
        color.setAlpha(int(255 * min(1.0, scene.ring_opacities[index])))

        painter.save()
        painter.rotate(angle)
        painter.setPen(self._pen(color, self.config.ring_widths[index]))

        bounds = QRectF(-radius, -radius, radius * 2.0, radius * 2.0)
        painter.drawArc(bounds, 0, arc_span * 16)

        accent_span = max(36, arc_span // 3)
        painter.drawArc(bounds, 190 * 16, accent_span * 16)
        self._draw_segments(painter, bounds, arc_span, index)

        painter.restore()

    def _draw_segments(
        self,
        painter: QPainter,
        bounds: QRectF,
        arc_span: int,
        index: int,
    ) -> None:
        segment_count = 3 + index
        segment_span = max(8, arc_span // (segment_count * 3))

        for segment_index in range(segment_count):
            start_angle = (segment_index * 360 // segment_count) + 18
            painter.drawArc(bounds, start_angle * 16, segment_span * 16)

    def _ring_color(self, index: int) -> QColor:
        if index % 2 == 0:
            return QColor(self.config.ring_color)

        return QColor(self.config.secondary_ring_color)

    @staticmethod
    def _pen(color: QColor, width: float) -> QPen:
        pen = QPen(color)
        pen.setWidthF(width)
        pen.setCapStyle(Qt.RoundCap)
        return pen
