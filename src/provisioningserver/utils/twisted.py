# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities related to the Twisted/Crochet execution environment."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'asynchronous',
    'callOut',
    'deferred',
    'DeferredValue',
    'deferToNewThread',
    'deferWithTimeout',
    'FOREVER',
    'IAsynchronous',
    'ISynchronous',
    'PageFetcher',
    'pause',
    'reactor_sync',
    'retries',
    'synchronous',
    'ThreadPool',
    'ThreadPoolLimiter',
    'ThreadUnpool',
    ]

from collections import Iterable
from contextlib import contextmanager
from functools import (
    partial,
    wraps,
)
from itertools import repeat
from operator import attrgetter
import sys
import threading

from crochet import run_in_reactor
from twisted.internet import reactor
from twisted.internet.defer import (
    AlreadyCalledError,
    CancelledError,
    Deferred,
    maybeDeferred,
    succeed,
)
from twisted.internet.threads import deferToThread
from twisted.python import (
    context,
    log,
    threadable,
    threadpool,
)
from twisted.python.failure import Failure
from twisted.python.reflect import fullyQualifiedName
from twisted.python.threadable import isInIOThread
from twisted.web.client import getPage
from zope import interface


undefined = object()
FOREVER = object()


def deferred(func):
    """Decorates a function to ensure that it always returns a `Deferred`.

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as asynchronous.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        return maybeDeferred(func, *args, **kwargs)
    return wrapper


class IAsynchronous(interface.Interface):
    """Denotes that a call to the provider will result in the execution of
    asynchronous or non-blocking code.

    Absence of this interface does not mean that a call will definitely not
    result in the execution of asynchronous/non-blocking code.
    """


def asynchronous(func=undefined, timeout=undefined):
    """Decorates a function to ensure that it always runs in the reactor.

    If the wrapper is called from the reactor thread, it will call straight
    through to the wrapped function. It will not be wrapped by `maybeDeferred`
    for example.

    If the wrapper is called from another thread, it will return a
    :py::class:`crochet.EventualResult`, as if it had been decorated with
    `crochet.run_in_reactor`.

    There's an additional convenience. If `timeout` has been specified, the
    :py:class:`~crochet.EventualResult` will be waited on for up to `timeout`
    seconds. This means that callers don't need to remember to wait. If
    `timeout` is `FOREVER` then it will wait indefinitely, which can be useful
    where the function itself handles time-outs, or where the called function
    doesn't actually defer work but just needs to run in the reactor thread.

    It is possible to programmatically determine if a function has been thusly
    decorated by checking if `IAsynchronous` is provided::

      if IAsynchronous.providedBy(a_function):
          ...  # a_function has been decorated with @asynchronous

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as asynchronous.
    """
    if func is undefined:
        return partial(asynchronous, timeout=timeout)

    if timeout is not undefined:
        if isinstance(timeout, (int, long, float)):
            if timeout < 0:
                raise ValueError(
                    "timeout must be >= 0, not %d"
                    % timeout)
        elif timeout is not FOREVER:
            raise ValueError(
                "timeout must an int, float, or undefined, not %r"
                % (timeout,))

    func_in_reactor = run_in_reactor(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        if threadable.ioThread is None or isInIOThread():
            return func(*args, **kwargs)
        elif timeout is undefined:
            return func_in_reactor(*args, **kwargs)
        elif timeout is FOREVER:
            return func_in_reactor(*args, **kwargs).wait()
        else:
            return func_in_reactor(*args, **kwargs).wait(timeout)

    # This makes it possible to reliably determine programmatically if a
    # function has been decorated with @asynchronous.
    interface.directlyProvides(wrapper, IAsynchronous)

    return wrapper


class ISynchronous(interface.Interface):
    """Denotes that a call to the provider will result in the execution of
    synchronous or blocking code.

    Absence of this interface does not mean that a call will definitely not
    result in the execution of synchronous/blocking code.
    """


def synchronous(func):
    """Decorator to ensure that `func` never runs in the reactor thread.

    If the wrapped function is called from the reactor thread, this will
    raise a :class:`AssertionError`, implying that this is a programming
    error. Calls from outside the reactor will proceed unaffected.

    There is an asymmetry with the `asynchronous` decorator. The reason
    is that it is essential to be aware when `deferToThread()` is being
    used, so that in-reactor code knows to synchronise with it, to add a
    callback to the :class:`Deferred` that it returns, for example. The
    expectation with `asynchronous` is that the return value is always
    important, and will be appropriate to the environment in which it is
    utilised.

    It is possible to programmatically determine if a function has been thusly
    decorated by checking if `ISynchronous` is provided::

      if ISynchronous.providedBy(a_function):
          ...  # a_function has been decorated with @synchronous

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as synchronous, or blocking.

    :raises AssertionError: When called inside the reactor thread.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        # isInIOThread() can return True if the reactor has previously been
        # started but has now stopped, so don't test isInIOThread() until
        # we've also checked if the reactor is running.
        if reactor.running and isInIOThread():
            raise AssertionError(
                "Function %s(...) must not be called in the "
                "reactor thread." % func.__name__)
        else:
            return func(*args, **kwargs)

    # This makes it possible to reliably determine programmatically if a
    # function has been decorated with @synchronous.
    interface.directlyProvides(wrapper, ISynchronous)

    return wrapper


@contextmanager
def reactor_sync():
    """Context manager that synchronises with the reactor thread.

    When holding this context the reactor thread is suspended, and the current
    thread is marked as the IO thread. You can then do almost any work that
    you would normally do in the reactor thread.

    The "almost" above refers to things that track state by thread, which with
    Twisted is not much. However, things like :py:mod:`twisted.python.context`
    may not behave quite as you expect.
    """
    # If we're already running in the reactor thread this is a no-op; we're
    # already synchronised with the execution of the reactor.
    if isInIOThread():
        yield
        return

    # If we're not running in the reactor thread, we need to synchronise
    # execution, being careful to avoid deadlocks.
    sync = threading.Condition()

    # When calling sync.wait() we specify a timeout of sys.maxint. The default
    # timeout of None cannot be interrupted by SIGINT, aka Ctrl-C, which can
    # be more than a little frustrating.

    def sync_io():
        # This runs in the reactor's thread. It first gets a lock on `sync`.
        with sync:
            # This then notifies a single waiter. That waiter will be the
            # thread that this context-manager was invoked from.
            sync.notify()
            # This then waits to be notified back. During this time the
            # reactor cannot run.
            sync.wait(sys.maxint)

    # Grab a lock on the `sync` condition.
    with sync:
        # Schedule `sync_io` to be called in the reactor. We do this with the
        # lock held so that `sync_io` cannot progress quite yet.
        reactor.callFromThread(sync_io)
        # Now, wait. This allows `sync_io` obtain the lock on `sync`, and then
        # awaken me via `notify()`. When `wait()` returns we once again have a
        # lock on `sync`. We're able to get this lock because `sync_io` goes
        # into `sync.wait()`, thus releasing its lock on it.
        sync.wait(sys.maxint)
        # Record the reactor's thread. This is safe to do now that we're
        # synchronised with the reactor.
        reactorThread = threadable.ioThread
        try:
            # Mark the current thread as the IO thread. This makes the
            # `asynchronous` and `synchronous` decorators DTRT.
            threadable.ioThread = threadable.getThreadID()
            # Allow this thread to execute while holding `sync`. The reactor
            # is prevented from spinning because `sync_io` is in `wait()`.
            yield
        finally:
            # Restore the IO thread.
            threadable.ioThread = reactorThread
            # Wake up `sync_io`, which can then run to completion, though not
            # until we release our lock on `sync` by exiting this context.
            sync.notify()


def retries(timeout=30, intervals=1, clock=reactor):
    """Helper for retrying something, sleeping between attempts.

    Returns a generator that yields ``(elapsed, remaining, wait)`` tuples,
    giving times in seconds. The last item, `wait`, is the suggested amount of
    time to sleep before trying again.

    :param timeout: From now, how long to keep iterating, in seconds. This can
        be specified as a number, or as an iterable. In the latter case, the
        iterator is advanced each time an interval is needed. This allows for
        back-off strategies.
    :param intervals: The sleep between each iteration, in seconds, an an
        iterable from which to obtain intervals.
    :param clock: An optional `IReactorTime` provider. Defaults to the
        installed reactor.
    """
    start = clock.seconds()
    end = start + timeout

    if isinstance(intervals, Iterable):
        intervals = iter(intervals)
    else:
        intervals = repeat(intervals)

    return gen_retries(start, end, intervals, clock)


def gen_retries(start, end, intervals, clock=reactor):
    """Helper for retrying something, sleeping between attempts.

    Yields ``(elapsed, remaining, wait)`` tuples, giving times in seconds. The
    last item, `wait`, is the suggested amount of time to sleep before trying
    again.

    This function works in concert with `retries`. It's split out so that
    `retries` can capture the correct start time rather than the time at which
    it is first iterated.

    :param start: The start time, in seconds, of this generator. This must be
        congruent with the `IReactorTime` argument passed to this generator.
    :param end: The desired end time, in seconds, of this generator. This must
        be congruent with the `IReactorTime` argument passed to this
        generator.
    :param intervals: A iterable of intervals, each in seconds, which should
        be used as hints for the `wait` value that's generated.
    :param clock: An optional `IReactorTime` provider. Defaults to the
        installed reactor.

    """
    for interval in intervals:
        now = clock.seconds()
        if now < end:
            wait = min(interval, end - now)
            yield now - start, end - now, wait
        else:
            yield now - start, end - now, 0
            break


def pause(duration, clock=reactor):
    """Pause execution for `duration` seconds.

    Returns a `Deferred` that will fire after `duration` seconds.
    """
    d = Deferred(lambda d: dc.cancel())
    dc = clock.callLater(duration, d.callback, None)
    return d


def deferWithTimeout(timeout, func=None, *args, **kwargs):
    """Call `func`, returning a `Deferred`.

    The `Deferred` will be cancelled after `timeout` seconds if not otherwise
    called.

    If `func` is not specified, or None, this will return a new
    :py:class:`Deferred` instance that will be cancelled after `timeout`
    seconds. Do not specify `args` or `kwargs` if `func` is `None`.

    :param timeout: The number of seconds before cancelling `d`.
    :param func: A callable, or `None`.
    :param args: Positional arguments to pass to `func`.
    :param kwargs: Keyword arguments to pass to `func`.
    """
    if func is None and len(args) == len(kwargs) == 0:
        d = Deferred()
    else:
        d = maybeDeferred(func, *args, **kwargs)

    timeoutCall = reactor.callLater(timeout, d.cancel)

    def done(result):
        if timeoutCall.active():
            timeoutCall.cancel()
        return result

    return d.addBoth(done)


def callOut(thing, func, *args, **kwargs):
    """Call out to the given `func`, but return `thing`.

    For example::

      d = client.fetchSomethingReallyImportant()
      d.addCallback(callOut, putKettleOn))
      d.addCallback(doSomethingWithReallyImportantThing)

    Use this where you need a side-effect when a :py:class:`~Deferred` is
    fired, but you don't want to clobber the result. Note that the result
    being passed through is *not* passed to the function.

    Note also that if the call-out raises an exception, this will be
    propagated; nothing is done to suppress the exception or preserve the
    result in this case.
    """
    return maybeDeferred(func, *args, **kwargs).addCallback(lambda _: thing)


def callOutToThread(thing, func, *args, **kwargs):
    """Call out to the given `func` in another thread, but return `thing`.

    For example::

      d = client.fetchSomethingReallyImportant()
      d.addCallback(callOutToThread, watchTheKettleBoil))
      d.addCallback(doSomethingWithReallyImportantThing)

    Use this where you need a side-effect when a :py:class:`~Deferred` is
    fired, but you don't want to clobber the result. Note that the result
    being passed through is *not* passed to the function.

    Note also that if the call-out raises an exception, this will be
    propagated; nothing is done to suppress the exception or preserve the
    result in this case.
    """
    return deferToThread(func, *args, **kwargs).addCallback(lambda _: thing)


class DeferredValue:
    """Coordination primitive for a value.

    Or a "Future", or a "Promise", or ...

    :ivar waiters: A set of :py:class:`Deferreds`, each of which has been
        handed to a caller of `get`, and which will be fired when `set` is
        called... or ``None``, immediately after `set` has been called.
    :ivar capturing: A `Deferred` from which the value or failure will be
        recorded, or `None`. The value or failure *will not* be passed back
        into the callback chain. If this `DeferredValue` is cancelled,
        `capturing` *will* also be cancelled.
    :ivar observing: A `Deferred` from which the value or failure will be
        recorded, or `None`. The value or failure *will* be passed back into
        the callback chain. If this `DeferredValue` is cancelled, `observing`
        *will not* be cancelled.
    :ivar value: The recorded value. This will not be present until the moment
        it is actually recorded; i.e. ``my_deferred_value.value`` will raise
        `AttributeError`.
    """

    def __init__(self):
        super(DeferredValue, self).__init__()
        self.waiters = set()
        self.capturing = None
        self.observing = None

    @property
    def isSet(self):
        """Has a value been recorded?

        Returns `True` if a value has been recorded, be that a failure or
        otherwise.
        """
        return self.waiters is None

    def set(self, value):
        """Set the promised value.

        Notifies all waiters of the value, or raises `AlreadyCalledError` if
        the value has been set previously.

        If a `Deferred` was being captured, it is cancelled, which is a no-op
        if it has already fired, and this object's reference to it is cleared.

        If a `Deferred` was being observed, it is *not* cancelled, and this
        object's reference to it is cleared.
        """
        if self.waiters is None:
            raise AlreadyCalledError(
                "Value already set to %r." % (self.value,))

        self.value = value
        waiters, self.waiters = self.waiters, None
        for waiter in waiters.copy():
            waiter.callback(value)
        capturing, self.capturing = self.capturing, None
        if capturing is not None:
            capturing.cancel()
        self.observing = None

    def fail(self, failure=None):
        """Set the promised value to a `Failure`.

        Notifies all waiters via `errback`, or raises `AlreadyCalledError` if
        the value has been set previously.

        :see: `DeferredValue.set`
        """
        if not isinstance(failure, Failure):
            failure = Failure(failure)

        self.set(failure)

    def capture(self, d):
        """Capture the result of `d`.

        The result (or failure) coming out of `d` will be saved in this
        `DeferredValue`, and the result passed down `d`'s chain will be
        `None`.

        :param d: :py:class:`Deferred`.
        :raise AlreadyCalledError: If another `Deferred` is already being
            captured or observed.
        """
        if self.waiters is None:
            raise AlreadyCalledError(
                "Value already set to %r." % (self.value,))
        if self.capturing is not None:
            raise AlreadyCalledError(
                "Already capturing %r." % (self.capturing,))
        if self.observing is not None:
            raise AlreadyCalledError(
                "Already observing %r." % (self.observing,))

        self.capturing = d
        return d.addCallbacks(self.set, self.fail)

    def observe(self, d):
        """Capture and pass-through the result of `d`.

        The result (or failure) coming out of `d` will be saved in this
        `DeferredValue`, but the result (or failure) will be propagated
        intact.

        :param d: :py:class:`Deferred`.
        :raise AlreadyCalledError: If another `Deferred` is already being
            captured or observed.
        """
        if self.waiters is None:
            raise AlreadyCalledError(
                "Value already set to %r." % (self.value,))
        if self.capturing is not None:
            raise AlreadyCalledError(
                "Already capturing %r." % (self.capturing,))
        if self.observing is not None:
            raise AlreadyCalledError(
                "Already observing %r." % (self.observing,))

        def set_and_return(value):
            self.set(value)
            return value

        self.observing = d
        return d.addBoth(set_and_return)

    def get(self, timeout=None):
        """Get a promise for the value.

        Returns a `Deferred` that will fire with the value when it's made
        available, or with `CancelledError` if this object is cancelled.

        If a time-out in seconds is specified, the `Deferred` will be
        cancelled if the value is not made available within the time.
        """
        if self.waiters is None:
            return succeed(self.value)

        if timeout is None:
            d = Deferred()
        else:
            d = deferWithTimeout(timeout)

        def remove(result, discard, d):
            discard(d)  # Remove d from the waiters list.
            return result  # Pass-through the result.

        d.addBoth(remove, self.waiters.discard, d)
        self.waiters.add(d)
        return d

    def cancel(self):
        """Cancel all waiters and prevent further use of this object.

        If a `Deferred` was being captured, it is cancelled, which is a no-op
        if it has already fired, and this object's reference to it is cleared.

        If a `Deferred` was being observed, it is *not* cancelled, and this
        object's reference to it is cleared.

        After cancelling, `AlreadyCalledError` will be raised if `set` is
        called, and any `Deferred`s returned from `get` will be already
        cancelled.
        """
        if self.waiters is None:
            return

        self.value = Failure(CancelledError())
        waiters, self.waiters = self.waiters, None
        for waiter in waiters.copy():
            waiter.cancel()
        capturing, self.capturing = self.capturing, None
        if capturing is not None:
            capturing.cancel()
        self.observing = None


class PageFetcher:
    """Fetches pages, coalescing concurrent requests.

    If a request comes in for, say, ``http://example.com/FOO`` then it is
    dispatched, and a `Deferred` is returned.

    If another request comes in for ``http://example.com/FOO`` before the
    first has finished then a `Deferred` is still returned, but no new request
    is dispatched. The second request piggy-backs onto the first.

    If a request comes in for ``http://example.com/BAR`` at a similar time
    then this is treated as a completely separate request. URLs are compared
    textually; coalescing does not occur under other circumstances.

    Once the first request for ``http://example.com/FOO`` is complete, all the
    interested parties are notified, but this object then forgets all about
    it. A subsequent request is treated as new.
    """

    def __init__(self, agent=None):
        super(PageFetcher, self).__init__()
        self.pending = {}
        if agent is None:
            self.agent = fullyQualifiedName(self.__class__)
        elif isinstance(agent, (bytes, unicode)):
            self.agent = agent  # This is fine.
        else:
            self.agent = fullyQualifiedName(agent)

    def get(self, url, timeout=90):
        """Issue an ``HTTP GET`` for the given URL."""
        if url in self.pending:
            dvalue = self.pending[url]
        else:
            fetch = getPage(url, agent=self.agent, timeout=timeout)
            fetch.addBoth(callOut, self.pending.pop, url, None)
            dvalue = self.pending[url] = DeferredValue()
            dvalue.capture(fetch)

        assert not dvalue.isSet, (
            "Reference to completed fetch result for %s found." % url)

        return dvalue.get()


def deferToNewThread(func, *args, **kwargs):
    """Defer `func` into a new thread.

    The thread is created for this one function call; it will not have been
    previously used, and will not be used again.

    :param func: A callable, typically a function.
    :param args: A tuple of positional arguments.
    :param kwargs: A dict of keyword arguments.

    :return: A :class:`Deferred` that fires with the result of `func`.
    """
    d = Deferred()
    ctx = context.theContextTracker.currentContext().contexts[-1]
    thread = threading.Thread(
        target=callInThread, args=(ctx, func, args, kwargs, d),
        name="deferToNewThread(%s)" % getattr(func, "__name__", "..."))
    thread.start()
    return d


def callInThread(ctx, func, args, kwargs, d):
    """Call `func` in a newly created thread.

    This function does not actually create the thread; this should be called
    as the target of a newly created thread. Generally you won't call this
    yourself, it will be called by `deferToNewThread`.

    :param ctx: A context as a dict; see :module:`twisted.python.context`.
    :param func: A callable, typically a function.
    :param args: A tuple of positional arguments.
    :param kwargs: A dict of keyword arguments.
    :param d: A :class:`Deferred` that will be called back with the result of
        the function call.

    """
    try:
        result = context.call(ctx, func, *args, **kwargs)
    except:
        # Failure() captures the exception information and trackback.
        reactor.callFromThread(context.call, ctx, d.errback, Failure())
    else:
        reactor.callFromThread(context.call, ctx, d.callback, result)


class ThreadUnpool:
    """A thread "pool" that doesn't pool.

    Creating a new thread is a quick and low-overhead operation. In MAAS the
    cost of creating a new thread is almost always dwarfed by the time and
    resources taken by the function called in that thread. Creating a new
    thread and letting it end also helps to ensure that thread-local resources
    are reaped.

    This class does allow limits on concurrency through the lock that can be
    passed into the constructor. Typically this is a ``DeferredSemaphore``.

    This is intended as an almost-drop-in-replacement for Twisted's
    thread-pool.
    """

    started = None

    def __init__(self, lock, context=None):
        super(ThreadUnpool, self).__init__()
        self.context = context
        self.lock = lock

    def start(self):
        """Start this thread-pool.

        This actually does almost nothing, but it does make this object more
        compatible with a regular Twisted thread-pool.
        """
        self.started = True

    def stop(self):
        """Stop this thread-pool.

        This actually does almost nothing, but it does make this object more
        compatible with a regular Twisted thread-pool.
        """
        self.started = False

    def callInThread(self, func, *args, **kwargs):

        """See :class:`twisted.python.threadpool.ThreadPool`.

        :return: a `Deferred`, which is mainly intended for testing.
            Twisted's `ThreadPool` does not return anything.
        """
        return self.callInThreadWithCallback(None, func, *args, **kwargs)

    def callInThreadWithCallback(self, onResult, func, *args, **kwargs):
        """See :class:`twisted.python.threadpool.ThreadPool`.

        One difference from Twisted's thread-pool is that `onResult` will be
        called in the reactor thread, not the thread in which `func` is
        called. This is an artefact of the implementation and not a
        fundamental limitation, so could be changed.

        :return: a `Deferred`, which is mainly intended for testing.
            Twisted's `ThreadPool` does not return anything.
        """
        ctxfunc = self.wrapFuncInContext(func)

        d = self.lock.acquire()

        def callInThreadWithLock(lock):
            dthread = deferToNewThread(ctxfunc, *args, **kwargs)
            return dthread.addBoth(callOut, lock.release)
        d.addCallback(callInThreadWithLock)

        if onResult is None:
            d.addErrback(log.err, "Failure when calling out to thread.")
        else:
            d.addCallbacks(partial(onResult, True), partial(onResult, False))
            d.addErrback(log.err, "Failure reporting result from thread.")

        return d

    def wrapFuncInContext(self, func):
        """Return a new function that will call `func` in context."""
        # If there's no context defined, return `func` unaltered.
        if self.context is None:
            return func

        # The context is prepared by calling it. Some context managers can be
        # reused, but many -- like those defined using `contextmanager` -- can
        # be used only once, so we expect `self.context` to actually be a
        # context factory.

        @wraps(func)
        def ctxfunc(*args, **kwargs):
            with self.context():
                return func(*args, **kwargs)

        # For convenience, when introspecting for example, expose the original
        # function on the function we're returning.
        ctxfunc.func = func

        return ctxfunc


class ThreadPool(threadpool.ThreadPool, object):
    """Thread-pool that wraps a context around each worker."""

    def __init__(self, minthreads=5, maxthreads=20, name=None, context=None):
        super(ThreadPool, self).__init__(minthreads, maxthreads, name)
        self.context = context

    def _worker(self):
        ct = self.currentThread()
        try:
            # Make the context active throughout the worker's lifetime.
            # XXX: What if self.context is None?
            with self.context():
                return super(ThreadPool, self)._worker()
        finally:
            # Belt-n-braces, in case the context blows up.
            if ct in self.threads:
                self.threads.remove(ct)


class ThreadPoolLimiter:
    """Limit the number of concurrent users of a given thread-pool.

    This wraps another thread-pool and gates access via the given lock, which
    should be a `DeferredLock` or `DeferredSemaphore`. This allows a larger
    thread-pool to be portioned out.
    """

    def __init__(self, pool, lock):
        super(ThreadPoolLimiter, self).__init__()
        self.pool = pool
        self.lock = lock

    start = property(attrgetter("pool.start"))
    started = property(attrgetter("pool.started"))
    stop = property(attrgetter("pool.stop"))

    def callInThread(self, func, *args, **kwargs):
        """Acquires the lock then calls the underlying pool."""
        return self.callInThreadWithCallback(None, func, *args, **kwargs)

    def callInThreadWithCallback(self, onResult, func, *args, **kwargs):
        """Acquires the lock then calls the underlying pool."""

        def signal(success, result, done=[False]):
            # Call onResult once and once only.
            if not done[0]:
                try:
                    onResult(success, result)
                finally:
                    done[0] = True

        def release(lock, done=[False]):
            # Release the lock once and once only.
            if not done[0]:
                try:
                    lock.release()
                finally:
                    done[0] = True

        if onResult is None:
            def callback(success, result, lock=self.lock):
                # Ignore the result; it was never wanted anyway.
                reactor.callFromThread(release, lock)
        else:
            def callback(success, result, lock=self.lock):
                # Make the callback before releasing the lock.
                try:
                    signal(success, result)
                finally:
                    reactor.callFromThread(release, lock)

        def locked(lock, pool=self.pool):
            try:
                # If this fails we have serious problems. On the other hand,
                # if this succeeds we have handed off all responsibility.
                pool.callInThreadWithCallback(callback, func, *args, **kwargs)
            except:
                try:
                    if onResult is None:
                        raise  # Don't suppress this; it's bad.
                    else:
                        signal(False, Failure())
                finally:
                    release(lock)

        return self.lock.acquire().addCallback(locked).addErrback(
            log.err, "Critical failure arranging call in thread")
