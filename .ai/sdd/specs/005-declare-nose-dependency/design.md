# Design: Declare `nose` as an explicit testing dependency

> Requirements: @requirements.md
> Status: Approved

## 1. Summary

Two changes:

1. Add `"nose>=1.3,<1.4"` to `pyproject.toml`'s
   `optional-dependencies.testing` list, alphabetically ordered
   alongside its existing siblings (FR-001).
2. Add a small compatibility shim at the top of
   `maastesting/noseplug.py` that restores two Python-version-removed
   names vanilla PyPI `nose==1.3.7` still imports:
   `unittest.runner._TextTestResult`/`unittest._TextTestResult` (as
   aliases of `unittest.runner.TextTestResult`, removed on Python 3.14),
   and `collections.Callable` (as an alias of
   `collections.abc.Callable`, removed since Python 3.10) — both before
   `nose` is imported (FR-002).

The shim is required because vanilla PyPI `nose==1.3.7` — what the
declared dependency range actually installs — raises
`ImportError: cannot import name '_TextTestResult'` on Python 3.14, and
(once that is fixed) `AttributeError: module 'collections' has no
attribute 'Callable'` on any Python since 3.10 — both discovered by
reproducing the break live during this feature's own implementation.
The system's `python3-nose` Debian package (`1.3.7-15`) silently worked
around both with an undocumented local patch; declaring the dependency
without the shim would only work by accident, on systems carrying that
exact undocumented patch.

## 2. Requirements Mapping

| Requirement | Design Coverage |
|-------------|-----------------|
| FR-001 | §3.1 |
| FR-002 | §3.2 |
| NFR-001 | §3.1 (version range matches the confirmed-working `1.3.7`) |

## 3. Technical Approach

### 3.1 Dependency declaration

Insert `"nose>=1.3,<1.4"` into the existing
`optional-dependencies.testing` array in `pyproject.toml`, in the
array's existing alphabetical order (between `"junitxml>=0.7,<0.8"` and
`"postgresfixture>=0.5,<0.6"`).

### 3.2 Python version compatibility shim (3.14 and 3.10+)

At the top of `maastesting/noseplug.py`, before any `nose` import:

```python
import collections
import collections.abc
import unittest

# nose==1.3.7 (PyPI) relies on several names removed from the standard
# library by Python 3.14 (and, for `collections.Callable`, since Python
# 3.10): `unittest._TextTestResult`/`unittest.runner._TextTestResult`
# (renamed to `TextTestResult`), and `collections.Callable` (moved to
# `collections.abc.Callable`). This repo's previously-ambient system
# `nose` package carried an undocumented local patch doing exactly
# this; restore both explicitly so the declared PyPI dependency
# (FR-001) works the same way regardless of which system installs it.
# Delete alongside `nose` itself at PLAN.md F08.
if not hasattr(unittest, "_TextTestResult"):
    unittest._TextTestResult = unittest.TextTestResult
if not hasattr(unittest.runner, "_TextTestResult"):
    unittest.runner._TextTestResult = unittest.runner.TextTestResult
if not hasattr(collections, "Callable"):
    collections.Callable = collections.abc.Callable

from nose.case import Test
...
```

`noseplug.py` is the single earliest chokepoint: `scripts.py` imports
`maastesting.noseplug.main` before anything else touches `nose`
(confirmed: only entry point importing `nose` transitively), so the
shim applied there covers every invocation path
(`bin/test.region`, `bin/test.rack`, `bin/test.parallel`).

The shim is guarded with `hasattr` checks so it is a true no-op on any
Python version where these names already exist (e.g. if run under an
older Python during the transition period) — it only ever adds a
missing attribute, never overwrites an existing one.

## 4. Component / Module Structure

```text
pyproject.toml              # modify: one line added to optional-dependencies.testing
maastesting/noseplug.py     # modify: compat shim added before nose imports
```

## 5. Data Model / State

Not applicable.

## 6. API / Integration Contract

Not applicable — no CLI, no endpoint, no code path exposed beyond the
existing `nose`-invoking entry points, which are otherwise unchanged.

## 7. Security / Permissions / Privacy

Not applicable.

## 8. User Flows

Not applicable — no user-facing flow; a dependency declaration plus an
import-time compatibility fix.

## 9. Edge Cases

| Case | Expected Behavior |
|------|--------------------|
| A fresh `.ve` is built from `pyproject.toml`'s `testing` extra with no ambient/system `nose` installed | `nose==1.3.7` installs from the declared range (PyPI build); the shim in `noseplug.py` restores both the `unittest`/`unittest.runner` names and `collections.Callable` before import; `bin/test.region`/`bin/test.rack` run successfully. |
| An ambient system `nose` (e.g. this repo's patched `python3-nose` Debian package) also satisfies the declared range and is resolved instead | Both `hasattr` guards are a no-op (the names already exist on the patched package); no behavior change. |
| `nose` is removed from the environment entirely (e.g. a future, non-testing install) | `noseplug.py`'s shim runs regardless (it only touches `unittest`/`collections`, not `nose`); the subsequent `from nose.case import Test` fails with the ordinary `ModuleNotFoundError`, unchanged from today. |
| A newer Python restores or renames these symbols again in the future | `hasattr` guards prevent the shim from ever overwriting a real, already-present name — it only fills a gap. |

## 10. Accessibility / UX Notes

Not applicable.

## 11. Observability / Operations

Not applicable — no runtime behavior change beyond making a previously
implicit, environment-specific patch explicit and portable.

## 12. Migration / Rollout

- **Rollout:** Both changes land together; `pyproject.toml`'s new
  declaration and `noseplug.py`'s shim are two halves of one fix — the
  declaration without the shim is what caused the regression discovered
  during implementation.
- **Rollback:** Revert both files. If `nose` is removed as a dependency,
  the shim becomes dead code (guarded by `hasattr`, inert on any Python
  that doesn't need it) — deleted alongside `noseplug.py` itself at
  PLAN.md F08, not before.

## 13. Technical Decisions

### TD-001: Range pin, not exact or unbounded

- **Decision:** `"nose>=1.3,<1.4"`.
- **Why:** Matches `testtools`/`testscenarios`/`testresources`'s
  existing pin style in the same list (requirements D-001).
- **Trade-off:** None material — `nose` is unmaintained, so the range's
  upper bound is unlikely to ever matter in practice.
- **Alternatives considered:** Exact pin `==1.3.7` (rejected — diverges
  from sibling convention without the specific reason `pyright`'s exact
  pin has); unbounded `nose` (rejected — reopens the ambient-version risk
  this feature exists to close).

### TD-002: Compatibility shim in `noseplug.py`, not a vendored/patched `nose`

- **Decision:** A ~10-line `hasattr`-guarded alias shim in
  `maastesting/noseplug.py`, applied before any `nose` import, rather
  than vendoring a patched `nose` wheel or depending on a system-level
  patch.
- **Why:** Discovered live during implementation (requirements D-002):
  vanilla PyPI `nose==1.3.7` fails on Python 3.14 (`_TextTestResult`)
  and, independently, on any Python since 3.10 (`collections.Callable`)
  without it. A shim at the single earliest `nose`-import chokepoint
  (`noseplug.py`) is minimal, self-contained in this repo's own source
  (not relying on an undocumented external patch), and temporary —
  deleted with the rest of `noseplug.py` at PLAN.md F08.
- **Trade-off:** Adds ~10 lines of Python-version-compatibility code
  for a dependency scheduled for full removal; accepted given the
  alternative (silent breakage on any environment without the
  undocumented system patch) is worse.
- **Alternatives considered:** Vendor a patched `nose` wheel (rejected —
  more invasive, needs its own build/distribution story for a ~1-year
  tool); rely on the system package continuing to carry its undocumented
  patch (rejected — this is precisely the ambient-dependency risk
  FR-001 exists to close, and is not portable to CI or other
  environments).

## 14. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| The shim's `hasattr` guard could mask a *different* future `unittest`/`collections` incompatibility by appearing to succeed while nose still breaks elsewhere | Low | The shim only touches three specific names; any other incompatibility would surface as its own distinct `ImportError`/`AttributeError`, not silently swallowed. |
| `nose` resolves to a yet-different build (not PyPI, not this system's patched Debian package) with its own quirks | Low | Out of scope — the shim fixes the one confirmed incompatibility (PyPI vanilla `1.3.7` on Python 3.14); a materially different `nose` build is not something this feature can anticipate, and `nose` itself is being retired (PLAN.md F08). |

## 15. Verification Strategy

- **Unit/component:** Not applicable — no code worth isolating in a
  unit test for a ~10-line, soon-to-be-deleted compatibility shim; verified
  by actually running the suite (next bullet), matching this feature's
  own design philosophy of fixing a problem discovered by direct
  reproduction.
- **Integration/manual:**
  1. Confirm `pyproject.toml` still parses as valid TOML after the edit.
  2. Remove any pre-existing ambient/system-shadowing `nose` install from
     `.ve` if present, confirm the suite still runs via the system
     package (sanity baseline).
  3. Force-install vanilla PyPI `nose==1.3.7` into `.ve` (reproducing the
     exact failure mode discovered during implementation) and confirm
     `bin/test.rack`'s full suite now passes with the shim in place
     (previously: `ImportError` on the first import).
  4. Confirm the shim is a no-op when the system's already-patched
     `nose` is active (re-run with the ambient package, confirm
     identical pass count to the pre-shim baseline).
- **Build/lint:** `make lint` (covers `pyproject.toml` syntax and
  `noseplug.py`'s Python syntax/style via Ruff).

## 16. Implementation FAQ

**Q:** Why not pin to the exact installed patch version?
**A:** D-001 in requirements.md: consistency with the three sibling
legacy-stack dependencies, all range-pinned the same way in the same
list.

**Q:** Why discover this gap only now, instead of during design?
**A:** The gap only manifests when the *declared* dependency is actually
*installed* from PyPI — the system's pre-existing, undocumented
Debian patch masked it in every environment checked during requirements
gathering (where "1.3.7 confirmed working" was true, but only via the
patched system package, not the vanilla PyPI release the new
declaration pulls in). It was found by attempting T1's own verification
step (triggering a dependency sync), which is exactly what design §15's
"verified by actually running the suite" is for.

**Q:** Does this shim affect anything outside `nose`'s own test runs?
**A:** No — it only adds three missing attributes to `unittest`/
`collections` if absent, and only at `noseplug.py` import time (which
happens only when `bin/test.region`/`bin/test.rack`/`bin/test.parallel`
run).
No other code path imports `noseplug.py`.
