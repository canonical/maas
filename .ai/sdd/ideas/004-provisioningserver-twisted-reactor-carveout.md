# Idea: Run `MAASTwistedRunTest` carve-out tests under pytest, not just nose

> Status: captured
> Created: 2026-11-18
> Source: F05 (`008-provisioningserver-cutover`) D-002, TD-001

## Raw Idea

F05 cuts `provisioningserver`'s 90 migratable test files over to
pytest, leaving 39 files carved out because they declare
`run_tests_with = MAASTwistedRunTest.make_factory(...)`: testtools'
own per-test Twisted reactor lifecycle manager. These 39 files
continue running under `nose` (`bin/test.rack`), unaffected by F05 —
not dead code, actively tested and passing today. This idea captures
what closing that fourth gap would require.

## Problem Space (confirmed via F05 design-time investigation, D-002)

`MAASTwistedRunTest` spins up and tears down a **fresh Twisted reactor
per test method**. This is structurally incompatible, within a single
pytest process, with the **always-on crochet reactor** that F03
(`maasserver`/`metadataserver`) and F05's own 90 migrated
`provisioningserver` files depend on (`crochet.setup()` called once at
process start, reactor runs for the process's whole lifetime).

Two reactor lifecycle models cannot coexist in one pytest worker
process:

1. **Crochet's model** (used by the 90 already-migrated files):
   `crochet.setup()` starts the reactor once; `deferToDatabase`-style
   calls dispatch onto it from synchronous test code; the reactor
   outlives every individual test.
2. **`MAASTwistedRunTest`'s model** (used by these 39 carve-out
   files): testtools' `Spinner` starts a **new** reactor for each test
   method, runs the test's deferred chain to completion against it,
   and tears it down — assuming no other reactor is already running in
   the process.

Running both models in the same pytest worker means either crochet's
reactor is already up when `MAASTwistedRunTest` tries to start its
own (fails — only one reactor per process, Twisted's own invariant),
or vice versa. No per-test or per-fixture reconciliation is possible
within a single process; this is a process-level, not a test-level,
conflict.

## The 39-file carve-out list

Complete, confirmed list: `.ai/sdd/specs/008-provisioningserver-cutover/design.md` §4
("Carve-out files (39, FR-007, D-002)"). Re-verified unchanged
(39/39, zero diff against design time) at F05 T1's implementation-time
re-grep. 3 of the 39 are FIPS/hardening-relevant
(`drivers/power/tests/test_virsh.py`, `rackdservices/tests/test_external.py`,
`utils/tests/test_network.py` — design.md §4's FIPS cross-reference).

## Possible Directions (not yet evaluated/chosen)

- **Separate pytest invocation/process for this subset**, mirroring
  `nose`'s own `bin/test.rack`/`bin/test.region` process split today —
  tests still run under pytest's runner/reporting, just in a dedicated
  process that never calls `crochet.setup()`, so `MAASTwistedRunTest`'s
  per-test reactor has the process to itself. Likely the lowest-risk
  option: no change to the 39 test files or to `MAASTwistedRunTest`
  itself, only to how/where that pytest invocation is launched (a new
  CI leg, a `pytest.ini`/`tox` environment, or a `maas-rack`-style
  entry point parallel to F03's `maas-region` one).
- **Rewrite the 39 files to use crochet's reactor model instead of
  `MAASTwistedRunTest`** — removes the carve-out entirely, but is the
  most invasive option: every file's `run_tests_with` declaration and
  any reactor-dependent setup/teardown assumptions would need
  per-file re-verification that behavior is unchanged, at real scale
  (39 files, some using Twisted's `trial`-style deferred assertions
  directly).
- **Defer to `nose` retirement (F08)** — if/when `nose` itself is
  retired project-wide, this carve-out forces a harder decision
  anyway (there will be no `nose` left to carry these 39 files), so
  closing the gap now may be premature relative to that larger
  decision. Lowest short-term effort, but leaves `nose` as a live
  dependency for an indefinite period solely because of these 39
  files, undermining F08's own goal.

## Open Questions

- Does closing this gap belong to a dedicated feature of its own, or
  should it be folded into F08 (nose retirement) directly, since `nose`
  cannot actually be removed from the repo until this carve-out is
  resolved one way or another?
- Is a second pytest invocation/process (Direction A) an acceptable
  permanent architecture, or only a stepping stone — i.e. does CI
  tolerate a second "pytest leg" indefinitely, or is the goal
  ultimately a single pytest process for all of `provisioningserver`?
- Do any of the 39 carve-out files' tests actually exercise
  cross-reactor-state interaction with the 90 already-migrated files
  (e.g. shared module-level state), which Direction A's process
  isolation would silently preserve as two independent test runs
  rather than surface as a bug?
