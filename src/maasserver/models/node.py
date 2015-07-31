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
from itertools import chain
from operator import attrgetter
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
    Q,
    SET_DEFAULT,
    SET_NULL,
    TextField,
)
from django.shortcuts import get_object_or_404
import djorm_pgarray.fields
from maasserver import DefaultMeta
from maasserver.clusterrpc.dhcp import (
    remove_host_maps,
    update_host_maps,
)
from maasserver.clusterrpc.power import (
    power_off_node,
    power_on_node,
)
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_BOOT,
    NODE_BOOT_CHOICES,
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    NODEGROUPINTERFACE_MANAGEMENT,
    POWER_STATE,
    POWER_STATE_CHOICES,
    PRESEED_TYPE,
)
from maasserver.exceptions import (
    NodeStateViolation,
    StaticIPAddressTypeClash,
)
from maasserver.fields import (
    JSONObjectField,
    MAC,
)
from maasserver.models.candidatename import gen_candidate_names
from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.dhcplease import DHCPLease
from maasserver.models.filesystem import Filesystem
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.interface import Interface
from maasserver.models.licensekey import LicenseKey
from maasserver.models.macaddress import (
    MACAddress,
    update_mac_cluster_interfaces,
)
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
from maasserver.utils import (
    get_db_state,
    strip_domain,
)
from maasserver.utils.dns import validate_hostname
from maasserver.utils.mac import get_vendor_for_mac
from maasserver.utils.orm import (
    get_one,
    post_commit,
    post_commit_do,
    transactional,
)
from metadataserver.enum import RESULT_TYPE
from netaddr import IPAddress
from piston.models import Token
from provisioningserver.logger import get_maas_logger
from provisioningserver.power.poweraction import UnknownPowerType
from provisioningserver.rpc.power import QUERY_POWER_TYPES
from provisioningserver.utils.enum import map_enum_reverse
from provisioningserver.utils.twisted import (
    asynchronous,
    callOut,
    callOutToThread,
    FOREVER,
    synchronous,
)
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread


maaslog = get_maas_logger("node")


def generate_node_system_id():
    return 'node-%s' % uuid1()

# Return type from `get_effective_power_info`.
PowerInfo = namedtuple("PowerInfo", (
    "can_be_started", "can_be_stopped", "can_be_queried", "power_type",
    "power_parameters"))


class BaseNodeManager(Manager):
    """A utility to manage the collection of Nodes."""

    extra_filters = {}

    def get_queryset(self):
        return super(
            BaseNodeManager, self).get_queryset().filter(**self.extra_filters)

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
        :type token: piston.models.Token.
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
        max_length=10, choices=NODE_STATUS_CHOICES, editable=False,
        default=NODE_STATUS.DEFAULT)

    owner = ForeignKey(
        User, default=None, blank=True, null=True, editable=False)

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
        default=Zone.objects.get_default_zone, editable=True, db_index=True,
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

    # Record the MAC address for the interface the node last PXE booted from.
    # This will be used for determining which MAC address to create a static
    # IP reservation for when starting a node.
    pxe_mac = ForeignKey(
        MACAddress, default=None, blank=True, null=True, editable=False,
        related_name='+', on_delete=SET_NULL)

    # Note that the ordering of the managers is meaningul.  More precisely, the
    # first manager defined is important: see
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

    def start_deployment(self):
        """Mark a node as being deployed."""
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
            self.mark_failed(
                "Node operation '%s' timed out after %s." % (
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
        # The static IP addresses are assigned/removed when a node is
        # allocated/deallocated.
        # The dynamic IP addresses are used by enlisting or commissioning
        # nodes.  This information is re-built periodically based on the
        # content of the DHCP lease file, the DB mappings can thus contain
        # outdated information for a short time.  They are returned here
        # for backward-compatiblity reasons (the static IP addresses were
        # introduced after the dynamic IP addresses) as only the static
        # mappings are guaranteed to be, well, static.
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
        # If the macaddresses and the ips have been prefetched (a la
        # nodes = nodes.prefetch_related('macaddress_set__ip_addresses')),
        # use the cache.
        mac_cache = self.macaddress_set.all()._result_cache
        can_use_cache = (
            mac_cache is not None and
            (
                len(mac_cache) == 0
                or
                (
                    len(mac_cache) > 0 and
                    # If the first MAC has its IP addresses cached, assume
                    # we can use the cache for all the MACs.
                    mac_cache[0].ip_addresses.all()._result_cache is not None
                )
            )
        )
        if can_use_cache:
            # The cache is populated: return the static IP addresses of all the
            # node's MAC addresses.
            macs = self.macaddress_set.all()
            node_ip_addresses = [
                [ipaddr.ip for ipaddr in mac.ip_addresses.all()]
                for mac in macs
            ]
            return list(chain(*node_ip_addresses))
        else:
            return StaticIPAddress.objects.filter(
                macaddress__node=self).values_list('ip', flat=True)

    def dynamic_ip_addresses(self):
        """Dynamic IP addresses allocated to this node."""
        macs = [mac.mac_address for mac in self.macaddress_set.all()]
        dhcpleases_qs = self.nodegroup.dhcplease_set.all()
        if dhcpleases_qs._result_cache is not None:
            # If the dhcp lease set has been pre-fetched: use it to
            # extract the IP addresses associated with the nodes' MAC
            # addresses.
            return [lease.ip for lease in dhcpleases_qs if lease.mac in macs]
        else:
            query = dhcpleases_qs.filter(mac__in=macs)
            return query.values_list('ip', flat=True)

    def get_static_ip_mappings(self):
        """Return node's static addresses, and their MAC addresses.

        :return: A list of (IP, MAC) tuples, both in string form.
        """
        macs = self.macaddress_set.all().prefetch_related('ip_addresses')
        return [
            (sip.ip, mac.mac_address)
            for mac in macs
            for sip in mac.ip_addresses.all()
            ]

    def mac_addresses_on_managed_interfaces(self):
        """Return MACAddresses for this node that have a managed cluster
        interface."""
        # Avoid circular imports
        from maasserver.models import MACAddress
        unmanaged = NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED
        macs = MACAddress.objects.none()
        if not self.installable and self.parent is not None:
            pxe_MAC_parent = self.parent.get_pxe_mac()
            is_pxe_MAC_on_managed_interface = (
                pxe_MAC_parent.cluster_interface is not None and
                pxe_MAC_parent.cluster_interface.management != unmanaged
            )
            if is_pxe_MAC_on_managed_interface:
                macs |= MACAddress.objects.filter(id=self.get_primary_mac().id)
        macs |= MACAddress.objects.filter(
            node=self, cluster_interface__isnull=False).exclude(
            cluster_interface__management=unmanaged)
        return macs

    def tag_names(self):
        # We don't use self.tags.values_list here because this does not
        # take advantage of the cache.
        return [tag.name for tag in self.tags.all()]

    def get_interfaces(self):
        """Return `QuerySet` for all the interfaces of this node."""
        RECURSIVE_INTERFACE_QUERY = """
            WITH RECURSIVE search_interfaces(id) AS (
                    SELECT i.id
                    FROM maasserver_interface i, maasserver_macaddress m
                    WHERE m.id = i.mac_id AND m.node_id = %s
                UNION ALL
                    SELECT link.child_id
                    FROM search_interfaces si,
                    maasserver_interfacerelationship link
                WHERE si.id = link.parent_id
            )
            SELECT * FROM maasserver_interface
            WHERE id in (SELECT id FROM search_interfaces);
        """
        cursor = connection.cursor()
        cursor.execute(RECURSIVE_INTERFACE_QUERY, [self.id])
        results = cursor.fetchall()
        ids = [res[0] for res in results]
        # Materialize the list of ID (that list will have a reasonnable size)
        # and return a QuerySet instead of using Manager.raw() that returns a
        # (very limited) RawQuerySet.
        return Interface.objects.filter(id__in=ids)

    def clean_pxe_mac(self):
        """Check that this Node's PXE MAC (if present) belongs to this Node.

        It's possible, though very unlikely, that the PXE MAC we are seeing
        is already assigned to another Node. If this happens, we need to
        catch the failure as early as possible.
        """
        if (self.pxe_mac is not None and self.id is not None and
                self.id != self.pxe_mac.node_id):
                raise ValidationError(
                    {'pxe_mac': ["Must be one of the node's mac addresses."]})

    def clean_status(self):
        """Check a node's status transition against the node-status FSM."""
        old_status = get_db_state(self, 'status')
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
            pass
        else:
            # Transition not permitted.
            error_text = "Invalid transition: %s -> %s." % (
                NODE_STATUS_CHOICES_DICT.get(old_status, "Unknown"),
                NODE_STATUS_CHOICES_DICT.get(self.status, "Unknown"),
                )
            raise NodeStateViolation(error_text)

    def clean_architecture(self):
        if self.architecture == '' and self.installable:
            raise ValidationError(
                {'architecture':
                    ["Architecture must be defined for installable nodes."]})

    def clean(self, *args, **kwargs):
        super(Node, self).clean(*args, **kwargs)
        self.clean_status()
        self.clean_architecture()
        self.clean_pxe_mac()

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

    def add_mac_address(self, mac_address):
        """Add a new MAC address to this `Node`.

        Returns the corresponding MACAddress object if mac_address represents a
        MACAddress already assigned to this node.

        Returns a new MACAddress object assigned to this node if this address
        is not assigned to any node in the system.

        Raises a ValidationError if mac_address corresponds to a MACAddress
        already assigned to a different node.

        :param mac_address: The MAC address to be added.
        :type mac_address: unicode
        :raises: django.core.exceptions.ValidationError_

        .. _django.core.exceptions.ValidationError: https://
           docs.djangoproject.com/en/dev/ref/exceptions/
           #django.core.exceptions.ValidationError

        """

        # Avoid circular imports
        from maasserver.models import MACAddress

        # Create the MACAddress, but only if it does not exist.
        try:
            mac = MACAddress(mac_address=mac_address, node=self)
            mac.save()
        except ValidationError as e:
            if any(("is not a valid MAC address." in m
                    for m in e.message_dict['mac_address'])):
                raise e  # will cause the stack to return an HTTP error status
            elif any((u'This MAC address is already registered.' == m
                      for m in e.message_dict['mac_address'])):
                mac = MACAddress.objects.get(mac_address=mac_address)
                if mac.node_id != self.id:
                    # This MACAddress is assigned to another node
                    raise e

        # See if there's a lease for this MAC and set its
        # cluster_interface if so.
        leases = DHCPLease.objects.filter(
            nodegroup=self.nodegroup, mac=mac.mac_address)
        lease = get_one(leases)
        if lease is not None:
            update_mac_cluster_interfaces(lease.ip, lease.mac, self.nodegroup)

        return mac

    def remove_mac_address(self, mac_address):
        """Remove a MAC address from this `Node`.

        :param mac_address: The MAC address to be removed.
        :type mac_address: string

        """
        # Avoid circular imports
        from maasserver.models import MACAddress

        mac = MACAddress.objects.get(mac_address=mac_address, node=self)
        if mac:
            mac.delete()

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
    def start_commissioning(self, user):
        """Install OS and self-test a new node.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to start and commission the node. This is already
            registered as a post-commit hook; it should not be added a second
            time.
        """
        # Avoid circular imports.
        from metadataserver.user_data.commissioning import generate_user_data
        from metadataserver.models import NodeResult

        commissioning_user_data = generate_user_data(node=self)
        # Clear any existing commissioning results.
        NodeResult.objects.clear_results(self)
        # We need to mark the node as COMMISSIONING now to avoid a race
        # when starting multiple nodes. We hang on to old_status just in
        # case the power action fails.
        old_status = self.status
        self.status = NODE_STATUS.COMMISSIONING
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
            starting = self.start(user, user_data=commissioning_user_data)
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
                callOutToThread, self._set_status, self.system_id,
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
    def abort_commissioning(self, user):
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

        # Prepare a transition monitor for later.
        monitor = TransitionMonitor.fromNode(self)

        try:
            # Node.stop() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            stopping = self.stop(user)
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
    def abort_deploying(self, user):
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

        # Prepare a transition monitor for later.
        monitor = TransitionMonitor.fromNode(self)

        try:
            # Node.stop() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            stopping = self.stop(user)
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
        d = deferToThread(cls._set_status, system_id, status=NODE_STATUS.NEW)
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
        d = deferToThread(cls._set_status, system_id,
                          status=NODE_STATUS.ALLOCATED)
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

        # Ensure that all static IPs are deleted, and keep track of the IP
        # addresses so we can delete the associated host maps.
        static_ips = StaticIPAddress.objects.delete_by_node(self)
        # Collect other IP addresses (likely in the dynamic range) that we
        # should delete host maps for. We need to do this because MAAS used to
        # declare host maps in the dynamic range. At some point we can stop
        # removing host maps from the dynamic range, once we decide that
        # enough time has passed.
        macs = self.mac_addresses_on_managed_interfaces().values_list(
            'mac_address', flat=True)
        leases = DHCPLease.objects.filter(
            nodegroup=self.nodegroup, mac__in=macs)
        leased_ips = leases.values_list("ip", flat=True)
        # Delete host maps for all addresses linked to this node.
        self.delete_host_maps(set().union(static_ips, leased_ips))
        # Delete the related mac addresses. The DHCPLease objects
        # corresponding to these MACs will be deleted as well. See
        # maasserver/models/dhcplease:delete_lease().
        self.macaddress_set.all().delete()

        super(Node, self).delete()

    def delete_host_maps(self, for_ips):
        """Delete any host maps for IPs allocated to this node.

        This should probably live on `NodeGroup`.

        :param for_ips: The set of IP addresses to remove host maps for.
        :type for_ips: `set`
        """
        assert isinstance(for_ips, set), "%r is not a set" % (for_ips,)
        if len(for_ips) > 0:
            maaslog.info("%s: Deleting DHCP host maps", self.hostname)
            removal_mapping = {self.nodegroup: for_ips}
            remove_host_maps_failures = list(
                remove_host_maps(removal_mapping))
            if len(remove_host_maps_failures) != 0:
                # There's only ever one failure here.
                raise remove_host_maps_failures[0].raiseException()

    def set_random_hostname(self):
        """Set `hostname` from a shuffled list of candidate names.

        See `gen_candidate_names`.

        http://en.wikipedia.org/wiki/Hostname#Restrictions_on_valid_host_names
        """
        for new_hostname in gen_candidate_names():
            self.hostname = "%s" % new_hostname
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

    def get_primary_mac(self):
        """Return the primary :class:`MACAddress` for this node."""
        macs = self.macaddress_set.order_by('created')[:1]
        if len(macs) > 0:
            return macs[0]
        else:
            return None

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

        # The "mac" parameter defaults to the node's primary MAC
        # address, but only if not already set.
        if 'mac_address' not in power_params:
            primary_mac = self.get_primary_mac()
            if primary_mac is not None:
                mac = primary_mac.mac_address.get_raw()
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

    def acquire(self, user, token=None, agent_name='', storage_layout=None):
        """Mark commissioned node as acquired by the given user and token."""
        assert self.owner is None
        assert token is None or token.user == user
        self.status = NODE_STATUS.ALLOCATED
        self.owner = user
        self.agent_name = agent_name
        self.token = token
        self.save()
        maaslog.info("%s: allocated to user %s", self.hostname, user.username)

        # Set the storage layout for the node.
        if storage_layout is None:
            storage_layout = Config.objects.get_config(
                "default_storage_layout")
        try:
            self.set_storage_layout(storage_layout)
        except StorageLayoutError:
            # Catch all storage errors setting up the layout.
            # `set_storage_layout` handles the logging of error messages.
            pass

    def set_storage_layout(self, layout, params={}, allow_fallback=True):
        """Set storage layout for this node."""
        if self.status != NODE_STATUS.ALLOCATED:
            raise NodeStateViolation(
                "Cannot set the storage layout when node is %s, "
                "it must be %s." % (
                    NODE_STATUS_CHOICES_DICT[self.status],
                    NODE_STATUS_CHOICES_DICT[NODE_STATUS.ALLOCATED],
                    ))
        storage_layout = get_storage_layout_for_node(
            layout, self, params=params)
        if storage_layout is not None:
            try:
                used_layout = storage_layout.configure(
                    allow_fallback=allow_fallback)
                maaslog.info(
                    "%s: storage layout was set to %s.",
                    self.hostname, used_layout)
            except StorageLayoutMissingBootDiskError:
                maaslog.error(
                    "%s: missing boot disk; no storage layout can be "
                    "applied.", self.hostname)
                raise
            except StorageLayoutError as e:
                maaslog.error(
                    "%s: failed to configure storage layout: %s",
                    self.hostname, e)
                raise
        else:
            maaslog.error(
                "%s: unable to configure storage layout; unknown storage "
                "layout '%s'.", self.hostname, layout)
            raise StorageLayoutError("Unknown storage layout: %s" % layout)

    def set_zone(self, zone):
        """Set this node's zone"""
        old_zone_name = self.zone.name
        self.zone = zone
        self.save()
        maaslog.info("%s: moved from %s zone to %s zone." % (
            self.hostname, old_zone_name, self.zone.name))

    def start_disk_erasing(self, user):
        """Erase the disks on a node.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to start and erase the node. This is already
            registered as a post-commit hook; it should not be added a second
            time.
        """
        # Avoid circular imports.
        from metadataserver.user_data.disk_erasing import generate_user_data

        disk_erase_user_data = generate_user_data(node=self)
        # Change the status of the node now to avoid races when starting
        # nodes in bulk.
        self.status = NODE_STATUS.DISK_ERASING
        self.save()

        try:
            # Node.start() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            starting = self.start(user, user_data=disk_erase_user_data)
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
                callOutToThread, self._set_status, self.system_id,
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

    def abort_disk_erasing(self, user):
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

        try:
            # Node.stop() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            stopping = self.stop(user)
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
        d = deferToThread(
            cls._set_status, system_id, status=NODE_STATUS.FAILED_DISK_ERASING)
        if is_stopping:
            return d.addCallback(
                callOut, maaslog.info, "%s: Disk erasing aborted", hostname)
        else:
            return d.addCallback(
                callOut, maaslog.warning, "%s: Could not stop node to abort "
                "disk erasure; it must be stopped manually", hostname)

    def abort_operation(self, user):
        """Abort the current operation.
        This currently only supports aborting Disk Erasing.
        """
        if self.status == NODE_STATUS.DISK_ERASING:
            self.abort_disk_erasing(user)
            return
        if self.status == NODE_STATUS.COMMISSIONING:
            self.abort_commissioning(user)
            return
        if self.status == NODE_STATUS.DEPLOYING:
            self.abort_deploying(user)
            return

        raise NodeStateViolation(
            "Cannot abort in current state: "
            "node %s is in state %s."
            % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status]))

    def release(self):
        """Mark allocated or reserved node as available again and power off.
        """
        maaslog.info("%s: Releasing node", self.hostname)

        # Don't perform stop the node if its already off. Doing so will
        # place an action in the power registry which is not needed and can
        # block a following deploy action. See bug 1453954 for an example of
        # the issue this will cause.
        if self.power_state != POWER_STATE.OFF:
            try:
                self.stop(self.owner)
            except Exception as ex:
                maaslog.error(
                    "%s: Unable to shut node down: %s", self.hostname,
                    unicode(ex))
                raise

        deallocate_ip_address = True
        if self.power_state == POWER_STATE.OFF:
            # Node is already off.
            self.status = NODE_STATUS.READY
            self.owner = None
        elif self.get_effective_power_info().can_be_queried:
            # Controlled power type (one for which we can query the power
            # state): update_power_state() will take care of making the node
            # READY, remove the owned, and deallocate the assigned static ip
            # address when the power is finally off.
            deallocate_ip_address = False
            self.status = NODE_STATUS.RELEASING
            self.start_transition_monitor(self.get_releasing_time())
        else:
            # Uncontrolled power type (one for which we can't query the power
            # state): mark the node ready.
            self.status = NODE_STATUS.READY
            self.owner = None
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

        # Do these after updating the node to avoid creating deadlocks with
        # other node editing operations.
        if deallocate_ip_address:
            self.deallocate_static_ip_addresses_later()

        # Clear the nodes storage configuration.
        self._clear_storage_configuration()

        # If this node has non-installable children, remove them.
        self.children.all().delete()

    def release_or_erase(self):
        """Either release the node or erase the node then release it, depending
        on settings."""
        erase_on_release = Config.objects.get_config(
            'enable_disk_erasing_on_release')
        if erase_on_release:
            self.start_disk_erasing(self.owner)
            return

        self.release()

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

    def mark_failed(self, error_description):
        """Mark this node as failed.

        The actual 'failed' state depends on the current status of the
        node.
        """
        new_status = get_failed_status(self.status)
        if new_status is not None:
            self.status = new_status
            self.error_description = error_description
            self.save()
            maaslog.error(
                "%s: Marking node failed: %s", self.hostname,
                error_description)
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

    def mark_broken(self, error_description):
        """Mark this node as 'BROKEN'.

        If the node is allocated, release it first.
        """
        if self.status in RELEASABLE_STATUSES:
            self.release()
        # release() normally sets the status to RELEASING and leaves the
        # owner in place, override that here as we're broken.
        self.status = NODE_STATUS.BROKEN
        self.owner = None
        self.error_description = error_description
        self.save()

    def mark_fixed(self):
        """Mark a broken node as fixed and change its state to 'READY'."""
        if self.status != NODE_STATUS.BROKEN:
            raise NodeStateViolation(
                "Can't mark a non-broken node as 'Ready'.")
        maaslog.info("%s: Marking node fixed", self.hostname)
        self.status = NODE_STATUS.READY
        self.error_description = ''
        self.osystem = ''
        self.distro_series = ''
        self.save()

        # Avoid circular imports
        from metadataserver.models import NodeResult
        # Clear installation results
        NodeResult.objects.filter(
            node=self, result_type=RESULT_TYPE.INSTALLATION).delete()

    def update_power_state(self, power_state):
        """Update a node's power state """
        self.power_state = power_state
        self.power_state_updated = now()
        mark_ready = (
            self.status == NODE_STATUS.RELEASING and
            power_state == POWER_STATE.OFF)
        if mark_ready:
            # Ensure the node is fully released after a successful power
            # down.
            self.status = NODE_STATUS.READY
            self.owner = None
            self.stop_transition_monitor()
            self.deallocate_static_ip_addresses_later()
        self.save()

    def claim_static_ip_addresses(
            self, mac=None, alloc_type=IPADDRESS_TYPE.AUTO,
            requested_address=None, update_host_maps=True):
        """Assign static IPs to a node's MAC.
        If no MAC is specified, defaults to its PXE MAC.

        By default, assigns IP addresses of type AUTO. If a different type
        is desired (such as STICKY), the optional alloc_type parameter can
        be used to override it.

        By default, any address inside the cluster's static range can be
        used. If the optional requested_address parameter is specified,
        will attempt to obtain it.

        :return: A list of ``(ip-address, mac-address)`` tuples.
        :raises: `StaticIPAddressExhaustion` if there are not enough IPs left.
        :raises: `StaticIPAddressUnavailable` if the supplied
        requested_address is already in use.
        """
        if mac is None:
            mac = self.get_pxe_mac()
            if mac is None:
                return []

        try:
            static_ips = mac.claim_static_ips(
                alloc_type=alloc_type, requested_address=requested_address,
                update_host_maps=update_host_maps)
        except StaticIPAddressTypeClash:
            # There's already a non-AUTO IP.
            return []

        # Return a list instead of yielding mappings as they're ready
        # because it's all-or-nothing (hence the atomic context).
        return [(static_ip.ip, unicode(mac)) for static_ip in static_ips]

    @staticmethod
    def update_nodegroup_host_maps(nodegroups, claims):
        """Update host maps for the given MAC->IP mappings.

        If a nodegroup list is given, update all of them.  If not, only
        update the nodegroup of the node.
        """
        static_mappings = defaultdict(dict)
        for nodegroup in nodegroups:
            static_mappings[nodegroup].update(claims)
        update_host_maps_failures = list(
            update_host_maps(static_mappings))
        num_failures = len(update_host_maps_failures)
        if num_failures != 0:
            # We've hit an error, so release any IPs we've claimed
            # and then raise the error for the call site to
            # handle.
            # StaticIPAddress.objects.deallocate_by_node(self)
            # StaticIPAddress.objects.deallocate_by_node()
            for claim in claims:
                StaticIPAddress.objects.get(ip=claim[0]).deallocate()

            # We know there's only one error because we only
            # sent one mapping to update_host_maps(), so we
            # extract the exception from the Failure and raise
            # it.
            raise update_host_maps_failures[0].raiseException()

    def update_host_maps(self, claims, nodegroups=None):
        """Update host maps for the given MAC->IP mappings.

        If a nodegroup list is given, update all of them.  If not, only
        update the nodegroup of the node.
        """

        # For some reason, we can call this method on a Node, but the intent
        # is to update nodegroups not on this node. That's why it's not
        # an "append" here.
        if nodegroups is None:
            nodegroups = [self.nodegroup]

        self.update_nodegroup_host_maps(nodegroups, claims)

    def deallocate_static_ip_addresses(
            self, alloc_type=IPADDRESS_TYPE.AUTO, ip=None):
        """Release the `StaticIPAddress` that is assigned to this node and
        remove the host mapping on the cluster.

        This should only be done when the node is in an unused state. If `ip`
        is supplied, only deallocate the specified address.
        """
        deallocated_ips = StaticIPAddress.objects.deallocate_by_node(
            self, alloc_type=alloc_type, ip=ip)

        if len(deallocated_ips) > 0:
            # Prevent circular imports
            from maasserver.dns import config as dns_config
            self.delete_host_maps(deallocated_ips)
            dns_config.dns_update_zones([self.nodegroup])

        return deallocated_ips

    @asynchronous(timeout=FOREVER)
    def deallocate_static_ip_addresses_later(self):
        """Schedule for `deallocate_static_ip_addresses` to be called later.

        This prevents the running task from blocking waiting for this task to
        finish. This can cause blocking and thread starvation inside the
        reactor threadpool.
        """
        reactor.callLater(
            0, deferToThread, transactional(
                self.deallocate_static_ip_addresses))

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

    def get_pxe_mac(self):
        """Get the MAC address this node is expected to PXE boot from.

        Normally, this will be the MAC address last used in a
        pxeconfig() API request for the node, as recorded in the
        'pxe_mac' property. However, if the node hasn't PXE booted since
        the 'pxe_mac' property was added to the Node model, this will
        return the node's first MAC address instead.
        """
        if self.pxe_mac is not None:
            return self.pxe_mac

        # Only use "all" and perform the sorting manually to stop extra queries
        # when the `macaddress_set` is prefetched.
        macs = sorted(self.macaddress_set.all(), key=attrgetter('id'))
        if len(macs) == 0:
            return None
        return macs[0]

    def get_pxe_mac_vendor(self):
        """Return the vendor of the MAC address the node pxebooted from."""
        pxe_mac = self.get_pxe_mac()
        if pxe_mac is None:
            return None
        else:
            return get_vendor_for_mac(pxe_mac.mac_address.get_raw())

    def get_extra_macs(self):
        """Get the MACs other that the one the node PXE booted from."""
        pxe_mac = self.get_pxe_mac()
        extra_macs = self.macaddress_set.all()
        if pxe_mac is not None:
            # Remove the pxe_mac without "exclude" as exclude will cause
            # another query to be performed if the `macaddress_set` is
            # prefetched.
            extra_macs = [
                mac
                for mac in extra_macs
                if mac != pxe_mac
                ]
        return extra_macs

    def is_pxe_mac_on_managed_interface(self):
        pxe_mac = self.get_pxe_mac()
        if pxe_mac is not None:
            cluster_interface = pxe_mac.get_cluster_interface()
            if cluster_interface is not None:
                return cluster_interface.is_managed
        return False

    @transactional
    def start(self, by_user, user_data=None, update_host_maps=True):
        """Request on given user's behalf that the node be started up.

        :param by_user: Requesting user.
        :type by_user: User_
        :param user_data: Optional blob of user-data to be made available to
            the node through the metadata service. If not given, any previous
            user data is used.
        :type user_data: unicode

        :raise StaticIPAddressExhaustion: if there are not enough IP addresses
            left in the static range for this node to get all the addresses it
            needs.
        :raise PermissionDenied: If `by_user` does not have permission to
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

        if not by_user.has_perm(NODE_PERMISSION.EDIT, self):
            # You can't start a node you don't own unless you're an admin.
            raise PermissionDenied()

        # Record the user data for the node. Note that we do this
        # whether or not we can actually send power commands to the
        # node; the user may choose to start it manually.
        NodeUserData.objects.set_user_data(self, user_data)

        # Claim static IP addresses for the node if it's ALLOCATED.
        if self.status == NODE_STATUS.ALLOCATED:

            # Don't update host maps if we're not on a managed interface.
            if not self.is_pxe_mac_on_managed_interface() and update_host_maps:
                update_host_maps = False

            self.claim_static_ip_addresses(
                update_host_maps=update_host_maps)

        if self.status == NODE_STATUS.ALLOCATED:
            transition_monitor = (
                TransitionMonitor.fromNode(self)
                .within(seconds=self.get_deployment_time())
                .status_should_be(self.status))
            self.start_deployment()
        else:
            transition_monitor = None

        power_info = self.get_effective_power_info()
        if not power_info.can_be_started:
            # The node can't be powered on by MAAS, so return early.
            # Everything we've done up to this point is still valid;
            # this is not an error state.
            return None

        @transactional
        def pc_deallocate_by_node():
            # Deallocate the static IPs we claimed earlier.
            StaticIPAddress.objects.deallocate_by_node(self)

        def pc_power_on_node(system_id, hostname, nodegroup_uuid, power_info):
            d = power_on_node(system_id, hostname, nodegroup_uuid, power_info)
            if transition_monitor is not None:
                d.addCallback(
                    callOut, self._start_transition_monitor_async,
                    transition_monitor, hostname)
            d.addErrback(callOutToThread, pc_deallocate_by_node)
            return d

        return post_commit_do(
            pc_power_on_node, self.system_id, self.hostname,
            self.nodegroup.uuid, power_info)

    @transactional
    def stop(self, by_user, stop_mode='hard'):
        """Request that the node be powered down.

        :param by_user: Requesting user.
        :type by_user: User_
        :param stop_mode: Power off mode - usually 'soft' or 'hard'.
        :type stop_mode: unicode

        :raise PermissionDenied: If `by_user` does not have permission to
            stop this node.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to stop the node. This is already registed as a
            post-commit hook; it should not be added a second time. If it has
            not been possible to stop the node because the power controller
            does not support it, `None` will be returned. The node must be
            powered off manually.
        """
        if not by_user.has_perm(NODE_PERMISSION.EDIT, self):
            # You can't stop a node you don't own unless you're an admin.
            raise PermissionDenied()

        power_info = self.get_effective_power_info()
        if not power_info.can_be_stopped:
            # We can't stop this node, so just return; trying to stop a
            # node we don't know how to stop isn't an error state, but
            # it's a no-op.
            return None

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

    def _clear_storage_configuration(self):
        """Clear's the current storage configuration for this node.

        This will remove all related models to `PhysicalBlockDevice`'s on
        this node and all `VirtualBlockDevice`'s.
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
