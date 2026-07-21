from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from app.conversation import ConversationManager
from app.ai import AIRequest, ProviderCredentialService
from app.settings import ApplicationSettings
from app.ui.main_window import MainWindow
from app.ui.settings_page import SettingsPage


class SettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.directory.name, "settings.ini")
        self.store = QSettings(self.path, QSettings.IniFormat)
        self.settings = ApplicationSettings(self.store)

    def tearDown(self): self.directory.cleanup()

    def test_settings_persist_default_priority_cloud_and_developer_mode(self):
        self.settings.set_default_provider("groq")
        self.settings.set_provider_priority(("openai", "groq", "local", "placeholder"))
        self.settings.set_value("privacy/cloud_processing", False)
        self.settings.set_value("developer/mode", False)
        restored = ApplicationSettings(QSettings(self.path, QSettings.IniFormat))
        self.assertEqual(restored.default_provider, "groq")
        self.assertEqual(restored.provider_priority, ("openai", "groq", "local", "placeholder"))
        self.assertFalse(restored.cloud_processing); self.assertFalse(restored.developer_mode)

    def test_provider_and_priority_changes_update_router_immediately(self):
        manager = ConversationManager(); page = SettingsPage(self.settings, manager)
        page._set_default("openai")
        self.assertEqual(manager.ai_manager.config.default_backend, "openai")
        self.assertEqual(manager.ai_manager.config.hybrid_mode, "openai_only")
        page.priority.setCurrentRow(1); page._move_priority(-1)
        self.assertEqual(manager.ai_manager.config.provider_priority[0], "openai")
        route = manager.ai_manager.router.route(__import__("app.ai", fromlist=["AIRequest"]).AIRequest(user_text="hello"),
                                                manager.ai_manager.config)
        self.assertEqual(route[0], "openai")
        manager.shutdown(); page.close()

    def test_provider_selection_and_routing_mode_persist(self):
        manager = ConversationManager(); page = SettingsPage(self.settings, manager)
        page.ai_providers_page.select_provider("groq")
        self.assertEqual(self.settings.default_provider, "groq")
        self.assertEqual(manager.ai_manager.config.hybrid_mode, "groq_only")
        page.ai_providers_page.select_provider("automatic")
        page.routing_priority.setCurrentIndex(page.routing_priority.findData("openai_first"))
        restored = ApplicationSettings(QSettings(self.path, QSettings.IniFormat))
        self.assertEqual(restored.default_provider, "automatic")
        self.assertEqual(restored.routing_mode, "openai_first")
        self.assertEqual(manager.ai_manager.config.hybrid_mode, "openai_first")
        manager.shutdown(); page.close()

    def test_placeholder_selection_routes_offline_only(self):
        manager = ConversationManager(); page = SettingsPage(self.settings, manager)
        page.ai_providers_page.select_provider("placeholder")
        routes = manager.ai_manager.router.route(AIRequest(user_text="hello"), manager.ai_manager.config)
        self.assertEqual(routes, ("placeholder",))
        manager.shutdown(); page.close()

    def test_credentials_mask_source_and_refresh_never_expose_secret(self):
        secret = "gsk_super_secret_value_7xQ"
        with patch.dict(os.environ, {"GROQ_API_KEY": secret, "OPENAI_API_KEY": ""}, clear=False):
            service = ProviderCredentialService(dotenv_path=os.path.join(self.directory.name, "missing.env"))
            self.assertEqual(service.get_provider_key_source("groq"), "Environment")
            masked = service.mask_secret(secret)
            self.assertTrue(masked.startswith("gsk_")); self.assertTrue(masked.endswith("7xQ"))
            self.assertNotIn(secret, repr(service.configs["groq"]))
            manager = ConversationManager(credential_service=service); page = SettingsPage(self.settings, manager)
            page.ai_providers_page.refresh_status(); displayed = " ".join(
                label.text() for label in page.ai_providers_page.findChildren(QLabel))
            self.assertNotIn(secret, displayed); self.assertEqual(page.provider_cards["groq"].configured.text(), "Yes")
            self.assertEqual(page.provider_cards["groq"].source.text(), "Environment")
            manager.shutdown(); page.close()

    def test_card_and_child_label_click_select_provider(self):
        manager = ConversationManager(); page = SettingsPage(self.settings, manager); page.show(); self.app.processEvents()
        card = page.provider_cards["groq"]
        QTest.mouseClick(card, Qt.LeftButton, pos=QPoint(5, 5)); self.app.processEvents()
        self.assertEqual(self.settings.default_provider, "groq")
        self.assertTrue(card.status.testAttribute(Qt.WA_TransparentForMouseEvents))
        manager.shutdown(); page.close()

    def test_provider_test_loading_success_and_failure(self):
        manager = ConversationManager(); page = SettingsPage(self.settings, manager); providers = page.ai_providers_page
        with patch.object(manager, "test_groq_connection", return_value=True):
            providers.test_provider("groq")
            self.assertFalse(providers.provider_cards["groq"].test_button.isEnabled())
        manager.groq_test_finished.emit({"success": True, "elapsed": .05}); self.app.processEvents()
        self.assertTrue(providers.provider_cards["groq"].test_button.isEnabled())
        self.assertEqual(providers.provider_cards["groq"].test.text(), "Success")
        manager.openai_test_finished.emit({"success": False, "category": "authentication", "message": "Authentication failed"})
        self.assertIn("authentication", providers.provider_cards["openai"].test.text())
        manager.shutdown(); page.close()

    def test_cloud_toggle_updates_conversation_config(self):
        with patch("app.ui.main_window.ApplicationSettings", return_value=self.settings):
            window = MainWindow()
        window.settings_page.cloud_processing.setChecked(False); self.app.processEvents()
        self.assertFalse(window.voice_manager.conversation_manager.ai_manager.config.allow_cloud_ai)
        window.close()

    def test_developer_mode_hides_tools_and_blocks_toggle(self):
        self.settings.set_value("developer/mode", True)
        with patch("app.ui.main_window.ApplicationSettings", return_value=self.settings):
            window = MainWindow()
        window.show(); self.app.processEvents()
        window.toggle_developer_tools(); self.app.processEvents(); self.assertTrue(window.developer_tools_panel.isVisible())
        window.settings_page.developer_mode.setChecked(False); self.app.processEvents()
        self.assertFalse(window.developer_tools_panel.isVisible())
        self.assertFalse(window.settings_page.open_developer_tools.isEnabled())
        self.assertFalse(hasattr(window.presence_status_bar, "gear_button"))
        window.toggle_developer_tools(); self.assertFalse(window.developer_tools_panel.isVisible()); window.close()

    def test_sidebar_is_the_only_navigation_and_exposes_top_level_pages(self):
        with patch("app.ui.main_window.ApplicationSettings", return_value=self.settings):
            window = MainWindow()
        expected = ["Home", "Presence", "Voice", "Brain", "Memory", "AI Providers", "Privacy", "Developer", "About"]
        self.assertEqual([window.sidebar.item(i).text() for i in range(window.sidebar.count())], expected)
        self.assertFalse(hasattr(window.settings_page, "navigation"))
        for index, name in enumerate(expected):
            window.sidebar.setCurrentRow(index); self.app.processEvents()
            self.assertIs(window.content_stack.currentWidget(), window.sidebar_pages[name])
        window.close()

    def test_developer_page_opens_tools_when_mode_enabled(self):
        self.settings.set_value("developer/mode", True)
        with patch("app.ui.main_window.ApplicationSettings", return_value=self.settings):
            window = MainWindow()
        window.show(); window.sidebar.setCurrentRow(7); self.app.processEvents()
        window.settings_page.open_developer_tools.click(); self.app.processEvents()
        self.assertEqual(window.sidebar.currentRow(), 0)
        self.assertIs(window.content_stack.currentWidget(), window.core)
        self.assertTrue(window.developer_tools_panel.isVisible()); window.close()


if __name__ == "__main__": unittest.main()
