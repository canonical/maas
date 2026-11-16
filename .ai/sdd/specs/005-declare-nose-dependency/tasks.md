# Tasks: Declare `nose` as an explicit testing dependency

> Requirements: @requirements.md
> Design: @design.md
> Status: Approved

## Requirement Coverage

| Requirement | Tasks | Notes |
|-------------|-------|-------|
| FR-001 | T1 | |
| FR-002 | T2 | Added after T1's own verification step reproduced a live regression (requirements D-002) |
| NFR-001 | T1 | |

## Implementation Readiness Check

| Check | Status | Notes |
|-------|--------|-------|
| Must Have requirements have tasks | Pass | FR-001 covered by T1, FR-002 by T2 |
| Requirements are covered by design | Pass | design.md §3.1/§3.2, §13 |
| Critical Questions are answered | Pass | requirements.md Questions: "None open" |
| Tasks have dependencies, acceptance criteria, files, and verification | Pass | See tasks below |
| Verification commands are known or marked manual/N/A | Pass | `make lint` + manual suite smoke runs (ambient and forced-PyPI) |

## Implementation Slices

### MVP Slice

- **Goal:** `nose` declared in `pyproject.toml` with the agreed version
  range, and actually working when resolved from that declaration (not
  just from this system's undocumented ambient patch).
- **User Stories:** US-001
- **Tasks:** T1, T2
- **Independent validation:** `nose` entry present, correctly pinned,
  alphabetically placed; `pyproject.toml` still parses; region/rack
  suites pass both via the ambient system package and via a
  forced-vanilla-PyPI install.

## Task T1: Add `nose` to `optional-dependencies.testing`

**Priority:** P0
**Estimate:** 15m
**Dependencies:** none
**Covers:** FR-001, NFR-001

### Work
- [x] Add `"nose>=1.3,<1.4"` to `pyproject.toml`'s
      `optional-dependencies.testing` list, in alphabetical order
      (between `junitxml` and `postgresfixture`)

### Acceptance Criteria
- [x] `pyproject.toml` contains `"nose>=1.3,<1.4"` in
      `optional-dependencies.testing`
- [x] The entry is alphabetically placed among its siblings
- [x] `pyproject.toml` still parses as valid TOML

### Files
- `pyproject.toml` — modify

### Verification
- [x] `pyproject.toml` parses via `tomllib.load` — confirmed
- [x] Manual: discovered during this task's own verification that a
      full `make lint` run syncs the `testing` extra, installing vanilla
      PyPI `nose==1.3.7` into `.ve`, which **breaks**
      `bin/test.rack`/`bin/test.region` (`ImportError: cannot import
      name '_TextTestResult'` — Python 3.14 removed the name vanilla
      PyPI `nose` still imports). This is a real regression, not a test
      artifact — recorded as requirements D-002, resolved by T2.

## Task T2: Python 3.14 compatibility shim for vanilla PyPI `nose`

**Priority:** P0
**Estimate:** 30m
**Dependencies:** T1 (shim fixes the regression T1's own verification discovered)
**Covers:** FR-002

### Work
- [x] Add the `hasattr`-guarded `unittest._TextTestResult`/
      `unittest.runner._TextTestResult` alias shim to the top of
      `maastesting/noseplug.py`, before any `nose` import (design §3.2)
- [x] Remove any vanilla-PyPI `nose` copy currently shadowing the system
      package in `.ve/lib/python3.14/site-packages/` (left over from
      T1's verification; restores the known-good baseline before
      re-verifying)
- [x] Discovered during verification: vanilla PyPI `nose==1.3.7` also
      fails with `AttributeError: module 'collections' has no attribute
      'Callable'` (removed Python 3.10, renamed
      `collections.abc.Callable`) — a second, independent
      incompatibility beyond `_TextTestResult`. Extended the same shim
      with a `collections.Callable = collections.abc.Callable` alias,
      same `hasattr`-guard pattern, approved by the user as an extension
      of this task rather than a separate feature.

### Acceptance Criteria
- [x] With the shim in place, force-installing vanilla PyPI
      `nose==1.3.7` into `.ve` (reproducing T1's discovered regression)
      no longer breaks `bin/test.rack`'s full suite — same pass count as
      the pre-regression baseline (3533 tests, OK) — confirmed
- [x] With the shim in place and the ambient/system `nose` package
      active (not the vanilla PyPI copy), the suite still passes
      identically — the shim's `hasattr` guard is confirmed a true no-op
      against the already-patched package — confirmed (3533 tests, OK)
- [x] `ruff check`/`ruff format --check` pass on the modified
      `noseplug.py` — confirmed

### Files
- `maastesting/noseplug.py` — modify

### Verification
- [ ] `make lint` passes
- [ ] Manual: ambient-package run — `.ve/bin/test.rack` full suite,
      confirm pass count matches the pre-existing baseline (3533 tests)
- [ ] Manual: forced-vanilla-PyPI run — install PyPI `nose==1.3.7` into
      `.ve` (reproducing T1's regression exactly), confirm the same full
      suite now passes with the shim active, then restore `.ve` to the
      ambient-package state afterward (do not leave the forced install
      in place — matches the repo's actual steady state, where the
      system package is what's ambiently present)
