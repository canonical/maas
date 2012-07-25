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
    IPAddressField,
    Manager,
    )
from maasserver import DefaultMeta
from maasserver.models.timestampedmodel import TimestampedModel
from piston.models import (
    KEY_SIZE,
    Token,
    )


worker_user_name = 'maas-nodegroup-worker'


class NodeGroupManager(Manager):
    """Manager for the NodeGroup class.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """

    def new(self, name, worker_ip, subnet_mask=None, broadcast_ip=None,
            router_ip=None, ip_range_low=None, ip_range_high=None):
        """Create a :class:`NodeGroup` with the given parameters.

        This method will generate API credentials for the nodegroup's
        worker to use.
        """
        # Avoid circular imports.
        from maasserver.models.user import create_auth_token
        from maasserver.worker_user import get_worker_user

        dhcp_values = [
            subnet_mask,
            broadcast_ip,
            router_ip,
            ip_range_low,
            ip_range_high,
            ]
        assert all(dhcp_values) or not any(dhcp_values), (
            "Provide all DHCP settings, or none at all.")

        api_token = create_auth_token(get_worker_user())
        nodegroup = NodeGroup(
            name=name, worker_ip=worker_ip, subnet_mask=subnet_mask,
            broadcast_ip=broadcast_ip, router_ip=router_ip,
            ip_range_low=ip_range_low, ip_range_high=ip_range_high,
            api_token=api_token, api_key=api_token.key)
        nodegroup.save()
        return nodegroup

    def ensure_master(self):
        """Obtain the master node group, creating it first if needed."""
        try:
            return self.get(name='master')
        except NodeGroup.DoesNotExist:
            return self.new('master', '127.0.0.1')


class NodeGroup(TimestampedModel):

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = NodeGroupManager()

    # A node group's name is also used for the group's DNS zone.
    name = CharField(
        max_length=80, unique=True, editable=True, blank=False, null=False)

    # Credentials for the worker to access the API with.
    api_token = ForeignKey(Token, null=False, editable=False, unique=True)
    api_key = CharField(
        max_length=KEY_SIZE, null=False, blank=False, editable=False,
        unique=True)

    # Address of the worker.
    worker_ip = IPAddressField(null=False, editable=True, unique=True)

    # DHCP server settings.
    subnet_mask = IPAddressField(
        editable=True, unique=False, blank=True, null=True, default='')
    broadcast_ip = IPAddressField(
        editable=True, unique=False, blank=True, null=True, default='')
    router_ip = IPAddressField(
        editable=True, unique=False, blank=True, null=True, default='')
    ip_range_low = IPAddressField(
        editable=True, unique=True, blank=True, null=True, default='')
    ip_range_high = IPAddressField(
        editable=True, unique=True, blank=True, null=True, default='')
