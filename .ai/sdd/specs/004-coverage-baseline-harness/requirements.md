# Feature: Coverage baseline harness

> Status: Approved
> Source: .ai/sdd/PLAN.md (F01), .ai/sdd/ideas/003-coverage-gated-pytest-cutover.md

## Overview

MAAS's merge gate runs no coverage today — `utilities/run-py-tests-ci`
(the actual PR gate) runs nose and pytest but neither measures coverage;
the only coverage job (`tics.yaml`) is a weekly/manual TiCS report, not a
gate. The coverage-gated pytest cutover plan (`PLAN.md` F04-F07) needs a
per-package branch-coverage baseline, captured before any test moves, so
that a package's post-cutover pytest-only coverage can be compared against
its pre-cutover nose baseline. This feature builds that baseline capture
and comparison, for `provisioningserver`, `metadataserver`, and
`maasserver` — nothing else depends on it, and every later cutover feature
depends on it.

## Business Context

- **Problem:** Without a baseline, "keep coverage the same" (the
  constraint that licenses deleting redundant legacy tests instead of
  porting all 12,921 of them) is unverifiable. The migration method
  collapses into guesswork without this feature.
- **Users:** MAAS engineers performing each package cutover (F04-F07);
  reviewers approving test deletions during cutover.
- **Value:** Converts "keep coverage the same" from a stated intent into
  a measurable, repeatable gate, reusable across all four cutover
  features without rebuilding it each time.
- **Success signal:** A committed baseline file exists per package
  (`provisioningserver`, `metadataserver`, `maasserver`); a comparison
  tool reports pass/fail against it; both were validated against the
  live coverage harness, not assumed to work.

## User Stories

### US-001: Engineer captures a trustworthy baseline before a cutover

**As a** MAAS engineer about to cut a package over to pytest
**I want to** capture that package's current branch coverage reliably
**So that** I have a number I can trust to compare against after the
cutover, not one polluted by run-to-run noise

**Acceptance Criteria:**
- [ ] Running the capture command 2-3 times on an unchanged tree produces
      coverage percentages that agree within the tolerance band (FR-004)
- [ ] The baseline is written to a committed, version-controlled file,
      not a local-only artifact
- [ ] The baseline is scoped per top-level package
      (`provisioningserver`, `metadataserver`, `maasserver`), not one
      repo-wide number

### US-002: Engineer checks whether a cutover held coverage

**As a** MAAS engineer who has moved a package's tests to pytest
**I want to** run one command that compares current coverage against the
committed baseline for that package
**So that** I know immediately whether the cutover is done or needs more
work, without hand-computing percentages

**Acceptance Criteria:**
- [ ] The tool reports, per package: baseline %, current %, delta, and
      pass/fail against the tolerance band
- [ ] The tool exits non-zero on failure, usable in a script or by a
      human running it manually
- [ ] The tool works against the pytest-only run, independent of whether
      nose still runs other packages

### US-003: Reviewer verifies a deleted test's coverage is truly duplicated

**As a** reviewer approving a package cutover that deletes legacy tests
**I want to** see, for each deleted test file, which surviving test
covers the same behavior
**So that** a coverage percentage holding steady cannot hide a silently
weakened scenario or edge case (the top risk named in `PLAN.md`)

**Acceptance Criteria:**
- [ ] The cutover's record (PR description, commit message, or a tracked
      file) names, per deleted legacy test file, the surviving test(s)
      that cover its behavior
- [ ] A cutover whose deletions have no such mapping is not considered
      coverage-gate-passing, regardless of the raw percentage

## Functional Requirements

### FR-001: Per-package baseline capture — Must Have

WHEN an engineer runs the baseline-capture command for a package
IF the package's legacy suite (nose) and `src/tests` suite both
   execute to completion
THE SYSTEM SHALL record that package's branch coverage percentage,
   statement count, and branch count to a committed file
SO THAT a later comparison has a trustworthy number to compare against

### FR-002: Per-package attribution — Must Have

WHEN coverage data is collected across the combined nose + pytest run
THE SYSTEM SHALL attribute coverage to the top-level package the
   covered source file belongs to (`src/provisioningserver/**`,
   `src/metadataserver/**`, `src/maasserver/**`)
SO THAT each cutover feature (F04-F07) can be gated on its own package's
   number, not a repo-wide average that could mask a regression in one
   package behind an improvement in another

### FR-003: Stability check before accepting a baseline — Must Have

WHEN a baseline is captured for the first time for a package
THE SYSTEM SHALL require the capture to be run at least twice on an
   unchanged tree
IF the two runs' branch coverage percentages differ by more than the
   tolerance band (FR-004)
THE SYSTEM SHALL refuse to accept the baseline and report the
   discrepancy
SO THAT flaky or nondeterministic tests cannot establish an unreliable
   baseline

### FR-004: Comparison tool with tolerance band — Must Have

WHEN an engineer runs the comparison command for a package after its
   cutover
THE SYSTEM SHALL compute current branch coverage for that package from a
   pytest-only run and compare it to the committed baseline
IF current coverage is at least (baseline − 1.0 percentage point)
THE SYSTEM SHALL report pass
ELSE
THE SYSTEM SHALL report fail with the exact delta
SO THAT "coverage held" has one unambiguous, reusable definition across
   all four cutover features

### FR-005: Deletion-mapping record requirement — Must Have

WHEN a package cutover deletes a legacy test file on the basis that its
   coverage is already duplicated
THE SYSTEM SHALL require a recorded mapping from the deleted file to the
   surviving test(s) that cover its behavior
SO THAT a reviewer can verify the deletion claim independently of the
   raw coverage percentage, per `PLAN.md`'s top risk

### FR-006: Baseline captured before first cutover — Must Have

THE SYSTEM SHALL produce committed baselines for `provisioningserver`,
   `metadataserver`, and `maasserver` before any of F04-F07 begins
   deleting or relocating tests
SO THAT every cutover feature has its gate ready at the moment it starts

## Non-Functional Requirements

### NFR-001: Reliability
- The stability check (FR-003) must catch at least the level of run-to-
  run noise observed in this repo's own suite today (acknowledged
  elsewhere in the SDD history as 2 pre-existing unrelated failures out
  of ~7,949 pytest tests); a baseline that passes the stability check
  should not itself be a source of false gate failures later.

### NFR-002: Usability
- The comparison tool's pass/fail output must be readable without
  consulting documentation: package name, baseline %, current %, delta,
  verdict.

## Out of Scope

- Wiring coverage into the permanent PR gate (`run-py-tests-ci`) — this
  is a migration-duration tool, used manually during F01-F07, not a
  permanent CI job (D-002).
- Capturing a baseline on CI hardware — local capture is sufficient
  (D-001).
- `src/tests`'s own existing coverage, `apiclient`, `maascli`,
  `maascommon`, `maasservicelayer`, `maasapiserver`,
  `maastemporalworker`, or `src/perftests` — none of these packages are
  in PLAN.md's cutover scope (F04-F07 only cover `provisioningserver`,
  `metadataserver`, `maasserver`).
- Enforcing the deletion-mapping record's format (PR template, commit
  trailer, tracked file) — left to each cutover feature's design.
- Line coverage — the project's existing `[tool.coverage]` config
  already runs with `run.branch = true`; this feature reuses branch
  coverage, it does not introduce a second metric.
- Fixing any coverage gap the baseline capture happens to surface in
  currently-untested code — out of scope for this feature; it measures,
  it does not improve, existing coverage.

## Decisions

### D-001: Baseline capture is local, not CI-dispatched

**Decision:** Capture the baseline with a local run of
`utilities/run-tests-coverage` (already verified to produce a real
coverage.py report), not a dedicated CI workflow.
**Reason:** Local capture was already demonstrated working end-to-end
(a single-file smoke run produced `TOTAL ... 8%` in 14s); a dedicated CI
run adds workflow maintenance for a migration-duration tool.
**Source:** Direct user instruction (capture_mode).
**Impacts:** FR-001, Out of Scope.

### D-002: Gate is a migration-duration manual tool, not a permanent CI check

**Decision:** The comparison tool is run manually by the engineer
performing each cutover (F04-F07); it is not wired into
`run-py-tests-ci` or any PR-triggered workflow.
**Reason:** This is a one-time-per-package migration gate, not a
permanent product feature; matches the plan's framing that Django/
Twisted (and therefore much of this test surface) has roughly a one-year
remaining life.
**Source:** Direct user instruction (gate_lifetime).
**Impacts:** FR-004, Out of Scope, NFR-002.

### D-003: Tolerance band is 1.0 percentage point

**Decision:** A package's post-cutover branch coverage must be at least
(baseline − 1.0pp) to pass.
**Reason:** Absorbs coverage.py measurement noise (confirmed to exist:
conditional imports, environment-dependent branches) without being loose
enough to hide a real regression.
**Source:** Direct user instruction (tolerance_value).
**Impacts:** FR-004.

### D-004: Deletions require a named reviewer-verifiable mapping

**Decision:** A legacy test file deleted as "coverage already
duplicated" must have a recorded mapping to the specific surviving
test(s) that cover its behavior; a coverage percentage alone never
licenses the deletion.
**Reason:** Directly mitigates `PLAN.md`'s top-listed risk: branch
coverage can hold while a scenario-multiplied test is replaced by a
weaker single-path equivalent, keeping lines green while testing less.
**Source:** Direct user instruction (deletion_signoff).
**Impacts:** FR-005, US-003.

### D-005: Baseline scoped per top-level package, not repo-wide

**Decision:** Coverage is attributed and gated per top-level package
(`provisioningserver`, `metadataserver`, `maasserver`), matching
`PLAN.md`'s per-package cutover features (F04-F07), not as one combined
repository percentage.
**Reason:** A repo-wide average could mask a real regression in one
package behind an improvement in another; each cutover feature needs its
own independently verifiable number.
**Source:** Direct user instruction, confirmed during requirements
gathering (per-package framing was accepted without objection across all
three question rounds).
**Impacts:** FR-002, US-001, US-002.

## Questions

None open. All scope-determining questions from this session were
resolved and recorded as D-001 through D-005.

## Glossary

- **Branch coverage:** The `coverage.py` metric already configured via
  `run.branch = true` in `pyproject.toml`; counts both statement
  execution and which branches of conditionals were taken.
- **Baseline:** The committed, pre-cutover branch coverage percentage for
  a given package, captured by this feature.
- **Cutover:** A `PLAN.md` Phase 1/2 feature (F04-F07) that relocates a
  package's tests to `src/tests/` and drops it from the nose runner.
- **Tolerance band:** The 1.0 percentage point allowance (D-003) by which
  post-cutover coverage may fall below baseline and still pass.
