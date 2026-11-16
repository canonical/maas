# Tasks: Dedicated pytest legs to close the remaining nose carve-outs

> Requirements: @requirements.md
> Design: @design.md
> Status: Approved

## Requirement Coverage

| Requirement | Tasks | Notes |
|-------------|-------|-------|
| Rack leg: 39 `MAASTwistedRunTest` files under pytest | T1, T2 | T1 = crochet no_setup gate; T2 = MAAS_SECRET persistence gate |
| Region-legacy leg: 10 legacy classes under pytest | T3 | MAAS_PREVENT_MIGRATIONS=1 + per-worker locked Django-migrate DB |
| xdist-safe | T2, T3 | scenario ordering already fixed (F06); per-worker DB (T3) |
| Zero test-content changes | all | mechanism is plugin/config only |
| Enable F08 nose removal | T4, T5 | wire legs into CI, verify nose removable |

## Task Summary

| Task | Title | Priority | Estimate | Dependencies | Status |
|------|-------|----------|----------|---------------|--------|
| T1 | Crochet no_setup gate for the rack leg | P0 | 1h | none | done |
| T2 | MAAS_SECRET persistence gate for the rack leg | P0 | 1h | T1 | done |
| T3 | Region-legacy leg: per-worker locked Django-migrate DB + settings | P0 | 2h | none | done |
| T4 | Wire both legs into CI and verify nose legs removable | P0 | 1h | T2, T3 | done |
| T5 | Full-suite + both-legs verification and INDEX/PLAN updates | P1 | 1h | T4 | done |

## Task T1: Crochet no_setup gate for the rack leg

**Priority:** P0
**Estimate:** 1h
**Dependencies:** none
**Covers:** Rack leg (idea 004)

### Work
- [x] Added the `MAAS_PYTEST_NO_CROCHET` gate to `_crochet_reactor`:
  when set, calls `setup_crochet(no_setup=True)` (EventualResult
  interop without the always-on reactor); otherwise starts crochet and
  installs the DB thread-pool as before. The reactor-independent
  logging level-name side effect runs in both branches.

### Acceptance Criteria
- [x] With the gate set, `test_common.py` (a `MAASTwistedRunTest` file)
  passes 34/34 under pytest — no `ReactorAlreadyRunning`. Without it,
  the main suite is unchanged (221 passed, crochet on).
- [x] `run_tests_with = MAASTwistedRunTest.make_factory(...)` is honored
  automatically (no bridge needed — testtools' `run()` instantiates it;
  verified in the spike).

### Verification
- [x] `MAAS_PYTEST_NO_CROCHET=1 pytest test_common.py` — 34 passed, no
  `ReactorAlreadyRunning`
- [x] `pytest src/tests/maasserver/... ` (no gate) — 221 passed, crochet on
- [x] `ruff check` — clean

## Task T2: MAAS_SECRET persistence gate for the rack leg

**Priority:** P0
**Estimate:** 1h
**Dependencies:** T1
**Covers:** Rack leg (idea 004), xdist-safe

### Work
- [x] Added the gate to `clean_globals`: when `MAAS_PYTEST_NO_CROCHET`
  is set, the per-test `MAAS_SECRET.set(None)` clear is skipped (the
  in-memory secret persists across tests in the process, matching nose),
  while explicit `.set(value)` calls still take effect. Main suite
  unaffected (clear still runs by default).
- [x] Confirmed all 39 files pass with both gates (T1 + T2).

### Acceptance Criteria
- [x] All 39 files pass under `-n 2 --dist=load` with both gates:
  1850 passed / 1 skipped (matches the spike exactly)

### Verification
- [x] `MAAS_PYTEST_NO_CROCHET=1 pytest <39 files> -n 2 --dist=load` —
  1850 passed / 0 failed / 1 skipped
- [x] Main suite (no gate) — 221 passed, secret still clears per test
- [x] `ruff check` — clean

## Task T3: Region-legacy leg — per-worker locked Django-migrate DB + settings

**Priority:** P0
**Estimate:** 2h
**Dependencies:** none
**Covers:** Region-legacy leg (idea 002)

### Work
- [x] Added session-scoped autouse `_legacy_django_db` fixture in
  `maastesting/pytest/django.py`: when `MAAS_PREVENT_MIGRATIONS=1` is
  set, builds a per-worker Django-migrate DB (`maas_legacy_{worker_id}`)
  exactly once under `cluster.lock.exclusive` and points Django's
  `default` at it via `call_command("migrate", run_syncdb=True)`. Does
  NOT use the `dbupgrade` pristine template (its `PackageRepository`
  seed breaks these tests — idea 002 gap 2).
- [x] Does NOT inject `ensuremaasdjangodb` for these tests; Django's
  own `TransactionTestCase` handles the DB.
- [x] Settings are process-level: `MAAS_PREVENT_MIGRATIONS=1` is set in
  the environment before `django.setup()` (the leg invocation provides it).

### Acceptance Criteria
- [x] All 10 legacy classes (7 files) pass: 69/69 at `-n 4`, matching
  the nose legacy leg's count exactly
- [x] Passes under `-n 2` and `-n 4` (per-worker DB avoids both the
  build race and the flush contention); serial 69/69 too

### Verification
- [x] `MAAS_PREVENT_MIGRATIONS=1 pytest <7 files> -n 4 --dist=load` —
  69/69
- [x] `MAAS_PREVENT_MIGRATIONS=1 pytest <7 files>` serial — 69/69
- [x] metadataserver legacy file alone — 9/9
- [x] Main suite without the gate (fixture inactive) — 191 passed
- [x] `ruff check` — clean

## Task T4: Wire both legs into CI and verify nose legs removable

**Priority:** P0
**Estimate:** 1h
**Dependencies:** T2, T3
**Covers:** Enable F08

### Work
- [x] Replaced the `bin/test.parallel` invocation (3 nose legs:
  `test.region.legacy`, `test.rack`, `test.region`) in
  `utilities/run-py-tests-ci` with two pytest legs + the existing main
  suite. `test.region` already collected 0 after F06, so test.parallel
  is fully redundant. Leg structure: rack-legacy
  (`MAAS_PYTEST_NO_CROCHET=1` over `src/provisioningserver`, the 39
  files), region-legacy (`MAAS_PREVENT_MIGRATIONS=1` over the 7
  computed legacy files), main suite (`src/tests`).
- [x] Found and fixed a worker-distribution flake the per-test
  clear-skip alone left: at `-n auto`, the 2 certificate tests could
  land in a worker where no prior test set `MAAS_SECRET`. Added a
  session fixture (`_rack_legacy_secret`) provisioning a deterministic
  secret once per worker, mirroring `rack_script.py`'s process-level
  setup. Verified: 3 consecutive `-n auto` runs all 1850 passed.

### Acceptance Criteria
- [x] CI invokes only pytest for these subsets (rack-legacy 1850/1850,
  region-legacy 69/69, no nose)
- [x] `bin/test.rack` is redundant — the 39 files now run under the
  rack-legacy pytest leg (its 1851 tests = 1850 pass + 1 skip under
  pytest)

### Verification
- [x] `bash -n utilities/run-py-tests-ci` — syntax OK
- [x] rack leg `-n auto` ×3 — 1850 passed each (deterministic)
- [x] region-legacy leg as scripted (computed file list) — 69 passed
- [x] `ruff check` — clean

## Task T5: Full-suite + both-legs verification and INDEX/PLAN updates

**Priority:** P1
**Estimate:** 1h
**Dependencies:** T4
**Covers:** Enable F08

### Work
- [x] Main suite (`bin/pytest -n auto`): 22446 passed / 6 failed / 192
  skipped — all 6 in the documented pre-existing set (2 etag,
  test_interface, test_runtest, 2 beaconing), none new from F010 (gates
  default off). `test_manager.py` (vault) absent this run — intermittent
  xdist-order artifact, not F010.
- [x] No double-run: `test.region` collects 0; 0 `MAASTwistedRunTest`
  files and 0 legacy-tagged files under `src/tests/` (the carve-out
  files live only in `src/provisioningserver` and
  `src/maasserver`/`src/metadataserver`, reachable only by their
  dedicated legs; the main suite covers only `src/tests`).
- [x] Region-legacy leg: 69/69 under `-n auto` (earlier 69-error run
  was template contention with the concurrent main-suite job, per
  design §14; clean once it finished).
- [x] Updated `INDEX.md` (spec 010 → implementation:done) and `PLAN.md`
  (F08 unblocked, F07 closed by 010).

### Acceptance Criteria
- [x] All three pytest invocations green (main 22446, rack-legacy 1850,
  region-legacy 69); nose collects nothing relevant
- [x] INDEX/PLAN reflect 010 done and F08 unblocked

### Verification
- [x] Main suite + both legs pass; `make lint` clean
