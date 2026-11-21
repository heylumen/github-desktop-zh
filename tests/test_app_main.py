"""GUI 主流程：便携版归一、版本守护、结果反馈、启动副作用与汉化包导入。"""
import json
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
    from PySide6.QtCore import Qt, QSettings
    import PySide6  # noqa: F401
except ImportError:
    ui = None
    Qt = None
    QSettings = None
else:
    import app as ui


def make_install(root, version="3.6.10", with_update=False):
    appdir = Path(root) / "Portable" / f"app-{version}" / "resources" / "app"
    appdir.mkdir(parents=True, exist_ok=True)
    (appdir / "main.js").write_text('"About GitHub Desktop"', encoding="utf-8")
    (appdir / "renderer.js").write_text('"Changes"', encoding="utf-8")
    (appdir / "package.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    if with_update:
        (appdir.parent.parent.parent / "Update.exe").write_bytes(b"update")
    return appdir


@unittest.skipIf(ui is None, "PySide6 is required for GUI checks")
class MainFlowGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qapp = ui.QApplication.instance() or ui.QApplication([])
        # 必须在 QApplication 创建之后再设置，否则 Windows 仍会写注册表
        QSettings.setDefaultFormat(QSettings.IniFormat)
        settings = ROOT / ".work" / "test-settings"
        settings.mkdir(parents=True, exist_ok=True)
        QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(settings))
        QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, str(settings))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="main-gui-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.local_dict = self.root / "localdict"
        env = {
            "GITHUB_DESKTOP_ZH_LOCAL_DICT": str(self.local_dict),
            "GITHUB_DESKTOP_ZH_LOG_DIR": str(self.root / "logs"),
        }
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.patches = [
            mock.patch.object(ui.App, "_detect_system_theme", return_value="light"),
            mock.patch.object(ui.App, "_refresh_path"),
            mock.patch.object(ui.App, "_remember_install"),
            mock.patch.object(ui.App, "_last_install", return_value=""),
            mock.patch.object(ui.zhcore, "update_state",
                              return_value={"state": "missing", "deploy_root": None}),
        ]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.window = ui.App()
        self.addCleanup(self._close)

    def _close(self):
        self.window.copilot_editor.setPlainText(self.window._copilot_loaded_text)
        self.window._worker = None
        self.window.close()
        self.qapp.processEvents()

    def test_portable_root_is_normalized_and_version_selected(self):
        appdir = make_install(self.root)
        info = self.window._apply_selected_path(str(appdir.parent.parent.parent))
        self.assertTrue(info.available)
        self.assertEqual(Path(self.window.path_var.text()), appdir)
        self.assertEqual(self.window._version_combo.currentText(), "3.6.10")
        self.assertTrue(self.window.btn_apply.isEnabled())
        self.assertIn("便携版", self.window._path_pill.text())

    def test_version_mismatch_disables_and_blocks_apply(self):
        appdir = make_install(self.root, version="3.6.9")
        self.window._apply_selected_path(str(appdir))
        self.assertFalse(self.window.btn_apply.isEnabled())
        self.assertIn("尚未导入", self.window._version_hint.text())

        self.window._version_combo.setCurrentText("3.6.10")
        self.window._update_version_hint()
        self.assertFalse(self.window.btn_apply.isEnabled())
        self.assertIn("尚未导入", self.window._version_hint.text())

        with mock.patch.object(ui.QMessageBox, "critical") as critical, \
                mock.patch.object(self.window, "_run") as run:
            self.window._on_apply()
        critical.assert_called_once()
        run.assert_not_called()

    def test_asar_install_is_reported_as_unsupported(self):
        resources = self.root / "Asar" / "resources"
        resources.mkdir(parents=True)
        (resources / "app.asar").write_bytes(b"asar")
        info = self.window._apply_selected_path(str(resources.parent))
        self.assertEqual(info.layout, "asar")
        self.assertIn("app.asar", self.window._path_pill.text())
        self.assertFalse(self.window.btn_apply.isEnabled())

    def test_worker_failure_is_surfaced_not_shown_as_ready(self):
        result = ui.zhcore.OperationResult(
            False, "apply_failed", "写入失败", details=["✗ [错误] 写入失败"])
        with mock.patch.object(ui.QMessageBox, "critical") as critical:
            self.window._on_worker_done(result)
        critical.assert_called_once()
        self.assertEqual(self.window.statusBar().currentMessage(), "操作失败")

    def test_worker_success_mentions_restart(self):
        result = ui.zhcore.OperationResult(True, "applied", "",
                                          details=["=== 应用完成 ==="])
        self.window._on_worker_done(result)
        self.assertIn("重新打开", self.window.statusBar().currentMessage())

    def test_refresh_update_state_never_mutates_updater(self):
        appdir = make_install(self.root, with_update=True)
        self.window._apply_selected_path(str(appdir))
        with mock.patch.object(ui.zhcore, "update_state",
                               return_value={"state": "enabled", "deploy_root": "X"}), \
                mock.patch.object(ui.zhcore, "set_auto_update_disabled") as setter:
            self.window._refresh_update_pill()
        setter.assert_not_called()
        self.assertEqual(self.window._update_pill.text(), "允许更新")

    def test_local_dictionary_requires_confirmation(self):
        appdir = make_install(self.root)
        self.window._apply_selected_path(str(appdir))
        with mock.patch.object(ui.zhcore, "dictionary_source",
                               return_value={"source": "本地", "path": str(self.local_dict)}), \
                mock.patch.object(ui.QMessageBox, "question",
                                  return_value=ui.QMessageBox.No) as question, \
                mock.patch.object(self.window, "_run") as run:
            self.window._on_apply()
        question.assert_called_once()
        run.assert_not_called()

    def test_import_dictionary_creates_version_and_selects_it(self):
        source = self.root / "download" / "3.7.0"
        source.mkdir(parents=True)
        (source / "main.js").write_text("imported main", encoding="utf-8")
        (source / "renderer.js").write_text("imported renderer", encoding="utf-8")
        with mock.patch.object(ui.QFileDialog, "getExistingDirectory",
                               return_value=str(source)), \
                mock.patch.object(ui.QInputDialog, "getText",
                                  return_value=("3.7.0", True)), \
                mock.patch.object(ui.QMessageBox, "question",
                                  return_value=ui.QMessageBox.Yes), \
                mock.patch.object(ui.QMessageBox, "information"):
            self.window._on_import_dict()
        self.assertTrue((self.local_dict / "3.7.0" / "main.js").is_file())
        self.assertIn("3.7.0", [
            self.window._version_combo.itemText(i)
            for i in range(self.window._version_combo.count())])
        self.assertEqual(self.window._version_combo.currentText(), "3.7.0")

    def test_navigation_and_switch_are_keyboard_focusable(self):
        for button in self.window._nav.values():
            self.assertNotEqual(button.focusPolicy(), Qt.NoFocus)
        self.assertNotEqual(self.window.sw_disable_update.focusPolicy(), Qt.NoFocus)

    def test_frameless_window_has_titlebar_and_resize_handles(self):
        self.assertTrue(self.window.windowFlags() & Qt.FramelessWindowHint)
        self.assertEqual(self.window._titlebar.HEIGHT, 40)
        self.assertEqual(len(self.window._resize_handles), 8)
        self.assertEqual(self.window._titlebar.close_btn.accessibleName(), "关闭")

    def test_version_selector_uses_chips_for_two_versions(self):
        versions = ["3.6.10", "3.6.7"]
        with mock.patch.object(ui.zhcore, "list_versions", return_value=versions):
            self.window._refresh_versions()
        self.assertFalse(self.window._version_chips.isHidden())
        self.assertTrue(self.window._version_combo.isHidden())
        self.assertEqual(len(self.window._version_chip_group.buttons()), 2)
        self.assertEqual(self.window._version_combo.currentText(), "3.6.10")
        second = [b for b in self.window._version_chip_group.buttons()
                  if b.text() == "3.6.7"][0]
        second.click()
        self.assertEqual(self.window._version_combo.currentText(), "3.6.7")

    def test_version_selector_uses_combo_above_three_versions(self):
        versions = ["3.6.10", "3.6.7", "3.6.6", "3.6.5"]
        with mock.patch.object(ui.zhcore, "list_versions", return_value=versions):
            self.window._refresh_versions()
        self.assertTrue(self.window._version_chips.isHidden())
        self.assertFalse(self.window._version_combo.isHidden())
        self.assertEqual(self.window._version_combo.count(), 4)

    def test_version_selector_handles_zero_versions(self):
        with mock.patch.object(ui.zhcore, "list_versions", return_value=[]):
            self.window._refresh_versions()
        self.assertTrue(self.window._version_chips.isHidden())
        self.assertEqual(self.window._version_combo.count(), 0)

    def test_version_selector_disables_with_busy(self):
        with mock.patch.object(ui.zhcore, "list_versions",
                               return_value=["3.6.10", "3.6.7"]):
            self.window._refresh_versions()
        self.window._set_busy(True)
        self.assertFalse(self.window._version_chips.isEnabled())
        self.window._set_busy(False)
        self.assertTrue(self.window._version_chips.isEnabled())

    def test_about_distinguishes_bundled_and_repository_versions(self):
        page = self.window._pages["关于"].widget()
        text = "\n".join(label.text() for label in page.findChildren(ui.QLabel))
        self.assertIn("EXE 内置最新 2 版", text)
        self.assertIn("来源说明：3.5.0–3.6.7 采用", text)
        self.assertNotIn("未内置的新版本可在", text)

    def test_theme_follows_system_without_manual_switch(self):
        self.assertFalse(hasattr(self.window, "_theme_group"))
        self.assertFalse(hasattr(self.window, "effect_combo"))
        with mock.patch.object(ui.App, "_detect_system_theme", return_value="dark"):
            self.window._on_system_theme_changed()
        self.assertEqual(self.window._theme, "dark")
        with mock.patch.object(ui.App, "_detect_system_theme", return_value="light"):
            self.window._on_system_theme_changed()
        self.assertEqual(self.window._theme, "light")


if __name__ == "__main__":
    unittest.main()
