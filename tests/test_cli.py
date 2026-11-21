"""CLI 端到端：版本守护、退出码、路径归一、导入与更新器作用域。"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


def make_install(root, version="3.6.10", with_update=False):
    appdir = Path(root) / "Portable" / f"app-{version}" / "resources" / "app"
    appdir.mkdir(parents=True, exist_ok=True)
    (appdir / "main.js").write_text('"About GitHub Desktop"', encoding="utf-8")
    (appdir / "renderer.js").write_text('"Changes"', encoding="utf-8")
    (appdir / "package.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    if with_update:
        (appdir.parent.parent.parent / "Update.exe").write_bytes(b"update")
    return appdir


def run_cli(*args, env=None):
    merged = dict(os.environ)
    merged.update(env or {})
    merged["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, str(ROOT / "gui" / "cli.py"), *args],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT), env=merged)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="cli-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_versions_lists_builtin_versions(self):
        result = run_cli("versions")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("3.6.10", result.stdout)

    def test_locate_accepts_client_root_and_reports_portable(self):
        appdir = make_install(self.root)
        result = run_cli("locate", "--path", str(appdir.parent.parent.parent))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(appdir), result.stdout)
        self.assertIn("便携版：是", result.stderr)

    def test_apply_blocks_version_mismatch_by_default(self):
        appdir = make_install(self.root, version="3.6.9")
        before = (appdir / "main.js").read_text(encoding="utf-8")
        result = run_cli("apply", "--path", str(appdir), "--version", "3.6.10")
        self.assertEqual(result.returncode, 1)
        self.assertIn("不一致", result.stdout + result.stderr)
        self.assertEqual((appdir / "main.js").read_text(encoding="utf-8"), before)
        self.assertFalse((appdir / "main.js.bak").exists())

    def test_apply_and_restore_with_matching_version(self):
        appdir = make_install(self.root, version="3.6.10")
        applied = run_cli("apply", "--path", str(appdir), "--version", "3.6.10")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertIn("应用完成", applied.stdout)
        self.assertTrue((appdir / "main.js.bak").exists())

        restored = run_cli("restore", "--path", str(appdir))
        self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
        self.assertEqual((appdir / "main.js").read_text(encoding="utf-8"),
                         '"About GitHub Desktop"')

    def test_allow_mismatch_is_explicit(self):
        appdir = make_install(self.root, version="3.6.9")
        result = run_cli("apply", "--path", str(appdir), "--version", "3.6.10",
                         "--allow-mismatch")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("版本不一致", result.stdout)

    def test_update_on_portable_without_updater_fails_without_touching_default(self):
        appdir = make_install(self.root)
        result = run_cli("update", "--path", str(appdir), "--disable")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Update.exe", result.stdout + result.stderr)

    def test_import_command_writes_local_dictionary(self):
        source = Path(self.root) / "3.7.0"
        source.mkdir()
        (source / "main.js").write_text("imported main", encoding="utf-8")
        (source / "renderer.js").write_text("imported renderer", encoding="utf-8")
        local = Path(self.root) / "localdict"
        result = run_cli("import", "--source", str(source), "--version", "3.7.0",
                         env={"GITHUB_DESKTOP_ZH_LOCAL_DICT": str(local)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((local / "3.7.0" / "main.js").is_file())
        listed = run_cli("versions", env={"GITHUB_DESKTOP_ZH_LOCAL_DICT": str(local)})
        self.assertEqual(listed.returncode, 0)
        self.assertIn("3.7.0", listed.stdout)

    def test_restore_without_backup_is_non_zero(self):
        appdir = make_install(self.root)
        result = run_cli("restore", "--path", str(appdir))
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
