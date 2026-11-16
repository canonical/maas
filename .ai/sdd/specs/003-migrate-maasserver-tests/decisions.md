# Decisions: Migrate maasserver tests (F03)

## Resource-reuse mechanism required (FR-006/D-004)

**Context:** Nose's speed for `MAASServerTestCase`/
`MAASTransactionServerTestCase`-based tests comes entirely from
`OptimisingTestSuite.run()`/`switch()` holding the shared
`DjangoDatabasesManager`/`DjangoPristineDatabaseManager` resource open
across a whole run of adjacent tests sharing it. This was flagged in
general terms by F02's `decisions.md` ("F03 implication: ... expect
resource build/teardown overhead per test (and per worker) that nose's
current CI run does not pay") but not quantified.

**Finding (design-phase spike, confirmed against a real file,
`src/maasserver/models/tests/test_template.py`, 4 tests, no mocks):**

- Unmitigated (plain pytest, no suite-level reuse): ~0.294s
  pristine-template rebuild (full `dbupgrade`/migrations cycle) +
  ~0.093s per-test DB copy ≈ ~0.4s/test tax. 4 tests → 4 separate
  pristine rebuilds, 4.28s total (vs. nose: 0.659s for the same 4 tests
  *after* its one-time build).
- 260 of 338 maasserver files (~7,374 test methods) use
  `MAASServerTestCase`/`MAASTransactionServerTestCase`, i.e. depend on
  this exact resource chain. Extrapolated: ~49 minutes of pure
  single-worker overhead — not linearly reducible by adding
  `pytest-xdist` workers, since every worker independently repeats full
  `dbupgrade` cycles against one shared Postgres cluster (potential
  lock/IO contention, not yet measured at full scale).
- **Fix, verified:** hold the two top-level manager singletons
  (`MAASServerTestCase.resources`/`MAASTransactionServerTestCase.resources`,
  each a class-level tuple shared by every subclass/instance) open for
  the life of each pytest worker process — `getResource()` once at
  session start, `finishedWith()` once at session end. Confirmed: 6
  tests across 3 files → 1 pristine build (not 6), 0.85s total (vs.
  4.28s unmitigated for just 4 tests). Per-test isolation
  (count-sensitive assertions) still holds, since it comes from
  `beginTransaction()`/rollback, independent of resource lifecycle.
  Verified correct under `-n 2 --dist=load` (each xdist worker holds
  its own instance correctly, no cross-worker interference).

**Decision:** This amends F03's original Constraint, which forbade new
resource-plugin work. A new, additive `maastesting/pytest/region.py`
plugin is added. No changes to `DjangoDatabasesManager`/
`DjangoPristineDatabaseManager`'s own `make`/`clean`/`isDirty`, or to
`MAASTestCase`/`MAASServerTestCase`'s existing `setUp`/`tearDown` —
only *when* the resource's use-count starts/ends changes.

**Source:** Design-phase spike (recorded in `design.md` §3/§13 TD-002),
confirmed with build-timing instrumentation against real files. User
approved the Constraint amendment (Q: resource_reuse).

**Impacts:** `requirements.md` D-004, FR-006, NFR-002, Constraint,
Risks; `design.md` §3, §13 TD-002.

## Reactor/crochet/thread-pool setup required (FR-007/D-005)

**Context:** A real, `deferToDatabase`-based file
(`src/maasserver/tests/test_security.py`) was used to validate
outcome parity per FR-001, independent of the resource-reuse spike
above.

**Finding:** 3 of 4 tests failed under plain pytest —
`AttributeError: 'EPollReactor' object has no attribute
'threadpoolForDatabase'` initially, then an unresolved, stuck
`Deferred` once the thread-pool was installed without also starting
the reactor via `crochet.setup()`. Same file: 4/4 pass under nose.
Root cause: nose's `run_region()` installs Twisted's thread-pools
(`install_default_pool`/`install_database_unpool`) and starts the
reactor in a background thread via `crochet.setup()` (with
`EventualResult` timeout-enforcement patching) — no existing
`maastesting/pytest/*.py` plugin replicates this. `src/tests` (the
existing pytest-native suite) has zero `deferToDatabase` usages today,
so this gap was never exercised before F03. 68 of 338 maasserver files
use `deferToDatabase`.

**Fix, verified:** install the identical sequence `run_region()`
already performs, once per pytest worker process, in the same new
`maastesting/pytest/region.py` plugin (`pytest_sessionstart`). All 4
tests in `test_security.py` pass, zero source changes. Confirmed
working in combination with the resource-reuse mechanism above and
F02's scenario plugin together (63 tests across 5 real files — plain
logic, DB-backed, reactor/crochet, and scenario-based — all pass,
including under `-n 2 --dist=load`).

**Decision:** No new third-party dependency (`pytest-twisted` is not
currently used); reuse the exact mechanism `run_region()` already
performs and already trusts. Small duplication between
`maastesting/noseplug.py`'s `Crochet` plugin and the new pytest plugin
is accepted (see `design.md` TD-003) to keep `noseplug.py` at zero diff
— both copies are deleted together when F07 retires nose.

**Source:** Design-phase spike (recorded in `design.md` §3/§13 TD-003),
confirmed against a real file. User approved (Q: reactor_setup).

**Impacts:** `requirements.md` D-005, FR-007, Risks; `design.md` §3,
§13 TD-003.

## F03 scope confirmation — metadataserver and nose's non-maasserver path untouched

**Decision:** F03 edits `run_region()` to drop only its
`--select-dir=src/maasserver` line (and matching `cover-package`
entry); `--select-dir=src/metadataserver` is untouched.
`run_region_legacy()` is untouched entirely (confirmed inert: zero
`legacy = True` test files exist in either tree today — F06's concern,
not F03's).

**Reason:** Consistent with `requirements.md`'s Constraint
(`src/metadataserver` must be unaffected) and D-002 (cutover, not
dual-run, scoped to `maasserver` only).

**Source:** `requirements.md` Constraints, confirmed via design-phase
code reading of `src/maastesting/scripts.py`.

**Impacts:** `design.md` §3 TD-001, §9 Edge Cases (explicit
metadataserver-stability verification task).

## Web API scenario-runtime gap required a source fix (new, implementation-time)

**Context:** While verifying outcome parity ahead of T6, a real
regression was found in `src/maasserver/api/tests/test_zone.py` (not
covered by any design-phase spike): 15 of 16 tests failed under
`bin/pytest`, all 16 pass under nose. This is distinct from and
additional to FR-006/FR-007's design-phase findings above.

**Root cause:** `maasserver/testing/api.py`'s `APITestCaseBase`
computed its `scenarios` attribute per-instance, inside `__init__` —
invisible to F02's `ScenarioUnitTestCase` plugin
(`maastesting/pytest/scenarios.py`), which detects scenario classes by
checking `scenarios` at the **class** level during collection. Classes
using this pattern fell through to stock pytest `UnitTestCase`
collection instead, which has no protection against the
bound-method/scenario-clone collision F02's plugin exists to avoid
(`TestCaseFunction.runtest()` binds the test method onto the original
instance; `testscenarios.apply_scenario`'s clone carries that binding
over, so the clone's `setUp()` runs on one instance while the actual
test body executes against the original — `self.client`/`self.user`
never populated on the instance the test method sees). Traced and
confirmed empirically (instance ids compared across `_getinstance()`,
`setUp()`, and the failing test body), not inferred.

**Scope:** All 67 `src/maasserver/api/tests/*.py` files — every
`APITestCase`/`APITransactionTestCase` subclass created via
`APITestType.forUsers()` (`.ForUser`, `.ForAdmin`,
`.ForAnonymousAndUser`, etc.).

**Fix, verified:** Moved the scenario computation from
`APITestCaseBase.__init__` to `APITestType.__new__` (the existing
metaclass), so `scenarios` is set once at class-definition time instead
of per-instance. Confirmed `type(name, (cls,), ns)` (used internally by
`forUsers()`) still invokes the custom metaclass correctly, so
dynamically-created `forUsers()` subclasses are covered. Subclasses
that set their own `scenarios` directly in their class body (e.g.
`test_events.py`'s `TestEventsURIsWithoutEvents`, adding a
query-parameter dimension) are still correctly merged via the existing
`merge_scenarios()` helper, now applied in `__new__` against the
namespace's own `scenarios` rather than the instance's.

**Decision:** This is a source change to `maasserver/testing/api.py`,
which `design.md` §4 originally listed as unaffected. Approved by user
as the resolution path (over broadening F02's plugin detection or
adding an `APITestCaseBase`-specific special case to the plugin — both
considered and rejected to keep F02's plugin generic and avoid an
instantiate-every-class collection-time probe).

**Verification:**
- `test_zone.py`: 16/16 pass (was 15 failed, 1 passed), matches nose's
  `Ran 16 tests ... OK` exactly.
- Collected nodeids now scenario-suffixed
  (`...[user=user,client=oauth]`), confirming F02's
  `ScenarioUnitTestCase` now correctly activates for these classes.
- `test_events.py::TestEventsURIsWithoutEvents` (own-`scenarios` +
  user/client merge case): 512 passed — multiplication still correct.
- `git status --short` confirmed only `maasserver/testing/api.py`
  touched for this fix.

**Impacts:** `design.md` §4 (Component Structure — `maasserver/testing/`
is no longer fully unchanged; `api.py` specifically is edited),
`tasks.md` T6 (parity run now includes this fix as a prerequisite for
the 67 API test files to pass).

## xdist collection-order nondeterminism in `test_storage_layouts.py` required a source fix (new, implementation-time)

**Context:** T6's full-suite `bin/pytest -n auto --dist=load src/maasserver`
run aborted entirely (`11 errors`, 0 tests ran) with `pytest-xdist`'s
"Different tests were collected between gw0 and gwN" error, for
`src/maasserver/tests/test_storage_layouts.py`.

**Root cause:** `TestGetAppliedStorageLayoutForNode.scenarios` and
`TestBlankStorageLayout.scenarios` both derive from `REGULAR_LAYOUTS`,
a list comprehension over `maasserver/storage_layouts.py`'s
`STORAGE_LAYOUTS` — a `frozenset` of class objects. Class-object
hashing is `id()`-based, differing by OS process memory layout;
`pytest-xdist` requires identical collection order across all worker
processes (each a separate OS process), so each worker computed a
different scenario order. Never surfaced under nose (single-process,
no cross-worker order requirement) — specific to `pytest-xdist`, which
F03 is the first to apply to `maasserver`. Confirmed no other file in
`src/maasserver` has this pattern (checked all `frozenset`/
`STORAGE_LAYOUTS`/`REGULAR_LAYOUTS` references).

**Fix, verified:** `REGULAR_LAYOUTS` now built via `sorted(..., key=lambda
layout_class: layout_class.name)` instead of an unordered frozenset
iteration — scoped entirely to the test file, zero production-code
change. Confirmed `test_storage_layouts.py`: 144/144 pass (unchanged
from before the fix). Confirmed order is now identical across
different `PYTHONHASHSEED` values (simulating different worker
processes) by importing `REGULAR_LAYOUTS` under `PYTHONHASHSEED=1/2/3`
directly — all three produced the identical ordered list.

**Decision:** User approved sorting in the test file (over changing
`storage_layouts.py`'s `STORAGE_LAYOUTS` from `frozenset` to a tuple in
production source, the alternative considered).

**Impacts:** `design.md` §4 (component structure — a second test file,
beyond `maasserver/testing/api.py`, required an implementation-time
edit), `tasks.md` T6 (prerequisite fix for the full-suite xdist run to
collect at all).

## Recorded verification evidence (design-phase spikes)

- **Spike 1 (resource-rebuild, unmitigated):**
  `src/maasserver/models/tests/test_template.py`, 4 tests — 4 pristine
  builds, 4 database-copy builds, `4 passed, 8 warnings in 4.28s`.
- **Spike 2 (nose baseline, same file):** `bin/test.region
  src/maasserver/models/tests/test_template.py` — `Ran 4 tests in
  0.659s — OK` (after a one-time pristine build inside the 4.092s wall
  time).
- **Spike 3 (precise per-build timing):** pristine rebuild times
  `[0.337, 0.271, 0.286, 0.283]`s (avg 0.294s); per-test DB copy times
  `[0.095, 0.089, 0.092, 0.098]`s (avg 0.093s).
- **Spike 4 (resource-reuse mechanism, held open):** 3 files
  (`test_template.py`, `test_mdns.py`, `test_neighbour.py`), 6 tests —
  1 pristine build, 1 databases build, `6 passed, 7 warnings in 0.85s`.
- **Spike 5 (mixed-flavor hold-open, both manager types pinned):**
  added `test_security.py` (3 `MAASTransactionServerTestCase` tests +
  1 `MAASTestCase` test) — still 1 pristine build;
  `MAASTransactionServerTestCase`'s manager correctly cycles
  make/clean per test (matches nose's own behavior for this
  `assume_dirty=True` class); 3 pre-existing failures (see below),
  unrelated to the resource mechanism.
- **Spike 6/7 (pre-existing-failure confirmation):** same 3 failures in
  `test_security.py` reproduced with no hold-open plugin at all
  (baseline plain pytest) — confirmed not caused by the resource
  mechanism. Nose baseline (`bin/test.region
  src/maasserver/tests/test_security.py`): `Ran 4 tests in 1.114s — OK`,
  all 4 pass.
- **Spike 8 (root cause identification):** isolated failure to
  `AttributeError: 'EPollReactor' object has no attribute
  'threadpoolForDatabase'` in `test_generates_new_secret_when_unset`.
- **Spike 9 (thread-pool fix, partial):** installing
  `install_default_pool`/`install_database_unpool` alone removed the
  `AttributeError` but left a stuck, unresolved `Deferred` (reactor not
  actually running).
- **Spike 10 (full reactor/crochet fix):** adding
  `init_asyncio_reactor()` + `crochet.setup()` (with `EventualResult`
  patching) — all 4 tests in `test_security.py` pass.
- **Spike 11 (combined, 5 files, single worker):** resource-reuse +
  reactor/crochet fix together, across `test_template.py`,
  `test_mdns.py`, `test_neighbour.py`, `test_security.py`, and F02's
  validated scenario file `test_config.py` — `63 passed, 11 warnings in
  3.70s`.
- **Spike 12 (combined, under xdist):** same 5 files, `-n 2
  --dist=load` — `63 passed, 25 warnings in 7.69s`; both workers
  exercised independently and correctly.

All spike artifacts (`/tmp/spike_plugin/*`, `.run_spike*` scratch
directories) were cleaned up after use; `git status --short` confirmed
clean (zero source changes) after each run.
