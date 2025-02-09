# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper class for all tests using the `PostgresListenerService` under
`maasserver.triggers.tests`."""

from django.contrib.auth.models import User
from piston3.models import Token
from twisted.internet.defer import DeferredQueue, inlineCallbacks, returnValue

from maasserver.enum import INTERFACE_TYPE, NODE_TYPE
from maasserver.listener import PostgresListenerService
from maasserver.models import Script, ScriptSet
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.bmc import BMC, Pod
from maasserver.models.cacheset import CacheSet
from maasserver.models.config import Config
from maasserver.models.dhcpsnippet import DHCPSnippet
from maasserver.models.dnsdata import DNSData
from maasserver.models.dnspublication import DNSPublication
from maasserver.models.dnsresource import DNSResource
from maasserver.models.domain import Domain
from maasserver.models.event import Event
from maasserver.models.fabric import Fabric
from maasserver.models.filesystem import Filesystem
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.interface import Interface
from maasserver.models.iprange import IPRange
from maasserver.models.node import Node, RackController, RegionController
from maasserver.models.nodedevice import NodeDevice
from maasserver.models.nodemetadata import NodeMetadata
from maasserver.models.packagerepository import PackageRepository
from maasserver.models.partition import Partition
from maasserver.models.partitiontable import PartitionTable
from maasserver.models.physicalblockdevice import PhysicalBlockDevice
from maasserver.models.rbacsync import RBACSync
from maasserver.models.regioncontrollerprocess import RegionControllerProcess
from maasserver.models.regioncontrollerprocessendpoint import (
    RegionControllerProcessEndpoint,
)
from maasserver.models.regionrackrpcconnection import RegionRackRPCConnection
from maasserver.models.resourcepool import ResourcePool
from maasserver.models.space import Space
from maasserver.models.sshkey import SSHKey
from maasserver.models.sslkey import SSLKey
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.staticroute import StaticRoute
from maasserver.models.subnet import Subnet
from maasserver.models.tag import Tag
from maasserver.models.user import create_auth_token
from maasserver.models.virtualblockdevice import VirtualBlockDevice
from maasserver.models.vlan import VLAN
from maasserver.models.zone import Zone
from maasserver.testing.factory import factory, RANDOM
from maasserver.triggers import register_trigger
from maasserver.utils.orm import reload_object, transactional
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for

wait_for_reactor = wait_for()


def apply_update(record, params):
    """Apply updates from `params` to `record`.

    Each key in `params` MUST correspond to a preexisting attribute on
    `record`, otherwise `AttributeError` is raised. It's not an update if
    there's nothing previously there.

    :param record: Any object.
    :param params: A mapping of attributes to values.
    """
    for key, value in params.items():
        if not hasattr(record, key):
            raise AttributeError(
                "%r has no %r attribute to which to assign "
                "the value %r" % (record, key, value)
            )
        setattr(record, key, value)


def apply_update_to_model(model, id, params, **kwargs):
    """Apply updates from `params` to `model` with ID `id`.

    See `apply_update`.

    :param model: A Django model class.
    :param id: The ID of `model` to `get`.
    :param params: A mapping of attributes to values.
    """
    record = model.objects.get(id=id)
    apply_update(record, params)
    return record.save(**kwargs)


class TransactionalHelpersMixin:
    """Helpers performing actions in transactions."""

    def make_listener_without_delay(self):
        listener = PostgresListenerService()
        self.patch(listener, "HANDLE_NOTIFY_DELAY", 0)
        self.patch(listener, "CHANNEL_REGISTRAR_DELAY", 0)
        return listener

    @transactional
    def get_node(self, system_id):
        node = Node.objects.get(system_id=system_id)
        return node

    @transactional
    def create_node(self, params=None):
        if params is None:
            params = {}
        vlan = factory.make_VLAN(space=factory.make_Space())
        node = factory.make_Node(vlan=vlan, **params)
        # prefetch the config so it doesn't cause queries in main thread
        node.current_config  # noqa: B018
        return node

    @transactional
    def create_node_with_interface(self, params=None):
        if params is None:
            params = {}
        return factory.make_Node_with_Interface_on_Subnet(**params)

    @transactional
    def get_node_ip_address(self, node):
        interface = node.get_boot_interface()
        return interface.ip_addresses.first()

    @transactional
    def update_node(self, system_id, params):
        node = Node.objects.get(system_id=system_id)
        apply_update(node, params)
        return node.save()

    @transactional
    def delete_node(self, system_id):
        node = Node.objects.get(system_id=system_id)
        node.delete()

    @transactional
    def create_device_with_parent(self, params=None):
        if params is None:
            params = {}
        vlan = factory.make_VLAN(space=factory.make_Space())
        parent = factory.make_Node(with_boot_disk=False)
        params["node_type"] = NODE_TYPE.DEVICE
        params["parent"] = parent
        device = factory.make_Node(vlan=vlan, **params)
        # prefetch the config so it doesn't cause queries in main thread
        device.current_config  # noqa: B018
        return device, parent

    @transactional
    def get_node_boot_interface(self, system_id):
        node = Node.objects.get(system_id=system_id)
        return node.get_boot_interface()

    @transactional
    def create_domain(self, params=None):
        if params is None:
            params = {}
        return factory.make_Domain(**params)

    @transactional
    def update_domain(self, id, params, **kwargs):
        return apply_update_to_model(Domain, id, params, **kwargs)

    @transactional
    def delete_domain(self, id):
        domain = Domain.objects.get(id=id)
        domain.delete()

    @transactional
    def create_dnsresource(self, params=None):
        if params is None:
            params = {}
        return factory.make_DNSResource(**params)

    @transactional
    def update_dnsresource(self, id, params, **kwargs):
        return apply_update_to_model(DNSResource, id, params, **kwargs)

    @transactional
    def delete_dnsresource(self, id):
        dnsresource = DNSResource.objects.get(id=id)
        dnsresource.delete()

    @transactional
    def get_first_staticipaddress(self, obj):
        return obj.ip_addresses.first()

    @transactional
    def create_dnsdata(self, params=None):
        if params is None:
            params = {}
        return factory.make_DNSData(**params)

    @transactional
    def update_dnsdata(self, id, params, **kwargs):
        return apply_update_to_model(DNSData, id, params, **kwargs)

    @transactional
    def delete_dnsdata(self, id):
        dnsdata = DNSData.objects.get(id=id)
        dnsdata.delete()

    @transactional
    def create_fabric(self, params=None):
        if params is None:
            params = {}
        return factory.make_Fabric(**params)

    @transactional
    def update_fabric(self, id, params, **kwargs):
        return apply_update_to_model(Fabric, id, params, **kwargs)

    @transactional
    def delete_fabric(self, id):
        fabric = Fabric.objects.get(id=id)
        fabric.delete()

    @transactional
    def create_bmc(self, params=None):
        if params is None:
            params = {}
        return factory.make_BMC(**params)

    @transactional
    def update_bmc(self, id, params, **kwargs):
        return apply_update_to_model(BMC, id, params, **kwargs)

    @transactional
    def delete_bmc(self, id):
        bmc = BMC.objects.get(id=id)
        bmc.delete()

    @transactional
    def create_pod(self, params=None):
        if params is None:
            params = {}
        return factory.make_Pod(**params)

    @transactional
    def create_pod_with_host(self, params=None):
        if params is None:
            params = {}
        subnet = factory.make_Subnet()
        machine = factory.make_Machine_with_Interface_on_Subnet(subnet=subnet)
        ip = factory.make_StaticIPAddress(
            subnet=subnet, interface=machine.boot_interface
        )
        pod = factory.make_Pod(ip_address=ip, **params)
        return pod, machine

    @transactional
    def update_pod(self, id, params, **kwargs):
        return apply_update_to_model(Pod, id, params, **kwargs)

    @transactional
    def delete_pod(self, id):
        pod = Pod.objects.get(id=id)
        pod.as_bmc().delete()

    @transactional
    def create_space(self, params=None):
        if params is None:
            params = {}
        return factory.make_Space(**params)

    @transactional
    def update_space(self, id, params, **kwargs):
        return apply_update_to_model(Space, id, params, **kwargs)

    @transactional
    def delete_space(self, id):
        space = Space.objects.get(id=id)
        space.delete()

    @transactional
    def create_subnet(self, params=None):
        if params is None:
            params = {}
        return factory.make_Subnet(**params, space=RANDOM)

    @transactional
    def update_subnet(self, id, params, **kwargs):
        return apply_update_to_model(Subnet, id, params, **kwargs)

    @transactional
    def delete_subnet(self, id):
        subnet = Subnet.objects.get(id=id)
        subnet.delete()

    @transactional
    def create_vlan(self, params=None):
        if params is None:
            params = {}
        return factory.make_VLAN(**params, space=RANDOM)

    @transactional
    def update_vlan(self, id, params, **kwargs):
        return apply_update_to_model(VLAN, id, params, **kwargs)

    @transactional
    def delete_vlan(self, id):
        vlan = VLAN.objects.get(id=id)
        vlan.delete()

    @transactional
    def create_zone(self, params=None):
        if params is None:
            params = {}
        return factory.make_Zone(**params)

    @transactional
    def update_zone(self, id, params, **kwargs):
        return apply_update_to_model(Zone, id, params, **kwargs)

    @transactional
    def delete_zone(self, id):
        zone = Zone.objects.get(id=id)
        zone.delete()

    @transactional
    def create_resource_pool(self, params=None):
        if params is None:
            params = {}
        return factory.make_ResourcePool(**params)

    @transactional
    def update_resource_pool(self, id, params, **kwargs):
        return apply_update_to_model(ResourcePool, id, params, **kwargs)

    @transactional
    def delete_resource_pool(self, id):
        pool = ResourcePool.objects.get(id=id)
        pool.delete()

    @transactional
    def create_tag(self, params=None):
        if params is None:
            params = {}
        return factory.make_Tag(**params)

    @transactional
    def add_node_to_tag(self, node, tag):
        node.tags.add(tag)
        node.save(force_update=True)

    @transactional
    def set_node_metadata(self, node, key, value):
        NodeMetadata.objects.update_or_create(
            node=node, key=key, defaults={"value": value}
        )

    @transactional
    def delete_node_metadata(self, node, key):
        NodeMetadata.objects.filter(node=node, key=key).delete()

    @transactional
    def remove_node_from_tag(self, node, tag):
        node.tags.remove(tag)
        node.save(force_update=True)

    @transactional
    def update_tag(self, id, params, **kwargs):
        return apply_update_to_model(Tag, id, params, **kwargs)

    @transactional
    def delete_tag(self, id):
        tag = Tag.objects.get(id=id)
        tag.delete()

    @transactional
    def create_user(self, params=None):
        if params is None:
            params = {}
        return factory.make_User(**params)

    @transactional
    def update_user(self, id, params, **kwargs):
        return apply_update_to_model(User, id, params, **kwargs)

    @transactional
    def delete_user(self, id):
        user = User.objects.get(id=id)
        user.consumers.all().delete()
        user.delete()

    @transactional
    def create_event_type(self, params=None):
        if params is None:
            params = {}
        return factory.make_EventType(**params)

    @transactional
    def create_event(self, params=None):
        if params is None:
            params = {}
        return factory.make_Event(**params)

    @transactional
    def update_event(self, id, params, **kwargs):
        return apply_update_to_model(Event, id, params, **kwargs)

    @transactional
    def delete_event(self, id):
        event = Event.objects.get(id=id)
        event.delete()

    @transactional
    def create_staticipaddress(self, params=None, vlan=None):
        if params is None:
            params = {}
        if vlan is not None:
            params["subnet"] = vlan.subnet_set.first()
        return factory.make_StaticIPAddress(**params)

    @transactional
    def update_staticipaddress(self, id, params, **kwargs):
        return apply_update_to_model(StaticIPAddress, id, params, **kwargs)

    @transactional
    def delete_staticipaddress(self, id):
        sip = StaticIPAddress.objects.get(id=id)
        sip.delete()

    @transactional
    def get_ipaddress_subnet(self, id):
        ipaddress = StaticIPAddress.objects.get(id=id)
        return ipaddress.subnet

    @transactional
    def get_ipaddress_vlan(self, id):
        ipaddress = StaticIPAddress.objects.get(id=id)
        return ipaddress.subnet.vlan

    @transactional
    def get_ipaddress_fabric(self, id):
        ipaddress = StaticIPAddress.objects.get(id=id)
        return ipaddress.subnet.vlan.fabric

    @transactional
    def get_ipaddress_space(self, id):
        ipaddress = StaticIPAddress.objects.get(id=id)
        return ipaddress.subnet.space

    @transactional
    def create_scriptset(self, node):
        script_set = ScriptSet.objects.create_commissioning_script_set(node)
        node.current_commissioning_script_set = script_set
        node.save()
        return script_set

    @transactional
    def delete_scriptset(self, script_set):
        script_set.delete(force=True)

    @transactional
    def create_scriptresult(self, script_set, params=None):
        if params is None:
            params = {}
        return factory.make_ScriptResult(script_set=script_set, **params)

    @transactional
    def delete_scriptresult(self, script_result):
        script_result.delete()

    @transactional
    def create_interface(self, params=None):
        if params is None:
            params = {}
        return factory.make_Interface(INTERFACE_TYPE.PHYSICAL, **params)

    @transactional
    def create_unknown_interface(self, params=None):
        if params is None:
            params = {}
        return factory.make_Interface(INTERFACE_TYPE.UNKNOWN, **params)

    @transactional
    def delete_interface(self, id):
        interface = Interface.objects.get(id=id)
        interface.delete()

    @transactional
    def update_interface(self, id, params, **kwargs):
        return apply_update_to_model(Interface, id, params, **kwargs)

    @transactional
    def get_interface_vlan(self, id):
        interface = Interface.objects.get(id=id)
        return interface.vlan

    @transactional
    def get_interface_fabric(self, id):
        interface = Interface.objects.get(id=id)
        return interface.vlan.fabric

    @transactional
    def create_blockdevice(self, params=None):
        if params is None:
            params = {}
        return factory.make_BlockDevice(**params)

    @transactional
    def create_physicalblockdevice(self, params=None):
        if params is None:
            params = {}
        return factory.make_PhysicalBlockDevice(**params)

    @transactional
    def create_virtualblockdevice(self, params=None):
        if params is None:
            params = {}
        return factory.make_VirtualBlockDevice(**params)

    @transactional
    def delete_blockdevice(self, id):
        blockdevice = BlockDevice.objects.get(id=id)
        blockdevice.delete()

    @transactional
    def update_blockdevice(self, id, params, **kwargs):
        return apply_update_to_model(BlockDevice, id, params, **kwargs)

    @transactional
    def update_physicalblockdevice(self, id, params, **kwargs):
        return apply_update_to_model(PhysicalBlockDevice, id, params, **kwargs)

    @transactional
    def update_virtualblockdevice(self, id, params, **kwargs):
        return apply_update_to_model(VirtualBlockDevice, id, params, **kwargs)

    @transactional
    def create_partitiontable(self, params=None):
        if params is None:
            params = {}
        return factory.make_PartitionTable(**params)

    @transactional
    def delete_partitiontable(self, id):
        partitiontable = PartitionTable.objects.get(id=id)
        partitiontable.delete()

    @transactional
    def update_partitiontable(self, id, params, **kwargs):
        return apply_update_to_model(PartitionTable, id, params, **kwargs)

    @transactional
    def create_partition(self, params=None):
        if params is None:
            params = {}
        return factory.make_Partition(**params)

    @transactional
    def delete_partition(self, id):
        partition = Partition.objects.get(id=id)
        partition.delete()

    @transactional
    def update_partition(self, id, params, **kwargs):
        return apply_update_to_model(Partition, id, params, **kwargs)

    @transactional
    def create_filesystem(self, params=None):
        if params is None:
            params = {}
        return factory.make_Filesystem(**params)

    @transactional
    def delete_filesystem(self, id):
        filesystem = Filesystem.objects.get(id=id)
        filesystem.delete()

    @transactional
    def update_filesystem(self, id, params, **kwargs):
        return apply_update_to_model(Filesystem, id, params, **kwargs)

    @transactional
    def create_filesystemgroup(self, params=None):
        if params is None:
            params = {}
        return factory.make_FilesystemGroup(**params)

    @transactional
    def delete_filesystemgroup(self, id):
        filesystemgroup = FilesystemGroup.objects.get(id=id)
        filesystemgroup.delete()

    @transactional
    def update_filesystemgroup(self, id, params, **kwargs):
        return apply_update_to_model(FilesystemGroup, id, params, **kwargs)

    @transactional
    def create_cacheset(self, params=None):
        if params is None:
            params = {}
        return factory.make_CacheSet(**params)

    @transactional
    def delete_cacheset(self, id):
        cacheset = CacheSet.objects.get(id=id)
        cacheset.delete()

    @transactional
    def update_cacheset(self, id, params, **kwargs):
        return apply_update_to_model(CacheSet, id, params, **kwargs)

    @transactional
    def create_token(self, params=None):
        if params is None:
            params = {}
        return create_auth_token(**params)

    @transactional
    def update_token(self, id, name=None):
        token = Token.objects.get(id=id)
        token.consumer.name = name
        token.consumer.save()
        return token

    @transactional
    def delete_token(self, id):
        token = Token.objects.get(id=id)
        token.delete()

    @transactional
    def create_sshkey(self, params=None):
        if params is None:
            params = {}
        return factory.make_SSHKey(**params)

    @transactional
    def update_sshkey(self, id, params, **kwargs):
        return apply_update_to_model(SSHKey, id, params, **kwargs)

    @transactional
    def delete_sshkey(self, id):
        key = SSHKey.objects.get(id=id)
        key.delete()

    @transactional
    def create_sslkey(self, params=None):
        if params is None:
            params = {}
        return factory.make_SSLKey(**params)

    @transactional
    def update_sslkey(self, id, params, **kwargs):
        return apply_update_to_model(SSLKey, id, params, **kwargs)

    @transactional
    def delete_sslkey(self, id):
        key = SSLKey.objects.get(id=id)
        key.delete()

    @transactional
    def create_rack_controller(self, params=None):
        if params is None:
            params = {}
        return factory.make_RackController(**params)

    @transactional
    def update_rack_controller(self, id, params, **kwargs):
        return apply_update_to_model(RackController, id, params, **kwargs)

    @transactional
    def delete_rack_controller(self, id):
        rack = RackController.objects.get(id=id)
        rack.delete()

    @transactional
    def create_iprange(self, params=None):
        if params is None:
            params = {}
        return factory.make_IPRange(**params)

    @transactional
    def update_iprange(self, id, params, **kwargs):
        return apply_update_to_model(IPRange, id, params, **kwargs)

    @transactional
    def delete_iprange(self, id):
        ipr = IPRange.objects.get(id=id)
        ipr.delete()

    @transactional
    def create_staticroute(self, params=None):
        if params is None:
            params = {}
        return factory.make_StaticRoute(**params)

    @transactional
    def update_staticroute(self, id, params, **kwargs):
        return apply_update_to_model(StaticRoute, id, params, **kwargs)

    @transactional
    def delete_staticroute(self, id):
        ipr = StaticRoute.objects.get(id=id)
        ipr.delete()

    @transactional
    def create_region_controller(self, params=None):
        if params is None:
            params = {}
        return factory.make_RegionController(**params)

    @transactional
    def update_region_controller(self, id, params, **kwargs):
        return apply_update_to_model(RegionController, id, params, **kwargs)

    @transactional
    def delete_region_controller(self, id):
        region = RegionController.objects.get(id=id)
        region.delete()

    @transactional
    def create_dhcp_snippet(self, params=None):
        if params is None:
            params = {}
        return factory.make_DHCPSnippet(**params)

    @transactional
    def update_dhcp_snippet(self, id, params, **kwargs):
        return apply_update_to_model(DHCPSnippet, id, params, **kwargs)

    @transactional
    def delete_dhcp_snippet(self, id):
        dhcp_snippet = DHCPSnippet.objects.get(id=id)
        dhcp_snippet.delete()

    @transactional
    def create_package_repository(self, params=None):
        if params is None:
            params = {}
        return factory.make_PackageRepository(**params)

    @transactional
    def update_package_repository(self, id, params, **kwargs):
        return apply_update_to_model(PackageRepository, id, params, **kwargs)

    @transactional
    def delete_package_repository(self, id):
        package_repository = PackageRepository.objects.get(id=id)
        package_repository.delete()

    @transactional
    def create_region_controller_process(self, params=None):
        if params is None:
            params = {}
        return factory.make_RegionControllerProcess(**params)

    @transactional
    def update_region_controller_process(self, id, params, **kwargs):
        return apply_update_to_model(
            RegionControllerProcess, id, params, **kwargs
        )

    @transactional
    def delete_region_controller_process(self, id):
        process = RegionControllerProcess.objects.get(id=id)
        process.delete()

    @transactional
    def create_region_controller_process_endpoint(self, params=None):
        if params is None:
            params = {}
        return factory.make_RegionControllerProcessEndpoint(**params)

    @transactional
    def update_region_controller_process_endpoint(self, id, params, **kwargs):
        return apply_update_to_model(
            RegionControllerProcessEndpoint, id, params, **kwargs
        )

    @transactional
    def delete_region_controller_process_endpoint(self, id):
        process = RegionControllerProcessEndpoint.objects.get(id=id)
        process.delete()

    @transactional
    def create_region_rack_rpc_connection(self, params=None):
        if params is None:
            params = {}
        return factory.make_RegionRackRPCConnection(**params)

    @transactional
    def update_region_rack_rpc_connection(self, id, params, **kwargs):
        return apply_update_to_model(
            RegionRackRPCConnection, id, params, **kwargs
        )

    @transactional
    def delete_region_rack_rpc_connection(self, id):
        process = RegionRackRPCConnection.objects.get(id=id)
        process.delete()

    @transactional
    def create_script(self, params=None):
        if params is None:
            params = {}
        return factory.make_Script(**params)

    @transactional
    def update_script(self, id, params, **kwargs):
        return apply_update_to_model(Script, id, params, **kwargs)

    @transactional
    def delete_script(self, id):
        script = Script.objects.get(id=id)
        script.delete()

    @transactional
    def reload_object(self, obj):
        return reload_object(obj)

    @transactional
    def create_config(self, name, value):
        config, freshly_created = Config.objects.get_or_create(
            name=name, defaults=dict(value=value)
        )
        assert freshly_created, "Config already created."
        return config

    @transactional
    def set_config(self, name, value):
        config = Config.objects.get(name=name)
        config.value = value
        config.save()

    @transactional
    def create_node_device(self, params=None):
        if params is None:
            params = {}
        return factory.make_NodeDevice(**params)

    @transactional
    def update_node_device(self, id, params, **kwargs):
        return apply_update_to_model(NodeDevice, id, params, **kwargs)

    @transactional
    def delete_node_device(self, id):
        node_device = NodeDevice.objects.get(id=id)
        node_device.delete()


class DNSHelpersMixin:
    """Helper to get the zone serial and to assert it was incremented."""

    @transactional
    def getPublication(self):
        try:
            return DNSPublication.objects.get_most_recent()
        except DNSPublication.DoesNotExist:
            return None

    @inlineCallbacks
    def capturePublication(self):
        """Capture the most recent `DNSPublication` record."""
        self.__publication = yield deferToDatabase(self.getPublication)
        returnValue(self.__publication)

    def getCapturedPublication(self):
        """Return the captured publication."""
        try:
            return self.__publication
        except AttributeError:
            self.fail(
                "No reference publication has been captured; "
                "use `capturePublication` before calling "
                "`getCapturedPublication`."
            )

    @inlineCallbacks
    def assertPublicationUpdated(self):
        """Assert there's a newer `DNSPublication` record.

        Call `capturePublication` first to obtain a reference record.
        """
        old = self.getCapturedPublication()
        new = yield self.capturePublication()
        if old is None:
            self.assertIsNotNone(new, "DNS has not been published at all.")
        else:
            self.assertGreater(
                new.serial, old.serial, "DNS has not been published again."
            )


class RBACHelpersMixin:
    """Helper to get the latest rbac sync."""

    @transactional
    def getSynced(self):
        try:
            return RBACSync.objects.order_by("-id").first()
        except RBACSync.DoesNotExist:
            return None

    @inlineCallbacks
    def captureSynced(self):
        """Capture the most recent `RBACSync` record."""
        self.__synced = yield deferToDatabase(self.getSynced)
        returnValue(self.__synced)

    def getCapturedSynced(self):
        """Return the captured sync record."""
        try:
            return self.__synced
        except AttributeError:
            self.fail(
                "No reference modification has been captured; "
                "use `captureSynced` before calling "
                "`getCapturedSynced`."
            )

    @inlineCallbacks
    def assertSynced(self):
        """Assert there's a newer `RBACSync` record.

        Call `captureSynced` first to obtain a reference record.
        """
        old = self.getCapturedSynced()
        new = yield self.captureSynced()
        if old is None:
            self.assertIsNotNone(
                new, "RBAC sync tracking has not been modified at all."
            )
        else:
            self.assertGreater(
                new.id,
                old.id,
                "RBAC sync tracking has not been modified again.",
            )


class NotifyHelperMixin:
    channels = ()
    channel_queues = {}
    postgres_listener_service = None

    @inlineCallbacks
    def set_service(self, listener):
        self.postgres_listener_service = listener
        yield self.postgres_listener_service.startService()

    def register_trigger(self, table, channel, ops=(), trigger=None):
        if channel not in self.channels:
            self.postgres_listener_service.registerChannel(channel)
            self.postgres_listener_service.register(channel, self.listen)
            self.channels = self.channels + (channel,)
        for op in ops:
            trigger = trigger or f"{channel}_{table}_{op}"
            register_trigger(table, trigger, op)

    @inlineCallbacks
    def listen(self, channel, msg):
        if msg and channel in self.channel_queues:
            yield self.channel_queues[channel].put(msg)

    def get_notify(self, channel):
        if channel in self.channel_queues:
            return self.channel_queues[channel].get()
        return None

    def start_reading(self):
        for channel in self.channels:
            self.channel_queues[channel] = DeferredQueue()
        self.postgres_listener_service.startReading()

    def stop_reading(self):
        for channel in self.channels:
            del self.channel_queues[channel]
        self.postgres_listener_service.stopReading()
