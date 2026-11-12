# Migration Attempt Resolution Implementation Plan

> **For agentic workers:** One phase at a time, in the order below. Each phase stops for a main-session review before the next one starts. Do not commit, push, switch branches, open a pull request, run a migration, or connect to a database. Fixtures only. Report the commands you ran and their results.

**Goal:** A dated migration folder whose apply failed, or whose result is unknown, can be resolved by its owner with evidence, and then archived, without ever being called verified and without editing the folder, its receipts or its earlier evidence.

**Problem, as observed in a downstream project (names left out on purpose):** a revision whose apply failed stays in the active tree with a `pending` attempt event and no receipt, even after a later revision of the same family is verified. `archive-migrations --all` for that schema exits 2 and moves nothing. The only way out is `--allow-unverified-attempts`, which records the attempt as "accepted" without anyone stating what happened on the target.

**Tech stack:** Python 3.10+ standard library, unittest with the existing fixtures, Bash, PowerShell. No new dependency. No database call anywhere in this work.

**Branch:** `feat/migration-attempt-resolution` in the 26.1 template, from current `main`. The 26.2 port follows as its own branch (phase 5).

## Current behaviour (verified at `9802cc5`)

1. `scripts/migrate.py` writes an attempt event at three points only: `pending` before the write (line 1039), `apply-not-started` when no write happened (1096), `verified` after a verified receipt (1209). The failure states `apply-failed-or-unknown` (1061, 1116, 1125) and `committed-verification-failed` (1159) go to the run record and the run manifest under `scratch/`. The event chain stays `pending`.
2. `scripts/migration_attempts.py`: `EVENT_STATES = {"pending", "apply-not-started", "verified"}` (line 30). `validate_attempt_event` requires the exact schema-1 field set and allows evidence only on `apply-not-started`. `reduce_attempt_events` allows one pending-to-terminal transition per attempt and reports `locked` when the last state is `pending` or `verified`.
3. Attempt events are not in Git: `.gitignore` has `migrations/**/attempt-event.*.json`, and `scratch/` is ignored too. Every piece of attempt evidence is local to one checkout. Only `status.<env>.json` receipts are committed.
4. `scripts/migration_manifest.py` (lines 600 to 613) accepts only SQL steps, `checks.json`, `status.<env>.json` and attempt-event files in a folder.
5. Readers of attempt state: `scripts/migration_revision.py` (`inspect_migration_lock`, line 189; `attempt_record_is_locked`, line 61), `scripts/migration_manifest.py` (595), `scripts/migrate.py` (replay refusals, 402 to 473), `scripts/migration_archive.py` (`_folder_evidence`, 158 to 197), `scripts/dev_test_core_migrations.py` (819, 879, 1043) and `scripts/rollout_capsule.py` (46, 66; capsule recovery).
6. `scripts/migration_archive.py`: an attempt with no verified receipt is refused unless `--allow-unverified-attempts`, which records `attempt-without-verified-receipt (accepted)`. `build_archive_plan` builds one plan, so the first refusal aborts `--all`. `_validate_prefix_selection` (line 200) requires the contiguous low prefix of a family or the whole family.
7. About ten refusals in `migrate.py` say "reconcile", and no command does it. `docs/TROUBLESHOOTING.md` (line 94) says to inspect the database and fix forward with a new revision; the old folder then stays locked.

## Design

### D1. A committed resolution record

Reconciling writes two things:

- A new attempt event that closes the chain (local, ignored by Git, as events are today).
- A committed sidecar in the folder, `resolution.<env>.json`, beside `status.<env>.json`. It is what another checkout, `archive-migrations` and a later reader see.

`resolution.<env>.json`, schema version 1, exact field set:

| Field | Meaning |
| --- | --- |
| `schemaVersion` | `1` |
| `environment` | `dev`, `staging` or `prod`; must equal the file name |
| `outcome` | `failed-no-target-effect`, `failed-target-effect-unknown` or `superseded` |
| `attemptId`, `runId` | the attempt it closes; `attemptId` is `null` in the scratch-only case |
| `payloadDigest`, `checksSha256` | of the folder, as the attempt recorded them |
| `target` | the attempt's target binding (`environment`, `connection`, `expected_user`, `current_schema`) |
| `evidence` | `{ "path": <repository-relative file>, "sha256": <digest> }` |
| `supersededBy` | only for `superseded`: `{ "folder": <name>, "receiptSha256": <digest of its status.<env>.json> }` |
| `recordedAt` | UTC timestamp |

Rules:

- The payload digest covers SQL steps and `checks.json` only, so adding the sidecar does not change the folder's identity, exactly as a receipt does not.
- A folder never has both `status.<env>.json` (verified) and `resolution.<env>.json` for the same environment. Reconcile refuses a target that has a verified receipt; `migrate` refuses to write a receipt where a resolution exists.
- The file is written once, with a no-overwrite install. A second reconcile for the same environment is refused.
- The evidence file must be a regular file inside the repository, outside `migrations/` and `scratch/`, not a symbolic link. The record stores its path and digest; the tool does not copy it. Docs say: no credentials, no personal data, sanitized database output only.

### D2. Attempt event states

`EVENT_STATES` gains the three outcomes as terminal states with `writeAttempted=true`. Each carries exactly one evidence item: `{ "kind": "owner-resolution", "path": ..., "sha256": ... }`. `pending`, `apply-not-started` and `verified` keep their meaning and their validation.

`reduce_attempt_events`: a chain is still one `pending` followed by at most one terminal state. The three new terminal states report the attempt as `resolved`. `AttemptState.status` stays `locked` for them, so the apply path refuses exactly as before (decision 2).

### D3. The lock report tells "locked" from "unresolved"

`inspect_migration_lock` adds states `resolution:<outcome>:<env>` from the sidecar. A scratch run manifest whose `runId` is named by a resolution is reported as resolved, not unknown. Nothing changes for a folder with no resolution.

`revise --check`, `migration-plan` and `feature convert-plan` print the resolution state. They treat a resolved folder as they treat a locked one (it is never applied again).

### D4. The command

```bash
scripts/team.sh reconcile-migration <folder> --env dev|staging|prod \
  --outcome failed-no-target-effect|failed-target-effect-unknown|superseded \
  --evidence <file> [--attempt <attempt-id>] [--superseded-by <folder>]
```

- Reads local files only. No database call, no SQLcl.
- Finds the pending attempt for that folder and environment. With more than one, it lists them and requires `--attempt`.
- Scratch-only case (a retained run manifest under `scratch/` names the folder and environment, but its attempt events are not in this checkout): the command resolves the run. The record's `attemptId` is `null`, the acknowledgment is `RECONCILE-MIGRATION <run-id>`, and no closing event is written, because a chain cannot be closed without its pending root. The lock report treats a missing event reference of a run that a valid resolution names as resolved.
- With neither an event nor a run manifest, it refuses and says so: in that checkout the folder has no attempt to resolve.
- Prints the folder, environment, attempt id, run id, recorded failure state from the run manifest when it exists, the outcome and the evidence digest, then requires the typed acknowledgment `RECONCILE-MIGRATION <attempt-id>` through `scripts/terminal_confirm.py` (`may_read_acknowledgment`: redirected input is refused; `TEAM_ACK_FROM_STDIN=1` is the test-only path). An agent never types it.
- Writes the resolution sidecar and the closing attempt event. It never edits or deletes an earlier event, the folder's SQL, `checks.json` or any receipt.
- Refuses: a wrong or empty acknowledgment; a missing, unsafe or changed evidence file; a target that has a verified receipt; an attempt that is not pending; `apply-not-started` attempts (nothing to resolve); an existing resolution; a folder whose bytes no longer match the attempt's payload digest.

### D5. Supersession is checked in code

`--outcome superseded` requires `--superseded-by <folder>` and passes only when that folder is a later revision of the same family and schema, has a `status.<env>.json` for the same environment, and `validate_receipt` accepts it. The folder may be visible or archived (found through the schema's `.archived.json` and its recorded destination). The record stores that receipt's digest.

### D6. Archive

- Evidence comes from the recorded outcome. A folder with `resolution.<env>.json` and no verified receipt is archivable without any flag, and its plan line reads `resolved:<outcome>:<env>`.
- New option `--preserve-unresolved`: archives a folder whose attempt has no receipt and no resolution, recording `unresolved (preserved)`. It does not call the attempt failed. `--allow-unverified-attempts` keeps working and is the only source of the word "accepted".
- `--all` evaluates every selected folder, prints every refusal with the command that resolves it, and archives nothing when any folder is refused (exit 2), as today. New option `--skip-refused`: archive what is eligible and list what was skipped. It still honours the prefix rule, so within a family it archives the eligible low prefix and stops at the first refused revision.
- The `.archived.json` record gains one optional key, `evidence` (the list of evidence strings from the plan). Schema version stays 1; a record without the key loads as before.
- The prefix rule is unchanged (decision 3). A prefix may end in a resolved revision, because a resolved revision is now archivable.

### D7. Messages

Every refusal in `migrate.py`, `migration_archive.py` and `migration_revision.py` that says "reconcile" or "state unknown" names the command: `scripts/team.sh reconcile-migration <folder> --env <env> --outcome ... --evidence <file>`. Wording changes only; no refusal is removed.

### D8. Compatibility

- Existing attempt events, receipts, schema-1 `.archived.json` indexes and archived folders load unchanged. Fixtures copied from the current format prove it.
- A checkout on an older template refuses a folder that holds `resolution.<env>.json` (unknown file). The upgrade note says: every developer upgrades the template before anyone commits a resolution.
- `migrate.py`, `migration_attempts.py`, `migration_revision.py` and `migration_manifest.py` are capsule engine files: the engine digest changes, and a capsule frozen before must be frozen again. The feature-capsule `RECONCILE` flow and `rollout_capsule.py` recovery behave exactly as before; a test pins that a resolved attempt is still "not replayable" for capsule recovery.

## Decisions (made by the owner on 2026-11-12: the recommended option each time; do not reopen)

1. **A resolution lives in a committed sidecar** `resolution.<env>.json` in the folder, plus the local closing event.
2. **A resolved folder is never applied again.** After `failed-no-target-effect` the folder stays locked; the next revision carries the fix.
3. **The contiguous-prefix rule stays.** A superseded revision is archived as part of a low prefix, not alone.
4. **`--all` reports every refusal and archives nothing;** `--skip-refused` archives the eligible folders and lists the rest.
5. **`migrate` does not record the failure itself.** The attempt stays `pending` until the owner reconciles; only the messages change.

## Phases

### Phase 1: failing tests and fixtures (no production code changes)

- Fixtures copied from the current formats under `tests/fixtures/migration_attempts_v1/`: a pending event, a pending-to-verified chain, an `apply-not-started` event with its evidence, a verified receipt, a schema-1 `.archived.json`, one archived folder. Neutral names only (`APP_ONE`, `archive-family`).
- New tests, expected to fail until phase 2 to 4:
  - `tests/test_migration_attempts.py`: each new state validates with one `owner-resolution` evidence item and is refused without it; old fixtures load unchanged; a chain with a second terminal event is refused.
  - `tests/test_migration_resolution.py` (new): the command writes the sidecar and the closing event; refusals for a wrong acknowledgment, a missing or changed evidence file, a target with a verified receipt, a non-pending attempt, an existing resolution, changed folder bytes; redirected acknowledgment refused; nothing written on any refusal; no SQLcl is started.
  - Supersession: refused without a later verified revision, with a later revision verified only in another environment, and with an unreadable receipt; accepted for a visible and for an archived later revision.
  - `tests/test_migration_archive.py`: a resolved folder archives without a flag and records its outcome; `--preserve-unresolved` records `unresolved (preserved)`; "accepted" appears only with `--allow-unverified-attempts`; `--all` reports every refusal per folder and moves nothing; `--skip-refused` archives the eligible prefix; a prefix ending in a superseded revision archives; an old index without `evidence` loads and round-trips.
  - `tests/test_migration_revision.py`, `tests/test_migrate_cli.py`: a resolved folder is still refused by `migrate` with the new message; `revise` continues from it; the refusal messages name the command.
  - `tests/test_feature_rollout.py`: capsule recovery treats a resolved attempt as before.
- Done when: the new tests fail for the expected reason and every existing test still passes.

### Phase 2: attempt states, resolution record, lock report

- `scripts/migration_attempts.py` (D2), new `scripts/migration_resolution.py` (record schema, read, validate, no-overwrite write; D1), `scripts/migration_manifest.py` (accept the sidecar and validate it on discovery), `scripts/migration_revision.py` (D3).
- Add `scripts/migration_resolution.py` to the engine list in `scripts/release_capsule.py` and to the tests that pin the list.
- Done when: the phase-1 tests for states, record and lock pass; the rest of the suite is unchanged.

### Phase 3: the reconcile command and supersession

- `scripts/migration_resolution.py` CLI (D4, D5), wrappers `scripts/team.sh` and `scripts/team.ps1` (identical usage texts), `scripts/migrate.py` (refuse a receipt where a resolution exists; messages, D7).
- Done when: the command tests and the supersession tests pass; `migrate` tests pass with only message expectations changed.

### Phase 4: archive, docs, rules

- `scripts/migration_archive.py` (D6).
- Docs: new `docs/migration-attempt-resolution.md` (the design, the command, worked examples), `docs/migration-rules.md` (archiving section and the attempt paragraph), `docs/TROUBLESHOOTING.md` (the "may be partially applied" row), `README.md`, `migrations/README.md`, `AGENTS.md` and `.agents/rules/agent-safety.md` (an agent never types `RECONCILE-MIGRATION`), `docs/known-limitations.md` (the tool records the owner's statement and does not check the target).
- Done when: the full suite passes (`python3 scripts/ci_run_tests.py --jobs 6`) and `python3 scripts/pre_push_check.py --all` passes.

### Phase 5: 26.2 port and parity

- Hand-merge phases 1 to 4 into the 26.2 template (its `migrate.py`, rehearsal and archive differ), then refresh `docs/superpowers/template-parity.json` until `tools/template_parity.py` exits 0.

## Pull request body must include

- Engine digest note (capsules must be frozen again).
- Upgrade note for downstream projects: run `scripts/team.sh upgrade-template` in every developer's repository first; then, for each folder that `archive-migrations --all` refuses, inspect the target, write the evidence file, run `reconcile-migration` with the matching outcome, commit the resolution and the evidence, and archive.

## Not verified by this plan

- No live database run: the change makes no database call, and the opt-in live module does not cover dated-migration attempts that fail.
- `team.ps1` on native Windows beyond CI's offline tests.
