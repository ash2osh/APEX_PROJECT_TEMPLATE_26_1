# Feature-oriented release capsules: local qualification

## Scope

- Repository: separate APEX 26.1 template checkout.
- Branch: `codex/feature-release-capsules-impl`; base and current `HEAD`: `e48b7053c53b05e014a30d511c1f399e880460ec`.
- Implementation changes are still uncommitted in the isolated worktree, so there is no pushed implementation SHA to qualify.
- Review was performed inline in this task; it is not an independent code review.

## Local evidence

- Focused Tasks 1–7 suite after the final code change: 413 tests passed, 10 skipped.
- `python3 scripts/pre_push_check.py --all`: passed after final changes; Python syntax, Ruff, Bash syntax, and changed test modules passed.
- The final changed `test_windows_support.py` run passed 43 tests with 15 platform skips. It includes the updated rollout-help contract for `--prepare`, `--capsule`, `--stage-report`, and `--recover`.
- Final `python3 scripts/ci_run_tests.py --jobs 8`: 2,108 tests, 32 skipped, zero failures/errors/incomplete modules. An earlier run exposed a stale rollout-help assertion; it was corrected and the final full suite is green.
- The review found that the engine digest omitted transitive runtime helpers and trusted SQL/Bash files, including `migrate.py`, SQLcl transport, catalog templates, and the APEX deployment path. The engine file set now binds those dependencies and refuses missing required files. A regression test failed before the fix for all 12 changed dependency cases and the missing-helper case, then passed afterward.
- Capsule tests cover deterministic payload and engine digests, selected-source binding, tamper detection, and build/load integrity. No project-specific capsule or live source was frozen in this qualification.
- Schema-version 1 rollout, migration, receipt, upgrade-preservation, and compatibility tests passed in the focused and pre-push runs; the feature path is dispatched separately.

## Gates not established

- Hosted Linux, Windows PowerShell/Git Bash, and macOS checks have not run for this implementation: no implementation commit was created or pushed. PR #41 is the separate documentation/spec PR; its passing checks do not qualify this worktree diff.
- No SQLcl connection, Oracle/APEX import, staging timing, or production action was run. Live staging performance remains unqualified until a named target and rehearsal are authorized.
- The production path still requires its own prepared plan and verified staging report for the same capsule. A passing local suite does not satisfy that gate.

## Inline review

- Review of PR #41's spec and plan found no blocking documentation contradictions. PR #41 remains documentation-only; its hosted checks do not qualify the implementation worktree.
- The new CLI is offline for init, diff, freeze, and cleanup preview; capture rejects non-DEV and duplicate environment selections before loading `.env`.
- Feature capsules are created only from committed selected bytes, bind source/payload/engine hashes, and use environment-specific target plans. Production validates staging evidence before confirmation.
- Ambiguous attempts remain in local release state and require reconciliation. Cleanup defaults to preview and refuses unresolved attempts.
- The database-object budget measures selected feature checkpoints and reports incomplete coverage when other object work is present; it cannot stop an Oracle DDL operation that has already committed.
- Downstream conversion is documented as a later, separate operation. No migration conversion or archive was performed here.
