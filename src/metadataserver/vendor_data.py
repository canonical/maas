# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""vendor-data for cloud-init's use."""

__all__ = [
    'get_vendor_data',
    ]

from itertools import chain

from maasserver import ntp
from maasserver.models import Config
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
