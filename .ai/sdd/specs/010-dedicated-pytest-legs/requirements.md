# Feature: Dedicated pytest legs to close the remaining nose carve-outs

> Status: Approved
> Source: `.ai/sdd/PLAN.md` (F08), `.ai/sdd/ideas/002-legacy-tests-under-pytest.md`,
> `.ai/sdd/ideas/004-provisioningserver-twisted-reactor-carveout.md`,
> `.ai/sdd/ideas/005-nose-retirement-carveout-closures.md`

## Overview

F04-F06 relocated all migratable `metadataserver`, `provisioningserver`,
and `maasserver` tests to pytest. Two carve-outs still require nose,
blocking F08 (full nose retirement):

- **idea 002:** 10 `legacy`-tagged test classes across 7 files, run via
  `bin/test.region.legacy` (`MAAS_PREVENT_MIGRATIONS` gap-3).
- **idea 004:** 39 `MAASTwistedRunTest` files, run via `bin/test.rack`
  (per-test Twisted reactor, incompatible with the always-on crochet
  reactor the main pytest suite uses).

This feature runs both carve-outs under **pytest in dedicated
invocations** with the process configuration each needs, eliminating
every remaining nose leg. It is the spike-proven mechanism from idea
005, with zero test-content changes.

A follow-on feature (spec 011, not yet planned) will eventually converge
to a single pytest process by rewriting the 39 reactor files onto the
crochet model and the 10 legacy classes off `DjangoTestCase`. This
feature deliberately does **not** do that rewrite — it retires nose
first, at low risk.

## Business Context

- **Problem:** nose is still a live test-runner dependency for exactly
  two test subsets. F08 cannot remove it (and its `noseplug`,
  `djangoloader`, `.noseids`, parallel-runner machinery, and the
  `nose`/`testtools`/`testscenarios`/`testresources` deps) until every
  test runs under pytest. Those two subsets are the last blockers.
- **Users:** MAAS engineers and CI maintainers who want a single test
  runner; downstream packagers who want the unmaintained `nose`
  dependency gone.
- **Value:** Retires nose completely, at low risk, without touching
  test logic. The rewrite-to-one-process goal (spec 011) is a separate,
  higher-risk effort that this feature does not block or require.
- **Success signal:** `bin/test.region.legacy` and `bin/test.rack` are
  removed; all tests run under pytest (in the main invocation plus
  dedicated legs); `nose` is droppable from `pyproject.toml`; CI's test
  leg(s) invoke only pytest.

## The two carve-outs and their required process configs

### Carve-out A — idea 004: 39 `MAASTwistedRunTest` files

- **Why they can't run in the main pytest invocation:** they declare
  `run_tests_with = MAASTwistedRunTest.make_factory(...)`, which spins
  up a fresh Twisted reactor per test method. The main suite's F03 shim
  starts crochet's always-on reactor once per process, and Twisted
  allows only one reactor per process — running both fails with
  `ReactorAlreadyRunning` (confirmed live).
- **Required process config:** scenarios-on (the existing
  `_expand_scenarios` shim) + crochet-off
  (`setup_crochet(no_setup=True)`) + `run_tests_with` honored (automatic
  — testtools' `run()` instantiates it; no bridge needed).
- **Spike-proven 2026-11-19:** all 39 files pass under pytest with this
  config, serially and under `-n 2 --dist=load`: **1850 passed / 0
  failed / 1 skipped**. Two env-gates were needed, not one:
  - `setup_crochet(no_setup=True)` — registers `EventualResult` interop
    without starting the always-on reactor.
  - Neutralize `maastesting/pytest/environment.py`'s `clean_globals`
    fixture's `MAAS_SECRET.set(None)` — under nose the in-memory
    `MAAS_SECRET` persists across tests in a process (set by an earlier
    test's side effect), but `clean_globals` actively clears it per
    test, which broke 2 certificate tests in `test_clusterservice.py`
    that rely on that persistence. Making the clear a no-op for this
    leg (while preserving explicit `.set(value)` calls) restores the
    nose-equivalent behavior. All 39 work with `no_setup` (37 use only
    `inlineCallbacks`; `test_plugin.py` mocks `no_setup`,
    `test_twisted.py` only asserts `EventualResult` type).

### Carve-out B — idea 002: 10 legacy classes

- **Why they can't run in the main pytest invocation:** they need
  `MAAS_PREVENT_MIGRATIONS=1` set *before* `django.setup()`, which puts
  `maasserver.tests`/`metadataserver.tests` in `INSTALLED_APPS` and
  replaces migrations with syncdb-style table creation. The main suite
  runs the exact opposite configuration; Django's app registry is fixed
  once per process.
- **Required process config:** `MAAS_PREVENT_MIGRATIONS=1` in the
  environment before settings import (gap 3), a Django-native
  `migrate`-built test database (no `dbupgrade` seed — gap 2), and
  Django's own `TransactionTestCase` handling (gap 1). The main pytest
  suite's `dbupgrade`-built pristine template seeds `PackageRepository`
  rows these tests recreate, so it cannot be reused — a separate,
  Django-migrated DB is required.
- **Spike-proven 2026-11-19:** all 10 classes across the 7 files pass
  under pytest: **69 passed / 0 failed** — matching the nose legacy
  leg's count exactly. Serial only; under xdist both workers race on
  the shared spike DB (`pytest_configure` drop+create+migrate), so the
  real implementation must build the DB once under a lock (a
  session-scoped fixture), not per-worker.
- **The 10 classes (7 files):** `TestMAASModelForm`, `TestXMLField`,
  `TestLargeObjectField`, `TestCIDRField`, `TestIPv4CIDRField`,
  `TestTimestampedModel`, `TestConnectToFieldChange`,
  `TestCleanSave`, `TestBulkManager`, `TestBinaryField`
  (metadataserver).

## Approach

Introduce a **dedicated-leg mechanism**: a pytest invocation configured
per carve-out (process env / plugin toggle) that runs only that subset.
Two instantiations:

1. **Rack leg** (carve-out A): pytest over the 39
   `MAASTwistedRunTest` files with crochet-off via an env/config gate
   in the `_crochet_reactor` fixture.
2. **Region-legacy leg** (carve-out B): pytest over the 7 legacy files
   with `MAAS_PREVENT_MIGRATIONS=1`.

Once both run under pytest, remove `bin/test.rack`,
`bin/test.region.legacy`, and the nose machinery per F08 (its own
follow-on).

## Out of Scope

- **Rewriting the carve-out tests to a single process** (spec 011).
  This feature adds pytest legs; it does not converge them.
- **Retiring nose itself** (F08: deleting `noseplug.py`, deps, CI
  changes). This feature is the *prerequisite* that makes F08 possible;
  F08 executes the actual removal.
- **Modernizing relocated tests** (F09).

## Open Questions

- The CI-leg wiring: are the two new pytest legs added to
  `utilities/run-py-tests-ci` (replacing the two nose legs), or run as
  separate CI jobs? (Implementation detail, decided at design time.)
- The env/config gate for crochet-off: env var, `pytest.ini` option, or
  a plugin parameter — decided at design time.
