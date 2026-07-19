from app.ai.ai_backend import AIBackend
from app.ai.errors import BackendUnavailableError


class OpenAIBackend(AIBackend):
    backend_name = "openai"
    backend_type = "cloud"

    def __init__(self, configured: bool = False): self._configured = configured
    def is_available(self): return self._configured
    def generate_reply(self, request):
        raise BackendUnavailableError("OpenAI backend is not configured.")
