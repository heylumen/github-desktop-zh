#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py — GitHub Desktop 汉化工具（命令行版）

与 GUI 共享同一套核心逻辑（zhcore），适合脚本化、CI 或高级用户。
按版本内置多个汉化（源自 743859910 的 MIT 整文件补丁），本工具为 Windows 专用。

用法示例：
  python cli.py locate
  python cli.py versions
  python cli.py apply --version 3.6.4
  python cli.py apply --path "C:\\Users\\Me\\AppData\\Local\\GitHubDesktop\\app-3.6.4\\resources\\app"
  python cli.py restore
"""
import argparse
import sys

import zhcore


def _resolve_path(args):
    path = (args.path or "").strip()
    if not path:
        path = zhcore.locate() or ""
    if not path:
        print("[错误] 未指定路径且无法自动检测，请用 --path 指定 resources/app 目录。", file=sys.stderr)
        sys.exit(2)
    return path


def _resolve_version(version):
    vers = zhcore.list_versions()
    if not vers:
        print("[错误] 未找到任何内置汉化版本。", file=sys.stderr)
        sys.exit(2)
    if version:
        if version not in vers:
            print(f"[错误] 版本 {version} 不存在，可用：{', '.join(vers)}", file=sys.stderr)
            sys.exit(2)
        return version
    return vers[0]  # 最新版


def cmd_locate(args):
    found = zhcore.locate()
    print(found or "（未检测到 GitHub Desktop 安装目录）")
    return 0 if found else 1


def cmd_versions(args):
    vers = zhcore.list_versions()
    if not vers:
        print("（未找到任何内置汉化版本）")
        return 1
    print(f"内置汉化版本（共 {len(vers)} 个，最新在前）：")
    for v in vers:
        print(f"  {v}")
    return 0


def cmd_apply(args):
    path = _resolve_path(args)
    version = _resolve_version(args.version)
    ok = zhcore.apply_version(path, version, log=print)
    return 0 if ok else 1


def cmd_restore(args):
    path = _resolve_path(args)
    ok = zhcore.restore(path, log=print)
    return 0 if ok else 1


def build_parser():
    p = argparse.ArgumentParser(
        prog="cli.py",
        description="GitHub Desktop 汉化工具（命令行版，基于 743859910 的 MIT 整文件补丁，Windows 专用）",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("locate", help="自动检测 GitHub Desktop 安装目录").set_defaults(func=cmd_locate)
    sub.add_parser("versions", help="列出所有内置汉化版本").set_defaults(func=cmd_versions)

    ap = sub.add_parser("apply", help="应用指定版本的汉化")
    ap.add_argument("--path", help="resources/app 目录（缺省则自动检测）")
    ap.add_argument("--version", default=None,
                    help="汉化版本号（缺省用最新内置版本，如 3.6.4）")
    ap.set_defaults(func=cmd_apply)

    rp = sub.add_parser("restore", help="还原为英文原版")
    rp.add_argument("--path", help="resources/app 目录（缺省则自动检测）")
    rp.set_defaults(func=cmd_restore)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
