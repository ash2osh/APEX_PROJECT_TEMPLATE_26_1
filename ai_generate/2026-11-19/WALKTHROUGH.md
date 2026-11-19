# Walkthrough 2026-11-19

Branch `codex/review-fixes-2026-11-19`, cut from `origin/main` after the shared-core sync `5c0a333`. Nothing is pushed and no pull request is open. Commits, in order: `99677c4` (backup scopes), `656c74f` (interrupt helper), `686c530` (`targets`), `cb4407f` (getting-started order), `4ef70a9` (README routes and owning docs), and the commit that adds this file and the TODO section.

## 1. backup-db keeps the scopes it did not refresh (`99677c4`)

**Observation:** `scripts/backup_db.sh` replaced the whole `database/<SCHEMA>/` mirror whenever a tables or code scope ran. A tables-only run deleted the committed `views/`, `packages/`, `procedures/`, `functions/`, `triggers/`, `synonyms/` and `manifest-code.txt`; a code-only run deleted `tables/` and `manifest-tables.txt`. Both exited 0. Seen with the fake SQLcl harness, not a live database.

| File | Change |
| --- | --- |
| `scripts/backup_db.sh` | `carry_committed_scope` copies, for each scope the run did not refresh, the directories `scope_directories` names and that scope's manifest, only when the committed mirror holds them. A scope that ran is still replaced whole. The ORDS carry-over is unchanged. |
| `tests/test_backup_db_cli.py` | Six new tests: tables-only, code-only and both-scope runs, for Bash and PowerShell. They use the real `replace_mirror` helper and a committed mirror that holds every output. |
| `docs/ords-export.md`, `README.md` | The replacement table and the `backup-db` row say that an unrefreshed scope is carried over unchanged. |

**Verified:**
- Before the fix, `test_bash_tables_only_run_keeps_committed_code_scope_and_manifest` and `test_bash_code_only_run_keeps_committed_tables_scope_and_manifest` failed; the other tests passed.
- After the fix, `python3 -m unittest discover -s tests -p test_backup_db_cli.py` ran 14 tests, OK.
- Against the pre-sync `scripts/backup_db.ps1` (`git show 5c0a333^:scripts/backup_db.ps1`, in a scratch copy), the PowerShell tables-only and code-only tests failed (2 failures). The synced file passes them.
- The both-scopes test passes before and after the fix. It guards behaviour that must not change, so it cannot fail on the old script.

**Not verified:** Windows PowerShell 5.1, and a live database.

## 2. Interrupt tests use the shared helper (`656c74f`)

**What changed:** four PowerShell interrupt tests in `tests/test_team_cli.py` now call `_test_subprocess_safety.interrupt_process_group` with their previous settle delay (0.1 s, 1.0 s, 0.1 s, 0.1 s). The doctor interrupt test and the Bash-only tests are unchanged. `tests/known_flaky.txt` is unchanged.

**Verified:** the four tests passed, and the whole `test_team_cli` module ran 68 tests, OK, with 6 platform skips, on this commit.

**Not verified:** the timing on a loaded Windows or macOS runner.

## 3. The `targets` command (`686c530`)

**What changed:** `scripts/team.sh targets` and `scripts/team.ps1 targets` run `python3 -m scripts.show_targets` (the existing offline report) after loading `.env`. They clear an inherited `PROJECT_SCHEMA` so every configured schema is listed, and refuse `--schema` before anything loads. Extra arguments get the module's argparse refusal, exit 2, the same status as `verify-local --bogus` and `template-status --bogus`. The command is in the full usage and the README command reference, not the everyday list. `docs/GETTING_STARTED.md` (step 6 and the cheat sheet) and `docs/migration-rules.md` describe it.

`docs/migration-rules.md` also had a wrong sentence: it said DEV migrations use the `CODE_*` profile. The code resolves a configured `MIGRATION_*` owner first, so the sentence now says so, and says that `new-migration` always reads the code profile.

**Verified:**
- Both wrappers print the report from a copy of `.env.example` and exit 0 (checked by hand, then by `test_targets_prints_the_example_env_report_offline_in_both_wrappers`).
- A split-owner `.env` shows `REFUSED: schema DEMO is not listed in MIGRATION_SCHEMA for dev` in both wrappers.
- Extra arguments and `--schema` exit 2 in both wrappers.
- A sanity run showed the fake SQLcl records a call for `doctor` and none for `targets`.
- Contract tests cover the README row and the getting-started and migration-rule sentences.

**Not verified:** Windows Git Bash `python3` resolution. The module's argparse prog name is `scripts/team.sh targets`, so a PowerShell refusal also names `team.sh`. That is in the shared core module and is not changed here.

## 4. Getting-started order (`cb4407f`)

**Observation:** step 7 told a new developer to run `verify-local` and fix every `FAIL`, but step 8 creates the app folder. A scratch copy of the repository before any export: `verify-local` exits 2 with `configured_app_100` and `configured_app_200` as FAIL, `directory not found under apps/`.

**What changed:** step 7 runs `targets` and then `doctor`, and explains the expected FAILs. Step 8 runs `verify-local` at its end and expects every line to pass; the `.env` review moved there too. The cheat sheet gained a `targets` row. No other document tells a new developer to run `verify-local` before the first export (checked by grep).

**Verified:**
- The three new documentation contract tests (the step order, the `targets` mention and the migration-rules profile sentence) fail on the documents as they were before this change, and pass on the new ones.
- A synthetic downstream copy (a lock, `.env` with `APEX_APP_ID=100`, and one app folder with `application.apx` and `deployments/dev.json`, built like the `tests/test_verify_local.py` fixture) gives every line PASS and exit 0.

**Not verified:** a real `export` against a database. The all-PASS result above is from the synthetic fixture.

## 5. README: Daily choices and owning docs (`4ef70a9`)

**Line counts:** `README.md` had 897 lines at the start of this work, 898 after the `targets` row, and 855 after this change.

**What changed:**
- A `Daily choices` section after `Start here`: five one-sentence routes, each linking to one owning place.
- `Builder-first workflow` and `File-first APEXlang workflow` are short summaries that link to `docs/GETTING_STARTED.md` section 9 and `docs/publish-rules.md`.
- Before the README text was cut, the detail it held and the owning docs lacked was moved into them: `docs/publish-rules.md` (the export-time Builder check, the database-clock comparison and time-zone note, the one-second refusal, the publish tag and its counter, `#APP_VERSION#`, the baseline advancement after a successful import, and the `Import successful.` requirement); `docs/GETTING_STARTED.md` section 9 (the export review and refusal rules, the `scratch/` staging, and the kept descriptors).
- `test_active_team_guidance_uses_the_current_cli` asserted publish sentences that moved. It now asserts them in `docs/publish-rules.md`.

**Verified:** every link and anchor in the Daily choices section and the two summaries resolves, checked with the test module's own heading-slug function. The documentation contract module passes. Each README claim removed was checked against the code (export refusal and staging in `scripts/export_apps.sh`, the counter in `scripts/stamp_publish_version.py`, `SYSDATE` in `scripts/check_builder_drift.sql`, the `Import successful.` check in `scripts/publish_app.sh`).

**Not verified:** how the links render on GitHub. The "promote" route points at the `EXAMPLES.md` section 7 deploy recipe. Feature-release rollouts are described in `docs/feature-releases.md`, and the Daily choices list does not link to them.

## 6. TODO and this walkthrough

`TODO.md` gained "Open after the 2026-11-19 review fixes" with the three open items listed under Open below. This file is the day's walkthrough.

## Verification

Commands run from this checkout, in order, with results:

- `python3 scripts/pre_push_check.py --all`: exit 0, "all checks passed". Ruff, ShellCheck (error severity), the PowerShell parse, shell syntax and the shared-core stamp check (242 files) all ran.
- `python3 -m unittest discover -s tests -p test_backup_db_cli.py`: OK, 14 tests (before the fix, two bash tests failed, see section 1).
- `python3 -m unittest discover -s tests -p test_team_cli.py -v`: OK, 68 tests, 6 skipped (platform skips that predate this work), after the interrupt change and before `targets`.
- `python3 -m unittest discover -s tests -p test_team_cli.py -k targets`: OK, 5 tests (on the `targets` commit).
- `python3 -m unittest discover -s tests -p test_documentation_contract.py`: OK, 30 tests (on the final docs).
- The full suite, `CI_TEST_JOBS=2 python3 scripts/ci_run_tests.py --jobs 2`: `CI_TEST_JOBS=2 python3 scripts/ci_run_tests.py --jobs 2` exited 0: `Combined: Ran 2841 tests; skipped=73; failures=1; errors=0; incomplete_modules=0`. The one failure was `test_powershell_exits_130_when_interrupted_while_a_helper_runs`, which pwsh ended with status -6 instead of 130. It is already listed in `tests/known_flaky.txt` with the same signature, and the runner reran it once and it passed (`Known flaky test passed on rerun`). Run again alone, `python3 -m unittest discover -s tests -p test_team_cli.py`: OK, 72 tests, 6 skipped. The flaky list was not changed.

## Not verified

- Windows and Windows PowerShell 5.1 for every change here. The PowerShell paths were run on PowerShell 7.7 on Linux.
- Any live database: no `doctor`, `export`, `publish`, `migrate` or `deploy` was run.
- A real export followed by `verify-local` (section 4 used a synthetic fixture).

## Open

- Virtual-column expression capture needs an edit in each template's `scripts/compare_env_catalog.sql` (not a shared core file).
- Oracle's catalog representation of INVISIBLE columns was not verified against a live database.
- The PowerShell backup change was verified on PowerShell 7.7 on Linux only, not Windows PowerShell 5.1.
