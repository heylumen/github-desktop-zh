#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cli.py — GitHub Desktop 汉化工具（命令行版）

与 GUI 共享 ``zhcore``：安装发现、版本校验、事务写入、备份与字典导入
使用同一套实现。适合脚本化与高级用户。

用法示例：
  python gui/cli.py locate
  python gui/cli.py versions
  python gui/cli.py apply --version 3.6.10
  python gui/cli.py apply --path "D:\\Portable\\GitHubDesktop"
  python gui/cli.py restore
  python gui/cli.py update --status
  python gui/cli.py import --source "D:\\Downloads\\3.6.11" --version 3.6.11
  python gui/cli.py copilot --show
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import zhcore


def _resolve_path(raw):
    """接受客户端 EXE、客户端根目录、resources 或 resources/app。"""
    text = str(raw or "").strip()
    if not text:
        text = zhcore.locate() or ""
    if not text:
        print("[错误] 未指定路径且无法自动检测，请用 --path 指定客户端目录。",
              file=sys.stderr)
        return None
    info = zhcore.install_info(text)
    if not info.available:
        print(f"[错误] {text} 不是可改写的 GitHub Desktop 安装。", file=sys.stderr)
        for error in info.errors:
            print("  · " + error, file=sys.stderr)
        if info.layout == "asar":
            print("  · 该安装以 app.asar 发布，当前版本不支持直接改写。", file=sys.stderr)
        return None
    return info.appdir


def _resolve_version(version):
    versions = zhcore.list_versions()
    if not versions:
        print("[错误] 未找到任何汉化版本。", file=sys.stderr)
        return None
    if version:
        if version not in versions:
            print(f"[错误] 版本 {version} 不存在，可用：{', '.join(versions)}", file=sys.stderr)
            return None
        return version
    return versions[0]


def cmd_locate(args):
    path = zhcore.locate(args.path)
    if not path:
        print("（未检测到 GitHub Desktop 安装目录）")
        return 1
    info = zhcore.install_info(path)
    print(path)
    print(f"版本：{info.version or '未知'}"
          f"（{info.version_source or '无法识别'}）"
          f"｜布局：{info.layout}"
          f"｜便携版：{'是' if info.portable else '否'}", file=sys.stderr)
    return 0


def cmd_versions(args):
    pairs = zhcore.list_version_sources()
    if not pairs:
        print("（未找到任何汉化版本）")
        return 1
    builtin = sum(1 for _, source in pairs if source == "内置")
    print(f"可用汉化版本（共 {len(pairs)} 个，内置 {builtin} 个，最新在前）：")
    for version, source in pairs:
        print(f"  {version}  {'（本地）' if source == '本地' else ''}".rstrip())
    return 0


def cmd_apply(args):
    appdir = _resolve_path(args.path)
    if not appdir:
        return 2
    version = _resolve_version(args.version)
    if not version:
        return 2
    result = zhcore.apply_version(
        appdir, version, allow_mismatch=args.allow_mismatch)
    return 0 if result.ok else 1


def cmd_restore(args):
    appdir = _resolve_path(args.path)
    if not appdir:
        return 2
    result = zhcore.restore(appdir)
    return 0 if result.ok else 1


def cmd_update(args):
    appdir = None
    if args.path:
        appdir = _resolve_path(args.path)
        if not appdir:
            return 2
    if args.enable:
        return 0 if zhcore.set_auto_update_disabled(False, appdir).ok else 1
    if args.disable:
        return 0 if zhcore.set_auto_update_disabled(True, appdir).ok else 1
    state = zhcore.update_state(appdir)
    labels = {
        "enabled": "已允许（可自动更新）",
        "disabled": "已禁用（禁止自动更新）",
        "inconsistent": "状态异常（Update.exe 与 .disabled 同时存在）",
        "missing": "未检测到更新器",
    }
    print(f"自动更新状态：{labels[state['state']]}")
    if state.get("deploy_root"):
        print(f"更新器目录：{state['deploy_root']}", file=sys.stderr)
    return 0 if state["state"] in ("enabled", "disabled") else 1


def cmd_import(args):
    result = zhcore.import_local_dictionary(args.source, args.version)
    if result.ok:
        print(f"已导入汉化版本 {result.data.get('version')} -> {result.data.get('target')}")
    return 0 if result.ok else 1


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
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="GitHub Desktop 汉化工具（命令行版，支持官方安装与便携版，Windows 专用）",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    locate = sub.add_parser("locate", help="自动检测 GitHub Desktop 安装目录")
    locate.add_argument("--path", help="优先验证的客户端路径（缺省全自动检测）")
    locate.set_defaults(func=cmd_locate)

    sub.add_parser("versions", help="列出所有可用汉化版本").set_defaults(func=cmd_versions)

    apply = sub.add_parser("apply", help="应用指定版本的汉化")
    apply.add_argument("--path", help="客户端 EXE / 根目录 / resources/app")
    apply.add_argument("--version", default=None, help="汉化版本号（缺省用最新版本）")
    apply.add_argument("--allow-mismatch", action="store_true",
                       help="客户端版本未知或与所选不一致时仍允许写入（危险）")
    apply.set_defaults(func=cmd_apply)

    restore = sub.add_parser("restore", help="还原为英文原版")
    restore.add_argument("--path", help="客户端 EXE / 根目录 / resources/app")
    restore.set_defaults(func=cmd_restore)

    update = sub.add_parser("update", help="禁用/允许 GitHub Desktop 自动更新")
    update.add_argument("--path", help="客户端 EXE / 根目录 / resources/app")
    group = update.add_mutually_exclusive_group()
    group.add_argument("--disable", action="store_true", help="禁止自动更新（重命名 Update.exe）")
    group.add_argument("--enable", action="store_true", help="允许自动更新（恢复 Update.exe）")
    group.add_argument("--status", action="store_true", help="仅查看当前状态（默认）")
    update.set_defaults(func=cmd_update)

    import_cmd = sub.add_parser("import", help="导入下载好的版本文件夹到本地字典目录")
    import_cmd.add_argument("--source", required=True,
                            help="包含 main.js + renderer.js 的文件夹（或其上级/Windows 目录）")
    import_cmd.add_argument("--version", help="目标版本号；缺省从文件夹或 provenance.json 推断")
    import_cmd.set_defaults(func=cmd_import)

    copilot = sub.add_parser("copilot", help="读取或编辑全局 Copilot 提交说明提示词")
    group = copilot.add_mutually_exclusive_group()
    group.add_argument("--show", action="store_true",
                       help="读取受管提示词（默认；正文输出到 stdout）")
    group.add_argument("--file", metavar="UTF8_FILE",
                       help="从 UTF-8 文本文件读取并保存提示词；空文件清除受管区块")
    group.add_argument("--preset", action="store_true", help="写入默认中文提交说明模板")
    group.add_argument("--clear", action="store_true", help="清除提示词区块，保留其他全局指令")
    copilot.set_defaults(func=cmd_copilot)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
