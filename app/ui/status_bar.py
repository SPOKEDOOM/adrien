from PySide6.QtWidgets import QLabel, QPushButton, QStatusBar


class AdrienStatusBar(QStatusBar):
    def __init__(self):
        super().__init__()

        self.showMessage("Booting")

        self.indicator = QLabel("●")
        self.indicator.setToolTip("ADRIEN status")
        self.gear_button = QPushButton("⚙")
        self.gear_button.setFlat(True)
        self.gear_button.setFixedSize(26, 22)

        self.cpu = QLabel("CPU: --%")
        self.ram = QLabel("RAM: --%")
        self.gpu = QLabel("GPU: --%")

        self.cpu.hide()
        self.ram.hide()
        self.gpu.hide()
        self.addPermanentWidget(self.indicator)
        self.addPermanentWidget(self.gear_button)
        self._set_indicator("#68717d")

    def _set_indicator(self, color: str) -> None:
        self.indicator.setStyleSheet(f"color: {color}; font-size: 16px;")

    def show_presence_state(self, state) -> None:
        names = {
            "BOOTING": "Booting", "MATERIALIZING": "Waking",
            "READY": "Ready", "SLEEP": "Sleeping", "LISTENING": "Listening...",
            "THINKING": "Thinking", "RESPONDING": "Speaking",
        }
        colors = {
            "BOOTING": "#68717d", "MATERIALIZING": "#70d7ff", "READY": "#66b7c9",
            "SLEEP": "#68717d", "LISTENING": "#9af5ff", "THINKING": "#65ccea",
            "RESPONDING": "#d0fbff",
        }
        self.indicator.setText("●")
        self.showMessage(names.get(state.name, state.name.title()))
        self._set_indicator(colors.get(state.name, "#68717d"))

    def show_error(self, message: str) -> None:
        self.showMessage(message)
        self.indicator.setText("⚠")
        self._set_indicator("#ffb45f")

    def show_visual_transition(self, operational_state, source, target, progress) -> None:
        percentage = round(progress * 100)
        self.showMessage(
            f"STATE: {operational_state.name}    "
            f"VISUAL: {source.name} -> {target.name} ({percentage}%)"
        )

    def show_materialization(self, progress, phase, active_particles=0, seed=None) -> None:
        seed_text = f"    SEED: {seed}" if seed is not None else ""
        self.showMessage(
            f"STATE: MATERIALIZING    MATERIALIZATION: {round(progress * 100)}%    "
            f"PHASE: {phase.name}    PARTICLES: {active_particles}{seed_text}"
        )

    def show_ambient(self, state, enabled, mode, seed) -> None:
        self.showMessage(
            f"STATE: {state.name}    AMBIENT: {'ON' if enabled else 'OFF'}    "
            f"MODE: {mode.name}    SEED: {seed}"
        )
