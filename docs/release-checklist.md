# 发布检查清单

在用户**明确要求发布**后才执行 tag / Release / 上传。任何一步失败都不要继续发布。

## 1. 版本与身份

- [ ] `gui/product_meta.py` 的 `APP_VERSION` 已更新
- [ ] 根目录 spec 文件名与 `EXE(name=...)` 已同步
- [ ] spec 文件名、`gui/build.bat`、CI workflow、README 示例路径中的版本号已同步
- [ ] `CHANGELOG.md` 已记录本次变更并写明发布日期
- [ ] `README.md` 的当前版本、支持范围、构建命令与截图已更新
- [ ] 工作树已提交（`build-info.json` 的 `dirty` 应为 `false`）

## 2. 验证

```bash
python scripts/build_dictionary_manifest.py --check
python scripts/check_dictionaries.py
python scripts/check_privacy.py
python scripts/check_self_methods.py
python scripts/check_consistency.py
python scripts/check_contrast.py
python -m pyright
python -m ruff check .
python -m coverage run --source=gui -m unittest discover -s tests -v
python -m coverage report --fail-under=68
python scripts/check_visual.py
```

- [ ] 所有测试通过，且没有 Node 相关 skip
- [ ] 覆盖率 ≥ 68%，截图回归通过，隐私/类型/死代码门禁通过
- [ ] 新增/变更的字典已在 manifest 中登记，散列一致
- [ ] 若改动生成器，AST 负面夹具全部通过

## 3. 构建与产物

```bat
cd gui
build.bat
```

或手动：

```bash
python -m PyInstaller --clean --noconfirm --distpath gui/dist --workpath gui/build github-desktop-zh-X.Y.Z.spec
python scripts/verify_archive.py gui/dist/github-desktop-zh-X.Y.Z.exe --version X.Y.Z
python scripts/smoke_exe.py gui/dist/github-desktop-zh-X.Y.Z.exe
python scripts/build_release.py --exe gui/dist/github-desktop-zh-X.Y.Z.exe
python scripts/check_consistency.py
python scripts/check_release.py --require-tag --exe gui/dist/github-desktop-zh-X.Y.Z.exe
```

> `check_release --require-tag` 必须在创建并检出 tag `vX.Y.Z` 后执行；tag 必须指向当前 HEAD。

- [ ] 归档校验通过：内置字典数量与 `product_meta` 一致、manifest、图标、入口、应用版本唯一
- [ ] EXE 无头自检通过：四页、版本选择器、About、Copilot、导入入口、窗口 chrome
- [ ] `gui/dist/SHA256SUMS.txt`、`build-info.json`、`licenses/` 已生成
- [ ] `build-info.json` 的 `dirty=false`、`bundled_dictionaries` 与预期一致
- [ ] 如发布官方客户端，确认安装包 SHA-256 与官方 checksums 一致，且未修改二进制

## 4. 发布资产

GitHub Release 资产：

- [ ] `github-desktop-zh-X.Y.Z.exe`（ASCII 文件名）
- [ ] `SHA256SUMS.txt`（工具 + 选定官方客户端）
- [ ] 如选择附带客户端：官方对应版本的 `GitHubDesktop-X.Y.Z-x64-Setup.exe`（未修改）
- [ ] `build-info.json`、`licenses/` 仅作为本地/CI 验证产物，**不默认上传**；如需合规包，单独打包并明确版本

Release 正文从小节开始，不要重复版本标题（页面已用 `name` 显示版本）。

## 5. 已知外部待办（不阻塞代码合入，但阻塞“正式商业发布”）

- [ ] 在真实 Windows 10/11 客户端完成启动、菜单、提交、Copilot 提示词的实际验证
- [ ] 决定是否使用 Authenticode 代码签名并提供证书与时间戳
- [ ] 生成/附带正式 SBOM（当前 `build-info.json` 仅记录关键构建信息，且不默认上传）
- [ ] 复核 Qt/PySide6 LGPL 分发义务与第三方许可完整性

## 6. 禁止事项

- 不在用户未明确要求时创建 tag、Release 或上传资产
- 不把构建日志、`build_env/`、`gui/dist/` 提交入库
- 不通过改名/解包强改 `app.asar` 客户端
- 不在启动时自动修改 GitHub Desktop 更新器
