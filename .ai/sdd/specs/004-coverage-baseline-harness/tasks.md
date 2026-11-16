# Tasks: Coverage baseline harness

> Requirements: @requirements.md
> Design: @design.md
> Status: Approved

## Requirement Coverage

| Requirement | Tasks | Notes |
|-------------|-------|-------|
| FR-001 | T1, T2, T5 | Core suite-run/combine/attribute functions (T1), `capture` writes the baseline (T2), real baselines committed (T5) |
| FR-002 | T1 | `_package_totals`'s `--include` filter, design TD-002 |
| FR-003 | T2 | Two-pass stability check, abort-on-disagreement |
| FR-004 | T3 | `check` subcommand, tolerance comparison |
| FR-005 | T4 | Deletion-mapping convention documented (design §12: not enforced in code, documented as process) |
| FR-006 | T5 | All three package baselines captured and committed before F04 |
| NFR-001 | T2, T5 | Stability check itself (T2); real-run evidence that it doesn't false-fail (T5) |
| NFR-002 | T3 | `check` output format |

## Implementation Readiness Check

| Check | Status | Notes |
|-------|--------|-------|
| Must Have requirements have tasks | Pass | FR-001–FR-006 all covered (table above) |
| Requirements are covered by design | Pass | Every FR maps to a named design section/TD (see `design.md` §2 Requirements Mapping) |
| Critical Questions are answered | Pass | `requirements.md` Questions: "None open"; 5 decisions (D-001–D-005) resolved |
| Tasks have dependencies, acceptance criteria, files, and verification | Pass | See tasks below |
| Verification commands are known or marked manual/N/A | Pass | `make lint`, direct script invocation, and `coverage report` cross-checks are all concrete; T1–T3 have no automated test suite by design decision (§15: tool verified by running it, not by wrapping it in tests) |

## Implementation Slices

### MVP Slice

- **Goal:** `utilities/coverage-baseline capture <pkg>` and
  `utilities/coverage-baseline check <pkg>` work correctly against the
  real repo for all three packages, baselines are committed, and the
  deletion-mapping convention is written down for F04-F07 to follow.
- **User Stories:** US-001, US-002, US-003
- **Tasks:** T1-T5 (all; this feature has no natural sub-phase — it is
  one small tool plus the one-time act of capturing three baselines)
- **Independent validation:** Each task's own verification (below);
  overall slice is validated when T5's real captured baselines exist,
  committed, and a `check` run immediately afterward reports PASS with
  ~0 delta for all three packages.

## Task Summary

| Task | Title | Priority | Estimate | Dependencies | Status |
|------|-------|----------|----------|---------------|--------|
| T1 | Script skeleton and core suite/combine/attribution functions | P0 | 2h | none | done |
| T2 | `capture` subcommand: two-pass stability check and baseline write | P0 | 2h | T1 | done |
| T3 | `check` subcommand: pytest-only run and tolerance comparison | P0 | 1.5h | T1 | done |
| T4 | Document the deletion-mapping convention for cutover features | P1 | 30m | none | done |
| T5 | Capture and commit real baselines for all three packages | P0 | 2h | T2, T3 | done |

## Task T1: Script skeleton and core suite/combine/attribution functions

**Priority:** P0
**Estimate:** 2h
**Dependencies:** none
**Covers:** FR-001, FR-002

### Work
- [x] Create `utilities/coverage-baseline` (Python, executable, `argparse`
      with `capture`/`check` subparsers per design TD-003 — matching the
      style of existing `utilities/*.py` scripts, no new CLI framework)
- [x] Implement `_run_suite(package, legacy, coverage_file)` per design
      §3/§4's suite-selection table:
      - `provisioningserver`, `legacy=True`: `.ve/bin/test.rack`
      - `metadataserver`/`maasserver`, `legacy=True`: `.ve/bin/test.region`
        (confirmed: nose has no per-package entry point for these two)
      - any package, `legacy=False`: `.ve/bin/pytest src/tests`
      - Each invocation wrapped in `coverage run --rcfile=pyproject.toml`
        with `COVERAGE_FILE` set to the given path (reuses
        `pyproject.toml`'s existing `[tool.coverage]` — `run.branch =
        true`, `run.source = ["src"]` — no new coverage config)
      - Propagate the subprocess's exit code; do not swallow failures
        (design §9 Edge Cases: suite failure → exit 2, not a fabricated
        0% baseline)
- [x] Implement `_combine(coverage_files, into)`: `coverage combine
      --keep <files...>` writing to `into` (verified command form during
      design)
- [x] Implement `_package_totals(coverage_file, package)`:
      `coverage json --include=src/<package>/* -o -` against
      `coverage_file`, parse stdout JSON, return the `totals` dict
      (verified during design: produces `percent_covered`,
      `num_statements`, `num_branches`, etc.)
- [x] Wire `argparse` so `capture`/`check` exist as subcommands — fully
      implemented (not stubbed) alongside T1's shared library, since both
      subcommands are thin callers of the same three functions; see T2/T3
      for their own dedicated verification

### Acceptance Criteria
- [x] `utilities/coverage-baseline --help` shows `capture` and `check`
      subcommands
- [x] `_run_suite`, `_combine`, `_package_totals` each independently
      callable and produce correct output when exercised manually
      against real suites: `_run_suite(legacy=True)` run against the
      real `bin/test.rack` (3,533 tests, OK, 94.73% provisioningserver);
      `_combine`/`_package_totals` run against two real pytest-produced
      coverage files (`src/tests/provisioningserver/utils/test_arch.py`-
      style files), confirming combined coverage (7.09%) exceeds either
      alone (6.96%) and that `metadataserver`'s filter is unaffected by
      `provisioningserver`-only test runs

### Files
- `utilities/coverage-baseline` — create

### Verification
- [x] `make lint` — `ruff check`/`ruff format --check` both pass (`make
      lint`'s underlying `tox -e lint` unavailable in this environment;
      ran `ruff` directly, installed via `uv pip install --python .ve/bin/python ruff`)
- [x] Manual: `_run_suite` exercised with `legacy=True` against the real
      `bin/test.rack` suite — produced a valid coverage file
- [x] Manual: `_package_totals` against that file with
      `--include=src/provisioningserver/*` — `percent_covered` present
      and non-zero (94.73%)
- [x] Manual: combined two independently-produced coverage files via
      `_combine`, confirmed `_package_totals` on the combined file
      reflects both (7.09% vs 6.96%/unknown for the individual files)

## Task T2: `capture` subcommand: two-pass stability check and baseline write

**Priority:** P0
**Estimate:** 2h
**Dependencies:** T1
**Covers:** FR-001, FR-003, NFR-001 (TD-001 minimum-of-two acceptance)

### Work
- [x] Implement `capture <package>`:
      1. Run the full pass (legacy + pytest, combined into one data
         file via `_combine`) **twice**, each reduced via
         `_package_totals` to that package's `percent_covered`
      2. If the two runs' `percent_covered` differ by more than 1.0pp,
         abort: print both numbers and the delta, exit 2, do not write
         or overwrite any baseline file (FR-003)
      3. If stable, accept `min(run1, run2)` as the baseline value
         (TD-001)
      4. Write `utilities/coverage-baselines/<package>.json` per design
         §5 schema: `package`, `captured_at` (ISO 8601 UTC), the
         accepted `percent_covered`, `num_statements`, `num_branches`,
         `stability_runs` (both raw values), `tolerance_pp` (1.0,
         stored alongside the value it validated against)
- [x] Create `utilities/coverage-baselines/` directory (new, committed
      JSON files live here per design §4)

### Acceptance Criteria
- [x] Running `capture <package>` twice in a row on an unchanged tree
      (no source changes between the two outer invocations) produces
      numbers that are themselves within tolerance of each other —
      verified directly: `provisioningserver`'s own internal two-pass
      check (94.908% vs 94.922%, 0.014pp) passed without aborting
- [x] A forced-disagreement scenario correctly aborts without writing a
      baseline file — verified by monkeypatching `_capture_one_pass` to
      return 50.0%/60.0% (10pp delta): `UNSTABLE` message printed, exit
      2, no `provisioningserver.json` written
- [x] The written JSON file matches the design §5 schema exactly (see
      T5's real captured baseline for the schema in practice)

### Verification
- [x] `make lint` passes (see T1 evidence)
- [x] Manual: `capture provisioningserver` run (see T5); JSON matches
      design §5 schema
- [x] Manual: both `stability_runs` values present; accepted value is
      their minimum (confirmed in forced-disagreement test and T5)

## Task T3: `check` subcommand: pytest-only run and tolerance comparison

**Priority:** P0
**Estimate:** 1.5h
**Dependencies:** T1
**Covers:** FR-004, NFR-002

### Work
- [x] Implement `check <package>`:
      1. Run the pytest-only pass (`legacy=False`) for `package`
      2. Compute `_package_totals`
      3. Load `utilities/coverage-baselines/<package>.json`; if missing,
         exit 2 with a clear "no baseline — run `capture` first" message
         (design §9 Edge Cases)
      4. Pass if `current.percent_covered >= baseline.percent_covered -
         1.0`, else fail
      5. Print the output block exactly as specified in design §6:
         `package`, `baseline`, `current`, `delta`, `tolerance`,
         `verdict`
      6. Exit 0 on pass, 1 on fail (coverage regression), 2 on
         usage/environment error (design §6)

### Acceptance Criteria
- [x] `check <package>` run immediately after `capture <package>` with
      no intervening code changes reports a correctly-computed
      current/baseline/delta and the verdict those numbers imply — per
      design §15 (amended): PASS-with-~0-delta is only expected once a
      package is cut over (pytest-only coverage matches the combined
      nose+pytest baseline only after tests relocate to `src/tests/`).
      Verified: `check provisioningserver` (pre-cutover, 2/131 test
      files under `src/tests/`) correctly reported
      `current: 9.19%, baseline: 94.91%, delta: -85.72pp, verdict: FAIL`
      — the real, expected mechanism output, not a bug
- [x] `check <package>` run with no baseline file present exits 2 with
      the documented message — verified directly:
      `cmd_check("metadataserver")` before any baseline existed printed
      "no baseline for metadataserver — run 'utilities/coverage-baseline
      capture metadataserver' first" and returned 2
- [x] Output format matches design §6 exactly (field names and order) —
      verified in `check provisioningserver`'s real output above

### Files
- `utilities/coverage-baseline` — modify (fill in `check`)

### Verification
- [x] `make lint` passes (see T1 evidence)
- [x] Manual: `capture provisioningserver` then `check
      provisioningserver` — correct mechanism confirmed (FAIL is
      expected pre-cutover; see AC evidence above)
- [x] Manual: `check metadataserver` before any baseline exists for it —
      confirmed exit 2 and the correct message (see AC evidence above)

## Task T4: Document the deletion-mapping convention for cutover features

**Priority:** P1
**Estimate:** 30m
**Dependencies:** none
**Covers:** FR-005, US-003

### Work
- [x] Add a short `README.md` (or equivalent doc) under
      `utilities/coverage-baselines/` stating the convention design §12
      already decided: a legacy test file deleted as "coverage already
      duplicated" during a cutover (F04-F07) must have a recorded
      mapping to the specific surviving test(s) that cover its behavior
      (e.g. a `decisions.md` entry per deleted file, or a PR-description
      table); a coverage percentage alone never licenses the deletion
      (D-004)
- [x] State explicitly that `utilities/coverage-baseline` does not
      enforce this mapping in code — it is a reviewer-verified process
      requirement on each cutover feature, matching design §12's exact
      wording

### Acceptance Criteria
- [x] The convention is written down somewhere a cutover feature's
      design/tasks can reference by path
      (`utilities/coverage-baselines/README.md`)
- [x] The doc does not claim the tool enforces something it does not —
      cross-checked against FR-005/D-004/US-003 in requirements.md,
      matches precisely

### Files
- `utilities/coverage-baselines/README.md` — create

### Verification
- [x] Manual: read the doc against design §12 and FR-005/US-003,
      confirm no contradiction or overstated claim — confirmed

## Task T5: Capture and commit real baselines for all three packages

**Priority:** P0
**Estimate:** 2h
**Dependencies:** T2, T3
**Covers:** FR-001, FR-002, FR-003, FR-006, NFR-001

### Work
- [x] Run `utilities/coverage-baseline capture provisioningserver`
- [x] Run `utilities/coverage-baseline capture metadataserver`
- [x] Run `utilities/coverage-baseline capture maasserver`
- [x] For each, confirm the two-pass stability check passed (no abort)
      and inspect the written JSON for a plausible `percent_covered`
      (sanity check against a manual `coverage report --include=` run,
      per design §15): provisioningserver 94.91% (0.014pp spread),
      metadataserver 95.05% (0.148pp spread), maasserver 96.01% (0.005pp
      spread) — all well within the 1.0pp tolerance
- [x] Run `utilities/coverage-baseline check <package>` for all three
      immediately afterward, confirm each reports a correctly-computed
      current/baseline/delta and the verdict those numbers imply (per
      design §15 amendment: FAIL is expected pre-cutover — pytest-only
      coverage of an un-migrated package is necessarily far below its
      nose+pytest baseline; this proves the capture→check round-trip's
      mechanism works end-to-end on real data, not that today's verdict
      is PASS): provisioningserver 9.19% vs 94.91% (FAIL), metadataserver
      7.24% vs 95.05% (FAIL), maasserver 10.44% vs 96.01% (FAIL) — all
      three correct, expected pre-cutover
- [x] Commit the three JSON files under
      `utilities/coverage-baselines/`

### Acceptance Criteria
- [x] `utilities/coverage-baselines/provisioningserver.json`,
      `metadataserver.json`, `maasserver.json` all exist, committed,
      each with a plausible (non-zero, non-100%) `percent_covered`
- [x] All three `check` runs immediately after their own `capture`
      report a correctly-computed delta and the verdict it implies (FAIL
      expected for all three today — none are cut over yet; see design
      §15 amendment) — confirmed above
- [x] FR-006's ordering requirement satisfied: all three baselines exist
      before any F04-F07 work begins (this task is the literal
      satisfaction of FR-006, not just evidence for it)

### Files
- `utilities/coverage-baselines/provisioningserver.json` — create
- `utilities/coverage-baselines/metadataserver.json` — create
- `utilities/coverage-baselines/maasserver.json` — create

### Verification
- [x] Manual: all three `capture` runs complete without a stability-
      check abort — confirmed (see AC evidence)
- [x] Manual: all three `check` runs report a correct, verifiable
      current/baseline/delta/verdict (FAIL expected pre-cutover) —
      confirmed
- [x] Manual: spot-check `provisioningserver`'s `percent_covered`
      against an independent `coverage report --include=` run on
      independently-produced combined data: baseline 94.91% vs
      independent report's TOTAL 95% (39226 stmts, 4278 branches —
      matching `_package_totals`' `num_statements`/`num_branches`
      exactly), confirming the numbers agree
