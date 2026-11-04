---
description: Claim a hub milestone and set up its branch and handoff
argument-hint: "<project> <id>"
---
Start milestone `$ARGUMENTS` on the dev_loop hub (first word = project, second = milestone id).

1. Hub tool `context` for it (leave `client` at its default). Read the briefing completely; fetch parts it moved out
   with `read_part`. Show me a short summary: goal, criteria, checks, size, model, open notes.
2. Hub tool `claim`. Keep the `session` key it returns and pass it as `session` to every later hub call on this
   milestone (`heartbeat`, `commit`, `precheck`, `submit`, `release`, `ask`). If it answers `already_claimed`,
   stop and tell me who holds it; `... in another session` means another session of mine works on it: never
   continue in parallel. Use `claim` with `takeover=true` only after I confirm that the other session stopped.
3. Local repository: if this directory is a clone of the project, fetch and create the branch the claim named
   (`<worker>/work/<id>`) from the project's default branch, or check it out if it exists (also look for
   `<worker>/park/<id>` and continue from there). If there is no local clone, work through the hub tools
   (`list_files`, `search`, `read_files`, `commit`) instead and say so.
4. If neither `handoff/<id>.md` nor `handoff/<id lower, dots as _>.md` exists, create `handoff/<id>.md` with the
   sections Done, Half done, Next step, Check results, Open decisions, and commit it with prefix `[<id>]`.
5. Tell me the plan for the first step, then start. While working: commit small steps, keep the handoff current,
   call `heartbeat` about every hour. If you need a decision of the project's owner, use the hub tool `ask`
   (never only the handoff).
