# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Interact with the Provisioning API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'get_provisioning_api_proxy',
    ]

from urllib import urlencode
from urlparse import urljoin
import warnings
import xmlrpclib

from django.conf import settings
from django.db.models.signals import (
    post_delete,
    post_save,
    )
from django.dispatch import receiver
from maasserver.models import (
    Config,
    MACAddress,
    Node,
    )


def get_provisioning_api_proxy():
    """Return a proxy to the Provisioning API.

    If ``PSERV_URL`` is not set, we attempt to return a handle to a fake proxy
    implementation. This will not be available in a packaged version of MAAS,
    in which case an error is raised.
    """
    url = settings.PSERV_URL
    if url is None:
        try:
            from maasserver import testing
        except ImportError:
            # This is probably in a package.
            raise RuntimeError("PSERV_URL must be defined.")
        else:
            warnings.warn(
                "PSERV_URL is None; using the fake Provisioning API.",
                RuntimeWarning)
            return testing.get_fake_provisioning_api_proxy()
    else:
        return xmlrpclib.ServerProxy(
            url, allow_none=True, use_datetime=True)


def get_metadata_server_url():
    """Return the URL where nodes can reach the metadata service."""
    return urljoin(Config.objects.get_config('maas_url'), "metadata/")


def compose_metadata(node):
    """Put together metadata information for `node`.

    :param node: The node to provide with metadata.
    :type node: Node
    :return: A dict containing metadata information that will be seeded to
        the node, so that it can access the metadata service.
    """
    # Circular import.
    from metadataserver.models import NodeKey
    token = NodeKey.objects.get_token_for_node(node)
    credentials = urlencode({
        'oauth_consumer_key': token.consumer.key,
        'oauth_token_key': token.key,
        'oauth_token_secret': token.secret,
        })
    return {
        'maas-metadata-url': get_metadata_server_url(),
        'maas-metadata-credentials': credentials,
    }


def name_arch_in_cobbler_style(architecture):
    """Give architecture name as used in cobbler.

    MAAS uses Ubuntu-style architecture names, notably including "amd64"
    which in Cobbler terms is "x86_64."

    :param architecture: An architecture name (e.g. as produced by MAAS).
    :type architecture: basestring
    :return: An architecture name in Cobbler style.
    :rtype: unicode
    """
    conversions = {
        'amd64': 'x86_64',
        'i686': 'i386',
    }
    if isinstance(architecture, bytes):
        architecture = architecture.decode('ascii')
    return conversions.get(architecture, architecture)


def select_profile_for_node(node, papi):
    """Select which profile a node should be configured for."""
    assert node.architecture, "Node's architecture is not known."
    cobbler_arch = name_arch_in_cobbler_style(node.architecture)
    return "%s-%s" % ("precise", cobbler_arch)


@receiver(post_save, sender=Node)
def provision_post_save_Node(sender, instance, created, **kwargs):
    """Create or update nodes in the provisioning server."""
    papi = get_provisioning_api_proxy()
    profile = select_profile_for_node(instance, papi)
    power_type = instance.get_effective_power_type()
    metadata = compose_metadata(instance)
    papi.add_node(instance.system_id, profile, power_type, metadata)


def set_node_mac_addresses(node):
    """Update the Node's MAC addresses in the provisioning server."""
    mac_addresses = [mac.mac_address for mac in node.macaddress_set.all()]
    deltas = {node.system_id: {"mac_addresses": mac_addresses}}
    get_provisioning_api_proxy().modify_nodes(deltas)


@receiver(post_save, sender=MACAddress)
def provision_post_save_MACAddress(sender, instance, created, **kwargs):
    """Create or update MACs in the provisioning server."""
    set_node_mac_addresses(instance.node)


@receiver(post_delete, sender=Node)
def provision_post_delete_Node(sender, instance, **kwargs):
    """Delete nodes in the provisioning server."""
    papi = get_provisioning_api_proxy()
    papi.delete_nodes_by_name([instance.system_id])


@receiver(post_delete, sender=MACAddress)
def provision_post_delete_MACAddress(sender, instance, **kwargs):
    """Delete MACs in the provisioning server."""
    set_node_mac_addresses(instance.node)
