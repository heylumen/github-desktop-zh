#!/usr/bin/env python3
"""Fail if tracked text contains personal data or credentials.

This is a lightweight, dependency-free guard for accidental leaks. It scans
tracked files only and deliberately skips third-party dictionaries/translations.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_PREFIXES = ("dictionaries/", "translations/", "licenses/", "gui/build/", "gui/dist/")
PATTERNS = {
    "phone": re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)"),
    "id_card": re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
    "github_token": re.compile(r"\b(?:gh[pousr]_|github_pat_)[A-Za-z0-9_]{20,}\b"),
    "api_key": re.compile(r"\b(?:sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "local_user_path": re.compile(r"(?i)[A-Z]:\\Users\\([^\\\s\"']+)\\"),
    "local_account_path": re.compile(r"(?i)[A-Z]:\\Github\\([^\\\s\"']+)\\"),
}
ALLOWED_USERS = {"Public", "Default", "WDAGUtilityAccount"}


def files() -> list[str]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode("utf-8")
    return [f for f in output.split("\0") if f and not f.startswith(SKIP_PREFIXES)]


def main() -> int:
    failures = []
    for name in files():
        path = ROOT / name
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data[:4096]:
            continue
        text = data.decode("utf-8", "ignore")
        for line_no, line in enumerate(text.splitlines(), 1):
            for kind, pattern in PATTERNS.items():
                for match in pattern.finditer(line):
                    value = match.group(0)
                    if kind == "local_user_path" and match.group(1) in ALLOWED_USERS:
                        continue
                    masked = value if len(value) <= 8 else value[:6] + "…" + value[-3:]
                    failures.append(f"{name}:{line_no}  {kind}  {masked}")
    if failures:
        print("[FAIL] privacy gate")
        for item in failures:
            print("  - " + item)
        return 1
    print("[OK] privacy gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
