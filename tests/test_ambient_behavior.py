import unittest

from app.core import PresenceState
from app.rendering.ambient_behavior import (
    AmbientBehaviorController, AmbientConfig, AmbientMode, STATE_AMBIENT_STRENGTH,
)
from app.rendering.animation import AnimationEngine
from app.rendering.scene import Scene


class AmbientBehaviorTests(unittest.TestCase):
    def test_same_seed_is_deterministic(self) -> None:
        first = AmbientBehaviorController(seed=17)
        second = AmbientBehaviorController(seed=17)
        for _ in range(120):
            first.update(0.1, PresenceState.READY)
            second.update(0.1, PresenceState.READY)
        self.assertEqual(first.mode, second.mode)
        self.assertEqual(first.mode_duration, second.mode_duration)
        self.assertEqual(first.values, second.values)

    def test_values_remain_within_configured_bounds(self) -> None:
        controller = AmbientBehaviorController(seed=8)
        config = controller.config
        for _ in range(1000):
            values = controller.update(0.1, PresenceState.READY)
            self.assertLessEqual(abs(values.glow_variation), config.glow_limit)
            self.assertLessEqual(abs(values.core_breathing), config.breathing_limit)
            self.assertLessEqual(abs(values.ring_drift), config.ring_drift_limit)
            self.assertLessEqual(abs(values.ring_wobble), config.ring_wobble_degrees)
            self.assertLessEqual(abs(values.particle_energy), config.particle_energy_limit)
            self.assertLessEqual(abs(values.particle_spread), config.particle_spread_limit)

    def test_mode_duration_uses_configured_range(self) -> None:
        controller = AmbientBehaviorController(seed=3)
        for mode in AmbientMode:
            controller._set_mode(mode)
            low, high = controller.config.mode_durations[tuple(AmbientMode).index(mode)]
            self.assertGreaterEqual(controller.mode_duration, low)
            self.assertLessEqual(controller.mode_duration, high)

    def test_automatic_selection_does_not_repeat_mode(self) -> None:
        controller = AmbientBehaviorController(seed=4)
        for _ in range(20):
            previous = controller.mode
            controller._choose_next_mode()
            self.assertIsNot(controller.mode, previous)

    def test_mode_transition_has_no_sudden_jump(self) -> None:
        controller = AmbientBehaviorController(seed=9)
        for _ in range(80):
            controller.update(0.1, PresenceState.READY)
        before = controller.values.glow_variation
        controller.cycle_mode()
        after = controller.update(0.01, PresenceState.READY).glow_variation
        self.assertLess(abs(after - before), 0.005)

    def test_disable_and_enable_are_smooth(self) -> None:
        controller = AmbientBehaviorController(seed=1)
        for _ in range(50):
            controller.update(0.1, PresenceState.READY)
        before = controller.strength
        self.assertFalse(controller.toggle())
        controller.update(0.1, PresenceState.READY)
        self.assertLess(controller.strength, before)
        self.assertTrue(controller.toggle())
        controller.update(0.1, PresenceState.READY)
        self.assertGreater(controller.strength, 0.0)

    def test_state_strength_is_centralized_and_reduced(self) -> None:
        self.assertGreater(STATE_AMBIENT_STRENGTH[PresenceState.READY], STATE_AMBIENT_STRENGTH[PresenceState.LISTENING])
        self.assertGreater(STATE_AMBIENT_STRENGTH[PresenceState.LISTENING], STATE_AMBIENT_STRENGTH[PresenceState.RESPONDING])
        self.assertEqual(STATE_AMBIENT_STRENGTH[PresenceState.BOOTING], 0.0)

    def test_materializing_has_no_ambient_interference(self) -> None:
        controller = AmbientBehaviorController(seed=2)
        for _ in range(50):
            controller.update(0.1, PresenceState.READY)
        values = controller.update(0.1, PresenceState.MATERIALIZING)
        self.assertEqual(controller.strength, 0.0)
        self.assertTrue(all(value == 0.0 for value in (
            values.glow_variation, values.core_breathing, values.ring_drift,
            values.particle_energy, values.particle_spread,
        )))

    def test_profile_composition_does_not_replace_blended_profile(self) -> None:
        scene = Scene()
        scene.set_state(PresenceState.READY)
        profile = scene.profile
        AnimationEngine(scene.config).tick(scene, 0.1)
        self.assertIs(scene.profile, profile)
        self.assertGreaterEqual(scene.core_radius, 0.0)

    def test_successive_values_change_continuously(self) -> None:
        controller = AmbientBehaviorController(AmbientConfig(), seed=11)
        previous = controller.update(0.1, PresenceState.READY).core_breathing
        for _ in range(500):
            current = controller.update(0.1, PresenceState.READY).core_breathing
            self.assertLess(abs(current - previous), 0.004)
            previous = current


if __name__ == "__main__":
    unittest.main()
