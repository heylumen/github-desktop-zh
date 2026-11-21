#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub Desktop 安装发现与路径归一化（无 UI、无第三方依赖）。

支持官方 Squirrel 安装、便携/绿色版（任意盘符、无 ``app-X.Y.Z`` 层级），
并明确区分“解包版”“仅 app.asar”“资源不完整”三种布局。

本模块是 GUI、CLI 与旧引擎共同的事实来源，避免各处重复推断路径和版本。
"""
from __future__ import annotations

from dataclasses import dataclass
import glob
import json
import os
import re
from typing import Iterable

TARGETS = ("main.js", "renderer.js")
APP_DIR_NAME = "app"
RESOURCES_DIR_NAME = "resources"
BACKUP_MANIFEST_NAME = ".github-desktop-zh-backup.json"

_APP_PATH_VERSION = re.compile(r"app-(\d+\.\d+\.\d+)", re.IGNORECASE)
_VERSION_TEXT = re.compile(r"(\d+\.\d+\.\d+)")
_SEMVER = re.compile(r"^\d+(?:\.\d+){1,3}$")


def version_key(version):
    """版本排序键：逐段数字比较；无数字的名字排在最后。"""
    nums = [int(x) for x in re.findall(r"\d+", str(version or ""))]
    return (1, nums) if nums else (0, [])


def is_version_name(value):
    return bool(_SEMVER.match(str(value or "").strip()))


def expand_path(path):
    """展开引号、环境变量与 ``~``；不做存在性判断。"""
    text = str(path or "").strip().strip('"').strip("'")
    if not text:
        return ""
    return os.path.abspath(os.path.expandvars(os.path.expanduser(text)))


def default_install_base():
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    return os.path.join(local, "GitHubDesktop")


def _looks_like_appdir(path):
    return (os.path.isdir(path)
            and os.path.basename(path).lower() == APP_DIR_NAME
            and os.path.basename(os.path.dirname(path)).lower() == RESOURCES_DIR_NAME)


def _candidate_appdirs(path):
    """把客户端 EXE、客户端根目录、resources、resources/app 归一为候选 app 目录。"""
    if not path:
        return []
    candidates = []
    p = path
    if os.path.isfile(p):
        if os.path.basename(p).lower() in TARGETS:
            p = os.path.dirname(p)
        else:
            p = os.path.dirname(p)
    if _looks_like_appdir(p):
        candidates.append(p)
    cur = p
    for _ in range(3):
        if not cur:
            break
        candidates.append(os.path.join(cur, RESOURCES_DIR_NAME, APP_DIR_NAME))
        candidates.append(os.path.join(cur, APP_DIR_NAME))
        # 官方 Squirrel 部署根：<deploy>/app-X.Y.Z/resources/app
        try:
            candidates.extend(glob.glob(os.path.join(cur, "app-*", RESOURCES_DIR_NAME, APP_DIR_NAME)))
        except OSError:
            pass
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    seen, result = set(), []
    for c in candidates:
        key = os.path.normcase(os.path.abspath(c))
        if key in seen:
            continue
        seen.add(key)
        if _looks_like_appdir(c):
            result.append(os.path.abspath(c))
    return result


def _read_package(appdir):
    package_path = os.path.join(appdir, "package.json")
    if not os.path.isfile(package_path):
        return None, None, None
    try:
        with open(package_path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        return None, package_path, f"无法读取 package.json：{error}"
    version = str(data.get("version") or "").strip() or None
    return data, package_path, None if version else "package.json 缺少 version 字段"


@dataclass(frozen=True)
class InstallInfo:
    """一次安装探测的完整结果。"""

    requested: str
    appdir: str | None = None
    resources_dir: str | None = None
    deploy_root: str | None = None
    layout: str = "invalid"          # unpacked / asar / incomplete / invalid
    version: str | None = None
    version_source: str | None = None
    package_version: str | None = None
    path_version: str | None = None
    files: tuple[tuple[str, str], ...] = ()
    missing: tuple[str, ...] = ()
    update_exe: str | None = None
    portable: bool = False
    asar_path: str | None = None
    package_json: str | None = None
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        return self.layout == "unpacked"

    @property
    def usable(self) -> bool:
        return self.layout in ("unpacked",)

    def as_dict(self):
        return {
            "requested": self.requested,
            "appdir": self.appdir,
            "resources_dir": self.resources_dir,
            "deploy_root": self.deploy_root,
            "layout": self.layout,
            "version": self.version,
            "version_source": self.version_source,
            "package_version": self.package_version,
            "path_version": self.path_version,
            "files": dict(self.files),
            "missing": list(self.missing),
            "update_exe": self.update_exe,
            "portable": self.portable,
            "asar_path": self.asar_path,
            "package_json": self.package_json,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _is_portable(deploy_root):
    base = default_install_base()
    if not deploy_root:
        return False
    if not base:
        return True
    try:
        return os.path.normcase(os.path.abspath(deploy_root)) != os.path.normcase(os.path.abspath(base))
    except OSError:
        return True


def inspect_install(path):
    """探测任意用户输入指向的 GitHub Desktop 安装。"""
    requested = expand_path(path)
    if not requested:
        return InstallInfo(requested="", errors=("未指定安装路径。",))

    candidates = _candidate_appdirs(requested)
    if not candidates:
        # 可能是“有 app.asar 但完全没解包目录”的布局
        probe = requested
        if os.path.isfile(probe):
            probe = os.path.dirname(probe)
        for _ in range(3):
            asar = os.path.join(probe, RESOURCES_DIR_NAME, "app.asar")
            if os.path.isfile(asar):
                return InstallInfo(
                    requested=requested,
                    resources_dir=os.path.dirname(asar),
                    deploy_root=os.path.dirname(os.path.dirname(asar)),
                    layout="asar",
                    asar_path=asar,
                    portable=_is_portable(os.path.dirname(os.path.dirname(asar))),
                    errors=("该 GitHub Desktop 以 app.asar 单包发布，当前版本不支持直接改写。",),
                )
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent
        return InstallInfo(
            requested=requested,
            errors=("未找到 GitHub Desktop 的 resources/app 目录。",),
        )

    appdir = candidates[0]
    resources_dir = os.path.dirname(appdir)
    deploy_root = os.path.dirname(os.path.dirname(resources_dir))
    package, package_path, package_error = _read_package(appdir)
    package_version = None
    if package:
        raw = str(package.get("version") or "").strip()
        if raw:
            match = _VERSION_TEXT.search(raw)
            package_version = match.group(1) if match else raw

    path_version = None
    match = _APP_PATH_VERSION.search(requested) or _APP_PATH_VERSION.search(appdir)
    if match:
        path_version = match.group(1)

    files = tuple((name, os.path.join(appdir, name)) for name in TARGETS
                  if os.path.isfile(os.path.join(appdir, name)))
    missing = tuple(name for name in TARGETS
                    if not os.path.isfile(os.path.join(appdir, name)))
    asar_path = os.path.join(resources_dir, "app.asar")
    has_asar = os.path.isfile(asar_path)
    if not missing:
        layout = "unpacked"
    elif has_asar:
        layout = "asar"
    else:
        layout = "incomplete"

    version = package_version or path_version
    version_source = "package.json" if package_version else ("路径" if path_version else None)
    errors, warnings = [], []
    if package_error:
        warnings.append(package_error)
    if layout == "asar":
        errors.append("该安装以 app.asar 单包发布，当前版本不支持直接改写。")
    elif layout == "incomplete":
        errors.append("安装目录缺少：" + "、".join(missing))
    if package_version and path_version and package_version != path_version:
        warnings.append(
            f"package.json 版本 {package_version} 与路径版本 {path_version} 不一致，以 package.json 为准。")

    update_exe = None
    canonical = os.path.join(deploy_root, "Update.exe")
    if os.path.isfile(canonical) or os.path.isfile(canonical + ".disabled"):
        update_exe = canonical

    return InstallInfo(
        requested=requested,
        appdir=appdir,
        resources_dir=resources_dir,
        deploy_root=deploy_root,
        layout=layout,
        version=version,
        version_source=version_source,
        package_version=package_version,
        path_version=path_version,
        files=files,
        missing=missing,
        update_exe=update_exe,
        portable=_is_portable(deploy_root),
        asar_path=asar_path if has_asar else None,
        package_json=package_path,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _default_install_dirs():
    base = default_install_base()
    if not base or not os.path.isdir(base):
        return []
    dirs = glob.glob(os.path.join(base, "app-*", "resources", "app"))
    # 官方安装器升级后可能保留旧版本目录，统一交给排序处理。
    return [d for d in dirs if os.path.isdir(d)]


def find_installs(extra: Iterable[str] = (), include_invalid=False):
    """发现所有可识别安装，按版本降序返回；同一目录只保留一次。"""
    requested = list(_default_install_dirs()) + [p for p in (extra or ()) if p]
    seen, installs = set(), []
    for path in requested:
        info = inspect_install(path)
        key = os.path.normcase(info.appdir or info.requested)
        if key in seen:
            continue
        seen.add(key)
        if info.layout != "invalid" or include_invalid:
            installs.append(info)
    installs.sort(
        key=lambda i: (1 if i.available else 0, version_key(i.version or ""), i.appdir or ""),
        reverse=True,
    )
    return installs


def autodetect_appdir(extra: Iterable[str] = ()):
    """返回可用安装中最新的 app 目录；没有则 None。"""
    for info in find_installs(extra):
        if info.available and info.appdir:
            return info.appdir
    return None


def latest_sibling_appdir(path):
    """在已知安装的部署根下重新发现最新版本目录。

    用于监控场景：官方升级会把 ``app-3.6.4`` 换成 ``app-3.6.5``，
    旧路径随即失效。
    """
    info = inspect_install(path)
    if not info.deploy_root or not os.path.isdir(info.deploy_root):
        return None
    candidates = glob.glob(os.path.join(info.deploy_root, "app-*", "resources", "app"))
    installs = []
    for candidate in candidates:
        current = inspect_install(candidate)
        if current.available and current.appdir:
            installs.append(current)
    installs.sort(key=lambda i: (version_key(i.version or ""), i.appdir or ""), reverse=True)
    return installs[0].appdir if installs else None


def resolve_app_files(appdir, main_path=None, renderer_path=None):
    """返回 ``[(target_name, path), ...]``，仅包含实际存在的文件。"""
    files = []
    if main_path:
        files.append((TARGETS[0], main_path))
    elif appdir:
        candidate = os.path.join(appdir, TARGETS[0])
        if os.path.isfile(candidate):
            files.append((TARGETS[0], candidate))
    if renderer_path:
        files.append((TARGETS[1], renderer_path))
    elif appdir:
        candidate = os.path.join(appdir, TARGETS[1])
        if os.path.isfile(candidate):
            files.append((TARGETS[1], candidate))
    return files


def detect_version(path):
    info = inspect_install(path)
    return info.version


def sha256_file(path):
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()
