# ADRIEN

ADRIEN is a modular PySide6 desktop assistant. Its voice pipeline supports typed
development input, optional local microphone transcription, and local speech output.
It includes a development Wake Engine, but no cloud service, LLM, or
continuous-conversation loop.

## Setup

Python 3.13 on Windows is the recommended voice-development environment. Use an
isolated environment:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The application launches without audio extras and retains typed fallback:

```powershell
python main.py
```

After confirming wheels exist for the active Python, enable microphone STT with:

```powershell
python -m pip install -r requirements-voice.txt
```

The first transcription may download `tiny.en`. Configure `stt_download_directory`
to control its cache. CPU/int8 is the default. For optional Piper output, install it,
download a voice, and set `VoiceConfig.tts_voice_model` to the local `.onnx` path:

```powershell
python -m pip install piper-tts
python -m piper.download_voices en_US-lessac-medium
```

Without a Piper model, Windows uses local System.Speech/SAPI through the system
default output device.

## Voice controls and troubleshooting

Wait for `READY`, choose a device, and click **Start Listening**. Speak, then remain
quiet for about one second. **Stop and Transcribe** finalizes audio; **Cancel**
discards it and safely returns to READY. **Test input**
remains usable when packages, permissions, devices, or models are unavailable.

If no devices appear, check Windows microphone privacy permissions and confirm that
sounddevice can enumerate PortAudio devices. Model and playback errors appear in the
panel and technical details are logged in the terminal.

Audio remains in memory and is discarded after transcription. Debug recordings are
disabled by default; ADRIEN does not retain microphone audio in Phase 2.

## Wake Engine development workflow

The Phase 3 default is the dependency-free development backend. Open the Wake Engine
debug panel, click **Force Sleep**, then use **Simulate Wake** or confidence injection.
Accepted candidates run `SLEEP -> MATERIALIZING -> READY` and begin normal command
listening. Spoken acknowledgement remains available but is disabled by default. With
no command ADRIEN sleeps after eight seconds. After a
response it remains READY for one second, then sleeps and resumes monitoring.

The fallback opens no microphone stream. A trained production model can later replace
`WakeBackend` while preserving `WakeManager` and the single-owner `AudioMode` handoff.

Developer Tools is hidden by default. Open it with the small gear button or `F12`.
`Ctrl+Space` simulates wake while ADRIEN is sleeping.
