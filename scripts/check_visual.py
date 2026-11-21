#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Screenshot regression gate for the main pages.

Generates deterministic offscreen screenshots for Home/About in light/dark and
compares them with ``tests/visual/baseline``. Run with ``--update`` after an
intentional UI change to regenerate the baselines.

Usage:
    python scripts/check_visual.py
    python scripts/check_visual.py --update
"""
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
GUI = ROOT / "gui"
BASELINE = ROOT / "tests" / "visual" / "baseline"
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("GDF_FORCE_OPAQUE", "1")

sys.path.insert(0, str(GUI))
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase, QImage  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import app as ui  # noqa: E402

WIDTH, HEIGHT = 1000, 660
TOLERANCE = 0.02       # <=2% pixels may differ (font AA / OS chrome)
MAX_CHANNEL_DELTA = 12  # ignore tiny antialias differences
THEMES = ("light", "dark")
PAGES = (("home", "汉化"), ("about", "关于"))


FIXTURE_ROOT = Path(os.environ.get("PUBLIC", r"C://Users//Public")) / "Documents" / "GitHubDesktopVisual"


def make_fixture() -> Path:
    shutil.rmtree(FIXTURE_ROOT, ignore_errors=True)
    appdir = FIXTURE_ROOT / "GitHubDesktop" / "app-3.6.10" / "resources" / "app"
    appdir.mkdir(parents=True)
    (appdir / "main.js").write_text('"About GitHub Desktop"', encoding="utf-8")
    (appdir / "renderer.js").write_text('"Changes"', encoding="utf-8")
    (appdir / "package.json").write_text('{"version":"3.6.10"}', encoding="utf-8")
    (appdir.parent.parent.parent / "Update.exe").write_bytes(b"update")
    return appdir


def build_window(temp: Path):
    fake = make_fixture()
    ui.App._remember_install = lambda self, path: None
    ui.App._last_install = lambda self: ""
    ui.App._detect_system_theme = lambda self: "light"
    ui.zhcore.locate = lambda preferred=None: str(fake)
    ui.zhcore.list_versions = lambda: ["3.6.10", "3.6.7"]
    qapp = QApplication.instance() or QApplication([])
    # 无头 Qt 默认字体库不含中文字体回退，显式加载系统字体，避免截图出现方框。
    for font_path in (
        Path(os.environ.get("WINDIR", r"C://Windows")) / "Fonts" / "msyh.ttc",
        Path(os.environ.get("WINDIR", r"C://Windows")) / "Fonts" / "msyhbd.ttc",
        Path(os.environ.get("WINDIR", r"C://Windows")) / "Fonts" / "simhei.ttf",
    ):
        if font_path.is_file():
            QFontDatabase.addApplicationFont(str(font_path))
    settings = temp / "settings"
    settings.mkdir()
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(settings))
    QSettings.setPath(QSettings.IniFormat, QSettings.SystemScope, str(settings))
    qapp.setFont(QFont("Microsoft YaHei UI" if "Microsoft YaHei UI" in QFontDatabase.families() else "Segoe UI", 9))
    win = ui.App()
    win.resize(WIDTH, HEIGHT)
    win.show()
    QTest.qWait(500)
    return qapp, win


def capture(win, theme: str, page: str, output: Path) -> None:
    win._apply_theme(theme)
    win._switch_page(page)
    QTest.qWait(250)
    image = win.grab()
    output.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(output), "PNG"):
        raise RuntimeError(f"无法保存截图：{output}")


def compare(reference: Path, current: Path) -> tuple[float, float]:
    expected = QImage(str(reference))
    actual = QImage(str(current))
    if expected.isNull() or actual.isNull():
        raise RuntimeError("截图无法读取")
    if expected.size() != actual.size():
        raise RuntimeError(f"尺寸不同：{expected.size()} vs {actual.size()}")
    width, height = expected.width(), expected.height()
    changed = 0
    total_delta = 0
    for y in range(height):
        for x in range(width):
            a = expected.pixelColor(x, y)
            b = actual.pixelColor(x, y)
            delta = max(abs(a.red() - b.red()), abs(a.green() - b.green()),
                        abs(a.blue() - b.blue()))
            total_delta += delta
            if delta > MAX_CHANNEL_DELTA:
                changed += 1
    pixels = width * height
    return changed / pixels, total_delta / (pixels * 255)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update", action="store_true", help="重写截图基线")
    parser.add_argument("--tolerance", type=float, default=TOLERANCE,
                        help="允许的差异像素比例，默认 0.02")
    args = parser.parse_args(argv)
    BASELINE.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="gdf-visual-") as tmp:
        qapp, win = build_window(Path(tmp))
        failures = []
        try:
            for theme in THEMES:
                for label, page in PAGES:
                    target = BASELINE / f"{theme}-{label}.png"
                    current = Path(tmp) / f"{theme}-{label}.png"
                    capture(win, theme, page, current)
                    if args.update:
                        target.write_bytes(current.read_bytes())
                        print(f"[update] {target.relative_to(ROOT)}")
                        continue
                    if not target.is_file():
                        failures.append(f"缺少基线：{target.relative_to(ROOT)}（运行 --update）")
                        continue
                    changed, mean_delta = compare(target, current)
                    print(f"{theme}-{label}: changed={changed:.4%} mean={mean_delta:.4f}")
                    if changed > args.tolerance:
                        failures.append(
                            f"{theme}-{label}: {changed:.2%} > {args.tolerance:.2%}")
        finally:
            shutil.rmtree(FIXTURE_ROOT, ignore_errors=True)
            win.copilot_editor.setPlainText(win._copilot_loaded_text)
            win._worker = None
            win.close()
            qapp.processEvents()

    if failures:
        print("[FAIL] visual gate")
        for failure in failures:
            print("  - " + failure)
        return 1
    print("[OK] visual gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
