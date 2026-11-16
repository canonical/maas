# Idea: Migrate nose-based tests to pytest

> Status: exploring
> Created: 2026-11-13

## Raw Idea

Get rid of nose tests, moving all to pytest.

## Problem Space

- `nose` is still the actual test runner for region (`test.region`, `src/maasserver` + `src/metadataserver`)
  and rack (`test.rack`, `src/provisioningserver`) suites, via `maastesting.noseplug`
  (wraps `nose.core.TestProgram`).
- `test.region.legacy` uses Django's test command but still carries nose-style flags
  (`--with-crochet`, `--with-scenarios`) for legacy-tagged tests.
- `test.parallel` orchestrates nose-based parallel test execution (`maastesting/parallel.py`).
- Direct nose coupling also found in: `maastesting/noseplug.py`, `maastesting/djangoloader.py`,
  `maastesting/scenarios.py`, `maastesting/testcase.py`, `maasserver/concurrency.py`,
  `maasserver/djangosettings/development.py`, `maasserver/forms/tests/test_machine.py`,
  `provisioningserver/logger/_logging.py`, and nose-plugin-specific tests
  (`tests/maastesting/test_noseplug.py`, `test_factory.py`).
- `Makefile` still manages `.noseids` (nose's test-id cache).
- `testscenarios`/`testresources` (`OptimisingTestSuite`) are used heavily across the suite for
  scenario-based test classes; this behavior has no stock pytest equivalent.
- pytest is already partially wired: `pyproject.toml` registers `pytest11` entry points
  (`maas-database`, `maas-django`, `maas-environment`, `maas-perftest`, `maas-seeds`,
  `maas-sqlalchemy`), and `pytest-xdist` is already a test dependency.

## Target Users

- MAAS engineers writing/running region and rack test suites.
- CI maintainers responsible for test suite runtime and reliability.

## Current Alternatives

- Today: nose (region, rack, parallel) + Django test command with nose flags (region legacy).
- Already partial pytest adoption for some v3/service-layer-adjacent suites via `pytest11` plugins.

## Desired Outcome

- Single pytest-based entrypoint for all region, rack, and legacy-tagged test suites.
- Parallel test execution via `pytest-xdist` instead of nose-based `test.parallel`.
- `testscenarios`/`testresources` scenario-based tests continue to work equivalently under pytest
  (via a dedicated `maastesting.pytest` plugin, following the existing `maas-django`/
  `maas-sqlalchemy` plugin pattern).
- `nose` dependency, `maastesting/noseplug.py`, and `.noseids` artifacts fully retired.

## Possible Directions

### Direction A: Module-by-module migration, building scenario plugin support as needed per module

- **Description:** Migrate `maasserver` first, then `metadataserver`, then `provisioningserver`,
  then legacy-tagged tests; build pytest scenario/resource support incrementally per module.
- **Pros:** Immediate, visible per-module progress from day one.
- **Cons:** Risks rediscovering the scenario/resource-ordering problem in every module; duplicated
  plugin-design effort.
- **Risks:** `OptimisingTestSuite` resource-setup ordering could be reinvented inconsistently
  across modules.

### Direction B: Rewrite scenario-based tests as plain pytest parametrize/fixtures

- **Description:** Instead of porting the nose scenario/resource runner, rewrite scenario-based
  test classes to idiomatic pytest parametrize/fixtures during migration.
- **Pros:** No custom plugin to build or maintain; ends on fully idiomatic pytest.
- **Cons:** Large rewrite surface across the whole suite; loses `testresources`
  `OptimisingTestSuite` setup/teardown optimization unless reimplemented per-test.
- **Risks:** Explicitly rejected — must preserve scenario-based tests as-is, not rewrite.

### Direction C: Infra first (pytest-xdist + scenario/resource plugin), then module-by-module migration

- **Description:** Build the pytest foundation first — `pytest-xdist` parallel execution and a
  `maastesting.pytest` scenario/resource plugin preserving `testscenarios`/`testresources`
  semantics — then migrate `maasserver` → `metadataserver` → `provisioningserver` →
  legacy-tagged tests, each gated green in CI before the next starts.
- **Pros:** De-risks the scenario/xdist interaction once, centrally, instead of per module;
  each subsequent module migration reuses proven infra.
- **Cons:** Delays first visible module-level progress until infra lands.
- **Risks:** `pytest-xdist` worker distribution can defeat `OptimisingTestSuite`'s resource-locality
  optimization (tests sharing expensive resources get scattered across workers) — needs validation
  before scaling to all modules.

## Open Questions

- How should `pytest-xdist` worker distribution interact with `testresources`
  `OptimisingTestSuite` resource-locality optimization? (needs a design spike in Phase 1)
- Exact scope/shape of the `maastesting.pytest` scenario/resource plugin API.

## Constraints

- Timeline: no fixed deadline, done opportunistically.
- Budget: N/A.
- Technology: must preserve `testscenarios`/`testresources` scenario-based test behavior;
  parallel execution must use `pytest-xdist` (already a test dependency).
- Team: per-module CI gate required — each module's pytest migration must be green in CI
  before the next module starts.
- Existing product constraints: FIPS/STIG/CIS hardening compliance must not be affected
  (test-infra-only change, but verify no coupling).

## Signals of Value

- Single, consistent test runner reduces onboarding friction and CI configuration surface.
- Removes a legacy dependency (`nose`, unmaintained) and the associated `.noseids` cache file.
- Aligns test infra with the rest of the pytest-based v3 API/service-layer stack already in repo.

## Recommendation

- [ ] Drop
- [ ] Keep exploring
- [x] Create PLAN
- [ ] Create REQUIREMENTS directly

**Reason:** Multi-phase, multi-module migration (infra phase + 4 module phases) with per-phase
CI gating — fits PLAN's purpose of mapping phases/dependencies before per-phase requirements.
Direction C selected as the committed direction.
