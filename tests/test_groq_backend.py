from __future__ import annotations

import asyncio
import os
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.ai import AIBackendManager, AIConfig, AIRequest, GroqConfig
from app.ai.backends import GroqBackend, PlaceholderAIBackend
from app.ai.errors import ProviderError, RequestCancelledError
from app.conversation.conversation_context import ConversationExchange


def completion(text="hello", *, choices=True):
    choice = SimpleNamespace(message=SimpleNamespace(content=text), finish_reason="stop")
    return SimpleNamespace(id="groq_safe_123456", choices=[choice] if choices else [],
                           usage=SimpleNamespace(prompt_tokens=4, completion_tokens=2, total_tokens=6))


class FakeCompletions:
    def __init__(self, value=None, failure=None, started=None):
        self.value, self.failure, self.started, self.kwargs = value, failure, started, None
    async def create(self, **kwargs):
        self.kwargs = kwargs
        if self.started: self.started.set(); await asyncio.sleep(10)
        if self.failure: raise self.failure
        return self.value


class FakeClient:
    def __init__(self, transport):
        self.chat = SimpleNamespace(completions=transport)


class GroqBackendTests(unittest.TestCase):
    def config(self, **updates):
        values = dict(api_key_present=True, model="test-groq", timeout_seconds=2,
                      max_output_tokens=50, enabled=True, api_key="secret")
        values.update(updates); return GroqConfig(**values)

    def backend(self, transport, config=None):
        backend = GroqBackend(config or self.config(), client_factory=lambda **_: FakeClient(transport))
        backend.initialize(); return backend

    def test_missing_sdk_key_and_valid_configuration(self):
        self.assertFalse(self.backend(FakeCompletions(completion()), self.config(api_key_present=False)).is_available())
        with patch("app.ai.backends.groq_backend.AsyncGroq", None):
            backend = GroqBackend(self.config()); backend.initialize()
        self.assertFalse(backend.is_available())
        self.assertTrue(self.backend(FakeCompletions(completion())).is_available())

    def test_environment_precedence_whitespace_and_defaults(self):
        dotenv = {"GROQ_API_KEY": "", "ADRIEN_GROQ_MODEL": "dotenv-model"}
        with patch.dict(os.environ, {"GROQ_API_KEY": "  runtime-secret  "}, clear=True):
            config = GroqConfig.from_environment(dotenv_values=dotenv)
        self.assertEqual(config.api_key, "runtime-secret"); self.assertTrue(config.environment_detected)
        self.assertEqual(config.model, "dotenv-model")
        with patch.dict(os.environ, {"GROQ_API_KEY": "key"}, clear=True):
            self.assertEqual(GroqConfig.from_environment().model, "llama-3.1-8b-instant")

    def test_empty_dotenv_file_does_not_override_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, ".env")
            with open(path, "w", encoding="utf-8") as stream: stream.write("GROQ_API_KEY=\n")
            with patch.dict(os.environ, {"GROQ_API_KEY": "runtime"}, clear=True):
                config = GroqConfig.resolve(dotenv_path=path)
        self.assertEqual(config.api_key, "runtime")

    def test_success_prompt_history_dedup_usage_and_extraction(self):
        transport = FakeCompletions(completion("answer")); backend = self.backend(transport)
        history = (ConversationExchange("first", "reply", SimpleNamespace()),)
        result = backend.generate_reply(AIRequest(user_text="current", system_prompt="ADRIEN prompt",
                                                  conversation_history=history))
        self.assertEqual(result.reply_text, "answer")
        self.assertEqual(transport.kwargs["messages"], [
            {"role": "system", "content": "ADRIEN prompt"}, {"role": "user", "content": "first"},
            {"role": "assistant", "content": "reply"}, {"role": "user", "content": "current"}])
        self.assertEqual(result.metadata["usage"]["total_tokens"], 6)
        self.assertEqual(result.metadata["response_id"], "groq_safe_123456")

    def test_personality_prompt_changes_next_request(self):
        transport = FakeCompletions(completion()); backend = self.backend(transport)
        backend.generate_reply(AIRequest(user_text="hello", system_prompt="Identity ADRIEN"))
        self.assertEqual(transport.kwargs["messages"][0]["content"], "Identity ADRIEN")
        backend.generate_reply(AIRequest(user_text="hello", system_prompt="Identity NOVA"))
        self.assertEqual(transport.kwargs["messages"][0]["content"], "Identity NOVA")

    def test_empty_choices_and_content_are_safe(self):
        for value in (completion(choices=False), completion("")):
            with self.subTest(value=value):
                with self.assertRaises(ProviderError) as caught:
                    self.backend(FakeCompletions(value)).generate_reply(AIRequest(user_text="hello"))
                self.assertEqual(caught.exception.category, "invalid_response")

    def test_exception_mapping_including_quota_and_model(self):
        cases = [
            ("AuthenticationError", 401, {}, "authentication"), ("PermissionDeniedError", 403, {}, "permission"),
            ("RateLimitError", 429, {}, "rate_limit"), ("RateLimitError", 429, {"error": {"code": "insufficient_quota"}}, "quota"),
            ("APITimeoutError", None, {}, "timeout"), ("APIConnectionError", None, {}, "connection"),
            ("BadRequestError", 400, {}, "invalid_request"), ("NotFoundError", 404, {"error": {"code": "model_not_found"}}, "model_not_found"),
            ("InternalServerError", 500, {}, "server"), ("OtherError", None, {}, "unknown"),
        ]
        for name, status, body, expected in cases:
            with self.subTest(name=name, expected=expected):
                failure = type(name, (Exception,), {"status_code": status, "body": body})()
                with self.assertRaises(ProviderError) as caught:
                    self.backend(FakeCompletions(failure=failure)).generate_reply(AIRequest(user_text="hello"))
                self.assertEqual(caught.exception.category, expected)

    def test_cancellation(self):
        started = threading.Event(); backend = self.backend(FakeCompletions(completion(), started=started)); caught = []
        def run():
            try: backend.generate_reply(AIRequest(user_text="hello"))
            except RequestCancelledError: caught.append("cancelled")
        worker = threading.Thread(target=run); worker.start(); self.assertTrue(started.wait(1))
        backend.cancel_current_request(); worker.join(2); self.assertEqual(caught, ["cancelled"])

    def test_groq_first_fallback_and_cloud_disabled(self):
        groq = self.backend(FakeCompletions(failure=type("RateLimitError", (Exception,), {})()))
        manager = AIBackendManager(AIConfig(hybrid_mode="groq_first"), groq_config=groq.config)
        manager.register_backend(groq); manager.register_backend(PlaceholderAIBackend()); manager.initialize()
        result = manager.generate_reply(AIRequest(user_text="Hello"))
        self.assertEqual(result.backend_used, "placeholder"); self.assertTrue(result.fallback_used)
        self.assertEqual(result.metadata["failure_reasons"]["groq"], "rate_limit")
        manager.config.allow_cloud_ai = False
        self.assertNotIn("groq", manager.router.route(AIRequest(user_text="Hello"), manager.config))
        manager.shutdown()

    def test_secret_absent_from_repr_and_logs(self):
        secret = "gsk-never-display"
        with patch.dict(os.environ, {"GROQ_API_KEY": secret}, clear=True):
            config = GroqConfig.from_environment()
            with self.assertLogs("app.ai.backends.groq_backend", level="INFO") as logs:
                backend = self.backend(FakeCompletions(completion()), config)
                backend.generate_reply(AIRequest(user_text="hello"))
        self.assertNotIn(secret, repr(config) + repr(backend) + "\n".join(logs.output))


if __name__ == "__main__": unittest.main()
