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


def _scan_dict_dirs():
    """扫描字典目录，返回 ``{版本号: "内置"/"本地"}``。

    本地目录（EXE 同级 ``dictionaries/``）与内置同名时以「本地」为准，
    便于用户用自己的翻译覆盖内置版本。
    """
    vers = {}
    for base, source in ((resource("dictionaries"), "内置"),
                         (local_dict_dir(), "本地")):
        if not os.path.isdir(base):
            continue
        for name in os.listdir(base):
            d = os.path.join(base, name)
            if (os.path.isdir(d)
                    and os.path.isfile(os.path.join(d, "main.js"))
                    and os.path.isfile(os.path.join(d, "renderer.js"))):
                vers[name] = source
    return vers


def _version_sort_key(ver):
    """版本号排序键：按数字段逐段比较。

    不含数字的名字排在最后（旧写法直接返回空列表，虽然也能跑，
    但语义含糊且依赖列表比较的隐式行为）。
    """
    nums = [int(x) for x in re.findall(r"\d+", ver)]
    return (1, nums) if nums else (0, [])


def _sorted_versions(vers):
    """已扫描的版本号，降序（最新在前）。"""
    return sorted(vers.keys(), key=_version_sort_key, reverse=True)


def list_versions():
    """返回所有汉化版本号（内置 + EXE 同级本地，降序，最新在前）。"""
    return _sorted_versions(_scan_dict_dirs())


def list_version_sources():
    """返回 ``(version, source)`` 列表，source 为 ``"本地"`` 或 ``"内置"``。"""
    vers = _scan_dict_dirs()
    return [(v, vers[v]) for v in _sorted_versions(vers)]


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
        moved = False
        if not os.path.exists(bak):
            try:
                os.replace(dst, bak)
                moved = True
                log(f"  ✓ 已备份原文件 -> {bak}")
            except OSError as e:
                log(f"✗ [错误] 无法备份 {tgt}（原文件保持不动）：{e}")
                ok = False
                continue
        try:
            shutil.copy2(src, dst)
        except OSError as e:
            log(f"✗ [错误] 写入 {tgt} 失败：{e}")
            # 关键回滚：原文件已被移走，若不还原，GitHub Desktop 会缺少该文件而无法启动
            if moved and not os.path.exists(dst):
                try:
                    os.replace(bak, dst)
                    log(f"  ↩ 已回滚 {tgt}（原文件已还原，未造成损坏）")
                except OSError as e2:
                    log(f"✗ 回滚失败：{e2}")
                    log(f"  ⚠ 请手动把 {bak} 改名为 {dst} 以恢复 GitHub Desktop")
            ok = False
            continue
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
    failed = False
    for tgt, path in files:
        bak = path + ".bak"
        if os.path.isfile(bak):
            try:
                os.replace(bak, path)
            except OSError as e:
                log(f"✗ [错误] 还原 {tgt} 失败：{e}")
                log("  请关闭 GitHub Desktop 后重试（文件可能正被占用）")
                failed = True
                continue
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
    return done and not failed


# ============================================================
# 禁止 GitHub Desktop 自动更新（Squirrel.Windows 机制）
#
# GitHub Desktop 基于 Electron 的 Squirrel.Windows 自动更新：
# 启动后由 resources/app/main.js 中的 autoUpdater 经部署根目录下的
# Update.exe（路径 = process.execPath/../../Update.exe）执行更新检查与安装。
# 该机制没有内置「关闭自动更新」开关，故本工具采用社区稳妥做法：
# 将 Update.exe 重命名为 Update.exe.disabled 即可彻底阻断自动更新；
# 恢复时改名回 Update.exe 即可重新启用。操作可逆、仅影响本机部署根，
# 不改动 GitHub Desktop 任何程序文件。
# ============================================================

def _deploy_root(appdir):
    """从 resources/app 目录上溯三级得到 GD 部署根（含 Update.exe）。

    appdir 形如 .../GitHubDesktop/app-3.6.5/resources/app
      -> resources -> app-3.6.5 -> GitHubDesktop

    只接受严格符合 ``.../<任意名>/resources/app`` 结构的路径：
    用户若误填了很短的相对路径（例如 "app"），abspath 会把它补成
    当前目录下的绝对路径并凑够三级，从而指向毫不相干的上级目录——
    那可能在磁盘任意位置误改同名的 Update.exe，因此这里直接拒绝。
    """
    if not appdir:
        return None
    d = os.path.abspath(appdir)
    if os.path.basename(d).lower() != "app":
        return None
    resources = os.path.dirname(d)
    if os.path.basename(resources).lower() != "resources":
        return None
    return os.path.dirname(os.path.dirname(resources))


def find_update_exe(appdir=None):
    """定位 Squirrel 更新器 Update.exe（规范化路径）。

    无论当前是 Update.exe（允许更新）还是 Update.exe.disabled（已禁用），
    均返回规范路径 ``.../GitHubDesktop/Update.exe``，便于上层统一 rename 切换。
    找不到任何线索时返回 None。
    """
    roots = []
    for d in (appdir, autodetect_appdir()):
        if d:
            root = _deploy_root(d)
            if root:
                roots.append(root)
    local = os.environ.get("LOCALAPPDATA")
    if local:
        roots.append(os.path.join(local, "GitHubDesktop"))
    # 去重保序
    seen, uniq = set(), []
    for r in roots:
        if r and r not in seen:
            seen.add(r)
            uniq.append(r)
    for r in uniq:
        cand = os.path.join(r, "Update.exe")
        disabled = cand + ".disabled"
        # 存在 Update.exe 或 Update.exe.disabled 任一，即认定该部署根
        if os.path.isfile(cand) or os.path.isfile(disabled):
            return cand
    # 兜底：扫描 LOCALAPPDATA/GitHubDesktop 下含 Update.exe / Update.exe.disabled 的目录
    if local:
        base = os.path.join(local, "GitHubDesktop")
        if os.path.isdir(base):
            for name in os.listdir(base):
                nl = name.lower()
                if nl == "update.exe" or nl == "update.exe.disabled":
                    return os.path.join(base, "Update.exe")  # 规范化回 canonical
    return None


def auto_update_disabled(appdir=None):
    """返回当前是否已禁用自动更新。

    返回 True  = 已禁用（Update.exe 被重命名为 .disabled）
    返回 False = 允许更新（Update.exe 就位）
    返回 None  = 未检测到 GitHub Desktop / 无法判定
    """
    p = find_update_exe(appdir)
    if p is None:
        return None
    return not os.path.isfile(p)


def set_auto_update_disabled(enable, appdir=None, log=print):
    """enable=True  => 禁止自动更新（Update.exe -> Update.exe.disabled）；
       enable=False => 允许自动更新（Update.exe.disabled -> Update.exe）。

    返回 True 表示达到目标状态（无论是否需要改动），False 表示失败。
    """
    p = find_update_exe(appdir)
    if p is None:
        log("✗ [错误] 未找到 GitHub Desktop 的 Update.exe（可能尚未安装，或安装路径异常）")
        return False
    disabled_name = p + ".disabled"
    if enable:
        if os.path.isfile(disabled_name):
            log("· 自动更新已处于禁用状态（Update.exe.disabled 已存在）")
            return True
        if os.path.isfile(p):
            try:
                os.rename(p, disabled_name)
            except OSError as e:
                log(f"✗ [错误] 无法禁用自动更新：{e}")
                log("  请关闭 GitHub Desktop 后以普通用户身份运行本工具（默认安装无需管理员）")
                return False
            log("✓ 已禁止自动更新（Update.exe 已重命名为 Update.exe.disabled）")
        else:
            # 既无 Update.exe 也无 .disabled：可能已被其它方式移除
            log("· 未找到 Update.exe，可能已被手动移除，自动更新应已失效")
        return True
    else:
        if os.path.isfile(disabled_name):
            try:
                os.rename(disabled_name, p)
            except OSError as e:
                log(f"✗ [错误] 无法恢复自动更新：{e}")
                return False
            log("✓ 已允许自动更新（Update.exe 已恢复）")
            return True
        if os.path.isfile(p):
            log("· 自动更新已处于允许状态（Update.exe 就位）")
            return True
        log("✗ [错误] 既无 Update.exe 也无 Update.exe.disabled，无法恢复自动更新")
        return False


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
