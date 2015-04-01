# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""ORM-related utilities."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'commit_within_atomic_block',
    'gen_retry_intervals',
    'get_exception_class',
    'get_first',
    'get_one',
    'is_serialization_failure',
    'macs_contain',
    'macs_do_not_contain',
    'make_serialization_failure',
    'outside_atomic_block',
    'post_commit',
    'post_commit_do',
    'psql_array',
    'request_transaction_retry',
    'retry_on_serialization_failure',
    'transactional',
    'validate_in_transaction',
    ]

from contextlib import contextmanager
from functools import wraps
from itertools import (
    chain,
    islice,
    repeat,
    takewhile,
)
from time import sleep

from django.core.exceptions import MultipleObjectsReturned
from django.db import (
    close_old_connections,
    connection,
    transaction,
)
from django.db.transaction import TransactionManagementError
from django.db.utils import OperationalError
from maasserver.utils.async import DeferredHooks
from provisioningserver.utils.backoff import (
    exponential_growth,
    full_jitter,
)
from provisioningserver.utils.twisted import callOut
import psycopg2
from psycopg2.errorcodes import SERIALIZATION_FAILURE
from twisted.internet.defer import Deferred


def get_exception_class(items):
    """Return exception class to raise.

    If `items` looks like a Django ORM result set, returns the
    `MultipleObjectsReturned` class as defined in that model.  Otherwise,
    returns the generic class.
    """
    model = getattr(items, 'model', None)
    return getattr(model, 'MultipleObjectsReturned', MultipleObjectsReturned)


def get_one(items):
    """Assume there's at most one item in `items`, and return it (or None).

    If `items` contains more than one item, raise an error.  If `items` looks
    like a Django ORM result set, the error will be of the same model-specific
    Django `MultipleObjectsReturned` type that `items.get()` would raise.
    Otherwise, a plain Django :class:`MultipleObjectsReturned` error.

    :param items: Any sequence.
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
        raise get_exception_class(items)("Got more than one item.")


def get_first(items):
    """Get the first of `items`, or None."""
    first_item = tuple(islice(items, 0, 1))
    if len(first_item) == 0:
        return None
    else:
        return first_item[0]


def psql_array(items, sql_type=None):
    """Return PostgreSQL array string and parameters."""
    sql = (
        "ARRAY[" +
        ",".join(["%s"] * len(items)) +
        "]")
    if sql_type is not None:
        sql += "::%s[]" % sql_type
    return sql, items


def macs_contain(key, macs):
    """Get the "Django ORM predicate: 'key' contains all the given macs.

    This method returns a tuple of the where clause (as a string) and the
    parameters (as a list of strings) used to format the where clause.
    This is typically used with Django's QuerySet's where() method::

      >>> from maasserver.models.node import Node

      >>> where, params = macs_contain('router', ["list", "of", "macs"])
      >>> all_nodes = Node.objects.all()
      >>> filtered_nodes = all_nodes.extra(where=[where], params=params)

    """
    where_clause = (
        "%s @> ARRAY[" % key +
        ', '.join(["%s"] * len(macs)) +
        "]::macaddr[]")
    return where_clause, macs


def macs_do_not_contain(key, macs):
    """Get the Django ORM predicate: 'key' doesn't contain any macs.

    This method returns a tuple of the where clause (as a string) and the
    parameters (as a list of strings) used to format the where clause.
    This is typically used with Django's QuerySet's where() method::

      >>> from maasserver.models.node import Node

      >>> where, params = macs_do_not_contain(
      ...     'routers', ["list", "of", "macs"])
      >>> all_nodes = Node.objects.all()
      >>> filtered_nodes = all_nodes.extra(where=[where], params=params)

    """
    contains_any = " OR ".join([
        "%s " % key + "@> ARRAY[%s]::macaddr[]"] * len(macs))
    where_clause = "((%s IS NULL) OR NOT (%s))" % (key, contains_any)
    return where_clause, macs


def get_psycopg2_exception(exception):
    """Find the root PostgreSQL error from an database exception.

    We may be dealing with a raw exception or with a wrapper provided by
    Django, put there by ``DatabaseErrorWrapper``. As a belt-n-braces measure
    this searches for instances of `psycopg2.Error`, then, if not found, in
    the exception's cause (``__cause__``), recursively.

    :return: The underlying `psycopg2.Error`, or `None` if there isn't one.
    """
    try:
        exception = exception.__cause__
    except AttributeError:
        return exception if isinstance(exception, psycopg2.Error) else None
    else:
        return get_psycopg2_exception(exception)


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


def request_transaction_retry():
    """Raise a serialization exception.

    This depends on the retry machinery being higher up in the stack, catching
    this, and then retrying the transaction, though it may choose to re-raise
    the error if too many retries have already been attempted.

    :raises OperationalError:
    """
    raise make_serialization_failure()


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


def retry_on_serialization_failure(func, reset=noop):
    """Retry the wrapped function when it raises a serialization failure.

    It will call `func` a maximum of ten times, and will only retry if a
    serialization failure is detected.

    BE CAREFUL WHERE YOU USE THIS.

    In general it only makes sense to use this to wrap the *outermost*
    transactional block, e.g. outside of an `atomic` decorator. This is
    because we want a new transaction to be started on the way in, and rolled
    back on the way out before this function attempts to retry.

    :param reset: An optional callable that will be called between attempts.
        It is *not* called before the first attempt. If the last attempt fails
        with a serialization failure it will *not* be called. If an attempt
        fails with a non-serialization failure, it will *not* be called.

    """
    @wraps(func)
    def retrier(*args, **kwargs):
        intervals = gen_retry_intervals()
        for _ in xrange(9):
            try:
                return func(*args, **kwargs)
            except OperationalError as error:
                if is_serialization_failure(error):
                    reset()  # Which may do nothing.
                    sleep(next(intervals))
                else:
                    raise
        else:
            return func(*args, **kwargs)
    return retrier


class PostCommitHooks(DeferredHooks):
    """A specialised set of `DeferredHooks` for post-commit tasks.

    Can be used as a context manager, to check for orphaned post-commit hooks
    on the way in, and to run newly added hooks on the way out.
    """

    def __enter__(self):
        if len(self.hooks) > 0:
            # Crash when there are orphaned post-commit hooks. These might
            # only turn up in testing, where transactions are managed by the
            # test framework instead of this decorator. We need to fail hard
            # -- not just warn about it -- to ensure it gets fixed.
            self.reset()
            raise TransactionManagementError(
                "Orphaned post-commit hooks found.")

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
        raise AssertionError(
            "Not a Deferred or callable: %r" % (hook,))

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
        raise AssertionError("Not callable: %r" % (func,))


def transactional(func):
    """Decorator that wraps calls to `func` in a Django-managed transaction.

    It ensures that connections are closed if necessary. This keeps Django
    happy, especially in the test suite.

    In addition, if `func` is being invoked from outside of a transaction,
    this will retry if it fails with a serialization failure.
    """
    func_within_txn = transaction.atomic(func)  # For savepoints.
    func_outside_txn = retry_on_serialization_failure(
        func_within_txn, reset=post_commit_hooks.reset)

    @wraps(func)
    def call_within_transaction(*args, **kwargs):
        if connection.in_atomic_block:
            # Don't use the retry-capable function if we're already in a
            # transaction; retrying is pointless when the txn is broken.
            return func_within_txn(*args, **kwargs)
        else:
            # Use the retry-capable function, firing post-transaction hooks.
            try:
                with post_commit_hooks:
                    return func_outside_txn(*args, **kwargs)
            finally:
                close_old_connections()

    return call_within_transaction


def commit_within_atomic_block(using="default"):
    """Exits an atomic block then immediately re-enters a new one.

    This relies on the fact that an atomic block commits when exiting the
    outer-most context.
    """
    with outside_atomic_block(using):
        pass  # We just want to exit and enter.


@contextmanager
def outside_atomic_block(using="default"):
    """A context manager that guarantees to not contain an atomic block.

    On entry into this context, this will exit all nested and unnested atomic
    blocks until it reaches clear air.

    On exit from this context, the same level of nesting will be
    reestablished.
    """
    connection = transaction.get_connection(using)
    atomic_context = transaction.atomic(using)
    assert connection.in_atomic_block

    depth = 0
    while connection.in_atomic_block:
        atomic_context.__exit__(None, None, None)
        depth = depth + 1
    try:
        yield
    finally:
        while depth > 0:
            atomic_context.__enter__()
            depth = depth - 1


def in_transaction(connection):
    """Is `connection` in the midst of a transaction?

    This only enquires as to Django's perspective on the situation. It does
    not actually check that the database agrees with Django.

    :return: bool
    """
    return (
        # Django's new transaction management stuff is active.
        connection.in_atomic_block or (
            # Django's "legacy" transaction management system is active.
            len(connection.transaction_state) > 0 and
            # Django is managing the transaction state.
            connection.transaction_state[-1]
        )
    )


def validate_in_transaction(connection):
    """Ensure that `connection` is within a transaction.

    This only enquires as to Django's perspective on the situation. It does
    not actually check that the database agrees with Django.

    :raise TransactionManagementError: If no transaction is in progress.
    """
    if not in_transaction(connection):
        raise TransactionManagementError(
            "PostgreSQL's large object support demands that all interactions "
            "are done in a transaction. Further, lobject() has been known to "
            "segfault when used outside of a transaction. This assertion has "
            "prevented the use of lobject() outside of a transaction. Please "
            "investigate.")
