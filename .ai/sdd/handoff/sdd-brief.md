# SDD Handoff Brief: `metadataserver` pilot cutover (F04)

> Status: Approved
> Readiness: Ready for Implementation
> Updated: 2026-11-17

## Metadata

- **Spec ID:** `007-metadataserver-pilot-cutover`
- **Spec Path:** `.ai/sdd/specs/007-metadataserver-pilot-cutover/`
- **Current .status:** `tasks:approved`
- **Source Inputs:** `.ai/sdd/PLAN.md` (F04);
  `.ai/sdd/ideas/003-coverage-gated-pytest-cutover.md`; no
  `.ai/strategy/handoff/strategy-brief.md` used

**Note on feature numbering:** this plan's F01-F10 IDs are a new
sequence and do not correspond to spec directories `001`-`003`, which
belong to the abandoned plugin-first approach (no code landed; see
`INDEX.md` Specs status correction). This brief **supersedes** the
prior `sdd-brief.md`, which covered `006-minimal-gap-shims` (F03,
review:approved, Ready for Release).

## Product / Feature Summary

- **User / Audience:** MAAS engineers working on `metadataserver`; CI
  maintainers reducing per-package runner count.
- **Problem:** `metadataserver` (23 legacy test files, 927 test
  definitions) currently requires `nose` to run at all. F01-F03 built
  the prerequisites (coverage baseline, `nose` dependency declaration,
  gap-closing shims) but no package has yet been fully cut over —
  `metadataserver` is the designated pilot, smallest and lowest-risk.
- **Outcome:** All 23 files relocated to `src/tests/metadataserver/`
  (mirroring their existing paths), `metadataserver` dropped from
  `nose`'s collection scope (a structural consequence of relocation,
  not a code change), and coverage parity proven against the committed
  baseline (95.05%, 1.0pp tolerance).
- **Scope:** `metadataserver` only. No modernization of test style
  (`MAASTestCase`/`scenarios` patterns kept as-is, per NFR-002/F09).
- **Out of Scope:** `provisioningserver` (F05) and `maasserver`
  (F06/F07) cutovers; `pytest-django` adoption (deferred, D-003);
  retiring `nose`/the legacy stack entirely (F08).

## Requirements Summary

- **Key User Stories:** `US-001` (full `metadataserver` suite runs via
  pytest alone), `US-002` (coverage parity proven, not assumed),
  `US-003` (5 gap-touching files triage cleanly using F03's shim)
- **Must Have Functional Requirements:** `FR-001` (relocate gap-free
  files), `FR-002` (triage gap-touching files), `FR-003` (drop from
  `nose`), `FR-004` (verify coverage parity), `FR-005` (reconcile
  pre-existing pytest-native overlap files)
- **Important NFRs:** `NFR-001` (reliability — deterministic, matching
  `nose`'s outcome), `NFR-002` (scope discipline — mechanical
  relocation only, no modernization; `provisioningserver`/`maasserver`
  untouched)
- **Acceptance Notes:** 0 open Questions. 3 decisions resolved
  (`D-001`-`D-003`): gap-tier count corrected via direct recount (5
  gap-touching, not `PLAN.md`'s estimated 9 — file/test-def totals of
  23/927 confirmed matching exactly); two pre-existing narrow
  pytest-native files are unrelated and don't shortcut triage of their
  legacy counterparts; `pytest-django` adoption stays deferred.

## Design Summary

- **Approach:** Pure `git mv` relocation for 21 of 23 files (no code
  change). The 5 gap-touching files rely entirely on F03's already-
  verified shim (`maastesting/pytest/legacy.py`,
  `maasserver/testing/api.py`) with zero further modification. Two
  relocation-specific hazards (not F03 gaps) were found and resolved by
  direct reproduction during design: a path collision with a
  pre-existing, unrelated 1-test file (`test_hooks.py`, resolved as a
  merge — TD-002) and a `sys.path`-dependent `snippets` package import
  affecting 4 files (TD-003) — 2 fix via a dotted-import rewrite, 2
  need a new scoped `conftest.py` because their *production* modules
  (not just the test files) contain their own internal
  `except ImportError: from snippets.maas_api_helper import ...`
  fallback. `nose` drops `metadataserver` once
  `--select-dir=src/metadataserver` resolves to zero test files — no
  change to `src/maastesting/scripts.py`.
- **Components / Modules:** Relocated: 23 files from
  `src/metadataserver/**/tests/test_*.py` to
  `src/tests/metadataserver/**/test_*.py`. New:
  `src/tests/metadataserver/user_data/templates/snippets/conftest.py`.
  Modified: 2 files get a dotted-import rewrite
  (`test_maas_wipe.py`/`test_maas_wipe_defs.py`); 1 file
  (`test_hooks.py`) gets merged into a pre-existing file at the same
  destination path. No change to any F03 file
  (`maastesting/pytest/legacy.py`, `maasserver/testing/api.py`,
  `pyproject.toml`).
- **Data / State:** Not applicable — test relocation only.
- **APIs / Integrations:** No new pytest plugin/entry point. Uses the
  existing `utilities/coverage-baseline check metadataserver` (F01)
  unmodified.
- **Technical Decisions:** `TD-001` (no test modernization during
  relocation — pure `git mv` plus the two confirmed fixes only);
  `TD-002` (merge, not rename-around, the `test_hooks.py` path
  collision — both test the same production module); `TD-003` (fix the
  path-import hazard per-file: dotted import for 2 files, scoped
  `conftest.py` for 2 — confirmed empirically which fix each file
  needs, not left open).
- **Risks / Constraints:** `--select-dir=src/metadataserver`'s no-op
  assumption could be wrong (nose errors instead of silently finding 0
  tests) — Low impact, mitigated by T4's full `bin/test.region` run
  confirming exit 0 with the expected reduced count. The
  `test_hooks.py` merge could silently drop the pre-existing file's one
  test — Low impact, mitigated by T1's explicit pre/post test-count
  check (1 + 155 = 156).

## Implementation Plan

- **Task Source:** `.ai/sdd/specs/007-metadataserver-pilot-cutover/tasks.md`
- **Recommended Order:** `T1, T2, T3 (parallel-safe, independent file
  sets) -> T4 -> T5`
- **Key Tasks:**
  - `T1` (1.5h, independent): Relocate 18 gap-free files + merge
    `test_hooks.py` collision (FR-001, FR-005 merge half)
  - `T2` (1h, independent): Relocate 5 gap-touching files, relying on
    F03's shim unmodified (FR-002)
  - `T3` (1.5h, independent): Relocate 4 path-import-hazard files — 2
    via dotted-import rewrite, 2 + new scoped `conftest.py` (FR-005)
  - `T4` (1h, depends T1-T3): Drop from `nose`, verify structurally —
    confirm `bin/test.region`'s count drops by exactly 927 (13013 ->
    12086) (FR-003)
  - `T5` (1h, depends T1-T4): Coverage parity check + full regression
    sign-off (FR-004, NFR-001, NFR-002)
- **Likely Files / Areas:** 23 files relocated under
  `src/tests/metadataserver/`; 1 new `conftest.py`; 2 files with a
  one-line import rewrite; `src/metadataserver/**/tests/` emptied of
  test files (production code untouched).

## Verification Plan

```text
Command: pytest --collect-only src/tests/metadataserver
Expected: 0 collection errors across all 23 relocated files, including
the merged test_hooks.py and the conftest.py-dependent pair (T1-T3)

Command: pytest src/tests/metadataserver -v
Expected: 927 test passes (zero deletions per design §3.1), matching
nose's current per-file counts exactly

Command: find src/metadataserver -name 'test_*.py' | wc -l
Expected: 0 (T4)

Command: bin/test.region (or .ve/bin/test.region)
Expected: exit 0, test count = 12086 (13013 baseline - 927) (T4)

Command: utilities/coverage-baseline check metadataserver
Expected: verdict: PASS (current coverage >= 95.05% - 1.0pp) (T5)

Command: bin/test.rack (full nose suite, provisioningserver)
Expected: 3533 tests, OK — unaffected baseline, confirms no
cross-package regression (T5)

Command: make lint
Expected: exit 0 across all touched/new files (every task)
```

No test modernization (base class changes, `scenarios` ->
`parametrize` conversion, etc.) may be introduced during T1-T3 beyond
the confirmed merge (T1) and import fixes (T3) — per NFR-002/TD-001.

## Review / Release Notes

- **Review Artifact:** Not yet created — run `/skill:sdd-review` after
  T1-T5 implementation completes.
- **Review Verdict:** N/A (pending implementation)
- **Known Follow-ups:** None yet — implementation not started.

## Handoff Readiness

- **Ready for Implementation:** yes — requirements, design, and tasks
  all approved; no open Questions; Readiness Check in `tasks.md` has no
  blocking failures.
- **Ready for QA:** no — T1-T5 not yet executed.
- **Ready for Release:** no.
- **Blockers:** None.
- **Recommended Next Action:** Execute F04 tasks T1-T5 with
  `/skill:sdd-exec`, in the stated order (T1/T2/T3 parallel-safe → T4 →
  T5).
