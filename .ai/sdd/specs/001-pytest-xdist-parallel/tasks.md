# Tasks: pytest-xdist parallel infra

> Requirements: @requirements.md
> Design: @design.md
> Status: Approved

## Requirement Coverage

| Requirement | Tasks | Notes |
|-------------|-------|-------|
| FR-001 | T1, T3 | Configurable concurrency via `MAAS_MAX_TEST_PROCESSES`/`--maxprocesses` |
| FR-002 | T1, T2 | Default of 4 (amended per TD-001) |
| FR-003 | T2, T4 | JUnit XML output structural check |
| FR-004 | T2 | Validation against `src/tests/**` pytest-native suite |
| NFR-001 | T2, T6 | Performance baseline capture and record |
| NFR-002 | T5 | Reliability / no flakiness across repeated runs |

## Implementation Readiness Check

| Check | Status | Notes |
|-------|--------|-------|
| Must Have requirements have tasks | Pass | FR-001–FR-004 all covered (table above) |
| Requirements are covered by design | Pass | design.md §2 Requirements Mapping covers all FR/NFR |
| Critical Questions are answered | Pass | requirements.md Questions: "None open"; design-phase gap (default value) resolved and requirements amended |
| Tasks have dependencies, acceptance criteria, files, and verification | Pass | see tasks below |
| Verification commands are known or marked manual/N/A | Pass | all commands explicit, derived from design.md §15 |

## Implementation Slices

### MVP Slice

- **Goal:** Confirm the existing pytest-xdist CI pattern satisfies all F01
  Must Have requirements, with no code changes unless a real gap surfaces.
- **User Stories:** US-001, US-002, US-003
- **Tasks:** T1, T2, T3, T4, T5, T6
- **Independent validation:** Each task's own verification step (below);
  overall slice is validated when the Readiness Check items all pass and
  T6's baseline record is committed.

## Task T1: Confirm single source of truth for worker-count config

**Priority:** P0
**Estimate:** 30m
**Dependencies:** none
**Covers:** FR-001, FR-002

### Work
- [x] Grep `pyproject.toml`, `tox.ini`, `pytest.ini` (none expected),
      `conftest.py` files under `src/tests`, and `Makefile` for any
      competing xdist worker-count configuration (e.g. `addopts` with
      `-n`, a second `MAAS_MAX_TEST_PROCESSES` reader, or hardcoded
      `--numprocesses`).
- [x] Confirm `utilities/run-py-tests-ci` is the sole place that reads
      `MAAS_MAX_TEST_PROCESSES` and passes `--maxprocesses`.

### Acceptance Criteria
- [x] No competing worker-count configuration found, OR any found is
      documented and reconciled (flagged to the user before proceeding).
      **Result:** none found. Zero matches in `pyproject.toml`, `tox.ini`,
      `Makefile`, `src/tests/**` (incl. all 7 `conftest.py` files);
      `MAAS_MAX_TEST_PROCESSES` read exactly once, in
      `utilities/run-py-tests-ci`.

### Files
- `utilities/run-py-tests-ci` — inspect only
- `pyproject.toml` — inspect only

### Verification
- [x] `grep -rn "numprocesses\|MAAS_MAX_TEST_PROCESSES\|-n auto\|-n=" pyproject.toml tox.ini Makefile src/tests` returns only the known `utilities/run-py-tests-ci` usage. **PASS** — zero matches outside that file.

## Task T2: Execute baseline validation run against src/tests

**Priority:** P0
**Estimate:** 1h
**Dependencies:** T1
**Covers:** FR-002, FR-003, FR-004, NFR-001 (baseline capture)

### Work
- [x] Run `MAAS_MAX_TEST_PROCESSES=4 bin/pytest -n auto --maxprocesses=4 --dist=load --junit-xml=junit-pytest.xml src/tests` with default concurrency.
- [x] Record wall-clock duration, exit code, and total tests
      collected/passed/failed/errored.
      **Result:** wall-clock 209.89s (202.62s pytest-internal); exit code 1;
      7949 collected (7766 passed, 2 failed, 181 skipped).
- [x] If exit code is non-zero due to a test failure unrelated to this
      feature (pre-existing flaky/broken test), note it separately — do
      not treat as a design gap.
      **Result:** 2 failures are `test_etag` in
      `test_resource_pools.py`/`test_zones.py` — hardcoded hash-string
      assertions. Reproduced identically serially (no xdist), last
      touched by unrelated historical commit `60a2eef16`, `git status`
      clean. Confirmed pre-existing, unrelated to this feature.

### Acceptance Criteria
- [x] Run completes (exit code `0`, or only pre-existing unrelated
      failures documented). **Result:** exit 1, documented above as
      pre-existing/unrelated — accepted per task's own exception clause.
- [x] `junit-pytest.xml` is produced and non-empty. **Result:** valid
      well-formed XML, single-line minified, 7949 `<testcase>` elements.
- [x] Total collected test count matches `find src/tests -iname "test_*.py"` expectations (no silent under-collection). **Result:** 7949 tests across 381 source files (~20 tests/file average) — no under-collection.

### Files
- `junit-pytest.xml` — generated artifact (repo root, already gitignored/CI artifact per existing convention)

### Verification
- [x] `MAAS_MAX_TEST_PROCESSES=4 bin/pytest -n auto --maxprocesses=4 --dist=load --junit-xml=junit-pytest.xml src/tests` — ran, exit 1 (2 pre-existing unrelated failures, see above).
- [x] `echo $?` confirms exit code — **1**, documented and accepted.
- [x] `wc -l junit-pytest.xml` confirms non-empty output — 42 (file is single-line minified XML); confirmed well-formed and complete via `ElementTree.parse` + `<testcase>` count (7949) matching `tests="7949"` attribute. **PASS**.

## Task T3: Verify concurrency override behavior

**Priority:** P1
**Estimate:** 30m
**Dependencies:** T2
**Covers:** FR-001

### Work
- [x] Re-run with an explicit override: `MAAS_MAX_TEST_PROCESSES=2 bin/pytest -n auto --maxprocesses=2 --dist=load src/tests -v`.
- [x] Confirm xdist reports 2 workers (visible in verbose/startup output,
      e.g. `gw0`/`gw1` worker IDs only, no `gw2`+).
      **Result:** only `[gw0]`/`[gw1]` appear across the entire run
      (14480+ lines of verbose output); no `gw2` or higher. Exit 1 (same
      2 pre-existing `test_etag` failures as T2, unrelated to override).
      Runtime 381.26s with 2 workers vs. 202.62s with 4 workers —
      consistent with halving parallelism.

### Acceptance Criteria
- [x] Worker count visibly changes from T2's run (4) to this run's
      override (2), proving the env var/flag is honored.
      **Result:** confirmed — `gw0`/`gw1` only, no `gw2`+.

### Files
- None (verification-only)

### Verification
- [x] `MAAS_MAX_TEST_PROCESSES=2 bin/pytest -n auto --maxprocesses=2 --dist=load src/tests -v 2>&1 | grep -oE "\[gw[0-9]+\]" | sort -u` shows only `[gw0]` and `[gw1]`. **PASS**.

## Task T4: Verify JUnit XML structural correctness

**Priority:** P1
**Estimate:** 30m
**Dependencies:** T2
**Covers:** FR-003

### Work
- [x] Parse `junit-pytest.xml` from T2's run and confirm it contains
      well-formed `<testsuite>`/`<testcase>` elements.
      **Result:** parses cleanly via `ElementTree`; root `<testsuites>`,
      one `<testsuite>` (attrs: errors=0, failures=2, skipped=181,
      tests=7949, time=202.449 — matches T2's recorded run exactly).
- [x] Confirm the number of `<testcase>` elements matches the collected
      test count from T2.
      **Result:** 7949 `<testcase>` elements == `tests="7949"` attribute
      == T2's recorded collected count. Exact match.
- [x] Confirm no translation step (e.g. `subunit2junitxml`) is needed —
      this file is pytest's native `--junit-xml` output.
      **Result:** confirmed — file produced directly by pytest's
      `--junit-xml` flag, no subunit/translation pipeline involved.

### Acceptance Criteria
- [x] XML parses without error. **PASS**.
- [x] `<testcase>` count matches T2's collected count. **PASS** — 7949 == 7949.

### Files
- `junit-pytest.xml` — inspect only

### Verification
- [x] `python3 -c "import xml.etree.ElementTree as ET; ET.parse('junit-pytest.xml')"` exits `0`. **PASS**.
- [x] `<testcase>` element count (via `ElementTree.iter`, not line-based `grep -c` — file is single-line minified XML) matches T2's recorded collected count (7949). **PASS**.

## Task T5: Reliability check — repeated run consistency

**Priority:** P1
**Estimate:** 1h
**Dependencies:** T2
**Covers:** NFR-002

### Work
- [x] Re-run the same validation command from T2 a second time.
- [x] Compare pass/fail/error counts between the two runs.
      **Result:** T2: 7766 passed, 2 failed, 181 skipped, 7949 total,
      202.62s, exit 1. T5 re-run: 7766 passed, 2 failed, 181 skipped,
      202.41s, exit 1. Identical failing tests both times
      (`test_resource_pools.py::test_etag`,
      `test_zones.py::test_etag`), same assertion values. No collection
      drift, no new flakes.

### Acceptance Criteria
- [x] Both runs report identical pass/fail/error counts (barring
      pre-existing known-flaky tests, which must be named explicitly if
      excluded).
      **Result:** identical — 7766/2/181 both runs. The 2 known
      pre-existing failures (test_etag, see T2) are the only failures in
      both runs, consistently.

### Files
- None (verification-only)

### Verification
- [x] Diff of collected/passed/failed/errored counts between T2's run and this re-run is empty (or documented exceptions only). **PASS** — 7766/2/181/7949 identical both runs.

## Task T6: Record performance baseline and scope note

**Priority:** P2
**Estimate:** 30m
**Dependencies:** T2, T5
**Covers:** NFR-001, Risk (PLAN.md wording ambiguity)

### Work
- [x] Append the recorded wall-clock baseline (from T2) to
      `design.md` §11 Observability/Operations as a dated, concrete value
      (replacing the current placeholder guidance).
      **Result:** done — 202.62s/209.89s at 4 workers (T2), 381.26s at 2
      workers (T3), dated 2026-11-13.
- [x] Add a short note to `.ai/sdd/PLAN.md`'s F01 row or a `decisions.md`
      entry clarifying that F01 does not retire nose/`test.parallel` —
      pointing to D-001/TD-002 — to pre-empt the risk noted in design.md
      §14.
      **Result:** created `decisions.md` with the scope-clarification
      note and a recorded-evidence summary of T1–T6.

### Acceptance Criteria
- [x] `design.md` contains a concrete recorded baseline duration (not a
      placeholder). **PASS** — §11 updated.
- [x] A scope-clarification note exists and is discoverable from
      `PLAN.md` or `decisions.md`. **PASS** — `decisions.md` created,
      cross-referenced from design.md and requirements.md.

### Files
- `.ai/sdd/specs/001-pytest-xdist-parallel/design.md` — modify (§11)
- `.ai/sdd/specs/001-pytest-xdist-parallel/decisions.md` — create (optional, if not folded into PLAN.md note)

### Verification
- [x] Manual review: baseline value present and consistent with T2's recorded number. **PASS** — design.md §11 baseline matches T2's recorded 202.62s/209.89s exactly.
