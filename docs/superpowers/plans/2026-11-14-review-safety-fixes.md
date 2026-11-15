# Review Safety Fixes Implementation Plan

> **For agentic workers:** The user selected an AGY CLI implementer and a separate Codex review. Repository workflow-pack selection is `none`; do not install or enable one. Use the task checkboxes as tracking.

**Goal:** Fix the eight verified review findings at `aa9462e` without weakening the existing publication, migration, and identity guards.

**Architecture:** Bind each approved rollout target to its actual writer, fail closed when publication lifecycle verification is unavailable, evaluate migration evidence per environment and target, and make baseline SQL retargeting lexical and conservative. Remove the acknowledgement bypass and align the public-command documentation with the wrappers.

**Tech stack:** Python, Bash, PowerShell, unittest, Oracle SQL/APEX metadata. The review report in the parent conversation is the specification; the concrete reproductions and acceptance criteria below are authoritative for this handoff.

## Global constraints

- Work only in this checkout. Do not connect to a database, container, SQLcl saved connection, or live target; do not print secrets.
- Read `AGENTS.md`, `AGENTS.project.md`, `.agents/rules/project.md`, `.agents/rules/agent-safety.md`, and `docs/known-limitations.md`. Do not fix accepted limitations unless the requested issue demonstrably exceeds them.
- No commits, pushes, PRs, remote actions, changes to `main`, or separate branches; Codex owns review and delivery.
- Agent never types a real `RECONCILE-MIGRATION` or `RECONCILE-RUN` acknowledgement, and never sets `TEAM_ACK_FROM_STDIN`. Tests must use in-process mocks or synthetic terminal fixtures, not a real acknowledgement or database.
- Keep existing documented production and DEV safeguards and Bash/PowerShell parity. Never relax assertions, fake test results, skip failing tests, or change known-flaky lists to obtain a pass.
- No new deployment or DB operation; generated SQL may be examined through offline tests only. Explain any uncertainty rather than claiming a live check passed.
- Use focused tests first. Leave the complete implementation and test evidence for Codex to review. Prefer preserving existing public APIs and supported behavior; refuse unsafe or unparseable input rather than guessing.

## Review focus

- Alias or service switches between approval, step preflight, and writer session; multi-step and capsule paths.
- A valid receipt and an unresolved attempt for different environments, and multiple attempts in one environment.
- Missing, incomplete, or failing lifecycle helpers in both entry points.
- SQL q-quoted literals, embedded apostrophes, schema-looking literal text, escaped identifiers, comments, and unsupported DDL.
- Target schema differs from source, including table defaults, view references, bitmap indexes, and unsupported metadata forms.

## Task 1: Bind rollout confirmation to writes

**Files:** `scripts/rollout.py`, `scripts/rollout_capsule.py`, relevant migration helpers and `tests/test_rollout*.py`, `tests/test_release_capsule.py`.

- [x] Add offline regressions for legacy and capsule production rollouts where approval observes `DB_A` and a later preflight or actual writer observes `DB_B` under the same alias/user. SQL-script, ORDS, migration, and app-deploy paths must refuse before the first payload statement. Cover matching identities, multiple targets and missing identity too.
- [x] Ensure the production name explicitly confirmed at the manifest gate is compared with each actual step's independently observed identity and ultimately in its writer session before executing a payload. Preserve existing stronger complete-identity checks and make the migration child receive/revalidate the approved name or complete approved identity without creating a second misleading confirmation. Do not silently convert a human approval to a different target.
- [x] Run the relevant focused rollout and identity tests. Record actual results.

## Task 2: Archive per-environment unresolved evidence

**Files:** `scripts/migration_archive.py`, `scripts/migration_revision.py` if needed, `tests/test_migration_archive.py`, relevant archive documentation.

- [x] Add a fixture with a validated DEV receipt and a pending STAGING attempt; default archive must refuse and make no changes. Cover a separate PROD attempt, same-environment matching verified receipt, unresolved and malformed/unknown evidence, and `--preserve-unresolved` retaining the folder and unresolved evidence at its archive destination.
- [x] Match receipts and terminal attempts to their own environment and target identity. A verified result for one target must never resolve or hide a different target's pending/unknown attempt. Preserve justified same-attempt receipt handling and the existing explicit override semantics.
- [x] Run archive, resolution, attempt and revision focused tests.

## Task 3: Require lifecycle verification

**Files:** `scripts/publish_app.sh`, `scripts/publish_app.ps1`, `tests/test_publish_lifecycle_gate.py`, `tests/test_publish_cli.py`, `tests/test_publication_identity.py`.

- [x] Add both-shell regressions: missing either lifecycle helper refuses before any import and cannot advance a DEV baseline; failing capture or verification refuses and keeps appropriate recovery evidence. Test staging, DEV and the promotion path using fake SQLcl only.
- [x] Make both helpers mandatory for an actual import; never bypass lifecycle capture, automation restoration, identity pinning or post-verification merely because files are absent. Keep read-only `--describe` and documented manual paths usable as appropriate, and preserve equivalent errors/exit codes.
- [x] Replace success fixtures that omit required helpers with realistic fake lifecycle fixtures; do not weaken their assertions. Run publication and lifecycle tests.

## Task 4: Baseline SQL mapping and quoting

**Files:** `scripts/baseline_bundles.py`, `scripts/baseline_sql.py` and focused baseline tests/documentation as needed.

- [x] Test a new target table whose default uses `"DEV"."SEQ".NEXTVAL`, a view referencing `"DEV"."CUSTOMERS"`, and `CREATE BITMAP INDEX "DEV"."IX" ON "DEV"."T"`. Each generated statement must address the selected target schema or generation must refuse with an actionable review message. No executable source-owner reference may leak silently.
- [x] Test an ALTER CHECK containing `q'[it's DEV.X]'`, paired and unpaired q delimiters, doubled quotes, comments, quoted identifiers and escaped identifier quotes. Literal and comment bytes must remain unchanged while actual schema identifiers are handled safely; unsupported syntax must fail closed.
- [x] Implement one lexical, quote-aware mapping strategy shared by table statements, indexes and views, or conservatively reject forms that cannot be mapped without changing semantics. Preserve external-schema references and exact stored-source contracts; do not replace text blindly inside PL/SQL literals or comments. Ensure relevant checks detect mismapped output where possible.
- [x] Run the baseline and SQL-quoting test modules using fake fixtures only.

## Task 5: Make acknowledgments terminal-only

**Files:** `scripts/terminal_confirm.py`, acknowledgment consumers, `tests/test_terminal_confirm.py` and relevant test/live-test documentation.

- [x] Add tests proving redirected input is refused for every acknowledgement even if `TEAM_ACK_FROM_STDIN` is present, while synthetic terminal input works. Ensure yes/no flags do not substitute for acknowledgments.
- [x] Remove the environment-variable bypass in production code and update tests/docs. If opt-in live tests need a terminal, adapt their harness to use a real pseudo-terminal or document a manual-only limitation; do not run live tests, and do not leave another environment-variable bypass.
- [x] Run terminal confirmation, migration resolution and feature recovery focused tests.

## Task 6: Public command documentation

**Files:** `README.md`, `docs/publish-rules.md`, `docs/GETTING_STARTED.md`, documentation contract tests.

- [x] Make the public `team.sh`/`team.ps1` contract explicit: `publish` targets DEV; `deploy` targets staging or production. Clarify any internal helper usage and make confirmation flags accurate. Check the reviewed docs against `team.sh --help` and the real parsers.
- [x] Add or update a documentation contract test for this distinction and run it.

## Handoff verification

- [x] Run focused tests and `python3 scripts/pre_push_check.py --all`; report exit statuses and missing tools. Set an external Python cache path if necessary.
- [x] Report changed files, tests and known gaps. Do not connect to live systems, commit, push or open a PR. Codex will independently review, run the required pre-push check, commit, push and open the PR.
