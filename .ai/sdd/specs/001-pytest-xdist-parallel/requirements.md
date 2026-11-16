# Feature: pytest-xdist parallel infra

> Status: Approved
> Source: .ai/sdd/PLAN.md (F01), .ai/sdd/ideas/001-nose-to-pytest-migration.md

## Overview

MAAS's test suite currently runs through two separate parallel paths in CI:
`bin/test.parallel` (nose-based, orchestrates `test.region`, `test.rack`,
`test.region.legacy` as subprocesses, merges subunit output into
`junit.xml`) and `bin/pytest -n auto` (already xdist-based, for suites that
are pytest-native today). This feature establishes and formalizes the
pytest-xdist invocation pattern — configurable concurrency and JUnit XML
reporting — that later phases (F03–F06) will plug migrated nose suites
into, without yet touching any nose-run suite.

## Business Context

CI maintainers need predictable, configurable parallel test execution with
no loss of reporting fidelity as suites migrate off nose module by module.
MAAS engineers need the eventual single test runner to be at least as fast
as today's dual-path setup. This feature is the foundation Phase 2 (F03–F06)
depends on; it must be proven against existing pytest-native suites before
any nose suite migrates.

## User Stories

### US-001: Configurable parallel worker count

**As a** CI maintainer
**I want to** control how many parallel workers run pytest-based tests
**So that** I can tune CI resource usage without code changes

**Acceptance Criteria:**
- [ ] A worker count can be set via an environment variable or command-line
      flag, without editing test code.
- [ ] When unset, the default worker count follows the existing CI
      convention (currently a fixed default of 4, overridable via
      `MAAS_MAX_TEST_PROCESSES`).

### US-002: Preserved JUnit XML reporting

**As a** CI maintainer
**I want to** get a JUnit XML report from the pytest-xdist run
**So that** existing CI reporting/dashboards keep working without changes

**Acceptance Criteria:**
- [ ] The pytest-xdist invocation produces a JUnit XML report file.
- [ ] The report's test identifiers and pass/fail/error states are usable by
      existing CI JUnit consumers without a separate translation step.

### US-003: No CI runtime regression

**As a** MAAS engineer
**I want to** the migrated test invocation to run at least as fast as today
**So that** CI feedback time doesn't get worse as suites move off nose

**Acceptance Criteria:**
- [ ] Full CI test runtime, once all suites are migrated (end state across
      F01–F06), is not more than ~10% slower than today's combined
      `test.parallel` + `bin/pytest -n auto` runtime.

## Functional Requirements

### FR-001: Configurable concurrency — Must Have

WHEN a CI maintainer or engineer runs the pytest-based test suite
IF a worker-count environment variable or flag is provided
THE SYSTEM SHALL use that worker count for parallel execution
SO THAT CI resource usage can be tuned without code changes

### FR-002: Default concurrency — Must Have

WHEN no worker-count override is provided
THE SYSTEM SHALL default to the existing CI convention (a fixed default of
4 workers)
SO THAT local and CI runs behave predictably out of the box

### FR-003: JUnit XML output — Must Have

WHEN the pytest-xdist test invocation completes
THE SYSTEM SHALL produce a JUnit XML report
SO THAT existing CI reporting/dashboards continue to function

### FR-004: Validated against pytest-native suites — Must Have

WHEN the pytest-xdist invocation pattern (FR-001–FR-003) is implemented
THE SYSTEM SHALL be validated against suites that already run natively
under pytest today (not nose-run suites)
SO THAT the pattern is proven before F03–F06 migrate nose suites onto it

## Non-Functional Requirements

### NFR-001: Performance

- End-to-end CI test runtime (after all of F01–F06 complete) must not
  regress by more than ~10% versus today's combined `test.parallel` +
  `bin/pytest -n auto` runtime.

### NFR-002: Reliability

- The new invocation pattern must not increase test flakiness or
  duplicate/missed test runs compared to today's `bin/pytest -n auto`
  baseline.

## Out of Scope

- Migrating `test.region`, `test.rack`, or `test.region.legacy` off nose
  (covered by F03–F06).
- Building the `testscenarios`/`testresources` pytest scenario/resource
  plugin (covered by F02).
- Removing the `nose` dependency or `maastesting/noseplug.py` (covered by
  F07).
- Preserving `test.parallel`'s subprocess-script orchestration model
  (spawning heterogeneous scripts and merging subunit streams) — pytest-
  xdist distributes test items within one pytest session and cannot
  replicate this model; it does not apply once suites are pytest-native.
- Explicit selector/narrowing requirement — pytest's native path/`-k`
  selection already covers this; no dedicated requirement needed.

## Decisions

### D-001: F01 scope boundary given no suite has migrated off nose yet

**Decision:** F01 is complete when the pytest-xdist invocation pattern
(configurable concurrency, JUnit XML output) is validated against suites
that already run natively under pytest in CI today. No nose-run suite is
touched in F01.
**Reason:** `pytest-xdist` distributes test items within a single pytest
collection session; it structurally cannot orchestrate `test.parallel`'s
current model of spawning `test.region`/`test.rack`/`test.region.legacy`
as separate nose subprocesses. F03–F06 plug migrated suites into this
proven pattern.
**Source:** Q-001 (resolved during PRD clarification)
**Impacts:** FR-004, Out of Scope, Overview, Business Context

### D-002: JUnit XML output must be preserved

**Decision:** The pytest-xdist invocation must produce a JUnit XML report
usable by existing CI consumers, equivalent in practice to today's
`junit.xml` / `junit-pytest.xml` outputs.
**Reason:** CI reporting/dashboards depend on this output; breaking it
would regress CI visibility during an infra-only migration.
**Source:** Direct user instruction
**Impacts:** US-002, FR-003

### D-003: Configurable concurrency must be preserved

**Decision:** Worker count must remain configurable (via
`MAAS_MAX_TEST_PROCESSES` / `--maxprocesses`), not fixed to `auto` only.
Default value is a fixed 4, matching the existing CI script
(`utilities/run-py-tests-ci`), not nose's historical cores-minus-2
convention.
**Reason:** CI maintainer needs to tune resource usage; the existing
pytest CI wrapper already defaults to 4 and is proven stable in
production CI — changing the default was judged riskier than documenting
the existing behavior.
**Source:** Direct user instruction (resolved during design clarification)
**Impacts:** US-001, FR-001, FR-002

### D-004: No dedicated selector-parity requirement

**Decision:** `test.parallel`'s positional `SELECTOR` arguments are not
replicated as an explicit requirement; pytest's native path/`-k` selection
is sufficient.
**Reason:** Native pytest selection already provides equivalent
capability without added requirement surface.
**Source:** Direct user instruction
**Impacts:** Out of Scope

## Questions

None open.

## Glossary

- **xdist:** `pytest-xdist`, a pytest plugin distributing test execution
  across multiple worker processes within one pytest session.
- **Pytest-native suite:** a test suite already collected and run directly
  by pytest today (as opposed to suites still run via the nose-based
  `test.region`/`test.rack`/`test.region.legacy` scripts).
