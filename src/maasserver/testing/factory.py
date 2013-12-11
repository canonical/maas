# Copyright 2013 Canonical Ltd.  This software is licensed under the
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
    ]

from io import BytesIO
import random
import time

from django.contrib.auth.models import User
from maasserver.enum import (
    ARCHITECTURE,
    NODE_STATUS,
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
    )
from maasserver.fields import MAC
from maasserver.models import (
    BootImage,
    DHCPLease,
    DownloadProgress,
    FileStorage,
    MACAddress,
    Node,
    NodeGroup,
    NodeGroupInterface,
    SSHKey,
    Tag,
    Zone,
    )
from maasserver.models.node import NODE_TRANSITIONS
from maasserver.testing import (
    get_data,
    reload_object,
    )
from maasserver.utils import map_enum
import maastesting.factory
from maastesting.factory import NO_VALUE
from metadataserver.fields import Bin
from metadataserver.models import (
    CommissioningScript,
    NodeCommissionResult,
    )
from netaddr import IPAddress

# We have a limited number of public keys:
# src/maasserver/tests/data/test_rsa{0, 1, 2, 3, 4}.pub
MAX_PUBLIC_KEYS = 5


ALL_NODE_STATES = map_enum(NODE_STATUS).values()


class Factory(maastesting.factory.Factory):

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
            content = self.getRandomString().encode('ascii')
        if name is None:
            name = self.make_name('file')
        assert isinstance(content, bytes)
        upload = BytesIO(content)
        upload.name = name
        return upload

    def getRandomEnum(self, enum, but_not=None):
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

    def getRandomChoice(self, choices, but_not=None):
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

    def _save_node_unchecked(self, node):
        """Save a :class:`Node`, but circumvent status transition checks."""
        valid_initial_states = NODE_TRANSITIONS[None]
        NODE_TRANSITIONS[None] = ALL_NODE_STATES
        try:
            node.save()
        finally:
            NODE_TRANSITIONS[None] = valid_initial_states

    def make_node(self, mac=False, hostname=None, status=None,
                  architecture=ARCHITECTURE.i386, updated=None,
                  created=None, nodegroup=None, routers=None, zone=None,
                  **kwargs):
        # hostname=None is a valid value, hence the set_hostname trick.
        if hostname is None:
            hostname = self.getRandomString(20)
        if status is None:
            status = NODE_STATUS.DEFAULT_STATUS
        if nodegroup is None:
            nodegroup = self.make_node_group()
        if routers is None:
            routers = [self.make_MAC()]
        if zone is None:
            zone = self.make_zone()
        node = Node(
            hostname=hostname, status=status, architecture=architecture,
            nodegroup=nodegroup, routers=routers, zone=zone, **kwargs)
        self._save_node_unchecked(node)
        if mac:
            self.make_mac_address(node=node)

        # Update the 'updated'/'created' fields with a call to 'update'
        # preventing a call to save() from overriding the values.
        if updated is not None:
            Node.objects.filter(id=node.id).update(updated=updated)
        if created is not None:
            Node.objects.filter(id=node.id).update(created=created)
        return reload_object(node)

    def get_interface_fields(self, ip=None, router_ip=None, network=None,
                             subnet_mask=None, broadcast_ip=None,
                             ip_range_low=None, ip_range_high=None,
                             interface=None, management=None, **kwargs):
        if network is None:
            network = factory.getRandomNetwork()
        if subnet_mask is None:
            subnet_mask = unicode(network.netmask)
        if broadcast_ip is None:
            broadcast_ip = unicode(network.broadcast)
        if ip_range_low is None:
            ip_range_low = unicode(IPAddress(network.first))
        if ip_range_high is None:
            ip_range_high = unicode(IPAddress(network.last))
        if router_ip is None:
            router_ip = factory.getRandomIPInNetwork(network)
        if ip is None:
            ip = factory.getRandomIPInNetwork(network)
        if management is None:
            management = factory.getRandomEnum(NODEGROUPINTERFACE_MANAGEMENT)
        if interface is None:
            interface = self.make_name('interface')
        return dict(
            subnet_mask=subnet_mask,
            broadcast_ip=broadcast_ip,
            ip_range_low=ip_range_low,
            ip_range_high=ip_range_high,
            router_ip=router_ip,
            ip=ip,
            management=management,
            interface=interface)

    def make_node_group(self, name=None, uuid=None, ip=None,
                        router_ip=None, network=None, subnet_mask=None,
                        broadcast_ip=None, ip_range_low=None,
                        ip_range_high=None, interface=None, management=None,
                        status=None, maas_url='', **kwargs):
        """Create a :class:`NodeGroup`.

        If network (an instance of IPNetwork) is provided, use it to populate
        subnet_mask, broadcast_ip, ip_range_low, ip_range_high, router_ip and
        worker_ip. This is a convenience to setup a coherent network all in
        one go.
        """
        if status is None:
            status = factory.getRandomEnum(NODEGROUP_STATUS)
        if management is None:
            management = NODEGROUPINTERFACE_MANAGEMENT.DHCP
        if name is None:
            name = self.make_name('nodegroup')
        if uuid is None:
            uuid = factory.getRandomUUID()
        interface_settings = self.get_interface_fields(
            ip=ip, router_ip=router_ip, network=network,
            subnet_mask=subnet_mask, broadcast_ip=broadcast_ip,
            ip_range_low=ip_range_low, ip_range_high=ip_range_high,
            interface=interface, management=management)
        interface_settings.update(kwargs)
        ng = NodeGroup.objects.new(
            name=name, uuid=uuid, **interface_settings)
        ng.status = status
        ng.maas_url = maas_url
        ng.save()
        return ng

    def make_unrenamable_nodegroup_with_node(self):
        """Create a `NodeGroup` that can't be renamed, and `Node`.

        Node groups can't be renamed while they are in an accepted state, have
        DHCP and DNS management enabled, and have a node that is in allocated
        state.

        :return: tuple: (`NodeGroup`, `Node`).
        """
        name = self.make_name('original-name')
        nodegroup = self.make_node_group(
            name=name, status=NODEGROUP_STATUS.ACCEPTED)
        interface = nodegroup.get_managed_interface()
        interface.management = NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS
        interface.save()
        node = self.make_node(
            nodegroup=nodegroup, status=NODE_STATUS.ALLOCATED)
        return nodegroup, node

    def make_node_group_interface(self, nodegroup, ip=None,
                                  router_ip=None, network=None,
                                  subnet_mask=None, broadcast_ip=None,
                                  ip_range_low=None, ip_range_high=None,
                                  interface=None, management=None, **kwargs):
        interface_settings = self.get_interface_fields(
            ip=ip, router_ip=router_ip, network=network,
            subnet_mask=subnet_mask, broadcast_ip=broadcast_ip,
            ip_range_low=ip_range_low, ip_range_high=ip_range_high,
            interface=interface, management=management)
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
            name = "ncrname-" + self.getRandomString(92)
        if data is None:
            data = b"ncrdata-" + self.getRandomBytes()
        if script_result is None:
            script_result = random.randint(0, 10)
        ncr = NodeCommissionResult(
            node=node, name=name, script_result=script_result, data=Bin(data))
        ncr.save()
        return ncr

    def make_MAC(self):
        """Generate a random MAC address, in the form of a MAC object."""
        return MAC(self.getRandomMACAddress())

    def make_mac_address(self, address=None, node=None):
        """Create a MACAddress model object."""
        if node is None:
            node = self.make_node()
        if address is None:
            address = self.getRandomMACAddress()
        mac = MACAddress(mac_address=MAC(address), node=node)
        mac.save()
        return mac

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

    def make_user(self, username=None, password=None, email=None):
        if username is None:
            username = self.getRandomUsername()
        if email is None:
            email = '%s@example.com' % self.getRandomString(10)
        if password is None:
            password = 'test'
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
        self._save_node_unchecked(tag)
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

    def make_admin(self, username=None, password=None, email=None):
        admin = self.make_user(
            username=username, password=password, email=email)
        admin.is_superuser = True
        admin.save()
        return admin

    def make_file_storage(self, filename=None, content=None, owner=None):
        fake_file = self.make_file_upload(filename, content)
        return FileStorage.objects.save_file(fake_file.name, fake_file, owner)

    def make_oauth_header(self, **kwargs):
        """Fake an OAuth authorization header.

        This will use arbitrary values.  Pass as keyword arguments any
        header items that you wish to override.
        """
        items = {
            'realm': self.getRandomString(),
            'oauth_nonce': random.randint(0, 99999),
            'oauth_timestamp': time.time(),
            'oauth_consumer_key': self.getRandomString(18),
            'oauth_signature_method': 'PLAINTEXT',
            'oauth_version': '1.0',
            'oauth_token': self.getRandomString(18),
            'oauth_signature': "%%26%s" % self.getRandomString(32),
        }
        items.update(kwargs)
        return "OAuth " + ", ".join([
            '%s="%s"' % (key, value) for key, value in items.items()])

    def make_boot_image(self, architecture=None, subarchitecture=None,
                        release=None, purpose=None, nodegroup=None):
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
        return BootImage.objects.create(
            nodegroup=nodegroup,
            architecture=architecture,
            subarchitecture=subarchitecture,
            release=release,
            purpose=purpose)

    def make_commissioning_script(self, name=None, content=None):
        if name is None:
            name = self.make_name('script')
        if content is None:
            content = b'content:' + self.getRandomString().encode('ascii')
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
            if self.getRandomBoolean():
                size = random.randint(0, 1000000000)
            else:
                size = None
        if bytes_downloaded is NO_VALUE:
            if self.getRandomBoolean():
                if size is None:
                    max_size = 1000000000
                else:
                    max_size = size
                bytes_downloaded = random.randint(0, max_size)
            else:
                bytes_downloaded = None
        if error is None:
            if self.getRandomBoolean():
                error = self.getRandomString()
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
            if self.getRandomBoolean():
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
            error = self.getRandomString()
        return self.make_download_progress_incomplete(
            nodegroup=nodegroup, filename=filename, size=size,
            bytes_downloaded=bytes_downloaded, error=error)

    def make_zone(self, name=None, description=None, nodes=None):
        """Create an availability `Zone`."""
        if name is None:
            name = self.make_name('zone')
        if description is None:
            description = self.getRandomString()
        zone = Zone(name=name, description=description)
        zone.save()
        if nodes is not None:
            zone.node_set.add(*nodes)
        return zone


# Create factory singleton.
factory = Factory()
