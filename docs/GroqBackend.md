# Groq backend

ADRIEN integrates Groq as a cloud `AIBackend` using the official asynchronous SDK
and Chat Completions API. `ConversationManager` supplies the provider-independent
personality prompt and bounded history; Groq only translates the structured request.

Install dependencies with `python -m pip install -r requirements.txt`. For the current
PowerShell session use `$env:GROQ_API_KEY="your-key-here"`. To persist it:

```powershell
[Environment]::SetEnvironmentVariable("GROQ_API_KEY", "your-key-here", "User")
```

Restart the terminal and ADRIEN after persistent changes. Optional variables are
`ADRIEN_GROQ_MODEL`, `ADRIEN_GROQ_TIMEOUT_SECONDS`,
`ADRIEN_GROQ_MAX_OUTPUT_TOKENS`, and `ADRIEN_GROQ_ENABLED`. The documented default is
`llama-3.1-8b-instant`; model availability changes, so it remains configurable.

`allow_cloud_ai` controls both Groq and OpenAI. Only final text and approved recent
text context are sent; microphone audio is never sent. Routing supports `groq_first`
and `groq_only`, with safe Placeholder fallback where configured. Cancellation stops
the active asyncio task and stale results cannot reach history or TTS.

Developer Tools provides a direct **Test Groq** action. It makes a small request only
when clicked and never treats fallback as success. Automated tests inject a fake client
and make no live calls. Groq usage may be rate-limited or incur charges depending on
the account plan.
