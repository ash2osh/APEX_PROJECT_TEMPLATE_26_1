# Persistent SQLcl sessions for deployments: design

Date: 2026-11-22. Status: approved in conversation by the owner (approach and outline). Applies to both templates and the shared core.

## Intent

A deployment starts a new SQLcl process for every generated script. A measured staging rollout of the natrec stage 2a capsule (32 feature checkpoints, 14 data scripts) launched SQLcl 191 times. Those launches took 735 of the rollout's 990 seconds, and the fastest launch took 1.8 s locally before any SQL ran. Against Autonomous Database over TLS a launch took 3.7–7 s, so the same launches are expected to cost 12–20 minutes per production rollout. The owner wants a deployment to keep a small number of SQLcl processes running (two or three, as needed) for its whole duration and send every script to them, instead of launching SQLcl per script.

## Goals

- A rollout, migrate, feature release, compare and read-only query run keeps at most three long-lived SQLcl processes per saved connection alias. It sends every Python-driven script to those processes.
- Every safety property that the per-script launch provides today is kept. These are listed under Constraints.
- The fallback stays: `SQLCL_PERSISTENT_SESSIONS=0` (root `.env` or environment) restores one launch per script. A platform or SQLcl that cannot support the protocol also falls back automatically, with one notice.
- Reports record both SQLcl processes started and database sessions used, so the saving is measurable.

## Non-goals

- The Bash and PowerShell app-import path (`deploy.sh`, `publish_app.sh`/`.ps1`, `migrate.sh`) keeps its own SQLcl launches. That is a few launches per app.
- No change to check semantics, the order of steps, or what is verified.
- No python-oracledb or any other driver. Saved SQLcl connections stay the only credential store, because the template keeps no passwords.
- Reducing duplicate database work, such as repeated catalog captures or duplicate precondition runs, is not part of this change. Those are review items handled separately; this change removes launch overhead only.

## Anti-goals (would make this a failure even if it is faster)

- A check after an apply passing because it ran in the session that wrote. Uncommitted data, package state or session settings must never make a check pass.
- An interrupted or timed-out write being reported as anything other than unknown. Its SQLcl process must be ended, exactly as today.
- One script's session settings leaking into the next script: `CURRENT_SCHEMA`, `DISABLE COMMIT IN PROCEDURE`, read-only transaction, compiler settings, NLS, `DEFINE`/`SET` options.
- A login.sql or SQLPATH injection path that the private-working-directory launcher closes today being reopened.

## Constraints (current behaviour that must hold)

- `scripts/sqlcl_session.run_sqlcl(target, driver_path, run_dir, phase=…, timeout_seconds=…, output_limit_bytes=…, cancel_event=…)` is the single Python entry point. Its callers are `rollout.py`, `migrate.py`, `feature_release.py`, `staging_neutralize.py`, `read_only_query.py`, plus `compare_schema`, `schema_catalog`, `migration_checks`, `application_lifecycle` and the dev-test modules, which take it as a runner.
- Its contract has these parts:
  - the alias characters are validated;
  - the driver must be a regular file inside a private `0700` run directory;
  - output is captured to `run_dir/sqlcl-output.log` for every attempt;
  - a non-zero exit, or `SQLCL_ERROR_RE` matching the output, is an error;
  - `SqlclTimeout`, `SqlclCancelled` and the output byte limit behave as they do now;
  - the default timeout is 300 s, with `MIGRATION_APPLY_TIMEOUT_SECONDS` / `MIGRATION_CHECK_TIMEOUT_SECONDS` by phase.
- Generated drivers start with `WHENEVER SQLERROR EXIT FAILURE ROLLBACK` and `WHENEVER OSERROR EXIT FAILURE ROLLBACK`.
  - Read-only drivers end with `EXIT SUCCESS ROLLBACK`.
  - Write drivers end with `EXIT SUCCESS COMMIT` (feature checkpoints `feature_release.py`, migrate apply `migrate.py`, automation restore `application_lifecycle.py`).
  - A failure therefore ends the SQLcl process with a non-zero status. This stays the failure path.
- `scripts/sqlcl_safe.sh` runs SQLcl from the private run directory with `SQLPATH`/`ORACLE_PATH` set to an empty child directory, so no `login.sql` is read.
- Each SQLcl launch gets its own process group (POSIX) or Job object (Windows, `windows_job.py`). Timeout, cancellation and SIGTERM/SIGHUP kill the whole tree.
- Recovery (`docs/feature-releases.md`) asks the operator to assert that "the original SQLcl process and database operation have ended". A killed process stays the end of an ambiguous write.
- `scripts/release_capsule.py` hashes the workflow engine files into `engineDigest`. Any new runtime file must be added there.
- `sqlcl_session.py`, `sqlcl_session.sh`, `sqlcl_safe.sh`, `windows_job.py` and `feature_release.py` are shared core files. The change lands in `APEX_TEMPLATE_CORE` first, then in each template by `sync_core.py sync`. Template-only callers such as `rollout.py` and `migrate.py` are changed in each template.

## Approaches considered

1. **Keep one launch per script (today).** Safe and simple, but launch overhead is most of the rollout time.
2. **One persistent SQLcl process per alias, reusing one database session for everything.** This saves the most, but every script inherits the previous script's session state. Undoing it would mean resetting compiler settings, NLS, package state, read-only transactions and more, generically and correctly. It also breaks "checks run in a fresh session".
3. **Persistent SQLcl processes with reused, reset database sessions (chosen).** Two or three long-lived processes per alias (writer, reader, optional second reader). Each connects once and keeps its session. After each script, one PL/SQL reset block (one round trip, about 0.5 s live) returns the session to its baseline and checks the result. A session that fails the check is replaced.
3b. **The same processes, with a new database session per script** (`connect -name` before every script). Rejected by the owner. Live, it costs 5.4–5.6 s per reconnect, almost a full launch, because SQLcl replays its client settings over the network on every connect. Locally it costs only 0.1 s.
4. **python-oracledb with a connection pool.** Rejected. Saved SQLcl connections hold the credentials and only SQLcl can open them, and the template stores no passwords.

The owner approved approach 3 in outline, as "2 or 3 concurrent SQLcl processes for the duration of the deployment". On 2026-11-22 the owner also rejected a new database session per script. The live measurements below back that up: against the real databases, a reconnect costs almost as much as a full launch. So database sessions are reused, and a reset runs after each script (see Session policy).

## Spike evidence (2026-11-22, SQLcl 26.3.0, local 23ai container)

- **Piped stdin does not work.** SQLcl reads piped stdin to end-of-file before running anything. A pseudo-terminal with `TERM=dumb` ran nothing either, and the JavaScript `script` command needs GraalVM, which SQLcl doesn't bundle.
- **A named pipe as a script works.** `@/run/slot.sql` on a FIFO blocks until the pool writes a script and closes the pipe. SQLcl then runs it and continues.
- **Reusing one FIFO races.** The next write can land before SQLcl has closed the previous read. A new FIFO per script fixes it.
- **Nesting is capped at 20** (`SP2-0309`). So the transport is a flat *loop file* listing K slot FIFOs, `@/run/s0.sql` … `@/run/s{K-1}.sql`, followed by `@/run/loop{b+1}.sql`. The next loop file and the next slot FIFO are created before the current slot is written. Nesting grows by one per K scripts; with K = 500, a process can run about 10,000 scripts before it must be replaced.
- **Measured:**
  - 600 scripts across 12 loop-file rollovers in one process: average 1.3 ms per script, maximum 7 ms.
  - Process start plus first connect: 1.5 s.
  - `connect -name e2e-stg-asherif` inside the running process: 0.08–0.14 s, with a new SID each time.
  - A query in an existing session: 18 ms.
  - `WHENEVER SQLERROR EXIT FAILURE ROLLBACK` ends the process with exit status 2 and end-of-file on stdout, so a failure is detected exactly as today.
  - `DEFINE` values survive both scripts and reconnects. SQLcl client state needs its own reset (see Design).
- **Live, SQLcl 26.3.1, from the developer workstation** (TCP round trip to DEV26 is 86 ms). DEV26 is `dev26_runerp_code`; production is `prod-natr`, read-only, `SELECT … FROM dual` only.

  | | DEV26 | Production (ADB) |
  | --- | ---: | ---: |
  | SQLcl start plus first connect | 6.5 s | 6.7 s |
  | `connect -name` inside the running process | 5.4 s | 5.6 s |
  | One query in an existing session | 0.45 s | 0.53 s |
  | Reset statements (rollback, enable commit in procedure, `RESET_PACKAGE`, metadata transform default, transaction probe), as five separate calls | 0.87 s | 0.98 s |

- **Where the connect time goes.** Thread dumps show SQLcl's `SettingReplaySupport.replayAll` / `DdlNamespace.resetDDLParameters` running about 20 `begin dbms_metadata.set_transform_param(dbms_metadata.session_transform, :OPTION, :VALUE); end;` calls, one round trip each, then `OracleNLSProvider.populateNLS`. No switch for it was found, and SQLcl 26.3.1 behaves the same as 26.3.0.
  - This is also why today's one-shot launches cost about 6.5 s against the real databases.
  - So a reconnect is no cheaper than a launch, and the design must reuse database sessions.
- Spike scripts are kept in the 26.1 checkout under `scratch/review-verification-2026-11-22/` (`fifo3.py`, `fifo4.py`).

## Design

### Pool and roles

- A new shared module, `scripts/sqlcl_pool.py`, provides a context manager: `with sqlcl_pool.deployment_sessions(environment):`.
  - While it is active, `run_sqlcl` sends scripts to the pool instead of launching SQLcl.
  - Outside it, `run_sqlcl` behaves exactly as today. Code and tests that never enter the context are unaffected.
- The entry points that enter the context are rollout (all paths: prepare, run, recovery), migrate, feature apply/prepare/capture/doctor `--live`, and compare-schema/compare-env. One context covers a whole command run, and a nested context (rollout calling `migrate.main` in-process) reuses the outer pool. Staging-neutralize and read-only query launch SQLcl once per command, so they stay one-shot (builder-check question 2).
- Processes are keyed by saved connection alias. Per alias there are at most three:
  - **writer:** runs `phase="apply"` scripts.
  - **reader:** runs everything else (preconditions, postconditions, inventory, catalog captures, phase None).
  - **second reader:** started only when a caller runs read-only scripts concurrently (for example `migration_checks.run_checks(..., jobs=N)`) while the first reader is busy. The reader cap is configurable with `SQLCL_POOL_MAX_READERS` (default 2).

  Each process connects once and keeps its database session for the whole command run (see Session policy). The writer and the reader are separate sessions. A check therefore never runs in the session that wrote, and it can see only committed data.
- A process is started lazily on first use. It is closed at context exit by writing `EXIT ROLLBACK` into the next slot and waiting, then killed after a grace period.

### Process start and transport

- Each process gets a private `0700` run directory holding:
  - an empty `.sqlcl-path`;
  - the loop files;
  - the slot FIFOs, created with mode `0600`.
- Start SQLcl with `sql -S -noupdates -nohistory /nolog @<run>/loop0.sql`, through the same safe launcher (private start directory, empty `SQLPATH`/`ORACLE_PATH`, no `login.sql`). Stdin is the null device.
  - The alias is validated exactly as in `sqlcl_session.sh`.
  - The process gets its own process group or Job object, as today.
- A reader thread per process feeds stdout lines into a queue. Writing a script means:
  1. create the next slot FIFO (and the next loop file when a batch ends);
  2. open the current slot for writing, write the script text and close it;
  3. remove the slot's path.
- Loop batch size K = 500 by default. Before nesting would reach SQLcl's limit of 20, the pool retires the process and starts a new one.

### Session policy

- **Connect once.** A process connects with `connect -name <alias>` when it starts. Straight after connecting it runs a session-init block in one round trip:
  1. Set the `DBMS_METADATA` session transforms to `DEFAULT`, so the first script sees the same state as every later one. This undoes SQLcl's replayed `DDL` settings, which no generated script relies on: the catalog scripts set the transforms they need themselves.
  2. Capture a baseline: the `NLS_SESSION_PARAMETERS` rows, the session's PL/SQL compiler parameters (`plsql_optimize_level`, `plsql_code_type`, `plsql_warnings`, `plsql_ccflags`, `plsql_debug` and `nls_length_semantics`, read from `V$PARAMETER` when the login can see it), the current edition and the session user.
- **Every script segment** is: database reset (below, except before the first script), then client reset, then `cd <run_dir>`, then `@<driver>`, then the sentinel `PROMPT __TEAM_SQLCL_DONE_<nonce>__`.
- **Database reset: one PL/SQL block, one round trip** (about 0.5 s live):
  1. `ROLLBACK`.
  2. `ALTER SESSION ENABLE COMMIT IN PROCEDURE`.
  3. `ALTER SESSION SET CURRENT_SCHEMA = <session user>`.
  4. `DBMS_SESSION.RESET_PACKAGE`. This clears package state, so a later reference never meets ORA-04068 after the writer replaces a package.
  5. `DBMS_METADATA` session transforms back to `DEFAULT`.
  6. Each captured NLS and compiler parameter set back to its baseline value with `ALTER SESSION`.
  7. Then, in the same block, verify: `DBMS_TRANSACTION.LOCAL_TRANSACTION_ID` is null, and the NLS and compiler values and the edition equal the baseline.

  The block prints one marker line. A missing marker, a mismatch or an error means the session can't be trusted. The pool then ends that process and starts a new one, a reconnect at about 6 s live, which should be rare.
- **Writer and reader stay separate.** Under acting-as logins, the writer's `ALTER SESSION SET CURRENT_SCHEMA` and compiler settings are reset like any other session state. The reader never runs a write, so it never holds uncommitted data. Checks after an apply therefore run in the reader's session and can see only what the writer committed.
- **Compiler baseline not readable.** When the login can't read `V$PARAMETER`, typically an owner login without catalog access on DEV, the writer reconnects before each apply instead of reusing its session. Readers are not affected, because read-only drivers don't change compiler settings. Writes are few (26 of 191 scripts in the measured 2a rollout).
- **What a reset can't clear** goes into `docs/known-limitations.md`: rows a script left in a session-duration global temporary table, application contexts set by a script, roles changed with `SET ROLE`, and session events. No generated driver uses these. A project script that does should run in its own capsule step or with `SQLCL_PERSISTENT_SESSIONS=0`.
- **Client reset.** SQLcl's own client state (`SET` options, `DEFINE` variables, `COLUMN`/`BREAK`/`COMPUTE` settings) lives in the SQLcl process, not in the database session. So before each script the pool restores the client state to a baseline:
  1. At process start, capture `SHOW ALL` and the `DEFINE` list.
  2. Before each script, send a fixed reset block: the `SET` options the generators use, back to their baseline values, plus `CLEAR BREAKS`, `CLEAR COMPUTES` and `CLEAR COLUMNS`. Then `UNDEFINE` every variable that isn't in the baseline list.
  3. In tests, and when `SQLCL_POOL_VERIFY_RESET=1`, compare `SHOW ALL` with the baseline after the reset. If it differs, replace the process. The builder chooses whether to keep that check on in production: it costs a few milliseconds per script.
- The per-script identity check in every driver is unchanged, and it still decides whether a script may run against the target.
- Before each script, the runner sends `cd <run_dir>`, so relative spool and `@@` paths resolve exactly as they do with today's working directory.
- The output up to the sentinel is that script's output. It is written to `run_dir/sqlcl-output.log`, checked against `SQLCL_ERROR_RE` and returned as `SqlclResult(returncode=0, …)`. The connect's own output (for example `Picked up JAVA_TOOL_OPTIONS`) is not part of the script's output, but it goes to the log. A failed connect is a script failure: the process is replaced, and the error is raised the way today's failed launch is.
- **Epilogue.** Drivers keep their `WHENEVER … EXIT FAILURE ROLLBACK` header. A final `EXIT SUCCESS ROLLBACK|COMMIT` would end the process, so drivers get it from one shared helper, `sqlcl_session.driver_epilogue(commit: bool)`. In one-shot mode the helper returns today's line. In pooled mode it returns `ROLLBACK;` or `COMMIT;`.
  - Every generator listed by `grep -rn "EXIT SUCCESS" scripts/*.py` switches to the helper.
  - `run_sqlcl` checks that a pooled driver ends with the pooled epilogue. If it doesn't (a generator not migrated yet), that script runs one-shot, so a missed generator costs speed, never safety.
- **Failure.** A SQL or OS error makes SQLcl exit through `WHENEVER`. The runner sees end-of-file before the sentinel, takes the process exit status as the script's return code, and drops the process. That gives the same result and error text as today. The next script starts a new process for that role.
- **Timeout, cancellation, output limit and parent signals** kill that process's whole tree, exactly as today, and raise the same exceptions. A killed writer is the "process ended" fact that recovery relies on.
- **Output limit.** The byte limit applies to the script's own output segment.
- **Timeout** covers the reset and the script together, plus the connect when a new process starts.
- **Idle and lost sessions.** A rollout `pause` step or a long gap may let the database or network drop an idle session. The reset block fails without its marker, so the pool replaces the process before sending the script. If the process itself has died, the pool sees end-of-file on its next write or read and starts a new one, but only before any of that script's text was written. Once a script's text has been written to a slot, it is never retried.

### Concurrency and ordering

- One script at a time per process, guarded by a lock. The pool never reorders scripts: the caller's sequence is unchanged, and a caller that runs scripts one by one gets the same order.
- With a single login for all schemas (acting-as profiles, as in natrec staging and production), a whole deployment uses one writer and one or two readers. With owner logins per schema (DEV), each alias gets its own small set, started only when used.

### Windows

Windows has no `mkfifo`. The equivalent is a Windows named pipe (`\\.\pipe\team-sqlcl-<nonce>-<n>.sql`), created per slot through the standard library's `_winapi.CreateNamedPipe`/`ConnectNamedPipe`. SQLcl's Java opens it as a file. The process tree is killed through a `windows_job` Job object.
- The builder proves this on the Windows CI runner with a fake and, if available, a real SQLcl.
- If it is not reliable, Windows falls back to one-shot with one notice, and `docs/known-limitations.md` gets a row.

### Reporting

- Rollout and feature reports already record `sqlclSessions` per checkpoint. Add the run totals `sqlclProcessesStarted`, `databaseSessions` (connects) and `sqlclMode` (`pooled` or `one-shot`, with the fallback reason).
- The mode is reported, not enforced. Production does not refuse a capsule whose staging proof ran in the other mode (builder-check question 3). The mode changes only how scripts reach SQLcl, not what runs or what is verified, and the engine code is still bound by `engineDigest`. If `release_state.py` checks the report metric set, it must accept the new fields.
- The pool writes one line per script to the run evidence: alias, role, process id, slot number, connect seconds and script seconds.

### Configuration

| Setting | Default | Meaning |
| --- | --- | --- |
| `SQLCL_PERSISTENT_SESSIONS` | `1` | `0` restores one launch per script |
| `SQLCL_POOL_MAX_READERS` | `2` | Maximum reader processes per alias |

Both are read through the existing loaders (`load_env.sh`, `load_env.ps1`, Python), and both loaders must accept them. A loader parity test exists.

### Tests (offline)

- A fake SQLcl (Python) that follows the loop-file and slot protocol, including the nesting limit. Tests must cover:
  - sentinel framing;
  - loop-file rollover and retiring the process before the nesting limit;
  - failure ends the process and the next call restarts it;
  - timeout kills the tree and raises `SqlclTimeout`;
  - cancellation;
  - output limit;
  - a failed connect;
  - the reset block runs before every script except the first; a missing marker or a mismatch replaces the process;
  - package state, an open transaction, a changed `CURRENT_SCHEMA`, NLS or compiler setting from one script is not visible to the next;
  - the writer reconnects before each apply when the compiler baseline can't be read;
  - client reset: a `DEFINE` or `SET` from one script is not visible to the next;
  - no retry once a script's text was written;
  - a driver without the pooled epilogue falls back to one-shot;
  - `SQLCL_PERSISTENT_SESSIONS=0` gives the old behaviour;
  - alias validation;
  - the start directory has an empty `SQLPATH`.
- Existing suites keep their fakes. Tests that run inside the context either get the protocol fake or set `SQLCL_PERSISTENT_SESSIONS=0`.
- `release_capsule` `engineDigest` includes `sqlcl_pool.py`, plus `sqlcl_session.sh`, which review item B5 found missing.

### Live proof

Rerun the local Docker end-to-end rehearsal (stage 2a on staging) with pooling on and off, on the same snapshot.
- Report wall time and SQLcl processes started in both modes.
- Check from the evidence lines that every postcondition ran in the reader's session, not the writer's, and that every reset passed.
- Then run a read-only pass against DEV26 (catalog captures and checks through the pool) to confirm the live per-script cost. Expect about 0.5 s of reset plus the script's own round trips, against about 6.5 s per launch today.

## Left to the builder

- The exact reset `SET` block, whether `CLEAR` needs more options, and whether the `SHOW ALL` comparison stays on outside tests.
- The sentinel nonce format and the loop batch size.
- The Windows proof and its outcome.
- Whether the dev-test runners get the pool now or later. Not required for deployments.

## As built (2026-11-22)

- **Transport and start.** The pool starts SQLcl through the existing safe launcher, with `-name <alias> @loop0.sql`, so the first connect happens at start. Only `cd <run dir>`, `@<driver>` and a sentinel go through a slot pipe; the driver itself stays a regular file. A process is retired after 12 loop files.
- **Reset is one PL/SQL call.** It sets CURRENT_SCHEMA, NLS, compiler settings and DBMS_METADATA transforms, checks the edition, and ends with `DBMS_SESSION.RESET_PACKAGE`.
  - Success is the `PROMPT TEAM_POOL_RESET_OK` that SQLcl prints after the block, because RESET_PACKAGE discards DBMS_OUTPUT from the same call.
  - Any error ends the process through WHENEVER, and the pool starts a new one before sending the script.
- **Client reset.** `STORE SET` is taken at process start and run before each script, followed by `CLEAR COLUMNS/BREAKS/COMPUTES`, then `UNDEFINE` for each variable the previous driver defined.
  - `SQLCL_POOL_VERIFY_RESET` was not implemented: the `STORE SET` script restores every SET option deterministically, as checked against SQLcl 26.3.1.
- **Settings.** `SQLCL_PERSISTENT_SESSIONS` (0/1) and `SQLCL_POOL_MAX_READERS` (1-4) are accepted by all three loaders. An inherited environment value is allowed, so one run can turn the pool off.
- **Tests.** The test bootstraps (`_test_subprocess_safety`, `_no_real_sqlcl`) and the CI runner default `SQLCL_PERSISTENT_SESSIONS=0`; only `tests/test_sqlcl_pool.py` turns it on, with the protocol fake `tests/fake_sqlcl_pool.py`.
- **Windows** falls back to one SQLcl per script in this change (`fallbackReason: windows-pipes`). A named-pipe transport is a follow-up.
- **Reports.** A rollout report carries `sqlcl` (mode, processesStarted, databaseSessions, scripts). Each run folder gets `sqlcl-session.json`.

