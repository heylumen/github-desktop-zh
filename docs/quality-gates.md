# 质量门禁（开发者 + 用户视角）

本文件是门禁的单一入口。CI 执行完整命令集；`gui/build.bat` 执行字典/隐私/一致性/对比度/截图/构建/归档检查；pyright、ruff 与覆盖率由 CI 或本地手动执行。

## 1. 分层

| 层级 | 何时 | 目标 |
|---|---|---|
| L0 本地 | 提交前 | 语法/静态/单测，快速反馈 |
| L1 PR/推送 | 每次 push/PR | 代码、状态、文档、构建、打包冒烟 |
| L2 发布 | tag/Release | 清洁工作树、tag、哈希、发布元数据 |
| L3 人工 | 发版前/夜间 | 真实客户端、Win10/Win11、高对比度、Snap |

## 2. 可执行命令

```bash
# 代码与事实源
python scripts/check_privacy.py
python scripts/check_self_methods.py
python scripts/check_consistency.py
python scripts/check_contrast.py
pyright
ruff check .

# 逻辑 + 覆盖率（当前基线 69.5%，阈值 68%）
python -m coverage run --source=gui -m unittest discover -s tests -v
python -m coverage report --fail-under=68

# 截图回归（light/dark × 首页/About）
python scripts/check_visual.py

# 打包
python -m PyInstaller --clean --noconfirm --distpath gui/dist --workpath gui/build github-desktop-zh-1.0.3.spec
python scripts/verify_archive.py gui/dist/github-desktop-zh-1.0.3.exe --version 1.0.3
python scripts/smoke_exe.py gui/dist/github-desktop-zh-1.0.3.exe
python scripts/build_release.py --exe gui/dist/github-desktop-zh-1.0.3.exe
python scripts/check_consistency.py

# 仅发布/tag
python scripts/check_release.py --require-tag --exe gui/dist/github-desktop-zh-1.0.3.exe
```

## 3. 当前覆盖

- 单一事实源：`gui/product_meta.py` → spec/build_release/verify_archive/app。
- 版本选择器状态：0/1/2/3/4 个版本、chips/combo、busy（`test_app_main.py`）。
- 覆盖率：`coverage` 总覆盖率基线 69.5%，门禁 68%（`gui/cli.py` 子进程路径暂未计入）。
- 截图：`tests/visual/baseline/` 4 张（light/dark × 首页/About），像素差异阈值 2%。
- 打包态：四页、About、版本选择器、窗口 chrome（`--self-test` + `smoke_exe`）。
- 属性/方法：`check_self_methods.py`，防止 `self._missing()`。
- 对比度：`check_contrast.py`，11–13px 可读文字低于 4.5:1 失败。
- 类型/死代码：`pyright` 当前 0 errors；`ruff check` 当前 0 errors（F401/F841/F821/F811）。
- 发布：`.github/workflows/release-gate.yml` + `check_release.py`。

## 4. 开发者视角检查

- 改 UI：同时看 light/dark、2/4 个版本、busy、0 版本、最小窗口。
- 改版本：更新 `product_meta`，跑 consistency；不要手改多处。
- 改文案：不要写“一键/极速”，状态要具体；About 区分“内置”和“仓库来源”。
- 改 QSS：跑 contrast；`#9ca3af`（浅色）/`#6b7280`（深色）只用于禁用。
- 删功能：搜残留关键词并删除模块/QSS/截图/文档，跑 self-method/死代码检查。
- 发布：只在 tag + clean + gate 通过后上传；Release 资产为 EXE、SHA256SUMS 与选定的官方客户端安装包。

## 5. 用户视角检查

- 首次启动：无崩溃；无版本 / 1 版 / 2 版 / 多版都能看到合理选择器。
- 选路径：官方/便携/无效/长路径都有明确反馈。
- 应用/还原：busy 时控件禁用，成功/失败文案具体，失败有日志路径。
- 切换主题：light/dark/high contrast 文字可读，无颜色/表面回退。
- 关闭/退出：Copilot 未保存、后台任务未完成有确认，不静默丢数据。
- 窗口：标题栏拖动、双击最大化、边缘缩放、最小尺寸不压扁内容。

## 6. 未自动化的边界

- 真实 GitHub Desktop 汉化 → 启动 → 还原（需要安装环境，L3 人工）。
- Win11 Snap/Alt+Space/多屏/高 DPI（L3）。
- 代码签名、SBOM、依赖漏洞（P2）。
- 视觉风格主观评审（ADR/人工）。
