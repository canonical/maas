# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Interact with the Provisioning API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'check_profiles',
    'get_provisioning_api_proxy',
    'get_all_profile_names',
    'present_detailed_user_friendly_fault',
    'ProvisioningProxy',
    ]

from functools import partial
import itertools
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
from django.utils.safestring import mark_safe
from maasserver.components import (
    COMPONENT,
    discard_persistent_error,
    register_persistent_error,
    )
from maasserver.exceptions import ExternalComponentException
from maasserver.models import (
    ARCHITECTURE_CHOICES,
    Config,
    MACAddress,
    Node,
    NODE_STATUS,
    )
from provisioningserver.enum import PSERV_FAULT
import yaml

# Presentation templates for various provisioning faults (will be used
# for long-lasting warnings about failing components).
DETAILED_PRESENTATIONS = {
    PSERV_FAULT.NO_COBBLER: """
        The provisioning server was unable to reach the Cobbler service:
        %(fault_string)s

        Check pserv.log, and restart MAAS if needed.
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
    PSERV_FAULT.COBBLER_DNS_LOOKUP_ERROR: """
        The provisioning server was unable to resolve the Cobbler server's
        DNS address: %(fault_string)s.

        Has Cobbler been properly installed and is it accessible by the
        provisioning server?  Check /var/log/cobbler/ and pserv.log.
        """,
    8002: """
        Unable to reach provisioning server (%(fault_string)s).

        Check pserv.log and your PSERV_URL setting, and restart MAAS if
        needed.
        """,
}

# Shorter presentation templates for various provisioning faults (will
# be used for one-off messages).
SHORT_PRESENTATIONS = {
    PSERV_FAULT.NO_COBBLER: """
        Unable to reach the Cobbler server.
        """,
    PSERV_FAULT.COBBLER_AUTH_FAILED: """
        Failed to authenticate with the Cobbler server.
        """,
    PSERV_FAULT.COBBLER_AUTH_ERROR: """
        Failed to authenticate with the Cobbler server.
        """,
    PSERV_FAULT.NO_SUCH_PROFILE: """
        Missing system profile: %(fault_string)s.
        """,
    PSERV_FAULT.GENERIC_COBBLER_ERROR: """
        Unknown problem encountered with the Cobbler server.
        """,
    PSERV_FAULT.COBBLER_DNS_LOOKUP_ERROR: """
        Unable to resolve the Cobbler server's DNS address:
        %(fault_string)s.
        """,
    8002: """
        Unable to reach provisioning server.
        """,
}


def _present_user_friendly_fault(fault, presentations):
    """Return a more user-friendly exception to represent `fault`.

    :param fault: An exception raised by, or received across, xmlrpc.
    :type fault: :class:`xmlrpclib.Fault`
    :param presentations: A mapping error -> message.
    :type fault: dict
    :return: A more user-friendly exception, if one can be produced.
        Otherwise, this returns None and the original exception should be
        re-raised.  (This is left to the caller in order to minimize
        erosion of the backtrace).
    :rtype: :class:`MAASAPIException`, or None.
    """
    params = {
        'fault_code': fault.faultCode,
        'fault_string': fault.faultString,
    }
    user_friendly_text = presentations.get(fault.faultCode)
    if user_friendly_text is None:
        return None
    else:
        return ExternalComponentException(dedent(
            user_friendly_text.lstrip('\n') % params))


present_user_friendly_fault = partial(
    _present_user_friendly_fault, presentations=SHORT_PRESENTATIONS)
"""Return a concise but user-friendly exception to represent `fault`.

:param fault: An exception raised by, or received across, xmlrpc.
:type fault: :class:`xmlrpclib.Fault`
:return: A more user-friendly exception, if one can be produced.
    Otherwise, this returns None and the original exception should be
    re-raised.  (This is left to the caller in order to minimize
    erosion of the backtrace).
:rtype: :class:`MAASAPIException`, or None.
"""


present_detailed_user_friendly_fault = partial(
    _present_user_friendly_fault, presentations=DETAILED_PRESENTATIONS)
"""Return a detailed and user-friendly exception to represent `fault`.

:param fault: An exception raised by, or received across, xmlrpc.
:type fault: :class:`xmlrpclib.Fault`
:return: A more user-friendly exception, if one can be produced.
    Otherwise, this returns None and the original exception should be
    re-raised.  (This is left to the caller in order to minimize
    erosion of the backtrace).
:rtype: :class:`MAASAPIException`, or None.
"""

# A mapping method_name -> list of components.
# For each method name, indicate the list of components that the method
# uses.  This way, when calling the method is a success, if means that
# the related components are working properly.
METHOD_COMPONENTS = {
    'add_node': [COMPONENT.PSERV, COMPONENT.COBBLER, COMPONENT.IMPORT_ISOS],
    'modify_nodes': [COMPONENT.PSERV, COMPONENT.COBBLER],
    'delete_nodes_by_name': [COMPONENT.PSERV, COMPONENT.COBBLER],
    'get_profiles_by_name': [COMPONENT.PSERV, COMPONENT.COBBLER],
}

# A mapping exception -> component.
# For each exception in this dict, the related component is there to
# tell us which component will be marked as 'failing' when this
# exception is raised.
EXCEPTIONS_COMPONENTS = {
    PSERV_FAULT.NO_COBBLER: COMPONENT.COBBLER,
    PSERV_FAULT.COBBLER_AUTH_FAILED: COMPONENT.COBBLER,
    PSERV_FAULT.COBBLER_AUTH_ERROR: COMPONENT.COBBLER,
    PSERV_FAULT.NO_SUCH_PROFILE: COMPONENT.IMPORT_ISOS,
    PSERV_FAULT.GENERIC_COBBLER_ERROR: COMPONENT.COBBLER,
    PSERV_FAULT.COBBLER_DNS_LOOKUP_ERROR: COMPONENT.COBBLER,
    8002: COMPONENT.PSERV,
}


def register_working_components(method_name):
    """Register that the components related to the provided method
    (if any) are working.
    """
    components = METHOD_COMPONENTS.get(method_name, [])
    for component in components:
        discard_persistent_error(component)


def register_failing_component(exception):
    """Register that the component corresponding to exception (if any)
    is failing.
    """
    component = EXCEPTIONS_COMPONENTS.get(exception.faultCode, None)
    if component is not None:
        detailed_friendly_fault = unicode(
            present_detailed_user_friendly_fault(exception))
        register_persistent_error(component, detailed_friendly_fault)


class ProvisioningCaller:
    """Wrapper for an XMLRPC call.

    - Runs xmlrpc exceptions through `present_user_friendly_fault` for better
    presentation to the user.
    - Registers failing/working components.
    """

    def __init__(self, method_name, method):
        # Keep track of the method name; xmlrpclib does not take lightly
        # to us attempting to look it up as an attribute of the method
        # object.
        self.method_name = method_name
        self.method = method

    def __call__(self, *args):
        try:
            result = self.method(*args)
        except xmlrpclib.Fault as e:
            # Register failing component.
            register_failing_component(e)
            # Raise a more user-friendly error.
            friendly_fault = present_user_friendly_fault(e)
            if friendly_fault is None:
                raise
            else:
                raise friendly_fault
        else:
            # The call was a success, discard persistent errors for
            # components referenced by this method.
            register_working_components(self.method_name)
            return result


class ProvisioningProxy:
    """Proxy for calling the provisioning service.

    This wraps an XMLRPC :class:`ServerProxy`, but translates exceptions
    coming in from, or across, the xmlrpc mechanism into more helpful ones
    for the user.
    """

    def __init__(self, xmlrpc_proxy):
        self.proxy = xmlrpc_proxy

    def __getattr__(self, attribute_name):
        """Return a wrapped version of the requested method."""
        attribute = getattr(self.proxy, attribute_name)
        if callable(attribute):
            # This attribute is callable.  Wrap it in a caller.
            return ProvisioningCaller(attribute_name, attribute)
        else:
            # This is a regular attribute.  Return it as-is.
            return attribute


class ProvisioningTransport(xmlrpclib.Transport):
    """An XML-RPC transport that sets a low socket timeout."""

    @property
    def timeout(self):
        return settings.PSERV_TIMEOUT

    def make_connection(self, host):
        """See `xmlrpclib.Transport.make_connection`.

        This also sets the desired socket timeout.
        """
        connection = xmlrpclib.Transport.make_connection(self, host)
        connection.timeout = self.timeout
        return connection


def get_provisioning_api_proxy():
    """Return a proxy to the Provisioning API.

    If ``PSERV_URL`` is not set, we attempt to return a handle to a fake proxy
    implementation. This will not be available in a packaged version of MAAS,
    in which case an error is raised.
    """
    if settings.USE_REAL_PSERV:
        # Use a real provisioning server.  This requires PSERV_URL to be
        # set.
        xmlrpc_transport = ProvisioningTransport(use_datetime=True)
        xmlrpc_proxy = xmlrpclib.ServerProxy(
            settings.PSERV_URL, transport=xmlrpc_transport, allow_none=True)
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
    maas_url = Config.objects.get_config('maas_url')
    if settings.FORCE_SCRIPT_NAME is None:
        path = "metadata/"
    else:
        path = "%s/metadata/" % settings.FORCE_SCRIPT_NAME
    return urljoin(maas_url, path)


def compose_cloud_init_preseed(token):
    """Compose the preseed value for a node in any state but Commissioning."""
    credentials = urlencode({
        'oauth_consumer_key': token.consumer.key,
        'oauth_token_key': token.key,
        'oauth_token_secret': token.secret,
        })

    # Preseed data to send to cloud-init.  We set this as MAAS_PRESEED in
    # ks_meta, and it gets fed straight into debconf.
    metadata_preseed_items = [
        ('datasources', 'multiselect', 'MAAS'),
        ('maas-metadata-url', 'string', get_metadata_server_url()),
        ('maas-metadata-credentials', 'string', credentials),
        ]

    return '\n'.join(
        "cloud-init   cloud-init/%s  %s %s" % (
            item_name,
            item_type,
            item_value,
            )
        for item_name, item_type, item_value in metadata_preseed_items)


def compose_commissioning_preseed(token):
    """Compose the preseed value for a Commissioning node."""
    return "#cloud-config\n%s" % yaml.dump({
        'datasource': {
            'MAAS': {
                'metadata_url': get_metadata_server_url(),
                'consumer_key': token.consumer.key,
                'token_key': token.key,
                'token_secret': token.secret,
            }
        }
    })


def compose_preseed(node):
    """Put together preseed data for `node`.

    This produces preseed data in different formats depending on the node's
    state: if it's Commissioning, it boots into commissioning mode with its
    own profile, its own user_data, and also its own preseed format.  It's
    basically a network boot.
    Otherwise, it will get a different format that feeds directly into the
    installer.

    :param node: The node to compose preseed data for.
    :type node: Node
    :return: Preseed data containing the information the node needs in order
        to access the metadata service: its URL and auth token.
    """
    # Circular import.
    from metadataserver.models import NodeKey
    token = NodeKey.objects.get_token_for_node(node)
    if node.status == NODE_STATUS.COMMISSIONING:
        return compose_commissioning_preseed(token)
    else:
        return compose_cloud_init_preseed(token)


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


def check_profiles():
    """Check that Cobbler has profiles defined for all the profiles used by
    MAAS.  If a profile is missing, display a persistent error with an invite
    to run the maas-import-isos script.
    """
    all_profiles = get_all_profile_names()
    papi = get_provisioning_api_proxy()
    existing_profiles = set(papi.get_profiles_by_name(all_profiles))
    missing_profiles = set(all_profiles) - existing_profiles
    if len(missing_profiles) != 0:
        # Some profiles are missing: display a persistent component
        # error.
        register_persistent_error(
            COMPONENT.IMPORT_ISOS,
            mark_safe(
                """
                Some of the required system profiles are missing.
                Run the maas-import-isos script to import Ubuntu isos and
                create the related profiles:
                <pre>sudo maas-import-isos</pre>
                """))


def get_all_profile_names():
    """Return all the names of the profiles used by MAAS."""
    architectures = {arch[0] for arch in ARCHITECTURE_CHOICES}
    commissioning = {True, False}
    product = itertools.product(architectures, commissioning)
    profiles = [
        get_profile_name(architecture, commissioning)
        for architecture, commissioning in product]
    return profiles


def get_profile_name(architecture, commissioning=False):
    """Return the profile name for a given architecture and whether the node
    is commissioning or not."""
    cobbler_arch = name_arch_in_cobbler_style(architecture)
    profile = "maas-%s-%s" % ("precise", cobbler_arch)
    if commissioning:
        profile += "-commissioning"
    return profile


def select_profile_for_node(node):
    """Select which profile a node should be configured for."""
    assert node.architecture, "Node's architecture is not known."
    commissioning = node.status == NODE_STATUS.COMMISSIONING
    return get_profile_name(node.architecture, commissioning)


@receiver(post_save, sender=Node)
def provision_post_save_Node(sender, instance, created, **kwargs):
    """Create or update nodes in the provisioning server."""
    papi = get_provisioning_api_proxy()
    profile = select_profile_for_node(instance)
    power_type = instance.get_effective_power_type()
    preseed_data = compose_preseed(instance)
    papi.add_node(
        instance.system_id, instance.hostname,
        profile, power_type, preseed_data)

    # When the node is allocated this must not modify the netboot_enabled
    # parameter. The node, once it has booted and installed itself, asks the
    # provisioning server to disable netbooting. If this were to enable
    # netbooting again, the node would reinstall itself the next time it
    # booted. However, netbooting must be enabled at the point the node is
    # allocated so that the first install goes ahead, hence why it is set for
    # all other statuses... with one exception; retired nodes are never
    # netbooted.
    if instance.status != NODE_STATUS.ALLOCATED:
        netboot_enabled = instance.status not in (
            NODE_STATUS.DECLARED, NODE_STATUS.RETIRED)
        delta = {"netboot_enabled": netboot_enabled}
        papi.modify_nodes({instance.system_id: delta})


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
