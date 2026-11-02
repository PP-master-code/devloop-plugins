---
description: Show my claims, open notes and what the dev loops are doing
argument-hint: "[project]"
---
Call the dev_loop hub tools `status` (with `project` = "$ARGUMENTS" if given) and `loops`.
Show compactly, in this order:
1. Open notes for me (to-dos, questions waiting for my answer, stall reports) with what each asks.
2. My claims: project, id, since when, last heartbeat, `waiting_for`, running checks.
3. Milestones in review (`review_url`).
4. Loops: which project the server's loop works for now, state, the weekly limit and the `hint`.
Then say in one sentence what I should do next.
