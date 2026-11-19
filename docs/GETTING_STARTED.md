# Getting started

This guide takes you from nothing to a working setup: a connection that
passes its health check, your first export of an APEX app, your first change,
and your first database migration. Plan on about 30 minutes, plus the time to
install anything you are missing.

Every command is shown for Bash (Linux, macOS, Git Bash on Windows). On
Windows you can run `pwsh -File scripts/team.ps1 <command>` instead of
`scripts/team.sh <command>`; the arguments are the same.

## 1. How it fits together

```text
 Your computer                          Shared by the whole team
┌────────────────────────────┐         ┌──────────────────────────────┐
│ your own Git repository    │         │ development Oracle database  │
│  apps/       APEX source   │ export  │  + APEX workspace (Builder)  │
│  database/   read-only copy│ ◄────── │                              │
│  migrations/ your SQL      │ publish │   the source of truth        │
│                            │ ──────► │                              │
└────────────────────────────┘         └──────────────────────────────┘
        the template's scripts reach the database through SQLcl
```

Four ideas are enough to start:

1. **The shared database is the truth.** Your Git repository holds a copy of
   the APEX apps (as APEXlang text files) so you can review changes, but the
   live app in the shared APEX workspace is what actually runs.
2. **One repository per developer.** Each developer has their own copy of this
   template. Repositories do not share commits, so Git does not protect the
   shared database. You coordinate with teammates in person or in chat.
3. **You always choose the direction.** `export` copies the live app *into*
   your files. `publish` copies your files *into* the live app. Nothing moves
   by itself.
4. **Passwords live in SQLcl, never in files.** This repository only stores
   the *name* of a saved SQLcl connection.

What each folder is for:

| Folder or file | What it holds | Who changes it |
| --- | --- | --- |
| `apps/<SCHEMA>/<app-id>/` | One APEX app as APEXlang (`.apx`) files | `export` writes it; you edit it and `publish` it |
| `database/<SCHEMA>/` | A read-only copy of your tables, views, code and synonyms (and, when configured, `ords/schema.sql`, the ORDS REST definition) | `backup-db` (and `backup-ords`) writes it; never edit by hand |
| `migrations/` | Dated SQL changes you write, one folder each | you |
| `app_context/` | Notes about each app, for AI assistants | you |
| `.env` | Literal configuration and SQLcl saved connection names (no credentials) | you; review and keep it in your own Git repository |
| `scripts/`, operational `docs/`, `.agents/` | Command implementations and guidance | template upgrades |
| Inherited `tests/` and `.github/` | Original-template maintenance and CI | remove from a new downstream clone after recording the upgrade baseline |

## 2. What you need

Check each row. The command in the last column prints the version.

| You need | Version | Check with |
| --- | --- | --- |
| An Oracle database with **APEX 26.1 or newer** and a workspace | 26.1+ | see the check at the end of step 5 |
| **SQLcl** | 26.1 or newer | `sql -V` |
| **Git** | any recent | `git --version` |
| **Python** | 3.10 or newer | `python3 --version` (Windows: `py -3 --version`) |
| **Bash** | 4.4 or newer | `bash --version` |

Notes:

- **macOS** ships Bash 3.2, which is too old. Install a current one with
  `brew install bash` and run the scripts with it.
- **Windows** needs Git for Windows (it provides Bash). A Python from python.org
  or winget provides `python.exe` and `py`, not `python3`, so check it with
  `py -3 --version`; `team.ps1` finds either one. PowerShell 7 or
  Windows PowerShell 5.1 can run the `team.ps1` wrapper. Windows PowerShell 5.1
  refuses to run scripts until `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`,
  and migration files must be saved as UTF-8 without a BOM and with LF line
  endings; see the Windows notes in the [README](../README.md#quickstart) and
  [Troubleshooting](TROUBLESHOOTING.md).
- Optional: `uv` and Graphify for the [knowledge graph](../README.md#optional-knowledge-graph),
  and an AI coding assistant such as Claude Code or Codex.

## 3. No APEX database yet? Run one on your computer

If your team already has a shared development database, skip to step 4.

To practice locally, the open-source
[United Codes `uc-local-apex-dev`](https://github.com/United-Codes/uc-local-apex-dev)
project runs Oracle Database 26ai Free, APEX and ORDS in containers. It needs
Docker or Podman (with the `compose` command), SQLcl on your `PATH`, `unzip`,
and `curl` or `wget`, plus roughly 4 GB of memory, 3 CPUs and 35 GB of disk.

```bash
git clone https://github.com/United-Codes/uc-local-apex-dev.git
cd uc-local-apex-dev
./install.sh                 # takes 20 to 40 minutes
./local-26ai.sh create-user  # creates a schema and an APEX workspace; follow the prompts
```

It opens APEX at `http://localhost:8181/ords/apex` and registers a SQLcl saved
connection for each user it creates. A saved connection names a host and port.
When the container that listens there is stopped, the connection fails with
ORA-12541 (no listener), even though the saved login is correct. Start that
container, or use a connection whose port is serving.

Run `./local-26ai.sh --help` for the other helpers, such as `upgrade-apex` (if
you need 26.1 or newer) and
`unexpire-accounts` (if a login says the account is locked). Their
[documentation](https://www.united-codes.com/products/uc-local-apex-dev/docs/)
is the authority for that setup; this template only needs a schema, a
workspace, and a saved connection.

This gives you a schema and a workspace, **not an APEX application**. Before
step 8, create or import an app in App Builder and note its numeric ID;
`export` can only export an app that already exists.

## 4. Create your project

Get your own copy of this template. Pick one:

**A. On GitHub:** open the template repository and click **Use this template**,
then clone your new repository. (A repository owner turns this button on once
under *Settings → General → Template repository*.)

**B. From the command line:**

```bash
git clone https://github.com/ash2osh/APEX_PROJECT_TEMPLATE_26_1.git my-apex-project
cd my-apex-project
git remote rename origin template     # keep the template as a separate remote
git remote add origin <your-new-repository-url>
```

Either way, the files `AGENTS.project.md`, `PROJECT.md` and
`.agents/rules/project.md` are yours. Put your project's own notes there,
because template upgrades replace `README.md` and `AGENTS.md` but never touch
those three.

### Post-clone cleanup

Do this in your new downstream project before its first push. The original
`APEX_PROJECT_TEMPLATE_26_1` repository retains its tests, workflows and
Dependabot for template development. The cleanup below is for a fresh clone;
in an established project, preserve any project-specific tests or CI first.

Record the installed template baseline while the checkout is clean:

```bash
scripts/team.sh upgrade-template --dry-run
scripts/team.sh upgrade-template
```

These upgrade commands do not connect to Oracle. Review any `.template-new`
files and resolve them before continuing. Keep the generated
`.template-lock.json`: it lets future upgrades preserve intentional deletion
of installed template files. Review and commit the upgrade result in your own
repository before cleaning it.

Then perform the cleanup from file-level provenance, not broad directory sweeps:
never delete a file simply because it lives under `tests/`, `.github/` or
`docs/superpowers/`. Review each file against `template-manifest.json` and
`.template-lock.json`:

```bash
# Workflows: list what this repository ships, then remove only the inherited template-maintenance workflows.
# A project's own workflow, for example a deployment workflow, must be listed and kept before anything is removed.
# Never remove by glob.
git ls-files .github
git rm --ignore-unmatch .github/workflows/template-checks.yml .github/dependabot.yml
# Tests: the lock records each test the upgrade installed from the template. A project's own regression tests
# are not in the lock. List the recorded tests, then remove by name only the inherited ones you reviewed.
python3 -c 'import json; print("\n".join(sorted(p for p in json.load(open(".template-lock.json"))["files"] if p.startswith("tests/"))))'
# Example, one reviewed path at a time: git rm --ignore-unmatch -- tests/test_name.py
# Planning documents: docs/superpowers/ holds the template's historical plans (templateOnly in the manifest, so
# upgrade-template does not install them). Remove only those by name after review; keep plans your project wrote.
# The shared-core stamp belongs to the template repository's shared-core check. A project created from the
# template inherits it, but it is not part of a downstream project; upgrade-template never ships it.
git rm --ignore-unmatch .core-stamp.json
git status --short
```

Explicitly preserve:
- Project-specific regression and unit tests in `tests/`, including any file the project added or depends on
- Project-written plans, specs and other documents under `docs/`
- `PROJECT.md`, `AGENTS.project.md`, `.agents/rules/project.md` and `TODO.md`
- Operational configuration (`.env`), application source (`apps/`), migrations (`migrations/`), and migration receipts and recovery evidence

Keep `scripts/`, operational documentation, `.agents/`, `.claude/`,
`template-manifest.json` and `.template-lock.json`; remove `.core-stamp.json`
as shown above. Configure the credential-free root `.env` in step 6 and keep it
in your own Git repository after validation. Review the cleanup, commit it, and
then push to your downstream remote.

After this cleanup, `scripts/team.sh template-status` reports removed tests and
`.github/` files as `removed-by-cleanup`. That state is informational, not drift:
the status stays `current` when nothing else differs.

An upgrade keeps previously installed files deleted (`KEEP-DELETED`), but may
introduce new template test/workflow files. Review those after every upgrade.
Do not delete your project's own regression tests as part of repeated cleanup.

### Recover an existing 26.1 upgrade lock

If your 26.1 project's `.template-lock.json` still records
`https://github.com/ash2osh/APEX_PROJECT_TEMPLATE_TEAM.git`, the upgrade may
refuse that repository's newer manifest contract. The lock's upstream takes
precedence over the local manifest; an explicit `--source` takes precedence over
both. With a clean working tree, review a dry-run and then apply the same source:

```bash
scripts/team.sh upgrade-template --source https://github.com/ash2osh/APEX_PROJECT_TEMPLATE_26_1.git --ref main --dry-run
scripts/team.sh upgrade-template --source https://github.com/ash2osh/APEX_PROJECT_TEMPLATE_26_1.git --ref main
```

Dry-run changes no files. Apply records the chosen source in the lock, preserves
local changes and emits `.template-new` files for conflicts. Resolve those
conflicts and review and commit the upgrade and lock together. Retain the old
lock until the upgrade writes its replacement. Deliberate custom forks keep
their recorded source unless explicitly overridden. See
[lock recovery](../README.md#recover-an-older-template-lock) for conflict and
version-selection details.

## 5. Save your SQLcl connection

SQLcl keeps the password in its own secure store. Save one connection for your
development schema:

```bash
sql /nolog
```

```text
SQL> connect -save my-dev -savepwd DEMO@localhost:1521/freepdb1
Password? ********
SQL> exit
```

Replace `my-dev` with any name, `DEMO` with your schema, and the address with
your database's host, port and service. If you used `./local-26ai.sh
create-user` in step 3, the connection already exists. List your saved
connections with:

```bash
sql /nolog
SQL> connmgr list
```

While you are connected, check the APEX version (step 2 asks for 26.1 or newer):

```text
SQL> connect -name my-dev
SQL> select version_no from apex_release;
```

## 6. Configure `.env`

```bash
cp .env.example .env
```

On Windows PowerShell use `Copy-Item .env.example .env`. Open `.env` and change
only what differs for you. Comment lines start with `#`; values are literal, so
do not add spaces or trailing comments.

| Setting | Meaning | Example |
| --- | --- | --- |
| `DEVELOPER_NAME` | Your name in capitals. It is stamped into the app version every time you publish, so teammates can tell whose import it was. | `ALICE` |
| `DB_ENVIRONMENT` | What kind of database this is: `development` for a shared dev database (the others are `test`, `staging` and `production`, in lowercase; anything else is refused with `DB_ENVIRONMENT must be development, test, staging, or production`). | `development` |
| `APEX_APP_ID` | The numeric IDs of your APEX apps, separated by commas. | `100,200` |
| `*_SCHEMA` | The schema that owns your tables, your code, and your APEX apps. | `DEMO` |
| `*_SQLCL_CONNECTION` | The saved connection from step 5. | `my-dev` |
| `*_EXPECTED_USER` | The database user that connection logs in as; scripts verify it. Supported commands can use a login different from `*_SCHEMA`; see [running as a login that acts as another schema](login-acts-as-schema.md). | `DEMO` |

The example uses the same schema, connection and user for tables, code and APEX,
which is right for most projects. If you work with an AI assistant, you can ask
it to run `/init` and it will ask these questions for you.

To see which schema, connection and login each operation will use, run
`scripts/team.sh targets`. It reads `.env` only and never connects.

## 7. Check the connection

Both checks below are read-only. Run the offline one first:

```bash
scripts/team.sh targets
```

It prints one row per operation (`read` for code metadata, `migration` for
`migrate`), with the schema, saved connection and login taken from your `.env`,
so a wrong name shows before anything connects. A `REFUSED` row names the setting
that stops that operation; the notes under the table explain a split owner.

Then check the DEV database connection. `doctor` connects and checks the login it
gets:

```bash
scripts/team.sh doctor
```

You should see:

```text
SQLcl target: session_user=DEMO, current_schema=DEMO, db_name=FREEPDB1, db_unique_name=FREE, service=freepdb1
...
SQLcl connection and database identity checks passed.
APEX_DOCTOR_VERIFIED:DEMO
Doctor checks passed for the configured DEV connection.
```

`doctor` only reads. If it fails, [TROUBLESHOOTING.md](TROUBLESHOOTING.md) lists
each message and what to do.

You have no application folder yet, so `scripts/team.sh verify-local` would now
report each configured application as `FAIL` (`configured application 100
directory not found under apps/`) and exit 2. That is expected until your first
export: run `verify-local` at the end of step 8, not here.

## 8. Export your first app

```bash
scripts/team.sh export 100
```

Use one of your own app IDs. You should see lines like:

```text
Exporting Workspace DEMO - application 100:Employee Self Service
File apps/DEMO/employee-self-service/application.apx created
```

The folder is renamed to the app ID when the export finishes:

```text
apps/DEMO/100/
├── application.apx        the app itself
├── page-groups.apx
├── pages/                 one .apx file per page, e.g. p00001-dashboard.apx
├── shared-components/     authorizations, lists, LOVs, and so on
├── workspace-components/
├── .apex/apexlang.json    export metadata (commit it with the rest)
├── deployments/           environment settings (next step; starts with default.json)
└── apex-team-export.json  records when the export was taken (used by publish)
```

### Tell the template where the app deploys

Publishing needs a small descriptor for each app that names the workspace, the app ID, and
the parsing schema. For each app folder, copy the example and edit the three values
(for another app, set its own `"id"`):

```bash
cp apps/templates/deployments/dev.json apps/DEMO/100/deployments/dev.json
```

```json
{
  "workspace": { "name": "DEMO" },
  "app": {
    "id": 100,
    "databaseSession": { "parsingSchema": "DEMO" }
  }
}
```

The same folder can hold `staging.json` and `prod.json` later.

### Check the app and the configuration

Now that the app folder exists, check it. This check is offline and changes nothing:

```bash
scripts/team.sh verify-local
```

Every line should say `PASS`. A line that says `ATTENTION` or `FAIL` names the file
or setting to fix; the command exits 0 only when every line passes.

`verify-local` expects an app folder for every ID in `APEX_APP_ID`. The example `.env`
lists `100,200`, so if you exported only app 100 you will still see
`configured application 200 directory not found`. Export each ID you use
(`scripts/team.sh export <app_id>`), or remove the IDs you do not use from `APEX_APP_ID`.
[TROUBLESHOOTING.md](TROUBLESHOOTING.md#local-readiness) lists the fix for each line.

Commit the exports and descriptors together:

```bash
git add apps/
git commit -m "Export app 100"
```

After validation, review your root `.env` and version it in your own downstream
Git repository. Keep only literal configuration and saved SQLcl connection
names in it; credentials stay in SQLcl's secure store. The root `.env` is
available to Git, while nested `.env` files and `.env.*` variants are ignored.
Template upgrades preserve your `.env`, including when it is tracked.

## 9. Make a change

There are two ways to change an app. Use whichever suits the task.

### A. Builder first

1. Tell your team you are editing app 100 in Builder.
2. Make and save the change in APEX Builder.
3. Bring it into Git:

```bash
scripts/team.sh export 100
git status --short --untracked-files=all -- apps/DEMO/100/
git diff apps/DEMO/100/
git add apps/ && git commit -m "Change the dashboard title"
```

Review the APEXlang changes before you commit them; `git status` also lists new
files. Export captures the current Builder state and never imports the app back into
Builder. It refuses to write over a local source folder that has uncommitted or
untracked changes, so commit or stash your own edits first. It exports into
`scratch/`, checks the SQLcl result and that Builder did not change while the export
ran, and only then replaces the local source. The `deployments/*.json` descriptors you
wrote are kept.

### B. Files first

1. Edit a file. For example, in `apps/DEMO/100/pages/p00001-dashboard.apx`
   change `title: Employee Self Service` to `title: Employee Self Service Portal`.
2. **Tell your team which app you are publishing**, and check that nobody has
   unsaved work in Builder on it. Git cannot see Builder.
3. Publish to DEV. `scripts/team.sh publish` targets DEV only (promotions to staging or production use `deploy`). You do not need to commit first: publish imports the files as
   they are on disk, and the shared DEV database is the source of truth.

```bash
scripts/team.sh publish 100 --env dev
```

Publish refuses, with an explanation, if the live app changed since your last
export. That is the safety net: run `export`, review, and try again. Every refusal,
what it means, and what to do is in [publish-rules](publish-rules.md), which also
explains the publish tag. On success
it stamps your name and the date onto the app version, imports, re-exports the
app to prove it matches your files, and ends with:

```text
Published APEX App 100 to DEV (DEMO / DEMO).
Commit the stamped version in apps/DEMO/100/application.apx: Release 1.0 [ALICE-2026-09-30r001]
```

4. Commit what you published, your edit and the stamp, so your repository
   records what DEV runs. Do it before your next `export` of this app, which
   refuses to write over uncommitted files:

```bash
git add apps/DEMO/100/
git commit -m "Change the dashboard title (published r001)"
```

## 10. Make your first database change

Database changes are dated folders of numbered SQL files, plus a `checks.json`
that proves the change is safe and that it worked.

```text
migrations/2026-09-30_add-notes-to-hr-users-r001/
├── 001-add-notes-column.sql
└── checks.json
```

`001-add-notes-column.sql`:

```sql
ALTER TABLE HR_USERS ADD (NOTES VARCHAR2(200));
```

This example assumes the table `HR_USERS` already exists in your schema. If it
does not, first apply a migration that creates it, or pick a table you have.
The precondition below fails when the table is missing, which is what you want.

`checks.json` (each check is a query that must return exactly one row containing
the number `1`; `expected` is always `1`):

```json
{
  "schemaVersion": 1,
  "preconditions": [
    {
      "id": "notes-column-absent",
      "sql": "SELECT CASE WHEN EXISTS (SELECT 1 FROM user_tables WHERE table_name = 'HR_USERS') AND NOT EXISTS (SELECT 1 FROM user_tab_columns WHERE table_name = 'HR_USERS' AND column_name = 'NOTES') THEN 1 ELSE 0 END FROM dual",
      "expected": 1
    }
  ],
  "postconditions": [
    {
      "id": "notes-column-present",
      "sql": "SELECT CASE WHEN COUNT(*) = 1 THEN 1 ELSE 0 END FROM user_tab_columns WHERE table_name = 'HR_USERS' AND column_name = 'NOTES'",
      "expected": 1
    }
  ]
}
```

*Preconditions* must be true before the change runs; *postconditions* must be
true afterwards. Check first, then apply:

```bash
scripts/team.sh check-conflicts migrations/2026-09-30_add-notes-to-hr-users-r001 --env dev
scripts/team.sh migrate        migrations/2026-09-30_add-notes-to-hr-users-r001 --env dev
```

`check-conflicts` reads only. `migrate` runs the SQL, then confirms the result
through a fresh connection and writes `status.dev.json` next to your files as
proof. Once you have tried to apply a migration, never edit it: add the next
revision folder instead (`...-r002`). Commit the folder.

## 11. Everyday cheat sheet

| I want to… | Run |
| --- | --- |
| check my setup | `scripts/team.sh doctor` |
| check my files without a database | `scripts/team.sh verify-local` |
| see which schema, connection and login each operation uses | `scripts/team.sh targets` (offline) |
| copy a live app into Git | `scripts/team.sh export <app-id>` |
| push my edited files to the live app | `scripts/team.sh publish <app-id> --env dev` |
| refresh the read-only database copy | `scripts/team.sh backup-db` |
| export a schema's ORDS (REST) definition (optional, see [ords-export.md](ords-export.md)) | `scripts/team.sh backup-ords` |
| test a SQL change without a database | `scripts/team.sh check-conflicts <folder> --local` |
| test a SQL change against the database | `scripts/team.sh check-conflicts <folder> --env dev` |
| plan or run the DEV fixture suite | `scripts/team.sh dev-test --env dev --schema <OWNER> --plan` or `--run`; see [dev-test.md](dev-test.md) for retained-fixture and project-suite rules |
| start a package or procedure change from the live DEV source | `scripts/team.sh new-migration <name> --source "PACKAGE BODY:<NAME>" --env dev` |
| apply a SQL change | `scripts/team.sh migrate <folder> --env dev` |
| change a migration that was already attempted | `scripts/team.sh revise <folder>` |
| list the everyday commands | `scripts/team.sh` (no command); `--help` lists every command |
| see how two environments differ | `scripts/team.sh compare-schema --from dev --to staging --object <NAME>` |
| release to staging or production | `scripts/team.sh deploy <app-id> --env staging` |
| get the latest template scripts | `scripts/team.sh upgrade-template --dry-run` |
| see local template-file changes | `scripts/team.sh template-status` |
| look something up in the database, read-only | `scripts/team.sh query --env dev --connection code "SELECT ..."` |

## Next steps

- [EXAMPLES.md](EXAMPLES.md): step-by-step recipes for common tasks, including
  several schemas, releases, and working with an AI assistant.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md): what each error means and how to fix it.
- [../README.md](../README.md): the full feature list, the skills list, and the
  command reference.
- [publish-rules.md](publish-rules.md) and [migration-rules.md](migration-rules.md):
  every rule in detail.

## Optional workflow packs

`/init` offers Superpowers, Matt Pocock's skills, both, or neither (default).
Change the choice later with `scripts/team.sh skills setup <selection>` or
`team.ps1 skills setup <selection>`; inspect it with `skills status`.
See [workflow skill setup](workflow-skills.md) for pinned versions, the primary
workflow when using both, global-plugin limits and existing-project upgrades.
