#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — GitHub Desktop 汉化工具（Windows 版 GUI，PySide6 / Qt6）
=====================================================================
- 仅支持 Windows 10 / 11；内置多个 GitHub Desktop 汉化版本（3.5.0 – 3.6.5）。
- 全部汉化资源已打包进 EXE（源自 743859910 的 MIT 整文件补丁），纯离线、不联网。
- 设计系统：整体白色主题（默认亮色，可切暗色）+ 白色卡片 + 充足留白；侧栏底部分段切换。

构建：见同目录 build.bat
"""
import os
import sys
import webbrowser

from PySide6.QtCore import (
    QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSettings, QSize, Qt,
    QThread, Property, Signal,
)
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPixmap, QPen
from PySide6.QtWidgets import (
    QAbstractButton, QApplication, QButtonGroup, QComboBox, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QPushButton, QScrollArea, QSizePolicy, QStackedWidget,
    QStatusBar, QVBoxLayout, QWidget,
)

import zhcore

APP_TITLE = "GitHub Desktop 汉化工具"
APP_VERSION = "1.0.1"
PROJECT_URL = "https://github.com/heylumen/github-desktop-zh"
DICT_URL = "https://github.com/743859910/GitHub_Desktop_Simplified_Chinese"
SETTINGS_ORG = "github-desktop-zh"
SETTINGS_APP = "app"


# ============================================================ 配色与 QSS
# Light / Dark 双主题。所有颜色严格对齐下方 token 常量（QSS_LIGHT / QSS_DARK）。

QSS_LIGHT = """
QMainWindow, QWidget { background-color: #ffffff; color: #111827;
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", system-ui, sans-serif;
    font-size: 13px; }

/* 侧栏 */
QWidget#Sidebar { background: #ffffff; border-right: 1px solid #e5e7eb; }
QLabel#LogoBadge { background: #0d6b5e; color: #ffffff; border-radius: 8px;
    font-size: 16px; font-weight: 700; min-width: 32px; max-width: 32px;
    min-height: 32px; max-height: 32px; }
QLabel#NavTitle { color: #111827; font-size: 13px; font-weight: 700; }
QLabel#NavSub { color: #6b7280; font-size: 11px; }
QPushButton#NavItem { background: transparent; color: #111827; border: none;
    text-align: left; padding: 10px 14px; font-size: 13px; border-radius: 8px; }
QPushButton#NavItem:hover { background: #f6f8fa; }
QPushButton#NavActive { background: #eef1f4; color: #111827; border: none;
    text-align: left; padding: 10px 14px; font-size: 13px; font-weight: 600;
    border-radius: 8px; }
QPushButton#NavActive:hover { background: #eef1f4; }
QWidget#ThemeToggle { background: #f3f4f6; border-radius: 8px; }
QPushButton#ThemeOpt { background: transparent; color: #6b7280; border: none;
    padding: 6px 12px; font-size: 12px; border-radius: 6px; }
QPushButton#ThemeOpt:checked { background: #ffffff; color: #111827;
    border: 1px solid #e5e7eb; }

/* 子页头 */
QLabel#Eyebrow { color: #6b7280; font-size: 11px; font-weight: 600;
    letter-spacing: 1px; }
QLabel#PageTitle { color: #111827; font-size: 22px; font-weight: 700; }
QLabel#PageSub { color: #6b7280; font-size: 12px; }
QLabel#CardTitle { color: #111827; font-size: 14px; font-weight: 600; }
QLabel#CardSub { color: #6b7280; font-size: 12px; }

/* 卡片 */
QFrame#Card { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px; }

/* 提示框 */
QFrame#TipBox { background: transparent; border: none; }
QLabel#TipText { color: #6b7280; font-size: 12px; }

/* 徽标 */
QLabel#BadgeSuccess { background: #d1fae5; color: #065f46; border-radius: 999px;
    padding: 3px 10px; font-size: 11px; font-weight: 600; }
QLabel#BadgeWarn { background: #fef3c7; color: #92400e; border-radius: 999px;
    padding: 3px 10px; font-size: 11px; font-weight: 600; }
QLabel#BadgeNeutral { background: #f3f4f6; color: #6b7280; border-radius: 999px;
    padding: 3px 10px; font-size: 11px; font-weight: 600; }
QLabel#BadgeInfo { background: #dbeafe; color: #1e40af; border-radius: 999px;
    padding: 3px 10px; font-size: 11px; font-weight: 600; }

/* 按钮 */
QPushButton#Primary { background: #0d6b5e; color: #ffffff; border: none;
    border-radius: 8px; padding: 0 18px; font-size: 13px; font-weight: 600; }
QPushButton#Primary:hover { background: #0a544a; }
QPushButton#Primary:pressed { background: #08453c; }
QPushButton#Primary:disabled { background: #a3c4bf; color: #ffffff; }
QPushButton#Secondary { background: #ffffff; color: #111827; border: 1px solid #d1d5db;
    border-radius: 8px; padding: 9px 18px; font-size: 13px; }
QPushButton#Secondary:hover { border-color: #9ca3af; }
QPushButton#Secondary:disabled { color: #9ca3af; background: #f3f4f6; }
QPushButton#Ghost { background: transparent; color: #6b7280; border: none;
    padding: 8px 14px; font-size: 13px; border-radius: 8px; }
QPushButton#Ghost:hover { background: #f3f4f6; color: #111827; }
QPushButton#Danger { background: #ffffff; color: #dc2626; border: 1px solid #dc2626;
    border-radius: 8px; padding: 9px 18px; font-size: 13px; }
QPushButton#Danger:hover { background: #fef2f2; }
QPushButton#Danger:disabled { color: #fca5a5; border-color: #fca5a5; background: #ffffff; }

/* 输入 */
QLineEdit { background: #ffffff; border: 1px solid #d1d5db; border-radius: 8px;
    padding: 8px 12px; font-size: 13px; color: #111827;
    selection-background-color: #cbd5e1; selection-color: #111827; }
QLineEdit:focus { border: 1px solid #0d6b5e; }
QLineEdit:disabled { background: #f3f4f6; color: #9ca3af; }
QComboBox { background: #ffffff; border: 1px solid #d1d5db; border-radius: 8px;
    padding: 7px 12px; font-size: 13px; color: #111827; }
QComboBox:focus { border: 1px solid #0d6b5e; }
QComboBox::drop-down { background: #ffffff; border: none; width: 24px; subcontrol-origin: padding; subcontrol-position: top right; }
QComboBox::drop-down:hover { background: #f6f8fa; }
QComboBox::down-arrow { image: none; width: 0; height: 0;
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid #6b7280; margin-right: 8px; }
QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #e5e7eb;
    border-radius: 8px; padding: 4px;
    selection-background-color: #cbd5e1; selection-color: #111827; outline: none; }

/* 列表（不画独立边框，避免与卡片边框叠成双层方框） */
QListWidget { background: #f6f8fa; border: none; border-radius: 10px;
    padding: 8px 10px; font-size: 13px; outline: none; color: #111827; }
QListWidget::item { padding: 4px 10px; border-radius: 6px; color: #111827; }
QListWidget::item:hover { background: #f6f8fa; }
QListWidget::item:selected { background: #cbd5e1; color: #111827; }
QListWidget::item:selected:hover { background: #b8c4d0; }

/* 状态栏 */
QStatusBar { background: transparent; color: #6b7280; font-size: 12px; }

/* 滚动条（垂直 + 水平均完整定义，避免出现原生箭头/小方块残留） */
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; border: none; }
QScrollBar::handle:vertical { background: #d1d5db; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #9ca3af; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; width: 0;
    background: none; border: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; border: none; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0; border: none; }
QScrollBar::handle:horizontal { background: #d1d5db; border-radius: 4px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #9ca3af; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { height: 0; width: 0;
    background: none; border: none; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; border: none; }
QAbstractScrollArea::corner { background: transparent; border: none; }

/* 注：开关为自绘控件 Switch（见 app.py），不再使用 QCheckBox::indicator —
   原生 indicator 画不出滑块，且 QCheckBox 聚焦时会出现虚线焦点框。 */
"""

QSS_DARK = """
QMainWindow, QWidget { background-color: #0b1e1b; color: #e5e7eb;
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", system-ui, sans-serif;
    font-size: 13px; }

QWidget#Sidebar { background: #0a1714; border-right: 1px solid #1f3530; }
QLabel#LogoBadge { background: #14b8a6; color: #0a1714; border-radius: 8px;
    font-size: 16px; font-weight: 700; min-width: 32px; max-width: 32px;
    min-height: 32px; max-height: 32px; }
QLabel#NavTitle { color: #e5e7eb; font-size: 13px; font-weight: 700; }
QLabel#NavSub { color: #6b7280; font-size: 11px; }
QPushButton#NavItem { background: transparent; color: #e5e7eb; border: none;
    text-align: left; padding: 10px 14px; font-size: 13px; border-radius: 8px; }
QPushButton#NavItem:hover { background: #1a2f2b; }
QPushButton#NavActive { background: #134e4a; color: #5eead4; border: none;
    text-align: left; padding: 10px 14px; font-size: 13px; font-weight: 600;
    border-radius: 8px; }
QPushButton#NavActive:hover { background: #134e4a; }
QWidget#ThemeToggle { background: #0b1e1b; border-radius: 8px; }
QPushButton#ThemeOpt { background: transparent; color: #6b7280; border: none;
    padding: 6px 12px; font-size: 12px; border-radius: 6px; }
QPushButton#ThemeOpt:checked { background: #1a2f2b; color: #e5e7eb;
    border: 1px solid #1f3530; }

QLabel#Eyebrow { color: #6b7280; font-size: 11px; font-weight: 600;
    letter-spacing: 1px; }
QLabel#PageTitle { color: #e5e7eb; font-size: 22px; font-weight: 700; }
QLabel#PageSub { color: #9ca3af; font-size: 12px; }
QLabel#CardTitle { color: #e5e7eb; font-size: 14px; font-weight: 600; }
QLabel#CardSub { color: #9ca3af; font-size: 12px; }

QFrame#Card { background: #132622; border: 1px solid #1f3530; border-radius: 12px; }

/* 提示框 */
QFrame#TipBox { background: transparent; border: none; }
QLabel#TipText { color: #9ca3af; font-size: 12px; }

QLabel#BadgeSuccess { background: #064e3b; color: #6ee7b7; border-radius: 999px;
    padding: 3px 10px; font-size: 11px; font-weight: 600; }
QLabel#BadgeWarn { background: #78350f; color: #fcd34d; border-radius: 999px;
    padding: 3px 10px; font-size: 11px; font-weight: 600; }
QLabel#BadgeNeutral { background: #1f3530; color: #9ca3af; border-radius: 999px;
    padding: 3px 10px; font-size: 11px; font-weight: 600; }
QLabel#BadgeInfo { background: #1e3a8a; color: #93c5fd; border-radius: 999px;
    padding: 3px 10px; font-size: 11px; font-weight: 600; }

QPushButton#Primary { background: #14b8a6; color: #0a1714; border: none;
    border-radius: 8px; padding: 0 18px; font-size: 13px; font-weight: 600; }
QPushButton#Primary:hover { background: #2dd4bf; }
QPushButton#Primary:pressed { background: #5eead4; }
QPushButton#Primary:disabled { background: #1f3530; color: #6b7280; }
QPushButton#Secondary { background: #132622; color: #e5e7eb; border: 1px solid #1f3530;
    border-radius: 8px; padding: 9px 18px; font-size: 13px; }
QPushButton#Secondary:hover { border-color: #374151; }
QPushButton#Secondary:disabled { color: #4b5563; background: #0f1f1c; }
QPushButton#Ghost { background: transparent; color: #9ca3af; border: none;
    padding: 8px 14px; font-size: 13px; border-radius: 8px; }
QPushButton#Ghost:hover { background: #1a2f2b; color: #e5e7eb; }
QPushButton#Danger { background: #132622; color: #f87171; border: 1px solid #f87171;
    border-radius: 8px; padding: 9px 18px; font-size: 13px; }
QPushButton#Danger:hover { background: #2a1212; }
QPushButton#Danger:disabled { color: #4b5563; border-color: #374151; background: #132622; }

QLineEdit { background: #1a2f2b; border: 1px solid #1f3530; border-radius: 8px;
    padding: 8px 12px; font-size: 13px; color: #e5e7eb;
    selection-background-color: #134e4a; selection-color: #5eead4; }
QLineEdit:focus { border: 1px solid #14b8a6; }
QLineEdit:disabled { background: #0f1f1c; color: #4b5563; }
QComboBox { background: #1a2f2b; border: 1px solid #1f3530; border-radius: 8px;
    padding: 7px 12px; font-size: 13px; color: #e5e7eb; }
QComboBox:focus { border: 1px solid #14b8a6; }
QComboBox::drop-down { background: #1a2f2b; border: none; width: 24px; subcontrol-origin: padding; subcontrol-position: top right; }
QComboBox::drop-down:hover { background: #1f3530; }
QComboBox::down-arrow { image: none; width: 0; height: 0;
    border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid #9ca3af; margin-right: 8px; }
QComboBox QAbstractItemView { background: #132622; border: 1px solid #1f3530;
    border-radius: 8px; padding: 4px;
    selection-background-color: #134e4a; selection-color: #5eead4; outline: none; }

QListWidget { background: #0f1f1c; border: none; border-radius: 10px;
    padding: 8px 10px; font-size: 13px; outline: none; color: #e5e7eb; }
QListWidget::item { padding: 4px 10px; border-radius: 6px; color: #e5e7eb; }
QListWidget::item:hover { background: #1a2f2b; }
QListWidget::item:selected { background: #134e4a; color: #5eead4; }
QListWidget::item:selected:hover { background: #0f766e; }

QStatusBar { background: transparent; color: #6b7280; font-size: 12px; }

/* 滚动条（垂直 + 水平均完整定义，避免出现原生箭头/小方块残留） */
QScrollBar:vertical { background: transparent; width: 8px; margin: 0; border: none; }
QScrollBar::handle:vertical { background: #1f3530; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #374151; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; width: 0;
    background: none; border: none; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; border: none; }
QScrollBar:horizontal { background: transparent; height: 8px; margin: 0; border: none; }
QScrollBar::handle:horizontal { background: #1f3530; border-radius: 4px; min-width: 24px; }
QScrollBar::handle:horizontal:hover { background: #374151; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { height: 0; width: 0;
    background: none; border: none; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; border: none; }
QAbstractScrollArea::corner { background: transparent; border: none; }
"""


# ============================================================ 全局异常钩子

def _global_excepthook(exc_type, exc_value, exc_tb):
    """全局异常钩子：避免偶发静默闪退。"""
    import traceback
    traceback.print_exception(exc_type, exc_value, exc_tb)
    try:
        app = QApplication.instance()
        if app is not None:
            QMessageBox.critical(
                None, "程序异常",
                f"发生未捕获异常：\n{exc_type.__name__}: {exc_value}")
    except Exception:  # noqa: BLE001
        pass


sys.excepthook = _global_excepthook


# ============================================================ 后台 Worker

class Worker(QThread):
    """在后台线程跑耗时操作，通过信号把日志/状态回传主线程。"""
    log_signal = Signal(str)
    status_signal = Signal(str)
    done_signal = Signal(bool)  # True=成功, False=出错

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    def run(self):
        ok = True
        try:
            self._fn(self.log_signal.emit, self.status_signal.emit)
        except Exception as e:  # noqa: BLE001
            ok = False
            self.log_signal.emit(f"✗ [异常] {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.done_signal.emit(ok)


# ============================================================ 主窗口

# 导航定义：name -> (display, 图标种类)
NAV_ITEMS = [
    ("汉化", "hanhua"),
    ("字典", "zidian"),
    ("关于", "guanyu"),
]


def _nav_icon(kind: str, color: str, size: int = 18) -> QIcon:
    """按主题稿绘制线性导航图标（24 单位坐标系、描边 2、圆角端点）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = size / 24.0
    p.scale(s, s)
    pen = QPen(QColor(color))
    pen.setWidthF(2.0)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    if kind == "hanhua":        # 圆 + 对勾
        p.drawEllipse(QPointF(12, 12), 10, 10)
        path = QPainterPath(QPointF(8.5, 12.5))
        path.lineTo(11, 15)
        path.lineTo(16, 9)
        p.drawPath(path)
    elif kind == "zidian":      # 书本
        p.drawRoundedRect(QRectF(6, 2, 14, 20), 2.5, 2.5)
        p.drawLine(QPointF(6, 17), QPointF(20, 17))
    else:                       # guanyu：信息圆
        p.drawEllipse(QPointF(12, 12), 10, 10)
        p.drawLine(QPointF(12, 16), QPointF(12, 11))
        p.drawLine(QPointF(12, 8.01), QPointF(12, 7.99))
    p.end()
    return QIcon(pm)


# ============================================================ 自绘开关

class Switch(QAbstractButton):
    """胶囊开关（自绘，替代 QCheckBox::indicator）。

    自绘原因：
    1. QCheckBox 获得焦点时 Qt 会在标签周围绘制虚线焦点框（观感突兀），
       且 QSS 无法可靠关闭；
    2. QSS 的 ::indicator 只能涂一块色，画不出「滑块」，看着不像开关。
    自绘后可完全控制：底色随状态平滑过渡 + 白色滑块左右位移，无任何多余边框。
    """

    W, H, _PAD = 46, 26, 3

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)          # 关键：不产生焦点虚线框
        self.setFixedSize(self.W, self.H)
        self.setAttribute(Qt.WA_Hover, True)
        self._dark = False
        self._t = 0.0                            # 0=关，1=开（动画进度）
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._on_toggled)

    # --- 供 QPropertyAnimation 驱动的动画属性 ---
    def _get_knob(self) -> float:
        return self._t

    def _set_knob(self, v: float) -> None:
        self._t = float(v)
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def set_dark(self, dark: bool) -> None:
        self._dark = bool(dark)
        self.update()

    def set_checked_instant(self, on: bool) -> None:
        """无动画地同步状态（程序化刷新用，避免非点击场景出现滑动效果）。"""
        self._anim.stop()
        self.blockSignals(True)
        self.setChecked(bool(on))
        self.blockSignals(False)
        self._t = 1.0 if on else 0.0
        self.update()

    def _on_toggled(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._t)
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def sizeHint(self) -> QSize:
        return QSize(self.W, self.H)

    def enterEvent(self, e):
        super().enterEvent(e)
        self.update()

    def leaveEvent(self, e):
        super().leaveEvent(e)
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        rad = r.height() / 2.0

        if self._dark:
            off_c, on_c, knob_c = QColor("#374151"), QColor("#14b8a6"), QColor("#f3f4f6")
        else:
            off_c, on_c, knob_c = QColor("#cbd5e1"), QColor("#0d6b5e"), QColor("#ffffff")

        t = self._t
        bg = QColor(
            round(off_c.red()   + (on_c.red()   - off_c.red())   * t),
            round(off_c.green() + (on_c.green() - off_c.green()) * t),
            round(off_c.blue()  + (on_c.blue()  - off_c.blue())  * t),
        )
        if not self.isEnabled():
            bg.setAlpha(110)
        elif self.underMouse():
            bg = bg.lighter(112) if self._dark else bg.darker(108)

        p.setPen(Qt.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, rad, rad)

        # 滑块
        d = r.height() - self._PAD * 2
        x0 = r.left() + self._PAD
        x1 = r.right() - self._PAD - d
        x = x0 + (x1 - x0) * t
        p.setBrush(knob_c)
        p.drawEllipse(QRectF(x, r.top() + self._PAD, d, d))
        p.end()


class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        # 窗口图标：onefile 运行时从 sys._MEIPASS 加载，开发态从脚本目录加载
        _icon_base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        self.setWindowIcon(QIcon(os.path.join(_icon_base, "assets", "icon.ico")))
        self.resize(1000, 660)
        self.setMinimumSize(820, 540)
        self._busy = False
        self._worker = None

        central = QWidget()
        self.setCentralWidget(central)
        self._build_layout(central)

        # 主题（先建控件，再 apply，让所有 objectName 生效）
        self._theme = "light"
        self._apply_theme(self._load_theme())

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("就绪")

        self._pages = {}
        self._nav = {}
        self._build_sidebar()
        self._build_stack()

        if self._auto_detect():
            self._refresh_path()
        # 启动时按本机实际状态初始化开关；若上次选择了「禁止」而本机被恢复，
        # 自动补执行一次，保证设置持续保持生效
        self._refresh_update_pill(apply_preference=True)

    # ---------------------------------------------------------------- 主题
    def _load_theme(self) -> str:
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        v = s.value("theme", "light")
        return "dark" if str(v) == "dark" else "light"

    def _save_theme(self, name: str) -> None:
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue("theme", name)

    def _apply_theme(self, name: str) -> None:
        """整体替换 QSS，刷新图标着色，保持无闪烁。"""
        self._theme = name
        QApplication.instance().setStyleSheet(QSS_DARK if name == "dark" else QSS_LIGHT)
        self._save_theme(name)
        # 自绘开关不读 QSS，需要手动同步配色
        if getattr(self, "sw_disable_update", None) is not None:
            self.sw_disable_update.set_dark(name == "dark")
        # 重新着色侧栏图标（主题色改变）
        if hasattr(self, "_nav") and self._nav:
            self._retint_nav_icons()

    def _on_toggle_theme(self, btn: QPushButton) -> None:
        self._apply_theme("dark" if btn.property("opt") == "dark" else "light")
        # 同步分段按钮的 checked
        for b in self._theme_group.buttons():
            b.setChecked(b is btn)
        # 重新着色所有 nav 图标（因为 _apply_theme 可能在 _build 之前调）
        self._retint_nav_icons()

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

        # 主体（v1.1：移除顶部薄荷色条，整体白色）
        body = QWidget()
        body.setContentsMargins(0, 0, 0, 0)
        self._body_h = QHBoxLayout(body)
        self._body_h.setContentsMargins(0, 0, 0, 0)
        self._body_h.setSpacing(0)
        root.addWidget(body, 1)

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(16, 18, 16, 16)
        sb.setSpacing(4)

        # Logo block
        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        badge = QLabel("译")
        badge.setObjectName("LogoBadge")
        badge.setAlignment(Qt.AlignCenter)
        logo_row.addWidget(badge)
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        nav_title = QLabel("汉化工具")
        nav_title.setObjectName("NavTitle")
        nav_sub = QLabel(f"v{APP_VERSION}")
        nav_sub.setObjectName("NavSub")
        title_box.addWidget(nav_title)
        title_box.addWidget(nav_sub)
        logo_row.addLayout(title_box)
        logo_row.addStretch(1)
        sb.addLayout(logo_row)
        sb.addSpacing(14)

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
            b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _checked=False, n=name: self._switch_page(n))
            self._nav_group.addButton(b)
            self._nav[name] = b
            sb.addWidget(b)
        self._retint_nav_icons()

        sb.addStretch(1)

        # 侧栏底部：主题分段 + 版权
        theme_row = QHBoxLayout()
        theme_row.setSpacing(0)
        theme_wrap = QWidget()
        theme_wrap.setObjectName("ThemeToggle")
        tw = QHBoxLayout(theme_wrap)
        tw.setContentsMargins(4, 4, 4, 4)
        tw.setSpacing(0)
        self._theme_group = QButtonGroup(self)
        self._theme_group.setExclusive(True)
        for opt, label in (("light", "☀ 亮色"), ("dark", "🌙 暗色")):
            tb = QPushButton(label)
            tb.setObjectName("ThemeOpt")
            tb.setCheckable(True)
            tb.setProperty("opt", opt)
            tb.setCursor(Qt.PointingHandCursor)
            tb.setFocusPolicy(Qt.NoFocus)
            tb.clicked.connect(lambda _checked=False, b=tb: self._on_toggle_theme(b))
            self._theme_group.addButton(tb)
            tw.addWidget(tb)
        theme_row.addWidget(theme_wrap)
        sb.addLayout(theme_row)
        # 初始选中
        for b in self._theme_group.buttons():
            b.setChecked(b.property("opt") == self._theme)

        self._body_h.addWidget(sidebar)

    def _build_stack(self):
        self._stack = QStackedWidget()
        self._body_h.addWidget(self._stack, 1)
        # 各页统一套滚动区：窗口变小时可滚动，避免控件被挤压变形
        self._pages["汉化"] = self._wrap_scroll(self._build_home())
        self._pages["字典"] = self._wrap_scroll(self._build_dict())
        self._pages["关于"] = self._wrap_scroll(self._build_about())
        for w in self._pages.values():
            self._stack.addWidget(w)
        self._stack.setCurrentWidget(self._pages["汉化"])

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

    # ---------------------------------------------------------------- 主页
    def _build_home(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(24, 14, 24, 14)
        outer.setSpacing(10)

        # 子页头（v1.3：应用户要求删除 eyebrow「汉化 · APPLY」）
        outer.addLayout(self._make_page_header(
            title="一键汉化 GitHub Desktop",
            sub="选择版本并应用，整文件覆盖 main.js / renderer.js。",
            right_widget=self._make_badge("BadgeSuccess", f"内置 {len(zhcore.list_versions())} 个版本"),
        ))

        # Card 1 — 安装路径（状态徽标放在标题行右侧，与其他卡片/页头对齐一致）
        self._path_pill = QLabel("待检测")
        self._path_pill.setObjectName("BadgeNeutral")
        c1 = self._make_card("GitHub Desktop 安装", "指向 resources/app 目录",
                             right_widget=self._path_pill)
        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.path_var = QLineEdit()
        self.path_var.setPlaceholderText(r"例如 C:\Users\你\AppData\Local\GitHubDesktop\app-3.6.4\resources\app")
        self.path_var.setMinimumHeight(36)
        row1.addWidget(self.path_var, 1)
        row1.addWidget(self._make_btn("浏览", "Secondary", self._browse))
        row1.addWidget(self._make_btn("自动检测", "Secondary", self._refresh_path))
        c1.body.addLayout(row1)
        outer.addWidget(c1.frame)

        # Card 2 — 汉化版本
        c2 = self._make_card("汉化版本", "路径变化时自动按 app-X.Y.Z 对齐")
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel("选择版本："))
        self._version_combo = QComboBox()
        self._version_combo.setMinimumWidth(140)
        self._version_combo.setMinimumHeight(36)
        self._version_combo.setToolTip("选择要应用到 GitHub Desktop 的汉化版本")
        self._version_combo.currentTextChanged.connect(lambda _t: self._update_version_hint())
        row2.addWidget(self._version_combo)
        self._version_hint = QLabel()
        self._version_hint.setObjectName("CardSub")
        row2.addWidget(self._version_hint, 1)
        c2.body.addLayout(row2)
        outer.addWidget(c2.frame)

        # Card 3 — 操作
        c3 = self._make_card("应用汉化", "首次应用会自动备份原文件为 .bak；还原可恢复英文原版")
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
            "开启后改名 Update.exe 以阻断自动更新（可逆，不改动程序文件）",
            right_widget=self._update_pill)
        row_u = QHBoxLayout()
        row_u.setSpacing(10)
        # 上下各留 5px：使本行高度 36px，与其它卡片的输入框/按钮行保持一致
        row_u.setContentsMargins(0, 5, 0, 5)
        self.sw_disable_update = Switch()
        self.sw_disable_update.toggled.connect(self._on_toggle_disable_update)
        lbl_u = QLabel("禁止 GitHub Desktop 自动更新")
        row_u.addWidget(self.sw_disable_update)
        row_u.addWidget(lbl_u, 0, Qt.AlignVCenter)
        row_u.addStretch(1)
        cu.body.addLayout(row_u)
        outer.addWidget(cu.frame)

        # Card 4 — 运行日志
        c4 = self._make_card("运行日志", "操作反馈与提示，含 ✓ ✗ ⚠ 彩色圆点")
        self.log = self._make_list(140)
        c4.body.addWidget(self.log)
        outer.addWidget(c4.frame, 1)

        self._refresh_versions()
        return page

    # ---------------------------------------------------------------- 字典页
    def _build_dict(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(24, 14, 24, 14)
        outer.setSpacing(10)

        n = len(zhcore.list_versions())
        outer.addLayout(self._make_page_header(
            title="内置汉化版本",
            sub="源自 743859910 的 MIT 整文件补丁，纯净离线。",
            right_widget=self._make_badge("BadgeInfo", f"{n} 个版本"),
        ))

        c1 = self._make_card("版本列表")
        self.dict_list = self._make_list(180)
        c1.body.addWidget(self.dict_list)
        outer.addWidget(c1.frame)

        c2 = self._make_card("操作", "打开本地字典目录 / 校验内置版本")
        op = QHBoxLayout()
        op.setSpacing(8)
        op.addWidget(self._make_btn("打开本地字典目录", "Secondary", self._open_local_dict_dir))
        op.addWidget(self._make_btn("校验内置版本", "Secondary", self._on_check_dict))
        op.addStretch(1)
        c2.body.addLayout(op)
        c2.body.addSpacing(6)
        sub = QLabel("校验结果")
        sub.setObjectName("CardSub")
        c2.body.addWidget(sub)
        self.dict_check_list = self._make_list(120)
        c2.body.addWidget(self.dict_check_list)
        outer.addWidget(c2.frame, 1)

        tip = self._make_tip(
            "提示：内置最新 5 个汉化版本（3.6.0–3.6.4）。"
            "当 GitHub Desktop 推出未内置的新版本，或你使用的是未内置的旧版（3.5.0–3.5.9）时，可按以下步骤自定义汉化：\n"
            "1. 在 GitHub Desktop 的「帮助 → 关于 GitHub Desktop」中查看你的版本号（如 3.7.0 或 3.5.5）\n"
            "2. 前往字典项目（743859910 的仓库）下载或适配该版本的 main.js + renderer.js\n"
            "3. 点击上方「打开本地字典目录」，在弹出的 dictionaries/ 下新建与版本号完全一致的子目录（如 3.7.0）\n"
            "4. 把 main.js + renderer.js 放入该子目录，重启本程序\n"
            "5. 版本列表会出现该版本并标记「（本地）」，切换到「汉化」页选中即可一键应用")
        outer.addWidget(tip)

        return page

    def _refresh_dict_page(self):
        self.dict_list.clear()
        pairs = zhcore.list_version_sources()
        if not pairs:
            it = QListWidgetItem("（未找到任何汉化版本）")
            self.dict_list.addItem(it)
            return
        for v, src in pairs:
            tag = "（本地）" if src == "本地" else ""
            it = QListWidgetItem(f"GitHub Desktop {v}  {tag}")
            f = it.font()
            f.setWeight(QFont.DemiBold)
            it.setFont(f)
            self.dict_list.addItem(it)

    def _on_check_dict(self):
        self.dict_check_list.clear()
        zhcore.validate_builtin(
            log=lambda m: self._append_log(m, target=self.dict_check_list))

    # ---------------------------------------------------------------- 关于页
    def _build_about(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(24, 14, 24, 14)
        outer.setSpacing(10)

        outer.addLayout(self._make_page_header(
            title="GitHub Desktop 汉化工具",
        ))

        c1 = self._make_card(f"{APP_TITLE}  v{APP_VERSION}")
        body = QLabel(
            "基于 GitHub 用户 743859910 提供的 MIT 许可整文件汉化补丁，对 GitHub Desktop 的\n"
            "main.js / renderer.js 做整体中文替换。\n\n"
            "本工具基于 MIT 许可开源，与 GitHub, Inc. 无任何关联。\n"
            "仅支持 Windows 10 / 11。")
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
        v.setContentsMargins(20, 14, 20, 14)
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
                          right_widget: QWidget = None, eyebrow: str = "") -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(2)
        if eyebrow:
            e = QLabel(eyebrow)
            e.setObjectName("Eyebrow")
            left.addWidget(e)
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
        v.setContentsMargins(14, 10, 14, 10)
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
    def _append_log(self, msg: str, target: QListWidget = None) -> None:
        target = target if target is not None else self.log
        # 主题感知配色
        if self._theme == "dark":
            ok_c, err_c, warn_c = "#6ee7b7", "#fca5a5", "#fcd34d"
        else:
            ok_c, err_c, warn_c = "#065f46", "#b91c1c", "#92400e"
        color = "#e5e7eb" if self._theme == "dark" else "#111827"
        if any(k in msg for k in ("✓", "已", "成功", "命中", "就绪", "完成", "一致", "校验通过")):
            color = ok_c
        elif any(k in msg for k in ("✗", "错误", "失败", "无清单", "未自动", "异常", "未通过")):
            color = err_c
        elif any(k in msg for k in ("⚠", "未命中", "跳过", "不一致", "建议", "无效")):
            color = warn_c
        it = QListWidgetItem("● " + msg)
        it.setForeground(QColor(color))
        target.addItem(it)
        target.scrollToBottom()

    def _set_status(self, s: str) -> None:
        self.statusBar().showMessage(s)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.btn_apply.setEnabled(not busy)
        self.btn_restore.setEnabled(not busy)
        self._set_status("处理中…" if busy else "就绪")

    # ---------------------------------------------------------------- 路径
    def _refresh_path(self):
        self._set_status("正在自动检测安装目录…")
        found = zhcore.locate()
        if found:
            self.path_var.setText(found)
            self._path_pill.setText("已自动定位")
            self._path_pill.setObjectName("BadgeSuccess")
            self._path_pill.style().unpolish(self._path_pill)
            self._path_pill.style().polish(self._path_pill)
            self._set_status("已自动定位安装目录")
        else:
            guess = os.path.join(os.environ.get("LOCALAPPDATA", ""), "GitHubDesktop")
            self.path_var.setText(guess)
            self._path_pill.setText("未自动检测到")
            self._path_pill.setObjectName("BadgeWarn")
            self._path_pill.style().unpolish(self._path_pill)
            self._path_pill.style().polish(self._path_pill)
            self._set_status("未自动检测到，请手动选择安装目录")
        # 长路径输入框默认滚到末尾、开头被藏住，光标归零让用户先看到盘符
        self.path_var.setCursorPosition(0)
        self._sync_version_to_path()
        self._refresh_update_pill()

    def _browse(self):
        d = QFileDialog.getExistingDirectory(
            self, "选择 GitHub Desktop 的 resources/app 目录")
        if d:
            self.path_var.setText(d)
            self._path_pill.setText("已选择")
            self._path_pill.setObjectName("BadgeNeutral")
            self._path_pill.style().unpolish(self._path_pill)
            self._path_pill.style().polish(self._path_pill)
            self.path_var.setCursorPosition(0)
            self._sync_version_to_path()
            self._refresh_update_pill()

    def _open_local_dict_dir(self):
        d = zhcore.local_dict_dir()
        try:
            os.makedirs(d, exist_ok=True)
            os.startfile(d)
        except OSError as e:
            # 目录创建失败或系统无默认文件管理器时不应中断程序
            self._append_log(f"⚠ 无法打开本地字典目录：{e}")
            self._append_log(f"本地字典目录：{d}")

    # ---------------------------------------------------------------- 禁止自动更新
    def _load_disable_update(self) -> bool:
        """读取用户上次的偏好（仅在无法探测本机实际状态时作为回退）。"""
        s = QSettings(SETTINGS_ORG, SETTINGS_APP)
        v = s.value("disable_update", "true")
        return str(v).lower() not in ("false", "0", "")

    def _save_disable_update(self, on: bool) -> None:
        QSettings(SETTINGS_ORG, SETTINGS_APP).setValue("disable_update", "true" if on else "false")

    def _sync_update_ui(self, st) -> None:
        """把开关与徽标一次性刷成同一个状态（st: True/False/None）。

        两者永远同源，杜绝「开关显示已禁止、徽标却显示允许更新」的矛盾。
        """
        if st is None:
            self._update_pill.setText("未检测到 GD")
            self._update_pill.setObjectName("BadgeNeutral")
        else:
            self.sw_disable_update.set_checked_instant(bool(st))
            self._update_pill.setText("已禁止更新" if st else "允许更新")
            self._update_pill.setObjectName("BadgeSuccess" if st else "BadgeWarn")
        self._update_pill.style().unpolish(self._update_pill)
        self._update_pill.style().polish(self._update_pill)

    def _refresh_update_pill(self, apply_preference: bool = False) -> None:
        """按本机实际状态刷新开关与徽标。

        apply_preference=True（仅启动时）：若用户上次选择了「禁止」，而本机当前
        实际为「允许」，则自动补执行一次，兑现「设置持续保持」。
        """
        appdir = self.path_var.text().strip() or None
        actual = zhcore.auto_update_disabled(appdir)

        if actual is None:
            # 探测不到 GitHub Desktop：以偏好显示，不修改任何文件
            want = self._load_disable_update()
            self.sw_disable_update.set_checked_instant(want)
            self._sync_update_ui(None)
            return

        if apply_preference and not actual and self._load_disable_update():
            if zhcore.set_auto_update_disabled(
                    True, appdir, log=lambda m: self._append_log(m)):
                now = zhcore.auto_update_disabled(appdir)
                if now:
                    actual = True
                    self._append_log("· 已按上次的设置继续保持「禁止自动更新」")

        self._save_disable_update(bool(actual))
        self._sync_update_ui(actual)

    def _on_toggle_disable_update(self, checked: bool) -> None:
        """开关被点击：先在本机落地，成功后再持久化；失败则把开关回滚。

        ⚠ 不要用 stateChanged(int) 的参数判断：PySide6 6.x 的 Qt.CheckState 是
        原生 Python 枚举，与 int 不相等（`2 == Qt.Checked` 为 False）。旧实现
        `checked = (state == Qt.Checked)` 恒为 False，导致「开启」被误判成「关闭」，
        开关点多少次都无法真正禁用。此处直接以 toggled(bool) 为准。
        """
        want = bool(checked)
        appdir = self.path_var.text().strip() or zhcore.locate() or None
        verb = "禁止" if want else "允许"

        self._append_log(f"== {verb}自动更新 ==")
        ok = zhcore.set_auto_update_disabled(
            want, appdir, log=lambda m: self._append_log(m))

        actual = zhcore.auto_update_disabled(appdir)
        if actual is None:
            # 探测不到 GD：无法落地，还原开关并提示
            self.sw_disable_update.set_checked_instant(not want)
            self._sync_update_ui(None)
            self._set_status("未检测到 GitHub Desktop，设置未生效")
            return

        # 开关 / 徽标 / 偏好一律跟随实际结果
        self.sw_disable_update.set_checked_instant(bool(actual))
        self._save_disable_update(bool(actual))
        self._update_pill.setText("已禁止更新" if actual else "允许更新")
        self._update_pill.setObjectName("BadgeSuccess" if actual else "BadgeWarn")
        self._update_pill.style().unpolish(self._update_pill)
        self._update_pill.style().polish(self._update_pill)

        if actual == want:
            self._set_status(f"已{verb}自动更新（即时生效）")
            self._append_log(f"· 设置已即时生效：当前{verb}自动更新")
        else:
            self._set_status(f"未能{verb}自动更新")
            if not ok:
                self._append_log("· 提示：请关闭 GitHub Desktop 后重试，或检查是否以管理员权限安装")

    # ---------------------------------------------------------------- 版本
    def _refresh_versions(self):
        vers = zhcore.list_versions()
        self._version_combo.blockSignals(True)
        self._version_combo.clear()
        self._version_combo.addItems(vers)
        self._sync_version_to_path(vers)
        self._version_combo.blockSignals(False)
        self._update_version_hint(vers)

    def _sync_version_to_path(self, vers=None):
        if vers is None:
            vers = [self._version_combo.itemText(i)
                    for i in range(self._version_combo.count())]
        if not vers:
            return
        detected = zhcore.detect_version(self.path_var.text())
        idx = vers.index(detected) if (detected and detected in vers) else 0
        self._version_combo.setCurrentIndex(idx)

    def _update_version_hint(self, vers=None):
        if vers is None:
            vers = [self._version_combo.itemText(i)
                    for i in range(self._version_combo.count())]
        if not vers:
            self._version_hint.setText("未找到内置汉化版本")
            return
        detected = zhcore.detect_version(self.path_var.text())
        sel = self._version_combo.currentText()
        if detected and detected in vers:
            self._version_hint.setText(
                f"检测到已安装 GitHub Desktop {detected} · 共 {len(vers)} 个内置版本")
        else:
            self._version_hint.setText(
                f"当前选择 {sel} · 共 {len(vers)} 个内置版本")

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

    def _valid_path(self):
        appdir = self.path_var.text().strip()
        if not appdir or not os.path.isdir(appdir):
            QMessageBox.critical(
                self, "路径错误",
                "请先指定有效的 GitHub Desktop 安装目录（resources/app）。")
            return None
        return appdir

    def _on_apply(self):
        appdir = self._valid_path()
        if not appdir:
            return
        version = self._version_combo.currentText()
        if not version:
            QMessageBox.critical(self, "未选择版本", "请先在上方选择要应用的汉化版本。")
            return
        disable_after = self.sw_disable_update.isChecked()

        def _task(log, status):
            log(f"== 应用汉化（版本 {version}）==")
            status("正在应用汉化…")
            zhcore.apply_version(appdir, version, log=log)
            # 汉化完成后，按开关状态同步「禁止自动更新」（开关默认开启）
            log("== 同步禁止自动更新设置 ==")
            zhcore.set_auto_update_disabled(disable_after, appdir, log=log)

        self._run(_task)

    def _on_restore(self):
        appdir = self._valid_path()
        if not appdir:
            return

        def _task(log, status):
            log("== 还原为英文原版 ==")
            status("正在还原…")
            zhcore.restore(appdir, log=log)

        self._run(_task)

    def _on_worker_done(self, ok: bool) -> None:
        self._set_busy(False)
        if ok:
            self._set_status("就绪")
        else:
            self._set_status("操作异常")

    def closeEvent(self, event):
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


if __name__ == "__main__":
    qapp = QApplication(sys.argv)
    qapp.setFont(QFont("Segoe UI", 9))
    win = App()
    win.show()
    sys.exit(qapp.exec())
