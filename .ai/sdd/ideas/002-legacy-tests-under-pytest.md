# Idea: Run `legacy`-tagged tests under pytest, not just nose

> Status: captured
> Created: 2026-11-16
> Source: F03 (`003-migrate-maasserver-tests`) T11 investigation, TD-004

## Raw Idea

`DjangoTestCase`/`DjangoTransactionTestCase`-based tests (via
`MAASLegacyServerTestCase`/`MAASLegacyTransactionServerTestCase`) are
tagged `legacy = True` and currently run **only** under nose, via
`bin/test.region.legacy` (`run_region_legacy()` in
`maastesting/scripts.py`, which calls `execute_from_command_line()`
with Django's own `manage.py test` command). This is invoked by
`bin/test.parallel`/CI (`utilities/run-py-tests-ci`'s first leg), so
these ~69+ tests (4+ files: `test_fields.py`, `test_cleansave.py`,
`test_signals.py`, `test_timestampedmodel.py` in `src/maasserver`,
plus any in `src/metadataserver`) are actively tested and passing
today — not dead code.

F03 excludes them from pytest collection (matching nose's own
`-a !legacy` exclusion for `bin/test.region`'s non-legacy run) rather
than migrating them, after an investigation (F03 T11, TD-004) found
three independent, compounding incompatibilities make a straightforward
`resources`-tuple fix infeasible. This idea captures what a real
migration would require.

## Problem Space (confirmed via direct investigation, F03 T11)

1. **No resource management.** `DjangoTestCase`/`DjangoTransactionTestCase`
   declare no `resources` tuple (inherit `MAASTestCase.resources = ()`),
   so neither nose's `--with-resources` plugin nor F03's
   `maastesting/pytest/region.py` ever manages their database — they
   rely solely on Django's own `TestCase._fixture_setup`/
   `_fixture_teardown` transaction wrapping over whatever connection is
   ambiently configured.
2. **Pristine-template seed-data mismatch.** The shared pristine
   template pytest's resource-reuse mechanism uses
   (`DjangoPristineDatabaseManager._make()`) is built via `dbupgrade`
   (Django + Alembic migrations), which seeds default `PackageRepository`
   rows. `manage.py test` never runs `dbupgrade` — only Django's native
   migrations — so this seed data has never existed in any database
   these tests have run against. `PackageRepositoryFixture`-using tests
   fail on "already exists" once pointed at a `dbupgrade`-built database.
3. **Process-global settings-mode conflict (the fatal one).**
   `run_region_legacy()` sets `MAAS_PREVENT_MIGRATIONS=1`, which (via
   `maasserver/djangosettings/development.py`) both adds
   `maasserver.tests`/`metadataserver.tests` to `INSTALLED_APPS` (the
   only way test-only models like `FieldChangeTestModel` get a real
   table) **and** replaces all app migrations with `maastesting.empty`,
   falling back to Django's `syncdb`-style table creation. F03's pytest
   suite runs the exact opposite configuration. Django's settings/app
   registry are configured once per process at `django.setup()` time —
   no per-test or per-resource fix can reconcile two mutually exclusive
   `INSTALLED_APPS`/`MIGRATION_MODULES` configurations within one
   pytest worker process.

## Possible Directions (not yet evaluated/chosen)

- **Separate pytest invocation/process** with `MAAS_PREVENT_MIGRATIONS=1`
  set before `django.setup()` runs (a third CI leg, mirroring
  `run_region_legacy()`'s own process isolation today) — tests still
  run under pytest's runner/reporting, just in a dedicated process with
  the settings mode they actually need.
- **Make test-only models migration-backed** (`maasserver.tests`,
  `metadataserver.tests` gain real Alembic/Django migrations so they
  exist under `dbupgrade` too), dropping the `MAAS_PREVENT_MIGRATIONS`
  dependency for these models specifically — removes gap 3 entirely,
  but is a non-trivial model/migration change touching test
  infrastructure several real features' tests depend on.
- **Rewrite the 4-7 affected test classes** to stop using
  `DjangoTestCase`/`DjangoTransactionTestCase` entirely (port to
  `MAASServerTestCase`/`MAASTransactionServerTestCase`-style resource
  management) — the most invasive option, but sidesteps all three gaps
  since these tests would no longer depend on Django's native
  `manage.py test` assumptions at all.

## Open Questions

- Is retiring `legacy`-tagged tests' special infrastructure (merging
  into the main pytest-managed resource/migration world) in scope for
  a later maasserver/metadataserver-wide nose retirement feature
  (F04-F07 per F03's `decisions.md`/`design.md` references), or does
  it need its own dedicated feature?
- How many files/classes are affected in total across `maasserver` and
  `metadataserver` combined (F03 only confirmed the `maasserver` side)?
