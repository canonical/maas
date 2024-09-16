# Copyright 2012-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Node objects."""

__all__ = [
    "Controller",
    "Device",
    "Node",
    "Machine",
    "RackController",
    "RegionController",
]

from collections import defaultdict, namedtuple, OrderedDict
from datetime import datetime, timedelta
from functools import partial
from itertools import chain, count
import json
import logging
from operator import attrgetter
import os
import random
import re
import socket
from socket import gethostname
from typing import List
from urllib.parse import urlparse

from crochet import TimeoutError
from django.contrib.auth.models import User
from django.core.exceptions import (
    ObjectDoesNotExist,
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
    GenericIPAddressField,
    IntegerField,
    JSONField,
    Manager,
    ManyToManyField,
    Model,
    OneToOneField,
    PositiveIntegerField,
    PROTECT,
    Q,
    SET_DEFAULT,
    SET_NULL,
    TextField,
)
from django.db.models.query import QuerySet
from django.shortcuts import get_object_or_404
from netaddr import IPAddress, IPNetwork
import petname
from temporalio.client import WorkflowFailureError
from twisted.internet import reactor
from twisted.internet.defer import (
    Deferred,
    DeferredList,
    inlineCallbacks,
    returnValue,
    succeed,
)
from twisted.internet.error import ConnectionDone
from twisted.python.failure import Failure
from twisted.python.threadable import isInIOThread

from maasserver.clusterrpc.pods import decompose_machine
from maasserver.clusterrpc.power import (
    power_driver_check,
    power_query_all,
    set_boot_order,
)
from maasserver.enum import (
    ALLOCATED_NODE_STATUSES,
    BMC_TYPE,
    FILESYSTEM_FORMAT_TYPE_CHOICES_DICT,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    INTERFACE_LINK_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_FAMILY,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_STATUS_CHOICES,
    NODE_STATUS_CHOICES_DICT,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
    POWER_WORKFLOW_ACTIONS,
    SERVICE_STATUS,
    SIMPLIFIED_NODE_STATUS,
    SIMPLIFIED_NODE_STATUSES_MAP_REVERSED,
)
from maasserver.exceptions import (
    IPAddressCheckFailed,
    NetworkingResetProblem,
    NodeStateViolation,
    NoScriptsFound,
    PowerProblem,
    StaticIPAddressExhaustion,
    StorageClearProblem,
)
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.cacheset import CacheSet
from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.defaultresource import DefaultResource
from maasserver.models.domain import Domain
from maasserver.models.filesystem import Filesystem
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.interface import Interface, InterfaceRelationship
from maasserver.models.licensekey import LicenseKey
from maasserver.models.numa import NUMANode, NUMANodeHugepages
from maasserver.models.ownerdata import OwnerData
from maasserver.models.partitiontable import PartitionTable
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.resourcepool import ResourcePool
from maasserver.models.service import Service
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.subnet import get_dhcp_vlan, Subnet
from maasserver.models.tag import Tag
from maasserver.models.timestampedmodel import now, TimestampedModel
from maasserver.models.vlan import VLAN
from maasserver.models.zone import Zone
from maasserver.node_status import (
    COMMISSIONING_LIKE_STATUSES,
    get_failed_status,
    get_node_timeout,
    is_failed_status,
    MONITORED_STATUSES,
    NODE_TRANSITIONS,
)
from maasserver.permissions import NodePermission
from maasserver.routablepairs import (
    get_routable_address_map,
    reduce_routable_address_map,
)
from maasserver.rpc import (
    getAllClients,
    getClientFor,
    getClientFromIdentifiers,
)
from maasserver.server_address import get_maas_facing_server_addresses
from maasserver.storage_layouts import (
    get_storage_layout_for_node,
    MIN_BOOT_PARTITION_SIZE,
    StorageLayoutError,
    StorageLayoutMissingBootDiskError,
    VMFS6StorageLayout,
    VMFS7StorageLayout,
)
from maasserver.utils.converters import parse_systemd_interval
from maasserver.utils.dns import validate_hostname
from maasserver.utils.orm import (
    get_one,
    MAASQueriesMixin,
    post_commit,
    post_commit_do,
    transactional,
)
from maasserver.utils.threads import callOutToDatabase, deferToDatabase
from maasserver.worker_user import get_worker_user
from maasserver.workflow import execute_workflow, start_workflow, stop_workflow
from maasserver.workflow.power import (
    convert_power_action_to_power_workflow,
    get_temporal_task_queue_for_bmc,
    PowerParam,
)
from maastemporalworker.workflow.deploy import DeployNParam, DeployParam
from metadataserver.enum import (
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_STATUS_FAILED,
    SCRIPT_STATUS_RUNNING_OR_PENDING,
)
from metadataserver.user_data import (
    generate_user_data,
    generate_user_data_for_status,
)
from metadataserver.user_data.snippets import get_userdata_template_dir
from provisioningserver.drivers.osystem import BOOT_IMAGE_PURPOSE
from provisioningserver.drivers.pod import Capabilities
from provisioningserver.drivers.power.ipmi import IPMI_BOOT_TYPE
from provisioningserver.drivers.power.registry import (
    PowerDriverRegistry,
    sanitise_power_parameters,
)
from provisioningserver.enum import POWER_STATE, POWER_STATE_CHOICES
from provisioningserver.events import EVENT_DETAILS, EVENT_TYPES
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
    LIST_MODALIASES_OUTPUT_NAME,
)
from provisioningserver.rpc.cluster import (
    AddChassis,
    CheckIPs,
    DisableAndShutoffRackd,
)
from provisioningserver.rpc.exceptions import (
    NoConnectionsAvailable,
    PowerActionFail,
    UnknownPowerType,
)
from provisioningserver.utils import znums
from provisioningserver.utils.enum import map_enum_reverse
from provisioningserver.utils.env import MAAS_ID
from provisioningserver.utils.ipaddr import get_mac_addresses
from provisioningserver.utils.network import get_default_monitored_interfaces
from provisioningserver.utils.twisted import asynchronous, callOut, undefined

log = LegacyLogger()
maaslog = get_maas_logger("node")


# Holds the known `bios_boot_methods`. If `bios_boot_method` is not in this
# list then it will fallback to `DEFAULT_BIOS_BOOT_METHOD`.
KNOWN_BIOS_BOOT_METHODS = frozenset(
    ["pxe", "uefi", "powernv", "powerkvm", "s390x_partition"]
)

# Default `bios_boot_method`. See `KNOWN_BIOS_BOOT_METHOD` above for usage.
DEFAULT_BIOS_BOOT_METHOD = "pxe"

# Return type from `get_effective_power_info`.
PowerInfo = namedtuple(
    "PowerInfo",
    (
        "can_be_started",
        "can_be_stopped",
        "can_be_queried",
        "can_set_boot_order",
        "power_type",
        "power_parameters",
    ),
)

DefaultGateways = namedtuple("DefaultGateways", ("ipv4", "ipv6", "all"))

GatewayDefinition = namedtuple(
    "GatewayDefinition", ("interface_id", "subnet_id", "gateway_ip")
)


# Timeout before marking a node as failing to exit rescue mode.
# This is a temporary fix until we write a workflow for exiting
# rescue mode. The timeout is to prevent race conditions, where
# Node.update_power_state() may be called during the power cycle
# when the machine is powered off.
EXIT_RESCUE_MODE_TIMEOUT = 60 * 5  # 5 minutes


def get_bios_boot_from_bmc(bmc):
    """Get the machine boot method from the BMC.

    This is only used to work around bug #1899486. When we fix that in a
    better way, we can remove this method.
    """
    if bmc is None or bmc.power_type != "ipmi":
        return None
    power_boot_type = bmc.get_power_parameters().get("power_boot_type")
    if power_boot_type == IPMI_BOOT_TYPE.EFI:
        return "uefi"
    elif power_boot_type == IPMI_BOOT_TYPE.LEGACY:
        return "pxe"
    else:
        return None


def generate_node_system_id():
    """Return an unused six-digit system ID.

    This chooses an ID at random and returns it if it's not currently in use.
    There is a chance of a collision between concurrent processes, which would
    result in an `IntegrityError` in one process or the other, but it's small:
    there are over 183 million six-digit system IDs to choose from.
    """
    for attempt in range(1, 1001):
        system_num = random.randrange(24**5, 24**6)
        system_id = znums.from_int(system_num)
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM maasserver_node WHERE system_id = %s",
                [system_id],
            )
            if cursor.fetchone() is None:
                return system_id
    # Wow, really? This should _never_ happen. You must be managing a
    # *lot* of machines. This is here as a fail-safe; it does not feel
    # right to leave a loop that might never terminate in the code.
    raise AssertionError(
        "The unthinkable has come to pass: after %d iterations "
        "we could find no unused node identifiers." % attempt
    )


class NodeQueriesMixin(MAASQueriesMixin):
    def filter_by_spaces(self, spaces):
        """Return the set of nodes with at least one interface in the specified
        spaces.
        """
        return self.filter(
            current_config__interface__ip_addresses__subnet__vlan__space__in=spaces
        )

    def exclude_spaces(self, spaces):
        """Return the set of nodes without any interfaces in the specified
        spaces.
        """
        return self.exclude(
            current_config__interface__ip_addresses__subnet__vlan__space__in=spaces
        )

    def filter_by_fabrics(self, fabrics):
        """Return the set of nodes with at least one interface in the specified
        fabrics.
        """
        return self.filter(current_config__interface__vlan__fabric__in=fabrics)

    def exclude_fabrics(self, fabrics):
        """Return the set of nodes without any interfaces in the specified
        fabrics.
        """
        return self.exclude(
            current_config__interface__vlan__fabric__in=fabrics
        )

    def filter_by_fabric_classes(self, fabric_classes):
        """Return the set of nodes with at least one interface in the specified
        fabric classes.
        """
        return self.filter(
            current_config__interface__vlan__fabric__class_type__in=fabric_classes
        )

    def exclude_fabric_classes(self, fabric_classes):
        """Return the set of nodes without any interfaces in the specified
        fabric classes.
        """
        return self.exclude(
            current_config__interface__vlan__fabric__class_type__in=fabric_classes
        )

    def filter_by_vids(self, vids):
        """Return the set of nodes with at least one interface whose VLAN has
        one of the specified VIDs.
        """
        return self.filter(current_config__interface__vlan__vid__in=vids)

    def exclude_vids(self, vids):
        """Return the set of nodes without any interfaces whose VLAN has one of
        the specified VIDs.
        """
        return self.exclude(current_config__interface__vlan__vid__in=vids)

    def filter_by_subnets(self, subnets):
        """Return the set of nodes with at least one interface configured on
        one of the specified subnets.
        """
        return self.filter(
            current_config__interface__ip_addresses__subnet__in=subnets
        )

    def exclude_subnets(self, subnets):
        """Return the set of nodes without any interfaces configured on one of
        the specified subnets.
        """
        return self.exclude(
            current_config__interface__ip_addresses__subnet__in=subnets
        )

    def filter_by_subnet_cidrs(self, subnet_cidrs):
        """Return the set of nodes with at least one interface configured on
        one of the specified subnet with the given CIDRs.
        """
        return self.filter(
            current_config__interface__ip_addresses__subnet__cidr__in=subnet_cidrs
        )

    def exclude_subnet_cidrs(self, subnet_cidrs):
        """Return the set of nodes without any interfaces configured on one of
        the specified subnet with the given CIDRs.
        """
        return self.exclude(
            current_config__interface__ip_addresses__subnet__cidr__in=subnet_cidrs
        )

    def filter_by_domains(self, domain_names):
        """Return the set of nodes with at least one interface configured in
        one of the specified dns zone names.
        """
        return self.filter(
            current_config__interface__ip_addresses__dnsresource_set__domain__name__in=(
                domain_names
            )
        )

    def exclude_domains(self, domain_names):
        """Return the set of nodes without any interfaces configured in
        one of the specified dns zone names.
        """
        return self.exclude(
            current_config__interface__ip_addresses__dnsresource_set__domain__name__in=(
                domain_names
            )
        )


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
        :type perm: `NodePermission`
        :return: A version of `node` that is filtered to include only those
            nodes that `user` is allowed to access.
        """
        # Local import to avoid circular imports.
        from maasserver.rbac import rbac

        # If the data is corrupt, this can get called with None for
        # user where a Node should have an owner but doesn't.
        # Nonetheless, the code should not crash with corrupt data.
        if user is None:
            return nodes.none()
        if user.is_superuser and not rbac.is_enabled():
            # Admin is allowed to see all nodes.
            return nodes

        # Non-admins aren't allowed to see controllers.
        if not user.is_superuser:
            nodes = nodes.exclude(
                Q(
                    node_type__in=[
                        NODE_TYPE.RACK_CONTROLLER,
                        NODE_TYPE.REGION_CONTROLLER,
                        NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                    ]
                )
            )

        visible_pools, view_all_pools = [], []
        deploy_pools, admin_pools = [], []
        if rbac.is_enabled():
            fetched_pools = rbac.get_resource_pool_ids(
                user.username,
                "view",
                "view-all",
                "deploy-machines",
                "admin-machines",
            )
            visible_pools = fetched_pools["view"]
            view_all_pools = fetched_pools["view-all"]
            deploy_pools = fetched_pools["deploy-machines"]
            admin_pools = fetched_pools["admin-machines"]

        if perm == NodePermission.view:
            condition = Q(Q(owner__isnull=True) | Q(owner=user))
            if rbac.is_enabled():
                condition |= Q(pool_id__in=view_all_pools)
        elif perm == NodePermission.edit:
            condition = Q(Q(owner__isnull=True) | Q(owner=user))
            if rbac.is_enabled():
                condition = Q(Q(pool_id__in=deploy_pools) & Q(condition))
        elif perm == NodePermission.admin:
            # There is no built-in Q object that represents False, but
            # this one does.
            condition = Q(id__in=[])
        else:
            raise NotImplementedError(
                "Invalid permission check (invalid permission name: %s)."
                % perm
            )
        if rbac.is_enabled():
            # XXX blake_r 2018-12-12 - This should be cleaned up to only use
            # the `condition` instead of using both `nodes.filter` and
            # `condition`. The RBAC unit tests cover the expected result.
            condition |= Q(pool_id__in=admin_pools)
            condition = Q(Q(node_type=NODE_TYPE.MACHINE) & condition)
            if user.is_superuser:
                condition |= Q(
                    node_type__in=[
                        NODE_TYPE.DEVICE,
                        NODE_TYPE.RACK_CONTROLLER,
                        NODE_TYPE.REGION_CONTROLLER,
                        NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                    ]
                )
                nodes = nodes.filter(
                    Q(
                        node_type=NODE_TYPE.MACHINE,
                        pool_id__in=set(visible_pools).union(view_all_pools),
                    )
                    | Q(
                        node_type__in=[
                            NODE_TYPE.DEVICE,
                            NODE_TYPE.RACK_CONTROLLER,
                            NODE_TYPE.REGION_CONTROLLER,
                            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                        ]
                    )
                )
            else:
                condition |= Q(node_type=NODE_TYPE.DEVICE, owner=user)
                nodes = nodes.filter(
                    Q(
                        node_type=NODE_TYPE.MACHINE,
                        pool_id__in=set(visible_pools).union(view_all_pools),
                    )
                    | Q(node_type=NODE_TYPE.DEVICE, owner=user)
                )

        return nodes.filter(condition)

    def get_nodes(self, user, perm, ids=None, from_nodes=None):
        """Fetch Nodes on which the User_ has the given permission.

        Warning: there could be a lot of nodes!  Keep scale in mind when
        calling this, and watch performance in general.  Prefetch related
        data where appropriate.

        :param user: The user that should be used in the permission check.
        :type user: User_
        :param perm: The permission to check.
        :type perm: a permission string from `NodePermission`
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
        else:
            # Make sure even if given a query set of multiple node types
            # get_nodes only returns nodes applicable to this manager.
            from_nodes = from_nodes.filter(**self.extra_filters)
        if perm == NodePermission.edit:
            from_nodes = from_nodes.filter(locked=False)
        nodes = self._filter_visible_nodes(from_nodes, user, perm)
        return self.filter_by_ids(nodes, ids)

    def get_node_or_404(self, system_id, user, perm, **kwargs):
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
        kwargs.update(self.extra_filters)
        node = get_object_or_404(self.model, system_id=system_id, **kwargs)
        if node.locked and perm == NodePermission.edit:
            raise PermissionDenied()
        elif user.has_perm(perm, node):
            return node.as_self()
        else:
            raise PermissionDenied()


class GeneralManager(BaseNodeManager):
    """All the node types:"""


class MachineManager(BaseNodeManager):
    """Machines (i.e. deployable objects)."""

    extra_filters = {"node_type": NODE_TYPE.MACHINE}

    def get_available_machines_for_acquisition(self, for_user):
        """Find the machines that can be acquired by the given user.

        :param for_user: The user who is to acquire the machine.
        :type for_user: :class:`django.contrib.auth.models.User`
        :return: Those machines which can be acquired by the user.
        :rtype: `django.db.models.query.QuerySet`
        """
        available_machines = self.get_nodes(for_user, NodePermission.edit)
        return available_machines.filter(status=NODE_STATUS.READY)


class DeviceManager(BaseNodeManager):
    """Devices are all the non-deployable nodes."""

    extra_filters = {"node_type": NODE_TYPE.DEVICE}


class ControllerManager(BaseNodeManager):
    """All controllers `RackController`, `RegionController`, and
    `RegionRackController`."""

    extra_filters = {
        "node_type__in": [
            NODE_TYPE.RACK_CONTROLLER,
            NODE_TYPE.REGION_CONTROLLER,
            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
        ]
    }


class RackControllerManager(ControllerManager):
    """Rack controllers are nodes which are used by MAAS to deploy nodes."""

    extra_filters = {
        "node_type__in": [
            NODE_TYPE.RACK_CONTROLLER,
            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
        ]
    }

    def get_running_controller(self):
        """Return the rack controller for the current host.

        :raises: `DoesNotExist` if no matching controller is found.
        """
        return self.get(system_id=MAAS_ID.get())

    def filter_by_url_accessible(self, url, with_connection=True):
        """Return a list of rack controllers which have access to the given URL

        If a hostname is given MAAS will do a DNS lookup to discover the IP(s).
        MAAS then uses the information it has about the network to return a
        a list of rack controllers which should have access to each IP."""
        if "://" not in url:
            # urlparse only works if given with a protocol
            if url.count(":") > 2:
                parsed_url = urlparse("FAKE://[%s]" % url)
            else:
                parsed_url = urlparse("FAKE://%s" % url)
        else:
            parsed_url = urlparse(url)
        # getaddrinfo can return duplicates
        ips = {
            address[4][0]
            for address in socket.getaddrinfo(parsed_url.hostname, None)
        }
        subnets = {Subnet.objects.get_best_subnet_for_ip(ip) for ip in ips}
        usable_racks = set(
            RackController.objects.filter(
                current_config__interface__ip_addresses__subnet__in=subnets,
                current_config__interface__ip_addresses__ip__isnull=False,
            )
        )
        # There is no MAAS defined subnet for loop back so if its in our list
        # of IPs add ourself
        if "127.0.0.1" in ips or "::1" in ips:
            running_rack = self.get_running_controller()
            if running_rack is not None:
                usable_racks.add(running_rack)

        if with_connection:
            conn_rack_ids = [client.ident for client in getAllClients()]
            return [
                rack
                for rack in usable_racks
                if rack.system_id in conn_rack_ids
            ]
        else:
            return list(usable_racks)

    def get_accessible_by_url(self, url, with_connection=True):
        """Return a rack controller with access to a URL."""
        racks = self.filter_by_url_accessible(url, with_connection)
        if not racks:
            return None
        else:
            # Lazy load balancing
            return random.choice(racks)


class RegionControllerManager(ControllerManager):
    """Region controllers are the API, UI, and Coordinators of MAAS."""

    extra_filters = {
        "node_type__in": [
            NODE_TYPE.REGION_CONTROLLER,
            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
        ]
    }

    def get_running_controller(self):
        """Return the region controller for the current host.

        :raises: `DoesNotExist` if no matching controller is found.
        """
        return self.get(system_id=MAAS_ID.get())

    def get_or_create_running_controller(self):
        """Return the region controller for the current host.

        :attention: This should be called early in the start-up process for a
            region controller to ensure that it can refer to itself.

        If the MAAS ID has been set, this searches for the controller only by
        its system ID. If the controller is not found `DoesNotExist` will be
        raised.

        If the MAAS ID has not yet been set this tries to discover a matching
        node via the current host's name and its MAC addresses. If no matching
        node is found, a new region controller will be created. In either case
        the MAAS ID will be set on the filesystem once the transaction has
        been committed.
        """
        maas_id = MAAS_ID.get()
        if maas_id is None:
            node = self._find_or_create_running_controller()
        else:
            try:
                node = Node.objects.get(system_id=maas_id)
            except Node.DoesNotExist:
                # The MAAS ID on the filesystem is stale. Perhaps this machine
                # has not been cleaned-up sufficiently from a previous life?
                # Regardless, a deliberate act has brought this about, like a
                # purge of the database, so we continue instead of crashing.
                node = self._find_or_create_running_controller()
            else:
                node = self._upgrade_running_node(node)

        # A region needs to have a commissioning_script_set available to
        # allow commissioning data to be sent on start.
        if node.current_commissioning_script_set is None:
            from maasserver.models import ScriptSet

            script_set = ScriptSet.objects.create_commissioning_script_set(
                node
            )
            node.current_commissioning_script_set = script_set
            node.save()

        return node

    def _find_or_create_running_controller(self):
        """Find the controller for the current host, or create one.

        Tries to discover the controller via the current host's name and MAC
        addresses. Don't use this if the MAAS ID has been set.

        If the discovered node is not yet a controller it is upgraded. If no
        node is found a preconfigured controller is minted. In either case,
        the MAAS ID on the filesystem is set post-commit.
        """
        node = self._find_running_node()
        if node is None:
            region = self._create_running_controller()
        else:
            region = self._upgrade_running_node(node)
        post_commit_do(MAAS_ID.set, region.system_id)
        return region

    def _find_running_node(self):
        """Find the node for the current host.

        Tries to discover the node via the current host's name and MAC
        addresses. Don't use this if the MAAS ID has been set.
        """
        hostname = gethostname()
        filter_hostname = Q(hostname=hostname)
        filter_macs = Q(
            current_config__interface__mac_address__in=get_mac_addresses()
        )
        # Look at all nodes, not just controllers; we might have to upgrade.
        nodes = Node.objects.filter(filter_hostname | filter_macs)
        # Select distinct because the join to MACs might yield duplicates.
        return get_one(nodes.distinct())

    def _upgrade_running_node(self, node):
        """Upgrade a node to a region controller for the host machine.

        This node is already known to MAAS, but this MAY be the first time
        that regiond has run on it, so ensure it's a region, owned by the
        worker user.
        """
        update_fields = []
        if not node.is_region_controller:
            if node.is_rack_controller:
                node.node_type = NODE_TYPE.REGION_AND_RACK_CONTROLLER
            else:
                node.node_type = NODE_TYPE.REGION_CONTROLLER
            update_fields.append("node_type")
        if node.owner is None:
            node.owner = get_worker_user()
            update_fields.append("owner")
        if node.pool:
            # controllers aren't assigned to pools
            node.pool = None
            update_fields.append("pool")
        if len(update_fields) > 0:
            node.save(update_fields=update_fields)
        # Always cast to a region controller.
        return node.as_region_controller()

    def _create_running_controller(self):
        """Create a region controller for the host machine.

        This node is NOT previously known to MAAS, and this is the first time
        regiond has run on it. Create a region controller only; it can be
        upgraded to a region+rack controller later if necessary.
        """
        hostname = gethostname()
        # Bug#1614584: it is possible that gethostname() reurns the FQDN.
        # Split it up, and get the appropriate domain.  If we wind up creating
        # one for it, we are not authoritative.
        # Just in case the default domain has not been created, let's create it
        # here, even if we subsequently overwrite it inside the if statement.
        domain = Domain.objects.get_default_domain()
        if hostname.find(".") > 0:
            hostname, domainname = hostname.split(".", 1)
            (domain, _) = Domain.objects.get_or_create(
                name=domainname, defaults={"authoritative": False}
            )
        return self.create(
            owner=get_worker_user(),
            hostname=hostname,
            domain=domain,
            status=NODE_STATUS.DEPLOYED,
            dynamic=True,
        )


def get_default_domain():
    """Get the default domain name."""
    return Domain.objects.get_default_domain().id


def get_default_zone():
    """Return the ID of the default zone."""
    return DefaultResource.objects.get_default_zone().id


# Statuses for which it makes sense to release a node.
RELEASABLE_STATUSES = frozenset(
    [
        NODE_STATUS.ALLOCATED,
        NODE_STATUS.RESERVED,
        NODE_STATUS.BROKEN,
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.DEPLOYED,
        NODE_STATUS.FAILED_DEPLOYMENT,
        NODE_STATUS.FAILED_DISK_ERASING,
        NODE_STATUS.FAILED_RELEASING,
    ]
)


class Node(CleanSave, TimestampedModel):
    """A `Node` represents a physical machine used by the MAAS Server.

    :ivar system_id: The unique identifier for this `Node`.
        (e.g. 'node-41eba45e-4cfa-11e1-a052-00225f89f211').
    :ivar hostname: This `Node`'s hostname.  Must conform to RFCs 952 and 1123.
    :ivar description: This `Node`'s description.  Readable by all users only
        editable by administrators or operators.
    :ivar node_type: The type of node. This is used to specify if the node is
        to be used as a node for deployment, as a device, or a rack controller
    :ivar parent: An optional parent `Node`.  This node will be deleted along
        with all its resources when the parent node gets deleted or released.
        This is only relevant for node types other than node.
    :ivar status: This `Node`'s status. See the vocabulary
        :class:`NODE_STATUS`.
    :ivar previous_status: This `Node`'s previous status.  See the vocabulary
        :class:`NODE_STATUS`.
    :ivar error_description: A human-readable description of why a node is
        marked broken.  Only meaningful when the node is in the state 'BROKEN'.
    :ivar owner: This `Node`'s owner if it's in use, None otherwise.
    :ivar bios_boot_method: The boot method used by the cluster to allow
        this node to boot. E.g. "pxe".
    :ivar osystem: This `Node`'s booting operating system, if it's blank then
        the default_osystem will be used.
    :ivar distro_series: This `Node`'s booting distro series, if
        it's blank then the default_distro_series will be used.
    :ivar bmc: The BMC / power controller for this node.
    :ivar tags: The list of :class:`Tag`s associated with this `Node`.
    :ivar objects: The :class:`GeneralManager`.
    :ivar install_rackd: An optional flag to indicate if this node should be
        deployed with the rack controller.
    :ivar install_kvm: An optional flag to indicate if this node should be
        deployed with KVM and added to MAAS.
    :ivar register_vmhost: An optional flag to indicate if this node should be
        deployed with LXD and registered to MAAS as a VM host.
    :ivar enable_ssh: An optional flag to indicate if this node can have
        ssh enabled during commissioning, allowing the user to ssh into the
        machine's commissioning environment using the user's SSH key.
    :ivar skip_bmc_config: An optional flag to indicate if this node can be
        commissioned without re-running the IPMI auto discovery mechanism.
    :ivar skip_networking: An optional flag to indicate if this node
        networking configuration doesn't need to be touched when it is
        commissioned.
    :ivar default_user: The username this `Node` will be configured with,
        None otherwise.
    """

    system_id = CharField(
        max_length=41,
        unique=True,
        default=generate_node_system_id,
        editable=False,
    )

    # The UUID of the node as defined by its hardware.
    hardware_uuid = CharField(
        max_length=36, default=None, null=True, blank=True, unique=True
    )

    hostname = CharField(
        max_length=255,
        default="",
        blank=True,
        unique=True,
        validators=[validate_hostname],
    )

    description = TextField(blank=True, default="", editable=True)

    pool = ForeignKey(
        ResourcePool,
        default=None,
        null=True,
        blank=True,
        editable=True,
        on_delete=PROTECT,
    )

    # What Domain do we use for this host unless the individual StaticIPAddress
    # record overrides it?
    domain = ForeignKey(
        Domain,
        default=get_default_domain,
        null=True,
        blank=True,
        editable=True,
        on_delete=PROTECT,
    )

    # TTL for this Node's IP addresses.  Since this must be the same for all
    # records of the same time on any given name, we need to coordinate the TTL
    # with any addresses that come from DNSResource.
    # If None, then we inherit from the parent Domain, or the global default.
    address_ttl = PositiveIntegerField(default=None, null=True, blank=True)

    status = IntegerField(
        choices=NODE_STATUS_CHOICES,
        editable=False,
        default=NODE_STATUS.DEFAULT,
    )

    previous_status = IntegerField(
        choices=NODE_STATUS_CHOICES,
        editable=False,
        default=NODE_STATUS.DEFAULT,
    )

    # Set to time in the future when the node status should transition to
    # a failed status. This is used by the StatusMonitorService inside
    # the region processes. Each run periodically to update nodes.
    status_expires = DateTimeField(
        null=True, blank=False, default=None, editable=False
    )

    owner = ForeignKey(
        User,
        default=None,
        blank=True,
        null=True,
        editable=False,
        on_delete=PROTECT,
    )

    bios_boot_method = CharField(max_length=31, blank=True, null=True)

    osystem = CharField(max_length=255, blank=True, default="")

    distro_series = CharField(max_length=255, blank=True, default="")

    architecture = CharField(max_length=31, blank=True, null=True)

    min_hwe_kernel = CharField(max_length=31, blank=True, null=True)

    hwe_kernel = CharField(max_length=31, blank=True, null=True)

    node_type = IntegerField(
        choices=NODE_TYPE_CHOICES, editable=False, default=NODE_TYPE.DEFAULT
    )

    parent = ForeignKey(
        "Node",
        default=None,
        blank=True,
        null=True,
        editable=True,
        related_name="children",
        on_delete=CASCADE,
    )

    agent_name = CharField(max_length=255, default="", blank=True, null=True)

    error_description = TextField(blank=True, default="", editable=False)

    zone = ForeignKey(
        Zone,
        verbose_name="Physical zone",
        default=get_default_zone,
        editable=True,
        db_index=True,
        on_delete=SET_DEFAULT,
    )

    # Juju expects the following standard constraints, which are stored here
    # as a basic optimisation over querying the lshw output.
    cpu_count = IntegerField(default=0)
    cpu_speed = IntegerField(default=0)  # MHz
    memory = IntegerField(default=0)

    swap_size = BigIntegerField(null=True, blank=True, default=None)

    bmc = ForeignKey(
        "BMC",
        db_index=True,
        null=True,
        editable=False,
        unique=False,
        on_delete=CASCADE,
    )

    # Power parameters specific to this node instance. Global power parameters
    # are stored in this node's BMC.
    instance_power_parameters = JSONField(
        max_length=(2**15), blank=True, default=str
    )

    power_state = CharField(
        max_length=10,
        null=False,
        blank=False,
        choices=POWER_STATE_CHOICES,
        default=POWER_STATE.UNKNOWN,
        editable=False,
    )

    # Set when a rack controller says its going to update the power state
    # for this node. This prevents other rack controllers from also checking
    # this node at the same time.
    power_state_queried = DateTimeField(
        null=True, blank=False, default=None, editable=False
    )

    # Set when a rack controller has actually checked this power state and
    # the last time the power was updated.
    power_state_updated = DateTimeField(
        null=True, blank=False, default=None, editable=False
    )

    # Updated each time a rack controller finishes syncing boot images.
    last_image_sync = DateTimeField(
        null=True, blank=False, default=None, editable=False
    )

    error = CharField(max_length=255, blank=True, default="")

    netboot = BooleanField(default=True)

    ephemeral_deploy = BooleanField(default=False)

    license_key = CharField(max_length=30, null=True, blank=True)

    # Whether this is a machine that was composed on allocation, or a machine
    # automatically created by MAAS as either a controller or a VM host
    dynamic = BooleanField(default=False)

    tags = ManyToManyField(Tag)

    # Record the Interface the node last booted from.
    # This will be used for determining which Interface to create a static
    # IP reservation for when starting a node.
    boot_interface = ForeignKey(
        Interface,
        default=None,
        blank=True,
        null=True,
        editable=False,
        related_name="+",
        on_delete=SET_NULL,
    )

    # Record the last IP address of the cluster this node used to request
    # TFTP data. This is used to send the correct IP address for the node to
    # download the image to install. Since the node just contacted the cluster
    # using this IP address then it will be able to access the images at this
    # IP address.
    boot_cluster_ip = GenericIPAddressField(
        unique=False, null=True, editable=False, blank=True, default=None
    )

    # Record the PhysicalBlockDevice that this node uses as its boot disk.
    # This will be used to make sure GRUB is installed to this device.
    boot_disk = ForeignKey(
        PhysicalBlockDevice,
        default=None,
        blank=True,
        null=True,
        editable=False,
        related_name="+",
        on_delete=SET_NULL,
    )

    # Default IPv4 subnet link on an interface for this node. This is used to
    # define the default IPv4 route the node should use.
    gateway_link_ipv4 = ForeignKey(
        StaticIPAddress,
        default=None,
        blank=True,
        null=True,
        editable=False,
        related_name="+",
        on_delete=SET_NULL,
    )

    # Default IPv6 subnet link on an interface for this node. This is used to
    # define the default IPv6 route the node should use.
    gateway_link_ipv6 = ForeignKey(
        StaticIPAddress,
        default=None,
        blank=True,
        null=True,
        editable=False,
        related_name="+",
        on_delete=SET_NULL,
    )

    # Used to configure the default username for this machine. It will be
    # empty by default, and the default user.
    default_user = CharField(max_length=32, blank=True, default="")

    # Used to deploy the rack controller on a installation machine.
    install_rackd = BooleanField(default=False)

    # Used to deploy KVM (via libvirt) on a machine and register it as a VM
    # host.
    install_kvm = BooleanField(default=False)
    # Used to deploy LXD on a machine and register it as a VM host.
    register_vmhost = BooleanField(default=False)

    # Used to determine whether to:
    #  1. Import the SSH Key during commissioning and keep power on.
    #  2. Skip reconfiguring networking when a node is commissioned.
    #  3. Skip reconfiguring storage when a node is commissioned.
    enable_ssh = BooleanField(default=False)
    skip_networking = BooleanField(default=False)
    skip_storage = BooleanField(default=False)

    # The URL the RackController uses to access to RegionController's.
    url = CharField(blank=True, editable=False, max_length=255, default="")

    # Used only by a RegionController to determine which
    # RegionControllerProcess is currently controlling DNS on this node.
    # Used only by `REGION_CONTROLLER` all other types this should be NULL.
    dns_process = OneToOneField(
        "RegionControllerProcess",
        null=True,
        editable=False,
        unique=True,
        on_delete=SET_NULL,
        related_name="+",
    )

    # Used only by a RackController to mark which RegionControllerProcess is
    # handling system level events for this rack controller.
    managing_process = ForeignKey(
        "RegionControllerProcess",
        null=True,
        editable=False,
        on_delete=SET_NULL,
        related_name="+",
    )

    # The ScriptSet for the currently running, or last run, commissioning
    # ScriptSet.
    current_commissioning_script_set = ForeignKey(
        "maasserver.ScriptSet",
        blank=True,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
    )

    # The ScriptSet for the currently running, or last run, installation.
    current_installation_script_set = ForeignKey(
        "maasserver.ScriptSet",
        blank=True,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
    )

    # The ScriptSet for the currently running, or last run, test ScriptSet.
    current_testing_script_set = ForeignKey(
        "maasserver.ScriptSet",
        blank=True,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
    )

    # The ScriptSet for the currently running, or last run, release ScriptSet.
    current_release_script_set = ForeignKey(
        "maasserver.ScriptSet",
        blank=True,
        null=True,
        on_delete=SET_NULL,
        related_name="+",
    )

    locked = BooleanField(default=False)

    last_applied_storage_layout = CharField(max_length=50, blank=True)

    # This actually always points to an entry, but can't be set to null=False
    # since NodeConfig also has a non-nullable foreign key to Node
    current_config = ForeignKey(
        "NodeConfig", null=True, on_delete=CASCADE, related_name="+"
    )

    # hardware updates
    enable_hw_sync = BooleanField(default=False)
    sync_interval = IntegerField(blank=True, null=True)
    last_sync = DateTimeField(blank=True, null=True)

    # Note that the ordering of the managers is meaningful.  More precisely,
    # the first manager defined is important: see
    # https://docs.djangoproject.com/en/1.7/topics/db/managers/ ("Default
    # managers") for details.
    # 'objects' are all the nodes types
    objects = GeneralManager()

    # Manager that returns all controller objects. See `ControllerManager`.
    controllers = ControllerManager()

    def __str__(self):
        if self.hostname:
            return f"{self.system_id} ({self.hostname})"
        else:
            return self.system_id

    @property
    def default_numanode(self):
        """Return NUMA node 0 for the node."""
        return self.numanode_set.get(index=0)

    @property
    def simplified_status(self):
        """Return simplified status"""
        return SIMPLIFIED_NODE_STATUSES_MAP_REVERSED.get(
            self.status, SIMPLIFIED_NODE_STATUS.OTHER
        )

    def lock(self, user, comment=None):
        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_LOCK, action="lock", comment=comment
        )

        if self.locked:
            return

        if self.status not in (NODE_STATUS.DEPLOYED, NODE_STATUS.DEPLOYING):
            raise NodeStateViolation(
                "Can't lock, node is not deployed or deploying"
            )

        maaslog.info("%s: Node locked by %s", self.hostname, user)
        self.locked = True
        self.save()

    def unlock(self, user, comment=None):
        self._register_request_event(
            user,
            EVENT_TYPES.REQUEST_NODE_UNLOCK,
            action="unlock",
            comment=comment,
        )

        if not self.locked:
            return

        maaslog.info("%s: Node unlocked by %s", self.hostname, user)
        self.locked = False
        self.save()

    @property
    def disable_ipv4(self):
        return False

    @property
    def is_rack_controller(self) -> bool:
        return self.node_type in [
            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
            NODE_TYPE.RACK_CONTROLLER,
        ]

    @property
    def is_region_controller(self) -> bool:
        return self.node_type in [
            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
            NODE_TYPE.REGION_CONTROLLER,
        ]

    @property
    def is_controller(self):
        return self.node_type in [
            NODE_TYPE.REGION_CONTROLLER,
            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
            NODE_TYPE.RACK_CONTROLLER,
        ]

    @property
    def is_machine(self) -> bool:
        return self.node_type == NODE_TYPE.MACHINE

    @property
    def is_device(self) -> bool:
        return self.node_type == NODE_TYPE.DEVICE

    @property
    def is_pod(self):
        return self.get_hosted_pods().exists()

    @property
    def next_sync(self):
        if self.last_sync and self.sync_interval:
            return self.last_sync + timedelta(seconds=self.sync_interval)
        return None

    @property
    def is_sync_healthy(self):
        if self.enable_hw_sync and self.last_sync and self.sync_interval:
            return (
                datetime.now()
                <= 1.5 * timedelta(seconds=self.sync_interval) + self.last_sync
            )
        return False

    def is_commissioning(self):
        return self.status not in (NODE_STATUS.DEPLOYED, NODE_STATUS.DEPLOYING)

    def set_power_config(
        self,
        power_type,
        power_params,
        from_commissioning=False,
    ):
        """Update the power configuration for a node.

        If power_type is not changed, this will update power parameters for the
        current BMC, so if the BMC is a chassis, the configuration will apply
        to all connected nodes.
        """
        from maasserver.models.bmc import BMC, create_bmc, get_or_create_bmc

        created_by_commissioning = from_commissioning
        old_bmc = self.bmc
        chassis, bmc_params, node_params = BMC.scope_power_parameters(
            power_type, power_params
        )
        if power_type == self.power_type:
            if power_type == "manual":
                self.bmc.set_power_parameters(bmc_params)
                self.bmc.save()
            else:
                existing_bmc = BMC.objects.filter(
                    power_type=power_type, power_parameters=bmc_params
                ).first()
                if existing_bmc and existing_bmc.id != self.bmc_id:
                    # Point all nodes using old BMC at the new one.
                    for node in self.bmc.node_set.exclude(id=self.id):
                        node.bmc = existing_bmc
                        node.save()
                    self.bmc = existing_bmc
                elif not existing_bmc:
                    self.bmc.set_power_parameters(bmc_params)
                    self.bmc.save()
        elif chassis:
            self.bmc, _ = get_or_create_bmc(
                power_type=power_type,
                power_parameters=bmc_params,
                defaults={
                    "created_by_commissioning": created_by_commissioning
                },
            )
        else:
            self.bmc = create_bmc(
                power_type=power_type,
                power_parameters=bmc_params,
                created_by_commissioning=created_by_commissioning,
            )
            self.bmc.save()

        self.set_instance_power_parameters(node_params or {})

        # delete the old bmc if no node is connected to it
        if old_bmc and old_bmc != self.bmc and not old_bmc.node_set.exists():
            old_bmc.delete()

    @property
    def power_type(self):
        return "" if self.bmc is None else self.bmc.power_type

    def get_instance_power_parameters(self):
        from maasserver.secrets import SecretManager

        power_parameters = self.instance_power_parameters or {}
        return {
            **power_parameters,
            **SecretManager().get_composite_secret(
                "power-parameters", obj=self.as_node(), default={}
            ),
        }

    def set_instance_power_parameters(self, power_parameters):
        power_parameters, secrets = sanitise_power_parameters(
            self.power_type, power_parameters
        )

        if secrets:
            from maasserver.secrets import SecretManager

            SecretManager().set_composite_secret(
                "power-parameters", secrets, obj=self.as_node()
            )
        self.instance_power_parameters = power_parameters

    def get_power_parameters(self):
        # Overlay instance power parameters over bmc power parameters.
        instance_parameters = self.get_instance_power_parameters()
        if not instance_parameters:
            instance_parameters = {}
        bmc_parameters = {}
        if self.bmc and (
            bmc_power_parameters := self.bmc.get_power_parameters()
        ):
            bmc_parameters = bmc_power_parameters
        return {**bmc_parameters, **instance_parameters}

    @property
    def instance_name(self):
        """Return the name of the VM instance for this machine, or None."""

        # LXD uses "instance_name", virsh uses "power_id"
        return self.get_instance_power_parameters().get(
            "instance_name"
        ) or self.get_instance_power_parameters().get("power_id")

    @property
    def fqdn(self):
        """Fully qualified domain name for this node.

        Return the FQDN for this host.
        """
        if self.domain is not None:
            return f"{self.hostname}.{self.domain.name}"
        else:
            return self.hostname

    def reset_status_expires(self):
        """Reset status_expires if set and in a monitored status."""
        if self.status_expires is not None:
            minutes = get_node_timeout(self.status)
            if minutes is not None:
                self.status_expires = now() + timedelta(minutes=minutes)

    def _register_request_event(
        self, user, type_name, action="", comment=None
    ):
        """Register a node request event.

        It registers events like start_commission (started by a user),
        or mark_failed (started by the system)"""

        # the description will be the comment, if any.
        description = comment if comment else ""
        # if the user exists, we need to construct the description with
        # the user. as it would be a user-driven request.
        if user is not None:
            if len(description) == 0:
                description = "(%s)" % user
            else:
                description = f"({user}) - {description}"
        event_details = EVENT_DETAILS[type_name]

        # Avoid circular imports.
        from maasserver.models.event import Event

        Event.objects.register_event_and_event_type(
            type_name,
            type_level=event_details.level,
            type_description=event_details.description,
            user=user,
            event_action=action,
            event_description=description,
            system_id=self.system_id,
        )

    @property
    def is_diskless(self):
        """Return whether or not this node has any disks."""
        # Use the queryset as it might be cached
        return len(self.current_config.blockdevice_set.all()) == 0

    def retrieve_storage_layout_issues(
        self,
        has_boot,
        root_mounted,
        root_on_bcache,
        boot_mounted,
        arch,
        any_bcache,
        any_zfs,
        any_vmfs,
        any_btrfs,
    ):
        """Create and retrieve storage layout issues error messages."""
        issues = []
        # Storage isn't applied to an ephemeral_deployment
        if self.ephemeral_deploy:
            return []
        if self.is_diskless:
            issues.append(
                "There are currently no storage devices.  Please add a "
                "storage device to be able to deploy this node."
            )
            return issues
        if not has_boot:
            issues.append(
                "Specify a storage device to be able to deploy this node."
            )
        if self.osystem == "esxi":
            # MAAS 2.6 added VMware ESXi storage support. To be backwards
            # compatible with previous versions of MAAS deploying with a Linux
            # layout is fine. In this case the default VMware ESXi storage
            # layout is created with a datastore. If the user applied the VMFS
            # storage layout a datastore must be defined as one will always be
            # created.
            if (
                VMFS6StorageLayout(self).is_layout()
                or VMFS7StorageLayout(self).is_layout()
            ):
                fs_groups = self.virtualblockdevice_set.filter(
                    filesystem_group__group_type=FILESYSTEM_GROUP_TYPE.VMFS6
                )
                if not fs_groups.exists():
                    issues.append(
                        "A datastore must be defined when deploying "
                        "VMware ESXi."
                    )
                    return issues
        # The remaining storage issue checks are only for Ubuntu, CentOS, and
        # RHEL. All other osystems storage isn't supported or in ESXi's case
        # we ignore unknown filesystems given.
        if self.osystem not in ["ubuntu", "centos", "rhel"]:
            return issues
        if not root_mounted:
            issues.append(
                "Mount the root '/' filesystem to be able to deploy this "
                "node."
            )
        if root_mounted and root_on_bcache and not boot_mounted:
            issues.append(
                "This node cannot be deployed because it cannot boot from a "
                "bcache volume. Mount /boot on a non-bcache device to be "
                "able to deploy this node."
            )
        if (
            not boot_mounted
            and arch == "arm64"
            and self.get_bios_boot_method() != "uefi"
        ):
            issues.append(
                "This node cannot be deployed because it needs a separate "
                "/boot partition.  Mount /boot on a device to be able to "
                "deploy this node."
            )
        if self.osystem in ["centos", "rhel"]:
            if any_bcache:
                issues.append(
                    "This node cannot be deployed because the selected "
                    "deployment OS, %s, does not support Bcache."
                    % self.osystem
                )
            if any_zfs:
                issues.append(
                    "This node cannot be deployed because the selected "
                    "deployment OS, %s, does not support ZFS." % self.osystem
                )
            # Upstream has completely removed support for BTRFS in
            # CentOS/RHEL 8. Check if '8' is in the distro_series so
            # this catches custom images as well.
            if any_btrfs and "8" in self.distro_series:
                issues.append(
                    "This node cannot be deployed because the selected "
                    "deployment OS release, %s %s, does not support BTRFS."
                    % (self.osystem, self.distro_series)
                )
        if any_vmfs:
            issues.append(
                "This node cannot be deployed because the selected "
                "deployment OS, %s, does not support VMFS6." % self.osystem
            )
        return issues

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
                if (parent.type != "physical" and on_bcache(parent)) or (
                    parent.get_effective_filesystem().fstype
                    in [
                        FILESYSTEM_TYPE.BCACHE_CACHE,
                        FILESYSTEM_TYPE.BCACHE_BACKING,
                    ]
                ):
                    return True
            return False

        has_boot = False
        root_mounted = False
        root_on_bcache = False
        any_bcache = False
        any_zfs = False
        any_vmfs = False
        any_btrfs = False
        boot_mounted = False
        arch, _ = self.split_arch()

        for block_device in self.current_config.blockdevice_set.all():
            if block_device.is_boot_disk():
                has_boot = True
            pt = block_device.get_partitiontable()
            if pt is not None:
                for partition in pt.partitions.all():
                    fs = partition.get_effective_filesystem()
                    if fs is None:
                        continue
                    if fs.mount_point == "/":
                        root_mounted = True
                        if on_bcache(block_device):
                            root_on_bcache = True
                    elif fs.mount_point == "/boot" and not on_bcache(
                        block_device
                    ):
                        boot_mounted = True
                    any_bcache |= fs.fstype in (
                        FILESYSTEM_TYPE.BCACHE_CACHE,
                        FILESYSTEM_TYPE.BCACHE_BACKING,
                    )
                    any_zfs |= fs.fstype == FILESYSTEM_TYPE.ZFSROOT
                    any_vmfs |= fs.fstype == FILESYSTEM_TYPE.VMFS6
                    any_btrfs |= fs.fstype == FILESYSTEM_TYPE.BTRFS
            else:
                fs = block_device.get_effective_filesystem()
                if fs is None:
                    continue
                if fs.mount_point == "/":
                    root_mounted = True
                    if on_bcache(block_device):
                        root_on_bcache = True
                elif fs.mount_point == "/boot" and not on_bcache(block_device):
                    boot_mounted = True
                any_bcache |= fs.fstype in (
                    FILESYSTEM_TYPE.BCACHE_CACHE,
                    FILESYSTEM_TYPE.BCACHE_BACKING,
                )
                any_zfs |= fs.fstype == FILESYSTEM_TYPE.ZFSROOT
                any_vmfs |= fs.fstype == FILESYSTEM_TYPE.VMFS6
                any_btrfs |= fs.fstype == FILESYSTEM_TYPE.BTRFS

        return self.retrieve_storage_layout_issues(
            has_boot,
            root_mounted,
            root_on_bcache,
            boot_mounted,
            arch,
            any_bcache,
            any_zfs,
            any_vmfs,
            any_btrfs,
        )

    def on_network(self):
        """Return true if the node is connected to a managed network."""
        for interface in self.current_config.interface_set.all():
            for link in interface.get_links():
                if (
                    link["mode"] != INTERFACE_LINK_TYPE.LINK_UP
                    and "subnet" in link
                ):
                    return True
        return False

    def _start_deployment(self):
        """Mark a node as being deployed."""
        from maasserver.models.event import Event
        from maasserver.models.scriptset import ScriptSet

        if not self.on_network():
            raise ValidationError(
                {"network": ["Node must be configured to use a network"]}
            )
        storage_layout_issues = self.storage_layout_issues()
        if len(storage_layout_issues) > 0:
            raise ValidationError({"storage": storage_layout_issues})
        # Ephemeral deployments need to be re-deployed on a power cycle
        # and will already be in a DEPLOYED state.
        if self.status == NODE_STATUS.ALLOCATED:
            self.update_status(NODE_STATUS.DEPLOYING)
        if self.ephemeral_deploy is False:
            script_set = ScriptSet.objects.create_installation_script_set(self)
            self.current_installation_script_set = script_set
        self.save()

        # Create a status message for DEPLOYING.
        Event.objects.create_node_event(self, EVENT_TYPES.DEPLOYING)

    def end_deployment(self):
        """Mark a node as successfully deployed."""
        # Avoid circular imports.
        from maasserver.models.event import Event

        self.update_status(NODE_STATUS.DEPLOYED)
        if self.enable_hw_sync:
            self.last_sync = datetime.now()
        self.update_deployment_time()
        self.save()

        # Create a status message for DEPLOYED.
        Event.objects.create_node_event(self, EVENT_TYPES.DEPLOYED)

    def update_deployment_time(self) -> None:
        from maasserver.models.event import Event

        Event.objects.create_node_event(
            self,
            EVENT_TYPES.IMAGE_DEPLOYED,
            event_description=f"deployed {self.osystem}/{self.distro_series}/{self.architecture}",
        )

    def ip_addresses(self, ifaces=None):
        """IP addresses allocated to this node.

        Return the current IP addresses for this Node, or the empty
        list if there are none.
        """
        # If the node has static IP addresses assigned they will be returned
        # before the dynamic IP addresses are returned. The dynamic IP
        # addresses will only be returned if the node has no static IP
        # addresses.
        ips = self.static_ip_addresses(ifaces=ifaces)
        if not ips:
            ips = self.dynamic_ip_addresses(ifaces=ifaces)
        return ips

    def static_ip_addresses(self, ifaces=None):
        """Static IP addresses allocated to this node."""
        # DHCP is included here because it is a configured type. Its not
        # just set randomly by the lease parser.
        if ifaces is None:
            ifaces = self.current_config.interface_set.all()
        return [
            ip_address.get_ip()
            for interface in ifaces
            for ip_address in interface.ip_addresses.all()
            if ip_address.ip
            and ip_address.alloc_type
            in [
                IPADDRESS_TYPE.DHCP,
                IPADDRESS_TYPE.AUTO,
                IPADDRESS_TYPE.STICKY,
                IPADDRESS_TYPE.USER_RESERVED,
            ]
        ]

    def dynamic_ip_addresses(self, ifaces=None):
        """Dynamic IP addresses allocated to this node."""
        if ifaces is None:
            ifaces = self.current_config.interface_set.all()
        return [
            ip_address.ip
            for interface in ifaces
            for ip_address in interface.ip_addresses.all()
            if (
                ip_address.ip
                and ip_address.alloc_type == IPADDRESS_TYPE.DISCOVERED
            )
        ]

    def get_interface_names(self):
        return list(
            self.current_config.interface_set.all().values_list(
                "name", flat=True
            )
        )

    def get_next_ifname(self, ifnames=None):
        """
        Scans the interfaces on this Node and returns the next free ifname in
        the format 'ethX', where X is zero or a positive integer.
        """
        if ifnames is None:
            ifnames = self.get_interface_names()
        used_ethX = []
        for ifname in ifnames:
            match = re.match("eth([0-9]+)", ifname)
            if match is not None:
                ifnum = int(match.group(1))
                used_ethX.append(ifnum)
        if len(used_ethX) == 0:
            return "eth0"
        else:
            ifnum = max(used_ethX) + 1
            return "eth%d" % ifnum

    def get_block_device_names(self):
        return list(
            self.current_config.blockdevice_set.all().values_list(
                "name", flat=True
            )
        )

    def get_next_block_device_name(self, block_device_names=None, prefix="sd"):
        """
        Scans the block devices on this Node and returns the next free block
        device name in the format '{prefix}X', where X is [a-z]+.
        """
        if block_device_names is None:
            block_device_names = self.get_block_device_names()
        for idx in count(0):
            name = BlockDevice._get_block_name_from_idx(idx, prefix=prefix)
            if name not in block_device_names:
                return name

    def tag_names(self):
        # We don't use self.tags.values_list here because this does not
        # take advantage of the cache.
        return [tag.name for tag in self.tags.all()]

    def clean_boot_disk(self):
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
                    raise ValidationError(
                        {
                            "boot_disk": [
                                "Cannot be set as the boot disk; already in-use "
                                "in %s '%s'."
                                % (
                                    filesystem.filesystem_group.get_nice_name(),
                                    filesystem.filesystem_group.name,
                                )
                            ]
                        }
                    )
                elif filesystem.cache_set is not None:
                    # Part of a cache set and cannot be set as the boot disk.
                    raise ValidationError(
                        {
                            "boot_disk": [
                                "Cannot be set as the boot disk; already in-use "
                                "in cache set '%s'."
                                % (filesystem.cache_set.name,)
                            ]
                        }
                    )

    def clean_boot_interface(self):
        """Check that this Node's boot interface (if present) belongs to this
        Node.

        It's possible, though very unlikely, that the boot interface we are
        seeing is already assigned to another Node. If this happens, we need to
        catch the failure as early as possible.
        """
        if (
            self.boot_interface is not None
            and self.id is not None
            and self.id != self.boot_interface.node_config.node_id
        ):
            raise ValidationError(
                {"boot_interface": ["Must be one of the node's interfaces."]}
            )

    def update_status(self, status, validate_transition=True):
        """Update the machine status, validating the transition by default.

        The previous status is returned.
        """
        current_status = self.status
        if validate_transition:
            self._validate_status_transition(current_status, status)
        self.status = status
        return current_status

    def _validate_status_transition(self, old_status, new_status):
        """Check a node's status transition against the node-status FSM."""
        if old_status is None:
            return
        if new_status == old_status:
            # No transition is always a safe transition.
            return
        elif old_status is None:
            # No transition to check as it has no previous status.
            return
        elif new_status in NODE_TRANSITIONS.get(old_status, ()):
            # Valid transition.
            stat = map_enum_reverse(NODE_STATUS, ignore=["DEFAULT"])
            maaslog.info(
                f"{self.hostname}: Status transition "
                f"from {stat[old_status]} to {stat[new_status]}"
            )
        else:
            # Transition not permitted.
            old = NODE_STATUS_CHOICES_DICT.get(old_status, "Unknown")
            new = NODE_STATUS_CHOICES_DICT.get(new_status, "Unknown")
            raise NodeStateViolation(f"Invalid transition: {old} -> {new}.")

    def clean_hostname_domain(self):
        # If you set the hostname to a name with dots, that you mean for that
        # to be the FQDN of the host. Se we check that a domain exists for
        # the remaining portion of the hostname.
        if "." in self.hostname:
            # They have specified an FQDN.  Split up the pieces, and throw
            # an error if the domain does not exist.
            name, domain_name = self.hostname.split(".", 1)
            domain = Domain.objects.filter(name=domain_name).first()
            if domain is None:
                raise ValidationError({"hostname": ["Nonexistant domain."]})
            self.hostname = name
            self.domain = domain
        elif self.domain is None:
            self.domain = Domain.objects.get_default_domain()

    def clean_pool(self):
        # Only machines can be in resource pools.
        if self.is_machine:
            if not self.pool:
                self.pool = ResourcePool.objects.get_default_resource_pool()
        elif self.pool:
            raise ValidationError(
                {"pool": ["Can't assign to a resource pool."]}
            )

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)
        self.clean_hostname_domain()
        self.clean_pool()
        self.clean_boot_disk()
        self.clean_boot_interface()

    def save(self, *args, **kwargs):
        # Reset the status_expires if not a monitored status. This prevents
        # a race condition seen in LP1603563 where an old status_expires caused
        # the node to do in a FAILED_RELEASING state due to an old
        # status_expire being set.
        if self.status not in MONITORED_STATUSES:
            self.status_expires = None
            if (
                "update_fields" in kwargs
                and "status_expires" not in kwargs["update_fields"]
            ):
                kwargs["update_fields"].append("status_expires")

        if self.enable_hw_sync and self.sync_interval is None:
            self.sync_interval = parse_systemd_interval(
                Config.objects.get_config("hardware_sync_interval")
            )

        if not self.hostname:
            self.set_random_hostname()
        super().save(*args, **kwargs)
        self._remove_orphaned_bmcs()

    def _remove_orphaned_bmcs(self):
        from maasserver.models.bmc import BMC

        BMC.objects.filter(node__isnull=True).exclude(
            bmc_type=BMC_TYPE.POD
        ).delete()

    def display_status(self):
        """Return status text as displayed to the user."""
        return NODE_STATUS_CHOICES_DICT[self.status]

    def display_memory(self):
        """Return memory in GiB."""
        # Commissioning gets all available memory to the system. However some
        # memory can be reserved by the motherboard(e.g for video memory) or
        # the kernel itself. Commissioning can't detect reserved RAM so show
        # the RAM in GiB to the first decimal place. Python rounds the float
        # which results in the correct value. For example a KVM virt is
        # configured with 2048 MiB of RAM but only 2047MiB is detectable.
        # 2047 / 1024 = 1.9990 which rounds to 2.0.
        return round(self.memory / 1024.0, 1)

    @property
    def physicalblockdevice_set(self):
        """Return `QuerySet` for all `PhysicalBlockDevice` assigned to node."""
        return PhysicalBlockDevice.objects.filter(
            node_config=self.current_config
        )

    @property
    def virtualblockdevice_set(self):
        """Return `QuerySet` for all `VirtualBlockDevice` assigned to node."""
        from maasserver.models.virtualblockdevice import VirtualBlockDevice

        return VirtualBlockDevice.objects.filter(
            node_config=self.current_config
        )

    @property
    def storage(self):
        """Return storage in megabytes.

        Compatility with API 1.0 this field needs to exist on the Node.
        """
        size = sum(
            block_device.size
            for block_device in self.current_config.blockdevice_set.all()
            if isinstance(block_device.actual_instance, PhysicalBlockDevice)
        )
        return size / 1000 / 1000

    def get_boot_disk(self):
        """Return the boot disk for this node."""
        if self.boot_disk is not None:
            return self.boot_disk.actual_instance
        else:
            # Fallback to using the first created physical block device as
            # the boot disk.
            block_devices = sorted(
                (
                    block_device.actual_instance
                    for block_device in self.current_config.blockdevice_set.all()
                    if isinstance(
                        block_device.actual_instance, PhysicalBlockDevice
                    )
                    and block_device.size >= MIN_BOOT_PARTITION_SIZE
                ),
                key=attrgetter("id"),
            )
            return block_devices[0] if block_devices else None

    def get_bios_boot_method(self):
        """Return the boot method the node's BIOS booted."""
        if self.bios_boot_method not in KNOWN_BIOS_BOOT_METHODS:
            if self.bios_boot_method:
                maaslog.warning(
                    " %s: Has a unknown BIOS boot method '%s'; "
                    "defaulting to '%s'."
                    % (
                        self.hostname,
                        self.bios_boot_method,
                        DEFAULT_BIOS_BOOT_METHOD,
                    )
                )
            # Work around bug #1899486.
            bmc_boot_method = get_bios_boot_from_bmc(self.bmc)
            if bmc_boot_method is not None:
                return bmc_boot_method
            else:
                return DEFAULT_BIOS_BOOT_METHOD
        else:
            return self.bios_boot_method

    def add_physical_interface(self, mac_address, name=None):
        """Add a new `PhysicalInterface` to `node` with `mac_address`."""
        # Avoid circular imports.
        from maasserver.models import PhysicalInterface, UnknownInterface

        if name is None:
            name = self.get_next_ifname()
        UnknownInterface.objects.filter(mac_address=mac_address).delete()
        numa_node = self.default_numanode if self.is_machine else None
        iface, created = PhysicalInterface.objects.get_or_create(
            mac_address=mac_address,
            defaults={
                "node_config": self.current_config,
                "name": name,
                "numa_node": numa_node,
            },
        )
        if not created and iface.node_config != self.current_config:
            # This MAC address is already registered to a different node.
            raise ValidationError(
                f"MAC address {mac_address} already in use "
                f"on {iface.node_config.node.hostname}."
            )
        return iface

    def get_metadata(self):
        """Return all Node metadata key, value pairs as a dict."""
        return {item.key: item.value for item in self.nodemetadata_set.all()}

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
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status])
            )

        self.start_commissioning(user)
        return self

    @classmethod
    @transactional
    def _set_status_expires(self, system_id, status=None):
        """Set the status_expires field on node."""
        try:
            node = Node.objects.get(system_id=system_id)
        except Node.DoesNotExist:
            return

        if status is None:
            status = node.status

        minutes = get_node_timeout(status)
        if minutes is not None:
            node.status_expires = now() + timedelta(minutes=minutes)
            node.save(update_fields=["status_expires"])

    @classmethod
    @transactional
    def _clear_status_expires(self, system_id):
        """Clear the status_expires field on node."""
        try:
            node = Node.objects.get(system_id=system_id)
        except Node.DoesNotExist:
            return

        node.status_expires = None
        node.save(update_fields=["status_expires"])

    @classmethod
    @transactional
    def _abort_all_tests(self, script_set_id):
        from maasserver.models import ScriptSet

        try:
            script_set = ScriptSet.objects.get(id=script_set_id)
        except ScriptSet.DoesNotExist:
            return

        qs = script_set.scriptresult_set.filter(
            status__in=SCRIPT_STATUS_RUNNING_OR_PENDING
        )
        qs.update(status=SCRIPT_STATUS.ABORTED, updated=now())

    @transactional
    def start_commissioning(
        self,
        user,
        enable_ssh=False,
        skip_bmc_config=False,
        skip_networking=False,
        skip_storage=False,
        commissioning_scripts=None,
        testing_scripts=None,
        script_input=None,
    ):
        """Install OS and self-test a new node.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to start and commission the node. This is already
            registered as a post-commit hook; it should not be added a second
            time.
        """
        from maasserver.models.event import Event
        from maasserver.models.scriptset import ScriptSet

        # Only commission if power type is configured.
        if self.power_type == "":
            raise UnknownPowerType(
                "Unconfigured power type. "
                "Please configure the power type and try again."
            )

        self._register_request_event(
            user,
            EVENT_TYPES.REQUEST_NODE_START_COMMISSIONING,
            action="start commissioning",
        )

        # Create a status message for COMMISSIONING.
        Event.objects.create_node_event(self, EVENT_TYPES.COMMISSIONING)

        # Set the commissioning options on the node.
        self.enable_ssh = enable_ssh
        self.skip_networking = skip_networking
        self.skip_storage = skip_storage

        # Generate the specific user data for commissioning this node.
        commissioning_user_data = generate_user_data_for_status(
            node=self, status=NODE_STATUS.COMMISSIONING
        )

        # Create a new ScriptSet for this commissioning run.
        commis_script_set = ScriptSet.objects.create_commissioning_script_set(
            self, scripts=commissioning_scripts, script_input=script_input
        )

        # The UI displays the latest ScriptResult for all scripts which have
        # ever been run. Always create the BMC configuration ScriptResults so
        # MAAS can log that they were skipped. This avoids user confusion when
        # BMC detection is run previously on the node but they don't want BMC
        # detection to run again.
        if skip_bmc_config or self.split_arch()[0] == "s390x":
            if self.split_arch()[0] == "s390x":
                result = b"INFO: BMC detection not supported on S390X"
            else:
                result = (
                    "INFO: User %s (%s) has choosen to skip BMC configuration "
                    "during commissioning\n" % (user.get_username(), user.id)
                ).encode()
            for script_result in commis_script_set.scriptresult_set.filter(
                script__tags__contains=["bmc-config"]
            ):
                script_result.store_result(
                    exit_status=0,
                    output=result,
                    stdout=result,
                    result=b"status: skipped",
                )

        # Create a new ScriptSet for any tests to be run after commissioning.
        try:
            testing_script_set = ScriptSet.objects.create_testing_script_set(
                self, scripts=testing_scripts, script_input=script_input
            )
        except NoScriptsFound:
            # Commissioning can run without running tests after.
            testing_script_set = []
            pass

        config = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "default_osystem",
                "default_distro_series",
                "default_min_hwe_kernel",
            ]
        )

        # Testing configured networking requires netplan which is only
        # available in 18.04+
        if config["commissioning_distro_series"] == "xenial":
            apply_configured_networking_found = False
            for script_result in chain(commis_script_set, testing_script_set):
                if (
                    script_result.script
                    and script_result.script.apply_configured_networking
                ):
                    apply_configured_networking_found = True
                    break
            if apply_configured_networking_found:
                commis_script_set.delete()
                if testing_script_set:
                    testing_script_set.delete()
                raise ValidationError(
                    "Unable to run script which configures custom networking "
                    "when using Ubuntu Xenial 16.04 as the ephemeral "
                    "operating system."
                )

        self.current_commissioning_script_set = commis_script_set
        if testing_script_set:
            self.current_testing_script_set = testing_script_set

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
        old_status = self.update_status(NODE_STATUS.COMMISSIONING)
        self.owner = user

        # Set to default_min_hwe_kernel if min_hwe_kernel not given, and
        # default_min_hwe_kernel is defined. Should ensure that set kernels
        # are respected on commission, while still allowing the MAAS-wide
        # defaults to be set.
        if not self.min_hwe_kernel and config["default_min_hwe_kernel"]:
            self.min_hwe_kernel = config["default_min_hwe_kernel"]
        self.save()

        try:
            # Node.start() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            starting = self._start(
                user,
                commissioning_user_data,
                old_status,
                allow_power_cycle=True,
                config=config,
            )
        except Exception as error:
            self.update_status(old_status)
            self.enable_ssh = False
            self.skip_networking = False
            self.skip_storage = False
            self.save()
            maaslog.error(
                "%s: Could not start node for commissioning: %s",
                self.hostname,
                error,
            )
            # Let the exception bubble up, since the UI or API will have to
            # deal with it.
            raise
        else:
            # Don't permit naive mocking of start(); it causes too much
            # confusion when testing. Return a Deferred from side_effect.
            assert isinstance(starting, Deferred) or starting is None

            post_commit().addCallback(
                callOutToDatabase, Node._set_status_expires, self.system_id
            )

            if starting is None:
                starting = post_commit()
                # MAAS cannot start the node itself.
                is_starting = False
            else:
                # MAAS can direct the node to start.
                is_starting = True

            starting.addCallback(
                callOut,
                self._start_commissioning_async,
                is_starting,
                self.hostname,
            )

            def eb_start(failure, hostname):
                maaslog.error(
                    "%s: Could not start node for commissioning: %s",
                    hostname,
                    failure.getErrorMessage(),
                )
                return failure  # Propagate.

            return starting.addErrback(eb_start, self.hostname)

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
                "must be started manually",
                hostname,
            )

    @transactional
    def start_testing(
        self, user, enable_ssh=False, testing_scripts=None, script_input=None
    ):
        """Run tests on a node."""
        from maasserver.models.event import Event
        from maasserver.models.scriptset import ScriptSet

        if not user.has_perm(NodePermission.edit, self):
            # You can't enter test mode on a node you don't own,
            # unless you're an admin.
            raise PermissionDenied()

        # Only test if power type is configured.
        if self.power_type == "":
            raise UnknownPowerType(
                "Unconfigured power type. "
                "Please configure the power type and try again."
            )

        # If this is an enlisted node make sure commissioning during enlistment
        # finished successfully.
        if (
            self.status == NODE_STATUS.NEW
            and not self.current_commissioning_script_set
        ):
            raise ValidationError(
                "Unable to start machine testing; this node has never been "
                "commissioned. Please use the 'Commission' action to "
                "commission & test this machine."
            )

        # Create a new ScriptSet for the tests to be run.
        script_set = ScriptSet.objects.create_testing_script_set(
            self, scripts=testing_scripts, script_input=script_input
        )
        commissioning_distro_series = Config.objects.get_config(
            "commissioning_distro_series"
        )
        # Additional validation for when starting testing and not
        # commissioning + testing.
        for script_result in script_set:
            for parameter in script_result.parameters.values():
                # If no interface is configured the ParametersForm sets a place
                # holder, 'all'. This works when commissioning as the default
                # network settings will be applied.
                if (
                    parameter["type"] == "interface"
                    and parameter["value"] == "all"
                ):
                    script_set.delete()
                    raise ValidationError(
                        "An interface must be configured to run "
                        "network testing!"
                    )
            if (
                NODE_STATUS.DEPLOYED in (self.status, self.previous_status)
                and script_result.script.destructive
            ):
                script_set.delete()
                raise ValidationError(
                    "Unable to run destructive test while deployed!"
                )
            if (
                commissioning_distro_series == "xenial"
                and script_result.script
                and script_result.script.apply_configured_networking
            ):
                script_set.delete()
                raise ValidationError(
                    "Unable to run script which configures custom networking "
                    "when using Ubuntu Xenial 16.04 as the ephemeral "
                    "operating system."
                )

        self.current_testing_script_set = script_set

        self._register_request_event(
            user,
            EVENT_TYPES.REQUEST_NODE_START_TESTING,
            action="start testing",
        )

        # Create a status message for COMMISSIONING.
        Event.objects.create_node_event(self, EVENT_TYPES.TESTING)

        # Set the test options on the node.
        self.enable_ssh = enable_ssh

        # Generate the specific user data for testing this node.
        testing_user_data = generate_user_data_for_status(
            node=self, status=NODE_STATUS.TESTING
        )

        # We need to mark the node as TESTING now to avoid a race when starting
        # multiple nodes. We hang on to old_status just in case the power
        # action fails.
        old_status = self.update_status(NODE_STATUS.TESTING)
        # Testing can be run in statuses which define an owner, only set one
        # if the node has no owner
        if self.owner is None:
            self.owner = user
        self.save()

        try:
            starting = self._start(
                user, testing_user_data, old_status, allow_power_cycle=True
            )
        except Exception as error:
            self.update_status(old_status)
            self.enable_ssh = False
            self.save()
            maaslog.error(
                "%s: Could not start testing for node: %s",
                self.hostname,
                error,
            )
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

            post_commit().addCallback(
                callOutToDatabase, Node._set_status_expires, self.system_id
            )

            starting.addCallback(
                callOut, self._start_testing_async, is_starting, self.hostname
            )

            def eb_start(failure, hostname):
                maaslog.error(
                    "%s: Could not start testing for node: %s",
                    hostname,
                    failure.getErrorMessage(),
                )
                return failure  # Propagate.

            return starting.addErrback(eb_start, self.hostname)

    @classmethod
    @asynchronous
    def _start_testing_async(cls, is_cycling, hostname):
        """Start testing, the post-commit bits.

        :param is_cycling: A boolean indicating if MAAS is able to start this
            node itself, or if manual intervention is needed.
        :param hostname: The node's hostname, for logging.
        """
        if is_cycling:
            maaslog.info("%s: Testing starting", hostname)
        else:
            maaslog.warning(
                "%s: Could not start testing the node; it "
                "must be started manually",
                hostname,
            )

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
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status])
            )

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
                self.hostname,
                error,
            )
            raise
        else:
            # Avoid circular imports.
            from maasserver.models.event import Event

            self._register_request_event(
                user,
                EVENT_TYPES.REQUEST_NODE_ABORT_COMMISSIONING,
                action="abort commissioning",
                comment=comment,
            )

            # Create a status message for ABORTED_COMMISSIONING.
            Event.objects.create_node_event(
                self, EVENT_TYPES.ABORTED_COMMISSIONING
            )

            # Don't permit naive mocking of stop(); it causes too much
            # confusion when testing. Return a Deferred from side_effect.
            assert isinstance(stopping, Deferred) or stopping is None

            post_commit().addCallback(
                callOutToDatabase, Node._clear_status_expires, self.system_id
            )
            post_commit().addCallback(
                callOutToDatabase,
                Node._abort_all_tests,
                self.current_commissioning_script_set_id,
            )
            post_commit().addCallback(
                callOutToDatabase,
                Node._abort_all_tests,
                self.current_testing_script_set_id,
            )

            if stopping is None:
                stopping = post_commit()
                # MAAS cannot stop the node itself.
                is_stopping = False
            else:
                # MAAS can direct the node to stop.
                is_stopping = True

            stopping.addCallback(
                callOut,
                self._abort_commissioning_async,
                is_stopping,
                self.hostname,
                self.system_id,
            )

            def eb_abort(failure, hostname):
                maaslog.error(
                    "%s: Error when aborting commissioning: %s",
                    hostname,
                    failure.getErrorMessage(),
                )
                return failure  # Propagate.

            return stopping.addErrback(eb_abort, self.hostname)

    @transactional
    def abort_testing(self, user, comment=None):
        """Power off a testing node and set its status to the previous status.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to stop the node. This is already registered as a
            post-commit hook; it should not be added a second time.
        """
        if self.status != NODE_STATUS.TESTING:
            raise NodeStateViolation(
                "Cannot abort testing of a non-testing node: "
                "node %s is in state %s."
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status])
            )

        try:
            # Node.stop() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            stopping = self._stop(user)
        except Exception as error:
            maaslog.error(
                "%s: Error when aborting testing: %s", self.hostname, error
            )
            raise
        else:
            # Avoid circular imports.
            from maasserver.models.event import Event

            self._register_request_event(
                user,
                EVENT_TYPES.REQUEST_NODE_ABORT_TESTING,
                action="abort testing",
                comment=comment,
            )

            # Create a status message for ABORTED_TESTING.
            Event.objects.create_node_event(self, EVENT_TYPES.ABORTED_TESTING)

            # Don't permit naive mocking of stop(); it causes too much
            # confusion when testing. Return a Deferred from side_effect.
            assert isinstance(stopping, Deferred) or stopping is None

            post_commit().addCallback(
                callOutToDatabase, Node._clear_status_expires, self.system_id
            )
            post_commit().addCallback(
                callOutToDatabase,
                Node._abort_all_tests,
                self.current_testing_script_set_id,
            )

            if stopping is None:
                stopping = post_commit()
                # MAAS cannot stop the node itself.
                is_stopping = False
            else:
                # MAAS can direct the node to stop.
                is_stopping = True

            if self.previous_status == NODE_STATUS.COMMISSIONING:
                # Commissioning automatically starts testings of short hardware
                # scripts. Allow the user to abort testing and go into a ready
                # state to be able to use the node right away.
                status = NODE_STATUS.READY
            else:
                status = self.previous_status

            stopping.addCallback(
                callOut,
                self._abort_testing_async,
                is_stopping,
                self.hostname,
                self.system_id,
                status,
            )

            def eb_abort(failure, hostname):
                maaslog.error(
                    "%s: Error when aborting testing: %s",
                    hostname,
                    failure.getErrorMessage(),
                )
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
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status])
            )

        try:
            stop_workflow(f"deploy:{self.system_id}")

            # Node.stop() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            stopping = self._stop(user)
        except Exception as error:
            maaslog.error(
                "%s: Error when aborting deployment: %s", self.hostname, error
            )
            raise
        else:
            # Avoid circular imports.
            from maasserver.models.event import Event

            self._register_request_event(
                user,
                EVENT_TYPES.REQUEST_NODE_ABORT_DEPLOYMENT,
                action="abort deploying",
                comment=comment,
            )

            # Create a status message for ABORTED_DEPLOYMENT.
            Event.objects.create_node_event(
                self, EVENT_TYPES.ABORTED_DEPLOYMENT
            )

            # Don't permit naive mocking of stop(); it causes too much
            # confusion when testing. Return a Deferred from side_effect.
            assert isinstance(stopping, Deferred) or stopping is None

            post_commit().addCallback(
                callOutToDatabase, Node._clear_status_expires, self.system_id
            )
            post_commit().addCallback(
                callOutToDatabase,
                transactional(Node._clear_deployment_resources),
                self.id,
            )
            post_commit().addCallback(
                callOutToDatabase,
                Node._abort_all_tests,
                self.current_installation_script_set_id,
            )

            if stopping is None:
                stopping = post_commit()
                # MAAS cannot stop the node itself.
                is_stopping = False
            else:
                # MAAS can direct the node to stop.
                is_stopping = True

            stopping.addCallback(
                callOut,
                self._abort_deploying_async,
                is_stopping,
                self.hostname,
                self.system_id,
            )

            def eb_abort(failure, hostname):
                maaslog.error(
                    "%s: Error when aborting deployment: %s",
                    hostname,
                    failure.getErrorMessage(),
                )
                return failure  # Propagate.

            return stopping.addErrback(eb_abort, self.hostname)

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
                callOut,
                maaslog.info,
                "%s: Commissioning aborted, stopping machine",
                hostname,
            )
        else:
            return d.addCallback(
                callOut,
                maaslog.warning,
                "%s: Could not stop node to abort "
                "commissioning; it must be stopped manually",
                hostname,
            )

    @classmethod
    @asynchronous
    def _abort_testing_async(cls, is_stopping, hostname, system_id, status):
        """Abort testing, the post-commit bits.

        :param is_stopping: A boolean indicating if MAAS is able to stop this
            node itself, or if manual intervention is needed.
        :param hostname: The node's hostname, for logging.
        :param system_id: The system ID for the node.
        """
        d = deferToDatabase(cls._set_status, system_id, status=status)
        if is_stopping:
            return d.addCallback(
                callOut,
                maaslog.info,
                "%s: Testing aborted, stopping node",
                hostname,
            )
        else:
            return d.addCallback(
                callOut,
                maaslog.warning,
                "%s: Could not stop node to abort "
                "testing; it must be stopped manually",
                hostname,
            )

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
            cls._set_status, system_id, status=NODE_STATUS.ALLOCATED
        )
        if is_stopping:
            return d.addCallback(
                callOut,
                maaslog.info,
                "%s: Deployment aborted, stopping machine",
                hostname,
            )
        else:
            return d.addCallback(
                callOut,
                maaslog.warning,
                "%s: Could not stop node to abort "
                "deployment; it must be stopped manually",
                hostname,
            )

    def delete(self, *args, **kwargs):
        """Delete this node."""
        from maasserver.secrets import SecretManager

        delete_node_secrets = partial(
            SecretManager().delete_all_object_secrets,
            self.as_node(),
        )

        bmc = self.bmc
        if (
            self.node_type == NODE_TYPE.MACHINE
            and bmc is not None
            and bmc.bmc_type == BMC_TYPE.POD
            and Capabilities.COMPOSABLE in bmc.capabilities
        ):
            pod = bmc.as_pod()

            client_idents = pod.get_client_identifiers()

            @transactional
            def _save(machine_id, pod_id, result):
                from maasserver.models.bmc import Pod

                machine = Machine.objects.filter(id=machine_id).first()
                if machine is not None:
                    maaslog.info("%s: Deleting machine", machine.hostname)
                    # delete related VirtualMachine, if any
                    from maasserver.models.virtualmachine import VirtualMachine

                    VirtualMachine.objects.filter(
                        machine_id=machine_id
                    ).delete()
                    delete_node_secrets()
                    super(Node, machine).delete()

                if isinstance(result, Failure):
                    maaslog.warning(
                        f"{self.hostname}: Failure decomposing machine: {result.value}"
                    )
                    return

                pod = Pod.objects.filter(id=pod_id).first()
                if pod is not None:
                    pod.sync_hints(result)

            maaslog.info("%s: Decomposing machine", self.hostname)

            d = post_commit()
            d.addCallback(lambda _: getClientFromIdentifiers(client_idents))
            d.addCallback(
                decompose_machine,
                pod.power_type,
                self.get_power_parameters(),
                pod_id=pod.id,
                name=pod.name,
            )
            d.addBoth(
                lambda result: (
                    deferToDatabase(_save, self.id, pod.id, result)
                )
            )
        else:
            maaslog.info("%s: Deleting node", self.hostname)

            # Delete my BMC if no other Nodes are using it.
            if (
                self.bmc is not None
                and self.bmc.bmc_type == BMC_TYPE.BMC
                and self.bmc.node_set.count() == 1
            ):
                # Delete my orphaned BMC.
                maaslog.info(
                    "%s: Deleting my BMC '%s'", self.hostname, self.bmc
                )
                self.bmc.delete()

            delete_node_secrets()
            super().delete(*args, **kwargs)

    def set_random_hostname(self):
        """Set a random `hostname`."""
        self.hostname = petname.generate()

    def get_effective_power_type(self):
        """Get power-type to use for this node.

        If no power type has been set for the node, raise
        UnknownPowerType.
        """
        if self.bmc is None or self.bmc.power_type == "":
            raise UnknownPowerType("Node power type is unconfigured")
        return self.bmc.power_type

    def get_effective_kernel_options(self, default_kernel_opts=None):
        """Return a string with kernel commandline."""
        options = list(
            self.tags.exclude(kernel_opts="")
            .order_by("name")
            .values_list("kernel_opts", flat=True)
        )
        if default_kernel_opts:
            options.insert(0, default_kernel_opts)
        return " ".join(options)

    def get_osystem(self, default: str | object = undefined) -> str:
        """Return the operating system to install that node."""
        use_default_osystem = self.osystem is None or self.osystem == ""
        if use_default_osystem:
            if default is undefined:
                default = Config.objects.get_config("default_osystem")
            return default
        else:
            return self.osystem

    def get_distro_series(self, default: str | object = undefined) -> str:
        """Return the distro series to install that node."""
        use_default_osystem = self.osystem is None or self.osystem == ""
        use_default_distro_series = (
            self.distro_series is None or self.distro_series == ""
        )
        if use_default_osystem and use_default_distro_series:
            if default is undefined:
                default = Config.objects.get_config("default_distro_series")
            return default
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
            self.license_key is None or self.license_key == ""
        )
        if use_global_license_key:
            osystem = self.get_osystem()
            distro_series = self.get_distro_series()
            try:
                return LicenseKey.objects.get_license_key(
                    osystem, distro_series
                )
            except LicenseKey.DoesNotExist:
                return ""
        else:
            return self.license_key

    def get_effective_power_parameters(self):
        """Return effective power parameters, including any defaults."""
        power_params = self.get_power_parameters().copy()

        power_params.setdefault("system_id", self.system_id)
        # TODO: This default ought to be in the virsh template.
        if self.bmc is not None and self.bmc.power_type == "virsh":
            power_params.setdefault("power_address", "qemu://localhost/system")
            power_params.setdefault("power_id", self.system_id)

        if self.bmc is not None and self.bmc.power_type == "ipmi":
            power_params.setdefault("power_off_mode", "")

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
            return PowerInfo(False, False, False, False, None, None)
        else:
            if power_type == "manual" or self.node_type in (
                NODE_TYPE.REGION_CONTROLLER,
                NODE_TYPE.REGION_AND_RACK_CONTROLLER,
            ):
                can_be_started = False
                can_be_stopped = False
            else:
                can_be_started = True
                can_be_stopped = True
            power_driver = PowerDriverRegistry.get_item(power_type)
            if power_driver is not None:
                can_be_queried = power_driver.queryable
                can_set_boot_order = power_driver.can_set_boot_order
            else:
                can_be_queried = False
                can_set_boot_order = False
            return PowerInfo(
                can_be_started,
                can_be_stopped,
                can_be_queried,
                can_set_boot_order,
                power_type,
                power_params,
            )

    def _get_boot_order(self, network_boot=None):
        """Return the expected boot order of the Node."""
        # Return the list of known physical devices. Give preference to the
        # currently defined boot device if available. Return all devices
        # incase the system is setup in redundency(RAID or multiple NICs
        # can route to MAAS).
        interfaces = sorted(
            (
                iface.serialize()
                for iface in self.current_config.interface_set.all()
            ),
            key=lambda iface: (
                iface["id"] != self.boot_interface_id,
                iface["id"],
            ),
        )
        if self.boot_disk_id:
            boot_disk_id = self.boot_disk.actual_instance.id
        else:
            boot_disk_id = None
        block_devices = sorted(
            (
                bd.actual_instance.serialize()
                for bd in self.current_config.blockdevice_set.all()
                if isinstance(bd.actual_instance, PhysicalBlockDevice)
            ),
            key=lambda bd: (
                bd["id"] != boot_disk_id,
                bd["id"],
            ),
        )

        if network_boot is None:
            if self.ephemeral_deploy:
                network_boot = True
            elif self.status == NODE_STATUS.EXITING_RESCUE_MODE:
                network_boot = self.previous_status != NODE_STATUS.DEPLOYED
            else:
                network_boot = self.status != NODE_STATUS.DEPLOYED

        if network_boot:
            return interfaces + block_devices
        else:
            return block_devices + interfaces

    def set_boot_order(self, network_boot=None):
        """Remotely configure the Node to network or local boot.

        If supported by the power driver this function will configure a
        Node remotely to either boot from the network or boot locally.
        This isn't done as part of self.set_netboot() as power commands
        already use self._power_control_node() which figures out which
        rack controller to issue power commands from.
        """
        power_info = self.get_effective_power_info()
        # Only send RPC call to set boot order if power driver
        # supports it.
        if not power_info.can_set_boot_order:
            return

        boot_order = self._get_boot_order(network_boot)

        @asynchronous
        def configure_boot_order():
            return self._power_control_node(
                succeed(None), None, power_info, boot_order
            )

        configure_boot_order().wait(120)

    def get_effective_special_filesystems(self):
        """Return special filesystems for the node."""
        deployed_statuses = {
            NODE_STATUS.ALLOCATED,
            NODE_STATUS.DEPLOYING,
            NODE_STATUS.DEPLOYED,
            NODE_STATUS.FAILED_DEPLOYMENT,
            NODE_STATUS.RELEASING,
            NODE_STATUS.FAILED_RELEASING,
            NODE_STATUS.DISK_ERASING,
            NODE_STATUS.FAILED_DISK_ERASING,
        }
        testing_statuses = {
            NODE_STATUS.RESCUE_MODE,
            NODE_STATUS.ENTERING_RESCUE_MODE,
            NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
            NODE_STATUS.EXITING_RESCUE_MODE,
            NODE_STATUS.FAILED_EXITING_RESCUE_MODE,
            NODE_STATUS.TESTING,
            NODE_STATUS.FAILED_TESTING,
        }
        before_testing_statuses = {
            NODE_STATUS.DEPLOYED,
            NODE_STATUS.FAILED_DEPLOYMENT,
            NODE_STATUS.FAILED_RELEASING,
            NODE_STATUS.FAILED_DISK_ERASING,
        }
        acquired = self.status in deployed_statuses or (
            self.status in testing_statuses
            and self.previous_status in before_testing_statuses
        )
        # loop over full queryset since it's usually prefetched:
        return [
            fs
            for fs in self.current_config.filesystem_set.all()
            if fs.block_device_id is None
            and fs.partition_id is None
            and fs.acquired == acquired
        ]

    @staticmethod
    @asynchronous
    @inlineCallbacks
    def confirm_power_driver_operable(client, power_type, conn_ident):
        @transactional
        def _get_rack_controller_fqdn(system_id):
            rack_controllers = RackController.objects.filter(
                system_id=system_id
            ).select_related("domain")
            if len(rack_controllers) > 0:
                return rack_controllers[0].fqdn

        missing_packages = yield power_driver_check(client, power_type)
        if len(missing_packages) > 0:
            missing_packages = sorted(missing_packages)
            if len(missing_packages) > 2:
                missing_packages = [
                    ", ".join(missing_packages[:-1]),
                    missing_packages[-1],
                ]
            package_list = " and ".join(missing_packages)
            fqdn = yield deferToDatabase(_get_rack_controller_fqdn, conn_ident)
            if fqdn:
                conn_ident = fqdn
            raise PowerActionFail(
                "Power control software is missing from the rack "
                "controller '%s'. To proceed, "
                "install the %s package%s."
                % (
                    conn_ident,
                    package_list,
                    "s" if len(missing_packages) > 1 else "",
                )
            )

    def acquire(
        self,
        user,
        agent_name="",
        comment=None,
        bridge_all=False,
        bridge_type=None,
        bridge_stp=None,
        bridge_fd=None,
    ):
        """Mark commissioned node as acquired by the given user."""
        assert self.owner is None or self.owner == user

        self._create_acquired_filesystems()
        self._register_request_event(
            user,
            EVENT_TYPES.REQUEST_NODE_ACQUIRE,
            action="acquire",
            comment=comment,
        )
        self.update_status(NODE_STATUS.ALLOCATED)
        self.owner = user
        self.agent_name = agent_name
        if bridge_all:
            self._create_acquired_bridges(
                bridge_type=bridge_type,
                bridge_stp=bridge_stp,
                bridge_fd=bridge_fd,
            )
        self.save()
        maaslog.info("%s: allocated to user %s", self.hostname, user.username)

    def set_zone(self, zone):
        """Set this node's zone"""
        old_zone_name = self.zone.name
        self.zone = zone
        self.save()
        maaslog.info(
            "%s: moved from %s zone to %s zone."
            % (self.hostname, old_zone_name, self.zone.name)
        )

    def start_disk_erasing(
        self, user, comment=None, secure_erase=None, quick_erase=None
    ):
        """Erase the disks on a node.

        :return: a `Deferred` which contains the post-commit tasks that are
            required to run to start and erase the node. This is already
            registered as a post-commit hook; it should not be added a second
            time.
        """
        # Generate the user data based on the global options and the passed
        # configuration.
        config = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "default_osystem",
                "default_distro_series",
                "disk_erase_with_secure_erase",
                "disk_erase_with_quick_erase",
            ]
        )
        use_secure_erase = config["disk_erase_with_secure_erase"]
        use_quick_erase = config["disk_erase_with_quick_erase"]
        if secure_erase is not None:
            use_secure_erase = secure_erase
        if quick_erase is not None:
            use_quick_erase = quick_erase
        disk_erase_user_data = generate_user_data_for_status(
            node=self,
            status=NODE_STATUS.DISK_ERASING,
            extra_content={
                "secure_erase": use_secure_erase,
                "quick_erase": use_quick_erase,
            },
        )

        self._register_request_event(
            user,
            EVENT_TYPES.REQUEST_NODE_ERASE_DISK,
            action="start disk erasing",
            comment=comment,
        )

        # Change the status of the node now to avoid races when starting
        # nodes in bulk.
        old_status = self.update_status(NODE_STATUS.DISK_ERASING)
        self.save()

        try:
            # Node.start() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            starting = self._start(
                user,
                disk_erase_user_data,
                old_status,
                allow_power_cycle=True,
                config=config,
            )
        except Exception as error:
            # We always mark the node as failed here, although we could
            # potentially move it back to the state it was in previously. For
            # now, though, this is safer, since it marks the node as needing
            # attention.
            self.update_status(NODE_STATUS.FAILED_DISK_ERASING)
            self.save()
            maaslog.error(
                "%s: Could not start node for disk erasure: %s",
                self.hostname,
                error,
            )
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
                callOut,
                self._start_disk_erasing_async,
                is_starting,
                self.hostname,
            )

            # If there's an error, reset the node's status.
            starting.addErrback(
                callOutToDatabase,
                Node._set_status,
                self.system_id,
                status=NODE_STATUS.FAILED_DISK_ERASING,
            )

            def eb_start(failure, hostname):
                maaslog.error(
                    "%s: Could not start node for disk erasure: %s",
                    hostname,
                    failure.getErrorMessage(),
                )
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
                "must be started manually",
                hostname,
            )

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
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status])
            )

        try:
            # Node.stop() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            stopping = self._stop(user)
        except Exception as error:
            maaslog.error(
                "%s: Error when aborting disk erasure: %s",
                self.hostname,
                error,
            )
            raise
        else:
            # Avoid circular imports.
            from maasserver.models.event import Event

            self._register_request_event(
                user,
                EVENT_TYPES.REQUEST_NODE_ABORT_ERASE_DISK,
                action="abort disk erasing",
                comment=comment,
            )

            # Create a status message for ABORTED_DISK_ERASING.
            Event.objects.create_node_event(
                self, EVENT_TYPES.ABORTED_DISK_ERASING
            )

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
                callOut,
                self._abort_disk_erasing_async,
                is_stopping,
                self.hostname,
                self.system_id,
            )

            def eb_abort(failure, hostname):
                maaslog.error(
                    "%s: Error when aborting disk erasure: %s",
                    hostname,
                    failure.getErrorMessage(),
                )
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
            cls._set_status, system_id, status=NODE_STATUS.FAILED_DISK_ERASING
        )
        if is_stopping:
            return d.addCallback(
                callOut, maaslog.info, "%s: Disk erasing aborted", hostname
            )
        else:
            return d.addCallback(
                callOut,
                maaslog.warning,
                "%s: Could not stop node to abort "
                "disk erasure; it must be stopped manually",
                hostname,
            )

    def abort_operation(self, user, comment=None):
        """Abort the current operation."""
        if self.status == NODE_STATUS.DISK_ERASING:
            self.abort_disk_erasing(user, comment)
        elif self.status == NODE_STATUS.COMMISSIONING:
            self.abort_commissioning(user, comment)
        elif self.status == NODE_STATUS.DEPLOYING:
            self.abort_deploying(user, comment)
        elif self.status == NODE_STATUS.TESTING:
            self.abort_testing(user, comment)
        else:
            raise NodeStateViolation(
                "Cannot abort in current state: "
                "node %s is in state %s."
                % (self.system_id, NODE_STATUS_CHOICES_DICT[self.status])
            )

    def start_releasing(
        self, user, comment=None, scripts=None, script_input=None, force=False
    ):
        """Start the release process for the machine."""
        from maasserver.models import ScriptSet

        if scripts is None:
            scripts = []

        self.maybe_delete_pods(not force)

        config = Config.objects.get_configs(
            [
                "commissioning_osystem",
                "commissioning_distro_series",
                "default_osystem",
                "default_distro_series",
                "disk_erase_with_secure_erase",
                "disk_erase_with_quick_erase",
                "enable_disk_erasing_on_release",
            ]
        )

        if config.get("enable_disk_erasing_on_release"):
            scripts.append("wipe-disks")

        if not scripts:
            self.release(user, comment)
            return

        self.current_release_script_set = (
            ScriptSet.objects.create_release_script_set(
                self, scripts=scripts, script_input=script_input
            )
        )
        self.save()

        template_file = os.path.join(
            get_userdata_template_dir(), "script_runner.template"
        )
        user_data = generate_user_data(self, template_file)

        failed_status = NODE_STATUS.FAILED_RELEASING
        # Before machine release scripts were introduced there was Erase Disk
        # functionality. We want to maintain backward compatible statuses
        # to be reported when only "wipe-disk" script is executed.
        if len(scripts) == 1 and "wipe-disks" in scripts:
            self._register_request_event(
                user,
                EVENT_TYPES.REQUEST_NODE_ERASE_DISK,
                action="start disk erasing",
                comment=comment,
            )
            old_status = self.update_status(NODE_STATUS.DISK_ERASING)
            failed_status = NODE_STATUS.FAILED_DISK_ERASING
        else:
            self._register_request_event(
                user,
                EVENT_TYPES.REQUEST_NODE_RELEASE,
                action="start node releasing",
                comment=comment,
            )

            old_status = self.update_status(NODE_STATUS.RELEASING)

        self.save()

        try:
            # Node.start() has synchronous and asynchronous parts, so catch
            # exceptions arising synchronously, and chain callbacks to the
            # Deferred it returns for the asynchronous (post-commit) bits.
            starting = self._start(
                user,
                user_data,
                old_status,
                allow_power_cycle=True,
                config=config,
            )
        except Exception as error:
            # We always mark the node as failed here, although we could
            # potentially move it back to the state it was in previously. For
            # now, though, this is safer, since it marks the node as needing
            # attention.
            self.update_status(failed_status)
            self.save()
            maaslog.error(
                f"{self.hostname}: Could not start node for release: {error}"
            )
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

            @asynchronous
            def async_start(is_starting, hostname):
                if is_starting:
                    maaslog.info(f"{hostname}: Release started")
                else:
                    maaslog.warning(
                        f"{hostname}: Could not start node for release; it "
                        "must be started manually",
                    )

            starting.addCallback(
                callOut,
                async_start,
                is_starting,
                self.hostname,
            )

            # If there's an error, reset the node's status.
            starting.addErrback(
                callOutToDatabase,
                Node._set_status,
                self.system_id,
                status=failed_status,
            )

            def eb_start(failure, hostname):
                maaslog.error(
                    f"{hostname}: Could not start node for "
                    f"releasing: {failure.getErrorMessage()}",
                )
                return failure  # Propagate.

            return starting.addErrback(eb_start, self.hostname)

    def release(self, user=None, comment=None):
        self._register_request_event(
            user,
            EVENT_TYPES.REQUEST_NODE_RELEASE,
            action="release",
            comment=comment,
        )
        self._release(user)

    def _release(self, user=None):
        """Mark allocated or reserved node as available again and power off."""
        # Avoid circular imports.
        from maasserver.models.event import Event

        maaslog.info("%s: Releasing node", self.hostname)

        # Don't perform stop the node if its already off. Doing so will
        # place an action in the power registry which is not needed and can
        # block a following deploy action. See bug 1453954 for an example of
        # the issue this will cause.
        if self.power_state != POWER_STATE.OFF:
            try:
                # Node.stop() has synchronous and asynchronous parts, so catch
                # exceptions arising synchronously, and chain callbacks to the
                # Deferred it returns for the asynchronous (post-commit) bits.
                stopping = self._stop(user)
                # If there's an error, reset the node's status.
                # Check for None (_stop returns None for manual power type).
                if stopping is not None:
                    stopping.addErrback(
                        callOutToDatabase,
                        Node._set_status,
                        self.system_id,
                        status=self.status,
                    )
            except Exception as ex:
                maaslog.error(
                    "%s: Unable to shut node down: %s", self.hostname, str(ex)
                )
                raise

        if self.power_state == POWER_STATE.OFF:
            # The node is already powered off; we can deallocate all attached
            # resources and mark the node READY without delay.
            finalize_release = True
        elif self.get_effective_power_info().can_be_queried:
            # Controlled power type (one for which we can query the power
            # state): update_power_state() will take care of making the node
            # READY, remove the owner, and release the assigned auto IP
            # addresses when the power is finally off.
            post_commit().addCallback(
                callOutToDatabase,
                Node._set_status_expires,
                self.system_id,
                NODE_STATUS.RELEASING,
            )
            finalize_release = False
        else:
            # The node's power cannot be reliably controlled. Frankly, this
            # node is not suitable for use with MAAS. Deallocate all attached
            # resources and mark the node READY without delay because there's
            # not much else we can do.
            finalize_release = True

        self.update_status(NODE_STATUS.RELEASING)
        self.agent_name = ""
        self.set_netboot()
        self.osystem = ""
        self.distro_series = ""
        self.license_key = ""
        self.hwe_kernel = None
        self.current_installation_script_set = None
        self.install_rackd = False
        self.install_kvm = False
        self.register_vmhost = False
        self.enable_hw_sync = False
        self.sync_interval = None
        self.last_sync = None
        self.save()

        # Create a status message for RELEASING.
        Event.objects.create_node_event(self, EVENT_TYPES.RELEASING)

        Node._clear_deployment_resources(self.id)

        # Clear the nodes acquired filesystems.
        self._clear_acquired_filesystems()

        # If this node has non-installable children, remove them.
        self.children.filter(node_type=NODE_TYPE.DEVICE).delete()

        # Release volatile metadata
        from maasserver.secrets import SecretManager

        SecretManager().delete_secret("deploy-metadata", obj=self.as_node())

        # Power was off or cannot be powered off so release to ready now.
        if finalize_release:
            self._finalize_release()

    @transactional
    def _finalize_release(self):
        """Release all remaining resources, mark the machine `READY` if not
        dynamic, otherwise delete the machine.

        Releasing a node can be straightforward or it can be a multi-step
        operation, which can include a reboot in order to erase disks, then a
        final power-down. This method should be the absolute last method
        called.
        """
        # Avoid circular imports.
        from maasserver.models.event import Event

        if self.dynamic:
            self.delete()
        else:
            self.release_interface_config()
            has_commissioning_data = (
                self.current_commissioning_script_set
                and self.current_commissioning_script_set.status
                == SCRIPT_STATUS.PASSED
            )
            self.update_status(
                NODE_STATUS.READY
                if has_commissioning_data
                else NODE_STATUS.NEW
            )
            self.owner = None
            self.save()

            # Create a status message for RELEASED.
            Event.objects.create_node_event(self, EVENT_TYPES.RELEASED)
            # Remove all set owner data.
            OwnerData.objects.filter(node=self).delete()

    def maybe_delete_pods(self, dry_run: bool):
        """Check if any pods are associated with this Node.

        All pods will be deleted if dry_run=False is passed in.

        :param dry_run: If True, raises NodeActionError rather than deleting
            pods.
        """
        hosted_pods = list(
            self.get_hosted_pods().values_list("name", flat=True)
        )
        if len(hosted_pods) > 0:
            if dry_run:
                raise ValidationError(
                    "The following VM hosts must be removed first:"
                    f" {', '.join(hosted_pods)}"
                )
            for pod in self.get_hosted_pods():
                if isInIOThread():
                    pod.async_delete()
                else:
                    reactor.callFromThread(pod.async_delete)

    def set_netboot(self, on=True):
        """Set netboot on or off."""
        log.info(
            "{hostname}: Turning {status} netboot for node",
            hostname=self.hostname,
            status="on" if on else "off",
        )
        self.netboot = on
        self.save()

    def split_arch(self) -> tuple[str, str]:
        """Return architecture and subarchitecture, as a tuple."""
        if not self.architecture:
            return ("", "")
        return tuple(self.architecture.split("/", 1))

    def mark_failed(
        self,
        user=None,
        comment=None,
        commit=True,
        script_result_status=SCRIPT_STATUS.FAILED,
    ):
        """Mark this node as failed.

        The actual 'failed' state depends on the current status of the
        node.
        """
        if user is None:
            # This is a system-driven event. Log level is ERROR.
            event_type = EVENT_TYPES.REQUEST_NODE_MARK_FAILED_SYSTEM
        else:
            # This is a user-driven event. Log level is INFO.
            event_type = EVENT_TYPES.REQUEST_NODE_MARK_FAILED
        self._register_request_event(
            user, event_type, action="mark_failed", comment=comment
        )

        from maasserver.models import ScriptResult

        qs = ScriptResult.objects.filter(
            script_set__in=[
                self.current_commissioning_script_set,
                self.current_testing_script_set,
                self.current_installation_script_set,
            ],
            status__in=SCRIPT_STATUS_RUNNING_OR_PENDING,
        )
        qs.update(status=script_result_status, updated=now())

        new_status = get_failed_status(self.status)
        if new_status is not None:
            self.update_status(new_status)
            self.error_description = comment if comment else ""
            if commit:
                self.save()
            log_snippet = f": {comment}" if comment else ""
            maaslog.error(f"{self.hostname}: Marking node failed{log_snippet}")
            if new_status == NODE_STATUS.FAILED_DEPLOYMENT:
                maaslog.debug(f"Node '{self.hostname}' failed deployment")
        elif self.status == NODE_STATUS.NEW:
            # Silently ignore, failing a new node makes no sense.
            pass
        elif is_failed_status(self.status):
            # Silently ignore a request to fail an already failed node.
            pass
        else:
            raise NodeStateViolation(
                "The status of the node is %s; this status cannot "
                "be transitioned to a corresponding failed status."
                % self.status
            )

    def mark_broken(self, user, comment=None):
        """Mark this node as 'BROKEN'.

        If the node is allocated, release it first.
        """
        event = EVENT_TYPES.REQUEST_NODE_MARK_BROKEN_SYSTEM
        if user:
            event = EVENT_TYPES.REQUEST_NODE_MARK_BROKEN
        self._register_request_event(
            user,
            event,
            action="mark broken",
            comment=comment,
        )

        if self.status in RELEASABLE_STATUSES:
            self._release(user)
        # release() normally sets the status to RELEASING and leaves the
        # owner in place, override that here as we're broken.
        self.update_status(NODE_STATUS.BROKEN)
        self.error_description = comment if comment else ""
        self.save()

    def mark_fixed(self, user, comment=None):
        """Mark a broken node as fixed and change its state to 'READY'."""
        event = EVENT_TYPES.REQUEST_NODE_MARK_FIXED_SYSTEM
        if user:
            event = EVENT_TYPES.REQUEST_NODE_MARK_FIXED
        self._register_request_event(
            user,
            event,
            action="mark fixed",
            comment=comment,
        )

        if self.status != NODE_STATUS.BROKEN:
            raise NodeStateViolation(
                "Can't mark a non-broken node as 'Ready'."
            )
        maaslog.info("%s: Marking node fixed", self.hostname)
        self.update_status(
            NODE_STATUS.DEPLOYED
            if self.previous_status == NODE_STATUS.DEPLOYED
            else NODE_STATUS.READY
        )
        self.error_description = ""
        self.osystem = ""
        self.distro_series = ""
        self.hwe_kernel = None
        self.current_installation_script_set = None
        self.save()

    def get_latest_failed_testing_script_results(self) -> List[int]:
        from maasserver.models import ScriptResult

        script_results = (
            ScriptResult.objects.filter(
                script_set__node__system_id=self.system_id,
                script_set__result_type=RESULT_TYPE.TESTING,
            )
            .values(
                "id",
                "status",
                "script_set__node_id",
                "script_name",
                "physical_blockdevice_id",
            )
            .order_by(
                "script_set__node_id",
                "script_name",
                "physical_blockdevice_id",
                "-id",
            )
            .distinct(
                "script_set__node_id", "script_name", "physical_blockdevice_id"
            )
        )
        node_script_results = [
            s["id"]
            for s in script_results
            if s["status"] in SCRIPT_STATUS_FAILED
        ]
        return node_script_results

    def override_failed_testing(self, user, comment=None):
        """Reset a node with failed tests into a working state."""
        self._register_request_event(
            user,
            EVENT_TYPES.REQUEST_NODE_OVERRIDE_FAILED_TESTING,
            action="ignore failed tests",
            comment=comment,
        )
        if self.status != NODE_STATUS.FAILED_TESTING:
            raise NodeStateViolation(
                "Unable to override node status. Node is not in "
                "'Failed testing' status."
            )
        if self.osystem == "":
            self.update_status(NODE_STATUS.READY)
            maaslog.info(
                "%s: Machine status 'Failed testing' overridden by user %s. "
                "Status transition from FAILED_TESTING to READY."
                % (self.hostname, user)
            )
        else:
            self.update_status(NODE_STATUS.DEPLOYED)
            maaslog.info(
                "%s: Machine status 'Failed testing' overridden by user %s. "
                "Status transition from FAILED_TESTING to DEPLOYED."
                % (self.hostname, user)
            )
        self.error_description = ""
        self.save()

    def update_power_state(self, power_state, when=None):
        """Update a node's power state"""
        # Avoid circular imports.
        from maasserver.models.event import Event

        self.power_state = power_state
        self.power_state_updated = now()
        # The code for transitioning to a different status doesn't really belong
        # to this method. It should be replaced with temporal workflow, where
        # the workflow is responsible for setting the correct status.
        mark_ready = (
            self.status == NODE_STATUS.RELEASING
            and power_state == POWER_STATE.OFF
        )
        if mark_ready:
            # Ensure the node is released when it powers down.
            self.status_expires = None
            self._finalize_release()
        if self.status == NODE_STATUS.EXITING_RESCUE_MODE:
            if when is None:
                when = now()
            # This code can be called at any time after the start of exiting
            # rescue mode, including before the machine has been turned off
            # or during the power cycle. To avoid any race conditions where
            # the machine would be marked as failing to exit rescue mode,
            # we make sure that some time as passed since the start of exiting
            # rescue mode before we mark the operation as failed.
            stop_rescue_event = (
                Event.objects.filter(
                    node=self,
                    type__name=EVENT_TYPES.REQUEST_NODE_STOP_RESCUE_MODE,
                )
                .order_by("-created")
                .first()
            )
            reached_stop_rescue_timeout = (
                stop_rescue_event.created
                + timedelta(seconds=EXIT_RESCUE_MODE_TIMEOUT)
                < when
            )

            if self.previous_status == NODE_STATUS.DEPLOYED:
                if power_state == POWER_STATE.ON:
                    # Create a status message for EXITED_RESCUE_MODE.
                    Event.objects.create_node_event(
                        self, EVENT_TYPES.EXITED_RESCUE_MODE
                    )
                    self.update_status(self.previous_status)
                elif reached_stop_rescue_timeout:
                    # Create a status message for FAILED_EXITING_RESCUE_MODE.
                    Event.objects.create_node_event(
                        self, EVENT_TYPES.FAILED_EXITING_RESCUE_MODE
                    )
                    self.update_status(NODE_STATUS.FAILED_EXITING_RESCUE_MODE)
            else:
                if power_state == POWER_STATE.OFF:
                    self.update_status(self.previous_status)
                    self.owner = None
                    # Create a status message for EXITED_RESCUE_MODE.
                    Event.objects.create_node_event(
                        self, EVENT_TYPES.EXITED_RESCUE_MODE
                    )
                elif reached_stop_rescue_timeout:
                    # Create a status message for FAILED_EXITING_RESCUE_MODE.
                    Event.objects.create_node_event(
                        self, EVENT_TYPES.FAILED_EXITING_RESCUE_MODE
                    )
                    self.update_status(NODE_STATUS.FAILED_EXITING_RESCUE_MODE)
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
                "has no writable disks.",
                self.hostname,
            )
        except StorageLayoutError as e:
            maaslog.error(
                "%s: Failed to configure storage layout: %s", self.hostname, e
            )

    def set_storage_layout(self, layout, params={}, allow_fallback=True):
        """Set storage layout for this node."""
        storage_layout = get_storage_layout_for_node(
            layout, self, params=params
        )
        if storage_layout is not None:
            used_layout = storage_layout.configure(
                allow_fallback=allow_fallback
            )
            self.last_applied_storage_layout = used_layout
            self.save(update_fields=["last_applied_storage_layout"])
            maaslog.info(
                f"{self.hostname}: Storage layout was set to {used_layout}."
            )
        else:
            raise StorageLayoutError(f"Unknown storage layout: {layout}")

    def set_storage_configuration_from_node(self, source_node):
        """Set the storage configuration for this node from the source node."""
        mapping = self._get_storage_mapping_between_nodes(source_node)
        self._clear_full_storage_configuration()

        # Get all the filesystem groups and cachesets for the source node. This
        # is used to do the cloning in layers, only cloning the filesystem
        # groups and cache sets once filesystems that make up have been cloned.
        fs_groups = list(
            FilesystemGroup.objects.filter_by_node(source_node)
            .order_by("id")
            .prefetch_related("filesystems")
        )
        fs_groups_map = {
            fs_group.id: fs_group
            for fs_group in FilesystemGroup.objects.filter_by_node(
                source_node
            ).order_by("id")
        }
        cacheset_groups = list(
            CacheSet.objects.get_cache_sets_for_node(source_node)
            .order_by("id")
            .prefetch_related("filesystems")
        )
        cacheset_groups_map = {
            cacheset_group.id: cacheset_group
            for cacheset_group in CacheSet.objects.get_cache_sets_for_node(
                source_node
            ).order_by("id")
        }

        # Clone the model at the physical level.
        filesystem_map = self._copy_between_block_device_mappings(mapping)

        # Continue through each layer until no more filesystem groups exist.
        fs_groups, fs_groups_layer = self._get_group_layers_for_copy(
            fs_groups, filesystem_map
        )
        (
            cacheset_groups,
            cacheset_groups_layer,
        ) = self._get_group_layers_for_copy(cacheset_groups, filesystem_map)

        cache_sets_mapping = {}
        while (
            fs_groups
            or cacheset_groups
            or fs_groups_layer
            or cacheset_groups_layer
        ):
            if not fs_groups_layer and not cacheset_groups_layer:
                raise ValueError(
                    "Copying the next layer of filesystems groups or cache "
                    "sets has failed."
                )

            # Always do `CacheSet`'s before `FilesystemGroup`, because a
            # filesystem group might depend on the cache set.
            for (
                source_cacheset,
                dest_filesystems,
            ) in cacheset_groups_layer.items():
                cacheset = cacheset_groups_map.pop(source_cacheset.id)
                self._clone_cache_set(cacheset, dest_filesystems)
                cache_sets_mapping[source_cacheset.id] = cacheset
            filesystem_map = {}
            for source_fs_group, dest_filesystems in fs_groups_layer.items():
                fs_group = fs_groups_map.pop(source_fs_group.id)
                group_fsmap = self._clone_filesystem_group(
                    fs_group, dest_filesystems, cache_sets_mapping
                )
                filesystem_map.update(group_fsmap)
            # load the next layer
            fs_groups, fs_groups_layer = self._get_group_layers_for_copy(
                fs_groups, filesystem_map
            )
            (
                cacheset_groups,
                cacheset_groups_layer,
            ) = self._get_group_layers_for_copy(
                cacheset_groups, filesystem_map
            )

        # Clone the special filesystems.
        for filesystem in source_node.current_config.special_filesystems.all():
            _clone_object(
                filesystem, uuid=None, node_config=self.current_config
            )

    def _get_storage_mapping_between_nodes(self, source_node):
        """Return the mapping between which disks from this node map to disks
        on the source node.

        Raises a `ValidationError` when storage is not identical.
        """
        # Both node's must be the same architecture and boot method to have
        # the same storage configuration.
        if self.architecture != source_node.architecture:
            raise ValidationError(
                "node architectures do not match (%s != %s)"
                % (self.architecture, source_node.architecture)
            )
        if self.bios_boot_method != source_node.bios_boot_method:
            raise ValidationError(
                "node boot methods do not match (%s != %s)"
                % (self.bios_boot_method, source_node.bios_boot_method)
            )

        self_boot_disk = self.get_boot_disk()
        if self_boot_disk is None:
            raise ValidationError(
                "destination node has no physical block devices"
            )
        source_boot_disk = source_node.get_boot_disk()
        if source_boot_disk is None:
            raise ValidationError("source node has no physical block devices")
        if self_boot_disk.size < source_boot_disk.size:
            raise ValidationError(
                "destination boot disk(%s) is smaller than source "
                "boot disk(%s)" % (self_boot_disk.name, source_boot_disk.name)
            )

        self_disks = list(
            self.physicalblockdevice_set.exclude(
                id=self_boot_disk.id
            ).order_by("id")
        )
        source_disks = list(
            source_node.physicalblockdevice_set.exclude(
                id=source_boot_disk.id
            ).order_by("id")
        )
        if len(self_disks) < len(source_disks):
            raise ValidationError(
                "source node does not have enough physical block devices "
                f"({len(self_disks) + 1} < {len(source_disks) + 1})"
            )

        mapping = {self_boot_disk: source_boot_disk}

        # First pass; match on identical size and tags.
        for self_disk in self_disks[:]:  # Iterate on copy
            for source_disk in source_disks[:]:  # Iterate on copy
                if self_disk.size == source_disk.size and set(
                    self_disk.tags
                ) == set(source_disk.tags):
                    mapping[self_disk] = source_disk
                    self_disks.remove(self_disk)
                    source_disks.remove(source_disk)
                    break

        if not self_disks:
            return mapping

        # Second pass; re-order by size to match by those that are closes with
        # identical tags.
        self_disks = sorted(self_disks, key=attrgetter("size"))
        source_disks = sorted(source_disks, key=attrgetter("size"))
        for self_disk in self_disks[:]:  # Iterate on copy
            for source_disk in source_disks[:]:  # Iterate on copy
                if self_disk.size >= source_disk.size and set(
                    self_disk.tags
                ) == set(source_disk.tags):
                    mapping[self_disk] = source_disk
                    self_disks.remove(self_disk)
                    source_disks.remove(source_disk)
                    break

        if not self_disks:
            return mapping

        # Third pass; still by size but tags don't need to match.
        self_disks = sorted(self_disks, key=attrgetter("size"))
        source_disks = sorted(source_disks, key=attrgetter("size"))
        for self_disk in self_disks[:]:  # Iterate on copy
            for source_disk in source_disks[:]:  # Iterate on copy
                if self_disk.size >= source_disk.size:
                    mapping[self_disk] = source_disk
                    self_disks.remove(self_disk)
                    source_disks.remove(source_disk)
                    break

        if self_disks:
            raise ValidationError(
                "%d destination node physical block devices do not match the "
                "source nodes physical block devices" % len(self_disks)
            )

        return mapping

    def _copy_between_block_device_mappings(self, mapping):
        """Copy the source onto the destination disks in the mapping.

        Block devices in this case can either be physical or virtual.
        """
        filesystem_map = {}
        for self_disk, source_disk in mapping.items():
            ptable = source_disk.get_partitiontable()
            if ptable is not None:
                partitions = ptable.partitions.order_by("id")
                _clone_object(ptable, block_device=self_disk)
                for partition in partitions.all():
                    filesystems = partition.filesystem_set.filter(
                        acquired=False
                    ).order_by("id")
                    _clone_object(partition, uuid=None, partition_table=ptable)
                    for filesystem in filesystems.all():
                        source_filesystem_id = filesystem.id
                        _clone_object(
                            filesystem,
                            node_config=ptable.block_device.node_config,
                            uuid=None,
                            block_device=None,
                            partition=partition,
                        )
                        filesystem_map[source_filesystem_id] = filesystem
            filesystems = source_disk.filesystem_set.filter(
                acquired=False
            ).order_by("id")
            for filesystem in filesystems:
                source_filesystem_id = filesystem.id
                _clone_object(
                    filesystem,
                    node_config=self_disk.node_config,
                    uuid=None,
                    block_device=self_disk,
                    partition=None,
                )
                filesystem_map[source_filesystem_id] = filesystem
        return filesystem_map

    def _get_group_layers_for_copy(self, filesystem_groups, filesystem_map):
        """Pop the filesystem groups or cache set from the `filesystem_groups`
        when all filesystems that make it up exist in `filesystem_map`."""
        layer = {}
        for group in filesystem_groups[:]:  # Iterate on copy
            contains_all = True
            dest_filesystems = []
            for filesystem in group.filesystems.all():
                dest_filesystem = filesystem_map.get(filesystem.id, None)
                if dest_filesystem:
                    dest_filesystems.append(dest_filesystem)
                else:
                    contains_all = False
                    break
            if contains_all:
                layer[group] = dest_filesystems
                filesystem_groups.remove(group)
        return filesystem_groups, layer

    def _clone_cache_set(self, cache_set, dest_filesystems):
        """Clone the `cache_set` linking to `dest_filesystems`."""
        _clone_object(cache_set)
        for dest_filesystem in dest_filesystems:
            cache_set.filesystems.add(dest_filesystem)

    def _clone_filesystem_group(
        self, fs_group, dest_filesystems, cache_sets_mapping
    ):
        """Clone the `source_group` linking to the `dest_filesystems`."""
        # Get two copies of the devices since we need to pass the original ones
        # for the filesystem_map.
        source_vds = fs_group.virtual_devices.order_by("id")
        dest_vds = fs_group.virtual_devices.order_by("id")

        cache_set = None
        if fs_group.cache_set_id is not None:
            cache_set = cache_sets_mapping[fs_group.cache_set_id]
        _clone_object(fs_group, uuid=None, cache_set=cache_set)
        for dest_filesystem in dest_filesystems:
            fs_group.filesystems.add(dest_filesystem)

        # Copy the virtual block devices for the created filesystem group.
        filesystem_map = {}
        for source_vd, dest_vd in zip(source_vds, dest_vds):
            _clone_object(
                dest_vd,
                uuid=None,
                node_config=self.current_config,
                filesystem_group=fs_group,
            )
            filesystem_map.update(
                self._copy_between_block_device_mappings({dest_vd: source_vd})
            )

        return filesystem_map

    def _clear_full_storage_configuration(self):
        """Clear's the full storage configuration for this node.

        This will remove all related models to `PhysicalBlockDevice`'s and
        on this node and all `VirtualBlockDevice`'s.

        This is used before commissioning to clear the entire storage model
        except for the `PhysicalBlockDevice`'s.
        Commissioning will update the `PhysicalBlockDevice` information
        on this node.
        """
        block_device_ids = list(
            self.physicalblockdevice_set.values_list("id", flat=True)
        )
        PartitionTable.objects.filter(
            block_device__id__in=block_device_ids
        ).delete()
        Filesystem.objects.filter(
            block_device__id__in=block_device_ids
        ).delete()
        self.current_config.special_filesystems.all().delete()
        virtual_devices = list(reversed(self.virtualblockdevice_set.all()))
        for _ in range(10):  # 10 times gives enough tries to remove.
            for virtual_bd in virtual_devices[:]:  # Iterate on copy.
                try:
                    virtual_bd.filesystem_group.delete(force=True)
                    virtual_devices.remove(virtual_bd)
                except FilesystemGroup.DoesNotExist:
                    # When a filesystem group has multiple virtual block
                    # devices it is possible that accessing `filesystem_group`
                    # will result in it already being deleted.
                    virtual_devices.remove(virtual_bd)
                except ValidationError:
                    # Cannot be deleted because another device depends on it.
                    # Next loop through will delete the device.
                    pass
            if not virtual_devices:
                # Done, all have been removed.
                break
        if virtual_devices:
            raise StorageClearProblem(
                "Failed to remove %d virtual devices: %s"
                % (
                    len(virtual_devices),
                    ", ".join(
                        [
                            virtual_bd.get_name()
                            for virtual_bd in virtual_devices
                        ]
                    ),
                )
            )

    def _create_acquired_filesystems(self):
        """Copy all filesystems that have a user mountable filesystem to be
        in acquired mode.

        Any modification to the filesystems from this point forward should use
        the acquired filesystems instead of the original. The acquired
        filesystems will be removed on release of the node.
        """
        self._clear_acquired_filesystems()
        filesystems = Filesystem.objects.filter_by_node(self).filter(
            fstype__in=FILESYSTEM_FORMAT_TYPE_CHOICES_DICT, acquired=False
        )
        for filesystem in filesystems:
            _clone_object(filesystem, acquired=True)

    @classmethod
    def _clear_deployment_resources(cls, node_id):
        # remove hugepages configuration since they only make sense when the node is deployed
        NUMANodeHugepages.objects.filter(numanode__node_id=node_id).delete()

    def _clear_acquired_filesystems(self):
        """Clear the filesystems that are created when the node is acquired."""
        filesystems = Filesystem.objects.filter_by_node(self).filter(
            acquired=True
        )
        filesystems.delete()

    def _create_acquired_bridges(
        self, bridge_type=None, bridge_stp=None, bridge_fd=None
    ):
        """Create an acquired bridge on all configured interfaces."""
        interfaces = self.current_config.interface_set.exclude(
            type=INTERFACE_TYPE.BRIDGE
        )
        interfaces = interfaces.prefetch_related("ip_addresses")
        for interface in interfaces:
            if interface.is_configured():
                interface.create_acquired_bridge(
                    bridge_type=bridge_type,
                    bridge_stp=bridge_stp,
                    bridge_fd=bridge_fd,
                )

    def claim_auto_ips(self, exclude_addresses=None, temp_expires_after=None):
        """Assign IP addresses to all interface links set to AUTO."""
        exclude_addresses = (
            exclude_addresses.copy() if exclude_addresses else set()
        )
        allocated_ips = set()
        # Query for the interfaces again here; if we use the cached
        # interface_set, we could skip a newly-created bridge if it was created
        # at deployment time.
        for interface in Interface.objects.filter(
            node_config=self.current_config
        ):
            maaslog.debug(f"Claiming IP for {self.system_id}:{interface.name}")
            claimed_ips = interface.claim_auto_ips(
                temp_expires_after=temp_expires_after,
                exclude_addresses=exclude_addresses,
            )
            for ip in claimed_ips:
                maaslog.debug(
                    f"Claimed IP for {self.system_id}:{interface.name}: "
                    f"{ip.ip}"
                )
                exclude_addresses.add(str(ip.ip))
                allocated_ips.add(ip)
        return allocated_ips

    @inlineCallbacks
    def _claim_auto_ips(self):
        """Perform claim AUTO IP addresses from the post_commit `defer`."""

        @transactional
        def clean_expired():
            """Clean the expired AUTO IP addresses."""
            StaticIPAddress.objects.filter(
                temp_expires_on__lte=datetime.utcnow()
            ).update(ip=None, temp_expires_on=None)

        # track which IPs have been already attempted for allocation
        attempted_ips = set()

        @transactional
        def get_racks_to_check(allocated_ips):
            """Calculate the rack controllers to perform the IP check on."""
            if not allocated_ips:
                return None, None

            # Map the allocated IP addresses to the subnets they belong.
            ip_ids = [ip.id for ip in allocated_ips]
            ips_to_subnet = StaticIPAddress.objects.filter(id__in=ip_ids)
            subnets_to_ips = defaultdict(set)
            for ip in ips_to_subnet:
                subnets_to_ips[ip.subnet_id].add(ip)

            # Map the rack controllers that have an IP address on each subnet
            # and have an actual connection to this region controller.
            racks_to_clients = {
                client.ident: client for client in getAllClients()
            }
            subnets_to_clients = {}
            for subnet_id in subnets_to_ips.keys():
                usable_racks = set(
                    RackController.objects.filter(
                        current_config__interface__ip_addresses__subnet=subnet_id,
                        current_config__interface__ip_addresses__ip__isnull=False,
                    )
                )
                subnets_to_clients[subnet_id] = [
                    racks_to_clients[rack.system_id]
                    for rack in usable_racks
                    if rack.system_id in racks_to_clients
                ]

            return subnets_to_ips, subnets_to_clients

        def perform_ip_checks(subnets_to_ips, subnets_to_clients):
            # Early-out if no IP addresses where allocated.
            if not subnets_to_ips:
                return None
            defers = []
            for subnet_id, ips in subnets_to_ips.items():
                clients = subnets_to_clients.get(subnet_id)
                if clients:
                    maaslog.debug(f"Creating deferred to check IP {ips}")
                    client = random.choice(clients)
                    d = client(
                        CheckIPs,
                        ip_addresses=[{"ip_address": ip.ip} for ip in ips],
                    )

                    def append_info(res, *, ident=None, ips=None):
                        return res, ident, ips

                    d.addBoth(
                        partial(append_info, ident=client.ident, ips=ips)
                    )
                else:
                    d = succeed((None, None, ips))
                defers.append(d)
            return DeferredList(defers)

        @transactional
        def process_results(results, do_cleanups):
            maaslog.debug(
                f"Processing IP allocation results for {self.system_id}"
            )
            check_failed, ips_in_use = False, False
            for _, (check_result, rack_id, ips) in results:
                ip_ids = [ip.id for ip in ips]
                ip_to_obj = {ip.ip: ip for ip in ips}
                if check_result is None:
                    # No rack controllers exists that can perform IP
                    # address checking. Mark all the IP addresses as
                    # available.
                    StaticIPAddress.objects.filter(id__in=ip_ids).update(
                        temp_expires_on=None
                    )
                elif isinstance(check_result, Failure):
                    check_failed = True
                    # Failed to perform IP address checking on the rack
                    # controller.
                    static_ips = StaticIPAddress.objects.filter(id__in=ip_ids)
                    if do_cleanups:
                        # Clear the temp_expires_on marking the IP address as
                        # assigned. Thsi was the last attempt to perform the
                        # allocation.
                        static_ips.update(temp_expires_on=None)
                    else:
                        # Clear the assigned IP address so new IP can be
                        # assigned in the next pass.
                        static_ips.update(ip=None, temp_expires_on=None)
                else:
                    # IP address checking was successful, use the results
                    # to either mark the assigned IP address no longer
                    # temporary or to mark the IP address as discovered.
                    for ip_result in check_result["ip_addresses"]:
                        ip_obj = ip_to_obj[ip_result["ip_address"]]
                        if ip_result["used"]:
                            attempted_ips.add(ip_obj.ip)
                            # lp:2024242: Do not add the neighbour: the network
                            # discovery service will detect the traffic and
                            # create the record accordingly
                            ip_obj.ip = None
                            ip_obj.temp_expires_on = None
                            ip_obj.save()
                            ips_in_use = True
                        else:
                            # IP was free and offically assigned.
                            ip_obj.temp_expires_on = None
                            ip_obj.save()

            return check_failed, ips_in_use

        retry, max_retries = 0, 2
        while retry <= max_retries:
            yield deferToDatabase(clean_expired)
            allocated_ips = yield deferToDatabase(
                transactional(self.claim_auto_ips),
                exclude_addresses=attempted_ips,
                temp_expires_after=timedelta(minutes=5),
            )
            if not allocated_ips:
                # no IPs to test (e.g. all IPs are statically assigned)
                return
            # skip IPs that have been tested already
            allocated_ips = {
                ip for ip in allocated_ips if ip.ip not in attempted_ips
            }
            if not allocated_ips:
                raise StaticIPAddressExhaustion(
                    "Failed to allocate the required AUTO IP addresses"
                )
            subnets_to_ips, subnets_to_clients = yield deferToDatabase(
                get_racks_to_check, allocated_ips
            )
            results = yield perform_ip_checks(
                subnets_to_ips, subnets_to_clients
            )
            if not results:
                return

            last_run = retry == max_retries
            check_failed, ips_in_use = yield deferToDatabase(
                process_results, results, last_run
            )
            if ips_in_use:
                retry = 0
            elif check_failed:
                retry += 1
            else:
                return

        # over the retry count, check failed
        raise IPAddressCheckFailed(
            f"IP address checks failed after {max_retries} retries."
        )

    @transactional
    def release_interface_config(self):
        """Release IP addresses on all interface links set to AUTO and
        remove all acquired interfaces."""
        for interface in self.current_config.interface_set.all():
            interface.release_auto_ips()
            if not interface.acquired:
                continue

            if interface.type == INTERFACE_TYPE.BRIDGE:
                # Move all IP addresses assigned to an acquired bridge to the
                # parent of the bridge.
                parent = interface.parents.first()
                if parent:
                    for sip in interface.ip_addresses.all():
                        sip.interface_set.remove(interface)
                        sip.interface_set.add(parent)
                    # Set flag to prevent a race condition that would otherwise
                    # cause the IP addresses moved to the parent interface to
                    # be deleted on interface removal.
                    setattr(interface, "_skip_ip_address_removal", True)
            interface.delete()

    def _clear_networking_configuration(self):
        """Clear the networking configuration for this node.

        The networking configuration is cleared when a node is going to be
        commissioned. This allows the new commissioning data to create a new
        networking configuration.
        """
        self.gateway_link_ipv4 = None
        self.gateway_link_ipv6 = None
        interfaces = self.current_config.interface_set.all()
        for interface in interfaces:
            interface.clear_all_links(clearing_config=True)

    def _hw_sync_preserve_network_interfaces(self, data):
        for iface in self.current_config.interface_set.filter(
            type=INTERFACE_TYPE.PHYSICAL
        ):
            if iface.name in data["networks"]:
                continue
            data["networks"][iface.name] = {
                "type": "broadcast",
                "hwaddr": iface.mac_address,
                "bridge": None,
                "bond": None,
                "vlan": None,
                "addresses": [
                    {
                        "address": link["ip_address"].ip,
                        "netmask": link["subnet"].netmask,
                        "family": (
                            "inet"
                            if link["subnet"].get_ip_version() == 4
                            else "inet6"
                        ),
                        "scope": "global",
                    }
                    for link in iface.get_links()
                ],
                "state": "up" if iface.link_connected else "down",
            }
        return data

    def restore_network_interfaces(self):
        """Restore the network interface to their commissioned state."""
        from metadataserver.builtin_scripts.hooks import (
            update_node_network_information,
        )

        data = self.get_commissioning_resources()
        assert data is not None, "No resources found from commissioning output"
        if "networks" not in data:
            raise NetworkingResetProblem(
                "Missing network information from commissioning script, "
                "please commission the machine again"
            )
        if self.enable_hw_sync:
            data = self._hw_sync_preserve_network_interfaces(data)
        update_node_network_information(
            self, data, NUMANode.objects.filter(node=self)
        )
        self.save()

    def get_commissioning_resources(self):
        script = self.current_commissioning_script_set.find_script_result(
            script_name=COMMISSIONING_OUTPUT_NAME
        )
        if not script or not script.stdout:
            return None
        return json.loads(script.stdout)

    def set_initial_networking_configuration(self):
        """Set the networking configuration to the default for this node.

        The networking configuration is set to an initial configuration where
        the boot interface is set to default_boot_interface_link_type and all
        other interfaces are set to LINK_UP.

        This is done after commissioning has finished.
        """
        # Do nothing if networking should be skipped.
        if self.skip_networking:
            return

        boot_interface = self.get_boot_interface()
        if boot_interface is None:
            # No interfaces on the node. Nothing to do.
            return

        assert self.status not in [
            NODE_STATUS.DEPLOYING,
            NODE_STATUS.DEPLOYED,
        ], "Node cannot be in a deploying state when configuring network"

        # Clear the configuration, so that we can call this method
        # multiple times.
        self._clear_networking_configuration()
        # Set default_boot_interface_link_type mode on the boot interface.
        default_set = False
        discovered_addresses = boot_interface.ip_addresses.filter(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, subnet__isnull=False
        )
        subnets_to_link = {
            ip_address.subnet for ip_address in discovered_addresses
        }
        for subnet in subnets_to_link:
            boot_interface.link_subnet(
                Config.objects.get_config("default_boot_interface_link_type"),
                subnet,
            )
            default_set = True
        if not default_set:
            # Failed to set default_boot_interface_link_type mode on the boot
            # interface. Lets force an AUTO on a subnet that is on the same
            # VLAN as the interface. If that fails we just set the interface
            # to DHCP with no subnet defined.
            boot_interface.force_auto_or_dhcp_link()

        # Set LINK_UP mode on all the other enabled interfaces.
        for interface in self.current_config.interface_set.all():
            if interface == boot_interface:
                # Skip the boot interface as it has already been configured.
                continue
            if interface.enabled:
                interface.ensure_link_up()
        self.save()

    def set_networking_configuration_from_node(self, source_node):
        """Set the networking configuration for this node from the source
        node."""
        mapping = self._get_interface_mapping_between_nodes(source_node)
        self._clear_networking_configuration()

        # Get all none physical interface for the source node. This
        # is used to do the cloning in layers, only cloning the interfaces
        # that have already been cloned to make up the next layer of
        # interfaces.
        source_interfaces = list(
            source_node.current_config.interface_set.exclude(
                type=INTERFACE_TYPE.PHYSICAL
            )
        )
        # Get another copy of interface objects since they will be modified
        # during cloning.
        interfaces_map = {
            interface.id: interface
            for interface in source_node.current_config.interface_set.exclude(
                type=INTERFACE_TYPE.PHYSICAL
            )
        }

        # Clone the model at the physical level.
        exclude_addresses = self._copy_between_interface_mappings(mapping)
        mapping = {
            source_interface.id: self_interface
            for self_interface, source_interface in mapping.items()
        }

        # Continue through each layer until no more interfaces exist.
        (
            source_interfaces,
            layer_interfaces,
        ) = self._get_interface_layers_for_copy(source_interfaces, mapping)
        while source_interfaces or layer_interfaces:
            if not layer_interfaces:
                raise ValueError(
                    "Copying the next layer of interfaces has failed."
                )
            for source_interface, dest_parents in layer_interfaces.items():
                interface = interfaces_map.pop(source_interface.id)
                self._clone_interface(interface, dest_parents)
                dest_mapping = {interface: source_interface}
                exclude_addresses += self._copy_between_interface_mappings(
                    dest_mapping, exclude_addresses=exclude_addresses
                )
                mapping.update(
                    {
                        source_interface.id: self_interface
                        for self_interface, source_interface in (
                            dest_mapping.items()
                        )
                    }
                )
            # Load the next layer.
            (
                source_interfaces,
                layer_interfaces,
            ) = self._get_interface_layers_for_copy(source_interfaces, mapping)

    def _get_interface_mapping_between_nodes(self, source_node):
        """Return the mapping between which interface from this node map to
        interfaces on the source node.

        Mapping between the nodes is done by the name of the interface. This
        node must have the same names as the names from `source_node`.

        Raises a `ValidationError` when interfaces cannot be matched.
        """
        self_interfaces = {
            interface.name: interface
            for interface in self.current_config.interface_set.all()
            if interface.type == INTERFACE_TYPE.PHYSICAL
        }
        missing = []
        mapping = {}
        for interface in source_node.current_config.interface_set.all():
            if interface.type == INTERFACE_TYPE.PHYSICAL:
                self_interface = self_interfaces.get(interface.name, None)
                if self_interface is not None:
                    mapping[self_interface] = interface
                else:
                    missing.append(interface.name)
        if missing:
            raise ValidationError(
                "destination node physical interfaces do not match the "
                "source nodes physical interfaces: %s" % ", ".join(missing)
            )
        return mapping

    def _copy_between_interface_mappings(
        self, mapping, exclude_addresses=None
    ):
        """Copy the source onto the destination interfaces in the mapping."""
        if exclude_addresses is None:
            exclude_addresses = []
        for self_interface, source_interface in mapping.items():
            self_interface.vlan = source_interface.vlan
            self_interface.params = source_interface.params
            self_interface.enabled = source_interface.enabled
            self_interface.acquired = source_interface.acquired
            self_interface.save()

            for ip_address in source_interface.ip_addresses.all():
                if ip_address.ip and ip_address.alloc_type in [
                    IPADDRESS_TYPE.AUTO,
                    IPADDRESS_TYPE.STICKY,
                    IPADDRESS_TYPE.USER_RESERVED,
                ]:
                    new_ip = StaticIPAddress.objects.allocate_new(
                        subnet=ip_address.subnet,
                        alloc_type=ip_address.alloc_type,
                        user=ip_address.user,
                        exclude_addresses=exclude_addresses,
                    )
                    self_interface.ip_addresses.add(new_ip)
                    exclude_addresses.append(new_ip.ip)
                elif ip_address.alloc_type != IPADDRESS_TYPE.DISCOVERED:
                    _clone_object(ip_address, ip=None)
                    self_interface.ip_addresses.add(ip_address)
        return exclude_addresses

    def _get_interface_layers_for_copy(
        self, source_interfaces, interface_mapping
    ):
        """Pops the interface from the `source_interfaces` when all interfaces
        that make it up exist in `interface_mapping`."""
        layer = {}
        for interface in source_interfaces[:]:  # Iterate on copy
            contains_all = True
            dest_parents = []
            for parent_interface in interface.parents.all():
                dest_interface = interface_mapping.get(
                    parent_interface.id, None
                )
                if dest_interface:
                    dest_parents.append(dest_interface)
                else:
                    contains_all = False
                    break
            if contains_all:
                layer[interface] = dest_parents
                source_interfaces.remove(interface)
        return source_interfaces, layer

    def _clone_interface(self, interface, dest_parents):
        """clone the `interface` linking to the `dest_parents`."""
        _clone_object(
            interface,
            node_config=self.current_config,
            mac_address=dest_parents[0].mac_address,
        )
        for parent in dest_parents:
            InterfaceRelationship.objects.create(
                child=interface, parent=parent
            )

    def get_gateways_by_priority(self):
        """Return all possible default gateways for the Node, by priority.

        This is determined by looking at all interfaces on the node and
        selecting the best possible default gateway IP. The criteria below
        is used to select the best possible gateway:

          1. Managed subnets over unmanaged subnets.
          2. Bond and bridge interfaces over physical interfaces.
          3. Node's boot interface over all other interfaces except bonds and
             bridges.
          4. Physical interfaces over VLAN interfaces.
          5. Sticky IP links over user reserved IP links.
          6. User reserved IP links over auto IP links.

        :return: List of (interface ID, subnet ID, gateway IP) tuples.
        :rtype: list
        """
        cursor = connection.cursor()

        # DISTINCT ON returns the first matching row for any given
        # IP family. Using the query's ordering.
        cursor.execute(
            """
            SELECT
                interface.id, subnet.id, subnet.gateway_ip
            FROM maasserver_node AS node
            JOIN maasserver_nodeconfig AS nodeconfig ON
                nodeconfig.node_id = node.id
            JOIN maasserver_interface AS interface ON
                interface.node_config_id = nodeconfig.id
            JOIN maasserver_interface_ip_addresses AS link ON
                link.interface_id = interface.id
            JOIN maasserver_staticipaddress AS staticip ON
                staticip.id = link.staticipaddress_id
            JOIN maasserver_subnet AS subnet ON
                subnet.id = staticip.subnet_id
            JOIN maasserver_vlan AS vlan ON
                vlan.id = subnet.vlan_id
            WHERE
                node.id = %s AND
                subnet.gateway_ip IS NOT NULL AND
                host(subnet.gateway_ip) != '' AND
                staticip.alloc_type != 5 AND /* Ignore DHCP */
                staticip.alloc_type != 6 /* Ignore DISCOVERED */
            ORDER BY
                family(subnet.gateway_ip),
                vlan.dhcp_on DESC,
                CASE
                    WHEN interface.type = 'bond' THEN 1
                    WHEN interface.type = 'bridge' THEN 1
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
            """,
            (self.id,),
        )
        return [
            GatewayDefinition(found[0], found[1], found[2])
            for found in cursor.fetchall()
        ]

    def _get_best_interface_from_gateway_link(self, gateway_link):
        """Return the best interface for the `gateway_link` and this node."""
        return (
            gateway_link.interface_set.filter(
                node_config_id=self.current_config_id
            )
            .order_by("type", "id")
            .first()
            .id
        )

    def _get_gateway_tuple(self, gateway_link):
        """Return a tuple for the interface id, subnet id, and gateway IP for
        the `gateway_link`."""
        return GatewayDefinition(
            self._get_best_interface_from_gateway_link(gateway_link),
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
            information, plus a list of all available gateways.
        :rtype: DefaultGateways tuple
        """
        all_gateways = self.get_gateways_by_priority()

        # Get the set gateways on the node.
        gateway_ipv4 = None
        gateway_ipv6 = None
        if self.gateway_link_ipv4 is not None:
            subnet = self.gateway_link_ipv4.subnet
            if subnet is not None:
                if subnet.gateway_ip:
                    gateway_ipv4 = self._get_gateway_tuple(
                        self.gateway_link_ipv4
                    )
        if self.gateway_link_ipv6 is not None:
            subnet = self.gateway_link_ipv6.subnet
            if subnet is not None:
                if subnet.gateway_ip:
                    gateway_ipv6 = self._get_gateway_tuple(
                        self.gateway_link_ipv6
                    )

        # Early out if we already have both gateways.
        if gateway_ipv4 and gateway_ipv6:
            return DefaultGateways(gateway_ipv4, gateway_ipv6, all_gateways)

        # Get the best guesses for the missing IP families.
        if not gateway_ipv4:
            gateway_ipv4 = self._get_gateway_tuple_by_family(
                all_gateways, IPADDRESS_FAMILY.IPv4
            )
        if not gateway_ipv6:
            gateway_ipv6 = self._get_gateway_tuple_by_family(
                all_gateways, IPADDRESS_FAMILY.IPv6
            )
        return DefaultGateways(gateway_ipv4, gateway_ipv6, all_gateways)

    def get_default_dns_servers(
        self, ipv4=True, ipv6=True, default_region_ip=None
    ):
        """Return the default DNS servers for this node."""
        # Circular imports.
        from maasserver.dns.zonegenerator import get_dns_server_addresses

        gateways = self.get_default_gateways()

        # Try first to use DNS servers from default gateway subnets.
        if ipv4 and gateways.ipv4 is not None:
            subnet = Subnet.objects.get(id=gateways.ipv4.subnet_id)
            if subnet.dns_servers:
                if not subnet.allow_dns:
                    return subnet.dns_servers
                rack_dns = []
                for rack in {
                    self.get_boot_primary_rack_controller(),
                    self.get_boot_secondary_rack_controller(),
                }:
                    if rack is None:
                        continue
                    rack_dns += [
                        str(ip)
                        for ip in get_dns_server_addresses(
                            rack_controller=rack,
                            ipv4=True,
                            ipv6=False,
                            include_alternates=True,
                            default_region_ip=default_region_ip,
                        )
                        if not ip.is_loopback()
                    ]
                # An IPv4 subnet is hosting the default gateway and has DNS
                # servers defined. IPv4 DNS servers take first-priority.
                return list(
                    OrderedDict.fromkeys(rack_dns + subnet.dns_servers)
                )
        if ipv6 and gateways.ipv6 is not None:
            subnet = Subnet.objects.get(id=gateways.ipv6.subnet_id)
            if subnet.dns_servers:
                if not subnet.allow_dns:
                    return subnet.dns_servers
                rack_dns = []
                for rack in {
                    self.get_boot_primary_rack_controller(),
                    self.get_boot_secondary_rack_controller(),
                }:
                    if rack is None:
                        continue
                    rack_dns += [
                        str(ip)
                        for ip in get_dns_server_addresses(
                            rack_controller=rack,
                            ipv4=False,
                            ipv6=True,
                            include_alternates=True,
                            default_region_ip=default_region_ip,
                        )
                        if not ip.is_loopback()
                    ]
                # An IPv6 subnet is hosting the default gateway and has DNS
                # servers defined. IPv6 DNS servers take second-priority.
                return list(
                    OrderedDict.fromkeys(rack_dns + subnet.dns_servers)
                )

        # Get the routable addresses between the node and all rack controllers,
        # when the rack proxy should be used (default).
        routable_addrs_map = {}
        if Config.objects.get_config("use_rack_proxy"):
            # LP:1847537 - Filter out MAAS DNS servers running on subnets
            # which do not allow DNS to be provided from MAAS.
            for node, addresses in get_routable_address_map(
                RackController.objects.all(), self
            ).items():
                filtered_addresses = [
                    address
                    for address in addresses
                    if getattr(
                        Subnet.objects.get_best_subnet_for_ip(address),
                        "allow_dns",
                        True,
                    )
                ]
                if filtered_addresses:
                    routable_addrs_map[node] = filtered_addresses

        if gateways.ipv4 is None and gateways.ipv6 is None:
            # node with no gateway can only use routable addrs
            maas_dns_servers = []
            routable_addrs_map = {
                node: sorted(
                    address
                    for address in addresses
                    if (
                        (ipv4 and address.version == 4)
                        or (ipv6 and address.version == 6)
                    )
                )
                for node, addresses in routable_addrs_map.items()
            }
        else:
            # Choose an address consistent with the primary address-family
            # in use, as indicated by the presence (or not) of a gateway.
            # Note that this path is only taken if the MAAS URL is set to
            # a hostname, and the hostname resolves to both an IPv4 and an
            # IPv6 address.
            maas_dns_servers = get_dns_server_addresses(
                rack_controller=self.get_boot_rack_controller(),
                ipv4=(ipv4 and gateways.ipv4 is not None),
                ipv6=(ipv6 and gateways.ipv6 is not None),
                include_alternates=True,
                default_region_ip=default_region_ip,
            )
            routable_addrs_map = {
                node: [
                    address
                    for address in addresses
                    if (
                        (
                            ipv4
                            and gateways.ipv4 is not None
                            and address.version == 4
                        )
                        or (
                            ipv6
                            and gateways.ipv6 is not None
                            and address.version == 6
                        )
                    )
                ]
                for node, addresses in routable_addrs_map.items()
            }

        # Routable rack controllers come before the region controllers when
        # using the rack DNS proxy.
        maas_dns_servers = list(
            OrderedDict.fromkeys(str(ip) for ip in maas_dns_servers)
        )

        routable_addrs = [
            str(addr)
            for addr in reduce_routable_address_map(routable_addrs_map)
        ]
        if routable_addrs:
            return routable_addrs + [
                ip for ip in maas_dns_servers if ip not in routable_addrs
            ]
        else:
            return maas_dns_servers

    def get_boot_purpose(self):
        """
        Return a suitable "purpose" for this boot, e.g. "install".
        """
        if self.status == NODE_STATUS.DEFAULT and self.is_device:
            # Always local boot a device.
            return "local"
        elif self.status in COMMISSIONING_LIKE_STATUSES:
            # It is commissioning or disk erasing. The environment (boot
            # images, kernel options, etc for erasing is the same as that
            # of commissioning.
            return "commissioning"
        elif self.status == NODE_STATUS.DEPLOYING:
            # Install the node if netboot is enabled,
            # otherwise boot locally.
            if self.netboot:
                return "xinstall"
            else:
                return "local"
        elif (
            self.status == NODE_STATUS.DEPLOYED
            or self.node_type != NODE_TYPE.MACHINE
        ):
            return "local"
        else:
            return "poweroff"

    def get_boot_interface(self):
        """Get the boot interface this node is expected to boot from.

        Normally, this will be the boot interface last used in a
        GetBootConfig RPC request for the node, as recorded in the
        'boot_interface' property. However, if the node hasn't booted since
        the 'boot_interface' property was added to the Node model, this will
        return the node's first interface instead.
        """
        if self.boot_interface is not None:
            return self.boot_interface

        # Only use "all" and perform the sorting manually to stop extra queries
        # when the `interface_set` is prefetched.
        interfaces = sorted(
            self.current_config.interface_set.all(), key=attrgetter("id")
        )
        if len(interfaces) == 0:
            return None
        return interfaces[0]

    def get_boot_rack_controller(self):
        """Return the `RackController` that this node booted from last.

        This uses the `boot_cluster_ip` to determine which rack controller
        this node booted from last. If empty or not a rack controller
        then it will fallback to the primary rack controller for the boot
        interface."""
        rack_controller = None
        if self.boot_cluster_ip is not None:
            rack_controller = RackController.objects.filter(
                current_config__interface__ip_addresses__ip=self.boot_cluster_ip
            ).first()
        if rack_controller is None:
            return self.get_boot_primary_rack_controller()
        else:
            return rack_controller

    def get_boot_primary_rack_controller(self):
        """Return the `RackController` that this node will boot from as its
        primary rack controller ."""
        boot_interface = self.get_boot_interface()
        if (
            boot_interface is None
            or boot_interface.vlan is None
            or not boot_interface.vlan.dhcp_on
        ):
            return None
        else:
            return boot_interface.vlan.primary_rack

    def get_boot_secondary_rack_controller(self):
        """Return the `RackController` that this node will boot from as its
        secondary rack controller ."""
        boot_interface = self.get_boot_interface()
        if (
            boot_interface is None
            or boot_interface.vlan is None
            or not boot_interface.vlan.dhcp_on
        ):
            return None
        else:
            return boot_interface.vlan.secondary_rack

    def get_boot_rack_controllers(self):
        """Return the `RackController` that this node will boot from."""
        boot_interface = self.get_boot_interface()
        if boot_interface is None:
            return []

        boot_vlan = get_dhcp_vlan(boot_interface.vlan)
        if boot_vlan is None:
            return []
        racks = [boot_vlan.primary_rack]
        if boot_vlan.secondary_rack:
            racks.append(boot_vlan.secondary_rack)
        return racks

    def get_extra_macs(self):
        """Get the MACs other that the one the node booted from."""
        boot_interface = self.get_boot_interface()
        # Use all here and not filter on type so the precache is used.
        return [
            interface.mac_address
            for interface in self.current_config.interface_set.all()
            if (
                interface != boot_interface
                and interface.type == INTERFACE_TYPE.PHYSICAL
            )
        ]

    def status_event(self):
        """Returns the most recent status event.

        None if there are no events.
        """
        if hasattr(self, "_status_event"):
            return self._status_event
        else:
            from maasserver.models.event import Event  # Avoid circular import.

            # Id's have a lower (non-zero under heavy load) chance of being out
            # of order than of two timestamps colliding.
            event = Event.objects.filter(
                node=self, type__level__gte=logging.INFO
            )
            event = event.select_related("type")
            event = event.order_by("-created", "-id").first()
            if event is not None:
                self._status_event = event
                return event
            else:
                return None

    def status_message(self):
        """Returns a string representation of the most recent event description
        (supplied through the status API) associated with this node, None if
        there are no events."""
        event = self.status_event()
        if event is not None:
            if event.description:
                return f"{event.type.description} - {event.description}"
            else:
                return event.type.description
        else:
            return None

    def status_action(self):
        """Returns a string representation of the most recent event action name
        (supplied through the status API) associated with this node, None if
        there are no events."""
        event = self.status_event()
        if event is not None:
            return event.action
        else:
            return None

    @property
    def status_name(self):
        """Returns the status of the nome as a user-friendly string."""
        return NODE_STATUS_CHOICES_DICT[self.status]

    @transactional
    def start(
        self,
        user,
        user_data=None,
        comment=None,
        install_kvm=None,
        register_vmhost=None,
        bridge_type=None,
        bridge_stp=None,
        bridge_fd=None,
        enable_hw_sync=None,
    ):
        if not user.has_perm(NodePermission.edit, self):
            # You can't start a node you don't own unless you're an admin.
            raise PermissionDenied()

        updates = {}
        if not self.install_kvm and install_kvm:
            updates["install_kvm"] = True
        if not self.register_vmhost and register_vmhost:
            updates["register_vmhost"] = True
        if not self.enable_hw_sync and enable_hw_sync:
            updates["enable_hw_sync"] = True
        if updates:
            for key, value in updates.items():
                setattr(self, key, value)
            self.save()
        event = EVENT_TYPES.REQUEST_NODE_START
        allow_power_cycle = False
        # If status is ALLOCATED, this start is actually for a deployment.
        # (Note: this is true even when nodes are being deployed from READY
        # state. See node_action.py; the node is acquired and then started.)
        # Power cycling is allowed when deployment is being started.
        if self.status == NODE_STATUS.ALLOCATED:
            event = EVENT_TYPES.REQUEST_NODE_START_DEPLOYMENT
            allow_power_cycle = True
            if self.install_kvm or self.register_vmhost:
                self._create_acquired_bridges(
                    bridge_type=bridge_type,
                    bridge_stp=bridge_stp,
                    bridge_fd=bridge_fd,
                )
        # Bug #1630361: Make sure that there is a maas_facing_server_address in
        # the same address family as our configured interfaces.
        # Every node in a real system has a rack controller, but many tests do
        # not.  To keep this unit-testable, only check for address family
        # compatibility when there is a rack controller.  If we don't have a
        # rack controller, the deployment will be rejected in any case.
        boot_primary_rack_controller = self.get_boot_primary_rack_controller()
        if boot_primary_rack_controller is not None:
            subnets = Subnet.objects.filter(
                staticipaddress__interface__node_config_id=self.current_config_id,
                staticipaddress__alloc_type__in=[
                    IPADDRESS_TYPE.AUTO,
                    IPADDRESS_TYPE.STICKY,
                    IPADDRESS_TYPE.USER_RESERVED,
                    IPADDRESS_TYPE.DHCP,
                ],
            )
            cidrs = subnets.values_list("cidr", flat=True)
            my_address_families = {IPNetwork(cidr).version for cidr in cidrs}
            rack_address_families = {
                4 if addr.is_ipv4_mapped() else addr.version
                for addr in get_maas_facing_server_addresses(
                    boot_primary_rack_controller
                )
            }
            if my_address_families & rack_address_families == set():
                # Node doesn't have any IP addresses in common with the rack
                # controller, unless it has a DHCP assigned without a subnet.
                dhcp_ips_exist = StaticIPAddress.objects.filter(
                    interface__node_config_id=self.current_config_id,
                    alloc_type=IPADDRESS_TYPE.DHCP,
                    subnet__isnull=True,
                ).exists()
                if not dhcp_ips_exist:
                    raise ValidationError(
                        {
                            "network": [
                                "Node has no address family in common with "
                                "the server"
                            ]
                        }
                    )
        if self.ephemeral_deploy and (
            self.install_kvm or self.register_vmhost
        ):
            raise ValidationError(
                "A machine can not be a VM host if it is deployed to memory."
            )
        if self.ephemeral_deploy:
            from maasserver.utils.osystems import (
                get_working_kernel,
                list_all_usable_osystems,
            )

            osystems = list_all_usable_osystems()
            release = osystems[self.osystem].releases[self.distro_series]
            if self.osystem != "ubuntu":
                kernel_arch = self.architecture
            else:
                kernel = get_working_kernel(
                    requested_kernel=self.hwe_kernel,
                    min_compatibility_level=self.min_hwe_kernel,
                    architecture=self.architecture,
                    osystem=self.osystem,
                    distro_series=self.distro_series,
                )
                main_arch = self.architecture.split("/", 1)[0]
                kernel_arch = f"{main_arch}/{kernel}"
            if not release.architectures[kernel_arch].can_deploy_to_memory:
                raise ValidationError(
                    "Deployment to memory not supported for "
                    f"{self.osystem}/{self.distro_series} on {self.architecture}"
                )
        self._register_request_event(
            user, event, action="start", comment=comment
        )
        return self._start(
            user,
            user_data,
            allow_power_cycle=allow_power_cycle,
        )

    def _get_bmc_client_connection_info(self, *args, **kwargs):
        """Return a tuple that list the rack controllers that can communicate
        to the BMC for this node.

        First entry in the tuple is the rack controllers that can communicate
        to a BMC because it has an IP address on a subnet that the rack
        controller also has an IP address.

        Second entry is a fallback to the old way pre-MAAS 2.0 where only
        the rack controller that owned the node could power it on. Here we
        provide the primary and secondary rack controllers that are managing
        the VLAN that this node PXE boots from.
        """
        if self.bmc is None:
            client_idents = []
        else:
            client_idents = self.bmc.get_client_identifiers()
        fallback_idents = [
            rack.system_id for rack in self.get_boot_rack_controllers()
        ]
        if len(client_idents) == 0 and len(fallback_idents) == 0:
            err_msg = "No rack controllers can access the BMC of node %s" % (
                self.hostname
            )
            self._register_request_event(
                self.owner,
                EVENT_TYPES.NODE_POWER_QUERY_FAILED,
                "Failed to query node's BMC",
                err_msg,
            )
            maaslog.warning(
                "%s: Could not change the power state. No rack controllers "
                "can access the BMC." % self.hostname
            )
            raise PowerProblem(err_msg)
        return client_idents, fallback_idents

    @transactional
    def _start_bmc_unavailable(self, user, old_status):
        # Avoid circular imports.
        from maasserver.models.event import Event

        stat = map_enum_reverse(NODE_STATUS, ignore=["DEFAULT"])
        maaslog.info(
            "%s: Aborting %s and reverted to %s. Unable to power "
            "control the node. Please check power credentials."
            % (self.hostname, stat[self.status], stat[old_status])
        )

        event_details = EVENT_DETAILS[EVENT_TYPES.NODE_POWER_QUERY_FAILED]
        Event.objects.register_event_and_event_type(
            EVENT_TYPES.NODE_POWER_QUERY_FAILED,
            type_level=event_details.level,
            event_action="",
            type_description=event_details.description,
            event_description=(
                "(%s) - Aborting %s and reverting to %s. Unable to "
                "power control the node. Please check power "
                "credentials." % (user, stat[self.status], stat[old_status])
            ),
            system_id=self.system_id,
        )

        self.update_status(old_status)
        self.save()

        self.get_latest_script_results.filter(
            status__in=SCRIPT_STATUS_RUNNING_OR_PENDING
        ).update(status=SCRIPT_STATUS.ABORTED, updated=now())

    def validate_bootresource_exists_for_action(self, config=None):
        from maasserver.models import BootResource

        # Validate that the operating system being booted and deployed are
        # available before booting. Checks for the allocated and deployed
        # state as validation occurs before transitioning.
        deployment_like_status = [NODE_STATUS.DEPLOYING, NODE_STATUS.ALLOCATED]
        if self.status in COMMISSIONING_LIKE_STATUSES + deployment_like_status:
            if config is None:
                config = Config.objects.get_configs(
                    [
                        "commissioning_osystem",
                        "commissioning_distro_series",
                        "default_osystem",
                        "default_distro_series",
                    ]
                )
            arch, platform = self.architecture.split("/")
            if self.status in deployment_like_status:
                osystem = self.get_osystem(default=config["default_osystem"])
                distro_series = self.get_distro_series(
                    default=config["default_distro_series"]
                )
                resource = BootResource.objects.get_resource_for(
                    osystem,
                    arch,
                    platform,
                    distro_series,
                    BOOT_IMAGE_PURPOSE.XINSTALL,
                )
                if resource is None:
                    raise ValidationError(
                        f"Deployment operating system {osystem}/{distro_series} "
                        f"is unavailable for {arch}/{platform}."
                    )
            # Non-Ubuntu deployments use the commissioning OS during deployment
            if self.status in COMMISSIONING_LIKE_STATUSES or (
                self.status in deployment_like_status
                and self.osystem != "ubuntu"
            ):
                resource = BootResource.objects.get_resource_for(
                    config["commissioning_osystem"],
                    arch,
                    platform,
                    config["commissioning_distro_series"],
                    BOOT_IMAGE_PURPOSE.COMMISSIONING,
                )

                if resource is None:
                    raise ValidationError(
                        f"Ephemeral operating system {config['commissioning_osystem']}"
                        f"/{config['commissioning_distro_series']} "
                        f"for {arch}/{platform} is unavailable."
                    )

    def set_user_data(self, user_data: bytes | None = None) -> None:
        from maasserver.models import NodeUserData

        # Record the user data for the node. Note that we do this
        # whether or not we can actually send power commands to the
        # node; the user may choose to start it manually.
        NodeUserData.objects.set_user_data(self, user_data)

    def _temporal_deploy(
        self, _, d: Deferred, power_info: PowerInfo, task_queue: str
    ) -> Deferred:
        dd = start_workflow(
            "deploy-n",
            param=DeployNParam(
                params=[
                    DeployParam(
                        system_id=str(self.system_id),
                        power_params=PowerParam(
                            system_id=str(self.system_id),
                            driver_type=str(power_info.power_type),
                            driver_opts=dict(power_info.power_parameters),
                            task_queue=task_queue,
                        ),
                        ephemeral_deploy=bool(self.ephemeral_deploy),
                        can_set_boot_order=bool(power_info.can_set_boot_order),
                        task_queue="region",
                    ),
                ],
            ),
            task_queue="region",
        )
        if not dd.called:
            return dd
        return d

    @transactional
    def _start(
        self,
        user: User,
        user_data: bytes | None = None,
        old_status=None,
        allow_power_cycle: bool = False,
        config=None,
    ) -> Deferred | None:
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
            required to run to start the node. This is already registered as a
            post-commit hook; it should not be added a second time. If it has
            not been possible to start the node because the power controller
            does not support it, `None` will be returned. The node must be
            powered on manually.
        """

        if not user.has_perm(NodePermission.edit, self):
            # You can't start a node you don't own unless you're an admin.
            raise PermissionDenied()

        self.validate_bootresource_exists_for_action(config=config)

        self.set_user_data(user_data=user_data)

        # Auto IP allocation and power on action are attached to the
        # post commit of the transaction.
        d = post_commit()
        claimed_ips = False
        needs_power_call = True

        power_info = self.get_effective_power_info()

        @inlineCallbacks
        def claim_auto_ips(_):
            yield self._claim_auto_ips()

        if self.status == NODE_STATUS.ALLOCATED:
            old_status = self.status
            set_deployment_timeout = False  # handled by temporal
            d.addCallback(claim_auto_ips)
            self._start_deployment()
            claimed_ips = True
            needs_power_call = False
            task_queue = str(get_temporal_task_queue_for_bmc(self))

            d.addCallback(self._temporal_deploy, d, power_info, task_queue)

        elif self.status in COMMISSIONING_LIKE_STATUSES:
            if old_status is None:
                old_status = self.status
            from maasserver.models import ScriptResult

            # Claim AUTO IP addresses if a script will be running in the
            # ephemeral environment which needs network configuration applied.
            if ScriptResult.objects.filter(
                script_set__in=[
                    self.current_commissioning_script_set,
                    self.current_testing_script_set,
                ],
                script__apply_configured_networking=True,
            ).exists():
                d.addCallback(claim_auto_ips)
                claimed_ips = True
            set_deployment_timeout = False
        elif self.status == NODE_STATUS.DEPLOYED and self.ephemeral_deploy:
            # Ephemeral deployments need to be re-deployed on a power cycle
            # and will already be in a DEPLOYED state.
            set_deployment_timeout = True
            self._start_deployment()
            needs_power_call = False

            task_queue = str(get_temporal_task_queue_for_bmc(self))

            d.addCallback(self._temporal_deploy, d, power_info, task_queue)
        else:
            set_deployment_timeout = False

        if not power_info.can_be_started:
            # The node can't be powered on by MAAS, so return early.
            # Everything we've done up to this point is still valid;
            # this is not an error state.
            return None

        if needs_power_call:
            if power_info.can_set_boot_order:
                boot_order = self._get_boot_order()
            else:
                boot_order = []

            # Request that the node be powered on post-commit.
            if self.power_state == POWER_STATE.ON and allow_power_cycle:
                d = self._power_control_node(
                    d, POWER_WORKFLOW_ACTIONS.CYCLE, power_info, boot_order
                )
            else:
                d = self._power_control_node(
                    d, POWER_WORKFLOW_ACTIONS.ON, power_info, boot_order
                )

        # Set the deployment timeout so the node is marked failed after
        # a period of time.
        if set_deployment_timeout:
            d.addCallback(
                callOutToDatabase,
                Node._set_status_expires,
                self.system_id,
                NODE_STATUS.DEPLOYING,
            )

        if old_status is not None:
            d.addErrback(
                callOutToDatabase,
                self._start_bmc_unavailable,
                user,
                old_status,
            )

        # If any part of this processes fails be sure to release the grabbed
        # auto IP addresses.
        if claimed_ips:
            d.addErrback(callOutToDatabase, self.release_interface_config)

        return d

    @transactional
    def stop(self, user=None, stop_mode="hard", comment=None):
        if user is not None and not user.has_perm(NodePermission.edit, self):
            # You can't stop a node you don't own unless you're an admin.
            raise PermissionDenied()
        self._register_request_event(
            user, EVENT_TYPES.REQUEST_NODE_STOP, action="stop", comment=comment
        )
        return self._stop(user, stop_mode)

    @transactional
    def _stop(self, user=None, stop_mode="hard"):
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
        if user is not None and not user.has_perm(NodePermission.edit, self):
            # You can't stop a node you don't own unless you're an admin.
            raise PermissionDenied()

        power_info = self.get_effective_power_info()
        if not power_info.can_be_stopped:
            # We can't stop this node, so just return; trying to stop a
            # node we don't know how to stop isn't an error state, but
            # it's a no-op.
            return None

        if power_info.can_set_boot_order:
            boot_order = self._get_boot_order()
        else:
            boot_order = []

        # Smuggle in a hint about how to power-off the self.
        if power_info.power_type == "ipmi":
            power_info.power_parameters["power_off_mode"] = stop_mode

        # Request that the node be powered off post-commit.
        d = post_commit()
        return self._power_control_node(
            d, POWER_WORKFLOW_ACTIONS.OFF, power_info, boot_order
        )

    @asynchronous
    def power_query(self):
        """Query the power state of the BMC for this node.

        This make sure either a layer-2 or a routable connection can be
        determined for the BMC before performing the query.

        This method can be called from within the reactor or will return an
        `EventualResult`. Wait should be called on the result for the desired
        waiting time. Recommend timeout is 45 seconds. 30 seconds for the
        power_query_all and 15 seconds for the power_query.
        """
        # Avoid circular imports.
        from maasserver.models.event import Event

        d = deferToDatabase(transactional(self.get_effective_power_info))

        def cb_query(power_info):
            d = self._power_control_node(
                succeed(None), POWER_WORKFLOW_ACTIONS.QUERY, power_info
            )
            d.addCallback(lambda result: (result, power_info))
            return d

        @transactional
        def cb_create_event(result):
            response, _ = result
            power_state = response["state"]
            power_error = (
                response["error_msg"] if "error_msg" in response else None
            )
            node = Node.objects.get(id=self.id)
            if power_error is None:
                log.debug(
                    f"Power state queried for node {node.system_id}: "
                    f"{power_state}"
                )
            else:
                Event.objects.create_node_event(
                    node,
                    EVENT_TYPES.NODE_POWER_QUERY_FAILED,
                    event_description=power_error,
                )
            return result

        def cb_update_power(result):
            response, power_info = result
            power_state = response["state"]
            if power_info.can_be_queried and self.power_state != power_state:

                @transactional
                def cb_update_queryable_node():
                    node = Node.objects.get(id=self.id)
                    node.update_power_state(power_state)
                    return power_state

                return deferToDatabase(cb_update_queryable_node)
            elif not power_info.can_be_queried:

                @transactional
                def cb_update_non_queryable_node():
                    node = Node.objects.get(id=self.id)
                    node.update_power_state(POWER_STATE.UNKNOWN)
                    return POWER_STATE.UNKNOWN

                return deferToDatabase(cb_update_non_queryable_node)
            else:
                return power_state

        d.addCallback(cb_query)
        d.addCallback(partial(deferToDatabase, cb_create_event))
        d.addCallback(cb_update_power)
        return d

    def _power_control_node(
        self, defer, power_method_name, power_info, order=None
    ):
        # Check if the BMC is accessible. If not we need to do some work to
        # make sure we can determine which rack controller can power
        # control this node.
        def is_bmc_accessible():
            node = Node.objects.get(id=self.id)
            if node.bmc is None:
                raise PowerProblem(
                    "No BMC is defined.  Cannot power control node."
                )
            else:
                return node.bmc.is_accessible()

        defer.addCallback(
            lambda _: deferToDatabase(transactional(is_bmc_accessible))
        )

        def cb_update_routable_racks(accessible):
            if not accessible:
                # Perform power query on all of the rack controllers to
                # determine which has access to this node's BMC.
                d = power_query_all(self.system_id, self.hostname, power_info)

                @transactional
                def cb_update_routable(result):
                    node = Node.objects.get(id=self.id)
                    power_state, routable_racks, non_routable_racks = result
                    if (
                        power_info.can_be_queried
                        and node.power_state != power_state
                    ):
                        # MAAS will query power types that even say they don't
                        # support query. But we only update the power_state on
                        # those we are saying MAAS reports on.
                        node.update_power_state(power_state)
                    node.bmc.update_routable_racks(
                        routable_racks, non_routable_racks
                    )

                # Update the routable information for the BMC.
                d.addCallback(
                    partial(deferToDatabase, transactional(cb_update_routable))
                )
                return d

        # Update routable racks only if the BMC is not accessible.
        defer.addCallback(cb_update_routable_racks)

        # Get the client connection information for the node.
        defer.addCallback(
            partial(deferToDatabase, self._get_bmc_client_connection_info)
        )

        def cb_power_control(result):
            client_idents, fallback_idents = result

            def eb_fallback_clients(failure):
                failure.trap(NoConnectionsAvailable)
                return getClientFromIdentifiers(fallback_idents)

            def cb_check_power_driver(client, power_info):
                d = Node.confirm_power_driver_operable(
                    client, power_info.power_type, client.ident
                )
                d.addCallback(lambda _: client)
                return d

            # Check that we should just not start with the fallback.
            try_fallback = True
            if len(client_idents) == 0:
                client_idents = fallback_idents
                try_fallback = False

            # Get the client and fallback if needed.
            d = getClientFromIdentifiers(client_idents)
            if try_fallback:
                d.addErrback(eb_fallback_clients)
            d.addCallback(cb_check_power_driver, power_info)
            if order:
                d.addCallback(
                    set_boot_order,
                    self.system_id,
                    self.hostname,
                    power_info,
                    order,
                )
            if power_method_name:
                d.addCallback(
                    lambda _: deferToDatabase(
                        convert_power_action_to_power_workflow,
                        power_method_name.replace("_", "-"),
                        self,
                        power_info,
                    ),
                )

                @inlineCallbacks
                def exec_power_workflow(workflow_info):
                    workflow_name, workflow_param = workflow_info
                    try:
                        res = yield execute_workflow(
                            workflow_name,
                            param=workflow_param,
                        )
                        returnValue(res)
                    except WorkflowFailureError as e:
                        cause = getattr(e.cause, "cause", e.cause)
                        raise PowerActionFail(cause)

                d.addCallback(exec_power_workflow)

                def _handle_workflow_result(result):
                    if result:
                        # workflow assumes bulk execution, return only result
                        return result
                    else:
                        return {"state": POWER_STATE.UNKNOWN}

                d.addCallback(_handle_workflow_result)

                @transactional
                def _update_node_power_state(result):
                    node = Node.objects.get(id=self.id)
                    node.update_power_state(result.get("state"))
                    return result

                d.addCallback(
                    lambda result: deferToDatabase(
                        _update_node_power_state, result
                    )
                )

            return d

        # Power control the node.
        defer.addCallback(cb_power_control)
        return defer

    @classmethod
    @transactional
    def _set_status(cls, system_id, status):
        """Set the status of the node identified by `system_id`.

        This is a convenience for use as a call-back.
        """
        node = cls.objects.get(system_id=system_id)
        node.status = status
        node.save()

    def _power_cycle(self):
        """Power cycle the node."""
        power_info = self.get_effective_power_info()
        if power_info.can_set_boot_order:
            boot_order = self._get_boot_order()
        else:
            boot_order = []

        # Request that the node be power cycled post-commit.
        d = post_commit()
        return self._power_control_node(
            d, POWER_WORKFLOW_ACTIONS.CYCLE, power_info, boot_order
        )

    @transactional
    def start_rescue_mode(self, user):
        """Start rescue mode."""
        # Avoid circular imports.
        from maasserver.models.event import Event
        from maasserver.models.nodeuserdata import NodeUserData

        if not user.has_perm(NodePermission.edit, self):
            # You can't enter rescue mode on a node you don't own,
            # unless you're an admin.
            raise PermissionDenied()
        # Power type must be configured.
        if self.power_type == "":
            raise UnknownPowerType(
                "Unconfigured power type. "
                "Please configure the power type and try again."
            )
        # Register event.
        self._register_request_event(
            user,
            EVENT_TYPES.REQUEST_NODE_START_RESCUE_MODE,
            action="start rescue mode",
        )

        rescue_mode_user_data = generate_user_data_for_status(
            node=self, status=NODE_STATUS.RESCUE_MODE
        )

        # Record the user data for the node. Note that we do this
        # whether or not we can actually send power commands to the
        # node; the user may choose to start it manually.
        NodeUserData.objects.set_user_data(self, rescue_mode_user_data)

        # We need to mark the node as ENTERING_RESCUE_MODE now to avoid a race
        # when starting multiple nodes. We hang on to old_status just in
        # case the power action fails.
        old_status = self.update_status(NODE_STATUS.ENTERING_RESCUE_MODE)
        self.owner = user
        self.save()

        # Create a status message for ENTERING_RESCUE_MODE.
        Event.objects.create_node_event(self, EVENT_TYPES.ENTERING_RESCUE_MODE)

        try:
            cycling = self._power_cycle()
        except Exception as error:
            self.update_status(old_status)
            self.save()
            maaslog.error(
                "%s: Could not start rescue mode for node: %s",
                self.hostname,
                error,
            )
            # Let the exception bubble up, since the UI or API will have to
            # deal with it.
            raise
        else:
            # Don't permit naive mocking of cycling(); it causes too much
            # confusion when testing. Return a Deferred from side_effect.
            assert isinstance(cycling, Deferred) or cycling is None

            post_commit().addCallback(
                callOutToDatabase, Node._set_status_expires, self.system_id
            )

            if cycling is None:
                cycling = post_commit()
                # MAAS cannot start the node itself.
                is_cycling = False
            else:
                # MAAS can direct the node to start.
                is_cycling = True

            cycling.addCallback(
                callOut,
                self._start_rescue_mode_async,
                is_cycling,
                self.hostname,
            )

            # If there's an error, reset the node's status.
            cycling.addErrback(
                callOutToDatabase,
                Node._set_status,
                self.system_id,
                status=old_status,
            )

            def eb_start(failure, hostname):
                maaslog.error(
                    "%s: Could not start rescue mode for node: %s",
                    hostname,
                    failure.getErrorMessage(),
                )
                return failure  # Propagate.

            return cycling.addErrback(eb_start, self.hostname)

    @classmethod
    @asynchronous
    def _start_rescue_mode_async(cls, is_cycling, hostname):
        """Start rescue mode, the post-commit bits.

        :param is_cycling: A boolean indicating if MAAS is able to start this
            node itself, or if manual intervention is needed.
        :param hostname: The node's hostname, for logging.
        """
        if is_cycling:
            maaslog.info("%s: Rescue mode starting", hostname)
        else:
            maaslog.warning(
                "%s: Could not start rescue mode for node; it "
                "must be started manually",
                hostname,
            )

    @transactional
    def stop_rescue_mode(self, user):
        """Exit rescue mode."""
        if not user.has_perm(NodePermission.edit, self):
            # You can't exit rescue mode on a node you don't own,
            # unless you're an admin.
            raise PermissionDenied()
        # Register event.
        self._register_request_event(
            user,
            EVENT_TYPES.REQUEST_NODE_STOP_RESCUE_MODE,
            action="stop rescue mode",
        )
        # We need to mark the node as EXITING_RESCUE_MODE now to avoid a race
        # when starting multiple nodes. We hang on to old_status just in
        # case the power action fails.
        old_status = self.update_status(NODE_STATUS.EXITING_RESCUE_MODE)
        self.save()

        try:
            if self.previous_status in (NODE_STATUS.READY, NODE_STATUS.BROKEN):
                self._stop(user)
            elif self.previous_status == NODE_STATUS.DEPLOYED:
                self._power_cycle()
        except Exception as error:
            self.update_status(old_status)
            self.save()
            maaslog.error(
                "%s: Could not stop rescue mode for node: %s",
                self.hostname,
                error,
            )
            # Let the exception bubble up, since the UI or API will have to
            # deal with it.
            raise

        # If the power state cannot be queried(manual power type) transition
        # to the previous state right away.
        if not self.get_effective_power_info().can_be_queried:
            if self.previous_status != NODE_STATUS.DEPLOYED:
                self.owner = None
            self.update_status(self.previous_status)
            self.save()

    def _as(self, model):
        """Create a `model` that shares underlying storage with `self`.

        In other words, the newly returned object will be an instance of
        `model` and its `__dict__` will be `self.__dict__`. Not a copy, but a
        reference to, so that changes to one will be reflected in the other.
        """
        new = object.__new__(model)
        new.__dict__ = self.__dict__
        return new

    def as_node(self):
        """Return a reference to self that behaves as a `Node`."""
        return self._as(Node)

    def as_machine(self):
        """Return a reference to self that behaves as a `Machine`."""
        return self._as(Machine)

    def as_device(self):
        """Return a reference to self that behaves as a `Device`."""
        return self._as(Device)

    def as_region_controller(self):
        """Return a reference to self that behaves as a `RegionController`."""
        return self._as(RegionController)

    def as_rack_controller(self):
        """Return a reference to self that behaves as a `RackController`."""
        return self._as(RackController)

    _as_self = {
        NODE_TYPE.DEVICE: as_device,
        NODE_TYPE.MACHINE: as_machine,
        NODE_TYPE.RACK_CONTROLLER: as_rack_controller,
        # XXX ltrager 18-02-2016 - Currently only rack controllers have
        # unique functionality so when combined return a rack controller
        NODE_TYPE.REGION_AND_RACK_CONTROLLER: as_rack_controller,
        NODE_TYPE.REGION_CONTROLLER: as_region_controller,
    }

    def as_self(self):
        """Return a reference to self that behaves as its own type."""
        return self._as_self[self.node_type](self)

    @property
    def get_latest_script_results(self):
        """Returns a QuerySet of the latest results from all runs."""
        from maasserver.models import ScriptResult

        qs = ScriptResult.objects.filter(script_set__node_id=self.id)
        qs = qs.select_related("script_set", "script")
        qs = qs.order_by(
            "script_name", "physical_blockdevice_id", "interface_id", "-id"
        )
        qs = qs.distinct(
            "script_name", "physical_blockdevice_id", "interface_id"
        )
        return qs

    @property
    def get_latest_commissioning_script_results(self):
        """Returns a QuerySet of the latest commissioning results."""
        return self.get_latest_script_results.filter(
            script_set__result_type=RESULT_TYPE.COMMISSIONING
        )

    @property
    def get_latest_testing_script_results(self):
        """Returns a QuerySet of the latest testing results."""
        return self.get_latest_script_results.filter(
            script_set__result_type=RESULT_TYPE.TESTING
        )

    @property
    def get_latest_installation_script_results(self):
        """Returns a QuerySet of the latest installation results."""
        return self.get_latest_script_results.filter(
            script_set__result_type=RESULT_TYPE.INSTALLATION
        )

    @property
    def modaliases(self) -> List[str]:
        """Return a list of modaliases from the node."""
        script_set = self.current_commissioning_script_set
        if script_set is None:
            return []

        script_result = script_set.find_script_result(
            script_name=LIST_MODALIASES_OUTPUT_NAME
        )
        if (
            script_result is None
            or script_result.status != SCRIPT_STATUS.PASSED
        ):
            return []
        else:
            return script_result.stdout.decode("utf-8").splitlines()

    def get_hosted_pods(self) -> QuerySet:
        # Circular imports
        from maasserver.models import Pod

        # Node's aren't created for Virsh or Intel Pods so the pod.hints.nodes
        # association isn't created. LXD Pods always have this association.
        our_static_ips = StaticIPAddress.objects.filter(
            interface__node_config_id=self.current_config_id
        ).values_list("ip")
        return Pod.objects.filter(
            Q(hints__nodes__in=[self]) | Q(ip_address__ip__in=our_static_ips)
        ).distinct()

    def should_be_dynamically_deleted(self):
        """Best guess if the node was dynamically created.

        MAAS doesn't track node transitions so we have to look at
        breadcrumbs.

        When a machine is created dynamically, it has the dynamic flag,
        and doesn't have a BMC. If that's still true, it probably was a machine.

        If the machine was dynamically created and later had the BMC
        set, it's ok  that this method returns False. Given that the BMC
        was set, it probably means that the user wants to keep this
        machine anyway.
        """
        return self.dynamic and self.bmc_id is None


# Piston serializes objects based on the object class.
# Here we define a proxy class so that we can specialize how devices are
# serialized on the API.    def get_primary_rack_controller(self):
class Machine(Node):
    """An installable node."""

    objects = MachineManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        super().__init__(node_type=NODE_TYPE.MACHINE, *args, **kwargs)

    def delete(self, force=False):
        """Deletes this Machine.

        Before deletion, checks if any hosted pods exist.

        Raises ValidationError if the machine is a host for one or more pods,
        and `force=True` was not specified.
        """
        self.maybe_delete_pods(not force)
        return super().delete()


class Controller(Node):
    """A node which is either a rack or region controller."""

    objects = ControllerManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def report_neighbours(self, neighbours):
        """Update the neighbour table for this controller.

        :param neighbours: A list of dictionaries containing neighbour data.
            Neighbour data is gathered directly from the ARP monitoring process
            running on each rack interface.
        """
        # Determine which interfaces' neighbours need updating.
        interface_set = {neighbour["interface"] for neighbour in neighbours}
        interfaces = Interface.objects.get_interface_dict_for_node(
            self, names=interface_set, fetch_fabric_vlan=True
        )
        for neighbour in neighbours:
            interface = interfaces.get(neighbour["interface"], None)
            if interface is not None:
                vid = neighbour.get("vid", None)
                if interface.neighbour_discovery_state:
                    interface.update_neighbour(
                        neighbour["ip"],
                        neighbour["mac"],
                        neighbour["time"],
                        vid=vid,
                    )
                if vid is not None:
                    interface.report_vid(vid, ip=neighbour["ip"])

    def report_mdns_entries(self, entries):
        """Update the mDNS entries on this controller.

        :param entries: A list of dictionaries containing discovered mDNS
            entries. mDNS data is gathered from an `avahi-browse` process
            running on each rack interface.
        """
        # Determine which interfaces' entries need updating.
        interface_set = {entry["interface"] for entry in entries}
        interfaces = Interface.objects.get_interface_dict_for_node(
            self, names=interface_set
        )
        for entry in entries:
            interface = interfaces.get(entry["interface"], None)
            if interface is not None:
                interface.update_mdns_entry(entry)

    def get_discovery_state(self):
        """Returns the interface monitoring state for this Controller.

        The returned object must be suitable to serialize into JSON for RPC
        purposes.
        """
        interfaces = self.current_config.interface_set.all()
        return {
            interface.name: interface.get_discovery_state()
            for interface in interfaces
        }

    @transactional
    def _get_token_for_controller(self):
        from maasserver.models import NodeKey

        token = NodeKey.objects.get_token_for_node(self)
        # Pull consumer into memory so it can be accessed outside a
        # database thread
        token.consumer
        return token

    @transactional
    def _signal_start_of_refresh(self):
        self._register_request_event(
            self.owner,
            EVENT_TYPES.REQUEST_CONTROLLER_REFRESH,
            action="starting refresh",
        )

    @property
    def info(self):
        try:
            return self.controllerinfo
        except ObjectDoesNotExist:
            return None

    @property
    def version(self):
        try:
            return self.controllerinfo.version
        except ObjectDoesNotExist:
            return None

    def update_discovery_state(self, discovery_mode):
        """Update network discovery state on this Controller's interfaces.

        The `discovery_mode` parameter must be a NetworkDiscoveryConfig tuple.

        Returns the `interfaces` dictionary used during processing.
        """
        # Get the interfaces in the [rough] format of the region/rack contract.
        interfaces = Interface.objects.get_all_interfaces_definition_for_node(
            self
        )
        # Use the data to calculate which interfaces should be monitored by
        # default on this controller, then update each interface.
        monitored_interfaces = get_default_monitored_interfaces(interfaces)
        for name, settings in interfaces.items():
            interface = settings["obj"]
            interface.update_discovery_state(
                discovery_mode, name in monitored_interfaces
            )
        return interfaces

    @inlineCallbacks
    def start_refresh(self):
        """Start refreshing the hardware and networking information.

        It signals the start of the refresh as an event and returns the
        credentials needed to post commissioning data to the metadata
        server.
        """
        token = yield deferToDatabase(self._get_token_for_controller)

        yield deferToDatabase(self._signal_start_of_refresh)
        returnValue(
            {
                "consumer_key": token.consumer.key,
                "token_key": token.key,
                "token_secret": token.secret,
            }
        )


class RackController(Controller):
    """A node which is running rackd."""

    objects = RackControllerManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        super().__init__(node_type=NODE_TYPE.RACK_CONTROLLER, *args, **kwargs)

    def add_chassis(
        self,
        user,
        chassis_type,
        hostname,
        username=None,
        password=None,
        accept_all=False,
        domain=None,
        prefix_filter=None,
        power_control=None,
        port=None,
        protocol=None,
        token_name=None,
        token_secret=None,
        verify_ssl=False,
    ):
        self._register_request_event(
            self.owner,
            EVENT_TYPES.REQUEST_RACK_CONTROLLER_ADD_CHASSIS,
            action="Adding chassis %s" % hostname,
        )
        client = getClientFor(self.system_id, timeout=1)
        call = client(
            AddChassis,
            user=user,
            chassis_type=chassis_type,
            hostname=hostname,
            username=username,
            password=password,
            accept_all=accept_all,
            domain=domain,
            prefix_filter=prefix_filter,
            power_control=power_control,
            port=port,
            protocol=protocol,
            token_name=token_name,
            token_secret=token_secret,
            verify_ssl=verify_ssl,
        )
        call.wait(30)

    def get_bmc_accessible_nodes(self):
        """Return `QuerySet` of nodes that this rack controller can access.

        This looks at the IP address assigned to all BMC's and filters out
        only the BMC's this rack controller can access. Returning all nodes
        connected to those BMCs.
        """
        subnet_ids = (
            StaticIPAddress.objects.filter(
                interface__node_config_id=self.current_config_id
            )
            .exclude(ip__isnull=True)
            .exclude(subnet_id__isnull=True)
            .values_list("subnet_id", flat=True)
        )
        nodes = Node.objects.filter(
            bmc__ip_address__ip__isnull=False,
            bmc__ip_address__subnet_id__in=subnet_ids,
        ).distinct()
        return nodes

    def migrate_dhcp_from_rack(self, commit: bool = True):
        """Migrate the DHCP away from the rack controller.

        :param commit: Whether to commit the change to the database. When False
            the change will not be committed and only what would have happened
            would be returned.
        :returns: List of tuples with (VLAN, new primary rack,
            new secondary rack). If both primary is set to `None` then
            `dhcp_on` will also be set to `False` for the VLAN.
        """
        changes = []

        controlled_vlans = (
            VLAN.objects.filter(dhcp_on=True)
            .prefetch_related("primary_rack", "secondary_rack")
            .filter(Q(primary_rack=self) | Q(secondary_rack=self))
        )
        for controlled_vlan in controlled_vlans:
            if controlled_vlan.primary_rack_id == self.id:
                if controlled_vlan.secondary_rack_id is not None:
                    new_rack, new_racks = (
                        None,
                        controlled_vlan.connected_rack_controllers(
                            exclude_racks=[
                                self,
                                controlled_vlan.secondary_rack,
                            ]
                        ),
                    )
                    if new_racks:
                        new_rack = new_racks[0]
                    changes.append(
                        (
                            controlled_vlan,
                            controlled_vlan.secondary_rack,
                            new_rack,
                        )
                    )
                    controlled_vlan.primary_rack = (
                        controlled_vlan.secondary_rack
                    )
                    controlled_vlan.secondary_rack = new_rack
                else:
                    new_rack, new_racks = (
                        None,
                        controlled_vlan.connected_rack_controllers(
                            exclude_racks=[self]
                        ),
                    )
                    if new_racks:
                        new_rack = new_racks[0]
                    changes.append((controlled_vlan, new_rack, None))
                    controlled_vlan.primary_rack = new_rack
                    if new_rack is None:
                        # No primary_rack now for the VLAN, so DHCP
                        # gets disabled.
                        controlled_vlan.dhcp_on = False
            elif controlled_vlan.secondary_rack_id == self.id:
                new_rack, new_racks = (
                    None,
                    controlled_vlan.connected_rack_controllers(
                        exclude_racks=[self, controlled_vlan.primary_rack]
                    ),
                )
                if new_racks:
                    new_rack = new_racks[0]
                changes.append(
                    (controlled_vlan, controlled_vlan.primary_rack, new_rack)
                )
                controlled_vlan.secondary_rack = new_rack

        if commit:
            for controlled_vlan in controlled_vlans:
                controlled_vlan.save()

        return changes

    def delete(self, force=False):
        """Delete this rack controller."""
        # Don't bother with the pod check if this is a region+rack, because
        # deleting a region+rack results in a region-only controller.
        if self.node_type != NODE_TYPE.REGION_AND_RACK_CONTROLLER:
            self.maybe_delete_pods(not force)

        from maasserver.models import RegionRackRPCConnection

        # Migrate this rack controller away from managing any VLAN's.
        changes = self.migrate_dhcp_from_rack(commit=True)
        if not force:
            # Ensure that none of the VLAN's DHCP would have been disabled.
            disabled = [
                vlan
                for vlan, primary_rack, secondary_rack in changes
                if primary_rack is None
            ]
            if disabled:
                raise ValidationError(
                    "Unable to delete '%s'; it is currently set as a "
                    "primary rack controller on VLANs %s and no other rack "
                    "controller can provide DHCP."
                    % (
                        self.hostname,
                        ", ".join([str(vlan) for vlan in disabled]),
                    )
                )

        # Disable and delete all services related to this node
        self.service_set.mark_dead(self, dead_rack=True)
        self.service_set.all().delete()

        try:
            client = getClientFor(self.system_id, timeout=1)
            call = client(DisableAndShutoffRackd)
            call.wait(10)
        except (NoConnectionsAvailable, TimeoutError, ConnectionDone):
            # NoConnectionsAvailable is always thrown. Either because the rack
            # is currently disconnected or rackd was killed.
            # TimeoutError may occur if the rack was just powered down and the
            # region thinks it still has a connection.
            # ConnectionDone occurs when the RPC call successfully stops and
            # disables the rack service.
            pass

        RegionRackRPCConnection.objects.filter(rack_controller=self).delete()

        for vlan in VLAN.objects.filter(secondary_rack=self):
            vlan.secondary_rack = None
            vlan.save()

        if self.node_type == NODE_TYPE.REGION_AND_RACK_CONTROLLER:
            self.node_type = NODE_TYPE.REGION_CONTROLLER
            self.save()
        elif not self.should_be_dynamically_deleted():
            self.node_type = NODE_TYPE.MACHINE
            self.save()
        else:
            super().delete()

    def update_rackd_status(self):
        """Update the status of the "rackd" service for this rack controller.

        The "rackd" service status is determined based on the number of
        connections it has to all region controller processes.
        """
        # Circular imports.
        from maasserver.models import (
            RegionControllerProcess,
            RegionRackRPCConnection,
        )

        connections = RegionRackRPCConnection.objects.filter(
            rack_controller=self
        ).prefetch_related("endpoint__process")
        if len(connections) == 0:
            # Not connected to any regions so the rackd is considered dead.
            Service.objects.mark_dead(self, dead_rack=True)
        else:
            connected_to_processes = {
                conn.endpoint.process for conn in connections
            }
            all_processes = set(RegionControllerProcess.objects.all())
            dead_regions = RegionController.objects.exclude(
                processes__in=all_processes
            ).count()
            missing_processes = all_processes - connected_to_processes
            if dead_regions == 0 and len(missing_processes) == 0:
                # Connected to all processes.
                Service.objects.update_service_for(
                    self, "rackd", SERVICE_STATUS.RUNNING
                )
            else:
                # Calculate precentage of connection.
                percentage = ((dead_regions * 4) + len(missing_processes)) / (
                    RegionController.objects.count() * 4
                )
                Service.objects.update_service_for(
                    self,
                    "rackd",
                    SERVICE_STATUS.DEGRADED,
                    "{:.0%} connected to region controllers.".format(
                        1.0 - percentage
                    ),
                )


class RegionController(Controller):
    """A node which is running multiple regiond's."""

    objects = RegionControllerManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        super().__init__(
            node_type=NODE_TYPE.REGION_CONTROLLER, *args, **kwargs
        )

    def delete(self, force=False):
        """Delete this region controller."""
        self.maybe_delete_pods(not force)
        # Avoid circular dependency.
        from maasserver.models import RegionControllerProcess

        connections = RegionControllerProcess.objects.filter(region=self)

        if len(connections) != 0:
            raise ValidationError(
                "Unable to delete %s as it's currently running."
                % self.hostname
            )

        if self.node_type == NODE_TYPE.REGION_AND_RACK_CONTROLLER:
            # Node.as_self() returns a RackController object when the node is
            # a REGION_AND_RACK_CONTROLLER. Thus the API and websocket will
            # transition a REGION_AND_RACK_CONTROLLER to a REGION_CONTROLLER.
            self.node_type = NODE_TYPE.RACK_CONTROLLER
            self.save()
        elif not self.should_be_dynamically_deleted():
            self.node_type = NODE_TYPE.MACHINE
            self.save()
        else:
            super().delete()


class Device(Node):
    """A non-installable node."""

    objects = DeviceManager()

    class Meta:
        proxy = True

    def __init__(self, *args, **kwargs):
        super().__init__(node_type=NODE_TYPE.DEVICE, *args, **kwargs)


class NodeGroupToRackController(CleanSave, Model):
    """Store some of the old NodeGroup data so we can migrate it when a rack
    controller is registered.
    """

    # The uuid of the nodegroup from < 2.0
    uuid = CharField(max_length=36, null=False, blank=False, editable=True)

    # The subnet that the nodegroup is connected to. There can be multiple
    # rows for multiple subnets on a signal nodegroup
    subnet = ForeignKey(
        "Subnet", null=False, blank=False, editable=True, on_delete=CASCADE
    )


def _clone_object(obj, **update_fields):
    """Save a new entry from the object by unsetting the primary key.

    Optionally, fields can be updated before saving the new object.
    """
    pk = obj._meta.pk
    setattr(obj, pk.attname, None)
    # inherited models have their pk pointing to the parent entry. In this case
    # we need to unset also PK fields from the parents
    while pk.related_model:
        pk = pk.related_model._meta.pk
        setattr(obj, pk.attname, None)
    obj.pk = None
    # unlink any related prefetched object
    obj._prefetched_objects_cache = {}
    for attr, value in update_fields.items():
        setattr(obj, attr, value)
    obj.save()
