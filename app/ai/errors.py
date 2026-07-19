class AIBackendError(RuntimeError): pass
class BackendUnavailableError(AIBackendError): pass
class BackendTimeoutError(AIBackendError): pass
class RequestCancelledError(AIBackendError): pass
class DuplicateRequestError(AIBackendError): pass
