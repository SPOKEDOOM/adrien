from PySide6.QtWidgets import QLabel, QStatusBar


class AdrienStatusBar(QStatusBar):
    def __init__(self):
        super().__init__()

        self.showMessage("ADRIEN is booting...")

        self.cpu = QLabel("CPU: --%")
        self.ram = QLabel("RAM: --%")
        self.gpu = QLabel("GPU: --%")

        self.addPermanentWidget(self.cpu)
        self.addPermanentWidget(self.ram)
        self.addPermanentWidget(self.gpu)

    def show_presence_state(self, state) -> None:
        self.showMessage(f"Presence state: {state.name}")
