# Feature: Declare `nose` as an explicit testing dependency

> Status: Approved
> Source: .ai/sdd/PLAN.md (F02), .ai/sdd/ideas/003-coverage-gated-pytest-cutover.md

## Overview

`nose` is imported by `maastesting/noseplug.py` and executed by every
region/rack test run (`bin/test.region`, `bin/test.rack`,
`bin/test.parallel`), but it is **not declared** in
`pyproject.toml`'s `optional-dependencies.testing` — unlike its
legacy-stack siblings `testtools`, `testscenarios`, and `testresources`,
which are all version-pinned there. The merge gate currently depends on
an ambient, undeclared install. This feature closes that gap for as
long as `nose` keeps running (until the broader cutover, PLAN.md
F04-F08, removes it entirely).

## Business Context

- **Problem:** A test runner the CI gate depends on is not a declared
  dependency. A clean environment with no system/ambient `nose` install
  would silently fail to run the region/rack suite, or (worse) could
  silently pick up an incompatible version from wherever it happens to
  be found.
- **Users:** CI maintainers (own the merge gate's dependency honesty);
  MAAS engineers setting up a fresh development environment.
- **Value:** Removes a latent, already-existing CI break — this is not
  a migration-dependent fix, it is correct today regardless of whether
  the broader cutover ever lands.
- **Success signal:** `nose` is declared in
  `optional-dependencies.testing` with an explicit version range; a
  fresh `.ve` built from `pyproject.toml` alone (no ambient system
  package) can run `bin/test.region`/`bin/test.rack` successfully.

## User Stories

### US-001: CI maintainer trusts that every test-runner dependency is declared

**As a** CI maintainer
**I want to** have `nose` declared in `pyproject.toml` like every other
testing dependency
**So that** the merge gate's dependency set is complete and reproducible,
not reliant on an ambient system install

**Acceptance Criteria:**
- [ ] `nose` appears in `pyproject.toml`'s
      `optional-dependencies.testing` list
- [ ] The declared version range matches the version currently proven to
      work (`1.3.7`), using the same `>=X,<X.1` range-pin style as the
      other legacy-stack entries in the same list (`testtools`,
      `testscenarios`, `testresources`)
- [ ] A fresh virtualenv built solely from `pyproject.toml`'s declared
      dependencies (no ambient/system `nose`) can successfully run the
      region and rack test suites

## Functional Requirements

### FR-001: Declare `nose` in `optional-dependencies.testing` — Must Have

THE SYSTEM SHALL add `"nose>=1.3,<1.4"` to `pyproject.toml`'s
   `optional-dependencies.testing` list
SO THAT the test-runner dependency set is complete and does not rely on
   an ambient install

### FR-002: Python version compatibility shim for vanilla PyPI `nose` — Must Have

WHEN `nose` is resolved from the declared PyPI range (FR-001) rather
   than from an ambient, pre-patched system package
IF `nose` is imported under a Python version that has removed a name
   vanilla PyPI `nose==1.3.7` still relies on directly — confirmed:
   `unittest._TextTestResult`/`unittest.runner._TextTestResult` (removed
   Python 3.14) and `collections.Callable` (removed since Python 3.10)
THE SYSTEM SHALL restore those names (as aliases of
   `unittest.runner.TextTestResult` and `collections.abc.Callable`
   respectively) before `nose` is imported
SO THAT `nose` run via the declared dependency works identically to how
   it works today via the system's own undocumented compat-patched
   package, closing the regressions discovered during implementation
   (confirmed: vanilla PyPI `nose==1.3.7` raises `ImportError: cannot
   import name '_TextTestResult'`, and, once fixed, `AttributeError:
   module 'collections' has no attribute 'Callable'`, on this repo's
   Python 3.14.4; the system `python3-nose` Debian package (`1.3.7-15`)
   carries an undocumented patch doing exactly this)

## Non-Functional Requirements

### NFR-001: Reliability
- The declared version range must match a version already confirmed
  working against this repo's suite (`1.3.7`, confirmed running
  successfully under Python 3.14.4 during this plan's evidence-gathering
  — see `.ai/sdd/ideas/003-coverage-gated-pytest-cutover.md`).

## Out of Scope

- Removing `nose` entirely — that is PLAN.md F08 (Retire nose and the
  legacy stack), gated on every package cutover (F04-F07) completing
  first.
- Any change to `maastesting/noseplug.py`, `scripts.py`, or any other
  code beyond the minimal compat shim (FR-002) — the shim is the only
  code change; everything else about how `nose` is imported/invoked is
  unchanged.
- Upgrading `nose` beyond `1.3.7` — it is unmaintained (last release
  2015); this feature pins to the version already proven working, not a
  newer one.
- CI workflow changes — `nose` already runs in CI today via whatever
  ambient install currently exists; this feature only makes the
  dependency explicit and portable to any environment, not reliant on
  that specific system's undocumented patch.

## Decisions

### D-001: Version pin style matches existing legacy-stack siblings

**Decision:** Pin `nose` with a `>=1.3,<1.4` range, matching the pin
style already used for `testtools`, `testscenarios`, and
`testresources` in the same `optional-dependencies.testing` list, rather
than an exact pin (`==1.3.7`) or an unbounded declaration (`nose`).
**Reason:** Consistency with the three other legacy-stack dependencies
declared in the same block, all of which use this range style. An
unbounded declaration would reopen exactly the ambient-version risk this
feature exists to close. An exact pin diverges from the established
convention for this dependency family without a specific reason (unlike
`pyright`'s exact pin elsewhere in the same block, which exists to work
around a specific upstream bug).
**Source:** Direct user instruction (nose_pin_style).
**Impacts:** FR-001.

### D-002: Python 3.14 incompatibility fixed with a minimal unittest-alias shim, not by avoiding the declaration or vendoring `nose`

**Decision:** Add a small compatibility shim (in `maastesting/noseplug.py`,
before `nose` is imported) that aliases
`unittest.runner.TextTestResult` to the old
`_TextTestResult`/`unittest._TextTestResult`/`unittest.runner._TextTestResult`
names vanilla PyPI `nose==1.3.7` expects, rather than (a) declaring
`nose` anyway and accepting it only works via the system's undocumented
patch, or (b) vendoring/patching a local copy of `nose` itself.
**Reason:** Discovered during implementation: declaring
`"nose>=1.3,<1.4"` (FR-001) causes any environment sync to install
vanilla PyPI `nose==1.3.7`, which raises
`ImportError: cannot import name '_TextTestResult'` on Python 3.14 —
reproduced live in this repo's own `.ve`. The previously-working system
package (`python3-nose` Debian `1.3.7-15`) carries this exact fix as an
undocumented local patch. A small, scoped shim is minimal (a few lines,
one file, already the project's established practice of patching
legacy-stack behavior at the `maastesting` boundary) and temporary —
`nose` itself is scheduled for full removal at PLAN.md F08, so the shim
is deleted along with it, not a long-lived maintenance burden.
**Source:** Direct user instruction (nose_py314_fix), following a live
regression discovered and reproduced during T1's implementation attempt.
**Impacts:** FR-002 (new), Out of Scope.

### D-003: `collections.Callable` incompatibility folded into the same FR-002 shim, not scoped as a separate feature

**Decision:** Extend the same shim (same file, same `hasattr`-guard
pattern) with `collections.Callable = collections.abc.Callable`, rather
than treating this as a new, separately-specced gap.
**Reason:** Discovered during T2's own verification (same mechanism as
D-002 — reproducing the suite with vanilla PyPI `nose==1.3.7` actually
installed): after the `_TextTestResult` fix, `bin/test.rack` next fails
with `AttributeError: module 'collections' has no attribute 'Callable'`
(removed since Python 3.10, renamed `collections.abc.Callable`) across
9 call sites in vanilla `nose`'s own source. Same root cause family
(stdlib API removed since this repo adopted `nose`, masked by the same
undocumented system patch), same fix shape, same file, same lifecycle
(deleted at PLAN.md F08) — a separate feature would only add process
overhead for an already-approved shim mechanism.
**Source:** Direct user instruction, confirming extension of the
existing T2 task rather than a new feature/spec cycle.
**Impacts:** FR-002 (scope), T2.

## Questions

None open. All three scope-determining questions (version-pin style,
the Python 3.14 `_TextTestResult` fix, and the `collections.Callable`
fix both discovered during implementation) were resolved and recorded
as D-001, D-002, and D-003.

## Glossary

- **Ambient dependency:** A package available at runtime because it
  happens to be installed system-wide or in `dist-packages`, not because
  it is declared in the project's own dependency manifest.
