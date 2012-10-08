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

import itertools
import math

from maasserver.enum import (
    ARCHITECTURE_CHOICES,
    ARCHITECTURE_CHOICES_DICT,
    )
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
        int_value = int(math.ceil(float(str_value)))
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


def generate_architecture_wildcards(choices=ARCHITECTURE_CHOICES):
    """Map 'primary' architecture names to a list of full expansions.

    Return a dictionary keyed by the primary architecture name (the part before
    the '/'). The value of an entry is a frozenset of full architecture names
    ('primary_arch/subarch') under the keyed primary architecture.

    """

    sorted_arch_list = sorted(choice[0] for choice in choices)

    def extract_primary_arch(arch):
        return arch.split('/')[0]

    return {
        primary_arch: frozenset(subarch_generator)
        for primary_arch, subarch_generator in itertools.groupby(
            sorted_arch_list, key=extract_primary_arch
        )
    }


architecture_wildcards = generate_architecture_wildcards()


# juju uses a general "arm" architecture constraint across all of its
# providers. Since armhf is the cross-distro agreed Linux userspace
# architecture and ABI and ARM servers are expected to only use armhf,
# interpret "arm" to mean "armhf" in MAAS.
architecture_wildcards['arm'] = architecture_wildcards['armhf']


def constrain_architecture(nodes, key, value):
    assert key == 'architecture', "This filter is for architecture only."

    if value in ARCHITECTURE_CHOICES_DICT:
        # Full 'arch/subarch' specified directly
        return nodes.filter(architecture=value)
    elif value in architecture_wildcards:
        # Try to expand 'arch' to all available 'arch/subarch' matches
        return nodes.filter(
            architecture__in=architecture_wildcards[value])
    else:
        raise InvalidConstraint(
            'architecture', value, "Architecture not recognised.")


# this is the mapping of constraint names to how to apply the constraint
constraint_filters = {
    # Currently architecture only supports exact matching. Eventually, we will
    # probably want more logic to note that eg, amd64 can be used for an i386
    # request
    'architecture': constrain_architecture,
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
