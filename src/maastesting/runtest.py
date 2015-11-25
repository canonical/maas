# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test executors for MAAS."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'MAASRunTest',
    'MAASTwistedRunTest',
    ]

import sys
import types

from testtools import (
    deferredruntest,
    runtest,
)
from twisted.internet import defer


class InvalidTest(Exception):
    """Signifies that the test is invalid; it's not a good test."""


def check_for_generator(result):
    if isinstance(result, types.GeneratorType):
        raise InvalidTest(
            "Test returned a generator. Should it be "
            "decorated with inlineCallbacks?")
    else:
        return result


class MAASRunTest(runtest.RunTest):
    """A specialisation of testtools' `RunTest`.

    It catches a common problem when writing tests for Twisted: forgetting to
    decorate a test with `inlineCallbacks` that needs it.

    Tests in `maas`, `maasserver`, and `metadataserver` run with a Twisted
    reactor managed by `crochet`. It can be easy to decorate a test that
    contains a ``yield`` with ``@wait_for_reactor`` or ``@asynchronous``,
    forget the crucial ``@inlineCallbacks``, but see that it passes... because
    it's not actually running.

    This is another reason why you should see your test fail before you make
    it pass, but why not have the computer check too?
    """

    def _run_user(self, function, *args, **kwargs):
        """Override testtools' `_run_user`.

        `_run_user` is used in testtools for running functions in the test
        case that should not normally return a generator, so we check that
        here, as it's a good sign that a test case (or `setUp`, or `tearDown`)
        is yielding without `inlineCallbacks` to support it.
        """
        try:
            result = function(*args, **kwargs)
            return check_for_generator(result)
        except KeyboardInterrupt:
            raise
        except:
            # TODO blake_r: Remove once we are using python3. This is needed
            # because Django sets __cause__ manually on the exception and it
            # does not set __traceback__. Since the traceback2 module is being
            # used this causes an issue. Once python3 is used it handles the
            # __traceback__ on __cause__ automatically.
            # See: https://github.com/testing-cabal/testtools/issues/162
            sysinfo = sys.exc_info()
            if hasattr(sysinfo[1], '__cause__'):
                sysinfo[1].__cause__.__traceback__ = None
            return self._got_user_exception(sysinfo)


class MAASTwistedRunTest(deferredruntest.AsynchronousDeferredRunTest):
    """A specialisation of testtools' `AsynchronousDeferredRunTest`.

    It catches a common problem when writing tests for Twisted: forgetting to
    decorate a test with `inlineCallbacks` that needs it.

    Tests in `maas`, `maasserver`, and `metadataserver` run with a Twisted
    reactor managed by `crochet`, so don't use this; it will result in a
    deadlock.
    """

    def _run_user(self, function, *args):
        """Override testtools' `_run_user`.

        `_run_user` is used in testtools for running functions in the test
        case that may or may not return a `Deferred`. Here we also check for
        generators, a good sign that a test case (or `setUp`, or `tearDown`)
        is yielding without `inlineCallbacks` to support it.
        """
        d = defer.maybeDeferred(function, *args)
        d.addCallback(check_for_generator)
        d.addErrback(self._got_user_failure)
        return d
