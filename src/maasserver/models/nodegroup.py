# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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


from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
    )
from maasserver import DefaultMeta
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUP_STATUS_CHOICES,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.models.bootsource import BootSource
from maasserver.models.bootsourceselection import BootSourceSelection
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.refresh_worker import refresh_worker
from piston.models import (
    KEY_SIZE,
    Token,
    )
from provisioningserver.omshell import generate_omapi_key
from provisioningserver.tasks import (
    add_seamicro15k,
    add_virsh,
    enlist_nodes_from_ucsm,
    import_boot_images,
    report_boot_images,
    )


class NodeGroupManager(Manager):
    """Manager for the NodeGroup class.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """

    def new(self, name, uuid, ip, subnet_mask=None,
            broadcast_ip=None, router_ip=None, ip_range_low=None,
            ip_range_high=None, dhcp_key='', interface='',
            status=NODEGROUP_STATUS.DEFAULT,
            management=NODEGROUPINTERFACE_MANAGEMENT.DEFAULT,
            cluster_name=None, maas_url='',
            static_ip_range_low=None, static_ip_range_high=None):
        """Create a :class:`NodeGroup` with the given parameters.

        This method will:
        - create the related NodeGroupInterface if `interface` is provided
        - generate API credentials for the nodegroup's worker to use.
        """
        dhcp_values = [
            interface,
            subnet_mask,
            router_ip,
            ip_range_low,
            ip_range_high,
            ]
        assert all(dhcp_values) or not any(dhcp_values), (
            "Provide all DHCP settings, or none at all. "
            "Only the broadcast address is optional.")

        if cluster_name is None:
            cluster_name = NODEGROUP_CLUSTER_NAME_TEMPLATE % {'uuid': uuid}
        nodegroup = NodeGroup(
            name=name, uuid=uuid, cluster_name=cluster_name, dhcp_key=dhcp_key,
            status=status, maas_url=maas_url)
        nodegroup.save()
        if interface != '':
            nginterface = NodeGroupInterface(
                nodegroup=nodegroup, ip=ip, subnet_mask=subnet_mask,
                broadcast_ip=broadcast_ip, router_ip=router_ip,
                interface=interface, ip_range_low=ip_range_low,
                ip_range_high=ip_range_high, management=management,
                static_ip_range_low=static_ip_range_low,
                static_ip_range_high=static_ip_range_high)
            nginterface.save()
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
                DEFAULT_DNS_ZONE_NAME, 'master', '127.0.0.1',
                dhcp_key=generate_omapi_key(),
                status=NODEGROUP_STATUS.ACCEPTED)

            # If any legacy nodes were still not associated with a node
            # group, enroll them in the master node group.
            Node.objects.filter(nodegroup=None).update(nodegroup=master)

        return master

    def get_by_natural_key(self, uuid):
        """For Django, a node group's uuid is a natural key."""
        return self.get(uuid=uuid)

    def refresh_workers(self):
        """Send refresh tasks to all node-group workers."""
        for nodegroup in self.filter(status=NODEGROUP_STATUS.ACCEPTED):
            refresh_worker(nodegroup)

    def _mass_change_status(self, old_status, new_status):
        nodegroups = self.filter(status=old_status)
        nodegroups_count = nodegroups.count()
        # Change the nodegroups one by one in order to trigger the
        # post_save signals.
        for nodegroup in nodegroups:
            nodegroup.status = new_status
            nodegroup.save()
        return nodegroups_count

    def reject_all_pending(self):
        """Change the status of the 'PENDING' nodegroup to 'REJECTED."""
        return self._mass_change_status(
            NODEGROUP_STATUS.PENDING, NODEGROUP_STATUS.REJECTED)

    def accept_all_pending(self):
        """Change the status of the 'PENDING' nodegroup to 'ACCEPTED."""
        return self._mass_change_status(
            NODEGROUP_STATUS.PENDING, NODEGROUP_STATUS.ACCEPTED)

    def import_boot_images_accepted_clusters(self):
        """Import the boot images on all the accepted cluster controllers."""
        accepted_nodegroups = NodeGroup.objects.filter(
            status=NODEGROUP_STATUS.ACCEPTED)
        for nodegroup in accepted_nodegroups:
            nodegroup.import_boot_images()


NODEGROUP_CLUSTER_NAME_TEMPLATE = "Cluster %(uuid)s"


class NodeGroup(TimestampedModel):

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    objects = NodeGroupManager()

    cluster_name = CharField(
        max_length=100, unique=True, editable=True, blank=True, null=False)

    # A node group's name is also used for the group's DNS zone.
    name = CharField(
        max_length=80, unique=False, editable=True, blank=True, null=False)

    status = IntegerField(
        choices=NODEGROUP_STATUS_CHOICES, editable=True,
        default=NODEGROUP_STATUS.DEFAULT)

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

    # The URL where the cluster controller can access the region
    # controller.
    maas_url = CharField(
        blank=True, editable=False, max_length=255, default='')

    def __repr__(self):
        return "<NodeGroup %s>" % self.uuid

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

    def get_managed_interfaces(self):
        """Return the list of interfaces for which MAAS manages DHCP."""
        # Filter in python instead of in SQL.  This will use the cached
        # version of self.nodegroupinterface_set if present.
        return [
            itf
            for itf in self.nodegroupinterface_set.all()
            if itf.management != NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
            ]

    def ensure_boot_source_definition(self):
        """Set default boot source if none is currently defined."""
        if not self.bootsource_set.exists():
            source = BootSource.objects.create(
                cluster=self,
                url='http://maas.ubuntu.com/images/ephemeral-v2/releases/',
                keyring_filename=(
                    '/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg'))
            # Default is to import supported Ubuntu LTS releases, for all
            # architectures, release versions only.
            for os_release in ('precise', 'trusty'):
                BootSourceSelection.objects.create(
                    boot_source=source, release=os_release,
                    arches=['*'], subarches=['*'], labels=['release'])

    def manages_dns(self):
        """Does this `NodeGroup` manage DNS on any interfaces?

        This returns `True` when the `NodeGroup` is accepted, and has a
        `NodeGroupInterface` that's set to manage both DHCP and DNS.
        """
        if self.status != NODEGROUP_STATUS.ACCEPTED:
            return False
        # Filter in python instead of in SQL.  This will use the cached
        # version of self.nodegroupinterface_set if present.
        for itf in self.nodegroupinterface_set.all():
            if itf.management == NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS:
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

    @property
    def work_queue(self):
        """The name of the queue for tasks specific to this nodegroup."""
        return self.uuid

    def import_boot_images(self):
        """Import the pxe files on this cluster controller.

        The files are downloaded through the proxy defined in the config
        setting 'http_proxy' if defined.
        """
        # Avoid circular imports.
        from maasserver.models import Config
        sources = [
            source.to_dict() for source in self.bootsource_set.all()]
        task_kwargs = {
            'callback': report_boot_images.subtask(
                options={'queue': self.uuid}),
            'sources': sources,
            }
        http_proxy = Config.objects.get_config('http_proxy')
        if http_proxy is not None:
            task_kwargs['http_proxy'] = http_proxy
        import_boot_images.apply_async(queue=self.uuid, kwargs=task_kwargs)

    def add_seamicro15k(self, mac, username, password, power_control=None):
        """ Add all of the specified cards the Seamicro SM15000 chassis at the
        specified MAC.

        :param mac: MAC address of the card.
        :param username: username for power controller
        :param password: password for power controller
        :param power_control: optional specify the power control method,
            either ipmi (default), restapi, or restapi2.
        """
        args = (mac, username, password, power_control)
        add_seamicro15k.apply_async(queue=self.uuid, args=args)

    def add_virsh(self, poweraddr, password=None):
        """ Add all of the virtual machines inside a virsh controller.

        :param poweraddr: virsh connection string
        :param password: ssh password
        """
        args = (poweraddr, password)
        add_virsh.apply_async(queue=self.uuid, args=args)

    def enlist_nodes_from_ucsm(self, url, username, password):
        """ Add the servers from a Cicso UCS Manager.

        :param URL: URL of the Cisco UCS Manager HTTP-XML API.
        :param username: username for UCS Manager.
        :param password: password for UCS Manager.
        """
        args = (url, username, password)
        enlist_nodes_from_ucsm.apply_async(queue=self.uuid, args=args)
