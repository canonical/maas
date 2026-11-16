# Design: Minimal gap shims for pytest-native legacy test execution

> Status: Approved

## 1. Summary

Add one new pytest plugin module, `maastesting/pytest/legacy.py`,
registered via the existing `pytest11` entry-point convention
(`pyproject.toml`), that closes two of the three identified gaps:

- **FR-001 (scenarios):** a `pytest_collection_modifyitems` hook that
  calls `testscenarios.generate_scenarios()` against each collected
  unittest-style test class with a non-empty `scenarios` attribute,
  replacing the un-multiplied items pytest's own unittest collector
  produced with the full scenario-multiplied set.
- **FR-002 (reactor/crochet):** a session-scoped, autouse fixture that
  calls the same `crochet.setup()`-plus-patching sequence
  `maastesting/noseplug.py`'s `Crochet` nose plugin already performs,
  refactored into a shared helper both plugins call, so the two
  runners start the reactor identically.

A third, independent one-line fix in `maasserver/testing/api.py`
(FR-003) moves `APITestCaseBase.__init__`'s scenario computation out of
`__init__` (which pytest's unittest collector invokes on the abstract
base itself, with `userfactories = None`) into a form that tolerates an
unset `userfactories`/`clientfactories` without raising at collection
time, while leaving concrete subclasses' (populated via `forUsers`)
scenario computation unchanged.

## 2. Requirements Mapping

| Requirement | Design Coverage |
|-------------|-----------------|
| FR-001 | §3.1 |
| FR-002 | §3.2 |
| FR-003 | §3.3 |
| FR-004 | §3.1-§3.3 (each shim is a no-op/unaffected for gap-free files — see Edge Cases) |
| NFR-001 | §9 (reactor started once per session, not per test; scenario hook is pure data transformation, no shared mutable state across tests) |
| NFR-002 | §13 TD-003 (explicit scope boundary; any fourth gap stops implementation) |

## 3. Technical Approach

### 3.1 Scenario application shim (FR-001)

New hook in `maastesting/pytest/legacy.py`:

```python
import testscenarios

def pytest_collection_modifyitems(session, config, items):
    """Apply testscenarios' own multiplication to unittest-style items
    pytest already collected un-multiplied, because pytest's unittest
    collector does not know about the ``scenarios`` class attribute.
    """
    seen_classes = set()
    new_items = []
    for item in items:
        cls = getattr(item, "cls", None)
        if cls is None or cls in seen_classes:
            # Non-unittest item, or a class already expanded below.
            new_items.append(item)
            continue
        scenarios = getattr(cls, "scenarios", None)
        if not scenarios:
            new_items.append(item)
            continue
        seen_classes.add(cls)
        # Reuse pytest's own unittest collector to build one TestCaseFunction
        # per (scenario, method) pair: construct one multiplied subclass per
        # scenario instance (testscenarios' own generate_scenarios operates
        # on *instances*, not classes, so this adapts it at class granularity
        # instead, matching nose's own per-class, not per-instance, expansion
        # timing).
        ...
    items[:] = new_items
```

The exact mechanism (detailed further during implementation, not
finalized at design time) multiplies at the **class**, not instance,
level: build one dynamically-named subclass per scenario entry (mirroring
`APITestType.forUsers`'s own established pattern of returning a `type(...)`
subclass already used elsewhere in this codebase — see §16 FAQ), with
each scenario's dict applied as class attributes, then re-collect that
subclass's test methods via pytest's own `Class`/`UnitTestCase` collector
so the resulting items are indistinguishable from any other
pytest-collected unittest item (correct IDs, correct fixtures, correct
`cls`). This avoids reimplementing `testscenarios.generate_scenarios()`'s
instance-level semantics while still using its exact scenario-merging
logic (calling it against a throwaway instance per scenario to validate
the merged attribute dict matches what `nose` + `testscenarios` would
have produced, then applying that dict at the class level instead of the
instance level pytest's collector requires).

### 3.2 Reactor/crochet session startup shim (FR-002)

Refactor the reactor-starting body currently inlined in
`maastesting/noseplug.py`'s `Crochet.configure()` into a shared function,
`maastesting.crochet.setup_crochet()`, called from both:

- `noseplug.py`'s `Crochet.configure()` (unchanged behavior, now calling
  the shared function instead of inlining the same code)
- `maastesting/pytest/legacy.py`'s new session-scoped, **autouse**
  fixture:

```python
@pytest.fixture(scope="session", autouse=True)
def _crochet_reactor():
    from maastesting.crochet import setup_crochet
    setup_crochet()
```

Autouse (not opt-in) because FR-002's acceptance criteria requires any
reactor-dependent legacy file to work without per-file/per-test
annotation — matching `nose`'s own behavior, where `--with-crochet` is a
global nose invocation flag, not a per-test marker. Session-scoped so it
runs exactly once, matching D-001.

### 3.3 `APITestCase` collection-time fix (FR-003)

In `maasserver/testing/api.py`, `APITestCaseBase.__init__` currently does:

```python
scenarios_users = tuple(
    ("user=%s" % name, {"userfactory": self.userfactories[name]})
    for name in sorted(self.userfactories)
)
```

`sorted(self.userfactories)` raises `TypeError: 'NoneType' object is not
iterable` when `userfactories` is still the class-level default (`None`)
— true only for the **abstract** `APITestCaseBase`/`APITestCase` classes
themselves, never for a concrete `.ForUser`/`.ForAdmin`/etc. subclass
(which always has a real `dict` from `APITestType.forUsers`). `nose`
never instantiates the abstract base (its own class/method selection
does not construct every `TestCase` subclass in a module's namespep —
only pytest's unittest collector does, once per discovered test id,
including for the abstract base class if a module happens to expose it
unqualified). Fix:

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    # Create scenarios for userfactories and clientfactories. These are
    # None only on the abstract base classes themselves (never on a
    # concrete forUsers()-derived subclass, which always provides a real
    # dict) - treat that case as "no scenarios to add" rather than
    # raising, so pytest's unittest collector can construct the abstract
    # base without error when it enumerates test ids.
    userfactories = self.userfactories or {}
    scenarios_users = tuple(
        ("user=%s" % name, {"userfactory": userfactories[name]})
        for name in sorted(userfactories)
    )
    self.userfactories = ()
    clientfactories = self.clientfactories or {}
    scenarios_clients = tuple(
        ("client=%s" % name, {"clientfactory": clientfactories[name]})
        for name in sorted(clientfactories)
    )
    self.clientfactories = ()
    self.scenarios = merge_scenarios(
        scenarios_users, scenarios_clients, self.scenarios
    )
```

`clientfactories` already defaults to a non-`None` dict
(`{"oauth": MAASSensibleOAuthClient}`) at the class level, so only the
`userfactories` guard is strictly required to fix the reported
`TypeError`; the `clientfactories or {}` guard is added for symmetry and
defense against a future subclass that sets `clientfactories = None`
explicitly (rare, but costs nothing and avoids a second gap report).

## 4. Component / Module Structure

```text
maastesting/pytest/legacy.py   # new: scenario + reactor pytest plugin
maastesting/crochet.py         # modify: add setup_crochet(), extracted from noseplug.py
maastesting/noseplug.py        # modify: Crochet.configure() calls the shared setup_crochet()
maasserver/testing/api.py      # modify: APITestCaseBase.__init__ None-tolerant
pyproject.toml                 # modify: register entry-points.pytest11.maas-legacy
```

## 5. Data Model / State

Not applicable — no persistent state. The reactor fixture's only shared
state is the Twisted reactor itself (process-global, started once per
session, identical to `nose`'s own lifecycle per D-001).

## 6. API / Integration Contract

- New pytest11 entry point: `entry-points.pytest11.maas-legacy =
  "maastesting.pytest.legacy"`, alongside the existing
  `maas-database`/`maas-django`/`maas-environment`/`maas-perftest`/
  `maas-seeds`/`maas-sqlalchemy` entries.
- `maastesting.crochet.setup_crochet()` is a new, small public function;
  `noseplug.py`'s `Crochet` plugin becomes a thin caller of it (no
  behavior change for `nose`'s own invocation).
- No change to `APITestCase`/`APITestCaseBase`'s existing public
  surface — same attributes, same `setUp()` contract, same
  `.ForUser`/`.ForAdmin`/etc. properties.

## 7. Security / Permissions / Privacy

Not applicable.

## 8. User Flows

Not applicable — build/test-time only; no end-user-facing flow.

## 9. Edge Cases

| Case | Expected Behavior |
|------|--------------------|
| A unittest-style class with a non-empty `scenarios` attribute, collected by pytest | One test item per scenario instance, named/IDed distinctly, matching `nose`'s own per-scenario test count (FR-001 AC1). |
| A unittest-style class with an empty or absent `scenarios` attribute | `getattr(cls, "scenarios", None)` is falsy; item passes through `pytest_collection_modifyitems` unchanged (FR-001 AC2, FR-004). |
| A non-unittest (plain pytest function/fixture-based) test item | Has no `.cls`, or `.cls` has no `scenarios` attribute; passes through unchanged — the hook only touches unittest-style classes. |
| A pytest session with no reactor-dependent tests at all | The autouse fixture still runs once (session-scoped autouse), starting the reactor unconditionally — matches `nose`'s own unconditional `--with-crochet` behavior (always on unless `--crochet-no-setup`); negligible cost (crochet's own setup is lightweight), and simpler than conditionally detecting reactor-dependent tests up front. |
| `APITestCaseBase`/`APITestCase` (abstract) collected directly by pytest's unittest collector | `userfactories`/`clientfactories` default to `None`/a real dict respectively; the `or {}` guard means `__init__` computes empty scenario tuples instead of raising — class collects successfully with zero scenario-derived test items beyond whatever the abstract base's own (if any) test methods produce. |
| A concrete `.ForUser`/`.ForAdmin`/etc. subclass | `userfactories`/`clientfactories` are real, non-empty dicts (from `APITestType.forUsers`); behavior is bit-for-bit identical to today — the `or {}` guard is never triggered (FR-003 AC2). |
| A file that is gap-free (147 of 496) | None of the three shims' conditions trigger (no `scenarios`, no reactor-dependent calls exercised at collection time, no `APITestCase` subclass) — zero behavior change (FR-004). |

## 10. Accessibility / UX Notes

Not applicable.

## 11. Observability / Operations

Not applicable — no runtime/production behavior change; test-infra only.
Collection-time errors from a genuinely new (fourth) gap surface as
ordinary pytest collection errors, visible in the same way any other
collection failure is today (no new suppression added by this design).

## 12. Migration / Rollout

- **Rollout:** All three shims land together behind the new
  `maas-legacy` pytest11 entry point and the `api.py` fix; both are
  additive/corrective, not gated behind any flag — any gap-tier file,
  once relocated to `src/tests/` by a future package cutover (F04-F07),
  picks up the shim automatically via standard pytest plugin discovery.
  Nothing here relocates any file itself.
- **Rollback:** Remove the `maas-legacy` entry point line and delete
  `maastesting/pytest/legacy.py`; revert the `api.py` and
  `noseplug.py`/`crochet.py` refactor. All changes are independently
  revertable.

## 13. Technical Decisions

### TD-001: One combined plugin module, not one per gap

- **Decision:** `maastesting/pytest/legacy.py` holds both the scenario
  hook (FR-001) and the reactor fixture (FR-002) in one module/one
  entry point, rather than two separate plugin files.
- **Why:** Both exist solely to support relocated legacy files (the
  same target file population); splitting them into two registered
  plugins adds entry-point bookkeeping with no isolation benefit, since
  neither can be meaningfully enabled without the other for a
  gap-tier file that needs both (e.g. a scenario-using, reactor-dependent
  test).
- **Trade-off:** Slightly less granular if a future feature wants only
  one of the two mechanisms — judged unlikely given both close gaps for
  the same file population (legacy tests being relocated).
- **Alternatives considered:** Two plugins (`maas-legacy-scenarios`,
  `maas-legacy-reactor`) — rejected, unnecessary split per above.

### TD-002: Reactor setup refactored into a shared helper, not duplicated

- **Decision:** Extract `noseplug.py`'s `Crochet.configure()` body into
  `maastesting.crochet.setup_crochet()`, called from both the existing
  nose plugin and the new pytest fixture.
- **Why:** D-001 requires pytest's reactor lifecycle to match `nose`'s
  own exactly (same `EventualResult` patching, same `crochet.setup()`
  call) — duplicating that logic risks silent drift between the two
  runners' behavior over time. A shared helper guarantees they stay
  identical by construction, and `maastesting/crochet.py` is already the
  established home for crochet-related test support
  (`EventualResultCatchingMixin`, `wait_for`).
- **Trade-off:** Touches `noseplug.py` (a file otherwise out of scope
  per F02's requirements) — acceptable here because F03's own
  requirements explicitly require matching `nose`'s crochet lifecycle
  (D-001), and the refactor is behavior-preserving for `nose` itself
  (verified in §15).
- **Alternatives considered:** Duplicate the setup code in
  `legacy.py` (rejected — drift risk per above); call `nose`'s own
  `Crochet` plugin class from pytest (rejected — couples the pytest
  shim to a nose-specific `Plugin` base class/API for no benefit).

### TD-003: Scope boundary enforced per NFR-002 — no speculative fourth-gap handling

- **Decision:** This design implements exactly FR-001 through FR-003.
  No defensive code is added for hypothetical additional incompatibilities
  not yet observed in the 349 gap-tier files.
- **Why:** `PLAN.md`'s Risk table and NFR-002 both require a
  stop-and-reassess on any newly discovered fourth gap, not a
  silently-widened shim (the same discipline F02 applied when
  `collections.Callable` was discovered mid-implementation — there, the
  user was asked before extending scope; the same process applies here
  if implementation surfaces a fourth gap).
- **Trade-off:** Implementation may need to pause and request scope
  clarification if a fourth gap is found — accepted, matches
  `PLAN.md`'s explicit risk mitigation and this plan's established
  precedent (F02 D-003).
- **Alternatives considered:** None — this is a direct restatement of
  an already-approved requirement (NFR-002), not a new design choice.

## 14. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| A fourth gap (beyond scenarios/reactor/`APITestCase`) surfaces when this shim is exercised against the full 349-file gap-tier sample, not just the representative sample named in requirements' Success Signal | Medium | Per TD-003/NFR-002: stop and ask the user before extending scope; do not silently patch further. |
| The class-level scenario-multiplication mechanism (§3.1) behaves subtly differently from `testscenarios`' own instance-level `generate_scenarios()` for some scenario shape not covered by the representative sample (e.g. scenarios that mutate shared state, or nested/scenario-of-scenario classes) | Medium | Verification (§15) explicitly compares pytest's post-shim test count and IDs against `nose`'s reported scenario count for the same file, for a representative file from each gap tier, not just a synthetic example. |
| Refactoring `noseplug.py`'s `Crochet` plugin to call a shared helper regresses `nose`'s own existing, working behavior | Low | Verification (§15) re-runs the full `nose` suite (`bin/test.rack`/`bin/test.region`) after the refactor to confirm identical pass count to the pre-refactor baseline, not just the new pytest path. |
| The `APITestCaseBase.__init__` fix masks a genuine future bug (e.g. a concrete subclass accidentally leaving `userfactories` unset, silently getting zero scenarios instead of the loud `TypeError` it gets today) | Low | `setUp()`'s existing `if not callable(self.userfactory): raise AssertionError(...)` check (already present, unmodified) still fires for any concrete subclass missing a real user factory — the loud failure moves from `__init__`-time to `setUp()`-time (still before any test body runs), not eliminated. |

## 15. Verification Strategy

- **Unit/component:** Add focused tests (new or extended) exercising:
  - `pytest_collection_modifyitems` against a small throwaway
    fixture class with a `scenarios` attribute — confirm item count
    matches scenario count and each item's constructed instance carries
    the expected scenario attributes.
  - `setup_crochet()` — confirm it is callable from both `noseplug.py`
    and the pytest fixture context without error, and that the reactor
    is running afterward.
  - `APITestCaseBase.__init__` — confirm direct instantiation (simulating
    pytest's collection-time construction) no longer raises, and that a
    `forUsers(...)`-derived subclass's scenarios are unchanged from
    before the fix.
- **Integration/manual:** Per requirements' Success Signal — pick one
  representative file from each of the three gap tiers (a
  scenario-using file, a reactor/crochet-using file, a file with
  `APITestCase` subclasses) and confirm:
  1. The file now collects and passes under pytest with the shim
     active (0 collection errors, same pass/fail outcome as `nose`).
  2. The same file's `nose` run (today's baseline) is unaffected —
     identical pass count before and after this feature lands.
  3. The 147 already-gap-free files continue to pass unmodified (spot
     check a handful, not all 147 — full-suite regression is covered by
     `bin/test.rack`/`bin/test.region`'s own CI run).
- **Build/lint:** `make lint` (Ruff over all modified/new Python files).

## 16. Implementation FAQ

**Q:** Why build a from-scratch class-multiplication mechanism in §3.1
instead of calling `testscenarios.generate_scenarios()` directly on each
pytest-collected item?
**A:** `generate_scenarios()` operates on an already-constructed test
*instance* and yields multiplied *instances*; pytest's own unittest
collector decides *which methods to construct instances for* before any
plugin hook runs, so by the time `pytest_collection_modifyitems` sees
`items`, pytest has already picked one (un-multiplied) instance per
method. The multiplication has to happen at the class level (producing
N subclasses, each independently collected) for pytest's own collector
machinery (IDs, fixtures, reporting) to treat each scenario as a
first-class separate item, matching `nose`'s own per-class scenario
expansion timing (nose's `--with-scenarios` plugin expands before test
instantiation too, per `maastesting/noseplug.py`'s own
`Scenarios`/`WithScenarios`-adjacent handling).

**Q:** Why extract `setup_crochet()` into `maastesting/crochet.py`
rather than leaving it in `noseplug.py` and importing it from there?
**A:** `noseplug.py` imports `nose` at module level (see F02's own
compat shim, which runs before those imports) — importing from
`noseplug.py` inside a pytest plugin would needlessly pull in `nose`
itself as a pytest-time dependency. `maastesting/crochet.py` has no such
import and is already the established home for crochet test-support
code.

**Q:** Does the `APITestCaseBase.__init__` fix change what scenarios a
concrete subclass receives?
**A:** No — `or {}` only changes behavior when the attribute is
genuinely `None`/falsy (true only for the abstract base). Every
concrete `.ForUser`-style subclass already has a real, non-empty dict
from `APITestType.forUsers`, so `userfactories or {}` evaluates to the
same dict `userfactories` already was.
