@AGENTS.md
@AGENTS.project.md

For optional multi-user DEV acceptance checks, see the [Playwright guide](docs/playwright-testing.md) and [skill](.claude/skills/playwright-browser-testing/SKILL.md).

## Session startup reminder
When a conversation starts without a named release bundle, run `scripts/team.sh release list` first; if open `draft` folders exist, ask the developer to choose one by number (`1- ...`, `2- ...`, `N- Create a new release folder`). All `release` commands are non-interactive (`--confirm-target <db_unique_name>` replaces stdin `[y/N]` prompts).
