from app.ai.ai_backend import AIBackend
from app.ai.ai_response import AIResponse
from app.conversation.conversation_context import ConversationContext


class LegacyConversationBackendAdapter(AIBackend):
    """Compatibility bridge for existing replaceable ConversationBackend tests/providers."""
    backend_type = "compatibility"

    def __init__(self, backend):
        self.backend = backend
        self.backend_name = getattr(backend, "name", type(backend).__name__)
        self._available = False
    def initialize(self): self.backend.initialize(); self._available = True
    def shutdown(self): self.backend.shutdown(); self._available = False
    def is_available(self): return self._available
    def generate_reply(self, request):
        context = ConversationContext(max(1, len(request.conversation_history) or 10))
        for exchange in request.conversation_history:
            context.add_exchange(exchange.user_message, exchange.adrien_reply, exchange.timestamp)
        reply = self.backend.generate_reply(request.user_text, context)
        return AIResponse(request.request_id, reply, self.backend_name)
