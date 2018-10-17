# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""vendor-data for cloud-init's use."""

__all__ = [
    'get_vendor_data',
    ]

from base64 import b64encode
from crypt import crypt
from itertools import chain
from os import urandom

from maasserver import ntp
from maasserver.models import (
    Config,
    NodeMetadata,
)
from maasserver.server_address import get_maas_facing_server_host
from netaddr import IPAddress
from provisioningserver.ntp.config import normalise_address
from provisioningserver.utils.text import make_gecos_field
from provisioningserver.utils.version import get_maas_version_track_channel


def get_vendor_data(node):
    return dict(chain(
        generate_system_info(node),
        generate_ntp_configuration(node),
        generate_rack_controller_configuration(node),
        generate_kvm_pod_configuration(node),
    ))


def generate_system_info(node):
    """Generate cloud-init system information for the given node."""
    if node.owner is not None and node.default_user:
        username = node.default_user
        fullname = node.owner.get_full_name()
        gecos = make_gecos_field(fullname)
        yield "system_info", {
            'default_user': {
                'name': username,
                'gecos': gecos,
            },
        }


def generate_ntp_configuration(node):
    """Generate cloud-init configuration for NTP servers.

    cloud-init supports::

      ntp:
        pools:
          - 0.mypool.pool.ntp.org
          - 1.myotherpool.pool.ntp.org
        servers:
          - 102.10.10.10
          - ntp.ubuntu.com

    MAAS assumes that IP addresses are "servers" and hostnames/FQDNs "pools".
    """
    ntp_servers = ntp.get_servers_for(node)
    if len(ntp_servers) >= 1:
        # Separate out IP addresses from the rest.
        addrs, other = set(), set()
        for ntp_server in map(normalise_address, ntp_servers):
            bucket = addrs if isinstance(ntp_server, IPAddress) else other
            bucket.add(ntp_server)
        servers = [addr.format() for addr in sorted(addrs)]
        pools = sorted(other)  # Hostnames and FQDNs only.
        yield "ntp", {"servers": servers, "pools": pools}


def generate_rack_controller_configuration(node):
    """Generate cloud-init configuration to install the rack controller."""

    # FIXME: For now, we are using a tag ('switch') to deploy the rack
    # controller but once the switch model is complete we need to switch.
    # In the meatime we will leave it as is for testing purposes.
    node_tags = node.tag_names()
    # To determine this is a machine that's accessing the metadata after
    # initial deployment, we use 'node.netboot'. This flag is set to off after
    # curtin has installed the operating system and before the machine reboots
    # for the first time.
    if (node.netboot is False and
            node.osystem in ['ubuntu', 'ubuntu-core'] and
            ('switch' in node_tags or 'wedge40' in node_tags or
             'wedge100' in node_tags or node.install_rackd is True)):
        maas_url = "http://%s:5240/MAAS" % get_maas_facing_server_host(
            node.get_boot_rack_controller())
        secret = Config.objects.get_config("rpc_shared_secret")
        source = get_maas_version_track_channel()
        yield "runcmd", [
            "snap install maas --devmode --channel=%s" % source,
            "/snap/bin/maas init --mode rack --maas-url %s --secret %s" % (
                maas_url, secret)
        ]


def generate_kvm_pod_configuration(node):
    """Generate cloud-init configuration to install the node as a KVM pod."""
    if node.netboot is False and node.install_kvm is True:
        architecture = None
        if node.architecture is not None:
            architecture = node.architecture
            if '/' in architecture:
                architecture = architecture.split('/')[0]
        runcmd = [
            # Restrict the $PATH so that rbash can be used to limit what the
            # virsh user can do if they manage to get a shell.
            ['mkdir', '-p', '/home/virsh/bin'],
            ['ln', '-s', '/usr/bin/virsh', '/home/virsh/bin/virsh'],
            ['sh', '-c', 'echo "PATH=/home/virsh/bin" >> /home/virsh/.bashrc'],
            # Use a ForceCommand to make sure the only thing the virsh user
            # can do with SSH is communicate with libvirt.
            ['sh', '-c',
                'printf "Match user virsh\\n'
                '    X11Forwarding no\\n'
                '    AllowTcpForwarding no\\n'
                '    PermitTTY no\\n'
                '    ForceCommand nc -q 0 -U /var/run/libvirt/libvirt-sock\\n"'
                '  >> /etc/ssh/sshd_config'],
            # Make sure the 'virsh' user is allowed to access libvirt.
            ['/usr/sbin/usermod', '--append', '--groups',
                'libvirt,libvirt-qemu', 'virsh'],
            # SSH needs to be restarted in order for the above changes to
            # take effect.
            ['systemctl', 'restart', 'sshd'],
            # Ensure services are ready before cloud-init finishes.
            ['/bin/sleep', '10'],
        ]
        if architecture == 'ppc64el':
            # XXX mpontillo 2018-10-12 - we should investigate if it might be
            # better to add a tag to the node that includes a kernel parameter
            # such as nosmt=force. (The only problem being that we should
            # probably also remove it after the machine is released.)
            runcmd.append([
                'sh', '-c', 'printf "'
                '#!/bin/sh\\n'
                'ppc64_cpu --smt=off\\n'
                'exit 0\\n'
                '"  >> /etc/rc.local'
            ])
            runcmd.append(['chmod', '+x', '/etc/rc.local'])
            runcmd.append(['/etc/rc.local'])
        yield "runcmd", runcmd
        # Generate a 32-character password by encoding 24 bytes as base64.
        virsh_password = b64encode(
            urandom(24), altchars=b'.!').decode('ascii')
        # Pass crypted (salted/hashed) version of the password to cloud-init.
        encrypted_password = crypt(virsh_password)
        # Store a cleartext version of the password so we can add a pod later.
        NodeMetadata.objects.update_or_create(
            node=node, key="virsh_password",
            defaults=dict(value=virsh_password))
        # Make sure SSH password authentication is enabled.
        yield "ssh_pwauth", True
        # Create a custom 'virsh' user (in addition to the default user)
        # with the encrypted password, and a locked-down shell.
        yield "users", [
            'default',
            {
                'name': 'virsh',
                'lock_passwd': False,
                'passwd': encrypted_password,
                'shell': '/bin/rbash',
            }
        ]
        packages = ["qemu-kvm", "libvirt-bin"]
        if architecture == 'amd64':
            packages.append('qemu-efi')
        yield "packages", packages
