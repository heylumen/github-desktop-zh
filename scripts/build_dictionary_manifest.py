#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成或校验 ``dictionaries/manifest.json``。

用法（仓库根目录）：
    python scripts/build_dictionary_manifest.py            # 重新生成
    python scripts/build_dictionary_manifest.py --check    # 仅校验，失败返回 1
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
DICTIONARIES = ROOT / "dictionaries"
TARGETS = ("main.js", "renderer.js")
SCHEMA = 1


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_key(version):
    numbers = [int(part) for part in re.findall(r"\d+", version)]
    return (1, numbers) if numbers else (0, [])


def collect():
    entries = {}
    for directory in sorted(DICTIONARIES.iterdir(), key=lambda p: version_key(p.name)):
        if not directory.is_dir():
            continue
        if not all((directory / target).is_file() for target in TARGETS):
            continue
        files = {}
        for target in TARGETS:
            path = directory / target
            files[target] = {"sha256": sha256(path), "size": path.stat().st_size}
        source = "upstream-743859910"
        provenance = directory / "provenance.json"
        if provenance.is_file():
            source = "official-adaptation"
            try:
                record = json.loads(provenance.read_text(encoding="utf-8"))
                if record.get("package_sha256"):
                    source = "official-adaptation"
            except (OSError, ValueError):
                pass
        entries[directory.name] = {"source": source, "files": files}
    return entries


def build_manifest(entries):
    return {
        "schema": SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "targets": list(TARGETS),
        "versions": entries,
    }


def check(manifest):
    versions = manifest.get("versions") or {}
    failures = []
    for version in sorted(versions, key=version_key):
        directory = DICTIONARIES / version
        if not directory.is_dir():
            failures.append(f"{version}: 缺少目录")
            continue
        for target in TARGETS:
            path = directory / target
            expected = ((versions[version].get("files") or {}).get(target) or {}).get("sha256")
            if not path.is_file():
                failures.append(f"{version}/{target}: 文件缺失")
            elif not expected:
                failures.append(f"{version}/{target}: 清单缺少散列")
            elif sha256(path) != expected:
                failures.append(f"{version}/{target}: 散列不一致")
    actual = set(collect())
    recorded = set(versions)
    for version in sorted(actual - recorded, key=version_key):
        failures.append(f"{version}: 目录存在但未登记到清单")
    for version in sorted(recorded - actual, key=version_key):
        failures.append(f"{version}: 清单已登记但目录不可用")
    return failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="只校验，不写入")
    args = parser.parse_args(argv)
    manifest_path = DICTIONARIES / "manifest.json"

    if args.check:
        if not manifest_path.is_file():
            print(f"[错误] 缺少 {manifest_path}", file=sys.stderr)
            return 1
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except ValueError as error:
            print(f"[错误] 清单无法解析：{error}", file=sys.stderr)
            return 1
        failures = check(manifest)
        if failures:
            for failure in failures:
                print("✗ " + failure, file=sys.stderr)
            return 1
        print(f"✓ 字典清单校验通过：{len(manifest.get('versions') or {})} 个版本")
        return 0

    entries = collect()
    if not entries:
        print("[错误] 未找到任何字典版本", file=sys.stderr)
        return 1
    manifest = build_manifest(entries)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"✓ 已生成 {manifest_path}（{len(entries)} 个版本）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
