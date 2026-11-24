# Known limitations and accepted behaviour

Reviews and end-to-end test runs have reported each item below and the maintainers
decided to keep it. **Do not report these again as defects, and do not "fix" them**,
unless the behaviour no longer matches this page or a change makes the risk worse.
Then report that difference. Each entry says why it is kept and what to do instead.

## Workflow decisions

| Behaviour | Why it is kept | What to do |
| --- | --- | --- |
| Persistent SQLcl sessions reuse database sessions; the reset cannot clear rows in a session-duration global temporary table, application contexts, `SET ROLE` or session events. | A reconnect costs about as much as a SQLcl start against a remote database; generated scripts use none of these. See [sqlcl-sessions.md](sqlcl-sessions.md). | Run such a project script with `SQLCL_PERSISTENT_SESSIONS=0`. |
| On Windows a deployment starts one SQLcl per script. | The persistent session pool uses POSIX named pipes. | Nothing; behaviour is as before the pool. |
| `publish` imports the files in the app folder whether or not they are committed. | The shared DEV database is the source of truth; Git records it. | Commit your edit and the stamped `application.apx` after publishing, before your next `export` of that app (export refuses to write over uncommitted files). |
| Two developers publishing the same app at the same instant can both import; there is no lock. | `AGENTS.md` forbids team mutexes, checkout rosters and metadata tables. | Tell the team which app you are publishing. The drift guard catches every import that is not simultaneous. |
| The first publish of an app made with `apex generate` stops at the post-import byte check and records no baseline. | Loosening the exact-bytes check for that case would weaken the main safety guard. | Follow "A new app from `apex generate`" in [publish-rules.md](publish-rules.md): commit, export, commit, publish again. |
| The drift guard cannot see unsaved edits in an open Builder page. | APEX records only saved changes. | Ask teammates before publishing a shared app. |
| A process with shell access can pass `-y` or `--confirm-target` to a staging or production run. | A `[y/N]` prompt cannot be answered from a pipe, and `release run` replaces stdin prompts altogether with `--confirm-target <db_unique_name>`. Explicit flags keep target confirmation recorded without making unattended automation impossible; agents supply `--confirm-target` only under the conditions in `AGENTS.md`. | Review the run before executing; keep `-y` out of scripts nobody reviews. |
| `publish` and `deploy` accept APEX 26.1 and 26.2 only. On a later release, the lifecycle adapter refuses with `ORA-20018` until that release is qualified. | The adapter's queries are qualified only on the releases its gate names, so the gate refuses others instead of running them unqualified. A full publish was verified end to end on APEX 26.2.0 (Oracle AI Database 26ai Free 23.26.3, Windows) on 2026-11-20. Restoring application automations after an import was not exercised on 26.2. | Use the template that qualifies your APEX release. After a publish on 26.2, check the application's automations by hand. |

## Checks and their reach

| Behaviour | Why it is kept | What to do |
| --- | --- | --- |
| A statement run directly in the session uses the login's privileges, so a missing owner grant is not caught for that statement in acts-as-schema mode. | The mode supports logins that cannot use the schema owner's credentials. | Rehearse in an environment with the owner login when owner-grant fidelity for directly-run statements matters; see [login-acts-as-schema.md](login-acts-as-schema.md). |
| In acts-as-schema mode, `dev-test` and `backup-ords` refuse a login that is not the selected schema owner. | Fixture execution and ORDS export require the actual session user to be the owner; `CURRENT_SCHEMA` does not change `SESSION_USER`. | Use a connection whose `SESSION_USER` is the selected schema owner; a proxy connection can provide that identity. See [dev-test.md](dev-test.md#limits-and-safe-use), [ords-export.md](ords-export.md), and [login-acts-as-schema.md](login-acts-as-schema.md). |
| `release check` and `release run` cannot see pending bundles or uncollected edits in another developer's repository. | Repositories are independent by design; there is no shared ledger. | Coordinate schema and code work; preflight checks the live target as it is. |
| SQLcl prints `APEX_IMPORT_VERIFIED:<id>` even after an import it skipped (an unknown workspace in the descriptor, an unreadable `.apx`). | The marker only proves the app is visible after the import session. The SQL cannot tell a skipped import from a real one, and publish also requires SQLcl's own `Import successful.` line, so such a publish is still refused and nothing is claimed. | Nothing; read the refusal publish prints. |
| DEV scenario SQL is trusted input, not sandboxed, and generated fixture names do not isolate indirect effects. | A scenario can commit, run DDL, or trigger autonomous/shared database work beyond its declared objects; DEV may also contain production-derived records. | Inspect the observed target, use synthetic run-tagged fixtures and review scenario effects. The runner requires a DEV profile and refuses production-looking identities, but cannot prove row provenance. See [dev-test.md](dev-test.md#limits-and-safe-use). |
| DEV test planning cannot guarantee future tablespace allocation from quota or free-space observations. | The schema owner may lack visibility, and available space can change between planning and execution. | DBA-wide visibility is advisory, not required. If fixture creation hits quota/allocation refusal, keep evidence, reduce the fixture if meaningful, or ask about space in the existing schema; do not automatically create another schema or replay an ambiguous write. |

## ORDS export

| Behaviour | Why it is kept | What to do |
| --- | --- | --- |
| `backup-ords` refuses a schema that owns an ORDS OAuth client. | SQLcl's `REST export schema` always includes OAuth clients (`p_include_oauth => TRUE`), and the template never exports OAuth clients, secrets or tokens. Removing them from the generated text would be a silent partial export. | Nothing; such a schema cannot be exported until SQLcl can leave OAuth clients out. |
| The ORDS export needs a login as the REST schema owner; a deployment account with `CURRENT_SCHEMA` is refused. | ORDS authorizes the actual session user, which `ALTER SESSION SET CURRENT_SCHEMA` does not change. | Save a connection that logs in as the REST schema owner. Do not enable REST for a deployment account. |
| ORDS is exported twice per schema. | The two exports must be identical; that is how a change during the export is detected without a lock. | Nothing. |
| A mismatch between the dictionary counts and the export's call counts fails the export, even when the export looks fine. | An export that silently holds less than the dictionary lists is worse than no export. | Run it again; if it repeats on a live system, report the entity and counts (the rules are `CALL_RULES` in `scripts/ords_export.py`). |
| The ORDS export was verified live only on ORDS 26.2.3 with SQLcl 26.2.2.0; other ORDS releases, non-REST-enabled and empty schemas, AutoREST objects and Windows were not. | The tests use a scripted fake SQLcl for everything else. | Run `scripts/team.sh doctor` and `backup-ords` against your DEV before relying on it; see [ords-export.md](ords-export.md#limitations-and-what-has-not-been-verified). |
| `backup-ords` lets the dictionary list more roles and privileges than the export holds. | The dictionary includes the roles and privileges that ship with ORDS, which ORDS does not export. | Nothing; an export with more of them than the dictionary lists is still refused. |

## SQLcl and release execution

| Behaviour | Why it is kept | What to do |
| --- | --- | --- |
| SQLcl trims whitespace-only lines in a plain script and treats a trailing hyphen as a continuation of the next line. | The SQLcl script reader normalizes these forms before Oracle sees the statement. | Avoid trailing hyphens in plain SQL scripts where a continuation is not intended. |
| Exact APEXlang source-byte verification after an app import can differ across APEX patch levels, including trailing blank lines, comments and message ordering. | `verify_publish_state.py` intentionally requires the imported source to match local source bytes after documented projections; it cannot assume which patch-level serializer changes are harmless. | Prefer the same APEX patch level on source and target. On a mismatch, retain the publish evidence, compare a fresh target export and qualify each difference before retrying. Do not weaken the byte check based only on a patch-level guess. |

## Interrupts and signals

| Behaviour | Why it is kept | What to do |
| --- | --- | --- |
| PowerShell 7 on Linux and macOS ignores cleanup on SIGTERM: `kill` ends `team.ps1`, while the Bash helper or SQLcl it started carries on, and its scratch folder stays. | PowerShell offers no script-level SIGTERM handler. Windows has no SIGTERM, and Linux users have `team.sh`, which hands its process to the helper. | Stop a PowerShell run with Ctrl-C, or signal its process group (`kill -TERM -- -<pgid>`); delete a left-over `scratch/` folder by hand. |
| A Ctrl-C that lands inside `Start-Process` itself, before it returns SQLcl to PowerShell, leaves that SQLcl unmanaged. | PowerShell cannot act on a process it has not been handed yet; the window is a few milliseconds, and SQLcl receives the same Ctrl-C. | Nothing. |
| `kill -9`, closing the terminal window, or a power cut stops any command without cleanup. | No program can clean up after being killed outright. | Treat an interrupted publish or release run as potentially partial; inspect live objects or restore from `scratch/backups/`. |

## Internal scripts

| Behaviour | Why it is kept | What to do |
| --- | --- | --- |
| Helper scripts run directly (`scripts/publish_app.ps1`, `scripts/load_env.ps1`, `scripts/replace_mirror.ps1`, ...) can report a refusal differently from the wrappers. A PowerShell helper's refusal is an exception, so `pwsh` exits 1 and prints its error view. | The supported entry points are `scripts/team.sh` and `scripts/team.ps1`; they print the plain message and give the exit statuses listed in README. | Run commands through the wrappers. |
| A Python module under `scripts/` run as a file (`python3 scripts/release.py --help`, `python3 scripts/verify_local.py ...`) can fail with `ImportError: attempted relative import` or `No module named 'scripts'` when importing sibling modules. | The modules are one package: they import each other, and the wrappers start them as `python3 -m scripts.<name>` from the repository root. | Use `scripts/team.sh` or `scripts/team.ps1`. To call a module yourself, run `python3 -m scripts.<name>` from the repository root. |
| `safe_rmtree` (Python scratch cleanup) does nothing for a path that is a symbolic link. | It only removes temporary directories the scripts themselves just created, never links, and `shutil.rmtree` never follows links inside a directory. | Nothing. |
