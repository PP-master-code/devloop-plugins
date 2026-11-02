"""Tests for plugins/gdscript-lint/hooks/lint.py with the real gdtoolkit 4 (CI installs it)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

LINT = Path(__file__).resolve().parents[1] / "plugins" / "gdscript-lint" / "hooks" / "lint.py"

CLEAN = "extends Node\n\n\nfunc good_name() -> void:\n\tpass\n"
LEGACY = "extends Node\n\n\nfunc OldName() -> void:\n\tpass\n"


class LintHook(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "game"
        self.root.mkdir()
        (self.root / "project.godot").write_text("config_version=5\n")
        self.session = f"test-{os.getpid()}-{id(self)}"

    def tearDown(self):
        self._tmp.cleanup()
        for p in Path(tempfile.gettempdir()).glob(f"gdscript-lint-missing-{self.session}*"):
            p.unlink()

    def hook(self, tool: str, file: Path, env: dict | None = None, **tool_input):
        event = {"tool_name": tool, "tool_input": {"file_path": str(file), **tool_input}, "cwd": str(self.root),
                 "session_id": self.session}
        e = dict(os.environ)
        e.pop("GDSCRIPT_LINT", None)
        e.update(env or {})
        return subprocess.run([sys.executable, str(LINT)],
                              input=json.dumps(event), capture_output=True, text=True, env=e, timeout=120)

    def write(self, name: str, text: str) -> Path:
        f = self.root / name
        f.write_text(text)
        return f

    def test_clean_file_passes(self):
        f = self.write("a.gd", CLEAN)
        res = self.hook("Write", f, content=CLEAN)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_bad_name_reported(self):
        f = self.write("a.gd", LEGACY)
        res = self.hook("Write", f, content=LEGACY)
        self.assertEqual(res.returncode, 2)
        self.assertIn("function-name", res.stderr)

    def test_only_changed_lines_reported(self):
        text = LEGACY + "\n\nfunc new_one() -> void:\n\tpass\n"
        f = self.write("a.gd", text)
        res = self.hook("Edit", f, old_string="x", new_string="func new_one() -> void:\n\tpass")
        self.assertEqual(res.returncode, 0, res.stderr)  # OldName on line 4 is old, not this edit's
        text2 = LEGACY + "\n\nfunc NewOne() -> void:\n\tpass\n"
        f.write_text(text2)
        res = self.hook("Edit", f, old_string="x", new_string="func NewOne() -> void:\n\tpass")
        self.assertEqual(res.returncode, 2)
        self.assertIn("NewOne", res.stderr)
        self.assertNotIn("OldName", res.stderr)

    def test_parse_error_always_reported(self):
        bad = "extends Node\nfunc broken(:\n"
        f = self.write("a.gd", bad)
        res = self.hook("Edit", f, old_string="x", new_string="extends Node")
        self.assertEqual(res.returncode, 2)
        self.assertIn("gdlint", res.stderr)

    def test_format_only_when_enabled(self):
        messy = "extends Node\nvar  x=1\n"
        f = self.write("a.gd", messy)
        self.assertEqual(self.hook("Write", f, content=messy).returncode, 0)
        (self.root / ".claude").mkdir()
        (self.root / ".claude" / "gdscript-lint.json").write_text('{"format": true}')
        res = self.hook("Write", f, content=messy)
        self.assertEqual(res.returncode, 2)
        self.assertIn("gdformat", res.stderr)

    def test_other_files_and_tools_ignored(self):
        f = self.write("a.py", "x=1\n")
        self.assertEqual(self.hook("Write", f, content="x").returncode, 0)
        g = self.write("a.gd", LEGACY)
        self.assertEqual(self.hook("Read", g).returncode, 0)

    def test_switched_off(self):
        f = self.write("a.gd", LEGACY)
        self.assertEqual(self.hook("Write", f, env={"GDSCRIPT_LINT": "0"}, content=LEGACY).returncode, 0)

    def test_missing_gdtoolkit_hint_once(self):
        f = self.write("a.gd", LEGACY)
        empty = tempfile.mkdtemp()
        try:
            # without site-packages (-S -I) and with an empty PATH, neither gdlint nor the gdtoolkit module is found
            event = {"tool_name": "Write", "tool_input": {"file_path": str(f)}, "cwd": str(self.root),
                     "session_id": self.session}
            run = lambda: subprocess.run([sys.executable, "-S", "-I", str(LINT)], input=json.dumps(event),
                                         capture_output=True, text=True, env={"PATH": empty, **{k: os.environ[k] for k in ("SYSTEMROOT", "TEMP", "TMP") if k in os.environ}}, timeout=60)
            first, second = run(), run()
            self.assertEqual(first.returncode, 2)
            self.assertIn("gdtoolkit is not installed", first.stderr)
            self.assertEqual(second.returncode, 0)
        finally:
            os.rmdir(empty)

    def test_garbage_input(self):
        res = subprocess.run([sys.executable, str(LINT)], input="nope", capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
