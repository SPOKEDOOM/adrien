from __future__ import annotations

from PySide6.QtCore import QElapsedTimer, QTimer
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from app.rendering import AnimationEngine, CoreRenderer, RendererConfig, Scene


class AICore(QWidget):
    def __init__(self):
        super().__init__()

        self.config = RendererConfig()
        self.scene = Scene(self.config)
        self.animation_engine = AnimationEngine(self.config)
        self.renderer = CoreRenderer(self.config)

        self.clock = QElapsedTimer()
        self.clock.start()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(16)

        self.setMinimumSize(480, 420)

    def animate(self):
        delta_seconds = self.clock.restart() / 1000.0
        self.animation_engine.tick(self.scene, delta_seconds)
        self.update()

    def paintEvent(self, event):
        self.scene.set_viewport(self.width(), self.height())

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        self.renderer.render(painter, self.scene)
