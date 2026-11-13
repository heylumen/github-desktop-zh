"""Rebuild the Windows x64 3.6.10 translations from the official NuGet package.

Requires Python 3.8+, Node.js and Acorn 8.15.0. See docs/3.6.10.md.
Only writes repository dictionary files, never an installed GitHub Desktop.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from zhtool import apply_entries, load_zh  # noqa: E402

PACKAGE_SHA256 = "0b6c599f45cf675208abd68459b3c8e99a533cc0a03e0d1544868a06d64e05fc"
ORIGINAL_SHA256 = {
    "main.js": "2f1afa93cfddec3d1e9e5634c40312a6842c6a6dc70c3757a4c53aa775f13857",
    "renderer.js": "3a5b3789b9755ffcd61e2e9cd05f4964364cbbedf28ab9d5b343e425a7c23cd4",
}
RELEASE = "https://github.com/desktop/desktop/releases/download/release-3.6.10/"
UPSTREAM_COMMIT = "51ab2165cc9d862dbff33c0f49e48906c74d6a13"


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--acorn", type=Path, required=True, help="Path to Acorn 8.15.0 dist/acorn.mjs")
    parser.add_argument("--node", default="node", help="Node.js executable")
    parser.add_argument("--output", type=Path, default=ROOT / "dictionaries" / "3.6.10")
    args = parser.parse_args()
    if sha256(args.package) != PACKAGE_SHA256:
        parser.error("Package SHA-256 does not match the official Windows x64 3.6.10 release")
    dictionary = ROOT / "translations" / "3.6.10.zh"
    entries = load_zh(dictionary)
    report = {
        "version": "3.6.10",
        "platform": "win32-x64",
        "package_url": RELEASE + "GitHubDesktop-3.6.10-x64-full.nupkg",
        "checksums_url": RELEASE + "GitHub.Desktop-3.6.10-checksums.txt",
        "package_sha256": PACKAGE_SHA256,
        "translation_source_url": "https://github.com/743859910/GitHub_Desktop_Simplified_Chinese/blob/"
                                  + UPSTREAM_COMMIT + "/Version/3.6.7/Temp/Windows.zh",
        "translation_rules_sha256": sha256(dictionary),
        "files": {},
    }
    work_root = ROOT / ".work"
    work_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="build-3.6.10-", dir=work_root) as temp:
        work = Path(temp)
        # TemporaryDirectory removes this tree on exit; keep it inside our workspace.
        work.resolve().relative_to(work_root.resolve())
        with zipfile.ZipFile(args.package) as package:
            base = "lib/net45/resources/app/"
            metadata = json.loads(package.read(base + "package.json"))
            if metadata["version"] != "3.6.10":
                parser.error("Unexpected package version")
            for target, expected in ORIGINAL_SHA256.items():
                original = work / ("original-" + target)
                original.write_bytes(package.read(base + target))
                if sha256(original) != expected:
                    parser.error("Unexpected official source hash: " + target)
                source = original.read_text(encoding="utf-8")
                translated, matched, unmatched = apply_entries(source, [e for e in entries if e[3] == target])
                output = work / target
                # Preserve the release's LF line endings even when running on Windows.
                output.write_bytes(translated.encode("utf-8"))
                verification = subprocess.run(
                    [args.node, str(ROOT / "scripts" / "verify_translation.mjs"),
                     str(original), str(output), str(args.acorn.resolve())],
                    check=True, capture_output=True, text=True, encoding="utf-8",
                )
                report["files"][target] = {
                    "original_sha256": expected,
                    "translated_sha256": sha256(output),
                    "matched_rules": len(matched),
                    "unmatched_rules": len(unmatched),
                    "validation": json.loads(verification.stdout),
                }
                (work / (target + ".LICENSE.txt")).write_bytes(package.read(base + target + ".LICENSE.txt"))
        # Both files must validate before any dictionary file is replaced.
        args.output.mkdir(parents=True, exist_ok=True)
        for target in ORIGINAL_SHA256:
            for name in (target, target + ".LICENSE.txt"):
                shutil.copyfile(work / name, args.output / name)
        shutil.copyfile(ROOT / "licenses" / "github-desktop-LICENSE", args.output / "LICENSE.github-desktop")
        shutil.copyfile(ROOT / "LICENSE", args.output / "LICENSE.translations")
        (args.output / "provenance.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
