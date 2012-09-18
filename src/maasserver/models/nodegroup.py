# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for NodeGroup which models a collection of Nodes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'NodeGroup',
    ]


from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
    )
from maasserver import DefaultMeta
from maasserver.dhcp import is_dhcp_management_enabled
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUP_STATUS_CHOICES,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.refresh_worker import refresh_worker
from maasserver.server_address import get_maas_facing_server_address
from maasserver.utils.orm import get_one
from netaddr import IPAddress
from piston.models import (
    KEY_SIZE,
    Token,
    )
from provisioningserver.omshell import generate_omapi_key
from provisioningserver.tasks import (
    add_new_dhcp_host_map,
    write_dhcp_config,
    )


class NodeGroupManager(Manager):
    """Manager for the NodeGroup class.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """

    def new(self, name, uuid, ip, subnet_mask=None,
            broadcast_ip=None, router_ip=None, ip_range_low=None,
            ip_range_high=None, dhcp_key='', interface='',
            management=NODEGROUPINTERFACE_MANAGEMENT.DEFAULT):
        """Create a :class:`NodeGroup` with the given parameters.

        This method will:
        - create the related NodeGroupInterface.
        - generate API credentials for the nodegroup's worker to use.
        """
        dhcp_values = [
            interface,
            subnet_mask,
            broadcast_ip,
            router_ip,
            ip_range_low,
            ip_range_high,
            ]
        assert all(dhcp_values) or not any(dhcp_values), (
            "Provide all DHCP settings, or none at all.")

        nodegroup = NodeGroup(name=name, uuid=uuid, dhcp_key=dhcp_key)
        nodegroup.save()
        nginterface = NodeGroupInterface(
            nodegroup=nodegroup, ip=ip, subnet_mask=subnet_mask,
            broadcast_ip=broadcast_ip, router_ip=router_ip,
            interface=interface, ip_range_low=ip_range_low,
            ip_range_high=ip_range_high, management=management)
        nginterface.save()
        return nodegroup

    def ensure_master(self):
        """Obtain the master node group, creating it first if needed."""
        # Avoid circular imports.
        from maasserver.models import Node

        try:
            master = self.get(name='master')
        except NodeGroup.DoesNotExist:
            # The master did not exist yet; create it on demand.
            master = self.new(
                'master', 'master', '127.0.0.1', dhcp_key=generate_omapi_key())

            # If any legacy nodes were still not associated with a node
            # group, enroll them in the master node group.
            Node.objects.filter(nodegroup=None).update(nodegroup=master)

        return master

    def get_by_natural_key(self, uuid):
        """For Django, a node group's uuid is a natural key."""
        return self.get(uuid=uuid)

    def refresh_workers(self):
        """Send refresh tasks to all node-group workers."""
        for nodegroup in self.all():
            refresh_worker(nodegroup)


class NodeGroup(TimestampedModel):

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = NodeGroupManager()

    # A node group's name is also used for the group's DNS zone.
    name = CharField(
        max_length=80, unique=True, editable=True, blank=False, null=False)

    status = IntegerField(
        choices=NODEGROUP_STATUS_CHOICES, editable=False,
        default=NODEGROUP_STATUS.DEFAULT_STATUS)

    # Credentials for the worker to access the API with.
    api_token = ForeignKey(Token, null=False, editable=False, unique=True)
    api_key = CharField(
        max_length=KEY_SIZE, null=False, blank=False, editable=False,
        unique=True)

    dhcp_key = CharField(
        blank=True, editable=False, max_length=255, default='')

    # Unique identifier of the worker.
    uuid = CharField(
        max_length=36, unique=True, null=False, blank=False, editable=True)

    def __repr__(self):
        return "<NodeGroup %r>" % self.name

    def accept(self):
        """Accept this nodegroup's enlistment."""
        self.status = NODEGROUP_STATUS.ACCEPTED
        self.save()

    def reject(self):
        """Reject this nodegroup's enlistment."""
        self.status = NODEGROUP_STATUS.REJECTED
        self.save()

    def save(self, *args, **kwargs):
        if self.api_token_id is None:
            # Avoid circular imports.
            from maasserver.models.user import create_auth_token
            from maasserver.worker_user import get_worker_user

            api_token = create_auth_token(get_worker_user())
            self.api_token = api_token
            self.api_key = api_token.key
        return super(NodeGroup, self).save(*args, **kwargs)

    def get_managed_interface(self):
        """Return the interface for which MAAS managed the DHCP service.

        This is a temporary method that should be refactored once we add
        proper support for multiple interfaces on a nodegroup.
        """
        return get_one(
            NodeGroupInterface.objects.filter(
                nodegroup=self).exclude(
                    management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED))

    def set_up_dhcp(self):
        """Write the DHCP configuration file and restart the DHCP server."""
        # Circular imports.
        from maasserver.dns import get_dns_server_address

        # Use the server's address (which is where the central TFTP
        # server is) for the next_server setting.  We'll want to proxy
        # it on the local worker later, and then we can use
        # next_server=self.worker_ip.
        next_server = get_maas_facing_server_address()

        interface = self.get_managed_interface()
        subnet = str(
            IPAddress(interface.ip_range_low) &
            IPAddress(interface.subnet_mask))
        write_dhcp_config.delay(
            subnet=subnet, next_server=next_server, omapi_key=self.dhcp_key,
            subnet_mask=interface.subnet_mask,
            broadcast_ip=interface.broadcast_ip,
            router_ip=interface.router_ip,
            dns_servers=get_dns_server_address(),
            ip_range_low=interface.ip_range_low,
            ip_range_high=interface.ip_range_high)

    def add_dhcp_host_maps(self, new_leases):
        if self.is_dhcp_enabled() and len(new_leases) > 0:
            # XXX JeroenVermeulen 2012-08-21, bug=1039362: the DHCP
            # server is currently always local to the worker system, so
            # use 127.0.0.1 as the DHCP server address.
            add_new_dhcp_host_map.delay(
                new_leases, '127.0.0.1', self.dhcp_key)

    def is_dhcp_enabled(self):
        """Is the DHCP for this nodegroup enabled?"""
        # Once we have support for multiple managed interfaces, this
        # method will have to be improved to cope with that.
        if not is_dhcp_management_enabled():
            return False

        interface = self.get_managed_interface()
        if interface is not None:
            return True
        else:
            return False
