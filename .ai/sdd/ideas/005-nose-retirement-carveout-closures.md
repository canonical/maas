# Idea: Closing the two remaining nose carve-outs (idea 002 + idea 004)

> Status: exploring
> Created: 2026-11-19
> Source: F04-F06 completion; the two carve-outs left under nose

## Raw Idea

F04-F06 relocated all migratable `metadataserver`, `provisioningserver`,
and `maasserver` tests to pytest. Two carve-outs still require nose,
blocking F08 (full nose retirement):

- **Idea 002** — 10 `legacy`-tagged test classes (region legacy leg,
  `MAAS_PREVENT_MIGRATIONS` gap-3).
- **Idea 004** — 39 `MAASTwistedRunTest` files (rack leg, per-test
  reactor vs always-on crochet reactor).

Both were captured separately. This surveys their closure designs
**together**, because they share one mechanism.

## Survey findings (confirmed 2026-11-19)

### Shared mechanism: Direction A (dedicated pytest invocation) fits both

Both ideas list "separate pytest invocation/process" as their
lowest-risk direction. The mechanisms are the *same shape* — run a
subset under pytest with a specific process configuration that the main
suite doesn't use:

- **Idea 002's Direction A:** a pytest leg with
  `MAAS_PREVENT_MIGRATIONS=1` set *before* `django.setup()`, so the
  test-only models get real tables. Process-global settings conflict is
  sidestepped by process isolation, mirroring `run_region_legacy()`'s
  own isolation today.
- **Idea 004's Direction A:** a pytest leg that does **not** start
  crochet's always-on reactor, so `MAASTwistedRunTest`'s per-test
  reactor owns the process. Mirrors `bin/test.rack`'s own isolation.

### Idea 004 has two real sub-problems, not one

Confirmed live (this survey):

1. **The reactor conflict is real.** Under normal pytest (shim's crochet
   running), `MAASTwistedRunTest` files fail with
   `twisted.internet.error.ReactorAlreadyRunning` (12 failed in
   `test_common.py` alone). Crochet and per-test reactors genuinely
   cannot coexist in one process — Twisted's own invariant.
2. **`run_tests_with` is not honored by pytest's unittest collector.**
   The F03 shim ignores it entirely; the `MAASTwistedRunTest.make_factory`
   wrapper (which drives the deferred chain and catches
   missing-`inlineCallbacks` generators) never runs under pytest. So
   even with crochet off, the files don't execute the way they do under
   nose.

Disabling the whole `maas-legacy` plugin (`-p no:maas-legacy`) removes
crochet **but also removes scenario multiplication**, breaking files
that depend on scenario injection (e.g. `test_common.py`'s `self.seq`/
`self.box`). So the closure needs scenarios **on**, crochet **off**,
and `run_tests_with` **honored** — three independent knobs, not a
single toggle.

### Idea 002 is blocked on settings, not runner mechanics

The 10 legacy classes fail under pytest with
`psycopg2.OperationalError: database "no_such_db" does not exist` —
Django's app registry is configured once per process with the *opposite*
`INSTALLED_APPS`/`MIGRATION_MODULES` than these tests need. No
in-process fix exists. Idea 002's three directions:
- **A (separate process):** lowest risk, mirrors today's isolation, but
  adds a permanent third CI leg.
- **B (migration-backed test models):** removes the conflict entirely
  but is a non-trivial change to `maasserver.tests`/`metadataserver.tests`
  migrations that real features depend on.
- **C (rewrite off DjangoTestCase):** most invasive, but eliminates the
  root dependency; touches test logic for the 10 classes.

## Closure design options

### Option 1 — One shared "dedicated pytest leg" mechanism for both

Build a single configurable pytest invocation (entry point or tox env)
that runs a named subset with a specific process config, and instantiate
it twice: once with `MAAS_PREVENT_MIGRATIONS=1` + no-crochet for idea
002, once with no-crochet + `run_tests_with` honored for idea 004.
Converges the two carve-outs onto one mechanism; nose's two remaining
legs become two pytest legs.

**Cost:** two new CI legs (net zero vs today's two nose legs); a
`run_tests_with` bridge in the shim; scenario/crochet knob separation.
**Risk:** low — mirrors existing process isolation, no test-content
changes. **Leaves:** pytest becomes the only runner, nose fully
retirable (F08 unblocked).

### Option 2 — Close idea 004 by rewriting to crochet (Direction B)

Rewrite the 39 files off `MAASTwistedRunTest` onto the crochet model,
eliminating the carve-out entirely. **Cost:** 39 files re-verified for
behavior equivalence, some using trial-style deferred assertions.
**Risk:** medium-high, per-file judgement at scale. Only addresses
idea 004; idea 002 still needs its own closure.

### Option 3 — Close idea 002 by rewriting off DjangoTestCase (Direction C)

Port the 10 legacy classes to `MAASServerTestCase`-style resource
management. **Cost:** 10 classes, test-logic changes. **Risk:** medium —
sidesteps all three gaps permanently. Only addresses idea 002.

## Recommendation

**Option 1** — one shared dedicated-pytest-leg mechanism, instantiated
for both carve-outs. It's the only option that closes *both* without
touching test logic, mirrors existing process isolation, and unblocks
F08 cleanly. Options 2 and 3 are single-carve-out, higher-effort, and
don't compose — choosing them means solving the two problems twice with
two different techniques.

**Spike-validated 2026-11-19:** the "one open question" is answered —
all three knobs work together with zero test-file changes. Running 3
`MAASTwistedRunTest` files (`test_utils`, `test_common`, `test_power`,
77 tests) under pytest with **scenarios-on + crochet-off +
`run_tests_with` honored** passes 77/77, both serially and under
`-n 2 --dist=load`. The mechanism:

- **crochet-off:** an env-gate in the `_crochet_reactor` session fixture
  calling `setup_crochet(no_setup=True)` instead of `setup_crochet()`.
  Registers `EventualResult` interop but does not start the always-on
  reactor, leaving the process free for `MAASTwistedRunTest`'s per-test
  reactor. (Plugin-registered autouse fixtures can't be overridden by a
  same-named `-p` fixture — an env-gate or a config option is the clean
  mechanism.)
- **`run_tests_with` honored:** requires no bridge. testtools' `run()`
  instantiates `self.__RunTest` from the class's `run_tests_with`
  property/factory, so a class declaring `MAASTwistedRunTest.make_factory`
  is executed by that factory under pytest's unittest runner
  automatically. Verified directly: the factory object is created and
  the deferred chain runs to completion (1 test, 0 errors).
- **scenarios-on:** the existing `_expand_scenarios` shim, unchanged.

## Open Questions

- ~~Does the `run_tests_with` bridge belong in the shim or a separate
  plugin?~~ **Answered (spike):** no bridge is needed. testtools' `run()`
  honors a class's `run_tests_with` property automatically, so no shim
  change is required for the executor — only the crochet env-gate.
- Is a second/third pytest leg acceptable to CI as a permanent
  architecture, or is the goal ultimately one pytest process (which
  would force Options 2/3 eventually anyway)? **Open — needs a CI/
  architecture decision from the team.**
- ~~Does idea 004 need `EventualResult` interop or only
  `inlineCallbacks`?~~ **Answered:** all 39 work with
  `setup_crochet(no_setup=True)` (37 use only `inlineCallbacks`; the 2
  exceptions are benign — `test_plugin.py` mocks `no_setup`,
  `test_twisted.py` only asserts `EventualResult` type). The `no_setup`
  toggle already exists in `maastesting.crochet.setup_crochet`.

## Spike-validated mechanism (2026-11-19)

All three knobs work together with zero test-file changes. 3
`MAASTwistedRunTest` files (77 tests) pass under pytest with
scenarios-on + crochet-off + `run_tests_with` honored, serially and
under `-n 2 --dist=load`. Only remaining design work: the env-gate /
config mechanism for the dedicated leg, and the CI-leg decision above.
