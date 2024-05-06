# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to interface changes."""


from django.db.models import Count
from django.db.models.signals import m2m_changed, post_save, pre_delete

from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE
from maasserver.models import (
    BondInterface,
    BridgeInterface,
    Config,
    Controller,
    Fabric,
    Interface,
    NodeConfig,
    PhysicalInterface,
    StaticIPAddress,
    UnknownInterface,
    VLAN,
    VLANInterface,
)
from maasserver.models.interface import InterfaceVisitingThreadLocal
from maasserver.utils.signals import SignalsManager
from provisioningserver.logger import LegacyLogger

INTERFACE_CLASSES = [
    BondInterface,
    BridgeInterface,
    Interface,
    PhysicalInterface,
    UnknownInterface,
    VLANInterface,
]

signals = SignalsManager()

log = LegacyLogger()


enabled_or_disabled_thread_local = InterfaceVisitingThreadLocal()


def ensure_link_up(interface):
    visiting = enabled_or_disabled_thread_local.visiting
    if interface.id not in visiting:
        try:
            visiting.add(interface.id)
            interface.ensure_link_up()
        finally:
            visiting.discard(interface.id)


def interface_enabled_or_disabled(instance, old_values, **kwargs):
    """When an interface is enabled be sure at minimum a LINK_UP is created.
    When an interface is disabled make sure that all its links are removed,
    even for all its children that are now disabled."""
    if instance.type != INTERFACE_TYPE.PHYSICAL:
        return
    if instance.is_enabled():
        log.msg(
            "%s: Physical interface enabled; ensuring link-up."
            % (instance.get_log_string())
        )
        # Make sure it has a LINK_UP link, and for its children.
        ensure_link_up(instance)
        for rel in instance.children_relationships.all():
            ensure_link_up(rel.child)

    else:
        log.msg(
            "%s: Physical interface disabled; removing links."
            % (instance.get_log_string())
        )
        # Was disabled. Remove the links.
        for ip_address in instance.ip_addresses.exclude(
            alloc_type=IPADDRESS_TYPE.DISCOVERED
        ):
            instance.unlink_ip_address(ip_address, clearing_config=True)
        # If any of the children of this interface are now disabled, all of
        # their links need to be removed as well.
        for rel in instance.children_relationships.all():
            if not rel.child.is_enabled():
                for ip_address in rel.child.ip_addresses.all():
                    rel.child.unlink_ip_address(
                        ip_address, clearing_config=True
                    )


for klass in INTERFACE_CLASSES:
    signals.watch_fields(
        interface_enabled_or_disabled, klass, ["enabled"], delete=False
    )


def _update_mtu(interface, mtu, instance):
    log.msg(
        "%s: MTU updated to %d (for consistency with %s)."
        % (interface.get_log_string(), mtu, instance.get_log_string())
    )
    params = interface.params.copy()
    params["mtu"] = mtu
    interface.params = params
    interface.save()


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

    # If the children have a larger MTU than the parent, we update the child's
    # MTU to be the same size as the parents. If the child doesn't have MTU
    # set then it is ignored.
    for rel in instance.children_relationships.all():
        child = rel.child
        if child.params and "mtu" in child.params:
            child_mtu = child.params["mtu"]
            if child_mtu > new_mtu:
                _update_mtu(child, new_mtu, instance)

    # Update the parents MTU to either be the same size of the child's MTU or
    # larger than the child's MTU.
    for parent in instance.parents.all():
        if parent.params:
            parent_mtu = parent.params.get("mtu", None)
            if parent_mtu is not None:
                if parent_mtu < new_mtu:
                    # Parent MTU is to small, make it bigger for the
                    # child interface.
                    _update_mtu(parent, new_mtu, instance)
            else:
                # Parent doesn't have MTU set. Set it to the child's
                # MTU value.
                _update_mtu(parent, new_mtu, instance)
        else:
            # Parent has not parameters at all. Create the parameters
            # object and set the MTU to the size of the child.
            parent.params = {}
            _update_mtu(parent, new_mtu, instance)


for klass in INTERFACE_CLASSES:
    signals.watch_fields(
        interface_mtu_params_update, klass, ["params"], delete=False
    )


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
    if instance.node_config is None:
        # Not assigned to a node. Nothing to do.
        return

    new_vlan = instance.vlan
    node = instance.node_config.node
    if node.is_controller:
        if old_vlan_id is None:
            return
        # Interface VLAN was changed on a controller. Move all linked subnets
        # to that new VLAN, unless the new VLAN is None. When the VLAN is
        # None then the administrator is say that the interface is now
        # disconnected.
        if new_vlan is not None:
            for ip_address in instance.ip_addresses.all():
                if ip_address.subnet is not None:
                    ip_address.subnet.vlan = new_vlan
                    ip_address.subnet.save()
                    log.msg(
                        "%s: IP address [%s] subnet %s: "
                        "VLAN updated (vlan=%s)."
                        % (
                            instance.get_log_string(),
                            ip_address.ip,
                            ip_address.subnet.cidr,
                            ip_address.subnet.vlan_id,
                        )
                    )
            # If any children are VLAN interfaces then we need to move those
            # VLANs into the same fabric as the parent.
            for rel in instance.children_relationships.all():
                if rel.child.type == INTERFACE_TYPE.VLAN:
                    new_child_vlan, _ = VLAN.objects.get_or_create(
                        fabric=new_vlan.fabric, vid=rel.child.vlan.vid
                    )
                    rel.child.vlan = new_child_vlan
                    rel.child.save()
                    # No need to update the IP addresses here this function
                    # will be called again because the child has been saved.
                    log.msg(
                        "%s: updated fabric on %s to %s (vlan=%s)"
                        % (
                            instance.get_log_string(),
                            rel.child.get_log_string(),
                            new_vlan.fabric.name,
                            rel.child.vlan_id,
                        )
                    )
    else:
        # Interface VLAN was changed on a machine or device. Remove all its
        # links except the DISCOVERED ones.
        instance.ip_addresses.exclude(
            alloc_type=IPADDRESS_TYPE.DISCOVERED
        ).delete()
        if old_vlan_id is not None:
            # Don't bother logging if the VLAN was previously NULL, since there
            # shouldn't be any IP addresses on the interface, anyway. (But keep
            # the above database cleanup, just in case of the unexpected.)
            log.msg(
                "%s: deleted IP addresses due to VLAN update (%s -> %s)."
                % (instance.get_log_string(), old_vlan_id, new_vlan_id)
            )

    if old_vlan_id not in (None, new_vlan_id):
        # XXX if the interface was previously attached to a fabric with no
        # subnets nor interfaces on its VLAN, delete the fabric. This happens
        # for instance when a new interface without links is created, in which
        # case it's place on its own fabric. If the VLAN gets updated earlier
        # here, the old fabric/VLAN are left empty.
        Fabric.objects.annotate(
            subnet_count=Count("vlan__subnet"),
            iface_count=Count("vlan__interface"),
        ).filter(subnet_count=0, iface_count=0, vlan__id=old_vlan_id).delete()


for klass in INTERFACE_CLASSES:
    signals.watch_fields(
        interface_vlan_update, klass, ["vlan_id"], delete=False
    )


def delete_children_interface_handler(sender, instance, **kwargs):
    """Remove children interface that no longer have a parent when the
    parent gets removed."""
    for rel in instance.children_relationships.all():
        # Use cached QuerySet instead of `count()`.
        if len(rel.child.parents.all()) == 1:
            # Last parent of the child, so delete the child.
            rel.child.delete()
            log.msg(
                "%s has been deleted; orphaned by %s."
                % (rel.child.get_log_string(), instance.get_log_string())
            )


for klass in INTERFACE_CLASSES:
    signals.watch(pre_delete, delete_children_interface_handler, klass)


def delete_related_ip_addresses(sender, instance, **kwargs):
    """Remove any related IP addresses that no longer will have any interfaces
    linked to them."""
    # Skip the removal if requested when the interface was deleted.
    should_skip = (
        hasattr(instance, "_skip_ip_address_removal")
        and instance._skip_ip_address_removal
    )
    if should_skip:
        return

    # Delete all linked IP addresses that only have one link
    StaticIPAddress.objects.annotate(
        interface_count=Count("interface")
    ).filter(
        id__in=instance.ip_addresses.all().values("id"), interface_count__lte=1
    ).delete()


for klass in INTERFACE_CLASSES:
    signals.watch(pre_delete, delete_related_ip_addresses, klass)


def resave_children_interface_handler(sender, instance, **kwargs):
    """Re-save all of the children interfaces to update their information."""
    for rel in instance.children_relationships.all():
        rel.child.save()


for klass in INTERFACE_CLASSES:
    signals.watch(post_save, resave_children_interface_handler, klass)


def remove_gateway_link_when_ip_address_removed_from_interface(
    sender, instance, action, model, pk_set, **kwargs
):
    """When an IP address is removed from an interface it is possible that
    the IP address was not deleted just moved. In that case we need to removed
    the gateway links on the node model."""
    if model == StaticIPAddress and action == "post_remove":
        try:
            node_config = instance.node_config
        except NodeConfig.DoesNotExist:
            return
        if node_config is not None:
            node = node_config.node
            for pk in pk_set:
                if node.gateway_link_ipv4_id == pk:
                    node.gateway_link_ipv4_id = None
                    node.save(update_fields=["gateway_link_ipv4_id"])
                if node.gateway_link_ipv6_id == pk:
                    node.gateway_link_ipv6_id = None
                    node.save(update_fields=["gateway_link_ipv6_id"])


def update_interface_monitoring(sender, instance, *args, **kwargs):
    """Updates the global state of interface monitoring."""
    # This is not really ideal, since we don't actually know if any of these
    # configuration options actually changed. Also, this function may be called
    # more than once (for each global setting) when the form is submitted, no
    # matter if anything changed or not. (But a little repitition for the sake
    # of simpler code is a good tradeoff for now, given that there will be a
    # relatively small number of Controller interfaces.
    discovery_config = Config.objects.get_network_discovery_config_from_value(
        instance.value
    )
    # We only care about Controller objects, since only Controllers run the
    # networks monitoring service.
    for controller in Controller.objects.all():
        controller.update_discovery_state(discovery_config)


signals.watch(
    m2m_changed,
    remove_gateway_link_when_ip_address_removed_from_interface,
    Interface.ip_addresses.through,
)

signals.watch_config(update_interface_monitoring, "network_discovery")

# Enable all signals by default.
signals.enable()
