# Feature: Minimal gap shims for pytest-native legacy test execution

> Status: Approved
> Source: .ai/sdd/PLAN.md (F03), .ai/sdd/ideas/003-coverage-gated-pytest-cutover.md

## Overview

Running the repo's evidence-gathering sample against stock pytest (no
MAAS plugins) showed that 147 of 496 legacy test files already pass
unmodified. The remaining 349 files fail for exactly three identified
reasons: `testscenarios`-style scenario multiplication is never applied,
Twisted's reactor/crochet is never started, and one shared test base
class (`maasserver/testing/api.py`'s `APITestCase`) computes its
scenarios in `__init__` rather than at class-definition time, which
aborts pytest collection for the whole file. This feature closes exactly
those three gaps with the smallest possible mechanism — a conftest-level
shim plus one one-file source fix — so that F04 (the `metadataserver`
pilot cutover) has a working foundation to relocate tests onto.

## Business Context

- **Problem:** Without these three gaps closed, moving any gap-touching
  legacy file into `src/tests/` produces collection-time errors or
  silent partial failures (a scenario-multiplied class running as a
  single un-multiplied instance), blocking every package cutover
  (F04-F07) that touches a gap-tier file.
- **Users:** MAAS engineers performing each package cutover; any
  engineer running the pytest suite locally against a relocated
  gap-tier file.
- **Value:** Converts the "hard tier" (349 of 496 files) from "needs
  bespoke plugin machinery" (the approach that failed twice in ideas
  001/002) to "runs under stock pytest once this small shim exists" —
  with no dependency on code scheduled for near-term removal
  (Django/Twisted) beyond the shim itself.
- **Success signal:** A representative sample of files from each of the
  three gap tiers (scenarios, reactor/crochet, `APITestCase`) passes
  under pytest with the shim in place, with the same pass/fail outcome
  as under `nose` today (not a new regression, not a new pass that
  nose itself didn't have).

## User Stories

### US-001: Engineer runs a scenario-multiplied legacy test under pytest

**As a** MAAS engineer relocating a legacy test file that uses a
`scenarios` class attribute
**I want to** have pytest apply those scenarios the same way `nose` +
`testscenarios` did
**So that** the test still exercises every scenario instance, not just
one un-multiplied instance or a collection-time failure

**Acceptance Criteria:**
- [ ] A test class with a non-empty `scenarios` attribute, run under
      pytest with the shim active, produces one test instance per
      scenario (matching `nose`'s reported test count for that class)
- [ ] A test class with an empty or absent `scenarios` attribute is
      unaffected (runs exactly as it does today, no behavior change)

### US-002: Engineer runs a reactor/crochet-dependent legacy test under pytest

**As a** MAAS engineer relocating a legacy test file that uses
`deferToDatabase`, `inlineCallbacks`, or other Twisted reactor-dependent
code
**I want to** have the reactor already running when such a test starts
**So that** the test doesn't fail with `AttributeError: 'Deferred'
object has no attribute 'wait'` or similar reactor-not-started errors

**Acceptance Criteria:**
- [ ] A file using `deferToDatabase`/`inlineCallbacks`, run under pytest
      with the shim active, passes with the same outcome it has under
      `nose` today
- [ ] The reactor is started once per pytest session (matching `nose`'s
      own `crochet.setup()` call site and lifecycle), not per test or
      per file

### US-003: Engineer runs an `APITestCase`-based legacy test under pytest

**As a** MAAS engineer relocating a legacy test file whose test classes
subclass `APITestCase`
**I want to** have the file collect successfully under pytest
**So that** a single abstract base class issue doesn't abort collection
of the entire file (61 files affected)

**Acceptance Criteria:**
- [ ] A file containing `APITestCase` subclasses collects successfully
      under pytest (no collection-time `TypeError`)
- [ ] Concrete `APITestCase` subclasses still receive their
      `userfactories`/`clientfactories`-derived scenarios correctly
      (same scenario multiplication as before the fix, verified via
      US-001's mechanism)

## Functional Requirements

### FR-001: Scenario application shim — Must Have

WHEN pytest collects a test class with a non-empty `scenarios` attribute
THE SYSTEM SHALL apply `testscenarios`' own scenario-multiplication
   mechanism to that class before pytest runs its tests
SO THAT scenario-multiplied legacy tests exercise every scenario
   instance under pytest, matching their behavior under `nose`

### FR-002: Reactor/crochet session startup shim — Must Have

WHEN a pytest session that will execute reactor-dependent tests starts
THE SYSTEM SHALL start Twisted's reactor via `crochet.setup()` once,
   before any test in the session runs
SO THAT `deferToDatabase`/`inlineCallbacks`-based legacy tests do not
   fail with a reactor-not-started error

### FR-003: `APITestCase` collection-time fix — Must Have

WHEN pytest collects a file containing `APITestCase` subclasses
THE SYSTEM SHALL compute the abstract base class's scenario-related
   attributes in a way that does not raise at collection time (the
   current `__init__`-based computation iterates `userfactories`/
   `clientfactories` when they are `None` on the abstract base)
SO THAT collection of the whole file does not abort, and concrete
   subclasses still receive their own correctly-computed scenarios

### FR-004: No behavior change for gap-free files — Must Have

THE SYSTEM SHALL NOT alter the pass/fail outcome of any legacy test file
   that does not use scenarios, reactor/crochet, or `APITestCase`
SO THAT the 147 already-passing files remain unaffected by this feature

## Non-Functional Requirements

### NFR-001: Reliability
- The shim must not introduce flakiness: a file that passes
  deterministically under `nose` today must pass deterministically
  under pytest with the shim, not pass intermittently.

### NFR-002: Scope discipline
- The shim closes exactly the three identified gaps (FR-001, FR-002,
  FR-003) and nothing else. Per `PLAN.md`'s Risks table: a fourth gap
  discovered during implementation triggers a stop-and-reassess
  decision with the user, not a silent scope extension.

## Out of Scope

- Any third-party pytest plugin that requires rewriting legacy test
  files to a new API (e.g. `pytest-cases`' decorator-based case
  system) — rejected during requirements clarification (D-002): the
  shim must apply to existing `scenarios = [...]`-style files
  unmodified, per D-003's "mechanical relocation first, modernize
  later" policy from the source idea.
- A port of `testresources`' `OptimisingTestSuite` (resource-reuse
  across tests) — `PLAN.md` F03 explicitly excludes this; pytest's own
  session/module-scoped fixtures are the modernization path (F09), not
  this feature's concern.
- `DjangoTestCase`/`DjangoTransactionTestCase` ("`legacy`-tagged")
  tests and their three independent, compounding incompatibilities —
  tracked separately in
  `.ai/sdd/ideas/002-legacy-tests-under-pytest.md`; out of scope here.
- Relocating any test file into `src/tests/` — that is each package
  cutover feature's own concern (F04-F07), not this feature's.
- Any change to `nose`'s own behavior or configuration — this feature
  only affects how pytest runs the same files; `nose` continues running
  them unchanged until each package's cutover drops it (F04-F07).

## Decisions

### D-001: Reactor shim is session-scoped, matching `nose`'s own lifecycle

**Decision:** The reactor-startup shim calls `crochet.setup()` once per
pytest session (fixture or `conftest.py`-level session scope), not per
test or per file.
**Reason:** Matches `crochet`'s own intended usage pattern (one reactor
per process) and `nose`'s existing behavior
(`maastesting/noseplug.py`'s `crochet.setup()` call site, confirmed to
run once per `nose` process) — reactor-dependent tests see the same
lifecycle under pytest as they do today.
**Source:** Direct user instruction (reactor_scope).
**Impacts:** FR-002, US-002.

### D-002: Scenario shim reuses `testscenarios`' own helper, not a third-party plugin

**Decision:** The scenario-application shim is a hand-rolled
`conftest.py`-level hook (e.g. `pytest_generate_tests`) that calls
`testscenarios`' own `generate_scenarios()` function against each
collected class's existing `scenarios` attribute. No third-party
pytest plugin (`pytest-cases`, `pytest-scenarios`) is adopted, and no
legacy test file is rewritten.
**Reason:** `pytest-cases` (confirmed via research: actively maintained,
124 releases, most recent 2026) does not read a `scenarios` class
attribute — it requires each test file rewritten to its own
decorator-based API (`@parametrize_with_cases`). Adopting it would mean
rewriting all ~89 scenario-using files as a precondition to closing this
gap, which conflicts with `PLAN.md`'s explicit scope rule for F03
("the shim closes the three identified gaps only... a fourth gap
triggers a stop-and-reassess, not an extension") and with D-003 from the
source idea (mechanical relocation first, opportunistic modernization
later, as its own feature — `PLAN.md` F09). `pytest-scenarios` (the
other candidate surfaced during research) is an unrelated MongoDB
testing library despite the similar name — not applicable at all.
`testscenarios` itself already ships the exact multiplication helper
needed, installed and working in this repo today, with zero file
rewrites required.
**Source:** Direct user instruction (scenarios_mechanism_v2, after
reconsidering an initially-selected `pytest-cases` direction that was
confirmed to conflict with `PLAN.md`'s approved scope rule).
**Impacts:** FR-001, US-001, Out of Scope.

### D-003: `APITestCase` fix stays in F03, per `PLAN.md`

**Decision:** The `maasserver/testing/api.py` one-file source fix is
part of this feature, not deferred to F04.
**Reason:** `PLAN.md`'s Must Have list names this fix explicitly as part
of F03's scope ("the smallest viable means" to close all three
identified gaps together); deferring it would leave F04 (the pilot
cutover) still blocked on it regardless, with no scope benefit from
splitting.
**Source:** Direct user instruction (api_fix_scope).
**Impacts:** FR-003, US-003.

## Questions

None open. All three scope-determining questions from this session were
resolved and recorded as D-001 through D-003.

## Glossary

- **Gap tier:** A legacy test file that fails under stock pytest for one
  of exactly three identified reasons (scenarios, reactor/crochet,
  `APITestCase`). 349 of 496 legacy files; 147 are gap-free and already
  pass unmodified.
- **Shim:** The conftest-level mechanism this feature builds to close
  the three gaps, deliberately scoped smaller than a full
  `nose`-semantics-replacement plugin (the approach that failed in ideas
  001/002).
- **`generate_scenarios()`:** `testscenarios`' own helper function that
  multiplies a test case/suite according to its `scenarios` attribute;
  reused directly by this feature's shim rather than reimplemented.
