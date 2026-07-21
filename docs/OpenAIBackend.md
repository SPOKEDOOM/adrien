# OpenAI backend

ADRIEN's cloud backend implements the existing `AIBackend` contract with the official
asynchronous OpenAI Python client and the Responses API. `ConversationManager` builds
the provider-independent personality instructions and supplies bounded recent history;
`OpenAIBackend` only translates that structured request, extracts text and returns an
`AIResponse`. Network work runs on ADRIEN's existing conversation worker, never on the
PySide6 UI thread.

## Installation and configuration

Install the normal project dependencies:

```powershell
python -m pip install -r requirements.txt
```

Set a key for the current PowerShell session, then launch ADRIEN from that session:

```powershell
$env:OPENAI_API_KEY="your-key-here"
python main.py
```

To persist it for the current Windows user:

```powershell
[Environment]::SetEnvironmentVariable(
    "OPENAI_API_KEY",
    "your-key-here",
    "User"
)
```

Restart the terminal and ADRIEN after a persistent environment change. Never commit a
real key. `.env.example` is documentation only; ADRIEN reads the process environment.

Optional settings are `ADRIEN_OPENAI_MODEL` (default `gpt-5.6-sol`),
`ADRIEN_OPENAI_TIMEOUT_SECONDS` (default `30`), and
`ADRIEN_OPENAI_MAX_OUTPUT_TOKENS` (default `700`). API usage may incur charges. OpenAI
API billing is separate from a ChatGPT subscription.

## Privacy, routing, fallback, and cancellation

`allow_cloud_ai` is the application-wide privacy control, exposed as **Allow cloud
processing** in Developer Tools → Conversation. When false, routing excludes
OpenAI before any provider call. No microphone audio is sent: only the final text,
provider-independent instructions, and the configured bounded recent text history are
included. Supported routes are `local_first`, `openai_first`, `local_only`,
`openai_only`, `automatic`, and `placeholder_only`. When permitted, the deterministic
Placeholder backend remains the last safe fallback.

Cancellation rejects late results, prevents cancelled exchanges from entering history,
and prevents them from reaching TTS. It cancels the in-flight asyncio task safely rather
than terminating a worker thread.

Developer Tools → Conversation shows configuration (never the key), status, model,
shortened response ID, latency, usage, error category, routing, and cloud permission.
**Test OpenAI** is the only explicit live diagnostic; it makes a small direct request,
does not use fallback, and disables itself while running.

## Tests

Normal tests use injected fake async clients and never call OpenAI:

```powershell
python -m pytest
```

## Troubleshooting

- **SDK missing:** install `requirements.txt`; ADRIEN still launches with Placeholder.
- **API key missing:** set `OPENAI_API_KEY`, then restart ADRIEN.
- **Invalid key:** verify or replace the key after an `auth` diagnostic.
- **No billing / insufficient credits:** check API billing and project limits; a ChatGPT
  subscription does not provide API credits.
- **Rate limit:** wait and retry or review the API project's limits.
- **Timeout:** increase `ADRIEN_OPENAI_TIMEOUT_SECONDS` or check network latency.
- **Network failure:** check connectivity, proxy, firewall, and DNS settings.
- **Unsupported model:** choose a Responses-API model available to the API project.
- **Cloud AI disabled:** enable `allow_cloud_ai` in ADRIEN's configuration before use.
