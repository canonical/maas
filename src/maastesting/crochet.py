# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Support for testing with `crochet`."""

from functools import wraps
import inspect

import crochet
from testtools.content import Content, UTF8_TEXT
from twisted.internet.defer import ensureDeferred
import wrapt

from maastesting import get_testing_timeout


def setup_crochet(no_setup=False):
    """Start (or inhibit starting) the Twisted reactor via Crochet.

    Used by the pytest runner (`maastesting.pytest.legacy`); it was
    originally shared with the retired `nose` runner so both started the
    reactor identically: once per process, with the same
    `EventualResult` patching applied first.
    """
    # Remove deprecated crochet APIs.
    if hasattr(crochet, "wait_for_reactor"):
        del crochet.wait_for_reactor
    if hasattr(crochet.EventLoop, "wait_for_reactor"):
        del crochet.EventLoop.wait_for_reactor
    if hasattr(crochet, "DeferredResult"):
        del crochet.DeferredResult

    # Make a default timeout forbidden.
    class EventualResult(crochet.EventualResult):
        def _result(self, timeout=None):
            if timeout is None:
                raise AssertionError("A time-out must be specified.")
            else:
                return super()._result(timeout)

    # Patch it back into crochet.
    crochet._eventloop.EventualResult = EventualResult
    crochet.EventualResult = EventualResult

    if no_setup:
        crochet.no_setup()
    else:
        crochet.setup()

    # Prevent the default STDLibLogObserver from forwarding Twisted
    # log events into Python's logging module, which may try to write
    # to a closed stream (closed test-capture handler) and crash with
    # "I/O operation on closed file". Replace the observer with the
    # production-style one that writes directly to sys.__stdout__.
    from twisted.logger import globalLogPublisher

    from provisioningserver.logger._twisted import EventLogger

    globalLogPublisher._observers = [EventLogger()]


class EventualResultCatchingMixin:
    """A mix-in for tests that checks for unfired/unhandled `EventualResults`.

    It reports about all py:class:`crochet.EventualResults` that are unfired
    or whose results have not been retrieved. A test detail is recorded for
    each, then the test is force-failed at the last moment.
    """

    def setUp(self):
        super().setUp()
        try:
            # Every EventualResult that crochet creates is registered into
            # this registry. We'll check it after the test has finished.
            registry = crochet._main._registry
        except AttributeError:
            # Crochet has not started, so we have nothing to check right now.
            pass
        else:
            # The registry stores EventualResults in a WeakSet, which means
            # that unfired and unhandled results can be garbage collected
            # before we get to see them. Here we patch in a regular set so
            # that nothing gets garbage collected until we've been able to
            # check the results.
            results = set()
            self.addCleanup(
                self.__patchResults,
                registry,
                self.__patchResults(registry, results),
            )
            # While unravelling clean-ups is a good time to check the results.
            # Any meaningful work represented by an EventualResult should have
            # done should been done by now.
            self.addCleanup(self.__checkResults, results)

    def __patchResults(self, registry, results):
        with registry._lock:
            originals = registry._results
            registry._results = set()
            return originals

    def __checkResults(self, eventual_results):
        fail_count = 0

        # Go through all the EventualResults created in this test.
        for eventual_result in eventual_results:
            # If the result has been retrieved, fine, otherwise look closer.
            if not eventual_result._result_retrieved:
                fail_count += 1

                try:
                    # Is there a result waiting to be retrieved?
                    result = eventual_result.wait(timeout=0)
                except crochet.TimeoutError:
                    # No result yet. This could be because the result is wired
                    # up to a Deferred that hasn't fired yet, or because it
                    # hasn't yet been connected.
                    if eventual_result._deferred is None:
                        message = [
                            "*** EventualResult has not fired:\n",
                            f"{eventual_result!r}\n",
                            "*** It was not connected to a Deferred.\n",
                        ]
                    else:
                        message = [
                            "*** EventualResult has not fired:\n",
                            f"{eventual_result!r}\n",
                            "*** It was connected to a Deferred:\n",
                            f"{eventual_result._deferred!r}\n",
                        ]
                else:
                    # A result, but nothing has collected it. This can be
                    # caused by forgetting to call wait().
                    message = [
                        "*** EventualResult has fired:\n",
                        f"{eventual_result!r}\n",
                        "*** It contained the following result:\n",
                        f"{result!r}\n",
                        "*** but it was not collected.\n",
                        "*** Was result.wait() called?\n",
                    ]

                # Record the details with a unique name.
                message = [block.encode("utf-8") for block in message]
                self.addDetail(
                    "Unfired/unhandled EventualResult #%d" % fail_count,
                    Content(UTF8_TEXT, lambda: message),  # noqa: B023
                )

        assert fail_count == 0, (
            "Unfired and/or unhandled EventualResult(s); see test details."
        )


class TimeoutInTestException(Exception):
    """Nicer reporting of what actually timed-out."""

    def __init__(self, function, fargs, fkwargs, timeout, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # It's not useful to see all the decorators
        self.function = inspect.unwrap(function)
        self.args = fargs
        self.kwargs = fkwargs
        self.timeout = timeout

    def __str__(self):
        return f"Timeout after {self.timeout}s running {self.function.__name__} with args {self.args!r} and kwargs {self.kwargs!r}"


def wait_for(timeout=None):
    """Backport of wait_for from Crochet 2.0.

    This allows async def definitions to be used.
    """
    timeout = get_testing_timeout(timeout)

    def decorator(function):
        def wrapper(function, _, args, kwargs):
            @crochet.run_in_reactor
            def run():
                if inspect.iscoroutinefunction(function):
                    return ensureDeferred(function(*args, **kwargs))
                else:
                    return function(*args, **kwargs)

            eventual_result = run()
            try:
                return eventual_result.wait(timeout)
            except crochet.TimeoutError:
                eventual_result.cancel()
                raise TimeoutInTestException(function, args, kwargs, timeout)  # noqa: B904

        if inspect.iscoroutinefunction(function):
            # Create a non-async wrapper with same signature.
            @wraps(function)
            def non_async_wrapper():
                pass

        else:
            # Just use default behavior of looking at underlying object.
            non_async_wrapper = None

        wrapper = wrapt.decorator(wrapper, adapter=non_async_wrapper)
        return wrapper(function)

    return decorator
