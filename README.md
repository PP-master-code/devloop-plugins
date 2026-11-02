# devloop-plugins

Claude Code plugins for working with the dev_loop hub (`hub.p2-software.de`).

## Installation

In Claude Code:

```
/plugin marketplace add PP-master-code/devloop-plugins
/plugin install devloop-hub@devloop
```

Then sign in to the hub once: `/mcp` → `devloop` → *Authenticate* (hub token or invitation code, as with the
claude.ai connector). If you already added the hub by hand (`claude mcp add ... devloop`), remove that entry
(`claude mcp remove devloop`), otherwise you have it twice.

Updates: `/plugin marketplace update devloop`.

## devloop-hub

| Part | What it does |
| --- | --- |
| `/hub-next [project]` | Finds a milestone you may take (`next`), shows size and model, starts it on request. |
| `/hub-start <project> <id>` | Briefing (`context`), `claim`, work branch `<worker>/work/<id>`, handoff file. |
| `/hub-submit [--precheck]` | Handoff, local checks, push, `submit` or `precheck`, waits via `check_result`, `report_usage`. |
| `/hub-park` | Handoff, push, `release` (work stays as `<worker>/park/<id>`). |
| `/hub-status [project]` | Notes, claims, reviews and the dev loops (`status`, `loops`). |
| `/hub-usage` | Reports this session's tokens (`report_usage`). |
| Guard (PreToolUse) | In dev_loop projects (`.claude/milestones.json` present) blocks: edits to `tests/acceptance/`, loop scripts (`run-loop.ps1`, `check-runner.ps1`, `loop-supervisor.ps1`, `install-autostart.ps1`, `loop-config.psd1`, `tools/selfcheck.ps1`), `STOP` and `.claude/milestones.json`; new `skip`/`xfail` markers in tests; `git stash`/`reset --hard`/`checkout .` while `milestones.json` has uncommitted changes; pushes to `main`/`master`. |
| SessionStart | On a work branch: loads the milestone, its handoff and `.claude/last_failure.md` into the session. |
| Stop | On a work branch: asks once to update the handoff when files changed after it was last written. |

The hub's own reference for AIs is its tool `guide`; the commands follow it.

### Project settings

A project can extend the guard in `.claude/devloop-guard.json`:

```json
{"protect": ["tests/*", "tests/**"], "allow": ["tests/acceptance/README.md"]}
```

Projects where each milestone writes its own check suite (e.g. `tools/checks/m3.gd`) protect only the suites of
finished milestones: `{"done_suite": "tools/checks/{id}.gd"}` (`{id}` = milestone id in lower case, dots as
underscores, as `FrozenSuitePath` in the loop). The current milestone's suite stays writable.

`DEVLOOP_UNLOCK=1` in the environment switches the guard and the stop reminder off for that session (for the
project owner planning milestones). The guard is a guard rail, not security: the hub checks every submit itself.

### Requirements

Claude Code, git, Python 3.9+ (`python3`, `python` or `py`; standard library only). On Windows the hooks run in
Git Bash, which Claude Code uses anyway. Without Python the hooks stay off and the commands still work.

## gdscript-lint

```
/plugin install gdscript-lint@devloop
pip install "gdtoolkit==4.*"
```

After every edit of a `.gd` file Claude makes, the hook runs `gdlint` on that file and hands findings on the lines
the edit wrote straight back to Claude (old problems elsewhere stay quiet; parse errors always show). `/gdlint-init`
sets up `gdlintrc` to fit an existing project. Settings in `.claude/gdscript-lint.json`:

```json
{"lint": true, "format": false, "godot_check": false}
```

`format` adds `gdformat --check` (whole file; off by default so files in another style are not reformatted),
`godot_check` runs `$GODOT_BIN --headless --check-only -s <file>` (off by default: `class_name` and autoload
references give false errors). `GDSCRIPT_LINT=0` turns the hook off. Without gdtoolkit the hook says so once per
session and then stays quiet.

## Development

```
pip install "gdtoolkit==4.*"
python -m unittest -v tests.test_guard tests.test_gdlint
claude plugin validate plugins/devloop-hub
claude plugin validate plugins/gdscript-lint
```

Nothing in this repository may contain secrets, server addresses other than the hub's public URL, or names of
private skills.
