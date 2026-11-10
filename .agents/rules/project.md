---
trigger: always_on
description: Use the browser MCP selected for this checkout (scripts/team.sh mcp status); the Chrome daemon is a fallback only.
---

<!-- Project-specific agent rules. The template upgrade never overwrites this file. -->
# Project browser access

- Before browser work, run `scripts/team.sh mcp status` and follow [the Browser MCP selection guide](../../docs/browser-mcp.md) and the skill for the selected browser: [the Chrome DevTools MCP skill](../skills/chrome-devtools-mcp/SKILL.md) or the [Firefox DevTools MCP skill](../skills/firefox-devtools-mcp/SKILL.md).
- With Chrome selected, use the direct Chrome DevTools MCP and do not start or call the Chrome daemon in the same session. Never call another browser MCP connection or attach directly to Chrome as a workaround.
- The Chrome daemon ([daemon guide](../../docs/CHROME_DEVTOOLS_MCP.md)) is a fallback. Use it only when Chrome is not selected, the task asks for Chrome browser work, and startup is authorized with user consent. Then route calls through `python3 tools/chrome_devtools_client.py <tool> [json_args]`. The client does not start a daemon. If the daemon is unavailable, report that and ask the user to start it.
- Treat browser actions as real app interactions. Follow `AGENTS.md` and shared APEX workflow rules before actions that write app data or Builder state.
