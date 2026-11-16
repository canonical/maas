# Review: Coverage baseline harness

> Requirements: @requirements.md
> Design: @design.md
> Tasks: @tasks.md

## Coverage Check

| Requirement | Expected Coverage | Status | Evidence / Notes |
|-------------|-------------------|--------|------------------|
| FR-001 | `cmd_capture` writes baseline JSON (T1/T2/T5) | Pass | Three real baselines captured and written with correct schema; verified against independent `coverage report --include=` run (provisioningserver: 95% TOTAL, 39226 stmts/4278 branches match exactly). |
| FR-002 | `_package_totals` `--include` filter (T1) | Pass | Verified: separate `--include=src/maasserver/*` vs `src/metadataserver/*` filters on the same combined `test.region` data file produced independent, correct totals (96.01% vs 95.05%). |
| FR-003 | Two-pass stability check, abort on >1.0pp disagreement (T2) | Pass | Real captures: spreads 0.014pp/0.148pp/0.005pp, all accepted. Forced-disagreement test (monkeypatched 50%/60%) confirmed abort, exit 2, no file written. |
| FR-004 | `check` tolerance comparison (T3) | Pass | `check` run immediately after each `capture`: correctly computed current/baseline/delta/verdict for all three packages (FAIL, as expected pre-cutover per design §15 amendment — not a defect). |
| FR-005 | Deletion-mapping convention documented, not enforced in code (T4) | Pass | `utilities/coverage-baselines/README.md` states the convention, explicitly disclaims code enforcement — matches design §12 wording exactly. |
| FR-006 | All three baselines committed before F04 (T5) | Pass | Baselines captured and committed at `4aee6a4e1`. No F04-F07 work started yet, so ordering requirement satisfied. |
| NFR-001 | Stability check doesn't false-fail (T2/T5) | Pass | All three real captures passed stability check with large margin (max spread 0.148pp vs 1.0pp tolerance). |
| NFR-002 | `check` output format (T3) | Pass | Output matches design §6 field names/order exactly (verified in real `check` runs). |

## Task Completion Check

| Task | Status | Evidence / Notes |
|------|--------|------------------|
| T1 | Pass | Script created, `_run_suite`/`_combine`/`_package_totals` all independently verified against real suites. `ruff check`/`format --check` both pass. |
| T2 | Pass | `capture` implemented and verified: real two-pass stability checks, forced-disagreement abort test, schema matches design §5 exactly. |
| T3 | Pass | `check` implemented and verified: correct mechanism output, missing-baseline exit 2 with documented message, output format matches design §6. |
| T4 | Pass | `utilities/coverage-baselines/README.md` written, cross-checked against design §12/FR-005/US-003 — no overstated claims. |
| T5 | Pass | All three baselines captured, cross-verified via independent `coverage report`, `check` round-trip confirmed correct, files committed at `4aee6a4e1`. |

## Design Check

| Design Area / Decision | Status | Notes |
|------------------------|--------|-------|
| TD-001 (accepted baseline = min of two runs) | Pass | All three baseline JSONs: `percent_covered == min(stability_runs)` confirmed programmatically. |
| TD-002 (`--include` filter, not per-package suite scoping) | Pass | Confirmed via FR-002 evidence above; `PYTEST_SUITE_COMMAND` always runs full `src/tests`, never scoped. |
| TD-003 (plain argparse, no new CLI framework) | Pass | Script uses only `argparse`/`subprocess`/`json`/stdlib; matches style of other `utilities/*.py` scripts. |
| §4 Suite-selection table | Pass | `LEGACY_SUITE_COMMANDS` dict matches design exactly: `test.rack` for provisioningserver, `test.region` for metadataserver/maasserver. |
| §6 Exit codes (0/1/2) | Pass | Verified: `check` PASS→0 path untested live (all three are pre-cutover FAILs) but code path is a direct `return 0 if verdict == "PASS" else 1`, matching FAIL→1 branch confirmed live; capture unstable→2, missing baseline→2, bad suite output→2 — all confirmed. |
| §9 Edge Cases (suite failure tolerance, missing baseline, no coverage data) | Pass | `_run_suite`'s exists-and-nonempty check before tolerating non-zero exit confirmed via real runs with pre-existing failures (2/7766 pytest failures tolerated, printed note, still wrote baseline). |
| §12 Migration/Rollout (no coupling elsewhere in repo) | Pass | Grepped `run-py-tests-ci`, `.github/workflows/*.yaml`, `Makefile`, and the whole repo for `coverage-baseline` references outside `utilities/coverage-baseline*` itself — none found. Confirms D-002 (not wired into CI) and the "additive only, fully removable" rollback claim. |
| §15 Verification Strategy (no unit tests, by design) | Pass | Explicit decision not to wrap a test-verification tool in its own test suite; verified instead by running it against real suites — honored throughout T1-T5. |

## Code Quality Check

- [x] Follows project conventions (matches `utilities/*.py` style, stdlib-only, argparse subcommands)
- [x] No obvious duplication (`_run_suite`/`_combine`/`_package_totals` shared by both subcommands via `_capture_one_pass`)
- [x] Error/loading/empty states handled (missing baseline, empty/missing coverage file, suite crash, combine failure, unstable capture — all exit 2 with a clear message)
- [x] Types are appropriate (type hints on all function signatures; `dict`/`Path`/`list[Path]` — matches repo's Python 3.9+ typing conventions)
- [x] Security/privacy considerations are handled — N/A, local-only tool, no network/secrets (design §7)
- [x] Accessibility considerations are handled where relevant — N/A, CLI tool (design §10)
- [x] No unnecessary complexity — three small functions, no new dependency, no new CLI framework (TD-003)

## Verification

```text
Command: .ve/bin/python -m ruff check utilities/coverage-baseline && .ve/bin/python -m ruff format --check utilities/coverage-baseline
Exit code: 0
Summary: All checks passed; file already formatted.
Verdict: PASS

Command: utilities/coverage-baseline --help / capture --help / check --help / capture nonexistent
Exit code: 0 (help) / 2 (invalid package choice)
Summary: CLI surface matches design §6; argparse rejects invalid package names correctly.
Verdict: PASS

Command: utilities/coverage-baseline capture {provisioningserver,metadataserver,maasserver} (real runs, prior session)
Exit code: 0 (all three)
Summary: Two-pass stability checks all passed (max spread 0.148pp, well under 1.0pp tolerance); JSON schema matches design §5 exactly for all three.
Verdict: PASS

Command: utilities/coverage-baseline check {provisioningserver,metadataserver,maasserver} (real runs, prior session)
Exit code: 1 (all three — expected pre-cutover FAIL per design §15 amendment)
Summary: Correctly computed current/baseline/delta/verdict for all three; FAIL is the correct mechanism output since no package has been cut over yet, not a bug.
Verdict: PASS (mechanism correctness; verdict content is expected-FAIL, not PASS)

Command: Independent coverage.py cross-check — legacy (`test.rack`) + pytest (`src/tests`) runs combined from scratch, `coverage report --include=src/provisioningserver/*`
Exit code: 0
Summary: TOTAL 95% (39226 stmts, 4278 branches) — exactly matches baseline JSON's num_statements/num_branches; percent_covered agrees within rounding (94.91% vs 95%).
Verdict: PASS

Command: grep -rl 'coverage-baseline' across run-py-tests-ci, .github/workflows/*.yaml, Makefile, repo-wide
Exit code: 1 (no matches, outside the tool's own files)
Summary: Confirms D-002 — not wired into any CI/PR gate; additive-only as designed.
Verdict: PASS
```

## Issues Found

### Issue 1: Baseline files staged but not committed — RESOLVED

- **Severity:** Low
- **File:** `utilities/coverage-baseline`, `utilities/coverage-baselines/{README.md,provisioningserver.json,metadataserver.json,maasserver.json}`
- **Problem:** T5's acceptance criteria and FR-006 require the three baseline JSON files to be "committed." `git status` shows all five new files as staged (`git add`-ed) but no commit has been made yet.
- **Requirement/Task Impact:** FR-006, T5 AC 1 ("all exist, committed").
- **Suggested Fix:** `git commit` the staged files before any F04-F07 work begins, so FR-006's ordering guarantee ("baselines exist before cutover work starts") is actually backed by repo history, not just a local working-tree state that could be lost or reordered.
- **Resolution:** Committed at `4aee6a4e1` ("feat(testing): add per-package coverage baseline harness"), branch `nuke_nose`. `git status` now shows a clean tree for all 5 files. FR-006 fully satisfied.

## Verdict

- [x] Approved
- [ ] Needs fixes

All six functional requirements and both NFRs pass on real, verified evidence (not assumed). Issue 1 (baseline files staged but not committed) is resolved — committed at `4aee6a4e1`. No remaining blocking or non-blocking issues.
