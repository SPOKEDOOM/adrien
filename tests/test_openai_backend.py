from __future__ import annotations

import asyncio
import os
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.ai import AIBackendManager, AIConfig, AIRequest, OpenAIConfig
from app.ai.backends import OpenAIBackend
from app.ai.errors import ProviderError, RequestCancelledError
from app.ai.backends.placeholder_backend import PlaceholderAIBackend
from app.conversation.conversation_context import ConversationExchange


class FakeResponses:
    def __init__(self, response=None, failure=None, started=None):
        self.response = response
        self.failure = failure
        self.started = started
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        if self.started:
            self.started.set()
            await asyncio.sleep(10)
        if self.failure:
            raise self.failure
        return self.response


class FakeClient:
    def __init__(self, responses): self.responses = responses


def response(text="hello", *, convenience=True):
    content = [SimpleNamespace(type="output_text", text=text)]
    return SimpleNamespace(
        id="resp_safe_123456", status="completed",
        output_text=text if convenience else "",
        output=[SimpleNamespace(content=content, finish_reason="stop")],
        usage=SimpleNamespace(input_tokens=4, output_tokens=2, total_tokens=6),
    )


class OpenAIBackendTests(unittest.TestCase):
    def config(self, **values):
        defaults = dict(api_key_present=True, model="test-model", timeout_seconds=2,
                        max_output_tokens=50, enabled=True)
        defaults.update(values)
        return OpenAIConfig(**defaults)

    def backend(self, fake_responses, config=None):
        backend = OpenAIBackend(config or self.config(), client_factory=lambda **_: FakeClient(fake_responses))
        backend.initialize()
        return backend

    def test_missing_key_is_unavailable_and_config_repr_has_no_secret(self):
        config = self.config(api_key_present=False)
        backend = self.backend(FakeResponses(response()), config)
        self.assertFalse(backend.is_available())
        self.assertNotIn("OPENAI_API_KEY", repr(config))

    def test_sdk_missing_is_safe_when_no_factory_is_injected(self):
        with patch("app.ai.backends.openai_backend.AsyncOpenAI", None):
            backend = OpenAIBackend(self.config()); backend.initialize()
        self.assertFalse(backend.is_available())
        self.assertEqual(backend.last_status, "unavailable")

    def test_environment_validation_and_defaults(self):
        env = {"OPENAI_API_KEY": "secret-value"}
        with patch.dict(os.environ, env, clear=True):
            config = OpenAIConfig.from_environment()
        self.assertTrue(config.api_key_present)
        self.assertEqual(config.timeout_seconds, 30)
        self.assertEqual(config.max_output_tokens, 700)
        self.assertNotIn("secret-value", repr(config))
        with self.assertRaises(ValueError): self.config(timeout_seconds=0)
        with self.assertRaises(ValueError): self.config(max_output_tokens=0)
        with self.assertRaises(ValueError): self.config(model=" ")

    def test_environment_key_absent_and_whitespace_is_stripped(self):
        with patch.dict(os.environ, {}, clear=True):
            missing = OpenAIConfig.from_environment()
        self.assertFalse(missing.api_key_present)
        self.assertFalse(missing.environment_detected)
        with patch.dict(os.environ, {"OPENAI_API_KEY": "  secret-value  "}, clear=True):
            configured = OpenAIConfig.from_environment()
        self.assertTrue(configured.api_key_present)
        self.assertTrue(configured.environment_detected)
        self.assertEqual(configured.api_key, "secret-value")

    def test_empty_dotenv_never_overrides_runtime_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, ".env")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("OPENAI_API_KEY=\nADRIEN_OPENAI_MODEL=\n")
            with patch.dict(os.environ, {"OPENAI_API_KEY": "runtime-secret"}, clear=True):
                config = OpenAIConfig.resolve(dotenv_path=path)
        self.assertTrue(config.api_key_present)
        self.assertTrue(config.environment_detected)
        self.assertEqual(config.api_key, "runtime-secret")
        self.assertEqual(config.model, "gpt-5.6-sol")

    def test_dotenv_is_used_only_when_runtime_value_is_absent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, ".env")
            with open(path, "w", encoding="utf-8") as stream:
                stream.write("OPENAI_API_KEY=dotenv-secret\nADRIEN_OPENAI_MODEL=dotenv-model\n")
            with patch.dict(os.environ, {}, clear=True):
                config = OpenAIConfig.resolve(dotenv_path=path)
        self.assertTrue(config.api_key_present)
        self.assertFalse(config.environment_detected)
        self.assertEqual(config.api_key, "dotenv-secret")
        self.assertEqual(config.model, "dotenv-model")

    def test_valid_key_without_model_uses_central_default(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "secret-value"}, clear=True):
            config = OpenAIConfig.from_environment()
        self.assertTrue(config.api_key_present)
        self.assertEqual(config.model, "gpt-5.6-sol")

    def test_success_passes_prompt_history_without_duplicate_and_extracts_metadata(self):
        transport = FakeResponses(response("fallback text", convenience=False))
        backend = self.backend(transport)
        history = (ConversationExchange("first", "answer", SimpleNamespace()),)
        result = backend.generate_reply(AIRequest(
            user_text="current", system_prompt="ADRIEN prompt", conversation_history=history,
        ))
        self.assertEqual(result.reply_text, "fallback text")
        self.assertEqual(transport.kwargs["instructions"], "ADRIEN prompt")
        self.assertEqual(transport.kwargs["input"], [
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "answer"},
            {"role": "user", "content": "current"},
        ])
        self.assertEqual(result.metadata["usage"]["total_tokens"], 6)
        self.assertEqual(result.metadata["response_id"], "resp_safe_123456")

    def test_unexpected_response_is_safe_provider_error(self):
        backend = self.backend(FakeResponses(SimpleNamespace(output_text="", output=[])))
        with self.assertRaises(ProviderError) as caught:
            backend.generate_reply(AIRequest(user_text="hello"))
        self.assertEqual(caught.exception.category, "invalid_response")

    def test_provider_exception_categories(self):
        expected = {
            "AuthenticationError": "auth", "PermissionDeniedError": "permission",
            "RateLimitError": "rate_limit", "APITimeoutError": "timeout",
            "APIConnectionError": "connection", "BadRequestError": "invalid_request",
            "InternalServerError": "server", "SomethingElse": "unknown",
        }
        for name, category in expected.items():
            with self.subTest(name=name):
                failure = type(name, (Exception,), {})()
                backend = self.backend(FakeResponses(failure=failure))
                with self.assertRaises(ProviderError) as caught:
                    backend.generate_reply(AIRequest(user_text="hello"))
                self.assertEqual(caught.exception.category, category)

    def test_secret_never_appears_in_repr_or_logs(self):
        secret = "sk-test-do-not-display"
        with patch.dict(os.environ, {"OPENAI_API_KEY": secret}, clear=True):
            config = OpenAIConfig.from_environment()
            with self.assertLogs("app.ai.backends.openai_backend", level="INFO") as logs:
                backend = self.backend(FakeResponses(response()), config)
                backend.generate_reply(AIRequest(user_text="hello"))
        output = "\n".join(logs.output) + repr(config) + repr(backend)
        self.assertNotIn(secret, output)
        self.assertIn("key_configured=yes", output)

    def test_hybrid_falls_back_and_records_openai_failure_category(self):
        openai_backend = self.backend(FakeResponses(failure=type("RateLimitError", (Exception,), {})()))
        manager = AIBackendManager(AIConfig(hybrid_mode="openai_first"))
        manager.register_backend(openai_backend); manager.register_backend(PlaceholderAIBackend())
        manager.initialize()
        result = manager.generate_reply(AIRequest(user_text="Hello"))
        self.assertEqual(result.backend_used, "placeholder")
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.metadata["failure_reasons"]["openai"], "rate_limit")
        manager.shutdown()

    def test_personality_change_affects_next_openai_instructions(self):
        transport = FakeResponses(response("first")); backend = self.backend(transport)
        backend.generate_reply(AIRequest(user_text="hello", system_prompt="Identity: ADRIEN"))
        self.assertEqual(transport.kwargs["instructions"], "Identity: ADRIEN")
        backend.generate_reply(AIRequest(user_text="hello", system_prompt="Identity: NOVA"))
        self.assertEqual(transport.kwargs["instructions"], "Identity: NOVA")

    def test_cancellation_cancels_async_task(self):
        started = threading.Event()
        backend = self.backend(FakeResponses(response(), started=started))
        caught = []
        worker = threading.Thread(target=lambda: self._capture_cancel(backend, caught))
        worker.start(); self.assertTrue(started.wait(1)); backend.cancel_current_request(); worker.join(2)
        self.assertEqual(caught, ["cancelled"])

    @staticmethod
    def _capture_cancel(backend, caught):
        try: backend.generate_reply(AIRequest(user_text="hello"))
        except RequestCancelledError: caught.append("cancelled")


if __name__ == "__main__": unittest.main()
