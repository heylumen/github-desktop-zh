#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对打包后的单文件 EXE 运行无头自检。

用法：
    python scripts/smoke_exe.py gui/dist/github-desktop-zh-1.0.3.exe
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exe")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    exe = Path(args.exe).resolve()
    if not exe.is_file():
        print(f"[错误] 文件不存在：{exe}", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="gdf-exe-smoke-") as temp:
        report = Path(temp) / "self-test.json"
        env = dict(os.environ)
        env.update({
            "QT_QPA_PLATFORM": "offscreen",
            "GDF_SELF_TEST_OUT": str(report),
            "GITHUB_DESKTOP_ZH_LOG_DIR": str(Path(temp) / "logs"),
            "COPILOT_HOME": str(Path(temp) / "copilot"),
            "PYTHONIOENCODING": "utf-8",
        })
        try:
            result = subprocess.run(
                [str(exe), "--self-test"], env=env, timeout=args.timeout,
                capture_output=True, text=True, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            print(f"[错误] 自检超时（{args.timeout}s）", file=sys.stderr)
            return 1
        payload = {}
        if report.is_file():
            try:
                raw = report.read_text(encoding="utf-8")
                payload = json.loads(raw.split("SELF_TEST_")[0].strip())
            except (OSError, ValueError):
                payload = {}
        if result.returncode != 0 or not payload.get("ok"):
            print(f"[错误] 自检失败，退出码 {result.returncode}", file=sys.stderr)
            print(result.stdout[-2000:], file=sys.stderr)
            print(result.stderr[-2000:], file=sys.stderr)
            return 1
        checks = payload.get("checks") or {}
        print(f"✓ EXE 无头自检通过：{exe.name}（{len(checks)} 项）")
        for name, passed in checks.items():
            print(("  ✓ " if passed else "  ✗ ") + name)
        return 0


if __name__ == "__main__":
    sys.exit(main())
