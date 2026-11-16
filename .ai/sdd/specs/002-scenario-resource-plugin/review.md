# Review: Scenario/resource pytest plugin (F02)

> Requirements: @requirements.md
> Design: @design.md
> Tasks: @tasks.md
> Status: Approved
> Reviewed: 2026-11-13

## Review Scope

- **Feature:** Scenario/resource pytest plugin (`002-scenario-resource-plugin`)
- **Implementation status:** implementation:done
- **Files reviewed:**
  - `src/maastesting/pytest/scenarios.py` (new plugin)
  - `pyproject.toml` (entry point registration)
  - `.ve/lib/python3.14/site-packages/maas-3.8.0a1.dist-info/entry_points.txt` (mirrored venv metadata)
  - `utilities/check-imports` (allowlist addition for `_pytest`)
  - `src/tests/maastesting/pytest/test_scenarios.py`
  - `src/tests/maastesting/pytest/test_resources_lifecycle.py`
  - `src/tests/maastesting/pytest/test_scenarios_and_resources.py`
  - `.ai/sdd/specs/002-scenario-resource-plugin/decisions.md` (new)
  - `.ai/sdd/specs/002-scenario-resource-plugin/design.md` §11 (cross-reference addition)
- **Out of review scope:**
  - `src/maasserver/dhcpd/tests/test_config.py` — inspected (unmodified) as the real-usage validation sample, not a changed file.
  - Real module migration, nose removal, resource-reuse performance work — all explicitly out of scope per requirements.md.

## Coverage Check

| Requirement | Expected Coverage | Status | Evidence / Notes |
|-------------|-------------------|--------|-------------------|
| FR-001 (scenario expansion) | `scenarios.py`: `pytest_pycollect_makeitem` + `ScenarioUnitTestCase.collect()` | Pass | T2: 3 distinct nodeids, correct per-scenario values, 1 isolated failure, not collapsed. Re-verified independently. |
| FR-002 (resource lifecycle) | No new code (TD-002); `MAASTestCase` existing `setUp`/`tearDown` | Pass | T3: resource-only class passes under the new plugin session; `build_count=2`, `_uses=0` after run confirms correct teardown, no leak. |
| FR-003 (no required source changes) | Automatic `scenarios` attribute detection | Pass | T5: `test_config.py` collected/passed unmodified; `git diff` empty, re-confirmed independently. |
| FR-004 (validated against real usage) | Real-file nose vs. pytest comparison | Pass | T5: nose `Ran 53 tests ... OK` vs. pytest `53 passed` — exact match, re-run independently with identical result. |
| FR-005 (combined scenario+resource) | Synthetic fixture, both attributes present | Pass | T4: 2 scenario-expanded instances, both pass with correct scenario value and resource attachment. |
| NFR-001 (reliability) | Repeat-run consistency | Pass | T6: identical counts across 2 runs; independently re-ran a 3rd time — still 53 passed. |
| NFR-002 (observability) | xdist/locality finding recorded and discoverable | Pass | `decisions.md` created, cross-referenced from `design.md` §11; T7 evidence (`gw0`/`gw1`, correct per-item outcomes) backs the finding. |

## Task Completion Check

| Task | Status | Evidence / Notes |
|------|--------|-------------------|
| T1 | Pass | Plugin + entry point exist; `--trace-config` confirms auto-load; 53 tests collected from `test_config.py` with 0 errors. |
| T2 | Pass | `1 failed, 2 passed, 3 skipped` — matches claimed result exactly on independent re-run. |
| T3 | Pass | Resource lifecycle fixture passes; teardown evidence (`_uses=0`) is sound, not just "it didn't crash." |
| T4 | Pass | Combined fixture, both scenarios pass. |
| T5 | Pass | Nose/pytest parity and zero-diff re-confirmed independently. |
| T6 | Pass | Reliability — re-confirmed with a third independent run, still consistent. |
| T7 | Pass | xdist run confirmed both workers exercised with correct per-item outcomes. |
| T8 | Pass | `decisions.md` contains concrete, non-placeholder evidence; cross-referenced from `design.md` §11. |

## Design Check

| Design Area / Decision | Status | Notes |
|------------------------|--------|-------|
| TD-001 (collection-time `UnitTestCase` subclass + `callobj=`) | Pass | Implementation matches design.md §3's documented code exactly: `tryfirst=True` hook, `ScenarioUnitTestCase(UnitTestCase)`, `callobj=` construction, no `originalname` passed. |
| TD-002 (no resource-lifecycle code) | Pass | Confirmed — no changes to `maastesting/testcase.py`, `maastesting/scenarios.py`, or `maasserver/testing/resources.py`. |
| Edge case: empty/default `scenarios` | Pass | Hook returns `None` for non-scenario classes (confirmed by T1's unchanged collection of `TestComposeConditionalBootloader` etc.). |
| Edge case: combined scenario+resource | Pass | T4. |
| Edge case: method-level `@unittest.skip` inside scenario'd class | Pass | T2's second method confirms both scenario variants report `SKIPPED` independently. |
| Edge case: class-level skip + scenarios | Pass (N/A, re-confirmed) | Re-checked the current codebase: `test_filesystemgroup.py`, `test_websocket_listener.py`, `test_clusterservice.py` each combine scenarios and `@skip` in the same file, but every `@skip` found is method-level, not class-level. Design.md's "zero such files exist today" claim still holds; the documented gap remains correctly flagged, non-blocking. |
| `--dist=load` under xdist | Pass | T7, re-confirmed: `gw0`/`gw1` both used, correct per-item outcomes. |
| Security/permissions | N/A | Test infrastructure only, no user input or auth path. |
| Accessibility | N/A | Not applicable — no UI. |

## Code Quality Check

- [x] Follows project conventions — matches `maastesting/pytest/*.py` module style, copyright header present and correctly dated (2026).
- [x] No obvious duplication — `CountingResourceManager` is duplicated verbatim between `test_resources_lifecycle.py` and `test_scenarios_and_resources.py` (see Issues, Low severity).
- [x] Error/loading/empty states handled — hook correctly falls through (`return None`) for non-matching classes; no silent swallowing.
- [x] Types are appropriate — no type hints added, consistent with the rest of `maastesting/pytest/*.py` (none of the sibling plugin modules use them either).
- [x] Security/privacy considerations — N/A.
- [x] Accessibility — N/A.
- [x] No unnecessary complexity — the plugin is minimal (33 lines of logic), matching design.md's scope exactly; no speculative generalization.
- [x] Tests cover important behavior and edge cases — scenario correctness, resource no-regression, combined usage, real-file parity, reliability, and xdist distribution are all covered; method-level skip edge case explicitly exercised.

## Verification

```text
Command: make lint
Exit code: 0
Summary: "congratulations :)" — ruff format, ruff check, pyright, check-imports, oapi all pass.
Verdict: PASS

Command: nose baseline — maastesting.noseplug.main(['--with-scenarios', '--with-crochet', 'src/maasserver/dhcpd/tests/test_config.py'])
Exit code: 0
Summary: Ran 53 tests in 1.437s — OK
Verdict: PASS

Command: bin/pytest src/maasserver/dhcpd/tests/test_config.py src/tests/maastesting/pytest/ -q
Exit code: 1 (expected — T2's fixture includes one intentionally failing scenario)
Summary: 1 failed, 61 passed, 3 skipped — 53 (test_config.py, matches nose exactly) + 8 fixture tests (2 T3 + 2 T4 + 4 T2, with 3 of those skipped)
Verdict: PASS

Command: git diff --stat src/maasserver/dhcpd/tests/test_config.py
Exit code: 0
Summary: empty — zero source changes to the real validation file, confirmed independently
Verdict: PASS

Command: grep -rln "scenarios = (" src --include="*.py" | xargs grep -l "@skip" (manual edge-case re-check)
Exit code: 0
Summary: 3 files found; all `@skip` usages are method-level, none class-level — design.md's documented gap remains correctly scoped as non-blocking
Verdict: PASS
```

## Issues Found

### Issue 1: `CountingResourceManager` duplicated across two fixture files

- **Severity:** Low
- **File:** `src/tests/maastesting/pytest/test_resources_lifecycle.py`, `src/tests/maastesting/pytest/test_scenarios_and_resources.py`
- **Line:** N/A (whole class, ~8 lines each)
- **Problem:** Identical `CountingResourceManager` (minus the module-level `build_count` global in one copy) is defined independently in both files instead of being shared.
- **Requirement/Task Impact:** None — both T3 and T4 pass; this is a maintainability nit, not a correctness or coverage gap.
- **Suggested Fix:** Extract to a small shared test helper (e.g. `src/tests/maastesting/pytest/conftest.py` or a local helper module) if a third consumer appears; not worth a refactor for two call sites today.

## Positive Findings

- Implementation is a direct, faithful translation of design.md's already-validated approach — no divergence between the documented `TD-001` code sample and the shipped module.
- Verification evidence in `tasks.md`/`decisions.md` is concrete and independently reproducible (re-ran every claimed command during review; all matched).
- The edge-case risk flagged in design.md §9 (class-level skip + scenarios) was re-checked against the current codebase during review, not just assumed still true — confirms the non-blocking classification is still accurate today.
- `decisions.md` correctly distinguishes the design-phase finding from the implementation-phase confirmed evidence (T3/T7), avoiding the trap of restating the spike without adding real proof.
- Necessary tooling friction (`_pytest` import allowlist, missing pip in the dev venv) was resolved transparently and recorded in `tasks.md`, not hidden or worked around silently.

## Follow-Ups

- If a future test file combines a class-level `@unittest.skip` with `scenarios`, `ScenarioUnitTestCase.collect()` needs the same `_is_skipped(cls)` guard that stock `UnitTestCase.collect()` has — not needed today (design.md §9/§14, reconfirmed above).
- F03 (first real module migration) should budget for the resource rebuild-per-test overhead documented in `decisions.md`/`design.md` §11 — no fix needed in F02.
- Low-severity duplication (Issue 1) — fold into a shared helper only if a third fixture needs the same resource manager.

## Verdict

- [x] Approved

**Reason:** All Must Have (FR-001–FR-004) and Should Have (FR-005) requirements pass with independently reproduced evidence; both NFRs are satisfied; design decisions (TD-001, TD-002) are implemented exactly as specified; all 8 tasks verified complete; `make lint` passes; only finding is a single Low-severity, non-blocking duplication note.
