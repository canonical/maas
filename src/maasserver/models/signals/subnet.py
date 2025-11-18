# Copyright 2019-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to Subnet CIDR changes."""

from django.db.models.signals import post_delete, post_save

from maascommon.enums.dns import DnsUpdateAction
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
from maasserver.enum import IPADDRESS_TYPE, RDNS_MODE
from maasserver.models import DNSPublication, StaticIPAddress, Subnet, VLAN
from maasserver.utils.orm import post_commit_do
from maasserver.utils.signals import SignalsManager
from maasserver.workflow import start_workflow
from maastemporalworker.worker import REGION_TASK_QUEUE

signals = SignalsManager()


def update_referenced_ip_addresses(subnet):
    """Updates the `StaticIPAddress`'s to ensure that they are linked to the
    correct subnet."""

    # Remove the IP addresses that no longer fall with in the CIDR.
    remove_ips = StaticIPAddress.objects.filter(
        alloc_type=IPADDRESS_TYPE.USER_RESERVED, subnet_id=subnet.id
    )
    remove_ips = remove_ips.extra(
        where=["NOT(ip << %s)"], params=[subnet.cidr]
    )
    remove_ips.update(subnet=None)

    # Add the IP addresses that now fall into CIDR.
    add_ips = StaticIPAddress.objects.filter(subnet__isnull=True)
    add_ips = add_ips.extra(where=["ip << %s"], params=[subnet.cidr])
    add_ips.update(subnet_id=subnet.id)


def post_created_dns_publication(sender, instance, created, **kwargs):
    if created:
        update_referenced_ip_addresses(instance)

        if instance.rdns_mode != RDNS_MODE.DISABLED:
            DNSPublication.objects.create_for_config_update(
                source=f"added subnet {instance.cidr}",
                action=DnsUpdateAction.RELOAD,
            )


def post_create_dhcp_workflow(sender, instance, created, **kwargs):
    if created:
        # If DHCP is enabled on the subnet's VLAN, trigger a DHCP configuration update.
        vlan = instance.vlan
        if vlan.dhcp_on or vlan.relay_vlan_id:
            param = ConfigureDHCPParam(vlan_ids=[vlan.id])
            post_commit_do(
                start_workflow,
                workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
                param=param,
                task_queue=REGION_TASK_QUEUE,
            )


def post_delete_dns_publication(sender, instance, **kwargs):
    if instance.rdns_mode != RDNS_MODE.DISABLED:
        DNSPublication.objects.create_for_config_update(
            source=f"removed subnet {instance.cidr}",
            action=DnsUpdateAction.RELOAD,
        )


def post_delete_dhcp_workflow(sender, instance, **kwargs):
    if instance.vlan.dhcp_on or instance.vlan.relay_vlan_id:
        param = ConfigureDHCPParam(vlan_ids=[instance.vlan.id])
        post_commit_do(
            start_workflow,
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=param,
            task_queue=REGION_TASK_QUEUE,
        )


def updated_cidr(instance, old_values, **kwargs):
    update_referenced_ip_addresses(instance)


def emit_dnspublication_on_change(instance, old_values, **kwargs):
    [old_cidr, old_rdns_mode, old_allow_dns] = old_values

    changes = []

    if old_cidr != instance.cidr:
        changes.append(f"cidr changed to {instance.cidr}")
    if old_rdns_mode != instance.rdns_mode:
        changes.append(f"rdns changed to {instance.cidr}")
    if old_allow_dns != instance.allow_dns:
        changes.append(f"allow_dns changed to {instance.allow_dns}")
    if changes:
        DNSPublication.objects.create_for_config_update(
            source=f"subnet {instance.cidr} changes: {', '.join(changes)}",
            action=DnsUpdateAction.RELOAD,
        )


def update_dhcp(instance, old_values, **kwargs):
    [old_vlan_id] = old_values

    old_vlan = None
    if old_vlan_id:
        old_vlan = VLAN.objects.get(id=old_vlan_id)

    vlans_to_update = set()

    if old_vlan and (old_vlan.dhcp_on or old_vlan.relay_vlan_id):
        vlans_to_update.add(old_vlan_id)
    if instance.vlan.dhcp_on or instance.vlan.relay_vlan_id:
        vlans_to_update.add(instance.vlan.id)

    if vlans_to_update:
        param = ConfigureDHCPParam(vlan_ids=list(vlans_to_update))
        post_commit_do(
            start_workflow,
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=param,
            task_queue=REGION_TASK_QUEUE,
        )


signals.watch(post_save, post_created_dns_publication, sender=Subnet)
signals.watch(post_save, post_create_dhcp_workflow, sender=Subnet)
signals.watch(post_delete, post_delete_dns_publication, sender=Subnet)
signals.watch(post_delete, post_delete_dhcp_workflow, sender=Subnet)
signals.watch_fields(updated_cidr, Subnet, ["cidr"], delete=False)
signals.watch_fields(
    emit_dnspublication_on_change,
    Subnet,
    ["cidr", "rdns_mode", "allow_dns"],
    delete=False,
)
signals.watch_fields(
    update_dhcp,
    Subnet,
    ["vlan_id"],
    delete=False,
)

# Enable all signals by default.
signals.enable()
