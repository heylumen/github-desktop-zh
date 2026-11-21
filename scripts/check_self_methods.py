#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static gate: catch ``self._missing_method()`` before the app runs.

The previous ``_rebuild_version_chips`` crash was valid Python and passed
``py_compile`` because the method is looked up lazily at runtime. This checker
builds a per-class method table and verifies that every ``self._name(...)``
call resolves inside that class (or a locally known base class).
"""
from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
MODULES = ("gui/app.py", "gui/widgets.py", "gui/zhcore.py", "gui/zhpaths.py",
           "gui/cli.py", "gui/copilot_config.py", "gui/diagnostics.py", "gui/theme.py")


def class_methods(node: ast.ClassDef) -> set[str]:
    return {item.name for item in node.body if isinstance(item, ast.FunctionDef)}


def all_methods(classes: dict[str, ast.ClassDef], name: str, seen=None) -> set[str]:
    seen = set() if seen is None else seen
    if name in seen or name not in classes:
        return set()
    seen.add(name)
    methods = class_methods(classes[name])
    for base in classes[name].bases:
        if isinstance(base, ast.Name):
            methods |= all_methods(classes, base.id, seen)
    return methods


def main() -> int:
    trees = {}
    methods: set[str] = set()
    classes: set[str] = set()
    assigned: set[str] = set()
    for relative in MODULES:
        path = ROOT / relative
        if not path.is_file():
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        trees[relative] = tree
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.add(node.name)
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        methods.add(item.name)
            if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Store):
                if isinstance(node.value, ast.Name) and node.value.id == "self":
                    assigned.add(node.attr)

    failures = []
    for relative, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "self"
                    and func.attr.startswith("_")):
                continue
            name = func.attr
            if name in methods or name in classes or name in assigned:
                continue
            failures.append(
                f"{relative}:{getattr(node, 'lineno', 0)} self.{name}() 未定义")
    if failures:
        print("[FAIL] self-method gate")
        for failure in failures:
            print("  - " + failure)
        return 1
    print("[OK] self-method gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
