#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — GitHub Desktop 汉化工具（Windows 版 GUI，PySide6 / Qt6）
=====================================================================
- 仅支持 Windows 10 / 11；仓库收录 3.5.0–3.6.7、3.6.10，EXE 默认打包最新 2 版。
- 旧版采用上游 MIT 整文件补丁；3.6.10 为官方同版本底包的中文字符串适配，纯离线、不联网。
- 设计系统：明暗主题自动跟随 Windows；不透明中性表面 + 单一墨绿强调色；
  高对比度交还系统调色板。详细规范见仓库根 DESIGN.md。

构建：见同目录 build.bat
"""
import json
import os
import sys
import webbrowser

from PySide6.QtCore import QEvent, QSettings, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QFileDialog, QFrame, QHBoxLayout,
    QSizePolicy,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QStackedWidget, QPlainTextEdit,
    QStatusBar, QVBoxLayout, QWidget,
)

import copilot_config
import diagnostics
import zhcore
from product_meta import BUNDLED_DICTIONARY_LIMIT
from theme import QSS_DARK, QSS_LIGHT, high_contrast_enabled
from widgets import ComboBox, ResizeHandle, Switch, TitleBar, nav_icon as _nav_icon

APP_TITLE = "GitHub Desktop 汉化工具"
# 打包归档校验读取该常量；必须与 product_meta.APP_VERSION 一致（check_consistency）。
APP_VERSION = "1.0.3"
PROJECT_URL = "https://github.com/heylumen/github-desktop-zh"
DICT_URL = "https://github.com/743859910/GitHub_Desktop_Simplified_Chinese"
SETTINGS_ORG = "github-desktop-zh"
SETTINGS_APP = "app"
LAST_INSTALL_KEY = "last_install"


# ============================================================ 全局异常钩子

def _global_excepthook(exc_type, exc_value, exc_tb):
    """全局异常钩子：记录诊断日志，避免偶发静默闪退。"""
    import traceback

    traceback.print_exception(exc_type, exc_value, exc_tb)
    diagnostics.get_logger().error(
        "未捕获异常", exc_info=(exc_type, exc_value, exc_tb))
    try:
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(
                None, "程序异常",
                f"发生未捕获异常：\n{exc_type.__name__}: {exc_value}\n\n"
                f"诊断日志：{diagnostics.log_path()}")
    except Exception:  # noqa: BLE001
        pass


sys.excepthook = _global_excepthook


# ============================================================ 后台 Worker

class Worker(QThread):
    """在后台线程跑耗时操作，通过信号把日志/状态回传主线程。

    ``done_signal`` 传递 ``zhcore.OperationResult``，而不是单一布尔值：
    GUI 必须能区分“成功 / 业务失败 / 抛出异常”，不能把失败显示为成功。
    """
    log_signal = Signal(str)
    status_signal = Signal(str)
    done_signal = Signal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        result = None
        try:
            result = self._fn(self.log_signal.emit, self.status_signal.emit)
        except Exception as error:  # noqa: BLE001
            diagnostics.get_logger().exception("后台操作异常")
            self.log_signal.emit(f"✗ [异常] {error}")
            result = zhcore.OperationResult(
                False, "exception", f"操作异常：{error}",
                details=[f"✗ [异常] {error}"])
        if result is None:
            result = zhcore.OperationResult(True, "ok", "")
        self.done_signal.emit(result)


# ============================================================ 主窗口

# 导航定义：name -> (display, 图标种类)
NAV_ITEMS = [
    ("汉化", "hanhua"),
    ("字典", "zidian"),
    ("Copilot 提示词", "copilot"),
    ("关于", "guanyu"),
]


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        # 窗口图标：onefile 运行时从 sys._MEIPASS 加载，开发态从脚本目录加载
        _icon_base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        self.setWindowIcon(QIcon(os.path.join(_icon_base, "assets", "icon.ico")))
        self.resize(1000, 660)
        self.setMinimumSize(820, 540)
        self.setAcceptDrops(True)
        # 无边框窗口 + 自定义标题栏
        self.setWindowFlag(Qt.FramelessWindowHint, True)
        self._busy = False
        self._worker = None
        self._last_result = None
        self._update_state_cache = {}

        central = QWidget()
        central.setObjectName("CentralRoot")
        self.setCentralWidget(central)
        self._build_layout(central)

        # 主题跟随系统；启动只读检测，不写用户偏好
        self._theme = self._detect_system_theme()
        self._refresh_stylesheet()

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("等待操作")

        self._pages = {}
        self._nav = {}
        self._build_sidebar()
        self._build_stack()

        hints = QGuiApplication.styleHints()
        if hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._on_system_theme_changed)
        self._apply_theme(self._detect_system_theme())

        if self._auto_detect():
            self._refresh_path()

    # ---------------------------------------------------------------- 主题
    def _detect_system_theme(self) -> str:
        """读取系统明暗偏好；Qt 6.5+ 优先，Windows 注册表兜底。"""
        try:
            scheme = QGuiApplication.styleHints().colorScheme()
            if hasattr(Qt, "ColorScheme"):
                if scheme == Qt.ColorScheme.Dark:
                    return "dark"
                if scheme == Qt.ColorScheme.Light:
                    return "light"
        except (AttributeError, RuntimeError):
            pass
        if sys.platform == "win32":
            try:
                import winreg

                path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                    value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "light" if int(value) else "dark"
            except (OSError, ValueError, ImportError):
                pass
        return "light"

    def _on_system_theme_changed(self, *_args) -> None:
        theme = self._detect_system_theme()
        if theme != self._theme:
            self._apply_theme(theme)
            self._set_status(f"已跟随系统切换为{'暗色' if theme == 'dark' else '亮色'}主题")

    def _refresh_stylesheet(self) -> None:
        app = QApplication.instance()
        if app is None:
            return
        # 高对比度时必须交还给系统调色板，不能继续套自定义主题。
        if high_contrast_enabled():
            app.setStyleSheet("")
            return
        app.setStyleSheet(QSS_DARK if self._theme == "dark" else QSS_LIGHT)

    def _apply_theme(self, name: str) -> None:
        """应用系统主题（不写用户偏好），同步图标与标题栏。"""
        self._theme = "dark" if name == "dark" else "light"
        self._refresh_stylesheet()
        if getattr(self, "sw_disable_update", None) is not None:
            self.sw_disable_update.set_dark(self._theme == "dark")
        if hasattr(self, "_nav") and self._nav:
            self._retint_nav_icons()
        if hasattr(self, "_titlebar"):
            self._titlebar.set_dark(self._theme == "dark")
        if hasattr(self, "_version_combo"):
            self._version_combo.set_dark(self._theme == "dark")

    def _retint_nav_icons(self) -> None:
        if not self._nav:
            return
        active_c = "#5eead4" if self._theme == "dark" else "#111827"
        inactive_c = "#9ca3af" if self._theme == "dark" else "#6b7280"
        for key, btn in self._nav.items():
            kind = btn.property("nav_kind")
            if kind is None:
                continue
            color = active_c if btn.objectName() == "NavActive" else inactive_c
            btn.setIcon(_nav_icon(kind, color))

    def _auto_detect(self) -> bool:
        return True  # 启动自动检测（保留扩展位）

    # ---------------------------------------------------------------- 布局
    def _build_layout(self, central):
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._titlebar = TitleBar(self, APP_TITLE, APP_VERSION)
        root.addWidget(self._titlebar)

        # 主体（无边框窗口；标题栏独立，主体不再有亮色条）
        body = QWidget()
        body.setContentsMargins(0, 0, 0, 0)
        self._body_h = QHBoxLayout(body)
        self._body_h.setContentsMargins(0, 0, 0, 0)
        self._body_h.setSpacing(0)
        root.addWidget(body, 1)

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(232)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(16, 20, 16, 16)
        sb.setSpacing(4)

        # 导航
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)
        for i, (name, kind) in enumerate(NAV_ITEMS):
            b = QPushButton("  " + name)
            b.setObjectName("NavActive" if i == 0 else "NavItem")
            b.setCheckable(True)
            b.setChecked(i == 0)
            b.setIconSize(QSize(18, 18))
            b.setProperty("nav_kind", kind)
            b.setFocusPolicy(Qt.StrongFocus)
            b.setAccessibleName(name)
            b.clicked.connect(lambda _checked=False, n=name: self._switch_page(n))
            self._nav_group.addButton(b)
            self._nav[name] = b
            sb.addWidget(b)
        self._retint_nav_icons()

        sb.addStretch(1)


        self._body_h.addWidget(sidebar)

    def _build_stack(self):
        self._stack = QStackedWidget()
        self._body_h.addWidget(self._stack, 1)
        # 各页统一套滚动区：窗口变小时可滚动，避免控件被挤压变形
        self._pages["汉化"] = self._wrap_scroll(self._build_home())
        self._pages["字典"] = self._wrap_scroll(self._build_dict())
        self._pages["Copilot 提示词"] = self._wrap_scroll(self._build_copilot())
        self._pages["关于"] = self._wrap_scroll(self._build_about())
        for w in self._pages.values():
            self._stack.addWidget(w)
        self._stack.setCurrentWidget(self._pages["汉化"])
        self._create_resize_handles()

    # ---------------------------------------------------------------- 无边框窗口
    def _create_resize_handles(self):
        self._resize_handles = []
        for edges in (
            Qt.LeftEdge | Qt.TopEdge,
            Qt.RightEdge | Qt.TopEdge,
            Qt.LeftEdge | Qt.BottomEdge,
            Qt.RightEdge | Qt.BottomEdge,
            Qt.LeftEdge, Qt.RightEdge, Qt.TopEdge, Qt.BottomEdge,
        ):
            handle = ResizeHandle(self, edges)
            handle.show()
            self._resize_handles.append(handle)
        self._layout_resize_handles()

    def _layout_resize_handles(self):
        handles = getattr(self, "_resize_handles", None)
        if not handles:
            return
        maximized = self.isMaximized() or self.isFullScreen()
        width, height = self.width(), self.height()
        border, corner = 6, 12
        for handle in handles:
            if maximized:
                handle.hide()
                continue
            edges = handle._edges
            left = bool(edges & Qt.LeftEdge)
            right = bool(edges & Qt.RightEdge)
            top = bool(edges & Qt.TopEdge)
            bottom = bool(edges & Qt.BottomEdge)
            if left and top:
                rect = (0, 0, corner, corner)
            elif right and top:
                rect = (width - corner, 0, corner, corner)
            elif left and bottom:
                rect = (0, height - corner, corner, corner)
            elif right and bottom:
                rect = (width - corner, height - corner, corner, corner)
            elif left:
                rect = (0, border, border, height - 2 * border)
            elif right:
                rect = (width - border, border, border, height - 2 * border)
            elif top:
                rect = (border, 0, width - 2 * border, border)
            else:
                rect = (border, height - border, width - 2 * border, border)
            handle.setGeometry(*rect)
            handle.show()
            handle.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._layout_resize_handles()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.WindowStateChange, QEvent.ThemeChange):
            if event.type() == QEvent.WindowStateChange and hasattr(self, "_titlebar"):
                self._titlebar.sync_state()
            QTimer.singleShot(0, self._layout_resize_handles)

    def _wrap_scroll(self, page: QWidget) -> QScrollArea:
        """把页面包进滚动区。

        widgetResizable=True 时：空间充足则页面填满视口（日志卡仍能撑满），
        空间不足则页面保持自身高度、只在右侧出现垂直滚动条，
        而不是把卡片内部控件压缩变形。
        """
        sa = QScrollArea()
        sa.setObjectName("PageScroll")
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sa.setWidget(page)
        return sa

    def _switch_page(self, name):
        for n, b in self._nav.items():
            b.setObjectName("NavActive" if n == name else "NavItem")
            b.style().unpolish(b)
            b.style().polish(b)
        self._retint_nav_icons()
        self._stack.setCurrentWidget(self._pages[name])
        if name == "字典":
            self._refresh_dict_page()
        elif name == "Copilot 提示词" and not self._copilot_has_changes():
            self._load_copilot_prompt()

    # ---------------------------------------------------------------- 主页
    def _build_home(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(8)

        # 子页头（无英文 eyebrow；标题 + 可选副标题）
        self._home_count_badge = self._make_badge(
            "BadgeNeutral", f"可用 {len(zhcore.list_versions())} 个版本")
        outer.addLayout(self._make_page_header(
            title="汉化 GitHub Desktop",
            sub="支持官方安装与便携/绿色版；按客户端版本匹配后整文件替换。",
            right_widget=self._home_count_badge,
        ))

        # Card 1 — 安装路径（状态徽标放在标题行右侧，与其他卡片/页头对齐一致）
        self._path_pill = QLabel("待检测")
        self._path_pill.setObjectName("BadgeNeutral")
        c1 = self._make_card(
            "GitHub Desktop 安装",
            "可选择客户端根目录或 resources/app；也支持把客户端 EXE/文件夹拖到此窗口",
            right_widget=self._path_pill)
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.path_var = QLineEdit()
        self.path_var.setPlaceholderText(
            r"例如 D:\Portable\GitHubDesktop 或其中的 resources\app 目录")
        self.path_var.setMinimumHeight(36)
        self.path_var.setAccessibleName("GitHub Desktop 安装路径")
        self.path_var.editingFinished.connect(self._on_path_edited)
        row1.addWidget(self.path_var, 1)
        self.btn_browse = self._make_btn("浏览", "Secondary", self._browse)
        self.btn_detect = self._make_btn("自动检测", "Secondary", self._refresh_path)
        row1.addWidget(self.btn_browse)
        row1.addWidget(self.btn_detect)
        c1.body.addLayout(row1)
        outer.addWidget(c1.frame)

        # Card 2 — 汉化版本
        c2 = self._make_card("汉化版本", "按客户端 package.json / app-X.Y.Z 自动匹配")
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("选择版本："))
        self._version_combo = ComboBox()
        self._version_combo.setMinimumWidth(140)
        self._version_combo.setMinimumHeight(36)
        self._version_combo.setAccessibleName("选择汉化版本")
        self._version_combo.setToolTip("选择要应用到 GitHub Desktop 的汉化版本")
        self._version_combo.currentTextChanged.connect(lambda _t: self._update_version_hint())
        row2.addWidget(self._version_combo)
        self._version_chips = QWidget()
        self._version_chips.setObjectName("VersionChips")
        self._version_chip_layout = QHBoxLayout(self._version_chips)
        self._version_chip_layout.setContentsMargins(0, 0, 0, 0)
        self._version_chip_layout.setSpacing(8)
        self._version_chip_group = QButtonGroup(self)
        self._version_chip_group.setExclusive(True)
        self._version_chips.hide()
        row2.addWidget(self._version_chips)
        self._version_hint = QLabel()
        self._version_hint.setObjectName("CardSub")
        self._version_hint.setWordWrap(True)
        row2.addWidget(self._version_hint, 1)
        c2.body.addLayout(row2)
        outer.addWidget(c2.frame)

        # Card 3 — 操作
        c3 = self._make_card("应用汉化", "版本不一致会阻止写入；两个文件一起成功才视为完成")
        op_row = QHBoxLayout()
        op_row.setSpacing(8)
        op_row.addStretch(1)
        self.btn_restore = self._make_btn("还原为英文原版", "Danger", self._on_restore)
        self.btn_apply = self._make_btn("应用汉化", "Primary", self._on_apply)
        self.btn_apply.setMinimumWidth(140)
        op_row.addWidget(self.btn_restore)
        op_row.addWidget(self.btn_apply)
        c3.body.addLayout(op_row)
        outer.addWidget(c3.frame)

        # Card 3.5 — 禁止自动更新（自绘开关；状态徽标同样置于标题行右侧）
        self._update_pill = QLabel("待检测")
        self._update_pill.setObjectName("BadgeNeutral")
        cu = self._make_card(
            "禁止自动更新",
            "仅在点击开关时改名 Update.exe；启动时不会自动修改。注意这会同时阻断安全更新。",
            right_widget=self._update_pill)
        row_u = QHBoxLayout()
        row_u.setSpacing(10)
        # 上下各留 5px：使本行高度 36px，与其它卡片的输入框/按钮行保持一致
        row_u.setContentsMargins(0, 4, 0, 4)
        self.sw_disable_update = Switch()
        self.sw_disable_update.toggled.connect(self._on_toggle_disable_update)
        lbl_u = QLabel("禁止 GitHub Desktop 自动更新")
        row_u.addWidget(self.sw_disable_update)
        row_u.addWidget(lbl_u, 0, Qt.AlignVCenter)
        row_u.addStretch(1)
        cu.body.addLayout(row_u)
        outer.addWidget(cu.frame)

        # Card 4 — 运行日志
        c4 = self._make_card("运行日志", "操作结果与错误提示")
        self.log = self._make_list(140)
        c4.body.addWidget(self.log)
        outer.addWidget(c4.frame, 1)

        self._refresh_versions()
        return page

    # ---------------------------------------------------------------- 字典页
    def _build_dict(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(8)

        n = len(zhcore.list_versions())
        self._dict_count_badge = self._make_badge("BadgeInfo", f"{n} 个版本")
        outer.addLayout(self._make_page_header(
            title="汉化版本",
            sub="内置版本逐文件散列校验；下载的新版本可直接导入，无需手工建目录。",
            right_widget=self._dict_count_badge,
        ))

        c1 = self._make_card("版本列表", "（本地）表示来自 EXE 同级的 dictionaries/，同名时优先于内置")
        self.dict_list = self._make_list(152)
        c1.body.addWidget(self.dict_list)
        outer.addWidget(c1.frame)

        c2 = self._make_card("操作", "导入汉化包 / 打开本地字典目录 / 检查资源完整性")
        op = QHBoxLayout()
        op.setSpacing(8)
        self.btn_import_dict = self._make_btn("导入汉化包…", "Primary", self._on_import_dict)
        self.btn_open_dict = self._make_btn("打开本地字典目录", "Secondary", self._open_local_dict_dir)
        self.btn_check_dict = self._make_btn("检查资源完整性", "Secondary", self._on_check_dict)
        op.addWidget(self.btn_import_dict)
        op.addWidget(self.btn_open_dict)
        op.addWidget(self.btn_check_dict)
        op.addStretch(1)
        c2.body.addLayout(op)
        c2.body.addSpacing(6)
        sub = QLabel("检查结果")
        sub.setObjectName("CardSub")
        c2.body.addWidget(sub)
        self.dict_check_list = self._make_list(112)
        c2.body.addWidget(self.dict_check_list)
        outer.addWidget(c2.frame, 1)

        tip = self._make_tip(
            "导入方式：点击「导入汉化包…」，直接选择下载好的版本文件夹（含 main.js + renderer.js，"
            "或其上级/Windows 目录），工具会自动识别版本并放到本地字典目录，无需手工建文件夹、无需重启。\n"
            "若文件夹名无法识别版本，会提示你输入客户端版本。\n"
            "安全提示：导入的 JavaScript 会被 GitHub Desktop 执行，请只使用可信来源；"
            "本地字典无法通过内置散列校验，列表中会标记「（本地）」。")
        outer.addWidget(tip)

        return page

    def _refresh_dict_page(self):
        self.dict_list.clear()
        pairs = zhcore.list_version_sources()
        if hasattr(self, "_dict_count_badge"):
            builtin = sum(1 for _, source in pairs if source == "内置")
            self._dict_count_badge.setText(f"{len(pairs)} 个版本")
            self._dict_count_badge.setToolTip(f"内置 {builtin} 个，本地 {len(pairs) - builtin} 个")
        if not pairs:
            self.dict_list.addItem(QListWidgetItem("（未找到任何汉化版本）"))
            return
        for version, source in pairs:
            tag = "（本地）" if source == "本地" else ""
            item = QListWidgetItem(f"GitHub Desktop {version}  {tag}")
            font = item.font()
            font.setWeight(QFont.DemiBold)
            item.setFont(font)
            item.setToolTip(str((zhcore.dictionary_source(version) or {}).get("path", "")))
            self.dict_list.addItem(item)

    def _on_check_dict(self):
        self.dict_check_list.clear()
        zhcore.validate_dictionaries(
            log=lambda m: self._append_log(m, target=self.dict_check_list))

    def _on_import_dict(self):
        source = QFileDialog.getExistingDirectory(
            self, "选择下载好的汉化版本文件夹（也可选择其上级目录）")
        if not source:
            return
        detected = zhcore.detect_version(self.path_var.text().strip()) or ""
        version, error = zhcore.infer_dictionary_version(source, None)
        suggested = version or detected
        if not version and error:
            self._append_log(f"⚠ 未能自动识别版本：{error}")
        text, accepted = QInputDialog.getText(
            self, "确认汉化版本",
            "请输入该汉化包对应的 GitHub Desktop 版本号（X.Y.Z）：",
            text=suggested)
        if not accepted:
            return
        version = text.strip()
        if not version:
            QMessageBox.warning(self, "版本必填", "请填写与客户端完全一致的版本号。")
            return
        confirm = QMessageBox.question(
            self, "确认导入汉化包",
            f"将导入版本 {version} 到本地字典目录。\n\n"
            "导入的 main.js / renderer.js 会在应用汉化时写入 GitHub Desktop 并被其执行。\n"
            "请确认文件来自可信来源。\n\n是否继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        self.dict_check_list.clear()
        result = zhcore.import_local_dictionary(
            source, version,
            log=lambda m: self._append_log(m, target=self.dict_check_list))
        if not result.ok:
            QMessageBox.warning(self, "导入失败", result.message or "请查看检查结果。")
            return
        imported = result.data.get("version") or version
        self._refresh_versions(select=imported)
        self._refresh_dict_page()
        self._switch_page("汉化")
        self._set_status(f"已导入汉化版本 {imported}，可直接应用")
        QMessageBox.information(
            self, "导入完成",
            f"版本 {imported} 已导入，并已在首页选中。\n"
            "无需重启程序；请确认客户端已关闭后再点击「应用汉化」。")

    # ---------------------------------------------------------------- Copilot 全局提示词
    def _build_copilot(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(8)
        outer.addLayout(self._make_page_header(
            title="Copilot 全局提交提示词",
            sub="统一设置生成提交说明时的语言、格式与内容要求。",
            right_widget=self._make_badge("BadgeInfo", "用户级配置"),
        ))

        path_card = self._make_card("全局指令文件", "保存后供所有项目的 Copilot 会话读取")
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self.copilot_path = QLineEdit()
        self.copilot_path.setReadOnly(True)
        self.copilot_path.setAccessibleName("Copilot 全局指令文件路径")
        path_row.addWidget(self.copilot_path, 1)
        self.btn_copilot_open = self._make_btn("打开目录", "Secondary", self._open_copilot_dir)
        path_row.addWidget(self.btn_copilot_open)
        path_card.body.addLayout(path_row)
        outer.addWidget(path_card.frame)

        prompt_card = self._make_card("提交说明要求", "仅编辑本工具管理的部分，保留文件中的其他全局指令")
        self.copilot_editor = QPlainTextEdit()
        self.copilot_editor.setAccessibleName("Copilot 全局提交说明提示词")
        self.copilot_editor.setPlaceholderText("输入生成提交说明时的要求，或点击“填入中文模板”。保存后生效。")
        self.copilot_editor.setMinimumHeight(220)
        self.copilot_editor.textChanged.connect(self._on_copilot_text_changed)
        prompt_card.body.addWidget(self.copilot_editor)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.btn_copilot_preset = self._make_btn("填入中文模板", "Secondary", self._on_copilot_preset)
        self.btn_copilot_clear = self._make_btn("清空", "Ghost", self._on_copilot_clear)
        self.btn_copilot_reload = self._make_btn("重新读取", "Secondary", self._on_copilot_reload)
        self.btn_copilot_save = self._make_btn("保存全局提示词", "Primary", self._save_copilot_prompt)
        row.addWidget(self.btn_copilot_preset)
        row.addWidget(self.btn_copilot_clear)
        row.addStretch(1)
        row.addWidget(self.btn_copilot_reload)
        row.addWidget(self.btn_copilot_save)
        prompt_card.body.addLayout(row)
        self.copilot_status = QLabel()
        self.copilot_status.setObjectName("CardSub")
        self.copilot_status.setWordWrap(True)
        self.copilot_status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        prompt_card.body.addWidget(self.copilot_status)
        outer.addWidget(prompt_card.frame, 1)

        other_card = self._make_card("其他全局指令", "以下内容会被保留，也可能影响生成结果")
        self._copilot_other_card = other_card.frame
        self.copilot_other = QPlainTextEdit()
        self.copilot_other.setReadOnly(True)
        self.copilot_other.setAccessibleName("保留的其他全局指令")
        self.copilot_other.setMinimumHeight(80)
        self.copilot_other.setMaximumHeight(120)
        other_card.body.addWidget(self.copilot_other)
        outer.addWidget(other_card.frame)
        outer.addWidget(self._make_tip(
            "保存后重新生成一次提交说明；若仍沿用旧要求，可重启 GitHub Desktop。\n"
            "清空后保存会移除本工具的要求。此设置适用于支持自定义指令的 Copilot 生成方式。"))
        self._copilot_revision = None
        self._copilot_loaded_text = ""
        self._load_copilot_prompt()
        return page

    def _load_copilot_prompt(self):
        try:
            self.copilot_path.setText(copilot_config.global_instructions_path())
            state = copilot_config.load_global_commit_instructions()
        except (OSError, UnicodeError, ValueError) as exc:
            self._copilot_revision = None
            self.copilot_editor.setReadOnly(True)
            self.btn_copilot_save.setEnabled(False)
            self.btn_copilot_preset.setEnabled(False)
            self.btn_copilot_clear.setEnabled(False)
            self.copilot_status.setText(f"读取失败：{exc}。处理后点击“重新读取”。")
            return False
        self._copilot_revision = state["revision"]
        self._copilot_loaded_text = state["prompt"]
        self.copilot_path.setText(state["path"])
        self.copilot_path.setToolTip(state["path"])
        self.copilot_path.setCursorPosition(0)
        self.copilot_editor.setReadOnly(False)
        self.btn_copilot_preset.setEnabled(True)
        self.btn_copilot_clear.setEnabled(True)
        self.copilot_editor.setPlainText(state["prompt"])
        self.copilot_editor.document().setModified(False)
        self.copilot_other.setPlainText(state["other_instructions"])
        self._copilot_other_card.setVisible(bool(state["other_instructions"].strip()))
        self.btn_copilot_save.setEnabled(False)
        self.copilot_status.setText("已读取已保存的提示词。" if state["prompt"] else
                                    "尚未设置提交说明要求。填入模板或输入内容后保存。")
        return True

    def _on_copilot_text_changed(self):
        if not hasattr(self, "btn_copilot_save"):
            return
        changed = self._copilot_has_changes()
        self.btn_copilot_save.setEnabled(changed and self._copilot_revision is not None)
        if changed:
            self.copilot_status.setText("有未保存的更改。" if self.copilot_editor.toPlainText().strip()
                                        else "保存后将移除本工具的提示词，其他全局指令会保留。")
        else:
            self.copilot_status.setText("与已读取的内容一致。")

    def _copilot_has_changes(self):
        # setPlainText()/clear() reset QTextDocument.isModified after textChanged.
        # Compare the draft itself so preset/clear/undo behave like typed edits.
        return self.copilot_editor.toPlainText() != self._copilot_loaded_text

    def _on_copilot_preset(self):
        self.copilot_editor.setPlainText(copilot_config.DEFAULT_COMMIT_INSTRUCTIONS)

    def _on_copilot_clear(self):
        self.copilot_editor.clear()

    def _on_copilot_reload(self):
        if self._copilot_has_changes():
            result = QMessageBox.question(
                self, "重新读取提示词", "编辑区有未保存的更改。重新读取将丢弃这些更改，是否继续？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if result != QMessageBox.Yes:
                return
        self._load_copilot_prompt()

    def _open_copilot_dir(self):
        target = os.path.dirname(self.copilot_path.text().strip())
        if not target:
            return
        try:
            os.makedirs(target, exist_ok=True)
            os.startfile(target)
        except OSError as error:
            self.copilot_status.setText(f"无法打开目录：{error}")

    def _save_copilot_prompt(self):
        if self._copilot_revision is None:
            return False
        try:
            result = copilot_config.save_global_commit_instructions(
                self.copilot_editor.toPlainText(), expected_revision=self._copilot_revision)
        except (OSError, UnicodeError, ValueError) as exc:
            self.copilot_status.setText(f"保存失败：{exc}")
            self._set_status("Copilot 全局提示词保存失败")
            return False
        if not self._load_copilot_prompt():
            return False
        message = "已保存全局提示词。重新生成提交说明即可使用。"
        if not self.copilot_editor.toPlainText().strip():
            message = "已移除本工具的提示词，其他全局指令已保留。"
        if result["backup_path"]:
            message += f"\n原文件备份：{result['backup_path']}"
        self.copilot_status.setText(message)
        self._set_status("Copilot 全局提示词已保存")
        return True

    # ---------------------------------------------------------------- 关于页
    def _build_about(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(24, 16, 24, 16)
        outer.setSpacing(8)

        outer.addLayout(self._make_page_header(
            title="GitHub Desktop 汉化工具",
        ))

        versions = zhcore.list_versions()
        builtin = [v for v in versions
                   if (zhcore.dictionary_source(v) or {}).get("source") == "内置"]
        preview = "、".join(versions[:4])
        if len(versions) > 4:
            preview += f" 等 {len(versions)} 个"
        scope = "当前 EXE" if getattr(sys, "frozen", False) else "当前源码"
        c1 = self._make_card(
            f"{APP_TITLE}  v{APP_VERSION}",
            right_widget=self._make_badge("BadgeNeutral", f"内置 {len(builtin)} 版"))
        body = QLabel(
            "本工具用于把 GitHub Desktop 的 Windows 界面文本替换为中文，"
            "支持官方安装版、便携版/绿色版和自定义汉化包导入。\n\n"
            "主要能力：\n"
            "· 自动识别客户端路径，读取 package.json 或 app-X.Y.Z 推断版本；\n"
            "· 版本不匹配时阻止写入；两个目标文件按备份、临时文件、替换、校验、失败回滚处理；\n"
            "· 支持还原英文原版、导入本地字典、检查内置字典完整性；\n"
            "· 可选禁用 GitHub Desktop 自动更新，操作仅作用于所选安装，且会同时阻断安全更新；\n"
            "· 可编辑当前用户的 Copilot 全局提交说明提示词。\n\n"
            "来源说明：3.5.0–3.6.7 采用 743859910 提供的 MIT 整文件汉化补丁；"
            "3.6.10 在官方同版本底包上移植中文字符串，保留当前版本逻辑。\n\n"
            f"版本范围：{scope}可用 {len(versions)} 个汉化版本（{preview}）；"
            f"EXE 内置最新 {BUNDLED_DICTIONARY_LIMIT} 版。\n"
            "支持 3.5.0–3.6.7、3.6.10；3.6.8、3.6.9、3.6.11、3.7.0 未内置，"
            "可在「字典」页导入；版本不一致会阻止写入，导入的本地字典会标记为未验证来源。\n\n"
            "工具默认不发起网络请求，日志仅写入本机；仅支持 Windows 10/11。\n"
            "本工具基于 MIT 许可开源，与 GitHub, Inc. / Microsoft 无任何关联。")
        body.setObjectName("CardSub")
        body.setWordWrap(True)
        c1.body.addWidget(body)
        outer.addWidget(c1.frame)

        c2 = self._make_card("致谢与许可")
        thanks = QLabel(
            "汉化内容 © 2008–2026 我只是你的过客工作室，MIT License。\n"
            "本工具 © 2026 Heylumen，MIT License。")
        thanks.setObjectName("CardSub")
        thanks.setWordWrap(True)
        c2.body.addWidget(thanks)
        op = QHBoxLayout()
        op.setSpacing(8)
        op.addWidget(self._make_btn("字典主页", "Secondary",
                                    lambda: webbrowser.open(DICT_URL)))
        op.addWidget(self._make_btn("项目主页", "Secondary",
                                    lambda: webbrowser.open(PROJECT_URL)))
        op.addStretch(1)
        c2.body.addLayout(op)
        outer.addWidget(c2.frame)
        outer.addStretch(1)
        return page

    # ---------------------------------------------------------------- 辅助构造
    class _Card:
        """轻量卡片：frame + body layout。"""
        def __init__(self, frame: QFrame, body: QVBoxLayout):
            self.frame = frame
            self.body = body

    def _make_card(self, title: str, sub: str = "",
                   right_widget: QWidget = None) -> "_Card":
        """卡片骨架：左侧标题/副标题，右侧可挂状态徽标（与页头徽标同一视觉语言）。"""
        f = QFrame()
        f.setObjectName("Card")
        # 垂直方向只允许放大、不允许压缩：窗口变小时应出现滚动条，
        # 而不是把卡片内部控件挤变形（QSizePolicy.Minimum = 仅 GrowFlag）
        f.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        v = QVBoxLayout(f)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("CardTitle")
        left.addWidget(t)
        if sub:
            s = QLabel(sub)
            s.setObjectName("CardSub")
            s.setWordWrap(True)
            left.addWidget(s)
        head.addLayout(left, 1)
        if right_widget is not None:
            # 顶部右对齐：使各卡片的状态徽标与卡片标题始终在同一水平线上
            head.addWidget(right_widget, 0, Qt.AlignTop | Qt.AlignRight)
        v.addLayout(head)
        return self._Card(f, v)

    def _make_page_header(self, title: str, sub: str = "",
                          right_widget: QWidget = None) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(2)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        left.addWidget(t)
        if sub:
            s = QLabel(sub)
            s.setObjectName("PageSub")
            s.setWordWrap(True)
            left.addWidget(s)
        row.addLayout(left, 1)
        if right_widget is not None:
            row.addWidget(right_widget, 0, Qt.AlignVCenter | Qt.AlignRight)
        return row

    def _make_badge(self, obj_name: str, text: str) -> QLabel:
        b = QLabel(text)
        b.setObjectName(obj_name)
        return b

    def _make_tip(self, text: str) -> QFrame:
        box = QFrame()
        box.setObjectName("TipBox")
        box.setFrameShape(QFrame.NoFrame)
        v = QVBoxLayout(box)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(0)
        t = QLabel(text)
        t.setObjectName("TipText")
        t.setWordWrap(True)
        t.setTextInteractionFlags(Qt.TextSelectableByMouse)
        v.addWidget(t)
        return box

    def _make_btn(self, text: str, variant: str, slot) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName(variant)
        b.setCursor(Qt.PointingHandCursor)
        b.setMinimumHeight(36)
        b.clicked.connect(slot)
        return b

    def _make_list(self, min_height: int) -> QListWidget:
        """统一的列表控件。

        长路径 / 长报错文本若不换行，会把列表撑出横向滚动条（并在右下角
        留下滚动条残影）。这里统一开启自动换行并禁用横向滚动。
        """
        lw = QListWidget()
        lw.setMinimumHeight(min_height)
        lw.setWordWrap(True)
        lw.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        lw.setTextElideMode(Qt.ElideNone)
        return lw

    # ---------------------------------------------------------------- 日志
    def _append_log(self, msg: str, target: QListWidget | None = None, level: str | None = None) -> None:
        if target is None:
            target = self.log
        assert target is not None
        if self._theme == "dark":
            ok_c, err_c, warn_c = "#6ee7b7", "#fca5a5", "#fcd34d"
        else:
            ok_c, err_c, warn_c = "#065f46", "#b91c1c", "#92400e"
        color = "#e5e7eb" if self._theme == "dark" else "#111827"
        text = str(msg)
        if level is None:
            if any(k in text for k in ("✗", "错误", "失败", "异常", "不一致", "未通过", "冲突")):
                level = "error"
            elif any(k in text for k in ("⚠", "未验证", "跳过", "未找到", "缺少", "无法")):
                level = "warning"
            elif any(k in text for k in ("✓", "===", "完成", "通过", "一致")):
                level = "success"
        if level == "error":
            color = err_c
        elif level == "warning":
            color = warn_c
        elif level == "success":
            color = ok_c
        item = QListWidgetItem("● " + text)
        item.setForeground(QColor(color))
        target.addItem(item)
        target.scrollToBottom()
        diagnostics.get_logger().info(text)

    def _set_status(self, s: str) -> None:
        self.statusBar().showMessage(s)
        diagnostics.get_logger().info("状态：" + str(s))

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        controls = [
            getattr(self, "btn_apply", None),
            getattr(self, "btn_restore", None),
            getattr(self, "btn_browse", None),
            getattr(self, "btn_detect", None),
            getattr(self, "btn_import_dict", None),
            getattr(self, "btn_check_dict", None),
            getattr(self, "btn_open_dict", None),
            getattr(self, "path_var", None),
            getattr(self, "_version_combo", None),
            getattr(self, "_version_chips", None),
            getattr(self, "sw_disable_update", None),
        ]
        for control in controls:
            if control is not None:
                control.setEnabled(not busy)
        if busy:
            self._set_status("处理中…")
        else:
            self._update_version_hint()
            self._refresh_update_pill()
            if not self.statusBar().currentMessage().startswith("操作失败"):
                self._set_status("等待操作")

    # ---------------------------------------------------------------- 路径
    def _last_install(self) -> str:
        value = QSettings(SETTINGS_ORG, SETTINGS_APP).value(LAST_INSTALL_KEY, "")
        return str(value or "").strip()

    def _remember_install(self, path: str) -> None:
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue(LAST_INSTALL_KEY, path or "")

    def _set_path_pill(self, text: str, badge: str) -> None:
        self._path_pill.setText(text)
        self._path_pill.setObjectName(badge)
        self._path_pill.style().unpolish(self._path_pill)
        self._path_pill.style().polish(self._path_pill)

    def _apply_selected_path(self, path: str, auto: bool = False):
        """归一化用户选择的 EXE / 根目录 / resources/app，并刷新相关状态。"""
        info = zhcore.install_info(path)
        self.path_var.setText(info.appdir or info.requested)
        self.path_var.setCursorPosition(0)
        if info.available:
            if info.appdir:
                self._remember_install(info.appdir)
            label = "已自动定位" if auto else "已选择"
            if info.portable:
                label += " · 便携版"
            self._set_path_pill(label, "BadgeInfo" if info.portable else "BadgeSuccess")
            version = info.version or "未知"
            self._set_status(f"已选择客户端 {version}（{info.layout}）")
            if not auto:
                self._append_log(f"· 已选择安装：{info.appdir}")
                self._append_log(
                    f"  · 客户端版本 {version}（来源：{info.version_source or '无法识别'}）")
            for warning in info.warnings:
                self._append_log("⚠ " + warning)
        else:
            if info.layout == "asar":
                self._set_path_pill("app.asar 不支持", "BadgeWarn")
            elif info.layout == "incomplete":
                self._set_path_pill("资源不完整", "BadgeWarn")
            else:
                self._set_path_pill("路径无效", "BadgeWarn")
            if not auto:
                for error in info.errors:
                    self._append_log("✗ " + error)
                if info.layout == "asar":
                    self._append_log("  · 该便携版把程序打包为 app.asar，当前版本无法直接改写；"
                                     "请改用官方安装包或解包版。")
            self._set_status("所选路径不是可改写的 GitHub Desktop 安装")
        self._sync_version_to_path()
        self._refresh_update_pill()
        return info

    def _refresh_path(self):
        self._set_status("正在自动检测安装目录…")
        found = zhcore.locate(self._last_install() or None)
        if found:
            self._apply_selected_path(found, auto=True)
            self._set_status("已自动定位安装目录")
        else:
            self.path_var.clear()
            self._set_path_pill("未自动检测到", "BadgeWarn")
            self._set_status("未自动检测到，请浏览或拖入客户端目录")
            self._version_hint.setText("请选择客户端目录或拖入 GitHubDesktop.exe")
            self._sync_version_to_path()
            self._refresh_update_pill()

    def _browse(self):
        directory = QFileDialog.getExistingDirectory(
            self, "选择 GitHub Desktop 客户端目录（含 resources/app）")
        if directory:
            self._apply_selected_path(directory, auto=False)

    def _on_path_edited(self):
        text = self.path_var.text().strip()
        if not text:
            self._set_path_pill("待检测", "BadgeNeutral")
            self._version_hint.setText("请选择客户端目录")
            self._refresh_update_pill()
            return
        self._apply_selected_path(text, auto=False)

    def dragEnterEvent(self, event):
        if any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event):
        urls = [url for url in event.mimeData().urls() if url.isLocalFile()]
        if not urls:
            super().dropEvent(event)
            return
        self._apply_selected_path(urls[0].toLocalFile(), auto=False)
        event.acceptProposedAction()

    def _open_local_dict_dir(self):
        d = zhcore.local_dict_dir()
        try:
            os.makedirs(d, exist_ok=True)
            os.startfile(d)
        except OSError as e:
            # 目录创建失败或系统无默认文件管理器时不应中断程序
            self._append_log(f"⚠ 无法打开本地字典目录：{e}")
            self._append_log(f"本地字典目录：{d}")

    # ---------------------------------------------------------------- 自动更新状态
    def _sync_update_ui(self, state) -> None:
        """开关与徽标严格反映本机实际状态；状态异常时禁用操作。"""
        enabled = state in ("enabled", "disabled")
        self.sw_disable_update.setEnabled(enabled and not self._busy)
        self.sw_disable_update.set_checked_instant(state == "disabled")
        if state == "disabled":
            text, badge = "已禁止更新", "BadgeSuccess"
            tip = "自动更新已禁用；点击开关可恢复"
        elif state == "enabled":
            text, badge = "允许更新", "BadgeWarn"
            tip = "自动更新未被阻断；点击开关可禁止（同时影响安全更新）"
        elif state == "inconsistent":
            text, badge = "状态异常", "BadgeWarn"
            tip = "Update.exe 与 Update.exe.disabled 同时存在，请手动清理其一"
        elif state == "missing":
            text, badge = "无更新器", "BadgeNeutral"
            tip = "该安装未检测到 Update.exe（便携版通常没有更新器）"
        else:
            text, badge = "未检测到 GD", "BadgeNeutral"
            tip = "未检测到 GitHub Desktop 安装"
        self._update_pill.setText(text)
        self._update_pill.setObjectName(badge)
        self._update_pill.setToolTip(tip + (f"\n更新器目录：{self._update_state_cache.get('deploy_root') or '未找到'}"))
        self._update_pill.style().unpolish(self._update_pill)
        self._update_pill.style().polish(self._update_pill)

    def _refresh_update_pill(self) -> None:
        """只读取状态，绝不在启动或刷新时自动修改 Update.exe。"""
        appdir = self.path_var.text().strip() or None
        self._update_state_cache = zhcore.update_state(appdir)
        self._sync_update_ui(self._update_state_cache.get("state"))

    def _on_toggle_disable_update(self, checked: bool) -> None:
        """用户明确点击开关时才落地修改；失败则回滚界面。"""
        want = bool(checked)
        appdir = self.path_var.text().strip() or zhcore.locate() or None
        if not appdir:
            self._refresh_update_pill()
            self._set_status("请先选择有效的 GitHub Desktop 安装目录")
            return
        verb = "禁止" if want else "允许"
        self._append_log(f"== {verb}自动更新 ==")
        result = zhcore.set_auto_update_disabled(want, appdir)
        self._refresh_update_pill()
        actual = zhcore.auto_update_disabled(appdir)
        if result.ok and actual == want:
            self._set_status(f"已{verb}自动更新（即时生效）")
            self._append_log(f"· 当前状态：{'已禁止更新' if want else '允许更新'}")
        else:
            self._set_status(f"未能{verb}自动更新")
            if result.message:
                self._append_log("✗ " + result.message)
            QMessageBox.warning(
                self, f"未能{verb}自动更新",
                (result.message or "操作未生效。")
                + "\n\n建议关闭 GitHub Desktop 后重试，并检查目录权限。")

    # ---------------------------------------------------------------- 版本
    def _refresh_versions(self, select: str | None = None):
        versions = zhcore.list_versions()
        if hasattr(self, "_home_count_badge"):
            self._home_count_badge.setText(f"可用 {len(versions)} 个版本")
        self._version_combo.blockSignals(True)
        self._version_combo.clear()
        self._version_combo.addItems(versions)
        info = zhcore.install_info(self.path_var.text().strip())
        detected = info.version if info.available else None
        if select and select in versions:
            index = versions.index(select)
        elif detected and detected in versions:
            index = versions.index(detected)
        elif not self.path_var.text().strip() and versions:
            index = 0
        elif detected:
            index = -1
        else:
            index = 0 if versions else -1
        self._version_combo.setCurrentIndex(index)
        self._version_combo.blockSignals(False)
        self._rebuild_version_chips(versions)
        self._update_version_hint(versions)

    def _sync_version_to_path(self, vers=None):
        if vers is None:
            vers = [self._version_combo.itemText(i)
                    for i in range(self._version_combo.count())]
        info = zhcore.install_info(self.path_var.text().strip())
        detected = info.version if info.available else None
        if detected and detected in vers:
            self._version_combo.blockSignals(True)
            self._version_combo.setCurrentIndex(vers.index(detected))
            self._version_combo.blockSignals(False)
        elif info.available:
            self._version_combo.blockSignals(True)
            self._version_combo.setCurrentIndex(-1)
            self._version_combo.blockSignals(False)
        self._refresh_version_chip_state()
        self._update_version_hint(vers)

    def _rebuild_version_chips(self, versions):
        """≤3 个版本用并排分段按钮，避免为两项打开下拉弹层。"""
        if not hasattr(self, "_version_chips"):
            return
        for button in list(self._version_chip_group.buttons()):
            self._version_chip_group.removeButton(button)
            button.deleteLater()
        compact = 0 < len(versions) <= 3
        for version in versions if compact else []:
            button = QPushButton(version)
            button.setObjectName("VersionChip")
            button.setCheckable(True)
            button.setMinimumHeight(36)
            button.setAccessibleName(f"选择汉化版本 {version}")
            button.clicked.connect(
                lambda _checked=False, value=version: self._select_version(value))
            self._version_chip_group.addButton(button)
            self._version_chip_layout.addWidget(button)
        self._version_chips.setVisible(compact)
        self._version_combo.setVisible(not compact)
        self._refresh_version_chip_state()

    def _select_version(self, version: str) -> None:
        if self._busy:
            return
        index = self._version_combo.findText(version)
        if index >= 0:
            self._version_combo.setCurrentIndex(index)

    def _refresh_version_chip_state(self) -> None:
        if not hasattr(self, "_version_chip_group"):
            return
        current = self._version_combo.currentText()
        for button in self._version_chip_group.buttons():
            button.setChecked(button.text() == current)

    def _update_version_hint(self, vers=None):
        self._refresh_version_chip_state()
        versions = vers if vers is not None else [
            self._version_combo.itemText(i) for i in range(self._version_combo.count())]
        path = self.path_var.text().strip()
        info = zhcore.install_info(path) if path else None
        selected = self._version_combo.currentText()
        can_apply = False
        if not path:
            text = "请先选择客户端目录；下载的新版本可在「字典」页导入"
        elif info and not info.available:
            text = "当前路径不可用：" + ("；".join(info.errors) or "未找到 resources/app")
        elif not versions:
            text = "未找到任何汉化版本，请在「字典」页导入"
        elif not info or not info.version:
            text = "无法识别客户端版本；应用前会要求二次确认"
            can_apply = bool(selected)
        elif info.version not in versions:
            text = f"检测到客户端 {info.version}，但尚未导入该版本汉化包 → 请到「字典」页导入"
        elif selected != info.version:
            text = f"客户端 {info.version} 与所选 {selected} 不一致，已阻止应用"
        else:
            source = zhcore.dictionary_source(selected) or {}
            suffix = " · 本地字典（未验证来源）" if source.get("source") == "本地" else ""
            text = f"已匹配客户端 {info.version} · 来源：{source.get('source', '未知')}{suffix}"
            can_apply = True
        self._version_hint.setText(text)
        button = getattr(self, "btn_apply", None)
        if button is not None:
            button.setEnabled(can_apply and not self._busy)

    # ---------------------------------------------------------------- Worker
    def _run(self, fn):
        if self._busy:
            return
        self._set_busy(True)
        self._worker = Worker(fn)
        self._worker.log_signal.connect(self._append_log)
        self._worker.status_signal.connect(self._set_status)
        self._worker.done_signal.connect(self._on_worker_done)
        self._worker.start()

    def _current_install(self):
        text = self.path_var.text().strip()
        if not text:
            QMessageBox.critical(self, "未选择客户端", "请先选择 GitHub Desktop 客户端目录。")
            return None
        info = zhcore.install_info(text)
        if not info.available:
            detail = "；".join(info.errors) or "未找到 main.js / renderer.js"
            QMessageBox.critical(
                self, "安装目录不可用",
                f"{detail}\n\n请选择客户端根目录或 resources/app。")
            self._apply_selected_path(text, auto=False)
            return None
        if info.appdir != self.path_var.text().strip():
            self.path_var.setText(info.appdir)
            self.path_var.setCursorPosition(0)
        return info

    def _on_apply(self):
        if self._busy:
            return
        info = self._current_install()
        if not info:
            return
        version = self._version_combo.currentText()
        if not version:
            QMessageBox.warning(
                self, "未选择版本",
                "请先在版本下拉框选择一个汉化版本；若客户端版本尚未收录，"
                "请到「字典」页点击「导入汉化包…」。")
            return
        allow_mismatch = False
        if info.version is None:
            confirm = QMessageBox.question(
                self, "无法确认客户端版本",
                "未能从 package.json 或 app-X.Y.Z 目录确认客户端版本。\n\n"
                "版本不匹配可能导致 GitHub Desktop 无法启动。\n是否仍要应用汉化？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if confirm != QMessageBox.Yes:
                return
            allow_mismatch = True
        elif info.version != version:
            QMessageBox.critical(
                self, "版本不匹配",
                f"客户端版本为 {info.version}，但选择的是 {version}。\n\n"
                "为避免客户端无法启动，已阻止写入。请选择匹配版本，或先导入对应汉化包。")
            return

        source = zhcore.dictionary_source(version) or {}
        if source.get("source") == "本地":
            confirm = QMessageBox.question(
                self, "使用本地字典",
                f"版本 {version} 来自本地字典：\n{source.get('path')}\n\n"
                "该目录未通过内置散列校验，其中的 JavaScript 会被 GitHub Desktop 执行。\n"
                "请确认文件来源可信。\n\n是否继续应用？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if confirm != QMessageBox.Yes:
                return

        appdir = info.appdir

        def _task(log, status):
            log(f"== 应用汉化（客户端 {info.version or '未知'} · 汉化 {version}）==")
            status("正在校验版本并写入文件…")
            return zhcore.apply_version(
                appdir, version, allow_mismatch=allow_mismatch)

        self._run(_task)

    def _on_restore(self):
        if self._busy:
            return
        info = self._current_install()
        if not info:
            return
        confirm = QMessageBox.question(
            self, "还原为英文原版",
            "将从 .bak 备份还原 main.js / renderer.js。\n"
            "请确认 GitHub Desktop 已关闭。是否继续？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        appdir = info.appdir

        def _task(log, status):
            log("== 还原为英文原版 ==")
            status("正在还原…")
            return zhcore.restore(appdir)

        self._run(_task)

    def _on_worker_done(self, result) -> None:
        ok = bool(getattr(result, "ok", result))
        code = getattr(result, "code", "")
        self._last_result = result
        self._set_busy(False)
        if ok:
            if code == "applied":
                self._set_status("汉化完成，请完全退出并重新打开 GitHub Desktop")
                self._append_log("· 下一步：完全退出 GitHub Desktop 后重新打开，界面即为中文",
                                 level="success")
            elif code == "restored":
                self._set_status("已还原为英文原版，请重新打开 GitHub Desktop")
            else:
                self._set_status(getattr(result, "message", "") or "操作完成")
            return
        message = getattr(result, "message", "") or ""
        details = getattr(result, "details", []) or []
        if not message:
            message = next((line for line in reversed(details)
                            if line.lstrip().startswith("✗")), "操作未成功，请查看运行日志。")
        self._set_status("操作失败")
        QMessageBox.critical(self, "操作失败", message + f"\n\n诊断日志：{diagnostics.log_path()}")

    def closeEvent(self, event):
        if self._copilot_has_changes():
            box = QMessageBox(self)
            box.setWindowTitle("提示词尚未保存")
            box.setText("Copilot 全局提示词有未保存的更改。")
            save = box.addButton("保存并退出", QMessageBox.AcceptRole)
            discard = box.addButton("放弃更改", QMessageBox.DestructiveRole)
            box.addButton("取消", QMessageBox.RejectRole)
            box.setDefaultButton(save)
            box.exec()
            if box.clickedButton() is save:
                if not self._save_copilot_prompt():
                    event.ignore()
                    return
            elif box.clickedButton() is not discard:
                event.ignore()
                return
        if self._worker is not None and self._worker.isRunning():
            # 后台线程可能正在写 main.js/renderer.js：强杀可能留下不完整文件，
            # 因此先征询用户，用户选择继续等待则取消关闭。
            r = QMessageBox.question(
                self, "操作进行中",
                "汉化 / 还原操作尚未完成。\n\n"
                "强行退出可能使 GitHub Desktop 的程序文件停留在不完整状态，\n"
                "建议等待操作结束后再关闭。\n\n确定要强行退出吗？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r != QMessageBox.Yes:
                event.ignore()
                return
            # 给后台线程最多 3 秒完成，超时则强制终止，避免窗口卡死
            try:
                self._worker.log_signal.disconnect()
                self._worker.status_signal.disconnect()
                self._worker.done_signal.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self._worker.wait(3000)
            if self._worker.isRunning():
                self._worker.terminate()
                self._worker.wait(2000)
            self._worker = None
        event.accept()


def _run_self_test(qapp) -> int:
    """打包后无头自检：验证页面、字典发现与模块导入，不触碰真实客户端。"""
    import tempfile

    temp = tempfile.mkdtemp(prefix="gdf-selftest-")
    os.environ.setdefault("COPILOT_HOME", os.path.join(temp, "copilot"))
    App._remember_install = lambda self, path: None
    App._last_install = lambda self: ""
    win = App()
    qapp.processEvents()
    pages = set(win._pages)
    versions = zhcore.list_versions()
    for page_name in win._pages:
        win._switch_page(page_name)
    win._switch_page("汉化")
    about_page = win._pages["关于"].widget()
    about_text = "\n".join(label.text() for label in about_page.findChildren(QLabel))
    compact = 0 < len(versions) <= 3
    checks = {
        "pages": pages == {"汉化", "字典", "Copilot 提示词", "关于"},
        "versions": len(versions) >= BUNDLED_DICTIONARY_LIMIT and versions[0].count(".") == 2,
        "version_selector": (not win._version_chips.isHidden()
                             and win._version_combo.isHidden()) if compact else (
                                 win._version_chips.isHidden()
                                 and not win._version_combo.isHidden()),
        "about": (f"EXE 内置最新 {BUNDLED_DICTIONARY_LIMIT} 版" in about_text
                  and "来源说明" in about_text and "主要能力" in about_text),
        "copilot": hasattr(win, "copilot_editor"),
        "import_button": hasattr(win, "btn_import_dict"),
        "window_chrome": hasattr(win, "_titlebar") and len(win._resize_handles) == 8,
    }
    print("SELF_TEST " + json.dumps(checks, ensure_ascii=False))
    for name, passed in checks.items():
        print(("  PASS " if passed else "  FAIL ") + name)
    ok = all(checks.values())
    report = "SELF_TEST_OK" if ok else "SELF_TEST_FAILED"
    target = os.environ.get("GDF_SELF_TEST_OUT")
    if target:
        try:
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"ok": ok, "checks": checks}, ensure_ascii=False, indent=2))
                handle.write("\n" + report + "\n")
        except OSError:
            pass
    win.copilot_editor.setPlainText(win._copilot_loaded_text)
    win._worker = None
    win.close()
    qapp.processEvents()
    try:
        import shutil

        shutil.rmtree(temp, ignore_errors=True)
    except OSError:
        pass
    print(report)
    return 0 if ok else 1


if __name__ == "__main__":
    diagnostics.setup_logging()
    qapp = QApplication(sys.argv)
    qapp.setFont(QFont("Segoe UI", 9))
    if "--self-test" in sys.argv:
        sys.exit(_run_self_test(qapp))
    win = App()
    win.show()
    sys.exit(qapp.exec())
