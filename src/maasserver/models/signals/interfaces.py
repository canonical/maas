# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to interface changes."""

__all__ = []

from maasserver.enum import (
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
)
from maasserver.models import (
    BondInterface,
    Interface,
    PhysicalInterface,
    VLANInterface,
)
from maasserver.utils.signals import connect_to_field_change


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


connect_to_field_change(
    interface_enabled_or_disabled,
    Interface, ['enabled'], delete=False)
connect_to_field_change(
    interface_enabled_or_disabled,
    PhysicalInterface, ['enabled'], delete=False)


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


connect_to_field_change(
    interface_mtu_params_update,
    Interface, ['params'], delete=False)
connect_to_field_change(
    interface_mtu_params_update,
    PhysicalInterface, ['params'], delete=False)
connect_to_field_change(
    interface_mtu_params_update,
    BondInterface, ['params'], delete=False)
connect_to_field_change(
    interface_mtu_params_update,
    VLANInterface, ['params'], delete=False)
