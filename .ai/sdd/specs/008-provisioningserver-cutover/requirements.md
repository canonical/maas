# Feature: Cut over `provisioningserver` to pytest (F05)

> Status: Approved
> Source: `.ai/sdd/PLAN.md` (F05), `.ai/sdd/ideas/003-coverage-gated-pytest-cutover.md`

## Overview

`provisioningserver` is the second package in the coverage-gated pytest
cutover (`PLAN.md`), following F04's successful `metadataserver` pilot
(23 files, pattern proven end-to-end). This feature relocates every
*migratable* `provisioningserver` legacy test file to
`src/tests/provisioningserver/` and drops those files from `nose`,
proving the migrated portion still meets its pre-cutover
branch-coverage baseline under pytest alone. `provisioningserver` is
129 files total, but **design-time investigation (D-002) found a
genuine fourth gap** beyond F03's three (scenarios / reactor-crochet /
`APITestCase`): 39 files rely on testtools' own per-test Twisted
reactor lifecycle (`run_tests_with = MAASTwistedRunTest.make_factory(...)`),
which is structurally incompatible, in a single pytest process, with
F03's always-on crochet reactor needed by `maasserver`/`metadataserver`.
Per direct user instruction and `PLAN.md`'s own risk table ("a fourth
gap triggers a stop-and-reassess, not an extension"), this feature
carves those 39 files out — a new, `provisioningserver`-specific
`nose`-under-pytest exception, parallel to idea 002's `legacy`-tagged
carve-out for `metadataserver`.

## Business Context

- **Problem:** `provisioningserver` currently requires `nose` to run at
  all; the 90 migratable files cannot be dropped from the `nose`
  invocation (`bin/test.rack`) until each collects and passes under
  pytest with equal or better coverage. The remaining 39
  `MAASTwistedRunTest` files cannot be dropped from `nose` *by this
  feature* — closing that gap is separate, follow-up work (see D-002,
  Out of Scope).
- **Users:** MAAS engineers who write/run `provisioningserver`
  (rack controller) tests daily; CI maintainers who want one test
  runner per package, incrementally.
- **Value:** Proves the coverage-gated method at real scale (90
  migratable files, ~4x F04's pilot) before committing to
  `maasserver`'s much larger 338-file cutover (F06/F07), while
  surfacing — rather than papering over — a genuine architectural
  limit of the current pytest shim before it reaches `maasserver`
  (which has 0 `MAASTwistedRunTest` usage today, but the discovery
  still de-risks F06/F07's own design-time triage).
- **Success signal:** The 90 migratable `provisioningserver` files no
  longer run under `nose`; their pytest-only branch coverage
  contribution is demonstrated (not assumed) against the committed
  baseline, with the 39-file carve-out's own coverage contribution
  explicitly still attributed to `nose` (not silently dropped from the
  gate).

## Evidence Base

Verified directly against the live tree (2026-11-18, post-F04), with a
design-time correction (D-002) superseding the first, requirements-time
pass (D-001):

| Fact | Value |
|------|-------|
| Legacy `provisioningserver` test files (outside `src/tests/`) | 129 |
| Total test definitions in those files | 2,733 |
| **Carve-out: files using `run_tests_with = MAASTwistedRunTest.make_factory(...)`** (D-002 — testtools' own per-test reactor lifecycle, incompatible with F03's always-on crochet reactor in one process) | 39 |
| Gap-touching (scenarios only) and migratable via F03's existing shim (D-003) | 18 |
| Gap-free (no scenarios, no reactor dependency) and migratable directly (D-003) | 72 |
| **Total migratable this feature** | 90 (72 + 18) |
| `APITestCase`/Django/`legacy = True` usage | 0 files — this gap and the `legacy`-tagged-under-nose carve-out (idea 002) do not apply to this package |
| Current coverage baseline | 94.91% branch coverage (`utilities/coverage-baselines/provisioningserver.json`), 1.0pp tolerance — captures **all 129** files (pre-cutover, combined); this feature's own `check` run will necessarily show a FAIL/partial-coverage signal for the 39 carved-out files' contribution, same documented-exception pattern as F04's TD-007 |
| FIPS/hardening-related test files (per `PLAN.md`'s non-deletable risk) | 11 total; of these, 3 fall in the carve-out (`drivers/power/tests/test_virsh.py`, `rackdservices/tests/test_external.py`, `utils/tests/test_network.py`) and remain under `nose`, 8 are migratable this feature (7 gap-free: `tests/test_hardening_command.py`, `dns/tests/test_config.py`, `drivers/power/tests/test_utils.py`, `drivers/power/tests/test_ssh_utils.py`, `drivers/power/tests/test_fips.py`, `rackdservices/tests/test_http_hardening.py`, `rackdservices/tests/test_http_binding.py`; 1 scenario-gap: `drivers/power/tests/test_ipmi.py`) |
| Pre-existing, unrelated pytest-native files already under `src/tests/provisioningserver/` | 5: `prometheus/test_utils.py`, `test_certificates_fips.py`, `drivers/osystem/test_ol.py`, `utils/test_env.py`, `utils/test_arch.py` |
| Legacy basename collisions with the 5 pre-existing files (different source subdirectories sharing a basename — exact path-collision status is a design-time question) | 1 basename (`test_utils.py` appears in `rpc/tests/` [carve-out], `drivers/power/tests/` [migratable, gap-free], `utils/tests/` [migratable, scenario-gap], and in the pre-existing `prometheus/` pytest-native file) — `drivers/power/tests/test_utils.py` and `utils/tests/test_utils.py` are both in scope for this feature's relocation, to distinct mirrored paths, neither colliding with the pre-existing file |

## User Stories

### US-001: Engineer runs the 90 migratable `provisioningserver` files via pytest alone

**As a** MAAS engineer working on `provisioningserver`
**I want to** run `pytest src/tests/provisioningserver` and get full
coverage of what `nose` used to test for the migratable 90 files
**So that** I no longer need `bin/test.rack` (or its `nose`-based
equivalent) for most of this package, with a clearly-documented
remainder

**Acceptance Criteria:**
- [ ] Every one of the 90 migratable legacy `provisioningserver` test
      files has been either relocated (unchanged or lightly adapted)
      into `src/tests/provisioningserver/`, or deleted with its
      covered behavior named as duplicated by a specific remaining
      test
- [ ] No migratable `provisioningserver` test file remains outside
      `src/tests/`
- [ ] `nose`'s invocation (`bin/test.rack`'s `--select-dir`, or
      equivalent) no longer collects any of the 90 migrated files, but
      still collects the 39 carved-out files (this feature narrows
      `nose`'s scope, it does not remove `nose` from this package
      entirely)

### US-002: Engineer trusts that coverage did not silently drop

**As a** MAAS engineer relying on the coverage gate
**I want to** see `provisioningserver`'s post-cutover combined
(pytest + the still-nose-only carve-out) coverage meet or exceed its
pre-cutover baseline
**So that** I know "fewer test files under pytest" did not mean "less
tested behavior", especially for scenario-multiplied tests that are
easy to quietly weaken

**Acceptance Criteria:**
- [ ] `utilities/coverage-baseline check provisioningserver` is run and
      its result is root-caused: any `FAIL` must be explained
      file-by-file (expected here, since `check` only measures
      pytest-only coverage while 39 files remain `nose`-only — same
      documented-exception pattern as F04's TD-007/D-004, not a
      regression)
- [ ] Any file whose scenario-dependent tests were deleted rather than
      ported names the specific remaining test(s) that cover the same
      behavior (not just "coverage number is green")

### US-003: Engineer triages the 18 scenario-gap files using F03's shim

**As a** MAAS engineer migrating a scenario-multiplied
`provisioningserver` file
**I want to** rely on F03's already-verified shim mechanism
**So that** these 16 files collect and pass under pytest without
bespoke per-file workarounds

**Acceptance Criteria:**
- [ ] All 18 scenario-gap files pass under `src/tests/`-rooted pytest
      with F03's shim active, matching their current `nose`-reported
      pass counts
- [ ] If F03's shim proves insufficient for any of these 16 files (a
      *fifth* gap, beyond the fourth this feature already carved out),
      the feature stops and reassesses rather than growing the shim ad
      hoc

### US-004: Engineer preserves FIPS/hardening test coverage

**As a** MAAS engineer responsible for FIPS 140-2/140-3 and STIG/CIS
hardening compliance
**I want to** every FIPS/hardening-related test file to keep running,
unchanged in behavior, after this feature — whether migrated or
carved-out
**So that** compliance coverage is never reduced as a side effect of
test-infrastructure migration

**Acceptance Criteria:**
- [ ] All 8 migratable FIPS/hardening-related files are relocated
      (never deleted-as-duplicate)
- [ ] All 3 carved-out FIPS/hardening-related files continue to run
      under `nose`, unchanged, and are explicitly listed as
      follow-up-required (not silently left out of any tracking)
- [ ] Each migrated file passes under pytest with the same
      assertions/behavior as under `nose` today

### US-005: Engineer understands the carve-out is tracked, not abandoned

**As a** MAAS engineer or CI maintainer
**I want to** see the 39 carved-out `MAASTwistedRunTest` files
explicitly named and their blocking reason documented
**So that** this is understood as a scoped, intentional deferral (like
idea 002's `legacy`-tagged carve-out), not a dropped requirement

**Acceptance Criteria:**
- [ ] The 39 carved-out files are listed (by path) in `design.md`
- [ ] A follow-up idea or feature is captured (or an existing one
      amended) naming the specific blocking mechanism (testtools'
      per-test `Spinner`-driven reactor vs. crochet's always-on
      reactor) so this is rediscovered, not re-investigated, later

## Functional Requirements

### FR-001: Relocate gap-free files — Must Have

WHEN a legacy `provisioningserver` test file touches none of F03's
   identified gaps and is not part of the `MAASTwistedRunTest`
   carve-out (D-002)
THE SYSTEM SHALL relocate that file into the mirrored path under
   `src/tests/provisioningserver/`, collecting and passing under
   pytest with no behavior change
SO THAT the 72 gap-free files move at the lowest possible cost,
   matching F03's and F04's own "gap-free files are unaffected"
   finding

### FR-002: Triage scenario-gap files — Must Have

WHEN a legacy `provisioningserver` test file touches F03's scenarios
   gap and is not part of the `MAASTwistedRunTest` carve-out (D-002)
THE SYSTEM SHALL either (a) relocate it under `src/tests/` relying on
   F03's shim to pass unmodified, or (b) delete it if its covered
   behavior is confirmed duplicated by an existing or newly-relocated
   test, naming that test explicitly
SO THAT the 18 scenario-gap files are resolved without silently
   losing scenario-dependent coverage

### FR-003: Never delete FIPS/hardening-related test coverage — Must Have

WHEN a legacy test file is identified as FIPS/hardening-related (per
   the Evidence Base's 11-file list, re-confirmed at design time)
THE SYSTEM SHALL relocate it if migratable (optionally via FR-002's
   shim path if also scenario-gap-touching), or leave it correctly
   under `nose` if it falls in the `MAASTwistedRunTest` carve-out
   (D-002) — never resolve any FIPS/hardening file via FR-002's
   delete-as-duplicate branch, migratable or not
SO THAT FIPS 140-2/140-3 and STIG/CIS hardening compliance coverage is
   never reduced by this migration, per `PLAN.md`'s own risk table and
   `AGENTS.md`'s FIPS/hardening compliance rule

### FR-004: Narrow `nose`'s `provisioningserver` scope to the carve-out only — Must Have

WHEN every migratable (90-file) `provisioningserver` legacy test file
   has been relocated or deleted per FR-001/FR-002/FR-003
THE SYSTEM SHALL narrow whatever `nose` invocation currently collects
   `provisioningserver` (`bin/test.rack`'s `--select-dir`,
   `utilities/run-py-tests-ci`, or equivalent) so it continues to
   collect only the 39 `MAASTwistedRunTest` carve-out files, not the
   90 migrated ones
SO THAT CI stops running the 90 migrated files twice (once under
   `nose`, once under `pytest`), while the 39 carve-out files keep
   running exactly as they do today

### FR-005: Verify coverage contribution — Must Have

WHEN FR-001-FR-004 are complete
THE SYSTEM SHALL run `provisioningserver`'s pytest-only suite with
   coverage and compare it against the committed baseline
   (`utilities/coverage-baselines/provisioningserver.json`) using the
   existing `utilities/coverage-baseline check` tool, root-causing and
   documenting any `FAIL` (expected, since the baseline includes the
   39 carve-out files' coverage contribution, which `check`'s
   pytest-only run cannot see) rather than silently waiving it
SO THAT the migrated portion's coverage is demonstrated, not assumed,
   and the carve-out's expected coverage-visibility gap is explicit
   rather than mistaken for a regression

### FR-006: Reconcile pre-existing pytest-native overlap files — Must Have

WHEN a legacy file's covered module already has a narrower,
   independently-authored pytest-native test file under
   `src/tests/provisioningserver/` (confirmed pre-existing and
   unrelated to this migration — see Evidence Base's 5-file list and
   basename-collision note)
THE SYSTEM SHALL treat the legacy file as still requiring its own
   relocation/triage decision (FR-001/FR-002, if migratable) rather
   than being considered already-migrated by the existing file's
   presence, and resolve any resulting path collision explicitly
   (merge, rename, or keep both at distinct paths) rather than
   silently overwriting either
SO THAT the existing narrow files (which predate and are unrelated to
   this cutover) do not cause broader legacy coverage to be silently
   dropped or clobbered as "already handled"

### FR-007: Track the carve-out for future closure — Must Have

WHEN this feature concludes with 39 `provisioningserver` files still
   under `nose`
THE SYSTEM SHALL record those 39 files (by path) and the specific
   blocking mechanism (testtools' `Spinner`-driven per-test reactor
   lifecycle, incompatible with F03's always-on crochet reactor) in a
   durable, discoverable location (`design.md` at minimum; a captured
   idea or amended `PLAN.md` feature recommended)
SO THAT this is understood as a tracked, scoped deferral — not a
   silently abandoned requirement, and not rediscovered from scratch
   when the remaining `provisioningserver` files or `nose` retirement
   (F08) are eventually tackled

## Non-Functional Requirements

### NFR-001: Reliability
- Every relocated/triaged file must pass deterministically under
  pytest, matching its deterministic `nose` outcome today (no new
  flakiness introduced by relocation).
- Given this package's reactor/Twisted usage among the migratable
  files, the full relocated suite must be re-run at least twice to
  confirm no reactor-state leakage between tests introduced by
  relocation (same discipline as F03's own T5 full-regression
  sign-off).
- The 39-file carve-out must continue passing under `nose`, unchanged
  and unmodified, confirming this feature's narrowing of `nose`'s
  `--select-dir`-equivalent scope did not accidentally exclude or
  break any carved-out file.

### NFR-002: Scope discipline
- This feature does not modernize test style (no `MAASTestCase` →
  plain-pytest-function rewrites, no `scenarios` → `parametrize`
  conversions) — that is F09's concern, per `PLAN.md`. Relocation is
  mechanical; only the 18 scenario-gap files get the minimum change
  needed to pass (relying on F03's shim), not a rewrite.
- This feature does not touch `metadataserver` (already cut over, F04)
  or `maasserver` (F06/F07).
- This feature does not design, prototype, or implement a fix for the
  `MAASTwistedRunTest`/per-test-reactor carve-out (D-002) — that is
  explicitly out of scope, tracked via FR-007 for separate, future
  work.
- A *fifth* gap (beyond F03's three plus this feature's own
  fourth/D-002) found during this feature's migratable-file work
  triggers a stop-and-reassess, per `PLAN.md`'s own risk table — not
  an ad hoc shim extension within this feature.

## Out of Scope

- Modernizing any relocated test to idiomatic pytest fixtures/parametrize
  (F09's concern).
- `metadataserver` (already done, F04) and `maasserver` (F06/F07)
  cutovers.
- Designing or implementing a fix for the 39-file `MAASTwistedRunTest`
  carve-out (D-002) — tracked via FR-007, not solved here. Candidate
  approaches (e.g., running `provisioningserver`'s carve-out as a
  separate pytest invocation/process from `maasserver`/`metadataserver`,
  mirroring `nose`'s own `bin/test.rack`/`bin/test.region` process
  split) are deferred to that follow-up work.
- Extending F03's shim to close any further (fifth+) gap discovered
  among the 90 migratable files — surfacing one stops this feature for
  reassessment instead.
- Resolving `PLAN.md`'s still-open `pytest-django` decision (not
  applicable here — this package has no Django coupling at all).

## Questions

None open at draft time. The one open structural question
(`test_utils.py` basename collision between the migratable
`utils/tests/test_utils.py` and the pre-existing
`src/tests/provisioningserver/prometheus/test_utils.py`) is evidence
for design-time triage, not a product-level ambiguity — FR-006 already
requires it be resolved explicitly rather than guessed.

## Decisions

### D-001 (superseded by D-002): Re-verify `PLAN.md`'s gap-tier estimate via direct recount

**Decision:** Recounted directly against the live tree rather than
reusing `PLAN.md`'s planning-time estimate (129 files/58 gap-touching/
71 gap-free). Initial recount: 57 gap-touching / 72 gap-free. **This
count was itself superseded by D-002's `MAASTwistedRunTest`-aware
recount (39 carve-out / 16 scenario-gap-migratable / 74 gap-free),
which was in turn corrected by D-003 to 39/18/72 (below). Kept here
for the historical record of the first pass.
**Reason:** `PLAN.md`'s own evidence base states its figures were
"verified 2026-11-16 against the live tree" but ahead of F04's
relocations; a fresh recount is cheap and prevents compounding a
stale estimate into FR-001/FR-002's acceptance criteria.
**Source:** Direct grep-based recount (see Evidence Base).
**Impacts:** Evidence Base, FR-001, FR-002 — further revised by D-002.

### D-002 (design-time correction): A fourth gap exists — carve out `MAASTwistedRunTest` files, do not attempt to shim them in this feature

**Decision:** During design-time investigation, found that 39 of the
57 originally-identified "reactor-gap" files actually use
`run_tests_with = MAASTwistedRunTest.make_factory(...)` — testtools'
own per-test Twisted reactor start/stop (`Spinner.run()`/`reactor.run()`
per test), not F03's crochet-managed always-on reactor pattern
(`MAASCrochetRunTest`). Confirmed empirically on a real, unmodified
file (`utils/tests/test_network.py`): running it under pytest with
F03's `maas-legacy` plugin active (auto-registered via `pytest11`
entry points) produces `twisted.internet.error.ReactorAlreadyRunning`
on 10/214 tests — not a bug in F03's shim, but a genuine architectural
conflict. `nose` never hits this because `bin/test.region`
(`--with-crochet`) and `bin/test.rack` (`--crochet-no-setup`) are
separate OS processes with different reactor-setup flags; merging
`provisioningserver`'s files into the same `src/tests/` tree as
`maasserver`/`metadataserver`, collected by one `pytest src/tests`
invocation, reintroduces the conflict nose's process split avoided.
Per direct user instruction, these 39 files are carved out of this
feature's scope entirely (remain under `nose`, tracked via FR-007) —
not re-attempted with a new shim within F05, and not blocking the
other 90 files' migration.
**Reason:** Matches `PLAN.md`'s own explicit risk mitigation ("A
fourth gap triggers a stop-and-reassess, not an extension") and
mirrors idea 002's already-accepted precedent (`metadataserver`'s
`legacy`-tagged `TestBinaryField` carve-out) of scoping a migration
down to what's actually ready, rather than blocking all 129 files on
solving the hardest 39 first.
**Source:** Direct user instruction, following design-time spike
evidence (see `design.md`'s Technical Decisions for the full
investigation).
**Impacts:** Overview, Business Context, Evidence Base, all User
Stories, FR-001 through FR-007 (FR-004 narrowed, FR-007 added), both
NFRs, Out of Scope. Supersedes D-001's 57/72 split with 39/16/74,
itself further corrected by D-003 to 39/18/72.

### D-003 (implementation-time correction): Scenario-gap count is 18, not 16 — two files missed by design-time's narrower candidate pool

**Decision:** T1 (tasks.md) re-ran the scenario-gap grep (`scenarios =
` ) against **all** 90 non-carve-out files directly, rather than only
against the subset design time had already flagged via a reactor/
crochet-keyword prefilter. Found 2 additional genuine
`testscenarios`-using files that design time's narrower candidate pool
never considered: `tests/test_config.py` and
`utils/tests/test_config.py` (both confirmed: real `scenarios = (...)`
class attributes, not false positives). Neither is FIPS/hardening-
related. Corrected partition: 39 carve-out / **18** scenario-gap / **72**
gap-free (was 39/16/74).
**Reason:** Design time's scenario-gap list (`design.md` §4) was
derived by filtering an earlier reactor/crochet-keyword-based
candidate pool, not by grepping the full 90-file non-carve-out set
directly for `scenarios = `. This is exactly the discrepancy T1 exists
to catch (`tasks.md` T1's own acceptance criterion: "re-run the
authoritative grep... do not reuse design.md's hand-copied list as
ground truth").
**Source:** Direct grep re-run at implementation time (T1), diffed
against `design.md`'s §4 list; both new files read directly to confirm
genuine `scenarios` usage (not keyword false positives).
**Impacts:** Evidence Base (72/18 replacing 74/16 throughout),
US-003, FR-001, FR-002, NFR-002 — `design.md` §4's file lists and §13
TD-001 unaffected (carve-out mechanism itself does not change).

## Glossary

- **Gap-touching file (scenario-gap):** A legacy test file using
  `testscenarios` (`scenarios = [...]` class attribute) — the one of
  F03's three identified gaps that remains both relevant to
  `provisioningserver` and closed by F03's existing shim (the second,
  reactor/crochet, applies only to `MAASCrochetRunTest`-pattern files,
  of which `provisioningserver` has none outside the carve-out; the
  third, `APITestCase`, is `maasserver`/Django-only).
- **Carve-out file:** A legacy test file using
  `run_tests_with = MAASTwistedRunTest.make_factory(...)` — testtools'
  own per-test Twisted reactor lifecycle, a fourth gap (D-002) not
  closed by F03's shim and out of scope for this feature.
- **Coverage baseline:** `utilities/coverage-baselines/provisioningserver.json`,
  captured by F01, covering all 129 files pre-cutover.
