# Tasks: Cut over `provisioningserver` to pytest (F05)

> Requirements: @requirements.md
> Design: @design.md
> Status: Approved

## Requirement Coverage

| Requirement | Tasks | Notes |
|-------------|-------|-------|
| FR-001 | T1, T2 | T1 generates the authoritative gap-free file list; T2 relocates them |
| FR-002 | T1, T3 | T1 generates the authoritative scenario-gap file list; T3 relocates them via F03's shim |
| FR-003 | T1, T2, T3 | FIPS/hardening files tracked through whichever bucket (§ design.md FIPS cross-reference) they fall in; none deleted |
| FR-004 | T2, T3, T5 | Narrowing is automatic once files move (design TD-001); T5 confirms the carve-out still runs under `nose` unaffected |
| FR-005 | T6 | `coverage-baseline check`, root-caused per design §9 |
| FR-006 | T2 (confirms no actual path collision at relocation time) | |
| FR-007 | T4 | Carve-out list recorded; follow-up idea captured |
| NFR-001 | T4, T5 | Double-run discipline; carve-out regression check |
| NFR-002 | T1 (stop-and-reassess gate), all tasks (no style changes) | |

## Implementation Readiness Check

| Check | Status | Notes |
|-------|--------|-------|
| Must Have requirements have tasks | Pass | FR-001–FR-007 all covered (table above) |
| Requirements are covered by design | Pass | Every FR maps to a named design section/TD (`design.md` §2) |
| Critical Questions are answered | Pass | `requirements.md` Questions: "None open"; D-001 (superseded), D-002 resolved via direct user instruction |
| Tasks have dependencies, acceptance criteria, files, and verification | Pass | See tasks below |
| Verification commands are known | Pass | `pytest`, `bin/test.rack`, `utilities/coverage-baseline check`, `make lint` all concrete, pre-existing commands |

## Implementation Slices

### MVP Slice

- **Goal:** All 90 migratable `provisioningserver` files pass under
  `pytest src/tests/provisioningserver`, the 39-file carve-out
  continues passing under `nose` unaffected, and the coverage/FIPS
  gates are run and root-caused.
- **User Stories:** US-001, US-002, US-003, US-004, US-005
- **Tasks:** T1-T6 (all; no natural sub-phase beyond
  gap-free-then-scenario-gap ordering, per design §12)
- **Independent validation:** T6's coverage-check run plus T5's
  carve-out regression pass together are the slice's completion
  signal.

## Task Summary

| Task | Title | Priority | Estimate | Dependencies | Status |
|------|-------|----------|----------|---------------|--------|
| T1 | Regenerate and freeze the authoritative three-way file partition | P0 | 1h | none | done |
| T2 | Relocate the 72 gap-free files | P0 | 3h | T1 | done |
| T3 | Relocate the 18 scenario-gap files | P0 | 2h | T1, T2 | done |
| T4 | Record the carve-out and capture a follow-up idea | P1 | 1h | T1 | done |
| T5 | Full-suite double-run and carve-out regression check | P0 | 1.5h | T2, T3 | done |
| T6 | Coverage-baseline check and root-cause | P0 | 1h | T5 | done |

## Task T1: Regenerate and freeze the authoritative three-way file partition

**Priority:** P0
**Estimate:** 1h
**Dependencies:** none
**Covers:** FR-001, FR-002, NFR-002 (stop-and-reassess gate)

### Work
- [x] Re-ran the authoritative carve-out grep against the live tree:
      `grep -rl 'run_tests_with.*MAASTwistedRunTest\|MAASTwistedRunTest.make_factory' src/provisioningserver --include='test_*.py'`
      — 39 files, identical to design.md's §4 list (stable, confirmed
      by diff)
- [x] Re-ran the scenario-gap grep (`scenarios = `) directly against
      all 90 non-carve-out files (not a reactor-keyword-prefiltered
      subset) — found **18** files, not design.md's 16: 2 additional
      genuine matches, `src/provisioningserver/tests/test_config.py`
      and `src/provisioningserver/utils/tests/test_config.py`, both
      confirmed by direct read to contain real `scenarios = (...)`
      class attributes (not keyword false positives)
- [x] Diffed against design.md §4: carve-out list unchanged (39/39,
      zero diff); scenario-gap list grew by exactly these 2 files;
      gap-free set correspondingly shrank from 74 to 72 (these 2 files
      were wrongly bucketed gap-free in design.md, since design time's
      candidate pool for the scenario grep never included them —
      documented as requirements.md D-003 / design.md TD-002)
- [x] No file matches both grep patterns; no file fails to bucket
      cleanly — no stop-and-reassess triggered

### Acceptance Criteria
- [x] Exactly 39 files match the carve-out grep
- [x] Exactly 18 files match the scenario-gap grep (excluding carve-out)
- [x] 129 − 39 − 18 = 72 remaining files are the gap-free set
- [x] No file appears in more than one bucket

### Files
- None (read-only verification; no files modified this task)

### Verification
- [x] Manual: grep output counts diffed against design.md §4 — 2
      discrepancies found (scenario-gap undercounted), individually
      reconciled by direct file read, and folded back into
      `requirements.md` (D-003) and `design.md` (TD-002, §4 lists)
      before proceeding to T2

## Task T2: Relocate the 72 gap-free files

**Priority:** P0
**Estimate:** 3h
**Dependencies:** T1
**Covers:** FR-001, FR-003 (gap-free FIPS files), FR-006

### Work
- [x] For each of the 72 gap-free files (T1's frozen list): `git mv`
      from `src/provisioningserver/<path>/tests/test_*.py` to
      `src/tests/provisioningserver/<path>/tests/test_*.py`
- [x] For `drivers/power/tests/test_utils.py` and
      `utils/tests/test_utils.py` specifically (the two migratable
      `test_utils.py` basename matches, design §9): confirm after move
      that both land at distinct paths, neither colliding with the
      pre-existing `src/tests/provisioningserver/prometheus/test_utils.py`
      (FR-006)
- [x] Run `pytest src/tests/provisioningserver` after all 72 are moved;
      confirm pass count matches the sum of each file's current
      `nose`-reported pass count (per-file, not just a final aggregate
      number). 2 of 72 files (`test_powernv.py`, `test_s390x.py`) still
      fail collection — expected, blocked on T3 (`test_pxe.py` not yet
      relocated). `test_beaconing.py` has 2 failures reproduced
      identically at the pre-move location under plain pytest
      (stdin-capture env quirk, pre-existing, out of scope).

### Acceptance Criteria
- [x] All 72 gap-free files exist only under `src/tests/provisioningserver/`,
      not under `src/provisioningserver/`
- [x] Every relocated file passes under pytest with the same pass count
      it had under `nose`, except the 2 pre-existing `test_beaconing.py`
      failures (confirmed identical before/after move) and the 2 files
      blocked on T3's `test_pxe.py` relocation
- [x] The two `test_utils.py` files and the pre-existing
      `prometheus/test_utils.py` all exist at distinct paths, confirmed
      by directory listing

### Files
- 72 files — `git mv` from `src/provisioningserver/**/tests/` to
  `src/tests/provisioningserver/**/tests/` (exact list per T1's frozen
  output)

### Verification
- [x] `pytest src/tests/provisioningserver -q` — 1044 passed, 2 failed
      (`test_beaconing.py`, pre-existing), 2 errors (`test_powernv.py`,
      `test_s390x.py`, blocked on T3)
- [x] `make lint` — no new violations from the move
- [x] `git status --short` — confirms only the expected 72 files moved
      plus fixes required by relocation (cross-test import rewrites,
      missing `__init__.py`, `test_amt.py`/`test_arguments.py` path fixes)

## Task T3: Relocate the 18 scenario-gap files

**Priority:** P0
**Estimate:** 2h
**Dependencies:** T1, T2
**Covers:** FR-002, FR-003 (`test_ipmi.py`)

### Work
- [x] For each of the 18 scenario-gap files (T1's frozen list): `git
      mv` from `src/provisioningserver/<path>/tests/test_*.py` to
      `src/tests/provisioningserver/<path>/tests/test_*.py` — no file
      content changes beyond relocation-path-assumption fixes below,
      relying on F03's already-registered `ScenarioUnitTestCase`
      plugin (`pytest11` entry point, no per-package wiring needed)
- [x] Run `pytest src/tests/provisioningserver` after all 18 are moved;
      confirm scenario multiplication produces the same effective test
      count as `nose`'s own scenario-multiplied count per file. Fixed
      3 `__file__`-relative path assumptions broken by relocation:
      `test_pxe.py` (cross-test import to relocated `test_kernel_opts`),
      `test_logger.py` (script path to `logsomething.py` helper,
      which correctly stays in `provisioningserver/logger/testing/`),
      `test_utils.py::test_returns_test_path` (template dir path,
      correctly stays relative to production `utils/__init__.py`, not
      the test's own location). Added missing
      `src/tests/provisioningserver/drivers/{__init__.py,tests/__init__.py}`.

### Acceptance Criteria
- [x] All 18 scenario-gap files exist only under
      `src/tests/provisioningserver/`
- [x] Each file's pytest-collected (scenario-suffixed) node count
      matches its `nose`-reported count exactly, per file — verified
      all 18 files individually (nose baseline captured via temporary
      restore of the one cross-moved dependency, `test_kernel_opts.py`,
      at its pre-T2 path; no working-tree changes left behind)
- [x] `test_ipmi.py` (FIPS, scenario-gap) passes with unchanged
      assertions/behavior — 22/22, matches nose baseline exactly

### Files
- 18 files — `git mv` from `src/provisioningserver/**/tests/` to
  `src/tests/provisioningserver/**/tests/` (exact list per T1's frozen
  output / design.md §4)

### Verification
- [x] `pytest src/tests/provisioningserver -q` — 1755 passed, 2 failed
      (`test_beaconing.py`, pre-existing per T2, reproduced identically
      before this move too)
- [x] `make lint` — no new violations
- [x] `git status --short` — confirms only the expected 18 files moved
      plus the 3 relocation-fallout fixes and 2 new `__init__.py` files

## Task T4: Record the carve-out and capture a follow-up idea

**Priority:** P1
**Estimate:** 1h
**Dependencies:** T1
**Covers:** FR-007, US-005

### Work
- [x] Confirm design.md §4's 39-file carve-out list is current (post
      T1's re-verification) and committed as the durable record —
      re-confirmed unchanged (39/39, zero diff) across T1, T2, and T3
- [x] Capture a new idea artifact,
      `.ai/sdd/ideas/004-provisioningserver-twisted-reactor-carveout.md`,
      naming: the blocking mechanism (testtools' `Spinner`-driven
      per-test reactor vs. crochet's always-on reactor), the exact
      39-file list (or a pointer to design.md §4), and the candidate
      directions already identified in design.md's Out of
      Scope/Migration-Rollout sections (separate pytest
      invocation/process, or deferral to `nose` retirement F08)
- [x] Update `.ai/sdd/INDEX.md`'s Ideas table with the new entry
      (`idea:captured`)

### Acceptance Criteria
- [x] The follow-up idea file exists, names the 39 files (by reference)
      and the specific blocking mechanism
- [x] `INDEX.md` lists it

### Files
- `.ai/sdd/ideas/004-provisioningserver-twisted-reactor-carveout.md` — create
- `.ai/sdd/INDEX.md` — modify (Ideas table)

### Verification
- [x] Manual: idea file content cross-checked against design.md's D-002
      and §4 for consistency (no contradicting file counts or claims)

## Task T5: Full-suite double-run and carve-out regression check

**Priority:** P0
**Estimate:** 1.5h
**Dependencies:** T2, T3
**Covers:** FR-004, NFR-001

### Work
- [x] Run `pytest src/tests` (full suite, not just
      `provisioningserver`) twice, confirming identical pass/fail
      results both times (NFR-001: catches reactor-state leakage
      introduced by relocating the 18 scenario-gap/Twisted-adjacent
      files into the same process as `maasserver`/`metadataserver`).
      Found and fixed 5 cross-package/cross-test import breaks caused
      by T2/T3's relocation that only surfaced at full-suite scale:
      `test_hooks.py` (metadataserver → relocated
      `provisioningserver.utils.tests.test_lxd`) plus, while verifying
      `bin/test.rack`'s narrowing below, 4 carve-out files
      (`test_boot.py`, `test_windows.py`, `test_tftp.py`,
      `test_services.py`) importing from relocated gap-free/scenario-
      gap test files — rewritten to the new
      `tests.provisioningserver.*` dotted path, confirmed resolvable
      under nose's own `PYTHONPATH=src` (same sys.path root as pytest's
      `src/tests` layout).
- [x] Run `bin/test.rack` (or `.ve/bin/test.rack`), confirming it still
      collects and passes exactly the 39 carve-out files (not 129 —
      confirming the other 90 are gone from its `--select-dir` walk
      automatically, no `scripts.py` edit needed per design TD-001)

### Acceptance Criteria
- [x] Two consecutive full `pytest src/tests` runs produce identical
      pass/fail outcomes (no flakiness introduced) — both runs: same 5
      named failures (`test_zones.py::test_etag`,
      `test_resource_pools.py::test_etag`,
      `test_runtest.py::test_catches_generator_tests[MAASTwistedRunTest]`,
      2x `test_beaconing.py`), all independently confirmed pre-existing
      and unrelated to F05 (etag tests pass in isolation — xdist DB-
      contention artifact; `test_runtest.py` reproduces identically at
      HEAD before any F05 change, file untouched by this feature;
      `test_beaconing.py` confirmed pre-existing in T2). 10 additional
      xdist-contention errors in run 1 (`maasservicelayer` DB
      repository tests) did not reproduce in run 2 and pass in
      isolation — confirmed environment/connection-pool flakiness, not
      a regression
- [x] `bin/test.rack`'s reported test count equals the 39 carve-out
      files' own total test count (not 129's worth), confirming
      automatic narrowing — `find src/provisioningserver -name
      'test_*.py' | wc -l` = 39; `bin/test.rack` collects/passes 1851
      tests, OK (SKIP=1)

### Files
- `src/tests/metadataserver/builtin_scripts/test_hooks.py` — fix
  cross-package import to relocated `test_lxd.py`
- `src/provisioningserver/boot/tests/test_boot.py`,
  `test_windows.py`, `rackdservices/tests/test_tftp.py`,
  `utils/tests/test_services.py` — fix cross-test imports from
  carve-out files to relocated gap-free/scenario-gap test files

### Verification
- [x] `pytest src/tests -q` × 2 — identical stable-failure-set results
      both runs (see above)
- [x] `bin/test.rack` — passes (1851 tests, SKIP=1), test count matches
      the 39-file carve-out only
- [x] `make lint` — clean

## Task T6: Coverage-baseline check and root-cause

**Priority:** P0
**Estimate:** 1h
**Dependencies:** T5
**Covers:** FR-005

### Work
- [x] Ran `utilities/coverage-baseline check provisioningserver`:
      `baseline 94.91% -> current 28.72%, delta -66.19pp, FAIL`.
- [x] Root-caused the delta to a **scoping artifact of the tool's own
      `--include=src/provisioningserver/*` filter**, not a regression.
      coverage.py expands a trailing `/*` recursively, so the filter
      counts *test files' own source lines* as measured code. At
      capture time all 129 test files lived under
      `src/provisioningserver/` and were executed (nose for the 39
      carve-out files, pytest for the rest), so their lines counted as
      ~100% covered. `check` runs pytest only, which never collects
      anything under `src/provisioningserver/`, so the 39 carve-out
      files' lines are counted but never executed. Measured directly:
      the filter spans 28,549 statements, of which only 14,318 are
      production code - i.e. **14,231 statements (50% of the
      denominator) are carve-out test files that pytest cannot run.**
- [x] Proved the deficit is pure execution-invisibility by combining
      the nose carve-out run with the pytest run (what `capture` does
      and `check` does not):
      - pytest only: 27.83% (production-only 49.78%)
      - nose + pytest combined: **93.22%** (production-only **88.26%**)
      Coverage is restored by running the carve-out, confirming the
      production code is still exercised; nothing regressed.
- [x] Like-for-like comparison against the baseline (adding the
      relocated tests' new home to the scope the baseline measured,
      `--include=src/provisioningserver/*,src/tests/provisioningserver/*`,
      combined nose+full-pytest): **95.07% vs baseline 94.91% =
      +0.16pp**, statements 39,662 vs 39,226. Coverage is marginally
      **better** than baseline. FR-005's "coverage must not regress"
      intent is satisfied.
- [x] Fixed two real defects surfaced by this task's full serial run
      (see Files below); full-suite failures went 54 -> 5 (the 5 being
      the documented pre-existing set from T5).

### Acceptance Criteria
- [x] `check`'s result recorded with exact numbers (94.91% -> 28.72%,
      -66.19pp, FAIL)
- [x] Root-cause written down: the tool's `--include` counts unexecuted
      carve-out test files as uncovered source; not a silent regression
- [x] The migrated files' coverage contribution independently confirmed
      non-regressed - like-for-like scope gives +0.16pp vs baseline

### Files
- `src/maasservicelayer/db/alembic/env.py` - fix unbounded `sys.path`
  growth (anchor on `__file__`, not the mutable `sys.path[0]`)
- `src/tests/maascommon/test_tracing.py` - autouse fixture resetting
  the `TRACE_ID` contextvar, fixing cross-test pollution
- `src/provisioningserver/utils/tests/test_twisted.py` - add missing
  `addCleanup(set_trace_id, "")`

### Verification
- [x] `utilities/coverage-baseline check provisioningserver` - FAIL
      recorded and root-caused as a tool-scoping artifact
- [x] `coverage json --include=...` cross-checks - combined nose+pytest
      restores 93.22%; like-for-like scope beats baseline by +0.16pp
- [x] Full suite: 5 failed / 10,434 passed (down from 54 failed)
- [x] `bin/test.rack` - 1851 tests, OK (SKIP=1)
- [x] `make lint` - clean
