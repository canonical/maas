# Copyright 2009-2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

# pylint: disable-msg=E0702

"""Test helper, copied from the Launchpad source tree."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'FakeMethod',
    'MultiFakeMethod',
    ]


class FakeMethod:
    """Catch any function or method call, and record the fact.

    Use this for easy stubbing.  The call operator can return a fixed
    value, or raise a fixed exception object.

    This is useful when unit-testing code that does things you don't
    want to integration-test, e.g. because it wants to talk to remote
    systems.
    """

    def __init__(self, result=None, failure=None):
        """Set up a fake function or method.

        :param result: Value to return.
        :param failure: Exception to raise.
        """
        self.result = result
        self.failure = failure

        # A log of arguments for each call to this method.
        self.calls = []

    def __call__(self, *args, **kwargs):
        """Catch an invocation to the method.

        Increment `call_count`, and adds the arguments to `calls`.

        Accepts any and all parameters.  Raises the failure passed to
        the constructor, if any; otherwise, returns the result value
        passed to the constructor.
        """
        self.calls.append((args, kwargs))

        if self.failure is None:
            return self.result
        else:
            # pylint thinks this raises None, which is clearly not
            # possible.  That's why this test disables pylint message
            # E0702.
            raise self.failure

    @property
    def call_count(self):
        return len(self.calls)

    def extract_args(self):
        """Return just the calls' positional-arguments tuples."""
        return [args for args, kwargs in self.calls]

    def extract_kwargs(self):
        """Return just the calls' keyword-arguments dicts."""
        return [kwargs for args, kwargs in self.calls]


class MultiFakeMethod:
    """Return a method whose behavior is derived from a list of methods.

    When called repeatedly, this method will call all the methods used to
    built it in turn, one after the other.

    This can be used, for instance, to simulate a temporary failure.
    >>> simulate_failures = MultiFakeMethod(
            [FakeMethod(failure=raised_exception)] * number_of_failures +
            [FakeMethod()])
    """

    def __init__(self, methods):
        self.methods = methods
        self._call_count = -1

    def __call__(self, *args, **kwargs):
        self._call_count = self._call_count + 1
        if self._call_count < len(self.methods):
            return self.methods[self._call_count](*args, **kwargs)
        else:
            raise ValueError(
                "No more method to call.  This MultiFakeMethod has been "
                "called %d times and it only contains %d method(s)." % (
                    self._call_count + 1, len(self.methods)))
