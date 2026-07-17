# ADRIEN Architecture

## Sprint 3 Phase 1 Presence Engine

ADRIEN's Sprint 2 Presence Engine is a modular rendering pipeline for the desktop assistant's animated visual core. The architecture keeps scene state, animation, and rendering separate so Sprint 3 can add state-driven behavior without rewriting the visual layer.

## Rendering Flow

```text
Scene
    ↓
AnimationEngine
    ↓
CoreRenderer
        ↓
BackgroundRenderer
        ↓
ParticleRenderer
        ↓
GlowRenderer
        ↓
EnergyCoreRenderer
        ↓
RingRenderer
        ↓
HighlightRenderer
        ↓
PostEffectRenderer
```

## Scene

`Scene` is the mutable world model consumed by the animation and rendering layers. It owns viewport size, elapsed time, lifecycle visibility, core dimensions, glow intensity, ring state, and particle state.

`Scene` does not draw. It exposes only the state needed by renderers and provides lifecycle helpers for materialization, dissolve, state changes, and particle spawning.

## AnimationEngine

`AnimationEngine` advances `Scene` over time. It is responsible for:

- Lifecycle transitions such as materialization and dissolve.
- Core breathing, pulse, deformation, and energy angle.
- Ring rotation, opacity, and assembly timing.
- Particle motion, organic drift, fading, retirement, and population control.

`AnimationEngine` does not perform rendering and does not know about individual renderer implementations.

## CoreRenderer

`CoreRenderer` coordinates render passes only. It owns the renderer instances and calls them in the correct order, preserving the visual stack without duplicating rendering logic.

The renderer order is intentional:

1. Background field.
2. Particles.
3. Ambient glow.
4. Energy core.
5. Inner rings.
6. Outer rings.
7. Highlights.
8. Post effects.

## Renderer Responsibilities

### BackgroundRenderer

Draws the static deep-field base and broad energy field behind the Presence core. It caches reusable viewport-dependent gradient data where possible.

### ParticleRenderer

Draws ambient orbital particles. Particles vary subtly in depth, opacity, size, drift, and organic wobble while preserving the existing visual style.

### GlowRenderer

Draws layered bloom and halo energy around the core. It uses smoother falloff, subtle breathing intensity, and blended cyan/blue tones without oversaturating the scene.

### EnergyCoreRenderer

Draws the breathing, deforming central energy shape. It owns the core gradient and core path construction, with reusable unit-angle data to reduce per-frame work.

### RingRenderer

Draws inner and outer energy rings. Each ring can rotate at a different speed and direction, with phase offsets and subtle drift so the motion feels layered rather than synchronized.

### HighlightRenderer

Draws core sparks and radial streak accents that add local energy and motion detail.

### PostEffectRenderer

Draws final screen-space effects such as the soft vignette, keeping post-processing separate from the core visual passes.

## Boundaries

Voice, AI, memory, plugins, wake word behavior, and the cinematic Sprint 4 materialization sequence remain intentionally out of scope.

## Operational State Flow

`PresenceState` defines the supported operational states: `BOOTING`, `MATERIALIZING`, `READY`, `LISTENING`, `THINKING`, `RESPONDING`, and `SLEEP`.

`PresenceStateManager` is the sole owner of operational state. It validates requests against an explicit transition map, retains the previous state, rejects invalid or duplicate requests without raising, and emits `state_changed(previous, current)` after successful transitions. A dedicated `reset()` method provides the controlled path back to `BOOTING`.

```text
PresenceStateManager
        -> Scene
        -> AnimationEngine
        -> CoreRenderer
        -> Dedicated renderers
```

Normal transitions are:

```text
BOOTING -> MATERIALIZING -> READY
READY -> LISTENING | SLEEP
LISTENING -> THINKING | READY
THINKING -> RESPONDING | READY
RESPONDING -> READY | LISTENING
SLEEP -> MATERIALIZING
```

Startup uses non-blocking single-shot Qt timers to request `BOOTING -> MATERIALIZING -> READY`.

## State Visual Profiles

Each `PresenceState` has one immutable `AnimationProfile`. Profiles centralize particle density, speed, opacity and attraction; glow and pulse tuning; ring speed and intensity; core energy; deformation; breathing; and highlight activity.

`Scene.profile` exposes the active profile. `AnimationEngine` converts its values into mutable frame data on `Scene`; renderers consume scene/profile values and only draw. Neither `Scene`, `AnimationEngine`, nor a renderer validates operational transitions.

Temporary development controls map keys 1-7 directly to the seven visual test states through the manager's explicit development-only transition method. Production requests continue to use the validated transition map. The status display and controls can be disabled with `MainWindow.DEVELOPMENT_STATE_CONTROLS`.

## Sprint 3 Phase 2: Visual State Transitions

`StateTransitionController` owns visual blending while `PresenceStateManager` continues to own only operational state. `Scene.profile` exposes a cached mutable blended profile rather than switching directly between state-profile presets.

```text
PresenceStateManager
        -> Scene
        -> StateTransitionController
        -> blended AnimationProfile
        -> AnimationEngine
        -> CoreRenderer
        -> dedicated renderers
```

The controller snapshots the current blended values whenever a transition starts. If another state arrives before completion, those in-flight values become the new source, preventing rollback or visual jumps. Numeric fields are blended once per animation tick with delta-time progress and transition-specific easing. Renderers remain state-agnostic and consume only scene/profile values.

Configured durations are:

| Transition | Duration |
| --- | ---: |
| BOOTING -> MATERIALIZING | 1.2 s |
| MATERIALIZING -> READY | 1.5 s |
| READY -> LISTENING | 0.35 s |
| LISTENING -> THINKING | 0.6 s |
| THINKING -> RESPONDING | 0.45 s |
| RESPONDING -> READY | 0.8 s |
| READY -> SLEEP | 1.8 s |
| SLEEP -> MATERIALIZING | 1.4 s |

Unlisted development transitions use a centralized 0.7-second fallback. Smoothstep is the calm default, ease-out cubic is used for responsive/energetic entry, and ease-in-out cubic is used for focused or awakening transitions.

Profile-driven entry accent values provide a soft core expansion for LISTENING, brief ring acceleration for THINKING, an outward pulse for RESPONDING, and stabilization for READY. No renderer checks operational states.

When `MainWindow.DEVELOPMENT_STATE_CONTROLS` is enabled, the status bar shows operational state, visual source and target, and percentage progress. Keys 1-7 remain window-scoped visual test controls. Disable that flag to remove both the shortcuts and transition display.

## Sprint 4 Phase 1: Materialization Prototype

`MaterializationController` is a frame-rate-independent lifecycle controller for the lightweight assembly sequence. It owns progress, phase, phase-local progress, activation, cancellation, and completion. It contains no renderer-specific code.

The 3.2-second sequence is divided into:

| Phase | Duration | Visual responsibility |
| --- | ---: | --- |
| FADE_IN | 0.45 s | Reveal faint scattered particles while the core remains dark. |
| CONVERGENCE | 1.15 s | Pull particles inward at varied rates and begin the glow. |
| CORE_FORMATION | 0.9 s | Form the core and reveal staggered partial ring arcs. |
| STABILIZATION | 0.7 s | Settle particles into normal orbits and complete the rings. |

Entering `MATERIALIZING` starts the controller. Existing particles are reused and scattered outward once; newly required particles use the existing materialization spawn path. `AnimationEngine` reads controller progress once per frame and converts it into core opacity and scale, glow intensity and radius, particle target radius, and staggered ring reveal values. Ring rendering remains state-agnostic and only draws the reveal value exposed by `Scene`.

The controller's `completed` signal is handled by `AICore`, which requests `READY` through `PresenceStateManager`. There is no fixed READY timer. Leaving `MATERIALIZING` early cancels the controller without resetting current visibility, core, glow, particle, or blended-profile values.

Development key 2 restarts materialization when selected from another state. While active, the status bar displays total percentage and current phase. The prototype retains the existing bounded particle population and performs no per-frame collection rebuild, per-pixel processing, or blocking work.

## Sprint 4 Phase 2: Cinematic Materialization Polish

Phase 2 retains the four-phase, 3.2-second controller and the existing renderer stack. At the start of each run, every particle receives cached trajectory and timing data. Convergence uses a quadratic interpolation in polar space: start radius/angle, a randomized control radius with a stable angular spiral offset, and the particle's compact formation radius. Control values are never regenerated per frame.

Particles arrive in three controlled waves. Per-particle delay, duration, and depth-aware easing vary within bounded ranges. Background, mid-field, and foreground layers tune depth, apparent size, opacity, convergence pace, and spiral amount without blur or extra particles. During convergence each particle retains only its two previous polar positions; the renderer draws these as short, quickly fading trail fragments and clears them during stabilization.

Core formation begins compressed and faint, grows progressively, and receives a small sinusoidal intensity accent in the final third before normalizing. Rings preserve their established style and rotation directions while using per-ring delays, partial arc growth, opacity approach, and a small reveal overshoot. Early in `STABILIZATION`, a single thin energy wave expands from the core and fades quadratically. Particle attraction and trail strength reduce as normal orbital values are restored, while ring reveal, core brightness, and glow settle into values inherited by `READY`.

When development controls are enabled, `M` requests a replay only from `READY` or `SLEEP` through `PresenceStateManager`; numeric key `2` remains unchanged. `MainWindow.MATERIALIZATION_DEBUG_SEED` defaults to `42` for repeatable development paths. Set the scene seed to `None` for a randomly selected production run seed. The status bar reports phase, percentage, active particle count, and the active seed.

Performance remains bounded by the existing particle count. Path, layer, delay, duration, and easing variation are cached once per sequence; trails use exactly two scalar position pairs; colors remain cached; no real blur, position-history collection, extra timer, blocking loop, or per-frame randomness is introduced.

## Sprint 4 Phase 3: Ambient Living Presence

`AmbientBehaviorController` is a non-rendering, delta-time controller owned by `Scene`. It exposes one reusable `AmbientValues` instance containing bounded modulation for core breathing, glow, ring drift/wobble, particle energy/spread, highlights, and pulse phase. Seeded randomness is used only when selecting modes, durations, phases, or a new development seed; frame updates use layered low-frequency oscillation and allocate no profiles.

Ambient modes are visual micro-behaviors rather than operational states:

| Mode | Duration | Character |
| --- | ---: | --- |
| `CALM` | 8-16 s | Balanced, minimal variation. |
| `BREATHING` | 6-12 s | Slightly fuller core and glow breathing. |
| `ENERGY_DRIFT` | 7-14 s | Gentle particle energy and spread movement. |
| `RING_RESONANCE` | 5-10 s | Emphasizes microscopic independent ring motion. |
| `DEEP_IDLE` | 10-20 s | Slowest and quietest variation. |

Selection excludes the current mode and uses seeded weighted randomness. Mode amplitudes crossfade over 2.4 seconds. Different low frequencies and cached per-ring phases prevent an obvious short loop.

Composition order is:

```text
Base state profile
    -> StateTransitionController blended profile
    -> materialization lifecycle values
    -> AmbientBehaviorController bounded modulation
    -> AnimationEngine mutable scene values
    -> state-agnostic renderers
```

State compatibility is centralized in `STATE_AMBIENT_STRENGTH`: READY `1.0`, SLEEP `0.42`, LISTENING `0.35`, THINKING `0.22`, RESPONDING `0.10`, and BOOTING/MATERIALIZING `0.0`. This keeps operational-state checks out of renderers. Zero-strength lifecycle states are applied immediately; other strength changes ease smoothly.

Development controls are available only when `MainWindow.DEVELOPMENT_STATE_CONTROLS` is enabled: `A` toggles ambient behavior, `B` cycles modes, and `N` selects a new reproducible seed. The status bar shows enabled state, current mode, and seed. Existing numeric controls and materialization replay remain unchanged.

## Sprint 5 Phase 1: Voice Pipeline Foundation

The voice layer is intentionally backend-neutral and has no renderer or UI responsibilities:

```text
Microphone -> SpeechRecognizer -> VoiceManager placeholder conversation
           -> SpeechSynthesizer -> Audio output
```

`VoiceManager` coordinates recognition, placeholder reply generation, synthesis, cancellation, errors, and operational-state requests. `SpeechRecognizer` and `SpeechSynthesizer` are abstract Qt-signal contracts, with local placeholder implementations used by default. Future Whisper, Vosk, cloud STT, Piper, or other TTS backends can replace only the relevant implementation.

The placeholder recognizer intentionally uses `submit_text()` rather than accessing a microphone. This keeps the foundation deterministic, platform-neutral, and testable while real audio capture is deferred. The placeholder conversation replies to `Hello`, `Time`, and `Date`; all other input gets a fixed next-stage reply. `AudioController` owns device names, clamped volume, mute, and future device-selection settings without opening platform audio devices.

Voice stages request `LISTENING`, `THINKING`, `RESPONDING`, then `READY`; cancellation and errors return to `READY`. The development Voice Pipeline panel shows listening, recognized text, reply, speech state, microphone, and speaker. With development controls enabled, press `V` to listen and submit placeholder text in the panel.
