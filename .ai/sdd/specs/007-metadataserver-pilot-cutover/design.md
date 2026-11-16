# Design: Cut over `metadataserver` to pytest (pilot)

> Status: Approved

## 1. Summary

Relocate all 23 legacy `metadataserver` test files into
`src/tests/metadataserver/` (mirroring each file's existing path under
`metadataserver/`), apply per-file triage only where a file's covered
behavior is confirmed duplicated elsewhere (candidate for deletion
rather than relocation), and verify the package's pytest-only coverage
against its committed baseline. `nose` drops `metadataserver`
automatically once no test files remain under `src/metadataserver`
(§3.3) — no code change to `run_region()`/`run_region_legacy()` is
needed. No new shim/plugin work: F03's `maastesting/pytest/legacy.py`
and `maasserver/testing/api.py` fix already cover all 5 gap-touching
files.

This design's central artifact is a complete, pre-committed
**per-file disposition table** (§3.1) — every one of the 23 files gets
an explicit relocate/path-fix/delete decision before implementation
starts, closing the "which 5 files hit what gap" ambiguity left open by
requirements and turning F07's later per-file judgement work into a
proven, repeatable pattern at small scale first.

## 2. Requirements Mapping

| Requirement | Design Coverage |
|-------------|-----------------|
| FR-001 (relocate gap-free files) | §3.1 rows marked "relocate" |
| FR-002 (triage gap-touching files) | §3.1 rows marked "relocate (shim)"; §3.2 |
| FR-003 (drop from nose) | §3.3 |
| FR-004 (verify coverage parity) | §3.4 |
| FR-005 (reconcile pre-existing overlap files) | §3.1 rows for `test_hooks.py`/`test_maas_wipe.py`; §9 Edge Cases |
| NFR-001 | §9 (no file is modified beyond what §3.1 names) |
| NFR-002 | §13 TD-001 (no modernization, no plugin changes) |

## 3. Technical Approach

### 3.1 Per-file disposition table

All 23 files, final-verified against the live tree (confirms
requirements' D-001: 5 gap-touching, 18 gap-free; no 24th file hiding).
"Gap" column names the F03 gap (`scenarios`/`reactor`/`apitestcase`) or
`path-import` (a new, non-F03 relocation hazard found during design —
see §9).

| # | File | Gap | Disposition |
|---|------|-----|-------------|
| 1 | `metadataserver/tests/test_api.py` | scenarios, apitestcase | Relocate to `src/tests/metadataserver/test_api.py` unmodified; relies on F03's shim (both gaps) |
| 2 | `metadataserver/tests/test_api_twisted.py` | reactor | Relocate to `src/tests/metadataserver/test_api_twisted.py` unmodified; relies on F03's reactor fixture |
| 3 | `metadataserver/builtin_scripts/tests/test_hooks.py` | scenarios | Relocate to `src/tests/metadataserver/builtin_scripts/test_hooks.py`; **name collision** with the pre-existing narrow file at that exact path (FR-005) — see §9 for the resolution rule |
| 4 | `metadataserver/builtin_scripts/testing_scripts/tests/test_fio.py` | scenarios | Relocate to `src/tests/metadataserver/builtin_scripts/testing_scripts/test_fio.py` unmodified; relies on F03's shim |
| 5 | `metadataserver/user_data/tests/test_generate_user_data.py` | scenarios | Relocate to `src/tests/metadataserver/user_data/test_generate_user_data.py` unmodified; relies on F03's shim |
| 6 | `metadataserver/tests/test_fields.py` | mixed (`TestBin` gap-free, `TestBinaryField` legacy-tagged) | **Split, not a pure relocate** (TD-005, implementation-time correction): `TestBin` relocates to `src/tests/metadataserver/test_fields.py`; `TestBinaryField` (`MAASLegacyTransactionServerTestCase`) stays at the original path, untouched, still covered only by `run_region_legacy()` |
| 7 | `metadataserver/tests/test_nodeinituser.py` | none | Relocate unmodified |
| 8 | `metadataserver/tests/test_vendor_data.py` | none | Relocate unmodified |
| 9 | `metadataserver/tests/test_address.py` | none | Relocate unmodified |
| 10 | `metadataserver/builtin_scripts/tests/test_network.py` | none | Relocate unmodified |
| 11 | `metadataserver/builtin_scripts/commissioning_scripts/tests/test_bmc_config.py` | none | Relocate unmodified |
| 12 | `metadataserver/builtin_scripts/commissioning_scripts/tests/test_dhcp_unconfigured_ifaces.py` | none | Relocate unmodified |
| 13 | `metadataserver/builtin_scripts/commissioning_scripts/tests/test_lldp.py` | none | Relocate unmodified |
| 14 | `metadataserver/builtin_scripts/commissioning_scripts/tests/test_machine_config_hints.py` | none | Relocate unmodified |
| 15 | `metadataserver/builtin_scripts/deployment_scripts/tests/test_curtin_install.py` | none | Relocate unmodified |
| 16 | `metadataserver/builtin_scripts/testing_scripts/tests/test_badblocks.py` | none | Relocate unmodified |
| 17 | `metadataserver/builtin_scripts/testing_scripts/tests/test_seven_z.py` | none | Relocate unmodified |
| 18 | `metadataserver/builtin_scripts/testing_scripts/tests/test_smartctl.py` | none | Relocate unmodified |
| 19 | `metadataserver/user_data/tests/test_snippets.py` | none | Relocate unmodified |
| 20 | `metadataserver/user_data/templates/snippets/tests/test_maas_wipe.py` | path-import | Relocate with a dotted-import fix (§9/TD-003); **name collision** with the pre-existing file at `.../release_scripts/test_maas_wipe.py` is a different path, no collision — see §9 |
| 21 | `metadataserver/user_data/templates/snippets/tests/test_maas_wipe_defs.py` | path-import (support module, not a test file) | Relocate alongside #20 with the same dotted-import fix — it is `test_maas_wipe.py`'s data-only dependency, not independently collected (0 `def test_` matches) |
| 22 | `metadataserver/user_data/templates/snippets/tests/test_maas_run_remote_scripts.py` | path-import (production-code fallback, not just the test file) | Relocate with a new scoped `conftest.py` (§9/TD-003) inserting `templates/` onto `sys.path` — the production module's own internal fallback import requires the bare `snippets` package to resolve, a dotted-import rewrite of the test file alone is insufficient |
| 23 | `metadataserver/user_data/templates/snippets/tests/test_maas_run_scripts.py` | path-import (production-code fallback, not just the test file) | Relocate with the same `conftest.py` fix as #22 |

**Zero deletions.** No file's covered behavior was confirmed duplicated
elsewhere in `src/tests/` during this design's triage — all 23 relocate.
FR-002's "(b) delete if duplicated" branch is therefore not exercised in
this feature; it remains available as a path if implementation discovers
genuine duplication, per the Implementation FAQ (§16).

### 3.2 Gap-touching files: no new shim work (FR-002)

Files #1-5 rely entirely on F03's already-verified mechanism:

- #1, #3, #4, #5 (`scenarios`): `maastesting/pytest/legacy.py`'s
  `pytest_collection_modifyitems` hook (F03 §3.1) multiplies their
  `scenarios` attribute identically regardless of the file's path —
  the hook has no package/path-scoping, it matches by class attribute.
- #1 (`apitestcase`): `maasserver/testing/api.py`'s `__init__` fix
  (F03 §3.3) already makes `APITestCase`/`APITestCaseBase` collectible
  under pytest from any path.
- #2 (`reactor`): `maastesting/pytest/legacy.py`'s session-scoped
  `_crochet_reactor` autouse fixture (F03 §3.2) starts the reactor
  regardless of which file needs it.

No code change to F03's scenario/`APITestCase` shims is required or
made by this feature. The reactor fixture itself (not this section's
scenario/`APITestCase` claim) does gain one implementation-time
addition — see TD-004.

### 3.3 Dropping `metadataserver` from `nose` (FR-003)

`src/maastesting/scripts.py`'s `run_region()`/`run_region_legacy()`
both invoke nose with:

```python
"--with-select",
"--select-dir=src/maasserver",
"--select-dir=src/metadataserver",
```

`--select-dir` is a directory-walk selector, not an explicit file list:
once every file in §3.1 is relocated (directory `src/metadataserver`
contains zero `test_*.py` files, only non-test production code), nose's
own directory walk finds nothing to collect there — `metadataserver`
drops out of the nose run **as a structural consequence of relocation
completing**, with no line of `scripts.py` touched.

**Verification-only task, not a code change:** after relocation,
`find src/metadataserver -name 'test_*.py'` must return exactly one
file — `tests/test_fields.py`, intentionally kept per TD-005 (its one
remaining class, `TestBinaryField`, is `legacy`-tagged and must stay
under `run_region_legacy()`'s own selection) — and `bin/test.region`'s
own test count must drop. The *static* `def test_` count across the
22 relocated/merged files (927, minus `TestBinaryField`'s 9 = 918)
undercounts the actual drop because `testscenarios`-based files
multiply one `def test_` into several runtime tests; T4's actual
measured run (§15) is the ground truth, not this estimate.

The `--select-dir=src/metadataserver` line itself is left in place
(not deleted) — removing it is `maasserver`'s concern too, since both
packages share this invocation (F01's TD-002 finding); it becomes a
no-op for an empty directory and costs nothing. Deleting it prematurely
would require re-adding it if `maasserver`'s own cutover (F06/F07) still
needs the combined invocation during its own transition window.

### 3.4 Coverage verification (FR-004)

Use the existing, already-built `utilities/coverage-baseline check
metadataserver` (F01) unmodified:

```text
$ utilities/coverage-baseline check metadataserver
```

This runs `pytest src/tests` under `coverage run` (its
`PYTEST_SUITE_COMMAND`, package-filtered to `metadataserver`'s own
source at report time, per F01's TD-002 pattern) and compares against
`utilities/coverage-baselines/metadataserver.json` (95.05%, 1.0pp
tolerance). No change to this tool is needed — it already targets
`src/tests` as the sole suite, which is exactly where every file lands
per §3.1.

## 4. Component / Module Structure

```text
src/tests/metadataserver/                                   # new tree, mirrors src/metadataserver/ layout
  test_api.py                                                # from metadataserver/tests/test_api.py
  test_api_twisted.py                                        # from metadataserver/tests/test_api_twisted.py
  test_fields.py                                             # from metadataserver/tests/test_fields.py - TestBin only, split per TD-005
  test_nodeinituser.py                                       # from metadataserver/tests/test_nodeinituser.py
  test_vendor_data.py                                        # from metadataserver/tests/test_vendor_data.py
  test_address.py                                            # from metadataserver/tests/test_address.py
  builtin_scripts/
    test_hooks.py                                            # MERGE TARGET - see §9
    test_network.py                                          # from metadataserver/builtin_scripts/tests/test_network.py
    commissioning_scripts/
      test_bmc_config.py
      test_dhcp_unconfigured_ifaces.py
      test_lldp.py
      test_machine_config_hints.py
    deployment_scripts/
      test_curtin_install.py
    testing_scripts/
      test_fio.py
      test_badblocks.py
      test_seven_z.py
      test_smartctl.py
  user_data/
    test_snippets.py
    test_generate_user_data.py
    templates/
      snippets/
        conftest.py                                          # new - sys.path insertion for maas_run_* pair, TD-003
        test_maas_wipe.py                                     # dotted-import fix - see §9/TD-003
        test_maas_wipe_defs.py                                # dotted-import fix - see §9/TD-003
        test_maas_run_remote_scripts.py                       # conftest.py fix - see §9/TD-003
        test_maas_run_scripts.py                              # conftest.py fix - see §9/TD-003
src/metadataserver/                                          # all gap-free/gap-touching test_*.py removed; production code untouched
  tests/test_fields.py                                        # TestBinaryField only (legacy-tagged) - stays here, TD-005
```

No change to `maastesting/noseplug.py`, `maasserver/testing/api.py`, or
`pyproject.toml`. `maastesting/pytest/legacy.py` gains the TD-004
database thread-pool install, additive to its existing fixture.

## 5. Data Model / State

Not applicable — test-infrastructure relocation only, no persistent
state.

## 6. API / Integration Contract

- No new pytest plugin or entry point. One existing fixture
  (`_crochet_reactor` in `maastesting/pytest/legacy.py`) gains two
  additional calls (TD-004) — same fixture, same scope, same autouse
  behavior, no new public surface.
- `metadataserver`'s own public API (production code) is entirely
  untouched — only test files move.
- `utilities/coverage-baseline`'s existing `check` subcommand interface
  is used as-is.

## 7. Security / Permissions / Privacy

Not applicable.

## 8. User Flows

Not applicable — build/test-time only.

## 9. Edge Cases

| Case | Expected Behavior |
|------|--------------------|
| `builtin_scripts/tests/test_hooks.py` (155 test defs, legacy) relocating to the exact path already occupied by a pre-existing, unrelated narrow file (`src/tests/metadataserver/builtin_scripts/test_hooks.py`, 1 test, `TestParseBootifCmdline`) | **Merge, do not overwrite.** The legacy file's classes are appended into the existing file (or the existing file's one class is appended into the relocated legacy file — either ordering is acceptable); the final single `test_hooks.py` must contain both `TestParseBootifCmdline` (pre-existing) and every class from the legacy file, verified by a before/after test-count diff (1 + legacy's own count, not a silent drop of either side). |
| `release_scripts/test_maas_wipe.py` pre-existing file vs. the legacy `templates/snippets/tests/test_maas_wipe.py` | **No collision** — different final paths (`builtin_scripts/release_scripts/test_maas_wipe.py` vs. `user_data/templates/snippets/test_maas_wipe.py`) and different modules under test (`metadataserver.builtin_scripts.release_scripts.maas_wipe` vs. the `snippets` package reached via path-insertion import, §9 row below) — both relocate/stay independently, per requirements D-002. |
| `test_maas_wipe.py`/`test_maas_wipe_defs.py`/`test_maas_run_remote_scripts.py`/`test_maas_run_scripts.py` import `from snippets import ...`/`from snippets.tests.test_maas_wipe_defs import ...` — resolvable today only because `metadataserver/user_data/templates/` has no `__init__.py`, so pytest's rootdir-insertion makes `templates/` (not `src/`) the first `sys.path` entry, exposing its `snippets/` child as a top-level package | **New relocation hazard, not an F03 gap** (does not match scenarios/reactor/`APITestCase` — a pytest import-mechanics issue specific to non-package directories, surfaced only by this feature's relocation). Confirmed empirically (TD-003): the `maas_wipe` pair fixes cleanly with a dotted-import rewrite (`from metadataserver.user_data.templates.snippets import ...`); the `maas_run_*` pair's *production* modules contain their own internal `except ImportError: from snippets.maas_api_helper import ...` fallback (explicitly commented "only used in tests"), so a dotted-import rewrite of the test file alone does not fix what the production module itself does — these 2 files instead get a scoped `conftest.py` inserting `templates/` onto `sys.path`, reproducing the original rootdir-insertion behavior explicitly. These fixes (2 dotted-import rewrites + 1 scoped `conftest.py`) are the **only required source edits** across all 23 files besides the merge in the first row above. |
| A `metadataserver` test importing another legacy file's test-support module by relative/sibling path (e.g. `metadataserver.tests.models.BinaryFieldModel`, used by `test_fields.py`) | Confirmed already a proper dotted import (`from metadataserver.tests.models import BinaryFieldModel`) — survives relocation unchanged since the source module itself stays in `src/metadataserver/tests/models.py` (not relocated; it's Django model test-support code, not a test file itself, has 0 `test_*` defs). |
| `run_region()`/`run_region_legacy()`'s `--select-dir=src/metadataserver` after relocation | Resolves to zero test files found; nose's own select-plugin reports 0 tests for that directory, not an error — confirmed by nose's directory-walk semantics (same mechanism that already makes an empty/non-test directory a no-op today). |
| Coverage check run before relocation is complete (partial state) | Out of scope to design for — FR-004's verification step runs only after FR-001/FR-002 are fully done, same single-cutover pattern as F03's "single full-suite cutover per D-001" discipline referenced in F03's `decisions.md`. |

## 10. Accessibility / UX Notes

Not applicable.

## 11. Observability / Operations

Not applicable — no runtime/production behavior change.

## 12. Migration / Rollout

- **Rollout:** All 23 files move in one cutover (not staged per-file in
  production), matching F03's own "single full-suite cutover" precedent
  — a half-moved package would leave `nose` and `pytest` both partially
  responsible for `metadataserver`, which the coverage tool cannot
  measure correctly (it assumes one package is either fully nose or
  fully pytest at report time, per F01's TD-002).
- **Rollback:** `git revert` the relocation commit(s) — every change is
  a `git mv` plus the 4-file import fix (§9) plus the 1-file merge
  (§9); fully revertable as a single commit/PR.

## 13. Technical Decisions

### TD-001: No test modernization during relocation

- **Decision:** Every relocated file keeps its existing
  `MAASTestCase`/`MAASServerTestCase`/`APITestCase` base classes,
  `scenarios` attributes, and test method structure unchanged. Only the
  4-file import fix (§9) and the 1-file merge (§9) are source edits;
  everything else is a pure `git mv`.
- **Why:** Matches requirements' NFR-002 and `PLAN.md`'s explicit
  "mechanical relocation first, modernize later (F09)" policy.
- **Trade-off:** Leaves `scenarios`/`MAASTestCase` patterns live in
  `src/tests/` rather than converting to `parametrize`/plain pytest
  functions — intentional, F09's concern.
- **Alternatives considered:** Opportunistic modernization during
  relocation — rejected, directly conflicts with NFR-002 and widens
  this feature's diff for no coverage benefit.

### TD-002: Merge, not rename-around, the `test_hooks.py` collision

- **Decision:** The legacy `test_hooks.py`'s classes are merged into the
  single destination file alongside the pre-existing
  `TestParseBootifCmdline`, rather than renaming one of the two to avoid
  the collision (e.g. `test_hooks_legacy.py`).
- **Why:** Both files test the exact same production module
  (`metadataserver.builtin_scripts.hooks`); keeping them as two files
  testing one module is a worse long-term layout than F09 would want to
  inherit, and merging costs nothing extra beyond the rename cost.
- **Trade-off:** A slightly larger single diff for this one file
  (appending ~150 test methods) versus a clean no-op `git mv` for every
  other file — accepted, it's the only file with this property.
- **Alternatives considered:** Keep both files side by side under
  different names — rejected, actively worse (two files for one module,
  confusing for F09 or any future reader); delete the narrow pre-existing
  file and keep only the relocated legacy one — rejected, would lose the
  pre-existing file's history/test without a documented duplication
  check (its one test, `test_parse`, is parametrized differently than
  anything in the legacy file — confirmed not a literal duplicate during
  design).

### TD-003: Fix the path-import hazard per-file — dotted import where possible, `conftest.py` `sys.path` insertion where required

- **Decision:** The 4 affected files split into two different fixes,
  confirmed empirically during design (not deferred to implementation):
  - `test_maas_wipe.py`/`test_maas_wipe_defs.py`: rewrite
    `from snippets import ...`/`from snippets.tests.test_maas_wipe_defs
    import ...` to the real dotted path,
    `from metadataserver.user_data.templates.snippets import ...`/
    `from metadataserver.user_data.templates.snippets.tests.test_maas_wipe_defs
    import ...` — confirmed working standalone (`maas_wipe.py` has zero
    internal path-dependent imports, only stdlib).
  - `test_maas_run_remote_scripts.py`/`test_maas_run_scripts.py`:
    **cannot** use a dotted-import fix alone. Their production modules
    (`maas_run_remote_scripts.py`/`maas_run_scripts.py`) contain their
    own internal
    `except ImportError: from snippets.maas_api_helper import ...`
    fallback, explicitly commented `# imports from maas_api_helpers
    (only used in tests)` — this is deploy-time production code
    (curtin/cloud-init runs these scripts standalone, sibling to
    `maas_api_helper.py`, no package) that only resolves its *own*
    `snippets.maas_api_helper` import when `snippets` is reachable as a
    bare top-level package. Fix: add
    `src/tests/metadataserver/user_data/templates/snippets/conftest.py`
    inserting the `templates/` directory into `sys.path` at collection
    time (confirmed empirically: `sys.path.insert(0, ".../templates");
    from snippets import maas_run_remote_scripts` succeeds), reproducing
    pytest's original rootdir-insertion behavior explicitly rather than
    relying on directory-structure accident.
- **Why:** The dotted-import fix is preferred wherever sufficient
  (`test_maas_wipe.py` pair) since it adds no new test-infrastructure
  surface; the `conftest.py` `sys.path` insertion is only used where the
  *production* code's own fallback import forces it (the `maas_run_*`
  pair) — confirmed by direct reproduction, not assumed.
- **Trade-off:** One small `conftest.py` is added specifically for this
  one subdirectory — a narrow, single-purpose shim, not a general-purpose
  mechanism; scoped to exactly the 2 files that need it.
- **Alternatives considered:** Changing the production modules'
  own `except ImportError` fallback to a dotted import — rejected,
  out of scope (these are deployed standalone scripts, not something
  this test-infrastructure feature should restructure); `conftest.py`
  insertion for all 4 files uniformly — rejected, unnecessary for the
  `maas_wipe` pair which works via the simpler dotted-import fix.

### TD-004 (implementation-time): Extend F03's `_crochet_reactor` fixture
with the missing database thread-pool install

- **Decision:** `maastesting/pytest/legacy.py`'s session-scoped
  `_crochet_reactor` fixture now also calls
  `threads.install_default_pool(maxthreads=1)` and
  `threads.install_database_unpool(maxthreads=1)` (plus
  `reactor.callFromThread(orm.disable_all_database_connections)`),
  mirroring `maastesting/scripts.py`'s `run_region()` exactly.
- **Why:** Discovered during this feature's T5 verification (not
  anticipated by F03's design): any relocated legacy test that actually
  *calls* `deferToDatabase` (not just imports the module) failed with
  `AttributeError: 'EPollReactor' object has no attribute
  'threadpoolForDatabase'` — `nose`'s own entry point installs this
  thread-pool before running any test; F03's pytest shim only started
  the reactor via `setup_crochet()`, never installed the pool. This is
  a genuine fourth gap beyond F03's three (scenarios/reactor-start/
  `APITestCase`), confirmed reproducible in isolation
  (`test_api_twisted.py`'s `TestStatusWorkerServiceTransactional`, 9
  tests) and resolved after explicit user sign-off per NFR-002/F03's
  own TD-003 stop-and-ask discipline.
- **Trade-off:** Reopens F03's already-approved, already-shipped
  design/file — accepted, the alternative (a brand-new dedicated
  feature for a 3-line fix) adds process overhead disproportionate to
  the change; the fix is purely additive to the existing fixture, no
  existing shim behavior changes.
- **Alternatives considered:** A separate follow-up feature to extend
  F03 — rejected per user decision (fix now, keep F04 moving); a
  per-test opt-in fixture instead of extending the autouse one —
  rejected, would require every affected legacy file to be
  individually annotated, the opposite of `nose`'s own
  always-on behavior this feature must match.

### TD-005 (implementation-time): Split `test_fields.py`, not relocate
the legacy class alongside the gap-free one

- **Decision:** `src/metadataserver/tests/test_fields.py`'s
  `TestBin` (gap-free) relocates to
  `src/tests/metadataserver/test_fields.py`; `TestBinaryField`
  (`MAASLegacyTransactionServerTestCase`, `legacy = True`-tagged) stays
  at the original `src/metadataserver/tests/test_fields.py` path,
  unchanged, still covered by `nose`'s separate
  `run_region_legacy()`/`bin/test.region.legacy` path only.
- **Why:** Design §3.1 row 6 misclassified this file as "none" gap/
  fully gap-free — it actually mixes a gap-free class with a
  legacy-tagged one. `legacy`-tagged `DjangoTestCase`/
  `DjangoTransactionTestCase`-derived tests are explicitly out of scope
  for pytest support (idea 002); relocating the whole file would have
  also silently dropped it from `run_region_legacy()`'s own coverage,
  since that command selects tests by directory
  (`--select-dir=src/metadataserver`) via Django's native `manage.py
  test`, not by file content — the class would end up tested nowhere.
- **Trade-off:** One relocated file (row 6) is no longer a pure,
  unmodified `git mv` — it is a content split across two files/
  locations. Still zero *behavior* change for either resulting file
  (`TestBin`'s 4 tests pass identically at the new path;
  `TestBinaryField`'s 9 tests are completely untouched at the old
  path).
- **Alternatives considered:** Relocate the whole file with a
  `pytest.mark.skip` on `TestBinaryField` — rejected after confirming
  it would remove `TestBinaryField` from `run_region_legacy()`'s
  directory-based selection too (a coverage loss FR-004's own
  parity gate would have failed to catch, since skipped-not-deleted
  pytest items aren't what `run_region_legacy()` measures); leave the
  whole file untouched (defer entirely) — rejected, loses `TestBin`'s
  gap-free coverage for no reason.

### TD-006 (implementation-time): Repoint 3 `maasserver` test files'
cross-package imports of relocated `test_hooks.py`

- **Decision:** `src/maasserver/tests/test_storage_layouts.py`,
  `src/maasserver/api/tests/test_machine.py`, and
  `src/maasserver/models/tests/test_node.py` each imported test-support
  helpers (`make_lxd_output`, `make_lxd_output_json`,
  `create_numa_nodes`) directly from
  `metadataserver.builtin_scripts.tests.test_hooks` - a module path
  that no longer exists once T1 merges that file into
  `src/tests/metadataserver/builtin_scripts/test_hooks.py`. Fixed by
  repointing each import to the new dotted path under the `tests`
  package (`from tests.metadataserver.builtin_scripts import
  test_hooks` / `from tests.metadataserver.builtin_scripts.test_hooks
  import make_lxd_output`), confirmed resolvable because
  `pyproject.toml`'s `[tool.pytest] testpaths = ["src/tests"]` already
  makes `src/tests/__init__.py` a top-level importable package named
  `tests`. Added `"tests"` to `lint.isort.known-first-party` so ruff
  sorts the new cross-package import correctly.
- **Why:** None of these three files were in this feature's own
  disposition table (§3.1) - they are `maasserver` test files, not
  `metadataserver` ones, and the design-time triage only scanned
  `metadataserver`'s own 23 files for internal path hazards (TD-003),
  not for *other* packages' tests importing *into* a relocated file.
  This gap was only found via T4's full `bin/test.region` run, which
  failed with `ImportError` at collection time for
  `test_storage_layouts.py` (the other two files share the same
  broken import but hadn't yet been collected/reached when the first
  failure aborted nose's run); a full grep for all 23 relocated/split
  files' basenames found exactly these 3 external importers, 2 of
  which were otherwise undetected.
- **Trade-off:** None - zero behavior change, same module, same
  function identities, only the import path differs.
- **Alternatives considered:** Leave a backward-compatible re-export
  shim at the old `metadataserver/builtin_scripts/tests/test_hooks.py`
  path - rejected, conflicts with NFR-002 (no new permanent
  compatibility surface for a one-year-lifespan legacy stack) and
  papers over the real triage gap instead of fixing the 3 call sites
  directly.

### TD-007 (implementation-time): Accept FR-004's coverage `check` FAIL
as a structural, documented exception - not a defect to fix here

- **Decision:** `utilities/coverage-baseline check metadataserver`
  reports `verdict: FAIL` (measured 89.33% vs. the 95.05% baseline,
  -5.72pp) after T1-T4, and this is accepted as this feature's final
  state. Root cause fully explained, not a mystery or a different
  regression: `check` only runs the pytest-only suite
  (`_run_suite(legacy=False)`); the baseline was captured from pytest
  **and** `nose` combined (`capture`'s `_capture_one_pass`).
  `TestBinaryField` - kept under `nose`'s `run_region_legacy()` per
  TD-005, since it's `legacy`-tagged and out of this feature's scope -
  is the sole exerciser of `metadataserver/tests/models.py`,
  `metadataserver/tests/apps.py`, `metadataserver/admin.py` (all 0%
  under pytest-only) and most of `fields.py`'s `BinaryField` logic
  (53% alone, down from previously-combined-with-`TestBin` coverage).
  Confirmed via a scoped pytest-only `coverage report
  --include=src/metadataserver/*` run: these specific files/lines
  account for the entire measured delta (1008/1008 tests still pass;
  no test failure, no silently-dropped test - only a
  tooling-visibility gap for code still exercised by `nose`). Final
  T5 sign-off re-measurement (post-TD-008): 89.15% vs. 95.05%
  (-5.90pp) - within normal run-to-run variance of the figure above
  (F01's own design noted <0.3pp spread across repeat captures);
  confirms TD-008's unrelated `maastesting/testcase.py`/`noseplug.py`
  fix introduced no new regression to `metadataserver`'s coverage.
- **Why:** Requirements D-004 records this as accepted, not fixed here
  - see D-004 for the full reasoning (fixing `check` itself to also
  run legacy nose coverage is shared cross-package tooling work,
  correctly out of this feature's scope per NFR-002).
- **Trade-off:** F04 ships with FR-004's acceptance criterion in a
  documented-exception state rather than a clean PASS. The alternative
  (blocking F04 indefinitely on idea 002 landing first) was rejected -
  see D-004.
- **Alternatives considered:** Recapture/lower the baseline to 89.33%
  - rejected, this would silently discard the signal that
  `TestBinaryField`'s dependent modules have real, measurable coverage
  dropping out of `check`'s view, exactly what FR-004 exists to catch;
  extend `check` to also run `bin/test.region.legacy` - correct
  long-term fix, deferred to idea 002/a dedicated coverage-tooling
  follow-up since it touches shared tooling beyond this feature's files.

### TD-008 (implementation-time): Extract and apply `nose`'s Python 3.14
compat shim repo-wide, in `maastesting/testcase.py` too, not just
`noseplug.py`

- **Decision:** T5's own acceptance criterion ("full `pytest src/tests`
  passes") exposed that `maastesting/testcase.py` - imported by nearly
  every `MAASTestCase`-based file, including most of `metadataserver`'s
  relocated ones - unconditionally imports `nose.proxy`/`nose.tools` at
  module level, with no guard. `nose==1.3.7` itself imports
  `unittest._TextTestResult`/`unittest.runner._TextTestResult`, both
  removed in Python 3.14 (the repo's own declared
  `requires-python = ">=3.14"`). `noseplug.py` already had an inline
  shim restoring these names (and `collections.Callable`) before its
  own `nose` imports, but `testcase.py` imported `nose` directly,
  without it. Extracted the shim into a new, tiny
  `maastesting/_nose_compat.py`, imported (for its side effect, with an
  `# isort: skip` to keep it textually before the `nose` imports it
  must precede) by both `noseplug.py` and `testcase.py`.
- **Why:** This is a pre-existing, repo-wide gap (confirmed reproducing
  identically on HEAD before any F04 change, via `git stash`), not
  caused by metadataserver's relocation - but it directly blocks T5's
  literal acceptance criterion, since `pytest src/tests` (the exact
  invocation CI's own `bin/pytest` uses, given
  `testpaths = ["src/tests"]`) could never collect ~45 files
  repo-wide before this fix. Per direct user instruction, fixed here
  rather than deferred, since it is a one-file guard-import fix, not a
  design change, and unblocks the one acceptance criterion that most
  directly measures "no regression to the rest of the suite."
- **Trade-off:** Touches `maastesting/testcase.py`, a file outside
  `metadataserver`'s own tree - a narrow exception to this feature's
  file scope, justified by being a no-behavior-change, environment-only
  guard (identical pattern already established by `noseplug.py`), not
  new functionality.
- **Alternatives considered:** Scope T5's acceptance down to
  per-package pytest runs only (what was already passing) - rejected
  per direct user instruction in favor of fixing the actual blocker,
  since the fix is small, safe, and precedented.

## 14. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| The `conftest.py` `sys.path` insertion (TD-003) for `test_maas_run_remote_scripts.py`/`test_maas_run_scripts.py` is scoped too broadly or too narrowly (e.g. affects unrelated collection elsewhere in `src/tests/metadataserver/`) | Low | Confirmed empirically during design (TD-003) that the insertion works for the two files needing it; verification (§15) re-confirms post-relocation, scoped to exactly that one `conftest.py`'s directory per pytest's own `conftest.py` scoping rules (applies only to its own directory and subdirectories). |
| The `test_hooks.py` merge (TD-002) silently drops the pre-existing narrow file's one test during the merge | Low | Verification (§15) explicitly checks post-merge test count = pre-existing count (1) + legacy count (155), not just "file compiles". |
| `run_region()`'s `--select-dir=src/metadataserver` no-op assumption (§3.3) is wrong — nose errors on an empty/non-existent select-dir rather than silently finding 0 tests | Low | Verification (§15) runs the full `bin/test.region` suite after relocation and confirms exit code 0 with the expected reduced test count, not just that it doesn't crash on an isolated check. |
| **(materialized, accepted — TD-007/D-004)** Coverage check (FR-004) fails - not because of `coverage.py`'s per-package filtering (that theory was wrong; filtering by production source tree works correctly, confirmed), but because `check` only measures pytest coverage and TD-005's `TestBinaryField` (kept under `nose`) is the sole exerciser of 3 production modules | Medium | Root-caused via scoped `coverage report` (TD-007); accepted as a documented, structural exception (D-004) rather than fixed here - correct fix is shared coverage-tooling work out of this feature's scope. |
| **(materialized, resolved — TD-004)** A relocated legacy test calling `deferToDatabase` fails under pytest because F03's shim never installed the reactor's database thread-pool | Medium | Fixed in `_crochet_reactor` (TD-004); re-verified: `test_api_twisted.py` 50/50 pass post-fix (was 41/50). |
| **(materialized, resolved — TD-005)** A gap-free/legacy-tagged class mix in one file (`test_fields.py`) was misclassified as fully gap-free in §3.1's original design-time triage | Low | Caught during T5's full-suite verification, before sign-off; fixed by splitting the file (TD-005); design §3.1 row 6 corrected to match. |
| **(materialized, resolved — TD-006)** 3 `maasserver` test files import `make_lxd_output`/`create_numa_nodes` helpers directly from `metadataserver.builtin_scripts.tests.test_hooks`, a module path removed by T1's merge - design's triage never scanned for *external* packages importing *into* relocated files | Medium | Found via T4's full `bin/test.region` collection failure (`ImportError`), confirmed by grepping all 23 relocated/split files' basenames repo-wide; all 3 call sites repointed to `tests.metadataserver.builtin_scripts.test_hooks`, re-verified passing under `nose` (144/144, `test_storage_layouts.py`) before re-running the full suite. |
| **(materialized, resolved — TD-008)** T5's own "full `pytest src/tests` passes" acceptance criterion failed repo-wide (~45 collection errors, not scoped to `metadataserver`) - `maastesting/testcase.py` imports `nose` unguarded against Python 3.14's removal of `unittest._TextTestResult`, unlike `noseplug.py`'s own existing inline shim | Medium | Confirmed pre-existing via `git stash` (reproduces identically at HEAD, unrelated to F04's relocation); fixed by extracting the shim into `maastesting/_nose_compat.py`, imported by both files; re-verified full `pytest src/tests` collects without error and `bin/test.region.legacy` still passes under `nose`. |

## 15. Verification Strategy

- **Collection check:** `pytest --collect-only src/tests/metadataserver`
  after relocation — 0 collection errors, confirms every one of the 23
  files (merged into the final file count per TD-002) collects cleanly,
  including the 5 gap-touching files relying on F03's shim and the 4
  path-import-fixed files.
- **Count check:** Post-relocation pytest test count for
  `src/tests/metadataserver/**` matches the sum of each individual
  relocated/merged file's own collected count (verified per-file at
  T1-T3, not re-derived from the static 927/918 `def test_` estimate,
  which `testscenarios` multiplication makes unreliable as a total) —
  measured: 1008 (full suite, `-n 2`), 0 behavior silently dropped.
- **Merge check (TD-002):** `test_hooks.py`'s post-merge test count
  equals 1 (pre-existing) + its legacy predecessor's own count.
- **Nose drop check (FR-003):** `find src/metadataserver -name
  'test_*.py'` returns exactly `tests/test_fields.py` (TD-005's
  intentional exception); `bin/test.region`'s reported test count
  drops compared to its pre-cutover baseline (13013, F03's T5) — the
  static 918-test-definition estimate (927 minus `TestBinaryField`'s 9)
  undercounts `testscenarios` multiplication; T4's actual measured run
  is the acceptance criterion, not the estimate (measured: 13013 →
  12024, a drop of 989, `SKIP=11` unchanged from baseline, 0 failures).
- **Coverage check (FR-004):** `utilities/coverage-baseline check
  metadataserver` reports `verdict: FAIL` (measured 89.33% vs. the
  95.05% baseline, -5.72pp) - accepted per D-004/TD-007 as a
  structural, documented exception (`check` only measures pytest
  coverage; `TestBinaryField`'s dependent modules are still tested,
  just under `nose`), not a defect requiring further code change here.
- **Full regression:** `bin/test.rack` (provisioningserver, unaffected —
  confirms no cross-package regression) and the full `pytest src/tests`
  run (confirms metadataserver's new tests pass alongside every other
  already-pytest-native package).
- **Build/lint:** `make lint` across all moved/modified files.

## 16. Implementation FAQ

**Q:** Why zero deletions, when requirements (FR-002) explicitly allow
deleting a gap-touching file if its coverage is duplicated?
**A:** Design-time triage (§3.1) found no case where a gap-touching
file's behavior is already covered by another test — all 5 are the only
tests for their respective modules/paths. FR-002's delete branch stays
available as a path, but this feature's actual disposition table has
nothing to delete. If implementation discovers a genuine duplicate not
visible at design time, stop and name the specific duplicate test before
deleting, per FR-002's own requirement text — do not delete speculatively.

**Q:** Why do `test_maas_run_remote_scripts.py`/`test_maas_run_scripts.py`
need a `conftest.py` while `test_maas_wipe.py`/`test_maas_wipe_defs.py`
only need a dotted-import rewrite?
**A:** Confirmed by direct reproduction during design (TD-003):
`maas_wipe.py` has zero internal path-dependent imports (stdlib only),
so rewriting its *test file's* import to a dotted path is sufficient.
`maas_run_remote_scripts.py`/`maas_run_scripts.py` (the production
modules under test) contain their own internal
`except ImportError: from snippets.maas_api_helper import ...` fallback
— rewriting only the *test file's* import doesn't change what the
*production module itself* does when executed, so the bare `snippets`
package must still be resolvable via `sys.path`, hence the scoped
`conftest.py`.


**Q:** Why keep `--select-dir=src/metadataserver` in `run_region()`
rather than removing it now that the directory structurally has no
tests left?
**A:** `maasserver`'s own relocation (F06/F07) is still pending; the
line's twin, `--select-dir=src/maasserver`, is still load-bearing.
Removing only the `metadataserver` line changes `scripts.py`, a file
this feature's requirements (Out of Scope) don't name, for a
zero-behavior-difference cleanup — safe to defer to F08 (nose retirement),
which already plans to delete this whole invocation.
