---
description: Set up gdlintrc for this Godot project so the gdscript-lint hook fits its code
---
Set up the GDScript lint rules for this project (gdtoolkit 4, used by the gdscript-lint hook).

1. Check that `gdlint` and `gdformat` are installed (`gdlint --version`); if not, tell me to run
   `pip install "gdtoolkit==4.*"` and stop.
2. If no `gdlintrc` or `.gdlintrc` exists in the project root, create one with `gdlint -d`.
3. Run `gdlint` over all `.gd` files of the project (skip `addons/` and `.godot/`) and `gdformat --check` on them.
   Summarize: number of problems per rule, and how many files gdformat would change.
4. Propose settings that keep the useful rules and fit the existing code: raise limits that the code clearly works
   with (e.g. `max-line-length`, `max-file-lines`, `function-arguments-number`), add `addons` and generated folders to
   `excluded_directories`, and disable rules only where the project deliberately differs. If gdformat would change
   most files, suggest `{"format": false}` in `.claude/gdscript-lint.json` instead of reformatting everything.
   Follow the project's CLAUDE.md and its GDScript conventions if it names any.
5. Show me the proposal; write `gdlintrc` (and `.claude/gdscript-lint.json` if needed) only after I agree. Never
   reformat or change `.gd` files in this command.
