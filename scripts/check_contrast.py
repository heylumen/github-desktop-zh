#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Accessibility gate: fail when readable QSS text falls below 4.5:1.

It parses the actual QSS strings (not a duplicated token table), so changing a
color in ``gui/theme.py`` is checked immediately.
"""
from __future__ import annotations

from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gui"))

from theme import QSS_DARK, QSS_LIGHT  # noqa: E402

MIN_RATIO = 4.5
HEX_RE = re.compile(r"#([0-9a-fA-F]{6})")


def luminance(hex_color: str) -> float:
    value = hex_color.lstrip("#")
    channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [
        channel / 12.92 if channel <= 0.03928
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def block(qss: str, selector: str) -> str:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", qss)
    return match.group(1) if match else ""


def color(block_text: str, key: str = "color") -> str:
    match = re.search(key + r"\s*:\s*(#[0-9a-fA-F]{6})", block_text)
    return match.group(1) if match else ""


def checks_for(qss: str, is_dark: bool):
    if is_dark:
        surface, card, neutral_bg = "#0b1e1b", "#132622", "#1f3530"
    else:
        surface, card, neutral_bg = "#ffffff", "#ffffff", "#f3f4f6"
    return [
        ("TitleBarVersion", "QLabel#TitleBarVersion", surface),
        ("NavSub", "QLabel#NavSub", surface),
        ("QStatusBar", "QStatusBar", surface),
        ("PageSub", "QLabel#PageSub", surface),
        ("CardSub", "QLabel#CardSub", card),
        ("TipText", "QLabel#TipText", surface),
        ("Ghost", "QPushButton#Ghost", surface),
        ("BadgeNeutral", "QLabel#BadgeNeutral", neutral_bg),
        ("BadgeSuccess", "QLabel#BadgeSuccess", "#064e3b" if is_dark else "#d1fae5"),
        ("BadgeWarn", "QLabel#BadgeWarn", "#78350f" if is_dark else "#fef3c7"),
        ("BadgeInfo", "QLabel#BadgeInfo", "#1e3a8a" if is_dark else "#dbeafe"),
    ]


def main() -> int:
    failures = []
    for label, qss, is_dark in (("light", QSS_LIGHT, False), ("dark", QSS_DARK, True)):
        for name, selector, background in checks_for(qss, is_dark):
            text = block(qss, selector)
            foreground = color(text, "color")
            bg = color(text, "background") or background
            if not foreground:
                failures.append(f"{label}/{name}: 未找到 color")
                continue
            ratio = contrast(foreground, bg)
            if ratio < MIN_RATIO:
                failures.append(
                    f"{label}/{name}: {foreground} on {bg} = {ratio:.2f}:1 < {MIN_RATIO}")
    if failures:
        print("[FAIL] contrast gate")
        for failure in failures:
            print("  - " + failure)
        return 1
    print("[OK] contrast gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
