#!/usr/bin/env python3
"""Hooks of the devloop-hub plugin: guard rails for dev_loop projects.

Usage (from hooks.json): guard.py pre | session | stop, with the hook's JSON on stdin.

- pre:     PreToolUse. Blocks writes to frozen files (acceptance suites, loop scripts, STOP, milestones.json),
           new skip/xfail markers in tests, git commands that discard milestones.json, and pushes to main/master.
           Exit 2 + reason on stderr = blocked (Claude sees the reason).
- session: SessionStart. On a work branch `<worker>/work/<id>`: prints the milestone, its handoff and
           .claude/last_failure.md so the session starts with them.
- stop:    Stop. On a work branch: blocks once when files changed after the handoff was last written.

Active only in dev_loop projects (repo root has .claude/milestones.json). DEVLOOP_UNLOCK=1 turns pre and stop off.
Project overrides in .claude/devloop-guard.json: {"protect": [globs], "allow": [globs]}.
Only the standard library; must run on Linux, macOS and Windows (Git Bash).
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

PROTECT = [
    "tests/acceptance/*",
    "tests/acceptance/**",
    "run-loop.ps1",
    "check-runner.ps1",
    "loop-supervisor.ps1",
    "install-autostart.ps1",
    "loop-config.psd1",
    "tools/selfcheck.ps1",
    "STOP",
    ".claude/milestones.json",
    ".claude/devloop-guard.json",
]

SKIP_MARKERS = re.compile(
    r"pytest\.skip\s*\(|pytest\.mark\.skip|pytest\.mark\.xfail|pytest\.xfail\s*\(|"
    r"@unittest\.skip|unittest\.expectedFailure|\.skipTest\s*\(|@skip\b|pending\s*\(\s*\)"
)
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
WORK_BRANCH = re.compile(r"^(?P<worker>[^/]+)/work/(?P<id>.+)$")
ALL_ARGS_VERBS = {"rm", "mv", "touch", "truncate", "chmod", "tee", "unlink", "shred"}
LAST_ARG_VERBS = {"cp", "install", "ln", "rsync"}
REDIRECT = re.compile(r"\d?>>?\s*(?!&)([^\s;&|<>]+)")
MAX_CONTEXT = 12000


# ---------------------------------------------------------------- helpers

def repo_root(start: Path) -> Path | None:
    p = start.resolve()
    for cand in [p, *p.parents]:
        if (cand / ".git").exists():
            return cand
    return None


def is_devloop(root: Path | None) -> bool:
    return root is not None and (root / ".claude" / "milestones.json").is_file()


def load_rules(root: Path) -> tuple[list[str], list[str]]:
    protect, allow = list(PROTECT), []
    cfg = root / ".claude" / "devloop-guard.json"
    if cfg.is_file():
        try:
            data = json.loads(cfg.read_text(encoding="utf-8"))
            protect += [str(g) for g in data.get("protect", [])]
            allow += [str(g) for g in data.get("allow", [])]
        except (OSError, ValueError):
            pass  # a broken override never unlocks anything
    return protect, allow


def rel(root: Path, path: str, cwd: Path) -> str | None:
    p = Path(path)
    if not p.is_absolute():
        p = cwd / p
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None  # outside the repo: not ours to guard


def protected(relpath: str, protect: list[str], allow: list[str]) -> bool:
    match = lambda globs: any(fnmatch.fnmatchcase(relpath, g) for g in globs)
    return match(protect) and not match(allow)


def git(root: Path, *args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=10)
        return out.stdout.rstrip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def branch(root: Path) -> str:
    return git(root, "rev-parse", "--abbrev-ref", "HEAD")


def handoff_candidates(mid: str) -> list[str]:
    return [f"handoff/{mid}.md", f"handoff/{mid.lower().replace('.', '_')}.md"]


def count_markers(text: str) -> int:
    return len(SKIP_MARKERS.findall(text or ""))


def is_test_file(relpath: str) -> bool:
    name = relpath.rsplit("/", 1)[-1]
    return relpath.startswith("tests/") or "/tests/" in relpath or name.startswith("test_") or "_test." in name


def block(reason: str) -> int:
    print(f"devloop-hub guard: {reason} (CLAUDE.md, Forbidden). If a person really wants this, they do it "
          f"themselves or start the session with DEVLOOP_UNLOCK=1.", file=sys.stderr)
    return 2


# ---------------------------------------------------------------- pre

def check_write(event: dict, root: Path, cwd: Path) -> int:
    ti = event.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    relpath = rel(root, path, cwd) if path else None
    if relpath is None:
        return 0
    protect, allow = load_rules(root)
    if protected(relpath, protect, allow):
        return block(f"{relpath} is frozen")
    if is_test_file(relpath):
        tool = event.get("tool_name")
        if tool == "Edit":
            old, new = ti.get("old_string", ""), ti.get("new_string", "")
        elif tool == "MultiEdit":
            edits = ti.get("edits") or []
            old = "\n".join(e.get("old_string", "") for e in edits)
            new = "\n".join(e.get("new_string", "") for e in edits)
        elif tool == "Write":
            target = root / relpath
            try:
                old = target.read_text(encoding="utf-8") if target.is_file() else ""
            except OSError:
                old = ""
            new = ti.get("content", "")
        else:
            old, new = "", ti.get("new_source", "")
        if count_markers(new) > count_markers(old):
            return block(f"new skip/xfail marker in {relpath}")
    return 0


def split_commands(command: str) -> list[list[str]]:
    parts = re.split(r"&&|\|\||;|\n|\|", command)
    out = []
    for part in parts:
        try:
            words = shlex.split(part, posix=True)
        except ValueError:
            words = part.split()
        if words:
            out.append(words)
    return out


def check_bash(event: dict, root: Path, cwd: Path) -> int:
    command = (event.get("tool_input") or {}).get("command", "")
    protect, allow = load_rules(root)
    for words in split_commands(command):
        if words[0] == "git" and len(words) > 1:
            sub, rest = words[1], words[2:]
            if sub in ("checkout", "restore") and any("milestones.json" in w for w in rest):
                return block("git would discard .claude/milestones.json")
            whole_tree = (sub in ("checkout", "restore") and "." in rest) or (sub == "reset" and "--hard" in rest) \
                or (sub == "stash" and (not rest or rest[0] in ("push", "save", "-u", "--include-untracked", "--all")))
            if whole_tree and git(root, "status", "--porcelain", "--", ".claude/milestones.json"):
                return block(f"git {sub} would discard the uncommitted .claude/milestones.json (the loop keeps "
                             f"status and work_base there)")
            if sub == "push":
                targets = [w for w in rest if not w.startswith("-")][1:]  # after the remote
                refs = [t.split(":")[-1].replace("refs/heads/", "").lstrip("+") for t in targets]
                if "HEAD" in refs:
                    refs.append(branch(root))
                if any(r in ("main", "master") for r in refs):
                    return block("push to main/master; the hub merges, workers push their own branch")
                if not targets and branch(root) in ("main", "master"):
                    return block("push from main/master; the hub merges, workers push their own branch")
    targets = REDIRECT.findall(command)
    for words in split_commands(command):
        verb = words[0].rsplit("/", 1)[-1]
        args = [w for w in words[1:] if not w.startswith("-")]
        if verb in ALL_ARGS_VERBS or (verb == "sed" and any(w.startswith("-i") for w in words[1:])):
            targets += args
        elif verb in LAST_ARG_VERBS and args:
            targets.append(args[-1])
    for token in targets:
        relpath = rel(root, token.replace("\\", "/"), cwd)
        if relpath and protected(relpath, protect, allow):
            return block(f"command writes or removes {relpath}")
    return 0


def cmd_pre(event: dict) -> int:
    if os.environ.get("DEVLOOP_UNLOCK") == "1":
        return 0
    cwd = Path(event.get("cwd") or os.getcwd())
    root = repo_root(cwd)
    if not is_devloop(root):
        return 0
    tool = event.get("tool_name")
    if tool in WRITE_TOOLS:
        return check_write(event, root, cwd)
    if tool == "Bash":
        return check_bash(event, root, cwd)
    return 0


# ---------------------------------------------------------------- session

def milestone_entry(root: Path, mid: str) -> dict | None:
    try:
        data = json.loads((root / ".claude" / "milestones.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for m in data.get("milestones", []):
        if str(m.get("id", "")).lower() == mid.lower():
            return m
    return None


def cmd_session(event: dict) -> int:
    cwd = Path(event.get("cwd") or os.getcwd())
    root = repo_root(cwd)
    if not is_devloop(root):
        return 0
    br = branch(root)
    found = WORK_BRANCH.match(br)
    lines = [f"[devloop-hub] dev_loop project, branch {br or '?'}."]
    if not found:
        lines.append("Not on a work branch. Hub flow: /hub-next, /hub-start <project> <id>; the hub tool guide "
                     "explains the rest.")
        print("\n".join(lines))
        return 0
    mid = found.group("id")
    m = milestone_entry(root, mid)
    if m:
        checks = ", ".join(c.get("name", "?") for c in m.get("checks", []))
        lines.append(f"Milestone {mid}: {m.get('title', '')} (size {m.get('size', '?')}, "
                     f"model {m.get('model', '?')}, checks: {checks or 'none'}).")
    for name in handoff_candidates(mid):
        f = root / name
        if f.is_file():
            lines.append(f"\n--- {name} ---\n" + f.read_text(encoding="utf-8", errors="replace"))
            break
    else:
        lines.append(f"No handoff yet: create handoff/{mid}.md (submit and release need it).")
    failure = root / ".claude" / "last_failure.md"
    if failure.is_file():
        lines.append("\n--- .claude/last_failure.md ---\n" + failure.read_text(encoding="utf-8", errors="replace"))
    text = "\n".join(lines)
    print(text[:MAX_CONTEXT] + ("\n[cut]" if len(text) > MAX_CONTEXT else ""))
    return 0


# ---------------------------------------------------------------- stop

def changed_files(root: Path) -> list[str]:
    names = set()
    for line in git(root, "status", "--porcelain").splitlines():
        if len(line) > 3:
            names.add(line[3:].split(" -> ")[-1].strip('"'))
    base = ""
    for ref in ("origin/HEAD", "origin/main", "origin/master", "main", "master"):
        base = git(root, "merge-base", "HEAD", ref)
        if base:
            break
    if base:
        names.update(git(root, "diff", "--name-only", f"{base}..HEAD").splitlines())
    return [n for n in names if n]


def cmd_stop(event: dict) -> int:
    if os.environ.get("DEVLOOP_UNLOCK") == "1" or event.get("stop_hook_active"):
        return 0
    cwd = Path(event.get("cwd") or os.getcwd())
    root = repo_root(cwd)
    if not is_devloop(root):
        return 0
    found = WORK_BRANCH.match(branch(root))
    if not found:
        return 0
    mid = found.group("id")
    handoffs = handoff_candidates(mid)
    work = [n for n in changed_files(root) if n not in handoffs and (root / n).is_file()]
    if not work:
        return 0
    existing = [root / h for h in handoffs if (root / h).is_file()]
    newest_work = max((root / n).stat().st_mtime for n in work)
    if existing and max(f.stat().st_mtime for f in existing) >= newest_work:
        return 0
    reason = (f"Update handoff/{mid}.md before you stop (done, half done, next step, check results, open "
              f"decisions) and commit it. A run can be cut off at any time; only committed work and the handoff "
              f"survive.") if existing else (f"Create handoff/{mid}.md before you stop and commit it; submit and "
              f"release refuse a branch without it.")
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


def main(argv: list[str]) -> int:
    mode = argv[1] if len(argv) > 1 else ""
    try:
        event = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        event = {}
    try:
        return {"pre": cmd_pre, "session": cmd_session, "stop": cmd_stop}.get(mode, lambda e: 0)(event)
    except Exception as exc:  # a broken guard must never wedge a session
        print(f"devloop-hub guard error ({mode}): {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
