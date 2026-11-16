# Tasks: Cut over `maasserver` to pytest (F06)

> Requirements: @requirements.md
> Design: @design.md
> Status: Draft

## Requirement Coverage

| Requirement | Tasks | Notes |
|-------------|-------|-------|
| Relocate migratable files | T2, T3 | T2 relocates the 332 clean files; T3 splits the 3 remaining mixed legacy files |
| Preserve legacy carve-out | T3, T4 | 9 legacy classes + 2 legacy-only files stay under nose; T4 confirms no double-run |
| Coverage non-regression | T1, T5 | T1 captures the v2 baseline (done); T5 runs and root-causes the check |
| No production/style changes | all | moves only; helpers copied per side, unused imports dropped |

## Implementation Readiness Check

| Check | Status | Notes |
|-------|--------|-------|
| Must Have requirements have tasks | Pass | table above |
| Requirements are covered by design | Pass | every goal maps to a design section/TD |
| Critical Questions are answered | Pass | triage set is empty (design §9); partition measured |
| Tasks have dependencies, acceptance criteria, files, and verification | Pass | below |
| Verification commands are known | Pass | `pytest`, `bin/test.region`, `bin/test.region.legacy`, `utilities/coverage-baseline check`, `make lint` |

## Task Summary

| Task | Title | Priority | Estimate | Dependencies | Status |
|------|-------|----------|----------|---------------|--------|
| T1 | Capture the v2 production-only coverage baseline | P0 | 1.5h | none | done |
| T2 | Relocate the 332 clean files | P0 | 4h | T1 | done |
| T3 | Split the 3 remaining mixed legacy files at class level | P0 | 3h | T2 | done |
| T4 | Verify nose narrowing and no double-run | P0 | 1h | T2, T3 | done |
| T5 | Coverage-baseline check and root-cause | P0 | 1h | T4 | done |
| T6 | Full-suite confirmation and INDEX/PLAN updates | P1 | 1h | T5 | done |

## Task T1: Capture the v2 production-only coverage baseline

**Priority:** P0
**Estimate:** 1.5h
**Dependencies:** none
**Covers:** Coverage non-regression (gate)

### Work
- [x] Run `utilities/coverage-baseline capture maasserver` (~78min;
  needs no deadline — the 3600s cap killed the first attempt mid-pass-2)
- [x] Commit `utilities/coverage-baselines/maasserver.json`

### Acceptance Criteria
- [x] Baseline written with `metric_version: 2`: **91.85%** over
  43,904 production statements (13,618 branches)
- [x] Two stability runs agree within 1.0pp (actual: 0.05pp)

### Verification
- [x] `cat utilities/coverage-baselines/maasserver.json` — v2, 91.85%

## Task T2: Relocate the 332 clean files

**Priority:** P0
**Estimate:** 4h
**Dependencies:** T1
**Covers:** Relocate migratable files

### Work
- [x] `git mv` the 332 clean files to mirrored `src/tests/maasserver/`
  paths, verbatim. Hit a transient stale `.git/index.lock` mid-run
  (killed coverage job's commit); 300 moved, re-ran the remaining 32
  after confirming no git process held the lock.
- [x] Created 34 missing `__init__.py` files in the new leaf packages —
  their absence caused basename-collision collection errors
  (`test_tag.py`, `test_vlan.py`, etc. exist in multiple subdirs).
- [x] Rewrote 49 files importing relocated test modules via the old
  `maasserver.<...>tests.test_*` dotted path to `tests.maasserver.*`
  (all intra-`maasserver`, so importers and sources move together);
  ruff `--fix` restored isort order.
- [x] Fixed the one genuine relocation break: `test_annotations.py`
  computed its Tempita template path from its own `__file__`, which
  moved. Anchored on the production `maasserver.api` package location
  (template stays in `src/maasserver/api/`). Swept for other
  `__file__`-relative `../` references in moved files — none.

### Acceptance Criteria
- [x] All 332 files exist only under `src/tests/maasserver/` (`find
  src/maasserver -name 'test_*.py' | wc -l` = 6, the legacy files)
- [x] `pytest src/tests/maasserver -n 4`: 12,333 passed / 2 failed
  pre-annotation-fix; the 2 = the annotation path break (fixed, 25/25)
  + `test_interface.py::test_duplicate_physical_macs_not_allowed`, a
  pre-existing order-dependent concurrency test failing identically in
  isolation under **both** nose and pytest at **both** paths — not a
  relocation break
- [x] No file left behind that `nose` would collect unintentionally

### Verification
- [x] `find src/maasserver -name 'test_*.py' | wc -l` = 6
- [x] `pytest src/tests/maasserver --collect-only` — 9,522 tests, 0 errors
- [x] `make lint` — clean

## Task T3: Split the 3 remaining mixed legacy files at class level

**Priority:** P0
**Estimate:** 3h
**Dependencies:** T2
**Covers:** Relocate migratable files, Preserve legacy carve-out

### Work
- [x] Split the 3 remaining mixed legacy files, replicating the proven
  `test_signals.py` mechanism:
  - `forms/tests/test_helpers.py`: `TestHelpers` moved; `TestMAASModelForm`
    stays (with its nested `TestClass`/`TestForm` helpers)
  - `tests/test_fields.py`: 13 gap-free classes moved; `TestXMLField`,
    `TestLargeObjectField`, `TestCIDRField`, `TestIPv4CIDRField` stay
  - `models/tests/test_timestampedmodel.py`: `TestUtilities` moved;
    `TestTimestampedModel` stays (keeps its `make_time_in_the_recent_past`
    helper)
- [x] Per design §9: each new file keeps its copyright header, carries a
  split-notice docstring referencing idea 002, imports only what its
  classes use (no helper copying needed — none of the moved classes use
  one); legacy files trimmed of moved classes and now-unused
  imports/helpers

### Acceptance Criteria
- [x] Gap-free halves pass under pytest with their pre-split counts:
  `test_helpers` 10, `test_fields` 85, `test_timestampedmodel` 1
- [x] Legacy halves pass under `bin/test.region.legacy` with their
  pre-split counts: `test_helpers` 3, `test_fields` 26,
  `test_timestampedmodel` 12
- [x] No class collected by both runners (per-file `--collect-only` /
  legacy-run cross-check); no class lost between halves

### Verification
- [x] `pytest <new-path> -p no:randomly` — 10/85/1 pass respectively
- [x] `bin/test.region.legacy <dotted.path>` — 3/26/12 pass (run
  serially; concurrent legacy runs race on the shared `test_maas` DB)
- [x] `ruff check` + `ruff format --check` on all 6 files — clean

## Task T4: Verify nose narrowing and no double-run

**Priority:** P0
**Estimate:** 1h
**Dependencies:** T2, T3
**Covers:** Preserve legacy carve-out

### Work
- [x] Ran `bin/test.region` (non-legacy): **0 tests** collected under
  `src/maasserver` — automatic narrowing confirmed (design TD-001, no
  `scripts.py` edit). Non-legacy nose is now empty across both packages
  (F04 already moved metadataserver's non-legacy content).
- [x] Ran `bin/test.region.legacy`: **69 tests, OK** — the full
  carve-out (9 maasserver legacy classes + metadataserver's
  `TestBinaryField`), unaffected by the relocation.
- [x] Cross-checked no double-run: all 10 legacy classes are
  exclusively under nose, none in the pytest tree (one `TestIPv` grep
  hit was a regex truncation artifact of `TestIPv4CIDRField`, confirmed
  absent from `src/tests/`).

### Acceptance Criteria
- [x] `bin/test.region` collects 0 under `src/maasserver` (narrowed to
  nothing — non-legacy content fully moved)
- [x] `bin/test.region.legacy` passes with the carve-out's own count
  (69)

### Verification
- [x] `bin/test.region` — 0 tests under src/maasserver, OK
- [x] `bin/test.region.legacy` — 69 tests, OK

## Task T5: Coverage-baseline check and root-cause

**Priority:** P0
**Estimate:** 1h
**Dependencies:** T4
**Covers:** Coverage non-regression

### Work
- [x] Ran `utilities/coverage-baseline check maasserver`: **PASS** —
  baseline 91.85% → current 91.89%, **+0.04pp**, well within the 1.0pp
  tolerance. (Serial + coverage full-suite run, ~82min; needed no
  deadline — the 1800s cap killed the first attempt at 18%.)
- [x] Root-cause: unlike F05's false FAIL (v1 filter counted test files
  as measured source, so relocating them craters the number), the v2
  production-only filter means the relocated files' *own* lines were
  never in the denominator — so moving them doesn't move the number.
  The 9-class legacy carve-out stays under nose, but its production
  modules are exercised by other relocated tests, so coverage holds.
  PASS is the honest result here, not a carve-out-depressed FAIL.
- [x] Like-for-like cross-check (see below) — confirms the migrated
  files' coverage is genuinely attributed under both scopes.

### Acceptance Criteria
- [x] Result recorded: 91.85% → 91.89%, +0.04pp, PASS
- [x] Like-for-like comparison (below)

### Verification
- [x] `utilities/coverage-baseline check maasserver` — PASS, +0.04pp
- [x] Like-for-like `coverage json
  --include=src/maasserver/*,src/tests/maasserver/*` over the same
  43,904 production statements: **91.36% vs baseline 91.85% = −0.49pp**,
  within the 1.0pp tolerance — the migrated portion is independently
  confirmed non-regressed. The two measurements (check +0.04pp,
  like-for-like −0.49pp) bracket zero; both within tolerance.

## Task T6: Full-suite confirmation and INDEX/PLAN updates

**Priority:** P1
**Estimate:** 1h
**Dependencies:** T5
**Covers:** Coverage non-regression

### Work
- [x] Full-suite double-run (`pytest src/tests`, `-n 4 --dist=load`;
  `-n auto` oversubscribes the DB fixture per design §9) — both runs
  produce **identical** results: 7 failed / 22,445 passed / 192
  skipped, identical failing-file sets. Found and fixed two real
  defects en route:
  - The F03 shim emitted scenario subclasses in source-collection
    iteration order; for frozenset-backed sources
    (`storage_layouts.STORAGE_LAYOUTS`) that order is per-process
    (id/address), so xdist workers collected the same tests in
    different orders and its "Different tests were collected"
    consistency check killed the run. Fixed by sorting scenario
    expansion by name (`sorted(scenarios, key=lambda e: e[0])` — the
    key is needed because bare `sorted` compares the vars dicts on
    duplicate names and raises TypeError).
  - The 7 stable failures are all pre-existing or latent-isolation,
    none caused by the relocation: 2 etag + `test_runtest` (T5
    reference set), 2 `test_beaconing`, `test_interface`
    (order-dependent concurrency, fails under nose too), and
    `test_manager` (vault — a latent test-isolation weakness the
    reshaped suite's worker assignment now exposes deterministically;
    passes in isolation 10/10 and with service-layer neighbors,
    unchanged by any file F06 touched).
- [x] Updated `INDEX.md` (spec 009 → implementation:done) and `PLAN.md`
  F06/F07 rows
- [x] Confirmed F07 subsumed — recast as the residual 9-class legacy
  carve-out tracked by idea 002, not a per-file triage tier

### Acceptance Criteria
- [x] Two consecutive full-suite runs produce identical results
  (7/22445/192, identical failing-file sets)
- [x] INDEX and PLAN reflect F06 done and F07's residual scope

### Verification
- [x] `pytest src/tests -q -n 4` × 2 — identical
- [x] `make lint` — clean (each fix linted before commit)
