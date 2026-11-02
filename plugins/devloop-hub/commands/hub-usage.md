---
description: Report this session's token use for a milestone to the hub
argument-hint: "[project id tokens]"
---
Report token use to the dev_loop hub with the tool `report_usage`.
If "$ARGUMENTS" gives project, id and tokens, use them. Otherwise take project and id from the current work branch
and estimate the tokens this session spent on the milestone (the client's usage display if you can see it, else a
rough estimate from the length of this session). Tell me the number before you report it, and report once per
session and milestone.
