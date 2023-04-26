# Copyright 2015-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to node changes."""


from django.db.models.signals import post_init, post_save, pre_delete, pre_save

from maasserver.enum import NODE_STATUS, POWER_STATE
from maasserver.models import (
    Controller,
    Device,
    Machine,
    Node,
    RackController,
    RegionController,
    Service,
)
from maasserver.models.nodeconfig import create_default_nodeconfig
from maasserver.models.nodekey import NodeKey
from maasserver.models.numa import create_default_numanode
from maasserver.utils.signals import SignalsManager

NODE_CLASSES = [
    Node,
    Machine,
    Device,
    Controller,
    RackController,
    RegionController,
]

signals = SignalsManager()


def pre_delete_update_events(sender, instance, **kwargs):
    """Update node hostname and id for events related to the node."""
    instance.event_set.all().update(
        node_hostname=instance.hostname, node_id=None
    )


for klass in NODE_CLASSES:
    signals.watch(pre_delete, pre_delete_update_events, sender=klass)


def post_init_store_previous_status(sender, instance, **kwargs):
    """Store the pre_save status of the instance."""
    instance.__previous_status = instance.status


for klass in NODE_CLASSES:
    signals.watch(post_init, post_init_store_previous_status, sender=klass)


def pre_save_update_status(sender, instance, **kwargs):
    """Update node previous_status when node status changes."""
    if (
        instance.__previous_status != instance.status
        and instance.__previous_status
        not in (
            NODE_STATUS.RESCUE_MODE,
            NODE_STATUS.ENTERING_RESCUE_MODE,
            NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
            NODE_STATUS.EXITING_RESCUE_MODE,
            NODE_STATUS.FAILED_EXITING_RESCUE_MODE,
            NODE_STATUS.TESTING,
        )
    ):
        instance.previous_status = instance.__previous_status


for klass in NODE_CLASSES:
    signals.watch(pre_save, pre_save_update_status, sender=klass)


def clear_owner_when_status_changes_to_new_or_ready(
    sender, instance, **kwargs
):
    """Clear owner when the status changes to NEW or READY."""
    # Controllers are currently stateless but do have an owner.
    if not instance.is_controller:
        for status in {NODE_STATUS.NEW, NODE_STATUS.READY}:
            if (
                instance.__previous_status != status
                and instance.status == status
            ):
                instance.owner = None
                break


for klass in NODE_CLASSES:
    signals.watch(
        pre_save, clear_owner_when_status_changes_to_new_or_ready, sender=klass
    )


def clear_nodekey_when_owner_changes(node, old_values, deleted=False):
    """Erase related `NodeKey` when node ownership changes."""
    assert not deleted, (
        "clear_nodekey_when_owner_changes is not prepared "
        "to deal with deletion of nodes."
    )

    owner_id_old = old_values[0]
    owner_id_new = node.owner_id

    if owner_id_new != owner_id_old:
        NodeKey.objects.clear_token_for_node(node)


for klass in NODE_CLASSES:
    signals.watch_fields(
        clear_nodekey_when_owner_changes, klass, ["owner_id"], delete=False
    )


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
        create_services_on_node_type_change, klass, ["node_type"], delete=False
    )
    signals.watch(post_save, create_services_on_create, sender=klass)


def create_default_related_entries_on_create(
    sender, instance, created, **kwargs
):
    """Create default related entries for a node."""
    if not created:
        return

    if not instance.is_device:
        create_default_numanode(instance)
    create_default_nodeconfig(instance)


for sender in (Device, Machine, Node, RackController, RegionController):
    signals.watch(
        post_save, create_default_related_entries_on_create, sender=sender
    )


def release_auto_ips(node, old_values, deleted=False):
    """Release auto assigned IPs once the machine is off and ready."""
    # Only machines use AUTO_IPs.
    if not node.is_machine:
        return
    # Commissioning and testing may acquire an AUTO_IP for network testing.
    # Users may keep the machine on after commissioning/testing to debug
    # issues where the assigned IP is still in use. Wait till the machine
    # is off and not in a status which will have an IP in use.
    if node.power_state == POWER_STATE.OFF and node.status not in (
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.DEPLOYED,
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.RESCUE_MODE,
        NODE_STATUS.ENTERING_RESCUE_MODE,
        NODE_STATUS.TESTING,
    ):
        node.release_interface_config()


for klass in [Node, Machine]:
    signals.watch_fields(release_auto_ips, klass, ["power_state"])


# Enable all signals by default.
signals.enable()
