"""Own-window regressions; CI installs Qt and runs under Cocoa or X11/Openbox."""
import importlib.util
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

AVAILABLE = importlib.util.find_spec("PySide6") is not None
if os.environ.get("HUD_REQUIRE_GUI") == "1" and not AVAILABLE:
    raise RuntimeError("Qt GUI coverage was required but PySide6 is missing")
if AVAILABLE:
    from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
    from PySide6.QtWidgets import QApplication, QDialogButtonBox
    from dashboard import start_server
    from metrics import atomic_json
    from overlay import ConversationPicker, Hud, Instance, mac_window_state
    from test_overlay import snapshot


@unittest.skipUnless(AVAILABLE, "Optional desktop HUD dependencies are not installed")
class OverlayGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.server = start_server(self.root, self.root / "runtime", native_enabled=True, native_follow_mode="activity")
        self.hud = Hud(self.server, "en", start_worker=False, tray=False)
        self.hud.show()
        self.app.processEvents()
        self.hud.apply_snapshot(snapshot())

    def tearDown(self):
        self.hud.shutdown()
        self.hud.hide()
        self.hud.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def test_real_visible_topmost_window_and_mac_native_flags(self):
        self.assertTrue(self.hud.isVisible())
        self.assertTrue(self.hud.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        native = mac_window_state(self.hud)
        if self.app.platformName() == "cocoa":
            self.assertEqual(native["collection_behavior"] & 257, 257)
            self.assertGreater(native["level"], 0)
        self.assertEqual(self.hud.native_error, "")

    def test_repeat_show_preserves_chat_and_measurements(self):
        self.hud.show_hud()
        self.hud.show_hud()
        self.assertEqual(self.hud.snapshot["thread"]["id"], "one")
        self.assertEqual(self.hud.rate_label.text(), "125.0")
        self.hud.update_menu()
        self.assertFalse(self.hud.show_action.isEnabled())

    def test_hidden_and_minimized_restore_without_reset(self):
        self.hud.hide()
        self.hud.update_menu()
        self.assertTrue(self.hud.show_action.isEnabled())
        self.hud.show_hud()
        self.assertTrue(self.hud.isVisible())
        self.hud.showMinimized()
        self.app.processEvents()
        self.hud.show_hud()
        self.app.processEvents()
        self.assertFalse(self.hud.isMinimized())
        self.assertEqual(self.hud.snapshot["thread"]["id"], "one")

    def test_unpin_waiting_state_keeps_window_and_clears_old_counts(self):
        self.hud.apply_snapshot({"threads": [], "thread": None, "live": None, "pinned_thread_id": None})
        self.assertTrue(self.hud.isVisible())
        self.assertEqual(self.hud.rate_label.text(), "—")
        self.hud.update_menu()
        self.assertTrue(any("Choose and pin" in a.text() for a in self.hud.menu.actions()))

    def test_no_tray_cannot_strand_hidden_window(self):
        self.hud.update_menu()
        self.assertFalse(self.hud.hide_action.isEnabled())
        self.hud.hide_hud()
        self.assertTrue(self.hud.isVisible())

    def test_expired_worker_heartbeat_hides_counts_and_does_not_block_gui(self):
        self.hud.received = time.monotonic() - 5
        started = time.monotonic()
        self.hud.render()
        self.app.processEvents()
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(self.hud.rate_label.text(), "—")

    def test_resize_and_move_are_saved_and_offscreen_layout_is_recovered(self):
        self.hud.resize(920, 190)
        self.hud.move(QApplication.primaryScreen().availableGeometry().topLeft() + QPoint(20, 30))
        self.hud.save_layout()
        self.hud.resize(700, 170)
        self.hud.restore_layout()
        self.assertEqual(self.hud.width(), 920)
        atomic_json(self.hud.runtime / "overlay-layout.json", {"x": 999999, "y": 999999, "width": 920, "height": 190})
        self.hud.restore_layout()
        self.assertTrue(self.hud.geometry().intersects(QApplication.primaryScreen().availableGeometry()))

    def test_picker_search_disambiguates_full_id(self):
        self.hud.snapshot["threads"] = [{"id": "first-exact-id", "title": "Same title"},
                                       {"id": "second-exact-id", "title": "Same title"}]
        picker = ConversationPicker(self.hud)
        picker.search.setText("second-exact-id")
        self.assertEqual(picker.items.count(), 1)
        self.assertFalse(picker.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
        picker.items.setCurrentRow(0)
        picker.pick()
        self.assertEqual(picker.thread_id, "second-exact-id")

    def test_dashboard_opens_with_exact_current_chat(self):
        with patch("overlay.webbrowser.open") as opening:
            self.hud.open_dashboard()
        self.assertIn("thread=one", opening.call_args.args[0])

    def test_relaunch_ipc_restores_existing_window(self):
        first = Instance(self.root / "instance")
        self.assertTrue(first.acquire())
        first.show_requested.connect(self.hud.show_hud)
        self.hud.hide()
        second = Instance(self.root / "instance")
        self.assertFalse(second.acquire())
        deadline = time.monotonic() + 2
        while not self.hud.isVisible() and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertTrue(self.hud.isVisible())
        self.assertEqual(self.hud.snapshot["thread"]["id"], "one")
        first.close()
        second.close()
        first.deleteLater()
        second.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_range_return_button_visible_and_snapshot_not_stale(self):
        data = snapshot()
        data["live"]["range"] = {"thread_id": "one", "rate": 20, "cache_percent": 25, "sample_count": 3}
        self.hud.apply_snapshot(data)
        self.assertTrue(self.hud.latest_button.isVisible())
        self.assertEqual(self.hud.rate_label.text(), "20.0")
        self.hud.apply_snapshot(snapshot())
        self.assertFalse(self.hud.latest_button.isVisible())

    def test_actions_fit_minimum_size_and_capture_synthetic_ui(self):
        directory = Path(os.environ.get("HUD_SCREENSHOT_DIR", "build/overlay-ui"))
        directory.mkdir(parents=True, exist_ok=True)
        for width, suffix in ((850, "normal"), (640, "compact")):
            self.hud.resize(width, 160)
            self.app.processEvents()
            for button in (self.hud.choose_button, self.hud.panel_button, self.hud.refresh_button, self.hud.more_button):
                self.assertTrue(button.isVisible())
                self.assertGreaterEqual(button.height(), 34)
                self.assertTrue(self.hud.rect().contains(button.geometry()), button.text())
            self.assertTrue(self.hud.grab().save(str(directory / (self.app.platformName() + "-" + suffix + ".png"))))


if __name__ == "__main__":
    unittest.main()
