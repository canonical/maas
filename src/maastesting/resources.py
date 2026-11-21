# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Self-contained test-resource management, replacing `testresources`.

This is a faithful reimplementation of the `testresources` contract that
MAAS's shared DB resource managers (`maasserver.testing.resources`) and
`MAASTestCase.setUpResources`/`tearDownResources` depend on, with the
nose-specific result-reporting plumbing (`_call_result_method_if_exists`,
the `result` parameter) dropped — under pytest there is no nose
`TestResult` proxy to report resource lifecycle to.

The contract, kept identical to `testresources`:

- A manager holds at most one current resource, reference-counted by
  `getResource`/`finishedWith`. The first `getResource` builds it (via
  `make`, after building any declared dependencies); the last
  `finishedWith` cleans it (via `clean`). This reference counting is what
  lets a shared singleton (the pristine test database) be built once and
  reused across many tests instead of once per test.
- A resource is "dirty" when a test has marked it unsuitable for reuse
  (e.g. a shared DB with mutated rows). The next `getResource` on a dirty
  manager `reset`s the resource instead of reusing it.
"""

__all__ = [
    "TestResourceManager",
    "setUpResources",
    "tearDownResources",
]


class TestResourceManager:
    """Manage a single reusable resource, with reference counting.

    Subclasses override `make` to construct the resource and `clean` to
    tear it down. Dependencies are declared as a class-level `resources`
    list of `(name, manager)` tuples; dependency resources are built
    before and cleaned after the managed resource, and attached to it as
    attributes named by `name`.
    """

    resources = []

    def __init__(self):
        self._dirty = False
        self._uses = 0
        self._currentResource = None
        self.resources = list(getattr(self.__class__, "resources", []))

    # -- subclass hooks -------------------------------------------------

    def make(self, dependency_resources):
        """Construct and return the resource. Override in subclasses."""
        raise NotImplementedError("Override make to construct resources.")

    def clean(self, resource):
        """Tear down the resource. Override in subclasses."""

    # -- dependency-aware build/clean -----------------------------------

    def _make_all(self):
        dependency_resources = {}
        for name, manager in self.resources:
            dependency_resources[name] = manager.getResource()
        resource = self.make(dependency_resources)
        for name, value in dependency_resources.items():
            setattr(resource, name, value)
        return resource

    def _clean_all(self, resource):
        self.clean(resource)
        for name, manager in self.resources:
            manager.finishedWith(getattr(resource, name))

    def _reset(self, resource, dependency_resources):
        self.clean(resource)
        return self.make(dependency_resources)

    def _setResource(self, new_resource):
        self._currentResource = new_resource
        self._dirty = False

    # -- dirtiness ------------------------------------------------------

    def dirtied(self, resource):
        """Mark the current resource unsuitable for reuse by other tests."""
        self._dirty = True

    def isDirty(self):
        if self._dirty:
            return True
        for _name, manager in self.resources:
            if manager.isDirty():
                return True
        return False

    def reset(self, old_resource):
        """Return a clean version of a dirty resource."""
        if not self.isDirty():
            return old_resource
        dependency_resources = {}
        for name, manager in self.resources:
            dependency_resources[name] = manager.reset(
                getattr(old_resource, name)
            )
        resource = self._reset(old_resource, dependency_resources)
        for name, value in dependency_resources.items():
            setattr(resource, name, value)
        return resource

    # -- reference counting ---------------------------------------------

    def getResource(self):
        """Return the resource, building/resetting it if needed."""
        if self._uses == 0:
            self._setResource(self._make_all())
        elif self.isDirty():
            self._setResource(self.reset(self._currentResource))
        self._uses += 1
        return self._currentResource

    def finishedWith(self, resource):
        """Record one fewer user; clean the resource when it reaches zero."""
        self._uses -= 1
        if self._uses == 0:
            self._clean_all(resource)
            self._setResource(None)


def setUpResources(test, resources):
    """Assign each declared resource to an attribute on `test`."""
    for name, manager in resources:
        setattr(test, name, manager.getResource())


def tearDownResources(test, resources):
    """Release each resource held by `test` and remove the attribute."""
    for name, manager in resources:
        manager.finishedWith(getattr(test, name))
        delattr(test, name)
