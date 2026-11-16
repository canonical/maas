# Design: Cut over `maasserver` to pytest (F06)

> Requirements: @requirements.md
> Status: Draft

## 1. Summary

Relocate the 332 clean `maasserver` legacy test files (plus the
gap-free classes in 4 mixed legacy files) from
`src/maasserver/**/tests/` to their mirrored paths under
`src/tests/maasserver/`, unchanged except where relocation forces a
dotted-path update. Unlike F05 there is **no reactor carve-out**
(`maasserver` has zero `MAASTwistedRunTest` usage), and unlike both
F04 and F05 the partition is **measured, not grep-derived**: F03's
`maastesting/pytest/legacy.py` shim already covers scenarios and
crochet generically, and `testresources` usage is zero.

The only content that stays under `nose` is:

- The **9 legacy classes** across 4 mixed files
  (`MAAS_PREVENT_MIGRATIONS` gap-3, idea 002 — confirmed live, all 60
  full-suite setup-errors), and
- The **2 legacy-only files** (`test_cleansave.py`, `test_managers.py`)
  that contain no gap-free classes to split.

`nose`'s `run_region()` discovers tests by whole-directory walk
(`--select-dir=src/maasserver`), so physically moving the migratable
content out of that tree narrows `nose` with **zero change to
`maastesting/scripts.py`** — the same mechanism F05 used (TD-001).

## 2. Requirements Mapping

| Requirement | Design Coverage |
|-------------|-----------------|
| (from requirements.md Goals) | §3 relocation, §4 partition |
| Coverage non-regression | §15 Verification (baseline gate) |
| Legacy carve-out preserved | §4, §12 Migration/Rollout |
| No production/style changes | §1, Out of Scope |

(Requirements.md carries its goals narratively rather than as numbered
FRs; this design maps to those goals directly.)

## 3. Technical Approach

Three-step move, no new plugin/shim code (F03's `legacy.py` shim is
reused as-is, plus three small infra fixes made during design — §9):

1. **Relocate 332 clean files** to mirrored paths under
   `src/tests/maasserver/`, verbatim (`git mv`). These already pass
   under pytest today (measured, requirements Evidence Base; the 4
   originally-failing files were fixed during design, §9).
2. **Split the 4 mixed legacy files** at class granularity: move each
   file's gap-free classes into a new file under
   `src/tests/maasserver/`, leaving the 9 legacy classes behind in the
   original file under `nose`. Mirrors F04's
   `metadataserver/tests/test_fields.py` precedent exactly (its
   `TestBinaryField` stayed, `TestBin` moved).
3. **Leave the 2 legacy-only files and the 9 legacy classes in place.**
   `run_region()`'s `--select-dir=src/maasserver` keeps finding them;
   `nose` simply finds the rest gone.

`maasserver.tests` is a registered Django app
(`djangosettings/development.py:32`) whose `models.py` backs test-only
models; the package **stays in place**, including `tests/models.py` and
`tests/apps.py`. Only `test_*.py` content relocates.

## 4. Partition (measured, not grep-derived)

338 files total:

| Bucket | Count | Disposition |
|--------|-------|-------------|
| Clean, relocate | 332 | `git mv` to `src/tests/maasserver/` |
| Mixed legacy, split | 4 | gap-free classes move; 9 legacy classes stay |
| Legacy-only | 2 | whole file stays under nose |

The 4 files originally failing independently (`test_plugin.py`,
`test_subnet.py`, `test_auth.py`, `test_views.py`) were all resolved by
shim/infra fixes during design (§9), moving them into the clean bucket
— no triage remainder. Pass/fail source: full-suite `-n 4 --dist=load`
run (requirements Evidence Base), 11,984 passed / 57 failed / 60
setup-errors pre-fix, fully reconciled.

## 5. Component / Module Structure

```text
src/maasserver/**/tests/test_*.py        # 338 files today
  -> 332 clean files:            git mv to src/tests/maasserver/**/
                                 (includes the 4 design-fixed triage files)
  -> 4 mixed files:              gap-free classes -> src/tests/maasserver/**/;
                                 legacy classes stay
  -> 2 legacy-only files:        UNCHANGED, stay under nose
src/maasserver/tests/{apps,models}.py    # UNCHANGED (registered Django app)
```

## 9. Edge Cases

- **Class-level split imports.** The 4 mixed files' gap-free classes
  may import shared module-level helpers. When split, each side keeps
  the imports it uses; duplicated helpers are copied, not shared via a
  new module (avoid creating a second convention).
- **Triage — all 4 resolved, zero test-content changes:** each failure
  was a shim/infra gap, not a test defect, fixed in shared machinery:
  was a shim/infra gap, not a test defect, fixed in shared machinery:
  - `test_plugin.py` (11): `'Settings' object has no attribute
    'USE_JSON_LOGGING'` — `maasserver.djangosettings.settings` reads
    `regiond.conf` at import time inside a try/except that skips
    config-derived values when `RegionConfiguration` falls back to an
    unreadable `/etc/maas`. The plugin's `django.py` imported settings
    at module scope before any fixture set `MAAS_ROOT`. Fixed by setting
    a throwaway `MAAS_ROOT` at `django.py` module top, pre-import.
    19/19 pass.
  - `test_subnet.py` (10): `psycopg2 syntax error at or near "t"` —
    Fixed by calling `make_logging_level_names_consistent()` directly in
    the session-scoped `_crochet_reactor` fixture — not the full
    `logger.configure()`, whose Twisted log observer kills xdist workers
    at startup under `-n 4`. 30/30 pass.
  All four move to the clean bucket; the triage set is now empty.
  Regression-checked: 803 tests across these files plus
  `src/tests/maasserver` pass.
- **xdist ceiling:** run verification at `-n 4` (or lower), never
  `-n auto` — the DB fixture fails to bring up nodes when oversubscribed.
  Note the separate transient failure mode: a full-suite run started
  immediately after a `coverage-baseline capture` (which rebuilds the
  shared `maas_test_master` template) can die at worker startup with 0
  tests run; this is DB-template contention, not a per-fix regression,
  and clears once the capture's cluster settles.

## 12. Migration / Rollout

- **Coverage gate first:** `utilities/coverage-baseline capture
  maasserver` must write a v2 (production-only) baseline **before** any
  file moves. `check maasserver` runs after relocation; a carve-out-
  depressed FAIL is expected and read against the 9-class carve-out
  size (design §15 of spec 004, TD-004 caveat).
- **Rollback:** the relocation is pure `git mv`; `git revert` restores.
- **Carve-out closure** (the 9 legacy classes) is idea 002's separate
  follow-up, out of scope here.

## 13. Technical Decisions

- **TD-001: Measured partition over grep.** F05 T1 proved grep-based
  partitions drift; `maasserver`'s was wrong by 36 files (PLAN) and my
  own grep was wrong by 49 (scenario inheritance). The partition here
  comes from a full-suite collection + run, not text matching.
- **TD-002: Class-granularity split over file-granularity.** 4 of the 6
  legacy files mix legacy and gap-free classes; moving whole files
  would either strand passing classes under nose or force legacy
  classes into a suite they can't survive. F04's `test_fields.py`
  precedent splits at class level. **Mechanism proven 2026-11-19:**
  `maasserver/utils/tests/test_signals.py` split into
  `src/tests/maasserver/utils/tests/test_signals.py` (gap-free
  `TestSignalsManager`, 8/8 pytest) + the legacy half
  (`TestConnectToFieldChange`, 12/12 nose) — pytest collects only the
  gap-free class, nose only the legacy one, no double-run, no orphaned
  class. Shared helpers go with the side that uses them; unused imports
  removed per side.

## 15. Verification Strategy

- Baseline: `capture maasserver` (v2) committed pre-relocation —
  **captured: 91.85% over 43,904 production statements** (13,618
  branches; two stability runs agreed within 0.05pp). Committed as
  `utilities/coverage-baselines/maasserver.json` with `metric_version: 2`.
- Post-fix full-suite measurement (2026-11-19, `-n 2 --dist=load`,
  41min): **12,012 passed / 28 failed / 60 setup-errors / 13 skipped**.
  All 88 non-passing nodes map to exactly 4 legacy classes
  (`TestBulkManager`, `TestConnectToFieldChange`, `TestMAASModelForm`,
  `TestTimestampedModel` — the legacy carve-out, with the 5
  `test_fields`/`test_cleansave` legacy classes within the 60
  setup-errors). The 4 originally-failing files contribute **zero**
  failures post-fix. No unexpected failures.
- Post-relocation: `pytest src/tests/maasserver -n 4` passes with the
  same per-file outcomes the measurement recorded.
- `bin/test.region` narrows automatically to the legacy-only content
  (no `scripts.py` edit), confirmed by its reported test count.
- Coverage: `check maasserver` result recorded and root-caused; a
  carve-out-depressed number is expected, not a regression.
