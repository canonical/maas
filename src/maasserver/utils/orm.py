# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
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
    'disable_all_database_connections',
    'enable_all_database_connections',
    'ExclusivelyConnected',
    'FullyConnected',
    'gen_retry_intervals',
    'get_exception_class',
    'get_first',
    'get_one',
    'in_transaction',
    'is_serialization_failure',
    'macs_contain',
    'macs_do_not_contain',
    'make_serialization_failure',
    'post_commit',
    'post_commit_do',
    'psql_array',
    'request_transaction_retry',
    'retry_on_serialization_failure',
    'savepoint',
    'TotallyDisconnected',
    'transactional',
    'validate_in_transaction',
    'with_connection',
    ]

from contextlib import contextmanager
from functools import wraps
from itertools import (
    chain,
    islice,
    repeat,
    takewhile,
)
import threading
from time import sleep
import types

from django.core.exceptions import (
    MultipleObjectsReturned,
    ValidationError,
)
from django.db import (
    connection,
    connections,
    transaction,
)
from django.db.models import Q
from django.db.transaction import TransactionManagementError
from django.db.utils import OperationalError
from maasserver.utils.async import DeferredHooks
from provisioningserver.utils import flatten
from provisioningserver.utils.backoff import (
    exponential_growth,
    full_jitter,
)
from provisioningserver.utils.network import parse_integer
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


def gen_description_of_hooks(hooks):
    """Generate lines describing the given hooks.

    :param hooks: An iterable of :class:`Deferred` instances.
    """
    for index, hook in enumerate(hooks):
        yield "== Hook %d: %r ==" % (index + 1, hook)
        for cb, eb in hook.callbacks:
            yield " +- callback: %r" % (cb[0],)
            yield " |      args: %r" % (cb[1],)
            yield " |    kwargs: %r" % (cb[2],)
            yield " |   errback: %r" % (eb[0],)
            yield " |      args: %r" % (eb[1],)
            yield " +--- kwargs: %r" % (eb[2],)


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
                "Orphaned post-commit hooks found:\n" + description)

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


@contextmanager
def connected():
    """Context manager that ensures we're connected to the database.

    If there is not yet a connection to the database, this will connect on
    entry and disconnect on exit. Preexisting connections will be left alone.
    """
    if connection.connection is None:
        connection.ensure_connection()
        try:
            yield
        finally:
            connection.close()
    else:
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
            "Savepoints cannot be created outside of a transaction.")


def in_transaction(connection=connection):
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
            # XXX: GavinPanella 2015-08-07 bug=1482563: This error message is
            # specific to lobjects, but this lives in a general utils module.
            "PostgreSQL's large object support demands that all interactions "
            "are done in a transaction. Further, lobject() has been known to "
            "segfault when used outside of a transaction. This assertion has "
            "prevented the use of lobject() outside of a transaction. Please "
            "investigate.")


class DisabledDatabaseConnection:
    """Instances of this class raise exceptions when used.

    Referencing an attribute elicits a :py:class:`RuntimeError`.

    Specifically, this is useful to help prevent Django's
    py:class:`~django.db.utils.ConnectionHandler` from handing out
    usable database connections to code running in the event-loop's
    thread (a.k.a. the reactor thread).
    """

    def __getattr__(self, name):
        raise RuntimeError(
            "Database connections in this thread (%s) are "
            "disabled." % threading.currentThread().name)

    def __setattr__(self, name, value):
        raise RuntimeError(
            "Database connections in this thread (%s) are "
            "disabled." % threading.currentThread().name)

    def __delattr__(self, name):
        raise RuntimeError(
            "Database connections in this thread (%s) are "
            "disabled." % threading.currentThread().name)


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
                raise AssertionError("Connection %s is open." % (alias,))

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

    from operator import (
        and_ as AND,
        inv as INV,
        or_ as OR,
    )
    AND_NOT = lambda current, next: AND(current, INV(next))

    if specifier.startswith('|'):
        op = OR
        specifier = specifier[1:]
    elif specifier.startswith('&'):
        op = AND
        specifier = specifier[1:]
    elif specifier.startswith('not_'):
        op = AND_NOT
        specifier = specifier[4:]
    elif specifier.startswith('!'):
        op = AND_NOT
        specifier = specifier[1:]
    else:
        # Default to OR.
        op = OR
    return specifier, op


def parse_item_specifier_type(specifier, spec_types={}, separator=':'):
    """
    Returns a tuple that splits the string int a specifier, and its specifier
    type.

    Retruns a tuple of (specifier, specifier_type). If no specifier type could
    be found in the set, returns None in place of the specifier_type.

    :param specifier: The specifier string, such as "ip:10.0.0.1".
    :param spec_types: A dict whose keys are strings that will be recognized
        as specifier types.
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


class MAASQueriesMixin(object):
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

    def get_filter_function(
            self, specifier_type, spec_types, item, separator=':'):
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
            elif isinstance(query, types.TupleType):
                # Specifies a query to a subordinate specifier function.
                # This will be a tuple in the format:
                # (manager_object, filter_from_object)
                # That is, filter_from_object defines how to relate the object
                # we're querying back to the object that we care about, and
                # manager_object is a Django Manager instance.
                (manager_object, filter_from_object) = query
                sub_ids = manager_object.filter_by_specifiers(
                    item).values_list(filter_from_object + '__id', flat=True)
                # Return a function to filter the current object based on
                # its IDs (as gathered from the query above to the related
                # object).
                kwargs = {"id__in": sub_ids}
                return lambda cq, op, i: op(cq, Q(**kwargs))
            elif isinstance(query, unicode):
                if separator in query:
                    # We got a string like "subnet:space". This means we want
                    # to actually use the query specifier at the 'subnet' key,
                    # but we want to convert the item from (for example)
                    # "space1" to "space:space1". When we loop back around,
                    # "subnet" will resolve to a tuple, and we'll query the
                    # specifier-based filter for Subnet.
                    query, subordinate = query.split(separator, 1)
                    item = subordinate + separator + item
                elif '__' in query:
                    # If the value for this query specifier contains the string
                    # '__', assume it's a Django filter expression, and return
                    # the appropriate query. Disambiguate what could be an
                    # 'alias expression' by allowing the __ to appear before
                    # the filter. (that is, prefix the filter string with __
                    # to query the current object.)
                    if query.startswith('__'):
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
            self, specifiers, specifier_types=None, separator=':'):
        """Returns a Q object for objects matching the given specifiers.

        See documentation for `filter_by_specifiers()`.

        :return:django.db.models.Q
        """
        if specifier_types is None:
            raise NotImplementedError("Subclass must specify specifier_types.")
        current_q = Q()
        # Handle a single item, or a list.
        specifiers = list(flatten(specifiers))
        for item in specifiers:
            item, op = parse_item_operation(item)
            item, specifier_type = parse_item_specifier_type(
                item, spec_types=specifier_types, separator=separator)
            query = self.get_filter_function(
                specifier_type, specifier_types, item, separator=separator)
            current_q = query(current_q, op, item)
        return current_q

    def filter_by_specifiers(self, specifiers, separator=':'):
        query = self.get_specifiers_q(specifiers, separator=separator)
        return self.filter(query)

    def exclude_by_specifiers(self, specifiers):
        """Excludes subnets by the given list of specifiers (or single
        specifier).

        See documentation for `filter_by_specifiers()`.

        :raise:AddrFormatError:If a specific IP address or CIDR is requested,
            but the address could not be parsed.
        :return:QuerySet
        """
        query = self.get_specifiers_q(specifiers)
        return self.exclude(query)

    def _add_vlan_vid_query(self, current_q, op, item):
        if item.lower() == 'untagged':
            vid = 0
        else:
            vid = parse_integer(item)
        if vid < 0 or vid >= 0xfff:
            raise ValidationError(
                "VLAN tag (VID) out of range "
                "(0-4094; 0 for untagged.)")
        current_q = op(current_q, Q(vlan__vid=vid))
        return current_q

    def get_matching_object_map(self, specifiers, query):
        filter = self.filter_by_specifiers(specifiers)
        # We'll be looping through the list assuming a particular order later
        # in this function, so make sure the interfaces are grouped by their
        # attached nodes.
        matches = filter.order_by(query)
        matches = matches.values_list('id', query)
        foreign_object_map = {}
        object_ids = set()
        object_id = None
        foreign_object_matches = None
        for foreign_id, current_id in matches:
            if foreign_id is None:
                # Skip objects that do not have a corresponding foreign key.
                continue
            if current_id != object_id:
                # Encountered a new node ID in the list, so create an empty
                # list and add it to the map. (and add it to the set of matched
                # nodes)
                foreign_object_matches = []
                foreign_object_map[current_id] = foreign_object_matches
                object_ids.add(current_id)
                object_id = current_id
            foreign_object_matches.append(foreign_id)
        return object_ids, foreign_object_map
