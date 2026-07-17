# ADRIEN Changelog

## Sprint 3 Phase 2

- Added `StateTransitionController` with delta-time profile interpolation.
- Added smoothstep, ease-in-out cubic, and ease-out cubic transition easing.
- Added centralized transition durations and a fallback for development transitions.
- Preserved visual continuity when state changes interrupt an active blend.
- Added transition lifecycle signals and concise start/completion logging.
- Added development status-bar progress for operational and visual states.
- Added profile-driven state-entry micro-animations without renderer state checks.
- Added transition duration, interruption, boundary, range, and coverage tests.

## Sprint 3 Phase 1

- Added the centralized seven-state `PresenceState` model.
- Added validated transitions, previous-state tracking, duplicate rejection, reset, and Qt state-change notifications.
- Connected operational state to `Scene`, `AnimationEngine`, and immutable visual profiles.
- Added distinct subtle particle, glow, core, ring, pulse, and highlight behavior for every state.
- Added non-blocking `BOOTING -> MATERIALIZING -> READY` startup timing.
- Added temporary 1-7 keyboard state controls and a status-bar state display.
- Added lightweight state-manager and profile-coverage tests.

## v0.0.1

- Project created
- GitHub repository created
- First desktop window

## v0.0.2

- Modular architecture
- Sidebar
- Status bar
- Presence Engine placeholder
