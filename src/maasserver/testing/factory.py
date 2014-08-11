# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
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

import hashlib
from io import BytesIO
import logging
import random
import time

from django.contrib.auth.models import User
from django.test.client import RequestFactory
from maasserver.clusterrpc.power_parameters import get_power_types
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    POWER_STATE,
    )
from maasserver.fields import (
    LargeObjectFile,
    MAC,
    )
from maasserver.models import (
    BootImage,
    BootResource,
    BootResourceFile,
    BootResourceSet,
    BootSource,
    BootSourceSelection,
    DHCPLease,
    DownloadProgress,
    Event,
    EventType,
    FileStorage,
    LargeFile,
    LicenseKey,
    MACAddress,
    MACStaticIPAddressLink,
    Network,
    Node,
    NodeGroup,
    NodeGroupInterface,
    SSHKey,
    SSLKey,
    StaticIPAddress,
    Tag,
    Zone,
    )
from maasserver.models.bootresourceset import (
    COMMISSIONABLE_SET,
    INSTALL_SET,
    XINSTALL_TYPES,
    )
from maasserver.models.node import NODE_TRANSITIONS
from maasserver.testing import get_data
from maasserver.testing.orm import reload_object
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
    IPRange,
    )
# XXX 2014-05-13 blake-rouse bug=1319143
# Need to not import directly, use RPC to info from cluster.
from provisioningserver.drivers.osystem import OperatingSystemRegistry
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS
from provisioningserver.utils import map_enum

# We have a limited number of public keys:
# src/maasserver/tests/data/test_rsa{0, 1, 2, 3, 4}.pub
MAX_PUBLIC_KEYS = 5


ALL_NODE_STATES = map_enum(NODE_STATUS).values()


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

    def pick_OS(self):
        """Pick a random operating system from the registry."""
        osystems = [obj for _, obj in OperatingSystemRegistry]
        return random.choice(osystems)

    def pick_release(self, osystem):
        """Pick a random release from operating system."""
        releases = osystem.get_supported_releases()
        return random.choice(releases)

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

    def make_node(self, mac=False, hostname=None, status=None,
                  architecture="i386/generic", updated=None,
                  created=None, nodegroup=None, routers=None, zone=None,
                  power_type=None, networks=None, sortable_name=False,
                  power_state=None, **kwargs):
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
            nodegroup = self.make_node_group()
        if routers is None:
            routers = [self.make_MAC()]
        if zone is None:
            zone = self.make_zone()
        if power_type is None:
            power_type = 'ether_wake'
        if power_state is None:
            power_state = self.pick_enum(POWER_STATE)
        node = Node(
            hostname=hostname, status=status, architecture=architecture,
            nodegroup=nodegroup, routers=routers, zone=zone,
            power_type=power_type, **kwargs)
        self._save_node_unchecked(node)
        # We do not generate random networks by default because the limited
        # number of VLAN identifiers (4,094) makes it very likely to
        # encounter collisions.
        if networks is not None:
            node.networks.add(*networks)
        if mac:
            self.make_mac_address(node=node)

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
            network = factory.getRandomNetwork()
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
            if static_range is not None:
                static_low = static_range.first
                static_high = static_range.last
                if static_ip_range_low is None:
                    static_ip_range_low = unicode(IPAddress(static_low))
                if static_ip_range_high is None:
                    static_ip_range_high = unicode(IPAddress(static_high))
            else:
                static_ip_range_low = None
                static_ip_range_high = None
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

    def make_node_group(self, name=None, uuid=None, cluster_name=None,
                        dhcp_key=None, ip=None, router_ip=None, network=None,
                        subnet_mask=None, broadcast_ip=None, ip_range_low=None,
                        ip_range_high=None, interface=None, management=None,
                        status=None, maas_url='', static_ip_range_low=None,
                        static_ip_range_high=None, **kwargs):
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
        cluster = NodeGroup.objects.new(
            name=name, uuid=uuid, cluster_name=cluster_name, status=status,
            dhcp_key=dhcp_key, maas_url=maas_url)
        if management is not None:
            interface_settings = dict(
                ip=ip, router_ip=router_ip, network=network,
                subnet_mask=subnet_mask, broadcast_ip=broadcast_ip,
                ip_range_low=ip_range_low, ip_range_high=ip_range_high,
                interface=interface, management=management,
                static_ip_range_low=static_ip_range_low,
                static_ip_range_high=static_ip_range_high)
            interface_settings.update(kwargs)
            self.make_node_group_interface(cluster, **interface_settings)
        return cluster

    def make_unrenamable_nodegroup_with_node(self):
        """Create a `NodeGroup` that can't be renamed, and `Node`.

        Node groups can't be renamed while they are in an accepted state, have
        DHCP and DNS management enabled, and have a node that is in allocated
        state.

        The cluster will also have a managed interface.

        :return: tuple: (`NodeGroup`, `Node`).
        """
        name = self.make_name('original-name')
        nodegroup = self.make_node_group(
            name=name, status=NODEGROUP_STATUS.ACCEPTED)
        factory.make_node_group_interface(
            nodegroup, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS)
        node = self.make_node(
            nodegroup=nodegroup, status=NODE_STATUS.ALLOCATED)
        return nodegroup, node

    def make_node_group_interface(self, nodegroup, name=None, ip=None,
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

    def make_node_commission_result(self, node=None, name=None,
                                    script_result=None, data=None):
        if node is None:
            node = self.make_node()
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

    def make_MAC(self):
        """Generate a random MAC address, in the form of a MAC object."""
        return MAC(self.getRandomMACAddress())

    def make_mac_address(self, address=None, node=None, networks=None,
                         **kwargs):
        """Create a MACAddress model object."""
        if node is None:
            node = self.make_node()
        if address is None:
            address = self.getRandomMACAddress()
        mac = MACAddress(mac_address=MAC(address), node=node, **kwargs)
        mac.save()
        if networks is not None:
            mac.networks.add(*networks)
        return mac

    def make_node_with_mac_attached_to_nodegroupinterface(
            self, management=NODEGROUPINTERFACE_MANAGEMENT.DHCP, **kwargs):
        """Create a Node that has a MACAddress which has a
        NodeGroupInterface.

        :param **kwargs: Additional parameters to pass to make_node.
        """
        if "nodegroup" in kwargs:
            nodegroup = kwargs.pop("nodegroup")
        else:
            nodegroup = self.make_node_group()
        node = self.make_node(mac=True, nodegroup=nodegroup, **kwargs)
        ngi = self.make_node_group_interface(
            nodegroup, management=management)
        mac = node.get_primary_mac()
        mac.cluster_interface = ngi
        mac.save()
        return node

    def make_staticipaddress(self, ip=None, alloc_type=IPADDRESS_TYPE.AUTO,
                             mac=None, user=None):
        """Create and return a StaticIPAddress model object.

        If a non-None `mac` is passed, connect this IP address to the
        given MAC Address.
        """
        if ip is None:
            ip = self.getRandomIPAddress()
        ipaddress = StaticIPAddress(ip=ip, alloc_type=alloc_type, user=user)
        ipaddress.save()
        if mac is not None:
            MACStaticIPAddressLink(
                mac_address=mac, ip_address=ipaddress).save()
        return ipaddress

    def make_dhcp_lease(self, nodegroup=None, ip=None, mac=None):
        """Create a :class:`DHCPLease`."""
        if nodegroup is None:
            nodegroup = self.make_node_group()
        if ip is None:
            ip = self.getRandomIPAddress()
        if mac is None:
            mac = self.getRandomMACAddress()
        lease = DHCPLease(nodegroup=nodegroup, ip=ip, mac=MAC(mac))
        lease.save()
        return lease

    def make_email(self):
        return '%s@example.com' % self.make_string(10)

    def make_user(self, username=None, password='test', email=None):
        if username is None:
            username = self.make_username()
        if email is None:
            email = self.make_email()
        return User.objects.create_user(
            username=username, password=password, email=email)

    def make_sshkey(self, user, key_string=None):
        if key_string is None:
            key_string = get_data('data/test_rsa0.pub')
        key = SSHKey(key=key_string, user=user)
        key.save()
        return key

    def make_tag(self, name=None, definition=None, comment='',
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
            user = self.make_user(**kwargs)
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
            user = self.make_user(**kwargs)
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

    def make_file_storage(self, filename=None, content=None, owner=None):
        fake_file = self.make_file_upload(filename, content)
        return FileStorage.objects.save_file(fake_file.name, fake_file, owner)

    def make_oauth_header(self, **kwargs):
        """Fake an OAuth authorization header.

        This will use arbitrary values.  Pass as keyword arguments any
        header items that you wish to override.
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
        return "OAuth " + ", ".join([
            '%s="%s"' % (key, value) for key, value in items.items()])

    def make_boot_image(self, osystem=None, architecture=None,
                        subarchitecture=None, release=None, purpose=None,
                        nodegroup=None, label=None, supported_subarches=None,
                        xinstall_path=None, xinstall_type=None):
        if osystem is None:
            osystem = self.make_name('os')
        if architecture is None:
            architecture = self.make_name('architecture')
        if subarchitecture is None:
            subarchitecture = self.make_name('subarchitecture')
        if release is None:
            release = self.make_name('release')
        if purpose is None:
            purpose = self.make_name('purpose')
        if nodegroup is None:
            nodegroup = self.make_node_group()
        if label is None:
            label = self.make_name('label')
        if supported_subarches is None:
            supported_subarches = [
                self.make_name("supportedsubarch1"),
                self.make_name("supportedsubarch2")]
        if isinstance(supported_subarches, list):
            supported_subarches = ",".join(supported_subarches)
        return BootImage.objects.create(
            nodegroup=nodegroup,
            osystem=osystem,
            architecture=architecture,
            subarchitecture=subarchitecture,
            release=release,
            purpose=purpose,
            label=label,
            supported_subarches=supported_subarches,
            xinstall_path=xinstall_path,
            xinstall_type=xinstall_type,
            )

    def make_boot_images_for_node_with_purposes(self, node, purposes):
        osystem = node.get_osystem()
        series = node.get_distro_series()
        arch, subarch = node.split_arch()
        images = []
        for purpose in purposes:
            if purpose == 'xinstall':
                xinstall_path = self.make_name('xi_path')
                xinstall_type = self.make_name('xi_type')
            else:
                xinstall_path = None
                xinstall_type = None
            images.append(
                self.make_boot_image(
                    osystem=osystem, architecture=arch,
                    subarchitecture=subarch, release=series, purpose=purpose,
                    nodegroup=node.nodegroup, xinstall_path=xinstall_path,
                    xinstall_type=xinstall_type))
        return images

    def make_commissioning_script(self, name=None, content=None):
        if name is None:
            name = self.make_name('script')
        if content is None:
            content = b'content:' + self.make_string().encode('ascii')
        return CommissioningScript.objects.create(
            name=name, content=Bin(content))

    def make_download_progress(self, nodegroup=None, filename=None,
                               size=NO_VALUE, bytes_downloaded=NO_VALUE,
                               error=None):
        """Create a `DownloadProgress` in some poorly-defined state.

        If you have specific wishes about the object's state, you'll want to
        use one of the specialized `make_download_progress_*` methods instead.

        Pass a `size` of `None` to indicate that total file size is not yet
        known.  The default picks either a random number, or None.
        """
        if nodegroup is None:
            nodegroup = self.make_node_group()
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

    def make_download_progress_initial(self, nodegroup=None, filename=None,
                                       size=NO_VALUE):
        """Create a `DownloadProgress` as reported before a download."""
        return self.make_download_progress(
            nodegroup=nodegroup, filename=filename, size=size,
            bytes_downloaded=None, error='')

    def make_download_progress_success(self, nodegroup=None, filename=None,
                                       size=None):
        """Create a `DownloadProgress` indicating success."""
        if size is None:
            size = random.randint(0, 1000000000)
        return self.make_download_progress(
            nodegroup=nodegroup, filename=filename, size=size,
            bytes_downloaded=size, error='')

    def make_download_progress_incomplete(self, nodegroup=None, filename=None,
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
        return self.make_download_progress(
            nodegroup=nodegroup, filename=filename, size=size,
            bytes_downloaded=bytes_downloaded, error='')

    def make_download_progress_failure(self, nodegroup=None, filename=None,
                                       size=NO_VALUE,
                                       bytes_downloaded=NO_VALUE, error=None):
        """Create a `DownloadProgress` indicating failure."""
        if error is None:
            error = self.make_string()
        return self.make_download_progress_incomplete(
            nodegroup=nodegroup, filename=filename, size=size,
            bytes_downloaded=bytes_downloaded, error=error)

    def make_zone(self, name=None, description=None, nodes=None,
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

    def make_vlan_tag(self, allow_none=False, but_not=None):
        """Create a random VLAN tag.

        :param allow_none: Whether `None` ("no VLAN") can be allowed as an
            outcome.  If `True`, `None` will be included in the possible
            results with a deliberately over-represented probability, in order
            to help trip up bugs that might only show up once in about 4094
            calls otherwise.
        :param but_not: A list of tags that should not be returned.  Any zero
            or `None` entries will be ignored.
        """
        if but_not is None:
            but_not = []
        if allow_none and random.randint(0, 1) == 0:
            return None
        else:
            for _ in range(100):
                vlan_tag = random.randint(1, 0xffe)
                if vlan_tag not in but_not:
                    return vlan_tag
            raise maastesting.factory.TooManyRandomRetries(
                "Could not find an available VLAN tag.")

    def make_network(self, name=None, network=None, vlan_tag=NO_VALUE,
                     description=None, sortable_name=False,
                     disjoint_from=None):
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
            network = self.getRandomNetwork(disjoint_from=disjoint_from)
        ip = unicode(network.ip)
        netmask = unicode(network.netmask)
        if description is None:
            description = self.make_string()
        if vlan_tag is NO_VALUE:
            vlan_tag = self.make_vlan_tag()
        network = Network(
            name=name, ip=ip, netmask=netmask, vlan_tag=vlan_tag,
            description=description)
        network.save()
        return network

    def make_networks(self, number, with_vlans=True, **kwargs):
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
                self.make_network(
                    vlan_tag=tag, disjoint_from=networks, **kwargs))
        return networks

    def make_boot_source(self, cluster=None, url=None,
                         keyring_filename=None, keyring_data=None):
        """Create a new `BootSource`."""
        if cluster is None:
            cluster = self.make_node_group()
        if url is None:
            url = "http://%s.com" % self.make_name('source-url')
        # Only set _one_ of keyring_filename and keyring_data.
        if keyring_filename is None and keyring_data is None:
            keyring_filename = self.make_name("keyring")
        boot_source = BootSource(
            cluster=cluster, url=url,
            keyring_filename=(
                "" if keyring_filename is None else keyring_filename),
            keyring_data=(
                b"" if keyring_data is None else keyring_data),
        )
        boot_source.save()
        return boot_source

    def make_boot_source_selection(self, boot_source=None, release=None,
                                   arches=None, subarches=None, labels=None):
        """Create a `BootSourceSelection`."""
        if boot_source is None:
            boot_source = self.make_boot_source()
        if release is None:
            ubuntu_os = UbuntuOS()
            release = self.pick_release(ubuntu_os)
        if arches is None:
            arch_count = random.randint(1, 10)
            arches = [self.make_name("arch") for i in range(arch_count)]
        if subarches is None:
            subarch_count = random.randint(1, 10)
            subarches = [
                self.make_name("subarch")
                for i in range(subarch_count)
                ]
        if labels is None:
            label_count = random.randint(1, 10)
            labels = [self.make_name("label") for i in range(label_count)]
        boot_source_selection = BootSourceSelection(
            boot_source=boot_source, release=release, arches=arches,
            subarches=subarches, labels=labels)
        boot_source_selection.save()
        return boot_source_selection

    def make_license_key(self, osystem=None, distro_series=None,
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

    def make_event_type(self, name=None, level=None, description=None):
        if name is None:
            name = self.make_name('name', size=20)
        if description is None:
            description = factory.make_name('description')
        if level is None:
            level = random.choice([
                logging.ERROR, logging.WARNING, logging.INFO])
        return EventType.objects.create(
            name=name, description=description, level=level)

    def make_event(self, node=None, type=None):
        if node is None:
            node = self.make_node()
        if type is None:
            type = self.make_event_type()
        return Event.objects.create(node=node, type=type)

    def make_large_file(self, content=None, size=512):
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

    def make_boot_resource(self, rtype=None, name=None, architecture=None,
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

    def make_boot_resource_set(self, resource, version=None, label=None):
        if version is None:
            version = self.make_name('version')
        if label is None:
            label = self.make_name('label')
        return BootResourceSet.objects.create(
            resource=resource, version=version, label=label)

    def make_boot_resource_file(self, resource_set, largefile, filename=None,
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
        largefile = self.make_large_file(content=content, size=size)
        return self.make_boot_resource_file(
            resource_set, largefile, filename=filename, filetype=filetype,
            extra=extra)

    def make_usable_boot_resource(
            self, rtype=None, name=None, architecture=None,
            extra=None, version=None, label=None):
        resource = self.make_boot_resource(
            rtype=rtype, name=name, architecture=architecture, extra=extra)
        resource_set = self.make_boot_resource_set(
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


# Create factory singleton.
factory = Factory()
