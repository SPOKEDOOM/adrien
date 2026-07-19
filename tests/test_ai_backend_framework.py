from __future__ import annotations

import threading
import time
import unittest

from PySide6.QtWidgets import QApplication

from app.ai import AIBackend, AIBackendManager, AIConfig, AIRequest, AIResponse, BackendState, HybridRouter
from app.ai.backends import LocalBackend, OpenAIBackend, PlaceholderAIBackend
from app.ai.errors import DuplicateRequestError


class FakeBackend(AIBackend):
    def __init__(self, name, available=True, failure=None, wait_event=None):
        self.backend_name = name; self._available = available; self.failure = failure
        self.wait_event = wait_event; self.initialized = self.stopped = self.cancelled = False
        self.calls = 0
    def initialize(self): self.initialized = True
    def shutdown(self): self.stopped = True
    def is_available(self): return self._available
    def generate_reply(self, request):
        self.calls += 1
        if self.wait_event: self.wait_event.wait(.5)
        if self.failure: raise self.failure
        return AIResponse(request.request_id, f"{self.backend_name}: {request.user_text}", self.backend_name)
    def cancel_current_request(self): self.cancelled = True; self.wait_event and self.wait_event.set()


class AIBackendFrameworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def manager(self, mode="local_first", local=None, cloud=None, placeholder=None, **values):
        config = AIConfig(hybrid_mode=mode, **values); manager = AIBackendManager(config)
        manager.register_backend(local or FakeBackend("local"))
        manager.register_backend(cloud or FakeBackend("openai"))
        manager.register_backend(placeholder or FakeBackend("placeholder"))
        manager.initialize(); return manager

    def request(self, **values):
        defaults = dict(user_text="hello", timeout_seconds=1)
        defaults.update(values); return AIRequest(**defaults)

    def test_registration_initialization_status_and_shutdown(self):
        local = FakeBackend("local"); manager = self.manager(local=local)
        self.assertIn("local", manager.backends); self.assertTrue(local.initialized)
        self.assertEqual(manager.statuses["local"].status, BackendState.AVAILABLE)
        manager.shutdown(); self.assertTrue(local.stopped)

    def test_framework_stubs_have_honest_availability(self):
        self.assertFalse(LocalBackend().is_available())
        self.assertFalse(OpenAIBackend().is_available())
        placeholder = PlaceholderAIBackend(); placeholder.initialize()
        self.assertTrue(placeholder.is_available())

    def test_routing_modes(self):
        expected = {
            "local_first": "local", "cloud_first": "openai", "automatic": "local",
            "placeholder_only": "placeholder", "local_only": "local", "cloud_only": "openai",
        }
        for mode, backend in expected.items():
            with self.subTest(mode=mode):
                manager = self.manager(mode); response = manager.generate_reply(self.request())
                self.assertEqual(response.backend_used, backend); manager.shutdown()

    def test_automatic_high_quality_prefers_cloud(self):
        manager = self.manager("automatic")
        response = manager.generate_reply(self.request(metadata={"high_quality_reasoning": True}))
        self.assertEqual(response.backend_used, "openai"); manager.shutdown()

    def test_privacy_local_only_and_private_block_cloud(self):
        for privacy in ("local_only", "private"):
            manager = self.manager("cloud_first", local=FakeBackend("local", available=False))
            response = manager.generate_reply(self.request(metadata={"privacy_level": privacy}))
            self.assertEqual(response.backend_used, "placeholder")
            self.assertEqual(manager.backends["openai"].calls, 0); manager.shutdown()

    def test_unavailable_and_failed_backends_fall_back_predictably(self):
        manager = self.manager(local=FakeBackend("local", available=False),
                               cloud=FakeBackend("openai", failure=RuntimeError("cloud failed")))
        fallbacks = []; manager.fallback_started.connect(lambda old, new: fallbacks.append((old, new)))
        response = manager.generate_reply(self.request())
        self.assertEqual(response.backend_used, "placeholder"); self.assertTrue(response.fallback_used)
        self.assertEqual(response.metadata["failed_backends"], ("local", "openai"))
        self.assertIn(("openai", "placeholder"), fallbacks); manager.shutdown()

    def test_unavailable_local_falls_back_to_cloud(self):
        manager = self.manager(local=FakeBackend("local", available=False))
        response = manager.generate_reply(self.request())
        self.assertEqual(response.backend_used, "openai"); self.assertTrue(response.fallback_used)
        manager.shutdown()

    def test_timeout_error_triggers_placeholder_fallback(self):
        manager = self.manager(local=FakeBackend("local", failure=TimeoutError("timeout")),
                               cloud=FakeBackend("openai", available=False))
        response = manager.generate_reply(self.request())
        self.assertEqual(response.backend_used, "placeholder")
        self.assertIn("local", response.metadata["failed_backends"]); manager.shutdown()

    def test_cancellation_and_unique_request_ids(self):
        release = threading.Event(); local = FakeBackend("local", wait_event=release)
        manager = self.manager(local=local)
        requests = (self.request(), self.request()); self.assertNotEqual(requests[0].request_id, requests[1].request_id)
        responses = []
        worker = threading.Thread(target=lambda: responses.append(manager.generate_reply(requests[0])))
        worker.start(); time.sleep(.02); self.assertTrue(manager.cancel_current_request())
        worker.join(1); self.assertTrue(local.cancelled); self.assertFalse(responses[0].success)
        manager.shutdown()

    def test_duplicate_active_request_is_rejected(self):
        release = threading.Event(); manager = self.manager(local=FakeBackend("local", wait_event=release))
        first = threading.Thread(target=lambda: manager.generate_reply(self.request()))
        first.start(); time.sleep(.02)
        with self.assertRaises(DuplicateRequestError): manager.generate_reply(self.request())
        manager.cancel_current_request(); first.join(1); manager.shutdown()

    def test_repeated_requests_emit_once_and_update_metrics(self):
        manager = self.manager(); responses = []; manager.response_ready.connect(responses.append)
        for _ in range(3): manager.generate_reply(self.request())
        self.assertEqual(len(responses), 3); self.assertEqual(manager.statuses["local"].request_count, 3)
        manager.shutdown()

    def test_router_respects_request_permissions_and_no_backend_error(self):
        router = HybridRouter(); config = AIConfig(fallback_enabled=False)
        self.assertEqual(router.route(self.request(allow_local=False, allow_cloud=False), config), ())
        manager = AIBackendManager(config); response = manager.generate_reply(self.request())
        self.assertFalse(response.success); self.assertIn("No AI backend", response.error_message)


if __name__ == "__main__": unittest.main()
