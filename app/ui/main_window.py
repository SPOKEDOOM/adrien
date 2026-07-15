from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QWidget

from app.ui.ai_core import AICore
from app.ui.sidebar import Sidebar
from app.ui.status_bar import AdrienStatusBar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ADRIEN")
        self.resize(1400, 850)

        container = QWidget()

        layout = QHBoxLayout(container)

        self.sidebar = Sidebar()
        self.core = AICore()

        layout.addWidget(self.sidebar)
        layout.addWidget(self.core, 1)

        self.setCentralWidget(container)

        self.setStatusBar(AdrienStatusBar())