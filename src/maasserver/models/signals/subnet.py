# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Respond to Subnet CIDR changes."""

from django.db.models.signals import post_save

from maasserver.enum import IPADDRESS_TYPE
from maasserver.models import StaticIPAddress, Subnet
from maasserver.utils.signals import SignalsManager

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


def post_created(sender, instance, created, **kwargs):
    if created:
        update_referenced_ip_addresses(instance)


def updated_cidr(instance, old_values, **kwargs):
    update_referenced_ip_addresses(instance)


signals.watch(post_save, post_created, sender=Subnet)
signals.watch_fields(updated_cidr, Subnet, ["cidr"], delete=False)

# Enable all signals by default.
signals.enable()
