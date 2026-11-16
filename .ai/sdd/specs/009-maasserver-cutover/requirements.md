# Feature: Cut over `maasserver` to pytest (F06)

> Status: Draft (awaiting pass/fail measurement)
> Source: `.ai/sdd/PLAN.md` (F06), `.ai/sdd/ideas/003-coverage-gated-pytest-cutover.md`

## Overview

`maasserver` is the third and largest package in the coverage-gated
pytest cutover (`PLAN.md`), following F04's `metadataserver` pilot
(23 files) and F05's `provisioningserver` cutover (90 migratable
files). It is the single largest nose-run test population in the repo
(338 `test_*.py` files) and the last blocking full nose retirement.

This feature relocates every *migratable* `maasserver` legacy test
file to `src/tests/maasserver/` and drops those files from `nose`,
proving the migrated portion still meets its pre-cutover
branch-coverage baseline under pytest alone.

`PLAN.md` framed this work as two features: F06 ("no-gap tier", 197
files) and F07 ("gap tier", 141 files), partitioned by a grep for
scenario/reactor/`testresources` keywords. Direct measurement against
the live tree shows that partition is obsolete, so this single spec
covers the whole package (see Evidence Base):

- F03's `maastesting/pytest/legacy.py` shim already handles scenario
  multiplication (including inherited/merged `APITestCaseBase`
  scenarios, which file-local greps cannot see) and crochet reactor
  startup — the two dimensions PLAN called the "gap tier".
- `testresources` usage in `maasserver` test files is **zero** (a
  keyword grep produced false positives on local variables named
  `resources`; no `import testresources` exists).
- All 338 files already collect cleanly under pytest (9,260 tests, 0
  collection errors, after one stale-import fix).

The only genuine carve-out is `maasserver`'s 9 `legacy`-tagged test
classes (across 6 files), which cannot run in the same process as the
pytest suite for the same process-global-settings reason F03 documented
for `metadataserver` (idea 002, gap 3: `MAAS_PREVENT_MIGRATIONS=1`
selects a mutually exclusive `INSTALLED_APPS`/`MIGRATION_MODULES`
configuration, fixed once per process at `django.setup()`). Per F04's
precedent, those classes stay under `nose`'s `bin/test.region.legacy`
while their files' gap-free classes split out and relocate.

## Business Context

- **Problem:** `maasserver`'s suite currently runs **only** under
  `nose` (`testpaths = ["src/tests"]` means bare pytest never sees
  `src/maasserver`). It cannot be dropped from `bin/test.region` until
  each migratable file collects and passes under pytest with equal or
  better coverage.
- **Users:** MAAS engineers who write/run `maasserver` (region
  controller) tests daily; CI maintainers who want one test runner.
- **Value:** Removing `maasserver` from `nose` is the largest single
  step toward full nose retirement (F08). It proves the coverage-gated
  method at the repo's largest scale and collapses PLAN's planned
  two-feature split into one, since the premise for that split no
  longer holds.
- **Success signal:** The migratable `maasserver` files no longer run
  under `nose`; their pytest-only branch coverage contribution is
  demonstrated (not assumed) against the committed baseline, with the
  9-class legacy carve-out's coverage explicitly still attributed to
  `nose`.

## Evidence Base

Verified directly against the live tree (2026-11-18, post-F05):

| Fact | Value |
|------|-------|
| Legacy `maasserver` test files (outside `src/tests/`) | 338 |
| Tests collected from those files under pytest | 9,260 |
| Collection errors | 0 (after fixing one stale F05-fallout import) |
| Files already relocated to `src/tests/maasserver/` | 23 |
| `MAASTwistedRunTest` (reactor) carve-out files | 0 (unlike `provisioningserver`'s 39) |
| `testresources` usage | 0 files |
| Files producing scenario/parametrized nodes (collection-measured) | 103 |
| Legacy-tagged files (`MAASLegacy*TestCase` / Django `*TestCase`) | 6 |
| Legacy classes within those files (stay under nose) | 9 |
| Gap-free classes within those files (split out and relocate) | 20 |
| Cross-test import hazards (all intra-`maasserver`, resolve uniformly) | 57 sites across 8 modules |

The 6 legacy-tagged files, with their class split:

| File | Legacy classes (stay) | Gap-free classes (move) |
|------|----------------------|--------------------------|
| `forms/tests/test_helpers.py` | 1 | 4 |
| `tests/test_fields.py` | 4 | 13 |
| `models/tests/test_timestampedmodel.py` | 1 | 1 |
| `models/tests/test_cleansave.py` | 1 | 0 |
| `models/tests/test_managers.py` | 1 | 0 |
| `utils/tests/test_signals.py` | 1 | 1 |

All 6 import their test models solely from `maasserver.tests.models` —
the registered Django app module that stays in place (F04 precedent) —
so relocation breaks none of them.

**Pass/fail under pytest (measured 2026-11-19, `-n 4 --dist=load`,
30min; re-confirmed post-fix at `-n 2`, 41min):** 12,012 passed / 28
failed / 60 setup-errors / 13 skipped. Fully reconciled — every one of
the 88 non-passing nodes maps to a legacy class in the carve-out:

- **Legacy carve-out (the 9 classes, expected):** all 60 setup-errors
  plus all 28 failures come from the 9 legacy classes across the 6
  legacy-tagged files (`TestBulkManager`, `TestConnectToFieldChange`,
  `TestMAASModelForm`, `TestTimestampedModel`, and the `test_fields`/
  `test_cleansave` classes), failing with
  `psycopg2.OperationalError: database "no_such_db" does not exist` and
  `django.db` connection errors — idea 002's documented
  `MAAS_PREVENT_MIGRATIONS` gap-3, confirmed live. Their gap-free
  sibling classes in the same files all pass. The carve-out is real and
  necessary, not speculative.
- **Independent failures (originally 4 files, 29 nodes):** all four
  were resolved during design by shim/infra fixes (no test-content
  changes — see design §9): `test_plugin.py` (settings `MAAS_ROOT`
  import ordering), `test_subnet.py` (unparameterized
  `application_name` SQL), `test_auth.py` (unwrapped `partial` scenario
  values), `test_views.py` (missing lower-case logging level names).
  Post-fix they contribute **zero** failures.
- **Operational constraint, not a per-file gap:** the DB fixture does
  not tolerate high xdist worker counts at session startup (`-n auto`
  dies bringing up nodes; `-n 4`/`-n 2` run cleanly). A separate
  transient: a run started immediately after a coverage-baseline
  capture can die at worker startup from template-DB contention; it
  clears once the capture's cluster settles.

**Final split for this feature (338 files):**

| Bucket | Files | Action |
|--------|-------|--------|
| Clean (all tests pass) | 332 | mechanical relocation |
| Legacy carve-out, mixed | 4 (`test_helpers.py`, `test_fields.py`, `test_timestampedmodel.py`, `test_signals.py`) | split: 9 legacy classes stay under nose, gap-free classes move (F04 precedent) |
| Legacy-only files (0 gap-free classes) | 2 (`test_cleansave.py`, `test_managers.py`) | leave whole file under nose |

The 4 originally-failing files are folded into the clean bucket after
their design-time fixes. Total mechanically relocatable: 332 files,
plus the gap-free classes in the 4 mixed legacy files. The 2
legacy-only files stay under nose entirely.

## Relocation model (from F04 precedent)

- `maasserver.tests` is a registered Django app
  (`djangosettings/development.py:32`) whose `models.py` backs
  test-only models. The package **stays in place**; only `test_*.py`
  files relocate.
- Support modules `tests/models.py` and `tests/apps.py` stay in place
  for the same reason.
- The 6 legacy-tagged files are split at class granularity: legacy
  classes stay, gap-free classes move (F04 did exactly this for
  `metadataserver/tests/test_fields.py`).

## Out of Scope

- Closing the 9-class legacy carve-out (idea 002 — separate work).
- Modernizing relocated tests to pytest fixtures (F09).
- Retiring `nose` and the legacy stack (F08) — this feature only makes
  `maasserver`'s *migratable* files pytest-runnable; nose continues to
  run the 9-class carve-out.

## Open Questions

- The 4 triage files' root causes are identified but not yet fixed;
  each needs a one-line diagnosis-to-fix decision at design time (fix,
  port-simply, or fold into the carve-out). These are the only files
  whose migration is not purely mechanical.
- Whether the two support modules (`tests/models.py`, `tests/apps.py`)
  need any settings/app-label change when their sibling `test_*.py`
  files move — F04 suggests not, but `maasserver` has more importers
  (6) than `metadataserver` did.
