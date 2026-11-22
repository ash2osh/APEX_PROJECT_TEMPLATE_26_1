# Release blockers, persistent SQLcl sessions and speed-ups: implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. The owner fixed the execution method on 2026-11-22: the orchestrator writes all code; Haiku subagents (`model: haiku`, `effort: high`) only run tests and the Docker end-to-end runs. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Fix the confirmed template release blockers. Then add the persistent SQLcl session pool. Then remove the duplicate database work the review confirmed, measure the result end to end, and only then fix the natrec release.

**Architecture:**
- **Shared files** are edited in `APEX_TEMPLATE_CORE/files/…`, committed, merged with a merge commit, and then synced into each template with `sync_core.py sync`.
- **Per-template files** get the same change made by hand in both `APEX_PROJECT_TEMPLATE_26_1` and `APEX_PROJECT_TEMPLATE_TEAM` (26.2).
- **PR sets, in order:**
  1. blockers;
  2. session pool;
  3. speed-ups;
  4. measurement;
  5. natrec.

  Each set is one core PR plus one PR per template.

**Tech Stack:** Python 3.10+ standard library, `unittest`, SQLcl 26.3.1, Oracle 23ai (local Docker), Bash and PowerShell launchers.

**Spec:**
- `docs/superpowers/specs/2026-11-22-persistent-sqlcl-sessions-design.md` (approved 2026-11-22);
- `scratch/review-verification-2026-11-22/VERIFIED.md` (verified review and rehearsal findings).

## Global Constraints

- The order is fixed by the owner: all template work first, natrec fixes last.
- The orchestrator writes code. Testers are Haiku at high effort. Testers never commit, push, or connect to anything except the `natrec-e2e-*` containers, through the isolated SQLcl home (`HOME=/tmp/claude-1000/agy-home-e2e JAVA_TOOL_OPTIONS=-Duser.home=/tmp/claude-1000/agy-home-e2e`).
- A shared-file change lands in `APEX_TEMPLATE_CORE` first. Merge it with a merge commit, never a squash. Then sync each template, commit the stamp, and open one PR per template.
- Run suites with `GIT_CONFIG_GLOBAL=/dev/null`, against tracked files only (`git ls-files`). Run `python3 scripts/pre_push_check.py` before every template push.
- Check `docs/known-limitations.md` before changing behaviour. Behaviour listed there is deliberate.
- No credentials in tracked files. No commit or push without the owner's instruction.
- Production and DEV26 are touched only read-only, and only when the owner asks for a live check.
- Pool settings and defaults:
  - `SQLCL_PERSISTENT_SESSIONS` (default `1`; `0` means one launch per script);
  - `SQLCL_POOL_MAX_READERS` (default `2`);
  - `SQLCL_POOL_VERIFY_RESET` (builder's call);
  - loop batch size K = 500;
  - SQLcl nesting limit 20.
- The pool reuses database sessions. One PL/SQL reset block runs per script. Writer and reader sessions stay separate. A failed reset replaces the process.

## Review Focus

1. **A capsule whose staging proof ran in the other SQLcl mode** must still be accepted. The mode is reported, not enforced. Test: `test_prod_accepts_staging_proof_from_other_sqlcl_mode` (Task 17).
2. **A database session lost during a rollout `pause` step:** the next script must replace the process before any of its text is written, and must never be retried after. Test: `test_lost_session_replaced_before_script_sent` (Task 15).
3. **An owner login without `V$PARAMETER` access (DEV):** the writer must reconnect before each apply instead of reusing an unverifiable session. Test: `test_writer_reconnects_when_compiler_baseline_unreadable` (Task 15).
4. **A driver from a generator not yet moved to the pooled epilogue** must run one-shot, never be mis-framed. Test: `test_driver_without_pooled_epilogue_runs_one_shot` (Task 16).
5. **An acting-as login that cannot read `DBA_TAB_PRIVS`** must make prepare refuse with a clear message, not pass a grant check that cannot see the grant. Test: `test_acting_as_without_dba_tab_privs_refuses_grant_checkpoint` (Task 4).

---

## Tester protocol (used by every task)

The orchestrator dispatches one Haiku tester per verification step. Use `Agent(model="haiku", effort="high", subagent_type="general-purpose")` with this brief, filled in:

> Clone `<repo>` at branch `<branch>` into `/tmp/claude-1000/test-<task>-<n>/`. Run exactly these commands from the clone root with `GIT_CONFIG_GLOBAL=/dev/null`: `<commands>`. Do not edit, commit or push. Do not connect to any database unless the brief names a `natrec-e2e-*` container. Report each command, its exit code, and the last 60 lines of output verbatim, then the failing test names. Never summarise a failure as a pass.

The orchestrator reads the raw output before treating a step as passed.

Test commands, run from a clone root:
- **Core:** `python3 sync_core.py refresh && python3 -m unittest discover -s tests && ruff check sync_core.py tests/ files/`.
- **Template, one test:** `python3 -m unittest tests.<module>.<Class>.<test> -v`.
- **Template, full:** `python3 scripts/ci_run_tests.py` and `python3 scripts/pre_push_check.py`.

---

## Phase 1: Template release blockers (PR set 1)

Branches:
- `fix/release-blockers` in the core;
- `fix/release-blockers` in each template, branched from `main`.

### Task 1: Record the observed identity for app-deploy targets (X1)

**Files:**
- Modify: `APEX_TEMPLATE_CORE/files/scripts/feature_release.py` (`_app_targets`, lines ~693-722; `load_target_plan` app-target validation).
- Test: `tests/test_feature_rollout.py` (per template).
- Test: `APEX_TEMPLATE_CORE/files/tests/test_release_capsule.py` if `load_target_plan` tests live there.

**Interfaces:**
- Produces: every `target_plan.targets["app:<id>"]` holds `"observed": dict` with the `rollout.OBSERVED_IDENTITY_FIELDS` keys. Its identity session user and current schema equal the resolved read target.

- [ ] **Step 1:** Write `test_prepare_records_observed_identity_for_app_target`.
  - Prepare a capsule with one `app-deploy` step, with `rollout._observe_target_identity` patched to return a full identity.
  - Assert `targets["app:100"]["observed"]["db_unique_name"] == "STGDB"`.
- [ ] **Step 2:** Write `test_confirm_target_rollout_accepts_capsule_with_app_step`. Run a staging rollout with `confirm_target="STGDB"` and assert status 0.
- [ ] **Step 3:** Write `test_prod_rollout_accepts_app_step_with_observed_name`.
- [ ] **Step 4:** Write `test_load_target_plan_refuses_app_target_without_observed_identity`. Assert `FeatureReleaseError` matching "application 100 prepared target identity is incomplete".
- [ ] **Step 5:** Tester runs the three tests and confirms they fail.
- [ ] **Step 6:** Implement in `_app_targets(root, steps, environment, environ) -> dict[str, dict]`.
  - Observe the identity with `rollout._observe_target_identity(target, root / "scratch" / "feature-release-prepare" / environment / f"app-{app_id}-identity")`, passed through `_identity(target, …)`.
  - Store it as `"observed"`. Raise `FeatureReleaseError(f"cannot capture complete target identity for application {app_id}: {error}")` on failure.
  - In `load_target_plan`, require the field for every `app:` key.
- [ ] **Step 7:** Tester runs the four tests, then the template full suite. All pass.
- [ ] **Step 8:** Commit in the core: `fix(feature-release): record observed identity for app-deploy targets`.

### Task 2: Revalidation tolerates the capsule's own earlier effects (E4, E6)

**Files:**
- Modify: `APEX_TEMPLATE_CORE/files/scripts/feature_release.py`, around lines 1967-1981 in `_execute_checkpoint_under_lease`. Add new helpers next to `_guard_valid_units`.
- Test: `tests/test_feature_rollout.py`.

**Interfaces:**
- Produces:
  - `_earlier_capsule_units(capsule: ReleaseCapsule, checkpoint: int, schema: str) -> frozenset[tuple[str, str]]`: (TYPE, NAME) of stored units written by earlier checkpoints of the same schema.
  - `_revalidation_view(structural: Mapping, guard_structural: Mapping, earlier_units: frozenset[tuple[str, str]], checkpoint: int) -> tuple[dict, dict]`: returns the comparable (fresh, guard) pair.

Rules for `_revalidation_view`. They apply only when `checkpoint > 1`; for checkpoint 1 it returns both unchanged.
- (a) Drop every row for a key in `earlier_units` from both sides, in `stored-code`, `views`, `triggers`, `invalid-objects` and `feature-dependencies`. Source verification after apply covers those units.
- (b) For a key present on both sides where the guard row's `status` is `VALID` and the fresh row's is `INVALID`, and every other field is equal, treat the fresh row as `VALID`. Drop that key's fresh `invalid-objects` row.
- Do **not** recompile anything, and do not swallow ORA-24344. The clone's recompile patch is rejected.

Steps:
- [ ] **Step 1:** Write `test_status_flip_from_earlier_ddl_does_not_refuse_next_checkpoint`.
  - Guard: a stored-code row `VALID`, hash H.
  - Fresh: the same row `INVALID`, hash H, plus an `invalid-objects` row.
  - Assert `execute_checkpoint` for checkpoint 2 reaches apply.
- [ ] **Step 2:** Write `test_unit_rewritten_by_earlier_checkpoint_is_excluded_from_revalidation`. The fresh hash differs for a unit in checkpoint 1's inputs; assert no refusal.
- [ ] **Step 3:** Write `test_real_drift_still_refuses`. Change a hash for a unit not in `earlier_units` and assert "live selected target metadata changed after preparation".
- [ ] **Step 4:** Write `test_status_flip_on_first_checkpoint_still_refuses`.
- [ ] **Step 5:** Tester confirms the four tests fail.
- [ ] **Step 6:** Implement both helpers.
  - Compare `_sha256(_canonical_bytes(fresh_view))` with `_sha256(_canonical_bytes(guard_view))`.
  - First check that the stored guard still matches `guard["structuralSha256"]`, raising "prepared structural checkpoint guard digest is malformed".
- [ ] **Step 7:** Tester runs the four tests plus `tests.test_feature_rollout` and `tests.test_live_feature_release`. All pass.
- [ ] **Step 8:** Commit: `fix(feature-release): revalidation ignores the capsule's own earlier effects`.

### Task 3: Prior-effect and namespace fixes in preflight (E3, E1a, E1b)

**Files:**
- Modify: `APEX_TEMPLATE_CORE/files/scripts/feature_preflight.py`:
  - `strip_prior_effects` (~1196-1290);
  - `_live_catalog` (~215) and `_simulated_catalog` (~284);
  - `_index_before_check` (~327) and its caller (~1021).
- Test: `APEX_TEMPLATE_CORE/files/tests/test_feature_preflight.py`, or the existing preflight test module.

Steps:
- [ ] **Step 1:** Write `test_strip_prior_effects_removes_identity_sequence_and_indexes_of_created_table`. A `CREATE_TABLE T` effect; the fresh capture has a sequence `ISEQ$$_1` whose identity row has table T, and an index on T. Assert both are removed.
- [ ] **Step 2:** Write `test_public_synonym_does_not_occupy_schema_namespace`. A new table `FOO` while a PUBLIC synonym `FOO` exists; assert no "namespace occupied" refusal.
- [ ] **Step 3:** Write `test_public_synonym_still_satisfies_view_dependency`.
- [ ] **Step 4:** Write `test_index_on_column_added_in_same_checkpoint_passes_before_check`. `ALTER TABLE T ADD (C NUMBER)` then `CREATE INDEX I ON T(C)`; assert the generated before-check does not require C to exist.
- [ ] **Step 5:** Tester confirms they fail.
- [ ] **Step 6:** Implement.
  - E3: the clone 16391420 logic (identity sequences and indexes of `CREATE_TABLE` names).
  - E1a: keep PUBLIC synonyms in a separate set that only the dependency checks read.
  - E1b: track `staged_columns` from `ALTER_ADD_COLUMN` operations, and pass `column_staged=True` to `_index_before_check` so it skips the column predicate for staged columns.
- [ ] **Step 7:** Tester runs the preflight module and `tests.test_feature_rollout`. All pass.
- [ ] **Step 8:** Commit: `fix(feature-preflight): prior identity sequences, PUBLIC synonym namespace, staged index columns`.

### Task 4: Grant visibility for acting-as logins (B2)

**Files:**
- Modify: `APEX_TEMPLATE_CORE/files/scripts/feature_preflight.py`:
  - `prepare_checkpoint` (~831): derive `acting_as` from `state["identity"]["session_user"] != checkpoint.schema`;
  - `_dependency_check` (~346) and `_effect_queries` (~601): use the privilege view.
- Modify: `APEX_TEMPLATE_CORE/files/scripts/feature_release.py`, the prepare loop: refuse an acting-as `GRANT_OBJECT` or synonym-dependency checkpoint when the capture marks `object-grants` unavailable.
- Modify: `scripts/compare_env_catalog.sql` in **both** templates, `feature-synonym-access` (26.1 ~1357-1368, 26.2 ~1325-1336). Mirror the `add_object_grants` acting-as branch: `DBA_TAB_PRIVS` with `OWNER`; ORA-942 means `add_unavailable('feature-synonym-access', …)`.
- Test: the core preflight test module; `tests/test_compare_env.py` (per template).

**Interfaces:**
- Produces: `_tab_privs_source(acting_as: bool) -> tuple[str, str]`, returning `("DBA_TAB_PRIVS", "OWNER")` or `("ALL_TAB_PRIVS", "TABLE_SCHEMA")`.

Steps:
- [ ] **Step 1:** Write `test_acting_as_grant_checks_read_dba_tab_privs`. Session user `ASHERIF`, schema `APP`; assert every generated grant check contains `DBA_TAB_PRIVS P WHERE P.OWNER = :target_schema` and none contains `ALL_TAB_PRIVS`.
- [ ] **Step 2:** Write `test_owner_login_grant_checks_keep_all_tab_privs`.
- [ ] **Step 3:** Write `test_acting_as_without_dba_tab_privs_refuses_grant_checkpoint` (Review Focus 5). Assert `FeatureReleaseError` containing "grant checks need SELECT on DBA_TAB_PRIVS".
- [ ] **Step 4:** Write `test_feature_synonym_access_uses_dba_tab_privs_when_acting_as` (in `test_compare_env`). Assert on the SQL text, the same way the PR #93 test does.
- [ ] **Step 5:** Tester confirms they fail.
- [ ] **Step 6:** Implement as described.
- [ ] **Step 7:** Tester runs the preflight module, `tests.test_compare_env` in both templates, and `tests.test_feature_rollout`. All pass.
- [ ] **Step 8:** Commit the core and both templates: `fix: grant checks and synonym access read DBA_TAB_PRIVS for acting-as logins`.

### Task 5: Allow `DB_UNIQUE_NAME` in read-only queries (E5)

**Files:**
- Modify: `APEX_TEMPLATE_CORE/files/scripts/read_only_query.py:57`. Change `_IDENTITY_ATTRIBUTES` to add `"db_unique_name"` and `"con_name"`.
- Test: the core `tests/test_read_only_query.py`.

Steps:
- [ ] **Step 1:** Write `test_db_unique_name_sys_context_is_allowed`. `validate_query("SELECT SYS_CONTEXT('USERENV','DB_UNIQUE_NAME') FROM DUAL")` does not raise.
- [ ] **Step 2:** Tester confirms it fails.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Tester confirms it passes, along with the module.
- [ ] **Step 5:** Commit: `fix(read-only-query): allow DB_UNIQUE_NAME and CON_NAME`.

### Task 6: Trigger header ENABLE/DISABLE in stored-source verification (E7)

**Files:**
- Modify: `APEX_TEMPLATE_CORE/files/scripts/feature_release.py`, `_stored_source` (~340-380).
- Test: `tests/test_feature_rollout.py`, or the stored-source test module.

Steps:
- [ ] **Step 1:** Live fact check, done by a tester on `natrec-e2e-stg`. Create two triggers with `ENABLE` as a standalone header line, and as `… ON T ENABLE` inline, then `SELECT TEXT FROM ALL_SOURCE`. Report the exact lines. Then drop the triggers. Check the container is started, and stopped again afterwards.
- [ ] **Step 2:** Write `test_trigger_header_enable_line_matches_all_source`, using the exact ALL_SOURCE text from Step 1.
- [ ] **Step 3:** Write `test_trigger_body_disable_word_is_kept`. `DISABLE` inside the body must not be stripped.
- [ ] **Step 4:** Implement the normalisation for both the standalone and the inline forms, limited to the header (before `COMPOUND TRIGGER`, `DECLARE`, `BEGIN` or `CALL`).
- [ ] **Step 5:** Tester runs both tests and the module.
- [ ] **Step 6:** Commit: `fix(feature-release): normalise trigger header ENABLE/DISABLE`.

### Task 7: Stored-code catalog pagination (B1)

**Files:**
- Modify: `scripts/compare_env_catalog.sql` in both templates, `add_stored_code` (26.1 ~1138-1157, 26.2 ~1124-1142).
- Test: `tests/test_compare_env.py` (both).

Steps:
- [ ] **Step 1:** Write `test_stored_code_pages_count_emitted_rows`. A SQL-text test: the loop appends a page when 500 rows have been **emitted**, and once at the end for the remainder. There is no `l_fetched < c_page_size` exit tied to cursor rows.
- [ ] **Step 2:** Implement one cursor without OFFSET, with `l_emitted` driving the page boundaries.
- [ ] **Step 3:** Tester runs `tests.test_compare_env` in both templates.
- [ ] **Step 4:** Tester runs a live equivalence check on `natrec-e2e-stg`. Compare old and new output for scopes `all`, `prefix` and `one-package`; it must be identical. Use `scratch/catalog-bench` style. Stop the container afterwards.
- [ ] **Step 5:** Commit both templates: `fix(compare-env): page stored code by emitted rows`.

### Task 8: Engine digest completeness (B5)

**Files:**
- Modify: `APEX_TEMPLATE_CORE/files/scripts/release_capsule.py:31-106`.
  - Add `scripts/sqlcl_session.sh`, `scripts/database_support.py` and `scripts/template_release.py`.
  - Add a per-template `ENGINE_EXTRA_FILES` read from an optional `scripts/engine_extra_files.txt` (per template), skipping lines that start with `#`.
- Create: `scripts/engine_extra_files.txt` in each template.
  - 26.2: `scripts/local_config.py`, `scripts/apex_compatibility.py`, `scripts/no_application_lock.sql`, `scripts/verify_apex_release.sql`, `scripts/verify_deployment_state.sql`, `scripts/apexlang_diff.py`, `scripts/apexlang_normalization.py`, `scripts/source_evidence.py`, `scripts/source_provenance.py`.
  - 26.1: the files that exist and are used at runtime.
- Test: the core `tests/test_release_capsule.py`.

Steps:
- [ ] **Step 1:** Write `test_engine_files_cover_runtime_imports_and_sql_includes`.
  - Walk the imports of `scripts/rollout.py`, `rollout_capsule.py`, `feature_release.py` and `migrate.py` (via `ast`).
  - Walk the `@`/`@@` includes and the `scripts/*.sh` invocations named in those files.
  - Assert every reached file under `scripts/` is in the engine set.
- [ ] **Step 2:** Implement.
- [ ] **Step 3:** Tester runs the test in both templates.
- [ ] **Step 4:** Commit: `fix(release-capsule): engine digest covers runtime files`.

### Task 9: 26.2 publish import flag (B3)

**Files:**
- Modify: `APEX_PROJECT_TEMPLATE_TEAM/scripts/publish_app.sh:677,680` and `publish_app.ps1:636,640`. Set the import-attempted flag false outside the dev block, beside `import_unverified=false`.
- Test: the 26.2 publish tests.

Steps:
- [ ] **Step 1:** Write `test_staging_publish_success_removes_diagnostics_and_prints_no_warning`, Bash and PowerShell variants, in the existing publish test style.
- [ ] **Step 2:** Implement.
- [ ] **Step 3:** Tester runs the publish test module.
- [ ] **Step 4:** Commit in 26.2: `fix(publish): clear import flag outside the dev lock block`.

### Task 10: staging-neutralize refuses a production-looking target (B4 part 1)

**Files:**
- Modify: `APEX_TEMPLATE_CORE/files/scripts/staging_neutralize.py`, the SQL guard (~261-272). Add an observed-name check using the same `_SQL_PRODUCTION_MARKER` pattern as `read_only_query.py`, on `db_unique_name`, `db_name` and `service_name`.
- Test: `tests/test_staging_neutralize.py`.

Steps:
- [ ] **Step 1:** Write `test_neutralize_sql_refuses_production_looking_observed_name`. Assert on the generated SQL text.
- [ ] **Step 2:** Implement.
- [ ] **Step 3:** Tester runs the module.
- [ ] **Step 4:** Commit: `fix(staging-neutralize): refuse production-looking observed names`.

### Task 11: Docs and cleanups (DOC1-4, C1, P1)

**Files:**
- `docs/compare-env.md` (both): acting-as reads `DBA_TAB_PRIVS`.
- 26.2 `docs/migration-rules.md:370`.
- 26.2 `docs/known-limitations.md:25`.
- `docs/ci-checks.md` (both): file count 261.
- The dead branches in `rollout_capsule.py:726` (per template), `migration_checks.py` (per template) and `feature_preflight.py:944` (core).
- The `stat -f %l` fallback in `.agents/` and `.claude/skills/apex-background/probe/run.sh` (both).
- `docs/known-limitations.md`: add rows for any behaviour Phase 1 deliberately keeps.

- [ ] **Step 1:** Edit.
- [ ] **Step 2:** Tester runs the template full suites (the docs tests check links and manifests).
- [ ] **Step 3:** Commit: `docs: align with acting-as grant reads and current behaviour`.

### Task 12: Land PR set 1

- [ ] **Step 1:** Tester runs the core full suite on `fix/release-blockers`.
- [ ] **Step 2:** The orchestrator asks the owner for go-ahead to commit and push and open the core PR. After the owner's merge approval, merge it with a merge commit.
- [ ] **Step 3:** In each template, run `python3 /home/ash/projects/APEX_TEMPLATE_CORE/sync_core.py sync . --core /home/ash/projects/APEX_TEMPLATE_CORE`, review `git diff`, and commit.
- [ ] **Step 4:** Tester runs `python3 scripts/ci_run_tests.py` and `python3 scripts/pre_push_check.py` in both templates.
- [ ] **Step 5:** Update the parity ledger in 26.2: `tools/template_parity.py ../APEX_PROJECT_TEMPLATE_26_1 --mark …` for per-template files changed identically.
- [ ] **Step 6:** Push and open the template PRs. Bind them with `ccd_pr`. CI is watched by the app.

---

## Phase 2: Persistent SQLcl sessions (PR set 2)

Branches:
- `feat/persistent-sqlcl-sessions` in the core, the 26.1 branch (which already holds the design doc), and 26.2.

New core files:
- `files/scripts/sqlcl_pool.py`: transport, sessions and pool;
- `files/tests/fake_sqlcl_pool.py`: a protocol fake;
- `files/tests/test_sqlcl_pool.py`.

### Task 13: One shared driver epilogue

**Files:**
- Modify: `APEX_TEMPLATE_CORE/files/scripts/sqlcl_session.py`. Add `driver_epilogue(commit: bool) -> str` and `POOLED_EPILOGUE_RE`.
- Modify every generator that writes `EXIT SUCCESS …` to call the helper:
  - core: `application_lifecycle.py:133,230`, `compare_schema.py:1340`, `dev_test_target.py:296`, `dev_test_runtime.py:434,755`, `feature_release.py:1862`, `read_only_query.py:718`, `migrate.py:760`, `migration_rehearsal.py:181,198`, `schema_catalog.py:752`, `staging_neutralize.py:256`;
  - per template: `migration_checks.py:968`, `rollout.py:1528`.
- Test: `files/tests/test_sqlcl_session.py`.

**Interfaces:**
- Produces:
  - `driver_epilogue(commit: bool) -> str`. One-shot mode returns `"EXIT SUCCESS COMMIT"` or `"EXIT SUCCESS ROLLBACK"`. Inside an active pool context it returns `"COMMIT;"` or `"ROLLBACK;"`, followed by the line `-- TEAM_POOLED_EPILOGUE`.
  - `is_pooled_driver(text: str) -> bool`.

Steps:
- [ ] **Step 1:** Write `test_driver_epilogue_one_shot_matches_legacy_lines` and `test_driver_epilogue_pooled_has_marker`.
- [ ] **Step 2:** Write `test_no_generator_writes_literal_exit_success`, a source scan of `scripts/*.py` excluding `sqlcl_session.py`.
- [ ] **Step 3:** Implement, and replace every site.
- [ ] **Step 4:** Tester runs the full suites in both templates. Byte-pinned SQL tests, such as `tests/test_baseline.py` hashes, are updated in the template PRs.
- [ ] **Step 5:** Commit: `refactor: one shared SQLcl driver epilogue`.

### Task 14: Pool transport: loop file, slot FIFOs, framing, failure

**Files:**
- Create: `files/scripts/sqlcl_pool.py`, the `_Transport` part.
- Create: `files/tests/fake_sqlcl_pool.py`. It's a Python fake `sql`. It reads `@loop0.sql`, follows slot FIFOs, enforces nesting at most 20 (prints `SP2-0309`), honours `WHENEVER SQLERROR EXIT` through a marker statement `FAKE_SQL_ERROR;`, and handles `connect -name X` and `PROMPT`.
- Create: `files/tests/test_sqlcl_pool.py`.

**Interfaces:**
- Produces:

```python
class SqlclProcess:
    def __init__(self, alias: str, run_root: Path, environment: Mapping[str, str], *, batch_size: int = 500) -> None: ...
    def start(self) -> None                      # launches through sqlcl_safe (private cwd, empty SQLPATH), connects once
    def run_segment(self, text: str, *, timeout_seconds: float,
                    output_limit_bytes: int | None, cancel_event) -> tuple[int, str]  # (returncode, output up to sentinel)
    def alive(self) -> bool
    def close(self) -> None                      # writes EXIT ROLLBACK into the next slot, waits, then kills the group
    nesting_depth: int                           # retire before 20
```

- `run_segment` returns `(0, output)` when the sentinel is seen. When the process ended first, it returns `(exit_status, output)` and the process is dead. Timeout and cancel kill the process group and raise `SqlclTimeout` or `SqlclCancelled` from `sqlcl_session`.

Steps:
- [ ] **Step 1:** Write these tests:
  - `test_segments_are_framed_by_sentinel`
  - `test_loop_file_rollover_keeps_order` (1,200 segments, K=50)
  - `test_process_retired_before_nesting_limit`
  - `test_sql_error_ends_process_and_returns_status`
  - `test_timeout_kills_process_group`
  - `test_cancel_event_kills_process`
  - `test_output_limit_applies_to_segment`
  - `test_alias_with_unsupported_characters_refused`
  - `test_start_dir_has_empty_sqlpath`
- [ ] **Step 2:** Tester confirms the tests fail.
- [ ] **Step 3:** Implement as in the spec's "Process start and transport". There is one reader thread per process, feeding a `queue.Queue`. FIFOs are `0600` inside a `0700` run root. The next slot is created before the current one is written. The sentinel is `__TEAM_SQLCL_DONE_<secrets.token_hex(16)>__`.
- [ ] **Step 4:** Tester runs `tests.test_sqlcl_pool` 5 times in a row; all pass, with no stray `sql` processes left (`pgrep -f fake_sqlcl_pool` is empty).
- [ ] **Step 5:** Commit: `feat(sqlcl-pool): loop-file transport for long-lived SQLcl`.

### Task 15: Session init, reset and verify; client reset

**Files:**
- Modify: `files/scripts/sqlcl_pool.py`. Add `_SessionState` and the session-init and reset blocks.
- Extend the fake: it simulates session state (a transaction flag, `CURRENT_SCHEMA`, NLS and compiler values, package state, `DEFINE`s) and the `RESET_MARKER` output.

**Interfaces:**
- Produces:
  - `session_init_block() -> str`
  - `reset_block(baseline: SessionBaseline) -> str`
  - `client_reset_block(baseline: ClientBaseline) -> str`
  - `SessionBaseline` (NLS dict, compiler dict or `None`, edition, session_user)
  - `ClientBaseline` (`show_all` text, `define` names)
  - `RESET_OK_MARKER = "TEAM_POOL_RESET_OK"`

Steps:
- [ ] **Step 1:** Write these tests:
  - `test_reset_runs_before_every_script_but_first`
  - `test_open_transaction_after_script_replaces_process`
  - `test_package_state_cleared_between_scripts`
  - `test_current_schema_restored`
  - `test_nls_and_compiler_settings_restored`
  - `test_define_and_set_from_one_script_not_visible_to_next`
  - `test_lost_session_replaced_before_script_sent` (Review Focus 2)
  - `test_writer_reconnects_when_compiler_baseline_unreadable` (Review Focus 3)
  - `test_reset_block_is_one_plsql_call` (the SQL text has exactly one `BEGIN … END;` plus `/`)
- [ ] **Step 2:** Tester confirms they fail.
- [ ] **Step 3:** Implement as in the spec's "Session policy".
  - The session-init block is one round trip: set `DBMS_METADATA` session transforms to `DEFAULT` and print the baseline as one JSON line.
  - The reset block is one round trip:
    1. rollback;
    2. enable commit in procedure;
    3. reset `CURRENT_SCHEMA`;
    4. `DBMS_SESSION.RESET_PACKAGE`;
    5. metadata transforms back to `DEFAULT`;
    6. `ALTER SESSION` for each baseline value that differs;
    7. verify, then `DBMS_OUTPUT.PUT_LINE(RESET_OK_MARKER)`. The block runs `DBMS_OUTPUT.ENABLE` itself, because `RESET_PACKAGE` clears the buffer.
  - The client reset sends the fixed `SET` block, `CLEAR BREAKS`, `CLEAR COMPUTES`, `CLEAR COLUMNS`, and `UNDEFINE` for each name not in the baseline. When `SQLCL_POOL_VERIFY_RESET=1`, compare `SHOW ALL` too.
- [ ] **Step 4:** Tester runs the module 5 times.
- [ ] **Step 5:** Commit: `feat(sqlcl-pool): reused sessions with one-round-trip reset`.

### Task 16: Pool, roles, and routing from `run_sqlcl`

**Files:**
- Modify: `files/scripts/sqlcl_pool.py`. Add `deployment_sessions(environment: Mapping[str, str] | None = None)` as a context manager, plus `SessionPool` (keyed by alias; writer, reader and second reader; locks; lazy start; nested contexts reuse the outer pool).
- Modify: `files/scripts/sqlcl_session.py`, `run_sqlcl`. If a pool is active and `SQLCL_PERSISTENT_SESSIONS != "0"` and the driver passes `is_pooled_driver`, send it as segment `cd <run_dir>` + `@<driver>`. Otherwise run one-shot as today. Write `sqlcl-output.log` and apply `SQLCL_ERROR_RE` exactly as today.
- Modify the entry points to enter the context: `rollout.py` `main` (per template), `migrate.py` `main`, `feature_cli.py` `main` (apply, prepare, capture, doctor `--live`), and `compare_schema.py` `main` and `main_compare_env`.

**Interfaces:**
- Consumes: `SqlclProcess` (Task 14) and `reset_block` (Task 15).
- Produces: `deployment_sessions()`, `active_pool() -> SessionPool | None`, and `SessionPool.stats() -> dict` (`processesStarted`, `databaseSessions`, `scripts`, `mode`, `fallbackReason`).

Steps:
- [ ] **Step 1:** Write these tests:
  - `test_apply_phase_goes_to_writer_checks_to_reader`
  - `test_reader_and_writer_are_different_processes`
  - `test_second_reader_only_when_first_busy`
  - `test_driver_without_pooled_epilogue_runs_one_shot` (Review Focus 4)
  - `test_persistent_sessions_off_uses_one_shot`
  - `test_nested_context_reuses_outer_pool`
  - `test_run_sqlcl_writes_output_log_per_script_in_pool_mode`
  - `test_entry_points_enter_pool` (patch `deployment_sessions` and assert each `main` enters it)
  - `test_pooled_driver_runs_safely_one_shot`: a pooled-epilogue driver sent one-shot after a fallback ends with its explicit `ROLLBACK;` or `COMMIT;` and exit 0. SQLcl's implicit commit on end-of-file then commits nothing extra.
- [ ] **Step 2:** Tester confirms they fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Tester runs the template full suites. Existing tests run one-shot, because their fakes don't speak the protocol: set `SQLCL_PERSISTENT_SESSIONS=0` in the test bootstrap (`tests/_no_real_sqlcl.py`).
- [ ] **Step 5:** Commit: `feat(sqlcl-pool): route deployment scripts through the pool`.

### Task 17: Configuration keys, reporting, engine digest

**Files:**
- Modify: `files/scripts/load_env.sh`, `load_env.ps1` and `local_config.py`: accept `SQLCL_PERSISTENT_SESSIONS`, `SQLCL_POOL_MAX_READERS` and `SQLCL_POOL_VERIFY_RESET`.
- Modify: `.env.example` in both templates.
- Modify: `rollout.py` / `rollout_capsule.py` (per template) and `feature_release.py` (core): add run totals `sqlclProcessesStarted`, `databaseSessions` and `sqlclMode` from `SessionPool.stats()`. Make `release_state.py` accept the fields.
- Modify: `release_capsule.py` to add `scripts/sqlcl_pool.py` to `ENGINE_HELPER_FILES`.

Steps:
- [ ] **Step 1:** Write `test_loaders_accept_pool_keys` (extend `tests.test_env_loader_key_parity`).
- [ ] **Step 2:** Write `test_report_records_sqlcl_mode_and_counts`.
- [ ] **Step 3:** Write `test_prod_accepts_staging_proof_from_other_sqlcl_mode` (Review Focus 1).
- [ ] **Step 4:** Write `test_engine_digest_includes_sqlcl_pool`.
- [ ] **Step 5:** Implement. Tester runs the full suites.
- [ ] **Step 6:** Commit: `feat(sqlcl-pool): settings, report fields, engine digest`.

### Task 18: Windows

- [ ] **Step 1:** Implement the Windows transport in `sqlcl_pool.py`: per-slot named pipes through `_winapi.CreateNamedPipe` / `ConnectNamedPipe`, named `\\.\pipe\team-sqlcl-<nonce>-<n>.sql`, and a `windows_job` Job object for the process tree. Gate it behind `os.name == "nt"`.
- [ ] **Step 2:** Make the fake support Windows pipes. The tests from Tasks 14-16 run unchanged.
- [ ] **Step 3:** The Windows offline CI job is the tester, once the template PR is open. If it fails and can't be fixed in two attempts, set Windows to the one-shot fallback (`fallbackReason="windows-pipes"`) and add a `docs/known-limitations.md` row.
- [ ] **Step 4:** Commit: `feat(sqlcl-pool): Windows named-pipe transport` (or `…: Windows falls back to one-shot`).

### Task 19: Docs and landing PR set 2

- [ ] **Step 1:** Create `docs/sqlcl-sessions.md` in both templates. Cover:
  - what the pool does;
  - the settings;
  - what the reset clears;
  - the known limits (session global temporary tables, application contexts, `SET ROLE`, events);
  - the one-shot fallback.

  Add rows to `docs/known-limitations.md`, and a line in `AGENTS.md`'s "Other commands", kept short.
- [ ] **Step 2:** Commit the design doc and this plan on the 26.1 branch.
- [ ] **Step 3:** Land PR set 2 the same way as Task 12.

---

## Phase 3: Speed-ups that remove database work (PR set 3)

Branch: `perf/release-db-work` (core plus templates). Each task follows the same pattern:
1. failing test;
2. tester confirms it fails;
3. implement;
4. tester runs the module and the full suite;
5. commit.

### Task 20: Drop the duplicate precondition session (S3)

**Files:** `APEX_TEMPLATE_CORE/files/scripts/feature_release.py:2001` and `:1845-1848`.

- [ ] Write `test_write_checkpoint_runs_preconditions_only_in_apply_session`. It asserts one preconditions run, the one embedded in the apply driver.
- [ ] Write `test_in_session_precondition_failure_before_payload_is_not_started`. ORA-20985 before `MIGRATION_PAYLOAD_STARTED` gives attempt status `not-started` and the target is not locked.
- [ ] Implement:
  - when `write_required`, skip the standalone `migration_checks.run_checks(..., preconditions)`;
  - classify in-session refusals as `feature_dev._retained_preconditions_refused` does.
- [ ] Commit: `perf(feature-release): run preconditions once per write checkpoint`.

### Task 21: Snapshot without a separate inventory session; dependency catalogs only when needed (S5)

**Files:**
- `APEX_TEMPLATE_CORE/files/scripts/schema_catalog.py:822-826`;
- `files/scripts/schema_catalog.sql:140-276`;
- the callers `migrate.py:866,1208` and `migration_checks.py:1657`.

- [ ] Write `test_snapshot_with_static_keys_launches_one_session`.
- [ ] Write `test_dependency_catalogs_skipped_without_create_view`.
- [ ] Write `test_compare_schema_pattern_keeps_inventory_first`.
- [ ] Implement:
  - `capture_snapshot_with_retries(target, keys, run_dir, *, include_dependencies: bool)`, which returns `(snapshot.before_inventory, snapshot)`;
  - `DEFINE include_dependencies` in `schema_catalog.sql`.
- [ ] Commit: `perf(schema-catalog): one snapshot session; dependency catalogs on demand`.

### Task 22: Reuse the first folder's preflight in leased non-interactive runs (S6)

**Files:** `APEX_TEMPLATE_CORE/files/scripts/migrate.py:994-996`, `:1069-1072`.

- [ ] Write `test_folder_one_preflight_reused_under_writer_lease_with_yes`.
- [ ] Write `test_folder_one_preflight_repeated_after_interactive_prompt`.
- [ ] Write `test_folder_two_always_fresh`.
- [ ] Implement the reuse condition: `writer_lease is not None and not interactive_confirmation and source hashes unchanged`.
- [ ] Commit: `perf(migrate): reuse folder-1 preflight in leased unattended runs`.

### Task 23: Light identity probe (S7)

**Files:**
- `files/scripts/schema_catalog.sql`: new `identity` phase (SYS_CONTEXT fields plus the `ALL_USERS` target check). Drop the 11 unused `COUNT(*)` queries from `inventory`.
- `files/scripts/schema_catalog.py`: `capture_identity(target, run_dir) -> dict`.
- `rollout.py` `_observe_target_identity` (per template): use `capture_identity`.

- [ ] Write `test_observe_target_identity_uses_identity_phase`.
- [ ] Write `test_identity_phase_sql_has_no_inventory_queries`.
- [ ] Write `test_inventory_phase_has_only_all_objects_coverage`.
- [ ] Implement.
- [ ] Commit: `perf: light identity probe`.

### Task 24: Catalog SQL hot spots, measured first (S4)

- [ ] **Step 1:** A tester times each `compare_env_catalog.sql` section live on `natrec-e2e-stg` (scoped captures as in PR #93) and reports seconds per section.
- [ ] **Step 2:** Change only the sections that take 1 s or more:
  - materialise and branch scoped versus unscoped in baseline-source, baseline-settings, baseline-views and triggers;
  - cache view DDL within the run.

  The ORA_HASH loop changes only if it is measured hot and the hashes stay equivalent.
- [ ] **Step 3:** The tester repeats the 5-scope equivalence (output byte-identical) and the timings.
- [ ] **Step 4:** Commit both templates: `perf(compare-env): faster scoped catalog sections`.
- [ ] **Step 5:** Land PR set 3 as in Task 12.

---

## Phase 4: Measure end to end (testers only)

### Task 25: Rehearsal with APEX 26.1, pool on and off

- [ ] **Step 1:** Check that APEX 26.1 install media is on the machine (`find / -name 'apex_26.1*.zip' 2>/dev/null`). If it isn't, ask the owner for the file or for go-ahead to download it, giving the name, source and size.
- [ ] **Step 2:** A tester reinstalls APEX 26.1 in `natrec-e2e-prod`, rebuilds the post-stage-1 staging snapshot volume, and records the timings.
- [ ] **Step 3:** A tester runs natrec stage 2a on staging with the upgraded template, twice from the same snapshot:
  - with `SQLCL_PERSISTENT_SESSIONS=0`;
  - with `SQLCL_PERSISTENT_SESSIONS=1`.

  Report wall time, SQLcl processes started, database sessions, and per-checkpoint seconds. Confirm from the evidence lines that every postcondition ran in the reader session and that every reset passed. This step uses the natrec release as it is, with only the rehearsal-only workarounds the E2E report lists. natrec's own fixes are Phase 5.
- [ ] **Step 4:** A tester runs a read-only DEV26 pass through the pool (catalog captures and checks only, no writes). Report the per-script seconds.
- [ ] **Step 5:** The orchestrator writes `scratch/natrec-e2e/run3/REPORT.md` and sends it to the owner.
- [ ] **Step 6:** Stop the containers; do not remove them.

---

## Phase 5: natrec release fixes (last)

Precondition: the owner decides F1-08 (drop step 38, or remove `DISABLE` and add an enabled check) and F1-20 (split 2a into capsules of 300 s or less, or change the template cap rule). Work in `/home/ash/projects/natrec_team`. Per the project rule, push each commit.

### Task 26: Upgrade natrec to the new template

- [ ] Run `scripts/team.sh upgrade-template` to template `main`. Review the diff and commit.
- [ ] Tester runs `scripts/team.sh verify-local` and the project tests (`tests/test_natrec_api_*.py`).

### Task 27: Stage 2a fixes

- [ ] Do the following (VERIFIED.md, natrec section):
  - F1-01: add COMMITs;
  - F1-02: remove the verify steps, and add a new folder `migrations/RUNERP_CUSTDATA/2026-11-2x_abshry-settings-identity-sync-r001` with a manifest step before the settings inserts;
  - F1-03: look up the parent page by name, fail if missing, add NOT EXISTS;
  - F1-05: remove the geography DDL step and the settings GRANT line;
  - F1-06: supervisors DDL before pickup DDL;
  - F1-07: topological, spec-first package order, keeping the workflow-tasks checkpoint;
  - F1-10: `DBA_TAB_PRIVS` in the feature `checks.json` files;
  - F1-08 as decided;
  - F1-20 as decided (capsule split);
  - drop-wahba `-r002` at the end of 2a.
- [ ] Run `scripts/team.sh feature doctor --live` (read-only) before the freeze. That is a DEV26 read; ask the owner first.

### Task 28: Stage 2b fixes

- [ ] Write new `-r002` folders with `CURRENT_SCHEMA` and `ALL_`/`DBA_ … WHERE OWNER =` checks, replacing the `SESSION_USER` and `USER_*` checks (F1-09):
  - retire-attachments, with a production-independent copy count (F1-12);
  - drop-supervisor-areas, without the camp-assignment checks (F1-13);
  - banner-selection-mode, folding in the add-then-drop constraint (F2-05);
  - retire-page-912;
  - address-default-oldest;
  - firebase-config-retire, with `STANDARD_HASH(clob)` (F1-17).
- [ ] Remove audit-trigger-retire (F1-14).
- [ ] Write one combined journey grant folder, EXECUTE then DEBUG (F1-15).
- [ ] Set the budget to 300 (X-3).
- [ ] Record that the `r002` folders don't run on DEV, because their effect is already there.

### Task 29: Runbook and readiness doc

- [ ] Update `docs/project/abshry/staging-readiness-2026-11-21.md`:
  - the `set_secrets.sql` step after 2a (F1-16);
  - the attachment copy script between 2a and 2b (F1-12);
  - the ORDS owner login and handler counts (F1-19);
  - the staging workspace (F1-18);
  - production privilege checks (F1-11, F1-04);
  - the current feature list (F2-01).

### Task 30: Rehearse and prepare

- [ ] A tester rehearses the fixed capsules on the Docker staging copy. Then the production copy uses the staging proof. There are no hand workarounds this time.
- [ ] With the owner's go-ahead, run a read-only `rollout --prepare --env prod` for the first capsule against real production.
- [ ] Write the daily record `ai_generate/YYYY-MM-DD/WALKTHROUGH.md`. Commit and push.
