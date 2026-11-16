# SDD Index

## Upstream Handoffs

- `.ai/strategy/handoff/strategy-brief.md`: missing

## Plan

- `.ai/sdd/PLAN.md`: **approved** (2026-11-16) — "Coverage-gated pytest
  cutover", F01-F10, from `ideas/003-coverage-gated-pytest-cutover.md`.
  Replaced the previous plugin-first F01-F07 map, which was abandoned with
  no code landed (old content recoverable at commit `a95f0c7f9`).

> **Note:** this plan's F01-F10 IDs are a new sequence. They do **not**
> correspond to the old plan's F01-F07, nor to the existing spec directories
> `001`-`003`, which belong to the abandoned approach.

## Ideas

| ID | Name | Status | Path |
|----|------|--------|------|
| 001 | Nose to pytest migration | idea:captured | `.ai/sdd/ideas/001-nose-to-pytest-migration.md` |
| 002 | Legacy-tagged tests under pytest | idea:captured | `.ai/sdd/ideas/002-legacy-tests-under-pytest.md` |
| 003 | Coverage-gated pytest cutover (supersedes 001/002 approach) | idea:captured | `.ai/sdd/ideas/003-coverage-gated-pytest-cutover.md` |
| 004 | `provisioningserver` `MAASTwistedRunTest` carve-out follow-up | idea:captured | `.ai/sdd/ideas/004-provisioningserver-twisted-reactor-carveout.md` |
| 005 | Nose-retirement carve-out closures (002+004 together) | idea:exploring | `.ai/sdd/ideas/005-nose-retirement-carveout-closures.md` |

## Feature Workspace

> Numbering source: actual directories under `.ai/sdd/specs/`, not this index.

| Field | Value | Notes |
|-------|-------|-------|
| Next Feature ID | 011 | Recompute from filesystem before creating a new spec |
| Numbering Issues | none | duplicate prefix / invalid status / non-canonical directory |

## Specs

> **Status correction (2026-11-16):** the F01-F03 implementation is **not
> present in the working tree**. Branch `nuke_nose` holds one commit
> (`27312b388`) touching only `.gitignore`; there is no
> `maastesting/pytest/region.py`, no `maastesting/pytest/scenarios.py`, and
> no `maas-region`/`maas-scenarios` `pytest11` entry point. The statuses
> below record artifact/approval state only, not landed code.

| ID | Feature | Status | Requirements | Design | Tasks | Review |
|----|---------|--------|--------------|--------|-------|--------|
| 001 | pytest-xdist parallel infra (F01) | review:done (specs only; no code in tree) | [requirements.md](specs/001-pytest-xdist-parallel/requirements.md) | [design.md](specs/001-pytest-xdist-parallel/design.md) | [tasks.md](specs/001-pytest-xdist-parallel/tasks.md) | [review.md](specs/001-pytest-xdist-parallel/review.md) |
| 002 | Scenario/resource pytest plugin (F02) | review:done (specs only; plugin absent from tree) | [requirements.md](specs/002-scenario-resource-plugin/requirements.md) | [design.md](specs/002-scenario-resource-plugin/design.md) | [tasks.md](specs/002-scenario-resource-plugin/tasks.md) | [review.md](specs/002-scenario-resource-plugin/review.md) |
| 003 | Migrate maasserver tests (F03) | abandoned (no code landed; superseded by idea 003) | [requirements.md](specs/003-migrate-maasserver-tests/requirements.md) | [design.md](specs/003-migrate-maasserver-tests/design.md) | [tasks.md](specs/003-migrate-maasserver-tests/tasks.md) | - |
| 004 | Coverage baseline harness (plan F01) | review:done | [requirements.md](specs/004-coverage-baseline-harness/requirements.md) | [design.md](specs/004-coverage-baseline-harness/design.md) | [tasks.md](specs/004-coverage-baseline-harness/tasks.md) | [review.md](specs/004-coverage-baseline-harness/review.md) |
| 005 | Declare `nose` dependency (plan F02) | implementation:done | [requirements.md](specs/005-declare-nose-dependency/requirements.md) | [design.md](specs/005-declare-nose-dependency/design.md) | [tasks.md](specs/005-declare-nose-dependency/tasks.md) | - |
| 006 | Minimal gap shims (plan F03) | review:approved | [requirements.md](specs/006-minimal-gap-shims/requirements.md) | [design.md](specs/006-minimal-gap-shims/design.md) | [tasks.md](specs/006-minimal-gap-shims/tasks.md) | [review.md](specs/006-minimal-gap-shims/review.md) |
| 007 | `metadataserver` pilot cutover (plan F04) | implementation:done | [requirements.md](specs/007-metadataserver-pilot-cutover/requirements.md) | [design.md](specs/007-metadataserver-pilot-cutover/design.md) | [tasks.md](specs/007-metadataserver-pilot-cutover/tasks.md) | - |
| 008 | `provisioningserver` cutover (plan F05) | implementation:done | [requirements.md](specs/008-provisioningserver-cutover/requirements.md) | [design.md](specs/008-provisioningserver-cutover/design.md) | [tasks.md](specs/008-provisioningserver-cutover/tasks.md) | - |
| 009 | `maasserver` cutover (plan F06) | implementation:done | [requirements.md](specs/009-maasserver-cutover/requirements.md) | [design.md](specs/009-maasserver-cutover/design.md) | [tasks.md](specs/009-maasserver-cutover/tasks.md) | - |
| 010 | Dedicated pytest legs to close nose carve-outs | implementation:done | [requirements.md](specs/010-dedicated-pytest-legs/requirements.md) | [design.md](specs/010-dedicated-pytest-legs/design.md) | [tasks.md](specs/010-dedicated-pytest-legs/tasks.md) | - |

## Handoff

- `.ai/sdd/handoff/sdd-brief.md`: refreshed (007 `metadataserver`
  pilot cutover / plan F04, implementation:in-progress — T1-T3
  executed (2 implementation-time corrections found and fixed: TD-004
  reactor thread-pool gap, TD-005 `test_fields.py` mixed-class split);
  T4-T5 pending). Previous brief covered 006 Minimal gap shims (F03,
  review:approved, Ready for Release).

## Next Actions

- [x] Capture first idea with `/skill:sdd-idea`
- [x] Create a plan with `/skill:sdd-plan` (approved: `.ai/sdd/PLAN.md`)
- [x] Create requirements for F01 (approved: `specs/001-pytest-xdist-parallel/requirements.md`)
- [x] Create design for F01 (approved: `specs/001-pytest-xdist-parallel/design.md`)
- [x] Create tasks for F01 (approved: `specs/001-pytest-xdist-parallel/tasks.md`)
- [x] T1: Confirm single source of truth for worker-count config — PASS
- [x] T2: Execute baseline validation run against src/tests — PASS (2 pre-existing unrelated failures documented; 209.89s, 7949 tests)
- [x] T3: Verify concurrency override behavior — PASS (gw0/gw1 only, no gw2+)
- [x] T4: Verify JUnit XML structural correctness — PASS (7949 testcases match tests attribute)
- [x] T5: Reliability check — PASS (identical 7766/2/181 counts across both runs)
- [x] T6: Record performance baseline and scope note — PASS (design.md §11, decisions.md created)
- [x] Run `/skill:sdd-review` against F01 implementation — Approved with follow-ups
- [x] Create requirements for F02 (scenario/resource pytest plugin) with `/skill:sdd-prd` — approved: `specs/002-scenario-resource-plugin/requirements.md`
- [x] Create design for F02 (approved: `specs/002-scenario-resource-plugin/design.md`) with `/skill:sdd-spec`
- [x] Create tasks for F02 with `/skill:sdd-tasks` — approved: `specs/002-scenario-resource-plugin/tasks.md`
- [x] Execute F02 tasks T1-T8 (`/skill:sdd-exec`) — all done. T1: plugin + entry point, confirmed via `--trace-config` + 53/53 collection match. T2: 3-scenario synthetic fixture, 1 isolated failure, skip handled per-scenario. T3: resource lifecycle no-regression (build_count=2, uses=0 after teardown). T4: combined scenario+resource, both pass. T5: real-file validation — nose 53 ok vs pytest 53 passed, zero source changes. T6: repeat run, identical counts. T7: xdist `-n 2 --dist=load`, gw0/gw1 both exercised, correct outcomes. T8: `decisions.md` created, cross-referenced from design.md §11.
- [x] Run `/skill:sdd-review` against F02 implementation — Approved (1 Low-severity, non-blocking follow-up: `CountingResourceManager` duplication across fixture files)
- [x] Plan F03 (first real nose module migration) with `/skill:sdd-prd` — approved: `specs/003-migrate-maasserver-tests/requirements.md`
- [x] Create design for F03 with `/skill:sdd-spec` — approved: `specs/003-migrate-maasserver-tests/design.md`. Design-phase spikes found 2 gaps beyond F02's plugin, both verified and folded back into `requirements.md` (amended with approval): FR-006/D-004 resource-reuse mechanism (nose's `OptimisingTestSuite` equivalent, measured ~0.4s/test tax across 260 files without it) and FR-007/D-005 reactor/crochet/thread-pool setup (real `deferToDatabase` file failed 3/4 under plain pytest, fixed to 4/4). New `maastesting/pytest/region.py` plugin covers both.
- [x] Create tasks for F03 with `/skill:sdd-tasks` — draft: `specs/003-migrate-maasserver-tests/tasks.md`, 10 tasks (T1-T10), all 6 Must Have FRs covered. Awaiting approval.
- [x] Approve F03 tasks (`specs/003-migrate-maasserver-tests/tasks.md`)
- [x] Execute F03 T1: `maastesting/pytest/region.py` created + `maas-region` entry point registered. `--trace-config` confirms registration; `make lint` exit 0.
- [x] Execute F03 T2: resource-reuse build-count verified — single-worker `{'pristine_build': 1, 'db_build': 5}` across 75 tests (3 mixed files); xdist 2-worker: `{'pristine_build': 1}` on each of gw0/gw1. 75/75 passed both modes.
- [x] Execute F03 T3: reactor/crochet fix verified against 5 real `deferToDatabase` files (`test_security.py` + 4 others) — pytest 69 passed vs. nose 69 (4+11+9+3+42), 0 failures either way, zero source changes.
- [~] F03 T4-T10 — **halted, superseded.** The F01-F03 work described above is
  not present in the working tree (see Specs status correction). Approach
  abandoned after ideas 001/002 hit three compounding incompatibilities.
- [x] Capture idea 003 (coverage-gated pytest cutover) with `/skill:sdd-idea`
  — `.ai/sdd/ideas/003-coverage-gated-pytest-cutover.md`, Direction A chosen
- [x] Create a replacement PLAN with `/skill:sdd-plan` from idea 003 —
  **approved**: `.ai/sdd/PLAN.md` (F01-F10, coverage-gated cutover)
- [x] Create requirements for F01 (coverage baseline harness) with
  `/skill:sdd-prd` — **approved**: `specs/004-coverage-baseline-harness/requirements.md`.
  Resolved during drafting: `maas-openfga-migrator` is now built and
  `bin/test.region` runs; `utilities/run-tests-coverage`'s mechanism
  verified end-to-end (real coverage.py report produced). 5 decisions
  recorded (D-001-D-005): local baseline capture, migration-duration
  manual tool (not a permanent CI gate), 1.0pp tolerance, reviewer-
  verified deletion mapping, per-package (not repo-wide) attribution.
- [x] Create design for F01 with `/skill:sdd-spec` — **approved**:
  `specs/004-coverage-baseline-harness/design.md`. One script
  (`utilities/coverage-baseline`, `capture`/`check` subcommands), three
  committed JSON baselines (`utilities/coverage-baselines/`). Key
  mechanism verified live: `coverage json --include=src/<pkg>/*` on one
  combined (pytest+nose) data file correctly isolates per-package
  totals; nose's `run_region()` has no metadataserver-only/maasserver-
  only mode, so metadataserver and maasserver share a nose invocation
  and rely on report-time filtering (TD-002). `bin/test.region.legacy`
  excluded — zero `DjangoTestCase` subclasses exist today.
- [x] Create tasks for F01 with `/skill:sdd-tasks` — **approved**:
  `specs/004-coverage-baseline-harness/tasks.md`. 5 tasks (T1-T5), all 6
  Must Have FRs covered, readiness check all Pass, 0 open questions.
  `.ai/sdd/handoff/sdd-brief.md` refreshed, ready for implementation.
- [x] Execute F01 tasks T1-T5 with `/skill:sdd-exec` — all done. T1-T4
  verified via `make lint` + direct manual exercise of each function/
  subcommand. T5: all three real baselines captured
  (provisioningserver 94.91%, metadataserver 95.05%, maasserver
  96.01%), two-pass stability spreads all <0.15pp (vs 1.0pp tolerance),
  `check` round-trip confirmed correct (FAIL expected pre-cutover —
  mechanism verified, not a bug), independent `coverage report`
  cross-check matches exactly.
- [x] Run `/skill:sdd-review` against F01 implementation — **Approved
  with follow-ups**: `specs/004-coverage-baseline-harness/review.md`.
  One Low-severity follow-up: baseline files `git add`-staged but not
  yet committed (FR-006/T5 AC says "committed").
- [x] Commit the staged `utilities/coverage-baseline` +
  `utilities/coverage-baselines/*` files (closes review Issue 1) —
  committed at `4aee6a4e1`; review verdict updated to **Approved**
  (no remaining follow-ups blocking release)
- [x] Plan F02 (declare `nose` dependency) and F03 (minimal gap shims)
  with `/skill:sdd-prd` — both **approved**:
  `specs/005-declare-nose-dependency/requirements.md` (1 FR, 1
  decision: `nose>=1.3,<1.4` range pin matching sibling legacy deps) and
  `specs/006-minimal-gap-shims/requirements.md` (4 FRs, 3 decisions —
  notably D-002: reconsidered away from `pytest-cases` after it was
  found to require rewriting ~89 files, conflicting with `PLAN.md`'s
  hard F03 scope rule; settled on a hand-rolled conftest hook reusing
  `testscenarios`' own `generate_scenarios()` helper instead).
- [x] Create design + tasks for F02 with `/skill:sdd-spec`/`/skill:sdd-tasks`
  and implement with `/skill:sdd-exec`: `pyproject.toml` declares
  `nose>=1.3,<1.4` (T1); `maastesting/noseplug.py` gained a Python
  version compat shim (T2) after T1's own verification reproduced a
  live regression — vanilla PyPI `nose==1.3.7` breaks on Python 3.14
  (`_TextTestResult`, removed) and on any Python since 3.10
  (`collections.Callable`, removed) — both undocumented-ly patched
  away by this repo's system `python3-nose` package, now fixed
  explicitly and portably (requirements D-002/D-003, design TD-002).
  Verified: `make lint`/`ruff` pass; `.ve/bin/test.rack` full suite
  (3533 tests, OK) passes both with vanilla PyPI `nose` force-installed
  and with the ambient system package restored afterward.
- [x] Create design + tasks for F03 with `/skill:sdd-spec`/`/skill:sdd-tasks`
  — both **approved**: `specs/006-minimal-gap-shims/design.md` (new
  `maastesting/pytest/legacy.py` plugin: class-level scenario
  multiplication + shared session-scoped `setup_crochet()` reactor
  fixture; one-line `or {}` guard in `maasserver/testing/api.py`) and
  `specs/006-minimal-gap-shims/tasks.md` (5 tasks: T1 shared crochet
  helper, T2 scenario+reactor plugin, T3 `APITestCase` fix, T4
  cross-tier integration check, T5 full-suite regression +
  scope-discipline sign-off).
- [x] Execute F03 tasks T1-T5 with `/skill:sdd-exec` — all done. T1:
  `maastesting/crochet.py` shared `Crochet.configure()` refactor,
  zero behavior change (confirmed via full regression below). T2:
  `maastesting/pytest/legacy.py` created (`maas-legacy` entry point);
  two real in-mechanism gaps found and fixed during verification
  (scenario merging happens in `APITestCaseBase.__init__`, not as a
  visible class attribute — fixed via throwaway-instance read; plain
  function scenario values bind as methods when set at class level via
  `setattr` — fixed via `staticmethod()` wrap). T3: one-line `or {}`
  guard in `maasserver/testing/api.py`. T4: 32 tests across 5 files
  pass together in one session; gap-free spot-checks (`test_vlan.py`,
  `test_eventloop.py`, `test_proxyconfig.py`) show zero behavior
  change; reactor confirmed single-shot. T5: full `nose` regression —
  `test.rack` 3533 tests OK (exact baseline match), `test.region`
  13013 tests OK (SKIP=11), zero failures; no fourth gap found.
- [x] Run `/skill:sdd-review` against F03 implementation — **Approved**:
  `specs/006-minimal-gap-shims/review.md`. All 4 FRs and both NFRs
  verified with exact-match evidence against `nose`'s own counts; no
  issues found.
- [x] F04 (`metadataserver` pilot cutover) unblocked: F01 (coverage
  baseline), F02 (`nose` dependency declared), and F03 (minimal gap
  shims) have all landed per `PLAN.md`'s dependency graph.
- [x] Create requirements for F04 with `/skill:sdd-prd` — **approved**:
  `specs/007-metadataserver-pilot-cutover/requirements.md`. Corrected
  `PLAN.md`'s gap-tier estimate via direct recount (D-001): 5
  gap-touching files (not 9), 18 gap-free (file/test-def totals of 23/
  927 confirmed matching `PLAN.md` exactly). Confirmed two pre-existing
  narrow pytest-native files under `src/tests/metadataserver/` are
  unrelated to this migration and do not shortcut triage of their
  legacy counterparts (D-002). Deferred `pytest-django` adoption,
  unchanged from `PLAN.md`'s open decision (D-003).
- [x] Create design for F04 with `/skill:sdd-spec` — **approved**:
  `specs/007-metadataserver-pilot-cutover/design.md`. Complete 23-file
  disposition table (zero deletions — no duplicate coverage found
  during design-time triage); no new F03 shim work needed. Two
  relocation-specific hazards found and resolved by direct
  reproduction: a path collision with a pre-existing unrelated test
  file (`test_hooks.py`, resolved as a merge, TD-002) and a
  `sys.path`-dependent `snippets` package import affecting 4 files
  (TD-003) — confirmed empirically that 2 fix via dotted-import
  rewrite and 2 need a scoped `conftest.py` because their *production*
  modules (not just the test files) contain their own internal
  `snippets`-relative fallback import.
- [x] Create tasks for F04 with `/skill:sdd-tasks` — **approved**:
  `specs/007-metadataserver-pilot-cutover/tasks.md`. 5 tasks (T1-T5),
  all Must Haves covered, readiness check all Pass, 0 open questions.
- [x] Execute F04 T1-T3 with `/skill:sdd-exec` — 22 of 23 files
  relocated to `src/tests/metadataserver/` (T1: 17 gap-free + merged
  `test_hooks.py`; T2: 4 gap-touching; T3: 4 path-import-hazard files,
  2 dotted-import fix + 2 `conftest.py` fix). Two implementation-time
  gaps found during T2/T1 verification, both fixed and folded back
  into `design.md`/`tasks.md` (TD-004/TD-005): (1) F03's
  `_crochet_reactor` fixture never installed the reactor's database
  thread-pool, so `test_api_twisted.py`'s `deferToDatabase` tests
  failed 41/50 — fixed by extending the fixture to mirror
  `run_region_legacy()`'s own setup, now 50/50; (2)
  `test_fields.py` mixed a gap-free class (`TestBin`) with a
  `legacy`-tagged class (`TestBinaryField`) that F03 already scoped
  out — misclassified as fully gap-free in design's original triage,
  fixed by splitting the file: `TestBin` relocates, `TestBinaryField`
  stays at the original path under `nose`'s
  `run_region_legacy()`. Corrected count: `bin/test.region`'s expected
  drop is 918, not 927 (`TestBinaryField`'s 9 tests were already
  excluded from `run_region()`'s own `-a !legacy` count).
- [x] Execute F04 T4 (confirm `nose` drop, verify count = 12095) + T5
  (coverage check + full regression sign-off) with `/skill:sdd-exec`
  — both done. T4: `metadataserver` fully dropped from `nose` (0 test
  files remain under `src/metadataserver/*`); `bin/test.region` runs
  clean post-drop. T5: ran all 4 verification commands; found and
  fixed one more implementation-time gap (TD-006) - 3 `maasserver`
  test files importing a helper from the now-relocated
  `metadataserver.builtin_scripts.tests.test_hooks` path, repointed to
  `tests.metadataserver.builtin_scripts.test_hooks` (also needed an
  import-policy allowlist addition in `utilities/check-imports`).
  Root-caused and documented (D-004/TD-007) FR-004's expected,
  structural coverage-check `FAIL` (89.15% vs. 95.05% baseline,
  -5.90pp): fully attributable to TD-005's `TestBinaryField` split
  (kept under `nose`, out of scope per idea 002) being the sole
  exerciser of 3 `metadataserver` production modules - accepted as a
  documented exception, not a regression, per direct user instruction.
  Also found and fixed (TD-008, per direct user instruction) a
  pre-existing, repo-wide `nose`/Python 3.14 import incompatibility in
  `maastesting/testcase.py` (confirmed reproducing identically at HEAD
  before any F04 change) that blocked T5's own "full `pytest
  src/tests` passes" criterion; fixed via a new shared
  `maastesting/_nose_compat.py`, mirroring `noseplug.py`'s own
  existing shim. Final measured results: full `pytest src/tests` -
  8741/8754 passed (3 pre-existing, unrelated failures), 0 collection
  errors (was 45 repo-wide before TD-008); `bin/test.rack` - 3533
  tests, 14 pre-existing/environment-only `setpgrp` permission errors
  (sandbox limitation, confirmed unrelated); `make lint` - clean. F04
  status: **implementation:done**.
- [x] Create requirements for F05 (`provisioningserver` cutover) with
  `/skill:sdd-prd` — **approved**:
  `specs/008-provisioningserver-cutover/requirements.md`. Recounted
  directly against the live tree (D-001): 129 files (exact match to
  `PLAN.md`), 57 gap-touching/72 gap-free (off-by-one from `PLAN.md`'s
  58/71 estimate, same drift pattern F04 hit). Confirmed zero Django/
  `APITestCase`/`legacy=True` coupling — the third F03 gap and idea
  002's nose carve-out do not apply to this package. New FR-003 (not
  present in F04): 11 FIPS/hardening-related files, 4 also
  gap-touching, must never be resolved via delete-as-duplicate.
  Flagged a `test_utils.py` basename collision across 3 legacy
  subdirectories + 1 pre-existing pytest-native file as a design-time
  question (FR-006).
- [x] Create design for F05 with `/skill:sdd-spec` — **approved**:
  `specs/008-provisioningserver-cutover/design.md`. 39-file
  `MAASTwistedRunTest` carve-out confirmed structurally incompatible
  with F03's always-on crochet reactor in a single pytest process
  (D-002); `nose`'s `--select-dir` directory-walk discovery means the
  carve-out narrows automatically once files relocate, no
  `scripts.py` edit needed (TD-001). `test_utils.py` 3-way basename
  check resolved: no actual collision (FR-006).
- [x] Create tasks for F05 with `/skill:sdd-tasks` — **approved**:
  `specs/008-provisioningserver-cutover/tasks.md`. 6 tasks (T1-T6).
- [x] Execute F05 T1 (regenerate/freeze the file partition) with
  `/skill:sdd-exec` — re-ran both authoritative greps directly against
  the live tree. Carve-out (39) matched design.md exactly. Scenario-gap
  grep found **18**, not design.md's 16: `tests/test_config.py` and
  `utils/tests/test_config.py` were missed by the original narrower
  candidate pool — both confirmed by direct read to contain real
  `scenarios = (...)` attributes. Gap-free set corrected 74 → 72.
  Folded back into `requirements.md` (D-003) and `design.md` (TD-002).
- [x] Execute F05 T2 (relocate the 72 gap-free files) with
  `/skill:sdd-exec` — all 72 `git mv`'d to
  `src/tests/provisioningserver/`. Fixed relocation fallout found
  during verification: 8 files' cross-test imports rewritten to the
  new dotted `tests.provisioningserver.*` path; missing `__init__.py`
  added per directory to avoid pytest basename collisions;
  `test_amt.py`'s `dirname(__file__)` assumption corrected to
  reference the production `amt` module's own location (its 3 XML
  fixtures correctly stay production-side, not test fixtures);
  `test_arguments.py`'s hardcoded self-referential dotted-path string
  updated. 1044/1046 relocated tests pass; 2 `test_beaconing.py`
  failures reproduce identically at the pre-move location (pytest
  stdin-capture quirk, pre-existing, out of scope); `test_powernv.py`/
  `test_s390x.py` pending T3 (depend on `test_pxe.py`). `make lint`
  clean. Committed.
- [x] Execute F05 T3 (relocate the 18 scenario-gap files) with
  `/skill:sdd-exec` — all 18 `git mv`'d, relying on F03's registered
  `ScenarioUnitTestCase` plugin for scenario multiplication, no
  per-package wiring. Fixed 3 more relocation-broken `__file__`-relative
  path assumptions: `test_pxe.py` (cross-test import to the already-
  relocated `test_kernel_opts`), `test_logger.py` (script path to the
  `logsomething.py` helper, which correctly stays production-side
  under `provisioningserver/logger/testing/`), `test_utils.py`'s
  template-directory path assertion (correctly relative to production
  `utils/__init__.py`'s own location, not the test's). Verified all 18
  files' pytest-collected (scenario-multiplied) node counts match
  their `nose`-reported counts exactly, per file — nose baseline
  captured via a git-worktree-isolated run (no working-tree changes
  left behind). Full suite: 1755/1757 pass (same 2 pre-existing
  `test_beaconing.py` failures). `make lint` clean. Committed.
- [x] Capture idea 004 (`MAASTwistedRunTest` carve-out follow-up) with
  `/skill:sdd-idea` per F05 T4 — `.ai/sdd/ideas/004-provisioningserver-twisted-reactor-carveout.md`.
  Names the 39-file carve-out (by reference to design.md §4), the
  blocking mechanism (testtools' `Spinner`-driven per-test reactor vs.
  crochet's always-on reactor), and 3 candidate directions (separate
  pytest invocation/process, full rewrite off `MAASTwistedRunTest`, or
  deferral to F08 `nose` retirement).
- [x] Execute F05 T5 (full-suite double-run + carve-out regression
  check). Found and fixed 5 cross-package/cross-test import breaks that
  only surface at full-suite scale. `bin/test.rack` narrows to the 39
  carve-out files automatically (1851 tests, OK) with no `scripts.py`
  edit, confirming design TD-001. Committed.
- [x] Execute F05 T6 (coverage-baseline check + root-cause). The
  `-66.19pp` FAIL is a scoping artifact of the harness, not a
  regression: like-for-like, coverage is **+0.16pp vs baseline**
  (95.07% vs 94.91%). Root-caused and fixed two latent defects the
  first full serial pytest run exposed — unbounded `sys.path` growth
  from `alembic/env.py` deriving its path from the mutable
  `sys.path[0]` (killed all 48 `test_logger.py` tests via
  `MAX_ARG_STRLEN`), and `TRACE_ID` contextvar leakage between tests.
  Full suite: 54 failures -> 5 (the documented pre-existing set).
  Committed.
- [x] Fix the coverage harness itself (follow-on from T6, user-approved
  scope): `_package_totals` now omits test files, so the metric tracks
  production code only; baselines carry a `metric_version` and `check`
  refuses to compare across versions. The 3 stored baselines are v1 and
  are recaptured lazily, each at the start of its own cutover feature.
  Recorded as design TD-004. Committed.

**F05 is complete** (T1-T6 all done). Next: F06 (`maasserver` cutover)
opens with `utilities/coverage-baseline capture maasserver` to replace
its stale v1 baseline.

- [x] F06 `maasserver` cutover (spec 009) — implementation:done. 332
  clean files relocated, 4 mixed files split at class level, 2
  legacy-only files left. v2 baseline 91.85%; post-relocation check
  PASS (+0.04pp).
- [x] Spec 010 dedicated pytest legs — implementation:done. Both nose
  carve-outs run under pytest: rack-legacy (39 MAASTwistedRunTest
  files, 1850/1850) and region-legacy (10 legacy classes, 69/69). Nose
  collects nothing.
- [x] F08 nose runner retirement — done (no spec; executed as a plan
  feature). Runner machinery, `nose` + `testresources` deps, and the 4
  `test.*` entry points removed; last consumers migrated off nose and
  off testresources (new `maastesting/resources.py`); migration-gate
  tools updated to the pytest legs. **Scope correction:** `testtools`,
  `testscenarios`, and `djangotestcase.py` are still load-bearing and
  remain — their removal is F09/F10-scale work. Verified: 22408
  passed / 6 failed (all pre-existing).

**F05, F06, F010, F08 are complete.** Nose and testresources are fully
retired. Remaining from the plan: F09 (modernize relocated tests to
fixtures — includes the `testscenarios` → `parametrize` migration of 91
files) and F10 (retire the shims — includes `testtools` and
`djangotestcase.py`), both load-bearing migrations, not runner
retirements.

