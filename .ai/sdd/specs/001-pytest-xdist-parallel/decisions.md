# Decisions: pytest-xdist parallel infra (F01)

## F01 scope clarification — nose is not retired by this feature

**Context:** `.ai/sdd/PLAN.md`'s Phase 1 feature map describes F01 as
"Replace `test.parallel`'s nose-based orchestration with `pytest-xdist`."
Read literally, this could be misunderstood as F01 removing or disabling
`nose`/`test.parallel`.

**Decision:** F01 does **not** touch, disable, or remove
`test.parallel`, `maastesting/noseplug.py`, the `nose` dependency, or any
nose-run suite (`test.region`, `test.rack`, `test.region.legacy`). F01
only validates the pytest-xdist invocation pattern
(`utilities/run-py-tests-ci`) against the suite that is already
pytest-native today (`src/tests/**`). Nose continues running unchanged
in CI until F03–F06 migrate suites off it and F07 retires nose entirely.

**Reason:** `pytest-xdist` distributes test items within a single pytest
collection session; it cannot orchestrate `test.parallel`'s current model
of spawning `test.region`/`test.rack`/`test.region.legacy` as separate
nose subprocesses (see `requirements.md` D-001, `design.md` TD-002).

**Source:** Design-phase clarification during `/skill:sdd-spec`,
confirmed during `/skill:sdd-exec` T6.

**Impacts:** `.ai/sdd/PLAN.md` F01 row (read in conjunction with this
note — no table wording changed), `requirements.md` D-001, `design.md`
TD-002, design.md §14 Risks (mitigates the "PLAN.md wording"
misread risk).

## Recorded verification evidence (F01 tasks T1–T6)

- **T1:** No competing worker-count/xdist configuration found outside
  `utilities/run-py-tests-ci`.
- **T2:** Baseline run — 7949 tests collected, 7766 passed, 2 failed
  (pre-existing, unrelated — `test_etag` in
  `test_resource_pools.py`/`test_zones.py`, hardcoded hash assertions,
  reproduced without xdist, last touched by unrelated commit
  `60a2eef16`), 181 skipped. 202.62s pytest-internal / 209.89s
  wall-clock at 4 workers.
- **T3:** Concurrency override confirmed — `MAAS_MAX_TEST_PROCESSES=2`
  produces only `gw0`/`gw1` worker IDs (no `gw2`+), 381.26s runtime.
- **T4:** `junit-pytest.xml` well-formed, 7949 `<testcase>` elements
  exactly matching `tests="7949"` attribute; no translation step needed
  (native pytest `--junit-xml` output).
- **T5:** Repeat run — identical counts (7766/2/181) both times, same
  failing tests both runs; no added flakiness.
- **T6:** This file; baseline also recorded in `design.md` §11.
