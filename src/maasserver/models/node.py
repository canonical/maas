# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Node objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "Node",
    "fqdn_is_duplicate",
    "nodegroup_fqdn",
    ]


from collections import (
    defaultdict,
    namedtuple,
)
from datetime import timedelta
from operator import attrgetter
import re
from uuid import uuid1

from django.contrib.auth.models import User
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.db import connection
from django.db.models import (
    BigIntegerField,
    BooleanField,
    CASCADE,
    CharField,
    DateTimeField,
    ForeignKey,
    IntegerField,
    Manager,
    ManyToManyField,
    PROTECT,
    Q,
    SET_DEFAULT,
    SET_NULL,
    TextField,
)
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
import djorm_pgarray.fields
from maasserver import DefaultMeta
from maasserver.clusterrpc.dhcp import remove_host_maps
from maasserver.clusterrpc.power import (
    power_driver_check,
    power_off_node,
    power_on_node,
)
from maasserver.enum import (
    ALLOCATED_NODE_STATUSES,
    FILESYSTEM_FORMAT_TYPE_CHOICES_DICT,
    FILESYSTEM_TYPE,
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_FAMILY,
    IPADDRESS_TYPE,
    NODE_BOOT,
    NODE_BOOT_CHOICES,
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    POWER_STATE,
    POWER_STATE_CHOICES,
    PRESEED_TYPE,
)
from maasserver.exceptions import NodeStateViolation
from maasserver.fields import (
    JSONObjectField,
    MAASIPAddressField,
    MAC,
)
from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.filesystem import Filesystem
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.interface import Interface
from maasserver.models.licensekey import LicenseKey
from maasserver.models.partitiontable import PartitionTable
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.tag import Tag
from maasserver.models.timestampedmodel import (
    now,
    TimestampedModel,
)
from maasserver.models.zone import Zone
from maasserver.node_status import (
    COMMISSIONING_LIKE_STATUSES,
    get_failed_status,
    is_failed_status,
    NODE_TRANSITIONS,
)
from maasserver.rpc.monitors import TransitionMonitor
from maasserver.storage_layouts import (
    get_storage_layout_for_node,
    StorageLayoutError,
    StorageLayoutMissingBootDiskError,
)
from maasserver.utils import strip_domain
from maasserver.utils.django import has_builtin_migrations
from maasserver.utils.dns import validate_hostname
from maasserver.utils.mac import get_vendor_for_mac
from maasserver.utils.orm import (
    get_one,
    MAASQueriesMixin,
    post_commit,
    post_commit_do,
    transactional,
)
from maasserver.utils.threads import (
    callOutToDatabase,
    deferToDatabase,
)
from metadataserver.enum import RESULT_TYPE
from netaddr import IPAddress
import petname
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_TYPES,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.power import QUERY_POWER_TYPES
from provisioningserver.power.poweraction import (
    PowerActionFail,
    UnknownPowerType,
)
from provisioningserver.rpc.exceptions import CannotRemoveHostMap
from provisioningserver.utils.enum import map_enum_reverse
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    synchronous,
)
from twisted.internet import reactor
from twisted.internet.defer import Deferred

# To support upgrading from MAAS versions <2.0 the piston module was named
# 'piston' not 'piston3'. Even though 'piston' and 'piston3' module are the
# same the import names are important because it will break south migrations
# unless piston is imported as 'piston'.
if has_builtin_migrations():
    from piston3.models import Token
else:
    from piston.models import Token


maaslog = get_maas_logger("node")


# Holds the known `bios_boot_methods`. If `bios_boot_method` is not in this
# list then it will fallback to `DEFAULT_BIOS_BOOT_METHOD`.
KNOWN_BIOS_BOOT_METHODS = ["pxe", "uefi"]

# Default `bios_boot_method`. See `KNOWN_BIOS_BOOT_METHOD` above for usage.
DEFAULT_BIOS_BOOT_METHOD = "pxe"


def generate_node_system_id():
    return 'node-%s' % uuid1()

# Return type from `get_effective_power_info`.
PowerInfo = namedtuple("PowerInfo", (
    "can_be_started", "can_be_stopped", "can_be_queried", "power_type",
    "power_parameters"))


class NodeQueriesMixin(MAASQueriesMixin):

    def filter_by_spaces(self, spaces):
        """Return the set of nodes with at least one interface in the specified
        spaces.
        """
        return self.filter(
            interface__ip_addresses__subnet__space__in=spaces)

    def exclude_spaces(self, spaces):
        """Return the set of nodes without any interfaces in the specified
        spaces.
        """
        return self.exclude(
            interface__ip_addresses__subnet__space__in=spaces)

    def filter_by_fabrics(self, fabrics):
        """Return the set of nodes with at least one interface in the specified
        fabrics.
        """
        return self.filter(
            interface__vlan__fabric__in=fabrics)

    def exclude_fabrics(self, fabrics):
        """Return the set of nodes without any interfaces in the specified
        fabrics.
        """
        return self.exclude(
            interface__vlan__fabric__in=fabrics)

    def filter_by_fabric_classes(self, fabric_classes):
        """Return the set of nodes with at least one interface in the specified
        fabric classes.
        """
        return self.filter(
            interface__vlan__fabric__class_type__in=fabric_classes)

    def exclude_fabric_classes(
            self, fabric_classes):
        """Return the set of nodes without any interfaces in the specified
        fabric classes.
        """
        return self.exclude(
            interface__vlan__fabric__class_type__in=fabric_classes)

    def filter_by_vids(self, vids):
        """Return the set of nodes with at least one interface whose VLAN has
        one of the specified VIDs.
        """
        return self.filter(
            interface__vlan__vid__in=vids)

    def exclude_vids(self, vids):
        """Return the set of nodes without any interfaces whose VLAN has one of
        the specified VIDs.
        """
        return self.exclude(
            interface__vlan__vid__in=vids)

    def filter_by_subnets(self, subnets):
        """Return the set of nodes with at least one interface configured on
        one of the specified subnets.
        """
        return self.filter(
            interface__ip_addresses__subnet__in=subnets)

    def exclude_subnets(self, subnets):
        """Return the set of nodes without any interfaces configured on one of
        the specified subnets.
        """
        return self.exclude(
            interface__ip_addresses__subnet__in=subnets)

    def filter_by_subnet_cidrs(self, subnet_cidrs):
        """Return the set of nodes with at least one interface configured on
        one of the specified subnet with the given CIDRs.
        """
        return self.filter(
            interface__ip_addresses__subnet__cidr__in=subnet_cidrs)

    def exclude_subnet_cidrs(self, subnet_cidrs):
        """Return the set of nodes without any interfaces configured on one of
        the specified subnet with the given CIDRs.
        """
        return self.exclude(
            interface__ip_addresses__subnet__cidr__in=subnet_cidrs)


class NodeQuerySet(QuerySet, NodeQueriesMixin):
    """Custom QuerySet which mixes in some additional queries specific to
    nodes. This needs to be a mixin because an identical method is needed on
    both the Manager and all QuerySets which result from calling the manager.
    """


class BaseNodeManager(Manager, NodeQueriesMixin):
    """A utility to manage the collection of Nodes."""

    extra_filters = {}

    def get_queryset(self):
        queryset = NodeQuerySet(self.model, using=self._db)
        return queryset.filter(**self.extra_filters)

    def filter_by_ids(self, query, ids=None):
        """Filter `query` result set by system_id values.

        :param query: A QuerySet of Nodes.
        :type query: django.db.models.query.QuerySet_
        :param ids: Optional set of ids to filter by.  If given, nodes whose
            system_ids are not in `ids` will be ignored.
        :type param_ids: Sequence
        :return: A filtered version of `query`.

        .. _django.db.models.query.QuerySet: https://docs.djangoproject.com/
           en/dev/ref/models/querysets/

        """
        if ids is None:
            return query
        else:
            return query.filter(system_id__in=ids)

    def _filter_visible_nodes(self, nodes, user, perm):
        """Filter a `Node` query depending on user permissions.

        :param nodes: A `Node` query set.
        :param user: The user making the request; the filtering is based on
            their privileges.
        :param perm: Type of access requested.  For example, a user may be
            allowed to view some nodes that they are not allowed to edit.
        :type perm: `NODE_PERMISSION`
        :return: A version of `node` that is filtered to include only those
            nodes that `user` is allowed to access.
        """
        # If the data is corrupt, this can get called with None for
        # user where a Node should have an owner but doesn't.
        # Nonetheless, the code should not crash with corrupt data.
        if user is None:
            return nodes.none()
        if user.is_superuser:
            # Admin is allowed to see all nodes.
            return nodes
        elif perm == NODE_PERMISSION.VIEW:
            return nodes.filter(Q(owner__isnull=True) | Q(owner=user))
        elif perm == NODE_PERMISSION.EDIT:
            return nodes.filter(owner=user)
        elif perm == NODE_PERMISSION.ADMIN:
            return nodes.none()
        else:
            raise NotImplementedError(
                "Invalid permission check (invalid permission name: %s)." %
                perm)

    def get_nodes(self, user, perm, ids=None, from_nodes=None):
        """Fetch Nodes on which the User_ has the given permission.

        Warning: there could be a lot of nodes!  Keep scale in mind when
        calling this, and watch performance in general.  Prefetch related
        data where appropriate.

        :param user: The user that should be used in the permission check.
        :type user: User_
        :param perm: The permission to check.
        :type perm: a permission string from NODE_PERMISSION
        :param ids: If given, limit result to nodes with these system_ids.
        :type ids: Sequence.
        :param from_nodes: Optionally, restrict the answer to these nodes.
        :type from_nodes: Query set of `Node`.

        .. _User: https://
           docs.djangoproject.com/en/dev/topics/auth/
           #django.contrib.auth.models.User

        """
        if from_nodes is None:
            from_nodes = self.all()
        nodes = self._filter_visible_nodes(from_nodes, user, perm)
        return self.filter_by_ids(nodes, ids)

    def get_allocated_visible_nodes(self, token, ids):
        """Fetch Nodes that were allocated to the User_/oauth token.

        :param user: The user whose nodes to fetch
        :type user: User_
        :param token: The OAuth token associated with the Nodes.
        :type token: piston3.models.Token.
        :param ids: Optional set of IDs to filter by. If given, nodes whose
            system_ids are not in `ids` will be ignored.
        :type param_ids: Sequence

        .. _User: https://
           docs.djangoproject.com/en/dev/topics/auth/
           #django.contrib.auth.models.User
        """
        if ids is None:
            nodes = self.filter(token=token)
        else:
            nodes = self.filter(token=token, system_id__in=ids)
        return nodes

    def get_node_or_404(self, system_id, user, perm):
        """Fetch a `Node` by system_id.  Raise exceptions if no `Node` with
        this system_id exist or if the provided user has not the required
        permission on this `Node`.

        :param name: The system_id.
        :type name: string
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :param perm: The permission to assert that the user has on the node.
        :type perm: unicode
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        node = get_object_or_404(
            self.model, system_id=system_id, **self.extra_filters)
        if user.has_perm(perm, node):
            return node
        else:
            raise PermissionDenied()

    def get_available_nodes_for_acquisition(self, for_user):
        """Find the nodes that can be acquired by the given user.

        :param for_user: The user who is to acquire the node.
        :type for_user: :class:`django.contrib.auth.models.User`
        :return: Those nodes which can be acquired by the user.
        :rtype: `django.db.models.query.QuerySet`
        """
        available_nodes = self.get_nodes(for_user, NODE_PERMISSION.VIEW)
        return available_nodes.filter(status=NODE_STATUS.READY)


class GeneralManager(BaseNodeManager):
    """All the nodes: installable and non-installable together."""


class NodeManager(BaseNodeManager):
    """Installable nodes (i.e. non-devices objects)."""

    extra_filters = {'installable': True}


class DeviceManager(BaseNodeManager):
    """Devices are all the non-installable nodes."""

    extra_filters = {'installable': False}


def patch_pgarray_types():
    """Monkey-patch incompatibility with recent versions of `djorm_pgarray`.

    An upstream commit in `djorm_pgarray` on 2013-07-21 effectively limits
    arrays to a fixed set of types.  An attempt to create an `ArrayField` of
    any other type results in the error "TypeError: invalid postgreSQL type."
    We have been getting that error with python-djorm-ext-pgarray 0.8, the
    first Ubuntu-packaged version, but not with 0.6.

    This function monkey-patches the set of supported types, adding macaddr.

    Upstream bug: https://github.com/niwibe/djorm-ext-pgarray/issues/19
    """
    # TYPES maps PostgreSQL type names to their Django casters.  The error
    # happens when using a postgres type name that is not in this dict.
    #
    # Older versions did not have TYPES, and worked out of the box.
    types_dict = getattr(djorm_pgarray.fields, 'TYPES', None)
    if types_dict is not None and 'macaddr' not in types_dict:
        djorm_pgarray.fields.TYPES['macaddr'] = MAC


# Monkey-patch djorm_pgarray's types list to support MAC.
patch_pgarray_types()


def nodegroup_fqdn(hostname, nodegroup_name):
    """Build a FQDN from a hostname and a nodegroup name.

    If hostname includes a domain, it is replaced with nodegroup_name.
    Otherwise, nodegroup name is append to hostname as a domain.
    """
    stripped_hostname = strip_domain(hostname)
    return '%s.%s' % (stripped_hostname, nodegroup_name)


def fqdn_is_duplicate(node, fqdn):
    """Determine if fqdn exists on any other nodes."""
    hostname = strip_domain(fqdn)
    nodes = Node.objects.filter(
        hostname__startswith=hostname).exclude(id=node.id)

    for check_node in nodes:
        if check_node.fqdn == fqdn:
            return True

    return False


def get_default_zone():
    """Return the ID of the default zone."""
    return Zone.objects.get_default_zone().id


# List of statuses for which it makes sense to release a node.
RELEASABLE_STATUSES = [
    NODE_STATUS.ALLOCATED,
    NODE_STATUS.RESERVED,
    NODE_STATUS.BROKEN,
    NODE_STATUS.DEPLOYING,
    NODE_STATUS.DEPLOYED,
    NODE_STATUS.FAILED_DEPLOYMENT,
    NODE_STATUS.FAILED_DISK_ERASING,
    NODE_STATUS.FAILED_RELEASING,
    ]


class Node(CleanSave, TimestampedModel):
    """A `Node` represents a physical machine used by the MAAS Server.

    :ivar system_id: The unique identifier for this `Node`.
        (e.g. 'node-41eba45e-4cfa-11e1-a052-00225f89f211').
    :ivar hostname: This `Node`'s hostname.  Must conform to RFCs 952 and 1123.
    :ivar installable: An optional flag to indicate if this node can be
        installed or not.  Non-installable nodes are nodes for which MAAS only
        manages DHCP and DNS.
    :ivar parent: An optional parent `Node`.  This node will be deleted along
        with all its resources when the parent node gets deleted or released.
        This is only relevant for non-installable nodes.
    :ivar status: This `Node`'s status. See the vocabulary
        :class:`NODE_STATUS`.
    :ivar error_description: A human-readable description of why a node is
        marked broken.  Only meaningful when the node is in the state 'BROKEN'.
    :ivar owner: This `Node`'s owner if it's in use, None otherwise.
    :ivar bios_boot_method: The boot method used by the cluster to allow
        this node to boot. E.g. "pxe".
    :ivar boot_type: This `Node`'s booting method. See the vocabulary
        :class:`NODE_BOOT`.
    :ivar osystem: This `Node`'s booting operating system, if it's blank then
        the default_osystem will be used.
    :ivar distro_series: This `Node`'s booting distro series, if
        it's blank then the default_distro_series will be used.
    :ivar power_type: The power type that determines how this
        node will be powered on. Its value must match a power driver template
        name.
    :ivar nodegroup: The `NodeGroup` this `Node` belongs to.
    :ivar tags: The list of :class:`Tag`s associated with this `Node`.
    :ivar objects: The :class:`NodeManager`.
    :ivar enable_ssh: An optional flag to indicate if this node can have
        ssh enabled during commissioning, allowing the user to ssh into the
        machine's commissioning environment using the user's SSH key.
    :ivar skip_networking: An optional flag to indicate if this node
        networking configuration doesn't need to be touched when it is
        commissioned.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    system_id = CharField(
        max_length=41, unique=True, default=generate_node_system_id,
        editable=False)

    hostname = CharField(
        max_length=255, default='', blank=True, unique=True,
        validators=[validate_hostname])

    status = IntegerField(
        choices=NODE_STATUS_CHOICES, editable=False,
        default=NODE_STATUS.DEFAULT)

    owner = ForeignKey(
        User, default=None, blank=True, null=True, editable=False,
        on_delete=PROTECT)

    bios_boot_method = CharField(max_length=31, blank=True, null=True)

    boot_type = CharField(
        max_length=20, choices=NODE_BOOT_CHOICES, default=NODE_BOOT.FASTPATH)

    osystem = CharField(
        max_length=20, blank=True, default='')

    distro_series = CharField(
        max_length=20, blank=True, default='')

    architecture = CharField(max_length=31, blank=True, null=True)

    min_hwe_kernel = CharField(max_length=31, blank=True, null=True)

    hwe_kernel = CharField(max_length=31, blank=True, null=True)

    installable = BooleanField(default=True, db_index=True, editable=False)

    parent = ForeignKey(
        "Node", default=None, blank=True, null=True, editable=True,
        related_name="children", on_delete=CASCADE)

    routers = djorm_pgarray.fields.ArrayField(dbtype="macaddr")

    agent_name = CharField(max_length=255, default='', blank=True, null=True)

    error_description = TextField(blank=True, default='', editable=False)

    zone = ForeignKey(
        Zone, verbose_name="Physical zone",
        default=get_default_zone, editable=True, db_index=True,
        on_delete=SET_DEFAULT)

    # Juju expects the following standard constraints, which are stored here
    # as a basic optimisation over querying the lshw output.
    cpu_count = IntegerField(default=0)
    memory = IntegerField(default=0)

    swap_size = BigIntegerField(null=True, blank=True, default=None)

    # For strings, Django insists on abusing the empty string ("blank")
    # to mean "none."
    # The possible choices for this field depend on the power types
    # advertised by the clusters.  This needs to be populated on the fly,
    # in forms.py, each time the form to edit a node is instantiated.
    power_type = CharField(
        max_length=10, null=False, blank=True, default='')

    # JSON-encoded set of parameters for power control, limited to 32kiB when
    # encoded as JSON.
    power_parameters = JSONObjectField(
        max_length=(2 ** 15), blank=True, default="")

    power_state = CharField(
        max_length=10, null=False, blank=False,
        choices=POWER_STATE_CHOICES, default=POWER_STATE.UNKNOWN,
        editable=False)

    power_state_updated = DateTimeField(
        null=True, blank=False, default=None, editable=False)

    token = ForeignKey(
        Token, db_index=True, null=True, editable=False, unique=False)

    error = CharField(max_length=255, blank=True, default='')

    netboot = BooleanField(default=True)

    license_key = CharField(max_length=30, null=True, blank=True)

    # This field can't be null, but we can't enforce that in the
    # database schema because we can only create the default value from
    # a complete schema, after schema migration.  We can't use custom
    # model validation either, because the node forms need to set their
    # default values *after* saving the form (with commit=False), which
    # incurs validation before the default values are set.
    # So all we can do is set blank=False, and make the field editable
    # to cajole Django out of skipping it during "model" (actually model
    # form) validation.
    nodegroup = ForeignKey(
        'maasserver.NodeGroup', editable=True, null=True, blank=False)

    tags = ManyToManyField(Tag)

    # Disable IPv4 support on node once deployed, on operating systems that
    # support this choice.
    disable_ipv4 = BooleanField(
        default=False, verbose_name="Disable IPv4 when deployed",
        help_text=(
            "On operating systems where this choice is supported, this option "
            "disables IPv4 networking on this node when it is deployed.  "
            "IPv4 may still be used for booting and installing the node.  "
            "THIS MAY STOP YOUR NODE FROM WORKING.  Do not disable IPv4 "
            "unless you know what you're doing: clusters must be configured "
            "to use a MAAS URL with a hostname that resolves on both IPv4 and "
            "IPv6."))

    # Record the Interface the node last booted from.
    # This will be used for determining which Interface to create a static
    # IP reservation for when starting a node.
    boot_interface = ForeignKey(
        Interface, default=None, blank=True, null=True, editable=False,
        related_name='+', on_delete=SET_NULL)

    # Record the last IP address of the cluster this node used to request
    # TFTP data. This is used to send the correct IP address for the node to
    # download the image to install. Since the node just contacted the cluster
    # using this IP address then it will be able to access the images at this
    # IP address.
    boot_cluster_ip = MAASIPAddressField(
        unique=False, null=True, editable=False, blank=True, default=None)

    # Record the PhysicalBlockDevice that this node uses as its boot disk.
    # This will be used to make sure GRUB is installed to this device.
    boot_disk = ForeignKey(
        PhysicalBlockDevice, default=None, blank=True, null=True,
        editable=False, related_name='+', on_delete=SET_NULL)

    # Default IPv4 subnet link on an interface for this node. This is used to
    # define the default IPv4 route the node should use.
    gateway_link_ipv4 = ForeignKey(
        StaticIPAddress, default=None, blank=True, null=True,
        editable=False, related_name='+', on_delete=SET_NULL)

    # Default IPv6 subnet link on an interface for this node. This is used to
    # define the default IPv6 route the node should use.
    gateway_link_ipv6 = ForeignKey(
        StaticIPAddress, default=None, blank=True, null=True,
        editable=False, related_name='+', on_delete=SET_NULL)

    # Used to determine whether to:
    #  1. Import the SSH Key during commissioning.
    #  2. Block the automatic power off during commissioning.
    #  3. Skip reconfiguring networking when a node is commissioned.
    #  4. Skip reconfiguring storage when a node is commissioned.
    enable_ssh = BooleanField(default=False)
    skip_networking = BooleanField(default=False)
    skip_storage = BooleanField(default=False)

    # Note that the ordering of the managers is meaningful.  More precisely,
    # the first manager defined is important: see
    # https://docs.djangoproject.com/en/1.7/topics/db/managers/ ("Default
    # managers") for details.
    # 'objects' are all the nodes: installable and non-installable together.
    objects = GeneralManager()

    # 'nodes' are all the installable nodes (i.e. non-devices objects).
    nodes = NodeManager()

    # 'devices' are all the non-installable nodes.
    devices = DeviceManager()

    def __unicode__(self):
        if self.hostname:
            return "%s (%s)" % (self.system_id, self.fqdn)
        else:
            return self.system_id

    @property
    def fqdn(self):
        """Fully qualified domain name for this node.

        If MAAS manages DNS for this node or if this node doesn't have a
        domain name set, replace or add the domain name configured
        on the cluster controller.  Otherwise simply return the node's
        hostname.
        """
        should_add_domain_name = (
            self.nodegroup.manages_dns() or
            self.hostname == strip_domain(self.hostname)
        )
        if should_add_domain_name:
            return nodegroup_fqdn(self.hostname, self.nodegroup.name)
        return self.hostname

    def get_deployment_time(self):
        """Return the deployment time of this node (in seconds).

        This is the maximum time the deployment is allowed to take.
        """
        # Return a *very* conservative estimate for now.
        # Something that shouldn't conflict with any deployment.
        return timedelta(minutes=40).total_seconds()

    def get_commissioning_time(self):
        """Return the commissioning time of this node (in seconds).

        This is the maximum time the commissioning is allowed to take.
        """
        # Return a *very* conservative estimate for now.
        return timedelta(minutes=20).total_seconds()

    def get_releasing_time(self):
        """Return the releasing time of this node (in seconds).

        This is the maximum time that releasing is allowed to take.
        """
        return timedelta(minutes=5).total_seconds()

    def _register_request_event(
            self, user, type_name, action='', comment=None):
        """Register a node user request event."""
        # don't register system generated non-user requests
        if user is not None:
            event_details = EVENT_DETAILS[type_name]
            description = "(%s)" % user.username
            if comment:
                description = "%s - %s" % (description, comment)
            # Avoid circular imports.
            from maasserver.models.event import Event
            Event.objects.register_event_and_event_type(
                self.system_id, type_name, type_level=event_details.level,
                type_description=event_details.description,
                event_action=action,
                event_description=description)

    def storage_layout_issues(self):
        """Return any errors with the storage layout.

        Checks that the node has / mounted. If / is mounted on bcache check
        that /boot is mounted and is not on bcache."""
        def on_bcache(obj):
            if obj.type == "physical":
                return False
            elif obj.type == "partition":
                return on_bcache(obj.partition_table.block_device)
            for parent in obj.virtualblockdevice.get_parents():
                if((parent.type != "physical" and on_bcache(parent)) or
                    (parent.get_effective_filesystem().fstype in
                     [FILESYSTEM_TYPE.BCACHE_CACHE,
                      FILESYSTEM_TYPE.BCACHE_BACKING])):
                    return True
            return False

        has_boot = False
        root_mounted = False
        root_on_bcache = False
        boot_mounted = False

        for block_device in self.blockdevice_set.all():
            if block_device.is_boot_disk():
                has_boot = True
            pt = block_device.get_partitiontable()
            if pt is not None:
                for partition in pt.partitions.all():
                    fs = partition.get_effective_filesystem()
                    if fs is None:
                        continue
                    if fs.mount_point == '/':
                        root_mounted = True
                        if on_bcache(block_device):
                            root_on_bcache = True
                        else:
                            # If / is mounted and its not on bcache the system
                            # is bootable
                            return []
                    elif (fs.mount_point == '/boot' and
                          not on_bcache(block_device)):
                        boot_mounted = True
            else:
                fs = block_device.get_effective_filesystem()
                if fs is None:
                    continue
                if fs.mount_point == '/':
                    root_mounted = True
                    if on_bcache(block_device):
                        root_on_bcache = True
                    else:
                        # If / is mounted and its not on bcache the system
                        # is bootable.
                        return []
                elif fs.mount_point == '/boot' and not on_bcache(block_device):
                    boot_mounted = True
        issues = []
        if not has_boot:
            issues.append(
                "Specify a storage device to be able to deploy this node.")
        if not root_mounted:
            issues.append(
                "Mount the root '/' filesystem to be able to deploy this "
                "node.")
        if root_mounted and root_on_bcache and not boot_mounted:
            issues.append(
                "This node cannot be deployed because it cannot boot from a "
                "bcache volume. Mount /boot on a non-bcache device to be "
                "able to deploy this node.")
        return issues

    def on_network(self):
        """Return true if the node is connected to a managed network."""
        for interface in self.interface_set.all():
            for link in interface.get_links():
                if (link['mode'] != INTERFACE_LINK_TYPE.LINK_UP and
                        'subnet' in link):
                    return True
        return False

    def _start_deployment(self):
        """Mark a node as being deployed."""
        if self.on_network() is False:
            raise ValidationError(
                {"network":
                 ["Node must be configured to use a network"]})
        storage_layout_issues = self.storage_layout_issues()
        if len(storage_layout_issues) > 0:
            raise ValidationError({"storage": storage_layout_issues})
        self.status = NODE_STATUS.DEPLOYING
        self.save()

    def end_deployment(self):
        """Mark a node as successfully deployed."""
        self.status = NODE_STATUS.DEPLOYED
        self.save()

    @synchronous
    def start_transition_monitor(self, timeout):
        """Start cluster-side transition monitor."""
        monitor = (
            TransitionMonitor.fromNode(self)
            .within(seconds=timeout)
            .status_should_be(self.status))
        post_commit().addCallback(
            callOut, self._start_transition_monitor_async, monitor,
            self.hostname)

    @synchronous
    def stop_transition_monitor(self):
        """Stop cluster-side transition monitor."""
        monitor = TransitionMonitor.fromNode(self)
        post_commit().addCallback(
            callOut, self._stop_transition_monitor_async, monitor,
            self.hostname)

    def handle_monitor_expired(self, context):
        """Handle a monitor expired event."""
        failed_status = get_failed_status(self.status)
        if failed_status is not None:
            timeout_timedelta = timedelta(seconds=context['timeout'])
            self._mark_failed(
                None, "Node operation '%s' timed out after %s." % (
                    (
                        NODE_STATUS_CHOICES_DICT[self.status],
                        timeout_timedelta
                    )))

    def ip_addresses(self):
        """IP addresses allocated to this node.

        Return the current IP addresses for this Node, or the empty
        list if there are none.

        If `disable_ipv4` is set, any IPv4 addresses will be omitted.
        """
        # If the node has static IP addresses assigned they will be returned
        # before the dynamic IP addresses are returned. The dynamic IP
        # addresses will only be returned if the node has no static IP
        # addresses.
        ips = self.static_ip_addresses()
        if len(ips) == 0:
            ips = self.dynamic_ip_addresses()
        if self.disable_ipv4:
            return [
                ip
                for ip in ips
                if IPAddress(ip).version > 4
                ]
        else:
            return ips

    def static_ip_addresses(self):
        """Static IP addresses allocated to this node."""
        # DHCP is included here because it is a configured type. Its not
        # just set randomly by the lease parser.
        ip_addresses = StaticIPAddress.objects.filter(
            interface__node=self, ip__isnull=False,
            alloc_type__in=[
                IPADDRESS_TYPE.DHCP,
                IPADDRESS_TYPE.AUTO,
                IPADDRESS_TYPE.STICKY,
                IPADDRESS_TYPE.USER_RESERVED,
            ])
        ips = []
        for ip in ip_addresses:
            ip = ip.get_ip()
            if ip:
                ips.append(ip)
        return ips

    def dynamic_ip_addresses(self):
        """Dynamic IP addresses allocated to this node."""
        ip_addresses = StaticIPAddress.objects.filter(
            interface__node=self, alloc_type=IPADDRESS_TYPE.DISCOVERED)
        return [
            ip
            for ip in ip_addresses.values_list('ip', flat=True)
            if ip
        ]

    def get_interface_names(self):
        return list(self.interface_set.all().values_list('name', flat=True))

    def get_next_ifname(self, ifnames=None):
        """
        Scans the interfaces on this Node and returns the next free ifname in
        the format 'ethX', where X is zero or a positive integer.
        """
        if ifnames is None:
            ifnames = self.get_interface_names()
        used_ethX = []
        for ifname in ifnames:
            match = re.match('eth([0-9]+)', ifname)
            if match is not None:
                ifnum = int(match.group(1))
                used_ethX.append(ifnum)
        if len(used_ethX) == 0:
            return "eth0"
        else:
            ifnum = max(used_ethX) + 1
            return "eth%d" % ifnum

    def tag_names(self):
        # We don't use self.tags.values_list here because this does not
        # take advantage of the cache.
        return [tag.name for tag in self.tags.all()]

    def clean_boot_disk(self, prev):
        """Check that the boot disk is either un-used or has a partition
        table.

        It's possible that the boot disk we are seeing is already in-use with a
        filesystem group or cache set.
        """
        if self.boot_disk is not None:
            filesystem = self.boot_disk.get_effective_filesystem()
            if filesystem is not None:
                if filesystem.fstype in FILESYSTEM_FORMAT_TYPE_CHOICES_DICT:
                    # Format-able filesystem so it can just be removed.
                    filesystem.delete()
                elif filesystem.filesystem_group is not None:
                    # Part of a filesystem group and cannot be set as the
                    # boot disk.
                    raise ValidationError({
                        "boot_disk": [
                            "Cannot be set as the boot disk; already in-use "
                            "in %s '%s'." % (
                                filesystem.filesystem_group.get_nice_name(),
                                filesystem.filesystem_group.name,
                                )]
                        })
                elif filesystem.cache_set is not None:
                    # Part of a cache set and cannot be set as the boot disk.
                    raise ValidationError({
                        "boot_disk": [
                            "Cannot be set as the boot disk; already in-use "
                            "in cache set '%s'." % (
                                filesystem.cache_set.name,
                                )]
                        })

    def clean_boot_interface(self, prev):
        """Check that this Node's boot interface (if present) belongs to this
        Node.

        It's possible, though very unlikely, that the boot interface we are
        seeing is already assigned to another Node. If this happens, we need to
        catch the failure as early as possible.
        """
        if (self.boot_interface is not None and self.id is not None and
                self.id != self.boot_interface.node_id):
                raise ValidationError({
                    'boot_interface': [
                        "Must be one of the node's interfaces."],
                    })

    def clean_status(self, prev):
        """Check a node's status transition against the node-status FSM."""
        old_status = None if prev is None else prev.status
        if self.status == old_status:
            # No transition is always a safe transition.
            pass
        elif self.status in NODE_TRANSITIONS.get(old_status, ()):
            # Valid transition.
            if old_status is not None:
                stat = map_enum_reverse(NODE_STATUS, ignore=['DEFAULT'])
                maaslog.info(
                    "%s: Status transition from %s to %s",
                    self.hostname, stat[old_status], stat[self.status])
        else:
            # Transition not permitted.
            error_text = "Invalid transition: %s -> %s." % (
                NODE_STATUS_CHOICES_DICT.get(old_status, "Unknown"),
                NODE_STATUS_CHOICES_DICT.get(self.status, "Unknown"),
                )
            raise NodeStateViolation(error_text)

    def clean_architecture(self, prev):
        if self.architecture == '' and self.installable:
            raise ValidationError(
                {'architecture':
                    ["Architecture must be defined for installable nodes."]})

    def clean(self, *args, **kwargs):
        super(Node, self).clean(*args, **kwargs)
        prev = get_one(Node.objects.filter(pk=self.pk))
        self.clean_status(prev)
        self.clean_architecture(prev)
        self.clean_boot_disk(prev)
        self.clean_boot_interface(prev)

    def display_status(self):
        """Return status text as displayed to the user."""
        return NODE_STATUS_CHOICES_DICT[self.status]

    def display_memory(self):
        """Return memory in GiB."""
        if self.memory < 1024:
            return '%.1f' % (self.memory / 1024.0)
        return '%d' % (self.memory / 1024)

    @property
    def physicalblockdevice_set(self):
        """Return `QuerySet` for all `PhysicalBlockDevice` assigned to node.

        This is need as Django doesn't add this attribute to the `Node` model,
        it only adds blockdevice_set.
        """
        return PhysicalBlockDevice.objects.filter(node=self)

    @property
    def virtualblockdevice_set(self):
        """Return `QuerySet` for all `VirtualBlockDevice` assigned to node.

        This is need as Django doesn't add this attribute to the `Node` model,
        it only adds blockdevice_set.
        """
        # Avoid circular imports
        from maasserver.models.virtualblockdevice import VirtualBlockDevice
        return VirtualBlockDevice.objects.filter(node=self)

    @property
    def storage(self):
        """Return storage in megabytes.

        Compatility with API 1.0 this field needs to exist on the Node.
        """
        size = (
            PhysicalBlockDevice.objects.total_size_of_physical_devices_for(
                self))
        return size / 1000 / 1000

    def display_storage(self):
        """Return storage in gigabytes."""
        if self.storage < 1000:
            return '%.1f' % (self.storage / 1000.0)
        return '%d' % (self.storage / 1000)

    def get_boot_disk(self):
        """Return the boot disk for this node."""
        if self.boot_disk is not None:
            return self.boot_disk
        else:
            # Fallback to using the first created physical block device as
            # the boot disk.
            return self.physicalblockdevice_set.order_by('id').first()

    def get_bios_boot_method(self):
        """Return the boot method the node's BIOS booted."""
        if self.bios_boot_method not in KNOWN_BIOS_BOOT_METHODS:
            if self.bios_boot_method:
                maaslog.warning(
                    "%s: Has a unknown BIOS boot method '%s'; "
                    "defaulting to '%s'." % (
                        self.hostname,
                        self.bios_boot_method,
                        DEFAULT_BIOS_BOOT_METHOD,
                        ))
            return DEFAULT_BIOS_BOOT_METHOD
        else:
            return self.bios_boot_method

    def add_physical_interface(self, mac_address, name=None):
        """Add a new `PhysicalInterface` to `node` with `mac_address`."""
        # Avoid circular imports
        from maasserver.models import PhysicalInterface, UnknownInterface
        if name is None:
            name = self.get_next_ifname()
        mac = MAC(mac_address)
        UnknownInterface.objects.filter(mac_address=mac).delete()
        try:
            iface = PhysicalInterface.objects.get(mac_address=mac)
        except PhysicalInterface.DoesNotExist:
            return PhysicalInterface.objects.create(
                node=self, mac_address=mac, name=name)
        if iface.node != self:
            # This MAC address is already registered to a different node.
            raise ValidationError(
                "MAC address %s already in use on %s." % (
                    mac_address, iface.node.hostname))
        return iface

    def accept_enlistment(self, user):
        """Accept this node's (anonymous) enlistment.

        This call makes sense only on a node in New state, i.e. one that
        has been anonymously enlisted and is now waiting for a MAAS user to
        accept that enlistment as authentic.  Calling it on a node that is in
        Ready or Commissioning state, however, is not an error -- it probably
        just means that somebody else has beaten you to it.

        :return: This node if it has made the transition from New, or
            None if it was already in an accepted state.
        """
        accepted_states = [NODE_STATUS.READY, NODE_STATUS.COMMISSIONING]
        if self.status in accepted_states:
            return None
        if self.status != NODE_STATUS.NEW:
            raise NodeStateViolation(
                "Cannot accept node enlistment: node %s is in state %s."
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status]))

        self.start_commissioning(user)
        return self

    @transactional
    def start_commissioning(
            self, user, enable_ssh=False, skip_networking=False,
            skip_storage=False):
        """Install OS and self-test a new node.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to start and commission the node. This is already
            registered as a post-commit hook; it should not be added a second
            time.
        """
        # Avoid circular imports.
        from metadataserver.user_data.commissioning import generate_user_data
        from metadataserver.models import NodeResult

        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_START_COMMISSIONING,
            action='start commissioning')

        # Set the commissioning options on the node.
        self.enable_ssh = enable_ssh
        self.skip_networking = skip_networking
        self.skip_storage = skip_storage

        # Generate the specific user data for commissioning this node.
        commissioning_user_data = generate_user_data(node=self)

        # Clear any existing commissioning results.
        NodeResult.objects.clear_results(self)

        # Clear the current storage configuration if networking is not being
        # skipped during commissioning.
        if not self.skip_storage:
            self._clear_full_storage_configuration()

        # Clear the current network configuration if networking is not being
        # skipped during commissioning.
        if not self.skip_networking:
            self._clear_networking_configuration()

        # We need to mark the node as COMMISSIONING now to avoid a race
        # when starting multiple nodes. We hang on to old_status just in
        # case the power action fails.
        old_status = self.status
        self.status = NODE_STATUS.COMMISSIONING
        self.owner = user
        # Set min_hwe_kernel to min_hwe_kernel if it isn't set incase
        # commissioning failed and the user set the min globally and is
        # retrying.
        if not self.min_hwe_kernel:
            self.min_hwe_kernel = Config.objects.get_config(
                'default_min_hwe_kernel')
        self.save()

        # Prepare a transition monitor for later.
        monitor = (
            TransitionMonitor.fromNode(self)
            .within(seconds=self.get_commissioning_time())
            .status_should_be(NODE_STATUS.READY))

        try:
            # Node.start() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            starting = self._start(user, commissioning_user_data)
        except Exception as error:
            self.status = old_status
            self.save()
            maaslog.error(
                "%s: Could not start node for commissioning: %s",
                self.hostname, error)
            # Let the exception bubble up, since the UI or API will have to
            # deal with it.
            raise
        else:
            # Don't permit naive mocking of start(); it causes too much
            # confusion when testing. Return a Deferred from side_effect.
            assert isinstance(starting, Deferred) or starting is None

            post_commit().addCallback(
                callOut, self._start_transition_monitor_async, monitor,
                self.hostname)

            if starting is None:
                starting = post_commit()
                # MAAS cannot start the node itself.
                is_starting = False
            else:
                # MAAS can direct the node to start.
                is_starting = True

            starting.addCallback(
                callOut, self._start_commissioning_async, is_starting,
                self.hostname)

            # If there's an error, reset the node's status.
            starting.addErrback(
                callOutToDatabase, self._set_status, self.system_id,
                status=old_status)

            def eb_start(failure, hostname):
                maaslog.error(
                    "%s: Could not start node for commissioning: %s",
                    hostname, failure.getErrorMessage())
                return failure  # Propagate.

            return starting.addErrback(eb_start, self.hostname)

    @classmethod
    @asynchronous
    def _start_transition_monitor_async(cls, monitor, hostname):
        """Start the given `monitor`.

        :param monitor: An instance of `TransitionMonitor`.
        :param hostname: The node's hostname, for logging.
        """
        def start():
            # Start the transition monitor. Only log failures; don't crash.
            return monitor.start().addErrback(eb_start, hostname)

        def eb_start(failure, hostname):
            maaslog.warning(
                "%s: Could not start transition monitor: %s",
                hostname, failure.getErrorMessage())

        reactor.callLater(0, start)

    @classmethod
    @asynchronous
    def _start_commissioning_async(cls, is_starting, hostname):
        """Start commissioning, the post-commit bits.

        :param is_starting: A boolean indicating if MAAS is able to start this
            node itself, or if manual intervention is needed.
        :param hostname: The node's hostname, for logging.
        """
        if is_starting:
            maaslog.info("%s: Commissioning started", hostname)
        else:
            maaslog.warning(
                "%s: Could not start node for commissioning; it "
                "must be started manually", hostname)

    @transactional
    def abort_commissioning(self, user, comment=None):
        """Power off a commissioning node and set its status to NEW.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to stop the node. This is already registered as a
            post-commit hook; it should not be added a second time.
        """
        if self.status != NODE_STATUS.COMMISSIONING:
            raise NodeStateViolation(
                "Cannot abort commissioning of a non-commissioning node: "
                "node %s is in state %s."
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status]))

        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_ABORT_COMMISSIONING,
            action='abort commissioning', comment=comment)

        # Prepare a transition monitor for later.
        monitor = TransitionMonitor.fromNode(self)

        try:
            # Node.stop() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            stopping = self._stop(user)
            if self.owner is not None:
                self.owner = None
                self.save()
        except Exception as error:
            maaslog.error(
                "%s: Error when aborting commissioning: %s",
                self.hostname, error)
            raise
        else:
            # Don't permit naive mocking of stop(); it causes too much
            # confusion when testing. Return a Deferred from side_effect.
            assert isinstance(stopping, Deferred) or stopping is None

            post_commit().addCallback(
                callOut, self._stop_transition_monitor_async, monitor,
                self.hostname)

            if stopping is None:
                stopping = post_commit()
                # MAAS cannot stop the node itself.
                is_stopping = False
            else:
                # MAAS can direct the node to stop.
                is_stopping = True

            stopping.addCallback(
                callOut, self._abort_commissioning_async, is_stopping,
                self.hostname, self.system_id)

            def eb_abort(failure, hostname):
                maaslog.error(
                    "%s: Error when aborting commissioning: %s",
                    hostname, failure.getErrorMessage())
                return failure  # Propagate.

            return stopping.addErrback(eb_abort, self.hostname)

    @transactional
    def abort_deploying(self, user, comment=None):
        """Power off a deploying node and set its status to ALLOCATED.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to stop the node. This is already registered as a
            post-commit hook; it should not be added a second time.
        """
        if self.status != NODE_STATUS.DEPLOYING:
            raise NodeStateViolation(
                "Cannot abort deployment of a non-deploying node: "
                "node %s is in state %s."
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status]))

        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_ABORT_DEPLOYMENT,
            action='abort deploying', comment=comment)

        # Prepare a transition monitor for later.
        monitor = TransitionMonitor.fromNode(self)

        try:
            # Node.stop() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            stopping = self._stop(user)
        except Exception as error:
            maaslog.error(
                "%s: Error when aborting deployment: %s",
                self.hostname, error)
            raise
        else:
            # Don't permit naive mocking of stop(); it causes too much
            # confusion when testing. Return a Deferred from side_effect.
            assert isinstance(stopping, Deferred) or stopping is None

            post_commit().addCallback(
                callOut, self._stop_transition_monitor_async, monitor,
                self.hostname)

            if stopping is None:
                stopping = post_commit()
                # MAAS cannot stop the node itself.
                is_stopping = False
            else:
                # MAAS can direct the node to stop.
                is_stopping = True

            stopping.addCallback(
                callOut, self._abort_deploying_async, is_stopping,
                self.hostname, self.system_id)

            def eb_abort(failure, hostname):
                maaslog.error(
                    "%s: Error when aborting deployment: %s",
                    hostname, failure.getErrorMessage())
                return failure  # Propagate.

            return stopping.addErrback(eb_abort, self.hostname)

    @classmethod
    @asynchronous
    def _stop_transition_monitor_async(cls, monitor, hostname):
        """Stop the given `monitor`.

        :param monitor: An instance of `TransitionMonitor`.
        :param hostname: The node's hostname, for logging.
        """
        def stop():
            # Stop the transition monitor. Only log failures; don't crash.
            return monitor.stop().addErrback(eb_stop, hostname)

        def eb_stop(failure, hostname):
            maaslog.warning(
                "%s: Could not stop transition monitor: %s",
                hostname, failure.getErrorMessage())

        reactor.callLater(0, stop)

    @classmethod
    @asynchronous
    def _abort_commissioning_async(cls, is_stopping, hostname, system_id):
        """Abort commissioning, the post-commit bits.

        :param is_stopping: A boolean indicating if MAAS is able to stop this
            node itself, or if manual intervention is needed.
        :param hostname: The node's hostname, for logging.
        :param system_id: The system ID for the node.
        """
        d = deferToDatabase(cls._set_status, system_id, status=NODE_STATUS.NEW)
        if is_stopping:
            return d.addCallback(
                callOut, maaslog.info, "%s: Commissioning aborted", hostname)
        else:
            return d.addCallback(
                callOut, maaslog.warning, "%s: Could not stop node to abort "
                "commissioning; it must be stopped manually", hostname)

    @classmethod
    @asynchronous
    def _abort_deploying_async(cls, is_stopping, hostname, system_id):
        """Abort deploying, the post-commit bits.

        :param is_stopping: A boolean indicating if MAAS is able to stop this
            node itself, or if manual intervention is needed.
        :param hostname: The node's hostname, for logging.
        :param system_id: The system ID for the node.
        """
        d = deferToDatabase(
            cls._set_status, system_id, status=NODE_STATUS.ALLOCATED)
        if is_stopping:
            return d.addCallback(
                callOut, maaslog.info, "%s: Deployment aborted", hostname)
        else:
            return d.addCallback(
                callOut, maaslog.warning, "%s: Could not stop node to abort "
                "deployment; it must be stopped manually", hostname)

    def delete(self):
        """Delete this node."""
        maaslog.info("%s: Deleting node", self.hostname)

        # Delete the related interfaces. This wil remove all of IP addresses
        # that are linked to those interfaces.
        self.interface_set.all().delete()

        super(Node, self).delete()

    def set_random_hostname(self):
        """Set a random `hostname`."""
        while True:
            self.hostname = petname.Generate(2, "-")
            try:
                self.save()
            except ValidationError:
                pass
            else:
                break

    def get_effective_power_type(self):
        """Get power-type to use for this node.

        If no power type has been set for the node, raise
        UnknownPowerType.
        """
        if self.power_type == '':
            raise UnknownPowerType("Node power type is unconfigured")
        return self.power_type

    def get_effective_kernel_options(self):
        """Determine any special kernel parameters for this node.

        :return: (tag, kernel_options)
            tag is a Tag object or None. If None, the kernel_options came from
            the global setting.
            kernel_options, a string indicating extra kernel_options that
            should be used when booting this node. May be None if no tags match
            and no global setting has been configured.
        """
        # First, see if there are any tags associated with this node that has a
        # custom kernel parameter
        tags = self.tags.filter(kernel_opts__isnull=False)
        tags = tags.order_by('name')
        for tag in tags:
            if tag.kernel_opts != '':
                return tag, tag.kernel_opts
        global_value = Config.objects.get_config('kernel_opts')
        return None, global_value

    @property
    def work_queue(self):
        """The name of the queue for tasks specific to this node."""
        return self.nodegroup.work_queue

    def get_osystem(self):
        """Return the operating system to install that node."""
        use_default_osystem = (self.osystem is None or self.osystem == '')
        if use_default_osystem:
            return Config.objects.get_config('default_osystem')
        else:
            return self.osystem

    def get_distro_series(self):
        """Return the distro series to install that node."""
        use_default_osystem = (
            self.osystem is None or
            self.osystem == '')
        use_default_distro_series = (
            self.distro_series is None or
            self.distro_series == '')
        if use_default_osystem and use_default_distro_series:
            return Config.objects.get_config('default_distro_series')
        else:
            return self.distro_series

    def get_effective_license_key(self):
        """Return effective license key.

        This returns the license key that should be used during the
        installation of the operating system for this node. This method first
        checks to see if the node has a specific license key set, if not then
        the license key registry is checked, if neither exists for this node or
        the booting operating system and release combination then an empty
        string is returned. An empty string can mean two things, one the
        operating system does not require a license key, or the installation
        media already has the license key builtin.
        """
        use_global_license_key = (
            self.license_key is None or
            self.license_key == '')
        if use_global_license_key:
            osystem = self.get_osystem()
            distro_series = self.get_distro_series()
            try:
                return LicenseKey.objects.get_license_key(
                    osystem, distro_series)
            except LicenseKey.DoesNotExist:
                return ''
        else:
            return self.license_key

    def get_effective_power_parameters(self):
        """Return effective power parameters, including any defaults."""
        if self.power_parameters:
            power_params = self.power_parameters.copy()
        else:
            # An empty power_parameters comes out as an empty unicode string!
            power_params = {}

        power_params.setdefault('system_id', self.system_id)
        # TODO: We should not be sending these paths to the templates;
        # the templates ought to know which tool to use themselves.
        power_params.setdefault('fence_cdu', '/usr/sbin/fence_cdu')
        power_params.setdefault('ipmipower', '/usr/sbin/ipmipower')
        power_params.setdefault('ipmitool', '/usr/bin/ipmitool')
        power_params.setdefault(
            'ipmi_chassis_config', '/usr/sbin/ipmi-chassis-config')
        power_params.setdefault('ipmi_config', 'ipmi.conf')
        # TODO: /end of paths that templates should know.
        # TODO: This default ought to be in the virsh template.
        if self.power_type == "virsh":
            power_params.setdefault(
                'power_address', 'qemu://localhost/system')
        else:
            power_params.setdefault('power_address', "")
        power_params.setdefault('username', '')
        power_params.setdefault('power_id', self.system_id)
        power_params.setdefault('power_driver', '')
        power_params.setdefault('power_pass', '')
        power_params.setdefault('power_off_mode', '')

        # The "mac" parameter defaults to the node's boot interace MAC
        # address, but only if not already set.
        if 'mac_address' not in power_params:
            boot_interface = self.get_boot_interface()
            if boot_interface is not None:
                mac = boot_interface.mac_address.get_raw()
                power_params['mac_address'] = mac

        # boot_mode is something that tells the template whether this is
        # a PXE boot or a local HD boot.
        if self.status == NODE_STATUS.DEPLOYED:
            power_params['boot_mode'] = 'local'
        else:
            power_params['boot_mode'] = 'pxe'

        return power_params

    def get_effective_power_info(self):
        """Get information on how to control this node's power.

        Returns a ``(can-be-started, can-be-stopped, power-type,
        power-parameters)`` tuple, where ``can-be-started`` and
        ``can-be-stopped`` are hints, based on the power type and power
        parameters, whether it's even worth trying to control this node's
        power.

        Put another way, if ``can-be-started`` is `False`, the node almost
        certainly cannot be started. If it's `True`, then it may be possible
        to control this node's power, but there are *no* guarantees. The same
        goes for ``can-be-stopped``.

        :return: :py:class:`PowerInfo` (a `namedtuple`)
        """
        power_params = self.get_effective_power_parameters()
        try:
            power_type = self.get_effective_power_type()
        except UnknownPowerType:
            maaslog.warning("%s: Unrecognised power type.", self.hostname)
            return PowerInfo(False, False, False, None, None)
        else:
            if power_type == 'ether_wake':
                mac = power_params.get('mac_address')
                can_be_started = (mac != '' and mac is not None)
                can_be_stopped = False
            else:
                can_be_started = True
                can_be_stopped = True
            can_be_queried = power_type in QUERY_POWER_TYPES
            return PowerInfo(
                can_be_started, can_be_stopped, can_be_queried,
                power_type, power_params,
            )

    def confirm_power_driver_operable(self):
        power_type = self.get_effective_power_type()
        missing_packages = power_driver_check(self.nodegroup.uuid, power_type)
        if len(missing_packages) > 0:
            missing_packages = sorted(missing_packages)
            if len(missing_packages) > 2:
                missing_packages = [", ".join(
                    missing_packages[:-1]), missing_packages[-1]]
            package_list = " and ".join(missing_packages)
            raise PowerActionFail(
                "Power control software is missing from the cluster "
                "controller. To proceed, "
                "install the %s package%s on the %s cluster." % (
                    package_list,
                    "s" if len(missing_packages) > 1 else "",
                    self.nodegroup.cluster_name))

    def acquire(
            self, user, token=None, agent_name='', comment=None):
        """Mark commissioned node as acquired by the given user and token."""
        assert self.owner is None
        assert token is None or token.user == user

        self._create_acquired_filesystems()
        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_ACQUIRE, action='acquire',
            comment=comment)
        self.status = NODE_STATUS.ALLOCATED
        self.owner = user
        self.agent_name = agent_name
        self.token = token
        self.save()
        maaslog.info("%s: allocated to user %s", self.hostname, user.username)

    def set_zone(self, zone):
        """Set this node's zone"""
        old_zone_name = self.zone.name
        self.zone = zone
        self.save()
        maaslog.info("%s: moved from %s zone to %s zone." % (
            self.hostname, old_zone_name, self.zone.name))

    def start_disk_erasing(self, user, comment=None):
        """Erase the disks on a node.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to start and erase the node. This is already
            registered as a post-commit hook; it should not be added a second
            time.
        """
        # Avoid circular imports.
        from metadataserver.user_data.disk_erasing import generate_user_data

        disk_erase_user_data = generate_user_data(node=self)

        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_ERASE_DISK,
            action='start disk erasing', comment=comment)

        # Change the status of the node now to avoid races when starting
        # nodes in bulk.
        self.status = NODE_STATUS.DISK_ERASING
        self.save()

        try:
            # Node.start() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            starting = self._start(user, disk_erase_user_data)
        except Exception as error:
            # We always mark the node as failed here, although we could
            # potentially move it back to the state it was in previously. For
            # now, though, this is safer, since it marks the node as needing
            # attention.
            self.status = NODE_STATUS.FAILED_DISK_ERASING
            self.save()
            maaslog.error(
                "%s: Could not start node for disk erasure: %s",
                self.hostname, error)
            # Let the exception bubble up, since the UI or API will have to
            # deal with it.
            raise
        else:
            # Don't permit naive mocking of start(); it causes too much
            # confusion when testing. Return a Deferred from side_effect.
            assert isinstance(starting, Deferred) or starting is None

            if starting is None:
                starting = post_commit()
                # MAAS cannot start the node itself.
                is_starting = False
            else:
                # MAAS can direct the node to start.
                is_starting = True

            starting.addCallback(
                callOut, self._start_disk_erasing_async, is_starting,
                self.hostname)

            # If there's an error, reset the node's status.
            starting.addErrback(
                callOutToDatabase, self._set_status, self.system_id,
                status=NODE_STATUS.FAILED_DISK_ERASING)

            def eb_start(failure, hostname):
                maaslog.error(
                    "%s: Could not start node for disk erasure: %s",
                    hostname, failure.getErrorMessage())
                return failure  # Propagate.

            return starting.addErrback(eb_start, self.hostname)

    @classmethod
    @asynchronous
    def _start_disk_erasing_async(cls, is_starting, hostname):
        """Start disk erasing, some of the post-commit bits.

        :param is_starting: A boolean indicating if MAAS is able to start this
            node itself, or if manual intervention is needed.
        :param hostname: The node's hostname, for logging.
        """
        if is_starting:
            maaslog.info("%s: Disk erasure started", hostname)
        else:
            maaslog.warning(
                "%s: Could not start node for disk erasure; it "
                "must be started manually", hostname)

    def abort_disk_erasing(self, user, comment=None):
        """Power off disk erasing node and set a failed status.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to stop the node. This is already registered as a
            post-commit hook; it should not be added a second time.
        """
        if self.status != NODE_STATUS.DISK_ERASING:
            raise NodeStateViolation(
                "Cannot abort disk erasing of a non disk erasing node: "
                "node %s is in state %s."
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status]))

        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_ABORT_ERASE_DISK,
            action='abort disk erasing', comment=comment)

        try:
            # Node.stop() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            stopping = self._stop(user)
        except Exception as error:
            maaslog.error(
                "%s: Error when aborting disk erasure: %s",
                self.hostname, error)
            raise
        else:
            # Don't permit naive mocking of stop(); it causes too much
            # confusion when testing. Return a Deferred from side_effect.
            assert isinstance(stopping, Deferred) or stopping is None

            if stopping is None:
                stopping = post_commit()
                # MAAS cannot stop the node itself.
                is_stopping = False
            else:
                # MAAS can direct the node to stop.
                is_stopping = True

            stopping.addCallback(
                callOut, self._abort_disk_erasing_async, is_stopping,
                self.hostname, self.system_id)

            def eb_abort(failure, hostname):
                maaslog.error(
                    "%s: Error when aborting disk erasure: %s",
                    hostname, failure.getErrorMessage())
                return failure  # Propagate.

            return stopping.addErrback(eb_abort, self.hostname)

    @classmethod
    @asynchronous
    def _abort_disk_erasing_async(cls, is_stopping, hostname, system_id):
        """Abort disk erasing, some of the post-commit bits.

        :param is_stopping: A boolean indicating if MAAS is able to stop this
            node itself, or if manual intervention is needed.
        :param hostname: The node's hostname, for logging.
        :param system_id: The system ID for the node.
        """
        d = deferToDatabase(
            cls._set_status, system_id, status=NODE_STATUS.FAILED_DISK_ERASING)
        if is_stopping:
            return d.addCallback(
                callOut, maaslog.info, "%s: Disk erasing aborted", hostname)
        else:
            return d.addCallback(
                callOut, maaslog.warning, "%s: Could not stop node to abort "
                "disk erasure; it must be stopped manually", hostname)

    def abort_operation(self, user, comment=None):
        """Abort the current operation.
        """
        if self.status == NODE_STATUS.DISK_ERASING:
            self.abort_disk_erasing(user, comment)
            return
        if self.status == NODE_STATUS.COMMISSIONING:
            self.abort_commissioning(user, comment)
            return
        if self.status == NODE_STATUS.DEPLOYING:
            self.abort_deploying(user, comment)
            return
        raise NodeStateViolation(
            "Cannot abort in current state: "
            "node %s is in state %s."
            % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status]))

    def release(self, user=None, comment=None):
        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_RELEASE, action='release',
            comment=comment)
        self._release(user)

    def _release(self, user=None):
        """Mark allocated or reserved node as available again and power off.
        """
        maaslog.info("%s: Releasing node", self.hostname)

        # Don't perform stop the node if its already off. Doing so will
        # place an action in the power registry which is not needed and can
        # block a following deploy action. See bug 1453954 for an example of
        # the issue this will cause.
        if self.power_state != POWER_STATE.OFF:
            try:
                self._stop(self.owner)
            except Exception as ex:
                maaslog.error(
                    "%s: Unable to shut node down: %s", self.hostname,
                    unicode(ex))
                raise

        if self.power_state == POWER_STATE.OFF:
            # The node is already powered off; we can deallocate all attached
            # resources and mark the node READY without delay.
            release_to_ready = True
        elif self.get_effective_power_info().can_be_queried:
            # Controlled power type (one for which we can query the power
            # state): update_power_state() will take care of making the node
            # READY, remove the owner, and release the assigned auto IP
            # addresses when the power is finally off.
            self.start_transition_monitor(self.get_releasing_time())
            release_to_ready = False
        else:
            # The node's power cannot be reliably controlled. Frankly, this
            # node is not suitable for use with MAAS. Deallocate all attached
            # resources and mark the node READY without delay because there's
            # not much else we can do.
            release_to_ready = True

        self.status = NODE_STATUS.RELEASING
        self.token = None
        self.agent_name = ''
        self.set_netboot()
        self.osystem = ''
        self.distro_series = ''
        self.license_key = ''
        self.hwe_kernel = None
        self.save()

        # Avoid circular imports
        from metadataserver.models import NodeResult
        # Clear installation results
        NodeResult.objects.filter(
            node=self, result_type=RESULT_TYPE.INSTALLATION).delete()

        # Clear the nodes acquired filesystems.
        self._clear_acquired_filesystems()

        # If this node has non-installable children, remove them.
        self.children.all().delete()

        if release_to_ready:
            # Release IP addresses later to avoid creating deadlocks with
            # other node editing operations (it can be slow).
            post_commit_do(
                reactor.callLater, 0, deferToDatabase,
                self._release_to_ready)

    @transactional
    def _release_to_ready(self):
        """Release all remaining resources and mark the node `READY`.

        Releasing a node can be straightforward or it can be a multi-step
        operation, which can include a reboot in order to erase disks, then a
        final power-down. This method should be the absolute last method
        called.
        """
        try:
            # XXX: This should be a 2-step process: update the database, then
            # perform RPC to mutate DHCP servers. Presently it does everything
            # from within a single database transaction.
            self.release_auto_ips()
        except CannotRemoveHostMap:
            self.mark_failed(None, "Could not release IP addresses")
        else:
            self.status = NODE_STATUS.READY
            self.owner = None
            self.save()

    def release_or_erase(self, user, comment=None):
        """Either release the node or erase the node then release it, depending
        on settings."""
        erase_on_release = Config.objects.get_config(
            'enable_disk_erasing_on_release')
        if erase_on_release:
            self.start_disk_erasing(user, comment)
        else:
            self.release(user, comment)

    def set_netboot(self, on=True):
        """Set netboot on or off."""
        maaslog.debug("%s: Turning on netboot for node", self.hostname)
        self.netboot = on
        self.save()

    def get_deployment_status(self):
        """Return a string repr of the deployment status of this node."""
        mapping = {
            NODE_STATUS.DEPLOYED: "Deployed",
            NODE_STATUS.DEPLOYING: "Deploying",
            NODE_STATUS.FAILED_DEPLOYMENT: "Failed deployment",
        }
        return mapping.get(self.status, "Not in deployment")

    def split_arch(self):
        """Return architecture and subarchitecture, as a tuple."""
        arch, subarch = self.architecture.split('/')
        return (arch, subarch)

    def mark_failed(self, user, comment=None):
        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_MARK_FAILED, action='mark_failed',
            comment=comment)
        self._mark_failed(user, comment)

    def _mark_failed(self, user, comment=None):
        """Mark this node as failed.

        The actual 'failed' state depends on the current status of the
        node.
        """
        new_status = get_failed_status(self.status)
        if new_status is not None:
            self.status = new_status
            self.error_description = comment if comment else ''
            self.save()
            maaslog.error(
                "%s: Marking node failed: %s", self.hostname, comment)
        elif self.status == NODE_STATUS.NEW:
            # Silently ignore, failing a new node makes no sense.
            pass
        elif is_failed_status(self.status):
            # Silently ignore a request to fail an already failed node.
            pass
        else:
            raise NodeStateViolation(
                "The status of the node is %s; this status cannot "
                "be transitioned to a corresponding failed status." %
                self.status)

    def mark_broken(self, user, comment=None):
        """Mark this node as 'BROKEN'.

        If the node is allocated, release it first.
        """
        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_MARK_BROKEN, action='mark broken',
            comment=comment)
        if self.status in RELEASABLE_STATUSES:
            self._release(user)
        # release() normally sets the status to RELEASING and leaves the
        # owner in place, override that here as we're broken.
        self.status = NODE_STATUS.BROKEN
        self.owner = None
        self.error_description = comment if comment else ''
        self.save()

    def mark_fixed(self, user, comment=None):
        """Mark a broken node as fixed and change its state to 'READY'."""
        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_MARK_FIXED, action='mark fixed',
            comment=comment)
        if self.status != NODE_STATUS.BROKEN:
            raise NodeStateViolation(
                "Can't mark a non-broken node as 'Ready'.")
        maaslog.info("%s: Marking node fixed", self.hostname)
        self.status = NODE_STATUS.READY
        self.error_description = ''
        self.osystem = ''
        self.distro_series = ''
        self.hwe_kernel = ''
        self.save()

        # Avoid circular imports
        from metadataserver.models import NodeResult
        # Clear installation results
        NodeResult.objects.filter(
            node=self, result_type=RESULT_TYPE.INSTALLATION).delete()

    @transactional
    def update_power_state(self, power_state):
        """Update a node's power state """
        self.power_state = power_state
        self.power_state_updated = now()
        mark_ready = (
            self.status == NODE_STATUS.RELEASING and
            power_state == POWER_STATE.OFF)
        if mark_ready:
            # Ensure the node is released when it powers down.
            self.stop_transition_monitor()
            self._release_to_ready()
        self.save()

    def is_in_allocated_state(self):
        """Return True if the node is in a state where it is allocated.

        See status in `ALLOCATED_NODE_STATUSES`.
        """
        return self.status in ALLOCATED_NODE_STATUSES

    def set_default_storage_layout(self):
        """Sets the default storage layout.

        This is called after a node has been commissioned to set the default
        storage layout. This is done after commissioning because only then
        will the node actually have some `PhysicalBlockDevice`'s.
        """
        # Do nothing if networking should be skipped.
        if self.skip_storage:
            return
        storage_layout = Config.objects.get_config("default_storage_layout")
        try:
            self.set_storage_layout(storage_layout)
        except StorageLayoutMissingBootDiskError:
            maaslog.error(
                "%s: Unable to set any default storage layout because it "
                "has no writable disks.", self.hostname)
        except StorageLayoutError as e:
            maaslog.error(
                "%s: Failed to configure storage layout: %s",
                self.hostname, e)

    def set_storage_layout(self, layout, params={}, allow_fallback=True):
        """Set storage layout for this node."""
        storage_layout = get_storage_layout_for_node(
            layout, self, params=params)
        if storage_layout is not None:
            used_layout = storage_layout.configure(
                allow_fallback=allow_fallback)
            maaslog.info(
                "%s: Storage layout was set to %s.",
                self.hostname, used_layout)
        else:
            raise StorageLayoutError("Unknown storage layout: %s" % layout)

    def _clear_full_storage_configuration(self):
        """Clear's the full storage configuration for this node.

        This will remove all related models to `PhysicalBlockDevice`'s on
        this node and all `VirtualBlockDevice`'s.

        This is used before commissioning to clear the entire storage model
        except for the `PhysicalBlockDevice`'s. Commissioing will update the
        `PhysicalBlockDevice` information on this node.
        """
        physical_block_devices = self.physicalblockdevice_set.all()
        PartitionTable.objects.filter(
            block_device__in=physical_block_devices).delete()
        Filesystem.objects.filter(
            block_device__in=physical_block_devices).delete()
        for block_device in self.virtualblockdevice_set.all():
            try:
                block_device.filesystem_group.delete(force=True)
            except FilesystemGroup.DoesNotExist:
                # When a filesystem group has multiple virtual block devices
                # it is possible that accessing `filesystem_group` will
                # result in it already being deleted.
                pass

    def _create_acquired_filesystems(self):
        """Copy all filesystems that have a user mountable filesystem to be
        in acquired mode.

        Any modification to the filesystems from this point forward should use
        the acquired filesystems instead of the original. The acquired
        filesystems will be removed on release of the node.
        """
        self._clear_acquired_filesystems()
        filesystems = Filesystem.objects.filter_by_node(self).filter(
            fstype__in=FILESYSTEM_FORMAT_TYPE_CHOICES_DICT, acquired=False)
        for filesystem in filesystems:
            filesystem.id = None
            filesystem.acquired = True
            filesystem.save()

    def _clear_acquired_filesystems(self):
        """Clear the filesystems that are created when the node is acquired.
        """
        filesystems = Filesystem.objects.filter_by_node(self).filter(
            acquired=True)
        filesystems.delete()

    def release_leases(self):
        """Release all leases assigned to the node."""
        ip_leases = StaticIPAddress.objects.filter(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip__isnull=False,
            subnet__isnull=False, interface__node=self)
        removal_mapping = defaultdict(set)
        for ip in ip_leases:
            if ip.ip:
                ngi = ip.subnet.get_managed_cluster_interface()
                if ngi is not None:
                    removal_mapping[ngi.nodegroup].add(ip.ip)
        remove_host_maps_failures = list(
            remove_host_maps(removal_mapping))
        if len(remove_host_maps_failures) != 0:
            # There's only ever one failure here.
            remove_host_maps_failures[0].raiseException()

    def claim_auto_ips(self):
        """Assign IP addresses to all interface links set to AUTO."""
        exclude_addresses = set()
        for interface in self.interface_set.all():
            claimed_ips = interface.claim_auto_ips(
                exclude_addresses=exclude_addresses)
            for ip in claimed_ips:
                exclude_addresses.add(unicode(ip.ip))

    @transactional
    def release_auto_ips(self):
        """Release IP addresses on all interface links set to AUTO."""
        for interface in self.interface_set.all():
            interface.release_auto_ips()

    def _clear_networking_configuration(self):
        """Clear the networking configuration for this node.

        The networking configuration is cleared when a node is going to be
        commissioned. This allows the new commissioning data to create a new
        networking configuration.
        """
        interfaces = self.interface_set.all()
        for interface in interfaces:
            interface.clear_all_links(clearing_config=True)

    def set_initial_networking_configuration(self):
        """Set the networking configuration to the default for this node.

        The networking configuration is set to an initial configuration where
        the boot interface is set to AUTO and all other interfaces are set
        to LINK_UP.

        This is done after commissioning has finished.
        """
        # Do nothing if networking should be skipped.
        if self.skip_networking:
            return

        boot_interface = self.get_boot_interface()
        if boot_interface is None:
            # No interfaces on the node. Nothing to do.
            return

        # Set AUTO mode on the boot interface.
        auto_set = False
        discovered_addresses = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet__isnull=False)
        for ip_address in discovered_addresses:
            boot_interface.link_subnet(
                INTERFACE_LINK_TYPE.AUTO, ip_address.subnet)
            auto_set = True
        if not auto_set:
            # Failed to set AUTO mode on the boot interface. Lets force an
            # AUTO on a managed subnet that is on the same VLAN as the
            # interface. If that fails we just set the interface to DHCP with
            # no subnet defined.
            boot_interface.force_auto_or_dhcp_link()

        # Set LINK_UP mode on all the other enabled interfaces.
        for interface in self.interface_set.all():
            if interface == boot_interface:
                # Skip the boot interface as it has already been configured.
                continue
            if interface.enabled:
                interface.ensure_link_up()

    def get_best_guess_for_default_gateways(self):
        """Return the best guess for the default gateways. This is
        either one IPv4 gateway, one IPv6 gateway, or both.

        This is determined by looking at all interfaces on the node and
        selecting the best possible default gateway IP. The criteria below
        is used to select the best possible gateway:
            1. Managed subnets over unmanaged subnets.
            2. Bond interfaces over physical interfaces.
            3. Node's boot interface over all other interfaces except bonds.
            4. Physical interfaces over VLAN interfaces.
            5. Sticky IP links over user reserved IP links.
            6. User reserved IP links over auto IP links.

        :return: List of tuples with (interface ID, subnet ID, and gateway IP)
        :rtype: list
        """
        cursor = connection.cursor()

        # DISTINCT ON returns the first matching row for any given
        # IP family. Using the query's ordering.
        #
        # For nodes that have disable_ipv4 set, leave out any IPv4 address.
        cursor.execute("""
            SELECT DISTINCT ON (family(subnet.gateway_ip))
                interface.id, subnet.id, subnet.gateway_ip
            FROM maasserver_node AS node
            JOIN maasserver_interface AS interface ON
                interface.node_id = node.id
            JOIN maasserver_interface_ip_addresses AS link ON
                link.interface_id = interface.id
            JOIN maasserver_staticipaddress AS staticip ON
                staticip.id = link.staticipaddress_id
            JOIN maasserver_subnet AS subnet ON
                subnet.id = staticip.subnet_id
            LEFT JOIN maasserver_nodegroupinterface AS ngi ON
                ngi.subnet_id = subnet.id
            LEFT JOIN maasserver_nodegroup AS nodegroup ON
                nodegroup.id = ngi.nodegroup_id
            WHERE
                node.id = %s AND
                subnet.gateway_ip IS NOT NULL AND
                host(subnet.gateway_ip) != '' AND
                staticip.alloc_type != 5 AND /* Ignore DHCP */
                staticip.alloc_type != 6 AND /* Ignore DISCOVERED */
                (
                    node.disable_ipv4 IS FALSE OR
                    family(subnet.gateway_ip) <> 4
                )
            ORDER BY
                family(subnet.gateway_ip),
                nodegroup.status,
                ngi.management DESC,
                CASE
                    WHEN interface.type = 'bond' THEN 1
                    WHEN interface.type = 'physical' AND
                        interface.id = node.boot_interface_id THEN 2
                    WHEN interface.type = 'physical' THEN 3
                    WHEN interface.type = 'vlan' THEN 4
                    WHEN interface.type = 'alias' THEN 5
                    ELSE 6
                END,
                CASE
                    WHEN staticip.alloc_type = 1 /* STICKY */
                        THEN 1
                    WHEN staticip.alloc_type = 4 /* USER_RESERVED */
                        THEN 2
                    WHEN staticip.alloc_type = 0 /* AUTO */
                        THEN 3
                    ELSE staticip.alloc_type
                END,
                interface.id
            """, (self.id,))
        return [
            (found[0], found[1], found[2])
            for found in cursor.fetchall()
        ]

    def _get_best_interface_from_gateway_link(self, gateway_link):
        """Return the best interface for the `gateway_link` and this node."""
        return gateway_link.interface_set.filter(
            node=self).order_by('type', 'id').first().id

    def _get_gateway_tuple(self, gateway_link):
        """Return a tuple for the interface id, subnet id, and gateway IP for
        the `gateway_link`."""
        return (
            self._get_best_interface_from_gateway_link(
                gateway_link),
            gateway_link.subnet.id,
            gateway_link.subnet.gateway_ip,
            )

    def _get_gateway_tuple_by_family(self, gateways, ip_family):
        """Return the gateway tuple from `gateways` that is in the IP address
        family."""
        for gateway in gateways:
            if IPAddress(gateway[2]).version == ip_family:
                return gateway
        return None

    def get_default_gateways(self):
        """Return the default gateways.

        :return: Return a tuple or tuples with IPv4 and IPv6 gateway
            information.
        :rtype: tuple
        """
        # Get the set gateways on the node.
        gateway_ipv4 = None
        gateway_ipv6 = None
        if self.gateway_link_ipv4 is not None:
            subnet = self.gateway_link_ipv4.subnet
            if subnet is not None:
                if subnet.gateway_ip:
                    gateway_ipv4 = self._get_gateway_tuple(
                        self.gateway_link_ipv4)
        if self.gateway_link_ipv6 is not None:
            subnet = self.gateway_link_ipv6.subnet
            if subnet is not None:
                if subnet.gateway_ip:
                    gateway_ipv6 = self._get_gateway_tuple(
                        self.gateway_link_ipv6)

        # Early out if we already have both gateways.
        if gateway_ipv4 and gateway_ipv6:
            return (gateway_ipv4, gateway_ipv6)

        # Get the best guesses for the missing IP families.
        found_gateways = self.get_best_guess_for_default_gateways()
        if not gateway_ipv4:
            gateway_ipv4 = self._get_gateway_tuple_by_family(
                found_gateways, IPADDRESS_FAMILY.IPv4)
        if not gateway_ipv6:
            gateway_ipv6 = self._get_gateway_tuple_by_family(
                found_gateways, IPADDRESS_FAMILY.IPv6)
        return (gateway_ipv4, gateway_ipv6)

    def get_boot_purpose(self):
        """
        Return a suitable "purpose" for this boot, e.g. "install".
        """
        # XXX: allenap bug=1031406 2012-07-31: The boot purpose is
        # still in flux. It may be that there will just be an
        # "ephemeral" environment and an "install" environment, and
        # the differing behaviour between, say, enlistment and
        # commissioning - both of which will use the "ephemeral"
        # environment - will be governed by varying the preseed or PXE
        # configuration.
        if self.status in COMMISSIONING_LIKE_STATUSES:
            # It is commissioning or disk erasing. The environment (boot
            # images, kernel options, etc for erasing is the same as that
            # of commissioning.
            return "commissioning"
        elif self.status == NODE_STATUS.DEPLOYING:
            # Install the node if netboot is enabled,
            # otherwise boot locally.
            if self.netboot:
                # Avoid circular imports.
                from maasserver.preseed import get_deploying_preseed_type_for
                preseed_type = get_deploying_preseed_type_for(self)
                if preseed_type == PRESEED_TYPE.CURTIN:
                    return "xinstall"
                else:
                    return "install"
            else:
                return "local"
        elif self.status == NODE_STATUS.DEPLOYED:
            return "local"
        else:
            return "poweroff"

    def get_boot_interface(self):
        """Get the boot interface this node is expected to boot from.

        Normally, this will be the boot interface last used in a
        pxeconfig() API request for the node, as recorded in the
        'boot_interface' property. However, if the node hasn't booted since
        the 'boot_interface' property was added to the Node model, this will
        return the node's first interface instead.
        """
        if self.boot_interface is not None:
            return self.boot_interface

        # Only use "all" and perform the sorting manually to stop extra queries
        # when the `interface_set` is prefetched.
        interfaces = sorted(self.interface_set.all(), key=attrgetter('id'))
        if len(interfaces) == 0:
            return None
        return interfaces[0]

    def get_pxe_mac_vendor(self):
        """Return the vendor of the MAC address the node booted from."""
        boot_interface = self.get_boot_interface()
        if boot_interface is None:
            return None
        else:
            return get_vendor_for_mac(boot_interface.mac_address.get_raw())

    def get_extra_macs(self):
        """Get the MACs other that the one the node booted from."""
        boot_interface = self.get_boot_interface()
        # Use all here and not filter on type so the precache is used.
        return [
            interface.mac_address
            for interface in self.interface_set.all()
            if (interface != boot_interface and
                interface.type == INTERFACE_TYPE.PHYSICAL)
        ]

    def substatus_message(self):
        """Returns a string representation of the most recent event description
        (supplied through the status API) associated with this node, None if
        there are no events."""
        from maasserver.models.event import Event  # Avoid circular import.
        # Id's have a lower (non-zero under heavy load) chance of being out of
        # order than of two timestamps colliding.
        event = Event.objects.filter(node=self).order_by('-id').first()
        return event.description if event is not None else None

    def substatus_action(self):
        """Returns a string representation of the most recent event action name
        (supplied through the status API) associated with this node, None if
        there are no events."""
        from maasserver.models.event import Event  # Avoid circular import.
        # Id's have a lower (non-zero under heavy load) chance of being out of
        # order than of two timestamps colliding.
        event = Event.objects.filter(node=self).order_by('-id').first()
        return event.action if event is not None else None

    @property
    def substatus_name(self):
        """Returns the subtatus of the nome as a user-friendly string."""
        return NODE_STATUS_CHOICES_DICT[self.status]

    def is_boot_interface_on_managed_interface(self):
        """Return True if the boot interface is attached to a managed cluster
        interface."""
        boot_interface = self.get_boot_interface()
        if boot_interface is not None:
            cluster_interface = boot_interface.get_cluster_interface()
            if cluster_interface is not None:
                return cluster_interface.is_managed
        return False

    @transactional
    def start(self, user, user_data=None, comment=None):
        if not user.has_perm(NODE_PERMISSION.EDIT, self):
            # You can't start a node you don't own unless you're an admin.
            raise PermissionDenied()
        event = EVENT_TYPES.REQUEST_NODE_START
        # if status is ALLOCATED, this start is actually for a deployment
        if self.status == NODE_STATUS.ALLOCATED:
            event = EVENT_TYPES.REQUEST_NODE_START_DEPLOYMENT
        self._register_request_event(
            user, event, action='start', comment=comment)
        return self._start(user, user_data)

    @transactional
    def _start(self, user, user_data=None):
        """Request on given user's behalf that the node be started up.

        :param user: Requesting user.
        :type user: User_
        :param user_data: Optional blob of user-data to be made available to
            the node through the metadata service. If not given, any previous
            user data is used.
        :type user_data: unicode

        :raise StaticIPAddressExhaustion: if there are not enough IP addresses
            left in the static range for this node to get all the addresses it
            needs.
        :raise PermissionDenied: If `user` does not have permission to
            start this node.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to start the node. This is already registed as a
            post-commit hook; it should not be added a second time. If it has
            not been possible to start the node because the power controller
            does not support it, `None` will be returned. The node must be
            powered on manually.
        """
        # Avoid circular imports.
        from metadataserver.models import NodeUserData

        if not user.has_perm(NODE_PERMISSION.EDIT, self):
            # You can't start a node you don't own unless you're an admin.
            raise PermissionDenied()

        # Record the user data for the node. Note that we do this
        # whether or not we can actually send power commands to the
        # node; the user may choose to start it manually.
        NodeUserData.objects.set_user_data(self, user_data)

        if self.status == NODE_STATUS.ALLOCATED:
            # Claim AUTO IP addresses for the node if it's ALLOCATED.
            self.claim_auto_ips()
            transition_monitor = (
                TransitionMonitor.fromNode(self)
                .within(seconds=self.get_deployment_time())
                .status_should_be(self.status))
            self._start_deployment()
        else:
            transition_monitor = None

        power_info = self.get_effective_power_info()
        if not power_info.can_be_started:
            # The node can't be powered on by MAAS, so return early.
            # Everything we've done up to this point is still valid;
            # this is not an error state.
            return None
        self.confirm_power_driver_operable()

        def pc_power_on_node(system_id, hostname, nodegroup_uuid, power_info):
            d = power_on_node(system_id, hostname, nodegroup_uuid, power_info)
            if transition_monitor is not None:
                d.addCallback(
                    callOut, self._start_transition_monitor_async,
                    transition_monitor, hostname)
            d.addErrback(callOutToDatabase, self.release_auto_ips)
            return d

        return post_commit_do(
            pc_power_on_node, self.system_id, self.hostname,
            self.nodegroup.uuid, power_info)

    @transactional
    def stop(self, user, stop_mode='hard', comment=None):
        if not user.has_perm(NODE_PERMISSION.EDIT, self):
            # You can't stop a node you don't own unless you're an admin.
            raise PermissionDenied()
        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_STOP, action='stop',
            comment=comment)
        return self._stop(user, stop_mode)

    @transactional
    def _stop(self, user, stop_mode='hard'):
        """Request that the node be powered down.

        :param user: Requesting user.
        :type user: User_
        :param stop_mode: Power off mode - usually 'soft' or 'hard'.
        :type stop_mode: unicode

        :raise PermissionDenied: If `user` does not have permission to
            stop this node.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to stop the node. This is already registed as a
            post-commit hook; it should not be added a second time. If it has
            not been possible to stop the node because the power controller
            does not support it, `None` will be returned. The node must be
            powered off manually.
        """
        if not user.has_perm(NODE_PERMISSION.EDIT, self):
            # You can't stop a node you don't own unless you're an admin.
            raise PermissionDenied()

        power_info = self.get_effective_power_info()
        if not power_info.can_be_stopped:
            # We can't stop this node, so just return; trying to stop a
            # node we don't know how to stop isn't an error state, but
            # it's a no-op.
            return None
        self.confirm_power_driver_operable()

        # Smuggle in a hint about how to power-off the self.
        power_info.power_parameters['power_off_mode'] = stop_mode

        # Request that the node be powered off post-commit.
        return post_commit_do(
            power_off_node, self.system_id, self.hostname,
            self.nodegroup.uuid, power_info)

    @classmethod
    @transactional
    def _set_status(cls, system_id, status):
        """Set the status of the node identified by `system_id`.

        This is a convenience for use as a call-back.
        """
        node = cls.objects.get(system_id=system_id)
        node.status = status
        node.save()


# Piston serializes objects based on the object class.
# Here we define a proxy class so that we can specialize how devices are
# serialized on the API.
class Device(Node):
    """A non-installable node."""

    objects = DeviceManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        super(Device, self).__init__(installable=False, *args, **kwargs)
