#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Release gate: refuse to publish an EXE that is not from a clean tag."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gui"))

from product_meta import APP_VERSION, BUNDLED_DICTIONARY_LIMIT  # noqa: E402


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True,
                                   encoding="utf-8").strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    raise SystemExit(1)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe")
    parser.add_argument("--require-tag", action="store_true")
    args = parser.parse_args(argv)

    status = git("status", "--porcelain")
    if status:
        fail("工作树不干净，拒绝发布：\n" + status)

    head = git("rev-parse", "HEAD")
    if args.require_tag:
        try:
            tag = git("describe", "--tags", "--exact-match", "HEAD")
        except subprocess.CalledProcessError:
            fail("HEAD 没有精确 tag，拒绝发布")
        expected = f"v{APP_VERSION}"
        if tag != expected:
            fail(f"tag={tag}，期望 {expected}")
        print(f"[OK] tag={tag} commit={head[:12]}")
    else:
        print(f"[OK] clean working tree commit={head[:12]}")

    build_info = ROOT / "gui" / "dist" / "build-info.json"
    if not build_info.is_file():
        fail("缺少 gui/dist/build-info.json")
    data = json.loads(build_info.read_text(encoding="utf-8"))
    if data.get("dirty") is not False:
        fail(f"build-info.dirty={data.get('dirty')!r}，必须为 false")
    if data.get("commit") != head:
        fail(f"build-info.commit={data.get('commit')!r} != HEAD {head!r}")
    if data.get("app_version") != APP_VERSION:
        fail(f"build-info.app_version={data.get('app_version')!r} != {APP_VERSION!r}")
    if len(data.get("bundled_dictionaries") or []) != BUNDLED_DICTIONARY_LIMIT:
        fail("build-info 内置字典数量不匹配")
    if args.exe:
        exe = Path(args.exe).resolve()
        if not exe.is_file():
            fail(f"EXE 不存在：{exe}")
        if data.get("sha256") != sha256(exe):
            fail("build-info.sha256 与 EXE 实际哈希不一致")
        if exe.name != f"github-desktop-zh-{APP_VERSION}.exe":
            fail(f"EXE 文件名 {exe.name} 与版本 {APP_VERSION} 不一致")
        print(f"[OK] exe={exe.name} sha256={data['sha256'][:12]}…")
    print("[OK] release gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
