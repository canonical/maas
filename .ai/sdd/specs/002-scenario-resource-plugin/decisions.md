# Decisions: Scenario/resource pytest plugin (F02)

## Resource-reuse/xdist-locality finding (US-004/NFR-002)

**Context:** Nose's `OptimisingTestSuite` reorders tests to reuse
shared `testresources` resources across adjacent tests (reset instead
of full teardown+rebuild) when running under `test.region`/`test.rack`.
Plain pytest collection has no equivalent mechanism, and `pytest-xdist`
distributes items across separate worker processes.

**Finding (evidence gathered in T3/T7):**

- **No suite-level reuse under plain pytest.** T3's build-counting
  resource manager recorded `build_count=2` for 2 tests sharing one
  resource — a full build+clean cycle per test, 0% reuse. `manager._uses
  == 0` after the run confirms teardown (`finishedWith`) still runs
  correctly; this is a performance characteristic, not a correctness
  gap.
- **xdist multiplies this per worker, by construction, not by
  scheduling chance.** T7 ran the T2/T4 fixtures under
  `bin/pytest -n 2 --dist=load`: scenario-expanded items split across
  `gw0`/`gw1` (e.g. `test_value_matches_scenario[two]` failed on gw0,
  `[one]`/`[three]` passed on gw1/gw0), each reporting its correct
  individual outcome. Each `pytest-xdist` worker is a separate OS
  process with its own class-level resource-manager state (no shared
  memory) — resource reuse **cannot** cross worker boundaries under any
  distribution strategy. This is a deterministic, structural property
  of plain-pytest + xdist collection, not a probabilistic "might get
  scattered" risk.

**Decision:** Per D-001 in `requirements.md`, F02's guarantee is
correctness only. This finding is accepted as a known, documented
performance characteristic; no fix is attempted in F02.

**F03 implication:** When a real module with expensive resources (e.g.
`DjangoDatabasesManager`, `DatabaseClusterManager`) migrates, expect
resource build/teardown overhead per test and per worker that nose's
current CI run does not pay today. F03 should account for this in its
own performance baseline rather than discover it in CI.

**Source:** Design-phase spike (recorded in `design.md` §3/§11),
confirmed with concrete evidence during `/skill:sdd-exec` T3/T7.

**Impacts:** `design.md` §11 Observability/Operations, §14 Risks;
`requirements.md` D-001; `.ai/sdd/PLAN.md` F03 planning (performance
expectations).

## F02 scope confirmation — nose remains untouched

**Decision:** F02 does not modify, disable, or remove `nose`,
`test.parallel`, `maastesting/noseplug.py`'s `Scenarios`/`Resources`
plugins, `maastesting/scenarios.py`'s `WithScenarios`, or
`maasserver/testing/resources.py`'s resource manager classes. The new
`maastesting/pytest/scenarios.py` plugin is additive: it only activates
for pytest-collected test classes with a non-empty `scenarios`
attribute; nose's own path keeps working exactly as today.

**Reason:** Consistent with F01's D-001 scope-clarification pattern and
`requirements.md`'s explicit Out of Scope ("Removing `nose`... that is
F07").

**Source:** `requirements.md` Non-Goals/Out of Scope, confirmed
unchanged by implementation (no edits to `maastesting/noseplug.py`,
`maastesting/scenarios.py`, or `maasserver/testing/resources.py` during
`/skill:sdd-exec`).

**Impacts:** `.ai/sdd/PLAN.md` F02 row (read in conjunction with this
note), `requirements.md` Out of Scope.

## Recorded verification evidence (F02 tasks T1–T7)

- **T1:** `maastesting/pytest/scenarios.py` created; `maas-scenarios`
  `pytest11` entry point registered and confirmed active via
  `--trace-config` with no conftest/opt-in. Collected 53 tests from
  `test_config.py`, 0 errors.
- **T2:** Synthetic 3-scenario fixture — 3 distinct nodeids, 1 isolated
  failure (`test_value_matches_scenario[two]`), 2 passed
  (`[one]`/`[three]`); both scenario variants of the `@skip`-decorated
  method reported `SKIPPED` independently. Result: `1 failed, 2 passed,
  3 skipped`.
- **T3:** Resource-only fixture, 2 tests sharing one resource — both
  passed, `build_count=2` (0% reuse, 1 build per test), `_uses=0` after
  run (correct teardown, no leak).
- **T4:** Combined scenario+resource fixture, 2 scenarios — both
  passed with correct scenario value and resource attachment.
- **T5:** Real-file validation — `test_config.py` (53 tests): nose
  baseline `Ran 53 tests in 1.547s — OK`; pytest with the new plugin
  `53 passed, 8 warnings in 2.60s`. Counts match exactly.
  `git status --short` on the test file: empty (zero source changes).
- **T6:** Repeat of T5's pytest run — `53 passed` both times, identical
  collected/passed/failed/skipped counts. No flakiness.
- **T7:** `-n 2 --dist=load` run of T2/T4 fixtures — both `gw0`/`gw1`
  exercised, each scenario-expanded item reported its correct outcome
  regardless of worker assignment (`1 failed, 4 passed, 3 skipped`,
  matching single-worker counts). See resource-reuse finding above for
  the cross-worker implication.
