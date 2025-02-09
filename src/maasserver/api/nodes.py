# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "AnonNodesHandler",
    "NodeHandler",
    "NodesHandler",
]

from itertools import chain

import bson
from django.db.models import Prefetch
from django.db.models.functions import Coalesce
from django.http import HttpResponse
from formencode.validators import Int, StringBool
from piston3.utils import rc

from maascommon.fields import MAC_FIELD_RE, normalise_macaddress
from maasserver.api.support import (
    admin_method,
    AnonymousOperationsHandler,
    deprecated,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import (
    get_mandatory_param,
    get_optional_list,
    get_optional_param,
)
from maasserver.enum import (
    BRIDGE_TYPE_CHOICES,
    BRIDGE_TYPE_CHOICES_DICT,
    NODE_STATUS,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
)
from maasserver.exceptions import (
    MAASAPIValidationError,
    NodeStateViolation,
    NoScriptsFound,
    StaticIPAddressExhaustion,
)
from maasserver.forms import BulkNodeSetZoneForm
from maasserver.forms.ephemeral import TestForm
from maasserver.models import Filesystem, Interface, Node, OwnerData
from maasserver.models.nodeprobeddetails import get_single_probed_details
from maasserver.models.scriptset import get_status_from_qs
from maasserver.node_constraint_filter_forms import ReadNodesForm
from maasserver.permissions import NodePermission
from maasserver.utils.forms import compose_invalid_choice_text
from maasserver.utils.orm import prefetch_queryset
from metadataserver.enum import (
    HARDWARE_TYPE,
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_STATUS_CHOICES,
)

NODES_SELECT_RELATED = (
    "bmc",
    "controllerinfo",
    "owner",
    "zone",
    "boot_disk__node_config__node",
    "domain",
    "pool",
    "current_config",
    "boot_interface__node_config__node",
    "virtualmachine",
)


def blockdev_prefetch(expression):
    for device in (
        expression,
        f"{expression}__physicalblockdevice",
        f"{expression}__virtualblockdevice",
    ):
        for filesystem_set in (
            "filesystem_set",
            "partitiontable_set__partitions__filesystem_set",
        ):
            yield Prefetch(
                f"{device}__{filesystem_set}",
                queryset=Filesystem.objects.select_related(
                    "cache_set",
                    "filesystem_group",
                ),
            )
        yield f"{device}__vmdisk__backing_pool"

    yield f"{expression}__physicalblockdevice__numa_node"


NODES_PREFETCH = [
    "domain__dnsresource_set__ip_addresses",
    "domain__dnsresource_set__dnsdata_set",
    "domain__globaldefault_set",
    "ownerdata_set",
    "gateway_link_ipv4__subnet",
    "gateway_link_ipv6__subnet",
    # storage prefetches
    *blockdev_prefetch("current_config__blockdevice_set"),
    *blockdev_prefetch(
        "current_config__blockdevice_set__partitiontable_set__partitions__"
        "partition_table__block_device__node_config__node__"
        "current_config__blockdevice_set"
    ),
    *blockdev_prefetch("boot_disk"),
    "current_config__filesystem_set",
    # interface prefetches
    "boot_interface__vlan__primary_rack",
    "boot_interface__vlan__secondary_rack",
    "boot_interface__vlan__fabric__vlan_set",
    "boot_interface__vlan__space",
    "boot_interface__ip_addresses__subnet",
    "boot_interface__parents",
    (
        "boot_interface__children_relationships__child__"
        "children_relationships__child"
    ),
    "current_config__interface_set__vlan__primary_rack",
    "current_config__interface_set__vlan__secondary_rack",
    "current_config__interface_set__vlan__fabric__vlan_set",
    "current_config__interface_set__vlan__space",
    "current_config__interface_set__parents",
    "current_config__interface_set__ip_addresses__subnet",
    "current_config__interface_set__numa_node",
    # Prefetch 3 levels deep, anything more will require extra queries.
    "current_config__interface_set__children_relationships__child__vlan",
    (
        "current_config__interface_set__children_relationships__child__"
        "children_relationships__child__vlan"
    ),
    (
        "current_config__interface_set__children_relationships__child__"
        "children_relationships__child__"
        "children_relationships__child__vlan"
    ),
    "tags",
    "nodemetadata_set",
    "numanode_set__hugepages_set",
]


def filtered_nodes_list_from_request(request, model=None):
    """List Nodes visible to the user, optionally filtered by criteria.

    Nodes are sorted by id (i.e. most recent last).

    :param hostname: An optional hostname. Only events relating to the node
        with the matching hostname will be returned. This can be specified
        multiple times to get events relating to more than one node.
    :param mac_address: An optional MAC address. Only events relating to the
        node owning the specified MAC address will be returned. This can be
        specified multiple times to get events relating to more than one node.
    :param id: An optional list of system ids.  Only events relating to the
        nodes with matching system ids will be returned.
    :param domain: An optional name for a dns domain. Only events relating to
        the nodes in the domain will be returned.
    :param zone: An optional name for a physical zone. Only events relating to
        the nodes in the zone will be returned.
    :param pool: An optional name for a resource pool. Only nodes belonging
        to the pool will be returned.
    :param agent_name: An optional agent name.  Only events relating to the
        nodes with matching agent names will be returned.
    """
    # Get filters from request.
    match_ids = get_optional_list(request.GET, "id")

    match_macs = get_optional_list(request.GET, "mac_address")
    if match_macs is not None:
        invalid_macs = [
            mac for mac in match_macs if not MAC_FIELD_RE.match(mac)
        ]
        if len(invalid_macs) != 0:
            raise MAASAPIValidationError(
                "Invalid MAC address(es): %s" % ", ".join(invalid_macs)
            )

    if model is None:
        model = Node
    # Fetch nodes and apply filters.
    nodes = model.objects.get_nodes(
        request.user, NodePermission.view, ids=match_ids
    )
    if match_macs is not None:
        nodes = nodes.filter(
            current_config__interface__mac_address__in=match_macs
        )
    match_hostnames = get_optional_list(request.GET, "hostname")
    if match_hostnames is not None:
        nodes = nodes.filter(hostname__in=match_hostnames)
    match_domains = get_optional_list(request.GET, "domain")
    if match_domains is not None:
        nodes = nodes.filter(domain__name__in=match_domains)
    match_zone_name = request.GET.get("zone", None)
    if match_zone_name is not None:
        nodes = nodes.filter(zone__name=match_zone_name)
    match_pool_name = request.GET.get("pool", None)
    if match_pool_name is not None:
        nodes = nodes.filter(pool__name=match_pool_name)
    match_agent_name = request.GET.get("agent_name", None)
    if match_agent_name is not None:
        nodes = nodes.filter(agent_name=match_agent_name)

    return nodes.order_by("id")


def is_registered(request, ignore_statuses=None):
    """Used by both `NodesHandler` and `AnonNodesHandler`."""
    if ignore_statuses is None:
        ignore_statuses = [NODE_STATUS.RETIRED]

    mac_address = normalise_macaddress(
        get_mandatory_param(request.GET, "mac_address")
    )

    interfaces = (
        Interface.objects.filter(mac_address=mac_address)
        .exclude(node_config__node__isnull=True)
        .exclude(node_config__node__status__in=ignore_statuses)
    )
    return interfaces.exists()


def get_cached_script_results(node):
    """Load script results into cache and return the cached list."""
    if not hasattr(node, "_cached_script_results"):
        node._cached_script_results = list(
            node.get_latest_script_results.only(
                "status", "script_set", "script", "suppressed"
            )
        )
        node._cached_commissioning_script_results = []
        node._cached_testing_script_results = []
        for script_result in node._cached_script_results:
            if (
                script_result.script_set.result_type
                == RESULT_TYPE.INSTALLATION
            ):
                # Don't include installation results in the health
                # status.
                continue
            elif script_result.status == SCRIPT_STATUS.ABORTED:
                # LP: #1724235 - Ignore aborted scripts.
                continue
            elif (
                script_result.script_set.result_type
                == RESULT_TYPE.COMMISSIONING
            ):
                node._cached_commissioning_script_results.append(script_result)
            elif script_result.script_set.result_type == RESULT_TYPE.TESTING:
                node._cached_testing_script_results.append(script_result)

    return node._cached_script_results


def get_script_status_name(script_status):
    for id, name in SCRIPT_STATUS_CHOICES:
        if id == script_status:
            return name
    return "Unknown"


class NodeHandler(OperationsHandler):
    """
    Manage an individual Node.

    The Node is identified by its system_id.
    """

    api_doc_section_name = "Node"

    # Disable create and update
    create = update = None
    model = Node

    # Override 'owner' so it emits the owner's name rather than a
    # full nested user object.
    @classmethod
    def owner(handler, node):
        if node.owner is None:
            return None
        return node.owner.username

    @classmethod
    def node_type_name(handler, node):
        return NODE_TYPE_CHOICES[node.node_type][1]

    @classmethod
    def current_commissioning_result_id(handler, node):
        return node.current_commissioning_script_set_id

    @classmethod
    def current_testing_result_id(handler, node):
        return node.current_testing_script_set_id

    @classmethod
    def current_installation_result_id(handler, node):
        return node.current_installation_script_set_id

    @classmethod
    def commissioning_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs(node._cached_commissioning_script_results)

    @classmethod
    def commissioning_status_name(handler, node):
        return get_script_status_name(handler.commissioning_status(node))

    @classmethod
    def testing_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs(node._cached_testing_script_results)

    @classmethod
    def testing_status_name(handler, node):
        return get_script_status_name(handler.testing_status(node))

    @classmethod
    def cpu_test_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs(
            [
                script_result
                for script_result in node._cached_testing_script_results
                if script_result.script.hardware_type == HARDWARE_TYPE.CPU
            ]
        )

    @classmethod
    def cpu_test_status_name(handler, node):
        return get_script_status_name(handler.cpu_test_status(node))

    @classmethod
    def memory_test_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs(
            [
                script_result
                for script_result in node._cached_testing_script_results
                if script_result.script.hardware_type == HARDWARE_TYPE.MEMORY
            ]
        )

    @classmethod
    def memory_test_status_name(handler, node):
        return get_script_status_name(handler.memory_test_status(node))

    @classmethod
    def network_test_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs(
            [
                script_result
                for script_result in node._cached_testing_script_results
                if script_result.script.hardware_type == HARDWARE_TYPE.NETWORK
            ]
        )

    @classmethod
    def network_test_status_name(handler, node):
        return get_script_status_name(handler.network_test_status(node))

    @classmethod
    def storage_test_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs(
            [
                script_result
                for script_result in node._cached_testing_script_results
                if script_result.script.hardware_type == HARDWARE_TYPE.STORAGE
            ]
        )

    @classmethod
    def storage_test_status_name(handler, node):
        return get_script_status_name(handler.storage_test_status(node))

    @classmethod
    def other_test_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs(
            [
                script_result
                for script_result in node._cached_testing_script_results
                if script_result.script.hardware_type == HARDWARE_TYPE.NODE
            ]
        )

    @classmethod
    def other_test_status_name(handler, node):
        return get_script_status_name(handler.other_test_status(node))

    @classmethod
    def interface_test_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs(
            [
                script_result
                for script_result in node._cached_testing_script_results
                if script_result.script.hardware_type == HARDWARE_TYPE.NETWORK
            ]
        )

    @classmethod
    def interface_test_status_name(handler, node):
        return get_script_status_name(handler.interface_test_status(node))

    @classmethod
    def interface_set(handler, node):
        return node.current_config.interface_set.all()

    @classmethod
    def hardware_info(handler, node):
        ret = {
            "system_vendor": "Unknown",
            "system_product": "Unknown",
            "system_family": "Unknown",
            "system_version": "Unknown",
            "system_sku": "Unknown",
            "system_serial": "Unknown",
            "cpu_model": "Unknown",
            "mainboard_vendor": "Unknown",
            "mainboard_product": "Unknown",
            "mainboard_serial": "Unknown",
            "mainboard_version": "Unknown",
            "mainboard_firmware_vendor": "Unknown",
            "mainboard_firmware_date": "Unknown",
            "mainboard_firmware_version": "Unknown",
            "chassis_vendor": "Unknown",
            "chassis_type": "Unknown",
            "chassis_serial": "Unknown",
            "chassis_version": "Unknown",
        }
        # Iterate over the NodeMetadata objects instead of filtering to
        # avoid another database call as the values have been prefetched.
        for nmd in node.nodemetadata_set.all():
            # The NodeMetdata model may contain values that shouldn't be
            # shown here. Only set the ones we expect.
            if nmd.key in ret:
                ret[nmd.key] = nmd.value
        return ret

    def read(self, request, system_id):
        """@description-title Read a node
        @description Reads a node with the given system_id.

        @param (string) "{system_id}" [required=true] A node's system_id.

        @success (http-status-code) "server-success" 200
        @success (json) "success-json" A JSON object containing
        information about the requested node.
        @success-example "success-json" [exkey=read-node] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node is not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.view
        )
        if self.model != Node:
            return node
        else:
            # Return the specific node type object so we get the correct
            # listing
            return node.as_self()

    def delete(self, request, system_id):
        """@description-title Delete a node
        @description Deletes a node with a given system_id.

        @param (string) "{system_id}" [required=true] A node's system_id.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node is not found.
        @error-example "not-found"
            No Node matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user is not authorized to delete the
        node.
        """
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        node.as_self().delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, node=None):
        #
        # This method is called by Piston in two different contexts:
        #
        # 1. When generating a URI template to be used in the documentation,
        #    in which case it is called with `node=None`. We return argument
        #    *names* instead of their values. Frustratingly, Piston itself
        #    discards these names and instead uses names derived from Django's
        #    URL patterns for the resource.
        #
        # 2. When populating the `resource_uri` field of an object returned by
        #    the API, in which case `node` is an instance of `Node`.
        #
        # There is a check made at handler class creation time to ensure that
        # the names from #1 match up to the handler's `fields`. In this way we
        # can declare which fields are required to render a resource's URI and
        # be sure that they are all present in a rendering of said resource.
        #
        # There is an additional unit test (see `TestResourceURIs`) to check
        # that the fields in each URI template match up to those fields
        # declared in a handler's `resource_uri` method.
        #
        node_system_id = "system_id"
        if node is not None:
            node_system_id = node.system_id
        return ("node_handler", (node_system_id,))

    @operation(idempotent=True)
    def details(self, request, system_id):
        """@description-title Get system details
        @description Returns system details -- for example, LLDP and
        ``lshw`` XML dumps.

        Returns a ``{detail_type: xml, ...}`` map, where
        ``detail_type`` is something like "lldp" or "lshw".

        Note that this is returned as BSON and not JSON. This is for
        efficiency, but mainly because JSON can't do binary content without
        applying additional encoding like base-64. The example output below is
        represented in ASCII using ``bsondump example.bson`` and is for
        demonstrative purposes.

        @param (string) "{system_id}" [required=true] The node's system_id.

        @success (http-status-code) "200" 200

        @success (json) "success-content" A BSON object represented here in
        ASCII using ``bsondump example.bson``.
        @success-example "success-content" [exkey=details] placeholder text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to see
        the node details.
        @error-example "no-perms"
            Forbidden

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node is not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        node = self.read(request, system_id)
        probe_details = get_single_probed_details(node)
        probe_details_report = {
            name: None if data is None else bson.Binary(data)
            for name, data in probe_details.items()
        }
        return HttpResponse(
            bson.BSON.encode(probe_details_report),
            # Not sure what media type to use here.
            content_type="application/bson",
        )

    @operation(idempotent=True)
    def power_parameters(self, request, system_id):
        """@description-title Get power parameters
        @description Gets power parameters for a given system_id, if any. For
        some types of power control this will include private information such
        as passwords and secret keys.

        Note that this method is reserved for admin users and returns a 403 if
        the user is not one.

        @success (http-status-code) "200" 200

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have permission to see
        the power parameters.
        @error-example "no-perms"
            This method is reserved for admin users.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node is not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        node = Node.objects.get_node_or_404(
            system_id, request.user, NodePermission.admin_read
        )
        return node.get_power_parameters()


class AnonNodeHandler(AnonymousOperationsHandler):
    """Anonymous access to Node."""

    read = create = update = delete = None
    model = Node

    resource_uri = NodeHandler.resource_uri


class AnonNodesHandler(AnonymousOperationsHandler):
    """Anonymous access to Nodes."""

    create = read = update = delete = None

    @operation(idempotent=True)
    def is_registered(self, request):
        """@description-title MAC address registered
        @description Returns whether or not the given MAC address is registered
        within this MAAS (and attached to a non-retired node).

        @param (url-string) "mac_address" [required=true] The MAC address to be
        checked.
        @param-example "mac_address"
            ``/nodes/?op=is_registered&mac_address=28:16:ad:a1:fa:63``

        @success (http-status-code) "200" 200
        @success (boolean) "success_example" 'true' or 'false'
        @success-example "success_example"
            false

        @error (http-status-code) "400" 400
        @error (content) "no-address" mac_address was missing
        @error-example "no-address"
            No provided mac_address!
        """
        # If a node is added with missing/incorrect arch/boot MAC it will
        # enter enlistment instead of commissioning. Enlistment should be
        # allowed to run. Once its done maas-run-remote-scripts will run
        # which will execute all user selected commissioning and testing
        # scripts.
        return is_registered(
            request,
            [NODE_STATUS.NEW, NODE_STATUS.COMMISSIONING, NODE_STATUS.RETIRED],
        )

    @operation(idempotent=True)
    def is_action_in_progress(self, request):
        """@description-title MAC address of deploying or commissioning node
        @description Returns whether or not the given MAC address is a machine
        that's either 'deploying' or 'commissioning'.

        @param (url-string) "mac_address" [required=true] The MAC address to be
        checked.
        @param-example "mac_address"
            ``/nodes/?op=is_action_in_progress&mac_address=28:16:ad:a1:fa:63``

        @success (http-status-code) "200" 200
        @success (boolean) "success_example" 'true' or 'false'
        @success "success_example"
            false

        @error (http-status-code) "400" 400
        @error (content) "no-address" mac_address was missing
        @error-example "no-address"
            No provided mac_address!
        """
        mac_address = get_mandatory_param(request.GET, "mac_address")
        interfaces = Interface.objects.filter(mac_address=mac_address)
        interfaces = interfaces.filter(
            node_config__node__status__in=[
                NODE_STATUS.COMMISSIONING,
                NODE_STATUS.DEPLOYING,
            ]
        )
        return interfaces.exists()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("nodes_handler", [])


class NodesHandler(OperationsHandler):
    """Manage the collection of all the nodes in the MAAS."""

    api_doc_section_name = "Nodes"
    create = update = delete = None
    anonymous = AnonNodesHandler
    base_model = Node

    def read(self, request):
        """@description-title List Nodes visible to the user
        @description List nodes visible to current user, optionally filtered by
        criteria.

        Nodes are sorted by id (i.e. most recent last) and grouped by type.

        @param (string) "hostname" [required=false] Only nodes relating to the
        node with the matching hostname will be returned. This can be specified
        multiple times to see multiple nodes.

        @param (int) "cpu_count" [required=false] Only nodes with the specified
        minimum number of CPUs will be included.

        @param (string) "mem" [required=false] Only nodes with the specified
        minimum amount of RAM (in MiB) will be included.

        @param (string) "mac_address" [required=false] Only nodes relating to
        the node owning the specified MAC address will be returned. This can be
        specified multiple times to see multiple nodes.

        @param (string) "id" [required=false] Only nodes relating to the nodes
        with matching system ids will be returned.

        @param (string) "domain" [required=false] Only nodes relating to the
        nodes in the domain will be returned.

        @param (string) "zone" [required=false] Only nodes relating to the
        nodes in the zone will be returned.

        @param (string) "pool" [required=false] Only nodes belonging to the
        pool will be returned.

        @param (string) "agent_name" [required=false] Only nodes relating to
        the nodes with matching agent names will be returned.

        @param (string) "fabrics" [required=false] Only nodes with interfaces
        in specified fabrics will be returned.

        @param (string) "not_fabrics" [required=false] Only nodes with
        interfaces not in specified fabrics will be returned.

        @param (string) "vlans" [required=false] Only nodes with interfaces in
        specified VLANs will be returned.

        @param (string) "not_vlans" [required=false] Only nodes with interfaces
        not in specified VLANs will be returned.

        @param (string) "subnets" [required=false] Only nodes with interfaces
        in specified subnets will be returned.

        @param (string) "not_subnets" [required=false] Only nodes with
        interfaces not in specified subnets will be returned.

        @param (string) "link_speed" [required=false] Only nodes with
        interfaces with link speeds greater than or equal to link_speed will
        be returned.

        @param (string) "status" [required=false] Only nodes with specified
        status will be returned.

        @param (string) "pod": [required=false] Only nodes that belong to a
        specified pod will be returned.

        @param (string) "not_pod": [required=false] Only nodes that don't
        belong to a specified pod will be returned.

        @param (string) "pod_type": [required=false] Only nodes that belong to
        a pod of the specified type will be returned.

        @param (string) "not_pod_type": [required=false] Only nodes that don't
        belong a pod of the specified type will be returned.

        @param (string) "devices": [required=false] Only return nodes which
        have one or more devices containing the following constraints in the
        format key=value[,key2=value2[,...]]

        Each key can be one of the following:

        - ``vendor_id``: The device vendor id
        - ``product_id``: The device product id
        - ``vendor_name``: The device vendor name, not case sensative
        - ``product_name``: The device product name, not case sensative
        - ``commissioning_driver``: The device uses this driver during
          commissioning.

        @success (http-status-code) "200" 200

        @success (json) "success_json" A JSON object containing a list of node
        objects.
        @success-example "success_json" [exkey=read-visible-nodes] placeholder
        text

        """

        if self.base_model == Node:
            # Avoid circular dependencies
            from maasserver.api.devices import DevicesHandler
            from maasserver.api.machines import MachinesHandler
            from maasserver.api.rackcontrollers import RackControllersHandler
            from maasserver.api.regioncontrollers import (
                RegionControllersHandler,
            )

            racks = RackControllersHandler().read(request).order_by("id")
            nodes = list(
                chain(
                    DevicesHandler().read(request).order_by("id"),
                    MachinesHandler().read(request).order_by("id"),
                    racks,
                    RegionControllersHandler()
                    .read(request)
                    .exclude(id__in=racks)
                    .order_by("id"),
                )
            )
            return nodes
        else:
            form = ReadNodesForm(data=request.GET)
            if not form.is_valid():
                raise MAASAPIValidationError(form.errors)
            nodes = self.base_model.objects.get_nodes(
                request.user, NodePermission.view
            )
            nodes, _, _ = form.filter_nodes(nodes)
            nodes = nodes.select_related(*NODES_SELECT_RELATED)
            nodes = prefetch_queryset(nodes, NODES_PREFETCH).order_by("id")
            nodes = nodes.annotate(
                virtualmachine_id=Coalesce("virtualmachine__id", None)
            )
            return nodes

    @operation(idempotent=True)
    def is_registered(self, request):
        """@description-title MAC address registered
        @description Returns whether or not the given MAC address is registered
        within this MAAS (and attached to a non-retired node).

        @param (url-string) "mac_address" [required=true] The MAC address to be
        checked.
        @param-example "mac_address"
            ``/nodes/?op=is_registered&mac_address=28:16:ad:a1:fa:63``

        @success (http-status-code) "200" 200

        @success (boolean) "success_example" 'true' or 'false'
        @success-example "success_example"
            false

        @error (http-status-code) "400" 400
        @error (content) "no-address" mac_address was missing
        @error-example "no-address"
            No provided mac_address!
        """
        return is_registered(request)

    @operation(idempotent=False)
    def set_zone(self, request):
        """@description-title Assign nodes to a zone
        @description Assigns a given node to a given zone.

        @param (string) "zone" [required=true] The zone name.
        @param (string) "nodes" [required=true] The node to add.

        @success (http-status-code) "204" 204

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have set the zone.
        @error-example "no-perms"
            This method is reserved for admin users.

        @error (http-status-code) "400" 400
        @error (content) "bad-param" The given parameters were not correct.
        """
        data = {
            "zone": request.data.get("zone"),
            "system_id": get_optional_list(request.data, "nodes"),
        }
        form = BulkNodeSetZoneForm(request.user, data=data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        form.save()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ("nodes_handler", [])


class WorkloadAnnotationsMixin:
    """Mixin that adds methods for workload annotations to the handler."""

    @classmethod
    def workload_annotations(cls, machine):
        """Workload annotations placed on the machine."""
        return OwnerData.objects.get_owner_data(machine)

    @classmethod
    def owner_data(cls, machine):
        """Deprecated, use workload_annotations instead."""
        return cls.workload_annotations(machine)

    @operation(idempotent=False)
    def set_workload_annotations(self, request, system_id):
        """@description-title Set key=value data
        @description Set key=value data for the current owner.

        Pass any key=value form data to this method to add, modify, or remove.
        A key is removed when the value for that key is set to an empty string.

        This operation will not remove any previous keys unless explicitly
        passed with an empty string. All workload annotations are removed when
        the machine is no longer allocated to a user.

        @param (string) "key" [required=true] ``key`` can be any string value.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node is not found.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user does not have set the zone.

        """
        node = self.model.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NodePermission.edit
        )
        if node.owner_id != request.user.id:
            raise NodeStateViolation(
                "Cannot set workload annotation: it hasn't been acquired."
            )
        owner_data = {
            key: None if value == "" else value
            for key, value in request.POST.items()
            if key != "op"
        }
        OwnerData.objects.set_owner_data(node, owner_data)
        return node

    @operation(idempotent=False)
    @deprecated(use=set_workload_annotations)
    def set_owner_data(self, request, system_id):
        """@description-title Deprecated, use set-workload-annotations.
        @description Deprecated, use set-workload-annotations instead."""
        return self.set_workload_annotations(request, system_id)


class PowerMixin:
    """Mixin which adds power commands to a node type."""

    @operation(idempotent=True)
    def query_power_state(self, request, system_id):
        """@description-title Get the power state of a node
        @description Gets the power state of a given node. MAAS sends a request
        to the node's power controller, which asks it about the node's state.
        The reply to this could be delayed by up to 30 seconds while waiting
        for the power controller to respond.  Use this method sparingly as it
        ties up an appserver thread while waiting.

        @param (string) "system_id" [required=true] The node to query.

        @success (http-status-code) "200" 200
        @success (json) "success_json" A JSON object containing the node's
        power state.
        @success-example "success_json" [exkey=query-power-state] placeholder
        text.

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node is not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.view
        )
        return {"state": node.power_query().wait(60)}

    @operation(idempotent=False)
    def power_on(self, request, system_id):
        """@description-title Turn on a node
        @description Turn on the given node with optional user-data and
        comment.

        @param (string) "user_data" [required=false] Base64-encoded blob of
        data to be made available to the nodes through the metadata service.

        @param (string) "comment" [required=false] Comment for the event log.

        @success (http-status-code) "204" 204
        @success (json) "success_json" A JSON object containing the node's
        information.
        @success-example "success_json" [exkey=power-on] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node is not found.
        @error-example "not-found"
            No Node matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user is not authorized to power on the
        node.

        @error (http-status-code) "503" 503
        @error (content) "no-ips" Returns 503 if the start-up attempted to
        allocate an IP address, and there were no IP addresses available on the
        relevant cluster interface.
        """
        user_data = request.POST.get("user_data", None)
        comment = get_optional_param(request.POST, "comment")

        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.edit
        )
        if node.owner is None and node.node_type != NODE_TYPE.RACK_CONTROLLER:
            raise NodeStateViolation(
                "Can't start node: it hasn't been allocated."
            )
        if isinstance(user_data, str):
            user_data = user_data.encode()
        try:
            # These parameters are passed in the request from
            # maasserver.api.machines.deploy when powering on
            # the node for deployment.
            install_kvm = get_optional_param(
                request.POST,
                "install_kvm",
                default=False,
                validator=StringBool,
            )
            register_vmhost = get_optional_param(
                request.POST,
                "register_vmhost",
                default=False,
                validator=StringBool,
            )
            bridge_type = get_optional_param(
                request.POST, "bridge_type", default=None
            )
            if (
                bridge_type is not None
                and bridge_type not in BRIDGE_TYPE_CHOICES_DICT
            ):
                raise MAASAPIValidationError(
                    {
                        "bridge_type": compose_invalid_choice_text(
                            "bridge_type", BRIDGE_TYPE_CHOICES
                        )
                    }
                )
            bridge_stp = get_optional_param(
                request.POST, "bridge_stp", default=None, validator=StringBool
            )
            bridge_fd = get_optional_param(
                request.POST, "bridge_fd", default=None, validator=Int
            )
            node.start(
                request.user,
                user_data=user_data,
                comment=comment,
                install_kvm=install_kvm,
                register_vmhost=register_vmhost,
                bridge_type=bridge_type,
                bridge_stp=bridge_stp,
                bridge_fd=bridge_fd,
            )
        except StaticIPAddressExhaustion:
            # The API response should contain error text with the
            # system_id in it, as that is the primary API key to a node.
            raise StaticIPAddressExhaustion(  # noqa: B904
                "%s: Unable to allocate static IP due to address"
                " exhaustion." % system_id
            )
        return node

    @operation(idempotent=False)
    def power_off(self, request, system_id):
        """@description-title Power off a node
        @description Powers off a given node.

        @param (string) "stop_mode" [required=false] Power-off mode. If 'soft',
        perform a soft power down if the node's power type supports it,
        otherwise perform a hard power off. For all values other than 'soft',
        and by default, perform a hard power off. A soft power off generally
        asks the OS to shutdown the system gracefully before powering off,
        while a hard power off occurs immediately without any warning to the
        OS.

        @param (string) "comment" [required=false] Comment for the event log.

        @success (http-status-code) "204" 204
        @success (json) "success_json" A JSON object containing the node's
        information.
        @success-example "success_json" [exkey=power-off] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node is not found.
        @error-example "not-found"
            No Node matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user is not authorized to power off the
        node.
        """
        stop_mode = request.POST.get("stop_mode", "hard")
        comment = get_optional_param(request.POST, "comment")
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.edit
        )
        power_action_sent = node.stop(
            request.user, stop_mode=stop_mode, comment=comment
        )
        if power_action_sent:
            return node
        else:
            return None

    @operation(idempotent=False)
    def test(self, request, system_id):
        """@description-title Begin testing process for a node
        @description Begins the testing process for a given node.

        A node in the 'ready', 'allocated', 'deployed', 'broken', or any failed
        state may run tests. If testing is started and successfully passes from
        'broken' or any failed state besides 'failed commissioning' the node
        will be returned to a ready state. Otherwise the node will return to
        the state it was when testing started.

        @param (int) "enable_ssh" [required=false] Whether to enable SSH for
        the testing environment using the user's SSH key(s). 0 == false. 1 ==
        true.

        @param (string) "testing_scripts" [required=false] A comma-separated
        list of testing script names and tags to be run. By default all tests
        tagged 'commissioning' will be run.

        @param (string) "parameters" [required=false] Scripts selected to run
        may define their own parameters. These parameters may be passed using
        the parameter name. Optionally a parameter may have the script name
        prepended to have that parameter only apply to that specific script.

        @success (http-status-code) "204" 204
        @success (json) "success_json" A JSON object containing the node's
        information.
        @success-example "success_json" [exkey=test] placeholder text

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node is not found.
        @error-example "not-found"
            No Node matches the given query.
        """
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.admin
        )
        form = TestForm(instance=node, user=request.user, data=request.data)
        if form.is_valid():
            try:
                return form.save()
            except NoScriptsFound:
                raise MAASAPIValidationError("No testing scripts found!")  # noqa: B904
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def override_failed_testing(self, request, system_id):
        """@description-title Ignore failed tests
        @description Ignore failed tests and put node back into a usable state.

        @param (string) "comment" [required=false] Comment for the event log.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node is not found.
        @error-example "not-found"
            No Node matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user is not authorized to override
        tests.
        """
        comment = get_optional_param(request.POST, "comment")
        node = self.model.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NodePermission.admin
        )
        node.override_failed_testing(request.user, comment)
        return node

    @operation(idempotent=False)
    def abort(self, request, system_id):
        """@description-title Abort a node operation
        @description Abort a node's current operation.

        @param (string) "comment" [required=false] Comment for the event log.

        @success (http-status-code) "204" 204

        @error (http-status-code) "404" 404
        @error (content) "not-found" The requested node is not found.
        @error-example "not-found"
            No Node matches the given query.

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user is not authorized to abort the
        current operation.
        """
        comment = get_optional_param(request.POST, "comment")
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NodePermission.edit
        )
        node.abort_operation(request.user, comment)
        return node


class PowersMixin:
    """Mixin which adds power commands to a nodes type."""

    @admin_method
    @operation(idempotent=True)
    def power_parameters(self, request):
        """@description-title Get power parameters
        @description Get power parameters for multiple machines. To request
        power parameters for a specific machine or more than one machine:
        ``op=power_parameters&id=abc123&id=def456``.

        @param (url-string) "id" [required=true] A system ID. To request more
        than one machine, provide multiple ``id`` arguments in the request.
        Only machines with matching system ids will be returned.
        @param-example "id"
            op=power_parameters&id=abc123&id=def456

        @success (http-status-code) "200" 200
        @success (json) "success_json" A JSON object containing a list of
        power parameters with system_ids as keys.
        @success-example "success_json" [exkey=get-power-params] placeholder
        text

        @error (http-status-code) "403" 403
        @error (content) "no-perms" The user is not authorized to view the
        power parameters.
        """
        match_ids = get_optional_list(request.GET, "id")

        if match_ids is None:
            machines = self.base_model.objects.all()
        else:
            machines = self.base_model.objects.filter(system_id__in=match_ids)

        return {
            machine.system_id: machine.get_power_parameters()
            for machine in machines
        }
