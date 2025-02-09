# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""ORM-related utilities."""

__all__ = [
    "disable_all_database_connections",
    "enable_all_database_connections",
    "ExclusivelyConnected",
    "FullyConnected",
    "gen_retry_intervals",
    "get_exception_class",
    "get_first",
    "get_one",
    "in_transaction",
    "is_deadlock_failure",
    "is_retryable_failure",
    "is_serialization_failure",
    "is_unique_violation",
    "make_deadlock_failure",
    "make_serialization_failure",
    "make_unique_violation",
    "post_commit",
    "post_commit_do",
    "psql_array",
    "request_transaction_retry",
    "retry_context",
    "retry_on_retryable_failure",
    "savepoint",
    "TotallyDisconnected",
    "transactional",
    "validate_in_transaction",
    "with_connection",
]

from collections import defaultdict, deque
from collections.abc import Iterable
from contextlib import contextmanager, ExitStack
from functools import wraps
from itertools import chain, islice, repeat, takewhile
import re
import threading
from time import sleep
import types
from typing import Container

from django.conf import settings
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.db import connection, connections, reset_queries, transaction
from django.db.models import F, Func, IntegerField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.db.transaction import TransactionManagementError
from django.db.utils import DatabaseError, IntegrityError, OperationalError
from django.http import Http404
import psycopg2
from psycopg2.errorcodes import (
    DEADLOCK_DETECTED,
    FOREIGN_KEY_VIOLATION,
    SERIALIZATION_FAILURE,
    UNIQUE_VIOLATION,
)
from twisted.internet.defer import Deferred

from maasserver.exceptions import MAASAPIBadRequest, MAASAPIForbidden
from maasserver.utils.asynchronous import DeferredHooks
from provisioningserver.utils import flatten
from provisioningserver.utils.backoff import exponential_growth, full_jitter
from provisioningserver.utils.network import parse_integer
from provisioningserver.utils.twisted import callOut


def postgresql_major_version(conn=None) -> int:
    """Return PostgreSQL major version as an integer.

    https://www.postgresql.org/docs/current/libpq-status.html#LIBPQ-PQSERVERVERSION

    The server version is formed by multiplying the server's major version
    number by 10000 and adding the minor version number.

    """
    if conn is None:
        conn = connection.cursor().connection
    version = conn.server_version
    return version // 10000


def ArrayLength(field):
    """Expression to return the length of a PostgreSQL array."""
    return Coalesce(
        Func(
            F(field),
            Value(1),
            function="array_length",
            output_field=IntegerField(),
        ),
        Value(0),
    )


def NotNullSum(column):
    """Expression like Sum, but returns 0 if the aggregate is None."""
    return Coalesce(Sum(column), Value(0))


def get_exception_class(items):
    """Return exception class to raise.

    If `items` looks like a Django ORM result set, returns the
    `MultipleObjectsReturned` class as defined in that model.  Otherwise,
    returns the generic class.
    """
    model = getattr(items, "model", None)
    return getattr(model, "MultipleObjectsReturned", MultipleObjectsReturned)


def get_one(items, exception_class=None):
    """Assume there's at most one item in `items`, and return it (or None).

    If `items` contains more than one item, raise an error.  If `items` looks
    like a Django ORM result set, the error will be of the same model-specific
    Django `MultipleObjectsReturned` type that `items.get()` would raise.
    Otherwise, a plain Django :class:`MultipleObjectsReturned` error.

    :param items: Any sequence.
    :param exception_class: The exception class to raise if there is an error.
        If not specified, will use MultipleObjectsReturned (from the
        appropriate model class, if it can be determined).
    :return: The one item in that sequence, or None if it was empty.
    """
    # The only numbers we care about are zero, one, and "many."  Fetch
    # just enough items to distinguish between these.  Use islice so as
    # to support both sequences and iterators.
    retrieved_items = tuple(islice(items, 0, 2))
    length = len(retrieved_items)
    if length == 0:
        return None
    elif length == 1:
        return retrieved_items[0]
    else:
        if exception_class is None:
            exception_class = get_exception_class(items)
        object_name = get_model_object_name(items)
        if object_name is None:
            object_name = "item"
        raise exception_class("Got more than one %s." % object_name.lower())


def get_first(items):
    """Get the first of `items`, or None."""
    first_item = tuple(islice(items, 0, 1))
    if len(first_item) == 0:
        return None
    else:
        return first_item[0]


def psql_array(items, sql_type=None):
    """Return PostgreSQL array string and parameters."""
    sql = "ARRAY[" + ",".join(["%s"] * len(items)) + "]"
    if sql_type is not None:
        sql += "::%s[]" % sql_type
    return sql, items


def get_psycopg2_exception(exception):
    """Find the root PostgreSQL error from an database exception.

    We may be dealing with a raw exception or with a wrapper provided by
    Django, put there by ``DatabaseErrorWrapper``. As a belt-n-braces measure
    this searches for instances of `psycopg2.Error`, then, if not found, in
    the exception's cause (``__cause__``), recursively.

    :return: The underlying `psycopg2.Error`, or `None` if there isn't one.
    """
    if exception is None:
        return None
    elif isinstance(exception, psycopg2.Error):
        return exception
    else:
        return get_psycopg2_exception(exception.__cause__)


def get_psycopg2_serialization_exception(exception):
    """Return the root-cause if `exception` is a serialization failure.

    PostgreSQL sets a specific error code, "40001", when a transaction breaks
    because of a serialization failure.

    :return: The underlying `psycopg2.Error` if it's a serialization failure,
    or `None` if there isn't one.

    :see: http://www.postgresql.org/docs/9.3/static/transaction-iso.html
    """
    exception = get_psycopg2_exception(exception)
    if exception is None:
        return None
    elif exception.pgcode == SERIALIZATION_FAILURE:
        return exception
    else:
        return None


def is_serialization_failure(exception):
    """Does `exception` represent a serialization failure?

    PostgreSQL sets a specific error code, "40001", when a transaction breaks
    because of a serialization failure. This is normally about the right time
    to try again.

    :see: http://www.postgresql.org/docs/9.3/static/transaction-iso.html
    """
    return get_psycopg2_serialization_exception(exception) is not None


class SerializationFailure(psycopg2.OperationalError):
    """Explicit serialization failure.

    A real serialization failure, arising out of psycopg2 (and thus signalled
    from the database) would *NOT* be an instance of this class. However, it
    is not obvious how to create a `psycopg2.OperationalError` with ``pgcode``
    set to `SERIALIZATION_FAILURE` without subclassing. I suspect only the C
    interface can do that.
    """

    pgcode = SERIALIZATION_FAILURE


def make_serialization_failure():
    """Make a serialization exception.

    Artificially construct an exception that resembles what Django's ORM would
    raise when PostgreSQL fails a transaction because of a serialization
    failure.

    :returns: an instance of :py:class:`OperationalError` that will pass the
        `is_serialization_failure` predicate.
    """
    exception = OperationalError()
    exception.__cause__ = SerializationFailure()
    assert is_serialization_failure(exception)
    return exception


class DeadlockFailure(psycopg2.OperationalError):
    """Explicit deadlock failure.

    A real deadlock failure, arising out of psycopg2 (and thus signalled
    from the database) would *NOT* be an instance of this class. However, it
    is not obvious how to create a `psycopg2.OperationalError` with ``pgcode``
    set to `DEADLOCK_DETECTED` without subclassing. I suspect only the C
    interface can do that.
    """

    pgcode = DEADLOCK_DETECTED


def make_deadlock_failure():
    """Make a deadlock exception.

    Artificially construct an exception that resembles what Django's ORM would
    raise when PostgreSQL fails a transaction because of a deadlock
    failure.

    :returns: an instance of :py:class:`OperationalError` that will pass the
        `is_deadlock_failure` predicate.
    """
    exception = OperationalError()
    exception.__cause__ = DeadlockFailure()
    assert is_deadlock_failure(exception)
    return exception


def get_psycopg2_deadlock_exception(exception):
    """Return the root-cause if `exception` is a deadlock failure.

    PostgreSQL sets a specific error code, "40P01", when a transaction breaks
    because of a deadlock failure.

    :return: The underlying `psycopg2.Error` if it's a deadlock failure,
    or `None` if there isn't one.
    """
    exception = get_psycopg2_exception(exception)
    if exception is None:
        return None
    elif exception.pgcode == DEADLOCK_DETECTED:
        return exception
    else:
        return None


def is_deadlock_failure(exception):
    """Does `exception` represent a deadlock failure?

    PostgreSQL sets a specific error code, "40P01", when a transaction breaks
    because of a deadlock failure. This is normally about the right time
    to try again.
    """
    return get_psycopg2_deadlock_exception(exception) is not None


def get_psycopg2_unique_violation_exception(exception):
    """Return the root-cause if `exception` is a unique violation.

    PostgreSQL sets a specific error code, "23505", when a transaction breaks
    because of a unique violation.

    :return: The underlying `psycopg2.Error` if it's a unique violation, or
    `None` if there isn't one.
    """
    exception = get_psycopg2_exception(exception)
    if exception is None:
        return None
    elif exception.pgcode == UNIQUE_VIOLATION:
        return exception
    else:
        return None


def is_unique_violation(exception):
    """Does `exception` represent a unique violation?

    PostgreSQL sets a specific error code, "23505", when a transaction breaks
    because of a unique violation.
    """
    return get_psycopg2_unique_violation_exception(exception) is not None


class UniqueViolation(psycopg2.IntegrityError):
    """Explicit serialization failure.

    A real unique violation, arising out of psycopg2 (and thus signalled from
    the database) would *NOT* be an instance of this class. However, it is not
    obvious how to create a `psycopg2.IntegrityError` with ``pgcode`` set to
    `UNIQUE_VIOLATION` without subclassing. I suspect only the C interface can
    do that.
    """

    pgcode = UNIQUE_VIOLATION


def make_unique_violation():
    """Make a serialization exception.

    Artificially construct an exception that resembles what Django's ORM would
    raise when PostgreSQL fails a transaction because of a unique violation.

    :returns: an instance of :py:class:`IntegrityError` that will pass the
        `is_unique_violation` predicate.
    """
    exception = IntegrityError()
    exception.__cause__ = UniqueViolation()
    assert is_unique_violation(exception)
    return exception


def get_psycopg2_foreign_key_violation_exception(exception):
    """Return the root-cause if `exception` is a foreign key violation.

    PostgreSQL sets a specific error code, "23503", when a transaction breaks
    because of a foreign violation.

    :return: The underlying `psycopg2.Error` if it's a foreign key violation,
    or `None` if there isn't one.
    """
    exception = get_psycopg2_exception(exception)
    if exception is None:
        return None
    elif exception.pgcode == FOREIGN_KEY_VIOLATION:
        return exception
    else:
        return None


def is_foreign_key_violation(exception):
    """Does `exception` represent a foreign key violation?

    PostgreSQL sets a specific error code, "23503", when a transaction breaks
    because of a foreign key violation.
    """
    return get_psycopg2_foreign_key_violation_exception(exception) is not None


class ForeignKeyViolation(psycopg2.IntegrityError):
    """Explicit serialization failure.

    A real foreign key violation, arising out of psycopg2 (and thus signalled
    from the database) would *NOT* be an instance of this class. However, it is
    not obvious how to create a `psycopg2.IntegrityError` with ``pgcode`` set
    to `FOREIGN_KEY_VIOLATION` without subclassing. I suspect only the C
    interface can do that.
    """

    pgcode = FOREIGN_KEY_VIOLATION


def make_foreign_key_violation():
    """Make a serialization exception.

    Artificially construct an exception that resembles what Django's ORM would
    raise when PostgreSQL fails a transaction because of a foreign key
    violation.

    :returns: an instance of :py:class:`IntegrityError` that will pass the
        `is_foreign_key_violation` predicate.
    """
    exception = IntegrityError()
    exception.__cause__ = ForeignKeyViolation()
    assert is_foreign_key_violation(exception)
    return exception


class RetryStack(ExitStack):
    """An exit stack specialised to the retry machinery."""

    def __init__(self):
        super().__init__()
        self._cm_pending = deque()
        self._cm_seen = set()

    def add_pending_contexts(self, contexts):
        """Add contexts that should be entered before the next retry."""
        self._cm_pending.extend(contexts)

    def enter_pending_contexts(self):
        """Enter all pending contexts and clear the pending queue.

        Exceptions are propagated. It's the caller's responsibility to exit
        this stack so that previous contexts are exited.

        Although this stack will be in a deterministic state after a crash —
        all previous contexts will remain active, the crashing context will be
        discarded, and other pending contexts will remain pending — the most
        sensible thing to do is probably to exit this stack in full before
        trying again.
        """
        while len(self._cm_pending) != 0:
            context = self._cm_pending.popleft()
            if context not in self._cm_seen:
                self.enter_context(context)
                self._cm_seen.add(context)


class RetryContext(threading.local):
    """A thread-local context managed by the retry machinery.

    At present it manages only an exit stack (see `contextlib.ExitStack` and
    `RetryStack`) but is a convenient place to put context that's relevant to
    a whole sequence of attempts.
    """

    def __init__(self):
        super().__init__()
        self.stack = None

    @property
    def active(self) -> bool:
        """Has this retry context been entered and not yet exited?"""
        return self.stack is not None

    def __enter__(self):
        assert not self.active, "Retry context already active."
        self.stack = RetryStack().__enter__()

    def __exit__(self, *exc_info):
        assert self.active, "Retry context not active."
        _stack, self.stack = self.stack, None
        return _stack.__exit__(*exc_info)

    def prepare(self):
        """Prepare for the first or subsequent retry."""
        self.stack.enter_pending_contexts()


# The global retry context.
retry_context = RetryContext()


class RetryTransaction(BaseException):
    """An explicit request that the transaction be retried."""


class TooManyRetries(Exception):
    """A transaction retry has been requested too many times."""


def request_transaction_retry(*extra_contexts):
    """Raise a serialization exception.

    This depends on the retry machinery being higher up in the stack, catching
    this, and then retrying the transaction, though it may choose to re-raise
    the error if too many retries have already been attempted.

    :param extra_contexts: Contexts to enter before the next retry. The caller
        may be on its last retry so there's no guarantee that these contexts
        will be used. A failure when entering any of these contexts will
        immediately terminate the retry machinery: there will be no further
        retries. A context entered will remain active on all subsequent
        retries until the retry machinery is complete.

    :raise RetryTransaction:
    """
    assert retry_context.active, "Retry context not active."
    retry_context.stack.add_pending_contexts(extra_contexts)
    raise RetryTransaction()


def is_retryable_failure(exception):
    """Does `exception` represent a retryable failure?

    This does NOT include requested retries, i.e. `RetryTransaction`.

    :param exception: An instance of :class:`DatabaseError` or one of its
        subclasses.
    """
    return (
        is_serialization_failure(exception)
        or is_deadlock_failure(exception)
        or is_unique_violation(exception)
        or is_foreign_key_violation(exception)
    )


def gen_retry_intervals(base=0.01, rate=2.5, maximum=10.0):
    """Generate retry intervals based on an exponential series.

    Once any interval exceeds `maximum` the interval generated will forever be
    `maximum`; this effectively disconnects from the exponential series. All
    intervals will be subject to "jitter" as a final step.

    The defaults seem like reasonable coefficients for a capped, full-jitter,
    exponential back-off series, and were derived by experimentation at the
    command-line. Real-world experience may teach us better values.
    """
    # An exponentially growing series...
    intervals = exponential_growth(base, rate)
    # from which we stop pulling one we've hit a maximum...
    intervals = takewhile((lambda i: i < maximum), intervals)
    # and thereafter return the maximum value indefinitely...
    intervals = chain(intervals, repeat(maximum))
    # and to which we add some randomness.
    return full_jitter(intervals)


def noop():
    """Do nothing."""


def retry_on_retryable_failure(func, reset=noop):
    """Retry the wrapped function when it raises a retryable failure.

    It will call `func` a maximum of ten times, and will only retry if a
    retryable failure is detected.

    BE CAREFUL WHERE YOU USE THIS.

    In general it only makes sense to use this to wrap the *outermost*
    transactional block, e.g. outside of an `atomic` decorator. This is
    because we want a new transaction to be started on the way in, and rolled
    back on the way out before this function attempts to retry.

    :param reset: An optional callable that will be called between attempts.
        It is *not* called before the first attempt. If the last attempt fails
        with a retryable failure it will *not* be called. If an attempt
        fails with a non-retryable failure, it will *not* be called.

    """

    @wraps(func)
    def retrier(*args, **kwargs):
        with retry_context:
            intervals = gen_retry_intervals()
            for _ in range(9):
                retry_context.prepare()
                try:
                    return func(*args, **kwargs)
                except RetryTransaction:
                    reset()  # Which may do nothing.
                    sleep(next(intervals))
                except DatabaseError as error:
                    if is_retryable_failure(error):
                        reset()  # Which may do nothing.
                        sleep(next(intervals))
                    else:
                        raise
            else:
                retry_context.prepare()
                try:
                    return func(*args, **kwargs)
                except RetryTransaction:
                    raise TooManyRetries(  # noqa: B904
                        "This transaction has already been attempted "
                        "multiple times; giving up."
                    )

    return retrier


def gen_description_of_hooks(hooks):
    """Generate lines describing the given hooks.

    :param hooks: An iterable of :class:`Deferred` instances.
    """
    for index, hook in enumerate(hooks):
        yield "== Hook %d: %r ==" % (index + 1, hook)
        for cb, eb in hook.callbacks:
            yield f" +- callback: {cb[0]!r}"
            yield f" |      args: {cb[1]!r}"
            yield f" |    kwargs: {cb[2]!r}"
            yield f" |   errback: {eb[0]!r}"
            yield f" |      args: {eb[1]!r}"
            yield f" +--- kwargs: {eb[2]!r}"


class PostCommitHooks(DeferredHooks):
    """A specialised set of `DeferredHooks` for post-commit tasks.

    Can be used as a context manager, to check for orphaned post-commit hooks
    on the way in, and to run newly added hooks on the way out.
    """

    def __enter__(self):
        if len(self.hooks) > 0:
            # Capture a textual description of the hooks to help us understand
            # why this is about to blow oodles of egg custard in our faces.
            description = "\n".join(gen_description_of_hooks(self.hooks))
            # Crash when there are orphaned post-commit hooks. These might
            # only turn up in testing, where transactions are managed by the
            # test framework instead of this decorator. We need to fail hard
            # -- not just warn about it -- to ensure it gets fixed.
            self.reset()
            raise TransactionManagementError(
                "Orphaned post-commit hooks found:\n" + description
            )

    def __exit__(self, exc_type, exc_value, exc_tb):
        if exc_value is None:
            self.fire()
        else:
            self.reset()


post_commit_hooks = PostCommitHooks()


def post_commit(hook=None):
    """Add a post-commit hook, specific to this thread.

    :param hook: Optional, but if provided it must be either a `Deferred`
        instance or a callable. In the former case, see `DeferredHooks` for
        behaviour. In the latter case, the callable will be passed exactly one
        argument when fired, a `Failure`, or `None`. If the `hook` argument is
        not provided (or is None), a new `Deferred` will be created.
    :return: The `Deferred` that has been registered as a hook.
    """
    if hook is None:
        hook = Deferred()
    elif isinstance(hook, Deferred):
        pass  # This is fine as it is.
    elif callable(hook):
        hook = Deferred().addBoth(hook)
    else:
        raise AssertionError(f"Not a Deferred or callable: {hook!r}")

    post_commit_hooks.add(hook)
    return hook


def post_commit_do(func, *args, **kwargs):
    """Call a function after a successful commit.

    This will arrange for the given `func` to be called with the given
    arguments after a successful commit. If there's an error committing the
    transaction, `func` will *not* be called. If there's an error in an
    earlier post-commit task, `func` will *not* be called.

    If `func` returns a `Deferred` it will be waited for.

    :return: The `Deferred` that has been registered as a hook.
    """
    if callable(func):
        return post_commit().addCallback(callOut, func, *args, **kwargs)
    else:
        raise AssertionError(f"Not callable: {func!r}")


@contextmanager
def connected():
    """Context manager that ensures we're connected to the database.

    If there is not yet a connection to the database, this will connect on
    entry and disconnect on exit. Preexisting connections will be left alone.

    If the preexisting connection is not usable it is closed and a new
    connection is made.
    """
    if connection.connection is None:
        connection.close_if_unusable_or_obsolete()
        connection.ensure_connection()
        try:
            yield
        finally:
            connection.close()
    elif connection.is_usable():
        yield
    else:
        # Connection is not usable, so we disconnect and reconnect. Since
        # the connection was previously connected we do not disconnect this
        # new connection.
        connection.close_if_unusable_or_obsolete()
        connection.ensure_connection()
        yield


def with_connection(func):
    """Ensure that we're connected to the database before calling `func`.

    If there is not yet a connection to the database, this will connect before
    calling the decorated function, and then it will disconnect when done.
    Preexisting connections will be left alone.

    This can be important when using non-transactional advisory locks.
    """

    @wraps(func)
    def call_with_connection(*args, **kwargs):
        with connected():
            return func(*args, **kwargs)

    # For convenience, when introspecting for example, expose the original
    # function on the function we're returning.
    call_with_connection.func = func

    return call_with_connection


def transactional(func):
    """Decorator that wraps calls to `func` in a Django-managed transaction.

    It ensures that connections are closed if necessary. This keeps Django
    happy, especially in the test suite.

    In addition, if `func` is being invoked from outside of a transaction,
    this will retry if it fails with a retryable failure.
    """
    func_within_txn = transaction.atomic(func)  # For savepoints.
    func_outside_txn = retry_on_retryable_failure(
        func_within_txn, reset=post_commit_hooks.reset
    )

    @wraps(func)
    def call_within_transaction(*args, **kwargs):
        if connection.in_atomic_block:
            # Don't use the retry-capable function if we're already in a
            # transaction; retrying is pointless when the txn is broken.
            with post_commit_hooks.savepoint():
                return func_within_txn(*args, **kwargs)
        else:
            # Use the retry-capable function, firing post-transaction hooks.
            #
            # If there is not yet a connection to the database, connect before
            # calling the decorated function, then disconnect when done. This
            # can be important when using non-transactional advisory locks
            # that may be held before, during, and/or after this transactional
            # block.
            #
            # Previously, close_old_connections() was used here, which would
            # close connections without realising that they were still in use
            # for non-transactional advisory locking. This had the effect of
            # releasing all locks prematurely: not good.
            #
            with connected(), post_commit_hooks:
                return func_outside_txn(*args, **kwargs)

    # For convenience, when introspecting for example, expose the original
    # function on the function we're returning.
    call_within_transaction.func = func

    return call_within_transaction


@contextmanager
def savepoint():
    """Context manager to wrap the code within a savepoint.

    This also enters a savepoint context for post-commit hooks, and so should
    always be used in preference to `transaction.atomic()` when only a
    savepoint is needed.

    If either a transaction or a savepoint within a transaction is what you
    want, use the `transactional` decorator.

    If you want a _decorator_ specifically, use the `transactional` decorator.

    If you want a _savepoint decorator_ specifically, write one, or adapt
    this to do it.

    """
    if connection.in_atomic_block:
        with post_commit_hooks.savepoint():
            with transaction.atomic():
                yield
    else:
        raise TransactionManagementError(
            "Savepoints cannot be created outside of a transaction."
        )


def in_transaction(_connection=None):
    """Is `_connection` in the midst of a transaction?

    This only enquires as to Django's perspective on the situation. It does
    not actually check that the database agrees with Django.

    :return: bool
    """
    if _connection is None:
        return connection.in_atomic_block
    else:
        return _connection.in_atomic_block


def validate_in_transaction(connection):
    """Ensure that `connection` is within a transaction.

    This only enquires as to Django's perspective on the situation. It does
    not actually check that the database agrees with Django.

    :raise TransactionManagementError: If no transaction is in progress.
    """
    if not in_transaction(connection):
        raise TransactionManagementError(
            # XXX: GavinPanella 2015-08-07 bug=1482563: This error message is
            # specific to lobjects, but this lives in a general utils module.
            "PostgreSQL's large object support demands that all interactions "
            "are done in a transaction. Further, lobject() has been known to "
            "segfault when used outside of a transaction. This assertion has "
            "prevented the use of lobject() outside of a transaction. Please "
            "investigate."
        )


class DisabledDatabaseConnection:
    """Instances of this class raise exceptions when used.

    Referencing an attribute elicits a :py:class:`RuntimeError`.

    Specifically, this is useful to help prevent Django's
    py:class:`~django.db.utils.ConnectionHandler` from handing out
    usable database connections to code running in the event-loop's
    thread (a.k.a. the reactor thread).
    """

    connection = None

    def __getattr__(self, name):
        self._raise_error()

    def __setattr__(self, name, value):
        self._raise_error()

    def __delattr__(self, name):
        self._raise_error()

    def _raise_error(self):
        raise RuntimeError(
            "Database connections in this thread "
            f"({threading.current_thread().name}) are disabled."
        )

    def close(self):
        """Nothing to close on a disabled connection."""
        return


def disable_all_database_connections():
    """Replace all connections in this thread with unusable stubs.

    Specifically, instances of :py:class:`~DisabledDatabaseConnection`.
    This should help prevent accidental use of the database from the
    reactor thread.

    Why?

    Database access means blocking IO, at least with the connections
    that Django hands out. While blocking IO isn't forbidden in the
    reactor thread, it ought to be avoided, because the reactor can't do
    anything else while it's happening, like handling other IO, or
    running delayed calls.

    Django's transaction and connection management code also assumes
    threads: it associates connections and transactions with the current
    thread, using threading.local. Using the database from the reactor
    thread is a recipe for intermingled transactions.
    """
    for alias in connections:
        connection = connections[alias]
        if type(connection) is not DisabledDatabaseConnection:
            connections[alias] = DisabledDatabaseConnection()
            connection.close()


def enable_all_database_connections():
    """Re-enable database connections in this thread after having...

    ... been previously disabled with `disable_all_database_connections`.

    See `disable_all_database_connections` for the rationale.
    """
    for alias in connections:
        # isinstance() fails because it references __bases__.
        if type(connections[alias]) is DisabledDatabaseConnection:
            del connections[alias]


class TotallyDisconnected:
    """Context to disallow all database connections within a block."""

    def __enter__(self):
        """Disable all database connections, closing those that are open."""
        disable_all_database_connections()

    def __exit__(self, *exc_info):
        """Enable all database connections, but don't actually connect."""
        enable_all_database_connections()


class ExclusivelyConnected:
    """Context to only permit database connections within a block.

    This blows up with `AssertionError` if a database connection is open when
    the context is entered. On exit, all database connections open in the
    current thread will be closed without niceties, and no effort is made to
    suppress database failures at this point.
    """

    def __enter__(self):
        """Assert that no connections are yet open."""
        for alias in connections:
            if connections[alias].connection is not None:
                raise AssertionError(f"Connection {alias} is open.")

    def __exit__(self, *exc_info):
        """Close database connections in the current thread."""
        for alias in connections:
            connections[alias].close()


class FullyConnected:
    """Context to ensure that all databases are connected.

    On entry, connections will be establed to all defined databases. On exit,
    they'll all be closed again. Simple.
    """

    def __enter__(self):
        """Assert that no connections are yet open."""
        for alias in connections:
            connections[alias].ensure_connection()

    def __exit__(self, *exc_info):
        """Close database connections in the current thread."""
        for alias in connections:
            connections[alias].close()


def parse_item_operation(specifier):
    """
    Returns a tuple indicating the specifier string, and its related
    operation (if one was found).

    If the first character in the specifier is '|', the operator will be OR.

    If the first character in the specifier is '&', the operator will be AND.

    If the first character in the specifier is '!', or the specifier starts
    with "not_", the operator will be AND(existing_query, ~(new_query)).

    If unspecified, the default operator is OR.

    :param specifier: a string containing the specifier.
    :return: tuple
    """
    specifier = specifier.strip()

    from operator import and_ as AND
    from operator import inv as INV
    from operator import or_ as OR

    def AND_NOT(current, next_):
        return AND(current, INV(next_))

    if specifier.startswith("|"):
        op = OR
        specifier = specifier[1:]
    elif specifier.startswith("&"):
        op = AND
        specifier = specifier[1:]
    elif specifier.startswith("not_"):
        op = AND_NOT
        specifier = specifier[4:]
    elif specifier.startswith("!"):
        op = AND_NOT
        specifier = specifier[1:]
    else:
        # Default to OR.
        op = OR
    return specifier, op


def parse_item_specifier_type(
    specifier, spec_types: Container = None, separator=":"
):
    """
    Returns a tuple that splits the string int a specifier, and its specifier
    type.

    Retruns a tuple of (specifier, specifier_type). If no specifier type could
    be found in the set, returns None in place of the specifier_type.

    :param specifier: The specifier string, such as "ip:10.0.0.1".
    :param spec_types: A container whose elements are strings that will be
        recognized as specifier types.
    :param separator: Optional specifier. Defaults to ':'.
    :return: tuple
    """
    if separator in specifier:
        tokens = specifier.split(separator, 1)
        if tokens[0] in spec_types:
            specifier_type = tokens[0]
            specifier = tokens[1].strip()
        else:
            specifier_type = None
    else:
        specifier_type = None
    return specifier, specifier_type


def get_model_object_name(queryset):
    """Returns the model object name for the given `QuerySet`, or None if
    it cannot be determined.
    """
    if hasattr(queryset, "model"):
        if hasattr(queryset.model, "_meta"):
            metadata = getattr(queryset.model, "_meta")  # noqa: B009
            if hasattr(metadata, "object_name"):
                return metadata.object_name
    return None


class MAASQueriesMixin:
    """Contains utility functions that any mixin for model object manager
    queries may need to make use of."""

    def get_id_list(self, raw_query):
        """Returns a list of IDs for each row in the specified raw query.

        This can be used to create additional filters to chain from a raw
        query, which would not otherwise be possible.

        Note that using this method risks a race condition, since a row
        could be inserted after the raw query runs.
        """
        ids = [row.id for row in raw_query]
        return self.filter(id__in=ids)

    def get_id_filter(self, raw_query):
        """Returns a `QuerySet` for the specified raw query, by executing it
        and adding an 'in' filter with the ID of each object in the raw query.
        """
        ids = self.get_id_list(raw_query)
        return self.filter(id__in=ids)

    def format_specifiers(self, specifiers):
        """Formats the given specifiers into a list.

        If the list of specifiers is given as a comma-separated list, it is
        inferred that the user would like a set of queries joined with
        logical AND operators.

        If the list of specifiers is given as a dict, it is inferred that each
        key is a specifier type, and each value is a list of specifier values.
        The specifier values inside each list will be joined with logical OR
        operators. The lists for each key will be joined with logical AND
        operators.

        For example, 'name:eth0,hostname:tasty-buscuits' might match interface
        eth0 on node 'tasty-biscuits'; that is, both constraints are required.
        """
        if isinstance(specifiers, int):
            return [str(specifiers)]
        elif isinstance(specifiers, str):
            return [
                "&" + specifier.strip() for specifier in specifiers.split(",")
            ]
        elif isinstance(specifiers, dict):
            return specifiers
        else:
            return list(flatten(specifiers))

    def get_filter_function(
        self, specifier_type, spec_types, item, separator=":"
    ):
        """Returns a function that must return a Q() based on some pervious
        Q(), an operation function (which will manipulate it), and the data
        that will be used as an argument to the filter operation function.

        :param:specifier_type: a string which will be used as a key to get
            the specifier from the spec_types dictionary.
        :param:spec_types: the dictionary of valid specifier types.
        :param:item: the string that will be used to filter by
        :param:separator: a string that must separate specifiers from their
            values. (for example, the default of ':' would be used if you
            wanted specifiers to look like "id:42".)

        :return: types.FunctionType or types.MethodType
        """
        query = spec_types.get(specifier_type, None)
        while True:
            if isinstance(query, (types.FunctionType, types.MethodType)):
                # Found a function or method that will appending the filter
                # string for us. Parameters must be in the format:
                # (<current_Q()>, <operation_function>, <item>), where
                # the operation_function must be a function that takes action
                # on the current_Q() to append a new query object (Q()).
                return query
            elif isinstance(query, tuple):
                # Specifies a query to a subordinate specifier function.
                # This will be a tuple in the format:
                # (manager_object, filter_from_object)
                # That is, filter_from_object defines how to relate the object
                # we're querying back to the object that we care about, and
                # manager_object is a Django Manager instance.
                (manager_object, filter_from_object) = query
                sub_ids = manager_object.filter_by_specifiers(
                    item
                ).values_list(filter_from_object + "__id", flat=True)
                # Return a function to filter the current object based on
                # its IDs (as gathered from the query above to the related
                # object).
                kwargs = {"id__in": sub_ids}
                return lambda cq, op, i: op(cq, Q(**kwargs))
            elif isinstance(query, str):
                if separator in query:
                    # We got a string like "subnet:space". This means we want
                    # to actually use the query specifier at the 'subnet' key,
                    # but we want to convert the item from (for example)
                    # "space1" to "space:space1". When we loop back around,
                    # "subnet" will resolve to a tuple, and we'll query the
                    # specifier-based filter for Subnet.
                    query, subordinate = query.split(separator, 1)
                    item = subordinate + separator + item
                elif "__" in query:
                    # If the value for this query specifier contains the string
                    # '__', assume it's a Django filter expression, and return
                    # the appropriate query. Disambiguate what could be an
                    # 'alias expression' by allowing the __ to appear before
                    # the filter. (that is, prefix the filter string with __
                    # to query the current object.)
                    if query.startswith("__"):
                        query = query[2:]
                    kwargs = {query: item}
                    return lambda cq, op, i: op(cq, Q(**kwargs))
                else:
                    query = spec_types.get(query, None)
            elif query is None:
                # The None key is for the default query for this specifier.
                query = spec_types[None]
            else:
                break
        return None

    def get_specifiers_q(
        self, specifiers, specifier_types=None, separator=":", **kwargs
    ):
        """Returns a Q object for objects matching the given specifiers.

        See documentation for `filter_by_specifiers()`.

        :return:django.db.models.Q
        """
        if specifier_types is None:
            raise NotImplementedError("Subclass must specify specifier_types.")
        current_q = Q()
        if isinstance(specifiers, dict):
            # If we got a dictionary, treat it as one of the entries in a
            # LabeledConstraintMap. That is, each key is a specifier, and
            # each value is a list of values (which must be OR'd together).
            for key, constraint_list in specifiers.items():
                assert isinstance(constraint_list, list)
                constraints = [
                    key + separator + value for value in constraint_list
                ]
                # Leave off specifier_types here because this recursion
                # will go back to the subclass to get the types filled in.
                current_q &= self.get_specifiers_q(
                    constraints, separator=separator
                )
        else:
            for item in specifiers:
                item, op = parse_item_operation(item)
                item, specifier_type = parse_item_specifier_type(
                    item, spec_types=specifier_types, separator=separator
                )
                query = self.get_filter_function(
                    specifier_type, specifier_types, item, separator=separator
                )
                current_q = query(current_q, op, item)
        if kwargs:
            current_q &= Q(**kwargs)
        return current_q

    def filter_by_specifiers(self, specifiers, separator=":", **kwargs):
        """Filters this object by the given specifiers.

        If additional keyword arguments are supplied, they will also be queried
        for, and treated as an AND.

        :return:QuerySet
        """
        specifiers = self.format_specifiers(specifiers)
        query = self.get_specifiers_q(
            specifiers, separator=separator, **kwargs
        )
        return self.filter(query)

    def exclude_by_specifiers(self, specifiers, **kwargs):
        """Excludes subnets by the given list of specifiers (or single
        specifier).

        See documentation for `filter_by_specifiers()`.

        If additional keyword arguments are supplied, they will also be queried
        for, and treated as an AND.

        :return:QuerySet
        """
        specifiers = self.format_specifiers(specifiers)
        query = self.get_specifiers_q(specifiers, **kwargs)
        return self.exclude(query)

    def _add_vlan_vid_query(self, current_q, op, item):
        """Query for a related VLAN with a specified VID (vlan__vid).

        Even though this is a rather specific query, it was placed in orm.py
        since it is shared by multiple subclasses. (It will not be used unless
        referred to by the specifier_types dictionary passed into
        get_specifiers_q() by the subclass.)
        """
        if item.lower() == "untagged":
            vid = 0
        else:
            vid = parse_integer(item)
        if vid < 0 or vid >= 0xFFF:
            raise ValidationError(
                "VLAN tag (VID) out of range (0-4094; 0 for untagged.)"
            )
        current_q = op(current_q, Q(vlan__vid=vid))
        return current_q

    def get_matching_object_map(self, specifiers, query, include_filter=None):
        """This method is intended to be called with a query for foreign object
        IDs. For example, if called from the Interface object (with a list
        of interface specifiers), it might be called with a query string like
        'node__id' (a "foreign" object ID). In general, this you will get a
        dictionary from this method in the form:

        {
            <foreign_id>: [<object_id1>, [<object_id2>], ...]]
            ...
        }

        In other words, call this method when you want a map from a related
        object IDs (specified by 'query') to a list of objects (of the current
        type) which match a query.
        """
        matches = self
        if include_filter is not None:
            matches = matches.filter(**include_filter)
        matches = matches.filter_by_specifiers(specifiers)
        # We'll be looping through the list assuming a particular order later
        # in this function, so make sure the interfaces are grouped by their
        # attached nodes.
        matches = matches.order_by(query)
        matches = matches.values_list("id", query)
        foreign_object_map = defaultdict(list)
        object_ids = set()
        object_id = None
        for foreign_id, current_id in matches:
            if foreign_id is None:
                # Skip objects that do not have a corresponding foreign key.
                continue
            if current_id != object_id:
                object_ids.add(current_id)
                object_id = current_id
            foreign_object_map[current_id].append(foreign_id)
        return object_ids, foreign_object_map

    def get_object_by_specifiers_or_raise(
        self, specifiers: int | str | dict | Iterable | None, **kwargs
    ):
        """Gets an object using the given specifier(s).

        If the specifier is empty, raises Http400.
        If multiple objects are returned, raises Http403.
        If the object cannot be found, raises Http404.

        :param:specifiers: unicode
        """
        object_name = get_model_object_name(self)
        if isinstance(specifiers, str):
            specifiers = specifiers.strip()
        if specifiers is None:
            raise MAASAPIBadRequest("%s specifier required." % object_name)
        try:
            object = get_one(self.filter_by_specifiers(specifiers, **kwargs))
            if object is None:
                raise Http404("No %s matches the given query." % object_name)
        except self.model.MultipleObjectsReturned:
            raise MAASAPIForbidden(  # noqa: B904
                "Too many %s objects match the given query." % object_name
            )
        return object

    def get_object_id(self, name, prefix=None):
        """
        Given the specified name and prefix, attempts to derive an object ID.

        By default (if a prefix is not supplied), uses the lowercase version
        of the current model object name as a prefix.

        For example, if the current model object name is "Fabric", and a string
        such as 'fabric-10' is supplied, int(10) will be returned. If an
        incorrect prefix is supplied, None will be returned. If an integer is
        supplied, the integer will be returned. If a string is supplied, that
        string will be parsed as an integer and returned (before trying to
        match against 'prefix-<int>').

        :param name: str
        :param prefix: str
        :return: int
        """
        if name is None:
            return None
        if isinstance(name, int):
            return name
        try:
            object_id = parse_integer(name)
            return object_id
        except ValueError:
            # Move on to check if this is a "name" like "object-10".
            pass
        if prefix is None:
            prefix = get_model_object_name(self).lower()
        name = name.strip()
        match = re.match(r"%s-(\d+)$" % prefix, name)
        if match is not None:
            (object_id,) = match.groups()
            object_id = int(object_id)
            return object_id
        else:
            return None

    def _add_default_query(self, current_q, op, item):
        """If the item we're matching is an integer, first try to locate the
        object by its ID. Otherwise, search by name.
        """
        object_id = self.get_object_id(item)
        if object_id is not None:
            return op(current_q, Q(id=object_id))
        else:
            return op(current_q, Q(name=item))


def reload_object(model_object):
    """Reload `obj` from the database.

    If the object has been deleted, this will return None.

    :param model_object: Model object to reload.
    :type model_object: Concrete `Model` subtype.
    :return: Freshly-loaded instance of `model_object`, or None.
    :rtype: Same as `model_object`.
    """
    model_class = model_object.__class__
    return get_one(model_class.objects.filter(id=model_object.id))


def prefetch_queryset(queryset, prefetches):
    """Perform prefetching on the `queryset`."""
    for prefetch in prefetches:
        queryset = queryset.prefetch_related(prefetch)
    return queryset


def log_sql_calls(func):
    """Inform the `count_queries` decorated to print all the SQL calls for
    this function."""
    func.__log_sql_calls__ = True
    return func


def count_queries(log_func):
    """Decorator that will count the queries and call `log_func` with the log
    message.
    """

    def wrapper(func):
        def inner_wrapper(*args, **kwargs):
            # Reset the queries count before performing the function.
            reset_queries()

            # Perform the work that will create queries.
            result = func(*args, **kwargs)

            # Calculate the query_time and log the number and time.
            query_time = sum(
                float(query.get("time", 0)) for query in connection.queries
            )
            log_func(
                "[QUERIES] %s executed %s queries in %s seconds"
                % (func.__name__, len(connection.queries), query_time)
            )

            # Log all the queries if requested.
            if getattr(func, "__log_sql_calls__", False) or getattr(
                settings, "DEBUG_QUERIES_LOG_ALL", False
            ):
                log_func("[QUERIES] === Start SQL Log: %s ===" % func.__name__)
                for query in connection.queries:
                    log_func("[QUERIES] %s" % query.get("sql"))
                log_func("[QUERIES] === End SQL Log: %s ===" % func.__name__)

            return result

        return inner_wrapper

    return wrapper


def get_database_owner() -> str:
    """Return database owner."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
                       SELECT pg_catalog.pg_get_userbyid(d.datdba)
                       FROM pg_catalog.pg_database d
                       WHERE d.datname = current_database()"""
        )
        row = cursor.fetchone()
    return row[0]
