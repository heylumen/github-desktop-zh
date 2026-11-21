#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为发布产物生成 SHA-256 清单与构建信息（不执行发布）。

用法：
    python scripts/build_release.py --exe gui/dist/github-desktop-zh-1.0.3.exe
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gui"))
from product_meta import APP_VERSION, BUNDLED_DICTIONARY_LIMIT  # noqa: E402

TARGETS = ("main.js", "renderer.js")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_key(version):
    parts = [int(x) for x in re.findall(r"\d+", version)]
    return (1, parts) if parts else (0, [])


def bundled_versions():
    versions = []
    for directory in (ROOT / "dictionaries").iterdir():
        if directory.is_dir() and all((directory / t).is_file() for t in TARGETS):
            versions.append(directory.name)
    versions.sort(key=version_key, reverse=True)
    return versions[:BUNDLED_DICTIONARY_LIMIT]


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def git_dirty():
    try:
        result = subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                                capture_output=True, text=True, check=True)
        return bool(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        return None


def bundle_licenses(out_dir, versions):
    """把可见的许可文本放到 EXE 旁，避免只藏在单文件内部。"""
    destination = out_dir / "licenses"
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)
    copies = [
        (ROOT / "LICENSE", "PROJECT-LICENSE.txt"),
        (ROOT / "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.md"),
        (ROOT / "licenses" / "github-desktop-LICENSE", "github-desktop-LICENSE.txt"),
    ]
    for version in versions:
        directory = ROOT / "dictionaries" / version
        for path in sorted(directory.glob("LICENSE*")):
            if path.is_file():
                copies.append((path, f"{version}-{path.name}"))
        for path in sorted(directory.glob("*.LICENSE.txt")):
            if path.is_file():
                copies.append((path, f"{version}-{path.name}"))
    written = []
    for source, name in copies:
        if source.is_file():
            target = destination / name
            target.write_bytes(source.read_bytes())
            written.append(target)
    return destination if written else None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--out-dir", help="输出目录（默认与 EXE 相同）")
    args = parser.parse_args(argv)
    exe = Path(args.exe)
    if not exe.is_file():
        print(f"[错误] 文件不存在：{exe}", file=sys.stderr)
        return 2
    if not exe.name.isascii():
        print("[错误] 发布资产名必须是 ASCII（中文名会被 GitHub 剥离）", file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir) if args.out_dir else exe.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256(exe)
    checksums = out_dir / "SHA256SUMS.txt"
    checksums.write_text(f"{digest}  {exe.name}\n", encoding="utf-8")
    info = {
        "artifact": exe.name,
        "app_version": APP_VERSION,
        "size": exe.stat().st_size,
        "sha256": digest,
        "commit": git_commit(),
        "dirty": git_dirty(),
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "bundled_dictionaries": bundled_versions(),
    }
    info_path = out_dir / "build-info.json"
    info_path.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    licenses = bundle_licenses(out_dir, info["bundled_dictionaries"])
    print(f"✓ {checksums}")
    print(f"✓ {info_path}")
    if licenses:
        print(f"✓ {licenses}")
    print(f"  sha256={digest}")
    print(f"  size={info['size']:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
