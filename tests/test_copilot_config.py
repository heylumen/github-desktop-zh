"""Global Copilot configuration tests; all writes stay in temporary folders."""

import codecs
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from gui import copilot_config as config


class CopilotConfigTests(unittest.TestCase):
    def setUp(self):
        test_root = Path(__file__).resolve().parent.parent / ".work"
        test_root.mkdir(exist_ok=True)
        self.workspace = tempfile.TemporaryDirectory(prefix="copilot-config-test-", dir=str(test_root))
        self.addCleanup(self.workspace.cleanup)
        self.home = Path(self.workspace.name)
        self.environment = mock.patch.dict(os.environ, {"COPILOT_HOME": ""})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.home_patch = mock.patch.object(config.Path, "home", return_value=self.home)
        self.home_patch.start()
        self.addCleanup(self.home_patch.stop)
        self.path = self.home / ".copilot" / "copilot-instructions.md"

    def write(self, content):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(content)

    def block(self, prompt, newline="\n"):
        return config.START_MARKER + newline + prompt + newline + config.END_MARKER

    def test_read_missing_does_not_create_directory(self):
        result = config.load_global_commit_instructions()
        self.assertEqual(result["path"], str(self.path))
        self.assertEqual(result["prompt"], "")
        self.assertEqual(result["other_instructions"], "")
        self.assertFalse(result["exists"])
        self.assertEqual(result["revision"], "missing")
        self.assertFalse(self.path.parent.exists())

    def test_absolute_environment_override_is_used(self):
        override = self.home / "copilot custom home"
        with mock.patch.dict(os.environ, {"COPILOT_HOME": str(override)}):
            result = config.save_global_commit_instructions("使用中文")
        self.assertEqual(result["path"], str(override / "copilot-instructions.md"))
        self.assertTrue((override / "copilot-instructions.md").exists())
        self.assertFalse(self.path.exists())

    def test_relative_environment_override_is_rejected(self):
        for value in ("relative/path", ".", " "):
            with self.subTest(value=value), mock.patch.dict(os.environ, {"COPILOT_HOME": value}):
                with self.assertRaisesRegex(ValueError, "绝对路径"):
                    config.load_global_commit_instructions()
        self.assertFalse(self.path.parent.exists())

    def test_load_without_block_preserves_other_text(self):
        original = "# Personal rules\r\nUse short answers.\r\n"
        self.write(codecs.BOM_UTF8 + original.encode("utf-8"))
        result = config.load_global_commit_instructions()
        self.assertEqual(result["prompt"], "")
        self.assertEqual(result["other_instructions"], original)
        self.assertEqual(result["revision"], hashlib.sha256(self.path.read_bytes()).hexdigest())

    def test_create_then_load_prompt(self):
        result = config.save_global_commit_instructions(config.DEFAULT_COMMIT_INSTRUCTIONS)
        self.assertTrue(result["changed"])
        self.assertIsNone(result["backup_path"])
        loaded = config.load_global_commit_instructions()
        self.assertEqual(loaded["prompt"], config.DEFAULT_COMMIT_INSTRUCTIONS)
        self.assertEqual(loaded["other_instructions"], "")

    def test_append_preserves_existing_content_and_bom_and_crlf(self):
        original = codecs.BOM_UTF8 + b"# Existing rules\r\nKeep this.\r\n"
        self.write(original)
        result = config.save_global_commit_instructions("第一行\n第二行")
        output = self.path.read_bytes()
        self.assertTrue(output.startswith(original))
        self.assertNotIn(b"\n", output.replace(b"\r\n", b""))
        self.assertEqual(Path(result["backup_path"]).read_bytes(), original)
        self.assertEqual(config.load_global_commit_instructions()["prompt"], "第一行\n第二行")

    def test_update_preserves_exact_bytes_outside_block(self):
        prefix = "# Rules\r\n\nKeep before.\r\n"
        suffix = "\r\nKeep after.\n"
        original = codecs.BOM_UTF8 + (prefix + self.block("旧内容", "\r\n") + suffix).encode("utf-8")
        self.write(original)
        result = config.save_global_commit_instructions("新内容\n另一行")
        expected = codecs.BOM_UTF8 + (prefix + self.block("新内容\r\n另一行", "\r\n") + suffix).encode("utf-8")
        self.assertEqual(self.path.read_bytes(), expected)
        self.assertEqual(Path(result["backup_path"]).read_bytes(), original)
        self.assertEqual(config.load_global_commit_instructions()["other_instructions"], prefix + suffix)

    def test_clear_removes_only_managed_span(self):
        prefix, suffix = "before\r\n", "\r\nafter\r\n"
        original = codecs.BOM_UTF8 + (prefix + self.block("待删除", "\r\n") + suffix).encode("utf-8")
        self.write(original)
        result = config.save_global_commit_instructions("  \n\t")
        self.assertTrue(result["changed"])
        self.assertEqual(self.path.read_bytes(), codecs.BOM_UTF8 + (prefix + suffix).encode("utf-8"))
        self.assertEqual(Path(result["backup_path"]).read_bytes(), original)

    def test_empty_missing_is_noop_and_creates_nothing(self):
        result = config.save_global_commit_instructions("")
        self.assertFalse(result["changed"])
        self.assertIsNone(result["backup_path"])
        self.assertFalse(self.path.parent.exists())

    def test_same_prompt_is_noop_without_new_backup(self):
        self.write(self.block("保留空白  \r\n\r\n第二段", "\r\n").encode("utf-8"))
        before = self.path.read_bytes()
        loaded = config.load_global_commit_instructions()
        result = config.save_global_commit_instructions(loaded["prompt"], expected_revision=loaded["revision"])
        self.assertFalse(result["changed"])
        self.assertIsNone(result["backup_path"])
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_backups_are_unique_and_original_backups_are_retained(self):
        first = b"Existing rules\n"
        self.write(first)
        one = config.save_global_commit_instructions("第一版")
        second = self.path.read_bytes()
        two = config.save_global_commit_instructions("第二版")
        self.assertNotEqual(one["backup_path"], two["backup_path"])
        self.assertEqual(Path(one["backup_path"]).read_bytes(), first)
        self.assertEqual(Path(two["backup_path"]).read_bytes(), second)

    def test_same_prompt_keeps_mixed_newlines_byte_for_byte(self):
        original = ("Other rules\n" + self.block("中文\r\n第二行", "\r\n") + "\nFooter\r\n").encode("utf-8")
        self.write(original)
        loaded = config.load_global_commit_instructions()
        result = config.save_global_commit_instructions(loaded["prompt"])
        self.assertFalse(result["changed"])
        self.assertIsNone(result["backup_path"])
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(len(list(self.path.parent.iterdir())), 1)

    def test_rejects_markers_inside_prompt_without_touching_file(self):
        self.write(b"Preserve me\n")
        for marker in (config.START_MARKER, config.END_MARKER):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(ValueError, "不能包含"):
                    config.save_global_commit_instructions("text " + marker)
        self.assertEqual(self.path.read_bytes(), b"Preserve me\n")
        self.assertEqual(len(list(self.path.parent.iterdir())), 1)

    def test_rejects_damaged_or_duplicate_existing_markers(self):
        damaged = [config.START_MARKER, config.END_MARKER,
                   "<!-- github-desktop-zh:commit-message:start",
                   config.END_MARKER + config.START_MARKER,
                   self.block("one") + self.block("two")]
        for content in damaged:
            with self.subTest(content=content):
                self.write(content.encode("utf-8"))
                with self.assertRaises(ValueError):
                    config.load_global_commit_instructions()
                with self.assertRaises(ValueError):
                    config.save_global_commit_instructions("new")
                self.assertEqual(self.path.read_bytes(), content.encode("utf-8"))
        self.assertEqual(len(list(self.path.parent.iterdir())), 1)

    def test_invalid_utf8_is_rejected_without_backup(self):
        self.write(b"invalid \xff")
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            config.load_global_commit_instructions()
        with self.assertRaisesRegex(ValueError, "UTF-8"):
            config.save_global_commit_instructions("new")
        self.assertEqual(self.path.read_bytes(), b"invalid \xff")
        self.assertEqual(len(list(self.path.parent.iterdir())), 1)

    def test_read_permission_error_is_clear_and_does_not_create_directory(self):
        with mock.patch.object(config.Path, "read_bytes", side_effect=PermissionError("denied")):
            with self.assertRaisesRegex(OSError, "无法读取.*copilot-instructions"):
                config.load_global_commit_instructions()
        self.assertFalse(self.path.parent.exists())

    def test_replace_failure_preserves_original_and_removes_staging_file(self):
        original = b"Personal rules\n"
        self.write(original)
        with mock.patch.object(config.os, "replace", side_effect=PermissionError("locked")):
            with self.assertRaisesRegex(OSError, "无法保存"):
                config.save_global_commit_instructions("new instructions")
        self.assertEqual(self.path.read_bytes(), original)
        backups = list(self.path.parent.glob("copilot-instructions.md.bak-*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertEqual(list(self.path.parent.glob(".copilot-instructions.md.tmp-*")), [])

    def test_backup_failure_preserves_original_and_never_replaces(self):
        original = b"Personal rules\n"
        self.write(original)
        with mock.patch.object(config, "_write_temporary", side_effect=OSError("disk full")), \
                mock.patch.object(config.os, "replace") as replace:
            with self.assertRaisesRegex(OSError, "无法保存"):
                config.save_global_commit_instructions("new instructions")
        replace.assert_not_called()
        self.assertEqual(self.path.read_bytes(), original)

    def test_revision_conflict_after_load_preserves_external_edit(self):
        self.write(b"Initial rules\n")
        loaded = config.load_global_commit_instructions()
        external = b"Changed by editor\n"
        self.path.write_bytes(external)
        with self.assertRaises(config.CopilotConfigConflictError):
            config.save_global_commit_instructions("new", expected_revision=loaded["revision"])
        self.assertEqual(self.path.read_bytes(), external)
        self.assertEqual(len(list(self.path.parent.iterdir())), 1)

    def test_missing_revision_detects_external_file_creation(self):
        loaded = config.load_global_commit_instructions()
        self.write(b"Created by editor\n")
        with self.assertRaises(config.CopilotConfigConflictError):
            config.save_global_commit_instructions("new", expected_revision=loaded["revision"])
        self.assertEqual(self.path.read_bytes(), b"Created by editor\n")

    def test_concurrent_edit_during_staging_is_preserved(self):
        self.write(b"Initial rules\n")
        write_temporary = config._write_temporary

        def external_edit(directory, prefix, content):
            temporary = write_temporary(directory, prefix, content)
            if ".tmp-" in prefix:
                self.path.write_bytes(b"Edited during save\n")
            return temporary

        with mock.patch.object(config, "_write_temporary", side_effect=external_edit), \
                mock.patch.object(config.os, "replace") as replace:
            with self.assertRaises(config.CopilotConfigConflictError):
                config.save_global_commit_instructions("new")
        replace.assert_not_called()
        self.assertEqual(self.path.read_bytes(), b"Edited during save\n")
        self.assertEqual(list(self.path.parent.glob(".copilot-instructions.md.tmp-*")), [])


if __name__ == "__main__":
    unittest.main()
