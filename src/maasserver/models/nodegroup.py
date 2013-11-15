# Copyright 2012 Canonical Ltd.  This software is licensed under the
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
from maasserver.models.nodegroupinterface import NodeGroupInterface
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.refresh_worker import refresh_worker
from piston.models import (
    KEY_SIZE,
    Token,
    )
from provisioningserver.omshell import generate_omapi_key
from provisioningserver.tasks import (
    add_new_dhcp_host_map,
    add_seamicro15k,
    import_boot_images,
    )


class NodeGroupManager(Manager):
    """Manager for the NodeGroup class.

    Don't import or instantiate this directly; access as `<Class>.objects` on
    the model class it manages.
    """

    def new(self, name, uuid, ip, subnet_mask=None,
            broadcast_ip=None, router_ip=None, ip_range_low=None,
            ip_range_high=None, dhcp_key='', interface='',
            status=NODEGROUP_STATUS.DEFAULT_STATUS,
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

        cluster_name = NODEGROUP_CLUSTER_NAME_TEMPLATE % {'uuid': uuid}
        nodegroup = NodeGroup(
            name=name, uuid=uuid, cluster_name=cluster_name, dhcp_key=dhcp_key,
            status=status)
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
            # Get the first created nodegroup if it exists.
            master = self.all().order_by('id')[0:1].get()
        except NodeGroup.DoesNotExist:
            # The master did not exist yet; create it on demand.
            master = self.new(
                'master', 'master', '127.0.0.1', dhcp_key=generate_omapi_key(),
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

    def get_any_interface(self):
        for interface in self.nodegroupinterface_set.all():
            return interface
        return None

    def get_managed_interface(self):
        """Return the interface for which MAAS managed the DHCP service.

        This is a temporary method that should be refactored once we add
        proper support for multiple interfaces on a nodegroup.
        """
        # Iterate over all the interfaces in python instead of doing the
        # filtering in SQL so that this will use the cached version of
        # self.nodegroupinterface_set if it is there.
        for interface in self.nodegroupinterface_set.all():
            if interface.management != NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED:
                return interface
        return None

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
        config_parameters = {
            'http_proxy',
            'main_archive',
            'ports_archive',
            'cloud_images_archive',
        }
        task_kwargs = {
            name: Config.objects.get_config(name)
            for name in config_parameters
            if Config.objects.get_config(name) is not None
        }
        import_boot_images.apply_async(queue=self.uuid, kwargs=task_kwargs)

    def add_seamicro15k(self, mac, username, password):
        """ Add all of the specified cards the Seamicro SM15000 chassis at the
        specified MAC. """
        args = (mac, username, password)
        add_seamicro15k.apply_async(queue=self.uuid, args=args)

    def add_dhcp_host_maps(self, new_leases):
        if self.get_managed_interface() is not None and len(new_leases) > 0:
            # XXX JeroenVermeulen 2012-08-21, bug=1039362: the DHCP
            # server is currently always local to the worker system, so
            # use 127.0.0.1 as the DHCP server address.
            task_kwargs = dict(
                mappings=new_leases, server_address='127.0.0.1',
                shared_key=self.dhcp_key)
            add_new_dhcp_host_map.apply_async(
                queue=self.uuid, kwargs=task_kwargs)
