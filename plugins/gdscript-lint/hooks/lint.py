#!/usr/bin/env python3
"""PostToolUse hook of the gdscript-lint plugin: after every edit of a .gd file, run gdlint and gdformat --check
(gdtoolkit 4) on exactly that file and hand the findings back to Claude (exit 2 + stderr), so it fixes them in the
same turn instead of meeting them later in a check.

Settings, optional, in .claude/gdscript-lint.json of the project:
  {"lint": true, "format": false, "godot_check": false}
gdlint findings are reported only for the lines the edit wrote (old problems elsewhere in the file stay quiet);
format (gdformat --check, whole file) is off by default because it would ask to reformat files written in another style.
godot_check runs `$GODOT_BIN --headless --check-only -s <file>` (off by default: class_name and autoload references
give false errors). The environment variable GDSCRIPT_LINT=0 turns the hook off.
Only the standard library; Linux, macOS and Windows (Git Bash).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

WRITE_TOOLS = {"Edit", "Write", "MultiEdit"}
DEFAULTS = {"lint": True, "format": False, "godot_check": False}
MAX_LINES = 60


def project_root(start: Path) -> Path:
    for cand in [start, *start.parents]:
        if (cand / "project.godot").is_file() or (cand / ".git").exists():
            return cand
    return start


def settings(root: Path) -> dict:
    s = dict(DEFAULTS)
    cfg = root / ".claude" / "gdscript-lint.json"
    if cfg.is_file():
        try:
            s.update({k: bool(v) for k, v in json.loads(cfg.read_text(encoding="utf-8")).items() if k in DEFAULTS})
        except (OSError, ValueError):
            pass
    return s


def tool_cmd(name: str, module: str) -> list[str] | None:
    exe = shutil.which(name)
    if exe:
        return [exe]
    try:
        found = importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):
        found = False
    return [sys.executable, "-m", module] if found else None


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as exc:
        return 0, f"(could not run {cmd[0]}: {exc})"
    return out.returncode, (out.stdout + out.stderr).strip()


def shorten(text: str) -> str:
    lines = text.splitlines()
    return "\n".join(lines[:MAX_LINES] + ([f"... {len(lines) - MAX_LINES} more lines"] if len(lines) > MAX_LINES else []))


def changed_lines(event: dict, text: str) -> set[int] | None:
    """Line numbers (1-based) the edit wrote, or None for all (Write, or text not found)."""
    ti = event.get("tool_input") or {}
    if event.get("tool_name") == "Edit":
        news = [ti.get("new_string", "")]
    elif event.get("tool_name") == "MultiEdit":
        news = [e.get("new_string", "") for e in ti.get("edits") or []]
    else:
        return None
    lines: set[int] = set()
    for new in news:
        if not new.strip():
            continue
        at = text.find(new)
        if at < 0:
            return None
        first = text.count("\n", 0, at) + 1
        lines.update(range(first, first + new.count("\n") + 1))
    return lines


def filter_lint(out: str, lines: set[int] | None) -> list[str]:
    """gdlint lines `path:LINE: Error: ...` for the changed lines; other output (summary) dropped."""
    keep = []
    for line in out.splitlines():
        parts = line.split(":")
        num = next((int(p) for p in parts[1:3] if p.strip().isdigit()), None)
        if num is None:
            continue
        if lines is None or num in lines:
            keep.append(line)
    return keep


def missing_once(session: str) -> bool:
    """True the first time in a session that gdtoolkit is missing (so the hint comes once, not on every edit)."""
    marker = Path(tempfile.gettempdir()) / f"gdscript-lint-missing-{session or 'nosession'}"
    if marker.exists():
        return False
    try:
        marker.touch()
    except OSError:
        pass
    return True


def main() -> int:
    if os.environ.get("GDSCRIPT_LINT") == "0":
        return 0
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    if event.get("tool_name") not in WRITE_TOOLS:
        return 0
    path = (event.get("tool_input") or {}).get("file_path") or ""
    if not path.endswith(".gd"):
        return 0
    cwd = Path(event.get("cwd") or os.getcwd())
    file = Path(path) if Path(path).is_absolute() else cwd / path
    if not file.is_file():
        return 0
    root = project_root(file.resolve().parent)
    s = settings(root)
    findings = []
    lint, fmt = tool_cmd("gdlint", "gdtoolkit.linter"), tool_cmd("gdformat", "gdtoolkit.formatter")
    if (s["lint"] and not lint) or (s["format"] and not fmt):
        if missing_once(str(event.get("session_id", ""))):
            print('gdscript-lint: gdtoolkit is not installed, so .gd files are not checked. Tell your person: '
                  'pip install "gdtoolkit==4.*" (or set GDSCRIPT_LINT=0).', file=sys.stderr)
            return 2
        return 0
    if s["lint"]:
        code, out = run([*lint, str(file)], root)
        if code != 0:
            wanted = changed_lines(event, file.read_text(encoding="utf-8", errors="replace"))
            hits = filter_lint(out, wanted)
            if hits:
                findings.append("gdlint:\n" + shorten("\n".join(hits)))
            elif not filter_lint(out, None):
                findings.append("gdlint:\n" + shorten(out))  # a parse error or crash, not a rule finding
    if s["format"]:
        code, out = run([*fmt, "--check", "--diff", str(file)], root)
        if code != 0:
            findings.append(f"gdformat --check (run `gdformat {file.name}` to apply, or adapt the code):\n"
                            + shorten(out))
    godot = os.environ.get("GODOT_BIN")
    if s["godot_check"] and godot:
        code, out = run([godot, "--headless", "--check-only", "-s", str(file)], root)
        if code != 0:
            findings.append("godot --check-only:\n" + shorten(out))
    if not findings:
        return 0
    print(f"gdscript-lint found problems in {file.name}; fix them now (project rules: gdlintrc, "
          f".claude/gdscript-lint.json):\n\n" + "\n\n".join(findings), file=sys.stderr)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # a broken hook must never wedge a session
        print(f"gdscript-lint error: {exc}", file=sys.stderr)
        sys.exit(0)
