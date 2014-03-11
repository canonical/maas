# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with asynchronous operations."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "gather",
]

from itertools import count
from Queue import Queue

from crochet import wait_for_reactor
from maasserver.exceptions import IteratorReusedError
from twisted.internet import reactor
from twisted.internet.defer import maybeDeferred
from twisted.python import log


class UseOnceIterator:
    """An iterator that is usable only once."""

    def __init__(self, *args):
        """Create a new :class:`UseOnceIterator`.

        Takes the same arguments as iter().
        """
        self.iterable = iter(*args)
        self.has_run_once = False

    def __iter__(self):
        return self

    def next(self):
        if self.has_run_once:
            raise IteratorReusedError(
                "It is not possible to reuse a UseOnceIterator.")
        try:
            return self.iterable.next()
        except StopIteration:
            self.has_run_once = True
            raise


@wait_for_reactor
def gather(calls, timeout=10.0):
    """gather(calls, timeout=10.0)

    Issue calls into the reactor, passing results back to another thread.

    :param calls: An iterable of no-argument callables to be called in
        the reactor thread. Each will be called via
        :py:func:`~twisted.internet.defer.maybeDeferred`.

    :param timeout: The number of seconds before further results are
        ignored. Outstanding results will be cancelled.

    :return: A :class:`UseOnceIterator` of results. A result might be a
        failure, i.e. an instance of
        :py:class:`twisted.python.failure.Failure`, or a valid result;
        it's up to the caller to check.

    """

    # Prepare of a list of Deferreds that we're going to wait for.
    deferreds = [maybeDeferred(call) for call in calls]

    # We'll use this queue (thread-safe) to pass results back.
    queue = Queue()

    # A sentinel to mark the end of the results.
    done = object()

    # This function will get called if not all results are in before
    # `timeout` seconds have passed. It puts `done` into the queue to
    # indicate the end of results, and cancels all outstanding deferred
    # calls.
    def cancel():
        queue.put(done)
        for deferred in deferreds:
            try:
                deferred.cancel()
            except:
                log.err()

    if timeout is None:
        canceller = None
    else:
        canceller = reactor.callLater(timeout, cancel)

    countdown = count(len(deferreds), -1)

    # Callback to report the result back to the queue. If it's the last
    # result to be reported, `done` is put into the queue, and the
    # delayed call to `cancel` is itself cancelled.
    def report(result):
        queue.put(result)
        if next(countdown) == 1:
            queue.put(done)
            if canceller is not None:
                if canceller.active():
                    canceller.cancel()

    for deferred in deferreds:
        deferred.addBoth(report)

    # If there are no calls then there will be no results, so we put
    # `done` into the queue, and cancel the nascent delayed call to
    # `cancel`, if it exists.
    if len(deferreds) == 0:
        queue.put(done)
        if canceller is not None:
            canceller.cancel()

    # Return an iterator to the invoking thread that will stop at the
    # first sign of the `done` sentinel.
    return UseOnceIterator(queue.get, done)
