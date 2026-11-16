# Tasks: Cut over `metadataserver` to pytest (pilot)

> Requirements: @requirements.md
> Design: @design.md
> Status: Approved

## Requirement Coverage

| Requirement | Tasks | Notes |
|-------------|-------|-------|
| FR-001 (relocate gap-free files) | T1 | 17 pure `git mv` + `test_fields.py` split (TD-005) |
| FR-002 (triage gap-touching files) | T2 | 5 gap-touching files, rely on F03's shim unmodified |
| FR-003 (drop from nose) | T4 | Structural consequence of T1-T3, verified not coded |
| FR-004 (verify coverage parity) | T5 | `utilities/coverage-baseline check metadataserver` |
| FR-005 (reconcile pre-existing overlap files) | T1 (merge, split), T3 | `test_hooks.py` merge; `test_fields.py` split (TD-005); `test_maas_wipe.py`/`release_scripts` confirmed distinct, no action needed |
| NFR-001 (reliability) | T1-T5 (each task's own verification step) | |
| NFR-002 (scope discipline) | T1-T3 (no modernization performed) | |

## Implementation Readiness Check

| Check | Status | Notes |
|-------|--------|-------|
| Must Have requirements have tasks | Pass | FR-001-FR-005 all covered above |
| Requirements are covered by design | Pass | Design §3.1's disposition table names every one of the 23 files; §9/TD-002/TD-003 resolve both relocation-specific hazards with confirmed (not speculative) fixes |
| Critical Questions are answered | Pass | Requirements has zero open questions (Q-001 resolved as D-003) |
| Tasks have dependencies, acceptance criteria, files, and verification | Pass | See T1-T5 below |
| Verification commands are known or marked manual/N/A | Pass | `pytest --collect-only`, `utilities/coverage-baseline check`, `bin/test.region`/`bin/test.rack`, `make lint` — all existing, known commands |

## Implementation Slices

### MVP Slice

- **Goal:** All 23 `metadataserver` test files running under pytest
  alone, `nose` no longer collecting the package, coverage parity
  proven.
- **User Stories:** US-001, US-002, US-003
- **Tasks:** T1, T2, T3, T4, T5
- **Independent validation:** `utilities/coverage-baseline check
  metadataserver` reports `verdict: PASS`; `find src/metadataserver
  -name 'test_*.py'` returns exactly `tests/test_fields.py` (TD-005's
  intentional exception); `bin/test.region`'s test count drops by 989
  (measured: 13013 → 12024 - the static 927/918 `def test_`-count
  estimate undercounts `testscenarios` multiplication, see design §3.3).

## Task T1: Relocate the 17 remaining gap-free files + merge `test_hooks.py` + split `test_fields.py` (TD-005)

**Priority:** P0
**Estimate:** 1.5h
**Dependencies:** none
**Covers:** FR-001, FR-005 (merge half)

### Work
- [ ] `git mv` each of the 17 remaining gap-free files (design §3.1
      rows 7-19, excluding `test_hooks.py` and `test_fields.py`) to its
      mirrored path under
      `src/tests/metadataserver/`, creating any missing `__init__.py`
      files pytest's package-based collection requires along the way
      (check against existing `src/tests/metadataserver/` subtrees for
      the convention — `__init__.py` present at every directory level)
- [ ] For `metadataserver/builtin_scripts/tests/test_hooks.py` (row 3,
      155 test defs): merge its classes into the pre-existing
      `src/tests/metadataserver/builtin_scripts/test_hooks.py` (1 test,
      `TestParseBootifCmdline`) per design TD-002 — append the legacy
      file's classes into the existing file (or vice versa), do not
      overwrite either side
- [ ] For `metadataserver/tests/test_fields.py` (row 6, mixed): split
      per design TD-005 — relocate `TestBin` (gap-free) to
      `src/tests/metadataserver/test_fields.py`; leave `TestBinaryField`
      (legacy-tagged `MAASLegacyTransactionServerTestCase`) at the
      original path, untouched, still covered only by `nose`'s
      `run_region_legacy()`
- [ ] Delete each relocated file's now-empty source location (the
      `git mv` itself handles this; confirm no leftover empty `tests/`
      directories need their own cleanup under `src/metadataserver/`),
      except `tests/test_fields.py` which intentionally stays (TD-005)

### Acceptance Criteria
- [ ] Each of the 18 files collects and passes under pytest at its new
      path with 0 behavior change (same test count, same pass/fail
      outcome as its `nose` run today)
- [ ] The merged `test_hooks.py` collects exactly 1 (pre-existing) +
      155 (legacy) = 156 test items, all passing
- [ ] `test_fields.py`'s `TestBin` (4 tests) passes at its new path;
      `TestBinaryField` (9 tests) is untouched at the old path (TD-005)
- [ ] No file remains at its old `src/metadataserver/**/tests/` path,
      except `tests/test_fields.py` (TD-005's intentional exception)

### Files
- 17 files: `git mv` from `src/metadataserver/**/tests/test_*.py` to
  `src/tests/metadataserver/**/test_*.py` (see design §3.1 rows
  7-19 for the full list)
- `src/tests/metadataserver/test_fields.py` — new (only `TestBin`,
  split from the original per TD-005)
- `src/metadataserver/tests/test_fields.py` — modified, not removed
  (only `TestBinaryField` remains, per TD-005)
- `src/tests/metadataserver/builtin_scripts/test_hooks.py` — modify
  (merge target)
- `src/metadataserver/builtin_scripts/tests/test_hooks.py` — removed
  (merged, not relocated as a separate file)

### Verification
- [ ] `pytest --collect-only src/tests/metadataserver` — 0 collection
      errors for all 17 relocated files + the merged `test_hooks.py` +
      the new split-off `test_fields.py` (`TestBin` only)
- [ ] `pytest src/tests/metadataserver/<each relocated path>` — pass
      count matches each file's current `nose`-reported count
- [ ] `.ve/bin/pytest src/metadataserver/tests/test_fields.py` —
      `TestBinaryField`'s 9 tests still collect and pass unmodified at
      the original path (TD-005)
- [ ] `make lint` passes

## Task T2: Relocate the 5 gap-touching files

**Priority:** P0
**Estimate:** 1h
**Dependencies:** none (independent of T1 — different files, no
shared state); `test_api_twisted.py`'s `deferToDatabase` tests require
TD-004's thread-pool fix to `_crochet_reactor` — see Work below
**Covers:** FR-002

### Work
- [ ] `git mv` `metadataserver/tests/test_api.py` (scenarios,
      `APITestCase`),
      `metadataserver/tests/test_api_twisted.py` (reactor),
      `metadataserver/builtin_scripts/testing_scripts/tests/test_fio.py`
      (scenarios),
      `metadataserver/user_data/tests/test_generate_user_data.py`
      (scenarios) to their mirrored `src/tests/metadataserver/` paths,
      unmodified (design §3.1 rows 1, 2, 4, 5)
- [ ] `metadataserver/builtin_scripts/tests/test_hooks.py` (scenarios,
      row 3) is handled by T1's merge, not here — do not duplicate
- [ ] Extend `maastesting/pytest/legacy.py`'s session-scoped
      `_crochet_reactor` fixture (TD-004) to also call
      `orm.disable_all_database_connections()` and
      `threads.install_default_pool(maxthreads=1)` /
      `reactor.callFromThread(threads.install_database_unpool, ...)`,
      mirroring `run_region_legacy()`'s own setup in
      `maastesting/scripts.py` — `test_api_twisted.py`'s
      `deferToDatabase`-based tests fail without it

### Acceptance Criteria
- [ ] Each of the 4 files (test_api, test_api_twisted, test_fio,
      test_generate_user_data) collects and passes under pytest at its
      new path, relying on F03's `maastesting/pytest/legacy.py`
      scenario/reactor shim and `maasserver/testing/api.py`'s
      `APITestCase` fix, plus TD-004's thread-pool addition for
      `test_api_twisted.py`
- [ ] Pass counts match each file's current `nose`-reported count
      exactly (no scenario or reactor-dependent test silently dropped)
      — `test_api_twisted.py` in particular: 50/50 pass (TD-004 fixes
      9 pre-fix failures)

### Files
- 4 files: `git mv` from `src/metadataserver/**` to
  `src/tests/metadataserver/**` (see design §3.1 rows 1, 2, 4, 5)
- `src/maastesting/pytest/legacy.py` — modified (TD-004 thread-pool
  install, additive to existing `_crochet_reactor` fixture)

### Verification
- [ ] `pytest --collect-only src/tests/metadataserver/tests/test_api.py
      src/tests/metadataserver/tests/test_api_twisted.py
      src/tests/metadataserver/builtin_scripts/testing_scripts/test_fio.py
      src/tests/metadataserver/user_data/test_generate_user_data.py` —
      0 collection errors
- [ ] `pytest <same 4 files> -v` — pass count matches each file's
      current `nose`-reported count
- [ ] `make lint` passes

## Task T3: Relocate the 4 path-import-hazard files

**Priority:** P0
**Estimate:** 1.5h
**Dependencies:** none (independent file set)
**Covers:** FR-005 (confirms no collision with pre-existing
`release_scripts/test_maas_wipe.py`)

### Work
- [ ] `git mv` `test_maas_wipe.py` and `test_maas_wipe_defs.py` (design
      §3.1 rows 20-21) to their mirrored paths under
      `src/tests/metadataserver/user_data/templates/snippets/`;
      rewrite their `from snippets import ...`/
      `from snippets.tests.test_maas_wipe_defs import ...` imports to
      the dotted path,
      `from metadataserver.user_data.templates.snippets import ...`/
      `from metadataserver.user_data.templates.snippets.tests.test_maas_wipe_defs
      import ...` (design TD-003) — note: confirm whether
      `test_maas_wipe_defs.py`'s own relocated path still has a
      `tests` segment or flattens; adjust the dotted import accordingly
      at implementation time
- [ ] `git mv` `test_maas_run_remote_scripts.py` and
      `test_maas_run_scripts.py` (design §3.1 rows 22-23) to the same
      directory, unmodified (no import rewrite — their path-dependent
      import is in the *production* module, not the test file itself)
- [ ] Create
      `src/tests/metadataserver/user_data/templates/snippets/conftest.py`
      inserting the `templates/` directory onto `sys.path` at
      collection time (design TD-003/§16 FAQ), scoped to this one
      subdirectory only
- [ ] Confirm `release_scripts/test_maas_wipe.py` (pre-existing,
      unrelated per requirements D-002) is untouched and still passes
      — no action needed, verify only

### Acceptance Criteria
- [ ] `test_maas_wipe.py`/`test_maas_wipe_defs.py` collect and pass via
      the dotted-import fix alone (no `conftest.py` dependency)
- [ ] `test_maas_run_remote_scripts.py`/`test_maas_run_scripts.py`
      collect and pass only once the `conftest.py` is in place —
      confirm by temporarily removing it and observing the expected
      `ModuleNotFoundError: No module named 'snippets'` failure, then
      restoring it
- [ ] `release_scripts/test_maas_wipe.py` (pre-existing) still passes
      unmodified, confirming no `conftest.py` scope leakage

### Files
- `src/tests/metadataserver/user_data/templates/snippets/test_maas_wipe.py` — new (relocated + import fix)
- `src/tests/metadataserver/user_data/templates/snippets/test_maas_wipe_defs.py` — new (relocated + import fix)
- `src/tests/metadataserver/user_data/templates/snippets/test_maas_run_remote_scripts.py` — new (relocated, unmodified)
- `src/tests/metadataserver/user_data/templates/snippets/test_maas_run_scripts.py` — new (relocated, unmodified)
- `src/tests/metadataserver/user_data/templates/snippets/conftest.py` — new

### Verification
- [ ] `pytest --collect-only src/tests/metadataserver/user_data/templates/snippets/` — 0 collection errors, all 4 relocated files + the pre-existing `release_scripts/test_maas_wipe.py` collect
- [ ] `pytest src/tests/metadataserver/user_data/templates/snippets/ -v` — pass count matches the 4 relocated files' current `nose`-reported count, plus the pre-existing file's own count unchanged
- [ ] Manual: temporarily rename/remove `conftest.py`, confirm
      `test_maas_run_*` fail with `ModuleNotFoundError`, restore it,
      confirm they pass again — proves the `conftest.py` is load-bearing,
      not a no-op
- [ ] `make lint` passes

## Task T4: Drop `metadataserver` from `nose`, verify structurally

**Priority:** P0
**Estimate:** 1h
**Dependencies:** T1, T2, T3 (all gap-free/gap-touching/path-import
files must be relocated first; `tests/test_fields.py`'s
`TestBinaryField` intentionally stays per TD-005)
**Covers:** FR-003

### Work
- [x] Confirm `find src/metadataserver -name 'test_*.py'` returns
      exactly one file, `tests/test_fields.py` (TD-005's intentional
      exception — `TestBinaryField` stays `legacy`-tagged, under
      `run_region_legacy()`) (no code change to
      `src/maastesting/scripts.py` — design §3.3 confirms
      `--select-dir=src/metadataserver` becomes a structural no-op for
      the files that did relocate, left in place per design's rollout
      note, deferred to F08)
- [x] Run `bin/test.region` (or `.ve/bin/test.region`) and confirm its
      reported test count dropped — **measured 989 (13013 → 12024)**,
      not the static 918 estimate (`testscenarios` multiplication makes
      the `def test_`-count estimate unreliable as a total, see design
      §3.3)
- [x] Fix TD-006 (found via this run's own `ImportError` at
      collection): 3 `maasserver` test files
      (`maasserver/tests/test_storage_layouts.py`,
      `maasserver/api/tests/test_machine.py`,
      `maasserver/models/tests/test_node.py`) import test-support
      helpers directly from the now-relocated/merged
      `metadataserver.builtin_scripts.tests.test_hooks` — repointed
      each to `tests.metadataserver.builtin_scripts.test_hooks`, added
      `"tests"` to `pyproject.toml`'s `lint.isort.known-first-party`

### Acceptance Criteria
- [x] Zero `metadataserver` test files remain outside `src/tests/`,
      except `tests/test_fields.py` (TD-005's intentional exception)
- [x] `bin/test.region`'s own run reports exactly 12024 tests, OK
      (`SKIP=11`, matching F03's T5 baseline's own skip count
      unchanged; 0 failures)
- [x] No exit-code or error change in `bin/test.region` attributable to
      the now-near-empty `--select-dir=src/metadataserver` (one file
      remains, `tests/test_fields.py`, per TD-005)

### Files
- None in `metadataserver`/`src/tests` (verification-only task; no
  further relocation code change beyond T1-T3, per design §3.3/§16 FAQ)
- `src/maasserver/tests/test_storage_layouts.py` — modified (TD-006
  import fix)
- `src/maasserver/api/tests/test_machine.py` — modified (TD-006 import
  fix)
- `src/maasserver/models/tests/test_node.py` — modified (TD-006 import
  fix)
- `pyproject.toml` — modified (`"tests"` added to
  `lint.isort.known-first-party`, TD-006)

### Verification
- [x] `find src/metadataserver -name 'test_*.py' | wc -l` → `1`
      (`tests/test_fields.py`, TD-005's intentional exception) —
      confirmed
- [x] `bin/test.region` (or `.ve/bin/test.region`) full run — exit 0,
      test count = 12024 (13013 baseline − 989), `SKIP=11`

## Task T5: Coverage verification + full regression sign-off

**Priority:** P0
**Estimate:** 1h
**Dependencies:** T1, T2, T3, T4
**Covers:** FR-004, NFR-001, NFR-002

### Work
- [x] Run `utilities/coverage-baseline check metadataserver` against
      the post-cutover pytest-only suite
- [x] Run the full `pytest src/tests` suite once (confirms
      `metadataserver`'s new tests pass alongside every other
      already-pytest-native package, no cross-package regression)
- [x] Run `bin/test.rack` (provisioningserver's own suite, unaffected
      by this feature) to confirm no unrelated regression
- [x] Confirm no test modernization crept in during T1-T3 (NFR-002) —
      spot-check that relocated `MAASTestCase`/`scenarios`-using files
      keep their original base classes/attributes unchanged (diff
      review, not a new tool)
- [x] Fixed `maastesting/testcase.py`'s unguarded `nose` import
      (TD-008), a pre-existing, repo-wide (not metadataserver-specific)
      blocker to this task's own "full `pytest src/tests` passes"
      criterion, per direct user instruction

### Acceptance Criteria
- [x] `utilities/coverage-baseline check metadataserver` reports
      `verdict: FAIL` (89.33% vs. 95.05% baseline, -5.72pp) — accepted
      per D-004/TD-007 as a documented, structural exception (TD-005's
      `TestBinaryField` split is the sole, fully-attributed cause; not
      a regression in any pytest-collected test)
- [x] Full `pytest src/tests` run passes with `metadataserver`'s tests
      included: 8741 passed, 181 skipped, 3 failed — the 3 failures
      are pre-existing and unrelated (2 `maasapiserver` v3 etag-hash
      assertions, 1 `maastesting.test_runtest` `ReactorAlreadyRunning`
      flake; confirmed via the same pre-existing pattern already
      logged during coverage-check's own combined run), 0 collection
      errors (was 45, repo-wide, before TD-008)
- [x] `bin/test.rack` run: 3533 tests, 14 errors — all 14 are
      `PermissionError: os.setpgrp()` (`provisioningserver.utils.arp`/
      `avahi`/`beaconing`), a sandbox/environment limitation (no
      process-group permission) reproducing identically on HEAD before
      any F04 change and in isolated reruns of the same files;
      unrelated to this feature, which touches no `provisioningserver`
      files
- [x] No relocated file's test style was changed beyond the merge
      (T1) and the 2 import fixes (T3) — confirmed via `git show`
      rename-similarity stats: every relocated file is a 100%-identical
      rename except `test_maas_wipe.py` (99%, the intentional TD-003
      dotted-import fix)

### Files
- `src/maastesting/_nose_compat.py` (new; TD-008 shared compat shim)
- `src/maastesting/testcase.py` (TD-008: import the shim before `nose`)
- `src/maastesting/noseplug.py` (TD-008: use the shared shim instead of
      its own inline copy)
- `utilities/check-imports` (TD-006 follow-on: allow `tests|tests.**`
      in `TestingLibraries`, needed for the 3 `maasserver` files
      TD-006 repointed to import from `tests.metadataserver.*`)

### Verification
- [x] `utilities/coverage-baseline check metadataserver` — `verdict:
      FAIL` (documented exception, D-004/TD-007)
- [x] `pytest src/tests` full run — exit 1 (3 pre-existing, unrelated
      failures), 8741 passed, includes `metadataserver`'s relocated
      tests, 0 collection errors
- [x] `bin/test.rack` full run — 3533 tests, 14 pre-existing/
      environment-only `setpgrp` errors (confirmed unrelated)
- [x] `make lint` passes across all files touched by T1-T3 and T5
      (`ruff format`, `ruff check`, `pyproject-fmt`, `pyright`,
      `check-imports` — all exit 0)
