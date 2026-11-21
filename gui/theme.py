#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""theme.py — 明暗主题 QSS 与高对比度检测（纯字符串，无 Qt 依赖）。

Token 说明见仓库根 DESIGN.md。主题由 app.py 根据系统偏好选择。
"""

# ============================================================ 配色与 QSS
# Light / Dark 两套基线。主题由系统决定，颜色严格对齐 DESIGN.md 与下方 QSS 常量。

QSS_LIGHT = """
QMainWindow, QWidget { background-color: #ffffff; color: #111827;
    font-family: "Segoe UI", "Microsoft YaHei UI", "PingFang SC", system-ui, sans-serif;
    font-size: 13px; }

/* 侧栏 */
QWidget#Sidebar { background: #ffffff; border-right: 1px solid #e5e7eb; }
QWidget#TitleBar { background: #ffffff; border-bottom: 1px solid #e5e7eb; }
QLabel#TitleBarTitle { color: #111827; font-size: 12px; font-weight: 600; }
QLabel#TitleBarVersion { color: #6b7280; font-size: 11px; }
QPushButton#WindowButton, QPushButton#WindowClose { background: transparent;
    border: none; border-radius: 6px; }
QPushButton#WindowButton:hover { background: #f3f4f6; }
QPushButton#WindowButton:pressed { background: #e5e7eb; }
QPushButton#WindowClose:hover { background: #dc2626; }
QPushButton#WindowButton:focus, QPushButton#WindowClose:focus {
    border: 1px solid #0d6b5e; }
QLabel#NavSub { color: #6b7280; font-size: 11px; }
QPushButton#NavItem { background: transparent; color: #111827; border: none;
    text-align: left; padding: 8px 12px; font-size: 13px; border-radius: 8px; }
QPushButton#NavItem:hover { background: #f6f8fa; }
QPushButton#NavActive { background: #eef1f4; color: #111827; border: none;
    text-align: left; padding: 8px 12px; font-size: 13px; font-weight: 600;
    border-radius: 8px; }
QPushButton#NavActive:hover { background: #eef1f4; }
/* 键盘焦点可见（不使用系统虚线框） */
QPushButton#NavItem:focus, QPushButton#NavActive:focus {
    border: 1px solid #0d6b5e; outline: none; }

/* 子页头 */
QLabel#PageTitle { color: #111827; font-size: 22px; font-weight: 600; }
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
    padding: 2px 8px; font-size: 11px; font-weight: 600; }
QLabel#BadgeWarn { background: #fef3c7; color: #92400e; border-radius: 999px;
    padding: 2px 8px; font-size: 11px; font-weight: 600; }
QLabel#BadgeNeutral { background: #f3f4f6; color: #4b5563; border-radius: 999px;
    padding: 2px 8px; font-size: 11px; font-weight: 600; }
QLabel#BadgeInfo { background: #dbeafe; color: #1e40af; border-radius: 999px;
    padding: 2px 8px; font-size: 11px; font-weight: 600; }

/* 按钮 */
QPushButton#Primary { background: #0d6b5e; color: #ffffff; border: none;
    border-radius: 8px; padding: 0 16px; font-size: 13px; font-weight: 600; }
QPushButton#Primary:hover { background: #0a544a; }
QPushButton#Primary:pressed { background: #08453c; }
QPushButton#Primary:disabled { background: #a3c4bf; color: #ffffff; }
QPushButton#Secondary { background: #ffffff; color: #111827; border: 1px solid #d1d5db;
    border-radius: 8px; padding: 8px 16px; font-size: 13px; }
QPushButton#Secondary:hover { border-color: #9ca3af; }
QPushButton#Secondary:disabled { color: #9ca3af; background: #f3f4f6; }
QPushButton#Ghost { background: transparent; color: #4b5563; border: none;
    padding: 8px 12px; font-size: 13px; border-radius: 8px; }
QPushButton#Ghost:hover { background: #f3f4f6; color: #111827; }
QPushButton#Danger { background: #ffffff; color: #dc2626; border: 1px solid #dc2626;
    border-radius: 8px; padding: 8px 16px; font-size: 13px; }
QPushButton#Danger:hover { background: #fef2f2; }
QPushButton#Danger:disabled { color: #fca5a5; border-color: #fca5a5; background: #ffffff; }

/* 输入 */
QLineEdit, QPlainTextEdit { background: #ffffff; border: 1px solid #d1d5db; border-radius: 8px;
    padding: 8px 12px; font-size: 13px; color: #111827;
    selection-background-color: #cbd5e1; selection-color: #111827; }
QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid #0d6b5e; }
QLineEdit:disabled, QPlainTextEdit:disabled { background: #f3f4f6; color: #9ca3af; }
QComboBox { background: #ffffff; border: 1px solid #d1d5db; border-radius: 8px;
    padding: 8px 32px 8px 12px; font-size: 13px; color: #111827; }
QComboBox:focus { border: 1px solid #0d6b5e; }
QComboBox::drop-down { background: #ffffff; border: none; width: 24px; subcontrol-origin: padding; subcontrol-position: top right; }
QComboBox::drop-down:hover { background: #f6f8fa; }
QComboBox::down-arrow { image: none; width: 0; height: 0; }
QComboBox QAbstractItemView { background: #ffffff; border: 1px solid #d1d5db;
    border-radius: 8px; padding: 4px;
    selection-background-color: #eef1f4; selection-color: #111827; outline: none; }
QComboBox QAbstractItemView::item { min-height: 28px; padding: 4px 8px;
    color: #111827; }
QComboBox QAbstractItemView::item:hover { background: #f6f8fa; color: #111827; }
QComboBox QAbstractItemView::item:selected { background: #eef1f4; color: #111827; }
QPushButton#VersionChip { background: #ffffff; border: 1px solid #d1d5db; border-radius: 8px;
    padding: 0 12px; font-size: 13px; color: #111827; }
QPushButton#VersionChip:hover { background: #f6f8fa; }
QPushButton#VersionChip:checked { background: #eef1f4; border-color: #0d6b5e;
    color: #0d6b5e; font-weight: 600; }
QPushButton#VersionChip:focus { border: 1px solid #0d6b5e; }

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
QWidget#TitleBar { background: #0b1e1b; border-bottom: 1px solid #1f3530; }
QLabel#TitleBarTitle { color: #e5e7eb; font-size: 12px; font-weight: 600; }
QLabel#TitleBarVersion { color: #9ca3af; font-size: 11px; }
QPushButton#WindowButton, QPushButton#WindowClose { background: transparent;
    border: none; border-radius: 6px; }
QPushButton#WindowButton:hover { background: #1a2f2b; }
QPushButton#WindowButton:pressed { background: #134e4a; }
QPushButton#WindowClose:hover { background: #c42b1c; }
QPushButton#WindowButton:focus, QPushButton#WindowClose:focus {
    border: 1px solid #14b8a6; }
QLabel#NavSub { color: #9ca3af; font-size: 11px; }
QPushButton#NavItem { background: transparent; color: #e5e7eb; border: none;
    text-align: left; padding: 8px 12px; font-size: 13px; border-radius: 8px; }
QPushButton#NavItem:hover { background: #1a2f2b; }
QPushButton#NavActive { background: #134e4a; color: #5eead4; border: none;
    text-align: left; padding: 8px 12px; font-size: 13px; font-weight: 600;
    border-radius: 8px; }
QPushButton#NavActive:hover { background: #134e4a; }
/* 键盘焦点可见（不使用系统虚线框） */
QPushButton#NavItem:focus, QPushButton#NavActive:focus {
    border: 1px solid #14b8a6; outline: none; }

QLabel#PageTitle { color: #e5e7eb; font-size: 22px; font-weight: 600; }
QLabel#PageSub { color: #9ca3af; font-size: 12px; }
QLabel#CardTitle { color: #e5e7eb; font-size: 14px; font-weight: 600; }
QLabel#CardSub { color: #9ca3af; font-size: 12px; }

QFrame#Card { background: #132622; border: 1px solid #1f3530; border-radius: 12px; }

/* 提示框 */
QFrame#TipBox { background: transparent; border: none; }
QLabel#TipText { color: #9ca3af; font-size: 12px; }

QLabel#BadgeSuccess { background: #064e3b; color: #6ee7b7; border-radius: 999px;
    padding: 2px 8px; font-size: 11px; font-weight: 600; }
QLabel#BadgeWarn { background: #78350f; color: #fcd34d; border-radius: 999px;
    padding: 2px 8px; font-size: 11px; font-weight: 600; }
QLabel#BadgeNeutral { background: #1f3530; color: #9ca3af; border-radius: 999px;
    padding: 2px 8px; font-size: 11px; font-weight: 600; }
QLabel#BadgeInfo { background: #1e3a8a; color: #93c5fd; border-radius: 999px;
    padding: 2px 8px; font-size: 11px; font-weight: 600; }

QPushButton#Primary { background: #14b8a6; color: #0a1714; border: none;
    border-radius: 8px; padding: 0 16px; font-size: 13px; font-weight: 600; }
QPushButton#Primary:hover { background: #2dd4bf; }
QPushButton#Primary:pressed { background: #5eead4; }
QPushButton#Primary:disabled { background: #1f3530; color: #6b7280; }
QPushButton#Secondary { background: #132622; color: #e5e7eb; border: 1px solid #1f3530;
    border-radius: 8px; padding: 8px 16px; font-size: 13px; }
QPushButton#Secondary:hover { border-color: #374151; }
QPushButton#Secondary:disabled { color: #4b5563; background: #0f1f1c; }
QPushButton#Ghost { background: transparent; color: #9ca3af; border: none;
    padding: 8px 12px; font-size: 13px; border-radius: 8px; }
QPushButton#Ghost:hover { background: #1a2f2b; color: #e5e7eb; }
QPushButton#Danger { background: #132622; color: #f87171; border: 1px solid #f87171;
    border-radius: 8px; padding: 8px 16px; font-size: 13px; }
QPushButton#Danger:hover { background: #2a1212; }
QPushButton#Danger:disabled { color: #4b5563; border-color: #374151; background: #132622; }

QLineEdit, QPlainTextEdit { background: #1a2f2b; border: 1px solid #1f3530; border-radius: 8px;
    padding: 8px 12px; font-size: 13px; color: #e5e7eb;
    selection-background-color: #134e4a; selection-color: #5eead4; }
QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid #14b8a6; }
QLineEdit:disabled, QPlainTextEdit:disabled { background: #0f1f1c; color: #4b5563; }
QComboBox { background: #1a2f2b; border: 1px solid #1f3530; border-radius: 8px;
    padding: 8px 32px 8px 12px; font-size: 13px; color: #e5e7eb; }
QComboBox:focus { border: 1px solid #14b8a6; }
QComboBox::drop-down { background: #1a2f2b; border: none; width: 24px; subcontrol-origin: padding; subcontrol-position: top right; }
QComboBox::drop-down:hover { background: #1f3530; }
QComboBox::down-arrow { image: none; width: 0; height: 0; }
QComboBox QAbstractItemView { background: #132622; border: 1px solid #1f3530;
    border-radius: 8px; padding: 4px;
    selection-background-color: #134e4a; selection-color: #5eead4; outline: none; }
QComboBox QAbstractItemView::item { min-height: 28px; padding: 4px 8px;
    color: #e5e7eb; }
QComboBox QAbstractItemView::item:hover { background: #1a2f2b; color: #e5e7eb; }
QComboBox QAbstractItemView::item:selected { background: #134e4a; color: #5eead4; }
QPushButton#VersionChip { background: #132622; border: 1px solid #1f3530; border-radius: 8px;
    padding: 0 12px; font-size: 13px; color: #e5e7eb; }
QPushButton#VersionChip:hover { background: #1a2f2b; }
QPushButton#VersionChip:checked { background: #134e4a; border-color: #14b8a6;
    color: #5eead4; font-weight: 600; }
QPushButton#VersionChip:focus { border: 1px solid #14b8a6; }

QListWidget { background: #0f1f1c; border: none; border-radius: 10px;
    padding: 8px 10px; font-size: 13px; outline: none; color: #e5e7eb; }
QListWidget::item { padding: 4px 10px; border-radius: 6px; color: #e5e7eb; }
QListWidget::item:hover { background: #1a2f2b; }
QListWidget::item:selected { background: #134e4a; color: #5eead4; }
QListWidget::item:selected:hover { background: #0f766e; }

QStatusBar { background: transparent; color: #9ca3af; font-size: 12px; }

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


def high_contrast_enabled():
    """Windows 高对比度时放弃自定义 QSS，交还系统调色板。"""
    import sys
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    class HIGHCONTRASTW(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD),
                    ("pszDefaultScheme", wintypes.LPWSTR)]

    info = HIGHCONTRASTW()
    info.cbSize = ctypes.sizeof(info)
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(
            0x0042, ctypes.sizeof(info), ctypes.byref(info), 0)
    except (AttributeError, OSError):
        return False
    return bool(ok and (info.dwFlags & 0x00000001))
