# Team APEX agent contract

This repository is the APEX 26.1+ / APEXlang team template. The template
repository follows its normal branch and pull-request process: its `main`
is protected, so a change goes through a branch and a pull request, and
`python3 scripts/pre_push_check.py` runs before the push (see
[docs/ci-checks.md](docs/ci-checks.md)). That rule is for the template
repository only; how a downstream repository handles its own `main` is its
owner's choice. A project
created from it gives each developer a separate Git repository; the team
shares its development Oracle database and APEX workspace, not Git history.
Never exchange downstream commits or assume a colleague's repository changes
are present locally. A Git branch does not isolate shared database or Builder
state.

## Conversation style

At the start of every conversation, before your first reply:

1. Read `AGENT_STYLE` (default `standard`; one of `standard`, `concise`, `teaching`,
   `asharif-style`) and `AGENT_STYLE_LEARNING` (default `on`) from the root `.env`.
2. Read `.agents/styles/<AGENT_STYLE>.md` and follow it for the whole conversation.
3. Read `.agents/styles/personal.md` if it exists and apply it over the style.
4. Open your first reply with one line: `Style: <name>`, plus ` + personal layer (N entries)`
   when `personal.md` has entries. If the value is invalid or a file is missing,
   fall back to `standard` and say so in that line.
5. **Session-start release picker:** When the user starts a session without naming a
   release folder, run `scripts/team.sh release list` (offline). If open `draft` release
   folders exist under `releases/`, ask which folder to work on as a numbered list:
   `1- <folder a>`, `2- <folder b>`, ..., `N- Create a new release folder`.

Precedence, highest first: this file, `.agents/rules/agent-safety.md` and the project rules; then
`personal.md`; then the style. A style or a personal entry never relaxes a gate (commits and
pushes, database writes, release applies, imports, claiming a check that did not run).

Learning, unless `AGENT_STYLE_LEARNING=off`: when the developer states a preference or corrects your
format, or makes the same choice three times, add one dated line to `personal.md` under the matching
heading and say `Recorded in personal.md: <entry>` in the same reply. Never record silently. Replace
an entry that the new one contradicts. Keep the file under about 40 lines. Never record credentials,
hosts, customer, employee or business data, project or schema names, or anything that loosens a
safety rule. Never commit or push `personal.md` on your own initiative. See
[.agents/styles/README.md](.agents/styles/README.md).

## Optional workflow packs

Read `.agent-skills.json` at task startup (missing means `none`). It records
`selection` (`none`, `superpowers`, `mattpocock`, `both`) and `primary`.
Only apply an enabled repository workflow pack. With both selected, use the
primary pack's process by default; use the other for an explicit user request
or task override, without duplicating whole workflows. Direct user instructions
and project safety rules take precedence over either pack.

Set up packs only when requested, using `scripts/team.sh skills setup <selection>`
(or `team.ps1`). Use `skills status` for offline installation evidence. Selection
controls repository-managed copies, not global skills or enabled app plugins;
report those separately when they affect a request to use neither.

The 14 template-authored domain/setup skills remain
independent of optional workflow packs. After installing Matt's pack, invoke
`/setup-matt-pocock-skills` when requested and put its project guidance in
`AGENTS.project.md`, preserving existing instructions, instead of template-owned
`AGENTS.md`/`CLAUDE.md`. See [workflow skill setup](docs/workflow-skills.md).

## Configuration and application source

- Copy `.env.example` to root `.env`, set `DEVELOPER_NAME` to the
  developer's uppercase name, and use SQLcl saved connection names. After
  local validation, review and keep this credential-free configuration in
  each developer's own downstream Git repository. The
  default points the table, code, and APEX profiles at the same DEV
  connection. Keep these profile values aligned unless the project needs
  separate connections. Staging and production connection/user pairs are
  optional. Each profile's schema, connection, and expected-user keys accept
  position-aligned comma lists; one value keeps current behavior. Use
  `--schema <NAME>` to narrow any command. `doctor` and `backup-db` default to
  all schemas. Never put credentials in `.env` or tracked files. An optional,
  independent `ORDS_SCHEMA`, `ORDS_SQLCL_CONNECTION` and `ORDS_EXPECTED_USER`
  profile (all three or none) enables the read-only ORDS export; its session
  user must equal the REST schema.
- Use numeric APEX application IDs in commands and descriptors. Store each
  app's APEXlang source and `deployments/{dev,staging,prod}.json` under
  `apps/<parsing-schema>/<app-id>/`. `apps/templates/deployments/` contains
  descriptor examples. Each descriptor names the target workspace, numeric
  app ID, and parsing schema explicitly.
- Keep APEXlang and SQL files in LF line endings. Review generated source and
  database mirror changes before committing.
- The shared database is the runtime source of truth. Do not add custom team
  metadata tables, mutexes, checkout rosters, or database-backed release
  ledgers.

Supported commands may use a SQLcl login different from the target schema;
owner-only commands retain their owner-login checks. See
[docs/login-acts-as-schema.md](docs/login-acts-as-schema.md).

## Team workflow

- **Builder-first:** Coordinate with teammates before editing a shared app in
  Builder. Run `scripts/team.sh export <app-id>`, review the APEXlang diff, and
  commit it. Export records the observed Builder state; do not import as part
  of this route.
- **File-first:** Edit the exact APEXlang source; committing before publish
  is optional, since publish imports the files on disk. Before importing
  to shared DEV, tell the team which numeric app ID is being published and
  check for in-progress Builder edits. Run
  `scripts/team.sh publish <app-id> --env dev`. The drift guard compares the
  live app's update time with the database-time revision captured before the
  latest export. The exporter also checks that Builder did not change during
  that export. Oracle records this value at one-second precision, so the
  exporter and guard fail closed when it matches the current database second.
  This timestamp cannot see unsaved Builder edits; communicate with teammates
  before publishing. APEX leaves it null after an APEXlang import, so each
  DEV publish stamps `[DEVELOPER_NAME-YYYY-MM-DDrNNN]` onto the application
  version in `application.apx` before import, and the guard also refuses when
  the live version differs from the baseline (a teammate's import). Commit the
  stamped `application.apx` after publish; `deploy` ships the tag unchanged.
  The guard refuses to overwrite newer Builder work. Export and reconcile
  before retrying. After import, publish re-exports the app and requires
  exact APEXlang file and byte equality before it advances the DEV baseline.
  A failed or ambiguous verification leaves the old baseline in place, so the
  next publish still refuses newer Builder state. Use `--force` only when the
  user explicitly directs an override after review. When publish refuses,
  follow [docs/publish-rules.md](docs/publish-rules.md), which lists every
  refusal, its meaning, and the fix.
- **Release bundles (`releases/<slug>/`):** Store each schema/code/ORDS/app release in a focused bundle under `releases/<slug>/` with `release.json`, `01-ddl/`, `02-code/`, `03-ords/`, and `04-verify/`. Use `scripts/team.sh release new <slug>` to create a draft bundle and `scripts/team.sh release collect <bundle> --from dev --schema <SCHEMA> --object <TYPE:NAME> --mode <new|replace|patch> [--target-env <env>]` to export stored units into `02-code/`. Run read-only `scripts/team.sh release check <bundle> --env <dev|staging|prod>` before any apply. `release` commands have **zero interactive `[y/N]` prompts** and are 100% agent-runnable; `release run <bundle> --env <dev|staging|prod> --confirm-target <db_unique_name>` requires explicit user authorization for that write and fails closed if live `DB_UNIQUE_NAME` does not match. For DEV, staging or disposable/test targets, an agent supplies `--confirm-target` only when the developer asked in this conversation to run that target write, reading `db_unique_name` from that same target in that run with a read-only query (`SELECT SYS_CONTEXT('USERENV','DB_UNIQUE_NAME') FROM DUAL` through `scripts/team.sh query`) — never guessing or copying from a log or earlier run. For production, an agent passes `--confirm-target` only with the exact name the developer typed for that run. `release run` backs up existing touched objects to `scratch/backups/`, applies `01-ddl/` -> `02-code/` -> `03-ords/` in phase order (1 session for single-schema bundles; consecutive same-schema batches for multi-schema), fails only on *new* invalid objects (ignoring pre-existing unrelated invalids), runs `04-verify/`, deploys optional `apps` via `scripts/deploy.sh <app_id> --env <env> --yes --confirm-target <db_unique_name>`, writes a markdown report to `scratch/release-reports/`, records what it applied in `releases/<slug>/state/<env>.json` (commit it; DEV/staging reruns apply only changed steps, `--full` applies all; a failed DEV/staging run records its finished `01-ddl` files in `state/<env>.partial.json` and `--resume` skips them), marks the bundle `staged` after a successful staging run, and on `--env prod` requires a matching staging record (`--no-staging-proof` only on the developer's word), locks `release.json` (`status: "deployed"`) and creates Git tag `release/<slug>`. `release status <bundle>` shows what each environment holds. `release adopt <bundle> --env <dev|staging>` (read-only, applies nothing) records what a bundle that ran before state existed already holds, proving only what it can (`--report` proves DDL, ORDS and apps). Make a staging copy of production inert with `staging-neutralize` before any rehearsal write there; its `--apply` follows the same target-name rule. See [docs/release-workflow.md](docs/release-workflow.md).
- **Schema comparison:** Use `scripts/team.sh compare-schema --env staging
  --object CUSTOMERS` or `--from dev --to prod --pattern 'HR_*'` to compare
  selected live objects. This reports current catalog drift. Keep it narrow: a schema can
  hold thousands of objects, so never compare a whole schema (no `--pattern '*'`,
  no unfiltered run). Name the objects a change creates or changes (`--object`,
  repeated) or use a narrow pattern. For a readiness check, read only the
  change's own objects with one read-only query (`all_objects`, `all_synonyms`,
  `dba_source`), and check the synonym and source before calling an object missing.
- **Daily change record:** A stored package file holds the whole source, so Git
  cannot always show what changed since the database mirror. For each day with code work, keep
  `ai_generate/YYYY-MM-DD/` with readable diffs (`git diff` or unified diffs against `database/<SCHEMA>/`) and one `WALKTHROUGH.md` for that day. Commit the folder with the work. See
  [docs/daily-change-record.md](docs/daily-change-record.md).
- **Promotion:** Put an explicit deployment descriptor in the application
  source. Use `scripts/team.sh deploy <app_id> --env staging` or `--env prod` (or list app IDs in `release.json` `apps` so `release run` invokes `deploy.sh --yes --confirm-target <db_unique_name>`).
  Each direct `deploy` import requires the displayed `[y/N]` confirmation, typed at a terminal, or `-y` / `--confirm-target` under the unattended-run rule above (`TEAM_ACK_FROM_STDIN` is retired and ignored). Add
  `--manual` to print a DBA runbook without connecting. A deployment writes
  to the selected APEX workspace and parsing schema.
- **Other commands:** `scripts/team.sh doctor` validates `.env` and performs a
  read-only SQLcl identity check. `scripts/team.sh verify-local` checks the
  configuration, template lock, application sources and deployment descriptors
  offline (`--live` adds `doctor`). `scripts/team.sh backup-db` refreshes the
  local table and code mirrors, and the ORDS mirror when the ORDS profile
  exists. `scripts/team.sh backup-ords` exports ORDS metadata only: it never
  enables REST, imports, changes ORDS configuration, creates metadata, grants
  privileges or commits, and it never exports OAuth clients or secrets. Read
  [docs/ords-export.md](docs/ords-export.md) before changing it.

## Optional Tooling

Browser MCPs are optional and selected per checkout with `scripts/team.sh mcp setup`. The choice is Chrome, Firefox, both, or none; `scripts/team.sh mcp status` shows it. Setup writes ignored local client configuration and starts no browser or MCP process. Codex loads project settings only for trusted checkouts. When Chrome's direct MCP is selected, never start or call the Chrome daemon for the same session. Follow `docs/browser-mcp.md` and the selected browser skill.

[Playwright acceptance testing](docs/playwright-testing.md) is optional for repeatable multi-user checks in DEV. Use the [Playwright skill](.agents/skills/playwright-browser-testing/SKILL.md) and follow project-owned browser rules.

`graphify` (a knowledge-graph indexer exposed via ignored `graphify-out/`) is
optional; every script works without it. Its rules live in
[`.agents/rules/graphify.md`](.agents/rules/graphify.md) and
[`.agents/workflows/graphify.md`](.agents/workflows/graphify.md), and every rule
is gated on `graphify-out/graph.json` existing. Install it with
`uv tool install graphifyy --with tree-sitter-sql`, run
`python3 scripts/setup_graphify_apx.py` (rerun after every Graphify upgrade;
`--verify` checks without changing anything), then `graphify extract . --force`.
For routine `.apx` and `database/*.sql` graph updates, use only the offline
local CLI command `graphify update .`; do not use the Graphify skill, MCP, or a
provider API to update the graph. These updates need no LLM API key. Semantic
indexing of changed `app_context/**/*.md` is optional and separate.
The corpus is a domain allowlist of `apps/`, `database/`, and `app_context/`.
Graphify links cross-schema references and mirrored synonyms when their targets
are present in the database mirror. The graph reflects this repository's
files, not shared Builder state. When the graph exists, each new conversation
starts a background `graphify update .` (see the graphify rules for its
guards); it is skipped when Graphify is absent.

## Template update check

At the start of every new conversation, run once in the background:
`python3 scripts/check_template_update.py`. This read-only check compares the
lock's `commit` with its recorded `templateRef` (branch or tag), using a portable
10-second timeout on each Git call. It does not fetch objects into the project.

- Stay silent when the lock/ref is missing or invalid, a commit is pinned,
  the ref is ambiguous, the network/Git is unavailable, or the commits match.
- If the command prints an update notice, include it once in the first reply,
  or the next progress update if the background result arrives later. Do not
  delay the reply while waiting for it.
- Never run the upgrade or commit on your own initiative; the developer decides.

## Project instructions

- After cloning into a new downstream project, follow the
  [post-clone cleanup](docs/GETTING_STARTED.md#post-clone-cleanup) instructions:
  establish `.template-lock.json`, then remove inherited template-maintenance
  tests, GitHub workflows/Dependabot and historical planning documents. This
  cleanup applies to downstream projects, not the original template repository,
  which retains its tests and CI. Preserve project-specific regression tests
  when cleaning an existing project. Keep `.env`, operational scripts, agent
  guidance, the manifest and upgrade lock.
- `AGENTS.md`, `CLAUDE.md`, `README.md`, and `.agents/rules/agent-safety.md`
  belong to the template; `scripts/team.sh upgrade-template` replaces them.
  Put project-specific agent instructions in `AGENTS.project.md`, project
  rules in `.agents/rules/project.md`, and the project overview in
  `PROJECT.md`. The upgrade never overwrites those files.
- Read `AGENTS.project.md` and `.agents/rules/project.md` after this file.
  When they conflict with this file, ask the user which applies.

## Rules for coding agents

- Before reporting a defect or changing behaviour in a review or test run,
  check [docs/known-limitations.md](docs/known-limitations.md). The behaviour
  listed there is deliberate: do not report or "fix" it again unless it no
  longer matches that page.
- Before writing PL/SQL for APEX automations, workflow activities, task
  actions, or background execution chains, read
  `.agents/skills/apex-background/SKILL.md`.
- Read the relevant `.apx`, APEXlang, SQL, release bundle, and deployment descriptor files
  before editing them. Preserve the app's numeric ID and explicit workspace
  mapping. Do not invent a live workspace, schema, connection, or release
  result.
- Treat export, release, publish, and deployment commands according to
  their database effects. Do not run `release run`, import, or deployment unless
  the user requested that operation. Export only when requested because it
  refreshes tracked source from shared Builder state.
- Coordinate shared DEV app imports with the human team. There are no database
  pause tables or acknowledgement commands in this workflow. Never claim that
  team communication or a live database check happened unless it did.
- Do not commit or push silently. Follow explicit instructions for commits;
  do not push unless asked.
- If SQLcl, the database, or a requested environment is unavailable, report
  the check as unknown or unavailable rather than passed.
- Before writing version-dependent SQL or PL/SQL, obtain database version and
  compatibility information for the intended target through the configured,
  identity-guarded read-only flow. `scripts/team.sh doctor` (or `team.ps1 doctor`)
  reports the full database version and `COMPATIBLE` for each checked DEV target;
  existing schema-comparison observations also record a database
  version, but do not establish its compatibility setting. Do not infer staging
  or production capabilities from DEV. For code intended for several targets,
  use features supported by all of them, within their compatibility settings.
  Use modern SQL and PL/SQL when supported and appropriate; preserve behavior,
  established interfaces and data conventions. Do not rewrite working code only
  to modernize it or assume different constructs have identical semantics.
  Check Oracle documentation or the `db` skill for feature-specific requirements;
  a version observation alone does not prove every feature is enabled or usable.
  If the target is unavailable or its compatibility is unknown, report that and
  ask once for the required compatibility level before choosing version-dependent
  features; continue unrelated work. Never guess or maintain a database-version
  setting in `.env`, and never change database compatibility to fit the code.

See [README.md](README.md) for setup and command examples, and
[docs/release-workflow.md](docs/release-workflow.md) for the Lean 6-Step Release Bundle contract.
