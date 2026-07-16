from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from PySide6.QtGui import QColor, QPainter

from app.rendering.config import RendererConfig

if TYPE_CHECKING:
    from app.rendering.scene import Scene


class Renderer(ABC):
    """Base class for all Presence Engine renderers."""

    def __init__(self, config: RendererConfig):
        self.config = config

    @abstractmethod
    def render(self, painter: QPainter, scene: Scene) -> None:
        raise NotImplementedError

    @staticmethod
    def with_alpha(color: QColor, alpha: int) -> QColor:
        adjusted = QColor(color)
        adjusted.setAlpha(max(0, min(255, alpha)))
        return adjusted
