import unittest

from app.core import PresenceState
from app.rendering.profiles import ANIMATION_PROFILES, profile_for
from app.rendering.state_transition import (
    Easing,
    PROFILE_FIELDS,
    TRANSITION_DURATIONS,
    StateTransitionController,
    eased_progress,
)


class StateTransitionControllerTests(unittest.TestCase):
    def test_transition_starts_from_current_profile(self) -> None:
        controller = StateTransitionController(PresenceState.READY)
        ready_glow = controller.current_profile.glow_intensity
        controller.transition_to(PresenceState.LISTENING)
        self.assertEqual(controller.current_profile.glow_intensity, ready_glow)
        self.assertEqual(controller.progress, 0.0)
        self.assertTrue(controller.is_active)

    def test_transition_reaches_target_profile(self) -> None:
        controller = StateTransitionController(PresenceState.READY)
        controller.transition_to(PresenceState.LISTENING)
        controller.update(controller.duration)
        target = profile_for(PresenceState.LISTENING)
        for name in PROFILE_FIELDS:
            self.assertAlmostEqual(
                getattr(controller.current_profile, name), getattr(target, name)
            )
        self.assertFalse(controller.is_active)

    def test_required_duration_mapping(self) -> None:
        expected = {
            (PresenceState.BOOTING, PresenceState.MATERIALIZING): 1.2,
            (PresenceState.MATERIALIZING, PresenceState.READY): 1.5,
            (PresenceState.READY, PresenceState.LISTENING): 0.35,
            (PresenceState.LISTENING, PresenceState.THINKING): 0.6,
            (PresenceState.THINKING, PresenceState.RESPONDING): 0.45,
            (PresenceState.RESPONDING, PresenceState.READY): 0.8,
            (PresenceState.READY, PresenceState.SLEEP): 1.8,
            (PresenceState.SLEEP, PresenceState.MATERIALIZING): 1.4,
        }
        self.assertEqual(TRANSITION_DURATIONS, expected)

    def test_interruption_uses_current_blend_as_new_source(self) -> None:
        controller = StateTransitionController(PresenceState.READY)
        controller.transition_to(PresenceState.LISTENING)
        controller.update(controller.duration / 2.0)
        interrupted_glow = controller.current_profile.glow_intensity

        controller.transition_to(PresenceState.SLEEP)

        self.assertEqual(controller.current_profile.glow_intensity, interrupted_glow)
        controller.update(0.01)
        self.assertLess(controller.current_profile.glow_intensity, interrupted_glow)

    def test_duplicate_target_request_is_ignored(self) -> None:
        controller = StateTransitionController(PresenceState.READY)
        self.assertTrue(controller.transition_to(PresenceState.LISTENING))
        controller.update(0.1)
        progress = controller.progress
        self.assertFalse(controller.transition_to(PresenceState.LISTENING))
        self.assertEqual(controller.progress, progress)

    def test_easing_boundaries(self) -> None:
        for easing in Easing:
            self.assertEqual(eased_progress(-1.0, easing), 0.0)
            self.assertEqual(eased_progress(0.0, easing), 0.0)
            self.assertEqual(eased_progress(1.0, easing), 1.0)
            self.assertEqual(eased_progress(2.0, easing), 1.0)

    def test_blended_values_stay_between_source_and_target(self) -> None:
        controller = StateTransitionController(PresenceState.READY)
        source = profile_for(PresenceState.READY)
        target = profile_for(PresenceState.RESPONDING)
        controller.transition_to(PresenceState.RESPONDING)
        controller.update(controller.duration / 2.0)
        for name in PROFILE_FIELDS:
            value = getattr(controller.current_profile, name)
            lower = min(getattr(source, name), getattr(target, name))
            upper = max(getattr(source, name), getattr(target, name))
            self.assertGreaterEqual(value, lower)
            self.assertLessEqual(value, upper)

    def test_all_presence_states_have_supported_profiles(self) -> None:
        self.assertEqual(set(ANIMATION_PROFILES), set(PresenceState))


if __name__ == "__main__":
    unittest.main()
