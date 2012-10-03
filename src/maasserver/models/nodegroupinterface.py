# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for NodeGroupInterface."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'NodeGroupInterface',
    ]


from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    ForeignKey,
    GenericIPAddressField,
    IntegerField,
    )
from maasserver import DefaultMeta
from maasserver.enum import (
    NODEGROUPINTERFACE_MANAGEMENT,
    NODEGROUPINTERFACE_MANAGEMENT_CHOICES,
    )
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from netaddr import (
    IPAddress,
    IPNetwork,
    )


class NodeGroupInterface(CleanSave, TimestampedModel):

    class Meta(DefaultMeta):
        unique_together = ('nodegroup', 'interface')

    # Static IP of the interface.
    ip = GenericIPAddressField(null=False, editable=True)

    # The `NodeGroup` this interface belongs to.
    nodegroup = ForeignKey(
        'maasserver.NodeGroup', editable=True, null=False, blank=False)

    management = IntegerField(
        choices=NODEGROUPINTERFACE_MANAGEMENT_CHOICES, editable=True,
        default=NODEGROUPINTERFACE_MANAGEMENT.DEFAULT)

    # DHCP server settings.
    interface = CharField(
        blank=True, editable=True, max_length=255, default='')
    subnet_mask = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    broadcast_ip = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    router_ip = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    ip_range_low = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)
    ip_range_high = GenericIPAddressField(
        editable=True, unique=False, blank=True, null=True, default=None)

    @property
    def network(self):
        """Return the network defined by the broadcast address and net mask.

        If either the broadcast address or the subnet mask is unset, returns
        None.

        :return: :class:`IPNetwork`
        """
        if self.broadcast_ip and self.subnet_mask:
            return IPNetwork("%s/%s" % (self.broadcast_ip, self.subnet_mask))
        return None

    def __repr__(self):
        return "<NodeGroupInterface %r,%s>" % (self.nodegroup, self.interface)

    def clean_network(self):
        """Ensure that the network settings are all congruent.

        Specifically, it ensures that the interface address, router address,
        and the address range, all fall within the network defined by the
        broadcast address and subnet mask.
        """
        network = self.network
        if network is None:
            return
        network_settings = (
            ("ip", self.ip),
            ("router_ip", self.router_ip),
            ("ip_range_low", self.ip_range_low),
            ("ip_range_high", self.ip_range_high),
            )
        network_errors = defaultdict(list)
        for field, address in network_settings:
            if address and IPAddress(address) not in network:
                network_errors[field].append(
                    "%s not in the %s network" % (address, network))
        if len(network_errors) != 0:
            raise ValidationError(network_errors)

    def clean(self, *args, **kwargs):
        super(NodeGroupInterface, self).clean(*args, **kwargs)
        self.clean_network()
