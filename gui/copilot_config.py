"""Read and edit the managed commit-message section of Copilot's global rules.

Only ``copilot-instructions.md`` under ``COPILOT_HOME`` (or ``~/.copilot``)
is touched. Repository instructions and installed GitHub Desktop files are not
part of this module.
"""

import codecs
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile


START_MARKER = "<!-- github-desktop-zh:commit-message:start -->"
END_MARKER = "<!-- github-desktop-zh:commit-message:end -->"
_MARKER_PREFIX = "<!-- github-desktop-zh:commit-message:"
MISSING_REVISION = "missing"

DEFAULT_COMMIT_INSTRUCTIONS = """始终使用简体中文生成git commit message。
严格按照以下格式输出: <type>: <描述>。
只允许使用以下类型:feat、fix、docs、refactor、perf、dx、workflow、types、wip、test、build、ci、chore、deps、release。
根据本次暂存改动的主要目的，选择最合适的一个type，不要罗列多个。
不要输出英文，不要附加解释，不要输出列表，只输出最终的commit message。
描述要简洁、准确、自然，避免'更新代码'、'调整内容'这类空话。
内容要条理清晰，用序号的方式说明改动内容，每条要换行。
""".rstrip("\n")


class CopilotConfigConflictError(ValueError):
    """The instruction file changed since it was loaded or while saving."""


def global_instructions_path():
    """Return the global instruction path without creating any directories."""
    configured = os.environ.get("COPILOT_HOME", "")
    if configured:
        if not os.path.isabs(configured):
            raise ValueError("COPILOT_HOME 必须是绝对路径，不能使用相对路径。")
        directory = Path(configured)
    else:
        directory = Path.home() / ".copilot"
    return str(directory / "copilot-instructions.md")


def _read_snapshot(path):
    try:
        return True, path.read_bytes()
    except FileNotFoundError:
        return False, b""
    except OSError as error:
        raise OSError("无法读取 Copilot 全局指令文件 {}：{}".format(path, error)) from error


def _revision(exists, content):
    return hashlib.sha256(content).hexdigest() if exists else MISSING_REVISION


def _decode(content, path):
    bom = content.startswith(codecs.BOM_UTF8)
    try:
        return content.decode("utf-8-sig"), bom
    except UnicodeDecodeError as error:
        raise ValueError("Copilot 全局指令文件不是有效的 UTF-8 文本：{}".format(path)) from error


def _managed_section(text):
    """Return the exact marker span; never guess around damaged markers."""
    starts = text.count(START_MARKER)
    ends = text.count(END_MARKER)
    without_markers = text.replace(START_MARKER, "").replace(END_MARKER, "")
    if _MARKER_PREFIX in without_markers:
        raise ValueError("Copilot 全局指令中的提交说明区块标记残缺，请先修复该文件。")
    if starts == ends == 0:
        return None
    if starts != 1 or ends != 1:
        raise ValueError("Copilot 全局指令中的提交说明区块标记重复或残缺，请先修复该文件。")
    start = text.index(START_MARKER)
    end = text.index(END_MARKER)
    if end < start:
        raise ValueError("Copilot 全局指令中的提交说明区块标记顺序错误，请先修复该文件。")
    return start, end + len(END_MARKER)


def _prompt_from_section(text, section):
    if section is None:
        return ""
    start, end = section
    prompt = text[start + len(START_MARKER):end - len(END_MARKER)]
    # Strip only the formatting newline immediately next to each marker.
    # Deliberately retain user whitespace and blank lines within the prompt.
    prompt = re.sub(r"^(?:\r\n|\n|\r)", "", prompt, count=1)
    prompt = re.sub(r"(?:\r\n|\n|\r)$", "", prompt, count=1)
    return prompt.replace("\r\n", "\n").replace("\r", "\n")


def load_global_commit_instructions():
    """Load the managed prompt and unmodified text outside its markers.

    ``revision`` is a hash of the complete file, including a possible BOM.
    Pass it back to ``save_global_commit_instructions`` to detect edits made
    while a settings dialog was open.
    """
    path = Path(global_instructions_path())
    exists, content = _read_snapshot(path)
    text, _ = _decode(content, path)
    section = _managed_section(text)
    other = text if section is None else text[:section[0]] + text[section[1]:]
    return {
        "path": str(path),
        "prompt": _prompt_from_section(text, section),
        "other_instructions": other,
        "exists": exists,
        "revision": _revision(exists, content),
    }


def _assert_snapshot(path, expected_exists, expected_content):
    exists, content = _read_snapshot(path)
    if exists != expected_exists or content != expected_content:
        raise CopilotConfigConflictError(
            "Copilot 全局指令文件已被其他程序修改，请重新加载后再保存：{}".format(path)
        )


def _write_temporary(directory, prefix, content):
    descriptor, filename = tempfile.mkstemp(dir=str(directory), prefix=prefix)
    path = Path(filename)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


def save_global_commit_instructions(prompt, expected_revision=None):
    """Atomically update only our block and back up any existing file first.

    Empty or whitespace-only input removes the managed block. Unchanged bytes
    produce a no-op: no directory, backup, or temporary file is created.
    ``expected_revision`` is optional for callers that do not retain a loaded
    snapshot; concurrent changes during this save are checked in either case.
    """
    if not isinstance(prompt, str):
        raise TypeError("提交说明提示词必须是文本。")
    if START_MARKER in prompt or END_MARKER in prompt or _MARKER_PREFIX in prompt:
        raise ValueError("提交说明提示词不能包含管理区块标记。")

    path = Path(global_instructions_path())
    exists, original = _read_snapshot(path)
    if expected_revision is not None and expected_revision != _revision(exists, original):
        raise CopilotConfigConflictError(
            "Copilot 全局指令文件已被其他程序修改，请重新加载后再保存：{}".format(path)
        )
    text, bom = _decode(original, path)
    section = _managed_section(text)
    newline_match = re.search(r"\r\n|\n|\r", text)
    newline = newline_match.group(0) if newline_match else os.linesep
    normalized_prompt = prompt.replace("\r\n", "\n").replace("\r", "\n")
    if section is not None and prompt.strip() and _prompt_from_section(text, section) == normalized_prompt:
        return {"path": str(path), "backup_path": None, "changed": False}
    if prompt.strip():
        block = START_MARKER + newline + normalized_prompt.replace("\n", newline) + newline + END_MARKER
    else:
        block = ""

    if section is not None:
        updated = text[:section[0]] + block + text[section[1]:]
    elif block:
        separator = "" if not text or text.endswith(("\n", "\r")) else newline
        updated = text + separator + block
    else:
        updated = text
    encoded = (codecs.BOM_UTF8 if bom else b"") + updated.encode("utf-8")
    result = {"path": str(path), "backup_path": None, "changed": encoded != original}
    if not result["changed"]:
        return result

    backup = None
    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _assert_snapshot(path, exists, original)
        if exists:
            backup = _write_temporary(path.parent, path.name + ".bak-", original)
        temporary = _write_temporary(path.parent, "." + path.name + ".tmp-", encoded)
        if exists:
            os.chmod(str(temporary), stat.S_IMODE(path.stat().st_mode))
        # Recheck after writing the backup and staging file so external edits
        # during those operations cannot silently replace the editor's version.
        _assert_snapshot(path, exists, original)
        os.replace(str(temporary), str(path))
        temporary = None
    except CopilotConfigConflictError:
        raise
    except OSError as error:
        raise OSError("无法保存 Copilot 全局指令文件 {}：{}".format(path, error)) from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    result["backup_path"] = str(backup) if backup is not None else None
    return result
