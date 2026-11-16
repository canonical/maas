# Review: pytest-xdist parallel infra (F01)

> Requirements: @requirements.md
> Design: @design.md
> Tasks: @tasks.md

## Coverage Check

| Requirement | Expected Coverage | Status | Evidence / Notes |
|-------------|-------------------|--------|-------------------|
| FR-001 (configurable concurrency) | T1 (no competing config), T3 (override verified) | Pass | T3: `MAAS_MAX_TEST_PROCESSES=2` → only `gw0`/`gw1` workers (14480+ lines verbose output, no `gw2`+). T1: single source of truth confirmed, zero competing config repo-wide. |
| FR-002 (default concurrency = fixed 4) | T1, T2 | Pass | Requirement itself was corrected mid-design (TD-001/D-003) from nose's historical "cores minus 2" to the actual existing default of 4 in `utilities/run-py-tests-ci`. T2 ran with the documented default and matched. |
| FR-003 (JUnit XML output) | T2 (produced), T4 (structural check) | Pass | T4: `junit-pytest.xml` well-formed, 7949 `<testcase>` == `tests="7949"` attribute, native pytest `--junit-xml` output (no translation step). |
| FR-004 (validated against pytest-native suites) | T2 | Pass | Full `src/tests/**` suite (381 files, 7949 tests) executed via the exact `utilities/run-py-tests-ci` invocation pattern. |
| NFR-001 (performance, ~10% ceiling at F01–F06 end-state) | T2, T6 | Pass (baseline only — not yet enforceable) | Baseline recorded in `design.md` §11: 202.62s/209.89s at 4 workers, 381.26s at 2 workers. NFR-001's actual ceiling is an **F06** acceptance item, not F01's — F01 correctly only establishes the "before" number. |
| NFR-002 (reliability, no added flakiness) | T5 | Pass | Two full runs of the same 7949-test suite produced identical pass/fail/skip counts (7766/2/181) and identical failing test IDs both times. |

## Task Completion Check

| Task | Status | Evidence / Notes |
|------|--------|-------------------|
| T1 | Pass | Grep across `pyproject.toml`, `tox.ini`, `Makefile`, `src/tests/**` (incl. all 7 `conftest.py` files) found zero competing worker-count config; `MAAS_MAX_TEST_PROCESSES` read in exactly one place. |
| T2 | Pass | Baseline run executed and recorded. Exit code 1 is accepted per the task's own documented exception clause (2 pre-existing failures, see Issues below). |
| T3 | Pass | Override to 2 workers confirmed via worker-ID inspection; no `gw2`+ present. |
| T4 | Pass | XML parses cleanly; `<testcase>` count exactly matches `tests` attribute. |
| T5 | Pass | Repeat run produced byte-for-byte identical pass/fail/skip counts. |
| T6 | Pass | `design.md` §11 updated with concrete dated baseline (no longer a placeholder); `decisions.md` created with scope-clarification note and full T1–T6 evidence log. |

## Design Check

| Design Area / Decision | Status | Notes |
|------------------------|--------|-------|
| TD-001 (keep fixed default of 4, amend requirements) | Pass | `requirements.md` FR-002/US-001/D-003 correctly reflect the amendment; no code change made or needed. |
| TD-002 (no scenario/resource plugin work in F01) | Pass | Confirmed — no `maastesting.pytest.*` files touched; scope held to validation against `src/tests/**` only. |
| §6 API/Integration Contract (native JUnit output, no translation step) | Pass | Verified directly against the generated file — produced by pytest's built-in writer, not a subunit pipeline. |
| §14 Risk: "PLAN.md wording" misread risk | Mitigated | `decisions.md` scope-clarification note created and cross-referenced from both `requirements.md` (D-001) and `design.md` (TD-002, §14). |
| §14 Risk: baseline staleness by F06 | Acknowledged, not yet due | Correctly deferred — re-measurement is an F06 responsibility per the design's own mitigation text. |

## Code Quality Check

- [x] Follows project conventions — no code changed; all edits are to `.ai/sdd/` artifacts (Markdown) and are internally consistent with existing spec conventions.
- [x] No obvious duplication — N/A, no code added.
- [N/A] Error/loading/empty states handled — not applicable to a test-infra validation feature.
- [N/A] Types are appropriate — no code changed.
- [x] Security/privacy considerations are handled — not applicable; no new inputs, secrets, or attack surface introduced.
- [N/A] Accessibility considerations — not applicable.
- [x] No unnecessary complexity — design explicitly avoided adding a plugin/abstraction layer where none was needed (TD-002); this is the correct outcome, not a shortfall.

## Verification

```text
Command: make lint
Exit code: 0 (no lint/type errors reported; "congratulations :)" from oapi check, no ruff/pyright failures surfaced)
Summary: Lint passes. Expected — no Python/Go source files were modified by this feature; only .ai/sdd/ Markdown artifacts changed.
Verdict: PASS
```

```text
Command: MAAS_MAX_TEST_PROCESSES=4 bin/pytest -n auto --maxprocesses=4 --dist=load --junit-xml=junit-pytest.xml src/tests (T2, re-verified via T5 repeat)
Exit code: 1 (2 pre-existing, unrelated failures — see Issues)
Summary: 7949 collected, 7766 passed, 2 failed, 181 skipped. Identical across two independent runs (T2, T5). Concurrency override (T3) and JUnit structural correctness (T4) independently verified against the same run.
Verdict: PASS (feature's own acceptance criteria explicitly except pre-existing unrelated failures; both failures confirmed pre-existing via serial reproduction and git history)
```

```text
Command: git status --short / git diff --stat
Exit code: 0
Summary: Only .ai/sdd/ artifacts added (untracked) plus one unrelated workshop.yaml change (pre-existing, not from this session — environment/SDK config, unrelated to F01). No production code, CI scripts, or pyproject.toml changes made — matches design's core claim that the infra already existed.
Verdict: PASS
```

## Issues Found

### Issue 1: Pre-existing `test_etag` failures (out of scope, not introduced by this feature)

- **Severity:** Low (pre-existing defect, unrelated to F01; flagged for tracking, not a blocker)
- **File:** `src/tests/maasapiserver/v3/api/public/models/responses/test_resource_pools.py`, `src/tests/maasapiserver/v3/api/public/models/responses/test_zones.py`
- **Problem:** `test_etag` asserts a hardcoded hash string that no longer matches the computed value. Reproduces identically with and without xdist, in isolation, single-process — confirming it's unrelated to concurrency/parallelism. Last touched by unrelated historical commit `60a2eef16`.
- **Requirement/Task Impact:** None — explicitly covered by T2's own documented exception clause ("if exit code is non-zero due to a test failure unrelated to this feature... note it separately — do not treat as a design gap"). Does not affect FR-001–FR-004 or NFR-001/002 verdicts.
- **Suggested Fix:** Open a separate bug ticket (outside SDD scope for F01) to update the hardcoded hash assertions or fix the underlying etag computation if it's the actual regression.

## Verdict

- [x] Approved with follow-ups

**Rationale:** All four Must Have functional requirements (FR-001–FR-004) and both NFRs (NFR-001 baseline, NFR-002 reliability) are verified with direct evidence. Design decisions (TD-001, TD-002) were followed faithfully, and the one requirements amendment made mid-flow (FR-002/US-001/D-003) was explicit, user-approved, and consistently propagated across `requirements.md`, `design.md`, and `tasks.md`. No code was changed, matching the design's own prediction that the infra already existed — this is correct scope discipline, not under-delivery. The single follow-up (Issue 1) is a pre-existing, out-of-scope defect that does not block this feature's verdict.
