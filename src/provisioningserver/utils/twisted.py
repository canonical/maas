# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities related to the Twisted/Crochet execution environment."""

from collections import defaultdict
from collections.abc import Iterable
import contextlib
from functools import partial, wraps
from http import HTTPStatus
from itertools import chain, repeat, starmap
from operator import attrgetter
import os
from os import kill as _os_kill
from os import killpg as _os_killpg
import signal
import threading

from crochet import run_in_reactor
from netaddr import AddrFormatError, IPAddress
from twisted.internet.defer import (
    AlreadyCalledError,
    CancelledError,
    Deferred,
    maybeDeferred,
    succeed,
)
from twisted.internet.error import ProcessDone
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.threads import deferToThread
from twisted.internet.utils import _EverythingGetter
from twisted.logger import Logger
from twisted.python import context, threadable, threadpool
from twisted.python.failure import Failure
from twisted.python.threadable import isInIOThread
from twisted.web.iweb import IAccessLogFormatter
from twisted.web.server import Site
from zope import interface
from zope.interface import provider

from provisioningserver.logger import LegacyLogger

log = LegacyLogger()


undefined = object()
FOREVER = object()
LONGTIME = 60 * 60 * 24 * 7 * 4  # 4 weeks.


def deferred(func):
    """Decorates a function to ensure that it always returns a `Deferred`.

    This also serves a secondary documentation purpose; functions decorated
    with this are readily identifiable as asynchronous.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        return maybeDeferred(func, *args, **kwargs)

    return wrapper


def threadDeferred(func):
    """Wrap a sync function to be run asynchronously in a thread."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        return deferToThread(func, *args, **kwargs)

    return wrapper


class IAsynchronous(interface.Interface):
    """Denotes that a call to the provider will result in the execution of
    asynchronous or non-blocking code.

    Absence of this interface does not mean that a call will definitely not
    result in the execution of asynchronous/non-blocking code.
    """


def asynchronous(func=undefined, *, timeout=undefined):
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
        if isinstance(timeout, (int, float)):
            if timeout < 0:
                raise ValueError("timeout must be >= 0, not %d" % timeout)
        elif timeout is not FOREVER:
            raise ValueError(
                f"timeout must be an int, float, or undefined, not {timeout!r}"
            )

    func_in_reactor = run_in_reactor(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        if threadable.ioThread is None or isInIOThread():
            return func(*args, **kwargs)
        elif timeout is undefined:
            return func_in_reactor(*args, **kwargs)
        elif timeout is FOREVER:
            # There's a bug in crochet where waiting for an undefined amount
            # of time -- i.e. by calling .wait() or .wait(None) -- waits for
            # an invalidly long time (2^31 seconds) which causes NO wait; i.e.
            # TimeoutError is raised immediately. Instead we wait 4 weeks,
            # which seems long enough, even for MAAS.
            return func_in_reactor(*args, **kwargs).wait(LONGTIME)
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
    try:
        # A function or method; see PEP 3155.
        func_name = func.__qualname__
    except AttributeError:
        # An instance with a __call__ method.
        func_name = type(func).__qualname__

    @wraps(func)
    def wrapper(*args, **kwargs):
        # isInIOThread() can return True if the reactor has previously been
        # started but has now stopped, so don't test isInIOThread() until
        # we've also checked if the reactor is running.
        from twisted.internet import reactor

        if reactor.running and isInIOThread():
            raise AssertionError(
                "Function %s(...) must not be called in the "
                "reactor thread." % func.__name__
            )
        else:
            result = func(*args, **kwargs)
            if isinstance(result, Deferred):
                args_reprs = chain(
                    map(repr, args), starmap("{}={!r}".format, kwargs.items())
                )
                raise TypeError(
                    "Synchronous call returned a Deferred: %s(%s)"
                    % (func_name, ", ".join(args_reprs))
                )
            else:
                return result

    # This makes it possible to reliably determine programmatically if a
    # function has been decorated with @synchronous.
    interface.directlyProvides(wrapper, ISynchronous)

    return wrapper


def suppress(failure, *exceptions, instead=None):
    """Used as a errback, suppress the given exceptions.

    Returns the given `instead` value... instead.
    """
    if failure.check(*exceptions) is None:
        return failure
    else:
        return instead


def retries(timeout=30, intervals=1, clock=None):
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
    if clock is None:
        from twisted.internet import reactor as clock
    start = clock.seconds()
    end = start + timeout

    if isinstance(intervals, Iterable):
        intervals = iter(intervals)
    else:
        intervals = repeat(intervals)

    return gen_retries(start, end, intervals, clock)


def gen_retries(start, end, intervals, clock=None):
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
    if clock is None:
        from twisted.internet import reactor as clock
    for interval in intervals:
        now = clock.seconds()
        if now < end:
            wait = min(interval, end - now)
            yield now - start, end - now, wait
        else:
            yield now - start, end - now, 0
            break


def pause(duration, clock=None):
    """Pause execution for `duration` seconds.

    Returns a `Deferred` that will fire after `duration` seconds.
    """
    if clock is None:
        from twisted.internet import reactor as clock
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

    from twisted.internet import reactor

    timeoutCall = reactor.callLater(timeout, d.cancel)

    def done(result):
        if timeoutCall.active():
            timeoutCall.cancel()
        return result

    return d.addBoth(done)


def call(_, func, *args, **kwargs):
    """Call the given `func`, discarding the first argument.

    For example, where ``doSomethingElse`` needs to become part of the
    callback chain, is not interested in the result of the previous step, but
    which produces an interesting result itself::

      d = doSomethingImportant()
      d.addCallback(call, doSomethingElse)
      d.addCallback(doSomethingWithTheResult)

    Often this would be handled by allowing a disposable first argument in
    ``doSomethingElse``, or with an ugly ``lambda``::

      d = doSomethingImportant()
      d.addCallback(lambda ignore_this: doSomethingElse())
      d.addCallback(doSomethingWithTheResult)

    :return: :class:`Deferred`.
    """
    return maybeDeferred(func, *args, **kwargs)


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

    :return: :class:`Deferred`.
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

    :return: :class:`Deferred`.
    """
    return deferToThread(func, *args, **kwargs).addCallback(lambda _: thing)


@asynchronous(timeout=FOREVER)
def callInReactor(func, *args, **kwargs):
    """Call the given `func` in the reactor.

    The return value from `func` will be returned unaltered to callers in the
    reactor thread, i.e. the call will not be wrapped in `maybeDeferred`.

    The return value from `func` will be returned unaltered to callers outside
    of the reactor thread UNLESS it is a `Deferred` instance, in which case it
    will be waited for indefinitely. The result of that `Deferred` will be
    returned to the caller.
    """
    return func(*args, **kwargs)


@asynchronous(timeout=FOREVER)
def callInReactorWithTimeout(timeout, func, *args, **kwargs):
    """Call the given `func` in the reactor.

    To callers in the reactor thread, a `Deferred` will always be returned. It
    will be cancelled after `timeout` seconds unless it has already fired.

    The return value from `func` will be returned unaltered to callers outside
    of the reactor thread UNLESS it is a `Deferred` instance, in which case it
    will be waited for. It will be cancelled after `timeout` seconds unless it
    has already fired.

    See `deferWithTimeout` for details.
    """
    return deferWithTimeout(timeout, func, *args, **kwargs)


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
        super().__init__()
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
            raise AlreadyCalledError(f"Value already set to {self.value!r}.")

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
            raise AlreadyCalledError(f"Value already set to {self.value!r}.")
        if self.capturing is not None:
            raise AlreadyCalledError(f"Already capturing {self.capturing!r}.")
        if self.observing is not None:
            raise AlreadyCalledError(f"Already observing {self.observing!r}.")

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
            raise AlreadyCalledError(f"Value already set to {self.value!r}.")
        if self.capturing is not None:
            raise AlreadyCalledError(f"Already capturing {self.capturing!r}.")
        if self.observing is not None:
            raise AlreadyCalledError(f"Already observing {self.observing!r}.")

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


class RPCFetcher:
    """Coalesces concurrent RPC requests.

    If a RPC request is being made to `client` then its is dispatched,
    and a `Deferred` is returned.

    If another RPC request is being made to the same `client` with the same
    parameters before the first has finished then a `Deferred` is still
    returned, but no new request is dispated. The second request piggy-backs
    onto the first.

    If a RPC request is being made to the same `client` but with different
    parameters then this is treated as a completely separate request.

    Once the first RPC request to `client` is complete, all the
    interested parties are notified, but this object then forgets all about
    it. A subsequent request is treated as new.
    """

    def __init__(self):
        super().__init__()
        self.pending = defaultdict(dict)

    def __call__(self, client, *args, **kwargs):
        """Call the command on the client."""
        command = (tuple(args), tuple(sorted(kwargs.items())))
        calls = self.pending[client]
        if command in calls:
            dvalue = calls[command]
        else:
            dvalue = calls[command] = DeferredValue()
            response = client(*args, **kwargs)
            response.addBoth(callOut, self._cleanup, client, command)
            dvalue.capture(response)

        return dvalue.get()

    def _cleanup(self, client, command):
        """Remove the command and/or client from `pending`."""
        self.pending[client].pop(command)
        if len(self.pending[client]) == 0:
            # Prevent leaking of clients that no longer are making any calls.
            del self.pending[client]


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
        target=callInThread,
        args=(ctx, func, args, kwargs, d),
        name="deferToNewThread(%s)" % getattr(func, "__name__", "..."),
    )
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
    from twisted.internet import reactor

    try:
        result = context.call(ctx, func, *args, **kwargs)
    except Exception:
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

    def __init__(self, lock, contextFactory=None):
        super().__init__()
        self.contextFactory = contextFactory
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
        if self.contextFactory is None:
            return func

        @wraps(func)
        def ctxfunc(*args, **kwargs):
            with self.contextFactory():
                return func(*args, **kwargs)

        # For convenience, when introspecting for example, expose the original
        # function on the function we're returning.
        ctxfunc.func = func

        return ctxfunc


class ThreadPool(threadpool.ThreadPool):
    """Thread-pool that wraps a context around each worker."""

    log = Logger()

    def __init__(
        self, minthreads=5, maxthreads=20, name=None, contextFactory=None
    ):
        super().__init__(minthreads, maxthreads, name)
        self.context = ThreadWorkerContext(
            NullContext if contextFactory is None else contextFactory
        )

    def threadFactory(self, target, name):
        """Spawn a thread for use as a worker.

        :param target: A no-argument callable; the worker function.
        :param name: The name of the thread.
        """

        def worker(log, context, target):
            ct = threading.current_thread()
            try:
                try:
                    return target()
                finally:
                    try:
                        # The worker context is entered by the first task that
                        # this worker runs (or a subsequent task if it fails);
                        # callInThreadWithCallback > callInContext is where
                        # that happens. This thread is not going to execute
                        # any more tasks so we exit the context.
                        context.exit()
                    except Exception:
                        # There is no application code for this exception to
                        # bubble up to, so just log it and move on.
                        log.failure("Failure exiting worker context.")
            finally:
                # Belt-n-braces, in case the context blows up. This works
                # around https://twistedmatrix.com/trac/ticket/8114 too.
                if ct in self.threads:
                    self.threads.remove(ct)

        return super().threadFactory(
            name=name, target=worker, args=(self.log, self.context, target)
        )

    def callInThreadWithCallback(self, onResult, func, *args, **kwargs):
        """See :class:`twisted.python.threadpool.ThreadPool`.

        In addition, this will attempt to enter the context passed to this
        pool's constructor before calling `func`. This is so that any
        exceptions arising from entering the context will be passed back into
        application code, rather than being logged (and ignored) and breaking
        the pool (which assumes that creating a thread will always succeed).
        """

        def callInContext(context, func, *args, **kwargs):
            context.enter()  # Delayed until now.
            return func(*args, **kwargs)

        return super().callInThreadWithCallback(
            onResult, callInContext, self.context, func, *args, **kwargs
        )


class ThreadWorkerContext(threading.local):
    """Helper to manage context in workers.

    This is used by `ThreadPool` to enter and exit its configured context in
    each worker. The context cannot be entered during worker start-up because
    the super-class assumes that thread creation cannot fail. Instead, the
    context, if not already entered, is entered before executing each task.

    In this way, failures arising from entering the worker context are passed
    up to application code where they can be handled, and transient failures
    can be recovered from when the next task is executed.
    """

    def __init__(self, contextFactory):
        super().__init__()
        self.contextFactory = contextFactory
        self.context = None

    def enter(self):
        """Enter the context if we've not already done so."""
        if self.context is None:
            context = self.contextFactory()
            context.__enter__()
            self.context = context

    def exit(self):
        """Exit the context if we've successfully entered it."""
        if self.context is not None:
            context, self.context = self.context, None
            context.__exit__(None, None, None)


class NullContext:
    """A context manager that does nothing."""

    def __enter__(self):
        """Do nothing."""

    def __exit__(self, *exc_info):
        """Do nothing."""


class ThreadPoolLimiter:
    """Limit the number of concurrent users of a given thread-pool.

    This wraps another thread-pool and gates access via the given lock, which
    should be a `DeferredLock` or `DeferredSemaphore`. This allows a larger
    thread-pool to be portioned out.
    """

    def __init__(self, pool, lock, clock=None):
        super().__init__()
        self.pool = pool
        self.lock = lock
        self.clock = clock
        if self.clock is None:
            from twisted.internet import reactor

            self.clock = reactor

    start = property(attrgetter("pool.start"))
    started = property(attrgetter("pool.started"))
    stop = property(attrgetter("pool.stop"))

    def callInThread(self, func, *args, **kwargs):
        """Acquires the lock then calls the underlying pool."""
        return self.callInThreadWithCallback(None, func, *args, **kwargs)

    def callInThreadWithCallback(self, onResult, func, *args, **kwargs):
        """Acquires the lock then calls the underlying pool."""

        def signal(success, result, done=[False]):  # noqa: B006
            # Call onResult once and once only.
            if not done[0]:
                try:
                    onResult(success, result)
                finally:
                    done[0] = True

        def release(lock, done=[False]):  # noqa: B006
            # Release the lock once and once only.
            if not done[0]:
                try:
                    lock.release()
                finally:
                    done[0] = True

        if onResult is None:

            def callback(success, result, lock=self.lock):
                # Ignore the result; it was never wanted anyway.
                self.clock.callFromThread(release, lock)

        else:

            def callback(success, result, lock=self.lock):
                # Make the callback before releasing the lock.
                try:
                    signal(success, result)
                finally:
                    self.clock.callFromThread(release, lock)

        def locked(lock, pool=self.pool):
            try:
                # The threadpool has a queue of "waiters" and "working" threads.
                # - The "waiters" are threads that are available to pick up tasks
                # - The "working" are threads that are currently handling tasks.
                #
                # This is one of the places where a thread is picked from the waiters queue to execute a task.
                # Since this class is mainly used to control the threads for the websocket and the django application,
                # this is exactly where we pick a thread to handle the requests.
                #
                # IMPORTANT: only when the callback has returned the thread is put back into the waiters queue. If you have
                # post_commits in your func and you are using deferToDatabase, then you are under the risk of a deadlock!
                #
                # If this fails we have serious problems. On the other hand,
                # if this succeeds we have handed off all responsibility.
                pool.callInThreadWithCallback(callback, func, *args, **kwargs)
            except Exception:
                try:
                    if onResult is None:
                        raise  # Don't suppress this; it's bad.
                    else:
                        signal(False, Failure())
                finally:
                    release(lock)

        return (
            self.lock.acquire()
            .addCallback(locked)
            .addErrback(log.err, "Critical failure arranging call in thread")
        )


def makeDeferredWithProcessProtocol():
    """Returns a (`Deferred`, `ProcessProtocol`) tuple.

    The Deferred's `callback()` will be called (with None) if the
    `ProcessProtocol` is called back indicating that no error occurred.
    Its `errback()` will be called with the `Failure` reason otherwise.
    """
    done = Deferred()
    protocol = ProcessProtocol()
    # Call the errback if the "failure" object indicates a non-zero exit.
    protocol.processEnded = lambda reason: (
        done.errback(reason)
        if (reason and not reason.check(ProcessDone))
        else done.callback(None)
    )
    return done, protocol


def terminateProcess(
    pid, done, *, term_after=0.0, quit_after=5.0, kill_after=10.0, reactor=None
):
    """Terminate the given process.

    A "sensible" way to terminate a process. Does the following:

      1. Sends SIGTERM to the process identified by `pid`.
      2. Waits for up to 5 seconds.
      3. Sends SIGQUIT to the process *group* of process `pid`.
      4. Waits for up to an additional 5 seconds.
      5. Sends SIGKILL to the process *group* of process `pid`.

    Steps #3 and #5 have a safeguard: if the process identified by `pid` has
    the same process group as the invoking process the signal is sent only to
    the process and not to the process group. This prevents the caller from
    inadvertently killing itself. For best effect, ensure that new processes
    become process group leaders soon after spawning.

    :param pid: The PID to terminate.
    :param done: A `Deferred` that fires when the process exits.
    """
    ppgid = os.getpgrp()

    if reactor is None:
        from twisted.internet import reactor

    def kill(sig):
        """Attempt to send `signal` to the given `pid`."""
        try:
            _os_kill(pid, sig)
        except ProcessLookupError:
            pass  # Already exited.

    def killpg(sig):
        """Attempt to send `signal` to the progress group of `pid`.

        If `pid` is running in the same process group as the invoking process,
        this falls back to using kill(2) instead of killpg(2).
        """
        try:
            pgid = os.getpgid(pid)
            if pgid == ppgid:
                _os_kill(pid, sig)
            else:
                _os_killpg(pgid, sig)
        except ProcessLookupError:
            pass  # Already exited.

    killers = (
        reactor.callLater(term_after, kill, signal.SIGTERM),
        reactor.callLater(quit_after, killpg, signal.SIGQUIT),
        reactor.callLater(kill_after, killpg, signal.SIGKILL),
    )

    def ended():
        for killer in killers:
            if killer.active():
                killer.cancel()

    done.addBoth(callOut, ended)


@provider(IAccessLogFormatter)
def reducedWebLogFormatter(timestamp, request):
    """Return a reduced formatted log line for the given request.

    The `timestamp` argument is ignored. The line returned is expected to be
    sent out by a logger which will add its own timestamp, so this one is
    superfluous.

    :see: `IAccessLogFormatter`
    :see: `combinedLogFormatter`
    """
    template = (
        "{origin} {method} {uri} {proto} --> {status} "
        "(referrer: {referrer}; agent: {agent})"
    )

    def field(value, default):
        if value is None or len(value) == 0 or value.isspace():
            return default
        elif isinstance(value, bytes):
            return value.decode("ascii", "replace")
        else:
            return value

    def normaliseAddress(address):
        """Normalise an IP address."""
        try:
            address = IPAddress(address)
        except AddrFormatError:
            return address  # Hostname?
        else:
            if address.is_ipv4_mapped():
                return address.ipv4()
            else:
                return address

    def describeHttpStatus(code):
        try:
            code = HTTPStatus(code)
        except ValueError:
            if isinstance(code, int):
                return str(code)
            else:
                return "???"
        else:
            return "{code.value:d} {code.name}".format(code=code)

    origin = field(getattr(request.getClientAddress(), "host", None), None)
    origin = "-" if origin is None else normaliseAddress(origin)

    return template.format(
        referrer=field(request.getHeader(b"referer"), "-"),
        agent=field(request.getHeader(b"user-agent"), "-"),
        status=describeHttpStatus(request.code),
        origin=origin,
        method=field(request.method, "???"),
        uri=field(request.uri, "-"),
        proto=field(request.clientproto, "-"),
    )


class SiteNoLog(Site):
    """A `Site` that does not log its request."""

    def log(self, request):
        # Do nothing.
        pass


def getProcessOutputAndValue(
    executable,
    args=(),
    env={},  # noqa: B006
    path=None,
    reactor=None,
):
    """Utility to create a process in the reactor and get all the output and
    return code of that process.

    This is very similar to the
    `twisted.internet.utils.getProcessOutputAndValue` except this ensures that
    the process is reaped at the end. Without this defunct processes will hang
    around until this process dies.
    """
    if reactor is None:
        from twisted.internet import reactor

    d = Deferred()
    proc = reactor.spawnProcess(
        _EverythingGetter(d),
        executable,
        (executable,) + tuple(args),
        env,
        None,
    )

    def cleanup(result):
        if proc.pid is not None:
            with contextlib.suppress(Exception):
                # Allow the error to occur, in the case the process has already
                # been reaped.
                proc.reapProcess()
        return result

    d.addBoth(cleanup)
    return d
