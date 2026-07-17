import unittest
import random

from app.core import PresenceState, PresenceStateManager
from app.rendering.materialization_controller import (
    PHASE_DURATIONS,
    TOTAL_MATERIALIZATION_DURATION,
    MaterializationController,
    MaterializationPhase,
)
from app.rendering.scene import Scene
from app.rendering.particle import Particle
from app.rendering.config import RendererConfig
from app.rendering.animation import AnimationEngine


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

    def test_trajectory_generation_is_deterministic(self) -> None:
        config = RendererConfig()
        particles = [Particle.create(config, random.Random(7), True) for _ in range(2)]
        for particle in particles:
            particle.configure_materialization(random.Random(42))
        self.assertEqual(particles[0].curved_position(0.55), particles[1].curved_position(0.55))
        self.assertEqual(particles[0].materialization_delay, particles[1].materialization_delay)

    def test_staggered_timing_is_bounded(self) -> None:
        config = RendererConfig()
        particles = [Particle.create(config, random.Random(i), True) for i in range(30)]
        rng = random.Random(42)
        for particle in particles:
            particle.configure_materialization(rng)
        self.assertGreater(len({round(p.materialization_delay, 3) for p in particles}), 3)
        self.assertTrue(all(0.06 <= p.materialization_delay <= 0.45 for p in particles))
        self.assertTrue(all(0.62 <= p.materialization_duration <= 1.08 for p in particles))

    def test_curved_path_changes_angle_and_clamps_progress(self) -> None:
        particle = Particle.create(RendererConfig(), random.Random(3), True)
        particle.configure_materialization(random.Random(9))
        start = particle.curved_position(-1.0)
        middle = particle.curved_position(0.6)
        end = particle.curved_position(99.0)
        self.assertEqual(start[0], particle.materialization_start_radius)
        self.assertNotEqual(middle[1], start[1])
        self.assertAlmostEqual(end[0], particle.target_radius * 0.53)

    def test_depth_layers_are_assigned(self) -> None:
        config = RendererConfig()
        rng = random.Random(42)
        layers = set()
        for index in range(80):
            particle = Particle.create(config, random.Random(index), True)
            particle.configure_materialization(rng)
            layers.add(particle.depth_layer)
        self.assertEqual(layers, {0, 1, 2})

    def test_trail_history_is_limited_to_two_positions(self) -> None:
        particle = Particle.create(RendererConfig(), random.Random(2))
        for radius in range(5):
            particle.orbit_radius = float(radius)
            particle.remember_trail()
        self.assertEqual((particle.trail_radius_2, particle.trail_radius_1), (3.0, 4.0))

    def test_replay_resets_controller_and_wave(self) -> None:
        scene = Scene(materialization_seed=42)
        scene.set_state(PresenceState.MATERIALIZING)
        scene.materialization_controller.update(1.0)
        scene.energy_wave_triggered = True
        scene.begin_materialization()
        self.assertEqual(scene.materialization_controller.progress, 0.0)
        self.assertFalse(scene.energy_wave_triggered)
        self.assertEqual(scene.active_materialization_seed, 42)

    def test_energy_wave_triggers_once_and_stabilization_completes(self) -> None:
        scene = Scene()
        scene.set_state(PresenceState.MATERIALIZING)
        engine = AnimationEngine(scene.config)
        controller = scene.materialization_controller
        controller.update(sum(list(PHASE_DURATIONS.values())[:3]) + 0.2)
        engine._animate_lifecycle(scene, 0.0)
        self.assertTrue(scene.energy_wave_triggered)
        first = scene.energy_wave_progress
        engine._animate_lifecycle(scene, 0.0)
        self.assertEqual(scene.energy_wave_progress, first)
        controller.update(10.0)
        self.assertTrue(controller.is_complete)

    def test_completion_signal_is_not_duplicated(self) -> None:
        controller = MaterializationController()
        completions = []
        controller.completed.connect(lambda: completions.append(True))
        controller.start()
        controller.update(99.0)
        controller.update(99.0)
        self.assertEqual(completions, [True])

    def test_replay_manager_accepts_only_safe_states(self) -> None:
        manager = PresenceStateManager(PresenceState.READY)
        self.assertTrue(manager.replay_materialization_for_development())
        self.assertFalse(manager.replay_materialization_for_development())


if __name__ == "__main__":
    unittest.main()
