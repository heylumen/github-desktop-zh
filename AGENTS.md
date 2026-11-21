# AGENTS.md — 构建、架构与协作约束

本文件面向在本仓库工作的编码代理与贡献者。视觉规范见 [DESIGN.md](DESIGN.md)。

## 项目是什么

Windows 专用的 GitHub Desktop 中文本地化工具：单文件 EXE（PySide6 + PyInstaller），按版本整文件替换 `main.js` / `renderer.js`，支持官方安装与便携版、事务式备份/回滚、版本强匹配、字典导入与 Copilot 全局提交提示词。

## 目录与职责

| 路径 | 职责 |
|---|---|
| `gui/app.py` | 唯一 GUI 入口；页面构建与协调层（主题实现位于 `theme.py`） |
| `gui/theme.py` | 明暗 QSS、高对比度检测 |
| `gui/widgets.py` | 自绘图标、胶囊开关、无边框标题栏与缩放边缘 |
| `gui/zhcore.py` | 核心业务：安装/版本、事务汉化、还原、更新器状态、字典校验/导入 |
| `gui/cli.py` | 命令行版，复用 `zhcore`；退出码 0/1/2 |
| `gui/copilot_config.py` | Copilot 全局指令的受管区块、原子写、备份与冲突检测 |
| `gui/diagnostics.py` | 本地滚动诊断日志 |
| `zhpaths.py` | 安装发现/归一化/版本识别（GUI、CLI、zhtool 共用） |
| `zhtool.py` | `.zh` 词典引擎；`apply/scan/merge/verify/watch`，并供 3.6.10 生成脚本复用 |
| `dictionaries/` | 22 个版本 + `manifest.json` 散列清单 |
| `scripts/` | 字典清单/语法、隐私/self/一致性/对比度/截图/发布门禁、3.6.10 生成、AST 校验、归档核验、EXE 自检、发布散列 |
| `tests/` | 单元、GUI offscreen、CLI、旧引擎、AST 负面夹具 |

## 常用命令

```bash
# 测试（需要项目 venv；GUI 用例在 offscreen 下运行）
gui/build_env/Scripts/python.exe -m unittest discover -s tests -v

# AST 校验器依赖 Acorn 8.15.0
npm install --prefix .work/js-parser --no-save acorn@8.15.0
GDF_REQUIRE_NODE=1 python -m unittest discover -s tests -v

# 字典清单与 JS 语法
python scripts/build_dictionary_manifest.py --check
python scripts/check_dictionaries.py

# 构建单文件 EXE（Python 3.10–3.13）
cd gui && build.bat

# 打包后无头自检（验证四页、版本选择器、About、Copilot、导入入口、窗口 chrome）
python scripts/smoke_exe.py gui/dist/github-desktop-zh-1.0.3.exe
```

CI（`.github/workflows/ci.yml`）执行：依赖安装 → 字典检查 → 隐私/self/一致性/对比度 → pyright/ruff → 覆盖率测试 → 截图回归 → 构建 → 归档核验/EXE 自检 → 生成 `SHA256SUMS.txt` / `build-info.json` / `licenses/`。**Node 相关测试在 CI 中禁止跳过。**

## 不可破坏的约束

1. **不做网络请求**：工具本身离线；仅用户点击固定链接时才交给浏览器。
2. **启动不得修改系统状态**：不得自动重命名 `Update.exe`、不得自动覆盖客户端文件；只有用户明确点击才执行。
3. **版本强匹配**：客户端版本与所选字典不一致时默认阻止；无法识别版本必须二次确认。
4. **两个目标文件必须事务处理**：备份 → 暂存 → 替换 → 校验 → 失败回滚；不得出现半中文状态。
5. **失败必须可见**：核心返回 `OperationResult`；GUI/CLI 不得丢弃 `ok=False`。
6. **更新器操作只作用于所选安装**：禁止回退到 `%LOCALAPPDATA%` 或其他安装。
7. **本地字典视为不可信输入**：导入需用户确认；内置字典必须按 manifest 散列校验。
8. **不要删除或改写历史字典**：新增版本用目录 + manifest 登记；旧版本变更必须说明原因。
9. **无边框窗口是自定义标题栏的前提**：不要在未评估原生窗口行为的情况下改回系统标题栏。
10. **界面使用中性实体表面**：保持实体背景与稳定颜色，不引入额外窗口特效。
11. **高对比度优先**：高对比度下必须清空自定义 QSS、交还系统调色板。
12. **EXE 内置字典只保留最新 2 版**：控制单文件体积；新增版本走导入/本地目录，不要为了离线便利重新膨胀主包。
13. **11–13px 可读文字对比度 ≥ 4.5:1**：`#9ca3af`（浅色）/`#6b7280`（深色）仅用于禁用态，不得用于版本号、状态栏或提示。
14. **文案不写热词和实现细节**：不用“一键/极速/丝滑/魔法”，状态写具体动作；见 DESIGN.md 第 11 节。

## 质量门禁

- 提交前：`python scripts/check_self_methods.py`、`python scripts/check_consistency.py`、`python scripts/check_contrast.py`、`python scripts/check_privacy.py`、`pyright`、`ruff check .`。
- 合并前：`python -m coverage run --source=gui -m unittest discover -s tests -v` + `coverage report --fail-under=68`、`python scripts/check_visual.py`，并构建/自检。
- 发布前：`python scripts/check_release.py --require-tag --exe <EXE>`；工作树必须干净。
- 详细命令与用户视角检查见 `docs/quality-gates.md`。

## 编码约定

- Python 3.10+ 语法，4 空格缩进；新增公共 API 写简短 docstring。
- 文件写操作使用 `zhcore._atomic_write` 或同目录临时文件 + `os.replace`；不要直接 `open(..., "w")` 覆盖客户端文件。
- 路径统一走 `pathlib` 或 `zhpaths` 归一化；不要自行拼接用户输入路径。
- 新增 GUI 逻辑时：
  - 主题只通过 `_apply_theme` / `_refresh_stylesheet` 切换，跟随系统，不新增手动主题开关。
  - 状态文案遵循 DESIGN.md：平实、无感叹号、无 emoji 标签。
- 测试要求：
  - 核心写文件路径必须有成功、失败、回滚用例；
  - GUI 测试不得用宽泛 `except ImportError` 隐藏真实导入错误；
  - 新增依赖同步更新 `gui/requirements-build.txt` 与 `gui/constraints-build.txt`。

## 新增字典版本流程

1. 获取与客户端**完全同版本**的 `main.js` + `renderer.js`。
2. 若来自官方包，按 `scripts/build_3_6_10.py` 的方式固定包/原始文件散列，并用 `scripts/verify_translation.mjs` 做 AST 校验。
3. 放入 `dictionaries/<version>/`，运行 `python scripts/build_dictionary_manifest.py` 更新清单。
4. 运行 `python scripts/check_dictionaries.py` 与全量测试。
5. 更新 README/CHANGELOG；不要手工改多处版本描述而不更新清单。

便携版暂无 ASAR 支持；不要用解包/改名等破坏性方式“强行支持”。

## 发布规则

- 版本号同时更新：`APP_VERSION`、根目录 spec 文件名与 `EXE(name=...)`、`gui/build.bat`、CI 路径。
- 发布前必须：全量测试通过、归档核验通过、`SHA256SUMS.txt` / `build-info.json` / `licenses/` 生成；GitHub Release 只上传 EXE、SHA256SUMS 与选定的官方客户端安装包，`build-info.json`/`licenses/` 作为本地/CI 验证产物。
- 只在用户明确要求发布时执行 tag/Release/上传；代码签名、SBOM 与法律合规需维护者确认。
- 不要在未发布时把版本号留在旧值造成“同名不同内容”。

## 已知限制

- `app.asar` 单包便携版不支持。
- 3.6.8 / 3.6.9 / 3.6.11 / 3.7.0 未内置，需导入。
- 真实 GitHub Desktop 的启动/登录/推拉验证不能由单元测试替代。
- 高对比度时使用系统调色板；界面保持中性实体表面。
