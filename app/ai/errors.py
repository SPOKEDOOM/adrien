class AIBackendError(RuntimeError): pass
class BackendUnavailableError(AIBackendError): pass
class BackendTimeoutError(AIBackendError): pass
class RequestCancelledError(AIBackendError): pass
class DuplicateRequestError(AIBackendError): pass


class ProviderError(AIBackendError):
    def __init__(self, category: str, user_message: str, *, transient: bool = False,
                 provider_code: str = "", http_status: int | None = None) -> None:
        super().__init__(user_message)
        self.category = category
        self.user_message = user_message
        self.transient = transient
        self.provider_code = provider_code
        self.http_status = http_status
