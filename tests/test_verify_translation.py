"""verify_translation.mjs: 显示上下文白名单与受保护常量负面夹具。"""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "verify_translation.mjs"
ACORN = ROOT / ".work" / "js-parser" / "node_modules" / "acorn" / "dist" / "acorn.mjs"
NODE = shutil.which("node")
REQUIRE_NODE = os.environ.get("GDF_REQUIRE_NODE") == "1"


class VerifyTranslationTests(unittest.TestCase):
    def setUp(self):
        if NODE is None or not ACORN.is_file():
            message = "需要 Node.js 与 .work 中的 Acorn 8.15.0（见 docs/3.6.10.md）"
            if REQUIRE_NODE:
                self.fail(message + "；GDF_REQUIRE_NODE=1 不允许跳过")
            self.skipTest(message)
        self.tmp = tempfile.TemporaryDirectory(prefix="verify-js-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_verify(self, original, translated):
        source = self.root / "original.js"
        target = self.root / "translated.js"
        source.write_text(original, encoding="utf-8")
        target.write_text(translated, encoding="utf-8")
        return subprocess.run(
            [NODE, str(SCRIPT), str(source), str(target), str(ACORN)],
            capture_output=True, text=True, encoding="utf-8")

    def assertRejected(self, original, translated):
        result = self.run_verify(original, translated)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def assertAccepted(self, original, translated):
        result = self.run_verify(original, translated)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("displayContextEnforced", result.stdout)
        return result

    def test_allows_reviewed_display_property_and_child(self):
        original = "const x = createElement('div', {title: 'Open'}, 'Open');"
        translated = "const x = createElement('div', {title: '打开'}, '打开');"
        result = self.assertAccepted(original, translated)
        self.assertIn('"changedLiterals":2', result.stdout.replace(" ", ""))

    def test_allows_template_text_inside_display_call(self):
        original = "const x = createElement('div', null, `Open ${name}`);"
        translated = "const x = createElement('div', null, `打开 ${name}`);"
        self.assertAccepted(original, translated)

    def test_rejects_first_create_element_argument(self):
        self.assertRejected(
            "createElement('div', null);",
            "createElement('分隔', null);")

    def test_rejects_variable_declaration_constant(self):
        self.assertRejected("const value = 'stable';", "const value = '稳定';")

    def test_rejects_assignment_constant(self):
        self.assertRejected(
            "target.value = 'stable';", "target.value = '稳定';")

    def test_rejects_return_constant(self):
        self.assertRejected(
            "function f() { return 'stable'; }", "function f() { return '稳定'; }")

    def test_rejects_comparison_constant(self):
        self.assertRejected(
            "if (mode === 'stable') { go(); }", "if (mode === '稳定') { go(); }")

    def test_rejects_object_key(self):
        self.assertRejected("const o = {'stable': 1};", "const o = {'稳定': 1};")

    def test_rejects_enum_reverse_mapping(self):
        self.assertRejected(
            "e[e.Notifications = 5] = 'Notifications';",
            "e[e.Notifications = 5] = '通知';")

    def test_rejects_non_chinese_display_replacement(self):
        self.assertRejected(
            "const x = createElement('div', {title: 'Open'});",
            "const x = createElement('div', {title: 'OpenX'});")

    def test_rejects_changed_identifier(self):
        self.assertRejected("function stable() {}", "function renamed() {}")

    def test_rejects_template_expression_order_change(self):
        self.assertRejected(
            "const x = createElement('div', null, `${a}${b}`);",
            "const x = createElement('div', null, `${b}${a}`);")

    def test_rejects_syntax_error(self):
        result = self.run_verify("const a = 'x';", "const = ;")
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
