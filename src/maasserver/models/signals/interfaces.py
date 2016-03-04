# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to interface changes."""

__all__ = [
    "signals",
]

from django.db.models.signals import post_save
from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_TYPE,
)
from maasserver.models import (
    BondInterface,
    Interface,
    PhysicalInterface,
    VLAN,
    VLANInterface,
)
from maasserver.utils.signals import SignalsManager


INTERFACE_CLASSES = [
    Interface,
    PhysicalInterface,
    BondInterface,
    VLANInterface,
]

signals = SignalsManager()


def interface_enabled_or_disabled(instance, old_values, **kwargs):
    """When an interface is enabled be sure at minimum a LINK_UP is created.
    When an interface is disabled make sure that all its links are removed,
    even for all its children that are now disabled."""
    if instance.type != INTERFACE_TYPE.PHYSICAL:
        return
    if instance.is_enabled():
        # Make sure it has a LINK_UP link, and for its children.
        instance.ensure_link_up()
        for rel in instance.children_relationships.all():
            rel.child.ensure_link_up()
    else:
        # Was disabled. Remove the links.
        for ip_address in instance.ip_addresses.exclude(
                alloc_type=IPADDRESS_TYPE.DISCOVERED):
            instance.unlink_ip_address(ip_address, clearing_config=True)
        # If any of the children of this interface are now disabled, all of
        # their links need to be removed as well.
        for rel in instance.children_relationships.all():
            if not rel.child.is_enabled():
                for ip_address in rel.child.ip_addresses.all():
                    rel.child.unlink_ip_address(
                        ip_address, clearing_config=True)


for klass in INTERFACE_CLASSES:
    signals.watch_fields(
        interface_enabled_or_disabled,
        klass, ['enabled'], delete=False)


def interface_mtu_params_update(instance, old_values, **kwargs):
    """When an interfaces MTU is changed we need to do two things.

        1. Update all children to use that MTU if that MTU is smaller than the
           childrens MTU.
        2. Update all parents to use the MTU if its larger than the parents
           current MTU.
    """
    new_mtu = old_mtu = None
    [old_params] = old_values
    if old_params:
        old_mtu = old_params.get("mtu", None)
    if instance.params:
        new_mtu = instance.params.get("mtu", None)
    if new_mtu is None:
        # MTU was not set in params, so nothing to do.
        return
    if old_mtu is not None and old_mtu == new_mtu:
        # MTU stayed the same nothing needs to be done.
        return

    # Update the children before the parents. Because calling update on the
    # parent will call save on all the children again.

    # If the children have a larger MTU than the parent, we update the childs
    # MTU to be the same size as the parents. If the child doesn't have MTU
    # set then it is ignored.
    for rel in instance.children_relationships.all():
        child = rel.child
        if child.params and 'mtu' in child.params:
            child_mtu = child.params['mtu']
            if child_mtu > new_mtu:
                child.params['mtu'] = new_mtu
                child.save()

    # Update the parents MTU to either be the same size of the childs MTU or
    # larger than the childs MTU.
    for parent in instance.parents.all():
        if parent.params:
            parent_mtu = parent.params.get('mtu', None)
            if parent_mtu is not None:
                if parent_mtu < new_mtu:
                    # Parent MTU is to small, make it bigger for the
                    # child interface.
                    parent.params['mtu'] = new_mtu
                    parent.save()
            else:
                # Parent doesn't have MTU set. Set it to the childs
                # MTU value.
                parent.params['mtu'] = new_mtu
                parent.save()
        else:
            # Parent has not parameters at all. Create the parameters
            # object and set the MTU to the size of the child.
            parent.params = {'mtu': new_mtu}
            parent.save()


for klass in INTERFACE_CLASSES:
    signals.watch_fields(
        interface_mtu_params_update,
        klass, ['params'], delete=False)


def update_bond_parents(sender, instance, created, **kwargs):
    """Update bond parents when interface created."""
    if instance.type == INTERFACE_TYPE.BOND:
        for parent in instance.parents.all():
            # Make sure the parent has not links as well, just to be sure.
            parent.clear_all_links(clearing_config=True)
            if parent.vlan != instance.vlan:
                parent.vlan = instance.vlan
                parent.save()


for klass in INTERFACE_CLASSES:
    signals.watch(
        post_save, update_bond_parents,
        sender=klass)


def interface_vlan_update(instance, old_values, **kwargs):
    """When an interfaces VLAN is changed we need to do the following.

        * If its a controller move all assigned subnets to the new VLAN. This
          is done because the subnets defined are discovered on the
          controller and an administrator cannot change them.
        * If its a machine or device then we need to remove all links if the
          VLAN is different.
    """
    new_vlan_id = instance.vlan_id
    [old_vlan_id] = old_values
    if new_vlan_id == old_vlan_id:
        # Nothing changed do nothing.
        return
    if instance.node is None:
        # Not assigned to a node. Nothing to do.
        return

    new_vlan = instance.vlan
    if instance.node.node_type in (
            NODE_TYPE.REGION_CONTROLLER,
            NODE_TYPE.RACK_CONTROLLER,
            NODE_TYPE.REGION_AND_RACK_CONTROLLER):
        # Interface VLAN was changed on a controller. Move all linked subnets
        # to that new VLAN.
        for ip_address in instance.ip_addresses.all():
            if ip_address.subnet is not None:
                ip_address.subnet.vlan = new_vlan
                ip_address.subnet.save()

        # If any children are VLAN interfaces then we need to move those
        # VLANs into the same fabric as the parent.
        for rel in instance.children_relationships.all():
            if rel.child.type == INTERFACE_TYPE.VLAN:
                new_child_vlan, _ = VLAN.objects.get_or_create(
                    fabric=new_vlan.fabric, vid=rel.child.vlan.vid)
                rel.child.vlan = new_child_vlan
                rel.child.save()
                # No need to update the IP addresses here this function
                # will be called again because the child has been saved.

    else:
        # Interface VLAN was changed on a machine or device. Remove all its
        # links except the DISCOVERED ones.
        instance.ip_addresses.exclude(
            alloc_type=IPADDRESS_TYPE.DISCOVERED).delete()


for klass in INTERFACE_CLASSES:
    signals.watch_fields(
        interface_vlan_update,
        klass, ['vlan_id'], delete=False)

# Enable all signals by default.
signals.enable()
