# ADRIEN Changelog

## Sprint 5 Phase 3

- Refactored all technical controls into one hidden, scrollable Developer Tools dock.
- Restored a clean central layout and added a subtle state indicator with short text.
- Made the development fallback explicit, disabled acknowledgement by default, and
  kept simulated sleep audio IDLE until command capture begins.
- Added modular wake backend, detector, manager, configuration, and audio ring buffer.
- Added confidence thresholding, phrase normalization, cooldown, duplicate suppression,
  state gating, acknowledgement, command timeout, and return-to-sleep behavior.
- Added explicit audio ownership modes and a dependency-free development fallback.
- Added Wake Engine debug controls, diagnostics, lifecycle tests, and safe shutdown.

## Sprint 5 Phase 2

- Fixed real microphone completion diagnostics, practical RMS thresholding, silence
  endpoint tracking, recording validation, and explicit Stop-and-Transcribe behavior.
- Split Stop and Cancel controls and exposed live RMS, threshold, speech detection,
  duration, model state, transcription state, and last error in the debug panel.
- Added optional sounddevice microphone capture with bounded energy endpointing,
  cancellation, input levels, and safe device release.
- Added reusable lazy Faster-Whisper STT and background transcription.
- Added background Piper synthesis/playback and local Windows SAPI fallback.
- Expanded voice configuration, device selectors, controls, diagnostics, and errors.
- Preserved typed fallback and added worker shutdown on window close.
- Added mocked tests for devices, endpointing, STT/TTS, state recovery, and shutdown.

## Sprint 5 Phase 1

- Added modular `app.voice` infrastructure: `VoiceManager`, abstract recognizer/synthesizer contracts, placeholder backends, audio preferences, and centralized voice configuration.
- Added placeholder conversation responses for Hello, Time, Date, and a default next-stage reply.
- Connected voice lifecycle to LISTENING, THINKING, RESPONDING, and READY without renderer coupling.
- Added a development Voice Pipeline panel and `V` listening shortcut using safe text injection for the local placeholder recognizer.
- Added voice lifecycle, contract, conversation, cancellation, disabled-mode, error, and state-transition tests.

## Sprint 4 Phase 3

- Added a deterministic, delta-time `AmbientBehaviorController` with five smoothly sequenced micro-behavior modes.
- Added layered irregular core breathing, bounded glow variation, independent ring drift/wobble, and restrained particle energy/spread.
- Added centralized per-state ambient strength with ambient disabled during BOOTING and MATERIALIZING.
- Composed ambient modulation after blended profiles and materialization without per-frame profile allocation.
- Added development controls: `A` toggle, `B` cycle mode, and `N` generate a new seed, with status diagnostics.
- Added ADRIEN's visual product principles to `docs/Vision.md` and documented the ambient architecture.
- Added deterministic, bounds, duration, repetition, transition, state compatibility, composition, and continuity tests.

## Sprint 4 Phase 2

- Added deterministic cached quadratic curved trajectories with spiral angle offsets and three staggered arrival waves.
- Added background, mid-field, and foreground particle depth layers plus bounded two-position convergence trails.
- Polished compressed core formation, late formation pulse, independent ring reveal overshoot, and smooth READY settling.
- Added one subtle outward stabilization wave near the end of materialization.
- Added safe development replay on `M`, deterministic seed diagnostics, and active-particle status output.
- Added trajectory, timing, depth, trail, replay, wave, stabilization, completion, and clamping tests.

## Sprint 4 Phase 1

- Added the frame-driven `MaterializationController` and four configurable phases.
- Added lightweight particle scattering, varied curved convergence, and orbital settling.
- Added progressive core/glow formation and staggered partial ring reveal.
- Replaced the fixed startup READY timer with controller completion through `PresenceStateManager`.
- Added clean materialization cancellation that preserves current visual values.
- Added status-bar materialization percentage and phase diagnostics.
- Added lifecycle, boundary, cancellation, interruption, clamping, and READY-contract tests.

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
