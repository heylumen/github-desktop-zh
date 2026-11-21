"""zhpaths: 安装归一化、版本识别、多安装排序与便携版布局。"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import zhpaths


def make_app(root, version="3.6.10", package=True, targets=True):
    appdir = Path(root) / "GitHubDesktop" / f"app-{version}" / "resources" / "app"
    appdir.mkdir(parents=True, exist_ok=True)
    if targets:
        (appdir / "main.js").write_text("main", encoding="utf-8")
        (appdir / "renderer.js").write_text("renderer", encoding="utf-8")
    if package:
        (appdir / "package.json").write_text(
            json.dumps({"name": "GitHub Desktop", "version": version}), encoding="utf-8")
    return appdir


class InstallDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zhpaths-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_normalizes_client_root_resources_and_app(self):
        appdir = make_app(self.root)
        deploy = appdir.parent.parent.parent
        for candidate in (appdir, appdir.parent, deploy):
            with self.subTest(candidate=candidate):
                info = zhpaths.inspect_install(candidate)
                self.assertEqual(info.layout, "unpacked")
                self.assertEqual(Path(info.appdir), appdir)
                self.assertEqual(info.version, "3.6.10")
                self.assertTrue(info.portable)

    def test_normalizes_client_exe_path(self):
        appdir = make_app(self.root)
        exe = appdir.parent.parent.parent / "GitHubDesktop.exe"
        exe.write_bytes(b"exe")
        info = zhpaths.inspect_install(exe)
        self.assertEqual(Path(info.appdir), appdir)
        self.assertEqual(info.version, "3.6.10")

    def test_package_version_wins_over_path_and_warns(self):
        appdir = make_app(self.root, version="3.6.9", package=False)
        (appdir / "package.json").write_text(
            json.dumps({"version": "3.6.10"}), encoding="utf-8")
        info = zhpaths.inspect_install(appdir)
        self.assertEqual(info.version, "3.6.10")
        self.assertEqual(info.path_version, "3.6.9")
        self.assertTrue(any("不一致" in warning for warning in info.warnings))

    def test_incomplete_and_asar_layouts(self):
        incomplete = Path(self.root) / "Incomplete" / "resources" / "app"
        incomplete.mkdir(parents=True)
        (incomplete / "main.js").write_text("only main", encoding="utf-8")
        info = zhpaths.inspect_install(incomplete)
        self.assertEqual(info.layout, "incomplete")
        self.assertIn("renderer.js", info.missing)

        asar_client = Path(self.root) / "Asar" / "resources"
        asar_client.mkdir(parents=True)
        (asar_client / "app.asar").write_bytes(b"asar")
        info = zhpaths.inspect_install(asar_client.parent)
        self.assertEqual(info.layout, "asar")
        self.assertFalse(info.available)

    def test_find_installs_sorted_latest_first(self):
        make_app(self.root / "A", "3.6.9")
        make_app(self.root / "B", "3.6.10")
        make_app(self.root / "C", "3.6.5")
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(self.root / "A")}), \
                mock.patch.object(zhpaths, "glob") as fake_glob:
            fake_glob.glob.return_value = [
                str(self.root / "A" / "GitHubDesktop" / "app-3.6.9" / "resources" / "app"),
                str(self.root / "B" / "GitHubDesktop" / "app-3.6.10" / "resources" / "app"),
                str(self.root / "C" / "GitHubDesktop" / "app-3.6.5" / "resources" / "app"),
            ]
            installs = zhpaths.find_installs()
            detected = zhpaths.autodetect_appdir()
        self.assertEqual([info.version for info in installs], ["3.6.10", "3.6.9", "3.6.5"])
        self.assertEqual(detected,
                         str(self.root / "B" / "GitHubDesktop" / "app-3.6.10"
                             / "resources" / "app"))

    def test_latest_sibling_follows_renamed_version_directory(self):
        old = make_app(self.root / "D", "3.6.9")
        new = make_app(self.root / "D", "3.6.10")
        self.assertEqual(Path(zhpaths.latest_sibling_appdir(old)), new)

    def test_invalid_path_reports_error_without_raising(self):
        info = zhpaths.inspect_install(str(self.root / "missing"))
        self.assertEqual(info.layout, "invalid")
        self.assertTrue(info.errors)
        self.assertIsNone(info.appdir)

    def test_version_name_and_sort_key(self):
        self.assertTrue(zhpaths.is_version_name("3.6.10"))
        self.assertFalse(zhpaths.is_version_name("v3.6"))
        self.assertGreater(zhpaths.version_key("3.6.10"), zhpaths.version_key("3.6.5"))


if __name__ == "__main__":
    unittest.main()
