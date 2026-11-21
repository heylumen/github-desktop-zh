#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地诊断日志：滚动写入用户目录，便于排障与用户反馈。

不联网、不上传。可用 ``GITHUB_DESKTOP_ZH_LOG_DIR`` 指定目录（测试用）。
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
import tempfile

LOGGER_NAME = "github_desktop_zh"
_MAX_BYTES = 512 * 1024
_BACKUPS = 3


def log_directory():
    override = os.environ.get("GITHUB_DESKTOP_ZH_LOG_DIR")
    if override:
        return override
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return os.path.join(local, "GitHubDesktopZh", "logs")
    return os.path.join(tempfile.gettempdir(), "GitHubDesktopZh", "logs")


def log_path():
    return os.path.join(log_directory(), "app.log")


def setup_logging():
    """初始化滚动日志；重复调用安全。返回日志路径或 None。"""
    logger = logging.getLogger(LOGGER_NAME)
    if logger.handlers:
        return log_path()
    try:
        os.makedirs(log_directory(), exist_ok=True)
        handler = RotatingFileHandler(
            log_path(), maxBytes=_MAX_BYTES, backupCount=_BACKUPS, encoding="utf-8")
    except OSError:
        return None
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(threadName)s %(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return log_path()


def get_logger():
    return logging.getLogger(LOGGER_NAME)
