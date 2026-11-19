# Project TODO

Keep project work and inherited-template feedback here. Follow
[the template feedback guide](docs/template-feedback.md) for confirmed issues
in inherited template files. This file belongs to the project and survives
template upgrades.

## Tracked feedback

<!-- Add one record per item. Keep evidence sanitized and useful to reproduce. -->

## Verification not done (parked 2026-11-12)

- `team.ps1` on native Windows: the `-y` and `--confirm-target` flags, `reconcile-migration` and the `archive-migrations` options (`--preserve-unresolved`, `--skip-refused`, `--all`) are covered by the CI PowerShell parse step and offline tests only. Run them on a Windows 11 machine against the disposable Docker schemas before relying on them there.
- Offline-only coverage: `_refuse_body_outside_release` (`scripts/feature_release.py`) and the superseded-cleanup rule (`_superseded_reconciliations` in `scripts/release_cleanup.py`) have unit tests but no scenario in `tests/test_live_feature_release.py`.
- `baseline export-grants` is not covered by `tests/test_live_baseline.py`: its system-privilege part needs a DBA login, which the disposable connections do not have.

## Open after the 2026-11-19 review fixes

- Virtual-column expression capture needs an edit in each template's `scripts/compare_env_catalog.sql`. That file is not a shared core file, so this branch does not change it. Checked 2026-11-19 on Oracle 23ai Free: `ALL_TAB_COLS.DATA_DEFAULT_VC` returns the expression (`"ID"*2`), but the Oracle 12.1 reference does not list that column and no 19c database was available, so capture is not implemented; virtual columns stay refused as a reviewed migration.
- INVISIBLE columns: the catalog shows them as `HIDDEN_COLUMN = 'YES'` and `USER_GENERATED = 'YES'` (system-generated hidden columns have `USER_GENERATED = 'NO'`), verified 2026-11-19 on Oracle 23ai Free. The baseline generator now adds a missing one with `INVISIBLE` and refuses a visibility difference. Older Oracle releases were not available to check.
- The PowerShell backup change (`scripts/backup_db.ps1`) was verified on PowerShell 7.7 on Linux only, not on Windows PowerShell 5.1.
- SQLcl session cost, measured 2026-11-19 on the local Docker Oracle 23ai Free containers: about 2.1 s for one session (connect, one statement, exit). A flow that opens 13 sessions therefore costs about 27 s of session overhead on this setup; consolidating sessions was not attempted.
