# DESIGN.md — GitHub Desktop 中文汉化工具

> 供设计代理与编码代理共同读取的界面规范。实现以 `gui/theme.py` 的 `QSS_LIGHT` / `QSS_DARK`、`gui/widgets.py` 的自绘控件为准；本文档与代码不一致时，先修正文档再改代码。
>
> 配套：`AGENTS.md` 说明如何构建与验证，本文件说明**看起来应该怎样**。

---

## 1. Visual Theme & Atmosphere

**Product**：为 Windows 用户本地化 GitHub Desktop 的离线单文件工具，支持官方安装与便携版。

**Character**：calm、exact、a little warm。安静的工具感，而不是营销页。

**World**：Windows 桌面工具 + 开发者终端。界面应当像系统设置/资源管理器一样可预期，而不是另一个 SaaS 落地页。

**Moments**：
1. 主操作「应用汉化」使用唯一的墨绿实心按钮。
2. 功能全部可用时，日志以少量状态色点给出确定感。

**Signature**：中性实体表面 + 系统调色板 + 自绘单色线性图标。不引入额外窗口特效。

**整体**：白色/近黑中性表面，单一墨绿强调色，细边框分层，不使用阴影堆叠、渐变文字、发光、彩色 blob。密度偏紧凑，留白足够但不空旷。

**Density**：紧凑桌面工具。侧栏固定 232px，页面边距 24px，卡片内边距 20px。

---

## 2. Color Palette & Roles

### Light（实体表面基线）

| Token | Value | Role |
|---|---|---|
| `surface` | `#ffffff` | 页面、卡片、输入框底色 |
| `sidebar` | `#ffffff` | 侧栏 |
| `titlebar` | `#ffffff` | 自定义标题栏 |
| `surface-muted` | `#f8fafc` | 列表背景 |
| `surface-hover` | `#f6f8fa` | 行/按钮 hover |
| `surface-selected` | `#cbd5e1` | 输入选择、列表选中 |
| `nav-active` | `#eef1f4` | 当前导航项 |
| `border` | `#e5e7eb` | 卡片、侧栏分隔 |
| `border-strong` | `#d1d5db` | 输入框 |
| `text-primary` | `#111827` | 标题、正文 |
| `text-secondary` | `#6b7280` | 副标题、标签 |
| `text-tertiary` | `#4b5563` | 中性徽标、短元信息 |
| `text-disabled` | `#9ca3af` | 仅禁用态 |
| `accent` | `#0d6b5e` | 唯一强调色：主按钮、Logo、焦点 |
| `accent-hover` | `#0a544a` | 主按钮 hover |
| `accent-pressed` | `#08453c` | 主按钮 pressed |
| `success` | `#065f46` on `#d1fae5` | 成功徽标/日志 |
| `warning` | `#92400e` on `#fef3c7` | 警告徽标/日志 |
| `danger` | `#dc2626` | 危险按钮/错误日志 |
| `info` | `#1e40af` on `#dbeafe` | 信息徽标 |

### Dark（实体表面基线）

| Token | Value | Role |
|---|---|---|
| `surface` | `#0b1e1b` | 页面底 |
| `sidebar` | `#0a1714` | 侧栏 |
| `titlebar` | `#0b1e1b` | 自定义标题栏 |
| `card` | `#132622` | 卡片/次表面 |
| `surface-muted` | `#0f1f1c` | 列表 |
| `surface-hover` | `#1a2f2b` | hover |
| `nav-active` | `#134e4a` | 当前导航项 |
| `border` | `#1f3530` | 边框 |
| `text-primary` | `#e5e7eb` | 主文字 |
| `text-secondary` | `#9ca3af` | 次文字 |
| `text-tertiary` | `#9ca3af` | 中性徽标、短元信息 |
| `text-disabled` | `#6b7280` | 仅禁用态 |
| `accent` | `#14b8a6` | 暗色强调色 |
| `success` | `#6ee7b7` on `#064e3b` | 成功 |
| `warning` | `#fcd34d` on `#78350f` | 警告 |
| `danger` | `#f87171` | 危险 |

### Solid surfaces

所有表面均使用 solid 填充与实际 QSS 色值。Light 与 Dark 的 `surface` / `card` / `sidebar` / `titlebar` token 即实际 QSS 值。

**规则**：只有一个强调色；语义色只表示状态；边框由文字色派生色或 `border` token 表达；禁止多套紫色/淡色文字。

---

## 3. Typography Rules

字体族：`"Segoe UI", "Microsoft YaHei UI", "PingFang SC", system-ui, sans-serif`。数字在等宽场景（哈希、版本、路径）使用系统等宽字体或 `tabular` 效果。

| Role | Size | Weight | Color |
|---|---|---|---|
| Page title | 22px | 600 | `text-primary` |
| Card title | 14px | 600 | `text-primary` |
| Body / control | 13px | 400 | `text-primary` |
| Nav label | 13px | 400（active 600） | `text-primary` |
| Caption / badge | 11–12px | 400–600 | `text-secondary` |
| Logo badge | 16px | 700 | on `accent` |

规则：
- 中文不做全大写、不加宽字距；不新造英文 eyebrow。
- 只使用 400 与 600 两级字重；不用粗体代替层级。
- 小字号不加负字距；不使用斜体强调。
- 短标签末尾不加句号；界面文案不使用感叹号、卖点词或 emoji。

---

## 4. Component Stylings

### Buttons
- **Primary**：`accent` 实心，白/深色文字，高 36px，圆角 8px，横向内边距 16px。每个操作区最多一个。
- **Secondary**：白/卡片底、1px `border-strong`，高 36px。
- **Ghost**：无底色，仅用于低权重动作。
- **Danger**：白/卡片底、`danger` 1px 边框与文字，高 36px。
- 状态：hover 提亮/加深；pressed 再深一档；disabled 降低对比度但保持可读；focus 使用 1px `accent` 边框，保留可见焦点。

### Inputs / Selects
- 高 36px，圆角 8px，1px `border-strong`，内边距 8px 12px；focus 边框换 `accent`。
- 下拉列表、对话框、工具提示使用独立实体弹层，避免与主界面混叠。

### Cards
- 圆角 12px，1px `border`，内边距 20px/16px，卡片间间距 8px。
- 卡片标题行可放状态徽标，垂直居中或顶部对齐；一卡一个主题。

### Badges
- 胶囊形，`padding 2px 8px`，11px/600。仅用于状态，不用于装饰。
- 语义：success / warning / info / neutral。

### Version selector
- **≤3 个可用版本：并排分段按钮**（36px，圆角 8px，选中 accent 边框 + `nav-active` 背景），不打开下拉弹层。
- **>3 个版本：下拉框**；自绘 chevron（1.6px），弹层 item 28px 高、4px 内边距，选中使用 `nav-active`。
- 版本数量变化时自动切换两种形态；不要为两个版本保留下拉框。

### Component states

| Component | Default | Hover | Pressed | Focus | Disabled | Loading |
|---|---|---|---|---|---|---|
| Primary | accent 实心 | accent-hover | accent-pressed | 1px accent 边框 | 降低对比度 | 文案切为操作中，禁用交互 |
| Secondary | 白/卡片底 + 1px 边框 | 边框加深 | 背景降一档 | 1px accent 边框 | 灰字灰底 | 禁用交互 |
| Ghost | 无底色 | surface-hover | surface-selected | 1px accent 边框 | 灰字 | 不适用 |
| Input/Select | 白/卡片底 + 1px 边框 | 边框加深 | — | 1px accent 边框 | 灰字灰底 | 不适用 |
| Nav item | 无底色 | surface-hover | surface-selected | 1px accent 边框 | 灰字 | 不适用 |
| Switch | 关/开胶囊 | 滑块微亮 | — | accent 焦点环 | 降低对比度 | 不适用 |
| Status bar | 实体底 + 次级文字 | — | — | — | — | 显示具体操作中状态 |


### Lists
- 背景 `surface-muted`，圆角 10px，行内边距 4px 10px；选中 `surface-selected`。
- 日志条目用圆点 + 文本；状态用语义色，不堆 emoji。

### Navigation
- 侧栏宽 232px；导航行高约 34px（padding 8px 12px），行间距 4px；当前项 `nav-active` + 600 字重。
- 图标 18px、单色线性、1.5px 视觉描边，颜色取文字角色色。
- 不使用系统默认图标，不把 emoji 当图标。

### Switch
- 46×26px 胶囊 + 白色滑块，140ms `OutCubic`；可用空格/回车切换；自绘 `accent` 焦点环。
- 只用于二元设置，不用于多选。

### Title bar
- 高 40px，背景随主题；`v` 版本号低对比度。
- 右侧 46×32 窗口按钮；关闭按钮 hover 红底白叉，其余 hover 浅表面色。
- 整条标题栏可拖拽；双击最大化/还原；按钮保留键盘焦点。

### Resize handles
- 无边框窗口四周 6px、四角 12px 无可见填充的缩放手柄；按下调用系统缩放。
- 最大化/全屏时隐藏；不与内容争夺常态点击。

### Window surface
- 不提供窗口特效菜单，也不引入额外窗口特效；高对比度时交还系统调色板。

---

## 5. Layout Principles

- 4px 间距网格：4 / 8 / 12 / 16 / 20 / 24 / 32。例外仅限微调（2px）与恰好居中的奇数。
- 窗口为**无边框**，顶部 40px 自定义标题栏；默认 1000×660，最小 820×540；页面内容不足时出垂直滚动条，不压缩控件。
- 页面边距：24px 水平、16px 垂直；页面块间距 8px。
- 卡片内边距：20px 水平、16px 垂直；卡片内部块间距 8px。
- 标题栏高 40px：左侧图标/标题/版本，右侧最小化、最大化、关闭；拖拽空白区移动窗口，双击最大化。
- 侧栏固定 232px；内容区自适应并设置最小宽度。
- 分组内间距 < 分组间间距；标签、图标、数字各自对齐到列。
- 侧栏底部保留留白，不放主题菜单。

---

## 6. Depth & Elevation

- **不使用投影**表达层级；用 `surface` 台阶 + 1px 边框 + 颜色对比。
- Light：页面白 → 列表近白灰 → 选中浅灰。
- Dark：页面近黑 → 卡片深墨绿 → hover 再亮一阶。
- 不引入额外窗口特效；全部界面由实体 QSS 表面组成，保证点击/拖动/切窗颜色稳定。
- 默认即为实体表面基线；高对比度时交还系统调色板，不套自定义 QSS。
- 对话框、工具提示、菜单必须使用实体弹层背景；不允许全局 `QWidget` 背景穿透到弹层。
- 不叠加彩色阴影、发光边框、高光贴纸。

---

## 7. Do's and Don'ts

### Do
- 保持一个强调色，只给主操作和选中/焦点。
- 用系统主题适配 Windows，不添加额外窗口特效。
- 文案平实、具体、可验证；错误提示说明下一步怎么做。
- 重要失败必须显式呈现，不能让界面停在泛化的“等待操作”。
- 所有控件保持键盘可达、焦点可见，文字对比度足够。

### Don'ts（来自 unslop 审查）
- 紫色/多色渐变、渐变文字、发光、彩色阴影、blob、星云、漂浮几何体。
- 装饰性循环动画、呼吸光、标题 shimmer、卡片 hover 缩放。
- 界面标签里使用 emoji、`NEW ✨`、全大写宽字距英文标签。
- 同屏多个强调色；用 10 种相近浅色表达文字层级。
- 13px、11px 等一次性间距混用；同类元素 padding 不一致。
- 一切皆为胶囊；卡片内嵌圆角不满足“外圆角 − padding”。
- 不引入额外窗口特效；界面保持中性实体表面。
- 把状态色做成装饰色，或把日志 emoji 当图标。

**模板测试**：把产品名换成任何其他桌面工具后，这个界面是否仍然成立？如果成立，说明签名细节（实体表面 + 自绘线性图标 + 状态日志）还不够具体。

---

## 8. Responsive Behavior

- 平台：Windows 10 / 11 桌面，非移动端；不做手机断点。
- 最小窗口 820×540；侧栏固定，内容区滚动；不隐藏核心操作。
- 高 DPI：所有尺寸为 Qt 逻辑像素；图标使用矢量绘制/QIcon 多尺寸。
- 长路径、长错误：输入框横向滚动，日志/列表自动换行并禁用横向滚动。
- 系统主题切换：运行时通过 `QStyleHints.colorSchemeChanged` 立即跟随，无需重启。
- 高对比度：禁用自定义 QSS，交还系统调色板。

---

## 9. Agent Prompt Guide

### Quick tokens
```
accent light #0d6b5e | hover #0a544a | pressed #08453c
accent dark  #14b8a6
surface light #ffffff | border #e5e7eb | text #111827 / #6b7280 / #4b5563
surface dark  #0b1e1b | card #132622 | border #1f3530 | text #e5e7eb / #9ca3af / #9ca3af
radius: control 8 | card 12 | list 10 | badge pill
space: 4 8 12 16 20 24 32
type: 11 / 12 / 13 / 14 / 22, weights 400/600
sidebar 232 | titlebar 40 | window 1000x660 (min 820x540) | page margin 24/16
```

### Ready-to-use prompt
> 按 `DESIGN.md` 修改这个 PySide6 界面：无边框 + 40px 自定义标题栏；保持单一墨绿强调色、中性表面、1px 边框、无装饰渐变；所有间距落在 4px 网格；主题自动跟随 Windows 明暗；不引入额外窗口特效，使用中性实体表面；图标保持 18px 单色线性；任何状态变化都要有可见反馈。

### Review checklist
- [ ] 无 emoji 图标、无渐变/发光/彩色阴影/无意义动效
- [ ] 间距为 4px 网格，侧栏行高约 34px，分组层次清晰
- [ ] 仅一个强调色，文字三档对比度达标
- [ ] 焦点可见、键盘可操作、禁用态可读
- [ ] 实体表面与高对比度模式下文字对比度足够
- [ ] 状态徽标语义正确，日志状态色不误导
- [ ] 截图与 README 描述一致，不展示不存在的效果


## 10. Accessibility

### Measured contrast

| Foreground | Background | Ratio | Use |
|---|---|---:|---|
| `#111827` | `#ffffff` | 17.74 | 浅色正文 |
| `#6b7280` | `#ffffff` | 4.83 | 浅色副标题/状态 |
| `#4b5563` | `#f3f4f6` | 6.87 | 浅色中性徽标 |
| `#e5e7eb` | `#0b1e1b` | 13.5 | 深色正文 |
| `#9ca3af` | `#0b1e1b` | 6.80 | 深色副标题/状态 |
| `#9ca3af` | `#1f3530` | 5.14 | 深色中性徽标 |
| `#0d6b5e` | `#ffffff` | 6.40 | 浅色主按钮 |
| `#14b8a6` | `#0b1e1b` | 6.94 | 深色强调色 |

- 所有 11–13px 可读文字至少 4.5:1；`#9ca3af`（浅色）和 `#6b7280`（深色）只允许用于禁用态。
- 焦点必须始终可见：1px `accent` 边框；不以颜色单独传达状态。
- 高对比度：清空自定义 QSS，交还系统调色板。

## 11. Copy Voice

- 说产品实际做什么，不用“一键/极速/丝滑/魔法/革命性”等热词。
- 状态必须具体：`等待操作` / `正在校验版本` / `已写入 main.js 和 renderer.js`，不要只写“处理中”。
- 错误说明：发生了什么 + 下一步；保留日志路径。
- 标签、按钮、徽标末尾不加句号；不使用感叹号、emoji、`NEW ✨`。
- 不把实现细节写进用户文案：例如不要写“含 ✓ ✗ ⚠ 彩色圆点”。
- 示例：
  - ✅ `汉化 GitHub Desktop`
  - ✅ `操作结果与错误提示`
  - ✅ `版本不匹配，已阻止写入；请选择 3.6.10 或导入对应汉化包`
  - ❌ `一键汉化 GitHub Desktop`
  - ❌ `操作反馈与提示，含 ✓ ✗ ⚠ 彩色圆点`

## 12. Known Gaps

- 真实 GitHub Desktop 客户端的汉化 → 启动 → 还原链路尚未自动化，只做了文件级/GUI 级测试。
- Win11 Snap Layout、Alt+Space、高 DPI 多屏行为未完成原生命中测试。
- 高对比度未做全量截图对比；明暗首页/About 已有 4 张视觉基线。
- 未提供 3.6.8、3.6.9、3.6.11、3.7.0 的内置字典；本地导入字典不能证明来源。
- 未做 Authenticode 签名与完整 SBOM。
- 设计 token 仍部分散落在 QSS 字符串中，尚未形成单一来源。

## 13. Iteration Guide

1. 一次只改一个组件；先确认它所在的 surface，再改颜色/间距。
2. 修改颜色前先查第 10 节的对比度表；11–13px 文字不低于 4.5:1。
3. 修改文案先对照第 11 节；状态必须具体，不写实现细节。
4. 改完运行 `python -m unittest discover -s tests` 并重新截图对比明暗主题。
5. 不新增窗口特效/渐变/发光/emoji；不要为了“现代”打破实体表面基线。
6. 新增组件时先补第 4 节状态矩阵，再写 QSS。

---

*本设计规范参考 Google Stitch 的 DESIGN.md 结构，以及 VoltAgent/awesome-design-md 的章节组织；「Do's and Don'ts」与审查清单参考 heydamir/unslop 的 slop 审计方法。*
