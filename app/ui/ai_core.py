from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class AICore(QWidget):
    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("ADRIEN Presence Engine")
        title.setAlignment(Qt.AlignCenter)

        state = QLabel("Status: BOOTING")
        state.setAlignment(Qt.AlignCenter)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(state)
        layout.addStretch()