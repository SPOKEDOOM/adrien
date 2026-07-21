from PySide6.QtWidgets import QListWidget


class Sidebar(QListWidget):
    PAGE_NAMES = (
        "Home", "Presence", "Voice", "Brain", "Memory",
        "AI Providers", "Privacy", "Developer", "About",
    )

    def __init__(self):
        super().__init__(); self.setFixedWidth(220); self.addItems(self.PAGE_NAMES)
