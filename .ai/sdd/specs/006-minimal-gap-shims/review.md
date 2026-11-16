# Review: Minimal gap shims for pytest-native legacy test execution (F06)

> Requirements: @requirements.md
> Design: @design.md
> Tasks: @tasks.md

## Coverage Check

| Requirement | Expected Coverage | Status | Evidence / Notes |
|-------------|-------------------|--------|-------------------|
| FR-001 (scenario application shim) | T2, T4 | Pass | `maastesting/pytest/legacy.py`'s `pytest_collection_modifyitems` builds one dynamically-typed subclass per scenario entry, re-collected via pytest's own unittest machinery. Verified against `test_nodedevices.py`: 13 tests both under `nose` (`Ran 13 tests ... OK`) and `pytest` (`13 passed`) — exact match. |
| FR-002 (reactor/crochet session startup shim) | T2, T4 | Pass | Session-scoped autouse `_crochet_reactor` fixture calls `maastesting.crochet.setup_crochet()` once. Verified against `test_module.py` (`deferToDatabase`-based): 4 passed. Verified single-shot across 32 tests spanning 5 files in one combined session — no reactor-restart errors. |
| FR-003 (`APITestCase` collection-time fix) | T3, T4 | Pass | `maasserver/testing/api.py`'s `APITestCaseBase.__init__` guards `userfactories`/`clientfactories` with `or {}` before `sorted(...)`. Verified against `test_not_found.py`: 0 collection errors (previously 1 `TypeError`), 12 passed both under `nose` and `pytest` — exact match, same `user=`/`client=` scenario names. |
| FR-004 (no behavior change for gap-free files) | T4 | Pass | `test_vlan.py` (scenario-tier, gap-free itself): 38 passed identically with/without the plugin active. `test_eventloop.py`/`test_proxyconfig.py`: identical pre-existing failures with/without the plugin (confirmed unrelated by disabling the plugin and reproducing the same failures both ways). |
| NFR-001 (reliability, no added flakiness) | T4, T5 | Pass | Full `nose` regression (`test.rack`: 3533 tests, OK; `test.region`: 13013 tests, OK, SKIP=11) confirms the `Crochet.configure()` refactor (T1) and the shim additions introduce zero regressions or flakiness in the existing suite. |
| NFR-002 (scope discipline) | T5 | Pass | Two sub-discoveries surfaced during T2 (scenario merging happening in `APITestCaseBase.__init__` rather than as a visible class attribute; plain-function scenario values binding as methods when set via `setattr` at class level) were both resolved *within* FR-001's own scenario-multiplication mechanism — not an independent fourth gap category. No stop-and-ask was triggered; none was warranted. |

## Task Completion Check

| Task | Status | Evidence / Notes |
|------|--------|-------------------|
| T1 | Pass | `Crochet.configure()`-based refactor in `maastesting/crochet.py` (shared by `noseplug.py` and the new pytest shim); `--trace-config` confirms plugin registration; full `test.rack`/`test.region` regression below confirms zero behavior change to `nose`'s own call site. |
| T2 | Pass | `maastesting/pytest/legacy.py` created; entry point `maas-legacy` registered in `pyproject.toml`. Two real implementation gaps found and fixed in-task (see NFR-002 row). 13/13 (`test_nodedevices.py`), 4/4 (`test_module.py`) confirmed against `nose`. |
| T3 | Pass | `maasserver/testing/api.py` one-line guard. 12/12 (`test_not_found.py`) confirmed against `nose`; 0 collection errors (previously 1). |
| T4 | Pass | 32 tests across 5 files (3 representative + 2 throwaway smoke files) pass together in one session; gap-free spot-checks show zero behavior change; reactor confirmed single-shot. |
| T5 | Pass | Full `nose` regression: `test.rack` 3533 tests OK (exact baseline match); `test.region` 13013 tests OK, SKIP=11, 2500.98s wall time, zero failures. `make lint` clean across all five touched files. No fourth gap found. |

## Design Check

| Design Area / Decision | Status | Notes |
|------------------------|--------|-------|
| D-001 (reactor shim session-scoped, matching `nose`'s own lifecycle) | Pass | `_crochet_reactor` fixture is `scope="session", autouse=True`; confirmed single-shot across a 5-file, 32-test combined session. |
| D-002 (reuse `testscenarios`' own `generate_scenarios()`-equivalent mechanism, no third-party plugin) | Pass | `legacy.py` implements class-level multiplication directly against the existing `scenarios` attribute; no `pytest-cases`/`pytest-scenarios` dependency added; zero legacy test files rewritten. |
| D-003 (`APITestCase` fix stays in F06, not deferred) | Pass | Fix landed in this feature's T3, as scoped. |
| §3.1 scenario multiplication mechanism (design) | Pass, with in-scope refinement | Design's original sketch read `cls.scenarios` directly; implementation discovered `APITestCaseBase.__init__` *merges additional* scenarios at instance-construction time, requiring a throwaway-instance read (`_effective_scenarios`) instead. This refinement was necessary for FR-001 to actually work against `APITestCase`-tier files (US-003's own acceptance criterion); correctly handled within T2, not scope creep. |
| §3.2 reactor fixture (design) | Pass | Implemented as specified; no deviation. |
| §3.3 `APITestCaseBase.__init__` fix (design) | Pass | Implemented exactly as specified (`or {}` guard). |

## Code Quality Check

- [x] Follows project conventions — new module (`maastesting/pytest/legacy.py`) matches the existing `maastesting/pytest/` plugin pattern (`region.py`, `environment.py`); entry point registered alphabetically in `pyproject.toml`.
- [x] No obvious duplication — reuses `maastesting.crochet.setup_crochet()` rather than reimplementing reactor startup.
- [x] Error/loading/empty states handled — classes with no/empty `scenarios` are left untouched (confirmed via throwaway smoke test: 1 plain item, unchanged).
- [x] Types are appropriate — `types.FunctionType` check before wrapping scenario values in `staticmethod()`, avoiding incorrect wrapping of non-callable scenario values.
- [x] Security/privacy considerations are handled — not applicable; no new inputs, secrets, or attack surface (test-infra only).
- [N/A] Accessibility considerations — not applicable.
- [x] No unnecessary complexity — the two bugs found (instance-merged scenarios, descriptor-binding on class-level callables) were fixed with minimal, targeted code (one throwaway-instance read, one `staticmethod()` wrap), not a broader rewrite.

## Verification

```text
Command: .ve/bin/python -m ruff check src/maastesting/crochet.py src/maastesting/noseplug.py src/maastesting/pytest/legacy.py src/maasserver/testing/api.py && .ve/bin/python -m ruff format --check <same files>
Exit code: 0
Summary: All checks passed; all 4 files already formatted.
Verdict: PASS
```

```text
Command: .ve/bin/test.rack (full nose suite)
Exit code: 0
Summary: Ran 3533 tests ... OK (SKIP=1) — exact match to F02's recorded baseline.
Verdict: PASS
```

```text
Command: .ve/bin/test.region (full nose suite)
Exit code: 0
Summary: Ran 13013 tests ... OK (SKIP=11), 2500.98s wall time, zero failures.
Verdict: PASS
```

```text
Command: .ve/bin/python -m pytest src/maasserver/api/tests/test_nodedevices.py src/maasserver/rpc/tests/test_module.py src/maasserver/api/tests/test_not_found.py <+2 throwaway smoke files> -v --no-header -q
Exit code: 0
Summary: 32 passed across all 5 files in one combined session.
Verdict: PASS
```

```text
Command: .ve/bin/python -m pytest src/maasserver/models/tests/test_vlan.py [-p no:maastesting.pytest.legacy]
Exit code: 0 (both invocations)
Summary: 38 passed, identical with and without the shim plugin active — FR-004 gap-free non-regression confirmed.
Verdict: PASS
```

## Issues Found

None. No fourth gap discovered; the two in-task sub-discoveries (instance-merged scenarios, class-level callable binding) are refinements within FR-001's own mechanism, documented in `tasks.md` T2, not independent defects or scope extensions.

## Verdict

- [x] Approved

**Rationale:** All four Must Have functional requirements (FR-001–FR-004) and both NFRs (NFR-001 reliability, NFR-002 scope discipline) are verified with direct, exact-match evidence against `nose`'s own reported counts (13/13, 4/4, 12/12 on the three representative files; 3533/3533 and 13013/13013 on the two full-suite regressions). All three design decisions (D-001–D-003) were followed faithfully. The scenario-multiplication mechanism required two in-flight refinements beyond the design's original sketch (instance-merged scenarios, class-level callable binding) — both stayed strictly within FR-001's own boundary, were fixed immediately, and are fully documented; no stop-and-ask was warranted per NFR-002. No code outside the five files named in `tasks.md` (`maastesting/crochet.py`, `maastesting/noseplug.py`, `maastesting/pytest/legacy.py`, `maasserver/testing/api.py`, `pyproject.toml`) was touched.
