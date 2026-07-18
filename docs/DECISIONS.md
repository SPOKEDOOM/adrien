# ADRIEN Engineering Decisions

## Sprint 5 Phase 3 Wake Engine

### Development backend selected by default

openWakeWord is the preferred future production candidate because it is offline,
Windows-capable through ONNX Runtime, CPU-efficient, Apache-2.0 code, and supports
custom training. It does not ship an "Adrien" model, bundled model licensing is
CC BY-NC-SA, and model training/validation is separate work. Porcupine requires an
external AccessKey and provisioned custom model. Neither is a safe zero-config default,
so Phase 3 ships a working development backend behind the same interface.

The configured default is explicitly `development`, not automatic backend selection.
The fallback uses no continuous microphone stream and is triggered from Developer
Tools or `Ctrl+Space` while sleeping.

### Microphone ownership is explicit

`AudioMode` permits one conceptual consumer at a time. Monitoring releases ownership
before command capture, and capture stops before TTS. This prevents two PortAudio
streams competing for one Windows device and makes overlap visible in logs and tests.

### Wake detection is limited to SLEEP

State gating prevents acknowledgement and replies from retriggering wake, avoids
overlapping command listeners, and gives SLEEP a clear low-energy meaning. READY
monitoring is configurable but disabled.

### Confidence and fallback

The default threshold is 0.75, deliberately stricter than openWakeWord's general 0.5
example until an Adrien-specific model is measured. A two-second cooldown and
in-progress guard suppress duplicate frames. The fallback keeps UI, lifecycle, audio
ownership, and state integration usable when a model, dependency, license, or
credential is absent.

### Developer controls are hidden

Permanent voice and wake diagnostic groups reduced the core visual and overwhelmed
the normal interface. They now live in one scrollable right-side Developer Tools dock,
closed by default and capped at 380 pixels. The production surface retains only the
core, presence state, subtle indicator, and short status text.

Spoken acknowledgement remains supported but defaults off until production wake/audio
handoff is validated. This removes an avoidable TTS transition before command capture.
