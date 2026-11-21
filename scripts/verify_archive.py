#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 PyInstaller 单文件 EXE 的关键内容。

检查项：
1. 内置字典上限来自 product_meta，且 main.js / renderer.js 成对、与仓库最新版本一致；
2. 字典清单 ``dictionaries/manifest.json`` 已打包；
3. 窗口图标 ``assets/icon.ico`` 已打包；
4. 顶层入口 ``app`` 的字节码中编译进了预期版本号。

用法：
    python scripts/verify_archive.py gui/dist/github-desktop-zh-1.0.3.exe
"""
from __future__ import annotations

import argparse
import marshal
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gui"))
from product_meta import BUNDLED_DICTIONARY_LIMIT  # noqa: E402

TARGETS = ("main.js", "renderer.js")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


def version_key(version):
    parts = [int(x) for x in re.findall(r"\d+", version)]
    return (1, parts) if parts else (0, [])


def expected_versions():
    versions = []
    base = ROOT / "dictionaries"
    for directory in base.iterdir():
        if directory.is_dir() and all((directory / t).is_file() for t in TARGETS):
            versions.append(directory.name)
    versions.sort(key=version_key, reverse=True)
    return versions[:BUNDLED_DICTIONARY_LIMIT]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe")
    parser.add_argument("--version", help="期望编译进 EXE 的应用版本号")
    args = parser.parse_args(argv)
    exe = Path(args.exe)
    if not exe.is_file():
        print(f"[错误] 文件不存在：{exe}", file=sys.stderr)
        return 2
    expected = args.version or (exe.stem.split("-")[-1] if "-" in exe.stem else "")
    expected = expected.lstrip("v")
    if not VERSION_RE.match(expected):
        print(f"[错误] 无法确定预期版本号：{expected!r}，请用 --version 指定", file=sys.stderr)
        return 2

    try:
        from PyInstaller.archive.readers import CArchiveReader
    except ImportError:
        print("[错误] 需要 PyInstaller 运行本脚本（使用构建 venv 的 Python）", file=sys.stderr)
        return 2

    archive = CArchiveReader(str(exe))
    names = list(archive.toc.keys())
    normalized = [name.replace("\\", "/") for name in names]
    dict_mains = sorted({p.split("/")[1] for p in normalized
                         if p.startswith("dictionaries/") and p.endswith("/main.js")})
    dict_renderers = sorted({p.split("/")[1] for p in normalized
                             if p.startswith("dictionaries/") and p.endswith("/renderer.js")})
    want = expected_versions()
    checks = []

    checks.append(("字典 main/renderer 成对", set(dict_mains) == set(dict_renderers)))
    checks.append((f"内置字典恰为最新 {BUNDLED_DICTIONARY_LIMIT} 版", sorted(dict_mains) == sorted(want)))
    checks.append(("字典清单已打包", "dictionaries/manifest.json" in normalized))
    checks.append(("窗口图标已打包", "assets/icon.ico" in normalized))
    checks.append(("顶层 app 入口存在", "app" in archive.toc))

    version_constants = set()
    try:
        code = marshal.loads(archive.extract("app"))
    except Exception as error:  # noqa: BLE001
        checks.append(("app 字节码可解析", False))
        print(f"[错误] 无法解析 app 字节码：{error}", file=sys.stderr)
    else:
        pending = [(code, 0)]
        while pending:
            current, depth = pending.pop()
            for constant in current.co_consts:
                if isinstance(constant, str) and VERSION_RE.match(constant):
                    version_constants.add(constant)
                elif hasattr(constant, "co_consts") and depth < 6:
                    pending.append((constant, depth + 1))
        # 允许出现字典版本（如 3.6.10）；只要求应用版本 1.x 存在且唯一
        app_versions = {value for value in version_constants if value.startswith("1.")}
        checks.append((f"应用版本号 {expected} 存在且唯一",
                       expected in version_constants and app_versions == {expected}))

    ok = all(passed for _, passed in checks)
    print(f"EXE：{exe}  {exe.stat().st_size:,} 字节")
    print(f"内置字典：{', '.join(dict_mains)}")
    print(f"版本常量：{', '.join(sorted(version_constants)) or '(未找到)'}")
    for label, passed in checks:
        print(("  ✓ " if passed else "  ✗ ") + label)
    print("\n结论：" + ("归档校验通过 ✔" if ok else "归档校验失败 ✗"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
