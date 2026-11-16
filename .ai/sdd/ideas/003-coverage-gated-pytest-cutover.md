# Idea: Coverage-gated pytest cutover, retiring nose and the legacy test stack

> Status: captured
> Created: 2026-11-16
> Supersedes approach in: `.ai/sdd/ideas/001-nose-to-pytest-migration.md`,
> `.ai/sdd/ideas/002-legacy-tests-under-pytest.md`
> Chosen direction: Direction A

## Raw Idea

While trying to move nose tests to pytest (ideas 001 and 002) we hit a
number of hard challenges. Try a different approach to the same goal:
run all unit tests using pytest, removing nose and other legacy/
deprecated frameworks.

Framing supplied with the idea:

- Django and Twisted are deprecated code in MAAS and will eventually be
  removed; do not over-engineer a solution for something short-lived
  (~1 year).
- All tests should live under `src/tests/`, following the existing
  structure.
- Prefer pytest fixtures and other modern features.
- Check whether mature pytest modules can be added as dependencies to
  solve problems.
- We do not need to migrate all tests, as long as we keep coverage the
  same.

## Why The Previous Approach Stalled

Ideas 001/002 chose a *parity-first, plugin-first* strategy: preserve
every legacy test unchanged and rebuild nose's semantics
(`testscenarios`, `testresources` `OptimisingTestSuite`, crochet/reactor
setup) as pytest plugins. That strategy ran into three compounding walls
documented in idea 002 — no resource management on Django-native test
cases, a pristine-template seed-data mismatch, and a process-global
`MAAS_PREVENT_MIGRATIONS` settings-mode conflict that no per-test fix can
reconcile inside one pytest worker.

It also built compatibility machinery for Django/Twisted-coupled code
that is scheduled for deletion, which contradicts the "do not
over-engineer short-lived code" constraint.

## Baseline State (verified 2026-11-16, not inferred)

Verification context: live `.ve` virtualenv, Python 3.14.4, pytest 9.2.0.

| Fact | Value | How confirmed |
|------|-------|---------------|
| Legacy inline test files (outside `src/tests/`) | 496 | `find src -name 'test_*.py' -not -path 'src/tests/*'` |
| — `maasserver` / `provisioningserver` / `metadataserver` / other | 338 / 129 / 23 / 6 | same, per directory |
| Legacy test definitions | 12,921 | `grep -E '^\s*(async )?def test_'` over those files |
| Already pytest-native under `src/tests/` | 381 files, 4,085 test defs | same method over `src/tests` |
| Legacy files using **no** hard feature | 147 of 496 | negative grep for scenarios/resources/`deferToDatabase`/`MAAS*ServerTestCase`/`inlineCallbacks`/crochet |
| Legacy files using ≥1 hard feature | 349 of 496 | same grep, positive |
| `nose` declared in `pyproject.toml` | **No** | `grep -n 'nose' pyproject.toml` → no match |
| `nose` importable | 1.3.7, from the venv and system `dist-packages` | `import nose` |
| nose still runs on Python 3.14 | Yes | `.ve/bin/test.rack src/provisioningserver/utils/tests/test_arp.py` → `Ran 4 tests in 0.043s — OK` |
| `pytest-django` installed | **No** | `import pytest_django` → `ModuleNotFoundError` |
| `testpaths` | `["src/tests"]` | `pyproject.toml [tool.pytest]` |
| Coverage tooling | `run.branch = true`, `run.source = ["src"]`, four per-suite `.cover` files | `pyproject.toml [tool.coverage]`, `utilities/run-tests-coverage` |

### Three findings that reshape the problem

1. **The F01–F03 implementation does not exist in the working tree.**
   Branch `nuke_nose` contains one commit (`27312b388 idea 01`) touching
   only `.gitignore`; `git status --short` shows only `.gitignore`
   modified. There is no `maastesting/pytest/region.py`, no
   `maastesting/pytest/scenarios.py`, and no `maas-region`/
   `maas-scenarios` `pytest11` entry point. `INDEX.md`'s F02
   `review:done` / F03 `implementation:in-progress` statuses are stale.
   **Consequence: there is no sunk implementation cost in changing
   approach.**

2. **Stock pytest already runs legacy `testtools` tests unmodified.**
   A sample of 20 untouched legacy files from the "no hard feature" tier
   ran `361 passed in 10.14s` under `.ve/bin/pytest` with zero MAAS
   plugins and zero source edits. A single legacy file took 0.42s under
   pytest vs 3.16s wall under nose. The blocker was never `testtools`
   collection; it is narrowly scoped to scenarios, `testresources`,
   reactor/crochet, and Django-DB setup.

3. **The scenarios tier degrades partially, not totally.**
   `src/provisioningserver/rpc/tests/test_common.py` under plugin-free
   pytest: `32 passed, 1 failed, 1 error` vs nose's `Ran 34 tests — OK`.
   Only the genuinely scenario-multiplied class breaks.

## Problem Space

- Two test runners gate every merge today (`utilities/run-py-tests-ci`
  runs `bin/test.parallel` *and* `bin/pytest`), doubling CI surface and
  onboarding cost.
- `nose` is unmaintained, Python-3-hostile, and — critically —
  **undeclared** in `pyproject.toml` while being imported by
  `maastesting/noseplug.py`. The suite depends on an ambient install.
  This is a latent CI break independent of any migration.
- The legacy stack (`testtools`, `testscenarios`, `testresources`,
  `fixtures`) is pinned in `optional-dependencies.testing` and keeps a
  large volume of `maastesting` machinery alive:
  `noseplug.py`, `djangoloader.py`, `djangotestcase.py`, `scenarios.py`,
  `parallel.py`, `runtest.py`, and the nose-specific parts of
  `scripts.py`.
- Tests live in two incompatible layouts: inline `**/tests/` next to
  source (legacy) and the mirrored `src/tests/<pkg>/...` tree (modern).
- Much of the hard-to-port surface is Django/Twisted-coupled — exactly
  the code scheduled for removal — so compatibility machinery built for
  it has a ~1-year payback window.

## Target Users

- **MAAS engineers** writing and running region/rack tests daily; want
  one runner, fast feedback, idiomatic fixtures.
- **CI maintainers** owning the gate; want one suite, attributable
  coverage, and no ambient undeclared dependencies.

## Current Alternatives

- Today: dual-runner CI — nose (`bin/test.region`, `bin/test.rack`,
  `bin/test.region.legacy`, orchestrated by `bin/test.parallel`) plus
  `bin/pytest` over `src/tests`.
- Ideas 001/002's approach: rebuild nose semantics as pytest plugins and
  migrate with strict test-for-test parity. Stalled on three compounding
  incompatibilities; no code landed.

## Desired Outcome

- One runner: `pytest`. `bin/test.parallel`, `bin/test.region`,
  `bin/test.region.legacy`, `bin/test.rack` and their nose entry points
  are gone.
- All tests under `src/tests/`, mirroring the existing convention.
- `nose`, `testtools`, `testscenarios`, `testresources` removed as
  dependencies; the `maastesting` modules that exist only to serve them
  deleted.
- Per-package branch coverage is **at or above** the pre-migration
  baseline, measured by `coverage.py`.
- No compatibility machinery built to outlive Django/Twisted removal.

## Possible Directions

### Direction A: Coverage-gated tiered cutover, package by package (CHOSEN)

- **Description:** Capture a per-package branch-coverage baseline first
  using the existing `utilities/run-tests-coverage` layout. Then, per
  package in dependency order (`provisioningserver` → `metadataserver`
  → `maasserver`): mechanically `git mv` its tests into
  `src/tests/<pkg>/...`; land the **easy tier** (147 files needing no
  hard feature) essentially as-is; triage the **hard tier** (349 files)
  per file into *port-simply* (small fixture rewrite),
  *delete-as-duplicated* (coverage already supplied elsewhere), or
  *port-with-small-conftest*; drop the package from the nose runner once
  its pytest-only branch coverage meets or exceeds baseline. After the
  last package, delete the nose/testtools machinery and dependencies.
- **Pros:** The coverage gate makes deletion measurable and safe rather
  than a judgement call. Easy tier is empirically proven to need zero
  machinery. Each package is independently shippable and revertable.
  Builds no plugin for soon-to-be-deleted code. Directly honours all
  four of the idea's framing constraints.
- **Cons:** Requires a trustworthy per-package coverage baseline before
  work starts. Hard-tier triage needs real per-file judgement and is the
  bulk of the effort.
- **Risks:** Branch coverage can hold while a *behavioural* edge case is
  silently lost — a scenario-multiplied test deleted in favour of a
  single-path equivalent keeps the lines green but tests less. Accepted
  under the chosen gate; mitigate by requiring scenario-derived
  deletions to be justified against an existing equivalent.

### Direction B: Big-bang relocate, then fix

- **Description:** Move all 496 files into `src/tests/` in one commit,
  run everything, fix the fallout.
- **Pros:** One disruptive rebase for the team rather than three; the
  split layout ends immediately.
- **Cons:** Produces one enormous red suite with no incremental gate;
  coverage regressions become unattributable to a package or a file.
- **Risks:** High — this is the failure mode the F03 attempt already hit,
  reproduced at roughly four times the scale.

### Direction C: Hybrid shim for the hard tier

- **Description:** Direction A, but instead of triaging the hard tier
  into port/delete, build one small `conftest.py`-level shim providing
  scenarios, `testresources` reuse, and reactor/crochet setup.
- **Pros:** Minimises test loss; nothing has to be deleted or judged.
- **Cons:** It is a smaller rebuild of precisely the F02/F03 plugin that
  already consumed two features and landed no code — built for Django/
  Twisted-coupled tests with a ~1-year life.
- **Risks:** Rediscovering idea 002's `MAAS_PREVENT_MIGRATIONS`
  process-global settings-mode conflict, which no per-test or
  per-fixture fix can reconcile within one pytest worker process.

## Decisions Taken During Exploration

- **D-001 — Coverage gate:** "Keep coverage the same" means **line/branch
  coverage percentage per package, measured by `coverage.py`**, baseline
  captured before migration. This is what licenses deleting redundant
  legacy tests.
- **D-002 — Hard-tier policy:** Delete hard-to-port tests whose coverage
  is already duplicated; port the rest simply. Do **not** keep nose alive
  for a residue, and do **not** build shims for deprecated code.
- **D-003 — Relocation policy:** Relocate in bulk per package,
  mechanically (`git mv` into the mirrored layout), then modernize to
  fixtures opportunistically. Decouples *where tests live* from *how they
  are written*, keeping move commits reviewable.

## Open Questions

- Does the per-package coverage baseline need to be captured on CI
  hardware to be trustworthy, or is a local `utilities/run-tests-coverage`
  run sufficient? (`bin/test.region` currently requires a built
  `src/maasopenfga/build/maas-openfga-migrator`, so a local full baseline
  has a prerequisite.)
- Should `pytest-django` be adopted, or is the existing hand-rolled
  `maastesting/pytest/django.py` sufficient for the Django-DB tier given
  Django's planned removal? (A mature-dependency question the idea's
  framing explicitly invites.)
- What is the per-package ordering rationale — is `provisioningserver`
  (129 files, Twisted-heavy, no Django) really the best pilot, or is
  `metadataserver` (23 files) a cheaper first proof?
- How is the undeclared `nose` dependency handled in the interim — add it
  explicitly to `optional-dependencies.testing` so CI is honest until it
  is removed, or accept the ambient install for the duration?
- For scenario-multiplied classes that are kept, is `pytest.mark.
  parametrize` the target form, and who adjudicates "coverage already
  duplicated" when deleting?

## Constraints

- **Timeline:** No fixed deadline, but bounded by Django/Twisted removal
  (~1 year); solutions must not assume a longer payback window.
- **Budget:** N/A.
- **Technology:** All tests under `src/tests/` following the existing
  mirroring convention. Prefer pytest fixtures and modern pytest
  features. Mature third-party pytest plugins are acceptable new
  dependencies. End state must have no `nose`, `testtools`,
  `testscenarios`, or `testresources`.
- **Team:** Per-package CI gate — a package's pytest-only run must meet
  or exceed its coverage baseline before the next package starts.
- **Existing product constraints:** FIPS 140-2/140-3 and STIG/CIS
  hardening compliance must not break (test-infra-only change, but
  `src/tests/maascommon/test_fips.py` and
  `src/tests/provisioningserver/test_certificates_fips.py` exist and must
  keep running). Conventional Commits; 79-char Python lines; Ruff.

## Signals of Value

- Removes an **undeclared, unmaintained** dependency (`nose`) that the
  merge gate currently relies on ambiently.
- Halves the CI test surface: one runner instead of two parallel legs.
- Deletes a large volume of bespoke `maastesting` runner machinery
  (`noseplug.py`, `djangoloader.py`, `parallel.py`, `scenarios.py`,
  `runtest.py`, nose entry points in `scripts.py`) rather than porting
  it.
- Easy tier is proven to require zero new code — 361 legacy tests passed
  unmodified under stock pytest during this exploration.
- Converges the two test layouts onto the one already declared by
  `testpaths`.

## Recommendation

- [ ] Drop
- [ ] Keep exploring
- [x] Create PLAN
- [ ] Create REQUIREMENTS directly

**Reason:** Multi-package, multi-phase work with a per-package coverage
gate and an explicit dependency ordering — exactly what PLAN exists to
map. The new PLAN **supersedes** the current `.ai/sdd/PLAN.md`, whose
F01–F07 feature map is built on the abandoned plugin-first approach and
references code that was never committed.
