# 第三方组件与许可说明

本项目自身以 MIT 许可发布，见 [LICENSE](LICENSE)。分发二进制或源码时，还需同时保留以下第三方声明。本文档用于汇总可见性，不构成法律意见；正式发布前建议由维护者按各依赖许可证再做一次合规确认。

## 汉化内容

- **743859910 / GitHub_Desktop_Simplified_Chinese**：MIT License，版权归 © 2008–2026 743859910（我只是你的过客工作室）。3.5.0–3.6.7 的整文件汉化来自该仓库；3.6.10 的译文规则以其 3.6.7 词典为基础再适配。
- **GitHub Desktop（desktop/desktop）**：MIT License。汉化文件是对官方 `main.js` / `renderer.js` 的修改版本；官方许可文本保留在 [licenses/github-desktop-LICENSE](licenses/github-desktop-LICENSE) 与 `dictionaries/3.6.10/LICENSE.github-desktop`。
- 各 JavaScript 包附带的第三方许可见对应目录的 `*.LICENSE.txt`。

## 运行时与构建依赖

| 组件 | 版本基线 | 许可证 | 说明 |
|---|---|---|---|
| Qt / PySide6 | 6.11.2 | LGPL-3.0 / GPL / 商业许可（以 Qt 官方为准） | EXE 动态打包 Qt 库；分发时需保留许可文本并满足 LGPL 对替换/重链接的要求，正式发布前请复核 |
| Python | 3.13.x | PSF License | PyInstaller 打包运行时 |
| PyInstaller | 6.22.2 | GPL-2.0-or-later，附 bootloader 例外 | 仅构建期使用 |
| pyinstaller-hooks-contrib | 2026.7 | Apache-2.0 / GPL 组合（见包元数据） | 构建期 |
| pefile / altgraph / pywin32-ctypes / packaging | 见 `gui/constraints-build.txt` | 各自许可证 | 构建期 |
| Acorn | 8.15.0 | MIT | 仅用于 3.6.10 适配与校验，不进入 EXE |

## 发布注意事项

- 建议在 Releases 中同时提供：`LICENSE`、本文件、`licenses/github-desktop-LICENSE`，以及构建产物的 `SHA256SUMS.txt` 与 `build-info.json`。
- EXE 内的 `_MEIPASS` 不便于最终用户直接查看许可文本，因此**不要只把许可藏在单文件内部**。
- 若未来启用代码签名，应同时记录证书主体与时间戳服务，便于验证构建来源。
