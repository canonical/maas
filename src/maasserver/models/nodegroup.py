# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for NodeGroup which models a collection of Nodes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'NodeGroup',
    'NODEGROUP_CLUSTER_NAME_TEMPLATE',
    ]

from apiclient.creds import convert_tuple_to_string
from crochet import TimeoutError
from django.db.models import (
    BooleanField,
    CharField,
    IntegerField,
    Manager,
    OneToOneField,
)
from maasserver import DefaultMeta
from maasserver.clusterrpc.boot_images import (
    get_boot_images,
    is_import_boot_images_running_for,
)
from maasserver.enum import (
    NODEGROUP_STATE,
    NODEGROUP_STATUS,
    NODEGROUP_STATUS_CHOICES,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.fields import DomainNameField
from maasserver.models.bootresource import BootResource
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.models.user import get_creds_tuple
from maasserver.rpc import getClientFor
from maasserver.utils.django import has_builtin_migrations
from provisioningserver.dhcp.omshell import generate_omapi_key
from provisioningserver.rpc.cluster import (
    AddSeaMicro15k,
    AddVirsh,
    AddVMware,
    EnlistNodesFromMicrosoftOCS,
    EnlistNodesFromMSCM,
    EnlistNodesFromUCSM,
)
from provisioningserver.rpc.exceptions import NoConnectionsAvailable

# To support upgrading from MAAS versions <2.0 the piston module was named
# 'piston' not 'piston3'. Even though 'piston' and 'piston3' module are the
# same the import names are important because it will break south migrations
# unless piston is imported as 'piston'.
if has_builtin_migrations():
    from piston3.models import (
        KEY_SIZE,
        Token,
    )
else:
    from piston.models import (
        KEY_SIZE,
        Token,
    )


class NodeGroupManager(Manager):
    """Manager for the NodeGroup class.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """

    def new(self, name, uuid, dhcp_key='',
            status=NODEGROUP_STATUS.DEFAULT, cluster_name=None, maas_url='',
            default_disable_ipv4=False):
        """Create a :class:`NodeGroup` with the given parameters.

        Also generates API credentials for the nodegroup's worker to use.
        """
        if cluster_name is None:
            cluster_name = NODEGROUP_CLUSTER_NAME_TEMPLATE % {'uuid': uuid}
        nodegroup = NodeGroup(
            name=name, uuid=uuid, cluster_name=cluster_name, dhcp_key=dhcp_key,
            status=status, maas_url=maas_url,
            default_disable_ipv4=default_disable_ipv4)
        nodegroup.save()
        return nodegroup

    def ensure_master(self):
        """Obtain the master node group, creating it first if needed."""
        # Avoid circular imports.
        from maasserver.models import Node
        from maasserver.forms import DEFAULT_DNS_ZONE_NAME

        try:
            # Get the first created nodegroup if it exists.
            master = self.all().order_by('id')[0:1].get()
        except NodeGroup.DoesNotExist:
            # The master did not exist yet; create it on demand.
            master = self.new(
                DEFAULT_DNS_ZONE_NAME, 'master',
                dhcp_key=generate_omapi_key(),
                status=NODEGROUP_STATUS.ENABLED)

            # If any legacy nodes were still not associated with a node
            # group, enroll them in the master node group.
            Node.objects.filter(nodegroup=None).update(nodegroup=master)

        return master

    def get_by_natural_key(self, uuid):
        """For Django, a node group's uuid is a natural key."""
        return self.get(uuid=uuid)

    def _mass_change_status(self, old_status, new_status):
        nodegroups = self.filter(status=old_status)
        nodegroups_count = nodegroups.count()
        # Change the nodegroups one by one in order to trigger the
        # post_save signals.
        for nodegroup in nodegroups:
            nodegroup.status = new_status
            nodegroup.save()
        return nodegroups_count

    def all_accepted(self):
        """Return the set of all accepted node-groups."""
        return self.filter(status=NODEGROUP_STATUS.ENABLED)

    def get_dhcp_managed_nodegroups(self, fabric=None):
        """Returns the DHCP-managed clusters relevant to the specified fabric.

        :param fabric: The fabric whose DHCP-managed clusters to update.
        """
        if fabric is not None:
            raise NotImplementedError("Fabrics are not yet supported.")
        return [
            nodegroup
            for nodegroup in NodeGroup.objects.all()
            if nodegroup.manages_dhcp()
            ]


NODEGROUP_CLUSTER_NAME_TEMPLATE = "Cluster %(uuid)s"


class NodeGroup(TimestampedModel):

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = NodeGroupManager()

    cluster_name = CharField(
        max_length=100, unique=True, editable=True, blank=True, null=False)

    # A node group's name is also used for the group's DNS zone.
    name = DomainNameField(
        max_length=80, unique=False, editable=True, blank=True, null=False)

    status = IntegerField(
        choices=NODEGROUP_STATUS_CHOICES, editable=True,
        default=NODEGROUP_STATUS.DEFAULT)

    # Credentials for the worker to access the API with.
    api_token = OneToOneField(Token, null=False, editable=False, unique=True)
    api_key = CharField(
        max_length=KEY_SIZE, null=False, blank=False, editable=False,
        unique=True)

    dhcp_key = CharField(
        blank=True, editable=False, max_length=255, default='')

    # Unique identifier of the worker.
    uuid = CharField(
        max_length=36, unique=True, null=False, blank=False, editable=True)

    # The URL where the cluster controller can access the region
    # controller.
    maas_url = CharField(
        blank=True, editable=False, max_length=255, default='')

    # Should nodes on this cluster be configured to disable IPv4 on deployment
    # by default?
    default_disable_ipv4 = BooleanField(
        default=False,
        verbose_name="Disable IPv4 by default when deploying nodes",
        help_text=(
            "Default setting for new nodes: disable IPv4 when deploying, on "
            "operating systems where this is supported."))

    @property
    def api_credentials(self):
        """Return a string containing credentials for this nodegroup."""
        return convert_tuple_to_string(get_creds_tuple(self.api_token))

    def __repr__(self):
        return "<NodeGroup %s>" % self.uuid

    def accept(self):
        """Accept this nodegroup's enlistment."""
        self.status = NODEGROUP_STATUS.ENABLED
        self.save()

    def reject(self):
        """Reject this nodegroup's enlistment."""
        self.status = NODEGROUP_STATUS.DISABLED
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

    def get_managed_interfaces(self):
        """Return the list of interfaces for which MAAS manages DHCP."""
        # Filter in python instead of in SQL.  This will use the cached
        # version of self.nodegroupinterface_set if present.
        return [
            itf
            for itf in self.nodegroupinterface_set.all()
            if itf.management != NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
            ]

    def get_fabric(self):
        """The Fabric this cluster belongs to."""
        for ngi in self.get_managed_interfaces():
            return ngi.vlan.fabric
        return None

    def manages_dns(self):
        """Does this `NodeGroup` manage DNS on any interfaces?

        This returns `True` when the `NodeGroup` is accepted, and has a
        `NodeGroupInterface` that's set to manage both DHCP and DNS.
        """
        if self.status != NODEGROUP_STATUS.ENABLED:
            return False
        # Filter in python instead of in SQL.  This will use the cached
        # version of self.nodegroupinterface_set if present.
        for itf in self.nodegroupinterface_set.all():
            if itf.management == NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS:
                return True
        return False

    def manages_dhcp(self):
        """Does this `NodeGroup` manages a DHCP server?

        This returns `True` when the `NodeGroup` is accepted, and has a
        `NodeGroupInterface` that's set to manage DHCP.
        """
        if self.status != NODEGROUP_STATUS.ENABLED:
            return False
        # Filter in python instead of in SQL.  This will use the cached
        # version of self.nodegroupinterface_set if present.
        for itf in self.nodegroupinterface_set.all():
            if itf.management != NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED:
                return True
        return False

    def ensure_dhcp_key(self):
        """Ensure that this nodegroup has a dhcp key.

        This method persists the dhcp key without triggering the model
        signals (pre_save/post_save/etc) because it's called from
        dhcp.configure_dhcp which, in turn, it called from the post_save
        signal of NodeGroup."""
        if self.dhcp_key == '':
            dhcp_key = generate_omapi_key()
            self.dhcp_key = dhcp_key
            # Persist the dhcp_key without triggering the signals.
            NodeGroup.objects.filter(id=self.id).update(dhcp_key=dhcp_key)

    def is_connected(self):
        """Is this cluster connected to his provisioning server?"""
        try:
            # Use a timeout of zero not to block.
            getClientFor(self.uuid, timeout=0)
        except NoConnectionsAvailable:
            return False
        else:
            return True

    def get_state(self):
        """Get the current state of the cluster.

        This returns information about if the cluster is connected,
        out-of-sync, syncing, synced.
        """
        try:
            images = get_boot_images(self)
        except (NoConnectionsAvailable, TimeoutError):
            return NODEGROUP_STATE.DISCONNECTED
        if not BootResource.objects.boot_images_are_in_sync(images):
            try:
                importing = is_import_boot_images_running_for(self)
            except (NoConnectionsAvailable, TimeoutError):
                return NODEGROUP_STATE.DISCONNECTED
            if not importing:
                return NODEGROUP_STATE.OUT_OF_SYNC
            return NODEGROUP_STATE.SYNCING
        return NODEGROUP_STATE.SYNCED

    @property
    def work_queue(self):
        """The name of the queue for tasks specific to this nodegroup."""
        return self.uuid

    def add_seamicro15k(self, user, mac, username, password,
                        power_control=None, accept_all=False):
        """ Add all of the specified cards the Seamicro SM15000 chassis at the
        specified MAC.

        :param user: user for the nodes.
        :param mac: MAC address of the card.
        :param username: username for power controller.
        :param password: password for power controller.
        :param power_control: optional specify the power control method,
            either ipmi (default), restapi, or restapi2.
        :param accept_all: commission enlisted nodes.

        :raises NoConnectionsAvailable: If no connections to the cluster
            are available.
        """
        try:
            client = getClientFor(self.uuid, timeout=1)
        except NoConnectionsAvailable:
            # No connection to the cluster so we can't do anything. We
            # let the caller handle the error, since we don't want to
            # just drop it.
            raise
        else:
            return client(
                AddSeaMicro15k, user=user, mac=mac, username=username,
                password=password, power_control=power_control,
                accept_all=accept_all)

    def add_virsh(self, user, poweraddr, password=None,
                  prefix_filter=None, accept_all=False):
        """ Add all of the virtual machines inside a virsh controller.

        :param user: user for the nodes.
        :param poweraddr: virsh connection string.
        :param password: ssh password.
        :param prefix_filter: imports virsh domains filtered by this prefix.
        :param accept_all: commission enlisted nodes.

        :raises NoConnectionsAvailable: If no connections to the cluster
            are available.
        """
        try:
            client = getClientFor(self.uuid, timeout=1)
        except NoConnectionsAvailable:
            # No connection to the cluster so we can't do anything. We
            # let the caller handle the error, since we don't want to
            # just drop it.
            raise
        else:
            return client(
                AddVirsh, user=user, poweraddr=poweraddr, password=password,
                prefix_filter=prefix_filter, accept_all=accept_all)

    def add_vmware(self, user, host, username, password, protocol=None,
                   port=None, prefix_filter=None, accept_all=False):
        """ Add virtual machines managed by vSphere, ESX, or ESXi, or other
        VMware products which support the VMware API.

        :param user: MAAS user (for commissioning)
        :param host: VMware hostname.
        :param username: VMware API username.
        :param password: VMware API password.
        :param prefix_filter: imports VMs with names filtered by this prefix.
        :param accept_all: commission enlisted nodes.

        :raises NoConnectionsAvailable: If no connections to the cluster
            are available.
        """
        try:
            client = getClientFor(self.uuid, timeout=1)
        except NoConnectionsAvailable:
            # No connection to the cluster so we can't do anything. We
            # let the caller handle the error, since we don't want to
            # just drop it.
            raise
        else:
            return client(
                AddVMware, user=user, host=host, username=username,
                password=password, protocol=protocol, port=port,
                prefix_filter=prefix_filter, accept_all=accept_all)

    def enlist_nodes_from_ucsm(self, user, url, username,
                               password, accept_all=False):
        """ Add the servers from a Cicso UCS Manager.

        :param user: user for the nodes.
        :param URL: URL of the Cisco UCS Manager HTTP-XML API.
        :param username: username for UCS Manager.
        :param password: password for UCS Manager.
        :param accept_all: commission enlisted nodes.

        :raises NoConnectionsAvailable: If no connections to the cluster
            are available.
        """
        try:
            client = getClientFor(self.uuid, timeout=1)
        except NoConnectionsAvailable:
            # No connection to the cluster so we can't do anything. We
            # let the caller handle the error, since we don't want to
            # just drop it.
            raise
        else:
            return client(
                EnlistNodesFromUCSM, user=user, url=url,
                username=username, password=password, accept_all=accept_all)

    def enlist_nodes_from_mscm(self, user, host, username,
                               password, accept_all=False):
        """ Add the servers from a Moonshot HP iLO Chassis Manager.

        :param user: user for the nodes.
        :param host: IP address for the MSCM.
        :param username: username for MSCM.
        :param password: password for MSCM.
        :param accept_all: commission enlisted nodes.

        :raises NoConnectionsAvailable: If no connections to the cluster
            are available.
        """
        try:
            client = getClientFor(self.uuid, timeout=1)
        except NoConnectionsAvailable:
            # No connection to the cluster so we can't do anything. We
            # let the caller handle the error, since we don't want to
            # just drop it.
            raise
        else:
            return client(
                EnlistNodesFromMSCM, user=user, host=host,
                username=username, password=password, accept_all=accept_all)

    def enlist_nodes_from_msftocs(
            self, user, ip, port, username, password, accept_all=False):
        """Add the servers from a Microsoft OCS Chassis Manager.

        :param user: MAAS user for the nodes.
        :param ip: IP address for the MicrosoftOCS.
        :param port: Port for the MicrosoftOCS.
        :param username: username for MicrosoftOCS.
        :param password: password for MicrosoftOCS.
        :param accept_all: commission enlisted nodes.

        :raises NoConnectionsAvailable: If no connections to the cluster
            are available.
        """
        try:
            client = getClientFor(self.uuid, timeout=1)
        except NoConnectionsAvailable:
            # No connection to the cluster so we can't do anything. We
            # let the caller handle the error, since we don't want to
            # just drop it.
            raise
        else:
            return client(
                EnlistNodesFromMicrosoftOCS, user=user, ip=ip, port=port,
                username=username, password=password, accept_all=accept_all)
