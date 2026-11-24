# Agent safety rules

- Read APEXlang and SQL source before changing it or applying it. Keep numeric
  app IDs and explicit deployment workspace/schema mappings consistent.
- Do not place database credentials in `.env`, tracked files, command output,
  or logs. Use saved SQLcl connection names. After local validation, recommend
  reviewing and versioning the credential-free root `.env` in the developer's
  own downstream Git repository; commit only when explicitly authorized.
- Treat export as a read from shared Builder that refreshes tracked local
  source. Do not export unless requested, and review the result before
  committing it.
- Do not run `release run`, APEX imports, or deployments unless the user asked
  for that database write. Coordinate with teammates before importing into a
  shared DEV app; Git branches do not protect shared database state.
- Store each schema, stored-code, ORDS, verification, and app release bundle
  under `releases/<slug>/` (`release.json`, `01-ddl/`, `02-code/`, `03-ords/`,
  `04-verify/`). Run read-only `scripts/team.sh release check <bundle> --env <env>`
  before executing `release run`. `release` commands have zero interactive
  `[y/N]` prompts; `release run` requires explicit `--confirm-target <db_unique_name>`
  and user authorization for the write. For DEV, staging or a disposable/test target,
  an agent passes `--confirm-target` only when the developer asked in this conversation
  to run that write, using the `db_unique_name` read from that same target in that run
  via a read-only query; production requires the exact name typed by the developer for
  that run. `release` refuses `deployed` bundles and refuses `patch` entries whose
  `baseSha256` disagrees with live target source. See `docs/release-workflow.md`.
- For standalone `deploy` and `staging-neutralize`, `-y` / `--yes` answers a staging or production `[y/N]` prompt only when the developer asked in the conversation for that run to be unattended. Production also needs `--confirm-target` with the name the developer typed for the run.
  `TEAM_ACK_FROM_STDIN` is retired and ignored; piped or redirected acknowledgments stay refused, and `--yes` is the recorded route.
- Use `scripts/team.sh compare-schema` with exact names or object prefixes for
  read-only live drift reports. Catalog shape cannot reliably prove which
  historical release changed an object.
- `scripts/team.sh deploy` requires confirmation for staging and production.
  `--manual` prints a runbook and makes no connection. Do not describe the
  manual output as an executed deployment.
- Do not claim a live check passed unless it actually ran. Report unavailable
  checks as unknown.
- For confirmed inherited-template issues, check known limitations, record a
  sanitized entry in project-owned `TODO.md`, and follow
  [`docs/template-feedback.md`](../../docs/template-feedback.md). Resolve the
  repository from the template lock and manifest, never the downstream
  `origin`; search existing upstream issues/PRs before filing. A focused PR
  needs current-task authorization for upstream-only commit/push. Queue
  ambiguous or unsafe reports locally and continue safe work. Never disclose
  credentials, project source/data, or full logs.
- Do not commit or push without an explicit instruction. Never silently push.
