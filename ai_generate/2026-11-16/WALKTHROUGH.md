# Walkthrough 2026-11-16

## Review findings on branch fix/review-2026-11-16

Branch `fix/review-2026-11-16` was cut from `main` at `6c3158e` (pull request 69). It closes six review findings. Commits, in order: `cb7ca4d`, `97e6252`, `8c14f02`, `4118afd`, `71a540e`, `57b21c1`, `2a77e26`, `2c31b90`. Nothing has been pushed and no pull request is open.

### Rollout receipts are never replaced (`cb7ca4d`, `97e6252`)

Probe result: a schema-version 1 manifest run again from step 1 executed every step a second time and overwrote the receipts under `scratch/rollout-receipts/`. The 26.2 template refuses that with exit 2 and runs nothing.

- `scripts/rollout.py`: `_assert_unreceipted_execution_range` refuses before any step when a selected step's canonical receipt path is a file, a directory or a symbolic link. It runs in the legacy path after the resume verification and before the dry-run branch, so a dry run is refused too.
- `_install_rollout_receipt` installs a receipt with an atomic no-overwrite link. `_write_receipt` uses it and reports "may have completed, but its rollout receipt was not installed" on failure.
- `scripts/rollout_capsule.py`: the capsule path calls the same guard for step 1 right after `start_rollout`. An unresolved earlier run is reported first; the run then ends failed with nothing started.
- Not ported, because they are 26.2-only: schema-2 target bindings, `capsule=True` and the writer identity fields. Also not ported: 26.2's write-time `_validate_evidence_paths` check.
- Tests in `tests/test_rollout.py`: the rerun of a sql-script manifest, malformed and symlinked receipts, a resume into a receipted step, the dry-run refusal, the install race, and a pause-only rerun. The existing resume test now fails step 3 first, so that step has no receipt when resumed. `tests/test_feature_rollout.py` gets the capsule rerun refusal. `tests/test_live_feature_release.py`: the reconcile scenario expects the refusal and continues with a continuation manifest.
- Docs aligned in `docs/feature-releases.md`, `docs/live-feature-tests.md`, `docs/migration-rules.md`, `README.md`. The dry-run sentence was narrowed to schema-version 1 in `2c31b90`.

### Building-apex-template-components skill (`8c14f02`)

- Copied from 26.2: `.agents/skills/building-apex-template-components/` (SKILL.md, references, templates) and the Claude pointer under `.claude/skills/`.
- Changed in the copy: every sentence that called uc-apx "retired". In 26.1 it is optional, user-controlled tooling (`install-uc-apx`, `INSTALL_UC_APX`), so the wording now says that.
- Lists updated: README skill table and counts (13), the Claude pointer sentence (five pointers), AGENTS.md ("13 template-authored domain/setup skills"), and `CORE_SKILLS` in `scripts/workflow_skills.py`.
- `CORE_SKILLS` also lacked `firefox-devtools-mcp`. It is added. A new test `CoreSkillListTests` in `tests/test_workflow_skills.py` pins the set to the template skill folders.
- `template-manifest.json` already covers both trees with globs, so it did not change.

### Browser MCP escape-path test (`4118afd`)

Ported `test_validate_target_path_refuses_a_path_that_escapes_the_checkout` into `tests/test_browser_mcp.py`. `scripts/browser_mcp.py` is byte-identical in both templates.

### Retired TEAM_ACK_FROM_STDIN (`71a540e`)

No code reads the variable any more. AGENTS.md and `.agents/rules/agent-safety.md` now say it is retired and ignored, keeping "piped or redirected acknowledgments stay refused; `--yes` is the recorded route". `may_read_acknowledgment` lost its unused `environ` parameter; its three callers did not pass it, and `tests/test_terminal_confirm.py` is updated. The test still sets the variable and checks that the gate stays closed.

### Privacy scrub (`57b21c1`)

- `docs/superpowers/specs/2026-10-15-confirmed-review-remediation.md`: the absolute home-directory path is now `scratch/review-2026-10-15/REVIEW.md`.
- The two agent-conversation-style documents: the downstream project names are replaced by "a downstream project" and the table row is generic.
- `tests/test_feature_ddl_adversarial.py` and `tests/test_feature_ddl_forms.py`: the grantee name is `BATCH_USER` instead of the downstream name, so the grep requirement holds.
- the privacy grep (the deny-list pattern, see the verification section) now hits only `tests/test_agent_styles.py`.

### Daily change record for 2026-11-15 (`2a77e26`)

`ai_generate/2026-11-15/WALKTHROUGH.md` describes pull request 69 (`331b111`, `2ccc4e6`, `245aa43`): `--yes` for rollout pause steps and `mcp setup`, `--yes` for the typed RECONCILE acknowledgments with `acknowledgedBy` recorded, and the Windows NUL `EOFError` fix. It was written from the diff only.

## Verification

Commands run in this session, from the 26.1 checkout, with results:

- `python3 -m py_compile` on the changed rollout, capsule and test modules: no errors.
- `PYTHONPATH=tests:. python3 -m unittest test_rollout test_feature_rollout`: OK, 105 tests (run before the capsule test was added).
- `PYTHONPATH=tests:. python3 -m unittest -v test_feature_rollout.FeatureRolloutTests.test_capsule_rerun_refuses_an_occupied_receipt_before_any_checkpoint`: OK.
- `PYTHONPATH=tests:. python3 -m unittest test_workflow_skills test_documentation_contract test_template_manifest test_upgrade_template test_chrome_devtools_docs test_apex_background_skill`: OK, 159 tests (after `firefox-devtools-mcp` was added to `CORE_SKILLS`).
- `PYTHONPATH=tests:. python3 -m unittest -v test_browser_mcp`: OK, 13 tests.
- Acknowledgment-gate modules (`test_feature_cli`, `test_feature_runtime`, `test_documentation_contract`, `test_feature_rollout`, `test_migration_resolution`, `test_migrate_cli`, `test_migration_archive`, `test_release_completion`, `test_feature_prepare`, `test_release_state`, `test_terminal_confirm`, `test_schema_normalization`, `test_live_feature_release`, `test_team_cli`): OK, 469 tests, 25 skipped.
- `test_feature_ddl_adversarial`, `test_feature_ddl_forms`, `test_agent_styles`: OK, 47 tests.
- `python3 scripts/pre_push_check.py --all`: exit 0, "all checks passed". Ruff passed. ShellCheck is not on PATH, so it did not run. Run twice: after `2a77e26` and after `2c31b90`.
- `CI_TEST_JOBS=4 python3 scripts/ci_run_tests.py`: exit 0, `Combined: Ran 2706 tests; skipped=60; failures=0; errors=0; incomplete_modules=0`. Run after the code and test changes; the later `2c31b90` edit is docs only.
- After `2c31b90`: `test_documentation_contract` and `test_rollout`: OK, 87 tests.
- the privacy grep: one hit, `tests/test_agent_styles.py` (the deny-list regex, kept as required).

## Not verified

- The live reconcile scenario and the other live feature tests (`tests/test_live_feature_release.py`): opt-in, they need a disposable database. They were skipped. The reconcile text now expects the refusal and a continuation manifest; nobody has run it against a database.
- ShellCheck and the Windows and macOS CI jobs: not run here. The full suite ran on Linux only.
- The skill's APEX 26.1 verification claim: taken from the copied text, not re-run.

## Open

- One downstream-prefixed example object name remains in `docs/compare-env.md` and `tests/test_compare_env.py`. It is outside the scrub pattern and was left alone.
- The copied `anatomy.md` still tells the reader to export a skeleton "in a throwaway worktree". Worktrees are against the owner's working style; wording to be decided.
- Whether the legacy dry-run should refuse on existing receipts (as 26.2 does) or allow it. Current behaviour: refuses.
- Not ported: the 26.2 write-time evidence-path check `_validate_evidence_paths`.
