"""zhtool: 校验退出码、清单缺失语义、应用失败可见、watch 跟随版本目录。"""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import zhtool  # noqa: E402


def make_app(root, version="3.6.10", main='"About GitHub Desktop"', renderer='"Changes"'):
    appdir = Path(root) / "GitHubDesktop" / f"app-{version}" / "resources" / "app"
    appdir.mkdir(parents=True, exist_ok=True)
    (appdir / "main.js").write_text(main, encoding="utf-8")
    (appdir / "renderer.js").write_text(renderer, encoding="utf-8")
    return appdir


def write_zh(path):
    path.write_text(
        '"About GitHub Desktop">*.*<"关于 GitHub Desktop">*.*<test>*.*<main.js\n'
        '"Changes">*.*<"变更">*.*<test>*.*<renderer.js\n',
        encoding="utf-8")


def run_zt(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "zhtool.py"), *args],
        capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT))


class ZhtoolCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zhtool-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.appdir = make_app(self.root)
        self.zh = self.root / "mini.zh"
        write_zh(self.zh)

    def test_apply_then_verify_then_mismatch(self):
        applied = run_zt("apply", "--appdir", str(self.appdir), "--zh", str(self.zh))
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertIn("关于 GitHub Desktop", (self.appdir / "main.js").read_text(encoding="utf-8"))
        self.assertTrue((self.appdir / "main.js.bak").exists())
        self.assertTrue((self.appdir / zhtool.MANIFEST_NAME).exists())

        verified = run_zt("verify", "--appdir", str(self.appdir))
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        self.assertIn("全部一致", verified.stdout)

        (self.appdir / "renderer.js").write_text('"Edited"', encoding="utf-8")
        mismatch = run_zt("verify", "--appdir", str(self.appdir))
        self.assertEqual(mismatch.returncode, 1)
        self.assertIn("存在差异", mismatch.stdout)

    def test_verify_without_manifest_is_not_reported_as_consistent(self):
        result = run_zt("verify", "--appdir", str(self.appdir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("未找到可对比的完整性清单", result.stdout)
        self.assertNotIn("全部一致", result.stdout)

    def test_dry_run_does_not_write(self):
        result = run_zt("apply", "--appdir", str(self.appdir), "--zh", str(self.zh), "--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.appdir / "main.js").read_text(encoding="utf-8"),
                         '"About GitHub Desktop"')
        self.assertFalse((self.appdir / "main.js.bak").exists())

    def test_watch_targets_follow_new_version_directory(self):
        old = make_app(self.root / "Multi", version="3.6.9")
        new = make_app(self.root / "Multi", version="3.6.10")
        args = argparse.Namespace(main=None, renderer=None)
        appdir, files = zhtool._resolve_watch_targets(str(old), args)
        self.assertEqual(Path(appdir), new)
        self.assertEqual({name for name, _ in files}, {"main.js", "renderer.js"})

    def test_apply_rejects_single_target_without_writing(self):
        target = str(self.appdir / "main.js")
        before = (self.appdir / "main.js").read_text(encoding="utf-8")
        manifest = zhtool.apply_to_files(
            [("main.js", target)], [str(self.zh)], False, log=lambda _line: None)
        self.assertFalse(manifest["ok"])
        self.assertEqual((self.appdir / "main.js").read_text(encoding="utf-8"), before)
        self.assertFalse((self.appdir / "main.js.bak").exists())

    def test_existing_backup_and_second_replace_failure_still_rolls_back(self):
        main = self.appdir / "main.js"
        renderer = self.appdir / "renderer.js"
        before_main = main.read_text(encoding="utf-8")
        before_renderer = renderer.read_text(encoding="utf-8")
        (self.appdir / "main.js.bak").write_text("old-main-backup", encoding="utf-8")
        (self.appdir / "renderer.js.bak").write_text("old-renderer-backup", encoding="utf-8")
        real_replace = os.replace

        def flaky_replace(src, dst):
            if str(dst).endswith("renderer.js") and ".zhtool-" in str(src):
                raise OSError("injected replace failure")
            return real_replace(src, dst)

        with mock.patch.object(zhtool.os, "replace", side_effect=flaky_replace):
            manifest = zhtool.apply_to_files(
                [("main.js", str(main)), ("renderer.js", str(renderer))],
                [str(self.zh)], False, log=lambda _line: None)
        self.assertFalse(manifest["ok"])
        self.assertEqual(main.read_text(encoding="utf-8"), before_main)
        self.assertEqual(renderer.read_text(encoding="utf-8"), before_renderer)
        self.assertEqual((self.appdir / "main.js.bak").read_text(encoding="utf-8"),
                         "old-main-backup")

    def test_wait_for_stable_returns_false_when_file_disappears(self):
        files = [("main.js", str(self.appdir / "main.js"))]
        (self.appdir / "main.js").unlink()
        self.assertFalse(zhtool._wait_for_stable(files, 0.3))


if __name__ == "__main__":
    unittest.main()
