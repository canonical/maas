# Tasks: Minimal gap shims for pytest-native legacy test execution

> Requirements: @requirements.md
> Status: Approved

## Requirement Coverage

| Requirement | Tasks | Notes |
|-------------|-------|-------|
| FR-001 | T2, T4 | Scenario shim + verification against representative file |
| FR-002 | T1, T4 | Shared `setup_crochet()` + fixture + verification |
| FR-003 | T3, T4 | `api.py` `__init__` guard + verification |
| FR-004 | T4 | Spot-check gap-free files unaffected |
| NFR-001 | T4 | Reactor-once, deterministic scenario IDs verified |
| NFR-002 | T5 | Explicit scope-boundary check before final sign-off |

## Implementation Readiness Check

| Check | Status | Notes |
|-------|--------|-------|
| Must Have requirements have tasks | Pass | FR-001/002/003/004 each covered |
| Requirements are covered by design | Pass | design.md §3.1-§3.3, §13 |
| Critical Questions are answered | Pass | requirements.md Questions: "None open" |
| Tasks have dependencies, acceptance criteria, files, and verification | Pass | See T1-T5 below |
| Verification commands are known or marked manual/N/A | Pass | `make lint`, targeted `pytest`/`nose` runs per task, full-suite runs in T4/T5 |

## Implementation Slices

### MVP Slice

- **Goal:** All three gaps closed; representative sample from each tier
  passes under pytest with the same outcome as `nose`; no regression to
  `nose` itself or to the 147 already-gap-free files.
- **User Stories:** US-001, US-002, US-003
- **Tasks:** T1 → T2, T1 → (T3 independent) → T4 → T5
- **Independent validation:** Each of T1-T3 is independently testable in
  isolation (unit-level); T4 is the cross-cutting integration proof; T5
  is the final scope-discipline/full-suite gate.

## Task T1: Extract shared `setup_crochet()` helper

**Priority:** P0
**Estimate:** 45m
**Dependencies:** none
**Covers:** FR-002 (shared-helper half)

### Work
- [x] Move the body of `noseplug.py`'s `Crochet.configure()` (the
      `EventualResult` patching + `crochet.setup()`/`crochet.no_setup()`
      call) into a new `maastesting.crochet.setup_crochet(no_setup=False)`
      function (design §3.2/TD-002)
- [x] Update `noseplug.py`'s `Crochet.configure()` to call
      `setup_crochet(no_setup=getattr(options, self.option_no_setup))`
      instead of inlining the logic
- [x] No change to `Crochet`'s nose-plugin contract (`options()`,
      `help()`, option name) — only the body of `configure()` changes

### Acceptance Criteria
- [x] `maastesting.crochet.setup_crochet` exists, callable with no
      required arguments, defaults to the `crochet.setup()` (not
      `no_setup()`) path — confirmed
- [x] `noseplug.py`'s `Crochet` plugin produces identical behavior to
      before the refactor (verified in T4/T5's full `nose` run)

### Files
- `maastesting/crochet.py` — modify (add `setup_crochet`)
- `maastesting/noseplug.py` — modify (`Crochet.configure()` calls it)

### Verification
- [x] `make lint` passes — confirmed (`ruff check`/`ruff format --check`)
- [x] Manual: `.ve/bin/python -c "from maastesting.crochet import
      setup_crochet; setup_crochet(); print('reactor running:',
      __import__('twisted.internet.reactor',
      fromlist=['reactor']).running)"` confirms the reactor starts
      without error — confirmed (`reactor running: True`)
- [ ] Full `nose` regression deferred to T5 (cheaper to batch once
      after T2/T3 land too, rather than running the full suite after
      every task)

## Task T2: Scenario application pytest plugin

**Priority:** P0
**Estimate:** 2h
**Dependencies:** T1 (shares the same new plugin module/entry point registration step)
**Covers:** FR-001

### Work
- [x] Create `maastesting/pytest/legacy.py` with:
  - `pytest_collection_modifyitems` hook implementing class-level
    scenario multiplication (design §3.1): for each collected unittest
    class with a non-empty *effective* `scenarios` list, build one
    dynamically-typed subclass per scenario entry, then re-collect via
    pytest's own `pytest_pycollect_makeitem`/`UnitTestCase` machinery
  - the session-scoped autouse `_crochet_reactor` fixture calling
    `maastesting.crochet.setup_crochet()` (FR-002's fixture half,
    design §3.2)
  - Discovered during verification (two real gaps beyond design §3.1's
    original sketch, both fixed within this task, not deferred):
    1. `APITestCaseBase.__init__` *merges additional* scenarios
       (user/client factory combinations) into `self.scenarios` at
       instance-construction time, not visible as a class attribute —
       reading the raw `cls.scenarios` silently dropped them. Fixed by
       building one throwaway instance per class
       (`_effective_scenarios`) to read the fully-merged list, since
       `__init__` only merges attributes and does not touch the
       database.
    2. `testscenarios.apply_scenario()` sets scenario values via
       `setattr(instance, key, value)` (instance `__dict__`), which
       never binds a plain function/lambda as a method. Setting the
       same value as a *class* attribute (required here, since
       multiplication happens at class level) silently bound it,
       passing `self` as an extra positional argument. Fixed by
       wrapping any `types.FunctionType` scenario value in
       `staticmethod()` before setting it as a class attribute,
       matching instance-attribute-set semantics.
- [x] Register `entry-points.pytest11.maas-legacy =
      "maastesting.pytest.legacy"` in `pyproject.toml`, between
      `maas-environment` and `maas-perftest` (confirmed alphabetical slot)

### Acceptance Criteria
- [x] A throwaway test class with a `scenarios = [("a", {...}), ("b",
      {...})]` attribute, collected by pytest with the plugin active,
      produces 2 distinct test items (one per scenario) with the
      expected per-scenario attributes set on each instance — confirmed
- [x] A class with no `scenarios` attribute (or an empty list) is
      collected unchanged — same single item as without the plugin —
      confirmed
- [x] The session-scoped reactor fixture starts the reactor exactly
      once per pytest session (not per test, not per file) — confirmed
      (32 tests across 5 files in one session, no per-test reactor
      re-setup errors)

### Files
- `maastesting/pytest/legacy.py` — new
- `pyproject.toml` — modify (entry point registration)

### Verification
- [x] `make lint` passes — confirmed
- [x] Manual: throwaway scenario-bearing test file + `pytest
      --collect-only` confirms the multiplied item count/IDs — confirmed
      (2 items, correct `value` per scenario)
- [x] Manual: against the representative scenario-tier file
      `src/maasserver/api/tests/test_nodedevices.py` (170 lines; has a
      `scenarios` attribute) — compare `pytest`'s collected/passed test
      count to `nose`'s own reported count for the same file (same
      invocation each via `.ve/bin/test.region`'s nose path vs. ad hoc
      `pytest src/maasserver/api/tests/test_nodedevices.py`) — confirmed:
      13 tests both runners (nose: `Ran 13 tests ... OK`; pytest: `13
      passed`)
- [x] Manual: against the representative reactor-tier file
      `src/maasserver/rpc/tests/test_module.py` (46 lines; uses
      `maastesting.crochet.wait_for`) — confirm it passes under pytest
      with the fixture active (previously would fail/hang without a
      running reactor) — confirmed (4 passed)

## Task T3: `APITestCaseBase.__init__` collection-time fix

**Priority:** P0
**Estimate:** 30m
**Dependencies:** none (independent of T1/T2 — different file, no shared state)
**Covers:** FR-003

### Work
- [x] In `maasserver/testing/api.py`, guard
      `APITestCaseBase.__init__`'s `self.userfactories`/
      `self.clientfactories` access with `or {}` before `sorted(...)`
      (design §3.3 — exact code block given there)

### Acceptance Criteria
- [x] Direct instantiation of `APITestCaseBase`/`APITestCase` (simulating
      pytest's unittest collector constructing the abstract class) no
      longer raises `TypeError` — confirmed indirectly: T2's
      `_effective_scenarios` helper constructs one throwaway instance of
      every collected `scenarios`-bearing class (including
      `APITestCaseBase`-derived abstract classes, if collected) during
      every representative-file run below, none raised
- [x] A concrete `.ForUser`/`.ForAdmin`-derived subclass's computed
      `self.scenarios` is unchanged from before the fix (same scenario
      dicts, same ordering) — confirmed: `test_not_found.py`'s 12-test
      pytest count exactly matches `nose`'s own 12-test count for the
      same file, with the same `user=`/`client=` scenario names

### Files
- `maasserver/testing/api.py` — modify

### Verification
- [x] `make lint` passes — confirmed
- [x] Manual: against the representative `APITestCase`-tier file
      `src/maasserver/api/tests/test_not_found.py` (36 lines) — confirm
      it collects successfully under `pytest` (0 collection errors) and
      passes with the same outcome as its existing `nose` run —
      confirmed: nose `Ran 12 tests ... OK`; pytest `12 passed`, 0
      collection errors (previously: 1 collection `TypeError`)

## Task T4: Cross-tier integration verification

**Priority:** P0
**Estimate:** 1h
**Dependencies:** T1, T2, T3
**Covers:** FR-001, FR-002, FR-003, FR-004, NFR-001

### Work
- [x] Run `pytest` against each of the three representative files named
      in T2/T3's verification steps together in one invocation,
      confirming all three collect and pass with the shims active
- [x] Spot-check a small sample (3-5 files) of the 147 already
      gap-free files under pytest with the shim active, confirming
      identical pass/fail outcome to before this feature (FR-004)
- [x] Confirm the reactor-starting fixture does not start the reactor
      more than once across a multi-file pytest invocation (NFR-001) —
      e.g. assert via a session-scoped counter or by inspecting
      `crochet`'s own internal state after the run

### Acceptance Criteria
- [x] All three representative files pass under pytest, matching their
      existing `nose` pass/fail outcome exactly — confirmed (13/13,
      4/4, 12/12)
- [x] Gap-free sample files show zero behavior change — confirmed:
      `test_vlan.py` 38 passed identically with/without the plugin
      active; `test_eventloop.py`/`test_proxyconfig.py` show identical
      pre-existing failures with/without the plugin (unrelated to this
      feature, confirmed by disabling the plugin and reproducing the
      same failures)
- [x] Reactor startup confirmed single-shot per session — confirmed: 32
      tests across 5 files (including 2 reactor-dependent files) passed
      in one combined session with no reactor-restart errors

### Files
- None (verification-only task; no new files)

### Verification
- [x] `pytest src/maasserver/api/tests/test_nodedevices.py
      src/maasserver/rpc/tests/test_module.py
      src/maasserver/api/tests/test_not_found.py -v` — all pass —
      confirmed (29 passed across the three files, combined with 2 more
      smoke-test files for 32 passed total)
- [x] Manual comparison of pass counts against each file's current
      `nose`-reported count (via `bin/test.region`/`bin/test.rack`
      targeted run or existing CI logs) — confirmed via
      `.ve/bin/test.region maasserver.api.tests.test_not_found` (12,
      OK) and `.ve/bin/test.region maasserver.api.tests.test_nodedevices`
      (13, OK)

## Task T5: Full-suite regression + scope-discipline sign-off

**Priority:** P0
**Estimate:** 1h
**Dependencies:** T1, T2, T3, T4
**Covers:** NFR-002 (scope discipline), overall non-regression

### Work
- [x] Run the full `nose`-based suite (`bin/test.rack`/`bin/test.region`
      or `.ve/bin/test.rack`/`.ve/bin/test.region` as applicable) after
      all changes land, confirming the `Crochet` refactor (T1) did not
      regress `nose`'s own pass count (compare to the known baseline:
      3533 tests, OK, per F02's own verification session) — `test.rack`
      confirmed (3533 tests, OK, exact match); `test.region` confirmed
      (13013 tests, OK, SKIP=11, 2500.98s wall time)
- [x] Confirm no additional (fourth) gap was discovered beyond
      scenarios/reactor/`APITestCase` during T2-T4's work — confirmed:
      the two sub-discoveries in T2 (scenario merging happening in
      `__init__` rather than as a class attribute; plain-function
      scenario values binding as methods when set at class level) are
      both squarely *within* FR-001's own scenario-multiplication
      mechanism, not a new, independent gap category — no
      stop-and-ask was required

### Acceptance Criteria
- [x] `nose`'s full suite passes with an identical count to the
      pre-feature baseline — `test.rack`: 3533 tests, OK (exact match);
      `test.region`: 13013 tests, OK (SKIP=11), no failures
- [x] No undocumented/unapproved scope extension occurred — confirmed,
      per Work item above

### Files
- None (verification-only task; no new files)

### Verification
- [x] `.ve/bin/test.rack` full run — pass count matches baseline (3533
      tests, OK); `.ve/bin/test.region` full run — 13013 tests, OK
      (SKIP=11), confirming T1's `Crochet` refactor is behavior-preserving
- [x] `make lint` passes across all files touched by T1-T3 — confirmed
      (`maastesting/crochet.py`, `maastesting/noseplug.py`,
      `maastesting/pytest/legacy.py`, `maasserver/testing/api.py`,
      `pyproject.toml`)
