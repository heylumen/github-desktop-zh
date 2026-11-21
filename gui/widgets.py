#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""widgets.py — 自绘导航图标与胶囊开关（PySide6）。"""
from PySide6.QtCore import QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSize, Qt, Property
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap, QPen
from PySide6.QtWidgets import QAbstractButton, QComboBox, QHBoxLayout, QLabel, QPushButton, QWidget


def nav_icon(kind: str, color: str, size: int = 18) -> QIcon:
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
    elif kind == "copilot":     # 提示词气泡
        path = QPainterPath(QPointF(5, 4))
        path.lineTo(19, 4)
        path.quadTo(22, 4, 22, 7)
        path.lineTo(22, 15)
        path.quadTo(22, 18, 19, 18)
        path.lineTo(10, 18)
        path.lineTo(5, 22)
        path.lineTo(5, 18)
        path.quadTo(2, 18, 2, 15)
        path.lineTo(2, 7)
        path.quadTo(2, 4, 5, 4)
        p.drawPath(path)
        p.drawLine(QPointF(7, 9), QPointF(17, 9))
        p.drawLine(QPointF(7, 13), QPointF(14, 13))
    else:                       # guanyu：信息圆
        p.drawEllipse(QPointF(12, 12), 10, 10)
        p.drawLine(QPointF(12, 16), QPointF(12, 11))
        p.drawLine(QPointF(12, 8.01), QPointF(12, 7.99))
    p.end()
    return QIcon(pm)


# ============================================================ 自绘开关

class ComboBox(QComboBox):
    """带自绘 chevron 的下拉框。

    QSS 的 ``::down-arrow`` 用 border 画三角在 Qt 子控件上会被渲染成短横线，
    因此隐藏原生箭头，统一用 QPainter 画一条 1.6px 的 chevron。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dark = False

    def set_dark(self, dark: bool) -> None:
        self._dark = bool(dark)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        color = QColor("#9ca3af" if self._dark else "#6b7280")
        if not self.isEnabled():
            color.setAlpha(110)
        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        x = self.width() - 15.0
        y = self.height() / 2.0
        painter.drawLine(QPointF(x - 4, y - 2), QPointF(x, y + 2))
        painter.drawLine(QPointF(x, y + 2), QPointF(x + 4, y - 2))
        painter.end()



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
        # 保持键盘可达：视觉焦点由 paintEvent 自绘，不使用 Qt 默认虚线框
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFixedSize(self.W, self.H)
        self.setAttribute(Qt.WA_Hover, True)
        self.setAccessibleName("禁止 GitHub Desktop 自动更新")
        self.setAccessibleDescription("按空格键切换")
        self._dark = False
        self._t = 0.0                            # 0=关，1=开（动画进度）
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._on_toggled)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            if self.isEnabled():
                self.toggle()
            event.accept()
            return
        super().keyPressEvent(event)

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

        # 自绘焦点环：键盘 Tab 时提供可见反馈，同时避免系统虚线框
        if self.hasFocus() and self.isEnabled():
            focus = QColor("#5eead4" if self._dark else "#0d6b5e")
            pen = QPen(focus)
            pen.setWidthF(1.5)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(1.0, 1.0, -1.0, -1.0), rad, rad)
        p.end()


# ============================================================ 无边框窗口铬件

def window_control_icon(kind: str, color: str, size: int = 20) -> QIcon:
    """绘制最小化/最大化/还原/关闭图标（20 单位坐标，细线）。"""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    s = size / 20.0
    p.scale(s, s)
    pen = QPen(QColor(color))
    pen.setWidthF(1.6)
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    if kind == "min":
        p.drawLine(QPointF(5, 10), QPointF(15, 10))
    elif kind == "max":
        p.drawRect(QRectF(5, 5, 10, 10))
    elif kind == "restore":
        p.drawRect(QRectF(7, 6, 8, 8))
        p.drawRect(QRectF(5, 8, 8, 8))
    else:  # close
        p.drawLine(QPointF(5, 5), QPointF(15, 15))
        p.drawLine(QPointF(15, 5), QPointF(5, 15))
    p.end()
    return QIcon(pm)


class WindowButton(QPushButton):
    def __init__(self, role: str, parent=None):
        super().__init__(parent)
        self._role = role
        self._dark = False
        self._hover = False
        self.setObjectName("WindowClose" if role == "close" else "WindowButton")
        self.setFixedSize(46, 32)
        self.setIconSize(QSize(12, 12))
        self.setFlat(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setCursor(Qt.PointingHandCursor)
        self._update_accessible()
        self._apply_icon()

    def _update_accessible(self):
        names = {"min": "最小化", "max": "最大化", "restore": "还原",
                 "close": "关闭"}
        self.setAccessibleName(names.get(self._role, "窗口按钮"))

    def set_role(self, role: str):
        if role == self._role:
            return
        self._role = role
        self._update_accessible()
        self._apply_icon()

    def set_dark(self, dark: bool):
        self._dark = dark
        self._apply_icon()

    def _apply_icon(self):
        color = "#ffffff" if (self._role == "close" and self._hover) else (
            "#e5e7eb" if self._dark else "#111827")
        self.setIcon(window_control_icon(self._role, color))

    def enterEvent(self, event):
        self._hover = True
        if self._role == "close":
            self._apply_icon()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        if self._role == "close":
            self._apply_icon()
        super().leaveEvent(event)


class TitleBar(QWidget):
    """无边框窗口标题栏：原生拖动、双击最大化、右侧窗口按钮。"""

    HEIGHT = 40

    def __init__(self, window, title: str, version: str, parent=None):
        super().__init__(parent or window)
        self._window = window
        self._press_global = None
        self.setObjectName("TitleBar")
        self.setFixedHeight(self.HEIGHT)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 0, 4, 0)
        row.setSpacing(8)

        icon = QLabel()
        icon.setPixmap(window.windowIcon().pixmap(16, 16))
        icon.setFixedSize(16, 16)
        icon.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row.addWidget(icon)

        title_label = QLabel(title)
        title_label.setObjectName("TitleBarTitle")
        title_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row.addWidget(title_label)
        version_label = QLabel(f"v{version}")
        version_label.setObjectName("TitleBarVersion")
        version_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        row.addWidget(version_label)
        row.addStretch(1)

        self.min_btn = WindowButton("min", self)
        self.max_btn = WindowButton("max", self)
        self.close_btn = WindowButton("close", self)
        self.min_btn.clicked.connect(self._window.showMinimized)
        self.max_btn.clicked.connect(self.toggle_maximized)
        self.close_btn.clicked.connect(self._window.close)
        row.addWidget(self.min_btn)
        row.addWidget(self.max_btn)
        row.addWidget(self.close_btn)
        self.sync_state()

    def set_dark(self, dark: bool):
        for button in (self.min_btn, self.max_btn, self.close_btn):
            button.set_dark(dark)

    def sync_state(self):
        self.max_btn.set_role("restore" if self._window.isMaximized() else "max")

    def toggle_maximized(self):
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()
        self.sync_state()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_global = None
            self.toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        self._press_global = event.globalPosition()
        event.accept()

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self._press_global is None:
            return super().mouseMoveEvent(event)
        delta = event.globalPosition() - self._press_global
        if abs(delta.x()) < 4 and abs(delta.y()) < 4:
            return
        self._press_global = None
        handle = self._window.windowHandle()
        if handle is None:
            return
        handle.startSystemMove()
        event.accept()

    def mouseReleaseEvent(self, event):
        self._press_global = None
        super().mouseReleaseEvent(event)


class ResizeHandle(QWidget):
    """无边框窗口 8 条缩放手柄；按下时进入系统缩放循环。"""

    def __init__(self, window, edges, parent=None):
        super().__init__(parent or window)
        self._window = window
        self._edges = edges
        self.setObjectName("ResizeHandle")
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(self._cursor_for(edges))

    @staticmethod
    def _cursor_for(edges):
        left = bool(edges & Qt.LeftEdge)
        right = bool(edges & Qt.RightEdge)
        top = bool(edges & Qt.TopEdge)
        bottom = bool(edges & Qt.BottomEdge)
        if (left and top) or (right and bottom):
            return Qt.SizeFDiagCursor
        if (right and top) or (left and bottom):
            return Qt.SizeBDiagCursor
        if left or right:
            return Qt.SizeHorCursor
        return Qt.SizeVerCursor

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        handle = self._window.windowHandle()
        if handle is None:
            return super().mousePressEvent(event)
        handle.startSystemResize(self._edges)
        event.accept()
