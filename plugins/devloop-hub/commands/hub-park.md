---
description: Stop work on the current milestone and park it for later
---
Park the milestone of the current work branch on the dev_loop hub.

1. Update the handoff so the next session (or another worker) can continue without asking: done, half done, the
   exact next step, check results, open decisions. Commit it with everything else and push the branch.
2. Hub tool `release` for it. The hub keeps the work as `<worker>/park/<id>`.
3. Estimate the tokens spent so far and call `report_usage`.
4. Tell me what was parked and where the next session starts.

Pass the `session` key from `claim` (or from `/hub-start` in this conversation) to every hub call on the milestone.
If the hub answers `session_required` (a new conversation) or `other_session`, stop and ask me whether another
session still works on it; only if I confirm it stopped, call `claim` with `takeover=true` and use the new key.
