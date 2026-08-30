#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zhcore.py — 汉化工具核心逻辑（无 UI 依赖，可独立测试）

按版本组织：内置多个 GitHub Desktop 汉化版本（源自 743859910 的 MIT 整文件补丁，
每个版本含 Windows/main.js + renderer.js 成品中文文件）。``apply_version`` 将选定
版本的成品 JS 整体替换到 GitHub Desktop 的 resources/app 目录（先备份 .bak）。

字典来源：GitHub 用户 743859910 的 MIT 许可汉化
  https://github.com/743859910/GitHub_Desktop_Simplified_Chinese
"""
import os
import re
import shutil
import sys

# 让本模块在「开发态（gui/ 下直接运行）」也能 import 到仓库根的 zhtool.py
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from zhtool import (  # noqa: E402
    autodetect_appdir,
    resolve_app_files,
    MANIFEST_NAME,
)


def resource(rel):
    """解析打包后的资源路径：冻结态用 _MEIPASS，开发态用仓库根。"""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return os.path.join(base, rel)
    return os.path.join(REPO_ROOT, rel)


def local_dict_dir():
    """用户本地字典目录：EXE 同级 ``dictionaries/``。

    当 GitHub Desktop 推出内置多版本尚未覆盖的新版本时，用户可从字典项目
    下载该版本目录（含 main.js + renderer.js）放至此目录，工具会自动纳入
    版本列表并优先使用（同名版本本地覆盖内置）。
    """
    return os.path.join(os.path.dirname(sys.executable), "dictionaries")


def list_versions():
    """返回所有汉化版本号（内置 + EXE 同级本地，降序，最新在前）。

    本地版本与内置版本同名时，本地优先（用户覆盖）。
    """
    vers = {}
    # 内置
    root = resource("dictionaries")
    if os.path.isdir(root):
        for name in os.listdir(root):
            d = os.path.join(root, name)
            if (os.path.isdir(d)
                    and os.path.isfile(os.path.join(d, "main.js"))
                    and os.path.isfile(os.path.join(d, "renderer.js"))):
                vers[name] = "内置"
    # 本地（同名覆盖内置标记）
    local = local_dict_dir()
    if os.path.isdir(local):
        for name in os.listdir(local):
            d = os.path.join(local, name)
            if (os.path.isdir(d)
                    and os.path.isfile(os.path.join(d, "main.js"))
                    and os.path.isfile(os.path.join(d, "renderer.js"))):
                vers[name] = "本地"
    ordered = sorted(
        vers.keys(),
        key=lambda v: [int(x) for x in re.findall(r"\d+", v)],
        reverse=True,
    )
    return ordered


def list_version_sources():
    """返回 ``(version, source)`` 列表，source 为 ``"本地"`` 或 ``"内置"``。"""
    vers = {}
    root = resource("dictionaries")
    if os.path.isdir(root):
        for name in os.listdir(root):
            d = os.path.join(root, name)
            if (os.path.isdir(d)
                    and os.path.isfile(os.path.join(d, "main.js"))
                    and os.path.isfile(os.path.join(d, "renderer.js"))):
                vers[name] = "内置"
    local = local_dict_dir()
    if os.path.isdir(local):
        for name in os.listdir(local):
            d = os.path.join(local, name)
            if (os.path.isdir(d)
                    and os.path.isfile(os.path.join(d, "main.js"))
                    and os.path.isfile(os.path.join(d, "renderer.js"))):
                vers[name] = "本地"
    ordered = sorted(
        vers.keys(),
        key=lambda v: [int(x) for x in re.findall(r"\d+", v)],
        reverse=True,
    )
    return [(v, vers[v]) for v in ordered]


def version_file(version, target):
    """返回版本 version 的某目标文件（main.js / renderer.js）路径。

    优先本地（``EXE 同级/dictionaries/<version>/``），回退到内置。
    不存在返回 None。
    """
    p = os.path.join(local_dict_dir(), version, target)
    if os.path.isfile(p):
        return p
    p = resource(os.path.join("dictionaries", version, target))
    return p if os.path.isfile(p) else None


def detect_version(appdir):
    """从 GD 安装路径推断版本号（如 ...\\app-3.6.4\\resources\\app → 3.6.4）。"""
    m = re.search(r"app-(\d+\.\d+\.\d+)", appdir or "")
    return m.group(1) if m else None


def locate():
    """自动定位 GitHub Desktop 的 resources/app 目录。"""
    return autodetect_appdir()


def apply_version(appdir, version, log=print):
    """用内置版本 version 的 Windows 成品 JS 整体替换 GD 的 main.js / renderer.js。

    先备份原文件为 .bak，再整体拷贝，保证 100% 命中该版本翻译。
    仅支持 Windows（本工具为 Windows 专用）。
    """
    src_main = version_file(version, "main.js")
    src_renderer = version_file(version, "renderer.js")
    if not src_main or not src_renderer:
        log(f"✗ [错误] 内置版本 {version} 缺少 Windows 翻译文件")
        return False
    files = resolve_app_files(appdir, None, None)
    if not files:
        log("✗ [错误] 在指定目录未找到 main.js / renderer.js")
        return False
    ok = True
    applied_any = False
    for tgt, dst in files:
        src = version_file(version, tgt)
        if src is None or not os.path.isfile(src):
            log(f"· {tgt}：内置版本 {version} 无对应文件，跳过")
            ok = False
            continue
        bak = dst + ".bak"
        if not os.path.exists(bak):
            os.replace(dst, bak)
            log(f"  ✓ 已备份原文件 -> {bak}")
        shutil.copy2(src, dst)
        log(f"  ✓ 已应用 {version} 的 {tgt}")
        applied_any = True
    if applied_any:
        log(f"=== 应用完成（版本 {version}）===")
    else:
        log(f"✗ 未应用任何文件（版本 {version}）")
        ok = False
    return ok


def restore(appdir, log=print):
    files = resolve_app_files(appdir, None, None)
    if not files:
        log("✗ [错误] 未找到 main.js / renderer.js")
        return False
    done = False
    for tgt, path in files:
        bak = path + ".bak"
        if os.path.isfile(bak):
            os.replace(bak, path)
            log(f"✓ 已还原 {tgt}（来自 .bak）")
            done = True
        else:
            log(f"· {tgt}：无 .bak 备份，可能已是英文原版，跳过")
    mp = os.path.join(appdir, MANIFEST_NAME)
    if os.path.isfile(mp):
        try:
            os.remove(mp)
            log("✓ 已清除完整性清单")
        except OSError:
            pass
    if done:
        log("=== 还原完成 ===")
    else:
        log("=== 还原：无需还原（无 .bak 备份，可能已是原版）===")
    return done


def validate_builtin(log=print):
    """校验内置多版本汉化资源的完整性：每个版本均含非空 main.js / renderer.js。"""
    vers = list_versions()
    if not vers:
        log("⚠ 未找到任何内置汉化版本")
        return False
    log(f"✓ 内置版本共 {len(vers)} 个：{', '.join(vers)}")
    ok = True
    for v in vers:
        for tgt in ("main.js", "renderer.js"):
            p = version_file(v, tgt)
            if not p or not os.path.isfile(p):
                log(f"⚠ 版本 {v} 缺少 {tgt}")
                ok = False
                continue
            sz = os.path.getsize(p)
            if sz == 0:
                log(f"⚠ 版本 {v} 的 {tgt} 为空文件")
                ok = False
            else:
                log(f"  ✓ 版本 {v} · {tgt} · {sz:,} 字节")
    log("结论：" + ("校验通过 ✔" if ok else "校验未通过 ✗"))
    return ok


if __name__ == "__main__":
    # 简单自检：在临时副本上跑一遍 apply_version/restore
    import tempfile

    tmp = tempfile.mkdtemp(prefix="zhcore_test_")
    app = os.path.join(tmp, "resources", "app")
    os.makedirs(app)
    open(os.path.join(app, "main.js"), "w", encoding="utf-8").write('"About GitHub Desktop"')
    open(os.path.join(app, "renderer.js"), "w", encoding="utf-8").write('"Changes"')
    print("locate() ->", locate())
    vers = list_versions()
    print("内置版本数 ->", len(vers), "最新 ->", vers[0] if vers else None)
    if vers:
        rc = apply_version(app, vers[0], log=print)
        print("apply_version RC ->", rc)
        restore(app, log=print)
    shutil.rmtree(tmp, ignore_errors=True)
    print("SELFTEST OK")
