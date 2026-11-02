"""Tests for plugins/devloop-hub/hooks/guard.py: run it as the hooks do, in throwaway git repositories."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parents[1] / "plugins" / "devloop-hub" / "hooks" / "guard.py"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


class GuardCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "proj"
        self.root.mkdir()
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@example.invalid")
        git(self.root, "config", "user.name", "t")
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "milestones.json").write_text(json.dumps({"milestones": [
            {"id": "M1.2", "title": "Feature", "size": "S", "model": "sonnet", "checks": [{"name": "unit", "cmd": "true"}]}
        ]}))
        (self.root / "tests" / "acceptance").mkdir(parents=True)
        (self.root / "tests" / "acceptance" / "test_m1.py").write_text("def test_a():\n    assert True\n")
        (self.root / "tests" / "unit").mkdir()
        (self.root / "tests" / "unit" / "test_x.py").write_text("def test_x():\n    assert True\n")
        (self.root / "src.py").write_text("x = 1\n")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-qm", "init")

    def tearDown(self):
        self._tmp.cleanup()

    def run_guard(self, mode: str, event: dict, env: dict | None = None):
        event.setdefault("cwd", str(self.root))
        e = dict(os.environ)
        e.pop("DEVLOOP_UNLOCK", None)
        e.update(env or {})
        return subprocess.run([sys.executable, str(GUARD), mode], input=json.dumps(event), capture_output=True,
                              text=True, env=e, timeout=30)

    def pre(self, tool: str, **tool_input):
        return self.run_guard("pre", {"tool_name": tool, "tool_input": tool_input})

    def assertBlocked(self, res):
        self.assertEqual(res.returncode, 2, res.stderr)
        self.assertIn("devloop-hub guard", res.stderr)

    def assertAllowed(self, res):
        self.assertEqual(res.returncode, 0, res.stderr)


class PreWrite(GuardCase):
    def test_frozen_acceptance_suite_blocked(self):
        self.assertBlocked(self.pre("Edit", file_path=str(self.root / "tests/acceptance/test_m1.py"),
                                    old_string="True", new_string="1"))

    def test_relative_path_and_new_file_in_acceptance_blocked(self):
        self.assertBlocked(self.pre("Write", file_path="tests/acceptance/test_new.py", content="x"))

    def test_loop_files_and_stop_blocked(self):
        for name in ("run-loop.ps1", "tools/selfcheck.ps1", "STOP", ".claude/milestones.json", "loop-config.psd1"):
            with self.subTest(name=name):
                self.assertBlocked(self.pre("Write", file_path=str(self.root / name), content="x"))

    def test_normal_file_allowed(self):
        self.assertAllowed(self.pre("Edit", file_path=str(self.root / "src.py"), old_string="1", new_string="2"))

    def test_new_skip_marker_in_test_blocked(self):
        self.assertBlocked(self.pre("Edit", file_path=str(self.root / "tests/unit/test_x.py"),
                                    old_string="def test_x():", new_string="@pytest.mark.skip\ndef test_x():"))
        self.assertBlocked(self.pre("Write", file_path=str(self.root / "tests/unit/test_x.py"),
                                    content="import pytest\ndef test_x():\n    pytest.skip('later')\n"))

    def test_existing_marker_moved_allowed(self):
        old = "@pytest.mark.xfail\ndef test_x():"
        self.assertAllowed(self.pre("Edit", file_path=str(self.root / "tests/unit/test_x.py"),
                                    old_string=old, new_string=old + "  # known"))

    def test_skip_word_outside_tests_allowed(self):
        self.assertAllowed(self.pre("Write", file_path=str(self.root / "src.py"), content="pytest.skip()\n"))

    def test_outside_repo_allowed(self):
        self.assertAllowed(self.pre("Write", file_path=str(Path(self._tmp.name) / "STOP"), content="x"))

    def test_not_a_devloop_project_allowed(self):
        (self.root / ".claude" / "milestones.json").unlink()
        self.assertAllowed(self.pre("Write", file_path=str(self.root / "run-loop.ps1"), content="x"))

    def test_unlock(self):
        res = self.run_guard("pre", {"tool_name": "Write",
                                     "tool_input": {"file_path": str(self.root / "STOP"), "content": "x"}},
                             env={"DEVLOOP_UNLOCK": "1"})
        self.assertAllowed(res)

    def test_project_config_protects_and_allows(self):
        (self.root / ".claude" / "devloop-guard.json").write_text(json.dumps(
            {"protect": ["tests/*", "tests/**"], "allow": ["tests/acceptance/test_m1.py"]}))
        self.assertBlocked(self.pre("Edit", file_path=str(self.root / "tests/unit/test_x.py"),
                                    old_string="True", new_string="1"))
        self.assertAllowed(self.pre("Edit", file_path=str(self.root / "tests/acceptance/test_m1.py"),
                                    old_string="True", new_string="1"))

    def test_broken_config_keeps_defaults(self):
        (self.root / ".claude" / "devloop-guard.json").write_text("{not json")
        self.assertBlocked(self.pre("Write", file_path=str(self.root / "STOP"), content="x"))


class PreBash(GuardCase):
    def bash(self, command: str):
        return self.pre("Bash", command=command)

    def test_reading_protected_files_allowed(self):
        self.assertAllowed(self.bash("cat run-loop.ps1 2>&1 | head"))
        self.assertAllowed(self.bash("python -m pytest -q tests/acceptance/test_m1.py"))

    def test_writing_protected_files_blocked(self):
        for cmd in ("rm STOP", "touch STOP", "echo x > tests/acceptance/test_m1.py", "echo y >> run-loop.ps1",
                    "sed -i 's/a/b/' tools/selfcheck.ps1", "cp /tmp/x .claude/milestones.json",
                    "git status && rm -f tests/acceptance/test_m1.py"):
            with self.subTest(cmd=cmd):
                self.assertBlocked(self.bash(cmd))

    def test_copy_from_protected_allowed(self):
        self.assertAllowed(self.bash("cp run-loop.ps1 /tmp/backup.ps1"))

    def test_discarding_milestones_json(self):
        self.assertBlocked(self.bash("git checkout -- .claude/milestones.json"))
        self.assertBlocked(self.bash("git restore .claude/milestones.json"))
        # whole-tree discards only matter while milestones.json has uncommitted changes
        self.assertAllowed(self.bash("git stash"))
        self.assertAllowed(self.bash("git reset --hard"))
        (self.root / ".claude" / "milestones.json").write_text('{"milestones": [], "x": 1}')
        for cmd in ("git stash", "git stash push -m x", "git reset --hard HEAD", "git checkout .", "git restore ."):
            with self.subTest(cmd=cmd):
                self.assertBlocked(self.bash(cmd))
        self.assertAllowed(self.bash("git stash list"))

    def test_push_to_main_blocked(self):
        self.assertBlocked(self.bash("git push origin main"))
        self.assertBlocked(self.bash("git push -u origin HEAD:main"))
        self.assertBlocked(self.bash("git push origin +master"))
        self.assertBlocked(self.bash("git push"))  # on main
        self.assertBlocked(self.bash("git push origin HEAD"))  # on main
        git(self.root, "checkout", "-qb", "phil/work/M1.2")
        self.assertAllowed(self.bash("git push -u origin phil/work/M1.2"))
        self.assertAllowed(self.bash("git push"))
        self.assertAllowed(self.bash("git push origin HEAD"))


class Session(GuardCase):
    def test_off_work_branch_hint(self):
        res = self.run_guard("session", {})
        self.assertAllowed(res)
        self.assertIn("Not on a work branch", res.stdout)

    def test_work_branch_shows_milestone_handoff_and_failure(self):
        git(self.root, "checkout", "-qb", "alex/work/M1.2")
        (self.root / "handoff").mkdir()
        (self.root / "handoff" / "m1_2.md").write_text("# M1.2\nNext step: parser\n")
        (self.root / ".claude" / "last_failure.md").write_text("check unit failed\n")
        res = self.run_guard("session", {})
        self.assertAllowed(res)
        self.assertIn("Milestone M1.2: Feature", res.stdout)
        self.assertIn("Next step: parser", res.stdout)
        self.assertIn("check unit failed", res.stdout)

    def test_missing_handoff_named(self):
        git(self.root, "checkout", "-qb", "alex/work/M1.2")
        self.assertIn("No handoff yet: create handoff/M1.2.md", self.run_guard("session", {}).stdout)

    def test_silent_outside_devloop(self):
        (self.root / ".claude" / "milestones.json").unlink()
        self.assertEqual(self.run_guard("session", {}).stdout, "")


class Stop(GuardCase):
    def stop(self, **extra):
        res = self.run_guard("stop", dict(extra))
        self.assertAllowed(res)
        return json.loads(res.stdout) if res.stdout.strip() else None

    def test_no_work_branch_no_block(self):
        (self.root / "src.py").write_text("x = 2\n")
        self.assertIsNone(self.stop())

    def test_changes_without_handoff_block(self):
        git(self.root, "checkout", "-qb", "alex/work/M1.2")
        (self.root / "src.py").write_text("x = 2\n")
        out = self.stop()
        self.assertEqual(out["decision"], "block")
        self.assertIn("Create handoff/M1.2.md", out["reason"])

    def test_stale_handoff_blocks_fresh_one_does_not(self):
        git(self.root, "checkout", "-qb", "alex/work/M1.2")
        (self.root / "handoff").mkdir()
        h = self.root / "handoff" / "M1.2.md"
        h.write_text("old\n")
        old = time.time() - 600
        os.utime(h, (old, old))
        (self.root / "src.py").write_text("x = 2\n")
        self.assertIn("Update handoff/M1.2.md", self.stop()["reason"])
        h.write_text("new\n")
        self.assertIsNone(self.stop())

    def test_committed_work_counts(self):
        git(self.root, "checkout", "-qb", "alex/work/M1.2")
        (self.root / "src.py").write_text("x = 3\n")
        git(self.root, "commit", "-qam", "[M1.2] step")
        self.assertEqual(self.stop()["decision"], "block")

    def test_no_changes_no_block(self):
        git(self.root, "checkout", "-qb", "alex/work/M1.2")
        self.assertIsNone(self.stop())

    def test_second_stop_passes(self):
        git(self.root, "checkout", "-qb", "alex/work/M1.2")
        (self.root / "src.py").write_text("x = 2\n")
        self.assertIsNone(self.stop(stop_hook_active=True))


class Robustness(GuardCase):
    def test_garbage_input_and_unknown_mode(self):
        for mode in ("pre", "session", "stop", "nope"):
            res = subprocess.run([sys.executable, str(GUARD), mode], input="not json", capture_output=True,
                                 text=True, cwd=self.root, timeout=30)
            self.assertEqual(res.returncode, 0, (mode, res.stderr))


if __name__ == "__main__":
    unittest.main()
