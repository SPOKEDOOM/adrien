from app.ai.ai_backend import AIBackend
from app.ai.errors import BackendUnavailableError


class LocalBackend(AIBackend):
    backend_name = "local"
    backend_type = "local"

    def __init__(self, available: bool = False, provider: str = "local_stub"):
        self._available, self.provider = available, provider
    def is_available(self): return self._available
    def generate_reply(self, request):
        raise BackendUnavailableError("Local AI backend is not installed.")
