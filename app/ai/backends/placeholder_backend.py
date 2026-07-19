from __future__ import annotations

from app.ai.ai_backend import AIBackend
from app.ai.ai_response import AIResponse
from app.conversation.placeholder_backend import PlaceholderBackend


class PlaceholderAIBackend(AIBackend):
    backend_name = "placeholder"
    backend_type = "fallback"
    model_name = "deterministic-placeholder"

    def __init__(self, backend=None): self.backend = backend or PlaceholderBackend()
    def initialize(self): self.backend.initialize()
    def shutdown(self): self.backend.shutdown()
    def is_available(self): return bool(self.backend.initialized)
    def generate_reply(self, request):
        reply = self.backend.generate_reply(
            request.user_text, None, request.metadata.get("personality")
        )
        return AIResponse(request.request_id, reply, self.backend_name, self.model_name)
