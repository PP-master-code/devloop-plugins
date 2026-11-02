---
description: Hand in the current milestone to the hub (checks run on the hub's server)
argument-hint: "[--precheck]"
---
Submit the milestone of the current work branch (`<worker>/work/<id>`) to the dev_loop hub.
With `--precheck` in "$ARGUMENTS": run the hub's checks only, do not merge.

1. Find project and id from the branch name and the hub tool `status`. If this is not a work branch, stop.
2. The handoff (`handoff/<id>.md` or the dev_loop form) must be current: done, open points, check results. Update
   and commit it if not.
3. Run the milestone's checks from `.claude/milestones.json` locally where you can (commands with `{python}`,
   `{godot}` etc.: substitute what is installed here; skip only what cannot run here and say which). Fix failures
   first.
4. Commit everything and push the branch (git remote or hub gateway). `.claude/milestones.json` must not be
   changed on the branch: submit refuses it.
5. Hub tool `precheck` (with `--precheck`) or `submit`. If it answers `running`, wait about a minute and ask
   `check_result`; repeat until there is a result, at most 15 minutes, never call submit twice.
6. Report the result: merged, review pull request (`url`), or rejected with the failing check and its log excerpt.
   On rejection, fix and offer to submit again.
7. After a merge or a review PR: estimate the tokens this session spent on the milestone and call `report_usage`
   (tell me the number you report).
