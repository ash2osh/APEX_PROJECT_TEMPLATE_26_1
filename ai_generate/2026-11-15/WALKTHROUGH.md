# Walkthrough 2026-11-15

## Pull request 69: unattended pauses and mcp setup

Pull request 69 (merge `6c3158e`, commits `331b111`, `2ccc4e6` and `245aa43`) let unattended runs get past the human stops that had no flag. An unattended rollout stopped at its first `pause` step, and `mcp setup` waited for a menu answer. The typed `RECONCILE` acknowledgments had no flag either, so an agent could not finish a reconcile. The records of these acknowledgments now show how each one was given.

- `-y` / `--yes` on a rollout `pause` step passes it without waiting. The report records that no person confirmed the manual step. `--confirm-target` alone does not accept a pause.
- `mcp setup --yes` takes the default choice, `none`. `--choice` wins when both are given. The usage text in `scripts/team.sh` and `scripts/team.ps1` lists the flag.
- `-y` / `--yes` replaces the typed acknowledgments of `reconcile-migration` (`RECONCILE-MIGRATION <attempt-id>`), `feature reconcile-run` (`RECONCILE-RUN <run-id>`) and `rollout --prepare --recover` (`RECONCILE <attempt>`). Every check still runs. The record stores `acknowledgedBy` as `--yes` or `terminal`, so a reviewer can see which one was used. Records without the key stay valid and read as `terminal`.
- Piped or redirected input without `--yes` is still refused. `--yes` alone on production is still refused for a run. Recovery preparation is the one exception: it needs no `--confirm-target`.
- The rule "an agent never types the acknowledgment" is withdrawn in `AGENTS.md`, `.agents/rules/agent-safety.md`, `README.md` and the feature, migration and live-test docs. It is replaced by the rule that an agent may pass `--yes` and that the evidence must come from checks the agent ran. `docs/known-limitations.md` now lists `--yes` for these commands as a deliberate, recorded flag.
- Windows: `sys.stdin.isatty()` reports `True` for the NUL device. `mcp setup` then reached `input()` and failed with `EOFError`. The prompt now turns that into the refusal `choose --choice chrome|firefox|both|none when stdin is not interactive`, with no writes (`245aa43`).

Files changed in the pull request (28 files, 629 insertions, 91 deletions):

| Area | Files |
| --- | --- |
| Rollout pause and recovery | `scripts/rollout.py`, `scripts/rollout_capsule.py`, `scripts/feature_release.py`, `scripts/release_state.py`, `scripts/release_recovery.py` |
| Acknowledgments | `scripts/feature_cli.py`, `scripts/migration_resolution.py`, `scripts/terminal_confirm.py` |
| mcp setup | `scripts/browser_mcp.py`, `scripts/team.sh`, `scripts/team.ps1`, `docs/browser-mcp.md` |
| Rules and docs | `AGENTS.md`, `README.md`, `.agents/rules/agent-safety.md`, `docs/feature-releases.md`, `docs/migration-rules.md`, `docs/migration-attempt-resolution.md`, `docs/live-feature-tests.md`, `docs/known-limitations.md` |
| Tests | `tests/test_rollout.py`, `tests/test_feature_rollout.py`, `tests/test_feature_cli.py`, `tests/test_migration_resolution.py`, `tests/test_release_state.py`, `tests/test_feature_prepare.py`, `tests/test_browser_mcp.py`, `tests/test_documentation_contract.py` |

Commands and results for this entry:

- `git log --oneline 9b7281a..6c3158e`: lists the four commits of the pull request. Read only.
- `git diff --stat 9b7281a..6c3158e` and `git show` on the three commits: read the diffs used above. Read only.
- Not run for this entry: any test, check, database command or live reconcile. The pull request's own check results are not restated here.

Not verified: that the `--yes` flags work against a live database or a Windows terminal. The `EOFError` fix was written for Windows; its cross-platform test patches `isatty` and `input`.

Open: nothing outstanding from this pull request. Rollout receipts are never replaced, which the 2026-11-16 walkthrough covers.
