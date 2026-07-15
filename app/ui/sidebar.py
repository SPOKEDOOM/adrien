from PySide6.QtWidgets import QListWidget


class Sidebar(QListWidget):
    def __init__(self):
        super().__init__()

        self.setFixedWidth(220)

        self.addItems(
            [
                "🏠 Home",
                "🧬 Presence",
                "🎤 Voice",
                "🧠 Brain",
                "💾 Memory",
                "💼 Business",
                "📁 Projects",
                "⚙ Settings",
            ]
        )