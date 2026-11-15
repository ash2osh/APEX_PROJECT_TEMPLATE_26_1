# Walkthrough 2026-11-14

## Review safety fixes

The review identified gaps in rollout target confirmation, migration archive evidence, publish lifecycle checks, generated SQL handling, terminal acknowledgments, and publish documentation. The implementation plan is in `docs/superpowers/plans/2026-11-14-review-safety-fixes.md`; the accompanying `review-safety-fixes.diff` records the code and documentation changes.

The changes bind rollout steps to their approved database targets; require matching migration evidence; fail closed when publish lifecycle helpers are absent; map generated SQL identifiers without rewriting literals or comments; require a terminal for acknowledgments; and correct the publish instructions. Regression tests use fake or mocked targets.

Verification:

- `python scripts/pre_push_check.py --all`: exit 0; Python, Ruff, shell syntax, PowerShell parsing, and changed-test checks passed. ShellCheck was unavailable locally.
- `CI_TEST_JOBS=4 python scripts/ci_run_tests.py`: exit 0; 2,664 tests, 90 skips, no failures. The skips include live tests, platform-specific checks, and unavailable optional Graphify tooling.
- `python -m unittest tests.test_migration_archive`: exit 0; 41 tests passed.
- `git ls-files --eol`: no tracked index entries with CRLF.

No live database, container, saved connection, migration, import, or deployment was requested for verification. An AGY startup briefly launched its configured SQLcl MCP without connection arguments; it was stopped, no database connection was observed, and later runs used an offline SQLcl guard. The two live reconciliation scenarios require a developer to perform them manually and type the acknowledgment.

## Linux CI follow-up

The Linux PowerShell error view wraps and colors the refusal message, so the lifecycle tests now match its stable identifying text and separately assert that no import ran. `python -m unittest discover -s tests -p test_publish_lifecycle_gate.py -v` passed all four tests on Windows, and `python scripts/pre_push_check.py` passed. The full Linux checks need to be rerun on the follow-up commit.

## View over-refusal

Fixed baseline view retargeting in `scripts/baseline_sql.py:retarget_sql_identifiers` where views using comma joins (`FROM "DEV"."A" a, "DEV"."B" b`), three-part columns (`"DEV"."T"."C"`), and sequence expressions (`"DEV"."SEQ".NEXTVAL`) were incorrectly refused with `BaselineError("ambiguous source-schema qualifier in view; review the migration")`. The view retargeter now tracks clause boundaries and parenthesis nesting so that three-part references and table references in `FROM` comma-lists are recognized as owners and retargeted, while ambiguous two-part alias references in expressions outside table clauses and bare schema uses continue to be refused. Added unit test import path resolution and 5 regression tests in `tests/test_baseline_generated_sql.py`.

Verification:

- `python3 -m unittest tests.test_baseline_generated_sql -v`: exit 0; `Ran 29 tests in 0.528s` (OK, 5 new regression tests).
- `python3 scripts/pre_push_check.py --all`: exit 0; Python syntax, Ruff, Shell syntax, PowerShell parse, and changed tests passed.
- `CI_TEST_JOBS=4 python3 scripts/ci_run_tests.py`: exit 0; `Combined: Ran 2674 tests; skipped=64; failures=0; errors=0; incomplete_modules=0`.

