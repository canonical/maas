# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'constrain_nodes',
    ]

from maasserver.exceptions import (
    InvalidConstraint,
    )
from maasserver.models import Tag
from maasserver.utils.orm import get_one


def constrain_identical(nodes, key, value):
    """Match the field 'key' to exactly match 'value'"""
    return nodes.filter(**{key: value})


def constrain_int_greater_or_equal(nodes, key, str_value):
    """Filter nodes that have value >= supplied value.

    :param str_value: Will be cast to an integer, if this fails, it is treated
        as an invalid constraint.
    """
    try:
        int_value = int(str_value)
    except ValueError as e:
        raise InvalidConstraint(key, str_value, e)
    return nodes.filter(**{'%s__gte' % (key,): int_value})


def constrain_tags(nodes, key, tag_expression):
    """Tags match: restrict to nodes that have all tags."""
    # We use ',' separated or space ' ' separated values.
    tag_names = tag_expression.replace(",", " ").strip().split()
    for tag_name in tag_names:
        tag = get_one(Tag.objects.filter(name=tag_name))
        if tag is None:
            raise InvalidConstraint('tags', tag_name, 'No such tag')
        nodes = nodes.filter(tags=tag)
    return nodes


# this is the mapping of constraint names to how to apply the constraint
constraint_filters = {
    # Currently architecture only supports exact matching. Eventually, we will
    # probably want more logic to note that eg, amd64 can be used for an i386
    # request
    'architecture': constrain_identical,
    'hostname': constrain_identical,
    'cpu_count': constrain_int_greater_or_equal,
    'memory': constrain_int_greater_or_equal,
    'tags': constrain_tags,
}


def constrain_nodes(nodes, constraints):
    """Apply the dict of constraints as filters against nodes.

    :param nodes: A QuerySet against nodes
    :param constraints: A dict of {'constraint': 'value'}
    """
    if not constraints:
        return nodes
    for constraint_name, value in constraints.items():
        filter = constraint_filters.get(constraint_name)
        if filter is not None:
            nodes = filter(nodes, constraint_name, value)
    return nodes
