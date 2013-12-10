# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test Zone objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.models.zone import Zone
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestZone(MAASServerTestCase):
    """Tests for :class:`Zone`."""

    def test_init(self):
        node1 = factory.make_node()
        node2 = factory.make_node()
        name = factory.make_name('name')
        description = factory.make_name('description')

        zone = Zone(name=name, description=description)
        zone.save()
        zone.node_set.add(node1)
        zone.node_set.add(node2)

        self.assertEqual(
            (
                set(zone.node_set.all()),
                zone.name,
                zone.description,
                node1.zone,
                node2.zone,
            ),
            (set([node1, node2]), name, description, zone, zone))
