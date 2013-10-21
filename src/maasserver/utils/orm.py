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
    'macs_contain',
    'macs_do_not_contain',
    'get_exception_class',
    'get_first',
    'get_one',
    ]

from itertools import islice

from django.core.exceptions import MultipleObjectsReturned


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
