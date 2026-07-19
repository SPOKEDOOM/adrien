from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.ai_response import AIResponse


class AIBackend(ABC):
    backend_name = "backend"
    backend_type = "generic"
    model_name = ""
    supports_streaming = False
    supports_tools = False
    supports_vision = False

    def initialize(self) -> None: pass
    def shutdown(self) -> None: pass
    @abstractmethod
    def is_available(self) -> bool: raise NotImplementedError
    @abstractmethod
    def generate_reply(self, request) -> AIResponse: raise NotImplementedError
    def cancel_current_request(self) -> None: pass
    def health_check(self) -> bool: return self.is_available()
