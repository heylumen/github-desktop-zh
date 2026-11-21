#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 ALL 字典目录：清单散列 + 使用 Node 做 JavaScript 语法检查。

用法（仓库根目录）：
    python scripts/check_dictionaries.py [--node node]
缺失 Node 时只做清单与文件检查，并在输出中明确提示。
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DICTIONARIES = ROOT / "dictionaries"
TARGETS = ("main.js", "renderer.js")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default="node", help="Node.js 可执行文件")
    args = parser.parse_args(argv)

    manifest = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_dictionary_manifest.py"), "--check"],
        capture_output=True, text=True, encoding="utf-8")
    print(manifest.stdout.strip())
    if manifest.returncode:
        print(manifest.stderr.strip(), file=sys.stderr)
        return 1

    versions = []
    for directory in sorted(DICTIONARIES.iterdir()):
        if directory.is_dir() and all((directory / t).is_file() for t in TARGETS):
            versions.append(directory)

    node = shutil.which(args.node) if args.node else None
    failures = []
    checked = 0
    for directory in versions:
        for target in TARGETS:
            path = directory / target
            if not path.is_file() or path.stat().st_size == 0:
                failures.append(f"{directory.name}/{target}: 缺失或为空")
                continue
            if node:
                result = subprocess.run([node, "--check", str(path)],
                                        capture_output=True, text=True, encoding="utf-8")
                checked += 1
                if result.returncode:
                    failures.append(f"{directory.name}/{target}: {result.stderr.strip()[:300]}")
    if failures:
        for failure in failures:
            print("✗ " + failure, file=sys.stderr)
        return 1
    print(f"✓ 字典检查通过：{len(versions)} 个版本，"
          f"{checked if node else 0} 个 JS 文件执行语法检查"
          + ("" if node else "（未找到 Node，仅检查存在性与散列）"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
