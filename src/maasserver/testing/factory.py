# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test object factories."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "factory",
    "Messages",
    ]

from datetime import timedelta
import hashlib
from io import BytesIO
import logging
import random
import time

from django.contrib.auth.models import User
from django.test.client import RequestFactory
from django.utils import timezone
from maasserver.clusterrpc.power_parameters import get_power_types
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    CACHE_MODE_TYPE,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_BOOT,
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    PARTITION_TABLE_TYPE,
    POWER_STATE,
)
from maasserver.fields import (
    LargeObjectFile,
    MAC,
)
from maasserver.models import (
    BlockDevice,
    BootResource,
    BootResourceFile,
    BootResourceSet,
    BootSource,
    BootSourceCache,
    BootSourceSelection,
    Device,
    DHCPLease,
    DownloadProgress,
    Event,
    EventType,
    Fabric,
    FileStorage,
    Filesystem,
    FilesystemGroup,
    LargeFile,
    LicenseKey,
    MACAddress,
    MACStaticIPAddressLink,
    Network,
    Node,
    NodeGroup,
    NodeGroupInterface,
    Partition,
    PartitionTable,
    PhysicalBlockDevice,
    Space,
    SSHKey,
    SSLKey,
    StaticIPAddress,
    Subnet,
    Tag,
    VirtualBlockDevice,
    VLAN,
    VolumeGroup,
    Zone,
)
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.bootresourceset import (
    COMMISSIONABLE_SET,
    INSTALL_SET,
    XINSTALL_TYPES,
)
from maasserver.models.interface import (
    Interface,
    InterfaceRelationship,
)
from maasserver.models.partition import MIN_PARTITION_SIZE
from maasserver.node_status import NODE_TRANSITIONS
from maasserver.testing import get_data
from maasserver.testing.orm import reload_object
from maasserver.utils.converters import round_size_to_nearest_block
import maastesting.factory
from maastesting.factory import NO_VALUE
from metadataserver.enum import RESULT_TYPE
from metadataserver.fields import Bin
from metadataserver.models import (
    CommissioningScript,
    NodeResult,
)
from netaddr import (
    IPAddress,
    IPNetwork,
    IPRange,
)
from provisioningserver.utils.enum import map_enum

# We have a limited number of public keys:
# src/maasserver/tests/data/test_rsa{0, 1, 2, 3, 4}.pub
MAX_PUBLIC_KEYS = 5


ALL_NODE_STATES = map_enum(NODE_STATUS).values()


# Use `undefined` instead of `None` for default factory arguments when `None`
# is a reasonable value for the argument.
undefined = object()


class Messages:
    """A class to record messages published by Django messaging
    framework.
    """

    def __init__(self):
        self.messages = []

    def add(self, level, message, extras):
        self.messages.append((level, message, extras))

    def __iter__(self):
        for message in self.messages:
            yield message


class Factory(maastesting.factory.Factory):

    def make_fake_request(self, path, method="GET"):
        """Create a fake request.

        :param path: The path to which to make the request.
        :param method: The method to use for the request
            ('GET' or 'POST').
        """
        rf = RequestFactory()
        request = rf.get(path)
        request.method = method
        request._messages = Messages()
        return request

    def make_file_upload(self, name=None, content=None):
        """Create a file-like object for upload in http POST or PUT.

        To upload a file using the Django test client, just include a
        parameter that maps not to a string, but to a file upload as
        produced by this method.

        :param name: Name of the file to be uploaded.  If omitted, one will
            be made up.
        :type name: `unicode`
        :param content: Contents for the uploaded file.  If omitted, some
            contents will be made up.
        :type content: `bytes`
        :return: A file-like object, with the requested `content` and `name`.
        """
        if content is None:
            content = self.make_string().encode('ascii')
        if name is None:
            name = self.make_name('file')
        assert isinstance(content, bytes)
        upload = BytesIO(content)
        upload.name = name
        return upload

    def pick_enum(self, enum, but_not=None):
        """Pick a random item from an enumeration class.

        :param enum: An enumeration class such as `NODE_STATUS`.
        :return: The value of one of its items.
        :param but_not: A list of choices' IDs to exclude.
        :type but_not: Sequence.
        """
        if but_not is None:
            but_not = ()
        return random.choice([
            value for value in list(map_enum(enum).values())
            if value not in but_not])

    def pick_choice(self, choices, but_not=None):
        """Pick a random item from `choices`.

        :param choices: A sequence of choices in Django form choices format:
            [
                ('choice_id_1', "Choice name 1"),
                ('choice_id_2', "Choice name 2"),
            ]
        :param but_not: A list of choices' IDs to exclude.
        :type but_not: Sequence.
        :return: The "id" portion of a random choice out of `choices`.
        """
        if but_not is None:
            but_not = ()
        return random.choice(
            [choice for choice in choices if choice[0] not in but_not])[0]

    def pick_power_type(self, but_not=None):
        """Pick a random power type and return it.

        :param but_not: Exclude these values from result
        :type but_not: Sequence
        """
        if but_not is None:
            but_not = []
        else:
            but_not = list(but_not)
        but_not.append('')
        return random.choice(
            [choice for choice in list(get_power_types().keys())
                if choice not in but_not])

    def pick_commissioning_release(self, osystem):
        """Pick a random commissioning release from operating system."""
        releases = osystem.get_supported_commissioning_releases()
        return random.choice(releases)

    def _save_node_unchecked(self, node):
        """Save a :class:`Node`, but circumvent status transition checks."""
        valid_initial_states = NODE_TRANSITIONS[None]
        NODE_TRANSITIONS[None] = ALL_NODE_STATES
        try:
            node.save()
        finally:
            NODE_TRANSITIONS[None] = valid_initial_states

    def make_Device(self, hostname=None, nodegroup=None, **kwargs):
        if hostname is None:
            hostname = self.make_string(20)
        if nodegroup is None:
            nodegroup = self.make_NodeGroup()
        device = Device(hostname=hostname, nodegroup=nodegroup, **kwargs)
        device.save()
        return device

    def make_Node(
            self, mac=False, hostname=None, status=None,
            architecture="i386/generic", min_hwe_kernel=None, hwe_kernel=None,
            installable=True, updated=None, created=None, nodegroup=None,
            routers=None, zone=None, networks=None, boot_type=None,
            sortable_name=False, power_type=None, power_parameters=None,
            power_state=None, power_state_updated=undefined, disable_ipv4=None,
            **kwargs):
        """Make a :class:`Node`.

        :param sortable_name: If `True`, use a that will sort consistently
            between different collation orders.  Use this when testing sorting
            by name, where the database and the python code may have different
            ideas about collation orders, especially when it comes to case
            differences.
        """
        # hostname=None is a valid value, hence the set_hostname trick.
        if hostname is None:
            hostname = self.make_string(20)
        if sortable_name:
            hostname = hostname.lower()
        if status is None:
            status = NODE_STATUS.DEFAULT
        if nodegroup is None:
            nodegroup = self.make_NodeGroup()
        if routers is None:
            routers = [self.make_MAC()]
        if zone is None:
            zone = self.make_Zone()
        if power_type is None:
            power_type = 'ether_wake'
        if power_parameters is None:
            power_parameters = ""
        if power_state is None:
            power_state = self.pick_enum(POWER_STATE)
        if power_state_updated is undefined:
            power_state_updated = (
                timezone.now() - timedelta(minutes=random.randint(0, 15)))
        if disable_ipv4 is None:
            disable_ipv4 = self.pick_bool()
        if boot_type is None:
            boot_type = self.pick_enum(NODE_BOOT)
        node = Node(
            hostname=hostname, status=status, architecture=architecture,
            min_hwe_kernel=min_hwe_kernel, hwe_kernel=hwe_kernel,
            installable=installable, nodegroup=nodegroup, routers=routers,
            zone=zone, boot_type=boot_type, power_type=power_type,
            power_parameters=power_parameters, power_state=power_state,
            power_state_updated=power_state_updated, disable_ipv4=disable_ipv4,
            **kwargs)
        self._save_node_unchecked(node)
        # We do not generate random networks by default because the limited
        # number of VLAN identifiers (4,094) makes it very likely to
        # encounter collisions.
        if networks is not None:
            node.networks.add(*networks)
        if mac:
            self.make_MACAddress(node=node)

        # Update the 'updated'/'created' fields with a call to 'update'
        # preventing a call to save() from overriding the values.
        if updated is not None:
            Node.objects.filter(id=node.id).update(updated=updated)
        if created is not None:
            Node.objects.filter(id=node.id).update(created=created)
        return reload_object(node)

    def get_interface_fields(self, name=None, ip=None, router_ip=None,
                             network=None, subnet_mask=None, broadcast_ip=None,
                             ip_range_low=None, ip_range_high=None,
                             interface=None, management=None,
                             static_ip_range_low=None,
                             static_ip_range_high=None, **kwargs):
        """Return a dict of parameters for a cluster interface.

        These are the values that go into a `NodeGroupInterface` model object
        or form, except the `NodeGroup`.  All IP address fields are unicode
        strings.

        The `network` parameter is not included in the result, but if you
        pass an `IPNetwork` as its value, this will be the network that the
        cluster interface will be attached to.  Its IP address, netmask, and
        address ranges will be taken from `network`.
        """
        if name is None:
            name = factory.make_name('ngi')
        if network is None:
            network = factory.make_ipv4_network()
        # Split the network into dynamic and static ranges.
        if network.size > 2:
            middle = network.size // 2
            dynamic_range = IPRange(network.first, network[middle])
            static_range = IPRange(network[middle + 1], network.last)
        else:
            dynamic_range = network
            static_range = None
        if subnet_mask is None:
            subnet_mask = unicode(network.netmask)
        if broadcast_ip is None:
            broadcast_ip = unicode(network.broadcast)
        if static_ip_range_low is None or static_ip_range_high is None:
            if static_range is None:
                static_ip_range_low = None
                static_ip_range_high = None
            else:
                static_low = static_range.first
                static_high = static_range.last
                if static_ip_range_low is None:
                    static_ip_range_low = unicode(IPAddress(static_low))
                if static_ip_range_high is None:
                    static_ip_range_high = unicode(IPAddress(static_high))
        if ip_range_low is None:
            ip_range_low = unicode(IPAddress(dynamic_range.first))
        if ip_range_high is None:
            ip_range_high = unicode(IPAddress(dynamic_range.last))
        if router_ip is None:
            router_ip = factory.pick_ip_in_network(network)
        if ip is None:
            ip = factory.pick_ip_in_network(network)
        if management is None:
            management = factory.pick_enum(NODEGROUPINTERFACE_MANAGEMENT)
        if interface is None:
            interface = self.make_name('netinterface')
        return dict(
            name=name,
            subnet_mask=subnet_mask,
            broadcast_ip=broadcast_ip,
            ip_range_low=ip_range_low,
            ip_range_high=ip_range_high,
            static_ip_range_low=static_ip_range_low,
            static_ip_range_high=static_ip_range_high,
            router_ip=router_ip,
            ip=ip,
            management=management,
            interface=interface)

    def make_NodeGroup(self, name=None, uuid=None, cluster_name=None,
                       dhcp_key=None, ip=None, router_ip=None, network=None,
                       subnet_mask=None, broadcast_ip=None, ip_range_low=None,
                       ip_range_high=None, interface=None, management=None,
                       status=None, maas_url='', static_ip_range_low=None,
                       static_ip_range_high=None, default_disable_ipv4=None,
                       **kwargs):
        """Create a :class:`NodeGroup`.

        If `management` is set (to a `NODEGROUPINTERFACE_MANAGEMENT` value),
        a :class:`NodeGroupInterface` will be created as well.

        If network (an instance of IPNetwork) is provided, use it to populate
        subnet_mask, broadcast_ip, ip_range_low, ip_range_high, router_ip and
        worker_ip.  This is a convenience for setting up a coherent network
        all in one go.
        """
        if status is None:
            status = factory.pick_enum(NODEGROUP_STATUS)
        if name is None:
            name = self.make_name('nodegroup')
        if uuid is None:
            uuid = factory.make_UUID()
        if cluster_name is None:
            cluster_name = factory.make_name('cluster')
        if dhcp_key is None:
            # TODO: Randomise this properly.
            dhcp_key = ''
        if default_disable_ipv4 is None:
            default_disable_ipv4 = factory.pick_bool()
        cluster = NodeGroup.objects.new(
            name=name, uuid=uuid, cluster_name=cluster_name, status=status,
            dhcp_key=dhcp_key, maas_url=maas_url,
            default_disable_ipv4=default_disable_ipv4)
        if management is not None:
            interface_settings = dict(
                ip=ip, router_ip=router_ip, network=network,
                subnet_mask=subnet_mask, broadcast_ip=broadcast_ip,
                ip_range_low=ip_range_low, ip_range_high=ip_range_high,
                interface=interface, management=management,
                static_ip_range_low=static_ip_range_low,
                static_ip_range_high=static_ip_range_high)
            interface_settings.update(kwargs)
            self.make_NodeGroupInterface(cluster, **interface_settings)
        return cluster

    def make_unrenamable_NodeGroup_with_Node(self):
        """Create a `NodeGroup` that can't be renamed, and `Node`.

        Node groups can't be renamed while they are in an accepted state, have
        DHCP and DNS management enabled, and have a node that is in allocated
        state.

        The cluster will also have a managed interface.

        :return: tuple: (`NodeGroup`, `Node`).
        """
        name = self.make_name('original-name')
        nodegroup = self.make_NodeGroup(
            name=name, status=NODEGROUP_STATUS.ENABLED)
        factory.make_NodeGroupInterface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        node = self.make_Node(
            nodegroup=nodegroup, status=NODE_STATUS.ALLOCATED)
        return nodegroup, node

    def make_NodeGroupInterface(self, nodegroup, name=None, ip=None,
                                router_ip=None, network=None,
                                subnet_mask=None, broadcast_ip=None,
                                ip_range_low=None, ip_range_high=None,
                                interface=None, management=None,
                                static_ip_range_low=None,
                                static_ip_range_high=None, **kwargs):
        interface_settings = self.get_interface_fields(
            name=name, ip=ip, router_ip=router_ip, network=network,
            subnet_mask=subnet_mask, broadcast_ip=broadcast_ip,
            ip_range_low=ip_range_low, ip_range_high=ip_range_high,
            interface=interface, management=management,
            static_ip_range_low=static_ip_range_low,
            static_ip_range_high=static_ip_range_high)
        interface_settings.update(**kwargs)
        interface = NodeGroupInterface(
            nodegroup=nodegroup, **interface_settings)
        interface.save()
        return interface

    def make_NodeResult_for_commissioning(
            self, node=None, name=None, script_result=None, data=None):
        """Create a `NodeResult` as one would see from commissioning a node."""
        if node is None:
            node = self.make_Node()
        if name is None:
            name = "ncrname-" + self.make_string(92)
        if data is None:
            data = b"ncrdata-" + self.make_bytes()
        if script_result is None:
            script_result = random.randint(0, 10)
        ncr = NodeResult(
            node=node, name=name, script_result=script_result,
            result_type=RESULT_TYPE.COMMISSIONING, data=Bin(data))
        ncr.save()
        return ncr

    def make_NodeResult_for_installation(
            self, node=None, name=None, script_result=None, data=None):
        """Create a `NodeResult` as one would see from installing a node."""
        if node is None:
            node = self.make_Node()
        if name is None:
            name = "ncrname-" + self.make_string(92)
        if data is None:
            data = b"ncrdata-" + self.make_bytes()
        if script_result is None:
            script_result = random.randint(0, 10)
        ncr = NodeResult(
            node=node, name=name, script_result=script_result,
            result_type=RESULT_TYPE.INSTALLATION, data=Bin(data))
        ncr.save()
        return ncr

    def make_MAC(self):
        """Generate a random MAC address, in the form of a MAC object."""
        return MAC(self.make_mac_address())

    def make_MACAddress(self, address=None, node=None, networks=None,
                        **kwargs):
        """Create a `MACAddress` model object."""
        if address is None:
            address = self.make_mac_address()
        mac = MACAddress(mac_address=MAC(address), node=node, **kwargs)
        mac.save()
        if networks is not None:
            mac.networks.add(*networks)
        return mac

    def make_MACAddress_with_Node(self, address=None, node=None, networks=None,
                                  **kwargs):
        """Create a `MACAddress` model that is guaranteed to be linked
        to a node.
        """
        if node is None:
            node = self.make_Node()
        return self.make_MACAddress(
            node=node, address=address, networks=networks, **kwargs)

    def make_Node_with_MACAddress_and_NodeGroupInterface(
            self, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP,
            mac_count=1, network=None, disable_ipv4=False, **kwargs):
        """Create a Node that has a MACAddress which has a
        NodeGroupInterface.

        :param mac_count: count of MAC addresses to add
        :param **kwargs: Additional parameters to pass to make_node.
        """
        nodegroup = kwargs.pop("nodegroup", None)
        if nodegroup is None:
            nodegroup = self.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED)
        node = self.make_Node(
            mac=True, nodegroup=nodegroup, disable_ipv4=disable_ipv4, **kwargs)
        ngi = self.make_NodeGroupInterface(
            nodegroup, network=network, management=management)
        mac = node.get_primary_mac()
        mac.cluster_interface = ngi
        mac.save()
        for _ in range(1, mac_count):
            mac = self.make_MACAddress(node=node)
            mac.cluster_interface = ngi
            mac.save()
        return node

    def make_StaticIPAddress(self, ip=None, alloc_type=IPADDRESS_TYPE.AUTO,
                             mac=None, user=None):
        """Create and return a StaticIPAddress model object.

        If a non-None `mac` is passed, connect this IP address to the
        given MAC Address.
        """
        if ip is None:
            ip = self.make_ipv4_address()
        ipaddress = StaticIPAddress(ip=ip, alloc_type=alloc_type, user=user)
        ipaddress.save()
        if mac is not None:
            MACStaticIPAddressLink(
                mac_address=mac, ip_address=ipaddress).save()
        return ipaddress

    def make_DHCPLease(self, nodegroup=None, ip=None, mac=None):
        """Create a :class:`DHCPLease`."""
        if nodegroup is None:
            nodegroup = self.make_NodeGroup()
        if ip is None:
            ip = self.make_ipv4_address()
        if mac is None:
            mac = self.make_mac_address()
        lease = DHCPLease(nodegroup=nodegroup, ip=ip, mac=MAC(mac))
        lease.save()
        return lease

    def make_email(self):
        return '%s@example.com' % self.make_string(10)

    def make_User(self, username=None, password='test', email=None):
        if username is None:
            username = self.make_username()
        if email is None:
            email = self.make_email()
        return User.objects.create_user(
            username=username, password=password, email=email)

    def make_SSHKey(self, user, key_string=None):
        if key_string is None:
            key_string = get_data('data/test_rsa0.pub')
        key = SSHKey(key=key_string, user=user)
        key.save()
        return key

    def make_SSLKey(self, user, key_string=None):
        if key_string is None:
            key_string = get_data('data/test_x509_0.pem')
        key = SSLKey(key=key_string, user=user)
        key.save()
        return key

    def make_Space(self, name=None):
        if name is None:
            name = self.make_name('space')
        space = Space(name=name)
        space.save()
        return space

    def make_Subnet(self, name=None, vlan=None, space=None, cidr=None,
                    gateway_ip=None, dns_servers=None):
        if name is None:
            name = factory.make_name('name')
        if vlan is None:
            vlan = factory.make_VLAN()
        if space is None:
            space = factory.make_Space()
        if cidr is None:
            network = factory.make_ip4_or_6_network()
            cidr = unicode(network.cidr)
        if gateway_ip is None:
            gateway_ip = factory.pick_ip_in_network(IPNetwork(cidr))
        if dns_servers is None:
            dns_servers = [
                self.make_ip_address() for _ in range(random.randint(1, 3))]
        subnet = Subnet(
            name=name, vlan=vlan, cidr=cidr, gateway_ip=gateway_ip,
            space=space, dns_servers=dns_servers)
        subnet.save()
        return subnet

    def make_Fabric(self, name=None):
        if name is None:
            name = self.make_name('fabric')
        fabric = Fabric(name=name)
        fabric.save()
        return fabric

    def _get_available_vid(self, fabric):
        """Return a free vid in the given Fabric."""
        taken_vids = set(fabric.vlan_set.all().values_list('vid', flat=True))
        for attempt in range(1000):
            vid = random.randint(1, 4095)
            if vid not in taken_vids:
                return vid
        raise maastesting.factory.TooManyRandomRetries(
            "Could not generate vid in fabric %s" % fabric)

    def make_VLAN(self, name=None, vid=None, fabric=None):
        assert vid != 0, "VID=0 VLANs are auto-created"
        if name is None:
            name = self.make_name('vlan')
        if fabric is None:
            fabric = self.make_Fabric()
        if vid is None:
            # Don't create the vid=0 VLAN, it's auto-created.
            vid = self._get_available_vid(fabric)
        vlan = VLAN(name=name, vid=vid, fabric=fabric)
        vlan.save()
        return vlan

    def make_Interface(self, type, mac=None, vlan=None, parents=None,
                       name=None):
        if name is None and type != INTERFACE_TYPE.VLAN:
            name = self.make_name('name')
        if vlan is None:
            vlan = self.make_VLAN()
        interface = Interface(mac=mac, type=type, name=name, vlan=vlan)
        interface.save()
        if parents:
            for parent in parents:
                InterfaceRelationship(child=interface, parent=parent).save()
        return reload_object(interface)

    def make_Tag(self, name=None, definition=None, comment='',
                 kernel_opts=None, created=None, updated=None):
        if name is None:
            name = self.make_name('tag')
        if definition is None:
            # Is there a 'node' in this xml?
            definition = '//node'
        tag = Tag(
            name=name, definition=definition, comment=comment,
            kernel_opts=kernel_opts)
        tag.save()
        # Update the 'updated'/'created' fields with a call to 'update'
        # preventing a call to save() from overriding the values.
        if updated is not None:
            Tag.objects.filter(id=tag.id).update(updated=updated)
        if created is not None:
            Tag.objects.filter(id=tag.id).update(created=created)
        return reload_object(tag)

    def make_user_with_keys(self, n_keys=2, user=None, **kwargs):
        """Create a user with n `SSHKey`.  If user is not None, use this user
        instead of creating one.

        Additional keyword arguments are passed to `make_user()`.
        """
        if n_keys > MAX_PUBLIC_KEYS:
            raise RuntimeError(
                "Cannot create more than %d public keys.  If you need more: "
                "add more keys in src/maasserver/tests/data/."
                % MAX_PUBLIC_KEYS)
        if user is None:
            user = self.make_User(**kwargs)
        keys = []
        for i in range(n_keys):
            key_string = get_data('data/test_rsa%d.pub' % i)
            key = SSHKey(user=user, key=key_string)
            key.save()
            keys.append(key)
        return user, keys

    def make_user_with_ssl_keys(self, n_keys=2, user=None, **kwargs):
        """Create a user with n `SSLKey`.

        :param n_keys: Number of keys to add to user.
        :param user: User to add keys to. If user is None, then user is made
            with make_user. Additional keyword arguments are passed to
            `make_user()`.
        """
        if n_keys > MAX_PUBLIC_KEYS:
            raise RuntimeError(
                "Cannot create more than %d public keys.  If you need more: "
                "add more keys in src/maasserver/tests/data/."
                % MAX_PUBLIC_KEYS)
        if user is None:
            user = self.make_User(**kwargs)
        keys = []
        for i in range(n_keys):
            key_string = get_data('data/test_x509_%d.pem' % i)
            key = SSLKey(user=user, key=key_string)
            key.save()
            keys.append(key)
        return user, keys

    def make_admin(self, username=None, password='test', email=None):
        if username is None:
            username = self.make_username()
        if email is None:
            email = self.make_email()
        return User.objects.create_superuser(
            username, password=password, email=email)

    def make_FileStorage(self, filename=None, content=None, owner=None):
        fake_file = self.make_file_upload(filename, content)
        return FileStorage.objects.save_file(fake_file.name, fake_file, owner)

    def make_oauth_header(self, missing_param=None, **kwargs):
        """Fake an OAuth authorization header.

        This will use arbitrary values.  Pass as keyword arguments any
        header items that you wish to override.
        :param missing_param: Optional parameter name.  This parameter will
            be omitted from the OAuth header.  This is used to create bogus
            OAuth headers to make sure the code deals properly with them.
        """
        items = {
            'realm': self.make_string(),
            'oauth_nonce': random.randint(0, 99999),
            'oauth_timestamp': time.time(),
            'oauth_consumer_key': self.make_string(18),
            'oauth_signature_method': 'PLAINTEXT',
            'oauth_version': '1.0',
            'oauth_token': self.make_string(18),
            'oauth_signature': "%%26%s" % self.make_string(32),
        }
        items.update(kwargs)
        if missing_param is not None:
            del items[missing_param]
        return "OAuth " + ", ".join([
            '%s="%s"' % (key, value) for key, value in items.items()])

    def make_CommissioningScript(self, name=None, content=None):
        if name is None:
            name = self.make_name('script')
        if content is None:
            content = b'content:' + self.make_string().encode('ascii')
        return CommissioningScript.objects.create(
            name=name, content=Bin(content))

    def make_DownloadProgress(self, nodegroup=None, filename=None,
                              size=NO_VALUE, bytes_downloaded=NO_VALUE,
                              error=None):
        """Create a `DownloadProgress` in some poorly-defined state.

        If you have specific wishes about the object's state, you'll want to
        use one of the specialized `make_DownloadProgress_*` methods instead.

        Pass a `size` of `None` to indicate that total file size is not yet
        known.  The default picks either a random number, or None.
        """
        if nodegroup is None:
            nodegroup = self.make_NodeGroup()
        if filename is None:
            filename = self.make_name('download')
        if size is NO_VALUE:
            if self.pick_bool():
                size = random.randint(0, 1000000000)
            else:
                size = None
        if bytes_downloaded is NO_VALUE:
            if self.pick_bool():
                if size is None:
                    max_size = 1000000000
                else:
                    max_size = size
                bytes_downloaded = random.randint(0, max_size)
            else:
                bytes_downloaded = None
        if error is None:
            if self.pick_bool():
                error = self.make_string()
            else:
                error = ''
        return DownloadProgress.objects.create(
            nodegroup=nodegroup, filename=filename, size=size,
            bytes_downloaded=bytes_downloaded)

    def make_DownloadProgress_initial(self, nodegroup=None, filename=None,
                                      size=NO_VALUE):
        """Create a `DownloadProgress` as reported before a download."""
        return self.make_DownloadProgress(
            nodegroup=nodegroup, filename=filename, size=size,
            bytes_downloaded=None, error='')

    def make_DownloadProgress_success(self, nodegroup=None, filename=None,
                                      size=None):
        """Create a `DownloadProgress` indicating success."""
        if size is None:
            size = random.randint(0, 1000000000)
        return self.make_DownloadProgress(
            nodegroup=nodegroup, filename=filename, size=size,
            bytes_downloaded=size, error='')

    def make_DownloadProgress_incomplete(self, nodegroup=None, filename=None,
                                         size=NO_VALUE,
                                         bytes_downloaded=None):
        """Create a `DownloadProgress` that's not done yet."""
        if size is NO_VALUE:
            if self.pick_bool():
                # File can't be empty, or the download can't be incomplete.
                size = random.randint(1, 1000000000)
            else:
                size = None
        if bytes_downloaded is None:
            if size is None:
                max_size = 1000000000
            else:
                max_size = size
            bytes_downloaded = random.randint(0, max_size - 1)
        return self.make_DownloadProgress(
            nodegroup=nodegroup, filename=filename, size=size,
            bytes_downloaded=bytes_downloaded, error='')

    def make_DownloadProgress_failure(self, nodegroup=None, filename=None,
                                      size=NO_VALUE,
                                      bytes_downloaded=NO_VALUE, error=None):
        """Create a `DownloadProgress` indicating failure."""
        if error is None:
            error = self.make_string()
        return self.make_DownloadProgress_incomplete(
            nodegroup=nodegroup, filename=filename, size=size,
            bytes_downloaded=bytes_downloaded, error=error)

    def make_Zone(self, name=None, description=None, nodes=None,
                  sortable_name=False):
        """Create a physical `Zone`.

        :param sortable_name: If `True`, use a that will sort consistently
            between different collation orders.  Use this when testing sorting
            by name, where the database and the python code may have different
            ideas about collation orders, especially when it comes to case
            differences.
        """
        if name is None:
            name = self.make_name('zone')
        if sortable_name:
            name = name.lower()
        if description is None:
            description = self.make_string()
        zone = Zone(name=name, description=description)
        zone.save()
        if nodes is not None:
            zone.node_set.add(*nodes)
        return zone

    make_zone = make_Zone

    def make_Network(self, name=None, network=None, vlan_tag=NO_VALUE,
                     description=None, sortable_name=False,
                     disjoint_from=None, default_gateway=None,
                     dns_servers=None):
        """Create a `Network`.

        :param network: An `IPNetwork`.  If given, the `ip` and `netmask`
            fields will be taken from this.
        :param vlan_tag: A number between 1 and 0xffe inclusive to create a
            VLAN, or 0 to create a non-VLAN network, or None to make a random
            choice.
        :param sortable_name: If `True`, use a that will sort consistently
            between different collation orders.  Use this when testing sorting
            by name, where the database and the python code may have different
            ideas about collation orders, especially when it comes to case
            differences.
        :param disjoint_from: List of other `Network` or `IPNetwork` objects
            whose IP ranges the new network must not overlap with.
        """
        if name is None:
            name = factory.make_name()
        if sortable_name:
            # The only currently known problem with sorting order is between
            # case-sensitive and case-insensitive ordering, so use lower-case
            # only.
            name = name.lower()
        if disjoint_from is None:
            disjoint_from = []
        # disjoint_from may contain both Network and IPNetwork.  Normalise to
        # all IPNetwork objects.
        disjoint_from = [
            entry.get_network() if isinstance(entry, Network) else entry
            for entry in disjoint_from
            ]
        if network is None:
            network = self.make_ipv4_network(disjoint_from=disjoint_from)
        if default_gateway is None and self.pick_bool():
            default_gateway = self.pick_ip_in_network(network)
        if dns_servers is None and self.pick_bool():
            dns_servers = " ".join(
                self.make_ipv4_address()
                for _ in range(random.choice((1, 2))))
        ip = unicode(network.ip)
        netmask = unicode(network.netmask)
        if description is None:
            description = self.make_string()
        if vlan_tag is NO_VALUE:
            vlan_tag = self.make_vlan_tag()
        network = Network(
            name=name, ip=ip, netmask=netmask, vlan_tag=vlan_tag,
            description=description, default_gateway=default_gateway,
            dns_servers=dns_servers)
        network.save()
        return network

    def make_Networks(self, number, with_vlans=True, **kwargs):
        """Create multiple networks.

        This avoids accidentally clashing VLAN tags.

        :param with_vlans: Whether the networks should be allowed to include
            VLANs.  If `True`, then the VLAN tags will be unique.
        """
        if with_vlans:
            vlan_tags = []
            for _ in range(1000):
                if len(vlan_tags) == number:
                    break
                vlan_tag = self.make_vlan_tag(allow_none=True)
                if vlan_tag is None or vlan_tag not in vlan_tags:
                    vlan_tags.append(vlan_tag)
            else:
                raise maastesting.factory.TooManyRandomRetries(
                    "Could not generate %d non-clashing VLAN tags" % number)
        else:
            vlan_tags = [None] * number
        networks = []
        for tag in vlan_tags:
            networks.append(
                self.make_Network(
                    vlan_tag=tag, disjoint_from=networks, **kwargs))
        return networks

    def make_BootSource(self, url=None, keyring_filename=None,
                        keyring_data=None):
        """Create a new `BootSource`."""
        if url is None:
            url = "http://%s.com" % self.make_name('source-url')
        # Only set _one_ of keyring_filename and keyring_data.
        if keyring_filename is None and keyring_data is None:
            keyring_filename = self.make_name("keyring")
        boot_source = BootSource(
            url=url,
            keyring_filename=(
                "" if keyring_filename is None else keyring_filename),
            keyring_data=(
                b"" if keyring_data is None else keyring_data),
        )
        boot_source.save()
        return boot_source

    def make_BootSourceCache(self, boot_source=None, os=None, arch=None,
                             subarch=None, release=None, label=None):
        """Create a new `BootSourceCache`."""
        if boot_source is None:
            boot_source = self.make_BootSource()
        if os is None:
            os = factory.make_name('os')
        if arch is None:
            arch = factory.make_name('arch')
        if subarch is None:
            subarch = factory.make_name('subarch')
        if release is None:
            release = factory.make_name('release')
        if label is None:
            label = factory.make_name('label')
        return BootSourceCache.objects.create(
            boot_source=boot_source, os=os, arch=arch,
            subarch=subarch, release=release, label=label)

    def make_many_BootSourceCaches(self, number, **kwargs):
        caches = list()
        for _ in range(number):
            caches.append(self.make_BootSourceCache(**kwargs))
        return caches

    def make_BootSourceSelection(self, boot_source=None, os=None,
                                 release=None, arches=None, subarches=None,
                                 labels=None):
        """Create a `BootSourceSelection`."""
        if boot_source is None:
            boot_source = self.make_BootSource()
        if os is None:
            os = self.make_name('os')
        if release is None:
            release = self.make_name('release')
        if arches is None:
            arch_count = random.randint(1, 10)
            arches = [self.make_name("arch") for _ in range(arch_count)]
        if subarches is None:
            subarch_count = random.randint(1, 10)
            subarches = [
                self.make_name("subarch")
                for _ in range(subarch_count)
                ]
        if labels is None:
            label_count = random.randint(1, 10)
            labels = [self.make_name("label") for _ in range(label_count)]
        boot_source_selection = BootSourceSelection(
            boot_source=boot_source, release=release, arches=arches,
            subarches=subarches, labels=labels)
        boot_source_selection.save()
        return boot_source_selection

    def make_LicenseKey(self, osystem=None, distro_series=None,
                        license_key=None):
        if osystem is None:
            osystem = factory.make_name('osystem')
        if distro_series is None:
            distro_series = factory.make_name('distro_series')
        if license_key is None:
            license_key = factory.make_name('key')
        return LicenseKey.objects.create(
            osystem=osystem,
            distro_series=distro_series,
            license_key=license_key)

    def make_EventType(self, name=None, level=None, description=None):
        if name is None:
            name = self.make_name('name', size=20)
        if description is None:
            description = factory.make_name('description')
        if level is None:
            level = random.choice([
                logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG])
        return EventType.objects.create(
            name=name, description=description, level=level)

    def make_Event(self, node=None, type=None, description=None):
        if node is None:
            node = self.make_Node()
        if type is None:
            type = self.make_EventType()
        if description is None:
            description = self.make_name('desc')
        return Event.objects.create(
            node=node, type=type, description=description)

    def make_LargeFile(self, content=None, size=512):
        """Create `LargeFile`.

        :param content: Data to store in large file object.
        :param size: Size of `content`. If `content` is None
            then it will be a random string of this size. If content is
            provided and `size` is not the same length, then it will
            be an inprogress file.
        """
        if content is None:
            content = factory.make_string(size=size)
        sha256 = hashlib.sha256()
        sha256.update(content)
        sha256 = sha256.hexdigest()
        largeobject = LargeObjectFile()
        with largeobject.open('wb') as stream:
            stream.write(content)
        return LargeFile.objects.create(
            sha256=sha256, total_size=size, content=largeobject)

    def make_BootResource(self, rtype=None, name=None, architecture=None,
                          extra=None):
        if rtype is None:
            rtype = self.pick_enum(BOOT_RESOURCE_TYPE)
        if name is None:
            if rtype == BOOT_RESOURCE_TYPE.UPLOADED:
                name = self.make_name('name')
            else:
                os = self.make_name('os')
                series = self.make_name('series')
                name = '%s/%s' % (os, series)
        if architecture is None:
            arch = self.make_name('arch')
            subarch = self.make_name('subarch')
            architecture = '%s/%s' % (arch, subarch)
        if extra is None:
            extra = {
                self.make_name('key'): self.make_name('value')
                for _ in range(3)
                }
        return BootResource.objects.create(
            rtype=rtype, name=name, architecture=architecture, extra=extra)

    def make_BootResourceSet(self, resource, version=None, label=None):
        if version is None:
            version = self.make_name('version')
        if label is None:
            label = self.make_name('label')
        return BootResourceSet.objects.create(
            resource=resource, version=version, label=label)

    def make_BootResourceFile(self, resource_set, largefile, filename=None,
                              filetype=None, extra=None):
        if filename is None:
            filename = self.make_name('name')
        if filetype is None:
            filetype = self.pick_enum(BOOT_RESOURCE_FILE_TYPE)
        if extra is None:
            extra = {
                self.make_name('key'): self.make_name('value')
                for _ in range(3)
                }
        return BootResourceFile.objects.create(
            resource_set=resource_set, largefile=largefile, filename=filename,
            filetype=filetype, extra=extra)

    def make_boot_resource_file_with_content(
            self, resource_set, filename=None, filetype=None, extra=None,
            content=None, size=512):
        largefile = self.make_LargeFile(content=content, size=size)
        return self.make_BootResourceFile(
            resource_set, largefile, filename=filename, filetype=filetype,
            extra=extra)

    def make_usable_boot_resource(
            self, rtype=None, name=None, architecture=None,
            extra=None, version=None, label=None):
        resource = self.make_BootResource(
            rtype=rtype, name=name, architecture=architecture, extra=extra)
        resource_set = self.make_BootResourceSet(
            resource, version=version, label=label)
        filetypes = COMMISSIONABLE_SET.union(INSTALL_SET)
        filetypes.add(random.choice(XINSTALL_TYPES))
        for filetype in filetypes:
            # We set the filename to the same value as filetype, as in most
            # cases this will always be true. The simplestreams content from
            # maas.ubuntu.com, is formatted this way.
            self.make_boot_resource_file_with_content(
                resource_set, filename=filetype, filetype=filetype)
        return resource

    def make_BlockDevice(
            self, node=None, name=None, id_path=None, size=None,
            block_size=None, tags=None):
        if node is None:
            node = self.make_Node()
        if name is None:
            name = self.make_name('name')
        if id_path is None:
            id_path = '/dev/disk/by-id/id_%s' % name
        if block_size is None:
            block_size = random.choice([512, 1024, 4096])
        if size is None:
            size = round_size_to_nearest_block(
                random.randint(
                    MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 1024),
                block_size)
        if tags is None:
            tags = [self.make_name('tag') for _ in range(3)]
        return BlockDevice.objects.create(
            node=node, name=name, size=size, block_size=block_size,
            tags=tags)

    def make_PhysicalBlockDevice(
            self, node=None, name=None, size=None, block_size=None,
            tags=None, model=None, serial=None):
        if node is None:
            node = self.make_Node()
        if name is None:
            name = self.make_name('name')
        if block_size is None:
            block_size = random.choice([512, 1024, 4096])
        if size is None:
            size = round_size_to_nearest_block(
                random.randint(
                    MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 1024),
                block_size)
        if tags is None:
            tags = [self.make_name('tag') for _ in range(3)]
        if model is None:
            model = self.make_name('model')
        if serial is None:
            serial = self.make_name('serial')
        return PhysicalBlockDevice.objects.create(
            node=node, name=name, size=size, block_size=block_size,
            tags=tags, model=model, serial=serial)

    def make_PartitionTable(
            self, table_type=None, block_device=None, node=None,
            block_device_size=None):
        if table_type is None:
            table_type = self.pick_enum(PARTITION_TABLE_TYPE)
        if block_device is None:
            block_device = self.make_PhysicalBlockDevice(
                node=node, size=block_device_size)
        return PartitionTable.objects.create(
            table_type=table_type, block_device=block_device)

    def make_Partition(
            self, partition_table=None, uuid=None, size=None, bootable=None,
            node=None, block_device_size=None):
        if partition_table is None:
            partition_table = self.make_PartitionTable(
                node=node, block_device_size=block_device_size)
        if size is None:
            size = round_size_to_nearest_block(
                random.randint(
                    MIN_PARTITION_SIZE, partition_table.get_available_size()),
                partition_table.get_block_size())
        if bootable is None:
            bootable = random.choice([True, False])
        return Partition.objects.create(
            partition_table=partition_table, uuid=uuid,
            size=size, bootable=bootable)

    def make_Filesystem(
            self, uuid=None, fstype=None, partition=None, block_device=None,
            filesystem_group=None, create_params=None, mount_point=None,
            mount_params=None, block_device_size=None):
        if fstype is None:
            fstype = self.pick_enum(FILESYSTEM_TYPE)
        if partition is None and block_device is None:
            if self.pick_bool():
                partition = self.make_Partition()
            else:
                block_device = self.make_PhysicalBlockDevice(
                    size=block_device_size)
        return Filesystem.objects.create(
            uuid=uuid, fstype=fstype, partition=partition,
            block_device=block_device, filesystem_group=filesystem_group,
            create_params=create_params, mount_point=mount_point,
            mount_params=mount_params)

    def make_FilesystemGroup(
            self, uuid=None, group_type=None, name=None, create_params=None,
            filesystems=None, node=None, block_device_size=None,
            cache_mode=None, num_lvm_devices=4):
        if group_type is None:
            group_type = self.pick_enum(FILESYSTEM_GROUP_TYPE)
        if group_type == FILESYSTEM_GROUP_TYPE.BCACHE and cache_mode is None:
            cache_mode = self.pick_enum(CACHE_MODE_TYPE)
        group = FilesystemGroup(
            uuid=uuid, group_type=group_type, name=name, cache_mode=cache_mode,
            create_params=create_params)
        group.save()
        if filesystems is None:
            if node is None:
                node = self.make_Node()
            if group_type == FILESYSTEM_GROUP_TYPE.LVM_VG:
                for _ in range(num_lvm_devices):
                    block_device = self.make_PhysicalBlockDevice(
                        node, size=block_device_size)
                    filesystem = self.make_Filesystem(
                        fstype=FILESYSTEM_TYPE.LVM_PV,
                        block_device=block_device)
                    group.filesystems.add(filesystem)
            elif group_type == FILESYSTEM_GROUP_TYPE.RAID_0:
                for _ in range(2):
                    block_device = self.make_PhysicalBlockDevice(node)
                    filesystem = self.make_Filesystem(
                        fstype=FILESYSTEM_TYPE.RAID,
                        block_device=block_device)
                    group.filesystems.add(filesystem)
            elif group_type == FILESYSTEM_GROUP_TYPE.RAID_1:
                for _ in range(2):
                    block_device = self.make_PhysicalBlockDevice(node)
                    filesystem = self.make_Filesystem(
                        fstype=FILESYSTEM_TYPE.RAID,
                        block_device=block_device)
                    group.filesystems.add(filesystem)
            elif (group_type == FILESYSTEM_GROUP_TYPE.RAID_4 or
                    group_type == FILESYSTEM_GROUP_TYPE.RAID_5):
                for _ in range(3):
                    block_device = self.make_PhysicalBlockDevice(node)
                    filesystem = self.make_Filesystem(
                        fstype=FILESYSTEM_TYPE.RAID,
                        block_device=block_device)
                    group.filesystems.add(filesystem)
                spare_block_device = self.make_PhysicalBlockDevice(node)
                spare_filesystem = self.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=spare_block_device)
                group.filesystems.add(spare_filesystem)
            elif group_type == FILESYSTEM_GROUP_TYPE.RAID_6:
                for _ in range(4):
                    block_device = self.make_PhysicalBlockDevice(node)
                    filesystem = self.make_Filesystem(
                        fstype=FILESYSTEM_TYPE.RAID,
                        block_device=block_device)
                    group.filesystems.add(filesystem)
                spare_block_device = self.make_PhysicalBlockDevice(node)
                spare_filesystem = self.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=spare_block_device)
                group.filesystems.add(spare_filesystem)
            elif group_type == FILESYSTEM_GROUP_TYPE.BCACHE:
                cache_block_device = self.make_PhysicalBlockDevice(node)
                cache_filesystem = self.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.BCACHE_CACHE,
                    block_device=cache_block_device)
                group.filesystems.add(cache_filesystem)
                backing_block_device = self.make_PhysicalBlockDevice(node)
                backing_filesystem = self.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                    block_device=backing_block_device)
                group.filesystems.add(backing_filesystem)
        else:
            for filesystem in filesystems:
                group.filesystems.add(filesystem)
        # Save again to make sure that the added filesystems are correct.
        group.save()
        return group

    def make_VolumeGroup(self, *args, **kwargs):
        if len(args) > 1:
            args[1] = FILESYSTEM_GROUP_TYPE.LVM_VG
        else:
            kwargs['group_type'] = FILESYSTEM_GROUP_TYPE.LVM_VG
        filesystem_group = self.make_FilesystemGroup(*args, **kwargs)
        return VolumeGroup.objects.get(id=filesystem_group.id)

    def make_VirtualBlockDevice(
            self, name=None, size=None, block_size=None,
            tags=None, uuid=None, filesystem_group=None, node=None):
        if node is None:
            node = factory.make_Node()
        if block_size is None:
            block_size = random.choice([512, 1024, 4096])
        if size is None:
            size = round_size_to_nearest_block(
                random.randint(
                    MIN_BLOCK_DEVICE_SIZE, MIN_BLOCK_DEVICE_SIZE * 1024),
                block_size)
        if tags is None:
            tags = [self.make_name("tag") for _ in range(3)]
        if filesystem_group is None:
            filesystem_group = self.make_FilesystemGroup(
                node=node,
                group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
                block_device_size=size,
                num_lvm_devices=2)
        elif not filesystem_group.is_lvm():
            raise RuntimeError(
                "make_VirtualBlockDevice should only be used with "
                "filesystem_group that has a group_type of LVM_VG.  "
                "If you need a VirtualBlockDevice that is for another type "
                "use make_FilesystemGroup which will create a "
                "VirtualBlockDevice automatically.")
        if name is None:
            name = self.make_name("lv")
        if size is None:
            size = random.randint(1, filesystem_group.get_size())
        if block_size is None:
            block_size = random.choice([512, 1024, 4096])
        return VirtualBlockDevice.objects.create(
            name=name, size=size, block_size=block_size,
            tags=tags, uuid=uuid, filesystem_group=filesystem_group)


# Create factory singleton.
factory = Factory()
