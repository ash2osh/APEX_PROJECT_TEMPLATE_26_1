# Feature ownership and DEV drift

Status: design for the feature-release path. The implementation lands in the same pull request.

A release capsule installs the **feature file**, not what is on DEV. Two things can therefore put an old
version of a stored unit into a release without any command complaining:

1. **Two features hold the same unit.** The copies drift apart; the release installs whichever feature it selects.
2. **A feature file is older than DEV.** DEV was changed (compiled by hand, by a teammate, by another feature)
   and the file was not refreshed.

## What the template does today

| Situation | Result today |
| --- | --- |
| A release selects both copies of a package | `feature freeze` refuses: `duplicate stored unit identity across selected release checkpoints` |
| A release selects only the older copy | `feature freeze` succeeds and the capsule installs the older package |
| A second feature runs `feature capture` for a package another feature holds | Allowed, nothing is reported |
| `feature capture --refresh` over a file that has lines DEV does not have | Overwrites without showing what disappears |
| A feature file is older than DEV | Not detected: `freeze` and `rollout --prepare` compare the capsule with the *target*, never with DEV |
| An owner decides a feature file keeps a line DEV lacks | There is nowhere to record it |

## Design

### D1. One command for the repository: `feature doctor`

`scripts/team.sh feature doctor [--feature <slug>] [--live]`

Offline checks (always):

- **Ownership.** Every claim is a stored-unit file (identity from the template's own source analysis:
  schema, type, name; spec and body are separate units) or an object created in a `ddl.sql`. A claim made by more
  than one feature is an error. `ALTER TABLE ... ADD COLUMN c` claims the pair (table, column), so two features may
  add different columns to one table.
- **Orphan checks.** A postcondition in a feature's `checks.json` that names a stored unit whose file is not in that
  feature is reported (warning).
- Exit code 0 clean, 1 findings, 2 could not run.

`feature freeze` runs the offline checks first and refuses on an ownership error.

### D2. What counts as a claim

| Source | Claim |
| --- | --- |
| `packages/*.pks.sql`, `*.pkb.sql`, `triggers/*.sql`, stored source files | `(schema, type, name)` |
| `CREATE TABLE`, `SEQUENCE`, `INDEX`, `VIEW`, `SYNONYM` in `ddl.sql` | `(schema, type, name)` |
| `ALTER TABLE t ADD (c ...)` in `ddl.sql` | `(schema, "COLUMN", t.c)` |

### D3. Moving a unit between features: `feature capture --move-from <slug>`

`feature capture` for a unit another feature holds is refused and names the owner. `--move-from <slug>` names it as the
source of a deliberate move. The command compares the old file with the current DEV capture first:

| Old file compared with DEV | Move does |
| --- | --- |
| Equal | Proceeds: removes the old files and the old feature's checks for the unit, writes the DEV capture |
| Behind DEV (DEV has more) | Proceeds and prints the old-to-new diff for review |
| Ahead of DEV, diverged, or an accepted difference exists | Refuses and lists the lines the capture would erase |
| Unit not on DEV | Refuses to capture |

Ways forward after a refusal: apply the lines to DEV and repeat; `--discard-unapplied` to erase them knowingly;
`--keep-file` to move the old bytes unchanged (an accepted-difference entry travels with the file).

### D4. Drift against DEV: `feature doctor --live`

Read-only. Reads the DEV source of every stored unit of every feature through the `CODE_*` profile (one fixed
`SELECT` on `ALL_SOURCE` in a read-only transaction), and compares it with the file, ignoring comments, blank lines,
whitespace and letter case. Each file is `EQUAL`, `BEHIND DEV`, `AHEAD OF DEV`, `DIVERGED`, `NOT ON DEV` or
`ACCEPTED`. `feature freeze` runs the live check when the DEV profile is configured; `--no-live "<reason>"` skips
it and the reason is recorded in the capsule. Without a DEV profile the report says the check was not live.

### D5. Differences the owner decided on: `features/<slug>/accepted-differences.json`

```json
[{"schema": "APP_CODE", "type": "PACKAGE BODY", "name": "ITEM_LOOKUP",
  "decision": "who decided, when, where it is recorded",
  "featureOnly": ["normalized line present only in the file"],
  "liveOnly": ["normalized line present only on DEV"]}]
```

A difference is `ACCEPTED` only while the differing lines equal the recorded lines; any other drift still fails.

### D6. `feature capture --refresh`

`--refresh` applies the D3 table to the file it replaces: lines the file has and DEV does not (unapplied edits, or an
accepted difference) stop the refresh unless `--discard-unapplied` is given.

## Examples

Names are generic.

| # | Before | Command | Result | After |
| --- | --- | --- | --- | --- |
| 1 | `inventory` holds `ITEM_LOOKUP`, equal to DEV | `capture orders --package ITEM_LOOKUP --move-from inventory` | Moves | `orders` holds it, equal to DEV; `inventory` has no file and no check for it |
| 2 | `inventory`'s file is 700 lines older than DEV | same | Moves, prints the 700-line diff | `orders` holds the DEV version |
| 3 | `inventory`'s file has 6 lines not compiled on DEV | same | Refuses, lists the 6 lines | unchanged; compile them on DEV and repeat, or `--discard-unapplied` |
| 4 | file has a new block and DEV has a new procedure | same | Refuses, shows both sides | unchanged |
| 5 | an accepted difference is recorded for the file | `capture ... --refresh` or a move | Refuses; with `--keep-file` the file and the entry move | `orders` keeps the decision |
| 6 | two features hold `ITEM_LOOKUP` | `feature doctor` | Reports it and which copy is closer to DEV | delete the other copy |
| 7 | `orders` runs `capture` for a unit `inventory` holds, no flag | `capture orders --package ITEM_LOOKUP` | Refuses and names `inventory` | unchanged |
| 8 | file never compiled on DEV | `--move-from` | Cannot capture; refuses unless `--keep-file` | file moves unchanged |

## Not covered

- Views, DDL files and data scripts are checked for ownership but not compared with DEV.
- The live comparison covers stored sources of the schema the `CODE_*` profile logs in to.
- A unit claimed by a feature and also by an old `migrations/` folder is not detected.

## Tests

Offline unit tests for each row of the tables; live checks (opt-in, Docker) in `tests/test_live_feature_release.py`
for `doctor --live`, a move and a refused refresh, as described in [live feature-release checks](live-feature-tests.md).
