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
    'ProvisioningProxy',
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
from maasserver.models import (
    Config,
    MACAddress,
    Node,
    )
from provisioningserver.enum import PSERV_FAULT

# Presentation templates for various provisioning faults.
PRESENTATIONS = {
    PSERV_FAULT.NO_COBBLER: """
        The provisioning server was unable to reach the Cobbler service:
        %(fault_string)s

        Check pserv.log, and restart MaaS if needed.
        """,
    PSERV_FAULT.COBBLER_AUTH_FAILED: """
        The provisioning server failed to authenticate with the Cobbler
        service: %(fault_string)s.

        This may mean that Cobbler's authentication configuration has
        changed.  Check /var/log/cobbler/ and pserv.log.
        """,
    PSERV_FAULT.COBBLER_AUTH_ERROR: """
        The Cobbler server no longer accepts the provisioning server's
        authentication token.  This should not happen; it may indicate
        that the server is under unsustainable load.
        """,
    PSERV_FAULT.NO_SUCH_PROFILE: """
        System profile does not exist: %(fault_string)s.

        Has the maas-import-isos script been run?  This will run
        automatically from time to time, but if it is failing, an
        administrator may need to run it manually.
        """,
    PSERV_FAULT.GENERIC_COBBLER_ERROR: """
        The provisioning service encountered a problem with the Cobbler
        server, fault code %(fault_code)s: %(fault_string)s

        If the error message is not clear, you may need to check the
        Cobbler logs in /var/log/cobbler/ or pserv.log.
        """,
    8002: """
        Unable to reach provisioning server (%(fault_string)s).

        Check pserv.log and your PSERV_URL setting, and restart MaaS if
        needed.
        """,
}


def present_user_friendly_fault(fault):
    """Return a more user-friendly exception to represent `fault`.

    :param fault: An exception raised by, or received across, xmlrpc.
    :type fault: :class:`xmlrpclib.Fault`
    :return: A more user-friendly exception, if one can be produced.
        Otherwise, this returns None and the original exception should be
        re-raised.  (This is left to the caller in order to minimize
        erosion of the backtrace).
    :rtype: :class:`Exception`, or None.
    """
    params = {
        'fault_code': fault.faultCode,
        'fault_string': fault.faultString,
    }
    user_friendly_text = PRESENTATIONS.get(fault.faultCode)
    if user_friendly_text is None:
        return None
    else:
        user_friendly_text = dedent(user_friendly_text.lstrip('\n') % params)
        return xmlrpclib.Fault(fault.faultCode, user_friendly_text)


class ProvisioningCaller:
    """Wrapper for an XMLRPC call.

    Runs xmlrpc exceptions through `present_user_friendly_fault` for better
    presentation to the user.
    """

    def __init__(self, method):
        self.method = method

    def __call__(self, *args, **kwargs):
        try:
            return self.method(*args, **kwargs)
        except xmlrpclib.Fault as e:
            friendly_fault = present_user_friendly_fault(e)
            if friendly_fault is None:
                raise
            else:
                raise friendly_fault


class ProvisioningProxy:
    """Proxy for calling the provisioning service.

    This wraps an XMLRPC :class:`ServerProxy`, but translates exceptions
    coming in from, or across, the xmlrpc mechanism into more helpful ones
    for the user.
    """

    def __init__(self, xmlrpc_proxy):
        self.proxy = xmlrpc_proxy

    def patch(self, method, replacement):
        setattr(self.proxy, method, replacement)

    def __getattr__(self, attribute_name):
        """Return a wrapped version of the requested method."""
        attribute = getattr(self.proxy, attribute_name)
        if getattr(attribute, '__call__', None) is None:
            # This is a regular attribute.  Return it as-is.
            return attribute
        else:
            # This attribute is callable.  Wrap it in a caller.
            return ProvisioningCaller(attribute)


def get_provisioning_api_proxy():
    """Return a proxy to the Provisioning API.

    If ``PSERV_URL`` is not set, we attempt to return a handle to a fake proxy
    implementation. This will not be available in a packaged version of MAAS,
    in which case an error is raised.
    """
    if settings.USE_REAL_PSERV:
        # Use a real provisioning server.  This requires PSERV_URL to be
        # set.
        xmlrpc_proxy = xmlrpclib.ServerProxy(
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
        xmlrpc_proxy = get_fake_provisioning_api_proxy()

    return ProvisioningProxy(xmlrpc_proxy)


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
