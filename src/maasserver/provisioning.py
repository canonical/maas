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
    'present_detailed_user_friendly_fault',
    'ProvisioningProxy',
    ]

from functools import partial
from textwrap import dedent
from urllib import urlencode
import xmlrpclib

from maasserver.components import (
    COMPONENT,
    discard_persistent_error,
    register_persistent_error,
    )
from maasserver.enum import NODE_STATUS
from maasserver.exceptions import ExternalComponentException
from maasserver.utils import absolute_reverse
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

        This is a Cobbler error and should no longer occur now that Cobbler
        has been removed as a component of MAAS.
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
    'add_node': [
        COMPONENT.PSERV,
        COMPONENT.COBBLER,
        COMPONENT.IMPORT_PXE_FILES,
        ],
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
    PSERV_FAULT.NO_SUCH_PROFILE: COMPONENT.IMPORT_PXE_FILES,
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
        ('maas-metadata-url', 'string', absolute_reverse('metadata')),
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
    return "#cloud-config\n%s" % yaml.safe_dump({
        'datasource': {
            'MAAS': {
                'metadata_url': absolute_reverse('metadata'),
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
