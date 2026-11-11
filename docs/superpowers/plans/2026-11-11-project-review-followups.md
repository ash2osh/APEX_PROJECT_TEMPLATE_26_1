# Project Review Follow-ups Implementation Plan

> **For agentic workers:** One phase at a time, in the order below. Each phase stops for a main-session review before the next one starts. Do not commit, push, switch branches, open a pull request, run a migration, or connect to a database. Report the commands you ran and their results.

**Goal:** Close the 4 issues and 6 improvements found in the 2026-11-11 full-project review of the 26.1 and 26.2 templates.

**Source:** review of both templates on 2026-11-11 (static scans, doc/code cross-checks, CI logs, targeted reading; not a line-by-line read of all scripts).

**Tech stack:** Python 3.10+ standard library, unittest, Bash, PowerShell, GitHub Actions. No new runtime dependency.

**Branches:** `chore/review-followups` in the 26.1 template, cut from `feat/migration-capsule-checkpoints` (phase A edits files that branch changed). Its pull request opens after ash2osh/APEX_PROJECT_TEMPLATE_26_1#57 merges. The 26.2 port uses `chore/review-followups-262`, cut from `feat/migration-capsule-checkpoints-262`, after ash2osh/APEX_PROJECT_TEMPLATE_TEAM#89 merges.

## Global constraints

- `ruff check scripts tools tests` clean, LF line endings, `python3 scripts/pre_push_check.py --all` before any push.
- Write the failing test first where practical. Never weaken an existing safety check to make a test pass.
- `scripts/team.sh` and `scripts/team.ps1` usage text stays identical apart from the script name.
- Any module added to or removed from the capsule engine must be reflected in `WORKFLOW_ENGINE_FILES` / `ENGINE_HELPER_FILES` in `scripts/release_capsule.py`.
- Check `docs/known-limitations.md` before changing behaviour; add a row when a limit is kept on purpose.
- One file per test run: `python3 -m unittest discover -s tests -p 'test_x.py'`. Full suite: `python3 scripts/ci_run_tests.py --jobs 8`.

## Item map

| # | Item | Phase |
| --- | --- | --- |
| 1 | Production confirmations accept piped input | C |
| 2 | Graphify pipeline tests never run in CI | B |
| 3 | 26.2 parity ledger out of date | D |
| 4 | "package files" wording after capture was widened | A |
| 5 | Seven functions with no caller | A |
| 6 | No shell or PowerShell lint beyond syntax | B |
| 7 | CI cannot tell when PowerShell tests skip | B |
| 8 | `pre_push_check.py` does not name the failed step | A |
| 9 | Three very large modules | F (separate pull request) |
| 10 | Parked decisions | E |

## Phase A: small code fixes (26.1)

### A1. Wording: "package files" becomes "stored source files" (item 4)

- Files: `scripts/feature_doctor.py` (lines near 266, 275, 278, 280), `scripts/feature_cli.py` (near 61, 147, 159, 165, 169), docstring at `scripts/feature_sources.py:867`.
- Use one phrase everywhere: "stored source file(s)". Keep "package" only where the text is about packages specifically.
- Update the tests that pin these strings (`tests/test_feature_doctor*.py`, `tests/test_feature_cli*.py`, `tests/test_live_feature_release.py`) and any quote in `docs/feature-releases.md` / `docs/feature-ownership.md`.
- Add one test: a feature holding only a procedure reports "stored source file(s)" in the doctor summary and the freeze record.
- Done when: `grep -n "package file" scripts/feature_*.py` shows only package-specific text, and the feature test files pass.

### A2. Remove dead code (item 5)

- Delete, after re-checking each has no caller in `scripts/`, `tools/`, `tests/`, `*.sh`, `*.ps1`:
  - `scripts/migrate.py`: `_same_target_identity`, `_update_run_manifest`
  - `scripts/feature_manifest.py`: `_unquote_identifier`, `_static_grant_object`
  - `scripts/compare_schema.py`: `_ordinary_inventory_entries`
  - `scripts/feature_claims.py`: `holders`
  - `scripts/dev_test_evidence.py`: `generate_object_prefix`
- Remove imports that become unused (Ruff reports them).
- `migrate.py`, `feature_manifest.py` and `feature_claims.py` are in the capsule engine digest, so the engine digest changes. That is expected; say so in the pull request (a capsule frozen before the change must be frozen again).
- Done when: Ruff is clean and the full suite passes.

### A3. `pre_push_check.py` names what failed (item 8)

- File: `scripts/pre_push_check.py`. Keep `(label, ok)` pairs instead of bare booleans and end with `CHECKS FAILED: <label>; <label>` listing each failed step.
- Test in `tests/test_pre_push_check.py`: a run with one failing step prints that step's label on the last line.
- Done when: the test passes and a deliberate failure (a temp file with a syntax error) shows its label.

## Phase B: CI coverage (26.1)

### B1. Run the Graphify pipeline tests in one job (item 2)

- File: `.github/workflows/template-checks.yml`, job `offline-latest-python` only (keeps the required `offline` job stdlib-only).
- Add a step before the tests: `python3 -m pip install --disable-pip-version-check --no-input '.[graph]'`, then `python3 scripts/setup_graphify_apx.py`.
- Read `tests/test_graphify_pipeline.py` (launcher lookup near line 157) first and make sure the installed launcher is the one it finds.
- If the install or the 5 tests prove unstable on the runner, stop and report; do not add them to `tests/known_flaky.txt` without evidence.
- Update `docs/ci-checks.md`.
- Done when: that job's log shows `test_graphify_pipeline` ran 5 tests.

### B2. Fail CI when an expected tool is missing instead of skipping (item 7)

- File: `scripts/ci_run_tests.py`. New option `--forbid-skip REGEX` (also `CI_FORBID_SKIP`): after the run, exit 1 and list the tests when any skip reason matches.
- Workflow: Linux and Windows jobs pass `PowerShell Core is not installed|no PowerShell found`; the latest-Python job also passes `Graphify Python launcher is unavailable`.
- Tests in `tests/test_ci_run_tests.py`: a matching skip fails the run, a non-matching skip does not, the option is ignored when unset.
- Done when: the tests pass and a local run with a fake `PATH` without `pwsh` fails with the listed tests.

### B3. ShellCheck and PowerShell parsing (item 6)

- Linux job: `shellcheck --severity=error scripts/*.sh` (ShellCheck ships on `ubuntu-latest`). Fix what it reports at error level.
- Run `--severity=warning` once locally or in a scratch CI run, list the findings in the pull request, and fix only the ones that are real defects. Do not mass-rewrite the scripts.
- Linux and Windows jobs: a `pwsh` step that parses every `scripts/*.ps1` with `[System.Management.Automation.Language.Parser]::ParseFile` and fails on any error.
- Add both to `scripts/pre_push_check.py` when the tool is present (skip with a note when it is not), and to `docs/ci-checks.md`.
- Done when: both steps are green in CI.

## Phase C: an auto-accept flag, and prompts that need a terminal (item 1 plus the developer's request of 2026-11-11, 26.1)

The developer asked that every command with a `[y/N]` prompt take `-y` (or similar) to accept it. That flag becomes the one explicit, recorded way to run without a prompt, so a piped answer is no longer needed and is refused.

Production behaviour follows decision 1 below: `-y` alone is refused on production; `-y --confirm-target <db_unique_name>` is accepted when the name matches. `rollout`, `publish` and `deploy` gain `--confirm-target` with the same matching rule `migrate` has.

### C1. `-y` / `--yes` on every `[y/N]` prompt

The four prompts, and where the flag goes:

| Prompt | Code | Flag added to |
| --- | --- | --- |
| `Migrating to <ENV>. Proceed? [y/N]` | `scripts/migrate.py` near line 1005 | `migrate` |
| `Rehearsing against <ENV>. Proceed? [y/N]` | `scripts/migration_rehearsal.py` near line 542 | `migrate --rehearse` |
| `Continue with this rollout? [y/N]` | `scripts/rollout.py` near line 985 | `rollout` |
| `Deploying to <target>. Proceed? [y/N]` | `scripts/publish_app.sh` near 247, `scripts/publish_app.ps1` near 231 | `publish` (non-DEV) and `deploy` |

- Spelling: `-y` and `--yes` on all four. `archive-migrations --yes` and `feature clean-capsule --yes` already exist; give both the `-y` alias so the spelling is the same everywhere.
- When the flag accepts a prompt, print one line, `Confirmed by --yes; the interactive prompt was skipped.`, and record `"confirmedBy": "--yes"` in the run report or attempt evidence wherever `--confirm-target` is recorded today.
- The target summary (connection, observed identity, hashes) is still printed before the write. `-y` skips the question only; every identity, drift, receipt and digest check still runs and still refuses.
- `migrate --confirm-target <db_unique_name>` keeps working unchanged.
- Not covered by `-y`, on purpose: the typed `RECONCILE <attempt>` and `RECONCILE-RUN <run-id>` acknowledgments (they are not yes/no questions; they state that an unknown write has ended), the `Press Enter to continue the rollout...` pause of a manual step, `publish --force`, and the browser MCP choice menu.
- Wrappers: pass the flag through in `scripts/team.sh` and `scripts/team.ps1`, and add it to both usage texts (they must stay identical).
- Tests, per prompt: with `-y` the command proceeds without reading stdin and the report records it; without it the prompt is asked as today.

### C2. Prompts refuse redirected input

- New helper `scripts/terminal_confirm.py`: `stdin_is_terminal()` and one refusal message that names `--yes`. Add it to `ENGINE_HELPER_FILES`.
- Python: `_confirm_from_terminal` in `scripts/migrate.py` and `scripts/rollout.py`, `_recovery_ack_from_terminal` in `scripts/rollout.py`, `_reconcile_ack_from_terminal` in `scripts/feature_cli.py` refuse when stdin is not a terminal. The injected `confirm=` callables used by offline tests are untouched.
- Bash: the prompt in `scripts/publish_app.sh` tests `[ -t 0 ]`. PowerShell: `scripts/publish_app.ps1` tests `[Console]::IsInputRedirected`.
- The 4 offline tests and the live tests that pipe `y` switch to `-y`.
- The two typed acknowledgments have no flag, so their live scenario needs a test-only path: `TEAM_ACK_FROM_STDIN=1` allows a redirected acknowledgment, prints `acknowledgment read from redirected input (TEAM_ACK_FROM_STDIN)` and records it. Only the live module sets it.

### C3. Rules and docs

- `AGENTS.md` and `.agents/rules/agent-safety.md`: an agent passes `-y` for staging or production only when the developer asked for that run to be unattended in the conversation, the same rule `--confirm-target` has today; an agent never sets `TEAM_ACK_FROM_STDIN`.
- `README.md`, `docs/migration-rules.md`, `docs/feature-releases.md`, `docs/publish-rules.md`: document the flag, what it does not skip, and that piped answers are refused.
- `docs/known-limitations.md`: one row (a process with shell access can pass `-y`; the flag makes it explicit and recorded, not impossible).
- Done when: offline suite passes, and the live module passes in both configurations in a main-session run (four allowed connections only, see `docs/live-feature-tests.md`).

## Phase D: 26.2 port and parity (item 3)

- Port phases A to C to `chore/review-followups-262` by hand-merging; 26.2 files differ on purpose (receipts are never replaced, `migrate` has no `--confirm-target`, extra commands).
- Then bring the ledger up to date, with both checkouts on the commits that will be merged:
  - `python3 tools/template_parity.py ../APEX_PROJECT_TEMPLATE_26_1`
  - For each of the 7 unreviewed and 41 changed files, read the diff and `--mark` it `intended`, `feature` or `missed` with a reason. Anything `missed` is ported or listed in `TODO.md`.
  - Remove the 2 stale entries (`.github/workflows/database-checks.yml`, `CLAUDE.md`).
- Keep it from drifting: add a line to the 26.2 pull-request checklist in `docs/ci-checks.md` ("run the parity report; exit 0"). Optional: a non-blocking CI step that checks out the 26.1 repository and prints the report as a warning, only if that repository is readable from the 26.2 workflow without a new secret.
- Done when: the parity tool exits 0.

## Phase E: parked decisions, now decided (item 10, 26.1)

### E1. `feature capture --refresh` uses the retained baseline

- File: `scripts/feature_sources.py` (the refresh guard). When the feature file is byte-equal (after the existing normalization) to the retained DEV baseline of its last capture, the file has no local edits, so the refresh replaces it with the current DEV source without `--discard-unapplied`.
- A file that differs from its retained baseline keeps today's rule exactly: lines DEV does not have stop the refresh unless `--discard-unapplied` is given. A missing or unreadable baseline also keeps today's rule.
- Tests in the feature-sources test file: unedited file refreshes; edited file still refused; missing baseline still refused. Update the live scenario `test_standalone_procedure_and_function_capture_refresh_move_and_doctor_drift`.
- Docs: `docs/feature-releases.md`; remove the entry from `TODO.md`.

### E2. Prepare refuses a replaced specification whose body is outside the release

- File: `scripts/feature_release.py`, in `prepare_target` beside `_refuse_disabled_triggers`. When a `PACKAGE` or `TYPE` specification will be replaced on the target (`targetExists` and `noOp` is false), the target has a body for it, and that body is not a unit of the same checkpoint, refuse with a message that names the unit and the fix: `feature capture --package <NAME>` (or `--type`) so the body ships with its specification.
- The body's existence is read with the existing read-only target catalog query path (`ALL_OBJECTS`); no new connection, no write.
- Tests in `tests/test_feature_prepare.py`: refused when the body exists on the target and is not in the release; allowed when the body is in the release; allowed when the target has no body; allowed when the specification is a no-op.
- Docs: `docs/feature-releases.md`; remove the entry from `TODO.md`.

### E3. `clean-capsule` after a reconciled run

- File: `scripts/release_state.py`, `_cleanup_report`. The blocker "a rollout for this payload was closed by reconciliation, not by verification" applies only to a reconciled run that has no later `verified` run of the same payload in the same environment. Every other blocker is unchanged, including the required complete verified production rollout and `_verify_local_completion`.
- Tests: reconciled staging run followed by a verified staging run and a verified production run is eligible; a reconciled run with no later verified run in its environment still blocks.
- Docs: `docs/feature-releases.md` (the cleanup section near "capsule ineligible for cleanup").

## Phase F: split the large modules (item 9, separate pull request, after everything above is merged)

- Order: `scripts/rollout.py` first (move the capsule path, `_run_capsule_rollout` and its helpers, into `scripts/rollout_capsule.py`), then `scripts/release_state.py`, then `scripts/baseline.py`.
- Moves only: no behaviour, message or signature change; `rollout.py` re-exports the moved names that tests import.
- Each new module goes into `WORKFLOW_ENGINE_FILES` / `ENGINE_HELPER_FILES`; the engine digest changes once per split.
- One module per pull request, each ported to 26.2 and marked in the parity ledger.
- Done when: the full suite and both live configurations pass with no test edited except import paths.

## Decisions (made by the developer on 2026-11-11: the recommended option each time; do not reopen)

1. **`-y` on production needs the target name.** `-y` accepts DEV and staging prompts. On production `-y` alone is refused with "production also needs --confirm-target <db_unique_name>"; `-y --confirm-target NAME` runs when NAME equals the observed `db_unique_name`. `rollout`, `publish` and `deploy` gain `--confirm-target`. A piped answer is refused; the flag replaces it.
2. **`--refresh` compares with the retained baseline** (phase E1).
3. **Prepare refuses a replaced specification whose existing body is not in the release** (phase E2).
4. **`clean-capsule` is allowed when a later verified run supersedes the reconciled one** (phase E3).

## Not verified by this plan

- `team.ps1` on native Windows paths (CI covers the offline tests only).
- ShellCheck findings are unknown until B3 runs; the count may change the size of that task.
