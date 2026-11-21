"""diagnostics: 日志目录覆盖、滚动写入、重复初始化安全。"""
import logging
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from gui import diagnostics


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="diag-")
        self.addCleanup(self.tmp.cleanup)

    def tearDown(self):
        logger = logging.getLogger(diagnostics.LOGGER_NAME)
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)

    def test_setup_writes_to_override_directory(self):
        with mock.patch.dict(os.environ, {"GITHUB_DESKTOP_ZH_LOG_DIR": self.tmp.name}):
            path = diagnostics.setup_logging()
            self.assertEqual(Path(path), Path(self.tmp.name) / "app.log")
            diagnostics.get_logger().info("测试日志")
            content = Path(path).read_text(encoding="utf-8")
        self.assertIn("测试日志", content)

    def test_setup_is_idempotent(self):
        with mock.patch.dict(os.environ, {"GITHUB_DESKTOP_ZH_LOG_DIR": self.tmp.name}):
            first = diagnostics.setup_logging()
            second = diagnostics.setup_logging()
        self.assertEqual(first, second)
        self.assertEqual(len(logging.getLogger(diagnostics.LOGGER_NAME).handlers), 1)


if __name__ == "__main__":
    unittest.main()
