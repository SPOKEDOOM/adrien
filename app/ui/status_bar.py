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
        self.showMessage(f"STATE: {state.name}")

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
