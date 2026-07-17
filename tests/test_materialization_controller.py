import unittest

from app.core import PresenceState, PresenceStateManager
from app.rendering.materialization_controller import (
    PHASE_DURATIONS,
    TOTAL_MATERIALIZATION_DURATION,
    MaterializationController,
    MaterializationPhase,
)
from app.rendering.scene import Scene


class MaterializationControllerTests(unittest.TestCase):
    def test_initial_progress(self) -> None:
        controller = MaterializationController()
        self.assertEqual(controller.progress, 0.0)
        self.assertFalse(controller.is_active)
        self.assertFalse(controller.is_complete)

    def test_start_resets_and_activates_sequence(self) -> None:
        controller = MaterializationController()
        controller.start()
        self.assertTrue(controller.is_active)
        self.assertIs(controller.phase, MaterializationPhase.FADE_IN)
        self.assertEqual(controller.progress, 0.0)

    def test_update_is_delta_time_based(self) -> None:
        controller = MaterializationController()
        controller.start()
        controller.update(TOTAL_MATERIALIZATION_DURATION / 2.0)
        self.assertAlmostEqual(controller.progress, 0.5)

    def test_phase_boundaries(self) -> None:
        controller = MaterializationController()
        controller.start()
        controller.update(PHASE_DURATIONS[MaterializationPhase.FADE_IN])
        self.assertIs(controller.phase, MaterializationPhase.CONVERGENCE)
        controller.update(PHASE_DURATIONS[MaterializationPhase.CONVERGENCE])
        self.assertIs(controller.phase, MaterializationPhase.CORE_FORMATION)
        controller.update(PHASE_DURATIONS[MaterializationPhase.CORE_FORMATION])
        self.assertIs(controller.phase, MaterializationPhase.STABILIZATION)

    def test_completion(self) -> None:
        controller = MaterializationController()
        completions = []
        controller.completed.connect(lambda: completions.append(True))
        controller.start()
        controller.update(TOTAL_MATERIALIZATION_DURATION)
        self.assertEqual(controller.progress, 1.0)
        self.assertTrue(controller.is_complete)
        self.assertFalse(controller.is_active)
        self.assertEqual(completions, [True])

    def test_cancellation(self) -> None:
        controller = MaterializationController()
        controller.start()
        controller.update(0.4)
        progress = controller.progress
        self.assertTrue(controller.cancel())
        controller.update(1.0)
        self.assertEqual(controller.progress, progress)
        self.assertFalse(controller.is_complete)

    def test_scene_interruption_cancels_without_resetting_visual_values(self) -> None:
        scene = Scene()
        scene.set_state(PresenceState.MATERIALIZING)
        scene.materialization_controller.update(0.5)
        scene.visibility = 0.42
        scene.set_state(PresenceState.READY)
        self.assertFalse(scene.materialization_controller.is_active)
        self.assertEqual(scene.visibility, 0.42)

    def test_ready_is_requested_only_on_completion(self) -> None:
        manager = PresenceStateManager()
        manager.transition_to(PresenceState.MATERIALIZING)
        controller = MaterializationController()
        controller.completed.connect(
            lambda: manager.transition_to(PresenceState.READY)
        )
        controller.start()
        controller.update(TOTAL_MATERIALIZATION_DURATION - 0.01)
        self.assertIs(manager.current_state, PresenceState.MATERIALIZING)
        controller.update(0.01)
        self.assertIs(manager.current_state, PresenceState.READY)

    def test_progress_is_clamped(self) -> None:
        controller = MaterializationController()
        controller.start()
        controller.update(-10.0)
        self.assertEqual(controller.progress, 0.0)
        controller.update(TOTAL_MATERIALIZATION_DURATION * 2.0)
        self.assertEqual(controller.progress, 1.0)


if __name__ == "__main__":
    unittest.main()
