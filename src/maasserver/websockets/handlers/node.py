# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The node handler for the WebSocket connection."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    "NodeHandler",
]

import logging
from operator import itemgetter

from lxml import etree
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_PERMISSION,
)
from maasserver.exceptions import NodeActionError
from maasserver.forms import AdminNodeWithMACAddressesForm
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.config import Config
from maasserver.models.event import Event
from maasserver.models.node import Node
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.nodeprobeddetails import get_single_probed_details
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.tag import Tag
from maasserver.node_action import compile_node_actions
from maasserver.rpc import getClientFor
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils.converters import XMLToYAML
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets.base import (
    HandlerDoesNotExistError,
    HandlerError,
    HandlerPermissionError,
)
from maasserver.websockets.handlers.event import dehydrate_event_type_level
from maasserver.websockets.handlers.timestampedmodel import (
    dehydrate_datetime,
    TimestampedModelHandler,
)
from metadataserver.enum import RESULT_TYPE
from metadataserver.models import NodeResult
from provisioningserver.drivers.power import POWER_QUERY_TIMEOUT
from provisioningserver.logger import get_maas_logger
from provisioningserver.power.poweraction import (
    PowerActionFail,
    UnknownPowerType,
)
from provisioningserver.rpc.cluster import PowerQuery
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.tags import merge_details_cleanly
from provisioningserver.utils.twisted import (
    asynchronous,
    deferWithTimeout,
)
from twisted.internet.defer import (
    CancelledError,
    inlineCallbacks,
    returnValue,
)


maaslog = get_maas_logger("websockets.node")


class NodeHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Node.nodes.filter(installable=True)
                .select_related('nodegroup', 'pxe_mac', 'owner')
                .prefetch_related('interface_set__ip_addresses__subnet__vlan')
                .prefetch_related('nodegroup__nodegroupinterface_set__subnet')
                .prefetch_related('zone')
                .prefetch_related('tags')
                .prefetch_related('blockdevice_set__physicalblockdevice')
                .prefetch_related('blockdevice_set__virtualblockdevice'))
        pk = 'system_id'
        pk_type = unicode
        allowed_methods = [
            'list',
            'get',
            'create',
            'update',
            'action',
            'set_active',
            'check_power',
        ]
        form = AdminNodeWithMACAddressesForm
        exclude = [
            "installable",
            "parent",
            "boot_interface",
            "boot_cluster_ip",
            "token",
            "netboot",
            "agent_name",
            "power_state_updated",
            "gateway_link_ipv4",
            "gateway_link_ipv6",
            "block_poweroff",
            "enable_ssh",
            "skip_networking",
            "skip_storage",
        ]
        list_fields = [
            "system_id",
            "hostname",
            "owner",
            "cpu_count",
            "memory",
            "power_state",
            "zone",
        ]
        listen_channels = [
            "node",
        ]

    def get_queryset(self):
        """Return `QuerySet` for nodes only vewable by `user`."""
        nodes = super(NodeHandler, self).get_queryset()
        return Node.nodes.get_nodes(
            self.user, NODE_PERMISSION.VIEW, from_nodes=nodes)

    def dehydrate_owner(self, user):
        """Return owners username."""
        if user is None:
            return ""
        else:
            return user.username

    def dehydrate_zone(self, zone):
        """Return zone name."""
        return {
            "id": zone.id,
            "name": zone.name,
        }

    def dehydrate_nodegroup(self, nodegroup):
        """Return the nodegroup name."""
        if nodegroup is None:
            return None
        else:
            return {
                "id": nodegroup.id,
                "uuid": nodegroup.uuid,
                "name": nodegroup.name,
                "cluster_name": nodegroup.cluster_name,
            }

    def dehydrate_routers(self, routers):
        """Return list of routers."""
        if routers is None:
            return []
        return [
            "%s" % router
            for router in routers
        ]

    def dehydrate_power_parameters(self, power_parameters):
        """Return power_parameters None if empty."""
        if power_parameters == '':
            return None
        else:
            return power_parameters

    def dehydrate(self, obj, data, for_list=False):
        """Add extra fields to `data`."""
        data["fqdn"] = obj.fqdn
        data["status"] = obj.display_status()
        data["actions"] = compile_node_actions(obj, self.user).keys()
        data["memory"] = obj.display_memory()

        data["extra_macs"] = [
            "%s" % mac_address
            for mac_address in obj.get_extra_macs()
        ]
        boot_interface = obj.get_boot_interface()
        if boot_interface is not None:
            data["pxe_mac"] = "%s" % boot_interface.mac_address
            data["pxe_mac_vendor"] = obj.get_pxe_mac_vendor()
        else:
            data["pxe_mac"] = data["pxe_mac_vendor"] = ""

        blockdevices = self.get_blockdevices_for(obj)
        physical_blockdevices = [
            blockdevice for blockdevice in blockdevices
            if isinstance(blockdevice, PhysicalBlockDevice)
            ]
        data["physical_disk_count"] = len(physical_blockdevices)
        data["storage"] = "%3.1f" % (
            sum([
                blockdevice.size
                for blockdevice in physical_blockdevices
                ]) / (1000 ** 3))
        data["storage_tags"] = self.get_all_storage_tags(blockdevices)

        data["tags"] = [
            tag.name
            for tag in obj.tags.all()
        ]
        if not for_list:
            data["osystem"] = obj.get_osystem()
            data["distro_series"] = obj.get_distro_series()
            data["hwe_kernel"] = obj.hwe_kernel

            # Network
            interfaces = [
                self.dehydrate_interface(interface, obj)
                for interface in obj.interface_set.all().order_by('id')
            ]
            data["interfaces"] = sorted(
                interfaces, key=itemgetter("is_pxe"), reverse=True)

            # Devices
            devices = [
                self.dehydrate_device(device)
                for device in obj.children.all()
            ]
            data["devices"] = sorted(
                devices, key=itemgetter("fqdn"))

            # Storage
            data["disks"] = [
                self.dehydrate_blockdevice(blockdevice)
                for blockdevice in blockdevices
            ]

            # Events
            data["events"] = self.dehydrate_events(obj)

            # Machine output
            data = self.dehydrate_summary_output(obj, data)
            data["commissioning_results"] = self.dehydrate_node_results(
                obj, RESULT_TYPE.COMMISSIONING)
            data["installation_results"] = self.dehydrate_node_results(
                obj, RESULT_TYPE.INSTALLATION)

            # Third party drivers
            if Config.objects.get_config('enable_third_party_drivers'):
                driver = get_third_party_driver(obj)
                if "module" in driver and "comment" in driver:
                    data["third_party_driver"] = {
                        "module": driver["module"],
                        "comment": driver["comment"],
                    }

        return data

    def dehydrate_device(self, device):
        """Return the `Device` formatted for JSON encoding."""
        return {
            "fqdn": device.fqdn,
            "interfaces": [
                self.dehydrate_interface(interface, device)
                for interface in device.interface_set.all().order_by('id')
            ],
        }

    def dehydrate_blockdevice(self, blockdevice):
        """Return `BlockDevice` formatted for JSON encoding."""
        # model and serial are currently only avalible on physical block
        # devices
        if isinstance(blockdevice, PhysicalBlockDevice):
            model = blockdevice.model
            serial = blockdevice.serial
        else:
            serial = model = ""
        partition_table = blockdevice.get_partitiontable()
        if partition_table is not None:
            partition_table_type = partition_table.table_type
        else:
            partition_table_type = ""
        return {
            "id": blockdevice.id,
            "name": blockdevice.name,
            "tags": blockdevice.tags,
            "type": blockdevice.type,
            "path": blockdevice.path,
            "size": blockdevice.size,
            "size_gb": "%3.1f" % (blockdevice.size / (1000 ** 3)),
            "block_size": blockdevice.block_size,
            "model": model,
            "serial": serial,
            "partition_table_type": partition_table_type,
            "filesystem": self.dehydrate_filesystem(
                blockdevice.filesystem),
            "partitions": self.dehydrate_partitions(
                blockdevice.get_partitiontable()),
        }

    def dehydrate_partitions(self, partition_table):
        """Return `PartitionTable` formatted for JSON encoding."""
        if partition_table is None:
            return None
        return [
            {
                "filesystem": self.dehydrate_filesystem(
                    partition.filesystem),
                "path": partition.path,
                "type": partition.type,
                "id": partition.id,
                "size": partition.size,
                "size_gb": "%3.1f" % (partition.size / (1000 ** 3)),
            }
            for partition in partition_table.partitions.all()
        ]

    def dehydrate_filesystem(self, filesystem):
        """Return `Filesystem` formatted for JSON encoding."""
        if filesystem is None:
            return None
        return {
            "label": filesystem.label,
            "mount_point": filesystem.mount_point,
            "fstype": filesystem.fstype,
            }

    def dehydrate_interface(self, interface, obj):
        """Dehydrate a `interface` into a interface definition."""
        # Statically assigned ip addresses.
        ip_addresses = []
        subnets = set()
        for ip_address in interface.ip_addresses.all():
            if ip_address.subnet is not None:
                subnets.add(ip_address.subnet)
            if ip_address.ip:
                if ip_address.alloc_type != IPADDRESS_TYPE.DISCOVERED:
                    ip_addresses.append({
                        "type": "static",
                        "alloc_type": ip_address.alloc_type,
                        "ip_address": "%s" % ip_address.ip,
                    })
                else:
                    ip_addresses.append({
                        "type": "dynamic",
                        "ip_address": "%s" % ip_address.ip,
                    })

        # Connected networks.
        networks = [
            {
                "id": subnet.id,
                "name": subnet.name,
                "cidr": "%s" % subnet.get_ipnetwork(),
                "vlan": subnet.vlan.vid,
            }
            for subnet in subnets
        ]
        return {
            "id": interface.id,
            "is_pxe": interface == obj.boot_interface,
            "mac_address": "%s" % interface.mac_address,
            "ip_addresses": ip_addresses,
            "networks": networks,
        }

    def dehydrate_summary_output(self, obj, data):
        """Dehydrate the machine summary output."""
        # Produce a "clean" composite details document.
        probed_details = merge_details_cleanly(
            get_single_probed_details(obj.system_id))

        # We check here if there's something to show instead of after
        # the call to get_single_probed_details() because here the
        # details will be guaranteed well-formed.
        if len(probed_details.xpath('/*/*')) == 0:
            data['summary_xml'] = None
            data['summary_yaml'] = None
        else:
            data['summary_xml'] = etree.tostring(
                probed_details, encoding=unicode, pretty_print=True)
            data['summary_yaml'] = XMLToYAML(
                etree.tostring(
                    probed_details, encoding=unicode,
                    pretty_print=True)).convert()
        return data

    def dehydrate_node_results(self, obj, result_type):
        """Dehydrate node results with the given `result_type`."""
        return [
            {
                "id": result.id,
                "result": result.script_result,
                "name": result.name,
                "data": result.data,
                "line_count": len(result.data.splitlines()),
                "created": dehydrate_datetime(result.created),
            }
            for result in NodeResult.objects.filter(
                node=obj, result_type=result_type)
        ]

    def dehydrate_events(self, obj):
        """Dehydrate the node events.

        The latests 50 not including DEBUG events will be dehydrated. The
        `EventsHandler` needs to be used if more are required.
        """
        events = (
            Event.objects.filter(node=obj)
            .exclude(type__level=logging.DEBUG)
            .select_related("type")
            .order_by('-id')[:50])
        return [
            {
                "id": event.id,
                "type": {
                    "id": event.type.id,
                    "name": event.type.name,
                    "description": event.type.description,
                    "level": dehydrate_event_type_level(event.type.level),
                },
                "description": event.description,
                "created": dehydrate_datetime(event.created),
            }
            for event in events
        ]

    def get_all_storage_tags(self, blockdevices):
        """Return list of all storage tags in `blockdevices`."""
        tags = set()
        for blockdevice in blockdevices:
            tags = tags.union(blockdevice.tags)
        return list(tags)

    def get_blockdevices_for(self, obj):
        """Return only `BlockDevice`s using the prefetched query."""
        return [
            blockdevice.actual_instance
            for blockdevice in obj.blockdevice_set.all()
        ]

    def get_object(self, params):
        """Get object by using the `pk` in `params`."""
        obj = super(NodeHandler, self).get_object(params)
        if self.user.is_superuser:
            return obj
        if obj.owner is None or obj.owner == self.user:
            return obj
        raise HandlerDoesNotExistError(params[self._meta.pk])

    def get_mac_addresses(self, data):
        """Convert the given `data` into a list of mac addresses.

        This is used by the create method and the hydrate method. The `pxe_mac`
        will always be the first entry in the list.
        """
        macs = data.get("extra_macs", [])
        if "pxe_mac" in data:
            macs.insert(0, data["pxe_mac"])
        return macs

    def get_form_class(self, action):
        """Return the form class used for `action`."""
        if action in ("create", "update"):
            return AdminNodeWithMACAddressesForm
        else:
            raise HandlerError("Unknown action: %s" % action)

    def preprocess_form(self, action, params):
        """Process the `params` to before passing the data to the form."""
        new_params = {}

        # Only copy the allowed fields into `new_params` to be passed into
        # the form.
        new_params["mac_addresses"] = self.get_mac_addresses(params)
        new_params["hostname"] = params.get("hostname")
        new_params["architecture"] = params.get("architecture")
        new_params["power_type"] = params.get("power_type")
        if "zone" in params:
            new_params["zone"] = params["zone"]["name"]
        if "nodegroup" in params:
            new_params["nodegroup"] = params["nodegroup"]["uuid"]
        if "min_hwe_kernel" in params:
            new_params["min_hwe_kernel"] = params["min_hwe_kernel"]

        # Cleanup any fields that have a None value.
        new_params = {
            key: value
            for key, value in new_params.viewitems()
            if value is not None
        }

        return super(NodeHandler, self).preprocess_form(action, new_params)

    def create(self, params):
        """Create the object from params."""
        # Only admin users can perform create.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        # Create the object, then save the power parameters because the
        # form will not save this information.
        data = super(NodeHandler, self).create(params)
        node_obj = Node.objects.get(system_id=data['system_id'])
        node_obj.power_parameters = params.get("power_parameters", {})
        node_obj.save()

        # Start the commissioning process right away, which has the
        # desired side effect of initializing the node's power state.
        node_obj.start_commissioning(self.user)

        return self.full_dehydrate(node_obj)

    def update(self, params):
        """Update the object from params."""
        # Only admin users can perform update.
        if not self.user.is_superuser:
            raise HandlerPermissionError()

        # Update the node with the form. The form will not update the
        # nodegroup or power_parameters, so we perform that logic here.
        data = super(NodeHandler, self).update(params)
        node_obj = Node.objects.get(system_id=data['system_id'])
        node_obj.nodegroup = NodeGroup.objects.get(
            uuid=params['nodegroup']['uuid'])
        node_obj.power_parameters = params.get("power_parameters")
        if node_obj.power_parameters is None:
            node_obj.power_parameters = {}

        # Update the tags for the node and disks.
        self.update_tags(node_obj, params['tags'])
        self.update_disk_tags(params['disks'])
        node_obj.save()
        return self.full_dehydrate(node_obj)

    def update_tags(self, node_obj, tags):
        # Loop through the nodes current tags. If the tag exists in `tags` then
        # nothing needs to be done so its removed from `tags`. If it does not
        # exists then the tag was removed from the node and should be removed
        # from the nodes set of tags.
        for tag in node_obj.tags.all():
            if tag.name not in tags:
                node_obj.tags.remove(tag)
            else:
                tags.remove(tag.name)

        # All the tags remaining in `tags` are tags that are not linked to
        # node. Get or create that tag and add the node to the tags set.
        for tag_name in tags:
            tag_obj, _ = Tag.objects.get_or_create(name=tag_name)
            if tag_obj.is_defined:
                raise HandlerError(
                    "Cannot add tag %s to node because it has a "
                    "definition." % tag_name)
            tag_obj.node_set.add(node_obj)
            tag_obj.save()

    def update_disk_tags(self, disks):
        # Loop through each disk and update the tags array list.
        for disk in disks:
            disk_obj = BlockDevice.objects.get(id=disk["id"])
            disk_obj.tags = disk["tags"]
            disk_obj.save(update_fields=['tags'])

    def action(self, params):
        """Perform the action on the object."""
        obj = self.get_object(params)
        action_name = params.get("action")
        actions = compile_node_actions(obj, self.user)
        action = actions.get(action_name)
        if action is None:
            raise NodeActionError(
                "%s action is not available for this node." % action_name)
        extra_params = params.get("extra", {})
        return action.execute(**extra_params)

    @asynchronous
    @inlineCallbacks
    def check_power(self, params):
        """Check the power state of the node."""

        # XXX: This is largely the same function as
        # update_power_state_of_node.

        @transactional
        def get_node_cluster_and_power_info():
            obj = self.get_object(params)
            if obj.installable:
                node_info = obj.system_id, obj.hostname
                nodegroup_info = obj.nodegroup.cluster_name, obj.nodegroup.uuid
                try:
                    power_info = obj.get_effective_power_info()
                except UnknownPowerType:
                    return node_info, nodegroup_info, None
                else:
                    return node_info, nodegroup_info, power_info
            else:
                raise HandlerError(
                    "%s: Unable to query power state; not an "
                    "installable node" % obj.hostname)

        @transactional
        def update_power_state(state):
            obj = self.get_object(params)
            obj.update_power_state(state)

        # Grab info about the node, its cluster, and its power parameters from
        # the database. If it can't be queried we can return early, but first
        # update the node's power state with what we know we don't know.
        node_info, cluster_info, power_info = (
            yield deferToDatabase(get_node_cluster_and_power_info))
        if power_info is None or not power_info.can_be_queried:
            yield deferToDatabase(update_power_state, "unknown")
            returnValue("unknown")

        # Get a client to talk to the node's cluster. If we're not connected
        # we can return early, albeit with an exception.
        cluster_name, cluster_uuid = cluster_info
        try:
            client = yield getClientFor(cluster_uuid)
        except NoConnectionsAvailable:
            maaslog.error(
                "Unable to get RPC connection for cluster '%s' (%s)",
                cluster_name, cluster_uuid)
            raise HandlerError("Unable to connect to cluster controller")

        # Query the power state via the node's cluster.
        node_id, node_hostname = node_info
        try:
            response = yield deferWithTimeout(
                POWER_QUERY_TIMEOUT, client, PowerQuery, system_id=node_id,
                hostname=node_hostname, power_type=power_info.power_type,
                context=power_info.power_parameters)
        except CancelledError:
            # We got fed up waiting. The query may later discover the node's
            # power state but by then we won't be paying attention.
            maaslog.error("%s: Timed-out querying power.", node_hostname)
            state = "error"
        except PowerActionFail:
            # We discard the reason. That will have been logged elsewhere.
            # Here we're signalling something very simple back to the user.
            state = "error"
        except NotImplementedError:
            # The power driver has declared that it doesn't after all know how
            # to query the power for this node, so "unknown" seems appropriate.
            state = "unknown"
        else:
            state = response["state"]

        yield deferToDatabase(update_power_state, state)
        returnValue(state)
