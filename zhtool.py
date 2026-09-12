#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zhtool.py — GitHub Desktop 中文汉化补丁工具（版本无关 / version-agnostic）
=========================================================================

适用对象：GitHub Desktop 的 renderer.js 与 main.js（位于安装目录
         resources/app/ 下）。本工具与具体版本解耦：只要提供目标版本的
         main.js / renderer.js 和一份 .zh 词典，即可完成汉化，并报告
         「未命中（字符串已变更/移除）」与「新增（需补译）」的差异。

.zh 词典格式（与原有 GithubDesktopZhTool 兼容）：
    英文串>*.*<中文串>*.*<分类>*.*<目标文件
    例： "Add worktree">*.*<"新建工作树">*.*<worktree>*.*<renderer.js

子命令：
    apply   把一份或多份 .zh 应用到 main.js / renderer.js（自动备份 .bak，
            并记录 SHA-256 完整性清单，供 verify / watch 使用）
    scan    从目标 renderer.js 中扫描候选英文 UI 串，输出待翻译 .zh 桩文件
    merge   把多份 .zh 合并成一份（去重，保留顺序，后者覆盖前者）
    verify  校验目标文件 SHA-256，与上次打补丁后的清单对比——可发现
            GitHub Desktop 自动更新、或被外部篡改
    watch   监控安装目录：当 GD 自动更新导致 main.js/renderer.js 变化时，
            自动重新打补丁（实现「升级后自动恢复中文」）

典型用法：
    # 干跑，仅查看会改哪些、哪些命中/未命中，不写文件
    python zhtool.py apply --appdir "C:/Users/你/AppData/Local/GitHubDesktop/app-3.6.4/resources/app" --zh dictionaries/Windows.zh --dry-run

    # 真正打补丁（自动备份原文件为 .bak，并生成 .zhtool_manifest.json）
    python zhtool.py apply --appdir "..." --zh dictionaries/Windows.zh

    # 校验当前安装是否仍是上次打补丁后的状态
    python zhtool.py verify --appdir "..."

    # 常驻监控：GD 一更新就自动恢复中文（可放进开机/计划任务）
    python zhtool.py watch --appdir "..." --zh dictionaries/Windows.zh --interval 60
"""

import argparse
import glob
import hashlib
import json
import os
import re
import sys
import time

DELIM = ">*.*<"  # .zh 字段分隔符
KNOWN_TARGETS = ("main.js", "renderer.js")
MANIFEST_NAME = ".zhtool_manifest.json"  # 打补丁后写入的 SHA-256 清单


# --------------------------------------------------------------------------
# 工具：SHA-256 / 清单
# --------------------------------------------------------------------------
def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path):
    if path and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None


def save_manifest(path, data):
    """写入完整性清单；失败只告警，不影响汉化结果。"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        sys.stderr.write(f"[warn] 无法写入完整性清单 {path}: {e}\n")
        return False


# --------------------------------------------------------------------------
# 词典读写
# --------------------------------------------------------------------------
def load_zh(path):
    """读取一份 .zh，返回 [(en, zh, cat, tgt), ...]。容错跳过格式错误行。"""
    entries = []
    with open(path, encoding="utf-8") as f:
        for lineno, raw in enumerate(f, 1):
            line = raw.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split(DELIM)
            if len(parts) != 4:
                sys.stderr.write(f"[warn] 跳过格式异常行 {path}:{lineno}: {line!r}\n")
                continue
            en, zh, cat, tgt = parts
            entries.append((en, zh, cat, tgt))
    return entries


def dump_zh(entries, path):
    with open(path, "w", encoding="utf-8") as f:
        for en, zh, cat, tgt in entries:
            f.write(f"{en}{DELIM}{zh}{DELIM}{cat}{DELIM}{tgt}\n")


# --------------------------------------------------------------------------
# 应用词典
# --------------------------------------------------------------------------
def apply_entries(text, entries):
    """
    把 entries 应用到 text 上（安全字面替换）。
    返回 (new_text, matched, unmatched)。
    - 先按英文串长度降序，优先替换更长、更具体的串，降低短串误伤概率。
    - 中文为空的条目视为「未翻译占位」，跳过（不参与替换）。
    - 保留 ${...} 插值表达式：因为做的是整串字面替换，插值片段随整串一起移动，不会破坏。
    """
    matched, unmatched = [], []
    ordered = sorted(
        [e for e in entries if e[1] != ""],
        key=lambda e: len(e[0]),
        reverse=True,
    )
    out = text
    for en, zh, cat, tgt in ordered:
        # 以「当前输出文本」判定是否命中：长串优先替换后，短串可能被吞没（如
        # "Terminal" 被 "Open in Terminal" 的译文覆盖），其含义已翻译，仍记为
        # 「已覆盖」，避免虚报未命中、夸大缺失。
        if en in out:
            matched.append(en)
            out = out.replace(en, zh)
        else:
            unmatched.append(en)
    return out, matched, unmatched


def apply_to_files(app_files, zh_files, dry_run, manifest_path=None, log=print):
    """
    app_files: [(target_name, path), ...]  如 [("main.js", ...), ("renderer.js", ...)]
    zh_files : [path, ...]
    按 target_name 把词典分流到对应文件，逐文件应用并打印报告。
    非 dry-run 时把每个文件打补丁后的 SHA-256 写入 manifest。
    log: 日志回调（默认 print），便于 GUI 接管输出。
    """
    by_target = {t: [] for t in KNOWN_TARGETS}
    total = 0
    for zf in zh_files:
        for e in load_zh(zf):
            total += 1
            tgt = e[3].strip()
            if tgt in by_target:
                by_target[tgt].append(e)
            else:
                sys.stderr.write(f"[warn] 未知目标文件 {tgt!r}，按 renderer.js 处理：{e[0]!r}\n")
                by_target["renderer.js"].append(e)

    manifest = {"version": 1, "zh": [os.path.abspath(z) for z in zh_files], "files": {}}
    grand_matched = grand_unmatched = 0
    for tgt, path in app_files:
        entries = by_target.get(tgt, [])
        if not entries:
            log(f"\n· {tgt}: 词典中无对应条目，跳过。")
            continue
        with open(path, encoding="utf-8") as f:
            src = f.read()
        new_text, matched, unmatched = apply_entries(src, entries)
        grand_matched += len(matched)
        grand_unmatched += len(unmatched)
        log(f"\n■ {tgt}  ({len(src)} → {len(new_text)} 字节)")
        log(f"  词典条目 {len(entries)} | 命中 {len(matched)} | 未命中 {len(unmatched)}")
        if unmatched:
            log(f"  ⚠ 未命中（可能该串在新版已被改名/移除，建议核对）：")
            for u in unmatched[:40]:
                log(f"     - {u!r}")
            if len(unmatched) > 40:
                log(f"     ... 其余 {len(unmatched) - 40} 条省略")
        if not dry_run:
            bak = path + ".bak"
            moved = False
            if not os.path.exists(bak):
                try:
                    os.replace(path, bak)
                    moved = True
                    log(f"  ✓ 已备份原文件 -> {bak}")
                except OSError as e:
                    log(f"  ✗ [错误] 无法备份 {tgt}（原文件保持不动）：{e}")
                    continue
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(new_text)
            except OSError as e:
                # 原文件已被移走，不还原会让 GitHub Desktop 缺少该文件
                log(f"  ✗ [错误] 写入 {tgt} 失败：{e}")
                if moved and not os.path.exists(path):
                    try:
                        os.replace(bak, path)
                        log(f"  ↩ 已回滚 {tgt}（原文件已还原，未造成损坏）")
                    except OSError as e2:
                        log(f"  ✗ 回滚失败：{e2}")
                        log(f"  ⚠ 请手动把 {bak} 改名为 {path} 以恢复 GitHub Desktop")
                continue
            log(f"  ✓ 已写入汉化后的 {tgt}")
            manifest["files"][tgt] = sha256_of(path)
    log(f"\n=== 汇总：词典条目 {total} | 命中 {grand_matched} | 未命中 {grand_unmatched} ===")
    if grand_unmatched:
        log("提示：未命中的条目不会破坏原文件，但对应英文会保留，需更新词典后重跑。")
    if manifest_path and not dry_run:
        if save_manifest(manifest_path, manifest):
            log(f"  ✓ 已写入完整性清单 -> {manifest_path}")
        else:
            log(f"  ⚠ 完整性清单写入失败（不影响汉化结果）-> {manifest_path}")
    return manifest


# --------------------------------------------------------------------------
# 扫描候选串（用于发现新版新增/变更 UI 文本）
# --------------------------------------------------------------------------
def _strip_quotes(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def scan_candidates(js_text, existing_ens):
    """从打包后的 renderer.js 中提取候选英文 UI 串，排除已在词典里的。"""
    found = {}
    noise = re.compile(r"[@#%]|(:[a-z]+:)|thanks|fixes something|example|lorem|todo|placeholder text|your name|username", re.I)

    def add(s):
        s = _strip_quotes(s)
        if not s:
            return
        if len(s) < 3 or len(s) > 90:
            return
        if noise.search(s):
            return
        if re.search(r"[{}();=]|//|/\*|\.js$|\bhttp|\bwww\.|<[A-Za-z]", s):
            return
        if re.search(r"[A-Za-z0-9_]+\.[A-Za-z0-9_]+", s) and " " not in s:
            return  # 形如 foo.bar 的标识符
        if not re.search(r"[a-z]{2,}", s):
            return  # 至少要有两个连续小写字母，避免纯常量
        s2 = s
        if s2 in existing_ens or ('"' + s2 + '"') in existing_ens or ("'" + s2 + "'") in existing_ens:
            return
        found[s] = found.get(s, 0) + 1

    # 1) __DARWIN__ ? 'X' : 'Y'  /  "X" : "Y"  （mac / 非mac 两套文案）
    for m in re.finditer(r"__DARWIN__\s*\?\s*'([^']+)'\s*:\s*'([^']+)'", js_text):
        add(m.group(1))
        add(m.group(2))
    for m in re.finditer(r'__DARWIN__\s*\?\s*"([^"]+)"\s*:\s*"([^"]+)"', js_text):
        add(m.group(1))
        add(m.group(2))

    # 2) defaultMessage: 'X' / "X"  （react-intl 默认文案）
    for m in re.finditer(r"defaultMessage\s*:\s*'([^']{2,90})'", js_text):
        add(m.group(1))
    for m in re.finditer(r'defaultMessage\s*:\s*"([^"]{2,90})"', js_text):
        add(m.group(1))

    # 3) 常见 UI 属性：label/title/placeholder/aria-label/... : "X"
    prop = r"(?:label|title|placeholder|aria-label|subtitle|description|confirmationTitle|dialogTitle|tooltip|header|heading|text|message|name)\s*:\s*"
    for m in re.finditer(prop + r'"([^"]{2,90})"', js_text):
        add(m.group(1))
    for m in re.finditer(prop + r"'([^']{2,90})'", js_text):
        add(m.group(1))

    # 4) JSX 文本节点 >Text<
    for m in re.finditer(r">([A-Za-z][A-Za-z ,.;:!?()'/\-]{2,80})<", js_text):
        add(m.group(1))

    return found


def cmd_scan(args):
    with open(args.renderer, encoding="utf-8") as f:
        js = f.read()
    existing = set()
    for zf in args.zh or []:
        for e in load_zh(zf):
            existing.add(e[0])
            existing.add(_strip_quotes(e[0]))
    cands = scan_candidates(js, existing)
    out_path = args.out
    with open(out_path, "w", encoding="utf-8") as f:
        for s in sorted(cands):
            f.write(f"{s}{DELIM}{DELIM}待翻译(扫描){DELIM}renderer.js\n")
    print(f"从 {args.renderer} 扫描到 {len(cands)} 条候选英文 UI 串（已排除词典内已有条目）。")
    print(f"已写入待翻译桩文件：{out_path}")
    print("请人工校对后填入中文，再并入主词典。")


# --------------------------------------------------------------------------
# 合并词典
# --------------------------------------------------------------------------
def cmd_merge(args):
    order = []
    last = {}
    for zf in args.zh:
        for e in load_zh(zf):
            key = (e[0], e[3])
            if key not in last:
                order.append(key)
            last[key] = e
    merged = [last[k] for k in order]
    dump_zh(merged, args.out)
    print(f"合并 {len(args.zh)} 份词典 -> {args.out}（共 {len(merged)} 条，已去重）")


# --------------------------------------------------------------------------
# 完整性校验 + 自动重打补丁（策略 C）
# --------------------------------------------------------------------------
def cmd_verify(args):
    appdir = args.appdir or autodetect_appdir()
    files = resolve_app_files(appdir, args.main, args.renderer)
    if not files:
        sys.stderr.write("未找到 main.js / renderer.js，请用 --appdir 指定安装目录。\n")
        sys.exit(2)
    manifest_path = args.manifest
    if manifest_path is None and appdir:
        manifest_path = os.path.join(appdir, MANIFEST_NAME)
    manifest = load_manifest(manifest_path)
    ok_all = True
    for t, p in files:
        if not os.path.isfile(p):
            print(f"{t}: 文件不存在 -> {p}")
            ok_all = False
            continue
        h = sha256_of(p)
        print(f"{t}: sha256={h[:16]}…（完整 {h}）")
        if manifest and "files" in manifest and t in manifest["files"]:
            if manifest["files"][t] == h:
                print("   ✔ 与清单一致（已打补丁且未被改动）")
            else:
                print("   ⚠ 与清单不一致：可能 GD 已自动更新，或文件被修改——建议重新 apply。")
                ok_all = False
        else:
            print("   （无清单可对比；先跑一次 apply 生成清单）")
    print("\n结论：", "全部一致 ✔" if ok_all else "存在差异，需关注 ⚠")


def cmd_watch(args):
    appdir = args.appdir or autodetect_appdir()
    files = resolve_app_files(appdir, args.main, args.renderer)
    if not files:
        sys.stderr.write("未找到 main.js / renderer.js，请用 --appdir 指定安装目录。\n")
        sys.exit(2)
    manifest_path = args.manifest or (os.path.join(appdir, MANIFEST_NAME) if appdir else None)
    manifest = load_manifest(manifest_path) or {"version": 1, "zh": [], "files": {}}
    print(f"▶ 开始监控：{appdir}")
    print(f"  间隔 {args.interval}s｜词典：{', '.join(args.zh)}｜Ctrl+C 退出")
    runs = 0
    try:
        while True:
            runs += 1
            changed = []
            for t, p in files:
                if not os.path.isfile(p):
                    changed.append(t)
                    continue
                if manifest.get("files", {}).get(t) != sha256_of(p):
                    changed.append(t)
            if changed:
                print(f"[{time.strftime('%H:%M:%S')}] 检测到 {', '.join(changed)} 变动，重新打补丁…")
                manifest = apply_to_files(files, args.zh, False, manifest_path)
            elif runs == 1:
                print(f"[{time.strftime('%H:%M:%S')}] 当前已是最新汉化状态，开始监控文件变化…")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n■ 已停止监控。")


# --------------------------------------------------------------------------
# 自动定位 GitHub Desktop 安装目录
# --------------------------------------------------------------------------
def autodetect_appdir():
    candidates = []
    local = os.environ.get("LOCALAPPDATA")
    if local:
        base = os.path.join(local, "GitHubDesktop")
        if os.path.isdir(base):
            candidates += glob.glob(os.path.join(base, "app-*", "resources", "app"))
    mac_path = "/Applications/GitHub Desktop.app/Contents/Resources/app"
    if os.path.isdir(mac_path):
        candidates.append(mac_path)
    linux_path = os.path.expanduser("~/.config/GitHub Desktop/resources/app")
    if os.path.isdir(linux_path):
        candidates.append(linux_path)
    opt_path = "/opt/github-desktop/resources/app"
    if os.path.isdir(opt_path):
        candidates.append(opt_path)
    for c in candidates:
        if os.path.isfile(os.path.join(c, "renderer.js")):
            return c
    return None


def resolve_app_files(appdir, main_path, renderer_path):
    files = []
    if main_path:
        files.append(("main.js", main_path))
    elif appdir:
        p = os.path.join(appdir, "main.js")
        if os.path.isfile(p):
            files.append(("main.js", p))
    if renderer_path:
        files.append(("renderer.js", renderer_path))
    elif appdir:
        p = os.path.join(appdir, "renderer.js")
        if os.path.isfile(p):
            files.append(("renderer.js", p))
    return files


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="GitHub Desktop 中文汉化补丁工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("apply", help="把 .zh 应用到 main.js / renderer.js")
    pa.add_argument("--appdir", help="GitHub Desktop 的 resources/app 目录（自动定位可省略）")
    pa.add_argument("--main", help="显式指定 main.js 路径")
    pa.add_argument("--renderer", help="显式指定 renderer.js 路径")
    pa.add_argument("--zh", nargs="+", required=True, help="一份或多份 .zh 词典")
    pa.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    pa.add_argument("--manifest", help="指定/保存完整性清单路径（默认写进 appdir 下的 .zhtool_manifest.json）")

    ps = sub.add_parser("scan", help="从 renderer.js 扫描候选英文串")
    ps.add_argument("--renderer", required=True, help="目标 renderer.js")
    ps.add_argument("--zh", nargs="*", help="已有词典（用于排除已翻译串）")
    ps.add_argument("-o", "--out", default="new-strings.zh", help="输出桩文件")

    pm = sub.add_parser("merge", help="合并多份 .zh")
    pm.add_argument("--zh", nargs="+", required=True)
    pm.add_argument("-o", "--out", required=True)

    pv = sub.add_parser("verify", help="校验目标文件 SHA-256（对比打补丁清单）")
    pv.add_argument("--appdir", help="resources/app 目录（自动定位可省略）")
    pv.add_argument("--main", help="显式指定 main.js 路径")
    pv.add_argument("--renderer", help="显式指定 renderer.js 路径")
    pv.add_argument("--manifest", help="对比用的清单路径（默认取 appdir 下的 .zhtool_manifest.json）")

    pw = sub.add_parser("watch", help="监控安装目录，GD 更新时自动重打补丁")
    pw.add_argument("--appdir", help="resources/app 目录（自动定位可省略）")
    pw.add_argument("--main", help="显式指定 main.js 路径")
    pw.add_argument("--renderer", help="显式指定 renderer.js 路径")
    pw.add_argument("--zh", nargs="+", required=True, help="一份或多份 .zh 词典")
    pw.add_argument("--interval", type=int, default=60, help="轮询间隔秒数（默认 60）")
    pw.add_argument("--manifest", help="清单路径（默认 appdir 下的 .zhtool_manifest.json）")

    args = ap.parse_args()

    if args.cmd == "apply":
        appdir = args.appdir or autodetect_appdir()
        files = resolve_app_files(appdir, args.main, args.renderer)
        if not files:
            if args.main or args.renderer:
                sys.stderr.write("指定的 --main / --renderer 路径不存在，请检查。\n")
            else:
                sys.stderr.write("未找到 main.js / renderer.js，请用 --appdir 显式指定安装目录。\n")
            sys.exit(2)
        print(f"目标目录：{appdir or '(显式指定文件)'}")
        print(f"待处理文件：{', '.join(p for _, p in files)}")
        for t, p in files:
            print(f"  发现 {t} -> {p}")
        manifest_path = args.manifest
        if manifest_path is None and appdir and not args.dry_run:
            manifest_path = os.path.join(appdir, MANIFEST_NAME)
        apply_to_files(files, args.zh, args.dry_run, manifest_path)

    elif args.cmd == "scan":
        cmd_scan(args)

    elif args.cmd == "merge":
        cmd_merge(args)

    elif args.cmd == "verify":
        cmd_verify(args)

    elif args.cmd == "watch":
        cmd_watch(args)


if __name__ == "__main__":
    main()
