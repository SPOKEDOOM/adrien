import unittest

from app.core import PresenceState
from app.rendering.profiles import ANIMATION_PROFILES, profile_for
from app.rendering.scene import Scene
from app.rendering.animation import AnimationEngine


class AnimationProfileTests(unittest.TestCase):
    def test_every_presence_state_has_exactly_one_profile(self) -> None:
        self.assertEqual(set(ANIMATION_PROFILES), set(PresenceState))
        for state in PresenceState:
            self.assertIs(profile_for(state), ANIMATION_PROFILES[state])

    def test_entering_materializing_initializes_scene_lifecycle(self) -> None:
        scene = Scene()
        self.assertTrue(callable(scene.begin_materialization))

        scene.set_state(PresenceState.MATERIALIZING)

        self.assertIs(scene.presence_state, PresenceState.MATERIALIZING)
        self.assertEqual(scene.materialization_progress, 0.0)
        self.assertEqual(scene.visibility, 0.0)

    def test_animation_tick_uses_the_live_state_profile(self) -> None:
        scene = Scene()
        engine = AnimationEngine(scene.config)
        scene.set_state(PresenceState.READY)
        engine.tick(scene, 0.1)
        ready_ring_delta = scene.ring_angles[-1]

        scene.ring_angles[-1] = 0.0
        scene.set_state(PresenceState.LISTENING)
        engine.tick(scene, 0.1)
        listening_ring_delta = scene.ring_angles[-1]

        self.assertGreater(listening_ring_delta, ready_ring_delta)
        self.assertIs(scene.profile, ANIMATION_PROFILES[PresenceState.LISTENING])


if __name__ == "__main__":
    unittest.main()
