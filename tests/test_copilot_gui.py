"""Exercise global prompt editing with an isolated user directory and offscreen Qt."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(ROOT / "gui"))
try:
    import app as ui
    from PySide6.QtGui import QCloseEvent
except ImportError:
    ui = None


@unittest.skipIf(ui is None, "PySide6 is required for GUI checks")
class GlobalPromptGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = ui.QApplication.instance() or ui.QApplication([])

    def setUp(self):
        work = ROOT / ".work"
        work.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="copilot-ui-test-", dir=work)
        Path(self.temporary.name).resolve().relative_to(work.resolve())
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.environment = mock.patch.dict(os.environ, {"COPILOT_HOME": str(self.directory)})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.patches = [
            mock.patch.object(ui.App, "_load_theme", return_value="light"),
            mock.patch.object(ui.App, "_save_theme"),
            mock.patch.object(ui.App, "_refresh_path"),
            mock.patch.object(ui.App, "_refresh_update_pill"),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.window = ui.App()
        self.addCleanup(self.close_window)
        self.path = self.directory / "copilot-instructions.md"

    def close_window(self):
        self.window.copilot_editor.setPlainText(self.window._copilot_loaded_text)
        self.window._worker = None
        self.window.close()
        self.qapp.processEvents()

    def test_preset_saves_and_reload_marks_clean(self):
        self.assertFalse(self.path.exists())
        self.window.btn_copilot_preset.click()
        self.assertTrue(self.window.btn_copilot_save.isEnabled())
        self.assertTrue(self.window._save_copilot_prompt())
        self.assertIn("简体中文", self.path.read_text(encoding="utf-8"))
        self.assertFalse(self.window._copilot_has_changes())
        self.assertFalse(self.window.btn_copilot_save.isEnabled())

    def test_external_edit_preserves_file_and_unsaved_draft(self):
        self.window._on_copilot_preset()
        self.assertTrue(self.window._save_copilot_prompt())
        self.window.copilot_editor.setPlainText("我的新要求")
        external = self.path.read_bytes() + b"\nOther editor's rules.\n"
        self.path.write_bytes(external)
        self.assertFalse(self.window._save_copilot_prompt())
        self.assertEqual(self.path.read_bytes(), external)
        self.assertEqual(self.window.copilot_editor.toPlainText(), "我的新要求")
        self.assertTrue(self.window._copilot_has_changes())
        self.assertIn("其他程序修改", self.window.copilot_status.text())

    def test_clear_keeps_other_global_instructions(self):
        other = b"# Personal rules\nUse concise replies.\n"
        self.path.write_bytes(other)
        self.window._load_copilot_prompt()
        self.window._on_copilot_preset()
        self.assertTrue(self.window._save_copilot_prompt())
        self.window.btn_copilot_clear.click()
        self.assertTrue(self.window._save_copilot_prompt())
        self.assertEqual(self.path.read_bytes(), other)
        self.assertEqual(self.window.copilot_editor.toPlainText(), "")
        backups = list(self.directory.glob("copilot-instructions.md.bak-*"))
        self.assertEqual(len(backups), 2)

    def test_page_switch_keeps_unsaved_text(self):
        self.window.btn_copilot_preset.click()
        self.window._switch_page("汉化")
        self.window._switch_page("Copilot 提示词")
        self.assertEqual(self.window.copilot_editor.toPlainText(), ui.copilot_config.DEFAULT_COMMIT_INSTRUCTIONS)
        self.assertFalse(self.path.exists())

    def test_invalid_file_disables_writing(self):
        self.path.write_bytes(b"\xff\xfeinvalid")
        self.assertFalse(self.window._load_copilot_prompt())
        self.assertFalse(self.window.btn_copilot_save.isEnabled())
        self.assertFalse(self.window.btn_copilot_preset.isEnabled())
        self.assertTrue(self.window.copilot_editor.isReadOnly())

    def test_cancel_close_does_not_interrupt_worker(self):
        self.window.copilot_editor.setPlainText("尚未保存")
        worker = mock.Mock()
        worker.isRunning.return_value = True
        self.window._worker = worker
        event = QCloseEvent()
        with mock.patch.object(ui.QMessageBox, "exec", return_value=0):
            self.window.closeEvent(event)
        self.assertFalse(event.isAccepted())
        worker.isRunning.assert_not_called()
        worker.terminate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
