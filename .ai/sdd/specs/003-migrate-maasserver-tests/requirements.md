# Feature: Migrate maasserver tests

> Status: Approved
> Source: .ai/sdd/PLAN.md (F03), .ai/sdd/specs/002-scenario-resource-plugin (prerequisite, review:done)

## Overview

MAAS's `src/maasserver` test suite (338 `test_*.py` files) currently runs
under `nose` via `test.region`'s `run_region()` entry point, combined in
one invocation with `src/metadataserver`'s suite. F02 built and validated
a `maastesting.pytest` plugin that makes `testscenarios`/`testresources`
scenario- and resource-based test classes — which `maasserver`'s suite
uses extensively — work correctly under pytest, with zero source changes
required. F03 uses that plugin to move the entire `maasserver` suite off
nose and onto `pytest-xdist`, cutting it over from `test.region`'s nose
invocation, while `src/metadataserver` continues running under nose
until F04.

## Business Context

- **Problem:** `maasserver`'s suite is the single largest nose-run test
  population (338 files) blocking full nose retirement (F07). It cannot
  move until a working scenario/resource pytest plugin exists — which F02
  now provides and validated against one representative real file.
- **Users:** MAAS engineers who write and run `maasserver` tests daily;
  CI maintainers who own the CI test gate.
- **Value:** Removes `maasserver` entirely from the legacy nose path,
  the largest single step toward F07 (full nose retirement); proves the
  F02 plugin at full-suite scale, not just a single representative file.
- **Success signal:** `bin/pytest` collects and passes 100% of
  `maasserver`'s test suite with the same pass/fail outcomes nose
  produces today, nose no longer runs any `maasserver` test, and CI
  (`utilities/run-py-tests-ci`) is green with this cutover in place.

## Goals

- Every test in `src/maasserver`'s 338 `test_*.py` files collects and
  passes under `bin/pytest` with outcomes identical to today's nose
  baseline (same pass/fail/skip per test).
- `src/maasserver` is fully removed from nose's `test.region`
  (`run_region()`) invocation; nose no longer executes any `maasserver`
  test.
- `src/metadataserver`'s suite continues running under nose, unaffected,
  until F04.
- CI's two required test jobs (`bin/test.parallel` / nose, and
  `bin/pytest`) are both green with the cutover in place.
- The pre-/post-migration runtime of the `maasserver` suite is measured
  and recorded (nose baseline vs. pytest-xdist), per F02's deferred
  performance question — without blocking completion on a specific
  target.

## Non-Goals / Out of Scope

- Migrating `src/metadataserver` — that is F04.
- Migrating `src/provisioningserver` (`test.rack`) — that is F05.
- `test.region.legacy` — that is F06. (Note: as of this writing, no test
  file in `maasserver` or `metadataserver` actually carries the `legacy`
  tag; `DjangoTestCase`/`DjangoTransactionTestCase`, the classes that set
  it, have zero subclasses in either tree today. This is a finding for F06
  to confirm/resolve, not something F03 needs to act on.)
- Rewriting any test as idiomatic pytest `parametrize`/fixtures — rejected
  per `PLAN.md`'s MVP Boundary; existing `MAASTestCase`/scenario/resource
  test classes are migrated unchanged.
- Enforcing a performance ceiling on the migrated suite's runtime — see
  Decisions (D-002); measured and recorded only.
- Reconciling or deduplicating the small number of pre-existing
  `src/tests/maasserver/**` pytest-native files that happen to share a
  filename with a `src/maasserver/**/tests/` nose file (e.g.
  `test_node.py`) — confirmed these are distinct, non-overlapping test
  content at different paths, not duplicates; no action needed.
- Removing `nose`, `maastesting/noseplug.py`, or the nose dependency —
  that is F07.
- New test coverage or behavior changes to any migrated test — this is a
  runner migration only.

## User Stories

### US-001: Maasserver tests produce identical outcomes under pytest

**As a** MAAS engineer running the test suite
**I want to** have every existing `maasserver` test (unchanged) pass or
fail under pytest exactly as it does today under nose
**So that** I can trust the migration introduced no behavior change,
only a different test runner

**Acceptance Criteria:**
- [ ] `bin/pytest` collects the same number of tests from `src/maasserver`
  that nose collects today.
- [ ] Every test's pass/fail/skip outcome under pytest matches its
  outcome under today's nose baseline.
- [ ] No source changes are required to any `maasserver` test file to
  achieve this (consistent with F02's D-003 convention-based detection).

### US-002: Maasserver no longer runs under nose

**As a** CI maintainer
**I want to** have `maasserver` tests removed from nose's `test.region`
invocation once they pass under pytest
**So that** there is a single source of truth for `maasserver` test
results, not two runners covering the same tests indefinitely

**Acceptance Criteria:**
- [ ] `run_region()` (or its replacement) no longer selects
  `src/maasserver` for nose execution.
- [ ] `src/metadataserver` continues to run under nose, unchanged, after
  the cutover.
- [ ] CI's nose-based job (`bin/test.parallel`) no longer reports any
  `maasserver` test result.

### US-003: CI remains green through the cutover

**As a** CI maintainer
**I want to** the cutover to land as a single CI-gated change, not a
partially-working intermediate state
**So that** CI never reports a false-green or false-red signal for
`maasserver` tests during the migration

**Acceptance Criteria:**
- [ ] `utilities/run-py-tests-ci` (both `bin/test.parallel` and
  `bin/pytest` legs) passes with the cutover in place.
- [ ] No `maasserver` test is silently dropped (missing from both
  runners) or silently duplicated (passing in both simultaneously) in
  the final state.

### US-004: Runtime impact is visible, not hidden

**As a** CI maintainer planning future module migrations (F04-F06)
**I want to** know the actual before/after runtime of the `maasserver`
suite
**So that** I can plan CI timing expectations for the remaining modules
with real data instead of guessing

**Acceptance Criteria:**
- [ ] The nose baseline runtime for `maasserver`'s suite (current state)
  is recorded.
- [ ] The pytest-xdist runtime for the same suite (post-migration) is
  recorded.
- [ ] Both numbers are written to a durable location (e.g. `design.md`
  or `decisions.md`), consistent with F01/F02's precedent.

## Functional Requirements

### FR-001: Full-suite pytest collection and parity — Must Have

WHEN `bin/pytest` collects `src/maasserver`'s test suite
THE SYSTEM SHALL collect and execute every test currently collected and
executed by nose under `test.region` for `src/maasserver`, with
identical pass/fail/skip outcomes per test
SO THAT the migration introduces zero behavioral change

### FR-002: Nose no longer runs maasserver tests — Must Have

WHEN the migration is complete
THE SYSTEM SHALL no longer execute any `src/maasserver` test under nose
(`test.region`/`run_region()`), while continuing to execute
`src/metadataserver` tests under nose unchanged
SO THAT `maasserver` has a single, authoritative test runner going
forward

### FR-003: No required source changes — Must Have

WHEN an existing `maasserver` test file already relies on `MAASTestCase`,
`scenarios`, and/or `resources` (as provided by F02's plugin)
THE SYSTEM SHALL run it correctly under pytest without requiring any
source change to that file
SO THAT this remains a runner migration only, consistent with F02's D-003

### FR-004: CI gate passes with the cutover — Must Have

WHEN the cutover lands
THE SYSTEM SHALL keep both of CI's required test jobs
(`bin/test.parallel` and `bin/pytest`, per `utilities/run-py-tests-ci`)
passing
SO THAT CI accurately reflects a fully working migrated state, not a
broken or partial one

### FR-005: Runtime measurement recorded — Should Have

THE SYSTEM SHALL record the nose baseline runtime and the post-migration
pytest-xdist runtime for the `maasserver` suite in a durable artifact

### FR-006: Resource-reuse mechanism for DB-backed tests — Must Have

WHEN a test depends on `maasserver.testing.resources.DjangoDatabasesManager`
(directly or via `DjangoPristineDatabaseManager`), as used by
`MAASServerTestCase`/`MAASTransactionServerTestCase`
THE SYSTEM SHALL reuse the built resource across tests within a pytest
worker process instead of rebuilding it per test, equivalent in effect
to nose's `OptimisingTestSuite` suite-level resource holding
SO THAT the migrated suite's runtime does not carry an unbounded
per-test resource-rebuild tax (measured at ~0.4s/test, affecting
~7,374 test methods across 260 files) that nose does not pay today

### FR-007: Reactor/crochet/thread-pool setup for pytest — Must Have

WHEN a test exercises `deferToDatabase`-based or other reactor/crochet-
dependent code (as used by 68 of 338 maasserver files), under pytest
THE SYSTEM SHALL install the same Twisted thread-pools
(`install_default_pool`/`install_database_unpool`) and start the
reactor via `crochet.setup()` (with the same `EventualResult` timeout
patching), once per pytest worker process, that nose's `run_region()`
already performs
SO THAT reactor/crochet-dependent tests produce the same outcome under
pytest as under nose today (confirmed: without this, a real sample
file failed 3/4; with it, 4/4 passed, zero source changes)

## Non-Functional Requirements

### NFR-001: Reliability

- Repeated runs of the migrated `maasserver` suite under pytest must
  produce identical pass/fail/error/skip counts across runs (no added
  flakiness from the migration itself), consistent with F01's NFR-002
  and F02's NFR-001 standard.

### NFR-002: Performance

- The migrated suite's runtime under pytest-xdist must be measured and
  recorded against the nose baseline.
- Per-test resource-rebuild overhead for `DjangoDatabasesManager`-backed
  tests must not scale linearly with test count the way unmitigated
  plain-pytest collection does (confirmed: ~0.4s/test without FR-006's
  reuse mechanism, ~49 min of pure overhead extrapolated across the
  260 affected files). FR-006's worker-scoped reuse is the required
  mitigation. No further specific ceiling is enforced as a pass/fail
  gate for F03 (D-002/D-003 still apply beyond this floor).

## User Experience Notes

Not applicable — this is a test-infrastructure-only change with no
user-facing surface. The only "user experience" is the MAAS engineer's
`bin/pytest`/`bin/test.region` command-line workflow, which is unchanged
in shape (same commands exist; `maasserver` simply stops appearing in
nose's output and appears in pytest's instead).

## Constraints

- Must build directly on F02's `maastesting.pytest.scenarios` plugin —
  no changes to `testscenarios`/`testresources` or `MAASTestCase`'s
  existing `scenarios`/`resources` wiring. A new, additive
  `maastesting/pytest/resources.py`-style plugin for worker-scoped
  resource reuse (FR-006/D-004) is in scope for F03; it must not change
  `DjangoDatabasesManager`/`DjangoPristineDatabaseManager`'s own
  `make`/`clean`/`isDirty` semantics, only when they are invoked.
- Must preserve `testscenarios`/`testresources` test behavior unchanged
  per `PLAN.md`'s MVP Boundary — no rewriting to pytest-idiomatic
  parametrize/fixtures.
- `src/metadataserver` must be unaffected and continue passing under
  nose after the cutover (verifies the entry-point split didn't
  regress the sibling suite F04 will migrate next).
- FIPS 140-2/140-3 and STIG/CIS hardening compliance must not be
  affected (test-infra-only change; verify no coupling, consistent with
  `AGENTS.md`'s standing requirement).

> Do not include implementation details such as database schema, API design, framework choice, or component structure.

## Decisions

### D-001: Full-suite cutover, not a partial slice

**Decision:** F03's Must Have requirement covers the entire
`src/maasserver` suite (338 test files) in one CI-gated cutover; nose no
longer runs any `maasserver` test once F03 is complete.
**Reason:** Matches `PLAN.md`'s per-module CI gate literally and gives
the clearest possible "done" signal — no F03-internal sub-phase needed.
**Source:** Direct user instruction (Q: scope_size)
**Impacts:** Goals, FR-001, FR-002, US-001, US-002, Success Metrics

### D-002: Cutover, not dual-run; maasserver leaves nose's test.region immediately

**Decision:** Once `maasserver`'s suite passes under pytest, it is
removed from nose's `run_region()` (or its replacement) entirely —
`maasserver` does not run under both runners simultaneously as a safety
net. `src/metadataserver` stays on nose, unaffected, until F04.
**Reason:** Matches `PLAN.md`'s "CI-gated green before next module"
wording most directly; avoids indefinite duplicate test maintenance and
an ambiguous "done" state where the same tests run twice.
**Source:** Direct user instruction (Q: cutover)
**Impacts:** Goals, FR-002, US-002, US-003, Out of Scope

### D-003: Measure performance, do not gate on a ceiling

**Decision:** F03 records the before/after runtime of the `maasserver`
suite (nose baseline vs. pytest-xdist) but does not block completion on
a specific performance ceiling.
**Reason:** F02 already found pytest+xdist has no suite-level
resource-reuse (every test rebuilds resources), a structural
characteristic, not a bug. F03 is the first real module to produce real
data on this; picking a ceiling now, before any data exists, risks
blocking an otherwise-correct migration on an arbitrary number.
**Source:** Direct user instruction (Q: perf_ceiling)
**Impacts:** Goals, FR-005, NFR-002, US-004, Out of Scope

### D-004: Build a worker-scoped resource-reuse plugin; amends the F02-only Constraint

**Decision:** F03 adds a new, additive pytest plugin that holds
`DjangoDatabasesManager`/`DjangoPristineDatabaseManager` resources open
for the life of a pytest-xdist worker process (equivalent in effect to
nose's `OptimisingTestSuite` suite-level resource holding), rather than
letting every test's `setUp`/`tearDown` cycle the resource's use-count
to 0 and trigger a full rebuild. This amends the original Constraint,
which forbade any new resource-plugin work in F03.
**Reason:** Design-phase spike measured the actual per-test cost of
*not* having this mechanism: ~0.294s pristine-template rebuild (full
`dbupgrade`/migrations) + ~0.093s per-test DB copy ≈ ~0.4s/test tax,
confirmed via build-timing instrumentation against a real file
(`src/maasserver/models/tests/test_template.py`). 260 of 338 maasserver
files (~7,374 test methods) use `MAASServerTestCase`/
`MAASTransactionServerTestCase`, i.e. depend on this exact resource
chain — extrapolating, ~49 minutes of pure single-worker overhead, not
accounting for likely Postgres-side lock/IO contention when every
`pytest-xdist` worker independently repeats full `dbupgrade` cycles
against one shared cluster. This is a correctness-adjacent scale
problem (nose's reuse mechanism is *why* the suite is fast today, not
an optional optimization), not the kind of "might be slower" risk the
original Constraint and D-003 anticipated.
**Source:** Direct user instruction (Q: resource_reuse), following a
design-phase spike that found the gap
**Impacts:** Constraint, FR-006 (new), NFR-002, Risks, `design.md`
(new component)

### D-005: Same plugin also installs reactor/crochet/thread-pool setup

**Decision:** The new pytest plugin from D-004 also installs the
Twisted thread-pools (`install_default_pool`/`install_database_unpool`)
and calls `crochet.setup()` (with `EventualResult` timeout patching),
once per pytest worker process — the same setup `run_region()` already
performs for nose, applied identically under pytest.
**Reason:** Design-phase spike found a second, distinct correctness gap
(not performance): a real `deferToDatabase`-based file
(`test_security.py`) failed 3/4 tests under plain pytest
(`AttributeError: 'EPollReactor' object has no attribute
'threadpoolForDatabase'`, then a stuck `Deferred` once the thread-pool
was added but the reactor wasn't actually running) and passed 4/4 under
nose. Root cause: no existing `maastesting/pytest/*.py` plugin installs
the thread-pool or starts the reactor via `crochet.setup()` — `src/tests`
(pytest-native suite) has zero `deferToDatabase` usages today, so this
gap was never hit before F03. Verified fix (same mechanism as
`run_region()`, no new library): all 4 tests pass, zero source changes.
68 of 338 maasserver files use `deferToDatabase`.
**Source:** Direct user instruction (Q: reactor_setup), following a
design-phase spike that found the gap
**Impacts:** FR-007 (new), Risks, `design.md` (same new component as D-004)

## Questions

None open.

## Success Metrics

| Metric | Target / Signal | Notes |
|--------|-----------------|-------|
| Test collection parity | `bin/pytest` collects the same test count as nose does today for `src/maasserver` | Proves no tests silently dropped |
| Outcome parity | 100% identical pass/fail/skip outcomes, pytest vs. nose baseline | Core correctness guarantee (FR-001) |
| Source changes required | 0 changes to existing `maasserver` test files | Confirms F02's convention-based detection holds at full-suite scale (FR-003) |
| Nose exclusion | 0 `maasserver` tests reported by nose post-cutover | Confirms FR-002/D-002 |
| Metadataserver stability | `src/metadataserver` suite unaffected, still green under nose | Confirms the entry-point split didn't regress the sibling suite |
| CI gate | `utilities/run-py-tests-ci` (both legs) green with the cutover in place | FR-004 |
| Reliability | Identical counts across repeated validation runs | Mirrors F01/F02's NFR standard |
| Runtime recorded | Nose baseline and pytest-xdist runtime both recorded | FR-005, non-blocking |
| Resource-reuse mitigation in place | Worker-scoped resource reuse confirmed (measured per-test overhead reduced from the unmitigated ~0.4s/test baseline) | FR-006/D-004 |
| Reactor/crochet parity | `deferToDatabase`/reactor-dependent tests produce identical outcomes to nose baseline | FR-007/D-005 |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| 338 files is a large surface; an undiscovered nose-specific behavior (e.g. a test relying on `OptimisingTestSuite` ordering for correctness, not just speed) could produce a silent behavior change | Medium | FR-001's full outcome-parity check (not just "it passes") catches this; compare exact pass/fail/skip per test, not just aggregate counts |
| Splitting the combined `run_region()` nose entry point could accidentally affect `src/metadataserver`'s invocation too | Medium | Explicit `src/metadataserver` stability check in Success Metrics and US-002's acceptance criteria |
| Resource rebuild-per-test overhead with no suite-level reuse (nose's `OptimisingTestSuite` equivalent missing under plain pytest) — measured at ~0.4s/test (pristine rebuild + DB copy) across ~7,374 tests in 260 files, extrapolating to ~49 min of single-worker overhead, with likely Postgres-side contention when `xdist` workers each repeat full `dbupgrade` cycles concurrently | High | FR-006/D-004: worker-scoped resource-reuse plugin holds the resource open across tests within a worker, mirroring `OptimisingTestSuite`; see `design.md` for the mechanism |
| Reactor/crochet/thread-pool setup missing under pytest — confirmed real failure (3/4 in a sample `deferToDatabase`-based file, `AttributeError`/stuck `Deferred`), affecting 68 of 338 files | High | FR-007/D-005: new plugin installs the same thread-pools and `crochet.setup()` as `run_region()`, once per worker; verified fix (4/4 pass, zero source changes) |

## Glossary

- **Cutover:** Removing a test suite from its old runner (nose) at the
  same time it becomes fully supported by the new runner (pytest), as
  opposed to running both runners over the same tests indefinitely.
- **`run_region()`:** The nose entry point (`maastesting/scripts.py`)
  backing `bin/test.region`, currently selecting both `src/maasserver`
  and `src/metadataserver` for nose execution.
- **Outcome parity:** Each individual test produces the same
  pass/fail/skip result under both runners being compared, not just a
  matching aggregate count.
- See also F02's requirements.md Glossary for `scenarios`/`resources`/
  `OptimisingTestSuite`/xdist definitions, reused unchanged here.

## Open Questions

None.
