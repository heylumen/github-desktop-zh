"""zhcore: 版本守护、事务写入/回滚、备份、还原、更新器作用域、字典导入与校验。"""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from gui import zhcore


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_install(root, version="3.6.10", package=True, targets=("main.js", "renderer.js"),
                 with_update=False):
    appdir = Path(root) / "Portable" / f"app-{version}" / "resources" / "app"
    appdir.mkdir(parents=True, exist_ok=True)
    for name in targets:
        write(appdir / name, f'"{name} original"')
    if package:
        write(appdir / "package.json", json.dumps({"version": version}))
    if with_update:
        (appdir.parent.parent.parent / "Update.exe").write_bytes(b"update")
    return appdir


def make_dictionary(root, version="3.6.10", main="patched main", renderer="patched renderer"):
    directory = Path(root) / "dict" / version
    write(directory / "main.js", main)
    write(directory / "renderer.js", renderer)
    return directory


class CoreTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="zhcore-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def patch_dictionary(self, version="3.6.10"):
        directory = make_dictionary(self.root, version)
        return mock.patch.object(
            zhcore, "dictionary_source",
            return_value={"source": "内置", "path": str(directory)})


class ApplyTests(CoreTestCase):
    def test_result_is_truthy_only_on_success(self):
        self.assertFalse(zhcore.OperationResult(False, "x"))
        self.assertTrue(zhcore.OperationResult(True, "x"))

    def test_apply_success_writes_both_files_backup_and_manifest(self):
        appdir = make_install(self.root)
        with self.patch_dictionary():
            result = zhcore.apply_version(appdir, "3.6.10")
        self.assertTrue(result.ok, result.details)
        self.assertEqual(result.code, "applied")
        self.assertEqual((appdir / "main.js").read_text(encoding="utf-8"), "patched main")
        self.assertEqual((appdir / "renderer.js").read_text(encoding="utf-8"), "patched renderer")
        self.assertEqual((appdir / "main.js.bak").read_text(encoding="utf-8"),
                         '"main.js original"')
        self.assertEqual((appdir / "renderer.js.bak").read_text(encoding="utf-8"),
                         '"renderer.js original"')
        manifest = json.loads((appdir / zhcore.BACKUP_MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual(manifest["dictionary_version"], "3.6.10")
        self.assertEqual(manifest["client_version"], "3.6.10")
        self.assertIn("main.js", manifest["files"])
        self.assertIn("renderer.js", manifest["files"])

    def test_version_mismatch_is_blocked_and_touches_nothing(self):
        appdir = make_install(self.root, version="3.6.9")
        with self.patch_dictionary():
            result = zhcore.apply_version(appdir, "3.6.10")
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "version_mismatch")
        self.assertEqual((appdir / "main.js").read_text(encoding="utf-8"), '"main.js original"')
        self.assertFalse((appdir / "main.js.bak").exists())

    def test_unknown_version_requires_explicit_override(self):
        target = Path(self.root) / "PortableNoVersion" / "resources" / "app"
        target.mkdir(parents=True)
        write(target / "main.js", '"About GitHub Desktop"')
        write(target / "renderer.js", '"Changes"')
        with self.patch_dictionary():
            blocked = zhcore.apply_version(target, "3.6.10")
            allowed = zhcore.apply_version(target, "3.6.10", allow_mismatch=True)
        self.assertFalse(blocked.ok)
        self.assertEqual(blocked.code, "version_mismatch")
        self.assertTrue(allowed.ok, allowed.details)
        self.assertTrue(any("未能确认" in warning for warning in allowed.warnings))

    def test_missing_renderer_rejects_before_any_write(self):
        appdir = make_install(self.root, targets=("main.js",))
        with self.patch_dictionary():
            result = zhcore.apply_version(appdir, "3.6.10")
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "target_missing")
        self.assertEqual((appdir / "main.js").read_text(encoding="utf-8"), '"main.js original"')
        self.assertFalse((appdir / "main.js.bak").exists())

    def test_missing_dictionary_file_rejects(self):
        appdir = make_install(self.root)
        directory = make_dictionary(self.root)
        (directory / "renderer.js").unlink()
        with mock.patch.object(zhcore, "dictionary_source",
                               return_value={"source": "内置", "path": str(directory)}):
            result = zhcore.apply_version(appdir, "3.6.10")
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "dictionary_incomplete")
        self.assertEqual((appdir / "main.js").read_text(encoding="utf-8"), '"main.js original"')

    def test_failure_on_second_replace_rolls_back_first(self):
        appdir = make_install(self.root)
        real_replace = os.replace

        def flaky_replace(src, dst):
            if (os.path.basename(dst) == "renderer.js"
                    and ".renderer.js.zh-new-" in os.path.basename(src)):
                raise OSError("simulated lock")
            return real_replace(src, dst)

        with self.patch_dictionary(), \
                mock.patch.object(zhcore.os, "replace", side_effect=flaky_replace):
            result = zhcore.apply_version(appdir, "3.6.10")
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "apply_failed")
        self.assertTrue(result.data.get("rolled_back"))
        self.assertEqual((appdir / "main.js").read_text(encoding="utf-8"), '"main.js original"')
        self.assertEqual((appdir / "renderer.js").read_text(encoding="utf-8"),
                         '"renderer.js original"')
        self.assertEqual(list(appdir.glob(".main.js.zh-new-*")), [])
        self.assertEqual(list(appdir.glob(".renderer.js.zh-new-*")), [])

    def test_second_apply_keeps_first_original_backup(self):
        appdir = make_install(self.root)
        first = make_dictionary(self.root, main="first main", renderer="first renderer")
        second = make_dictionary(self.root, version="3.6.10", main="second main",
                                 renderer="second renderer")
        with mock.patch.object(zhcore, "dictionary_source",
                               return_value={"source": "内置", "path": str(first)}):
            self.assertTrue(zhcore.apply_version(appdir, "3.6.10").ok)
        with mock.patch.object(zhcore, "dictionary_source",
                               return_value={"source": "内置", "path": str(second)}):
            self.assertTrue(zhcore.apply_version(appdir, "3.6.10").ok)
        self.assertEqual((appdir / "main.js").read_text(encoding="utf-8"), "second main")
        self.assertEqual((appdir / "main.js.bak").read_text(encoding="utf-8"),
                         '"main.js original"')


class RestoreTests(CoreTestCase):
    def test_restore_requires_complete_backup_pair(self):
        appdir = make_install(self.root)
        with self.patch_dictionary():
            self.assertTrue(zhcore.apply_version(appdir, "3.6.10").ok)
        (appdir / "renderer.js.bak").unlink()
        before = (appdir / "renderer.js").read_text(encoding="utf-8")
        result = zhcore.restore(appdir)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "backup_incomplete")
        self.assertEqual((appdir / "renderer.js").read_text(encoding="utf-8"), before)
        self.assertTrue((appdir / "main.js.bak").exists())

    def test_restore_returns_originals_and_cleans_manifest(self):
        appdir = make_install(self.root)
        with self.patch_dictionary():
            self.assertTrue(zhcore.apply_version(appdir, "3.6.10").ok)
        result = zhcore.restore(appdir)
        self.assertTrue(result.ok, result.details)
        self.assertEqual(result.code, "restored")
        self.assertEqual((appdir / "main.js").read_text(encoding="utf-8"), '"main.js original"')
        self.assertEqual((appdir / "renderer.js").read_text(encoding="utf-8"),
                         '"renderer.js original"')
        self.assertFalse((appdir / zhcore.BACKUP_MANIFEST_NAME).exists())
        self.assertFalse((appdir / "main.js.bak").exists())

    def test_restore_without_backups_is_explicit_failure(self):
        appdir = make_install(self.root)
        result = zhcore.restore(appdir)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "no_backup")


class UpdateTests(CoreTestCase):
    def test_update_operations_never_fall_back_to_other_install(self):
        chosen = make_install(self.root / "Custom", with_update=False)
        default = Path(self.root) / "LocalAppData" / "GitHubDesktop"
        default.mkdir(parents=True)
        (default / "Update.exe").write_bytes(b"default")
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(Path(self.root) / "LocalAppData")}), \
                mock.patch.object(zhcore, "autodetect_appdir",
                                  return_value=str(default.parent / "app-3.6.10" / "resources" / "app")):
            self.assertIsNone(zhcore.find_update_exe(str(chosen)))
            result = zhcore.set_auto_update_disabled(True, str(chosen))
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "update_missing")
        self.assertTrue((default / "Update.exe").exists())

    def test_update_state_machine_and_inconsistent_state(self):
        appdir = make_install(self.root, with_update=True)
        self.assertEqual(zhcore.update_state(appdir)["state"], "enabled")
        self.assertTrue(zhcore.set_auto_update_disabled(True, appdir).ok)
        self.assertEqual(zhcore.update_state(appdir)["state"], "disabled")
        self.assertTrue(zhcore.set_auto_update_disabled(False, appdir).ok)
        self.assertEqual(zhcore.update_state(appdir)["state"], "enabled")

        root = appdir.parent.parent.parent
        (root / "Update.exe.disabled").write_bytes(b"duplicate")
        self.assertEqual(zhcore.update_state(appdir)["state"], "inconsistent")
        result = zhcore.set_auto_update_disabled(True, appdir)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "update_inconsistent")
        self.assertTrue((root / "Update.exe").exists())
        self.assertTrue((root / "Update.exe.disabled").exists())


class DictionaryTests(CoreTestCase):
    def _patch_dictionary_root(self, root, local_root, manifest=None):
        dictionaries = Path(root) / "dictionaries"
        if manifest is not None:
            write(dictionaries / "manifest.json", json.dumps(manifest))

        def fake_resource(rel):
            return str(Path(root) / rel)

        return mock.patch.multiple(
            zhcore,
            resource=mock.Mock(side_effect=fake_resource),
            local_dict_dir=mock.Mock(return_value=str(local_root)),
        )

    def test_validate_dictionaries_detects_corruption(self):
        root = Path(self.root) / "builtin"
        local = Path(self.root) / "local"
        version = "3.6.10"
        write(root / "dictionaries" / version / "main.js", "main")
        write(root / "dictionaries" / version / "renderer.js", "renderer")
        hashes = {
            name: zhcore.sha256_file(root / "dictionaries" / version / name)
            for name in ("main.js", "renderer.js")
        }
        manifest = {"schema": 1, "versions": {version: {"files": {
            name: {"sha256": digest} for name, digest in hashes.items()}}}}
        with self._patch_dictionary_root(root, local, manifest):
            ok = zhcore.validate_dictionaries(log=lambda _m: None)
            self.assertTrue(ok.ok, ok.details)
            write(root / "dictionaries" / version / "renderer.js", "tampered")
            bad = zhcore.validate_dictionaries(log=lambda _m: None)
        self.assertFalse(bad.ok)
        self.assertEqual(bad.code, "dictionary_mismatch")

    def test_local_dictionary_is_reported_as_unverified(self):
        root = Path(self.root) / "builtin"
        local = Path(self.root) / "local"
        write(root / "dictionaries" / "3.6.10" / "main.js", "main")
        write(root / "dictionaries" / "3.6.10" / "renderer.js", "renderer")
        hashes = {
            name: zhcore.sha256_file(root / "dictionaries" / "3.6.10" / name)
            for name in ("main.js", "renderer.js")
        }
        manifest = {"schema": 1, "versions": {"3.6.10": {"files": {
            name: {"sha256": digest} for name, digest in hashes.items()}}}}
        write(local / "3.7.0" / "main.js", "local main")
        write(local / "3.7.0" / "renderer.js", "local renderer")
        with self._patch_dictionary_root(root, local, manifest):
            result = zhcore.validate_dictionaries(log=lambda _m: None)
        self.assertTrue(result.ok, result.details)
        self.assertIn("3.7.0", result.data["local"])


class ImportDictionaryTests(CoreTestCase):
    def test_imports_from_upstream_layout_and_infers_version(self):
        source = Path(self.root) / "Download" / "Version" / "3.6.11"
        write(source / "Windows" / "main.js", "imported main")
        write(source / "Windows" / "renderer.js", "imported renderer")
        local_root = Path(self.root) / "localdict"
        with mock.patch.object(zhcore, "local_dict_dir", return_value=str(local_root)):
            result = zhcore.import_local_dictionary(str(source), log=lambda _m: None)
            self.assertTrue(result.ok, result.details)
            self.assertEqual(result.data["version"], "3.6.11")
            self.assertTrue((local_root / "3.6.11" / "main.js").is_file())
            self.assertTrue((local_root / "3.6.11" / "renderer.js").is_file())
            record = json.loads((local_root / "3.6.11" / "local-import.json").read_text(encoding="utf-8"))
            self.assertEqual(record["version"], "3.6.11")
            self.assertTrue(record["verified"])

            # 再次导入同版本：旧本地字典需保留为备份
            write(source / "Windows" / "renderer.js", "imported renderer v2")
            second = zhcore.import_local_dictionary(str(source), log=lambda _m: None)
            self.assertTrue(second.ok, second.details)
            backups = [p for p in local_root.iterdir() if p.name.startswith("3.6.11.bak-")]
            self.assertEqual(len(backups), 1)
            self.assertEqual((local_root / "3.6.11" / "renderer.js").read_text(encoding="utf-8"),
                             "imported renderer v2")

    def test_rejects_folder_without_pair_and_ambiguous_candidates(self):
        empty = Path(self.root) / "empty"
        empty.mkdir()
        local_root = Path(self.root) / "localdict"
        with mock.patch.object(zhcore, "local_dict_dir", return_value=str(local_root)):
            result = zhcore.import_local_dictionary(str(empty), log=lambda _m: None)
            self.assertFalse(result.ok)
            self.assertEqual(result.code, "source_invalid")

            ambiguous = Path(self.root) / "ambiguous"
            for name in ("3.6.10", "3.6.11"):
                write(ambiguous / name / "main.js", "m")
                write(ambiguous / name / "renderer.js", "r")
            result = zhcore.import_local_dictionary(str(ambiguous), log=lambda _m: None)
            self.assertFalse(result.ok)
            self.assertEqual(result.code, "source_invalid")

    def test_non_javascript_content_is_imported_with_warning(self):
        source = Path(self.root) / "html" / "3.6.11"
        write(source / "main.js", "<html>not found</html>")
        write(source / "renderer.js", "<html>not found</html>")
        local_root = Path(self.root) / "localdict"
        with mock.patch.object(zhcore, "local_dict_dir", return_value=str(local_root)):
            result = zhcore.import_local_dictionary(str(source), log=lambda _m: None)
        self.assertTrue(result.ok)
        self.assertFalse(result.data["verified"])
        self.assertTrue(result.warnings)


class LocateTests(CoreTestCase):
    def test_preferred_portable_path_wins_over_default(self):
        portable = make_install(self.root / "PortableRoot", version="3.6.10")
        default = make_install(self.root / "Default", version="3.6.10")
        with mock.patch.object(zhcore, "autodetect_appdir", return_value=str(default)):
            self.assertEqual(Path(zhcore.locate(str(portable))), portable)
            self.assertEqual(Path(zhcore.locate(str(self.root / "missing"))), default)


if __name__ == "__main__":
    unittest.main()
