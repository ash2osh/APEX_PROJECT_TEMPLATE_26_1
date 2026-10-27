# Mutable feature sources and frozen release capsules

Date: 2026-10-27
Status: implementation contract for PR review. This PR contains documentation only.

Implementation plan: [feature release capsule plan](../plans/2026-10-27-feature-oriented-release-capsules.md).

## Outcome and scope

Keep one editable source directory per feature and one editable current release
manifest. Freeze selected source into a release capsule, review its package
diffs, rehearse it on staging, then promote the same payload to production.

The requested delivery order is template implementation and PR, downstream
template upgrade after merge, then downstream migration conversion and staging
qualification. This documentation PR supplies the spec and implementation plan;
it implements no commands and authorizes no database writes or template upgrade.
The target is the APEX 26.1 template. Work is inline, without subagents.

For a small release containing a couple of DDL statements and a few package
updates, the proposed database-object target is 120 seconds, including identity
revalidation, focused preconditions, apply, and final checks. A reviewed larger
object release may use up to 300 seconds. These are qualification targets, not
measured promises. APEX import has no fixed duration cap and is timed separately.
ORDS, data repair/backfill, preparation, and manual pauses also have separate times.

## Existing behavior and approach

At the observed template baseline `b1917cd`, `migrate.apply_batch` repeats
identity, inventory/catalog preflight, and preconditions for each migration
folder; `apply_folder` starts a SQLcl apply session for each folder. A rollout
already provides one operator command, one promotion confirmation, input hashes,
timings, and local receipts. Renaming folders alone cannot remove that overhead.

Three approaches were considered:

- Tune dated migration folders: a smaller change, but source/revision clutter
  remains and a release still lists historical migration folders.
- Mutable feature source plus a generated capsule: selected approach. Git keeps
  source history; one frozen payload represents the intended final release.
- One large hand-maintained SQL file: avoids directories but obscures feature
  ownership, review, and recovery boundaries.

The existing `baseline build --bundle` remains a generation helper. It does not
replace the new capsule execution path.

## Source layout and mutability

```text
features/
  staff-scheduling/
    README.md
    APP_DATA/
      ddl.sql
      checks.json
    APP_CODE/
      packages/
        dispatch_pkg.pks.sql
        dispatch_pkg.pkb.sql
      checks.json
releases/
  current.json
  .local-state.json        # ignored local attempt/receipt index
```

Feature SQL and checks are edited in place for later releases. There are no
dated or numbered revision directories in this route. Complete package sources
stay in stable files. One-time DDL contains only the pending operations selected
for the current release. The release manifest selects exact files and order;
after promotion, update that same manifest for the next release.

Selected release sources and the manifest must match their committed Git
versions before staging. Unrelated dirty files do not block preparation. The
capsule records the source commit and file hashes; Git preserves earlier
released versions after working files are edited.

The capsule is immutable while prepared, attempted, staged, or awaiting production.
Editing selected source invalidates that candidate and requires a new capsule and
staging run. After an ambiguous write, retain the old capsule/evidence until
reconciliation; the feature source does not become permanently immutable.
Cleanup after verified production removes generated payload copies and retains
compact receipts and the committed review diffs.

## Public workflow

The proposed commands are:

```bash
scripts/team.sh feature init staff-scheduling --schema APP_CODE
scripts/team.sh feature capture staff-scheduling --package DISPATCH_PKG --schema APP_CODE --env dev
scripts/team.sh feature diff staff-scheduling --schema APP_CODE

scripts/team.sh rollout releases/current.json --env staging --dry-run
scripts/team.sh rollout releases/current.json --env staging --prepare
scripts/team.sh rollout releases/current.json --env staging

scripts/team.sh rollout releases/current.json --env prod --prepare
scripts/team.sh rollout releases/current.json --env prod
```

`init` is an offline scaffold. `capture` is a guarded read from live DEV plus
local file writes; `--package` captures the complete spec and body when a body
exists. It refuses to overwrite edited source by default; `--refresh` is an
explicit recapture after reconciliation. A spec-only package is supported.
`diff` is offline and requires a retained capture baseline. There is no fallback
to the database mirror.

`--dry-run` stays offline: validate inputs, checks, ordering, and hashes; do not
evaluate live checks or create write-attempt/success receipts. `--prepare` reads
only selected live objects, creates review diffs and a target guard plan, and
writes local artifacts. It makes no database changes or success receipts.
Normal execution requires a matching prepared plan and one manifest confirmation
before any writes. A missing or changed plan prints the preparation command
and refuses execution.

Preparation happens before the production write window. Its duration is
reported separately, not hidden in the object execution measurement. Actual
execution revalidates the prepared target state and refuses drift; it never
silently refreshes an approved baseline.

Bash and PowerShell expose the same arguments, behavior, and exit codes.
Exit 0 means the requested operation completed, 1 means a check/confirmation/
budget gate refused, and 2 means invalid input, unavailable evidence, or an
unknown apply outcome. Preserve existing interrupt exit conventions.

## Release manifest version 2

```json
{
  "schemaVersion": 2,
  "databaseObjectBudgetSeconds": 120,
  "steps": [
    {
      "type": "feature-migrate",
      "schema": "APP_DATA",
      "inputs": ["features/staff-scheduling/APP_DATA/ddl.sql"]
    },
    {
      "type": "feature-migrate",
      "schema": "APP_CODE",
      "inputs": [
        "features/staff-scheduling/APP_CODE/packages/dispatch_pkg.pks.sql",
        "features/staff-scheduling/APP_CODE/packages/dispatch_pkg.pkb.sql"
      ]
    },
    {"type": "app-deploy", "appId": 100}
  ]
}
```

Version 2 accepts existing rollout step types plus `feature-migrate`.
The budget is an integer from 1 through 300, default 120 when omitted.
Each feature step is one schema/checkpoint and has `type`, `schema`,
and a nonempty ordered `inputs` list, with an optional nonempty `checks` path
list for an explicit intermediate boundary. A step can select files from several
features in the same schema. Infer the feature slug from
`features/<slug>/<SCHEMA>/...`; require its schema-level `checks.json`
and namespace check IDs by feature/check file. An explicit `checks` list
replaces that default and must remain under the selected feature/schema trees.
Keep the current schema-1 check format.

Validate UTF-8/LF, exact allowed keys, safe paths, schema/owner mapping, SQLcl
transport, explicit order, and duplicate object identities. Inputs must be
ordinary files inside the named feature/schema tree; refuse traversal,
symlinks/reparse points, and ambiguous owner changes. A stored unit may appear
only once across the selected release. Conflicting versions never select a
silent "last one wins."

The fast path accepts complete stored-source units and supported, statically
analyzable object DDL/grants. Opaque blocks, runtime DML, data repair/backfills,
and arbitrary dynamic SQL belong in separately reviewed existing step types.
Trusted generated source-delivery wrappers are permitted only when generated
from validated full source and bound to that source hash.

Legacy version-1 manifests and dated migration execution remain unchanged.

## Whole packages and review evidence

Feature capture reads the complete `PACKAGE` and `PACKAGE BODY` from
identity-checked live DEV, including existing compiler settings. Store full
source as separate spec/body files. A whole-package transfer selects both;
a later body-only change may select the complete body alone. Emit the final
source once per selected unit. An exactly matching, valid target unit may be
a recorded no-op; never omit a changed spec merely to save time.

Keep three views available for review:

1. Complete deployable source in the feature files.
2. Normal Git diff against the previously committed feature source.
3. Unified diffs under `ai_generate/YYYY-MM-DD/feature-diffs/`, with a
   `review.json` recording feature, owner, unit type/name, observed identity,
   before/after hashes, payload digest, and baseline kind.

The development diff compares captured live DEV source with edited feature
source. The deployment diff compares the actual selected staging/production
source with the same payload during `--prepare`. These baselines may differ;
a DEV editing diff is not proof of what production will replace.
DEV unchanged-since-capture guards apply to DEV work; staging and production
use their own captured before-state guards. Never copy a DEV source hash into
an unrelated target's expected before-state. Namespace artifacts by
feature/schema/unit/environment and payload digest to avoid
overwriting same-day reviews. A first-time source addition still gets a
meaningful live-source diff even when Git shows the whole file as new.
Daily `WALKTHROUGH.md` remains part of the existing change-record policy.

Use existing exact-source projections and SQLcl transport helpers. Preserve
meaningful whitespace, Unicode, dollar signs, quoting, and compiler settings.
Where SQLcl would alter source bytes, generate a trusted CLOB delivery wrapper
and retain the original readable source and its hash. Never diff generated
wrapper noise as the business change.

## Capsule and target plans

Generate a private capsule under ignored `scratch/release-capsules/`. It freezes
selected feature SQL/checks, the rollout source, shared APEX/ORDS inputs, source
commit, source-to-driver mapping, and generated driver hashes. Record two
different digests:

- `payloadDigest`: environment-neutral frozen sources and generated payload
  definitions. This must match staging and production.
- `targetPlanDigest`: environment-specific identity, expected before-state,
  focused guard queries, deployment descriptors, and review evidence. Staging
  and production plans normally differ.

Record an engine digest for the capsule generation/execution modules and trusted
SQL templates. A changed engine requires preparation and staging qualification
again. No generated or imported capsule may execute its own Python/shell code.

Production consumes the stored staged payload and its successful stage report.
A different checkout must receive that capsule/report or reconstruct the exact
recorded commit and verify its payload digest. Target descriptors and guards
are prepared separately for production and displayed in the normal confirmation.
A report is local operator evidence, not a cryptographic signature.

## Fast execution, timing, and recovery

Use one apply SQLcl session per compatible schema checkpoint. Keep pre/post
checks in the existing read-only harness and batch them at their real dependency
boundary. Preserve its check-size limits and session identity validation.
Intermediate dependencies that need verification create another checkpoint.

The feature path captures only selected-object state. Full-schema inventories
remain explicit baseline/audit operations. Revalidate target identity and
expected source/metadata immediately before each checkpoint. Deploy final
package versions once, then check exact source/settings and validity/errors
for selected units and explicitly declared dependents. Do not run an unbounded
schema-wide recompile. Missing required objects, compilation errors (including
SQLcl's warning-success output), or changed source produce failure rather than
a receipt. Preserve the existing treatment of ordinary compiler warnings.

Route all DDL/package work in a qualified release through `feature-migrate`.
The timing report lists included and excluded steps; object work remaining in
legacy/DBA steps makes coverage incomplete and the fast production qualification
ineligible. Measure `feature-migrate` execution from guarded revalidation through final
checks. Sum that time across all object checkpoints and compare it with
`databaseObjectBudgetSeconds`; preparation, APEX import, ORDS, data steps, and
pauses have independent durations. A stage budget overrun preserves verified
database results but disqualifies the stage report for production promotion.
Do not hard-kill active DDL to meet the aggregate budget. Stop before starting
further object writes after the budget is exhausted.

Before a possible write, atomically record the attempt in
`releases/.local-state.json`, outside scratch. Store target scope, capsule and
plan digests, checkpoint, state, and evidence references. This index is ignored
local receipt evidence and survives scratch cleanup. It is not a database ledger,
does not coordinate different repositories, and cannot prove current live state.
Only an owned local writer may update it; concurrent updates must fail closed.

An interrupted/unknown apply stays unresolved even if scratch is missing.
Refuse automatic retry or a new overlapping target release. Read the live
selected state before preparing recovery. The explicit
`--prepare --recover <attempt-id>` path binds a new reviewed target plan to
that attempt and the observed partial state; it executes no repair by itself.
Keep old attempt evidence and link a verified recovery rather than rewriting it.
Conclusive no-write connection refusals may use the current strict no-payload
proof; other failures remain unknown.

Cleanup defaults to a local dry run. `feature clean-capsule <digest> --yes`
may remove only generated payload/evidence after verified production and while
no unresolved attempt references it. Retain compact receipts, source hashes,
cleanup history, and review diffs. A missing success receipt never becomes a
cleanup shortcut.

## Adoption and qualification

Python 3.10+, standard library, SQLcl 26.3+ for the capture/prepare path, and
current APEX 26.1 source/deploy behavior are the implementation baseline.
Use target-observed database version/compatibility for feature-specific SQL;
introduce no guessed version setting or new database feature requirement.

Protect downstream `features/` and `releases/` from template upgrades.
Keep examples and the new user guide template-owned, with source trees and
local receipt state project-owned. Existing migration/check/receipt formats,
version-1 rollout arguments, and baseline generation stay compatible.

After the implementation PR is merged, upgrade the downstream template first.
Then inventory and reconcile old attempts, construct current feature sources
from final agreed objects, and create one checksum-manifested legacy archive
of exact SQL/checks/receipts/attempt evidence before removing converted active
folders. Retire old archive indexes only with their whole converted legacy
tree; never leave active families pointing into a removed tree. Keep one-time
data work separate. This conversion is a later project operation, not a side
effect of template upgrade or this documentation PR.

Required evidence before claiming runtime improvement: offline safety tests,
Bash/PowerShell and Windows parity, then an authorized disposable staging
rehearsal with the exact package/DDL payload, package diffs, SQLcl session counts,
per-phase times, and final source/settings/validity proof. No timing success,
production readiness, or live result is claimed by these documents.
