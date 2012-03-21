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

from logging import getLogger
from textwrap import dedent
from urllib import urlencode
from urlparse import urljoin
import xmlrpclib

from django.conf import settings
from django.db.models.signals import (
    post_delete,
    post_save,
    )
from django.dispatch import receiver
from maasserver.exceptions import MissingProfileException
from maasserver.models import (
    Config,
    MACAddress,
    Node,
    )
from provisioningserver.enum import PSERV_FAULT


def get_provisioning_api_proxy():
    """Return a proxy to the Provisioning API.

    If ``PSERV_URL`` is not set, we attempt to return a handle to a fake proxy
    implementation. This will not be available in a packaged version of MAAS,
    in which case an error is raised.
    """
    if settings.USE_REAL_PSERV:
        # Use a real provisioning server.  This requires PSERV_URL to be
        # set.
        return xmlrpclib.ServerProxy(
            settings.PSERV_URL, allow_none=True, use_datetime=True)
    else:
        # Create a fake.  The code that provides the testing fake is not
        # available in an installed production system, so import it only
        # when a fake is requested.
        try:
            from maasserver.testing import get_fake_provisioning_api_proxy
        except ImportError:
            getLogger('maasserver').error(
                "Could not import fake provisioning proxy.  "
                "This may mean you're trying to run tests, or have set "
                "USE_REAL_PSERV to False, on an installed MAAS.  "
                "Don't do either.")
            raise
        return get_fake_provisioning_api_proxy()


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
    return "maas-%s-%s" % ("precise", cobbler_arch)


@receiver(post_save, sender=Node)
def provision_post_save_Node(sender, instance, created, **kwargs):
    """Create or update nodes in the provisioning server."""
    papi = get_provisioning_api_proxy()
    profile = select_profile_for_node(instance, papi)
    power_type = instance.get_effective_power_type()
    metadata = compose_metadata(instance)
    try:
        papi.add_node(instance.system_id, profile, power_type, metadata)
    except xmlrpclib.Fault as e:
        if e.faultCode == PSERV_FAULT.NO_SUCH_PROFILE:
            raise MissingProfileException(dedent("""
                System profile %s does not exist.  Has the maas-import-isos
                script been run?  This will run automatically from time to
                time, but if it is failing, an administrator may need to run
                it manually.
                """ % profile).lstrip('\n'))
        else:
            raise


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
