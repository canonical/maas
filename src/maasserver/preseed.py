# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Preseed module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []


GENERIC_FILENAME = 'generic'


# XXX: rvb 2012-06-14 bug=1013146:  'precise' is hardcoded here.
def get_preseed_filenames(node, type, release='precise'):
    """List possible preseed template filenames for the given node.

    :param node: The node to return template preseed filenames for.
    :type node: :class:`maasserver.models.Node`
    :param type: The preseed type (will be used as a prefix in the template
        filenames).  Usually one of {'', 'enlist', 'commissioning'}.
    :type type: basestring
    :param release: The Ubuntu release to be used.
    :type type: basestring

    Returns a list of possible preseed template filenames using the following
    lookup order:
    {type}_{node_architecture}_{node_subarchitecture}_{release}_{node_hostname}
    {type}_{node_architecture}_{node_subarchitecture}_{release}
    {type}_{node_architecture}
    {type}
    'generic'
    """
    arch = split_subarch(node.architecture)
    elements = [type] + arch + [release, node.hostname]
    while elements:
        yield compose_filename(elements)
        elements.pop()
    yield GENERIC_FILENAME


def split_subarch(architecture):
    """Split the architecture and the subarchitecture."""
    return architecture.split('/')


def compose_filename(elements):
    """Create a preseed filename from a list of elements."""
    return '_'.join(elements)
