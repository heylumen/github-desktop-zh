#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py — GitHub Desktop 汉化工具（命令行版）

与 GUI 共享同一套核心逻辑（zhcore），适合脚本化、CI 或高级用户。
按版本组织 Windows 汉化：旧版采用上游 MIT 整文件补丁，3.6.10 基于官方同版本底包适配中文字符串。

用法示例：
  python cli.py locate
  python cli.py versions
  python cli.py apply --version 3.6.10
  python cli.py apply --path "C:\\Users\\Me\\AppData\\Local\\GitHubDesktop\\app-3.6.10\\resources\\app"
  python cli.py restore
  python cli.py copilot --show
  python cli.py copilot --file "commit-instructions.txt"
"""
import argparse
from pathlib import Path
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


def cmd_update(args):
    path = (args.path or "").strip()
    appdir = path or None
    if args.enable:
        ok = zhcore.set_auto_update_disabled(False, appdir, log=print)
        return 0 if ok else 1
    if args.disable:
        ok = zhcore.set_auto_update_disabled(True, appdir, log=print)
        return 0 if ok else 1
    # 默认：查看状态
    st = zhcore.auto_update_disabled(appdir)
    if st is None:
        print("（未检测到 GitHub Desktop 安装，或无法判定自动更新状态）")
        return 1
    print("自动更新状态：" + ("已禁用（禁止更新）" if st else "已允许（可自动更新）"))
    return 0


def cmd_copilot(args):
    import copilot_config

    try:
        if args.file is not None:
            prompt = Path(args.file).read_text(encoding="utf-8-sig")
        elif args.preset:
            prompt = copilot_config.DEFAULT_COMMIT_INSTRUCTIONS
        elif args.clear:
            prompt = ""
        else:
            current = copilot_config.load_global_commit_instructions()
            print(f"全局指令文件：{current['path']}", file=sys.stderr)
            if current["prompt"]:
                status = "已设置本工具管理的提交说明提示词"
            elif current["exists"]:
                status = "文件已存在，尚未设置本工具管理的提示词"
            else:
                status = "文件尚不存在，尚未设置本工具管理的提示词"
            print(f"状态：{status}", file=sys.stderr)
            if current["other_instructions"].strip():
                print("文件还包含其他全局指令，保存时会保留。", file=sys.stderr)
            prompt = current["prompt"]
            sys.stdout.write(prompt)
            if prompt and not prompt.endswith("\n"):
                sys.stdout.write("\n")
            return 0

        result = copilot_config.save_global_commit_instructions(prompt)
        action = "已清除受管提示词" if not prompt.strip() else "已保存受管提示词"
        if not result["changed"]:
            action = "内容未变化"
        print(f"{action}：{result['path']}", file=sys.stderr)
        if result["backup_path"]:
            print(f"原文件备份：{result['backup_path']}", file=sys.stderr)
        return 0
    except (OSError, UnicodeError, ValueError, copilot_config.CopilotConfigConflictError) as exc:
        print(f"[错误] 无法读取或保存全局 Copilot 提示词：{exc}", file=sys.stderr)
        return 1


def build_parser():
    p = argparse.ArgumentParser(
        prog="cli.py",
        description="GitHub Desktop 汉化工具（命令行版，采用上游 MIT 译文及同版本官方底包适配，Windows 专用）",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("locate", help="自动检测 GitHub Desktop 安装目录").set_defaults(func=cmd_locate)
    sub.add_parser("versions", help="列出所有内置汉化版本").set_defaults(func=cmd_versions)

    ap = sub.add_parser("apply", help="应用指定版本的汉化")
    ap.add_argument("--path", help="resources/app 目录（缺省则自动检测）")
    ap.add_argument("--version", default=None,
                    help="汉化版本号（缺省用最新可用版本，如 3.6.10）")
    ap.set_defaults(func=cmd_apply)

    rp = sub.add_parser("restore", help="还原为英文原版")
    rp.add_argument("--path", help="resources/app 目录（缺省则自动检测）")
    rp.set_defaults(func=cmd_restore)

    up = sub.add_parser("update", help="禁用/允许 GitHub Desktop 自动更新")
    up.add_argument("--path", help="resources/app 目录（缺省则自动检测）")
    ug = up.add_mutually_exclusive_group()
    ug.add_argument("--disable", action="store_true", help="禁止自动更新（重命名 Update.exe）")
    ug.add_argument("--enable", action="store_true", help="允许自动更新（恢复 Update.exe）")
    ug.add_argument("--status", action="store_true", help="仅查看当前状态（默认）")
    up.set_defaults(func=cmd_update)

    cp = sub.add_parser("copilot", help="读取或编辑全局 Copilot 提交说明提示词")
    cg = cp.add_mutually_exclusive_group()
    cg.add_argument("--show", action="store_true",
                    help="读取受管提示词（默认；正文输出到 stdout，路径和状态输出到 stderr）")
    cg.add_argument("--file", metavar="UTF8_FILE",
                    help="从 UTF-8 文本文件读取并保存提示词；空文件清除受管区块")
    cg.add_argument("--preset", action="store_true", help="写入默认中文提交说明模板")
    cg.add_argument("--clear", action="store_true", help="清除本工具的提示词区块，保留其他全局指令")
    cp.set_defaults(func=cmd_copilot)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
