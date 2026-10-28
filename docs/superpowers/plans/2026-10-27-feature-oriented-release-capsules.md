# Feature Source and Release Capsule Implementation Plan

> **For agentic workers:** Execute task by task, inline. Use superpowers:executing-plans when the checkout's workflow selection enables it; otherwise follow the same checked steps directly. The user explicitly prohibited subagents. Do not install or enable a workflow pack. All checkboxes describe future work; this PR implements documentation only.

**Goal:** Replace revision-folder authoring for new work with editable feature sources, reviewable whole-package diffs, and a frozen staged payload whose database-object phase meets a measured 120-second target or reviewed budget up to 300 seconds.

**Architecture:** A feature loader validates selected current sources. A deterministic capsule freezes them, while separate environment plans hold live target guards and diffs. The existing rollout orchestrator delegates feature checkpoints to a focused executor and keeps legacy execution compatible.

**Tech Stack:** Python 3.10+ standard library, existing SQLcl 26.3+ capture/session helpers, Bash and PowerShell, unittest fixtures/fake SQLcl, Oracle/APEX 26.1 compatibility.

**Spec:** [Mutable feature sources and frozen release capsules](../specs/2026-10-27-feature-oriented-release-capsules-design.md).

## Global Constraints

- This PR adds a spec and plan only. Do not execute implementation tasks, migrations, exports, imports, upgrades, downstream conversion, or live rehearsal from this plan without the corresponding work request.
- Implement inline; do not spawn subagents. Future commit suggestions do not authorize extra pushes or merges.
- Python 3.10+, standard library; SQLcl 26.3+ for capture/prepare; preserve APEX 26.1 application behavior.
- Mutable source: `features/<feature>/<SCHEMA>/...`; mutable manifest: `releases/current.json`; no new revision directories.
- Selected inputs must match committed Git bytes before staging. Unrelated worktree changes are preserved.
- Version-2 budget defaults to 120 seconds and accepts integers 1..300. Preparation, APEX, ORDS, data work, and pauses are reported separately.
- Whole package source is stored as complete spec/body files. One final selected unit per owner/type/name; no silent conflict resolution.
- `payloadDigest` is shared across staging/production; `targetPlanDigest` is environment-specific. Keep the engine digest bound.
- Keep existing schema-1 checks, read-only restrictions, transport protections, exact source/settings verification, and legacy formats.
- No database ledger/mutex/roster. Local attempt state survives scratch cleanup in ignored `releases/.local-state.json`.
- No hard kill to enforce an aggregate budget; Oracle DDL may commit before failure.
- Observe target database version/compatibility before choosing version-dependent SQL. Reuse existing portable SQL; do not add a database-version setting.
- All new source/JSON/SQL uses UTF-8/LF. Keep project source and credentials out of template examples.

## Review Focus

1. A new package file appears wholly added in Git: captured-DEV and actual-target diffs must still show the real replacement (Task 2/4).
2. Production uses a different descriptor/identity from staging: shared payload must match while target plans differ (Task 3/5).
3. Scratch is deleted after a possible write: the persistent local index must refuse blind retry (Task 5).
4. SQLcl alters source containing whitespace-only lines, trailing hyphens, Unicode, or quotes: exact final source must be proved (Task 2/6).
5. A budget is exceeded after correct SQL: record verified database state separately from a failed promotion-time gate (Task 5/6).

---

## File responsibilities and stable interfaces

Create these focused modules; keep unrelated legacy refactoring out:

| Module | Responsibility |
| --- | --- |
| `scripts/feature_manifest.py` | Paths, source classification, check loading, owner/order/conflict validation |
| `scripts/feature_sources.py` | Guarded whole-package capture, baseline retention, readable source diffs |
| `scripts/release_capsule.py` | Deterministic freezing, digests, source/driver mapping, safe loading |
| `scripts/release_state.py` | Persistent local attempt/receipt transitions, stage proof, cleanup eligibility |
| `scripts/feature_release.py` | Selected-target preparation, focused execution, per-phase metrics |
| `scripts/feature_cli.py` | Feature scaffold/capture/diff/cleanup argument handling |
| Existing `scripts/rollout.py` | Version-2 orchestration and promotion; existing version-1 route remains intact |

Shared frozen dataclasses:

- `FeatureInput(path: str, source: bytes, sha256: str, unit: tuple[str, str, str] | None, category: str)`; unit is owner/type/name; category is `stored-source` or `ddl`.
- `FeatureCheckpoint(schema: str, inputs: tuple[FeatureInput, ...], preconditions: tuple[QueryCheck, ...], postconditions: tuple[QueryCheck, ...], object_keys: tuple[tuple[str, str], ...])` in `feature_manifest.py`.
- `ReleaseCapsule(root: Path, manifest_sha256: str, payload_digest: str, engine_digest: str, source_commit: str, checkpoints: tuple[FeatureCheckpoint, ...], input_hashes: tuple[dict, ...])` in `release_capsule.py`.
- `TargetPlan(environment: str, payload_digest: str, plan_digest: str, targets: dict[str, dict], checkpoint_guards: tuple[dict, ...], review_paths: tuple[str, ...], recovery_attempt: str | None)` in `feature_release.py`. `targets` holds complete observed identity and descriptor hashes; guards contain expected source/settings/metadata and validated checks for each numbered checkpoint.
- `CheckpointResult(exit_code: int, database_state: str, object_seconds: float, session_count: int, evidence_paths: tuple[str, ...], message: str)` in `feature_release.py`; state is `not-started`, `verified`, or `unknown`.

Use the existing `QueryCheck`, `Target`, source projections, SQL/check validators,
and `run_sqlcl`; do not define incompatible parallel target or query models.
Use deferred/type-checking-only cross-module annotations to keep state,
capsule, and execution imports acyclic.

### Task 1: Load mutable feature inputs and version-2 manifests

**Files:** create `scripts/feature_manifest.py`, `tests/test_feature_manifest.py`; modify `scripts/rollout.py`, `tests/test_rollout.py`.

**Interfaces:**
- `load_feature_checkpoint(repo_root: Path, step: Mapping) -> FeatureCheckpoint`.
- `analysis_migration(checkpoint: FeatureCheckpoint) -> Migration`: in-memory adapter for `analyze_batch`/`compiled_units` only; creates no dated folders or legacy receipts.
- Extend `rollout.load_manifest` and `validate_step` with a version argument defaulting to 1, preserving old callers.

- [ ] Write failing tests for version 2 with default budget 120, explicit 300, and rejection of 0/301/bool/string. Pin unchanged version-1 valid/invalid fixtures.
- [ ] Test ordered multi-feature inputs in one schema checkpoint; implicit schema `checks.json`; explicit nonempty `checks` override; namespaced IDs; missing checks; and no-check DDL refusal.
- [ ] Test duplicate owner/type/name across files/features, mismatched owner/schema, traversal, symlink/reparse paths, unknown keys, outside-feature inputs, malformed UTF-8/CRLF, and SQLcl injection before any connection.
- [ ] Classify full stored-source files as one unit plus only validated compiler-setting prefixes. Use existing `validate_migration` SQL-only and `migration_checks.analyze_batch` logic; refuse runtime DML, arbitrary dynamic/opaque blocks, and unbounded recompile in the fast path.
- [ ] Run `PYTHONPATH=tests:. python3 -m unittest -v test_feature_manifest test_rollout` before and after implementation; new tests must first fail for missing behavior.
- [ ] Implement the loader and pure analysis adapter. Do not relax legacy folder/date validation.
- [ ] Future commit: `feat: validate feature source checkpoints and rollout v2`.

**Done:** an offline validated feature checkpoint is usable by capsule generation and no database call occurred.

### Task 2: Capture complete packages and retain useful review diffs

**Files:** create `scripts/feature_sources.py`, `tests/test_feature_sources.py`, `tests/test_feature_diffs.py`; reuse `scripts/new_migration.py`, `scripts/baseline.py`, and `scripts/migration_diff.py` helpers without changing legacy defaults.

**Interfaces:**
- `capture_package(repo_root: Path, feature: str, schema: str, package: str, *, environ: Mapping[str, str], refresh: bool = False) -> tuple[Path, ...]`.
- `write_source_review(repo_root: Path, feature: str, schema: str, unit: tuple[str, str], before: str, after: str, *, identity: Mapping[str, str], baseline_kind: str, payload_digest: str | None, day: str) -> tuple[Path, Path]`: returns unified diff and `review.json` paths.
- `diff_captured_package(repo_root: Path, feature: str, schema: str, *, day: str) -> tuple[Path, ...]`.

- [ ] Test `--package` reads complete spec and body with exact owner/type/name/settings, supports a spec-only package, and writes stable source paths with no revision folder.
- [ ] Test a deliberately stale mirror is ignored; first-time Git additions still produce the captured-DEV line diff; missing capture baseline refuses instead of comparing with a mirror.
- [ ] Test default capture refuses edited existing source and `refresh=True` explicitly recaptures; multi-unit capture failure leaves existing feature files byte-identical.
- [ ] Test whitespace-only lines, trailing hyphens, Unicode/quoted identifiers, dollar signs, and spec/body distinction. Hash exact reviewed source; normalize only existing documented source-header projections.
- [ ] Use the existing guarded `baseline._capture` source/settings sections with selected names and `new_migration` source rendering/check helpers. Keep temporary baseline copies in stable ignored `scratch/feature-source/<feature>/<schema>/`; never replace the mirror.
- [ ] Implement content/digest-namespaced `ai_generate/YYYY-MM-DD/feature-diffs/` output. Include identity, before/after hashes, baseline kind, and unit; preserve existing same-day reports and `WALKTHROUGH.md`.
- [ ] Run `PYTHONPATH=tests:. python3 -m unittest -v test_feature_sources test_feature_diffs test_new_migration test_migration_diff`.
- [ ] Future commit: `feat: capture whole feature packages with review diffs`.

**Done:** a reviewer sees full source plus genuine before/after differences even on the first feature capture.

### Task 3: Freeze a deterministic environment-neutral capsule

**Files:** create `scripts/release_capsule.py`, `tests/test_release_capsule.py`; reuse `scripts/directory_install.py` exclusive installation and rollout input enumeration.

**Interfaces:**
- `build_capsule(repo_root: Path, manifest_path: Path, checkpoints: Sequence[FeatureCheckpoint], shared_inputs: Mapping[str, bytes]) -> ReleaseCapsule`.
- `load_capsule(repo_root: Path, capsule_dir: Path) -> ReleaseCapsule`.
- `capsule_engine_digest(repo_root: Path) -> str`: hashes this workflow's six modules, `rollout.py`, and the existing SQLcl/check/source/transport helpers it calls; persist the exact ordered engine file list.

- [ ] Test identical committed input bytes yield identical payload digests and installed payload files; timestamps, environment labels, descriptors, and target capture must not change that digest.
- [ ] Test changing a package byte, check, shared APEX/ORDS source, source-to-driver mapping, manifest order, or engine file changes the appropriate digest.
- [ ] Test selected sources/manifest must match committed Git bytes; unrelated dirty files are allowed. Untracked/changed selected inputs refuse before capture/apply.
- [ ] Freeze every shared app/ORDS input using existing rollout enumeration, preserving exclusion and filename edge cases. Keep environment-specific descriptors in target plans.
- [ ] Generate transport-safe package delivery using existing `baseline._needs_clob_assembly`, `_clob_source_step`, and `_direct_source_step`; validate original unit metadata and hash generated wrappers. Arbitrary source-supplied dynamic blocks remain refused.
- [ ] Test occupied output, partial generation, path traversal, copied-artifact symlinks/reparse points, missing/extra files, and edited drivers fail without replacing a prior capsule. Load artifacts as data, never executable Python/shell.
- [ ] Run `PYTHONPATH=tests:. python3 -m unittest -v test_release_capsule test_directory_install test_rollout`.
- [ ] Future commit: `feat: freeze deterministic release capsule payloads`.

**Done:** one exact payload can move between environments while target guards remain separate.

### Task 4: Prepare selected-target guards and deployment diffs read-only

**Files:** create `scripts/feature_release.py`, `tests/test_feature_prepare.py`; add narrowly scoped helpers in `scripts/schema_catalog.py` only if existing selected-source/catalog capture cannot supply the required state.

**Interfaces:**
- `capture_selected_state(target: Target, checkpoint: FeatureCheckpoint, run_dir: Path) -> dict`: identity, exact selected source/settings, and affected structural metadata only.
- `prepare_target(repo_root: Path, capsule: ReleaseCapsule, environment: str, *, environ: Mapping[str, str], recovery_attempt: str | None = None) -> TargetPlan`.
- `load_target_plan(repo_root: Path, capsule: ReleaseCapsule, environment: str) -> TargetPlan`.

- [ ] Test prepare creates no apply driver invocation, DDL/DML, attempt marker, or success receipt. Intercept the SQLcl runner; preparation may issue only guarded metadata/source reads.
- [ ] Test target diffs compare actual staging/prod source with the proposed full source, including when DEV and target differ. Emit both baseline kinds with separate names and before hashes; a DEV capture guard must never become a production before-state guard.
- [ ] Test staging/prod share `payload_digest` but have different `plan_digest` for identity, before-source, and target descriptor changes. Reject incomplete identity or conflicting schema/edition.
- [ ] Prepare exact source-line/settings guards and explicit structural preconditions from selected objects; do not call unfiltered `capture_inventory` or full `compare-env`. Include affected dependency/access checks rather than silently losing legacy structural protection.
- [ ] Test an identical valid stored unit is a recorded no-op; changed or invalid source is checked/applied as planned. Never infer no-op DDL from a receipt or omit a changed package spec.
- [ ] Reuse `baseline._source_check_queries` and exact settings helpers. Bind every review artifact and guard query to the prepared target-plan digest.
- [ ] Run `PYTHONPATH=tests:. python3 -m unittest -v test_feature_prepare test_schema_catalog test_feature_diffs`.
- [ ] Future commit: `feat: prepare target guards and package deployment diffs`.

**Done:** the operator can review exactly what this environment will receive before entering the write window.

### Task 5: Persist attempts, staging proof, recovery, and safe cleanup

**Files:** create `scripts/release_state.py`, `tests/test_release_state.py`, `tests/test_release_promotion.py`; modify `.gitignore`.

**Interfaces:**
- `record_attempt(repo_root: Path, capsule: ReleaseCapsule, plan: TargetPlan, checkpoint: int) -> str`: returns an attempt UUID before any possible write.
- `finish_attempt(repo_root: Path, attempt_id: str, *, state: str, evidence: Sequence[str], metrics: Mapping) -> None`.
- `validate_stage_proof(capsule: ReleaseCapsule, report: Mapping) -> None`.
- `cleanup_capsule(repo_root: Path, payload_digest: str, *, apply: bool = False) -> dict`.

- [ ] Define strict local index schema 1: target scope, checkpoint/attempt UUID, source commit, payload/engine/plan digests, state, evidence references, timing, budget result, and recovery link. Validate duplicate keys, corrupt/incomplete entries, and target scope independently of aliases.
- [ ] Test atomic local updates and exclusive owned-writer protection; concurrent writers must refuse before writes. An orphaned local writer lock refuses until reconciliation; never guess from PID alone.
- [ ] Test scratch deletion after `attempting` still blocks blind retry/new overlapping release through `releases/.local-state.json`. It never locks mutable feature files permanently.
- [ ] Preserve existing narrow no-write proof semantics: known pre-payload connection/start refusal can unlock; payload marker, lost log, timeout, cancellation, or unknown evidence remains unresolved.
- [ ] Test production requires successful stage proof matching payload, engine, shared source hashes, complete object-budget coverage, and budget; changed target descriptor is allowed only with its own valid prepared plan.
- [ ] Test database verified + budget exceeded is retained as verified state with failed performance eligibility; do not mislabel committed SQL as unknown.
- [ ] Bind `--recover <attempt-id>` preparation to observed partial state and the old attempt. A new verified recovery links the old entry; old evidence is never rewritten as success.
- [ ] Test cleanup is dry-run by default, refuses unresolved/unverified capsules, preserves review files/local receipts, and records removed evidence paths honestly after `--yes`.
- [ ] Run `PYTHONPATH=tests:. python3 -m unittest -v test_release_state test_release_promotion test_migration_attempts test_migration_revision`.
- [ ] Future commit: `feat: retain capsule attempts and enforce staged promotion`.

**Done:** changing source or deleting scratch cannot turn an ambiguous write into a clean retry.

### Task 6: Execute fast schema checkpoints through the existing rollout

**Files:** extend `scripts/feature_release.py`, `scripts/rollout.py`; create `tests/test_feature_runtime.py`, `tests/test_feature_rollout.py`; retain legacy runtime fixtures.

**Interfaces:**
- `execute_checkpoint(repo_root: Path, capsule: ReleaseCapsule, plan: TargetPlan, checkpoint: int, *, environ: Mapping[str, str]) -> CheckpointResult`.
- Extend `run_rollout` with keyword defaults `prepare_only=False`, `capsule_path=None`, `stage_report_path=None`, `recovery_attempt=None`; old callers stay valid.
- Version-2 report adds payload/engine/target-plan digests, preparation time, object phase total/budget/coverage, per-checkpoint SQLcl session counts, and independent app/ORDS/data durations.

- [ ] Test missing/stale prepared plans refuse before writes; changed live target source/metadata between prepare and run refuses; wrong identity during any session fails.
- [ ] Reuse `migration_checks.run_checks` for read-only pre/post checks and `sqlcl_session.run_sqlcl` for apply. Reuse identity/compile guard generation from `migrate.py`; do not call `migrate.apply_batch` or its full-schema `_preflight_snapshot` on the feature path.
- [ ] Apply ordered final sources once per checkpoint in one apply session. Derive compile guards from raw validated units before trusted wrapper generation; verify exact stored source/settings and scoped validity afterward.
- [ ] Test one apply session for several package inputs, final source once per unit, explicit no-op units, required dependent compile checks, and no unrelated-schema invalid-object failure.
- [ ] Test full source preservation through fake SQLcl for Unicode/quotes/whitespace-only lines/trailing hyphens; missing completion markers, SQLcl's "created with compilation errors" warning-success output, and postcondition failure leave no success receipt. Preserve existing ordinary-warning policy.
- [ ] Test frozen payload or engine tampering during confirmation/step fails; production runs the staged payload and new production guards. Preserve existing app-deploy confirmation and byte-verification behavior.
- [ ] Measure revalidation/apply/check duration for each feature step. Test fake-clock 120/300-second budgets, verified overrun reporting, stop-before-next-object-write behavior, and app imports excluded from object budget.
- [ ] Report included/excluded steps and incomplete object-budget coverage when legacy/DBA object work remains; never claim whole-database performance from a subset.
- [ ] Run `PYTHONPATH=tests:. python3 -m unittest -v test_feature_runtime test_feature_rollout test_rollout test_migration_runtime test_migration_receipts`.
- [ ] Future commit: `feat: run focused feature checkpoints with phase timing`.

**Done:** feature releases avoid per-folder full inventories and apply sessions while retaining verifiable source and recovery.

### Task 7: Ship the simple CLI, upgrade protection, and adoption guide

**Files:** create `scripts/feature_cli.py`, `docs/feature-releases.md`, `docs/feature-release.example.json`, `tests/test_feature_cli.py`; modify `scripts/team.sh`, `scripts/team.ps1`, `scripts/rollout.sh`, `scripts/upgrade_template.py`, `template-manifest.json`, `README.md`, `AGENTS.md`, `CLAUDE.md`, `.agents/rules/agent-safety.md`, `docs/migration-rules.md`, `docs/daily-change-record.md`, `docs/known-limitations.md`, and the existing CLI/upgrade/manifest/documentation tests.

**Interfaces:** `feature_cli.main(argv: Sequence[str] | None = None, *, repo_root: Path, environ: Mapping[str, str] | None = None) -> int`.

- [ ] Implement `feature init`, `capture --package`, `diff`, and `clean-capsule`; add rollout `--prepare`, `--capsule`, `--stage-report`, and `--recover`. Refuse invalid combinations before connecting.
- [ ] Test offline init/diff/cleanup need no `.env`, SQLcl, or network. Capture accepts DEV only and resolves an explicit schema; no source overwrite without reviewed `--refresh`.
- [ ] Route Bash/PowerShell through the same Python implementation; preserve Windows Git Bash path handling, spaces/brackets/non-ASCII checkouts, and existing flags/exit codes.
- [ ] Protect every downstream `features/` and `releases/` path in `protected_project_path`. Mark the new guide/example template-owned; docs/superpowers stay template-only. Test upgrade preserves edited feature files, current manifest, local state, and unrelated changes.
- [ ] Follow the checkout's agent-document guidance and use writing-for-agents only when available/enabled. Explain mutable feature source, frozen capsules, readable package diffs, targeted checks, local-only receipt limits, budget scope, and legacy migration immutability during adoption.
- [ ] Document the later downstream conversion procedure: inventory/reconcile old attempts; derive final package sources once; keep DML separate; checksum-archive SQL/checks/receipts/attempt evidence; retire an entire converted legacy tree/index together; verify archive before removal. This guide performs no conversion automatically.
- [ ] Run `PYTHONPATH=tests:. python3 -m unittest -v test_feature_cli test_team_cli test_template_manifest test_upgrade_template test_documentation_contract` and `bash -n scripts/team.sh scripts/rollout.sh`.
- [ ] Future commit: `feat: expose feature release workflow and protect project sources`.

**Done:** the operator has a short source-edit/prepare/review/run workflow and upgrading cannot overwrite it.

### Task 8: Qualify the exact branch and hand off the production gate

**Files:** update the new guide and a template-only qualification report under `docs/superpowers/reviews/`; keep customer-specific evidence in the downstream repository.

- [ ] Run focused tests from Tasks 1–7 after the final change, `python3 scripts/pre_push_check.py --all`, and the existing full offline suite once. Repeat only failed or affected checks after subsequent edits.
- [ ] Verify hosted Linux, Windows PowerShell/Git Bash, and macOS checks at the exact pushed SHA. Report unsupported/skipped platforms explicitly.
- [ ] Review inline against the spec: every requirement maps to a completed task; no implementation-only behavior changed version-1 migration/import semantics; selected source and engine hashes match.
- [ ] Only after a named-target request, use a disposable staging clone and the real owner/acts-as-schema profiles to measure selected-source capture, prepare/diffs, object revalidation/apply/checks, session counts, and exact final source/settings/validity.
- [ ] Qualify a small package/DDL capsule against 120 seconds and a reviewed larger capsule against its explicit budget up to 300. Keep APEX import, ORDS, and data times separate. A failed budget or unavailable target is not a pass.
- [ ] Record template PR/merge state independently from offline CI and live qualification. A passing documentation/implementation PR alone does not establish a fast production deployment.
- [ ] After implementation merge, perform the separately requested downstream upgrade/conversion; production execution requires its own explicit target/action request.

**Done:** code, platform checks, live qualification, downstream adoption, and production authorization have distinct, evidenced states.

## Review and execution handoff

This plan is for review in the documentation PR. Preserve inline execution when
implementation is requested. The next runtime change should be its own
implementation PR linked to this spec/plan; merging these documents alone does
not make an upgrade or the proposed commands available.
