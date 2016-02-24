# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Construct sample application data dynamically."""

__all__ = [
    "populate",
]

from random import choice

from maasserver.enum import NODE_STATUS
from maasserver.testing.factory import factory
from maasserver.utils.orm import transactional


@transactional
def populate():
    """Populate the database with example data.

    This should:

    - Mimic a real-world MAAS installation,

    - Create example data for all of MAAS's features,

    - Not go overboard; in general there need be at most a handful of each
      type of object,

    - Have elements of randomness; the sample data should never become
      something we depend upon too closely — for example in QA, demos, and
      tests — and randomness helps to keep us honest.

    If there is something you need, add it. If something does not make sense,
    change it or remove it. If you need something esoteric that would muddy
    the waters for the majority, consider putting it in a separate function.

    This function expects to be run into an empty database. It is not
    idempotent, and will almost certainly crash if invoked multiple times on
    the same database.

    """

    admin = factory.make_admin(username="admin", password="test")  # noqa
    user1, _ = factory.make_user_with_keys(username="user1", password="test")
    user2, _ = factory.make_user_with_keys(username="user2", password="test")

    zones = [
        factory.make_Zone(name="zone-north"),
        factory.make_Zone(name="zone-south"),
    ]
    fabrics = [
        factory.make_Fabric(name="fabric-red"),
        factory.make_Fabric(name="fabric-blue"),
    ]
    racks = [  # noqa
        factory.make_RackController(
            fabric=fabric, vlan=fabric.get_default_vlan())
        for fabric in fabrics
    ]

    user1_machines = [  # noqa
        factory.make_Node(
            owner=user1, status=NODE_STATUS.ALLOCATED, zone=choice(zones),
            fabric=choice(fabrics),
        ),
        factory.make_Node(
            owner=user1, status=NODE_STATUS.DEPLOYED, zone=choice(zones),
            fabric=choice(fabrics),
        ),
    ]
    user2_machines = [  # noqa
        factory.make_Node(
            owner=user2, status=NODE_STATUS.DEPLOYING, zone=choice(zones),
            fabric=choice(fabrics),
        ),
        factory.make_Node(
            owner=user2, status=NODE_STATUS.RELEASING, zone=choice(zones),
            fabric=choice(fabrics),
        ),
    ]
