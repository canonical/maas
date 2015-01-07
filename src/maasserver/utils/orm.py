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
    'get_exception_class',
    'get_first',
    'get_one',
    'is_serialization_failure',
    'macs_contain',
    'macs_do_not_contain',
    'make_serialization_failure',
    'outside_atomic_block',
    'request_transaction_retry',
    'retry_on_serialization_failure',
    'validate_in_transaction',
    ]

from contextlib import contextmanager
from functools import wraps
from itertools import islice

from django.core.exceptions import MultipleObjectsReturned
from django.db import transaction
from django.db.transaction import TransactionManagementError
from django.db.utils import OperationalError
from psycopg2.errorcodes import SERIALIZATION_FAILURE


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


def is_serialization_failure(exception):
    """Does `exception` represent a serialization failure?

    PostgreSQL sets a specific error code, "40001", when a transaction breaks
    because of a serialization failure. This is normally about the right time
    to try again.

    :see: http://www.postgresql.org/docs/9.3/static/transaction-iso.html
    """
    if isinstance(exception, OperationalError):
        try:
            pgcode = exception.__cause__.pgcode
        except AttributeError:
            return False  # Presumably no __cause__.
        else:
            return pgcode == SERIALIZATION_FAILURE
    else:
        return False


def make_serialization_failure():
    """Make a serialization exception.

    :returns: an instance of :py:class:`OperationalError` that will pass an
        `is_serialization_failure` predicate.
    """
    exception = OperationalError()
    exception.__cause__ = Exception()
    exception.__cause__.pgcode = SERIALIZATION_FAILURE
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


def retry_on_serialization_failure(func):
    """Retry the wrapped function when it raises a serialization failure.

    It will call `func` a maximum of ten times, and will only retry if a
    serialization failure is detected.

    BE CAREFUL WHERE YOU USE THIS.

    In general it only makes sense to use this to wrap the *outermost*
    transactional block, e.g. outside of an `atomic` decorator. This is
    because we want a new transaction to be started on the way in, and rolled
    back on the way out before this function attempts to retry.

    """
    @wraps(func)
    def retrier(*args, **kwargs):
        for _ in xrange(9):
            try:
                return func(*args, **kwargs)
            except OperationalError as error:
                if not is_serialization_failure(error):
                    raise
        else:
            return func(*args, **kwargs)
    return retrier


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


def validate_in_transaction(connection):
    """Ensure that `connection` is within a transaction.

    This only enquires as to Django's perspective on the situation. It does
    not actually check that the database agrees with Django.

    :raise TransactionManagementError: If no transaction is in progress.
    """
    in_transaction = (
        # Django's new transaction management stuff is active.
        connection.in_atomic_block or (
            # Django's "legacy" transaction management system is active.
            len(connection.transaction_state) > 0 and
            # Django is managing the transaction state.
            connection.transaction_state[-1]
        )
    )
    if not in_transaction:
        raise TransactionManagementError(
            "PostgreSQL's large object support demands that all interactions "
            "are done in a transaction. Further, lobject() has been known to "
            "segfault when used outside of a transaction. This assertion has "
            "prevented the use of lobject() outside of a transaction. Please "
            "investigate.")
