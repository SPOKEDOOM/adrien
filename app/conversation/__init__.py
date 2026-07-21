from app.conversation.conversation_backend import ConversationBackend
from app.conversation.conversation_config import ConversationConfig
from app.conversation.conversation_context import ConversationContext, ConversationExchange
from app.conversation.conversation_memory import ConversationMemory, ConversationSummary
from app.conversation.placeholder_backend import PlaceholderBackend

__all__ = [
    "ConversationBackend", "ConversationConfig", "ConversationContext", "ConversationMemory", "ConversationSummary",
    "ConversationExchange", "ConversationManager", "PlaceholderBackend",
]


def __getattr__(name):
    # ConversationManager imports the AI framework, whose placeholder adapter reuses
    # PlaceholderBackend. Lazy exposure prevents that compatibility path from cycling.
    if name == "ConversationManager":
        from app.conversation.conversation_manager import ConversationManager
        return ConversationManager
    raise AttributeError(name)
