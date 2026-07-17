import unittest

from app.core import PresenceState, PresenceStateManager


class PresenceStateManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manager = PresenceStateManager()

    def test_initial_state(self) -> None:
        self.assertIs(self.manager.current_state, PresenceState.BOOTING)
        self.assertIsNone(self.manager.previous_state)

    def test_valid_transition_updates_current_and_previous_state(self) -> None:
        self.assertTrue(self.manager.transition_to(PresenceState.MATERIALIZING))
        self.assertIs(self.manager.current_state, PresenceState.MATERIALIZING)
        self.assertIs(self.manager.previous_state, PresenceState.BOOTING)

    def test_invalid_transition_is_rejected(self) -> None:
        self.assertFalse(self.manager.transition_to(PresenceState.THINKING))
        self.assertIs(self.manager.current_state, PresenceState.BOOTING)

    def test_duplicate_state_is_rejected(self) -> None:
        self.assertFalse(self.manager.transition_to(PresenceState.BOOTING))
        self.assertIsNone(self.manager.previous_state)

    def test_notification_contains_previous_and_current_state(self) -> None:
        notifications = []
        self.manager.state_changed.connect(
            lambda previous, current: notifications.append((previous, current))
        )
        self.manager.transition_to(PresenceState.MATERIALIZING)
        self.assertEqual(
            notifications,
            [(PresenceState.BOOTING, PresenceState.MATERIALIZING)],
        )

    def test_controlled_reset(self) -> None:
        self.manager.transition_to(PresenceState.MATERIALIZING)
        self.assertTrue(self.manager.reset())
        self.assertIs(self.manager.current_state, PresenceState.BOOTING)

    def test_development_transition_can_select_any_state(self) -> None:
        self.assertTrue(
            self.manager.transition_to_for_development(PresenceState.RESPONDING)
        )
        self.assertIs(self.manager.current_state, PresenceState.RESPONDING)
        self.assertIs(self.manager.previous_state, PresenceState.BOOTING)


if __name__ == "__main__":
    unittest.main()
