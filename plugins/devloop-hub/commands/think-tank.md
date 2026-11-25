---
description: Have an idea criticised by several opposing AI roles (think tank on the dev_loop hub)
argument-hint: "[panel: standard|spiel|technik|geschaeft] [kurz] <idea>"
---
Run a think tank on this idea: "$ARGUMENTS". Use the dev_loop hub's MCP tools (server `devloop`; if you have the hub
connected under another name, use that). The roles run as subagents on my own account; the hub only hands out the
roles and keeps the result and my rating.

1. Work out the panel (`standard` default, `spiel` for a game idea or mechanic, `technik` for architecture or tools,
   `geschaeft` for product or market) and the depth (`kurz` if I wrote it, else `voll`). If the idea is too vague for
   anyone to judge, ask me one question first. Tell me once roughly what it costs (full run with five roles about
   60-150k tokens, `kurz` about half) and that topic and result are kept on the hub to improve the roles (I can
   say "nur Bewertung" for `share="rating"`).
2. Call `think_tank(topic, panel, depth)` with the idea plus what you know of its context (project, engine, team,
   budget). Follow the `procedure` it returns exactly: briefing, then round 1 with one subagent per role in parallel
   (Agent tool, `model` = the role's model, each sees only the briefing, its role prompt and the format), then
   round 2 the same way with all round-1 statements added (not with `kurz`), then your own conclusion as moderator.
   Subagents only read; they change no files.
3. Show me the conclusion (recommendation, weighted score, consensus, disputes, top risks, improvements, open
   questions, next steps). The single statements only if I ask.
4. `think_tank_save(session, result, statements, mode="subagents")`. Then ask me: how helpful was it (1-5), which role
   helped most, which not at all. Save my answer with `think_tank_save(session, rating, feedback, role_feedback)`.
