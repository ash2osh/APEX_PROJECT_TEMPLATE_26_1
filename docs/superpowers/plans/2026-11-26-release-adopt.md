# `release adopt` Implementation Plan

> **For agentic workers:** owner prefers inline execution (no subagents). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Give a bundle that ran before release state existed a trustworthy `state/<env>.json` for DEV or staging, built from live read-only queries plus an old successful run report, so the next run applies only what is really missing.

**Architecture:** New subcommand `release adopt` in `scripts/release.py` (core-shared). It reuses `_load_and_validate_manifest`, `_fetch_schema_objects` (read-only), `_collect_step_items`, `_bundle_fingerprints` and `merge_state`/`write_state` from `scripts/release_state.py`. It never runs DDL, code, verify or app deploys.

**Tech Stack:** Python 3 stdlib, existing SQLcl fetch driver, `unittest` with `tests/fake_sqlcl`.

**Spec:** `docs/superpowers/specs/2026-11-25-release-state-design.md` (state file format, rules 1–4, 12). This plan adds one command on top of it.

## Owner request (2026-11-26)

"Adopt from the report and the queries against the database, both dev and stage." Natrec's prod-v1 is the first user: staging ran it successfully on 2026-11-25 (report `prod-v1-staging-20261125T093603Z-…`), before the state files existed; DEV never ran it (owner decision 5).

## Global Constraints

- Envs: `dev` and `staging` only. `prod` is refused (production records come only from the locking run).
- Read-only: one fetch per schema through the existing driver; the identity guard (`DB_UNIQUE_NAME`, `CON_NAME`, `USER`) applies as in `check`.
- `release.json` is never changed: adopt never sets `staged`. The next normal run does, once every fingerprint matches.
- An existing `state/<env>.json` is refused unless `--replace` (adopt is for bundles with no record).
- Each adopted entry carries `"adopted": {"by": "live-source" | "report", "at": …}`; `lastRun.mode = "adopt"` and lists what was proven and what was not.
- `--dry-run` prints the result and writes nothing.
- Tag new code `ASHARIF 2026-11-26`.

## Proof rules (what gets recorded)

| Step kind | Recorded when | Entry |
|---|---|---|
| code (package, body, view, trigger…) | live source equals the bundle file, compared with `normalize_source_for_hash` after the file is reduced to its object text (no `ALTER SESSION` header, no trailing GRANT/synonym block, first line spacing and own-schema prefix ignored) | `sha256`, `liveSha256` (live hash now), `adopted.by = live-source` |
| ddl / ords | `--report` given, report says `SUCCEEDED` for this slug and env, its identity equals live, the file at `--commit` equals today's file, **and** every object the step names (`objects` or the parsed DDL candidates) exists live | `sha256`, `adopted.by = report`, `report`, `commit` |
| app | report lists the app under "Apps deployed" and the app source at `--commit` equals today's | `apps.<id>.sourceSha256`, `adopted.by = report` |
| anything else | not recorded; the next run applies it (safe default) | — |

`--commit` defaults to the report's `Commit`. It may be given explicitly when the run used files committed later (natrec: report says `439ae782`, the files it ran were committed as `309901b2`); the report path and both commits are written to `lastRun`.

Without `--report` (DEV for prod-v1): only code steps can be adopted.

## Review Focus

1. A code step whose live object exists but differs (natrec 068, to-do 76): not recorded, so the next staging run applies it.
2. A trigger or view whose DBMS_METADATA text differs only by formatting: compared on `ALL_SOURCE` text (the same text `liveSha256` uses), not DDL, so formatting alone does not block proof; a real difference still does.
3. A report for another env, slug or database, or a FAILED report: refused.
4. A DDL file edited after the report's commit: not recorded.
5. Existing state file: refused without `--replace`; `--dry-run` writes nothing.

---

### Task 1: file-to-object text and the live comparison

**Files:** Modify `scripts/release.py`; Test `tests/test_release.py`.

- [ ] Tests: `test_object_text_from_file_strips_header_and_grants` (package body with `ALTER SESSION` header and trailing GRANT → equals the `ALL_SOURCE`-shaped text), `test_object_text_view_stops_at_semicolon`, `test_object_text_trigger_matches_all_source`.
- [ ] Implement `_object_text_from_file(object_type: str, schema: str, text: str) -> str` (returns text whose `compute_source_sha256` equals the live hash for an unchanged object).
- [ ] Run → pass. Commit.

### Task 2: report reader

- [ ] Tests: `test_read_report_ok`, `test_read_report_refuses_failed_wrong_slug_env`.
- [ ] Implement `_read_run_report(path: Path) -> RunReport` (`slug`, `env`, `outcome`, `commit`, `identities: dict[schema, (dbUniqueName, conName, user)]`, `apps_deployed: list[int]`), parsing the existing markdown report lines.
- [ ] Run → pass. Commit.

### Task 3: `cmd_adopt`

**Interfaces:** `cmd_adopt(repo_root, bundle_arg, *, env, report_arg: str | None, commit: str | None, replace: bool, dry_run: bool, fmt: str, environ, runner) -> int`; parser `release adopt <bundle> --env {dev,staging} [--report PATH] [--commit SHA] [--replace] [--dry-run] [--format text|json]`.

- [ ] Tests: `test_adopt_records_matching_code_only_without_report`, `test_adopt_with_report_records_ddl_when_objects_exist_and_file_unchanged`, `test_adopt_skips_ddl_changed_after_commit`, `test_adopt_records_app_from_report`, `test_adopt_refuses_prod_and_existing_state`, `test_adopt_dry_run_writes_nothing`, `test_adopt_then_run_applies_only_unproven` (follow-up staging run applies the unproven steps and sets `staged`).
- [ ] Implement; print per step `adopted (live-source)`, `adopted (report)`, `not proven: <reason>`, and the files to commit.
- [ ] Run whole `tests/test_release.py` → pass. Commit.

### Task 4: docs and delivery

- [ ] `docs/release-workflow.md` section "Adopting a bundle that ran before release state"; `AGENTS.md` release paragraph one sentence; `team.sh`/`team.ps1` help line.
- [ ] Core repo: `sync_core.py refresh`, core tests + Ruff, PR, CI green, merge. Template: sync, `pre_push_check.py`, PR, CI green, merge.
- [ ] Live check on local Docker: run a bundle, delete its state, adopt, rerun shows apply 0.

### Task 5: natrec

- [ ] Upgrade natrec (`upgrade-template --ref main`).
- [ ] `release adopt prod-v1 --env staging --report scratch/release-reports/prod-v1-staging-20261125T093603Z-1225764-a8a56a93.md --commit 309901b2 --dry-run`, review, then without `--dry-run`. Expected from the 2026-11-26 read-only check: about 88 code steps by live source (more if the trigger comparison on `ALL_SOURCE` clears the 4 formatting-only triggers), 35 DDL steps by report, App 130 by report; not proven: 068 (to-do 76), 036 setting seed (to-do 76), view 003 and any trigger that still differs.
- [ ] `release adopt prod-v1 --env dev` (code only) when DEV26 is reachable; `ABSH_CREATE_ORDER` must stay not proven (decision 5).
- [ ] Commit `state/staging.json` (and `state/dev.json`), push. Then, only on the owner's go-ahead, `release run prod-v1 --env staging --confirm-target edn1pod` applies the unproven steps and marks prod-v1 `staged`.
