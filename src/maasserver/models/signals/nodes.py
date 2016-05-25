# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to node changes."""

__all__ = [
    "signals",
]

from django.db.models.signals import post_save
from maasserver.models import (
    Controller,
    Device,
    Machine,
    Node,
    RackController,
    RegionController,
    Service,
)
from maasserver.utils.signals import SignalsManager
from metadataserver.models.nodekey import NodeKey


NODE_CLASSES = [
    Node,
    Machine,
    Device,
    Controller,
    RackController,
    RegionController,
]

signals = SignalsManager()


def clear_nodekey_when_owner_changes(node, old_values, deleted=False):
    """Erase related `NodeKey` when node ownership changes."""
    assert not deleted, (
        "clear_nodekey_when_owner_changes is not prepared "
        "to deal with deletion of nodes.")

    owner_id_old = old_values[0]
    owner_id_new = node.owner_id

    if owner_id_new != owner_id_old:
        NodeKey.objects.clear_token_for_node(node)

for klass in NODE_CLASSES:
    signals.watch_fields(
        clear_nodekey_when_owner_changes,
        klass, ['owner_id'], delete=False)


def create_services_on_node_type_change(node, old_values, deleted=False):
    """Create services when node_type changes."""
    old_node_type = old_values[0]
    new_node_type = node.node_type
    if new_node_type != old_node_type:
        Service.objects.create_services_for(node)


def create_services_on_create(sender, instance, created, **kwargs):
    """Create services when node created."""
    if created:
        Service.objects.create_services_for(instance)

for klass in NODE_CLASSES:
    signals.watch_fields(
        create_services_on_node_type_change,
        klass, ['node_type'], delete=False)
    signals.watch(
        post_save, create_services_on_create,
        sender=klass)


# Enable all signals by default.
signals.enable()
