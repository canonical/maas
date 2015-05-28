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

import crochet
from lxml import etree
from maasserver.enum import NODE_PERMISSION
from maasserver.exceptions import NodeActionError
from maasserver.forms import AdminNodeWithMACAddressesForm
from maasserver.models.config import Config
from maasserver.models.event import Event
from maasserver.models.node import Node
from maasserver.models.nodegroup import NodeGroup
from maasserver.models.nodeprobeddetails import get_single_probed_details
from maasserver.models.tag import Tag
from maasserver.node_action import compile_node_actions
from maasserver.rpc import getClientFor
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils.converters import XMLToYAML
from maasserver.utils.orm import transactional
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
from provisioningserver.logger import get_maas_logger
from provisioningserver.power.poweraction import (
    PowerActionFail,
    UnknownPowerType,
)
from provisioningserver.rpc.cluster import PowerQuery
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.tags import merge_details_cleanly
from provisioningserver.utils.twisted import asynchronous
from twisted.internet.threads import deferToThread


maaslog = get_maas_logger("websockets.node")


class NodeHandler(TimestampedModelHandler):

    class Meta:
        queryset = (
            Node.nodes.filter(installable=True)
                .select_related('nodegroup', 'pxe_mac', 'owner')
                .prefetch_related('macaddress_set')
                .prefetch_related('macaddress_set__networks')
                .prefetch_related('nodegroup__nodegroupinterface_set')
                .prefetch_related('zone')
                .prefetch_related('tags')
                .prefetch_related('blockdevice_set__physicalblockdevice'))
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
            "pxe_mac",
            "token",
            "netboot",
            "agent_name",
        ]
        list_fields = [
            "system_id",
            "hostname",
            "owner",
            "cpu_count",
            "memory",
            "power_state",
            "pxe_mac",
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
            "%s" % mac_address.mac_address
            for mac_address in obj.get_extra_macs()
        ]
        pxe_mac = obj.get_pxe_mac()
        if pxe_mac is not None:
            data["pxe_mac"] = "%s" % pxe_mac
            data["pxe_mac_vendor"] = obj.get_pxe_mac_vendor()
        else:
            data["pxe_mac"] = data["pxe_mac_vendor"] = ""

        physicalblockdevices = self.get_physicalblockdevices_for(obj)
        data["disks"] = len(physicalblockdevices)
        data["storage"] = "%3.1f" % (
            sum([
                blockdevice.size
                for blockdevice in physicalblockdevices
                ]) / (1000 ** 3))
        data["storage_tags"] = self.get_all_storage_tags(physicalblockdevices)

        data["tags"] = [
            tag.name
            for tag in obj.tags.all()
        ]
        data["networks"] = self.dehydrate_networks(obj)
        if not for_list:
            data["osystem"] = obj.get_osystem()
            data["distro_series"] = obj.get_distro_series()

            # Network
            mac_addresses = obj.macaddress_set.all().prefetch_related(
                'ip_addresses').order_by('id')
            interfaces = [
                self.dehydrate_interface(mac_address, obj)
                for mac_address in mac_addresses
            ]
            data["interfaces"] = sorted(
                interfaces, key=itemgetter("is_pxe"), reverse=True)

            # Storage
            data["physical_disks"] = [
                self.dehydrate_physicalblockdevice(blockdevice)
                for blockdevice in physicalblockdevices
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

    def dehydrate_physicalblockdevice(self, blockdevice):
        """Return `PhysicalBlockDevice` formatted for JSON encoding."""
        return {
            "name": blockdevice.name,
            "tags": blockdevice.tags,
            "path": blockdevice.path,
            "size": blockdevice.size,
            "size_gb": "%3.1f" % (blockdevice.size / (1000 ** 3)),
            "block_size": blockdevice.block_size,
            "model": blockdevice.model,
            "serial": blockdevice.serial,
        }

    def dehydrate_interface(self, mac_address, obj):
        """Dehydrate a `mac_address` into a interface definition."""
        # Statically assigned ip addresses.
        ip_addresses = [
            {
                "type": "static",
                "alloc_type": ip_address.alloc_type,
                "ip_address": "%s" % ip_address.ip,
            }
            for ip_address in mac_address.ip_addresses.all()
        ]

        # Dynamically assigned ip addresses come from parsing the leases file.
        # This will also contain the statically assigned ip addresses as they
        # show up in the leases file. Remove any that already appear in the
        # static ip address table.
        static_addresses = [
            ip_address["ip_address"]
            for ip_address in ip_addresses
        ]
        ip_addresses += [
            {
                "type": "dynamic",
                "ip_address": lease.ip,
            }
            for lease in obj.nodegroup.dhcplease_set.all()
            if (lease.mac == mac_address.mac_address and
                lease.ip not in static_addresses)
        ]

        # Connected networks.
        networks = [
            {
                "id": network.id,
                "name": network.name,
                "ip": network.ip,
                "cidr": "%s" % network.get_network().cidr,
                "vlan": network.vlan_tag,
            }
            for network in mac_address.networks.all()
        ]
        return {
            "id": mac_address.id,
            "is_pxe": mac_address == obj.pxe_mac,
            "mac_address": "%s" % mac_address.mac_address,
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

    def dehydrate_networks(self, obj):
        """Dehydrate all the networks this node belongs to."""
        return list({
            network.name
            for mac_address in obj.macaddress_set.all()
            for network in mac_address.get_networks()
        })

    def get_all_storage_tags(self, physicalblockdevices):
        """Return list of all storage tags in `physicalblockdevices`."""
        tags = set()
        for blockdevice in physicalblockdevices:
            tags = tags.union(blockdevice.tags)
        return list(tags)

    def get_physicalblockdevices_for(self, obj):
        """Return only `PhysicalBlockDevice`s using the prefetched query."""
        return [
            blockdevice.physicalblockdevice
            for blockdevice in obj.blockdevice_set.all()
            if hasattr(blockdevice, "physicalblockdevice")
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

        # Update the tags for the node.
        self.update_tags(node_obj, params['tags'])
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

    def check_power(self, params):
        """Check the power state of the node."""
        obj = self.get_object(params)
        if not obj.installable:
            raise HandlerError(
                "%s: Unable to query power state; not an installable node" %
                obj.hostname)

        ng = obj.nodegroup

        try:
            client = getClientFor(ng.uuid)
        except NoConnectionsAvailable:
            maaslog.error(
                "Unable to get RPC connection for cluster '%s' (%s)",
                ng.cluster_name, ng.uuid)
            raise HandlerError("Unable to connect to cluster controller")

        state = None
        try:
            power_info = obj.get_effective_power_info()
        except UnknownPowerType:
            # Only raises this error when the node doesn't have a power type
            # set. Return unknown because with no power type, we don't know
            # its power state.
            state = "unknown"
        if not power_info.can_be_started:
            # If its cannot be started then its not queryable.
            state = "unknown"

        if state is None:
            call = client(
                PowerQuery, system_id=obj.system_id, hostname=obj.hostname,
                power_type=power_info.power_type,
                context=power_info.power_parameters)
            try:
                # Allow 15 seconds for the power query max as we're holding
                # up a thread waiting.
                state = call.wait(15)['state']
            except crochet.TimeoutError:
                maaslog.error(
                    "%s: Timed out waiting for power response in "
                    "Node.power_state",
                    obj.hostname)
                state = "error"
            except (NotImplementedError, PowerActionFail):
                state = "error"

        @asynchronous
        def update_power_state(state):
            transactional_update = transactional(obj.update_power_state)
            return deferToThread(transactional_update, state)

        # Update the power_state of the node. This will cause the update to
        # occur in a seperate thread wrapped with transactional. This will make
        # sure the change is committed and retried if required. Not pushing
        # this to another thread, would result in the entire power query being
        # performed again.
        update_power_state(state).wait(15)
        return state
