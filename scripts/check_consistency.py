#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consistency gate: one source of truth must agree across build, UI and docs.

Checks:
1. gui/product_meta.py is importable and has APP_VERSION / BUNDLED_DICTIONARY_LIMIT.
2. The top-N dictionaries discovered on disk are what build_release/verify_archive use.
3. spec, build_release.py and verify_archive.py no longer hard-code a different N.
4. build.bat / CI use the expected EXE name.
5. README / docs state the same built-in count (current statements only).
6. gui/dist/build-info.json, if present, lists the same built-in dictionaries.

Exit code 0 = consistent, 1 = mismatches.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
GUI = ROOT / "gui"
sys.path.insert(0, str(GUI))

from product_meta import APP_VERSION, BUNDLED_DICTIONARY_LIMIT  # noqa: E402

TARGETS = ("main.js", "renderer.js")
MISMATCHES: list[str] = []


def fail(message: str) -> None:
    MISMATCHES.append(message)


def version_key(version: str):
    parts = [int(x) for x in re.findall(r"\d+", version)]
    return (1, parts) if parts else (0, [])


def discovered_versions() -> list[str]:
    versions = []
    base = ROOT / "dictionaries"
    if not base.is_dir():
        return versions
    for directory in base.iterdir():
        if directory.is_dir() and all((directory / target).is_file() for target in TARGETS):
            versions.append(directory.name)
    versions.sort(key=version_key, reverse=True)
    return versions


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_no_hardcoded_limit(relative: str) -> None:
    text = (ROOT / relative).read_text(encoding="utf-8")
    matches = re.findall(r"versions\[:\s*(\d+)\s*\]", text)
    for value in matches:
        if int(value) != BUNDLED_DICTIONARY_LIMIT:
            fail(f"{relative}: versions[:{value}] != product_meta limit {BUNDLED_DICTIONARY_LIMIT}")


def check_expected_docs_count() -> None:
    expected = str(BUNDLED_DICTIONARY_LIMIT)
    patterns = (
        r"内置最新\s*(\d+)\s*版",
        r"内置\s*(\d+)\s*版",
        r"内置\s*(\d+)\s*个版本",
    )
    for relative in ("README.md", "DESIGN.md", "docs/3.6.10.md", "docs/troubleshooting.md"):
        path = ROOT / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            for value in re.findall(pattern, text):
                if value != expected:
                    fail(f"{relative}: 文案写内置 {value} 版，product_meta 是 {expected}")


def check_exe_name(relative: str) -> None:
    text = (ROOT / relative).read_text(encoding="utf-8")
    expected = f"github-desktop-zh-{APP_VERSION}.exe"
    if expected not in text:
        fail(f"{relative}: 未出现期望的 EXE 名 {expected}")


def check_build_info() -> None:
    path = ROOT / "gui" / "dist" / "build-info.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        fail(f"build-info.json 无法读取：{error}")
        return
    if data.get("app_version") not in (None, APP_VERSION):
        fail(f"build-info.json app_version={data.get('app_version')!r}，期望 {APP_VERSION!r}")
    expected = discovered_versions()[:BUNDLED_DICTIONARY_LIMIT]
    actual = data.get("bundled_dictionaries")
    if actual != expected:
        fail(f"build-info.json bundled_dictionaries={actual!r}，期望 {expected!r}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build-info", action="store_true",
                        help="构建前忽略旧的 build-info.json")
    args = parser.parse_args(argv)
    versions = discovered_versions()
    expected = versions[:BUNDLED_DICTIONARY_LIMIT]

    if not expected:
        fail("dictionaries/ 下没有可用的 main.js + renderer.js")
    if len(expected) < BUNDLED_DICTIONARY_LIMIT:
        fail(f"内置字典上限 {BUNDLED_DICTIONARY_LIMIT}，实际只有 {len(expected)} 个")

    build_release = load_module("build_release_check", ROOT / "scripts" / "build_release.py")
    verify_archive = load_module("verify_archive_check", ROOT / "scripts" / "verify_archive.py")
    if build_release.bundled_versions() != expected:
        fail(f"build_release 内置列表 {build_release.bundled_versions()!r}，期望 {expected!r}")
    if verify_archive.expected_versions() != expected:
        fail(f"verify_archive 内置列表 {verify_archive.expected_versions()!r}，期望 {expected!r}")

    for relative in ("scripts/build_release.py", "scripts/verify_archive.py",
                     "github-desktop-zh-1.0.3.spec"):
        check_no_hardcoded_limit(relative)

    app_text = (ROOT / "gui" / "app.py").read_text(encoding="utf-8")
    app_match = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', app_text, re.MULTILINE)
    if not app_match or app_match.group(1) != APP_VERSION:
        fail(f"gui/app.py APP_VERSION={app_match.group(1) if app_match else None!r}，product_meta={APP_VERSION!r}")
    if not (ROOT / f"github-desktop-zh-{APP_VERSION}.spec").is_file():
        fail(f"缺少 spec：github-desktop-zh-{APP_VERSION}.spec")
    check_exe_name("gui/build.bat")
    check_exe_name(".github/workflows/ci.yml")
    check_expected_docs_count()
    if not args.skip_build_info:
        check_build_info()

    if MISMATCHES:
        print("[FAIL] consistency gate")
        for mismatch in MISMATCHES:
            print("  - " + mismatch)
        return 1
    print("[OK] consistency gate")
    print(f"  app_version={APP_VERSION}")
    print(f"  bundled_limit={BUNDLED_DICTIONARY_LIMIT}")
    print(f"  bundled={expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
