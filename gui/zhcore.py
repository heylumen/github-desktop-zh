#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zhcore.py — 汉化工具核心逻辑（无 UI 依赖，可独立测试）。

设计要点：
- 路径与版本事实统一来自 ``zhpaths``，支持官方安装与便携/绿色版。
- 任何写操作都返回 ``OperationResult``，失败必须可被 GUI/CLI 看见。
- 应用汉化采用“备份 → 暂存 → 双文件替换 → 失败回滚”的事务流程。
- 自动更新操作严格限定在指定安装，绝不回退修改另一份安装。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import zhpaths
from zhpaths import (
    BACKUP_MANIFEST_NAME,
    TARGETS,
    autodetect_appdir,
    inspect_install,
    sha256_file,
    version_key,
)

DICTIONARY_MANIFEST = "manifest.json"
LOCAL_IMPORT_RECORD = "local-import.json"


@dataclass
class OperationResult:
    """可被 GUI 与 CLI 共同消费的结构化结果。"""

    ok: bool
    code: str
    message: str = ""
    details: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)

    def __bool__(self):
        return self.ok

    def emit(self, log=print):
        for line in self.details:
            log(line)
        for line in self.warnings:
            log("⚠ " + line)
        if self.message:
            log(self.message)
        return self


def _result(ok, code, message="", details=None, warnings=None, data=None):
    return OperationResult(bool(ok), code, message, list(details or []),
                           list(warnings or []), dict(data or {}))


def _now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def resource(rel):
    """解析打包后的资源路径：冻结态用 _MEIPASS，开发态用仓库根。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, rel)
    return os.path.join(REPO_ROOT, rel)


def local_dict_dir():
    """用户本地字典目录。

    - 打包后：EXE 同级 ``dictionaries/``；
    - 源码运行：仓库根 ``local-dictionaries/``（避免写进 venv 的 Scripts 目录）；
    - ``GITHUB_DESKTOP_ZH_LOCAL_DICT`` 可覆盖（测试与高级部署用）。
    """
    override = os.environ.get("GITHUB_DESKTOP_ZH_LOCAL_DICT")
    if override:
        return os.path.abspath(os.path.expanduser(override))
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "dictionaries")
    return os.path.join(REPO_ROOT, "local-dictionaries")


# --------------------------------------------------------------------------
# 字典发现与完整性
# --------------------------------------------------------------------------
def _scan_dict_dirs():
    vers = {}
    for base, source in ((resource("dictionaries"), "内置"),
                         (local_dict_dir(), "本地")):
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            directory = os.path.join(base, name)
            if (os.path.isdir(directory)
                    and all(os.path.isfile(os.path.join(directory, t)) for t in TARGETS)):
                vers[name] = source
    return vers


def list_versions():
    return sorted(_scan_dict_dirs().keys(), key=version_key, reverse=True)


def list_version_sources():
    vers = _scan_dict_dirs()
    return [(v, vers[v]) for v in sorted(vers.keys(), key=version_key, reverse=True)]


def dictionary_source(version):
    """返回 ``{"source", "path"}``；同名时本地优先。"""
    local = os.path.join(local_dict_dir(), version)
    if all(os.path.isfile(os.path.join(local, t)) for t in TARGETS):
        return {"source": "本地", "path": local}
    builtin = resource(os.path.join("dictionaries", version))
    if all(os.path.isfile(os.path.join(builtin, t)) for t in TARGETS):
        return {"source": "内置", "path": builtin}
    return None


def version_file(version, target):
    info = dictionary_source(version)
    if not info:
        return None
    path = os.path.join(info["path"], target)
    return path if os.path.isfile(path) else None


def load_dictionary_manifest():
    path = resource(os.path.join("dictionaries", DICTIONARY_MANIFEST))
    if not os.path.isfile(path):
        return None, path
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        return {"__error__": str(error)}, path
    return data, path


def _manifest_entry(manifest, version):
    if not isinstance(manifest, dict):
        return None
    versions = manifest.get("versions")
    if not isinstance(versions, dict):
        return None
    entry = versions.get(version)
    return entry if isinstance(entry, dict) else None


def _verify_path_with_entry(path, entry):
    for target in TARGETS:
        actual_path = os.path.join(path, target)
        if not os.path.isfile(actual_path):
            return False
        expected = None
        if entry and isinstance(entry.get("files"), dict):
            expected = (entry["files"].get(target) or {}).get("sha256")
        if not expected or str(expected).lower() != sha256_file(actual_path):
            return False
    return True


def dictionary_snapshot(version):
    """返回字典来源与文件散列，供 UI 展示来源/信任状态。"""
    info = dictionary_source(version)
    if not info:
        return None
    files = {}
    for target in TARGETS:
        path = os.path.join(info["path"], target)
        files[target] = {"path": path, "size": os.path.getsize(path),
                         "sha256": sha256_file(path)}
    return {"version": version, "source": info["source"], "path": info["path"],
            "files": files}


def validate_dictionaries(log=print):
    """校验全部内置字典散列，并显式区分未验证的本地字典。"""
    manifest, manifest_path = load_dictionary_manifest()
    if manifest is None:
        return _result(False, "manifest_missing",
                       f"✗ [错误] 缺少字典清单：{manifest_path}").emit(log)
    if "__error__" in manifest:
        return _result(False, "manifest_invalid",
                       f"✗ [错误] 字典清单无法解析：{manifest['__error__']}").emit(log)

    builtin_root = resource("dictionaries")
    builtin_versions = []
    if os.path.isdir(builtin_root):
        for name in os.listdir(builtin_root):
            directory = os.path.join(builtin_root, name)
            if (os.path.isdir(directory)
                    and all(os.path.isfile(os.path.join(directory, t)) for t in TARGETS)):
                builtin_versions.append(name)
    builtin_versions.sort(key=version_key, reverse=True)

    details = [f"字典清单：{manifest_path}"]
    failures = []
    for version in builtin_versions:
        entry = _manifest_entry(manifest, version)
        if _verify_path_with_entry(os.path.join(builtin_root, version), entry):
            details.append(f"  ✓ {version} · 内置散列一致")
        else:
            failures.append(version)
            details.append(f"  ✗ {version} · 内置散列不一致或清单缺失")

    local_root = local_dict_dir()
    local_versions = []
    if os.path.isdir(local_root):
        for name in os.listdir(local_root):
            directory = os.path.join(local_root, name)
            if (os.path.isdir(directory)
                    and all(os.path.isfile(os.path.join(directory, t)) for t in TARGETS)):
                local_versions.append(name)
    local_versions.sort(key=version_key, reverse=True)
    for version in local_versions:
        details.append(f"  ⚠ {version} · 本地字典（来源未验证）")

    ok = not failures
    if ok:
        details.append(f"结论：内置 {len(builtin_versions)} 个版本散列校验通过"
                       + (f"；本地 {len(local_versions)} 个版本未验证" if local_versions else ""))
    else:
        details.append(f"结论：{len(failures)} 个内置版本校验失败：{', '.join(failures)}")
    return _result(ok, "dictionary_ok" if ok else "dictionary_mismatch", "",
                   details=details,
                   data={"builtin": builtin_versions, "local": local_versions,
                         "failures": failures}).emit(log)


def validate_builtin(log=print):
    """兼容旧调用：返回布尔值。"""
    return validate_dictionaries(log=log).ok


# --------------------------------------------------------------------------
# 安装发现与版本
# --------------------------------------------------------------------------
def locate(preferred=None):
    """自动定位安装；``preferred`` 是用户上次使用/手选的路径，优先验证。"""
    if preferred:
        info = inspect_install(preferred)
        if info.available and info.appdir:
            return info.appdir
    return autodetect_appdir()


def detect_version(appdir):
    return inspect_install(appdir).version


def install_info(appdir):
    return inspect_install(appdir)


def list_installs(extra=()):
    return zhpaths.find_installs(extra)


# --------------------------------------------------------------------------
# 原子文件工具
# --------------------------------------------------------------------------
def _write_temp(directory, prefix, data, mode=None):
    descriptor, filename = tempfile.mkstemp(dir=str(directory), prefix=prefix)
    path = str(filename)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if mode is not None:
            os.chmod(path, stat.S_IMODE(mode))
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise
    return path


def _atomic_write(dst, data, mode=None):
    directory = os.path.dirname(dst) or "."
    temp = _write_temp(directory, "." + os.path.basename(dst) + ".tmp-", data, mode)
    try:
        os.replace(temp, dst)
    except BaseException:
        try:
            os.unlink(temp)
        except OSError:
            pass
        raise


def _sha256_bytes(data):
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _read_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


# --------------------------------------------------------------------------
# 应用 / 还原
# --------------------------------------------------------------------------
def _unsupported_install(info):
    lines = ["✗ [错误] 该目录不是可改写的 GitHub Desktop 安装。"]
    lines.extend("  · " + e for e in info.errors)
    if info.layout == "asar":
        lines.append("  · 便携版若以 app.asar 打包，请改用解包版或官方安装包后再汉化。")
    return _result(False, "unsupported_install", "", details=lines,
                   data={"install": info.as_dict()})


def _version_guard(info, version, allow_mismatch):
    """返回 (ok, warnings, message)。版本未知或与选择不符默认拒绝。"""
    warnings = []
    if info.version is None:
        if not allow_mismatch:
            return False, warnings, (
                "无法从 package.json 或 app-X.Y.Z 目录确认客户端版本。"
                "请选择包含版本信息的目录，或确认风险后强制继续。")
        warnings.append("未能确认客户端版本，已按用户确认强制继续。")
        return True, warnings, ""
    if info.version != version:
        if not allow_mismatch:
            return False, warnings, (
                f"客户端版本 {info.version} 与所选汉化版本 {version} 不一致。"
                "为避免客户端无法启动，已阻止写入。")
        warnings.append(f"版本不一致：客户端 {info.version}，所选 {version}。")
    return True, warnings, ""


def apply_version(appdir, version, log=print, allow_mismatch=False):
    """把指定版本字典事务式应用到安装目录。

    返回 ``OperationResult``（可用作布尔值）。只有两个文件都成功替换才算成功。
    """
    info = inspect_install(appdir)
    details = [f"目标安装：{info.appdir or info.requested}"]
    if info.portable:
        details.append("  · 检测到非默认目录安装（便携版/绿色版）")
    if info.version:
        details.append(f"  · 客户端版本：{info.version}（来源：{info.version_source}）")
    for warning in info.warnings:
        details.append("  ⚠ " + warning)
    if info.layout == "incomplete":
        details.append("✗ [错误] 安装目录缺少：" + "、".join(info.missing)
                       + "；为保持两个文件一致，未写入任何文件")
        return _result(False, "target_missing", "", details=details).emit(log)
    if not info.available:
        return _unsupported_install(info).emit(log)
    if not info.appdir:
        return _result(False, "appdir_missing", "无法定位安装目录",
                       details=details).emit(log)

    guard_ok, warnings, guard_message = _version_guard(info, version, allow_mismatch)
    if not guard_ok:
        return _result(False, "version_mismatch", "✗ [错误] " + guard_message,
                       details=details, warnings=warnings).emit(log)

    source = dictionary_source(version)
    if not source:
        details.append(f"✗ [错误] 未找到汉化版本 {version} 的 main.js / renderer.js")
        return _result(False, "dictionary_missing", "", details=details).emit(log)
    details.append(f"  · 字典来源：{source['source']} · {source['path']}")

    destinations = {}
    for target in TARGETS:
        dst = os.path.join(info.appdir, target)
        if not os.path.isfile(dst):
            details.append(f"✗ [错误] 安装目录缺少 {target}，未写入任何文件")
            return _result(False, "target_missing", "", details=details).emit(log)
        destinations[target] = dst

    source_paths = {}
    for target in TARGETS:
        path = os.path.join(source["path"], target)
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            details.append(f"✗ [错误] 字典缺少有效的 {target}")
            return _result(False, "dictionary_incomplete", "", details=details).emit(log)
        source_paths[target] = path

    originals, modes, original_hashes = {}, {}, {}
    try:
        for target, dst in destinations.items():
            originals[target] = _read_bytes(dst)
            original_hashes[target] = _sha256_bytes(originals[target])
            modes[target] = os.stat(dst).st_mode
    except OSError as error:
        details.append(f"✗ [错误] 无法读取目标文件，已中止：{error}")
        return _result(False, "read_failed", "", details=details).emit(log)

    backup_paths, created_backups = {}, []
    temps, replaced = {}, []
    started = time.time()
    try:
        for target, dst in destinations.items():
            backup = dst + ".bak"
            backup_paths[target] = backup
            if not os.path.isfile(backup):
                _atomic_write(backup, originals[target], modes[target])
                created_backups.append(target)
                details.append(f"  ✓ 已备份原文件 -> {backup}")
            else:
                details.append(f"  · 保留已有备份 -> {backup}")
        for target in TARGETS:
            temps[target] = _write_temp(
                info.appdir, "." + target + ".zh-new-",
                _read_bytes(source_paths[target]), modes[target])
        # 暂存期间若目标被其他程序改动，拒绝覆盖。
        for target, dst in destinations.items():
            if sha256_file(dst) != original_hashes[target]:
                raise RuntimeError(f"{target} 在应用过程中被其他程序修改，已中止。")
        for target in TARGETS:
            os.replace(temps[target], destinations[target])
            temps.pop(target, None)
            replaced.append(target)
        for target in TARGETS:
            if sha256_file(destinations[target]) != sha256_file(source_paths[target]):
                raise RuntimeError(f"{target} 写入后散列不一致。")
    except BaseException as error:
        rollback_errors = []
        for target in replaced:
            try:
                _atomic_write(destinations[target], originals[target], modes[target])
            except OSError as restore_error:
                rollback_errors.append(f"{target}: {restore_error}")
        for temp in temps.values():
            try:
                os.unlink(temp)
            except OSError:
                pass
        if replaced:
            details.append("  ↩ 已回滚本次已替换的文件")
        details.append(f"✗ [错误] 应用失败：{error}")
        if rollback_errors:
            details.append("  ⚠ 自动回滚未完成，请用 .bak 手动恢复：" + "; ".join(rollback_errors))
        return _result(False, "apply_failed", "", details=details, warnings=warnings,
                       data={"rolled_back": bool(replaced) and not rollback_errors}).emit(log)

    for target in TARGETS:
        details.append(f"  ✓ 已应用 {version} 的 {target}")
    backup_manifest = {
        "schema": 1,
        "applied_at": _now(),
        "client_version": info.version,
        "dictionary_version": version,
        "dictionary_source": source["source"],
        "dictionary_path": source["path"],
        "portable": info.portable,
        "files": {
            target: {
                "patched_sha256": sha256_file(destinations[target]),
                "current_before_sha256": original_hashes[target],
                "backup_path": backup_paths[target],
                "backup_sha256": sha256_file(backup_paths[target])
                if os.path.isfile(backup_paths[target]) else None,
                "backup_created": target in created_backups,
            }
            for target in TARGETS
        },
    }
    manifest_path = os.path.join(info.appdir, BACKUP_MANIFEST_NAME)
    try:
        _atomic_write(manifest_path,
                      json.dumps(backup_manifest, ensure_ascii=False, indent=2).encode("utf-8"))
        details.append(f"  ✓ 已写入备份清单 -> {manifest_path}")
    except OSError as error:
        warnings.append(f"备份清单写入失败（不影响汉化结果）：{error}")

    elapsed = time.time() - started
    details.append(
        f"=== 应用完成（客户端 {info.version or '未知'} · 汉化 {version} · {elapsed:.2f}s）===")
    return _result(True, "applied", "", details=details, warnings=warnings,
                   data={"backup_manifest": manifest_path,
                         "backup_paths": backup_paths,
                         "dictionary_source": source["source"]}).emit(log)


def restore(appdir, log=print):
    """从 .bak 事务式还原两个文件。只有全部必需文件还原成功才算成功。"""
    info = inspect_install(appdir)
    details = [f"目标安装：{info.appdir or info.requested}"]
    if not info.available:
        return _unsupported_install(info).emit(log)
    if not info.appdir:
        return _result(False, "appdir_missing", "无法定位安装目录", details=details).emit(log)
    destinations = {target: os.path.join(info.appdir, target) for target in TARGETS}
    backups, missing = {}, []
    for target, dst in destinations.items():
        backup = dst + ".bak"
        if os.path.isfile(backup):
            backups[target] = backup
        else:
            missing.append(target)
    if not backups:
        details.append("· 未找到 .bak 备份，可能已是英文原版")
        return _result(False, "no_backup", "", details=details).emit(log)
    if missing:
        details.append("⚠ 缺少备份：" + "、".join(missing) + "；为保持两个文件一致，未执行还原")
        return _result(False, "backup_incomplete", "", details=details).emit(log)

    originals, modes, temps, replaced = {}, {}, {}, []
    try:
        for target in TARGETS:
            dst = destinations[target]
            originals[target] = _read_bytes(dst) if os.path.isfile(dst) else b""
            modes[target] = os.stat(dst).st_mode if os.path.isfile(dst) else 0o666
            temps[target] = _write_temp(
                info.appdir, "." + target + ".restore-",
                _read_bytes(backups[target]), modes[target])
        for target in TARGETS:
            os.replace(temps[target], destinations[target])
            temps.pop(target, None)
            replaced.append(target)
        for target in TARGETS:
            if sha256_file(destinations[target]) != sha256_file(backups[target]):
                raise RuntimeError(f"{target} 还原后散列不一致。")
    except BaseException as error:
        rollback_errors = []
        for target in replaced:
            if originals[target]:
                try:
                    _atomic_write(destinations[target], originals[target], modes[target])
                except OSError as restore_error:
                    rollback_errors.append(f"{target}: {restore_error}")
        for temp in temps.values():
            try:
                os.unlink(temp)
            except OSError:
                pass
        details.append(f"✗ [错误] 还原失败：{error}")
        if rollback_errors:
            details.append("  ⚠ 回滚未完成：" + "; ".join(rollback_errors))
        return _result(False, "restore_failed", "", details=details).emit(log)

    for target in TARGETS:
        try:
            os.remove(backups[target])
        except OSError as error:
            details.append(f"  ⚠ 无法删除备份 {backups[target]}：{error}")
        details.append(f"  ✓ 已还原 {target}")
    manifest_path = os.path.join(info.appdir, BACKUP_MANIFEST_NAME)
    if os.path.isfile(manifest_path):
        try:
            os.remove(manifest_path)
            details.append("  ✓ 已清除备份清单")
        except OSError as error:
            details.append(f"  ⚠ 无法删除备份清单：{error}")
    details.append("=== 还原完成 ===")
    return _result(True, "restored", "", details=details).emit(log)


# --------------------------------------------------------------------------
# 自动更新控制（严格限定在指定安装）
# --------------------------------------------------------------------------
def find_update_exe(appdir=None):
    """定位 Squirrel 更新器；指定 ``appdir`` 时不会回退到其他安装。"""
    if appdir:
        info = inspect_install(appdir)
        root = info.deploy_root
        if not root:
            return None
        canonical = os.path.join(root, "Update.exe")
        if os.path.isfile(canonical) or os.path.isfile(canonical + ".disabled"):
            return canonical
        return None
    for info in zhpaths.find_installs():
        if info.update_exe:
            return info.update_exe
    return None


def update_state(appdir=None):
    """返回自动更新状态：enabled / disabled / inconsistent / missing。"""
    if appdir:
        info = inspect_install(appdir)
        root, version, portable = info.deploy_root, info.version, info.portable
    else:
        installs = zhpaths.find_installs()
        info = installs[0] if installs else None
        root = info.deploy_root if info else None
        version = info.version if info else None
        portable = info.portable if info else False
    if not root:
        return {"state": "missing", "deploy_root": None, "version": version,
                "portable": portable, "canonical": None, "disabled": None}
    canonical = os.path.join(root, "Update.exe")
    disabled = canonical + ".disabled"
    has_canonical, has_disabled = os.path.isfile(canonical), os.path.isfile(disabled)
    if has_canonical and has_disabled:
        state = "inconsistent"
    elif has_canonical:
        state = "enabled"
    elif has_disabled:
        state = "disabled"
    else:
        state = "missing"
    return {"state": state, "deploy_root": root, "version": version,
            "portable": portable, "canonical": canonical, "disabled": disabled}


def auto_update_disabled(appdir=None):
    state = update_state(appdir)["state"]
    if state == "disabled":
        return True
    if state == "enabled":
        return False
    return None


def set_auto_update_disabled(enable, appdir=None, log=print):
    """enable=True 禁止更新；False 允许更新。返回 OperationResult。"""
    info = update_state(appdir)
    state = info["state"]
    details = [f"更新器目录：{info.get('deploy_root') or '（未找到）'}"]
    if state == "missing":
        details.append("✗ [错误] 该安装未检测到 Update.exe（便携版可能没有更新器）")
        return _result(False, "update_missing", "", details=details).emit(log)
    if state == "inconsistent":
        details.append("✗ [错误] 同时存在 Update.exe 与 Update.exe.disabled，状态异常")
        details.append("  · 请确认要保留哪一个后手动清理，工具不会自动删除文件")
        return _result(False, "update_inconsistent", "", details=details).emit(log)
    desired = "disabled" if enable else "enabled"
    if state == desired:
        details.append("· 自动更新已处于目标状态，无需修改")
        return _result(True, "update_unchanged", "", details=details).emit(log)
    try:
        if enable:
            os.replace(info["canonical"], info["disabled"])
        else:
            os.replace(info["disabled"], info["canonical"])
    except OSError as error:
        details.append(f"✗ [错误] 无法修改自动更新状态：{error}")
        details.append("  请关闭 GitHub Desktop 后重试；默认安装通常不需要管理员权限")
        return _result(False, "update_failed", "", details=details).emit(log)
    actual = update_state(appdir)["state"]
    if actual != desired:
        details.append(f"✗ [错误] 操作后状态仍为 {actual}，请检查文件占用或权限")
        return _result(False, "update_not_persisted", "", details=details).emit(log)
    details.append("✓ 已禁止自动更新" if enable else "✓ 已允许自动更新")
    return _result(True, "update_changed", "", details=details).emit(log)


# --------------------------------------------------------------------------
# 本地字典导入
# --------------------------------------------------------------------------
def _resolve_dictionary_source(source):
    source = zhpaths.expand_path(source)
    if not os.path.isdir(source):
        return None, "请选择包含 main.js 与 renderer.js 的文件夹。"
    candidates = []
    if all(os.path.isfile(os.path.join(source, t)) for t in TARGETS):
        candidates.append(source)
    windows = os.path.join(source, "Windows")
    if all(os.path.isfile(os.path.join(windows, t)) for t in TARGETS):
        candidates.append(windows)
    try:
        children = sorted(os.listdir(source))
    except OSError as error:
        return None, f"无法读取所选文件夹：{error}"
    for name in children:
        child = os.path.join(source, name)
        if (os.path.isdir(child)
                and all(os.path.isfile(os.path.join(child, t)) for t in TARGETS)):
            candidates.append(child)
    unique, seen = [], set()
    for candidate in candidates:
        key = os.path.normcase(os.path.abspath(candidate))
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    if not unique:
        return None, "所选文件夹中没有成对的 main.js 与 renderer.js。"
    if len(unique) > 1:
        return None, "所选文件夹包含多个候选汉化目录，请直接选择其中一个版本文件夹。"
    return unique[0], ""


def _infer_dictionary_version(source, explicit=None):
    if explicit:
        value = str(explicit).strip()
        if not zhpaths.is_version_name(value):
            return None, "版本号格式应为 3.6.10 这样的 X.Y.Z。"
        return value, ""
    provenance = os.path.join(source, "provenance.json")
    if os.path.isfile(provenance):
        try:
            with open(provenance, encoding="utf-8") as handle:
                value = str(json.load(handle).get("version") or "").strip()
            if zhpaths.is_version_name(value):
                return value, ""
        except (OSError, ValueError):
            pass
    for candidate in (source, os.path.dirname(source), os.path.dirname(os.path.dirname(source))):
        name = os.path.basename(candidate)
        if zhpaths.is_version_name(name):
            return name, ""
        match = re.search(r"(\d+\.\d+\.\d+)", name)
        if match:
            return match.group(1), ""
    return None, "无法从文件夹名推断版本号，请手动指定客户端版本。"


def _looks_like_javascript(path):
    try:
        with open(path, "rb") as handle:
            head = handle.read(512)
        if not head or head.lstrip().startswith(b"<"):
            return False
        head.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return True


def infer_dictionary_version(source, version=None):
    """供 UI 预填版本：返回 ``(版本号或 None, 错误文本)``。"""
    resolved, error = _resolve_dictionary_source(source)
    if not resolved:
        return None, error
    return _infer_dictionary_version(resolved, version)


def import_local_dictionary(source, version=None, log=print):
    """把用户下载的汉化目录导入 EXE 同级 ``dictionaries/<version>/``。"""
    resolved, error = _resolve_dictionary_source(source)
    if not resolved:
        return _result(False, "source_invalid", "✗ [错误] " + error).emit(log)
    inferred, error = _infer_dictionary_version(resolved, version)
    if not inferred:
        return _result(False, "version_unknown", "✗ [错误] " + error).emit(log)

    target_root = local_dict_dir()
    target = os.path.join(target_root, inferred)
    if os.path.normcase(os.path.abspath(resolved)) == os.path.normcase(os.path.abspath(target)):
        return _result(True, "dictionary_unchanged", "· 所选目录已是本地字典目录",
                       details=[f"目录：{target}"]).emit(log)

    details = [f"导入来源：{resolved}", f"目标版本：{inferred}"]
    warnings = []
    for name in TARGETS:
        if not _looks_like_javascript(os.path.join(resolved, name)):
            warnings.append(f"{name} 看起来不是有效的 UTF-8 JavaScript 文件，已标记为未验证")
    try:
        os.makedirs(target_root, exist_ok=True)
    except OSError as error:
        return _result(False, "dictionary_import_failed",
                       f"✗ [错误] 无法创建本地字典目录：{error}").emit(log)

    staging = tempfile.mkdtemp(prefix=".import-", dir=target_root)
    backups = []
    try:
        hashes = {}
        for name in TARGETS:
            src = os.path.join(resolved, name)
            dst = os.path.join(staging, name)
            shutil.copy2(src, dst)
            hashes[name] = {"sha256": sha256_file(dst), "size": os.path.getsize(dst)}
        record = {
            "schema": 1,
            "version": inferred,
            "imported_at": _now(),
            "source": resolved,
            "files": hashes,
            "verified": not warnings,
        }
        with open(os.path.join(staging, LOCAL_IMPORT_RECORD), "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)

        if os.path.isdir(target):
            backup = target + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
            suffix = 1
            while os.path.exists(backup):
                backup = target + f".bak-{time.strftime('%Y%m%d-%H%M%S')}-{suffix}"
                suffix += 1
            os.replace(target, backup)
            backups.append((target, backup))
            details.append(f"  ✓ 已备份旧本地字典 -> {backup}")
        os.replace(staging, target)
        staging = None
    except OSError as error:
        if staging and os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)
        for original, backup in reversed(backups):
            if not os.path.isdir(original) and os.path.isdir(backup):
                try:
                    os.replace(backup, original)
                except OSError:
                    pass
        details.append(f"✗ [错误] 导入失败：{error}")
        return _result(False, "dictionary_import_failed", "", details=details).emit(log)
    finally:
        if staging and os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)

    details.append(f"  ✓ 已导入到 {target}")
    details.append(
        f"  · main.js {hashes['main.js']['size']:,} 字节 · "
        f"renderer.js {hashes['renderer.js']['size']:,} 字节")
    if warnings:
        details.append("  ⚠ 本地字典未做语法级验证，使用前请确认来源可信")
    details.append(f"=== 导入完成（版本 {inferred}），已在版本列表中生效 ===")
    return _result(True, "dictionary_imported", "", details=details, warnings=warnings,
                   data={"version": inferred, "target": target, "hashes": hashes,
                         "verified": not warnings}).emit(log)


if __name__ == "__main__":
    # 简单自检：在临时副本上跑一遍 apply_version/restore
    tmp = tempfile.mkdtemp(prefix="zhcore_test_")
    app = os.path.join(tmp, "GitHubDesktop", "app-3.6.10", "resources", "app")
    os.makedirs(app)
    with open(os.path.join(app, "main.js"), "w", encoding="utf-8") as handle:
        handle.write('"About GitHub Desktop"')
    with open(os.path.join(app, "renderer.js"), "w", encoding="utf-8") as handle:
        handle.write('"Changes"')
    print("locate() ->", locate())
    vers = list_versions()
    print("可用版本数 ->", len(vers), "最新 ->", vers[0] if vers else None)
    if vers:
        print("apply ->", apply_version(app, vers[0], allow_mismatch=True).ok)
        print("restore ->", restore(app).ok)
    shutil.rmtree(tmp, ignore_errors=True)
    print("SELFTEST OK")
