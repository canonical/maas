# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""pytest plugin closing the two "gap shims" needed to run `nose` +
`testscenarios`/`crochet`-style legacy tests under pytest, without
rewriting the legacy files themselves:

- Scenario multiplication (``testscenarios``-style ``scenarios`` class
  attribute), applied at collection time (see
  ``pytest_collection_modifyitems``).
- Twisted reactor startup via `crochet`, matching the retired `nose`
  runner's Crochet plugin lifecycle (see ``_crochet_reactor``).
"""

import functools
import os
import sys
import types

import pytest

from maastesting.crochet import setup_crochet


def _effective_scenarios(cls, method_name):
    """Return `cls`'s effective, fully-merged `scenarios` list, or
    `None` if `cls` has no `scenarios` attribute at all.

    Some base classes (notably `maasserver.testing.api.APITestCaseBase`)
    merge additional scenarios (e.g. one per user/client factory
    combination) into `self.scenarios` from `__init__`, rather than
    exposing the merged result as a class attribute. Build one
    throwaway instance (cheap: `__init__` only merges attributes, it
    does not touch the database - that happens in `setUp`) to read the
    scenarios actually in effect, rather than the raw, possibly
    incomplete `cls.scenarios`. Classes with no `scenarios` attribute
    at all (the common case) are skipped without instantiating them.
    """
    if not hasattr(cls, "scenarios"):
        return None
    instance = cls(method_name)
    return instance.scenarios


def _expand_scenarios(module_collector, cls, method_names):
    """Build one dynamically-named subclass of `cls` per scenario entry
    in its effective, fully-merged scenarios list, collect each via
    pytest's own unittest machinery, and return the resulting items.

    `testscenarios.generate_scenarios()` itself operates on test
    *instances*, multiplying them after pytest has already picked one
    (un-multiplied) instance per method. To get pytest's own collector
    to treat each scenario as a first-class, separately reported item
    (correct IDs, correct fixtures), the multiplication instead happens
    at the *class* level: one subclass per scenario, each exposed as a
    module attribute so pytest's standard collection hooks can find and
    collect it exactly as they would any other `unittest.TestCase`
    subclass.
    """
    scenarios = _effective_scenarios(cls, method_names[0])
    module = sys.modules[cls.__module__]
    items = []
    # Sort by scenario name: some scenario sources are unordered
    # collections whose iteration order is process-dependent (e.g.
    # storage_layouts.py's STORAGE_LAYOUTS is a frozenset, iterated in
    # id()/address order). Under xdist each worker would otherwise expand
    # the same class into the same subclasses in a different ORDER,
    # tripping xdist's "Different tests were collected between gwN and
    # gwM" consistency check. Sorting by name makes the expansion
    # deterministic across workers.
    for scenario_name, scenario_vars in sorted(
        scenarios, key=lambda entry: entry[0]
    ):
        subclass_name = f"{cls.__name__}[{scenario_name}]"
        attrs = {}
        for key, value in scenario_vars.items():
            # testscenarios' own apply_scenario() sets scenario values on
            # the *instance* (setattr(newtest, key, value)), which never
            # triggers descriptor binding. Setting a callable as a *class*
            # attribute instead (necessary here, since the multiplication
            # happens at class level - see module docstring) would make
            # attribute access bind it as a method, silently passing
            # `self` as an extra argument. Wrap such callables in
            # staticmethod to match instance-attribute-set semantics.
            # This must cover plain functions/lambdas AND functools.partial
            # values: partial is a descriptor (partial.__get__ returns a
            # bound method) and so binds `self` identically when left
            # unwrapped (observed as `has no attribute 'node'` in
            # maasserver test_auth.py). Real descriptors that manage their
            # own binding correctly (property, classmethod, staticmethod)
            # are left alone.
            if isinstance(value, (types.FunctionType, functools.partial)):
                value = staticmethod(value)
            attrs[key] = value
        attrs["scenarios"] = None
        # Suppress base classes (e.g. APITestCaseBase) that merge
        # further scenarios from these attributes in their own
        # __init__ - the merge has already happened in
        # _effective_scenarios above; re-running it here would multiply
        # the same scenario again.
        if "userfactory" in scenario_vars:
            attrs["userfactories"] = None
        if "clientfactory" in scenario_vars:
            attrs["clientfactories"] = None
        subclass = type(subclass_name, (cls,), attrs)
        subclass.__module__ = cls.__module__
        # Expose the subclass on the module so pytest's own collection
        # hooks can discover it the same way they discover any other
        # module-level TestCase subclass.
        setattr(module, subclass_name, subclass)
        result = module_collector.ihook.pytest_pycollect_makeitem(
            collector=module_collector, name=subclass_name, obj=subclass
        )
        collectors = result if isinstance(result, list) else [result]
        for collector in collectors:
            if collector is None:
                continue
            if hasattr(collector, "collect"):
                items.extend(collector.collect())
            else:
                items.append(collector)
    return items


def pytest_collection_modifyitems(session, config, items):
    """Apply `testscenarios`-style scenario multiplication to collected
    unittest items whose class has a non-empty effective `scenarios`
    list.

    pytest's own unittest collector has no notion of ``scenarios``: it
    collects exactly one (un-multiplied) item per test method. This
    hook replaces those un-multiplied items with the full,
    scenario-multiplied set, matching `nose` + `testscenarios`'
    behavior (the retired nose runner's ``--with-scenarios`` plugin
    applied the same multiplication, at the same, pre-instance
    granularity).
    """
    by_class = {}
    for item in items:
        cls = getattr(item, "cls", None)
        if cls is None:
            continue
        by_class.setdefault(cls, []).append(item)

    expanded = {}
    for cls, class_items in by_class.items():
        method_names = [item.name for item in class_items]
        scenarios = _effective_scenarios(cls, method_names[0])
        if not scenarios:
            continue
        module_collector = class_items[0].parent.parent
        expanded[cls] = _expand_scenarios(module_collector, cls, method_names)

    if not expanded:
        return

    seen = set()
    new_items = []
    for item in items:
        cls = getattr(item, "cls", None)
        if cls in expanded:
            if cls not in seen:
                new_items.extend(expanded[cls])
                seen.add(cls)
            continue
        new_items.append(item)
    items[:] = new_items


@pytest.fixture(scope="session", autouse=True)
def _crochet_reactor():
    """Start the Twisted reactor once per pytest session, matching the
    retired `nose` runner's Crochet plugin lifecycle (always on, once
    per process) so `deferToDatabase`/`inlineCallbacks`-based legacy
    tests work under pytest without a reactor-not-started error.
    """
    # The MAASTwistedRunTest carve-out spins up its own
    # per-test reactor, which is incompatible with this always-on
    # reactor (Twisted allows only one per process). The dedicated
    # rack-legacy leg runs those files with MAAS_PYTEST_NO_CROCHET=1 to
    # register EventualResult interop WITHOUT starting the reactor, so
    # the per-test-reactor files own the process's reactor lifecycle.
    if os.environ.get("MAAS_PYTEST_NO_CROCHET"):
        setup_crochet(no_setup=True)
    else:
        setup_crochet()

        # Mirrors the retired nose runner's `run_region()` entry point:
        # it installed a reactor-wide, single-threaded database
        # thread-pool before any test ran, so
        # `maasserver.utils.threads.deferToDatabase` has somewhere to
        # dispatch to. Without this, any relocated legacy test that
        # actually calls `deferToDatabase` (not just imports it) fails
        # with `AttributeError: 'EPollReactor' object has no attribute
        # 'threadpoolForDatabase'` under plain pytest.
        from twisted.internet import reactor as _reactor

        from maasserver.utils import orm, threads

        if getattr(_reactor, "threadpool", None) is None:
            threads.install_default_pool(maxthreads=1)
        if getattr(_reactor, "threadpoolForDatabase", None) is None:
            threads.install_database_unpool(maxthreads=1)
            _reactor.callFromThread(orm.disable_all_database_connections)

    # Mirror the level-name side effect of the retired nose runner's
    # `run_region()` calling `logger.configure(mode=LoggingMode.COMMAND)`
    # once per process: that call runs make_logging_level_names_consistent(),
    # which renames the standard `logging` levels to Twisted's lower-case
    # forms. A test that captures logs with FakeLogger and asserts on
    # `%(levelname)s` (e.g. maasserver test_views.py's "debug:"/"error:")
    # depends on that global mutation having happened; without it the
    # stdlib's upper-case "DEBUG:"/"ERROR:" leak through and the assertion
    # fails. Call only the rename, not logger.configure() itself: the full
    # configure also installs a Twisted log observer, which breaks xdist
    # worker startup when run from this fixture (observed: workers die at
    # "bringing up nodes..." under -n 4).
    from provisioningserver.logger._common import (
        make_logging_level_names_consistent,
    )

    make_logging_level_names_consistent()
