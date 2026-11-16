# Feature: Scenario/resource pytest plugin

> Status: Approved
> Source: .ai/sdd/PLAN.md (F02), .ai/sdd/ideas/001-nose-to-pytest-migration.md

## Overview

MAAS test suites rely heavily on two `nose`-only mechanisms that have no
stock pytest equivalent: `testscenarios` (a test class declares a
`scenarios` tuple; one test method becomes N parameterized test
instances) and `testresources` (a test class declares a `resources`
tuple naming shared, expensive-to-build fixtures — e.g. a Django/Postgres
database — reused and reset across tests instead of rebuilt per test).
Today these are wired into `nose` via `maastesting.noseplug`'s
`Scenarios` and `Resources` plugins. F01 proved the `pytest-xdist`
invocation pattern against suites that need neither mechanism. This
feature builds a `maastesting.pytest` plugin, following the existing
`maas-django`/`maas-sqlalchemy` entry-point pattern, so that any test
class pytest collects with a non-empty `scenarios` and/or `resources`
attribute behaves equivalently under pytest — with zero changes to the
~137 existing files that declare these attributes. This is the
prerequisite for F03–F06, which migrate real nose-run modules onto
pytest.

## Business Context

- **Problem:** Nose-only scenario/resource behavior blocks every
  subsequent module migration (F03–F06); without it, migrating any
  scenario- or resource-using test file off nose would require rewriting
  the test itself, which PLAN.md's MVP Boundary explicitly rejects.
- **Users:** MAAS engineers who author and migrate region/rack test
  suites; CI maintainers who need migrated suites to keep passing with
  the same test semantics.
- **Value:** Removes the single largest technical blocker to the nose →
  pytest migration, without asking engineers to rewrite ~137 existing
  test files.
- **Success signal:** A representative sample of real, currently
  nose-run scenario- and resource-using test files produces identical
  pass/fail/skip outcomes when run under pytest with this plugin as they
  do today under nose — with no source changes to those files.

## Goals

- Any pytest-collected test class with a non-empty `scenarios` tuple
  expands into one test instance per scenario, equivalent to nose's
  `Scenarios` plugin.
- Any pytest-collected test class with a non-empty `resources` tuple
  gets its declared resources set up and torn down correctly, equivalent
  to nose's `Resources` plugin and `testresources`' own lifecycle.
- Zero source changes required in existing test files that already
  declare `scenarios` and/or `resources` (convention-based detection).
- Document, as a design-phase finding, how `pytest-xdist` worker
  distribution interacts with `testresources`' resource-reuse behavior —
  without that finding gating this feature's pass/fail outcome.

## Non-Goals / Out of Scope

- Migrating any real nose-run module (`test.region`, `test.rack`,
  `test.region.legacy`) off nose — that is F03–F06.
- Rewriting any scenario- or resource-based test as idiomatic pytest
  `parametrize`/fixtures — explicitly rejected per `PLAN.md`'s MVP
  Boundary.
- Guaranteeing or enforcing that resource-sharing tests land on the same
  `pytest-xdist` worker (worker affinity) — see D-001.
- A bounded performance ceiling on resource setup/teardown overhead
  versus nose's `OptimisingTestSuite`-ordered execution — see D-001;
  deferred to F03 when a full real module migrates and a representative
  before/after comparison becomes possible.
- Removing `nose`, `maastesting/noseplug.py`, or the nose dependency —
  that is F07.
- Changing `testresources`' or `testscenarios`' own behavior or the
  resource manager classes in `maasserver/testing/resources.py`.

## User Stories

### US-001: Scenario expansion works under pytest

**As a** MAAS engineer migrating a test module in F03–F06
**I want to** have my existing scenario-based test classes (declaring a
`scenarios` tuple) run correctly under pytest, unchanged
**So that** I don't have to rewrite scenario-based tests to migrate a
module off nose

**Acceptance Criteria:**
- [ ] A test class with a `scenarios` tuple of N entries produces N
  distinct test results when collected and run by pytest (one per
  scenario), matching the count and per-scenario attribute values nose
  produces today for the same class.
- [ ] A sample of real, currently nose-run scenario-based test files
  (e.g. from `src/maasserver/dhcpd/tests/test_config.py` or similar)
  produces the same pass/fail outcome under pytest as it does today
  under `test.region`/`test.rack`, with no source changes to those
  files.

### US-002: Resource setup/teardown works under pytest

**As a** MAAS engineer migrating a test module in F03–F06
**I want to** have my existing resource-based test classes (declaring a
`resources` tuple, e.g. `DjangoDatabasesManager`) set up and tear down
their declared resources correctly under pytest, unchanged
**So that** expensive fixtures (like a test database) continue to work
without rewriting resource management per test

**Acceptance Criteria:**
- [ ] A test class with a `resources` tuple has each named resource
  available as an instance attribute during the test body, matching
  nose's current behavior.
- [ ] Resources are torn down (via `finishedWith`/`tearDownResources`)
  after the tests that use them have completed, with no leaked resource
  state observable across unrelated test runs.
- [ ] A sample of real, currently nose-run resource-based test files
  (e.g. using `maasserver/testing/resources.py` managers) produces the
  same pass/fail outcome under pytest as it does today, with no source
  changes to those files.

### US-003: No per-file migration cost for existing scenario/resource usage

**As a** MAAS engineer migrating a module in F03–F06
**I want to** have scenario/resource detection happen automatically
based on the class attributes that already exist
**So that** migrating a module doesn't require touching every test file
in it just to opt in to the plugin

**Acceptance Criteria:**
- [ ] No test file in the validation sample required a source change
  (no new marker, import, or opt-in decorator) to get correct
  scenario/resource behavior under pytest.

### US-004: xdist/locality interaction is documented, not silently ignored

**As a** CI maintainer evaluating whether to proceed with F03
**I want to** a clear, written account of how `pytest-xdist`'s worker
distribution affects resource-reuse behavior
**So that** F03's module migration can plan around any real performance
implication instead of discovering it later in CI

**Acceptance Criteria:**
- [ ] A finding is recorded (e.g. in `design.md`) describing whether and
  how resource-sharing tests get distributed across `pytest-xdist`
  workers, and what effect that has on resource rebuild frequency
  compared to nose's `OptimisingTestSuite` ordering.

## Functional Requirements

### FR-001: Scenario expansion — Must Have

WHEN pytest collects a test class whose `scenarios` attribute is a
non-empty sequence
THE SYSTEM SHALL expand that class into one test instance per scenario
entry, applying each scenario's named attribute overrides to the
corresponding instance
SO THAT scenario-based tests run equivalently to how nose's `Scenarios`
plugin runs them today

### FR-002: Resource lifecycle — Must Have

WHEN pytest collects and runs a test class whose `resources` attribute
is a non-empty sequence
THE SYSTEM SHALL set up each named resource before the test body runs
and make it available as the declared instance attribute, and tear down
resources no longer needed by any remaining test in the run
SO THAT resource-based tests run equivalently to how nose's `Resources`
plugin and `testresources` run them today

### FR-003: No required source changes — Must Have

WHEN an existing test file already declares `scenarios` and/or
`resources` class attributes (MAAS's existing convention, inherited via
`MAASTestCase`)
THE SYSTEM SHALL detect and handle them under pytest without requiring
any marker, import, or other source change to that file
SO THAT future module migrations (F03–F06) do not need to touch every
test file just to adopt the plugin

### FR-004: Validated against real usage — Must Have

THE SYSTEM SHALL be validated against a sample of real, currently
nose-run test files that use `scenarios` and/or `resources` (in
addition to synthetic fixtures covering edge cases), confirming
identical pass/fail/skip outcomes to the current nose-run results

### FR-005: Combined scenario + resource usage — Should Have

THE SYSTEM SHALL correctly handle a test class that declares both a
non-empty `scenarios` tuple and a non-empty `resources` tuple
simultaneously (each generated scenario instance gets correct resource
setup/teardown)

## Non-Functional Requirements

### NFR-001: Reliability

- Repeated runs of the same validation sample under pytest must produce
  identical pass/fail/error/skip counts across runs (no added flakiness
  from the plugin itself), consistent with F01's NFR-002 standard.

### NFR-002: Observability

- The `pytest-xdist`/resource-locality interaction finding (US-004) must
  be written down and discoverable from this feature's design artifact,
  not left as undocumented tribal knowledge.

## Out of Scope

- Real module migration (F03–F06).
- Rewriting scenario/resource tests as pytest-idiomatic
  parametrize/fixtures (D-001, rejected direction per `PLAN.md`).
- Worker affinity / guaranteed resource-locality scheduling under xdist
  (D-002).
- A bounded performance ceiling on resource reuse overhead (D-002;
  deferred to F03).
- Removing `nose` or any nose dependency (F07).

## Decisions

### D-001: Core guarantee is correctness, not scheduling performance

**Decision:** F02 must guarantee that scenario- and resource-based
tests produce identical pass/fail outcomes under pytest as under nose.
The interaction between `pytest-xdist` worker distribution and
`testresources`' resource-reuse optimization is investigated and
recorded as a design-phase finding (US-004/NFR-002), not enforced as a
hard performance or scheduling requirement.
**Reason:** No real module has migrated yet, so there is no
representative real-world baseline to measure a performance ceiling
against (unlike F01, which had the existing `src/tests/**` suite
available). Forcing a scheduling guarantee now risks over-constraining
the design before real usage data exists.
**Source:** Direct user instruction
**Impacts:** Goals, Out of Scope, US-004, NFR-002; FR list contains no
performance/locality requirement

### D-002: Validation uses both synthetic fixtures and a real-file sample

**Decision:** F02 is validated against both (a) synthetic
scenario/resource test fixtures written to exercise plugin edge cases
in isolation, and (b) a small sample of real, currently nose-run test
files (e.g. from `src/maasserver/dhcpd/tests/test_config.py` and
`maasserver/testing/resources.py` consumers), run under pytest without
modification.
**Reason:** No pytest-native scenario/resource suite exists yet to
validate against (unlike F01's `src/tests/**`); synthetic fixtures alone
would not prove the plugin against MAAS's actual, sometimes complex
resource manager usage (e.g. `DjangoDatabasesManager`,
`DatabaseClusterManager`).
**Source:** Direct user instruction
**Impacts:** FR-004, US-001, US-002

### D-003: Detection is automatic and convention-based

**Decision:** The plugin automatically detects any pytest-collected
test class with a non-empty `scenarios` and/or `resources` attribute —
MAAS's existing convention via `MAASTestCase` — with no required
opt-in marker, import, or other source change.
**Reason:** F03–F06 migrate real modules containing ~137 existing files
using these attributes; requiring per-file opt-in would add migration
cost this plugin is meant to remove.
**Source:** Direct user instruction
**Impacts:** FR-003, US-003, Goals

## Questions

None open.

## Success Metrics

| Metric | Target / Signal | Notes |
|--------|-----------------|-------|
| Synthetic fixture pass rate | 100% of synthetic scenario/resource fixtures produce expected test counts and outcomes under pytest | Covers isolated edge cases (empty scenarios, combined scenario+resource, etc.) |
| Real-sample outcome parity | Sampled real nose-run files produce identical pass/fail/skip outcomes under pytest vs. nose | Proves plugin against actual MAAS usage |
| Source changes required | 0 changes to existing test files in the validation sample | Confirms convention-based detection (D-003) |
| Reliability | Identical counts across repeated validation runs | Mirrors F01's NFR-002 standard |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| `pytest-xdist` worker distribution defeats `OptimisingTestSuite`-style resource-reuse locality, causing real module migrations (F03+) to be slower than expected | Medium | Document the finding now (US-004); defer any performance-ceiling requirement to F03 when a real module and baseline exist |
| Combined scenario + resource usage has no current production example to validate against directly | Low | Cover via a synthetic fixture (FR-005, D-002) |
| Auto-detection (D-003) collides with another existing `maastesting.pytest` plugin's collection hooks (e.g. `maas-django`) | Low | Verify during design against existing plugin hook implementations before finalizing the approach |

## Glossary

- **xdist:** `pytest-xdist`, a pytest plugin distributing test execution
  across multiple worker processes within one pytest session.
- **Scenario (testscenarios):** a named set of instance-attribute
  overrides declared in a test class's `scenarios` tuple; each entry
  produces one test instance per scenario at collection/run time.
- **Resource (testresources):** a shared, potentially expensive fixture
  (e.g. a database) declared in a test class's `resources` tuple and
  managed by a `TestResourceManager` subclass; reused across tests
  instead of rebuilt each time where safe.
- **OptimisingTestSuite:** `testresources`' test suite subclass that
  reorders tests to maximize resource reuse (reset instead of
  teardown+setup) between tests sharing a resource.
- **MAASTestCase:** `maastesting.testcase.MAASTestCase`, the common base
  class for MAAS tests; declares the default (empty) `scenarios` and
  `resources` tuples and calls `testresources.setUpResources` in `setUp`.
