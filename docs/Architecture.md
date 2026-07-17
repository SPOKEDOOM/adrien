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

Temporary development controls map keys 1-7 to the seven states. Key 1 invokes the controlled reset; all other keys use normal validated transitions. The status bar display and controls can be disabled with `MainWindow.DEVELOPMENT_STATE_CONTROLS`.
