# Feature Release Review Remediation Implementation Plan

> **For agentic workers:** Execute task by task, inline, without subagents. The repository workflow selection is none; follow these checked steps directly. Do not install or enable a workflow pack. This is a planning deliverable, not authorization to implement, commit, push, merge, connect to a database, or deploy.

**Goal:** Fix all twelve confirmed template-review findings while preserving the mutable-source workflow, frozen staged payload, target guards, durable recovery evidence, and version-1 behavior.

**Architecture:** Keep the existing feature/capsule/rollout split. Add a focused structural-preflight helper and local execution-ownership helper; extend the local state index with checkpoint verification and whole-rollout evidence so successful no-ops and recovered attempts have durable records. Resolve target-dependent settings and auxiliary-step bindings in target plans, leaving the capsule payload environment-neutral.

**Tech Stack:** Python 3.10+ standard library, unittest and existing fake SQLcl fixtures, Bash, Windows PowerShell 5.1/PowerShell 7, SQLcl 26.3+, Oracle/APEX 26.1.

**Spec:** [Original feature release contract](../specs/2026-10-27-feature-oriented-release-capsules-design.md), [confirmed findings F1–F12](../reviews/2026-10-27-template-review-findings.md), and the explicit repair decisions below. The [original implementation plan](2026-10-27-feature-oriented-release-capsules.md) supplies the unchanged workflow requirements.

## Global constraints

- Work in the existing isolated 26.1 worktree and preserve its uncommitted implementation and unrelated files. Do not port the whole 26.2 branch.
- Python 3.10+ and standard library only. Keep SQLcl 26.3+ and APEX 26.1 compatibility; introduce no guessed database-version setting.
- Before any new version-dependent SQL, obtain the intended target's guarded version and COMPATIBLE observation. Planning and offline tests authorize no database connection.
- Preserve version-1 manifest, migration, receipt, rehearsal, publish/import, and target-profile semantics. Do not weaken existing read-only checks, identity guards, transport checks, or known limitations.
- Preserve committed-source freezing, source/payload/engine/plan hashes, exact source/settings verification, native exclusive capsule installation, and selected-unit compile guards.
- Budget defaults to 120 seconds and accepts integers 1..300. Revalidation through final object checks counts; preparation, APEX, ORDS, data, and pauses remain separate. No hard kill of DDL.
- Local state and ownership coordinate this checkout only. No database ledger, mutex, metadata table, or claim of cross-repository exclusivity.
- Unknown/attempting evidence never becomes success by editing history, deleting scratch, changing source, or a normal no-op retry.
- Protect downstream features/, releases/, local evidence, and review diffs. Use UTF-8/LF; retain full identifiers in metadata and human-readable diffs.
- No commits, pushes, hosted runs, live rehearsal, downstream conversion, or deployment without the corresponding user instruction. Suggested task boundaries do not authorize those actions.

## Repair decisions

1. Dispatch by manifest version before confirmation or execution. A version-2 dry run may remain offline without a capsule; a version-2 write run requires an explicit validated capsule and prepared plan.
2. Check stored-unit identity once across the whole release, using the lexer-normalized owner/type/name. Distinct quoted identifiers remain distinct; spec and body remain separate units.
3. Use the migration profile for both feature preparation's read-only capture and execution. APEX app preparation retains its own environment profile. Different schemas on the same database are valid targets.
4. Structural preflight must evaluate ordered supported effects against a complete selected scope, including prerequisites, namespaces, dependencies and direct-access evidence. Do not label a partial inventory as a complete owner inventory or relax legacy preflight to accept one.
5. Keep frozen source drivers environment-neutral. Generate a complete per-unit compiler-setting prologue from the prepared target plan immediately before each applied unit; hash it as target-plan/execution evidence.
6. Extend the ignored local index to schema 2. Preserve strict schema-1 reading and migrate under the existing atomic owned-writer transaction, retaining the original bytes and digest. Old attempts/evidence remain historical.
7. Distinguish possible writes from verification: no-op checkpoints create no write attempt but do create a durable checkpoint-verification receipt. All checkpoint modes must check unresolved occupancy.
8. Use an OS-backed local execution lease to refuse concurrent writers. Recovery of attempting requires an unavailable old lease plus explicit terminal-execution reconciliation; a free lease or a PID alone never proves an orphaned SQLcl/database operation has ended.
9. Cleanup requires a complete verified production rollout, all checkpoint verifications including no-ops, successful app/ORDS/data steps, and no unresolved attempt or run. Individual write attempts are insufficient.
10. Before allowing F10 promotion, remove environment-specific aliases from unreleased version-2 SQL/ORDS step definitions. Resolve their logical schema through the selected environment during preparation. Never silently ignore an explicitly supplied connection or login.

### Local state and interface contract

Keep existing attempt fields and terminal-history rules. Schema 2 adds:

- checkpointVerifications: verification UUID, run UUID, environment, checkpoint, target scope, source commit, payload/engine/plan digests, mode (applied/no-op/recovery), optional attempt UUID, verified-at time, hashed evidence, object seconds and session count.
- recoveryLinks: old attempt UUID, new verification UUID, reconciliation evidence reference and timestamp. Resolve old attempts through validated links; retain their original attempting/unknown state and evidence. Existing schema-1 recoveredBy links remain readable.
- rollouts: run UUID, environment, source/payload/engine/plan identities, target scopes, state (running/verified/failed/unknown/not-started), separate databaseState, ordered step outcomes and receipt hashes, checkpoint verification UUIDs, budget, and final report hash.
- migrationProvenance: original schema-1 index hash and private retained copy under ignored releases/.local-state-history/. A malformed or duplicate-key index refuses without mutation.

The strict schema-2 top-level keys are schemaVersion, attempts, cleanupHistory,
checkpointVerifications, recoveryLinks, rollouts and migrationProvenance.
Target plans move to schema 2 for the new structural/settings/binding records;
old plans require fresh preparation rather than an automatic approval upgrade.

Introduce these interfaces; use existing QueryCheck, Target and FeatureCheckpoint models:

    feature_manifest.validate_release_units(checkpoints: Sequence[FeatureCheckpoint]) -> None
    feature_preflight.required_scope(checkpoint: FeatureCheckpoint) -> SelectedScope
    feature_preflight.prepare_checkpoint(checkpoint: FeatureCheckpoint, state: Mapping,
                                        earlier_effects: Sequence[Mapping]) -> StructuralPlan
    release_ownership.target_writer_lease(repo_root: Path, target_scope: Mapping, *,
                                          run_id: str) -> ContextManager[TargetWriterLease]
    release_state.assert_checkpoint_allowed(repo_root: Path, capsule: ReleaseCapsule,
                                           plan: TargetPlan, checkpoint: int, *,
                                           run_id: str, lease: TargetWriterLease) -> None
    release_state.record_attempt(repo_root: Path, capsule: ReleaseCapsule, plan: TargetPlan,
                                 checkpoint: int, *, run_id: str,
                                 lease: TargetWriterLease) -> str
    release_state.record_checkpoint_verification(repo_root: Path, capsule: ReleaseCapsule,
                                                plan: TargetPlan, checkpoint: int, *,
                                                run_id: str, attempt_id: str | None,
                                                lease: TargetWriterLease,
                                                evidence: Sequence[str], metrics: Mapping) -> str
    release_state.start_rollout(repo_root: Path, capsule: ReleaseCapsule, plan: TargetPlan) -> str
    release_state.finish_rollout(repo_root: Path, run_id: str, *, outcome: Mapping) -> None

SelectedScope has owner: str, object_keys: tuple[ObjectKey, ...],
prerequisite_keys: tuple[ObjectKey, ...], and sections: tuple[str, ...].
StructuralPlan has scope: SelectedScope, expected_before_sha256: str,
effects_sha256: str, preconditions/postconditions: tuple[QueryCheck, ...],
compile_units: tuple[tuple[str, str, str, bool], ...], and
prior_checkpoints: tuple[int, ...]. Serialize strict JSON records into the
target plan; load them as data and revalidate them. Future verification UUIDs
are execution evidence, not values that preparation can know in advance.

Extend execute_checkpoint with a required keyword run_id supplied by the
version-2 orchestrator. Direct internal callers and tests must start an actual
local rollout record first. These are internal version-2 API changes; update
all direct callers and fixtures together. Extend CheckpointResult with verification_id:
str | None (default None for compatibility with legacy test doubles).

## Finding coverage and order

| Task | Finding | Depends on |
| --- | --- | --- |
| 0 | Preserve baseline and repair evidence | — |
| 1 | F1 dispatch; F9 global unit uniqueness | 0 |
| 2 | F6 multi-schema; F7 migration profiles | 1 |
| 3 | F2 focused structural preflight | 2 |
| 4 | F8 complete target compiler settings | 2 |
| 5 | F5 execution ownership and interrupted recovery | 2 |
| 6 | F3 no-op occupancy, verification and recovery links | 5 |
| 7 | F4 whole-release completion and cleanup, including no-ops | 6 |
| 8 | F10 data/ORDS promotion and environment binding | 3, 7 |
| 9 | F11 second-schema scaffolding | 0 |
| 10 | F12 bounded identifier-derived paths | 0 |
| 11 | Whole-candidate review and qualification | 1–10 |

## Review focus

- A version-2 manifest begins with a valid write step but omits --capsule: Task 1 must refuse before that first write or confirmation.
- A later statement depends on an absent table/column, or on an object created by an earlier checkpoint: Task 3 must refuse the former before any DDL and accept only the verified planned transition for the latter.
- A process dies after recording attempting, or a retry is entirely no-op: Tasks 5–7 must preserve occupancy and require explicit reconciliation, then record completion without inventing a write.
- Staging and production use different users/aliases, including a separate migration owner and ORDS owner: Tasks 2 and 8 must bind each environment independently while keeping payload bytes identical.
- Compiler flags differ per existing unit and names contain long Unicode/quoted text: Tasks 4 and 10 must preserve behavior, identity, and readable evidence without session leakage or oversized filenames.

---

### Task 0: Preserve the reviewed implementation and establish repair evidence

**Files:** Read the spec, findings, current plan, AGENTS.md/project rules, and docs/known-limitations.md. Create ignored scratch/feature-release-remediation/ evidence only.

- [ ] Record branch, HEAD, Git status and a content-hash inventory of the existing uncommitted implementation. Reviewed HEAD is e48b7053c53b05e014a30d511c1f399e880460ec; it does not include the runtime diff.
- [ ] Recheck PR #41 and upstream state read-only before implementation. Review intervening changes if the candidate moved; preserve the current worktree rather than resetting it.
- [ ] Record that F1–F12 are open and that prior green tests do not cover them. Save each new red/green transcript and a task ledger under the ignored evidence directory.
- [ ] Keep the test harness's real-SQLcl blocker active. Baseline tests already have recorded evidence; repeat only affected checks until the final whole-suite gate.

### Task 1: Close version-2 dispatch bypasses and reject duplicate release units — F1, F9

**Files:** scripts/rollout.py, scripts/feature_manifest.py, scripts/release_capsule.py; tests/test_rollout.py, tests/test_feature_manifest.py, tests/test_release_capsule.py, tests/test_feature_rollout.py.

**Interfaces:** Add validate_release_units above. Keep run_rollout's public defaults and version-1 route. load_manifest, capsule construction and capsule loading all enforce the same global identity rule.

- [ ] Add test_v2_without_capsule_refuses_before_any_step: both a SQL-only production manifest and a SQL-before-feature manifest must refuse with zero confirmation, target observation, SQLcl or executor calls.
- [ ] Add positive tests for unchanged version-1 execution and offline version-2 dry run without .env/SQLcl. A missing version-2 capsule prints the freeze/prepare/run commands and exits 2 before possible writes.
- [ ] Add test_release_rejects_duplicate_units_across_checkpoints for identical/different bytes, same/different feature paths and repeated paths. Permit different owners, spec versus body, and distinct quoted-case names.
- [ ] Run the new tests and record the expected failures; implement dispatch based on the parsed schema version and whole-release uniqueness. Reject inconsistent loaded capsule checkpoint metadata too.
- [ ] Run: PYTHONPATH=tests:. python3 -m unittest -v test_rollout test_feature_manifest test_release_capsule test_feature_rollout

### Task 2: Prepare the actual migration target and allow several schemas — F6, F7

**Files:** scripts/feature_release.py; tests/test_feature_prepare.py, tests/test_feature_runtime.py, tests/test_db_targets.py, tests/test_verify_checks.py, tests/test_read_only_query.py.

**Interfaces:** Keep prepare_target/load_target_plan/capture_selected_state signatures. Feature schema target records must resolve through resolve_target(..., operation='migration') for both capture and execution. Captures remain read-only.

- [ ] Add test_prepare_multiple_schemas_in_one_database: APP_DATA then APP_CODE, same database/container/edition, distinct logins/aliases, must prepare and execute through their own profiles.
- [ ] Add owner-login and acts-as-schema cases with STAGING_/PROD_MIGRATION_* triples different from ordinary profiles. Assert the capture session and writer both match the intended migration target.
- [ ] Test conflicting observations for the same physical schema/edition, changed profiles after preparation, incomplete triples and a schema absent from the migration profile: refuse before writes with no fallback.
- [ ] Record failing regressions, fix consistency grouping so different schemas are not a conflict, and bind each complete observed migration identity. Keep app target preparation independent.
- [ ] Run: PYTHONPATH=tests:. python3 -m unittest -v test_db_targets test_verify_checks test_read_only_query test_feature_prepare test_feature_runtime

### Task 3: Restore focused structural preflight before any DDL — F2

**Files:** Create scripts/feature_preflight.py and tests/test_feature_preflight.py. Modify scripts/feature_manifest.py, scripts/feature_release.py, scripts/compare_schema.py and scripts/compare_env_catalog.sql only where selected capture needs additional scope. Extend existing prepare/runtime/catalog tests and capsule engine dependency tests.

**Interfaces:** Implement SelectedScope, StructuralPlan, required_scope and prepare_checkpoint above. Preserve legacy migration_checks.preflight's full-owner coverage contract.

- [ ] Add test_later_missing_index_table_refuses_before_first_create using CREATE TABLE EARLY followed by an index on MISSING_TABLE. Preparation must identify the missing prerequisite; execution must make zero apply calls/attempt records.
- [ ] Add missing indexed-column, occupied namespace, unsupported dependency, missing direct grant/synonym-target, and newly invalid required-dependent cases. No SELECT 1 postcondition may waive a statically detectable conflict.
- [ ] Add positive ordered cases: create table then index in one checkpoint; table in an earlier checkpoint then index in the next; same-schema view dependencies; ordinary known synonym/access limits unchanged.
- [ ] Derive scope from names AND referenced tables/columns/namespaces/dependents, not just created object names. Capture only that explicit scope and distinguish complete selected coverage from complete owner inventory.
- [ ] Simulate deterministic earlier selected effects by schema when preparing later checkpoint guards. Bind required prior checkpoint numbers and effect digests; at execution require their matching verification UUIDs from the same run. Never silently refresh an approved before-state after execution starts.
- [ ] Generate validated structural QueryChecks and rerun them in the apply session before its first payload include. Verify selected effects and required dependents afterward; no schema-wide recompile.
- [ ] Bind the new module/templates to engineDigest. Run: PYTHONPATH=tests:. python3 -m unittest -v test_feature_preflight test_feature_prepare test_feature_runtime test_compare_env test_migration_checks test_check_conflicts test_release_capsule

### Task 4: Apply the complete prepared settings before every stored unit — F8

**Files:** scripts/feature_release.py, scripts/release_capsule.py as needed; tests/test_feature_runtime.py, tests/test_feature_prepare.py, tests/test_release_capsule.py, tests/test_baseline_settings.py.

**Interfaces:** Extend each source guard with canonical settings-prologue bytes/hash derived from validated applySettings. Keep payloadDigest environment-neutral; the prologue belongs to targetPlanDigest and execution evidence.

- [ ] Add test_omitted_settings_use_prepared_target_values for a changed existing package with custom PLSQL_CCFLAGS and code type. A fake SQLcl must model session-setting effects, not return unconditional successful postchecks.
- [ ] Cover partial overrides, spec/body with different settings, two consecutive units with conflicting settings, and a new unit without a complete setting set. No value may leak from a preceding input.
- [ ] Record failures; stage a full trusted settings prologue immediately before each non-no-op unit, using existing baseline setting rendering/validation. Preserve and hash original readable source and frozen drivers.
- [ ] Assert the emitted prologue matches its prepared hash before SQLcl starts, and exact settings/source checks still run afterward. A changed prologue/plan refuses before writes.
- [ ] Run: PYTHONPATH=tests:. python3 -m unittest -v test_feature_runtime test_feature_prepare test_release_capsule test_baseline_settings test_sqlcl_transport

### Task 5: Support explicit recovery after a writer terminates — F5

**Files:** Create scripts/release_ownership.py and tests/test_release_ownership.py. Modify scripts/release_state.py, scripts/feature_release.py, scripts/rollout.py, .gitignore, recovery CLI/docs and their tests.

**Interfaces:** Implement TargetWriterLease/target_writer_lease using nonblocking OS locks on ordinary private local files, with token, target scope and execution identity. Hold the lease from occupancy validation through terminal persistence. Keep the existing short index-writer lock for atomic mutations. Introduce schema-2 validation/upgrade and start_rollout/finish_rollout primitives here so Task 6 has a real run record; success without the required verification/step evidence must refuse.

Extend prepare_target with terminal_ack: str | None = None, and run_rollout
with recovery_confirm: Callable[[str], str] | None = None. The CLI supplies its
terminal-input adapter; a programmatic recovery call without an acknowledgment
refuses. No recovery code reads input behind an uninjectable low-level API.

- [ ] Add separate-process tests: an active owner blocks normal and recovery runs; terminating the owner releases the kernel lease; a stale file/PID alone neither proves a live owner nor authorizes recovery. Exercise native Windows and POSIX implementations.
- [ ] Add test_prepare_recovery_accepts_reconciled_attempting and preserve the existing unknown route. An attempting record must remain recoverable after a crash without hand-editing the index.
- [ ] Require exact typed RECONCILE <attempt-uuid> acknowledgment after displaying scope, evidence, and the assertion that the original SQLcl/database operation has ended. Refuse if a local lease is active, the acknowledgment is absent/wrong, or terminal-execution reconciliation is unavailable. Lease availability alone is not SQLcl terminal proof.
- [ ] Capture the live selected partial state read-only; bind its fingerprint, old attempt UUID/state and reconciliation evidence into the new recovery plan. Do not change the old attempt to success or clear its evidence.
- [ ] At execution, reacquire ownership, revalidate that recovery binding and observed state, and refuse any intervening owner/attempt change.
- [ ] Add the ownership module to engineDigest and ignore only its generated local files. Run: PYTHONPATH=tests:. python3 -m unittest -v test_release_ownership test_release_state test_feature_prepare test_feature_runtime test_sqlcl_session test_sqlcl_transcript test_windows_support

### Task 6: Give no-ops durable verification and enforce occupancy universally — F3

**Files:** scripts/release_state.py, scripts/feature_release.py, scripts/rollout.py; tests/test_release_state.py, tests/test_feature_runtime.py, tests/test_feature_prepare.py, tests/test_feature_rollout.py, tests/test_release_promotion.py.

**Interfaces:** Consume Task 5's schema-2 store, ownership and run primitives. Implement assert_checkpoint_allowed, the owned record_attempt signature and record_checkpoint_verification above, including strict recoveryLinks. Retain legacy schema-1 reads and historical recoveredBy relationships.

- [ ] Add test_noop_cannot_bypass_unknown_or_attempting: normal prepare/run may read state but must not produce success, verification or staging proof while overlapping unresolved occupancy exists.
- [ ] Add test_noop_recovery_links_verified_observation: explicit reconciled recovery verifies exact state/checks, records a no-op verification with no SQLcl apply/write attempt, and appends a validated recovery link resolving the old attempt.
- [ ] Add a clean no-op case producing a durable verification; test mixed applied/no-op checkpoints, missing/corrupt evidence, concurrent runs, and failures before/after postchecks.
- [ ] Implement schema-1 upgrade atomically under the owned index writer; retain original bytes/digest before replacement. Corruption, duplicate IDs, broken links or failed upgrade leave original evidence intact.
- [ ] Call the same occupancy/ownership checks for every checkpoint before considering noOp; persist verification only after all scoped source/settings/validity/check evidence is verified.
- [ ] Run: PYTHONPATH=tests:. python3 -m unittest -v test_release_state test_release_promotion test_feature_prepare test_feature_runtime test_feature_rollout test_migration_receipts
- [ ] Inspect the resulting state: old evidence stays byte-identical, links identify the precise verified checkpoint/scope, and no success run lacks mandatory verification references.

### Task 7: Require complete production evidence for cleanup — F4

**Files:** scripts/release_state.py, scripts/rollout.py; create tests/test_release_completion.py; extend tests/test_release_promotion.py and tests/test_feature_rollout.py.

**Interfaces:** Consume and finish integrating Task 5's start_rollout/finish_rollout primitives and Task 6's verification receipts. The orchestrator supplies run_id to every checkpoint and persists all ordered step outcomes. A terminal success record contains every checkpoint verification and every step receipt hash.

- [ ] Add tests that successful feature writes followed by failed/interrupted app, ORDS, data, verification or pause steps cannot authorize cleanup; preserve the capsule and all recovery evidence.
- [ ] Add successful all-no-op and mixed no-op/applied production cases: cleanup preview/apply is eligible only after the complete production run verifies.
- [ ] Cover missing/edited final report or step receipts, missing checkpoint verification, wrong plan/environment/engine, budget failure, a later unresolved run after an earlier success, and copy-only local evidence.
- [ ] Make start_rollout revalidate the capsule and persist running under the same index transaction used by cleanup eligibility. A cleanup/start race must either retain an active capsule or refuse a stale start after deletion.
- [ ] Persist failure/unknown outcomes honestly, independently of databaseState. A crash leaves a nonterminal run that blocks cleanup. Reconcile through retained step-specific live/receipt evidence; do not replay completed DDL or turn failed history into success merely to obtain cleanup eligibility. If completion cannot be proved, retain the capsule.
- [ ] Make cleanup consult complete production success plus all unresolved references. Retain compact completion/checkpoint/recovery records and review diffs; deletion history lists actual removed paths.
- [ ] Keep staging proof portable as data with embedded canonical completion/step evidence; do not require a production checkout to possess the staging checkout's local index or treat the report as a signature.
- [ ] Run: PYTHONPATH=tests:. python3 -m unittest -v test_release_completion test_release_promotion test_release_state test_feature_rollout test_rollout

### Task 8: Permit qualified data/ORDS promotion with correct environment targets — F10

**Files:** scripts/rollout.py, scripts/release_capsule.py, scripts/feature_release.py, scripts/release_state.py; tests/test_feature_rollout.py, tests/test_release_capsule.py, tests/test_release_promotion.py, tests/test_rollout.py; guide/example/spec amendments.

**Interfaces:** Add classify_auxiliary_step(step: Mapping, frozen_source: bytes) -> str, returning data, ords or uncovered-object. Version-2 SQL/ORDS targets become logical schema references:

    {"type":"sql-script","file":"scripts/data.sql","schema":"APP_CODE"}
    {"type":"ords-import","file":"database/REST_OWNER/ords/schema.sql","schema":"REST_OWNER","excludeModules":[]}

Resolve SQL-script through the selected environment's migration profile; resolve
ORDS through the selected environment profile and require the actual REST owner
login. Persist targets under step:<manifest-number> in TargetPlan with profile
binding and complete observed identity, and revalidate them before writes.
Version-1 explicit connection/expectedUser behavior remains unchanged.

- [ ] Add successful staging/production cases with feature objects plus pure INSERT/UPDATE/DELETE/MERGE and separately validated ORDS imports; assert independent durations and complete feature-object coverage.
- [ ] Add tests where staging/prod aliases, logins and descriptors differ: payloadDigest stays equal, targetPlanDigest differs, and production never reuses the staging alias or identity.
- [ ] Use the same owned-target occupancy and terminal-state rules for SQL/ORDS writes. Preparation captures their complete target identities read-only; execution must not merely observe and accept a new identity for the first time.
- [ ] Reject unreleased version-2 explicit connection/expectedUser fields with an actionable conversion message before capture/apply; never ignore them silently. Recheck release provenance at Task 0: if a version-2 runtime contract has shipped meanwhile, version the refined contract instead of silently reinterpreting it.
- [ ] Classify only lexically validated static top-level DML plus explicit COMMIT/ROLLBACK as data. DDL, opaque PL/SQL, arbitrary calls and unclassified forms remain uncovered object work. Recognized ORDS import definitions remain their separate phase, with existing exclusions/OAuth/owner protections.
- [ ] Count only actual uncovered object steps in excludedObjectSteps. Record each auxiliary step's phase/classification reason in reports and bind it to frozen bytes/engine. Do not claim the classification proves absence of trigger, autonomous, or external effects.
- [ ] Require complete whole-rollout success and matching phase coverage in stage proof. Real legacy/object work outside feature checkpoints must still disqualify fast production promotion.
- [ ] Update the guide, example and original spec's version-2 target-field contract. Changed engine/plan/report semantics invalidate old candidate capsules/proofs; require re-freeze, prepare and staging again.
- [ ] Run: PYTHONPATH=tests:. python3 -m unittest -v test_feature_rollout test_release_capsule test_release_promotion test_rollout test_ords_contracts test_db_targets test_verify_checks

### Task 9: Initialize another schema without overwriting feature files — F11

**Files:** scripts/feature_cli.py; tests/test_feature_cli.py, tests/test_team_cli.py.

**Interfaces:** Keep _init_feature(...) -> tuple[Path, ...]; return only newly created files.

- [ ] Add test_init_second_schema_preserves_shared_readme: initialize APP_CODE, edit README, initialize APP_DATA, and assert README bytes/first checks unchanged while only the second schema scaffold is created.
- [ ] Preserve refusal for existing target-schema checks, symlink/reparse paths and non-file README. If the README is absent, create it; an existing ordinary README is retained.
- [ ] Inject a second-file creation failure and prove rollback deletes only files owned by this invocation. Exercise both wrappers and spaces/brackets/non-ASCII checkout paths.
- [ ] Run: PYTHONPATH=tests:. python3 -m unittest -v test_feature_cli test_team_cli

### Task 10: Bound identifier-derived artifact paths — F12

**Files:** scripts/feature_sources.py and capture metadata/path helpers as needed; tests/test_feature_diffs.py, tests/test_feature_sources.py, tests/test_feature_prepare.py.

**Interfaces:** Add _unit_artifact_stem(unit: tuple[str, str]) -> str producing a deterministic ASCII component of at most 96 bytes. Include bounded type/name hints plus hashes of the exact case-sensitive UTF-8 identity and review content.

- [ ] Add real-filesystem tests for an accepted 128-character ASCII name, long quoted Unicode names within the identifier byte limit, different names sharing a truncated slug, and case-distinct identifiers.
- [ ] Ensure review/diff generation and target preparation succeed; metadata/diff headers retain the exact full identifier and source hashes. Every generated component remains within its bound and distinct identities cannot collide.
- [ ] Audit other identifier-derived capture/source filename components for the same input class. Preserve existing safe short source paths and valid retained metadata mappings; do not silently rename existing feature source/baselines.
- [ ] Keep content-namespaced non-overwriting same-day reviews and WALKTHROUGH preservation. Run: PYTHONPATH=tests:. python3 -m unittest -v test_feature_sources test_feature_diffs test_feature_prepare
- [ ] Run those path cases on native Windows/macOS during final qualification; a Linux-only path pass does not establish Windows parity.

### Task 11: Audit every finding and qualify the final candidate

**Files:** Update the repair ledger, docs/feature-releases.md, docs/known-limitations.md only for deliberate limits, relevant agent guidance, and a new template-only review result. Keep the historical qualification report factual.

- [ ] Map F1–F12 to the exact new regressions and final code; inspect each red/green transcript. Review the complete changed branch inline, including state upgrades, ownership interruption paths and version-1 compatibility.
- [ ] Run focused suites after their final affected change; then python3 scripts/pre_push_check.py --all, the full offline suite python3 scripts/ci_run_tests.py --jobs 8, and git diff --check once for the final candidate. Repeat only failed/affected checks after later edits.
- [ ] Verify Python 3.10 and Bash/PowerShell argument/exit parity. Native Windows must exercise file locking, owner termination, path bounds and cleanup races; native macOS must exercise ownership and exclusive installation. Mark unavailable platforms as unverified.
- [ ] Recheck engine file closure, selected-source/payload hashes, target-specific settings and target-plan hashes. Prove no cleanup or state-upgrade test can erase unresolved evidence.
- [ ] If a commit/push is separately authorized, run the required pre-push gate and verify hosted checks at that exact pushed SHA. PR #41's documentation checks do not qualify runtime repairs.
- [ ] Only after a named-target request, qualify a disposable staging capsule with real owner and acts-as-schema profiles, two schemas, custom compiler flags, recovery/no-op completion, data and ORDS phases. Read final source/settings/validity back; measure small/large object budgets separately from other phases.
- [ ] Report local tests, hosted platforms, live qualification, PR/merge state and downstream adoption as distinct evidence. No runtime performance/deployment claim follows from offline tests alone.

## Completion criteria

Every F1–F12 regression is fixed and the final appropriate local checks pass.
No version-2 write can reach the legacy executor; selected dependencies and
target identities are proved before writes; every checkpoint and full rollout
has truthful durable completion/recovery evidence; cleanup uses that evidence.
The report must identify any unavailable hosted/native/live gate explicitly.
No downstream upgrade, conversion, merge, or production execution is part of
this repair plan.
