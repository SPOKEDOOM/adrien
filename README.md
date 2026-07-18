# ADRIEN

ADRIEN is a modular PySide6 desktop assistant. Its voice pipeline supports typed
development input, optional local microphone transcription, and local speech output.
It has no wake word, cloud service, LLM, or continuous-conversation loop.

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
quiet for about one second. **Stop / Cancel** safely returns to READY. **Test input**
remains usable when packages, permissions, devices, or models are unavailable.

If no devices appear, check Windows microphone privacy permissions and confirm that
sounddevice can enumerate PortAudio devices. Model and playback errors appear in the
panel and technical details are logged in the terminal.

Audio remains in memory and is discarded after transcription. Debug recordings are
disabled by default; ADRIEN does not retain microphone audio in Phase 2.
