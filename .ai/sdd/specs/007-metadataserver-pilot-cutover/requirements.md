# Feature: Cut over `metadataserver` to pytest (pilot)

> Status: Approved
> Source: `.ai/sdd/PLAN.md` (F04), `.ai/sdd/ideas/003-coverage-gated-pytest-cutover.md`

## Overview

`metadataserver` is the smallest of the three legacy-nose packages (23
files, 927 test definitions) and the designated pilot for the
coverage-gated cutover method established by F01-F03. This feature
relocates every `metadataserver` legacy test file to `src/tests/metadataserver/`,
drops the package from `nose`, and proves the whole package still meets
its pre-cutover branch-coverage baseline under pytest alone — validating
the end-to-end method (baseline, triage, relocate-or-delete, verify) on
the smallest, lowest-risk package before applying it to the much larger
`provisioningserver` (F05) and `maasserver` (F06/F07).

## Business Context

- **Problem:** `metadataserver` currently requires `nose` to run at all;
  it cannot be dropped from the `nose` invocation until every file
  collects and passes under pytest with equal or better coverage.
- **Users:** MAAS engineers who write/run `metadataserver` tests daily;
  CI maintainers who want one test runner per package, incrementally.
- **Value:** First real proof that the coverage-gated method (not
  "port every test unchanged") works end-to-end, at the cheapest
  possible scale (23 files) before committing the much larger
  `provisioningserver`/`maasserver` cutovers to the same method.
- **Success signal:** Zero `metadataserver` files run under `nose`
  afterward; the package's pytest-only branch coverage meets or exceeds
  the captured baseline (95.05%, 1.0pp tolerance, per
  `utilities/coverage-baselines/metadataserver.json`).

## Evidence Base

Verified directly against the live tree (superseding `PLAN.md`'s
planning-time estimate of "23 files, 9 gap-touching" with an exact
recount — see D-001):

| Fact | Value |
|------|-------|
| Legacy `metadataserver` test files (outside `src/tests/`) | 23 |
| Total test definitions in those files | 927 |
| Files touching ≥1 of F03's three identified gaps (scenarios / reactor-crochet / `APITestCase`) | 5: `test_api.py` (scenarios, `APITestCase`), `test_api_twisted.py` (reactor), `test_hooks.py` (scenarios), `test_fio.py` (scenarios), `test_generate_user_data.py` (scenarios) |
| Files touching no gap | 18 |
| Current coverage baseline | 95.05% branch coverage (`utilities/coverage-baselines/metadataserver.json`), 1.0pp tolerance |
| Pre-existing, unrelated pytest-native files already present under `src/tests/metadataserver/` | `builtin_scripts/test_hooks.py` (17 lines, narrow — tests only `parse_bootif_cmdline`), `builtin_scripts/release_scripts/test_maas_wipe.py` (tests a different module path, `metadataserver.builtin_scripts.release_scripts.maas_wipe`, not the legacy `snippets.maas_wipe`), `builtin_scripts/test_builtin_scripts.py` |

## User Stories

### US-001: Engineer runs the full `metadataserver` suite via pytest alone

**As a** MAAS engineer working on `metadataserver`
**I want to** run `pytest src/tests/metadataserver` and get full
coverage of what `nose` used to test
**So that** I no longer need `bin/test.region metadataserver` (or its
`nose`-based equivalent) for this package

**Acceptance Criteria:**
- [ ] Every one of the 23 legacy `metadataserver` test files has been
      either relocated (unchanged or lightly adapted) into
      `src/tests/metadataserver/`, or deleted with its covered behavior
      named as duplicated by a specific remaining test
- [ ] No `metadataserver` test file remains outside `src/tests/`
- [ ] `nose`'s invocation (`bin/test.region`/CI) no longer collects any
      `metadataserver` test

### US-002: Engineer trusts that coverage did not silently drop

**As a** MAAS engineer relying on the coverage gate
**I want to** see `metadataserver`'s post-cutover pytest-only branch
coverage meet or exceed its pre-cutover baseline
**So that** I know "fewer test files" did not mean "less tested
behavior", especially for scenario-multiplied and reactor-dependent
tests that are easy to quietly weaken

**Acceptance Criteria:**
- [ ] `utilities/coverage-baseline check metadataserver` (or equivalent)
      passes against the pytest-only run, within the recorded tolerance
- [ ] Any file whose scenario/reactor-dependent tests were deleted
      rather than ported names the specific remaining test(s) that
      cover the same behavior (not just "coverage number is green")

### US-003: Engineer triages the 5 gap-touching files using F03's shim

**As a** MAAS engineer migrating a scenario-multiplied, reactor-
dependent, or `APITestCase`-based `metadataserver` file
**I want to** rely on F03's already-verified shim mechanism
**So that** these 5 files collect and pass under pytest without
bespoke per-file workarounds

**Acceptance Criteria:**
- [ ] `test_api.py`, `test_api_twisted.py`, `test_hooks.py`,
      `test_fio.py`, `test_generate_user_data.py` each pass under
      `src/tests/`-rooted pytest with F03's shim active, matching their
      current `nose`-reported pass counts

## Functional Requirements

### FR-001: Relocate gap-free files — Must Have

WHEN a legacy `metadataserver` test file touches none of F03's three
   identified gaps
THE SYSTEM SHALL relocate that file into the mirrored path under
   `src/tests/metadataserver/`, collecting and passing under pytest
   with no behavior change
SO THAT the 18 gap-free files move at the lowest possible cost,
   matching F03's own "gap-free files are unaffected" finding

### FR-002: Triage gap-touching files — Must Have

WHEN a legacy `metadataserver` test file touches ≥1 of F03's three
   identified gaps
THE SYSTEM SHALL either (a) relocate it under `src/tests/` relying on
   F03's shim to pass unmodified, or (b) delete it if its covered
   behavior is confirmed duplicated by an existing or newly-relocated
   test, naming that test explicitly
SO THAT the 5 gap-touching files are resolved without silently losing
   scenario- or reactor-dependent coverage

### FR-003: Drop `metadataserver` from `nose` — Must Have

WHEN every `metadataserver` legacy test file has been relocated or
   deleted per FR-001/FR-002
THE SYSTEM SHALL remove `metadataserver` from whatever `nose`
   invocation currently collects it (`bin/test.region`'s module scope,
   `utilities/run-py-tests-ci`, or equivalent)
SO THAT CI no longer runs `metadataserver` tests twice (once under
   `nose`, once under `pytest`)

### FR-004: Verify coverage parity — Must Have

WHEN FR-001-FR-003 are complete
THE SYSTEM SHALL run `metadataserver`'s pytest-only suite with coverage
   and compare it against the committed baseline
   (`utilities/coverage-baselines/metadataserver.json`) using the
   existing `utilities/coverage-baseline check` tool and its recorded
   tolerance (1.0pp)
SO THAT the cutover is only considered complete once coverage parity
   is demonstrated, not assumed

**Exception (D-004, implementation-time):** `check` is expected to
   report `verdict: FAIL` for as long as TD-005's `TestBinaryField`
   split stands - `check` only measures pytest coverage, and that one
   class (kept under `nose` per idea 002's scope, not this feature's)
   is the sole exerciser of 3 production modules. This is accepted as
   F04's final, documented state, not a blocking defect; see D-004 for
   the full reasoning and `utilities/coverage-baseline`'s own structural
   limitation.

### FR-005: Reconcile pre-existing pytest-native overlap files — Must Have

WHEN a legacy file's covered module already has a narrower,
   independently-authored pytest-native test file under
   `src/tests/metadataserver/` (confirmed pre-existing and unrelated to
   this migration, per the Evidence Base)
THE SYSTEM SHALL treat the legacy file as still requiring its own
   relocation/triage decision (FR-001/FR-002) rather than being
   considered already-migrated by the existing file's presence
SO THAT the existing narrow files (which predate and are unrelated to
   this cutover) do not cause broader legacy coverage to be silently
   dropped as "already handled"

## Non-Functional Requirements

### NFR-001: Reliability
- Every relocated/triaged file must pass deterministically under
  pytest, matching its deterministic `nose` outcome today (no new
  flakiness introduced by relocation).

### NFR-002: Scope discipline
- This feature does not modernize test style (no `MAASTestCase` →
  plain-pytest-function rewrites, no `scenarios` → `parametrize`
  conversions) — that is F09's concern, per `PLAN.md`. Relocation is
  mechanical; only the 5 gap-touching files get the minimum change
  needed to pass (relying on F03's shim), not a rewrite.
- This feature does not touch `provisioningserver` or `maasserver`.

## Out of Scope

- Modernizing any relocated test to idiomatic pytest fixtures/parametrize
  (F09's concern).
- Adopting `pytest-django` (open `PLAN.md` decision; F04 may surface
  evidence for it but does not resolve it here unless it blocks a file).
- `provisioningserver` (F05) and `maasserver` (F06/F07) cutovers.
- Retiring `nose`/the legacy stack entirely (F08) — `nose` keeps running
  for the two remaining packages until they are also cut over.
- Any new feature or behavior change to `metadataserver` itself — this
  is test-infrastructure-only.

## Decisions

### D-001: Supersede `PLAN.md`'s gap-tier estimate with a direct recount

**Decision:** This feature's requirements use the directly re-verified
count (5 gap-touching, 18 gap-free) rather than `PLAN.md`'s
planning-time estimate (9 gap-touching, 14 gap-free).
**Reason:** `PLAN.md`'s evidence-base grep pattern is not precisely
documented; a fresh, direct grep against the live tree for exactly F03's
three identified gap signatures (`scenarios =`, `deferToDatabase`/
`inlineCallbacks`/`crochet`, `APITestCase`) found 5 files, confirmed by
also cross-checking the file-count (23) and test-def-count (927)
against `PLAN.md`'s own table, which match exactly — only the gap-tier
split differs. Per F01/F03's established pattern this session (TD-004,
D-004), direct re-verification supersedes a planning-time estimate.
**Source:** Direct user instruction (gap_count_reconciliation).
**Impacts:** Evidence Base, FR-001, FR-002, US-003.

### D-002: Pre-existing overlap files are unrelated, do not shortcut triage

**Decision:** `src/tests/metadataserver/builtin_scripts/test_hooks.py`
and `.../release_scripts/test_maas_wipe.py` (both pre-dating this
feature, confirmed via `git log`: last touched by an unrelated `chore:
migrate to ruff` commit) are treated as independent, narrower
pytest-native tests. Their existence does not mark the corresponding
legacy files as already migrated.
**Reason:** The narrow file only covers `parse_bootif_cmdline` out of
`test_hooks.py`'s full 155-test-def legacy counterpart; the `maas_wipe`
pair test different module paths entirely
(`metadataserver.builtin_scripts.release_scripts.maas_wipe` vs. the
legacy file's `snippets.maas_wipe`). Treating them as equivalent would
silently drop most of both files' actual coverage.
**Source:** Direct user instruction (partial_overlap_files).
**Impacts:** FR-005, Evidence Base.

### D-003: Keep `pytest-django` adoption deferred, not decided in F04

**Decision:** F04 does not adopt `pytest-django`; `PLAN.md`'s open
decision on it carries forward unchanged.
**Reason:** F03's hand-rolled shim (`maastesting/pytest/legacy.py`)
already proves `APITestCase` collects and passes without it; adopting
it now would add a new dependency and expand scope for Django code
scheduled for removal within ~1 year, contradicting NFR-002's
mechanical-relocation-only boundary.
**Source:** Direct user instruction (pytest_django).
**Impacts:** Out of Scope, NFR-002.

### D-004 (implementation-time): Accept FR-004's `check` as structurally
unable to reach full parity while `TestBinaryField` stays under `nose`

**Decision:** `utilities/coverage-baseline check metadataserver` is
expected to report `verdict: FAIL` (measured: 89.33% vs. the 95.05%
baseline, -5.72pp) for as long as design TD-005's split stands, and
this is accepted as this feature's final, documented state — not
treated as a blocking defect requiring further code change here.
**Reason:** `check` only runs `metadataserver`'s pytest-only suite
(`_run_suite(legacy=False)`); the committed 95.05% baseline was
captured by combining pytest *and* `nose` coverage (`capture`'s own
2-suite combination, `_capture_one_pass`). `TestBinaryField` -
intentionally kept under `nose`'s `run_region_legacy()` per TD-005,
since it is `legacy`-tagged and out of this feature's scope (idea 002)
- is the sole exerciser of 3 production modules
(`metadataserver/tests/models.py`, `metadataserver/tests/apps.py`,
`metadataserver/admin.py`) and most of `fields.py`'s `BinaryField`
logic (down to 53% alone). That code is still tested today, just not
by a suite `check` currently measures - a tooling blind spot, not a
real coverage loss. Fixing `check` itself (teaching it to also run
`bin/test.region.legacy` and combine, mirroring `capture`) is shared
tooling work affecting `maasserver`/`provisioningserver` too, and is
out of this feature's scope (NFR-002) - correctly belongs to idea 002
(legacy tests under pytest) or a dedicated coverage-tooling follow-up,
not a point fix inside F04.
**Source:** Direct user instruction (coverage_gap_resolution,
2026-11-18): "Document as known/accepted gap, don't block F04, proceed".
**Impacts:** FR-004 (acceptance criterion amended with this exception),
review.md (if written) must record this as the F04 handoff condition,
not a defect.

## Questions

None open. The one scope-determining question from this session
(Q-001, pytest-django adoption) was resolved and recorded as D-003.

## Glossary

- **Gap-touching file:** A legacy test file using ≥1 of F03's three
  identified pytest incompatibilities (scenarios, reactor/crochet,
  `APITestCase`).
- **Baseline:** The committed per-package branch-coverage figure in
  `utilities/coverage-baselines/metadataserver.json`, captured by F01.
