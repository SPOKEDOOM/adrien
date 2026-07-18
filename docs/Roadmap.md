# ADRIEN Roadmap

## Completed

- Sprint 1-3: modular desktop shell, Presence Engine, and state transitions.
- Sprint 4: cinematic materialization and Ambient Living Presence.
- Sprint 5 Phase 1: backend-neutral voice pipeline foundation with placeholder STT, conversation, and TTS.
- Sprint 5 Phase 2: optional microphone capture, energy endpointing, Faster-Whisper
  STT, Piper/Windows SAPI output, device controls, and safe workers.
- Sprint 5 Phase 3: Wake Engine lifecycle, confidence/cooldown protection, explicit
  audio ownership, acknowledgement, command timeout, debug fallback, and UI.

## Deferred

- Production trained "Adrien" wake-word model integration.
- AI backend, memory, plugins, automation, and OS control.

Production wake-model selection and continuous-conversation behavior remain deferred. Typed input remains
the deterministic fallback when optional local audio dependencies are unavailable.
