# Design: Dedicated pytest legs to close the remaining nose carve-outs

> Requirements: @requirements.md
> Status: Approved

## 1. Summary

Run the two remaining nose carve-outs under pytest in dedicated
invocations, each with the process configuration its subset needs, then
remove the corresponding nose legs. This is the spike-proven mechanism
from idea 005 with zero test-content changes. It does not converge the
legs into the main pytest process (that is spec 011's rewrite goal);
it retires nose first.

Two legs, two configs:

- **Rack leg** (idea 004, 39 `MAASTwistedRunTest` files): scenarios-on,
  crochet-off, `run_tests_with` honored, `MAAS_SECRET` persistence
  restored.
- **Region-legacy leg** (idea 002, 10 legacy classes across 7 files):
  `MAAS_PREVENT_MIGRATIONS=1`, a Django-native-`migrate` DB (no
  `dbupgrade` seed), Django's own `TransactionTestCase`.

## 2. Requirements Mapping

| Requirement | Design Coverage |
|-------------|-----------------|
| Run 39 `MAASTwistedRunTest` files under pytest | §3 Rack leg, §4 |
| Run 10 legacy classes under pytest | §3 Region-legacy leg, §4 |
| Zero test-content changes | §3 (mechanism is plugin/config only) |
| Enable F08 nose removal | §12 handoff |
| xdist-safe DB build | §9 (session-locked DB) |

## 3. Technical Approach

### The dedicated-leg mechanism

A **dedicated leg** is a pytest invocation whose plugins/config differ
from the main suite's, scoped to a named subset. The mechanism is an
env/config gate in the existing F03/F05 plugins, not new test code.

### Rack leg (idea 004)

The main suite's `_crochet_reactor` session fixture starts crochet's
always-on reactor; these 39 files need the process free for their
per-test reactor. Two gates, both proven in the spike:

1. **crochet-off gate.** `_crochet_reactor` reads an env/config flag
   (e.g. `MAAS_PYTEST_NO_CROCHET=1`) and calls
   `setup_crochet(no_setup=True)` instead of `setup_crochet()`.
   `no_setup=True` registers crochet's `EventualResult` interop without
   starting the reactor (verified: all 39 work this way — 37 use only
   `inlineCallbacks`; `test_plugin.py` mocks `no_setup`;
   `test_twisted.py` only asserts `EventualResult` type).
2. **`MAAS_SECRET` persistence gate.** `maastesting/pytest/environment.py`'s
   `clean_globals` fixture calls `MAAS_SECRET.set(None)` per test,
   clearing the in-memory secret that under nose persists across tests
   in a process (set by an earlier test's side effect). Two
   `test_clusterservice.py` certificate tests depend on that persistence.
   For this leg only, the clear is a no-op; explicit `.set(value)` calls
   still take effect.

   `run_tests_with` needs **no bridge**: testtools' `run()` instantiates
   `self.__RunTest` from the class's `run_tests_with` property/factory,
   so `MAASTwistedRunTest.make_factory` executes automatically under
   pytest's unittest runner (verified directly).

### Region-legacy leg (idea 002)

Three mechanisms, one per documented gap:

1. **Gap 3 (settings):** `MAAS_PREVENT_MIGRATIONS=1` in the environment
   before `django.setup()`, putting `maasserver.tests`/
   `metadataserver.tests` in `INSTALLED_APPS` and enabling syncdb-style
   table creation. Process-level, so the leg is a separate invocation.
2. **Gap 2 (seed-data):** a Django-native `migrate`-built test DB, NOT
   the `dbupgrade`-built pristine template the main suite uses. The
   template seeds `PackageRepository` rows these tests recreate (via
   `factory.make_default_PackageRepositories`), causing
   `validate_unique` failures. The leg builds its own DB via
   `call_command("migrate", run_syncdb=True)`.
3. **Gap 1 (resource management):** Django's own `TransactionTestCase`
   handles transactions; no pytest DB fixture is injected (the
   `ensuremaasdjangodb` template fixture must NOT apply here).

## 4. Component / Module Structure

```text
Dedicated legs (new entry points, parallel to F03's maas-region):
  rack-legacy leg:   pytest <39 MAASTwistedRunTest files>
                     with MAAS_PYTEST_NO_CROCHET=1 + secret-persistence gate
  region-legacy leg: pytest <7 legacy files>
                     with MAAS_PREVENT_MIGRATIONS=1 + Django-migrate DB

Mechanism changes (plugin/config only, no test edits):
  maastesting/pytest/legacy.py     - env/config gate in _crochet_reactor
  maastesting/pytest/environment.py - secret-persistence gate for the leg
  (new) a legacy-DB session fixture - per-worker Django-migrate DB,
        built once under cluster.lock (see §9)
```

## 9. Edge Cases

- **xdist DB race (region-legacy leg):** two distinct contention modes,
  both resolved by a **per-worker Django-migrate DB** built once under
  the cluster lock (`maas_legacy_spike_{worker_id}`):
  1. *Build race* — `pytest_configure` (or an unguarded fixture) makes
     each worker drop+create+migrate the same name (`KeyError:
     <WorkerController gw0>`). The `cluster.lock.exclusive` guard
     serializes the build.
  2. *Flush contention* — even with the build locked, sharing one DB
     across workers makes `TransactionTestCase`'s per-test flush
     truncate another worker's live tables (26 failed + 12 errors at
     `-n 2`). A per-worker DB (`{name}_{worker_id}`), matching the main
     suite's own pattern, eliminates it.
  **Proven 2026-11-19:** 69/69 under both `-n 2` and `-n 4` with a
  session-scoped autouse fixture building `maas_legacy_spike_{worker_id}`
  inside `cluster.lock.exclusive` and pointing Django's `default` at it.
- **Rack-leg scenario ordering:** the F03 shim already sorts scenario
  expansion by name (F06 fix), so these files are xdist-deterministic.
- **Isolation between legs:** the two legs must run in separate pytest
  invocations (different `INSTALLED_APPS`/`MIGRATION_MODULES` and
  reactor configs) — they cannot share a process with each other or with
  the main suite.

## 12. Migration / Rollout (F08 handoff)

Once both legs pass under pytest, F08 removes:

- `bin/test.rack` (replaced by the rack-legacy leg),
- `bin/test.region.legacy` (replaced by the region-legacy leg),
- `maastesting/noseplug.py`, `djangoloader.py`, `.noseids`,
  `parallel.py`, and the `nose`/`testtools`/`testscenarios`/
  `testresources` deps from `pyproject.toml`.

This feature produces the pytest legs; F08 executes the removal. The
legs are wired into `utilities/run-py-tests-ci` as pytest invocations
replacing the two nose legs (CI-leg count unchanged: 2 nose legs → 2
pytest legs).

## 13. Technical Decisions

- **TD-001: Dedicated legs over rewriting.** Closing both carve-outs via
  process config (spike-proven, zero test edits) is far lower risk than
  rewriting 39 files to crochet + 10 classes off `DjangoTestCase`
  (idea 004 Option 2, idea 002 Option 3). The rewrite is spec 011's
  separate goal; this feature retires nose first without it.
- **TD-002: Env/config gates over per-file shims.** The mechanism is a
  gate in the existing plugins, not per-file markers or a new plugin
  per leg. Keeps the toggle in one place per concern.
- **TD-003: Django-migrate DB over the pristine template (legacy leg).**
  The template's `dbupgrade` seed is fundamentally incompatible with
  these tests' fixtures (gap 2); a separate Django-migrated DB is the
  only config that mirrors `manage.py test`.

## 15. Verification Strategy

- **Rack leg:** `pytest <39 files>` with the gates — all pass (spike:
  1850/1850), serially and under `-n 2 --dist=load`. `bin/test.rack`
  narrows to 0 and is removable.
- **Region-legacy leg:** `pytest <7 files>` with
  `MAAS_PREVENT_MIGRATIONS=1` + Django-migrate DB — all pass (spike:
  69/69), matching the nose legacy leg's count. `bin/test.region.legacy`
  is removable.
- **No double-run:** after the legs exist, nose collects none of these
  files (they're already under `src/maasserver`/`src/provisioningserver`
  but excluded from the remaining nose legs by their removal).
- **CI:** `utilities/run-py-tests-ci` invokes only pytest.
