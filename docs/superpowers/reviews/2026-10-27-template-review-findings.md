# APEX 26.1 template review: open findings

Date: 2026-10-27

Scope: the uncommitted implementation on branch codex/feature-release-capsules-impl,
based on e48b7053c53b05e014a30d511c1f399e880460ec. The review inspected the latest
feature workflow and its interactions with migration preflight, target profiles,
application deployment, upgrade ownership, archive/baseline safety, and CI.
Database-facing reproductions used isolated fixtures and replaced the SQLcl
boundary; no live Oracle operation was performed.

All findings below are open. The earlier 2,108-test local pass is historical
qualification evidence, not evidence that these regressions are covered.

Repair plan: [feature release review remediation](../plans/2026-10-27-feature-release-review-remediation.md).

| ID | Priority | Finding and reproduction | Source at review |
| --- | --- | --- | --- |
| F1 | P1 | Version-2 execution without --capsule enters the legacy executor. A production SQL-only manifest returned success without staging proof; a mixed manifest executed its SQL step before rejecting feature-migrate. | scripts/rollout.py:2240 |
| F2 | P1 | Supported DDL has no focused dependency preflight. CREATE TABLE EARLY followed by CREATE INDEX IX ON MISSING_TABLE(ID) produced a prepared plan with zero preconditions; MISSING_TABLE was absent from capture scope. Earlier DDL can commit before the later statement fails. | scripts/feature_manifest.py:263; scripts/feature_release.py:905 |
| F3 | P1 | A no-op checkpoint skips durable unresolved-attempt checks and completion. An unknown attempt remained unresolved while a normal staging retry returned success and its stage proof was accepted. No-op recovery left recoveredBy unset. | scripts/feature_release.py:1232 |
| F4 | P1 | Cleanup infers release success only from feature write attempts. It was eligible with a failed production app step; a verified production no-op was ineligible because no attempt existed. | scripts/release_state.py:1041 |
| F5 | P1 | Abrupt termination leaves attempting, but the recovery route accepts only unknown. The documented --recover path refused that persisted state while ordinary writes remained blocked. | scripts/release_state.py:705 |
| F6 | P1 | Two schemas in one database/container are treated as conflicting identities. Preparation of APP_CODE plus APP_DATA failed despite the same observed database and edition. | scripts/feature_release.py:751 |
| F7 | P2 | Preparation resolves the normal read profile, while execution resolves the migration profile. An independently configured migration connection/login was refused as target drift. | scripts/feature_release.py:740,1185 |
| F8 | P2 | Target settings are retained in applySettings but omitted settings are not emitted before CREATE OR REPLACE. A planned PLSQL_CCFLAGS=branch:TRUE was absent from the generated driver, allowing session defaults or a previous input's settings to compile the unit. | scripts/release_capsule.py:466; scripts/feature_release.py:347 |
| F9 | P2 | Stored-unit uniqueness is local to one checkpoint. Capsule generation accepted two different versions of APP_CODE.PROCEDURE.P in separate checkpoints. | scripts/feature_manifest.py:377 |
| F10 | P2 | All SQL-script and ORDS steps count as uncovered object work. A successful staging capsule with an additional UPDATE had incomplete object coverage and could not qualify for production. | scripts/rollout.py:2139 |
| F11 | P2 | Initializing a second schema for the same feature refuses the existing shared README. | scripts/feature_cli.py:67 |
| F12 | P2 | Review directory components repeat the full object name and exceed filesystem limits. An accepted 128-character package name failed review generation with file name too long. | scripts/feature_sources.py:509 |

F8 follows Oracle's documented compilation model: explicit CREATE OR REPLACE
uses compilation settings from the session. See
[PL/SQL units and compilation parameters](https://docs.oracle.com/en/database/oracle/oracle-database/19/lnpls/architecture-pl-sql.html).

The F10 repair must also address target binding before enabling mixed-capsule
promotion: current version-2 standalone SQL/ORDS steps embed one connection and
login in the frozen manifest. Merely relaxing coverage would retain the staging
binding during production promotion.
