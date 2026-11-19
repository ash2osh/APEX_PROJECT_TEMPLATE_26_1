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

## 7. Review follow-ups ported from the sibling template

**Observation:** the same review findings, fixed in the sibling template, were still open here. Reproduced on a scratch copy with a corrupt `template-manifest.json`: `scripts/verify_local.py --format json` exited with a traceback at its `scripts/local_config.py` import, because `local_config` reads the manifest when it is imported. Also, a locked test or `.github/` file removed by the post-clone cleanup counted as `missing`, and a linked worktree was not recognized as the original template because `is_original_template` read `.git/config` only.

| File | Change |
| --- | --- |
| `scripts/template_drift.py` | `CLEANUP_PREFIXES` (`tests/`, `.github/`): a missing locked file under them is `removed-by-cleanup`, which does not make the status `attention`. `_git_config_path` reads a `.git` directory, or a `.git` file's `gitdir:` line and its `commondir`, with no Git process. `is_original_template` uses it. |
| `scripts/verify_local.py` | The `local_config` import is guarded. A malformed or unknown manifest gives one failed `template_release` check and exit 2, in both formats. The `template_drift` message counts the removed files. |
| `scripts/team.ps1` | `targets` passes `prog='scripts/team.ps1 targets'` in both the `.env` branch (now `-c`, not `-m`) and the no-`.env` branch. |
| `tests/test_template_drift.py` | Three tests: cleanup removals, a missing file outside the prefixes, a customized test file. |
| `tests/test_verify_local.py` | Cleanup drift tests, original-template detection (plain, linked worktree with and without `commondir`, garbage `.git` file, a real `git worktree`), and malformed-manifest runs as subprocesses. |
| `tests/test_team_cli.py` | `targets` usage under PowerShell 7, skipped without `pwsh`. |
| `docs/GETTING_STARTED.md`, `docs/ci-checks.md`, `docs/TROUBLESHOOTING.md`, `README.md` | The cleanup removes `.core-stamp.json` and explains `removed-by-cleanup`; the shared-core stamp wording; two local-readiness rows; the template-status sentence. |

**Deviations from the sibling template:**
- In 26.1 `is_original_template` lives in `scripts/template_drift.py`, so `_git_config_path` lives there too, and `verify_local.py` still imports the function.
- The application-lock item (`app-unlock` closing `held` records) is not ported: 26.1 has no application lock script. `docs/publish-rules.md` is unchanged.
- The 26.1 cleanup is one `git rm -r --ignore-unmatch tests .github docs/superpowers` command, so the `.core-stamp.json` removal is a separate line.

**Verified:**
- Before and after, same commands: `test_template_drift` 4 then 7 OK; `test_verify_local` 29 then 39 OK; `test_team_cli` 74 then 75 OK (6 platform skips in both); `test_documentation_contract` 30 OK; `test_show_targets` 11 OK.
- Each new test that targets a change fails against the old behaviour (scratch copies, no stash): cleanup state reverted to `missing` (1 template_drift test and 2 verify_local tests fail); old `verify_local.py` (3 malformed-manifest tests fail); `.git` file handling replaced by the old fixed path (3 worktree tests fail); old `team.ps1` (2 PowerShell usage cases fail).
- A healthy repository with the same trees gives the same `verify-local` exit code and `template-status` output; the only text change is the added `0 removed by cleanup` count.
- `ruff check` on the touched Python files and `scripts/sync_core.py check .` (242 shared files OK).

**Not verified:** Windows PowerShell 5.1 (PowerShell 7 on Linux only). No database, SQLcl or network call ran, and `scripts/pre_push_check.py --all` and the full CI suite were not run.

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

## 8. Review pass 2 ported from the sibling template

**Observation:** the 26.2 template's second review pass had fixes this template did not have. A credential in `--source` could reach `.template-lock.json` and error text. A remote spelled another way, or a repeated `fetch` line, broke original-template detection. A lock with empty `files` or no `commit` read as current. `team.ps1` left `PROJECT_SCHEMA` set in a persistent PowerShell session after `--schema` or `targets`.

| File | Change |
| --- | --- |
| `scripts/upgrade_template.py` | `_reject_credentials` refuses a password anywhere and a username on http(s). `ssh://user@host` and scp-style `user@host:path` stay allowed. It runs in `_normalize_source`, in `main` before any git command for an explicit `--source`, and in `_validated_lock` for the lock's upstream (the message adds "remove it from .template-lock.json"). `run_git` redacts `scheme://user[:password]@` in the arguments and stderr it prints. `read_lock_with_hash` refuses a lock whose `commit` is not a 40- or 64-hex string or whose `files` is empty. |
| `scripts/template_drift.py` | `is_original_template` uses `ConfigParser(interpolation=None, strict=False)` and `_normalized_remote`, which compares (lowercase host, path) so https, http, git, ssh, ssh-with-port and scp-style spellings of one repository match. Unparsable values never match. `_local_file_state` reports `matches-lock` when the lock holds either the raw or the normalized digest. |
| `scripts/team.ps1` | The caller's `PROJECT_SCHEMA` is saved at the top and restored by `Restore-CallerProjectSchema`, called from `Fail`, `Exit-Team`, the catch-block refusal exit and the outer `finally`. It is idempotent. |
| `tests/test_upgrade_template.py` | `SourceCredentialTests` and `LockReadStateTests`. |
| `tests/test_template_drift.py` | Five tests: legacy raw-hash CRLF match, unrelated hash, LF normalized match, empty `files`, missing `commit`. The fixture lock gained `"commit": "a" * 40`, because a lock without a commit is now invalid. |
| `tests/test_verify_local.py` | `OriginalTemplateRemoteTests`: two `fetch` lines, equivalent spellings, a different repository or host, local path upstream, garbage origins, and the normalizer. It imports `_normalized_remote` from `scripts/template_drift.py`. |
| `tests/test_team_cli.py` | `TeamPs1EnvironmentTests`: three PowerShell tests, skipped without `pwsh`. |
| `README.md` | "Safety built in" row: production is never written without an explicit confirmation (a typed `y`, or `--confirm-target` naming the observed `db_unique_name`). The old phrase "production is read-only" was false for 26.1, which writes to production after confirmation. The two legacy-lock recovery commands gained `--ref main`. |
| `docs/GETTING_STARTED.md` | The cleanup is selective. `git ls-files .github` lists what the template ships, and only `template-checks.yml` and `dependabot.yml` are removed by name. The tests the lock records are listed from `.template-lock.json`, and only reviewed names are removed. `docs/superpowers/` is removed by name after review. A list of preserved project data follows. The `.core-stamp.json` and `removed-by-cleanup` sentences are kept. The two legacy-lock recovery commands gained `--ref main`. |

**Deviations from the 26.2 patch:**
- In 26.1, `is_original_template` and `_normalized_remote` live in `scripts/template_drift.py`, so the change is there. `scripts/verify_local.py` is unchanged and still imports the function.
- The cleanup text is 26.1's own. The 26.2 guide says to review `tests/` by hand. Here the lock's recorded `tests/` entries give the list, because `tests/**` is template-owned in the manifest and a project's own tests are not in the lock.
- The README wording is the 26.2 sentence, checked against 26.1: `scripts/migrate.py` refuses `--yes` alone for production and accepts a typed `y` or a matching `--confirm-target`, and `scripts/deploy.sh` does the same.
- Not ported: the `features/` and `releases/` protection (26.1 already has it) and the `application_lock.py` follow-ups (26.1 has no application lock script). `docs/publish-rules.md`, `TODO.md`, `template-manifest.json` and `docs/superpowers/*` were not touched.
- The shared-core files were not edited. `scripts/sync_core.py check .` reports OK for 243 files.

**Tests, before and after** (`python3 -m unittest discover -s tests -p <file>`):
- `test_upgrade_template.py`: 62 OK before, 73 OK after.
- `test_template_drift.py`: 7 OK before, 12 OK after.
- `test_verify_local.py`: 39 OK before, 45 OK after.
- `test_team_cli.py`: 75 OK (6 skipped) before, 78 OK (6 skipped) after. The three new PowerShell tests ran on PowerShell 7.7 on Linux.
- `test_documentation_contract.py`: 30 OK before and after.
- `test_template_update_notice.py`: 9 OK before and after.
- `ruff check` on the seven touched Python files: all checks passed.

**New tests against the old code** (scratch copy of `git archive HEAD` with the new test files, no stash):
- `test_upgrade_template.py`: 7 failures and 10 errors. The errors are the credential tests, because `_reject_credentials` does not exist on HEAD. The failures are the CLI, `_lock_bytes`, lock-read and `run_git` redaction checks and the four lock-state refusals. The "normal lock still reads" test passes on HEAD, as intended.
- `test_template_drift.py`: 3 failures (legacy raw-hash CRLF, empty `files`, missing `commit`).
- `test_verify_local.py`: 7 failures and 1 error. The error is the normalizer import, because `_normalized_remote` does not exist on HEAD.
- `test_team_cli.py`: 2 failures on the old `team.ps1` (the `targets --help` inherited-schema test and the refused `doctor --schema` test). The unset-schema guard passes on the old script, as intended.

**Not verified:** Windows PowerShell 5.1 (PowerShell 7.7 on Linux only). No database, SQLcl, network, publish, migrate or deploy command ran. The full `scripts/ci_run_tests.py` suite was not run; only the six modules named above were run.

## Live verification on local Docker Oracle (2026-11-19, pass 3)

Targets: the three disposable scratch containers `fq-scratch-dev`, `fq-scratch-stg` and `fq-scratch-prod` (Oracle AI Database 26ai Free 23.26.3, schema `FEATURE_QA`, saved connections `fqdev`, `fqstg`, `fqtarget3`). The persistent `local-26ai` container was not written to. The scratch containers were started for this run and stopped afterwards.

- **Repository live modules, run from throwaway clones of the final branch:** `tests/test_live_baseline.py` 14 tests OK; `tests/test_live_feature_release.py` 22 tests OK with the three-target proof, the dedicated long-view and the staging benchmark scenarios enabled (1 skipped: the two-schema scenario needs a second schema).
- **Generator checks written for this pass (32, all OK):** the CHECK replacement block compiles and runs on Oracle (reviewed replace, idempotent re-run, refusal with -20994 for a stale review or changed status, -20993 for a primary key of the same name, DISABLED stays DISABLED, quoted identifiers compare by their text, the precondition query counts violating rows, and the known drop-then-add hazard is confirmed so the precondition is what prevents it); the sequence block restores the target's own increment; an owner-qualified object-type column adds and checks; catalog-shaped foreign-key order creates parent first; `ALL_TAB_PRIVS.GRANTABLE` exists; GRANT ALL and column grants are not recorded as ALL or UPDATE(col); INVISIBLE columns add with `INVISIBLE` (also before an identity clause) and the postcondition checks `HIDDEN_COLUMN`.
- **What the catalog showed:** an INVISIBLE user column is `HIDDEN_COLUMN=YES`, `USER_GENERATED=YES`; a function-based index column is hidden, `USER_GENERATED=NO`, virtual; `ALL_TAB_COLS.DATA_DEFAULT_VC` returns a virtual column's expression on 23ai (not confirmed on older releases, so expression capture is not implemented). `DATA_DEFAULT` is a LONG and cannot be used in a SQL expression.
- **SQLcl session cost:** about 2.1 s for connect, one statement, exit.
- **Real project check:** `upgrade_template.py --dry-run` against a long-lived downstream project changed nothing in it (the working tree stayed clean) and found no mode-only updates.
- **Not verified:** Windows PowerShell 5.1.
