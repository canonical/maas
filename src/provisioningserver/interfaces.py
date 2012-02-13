# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Provisioning API interfaces."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "IProvisioningAPI",
    "IProvisioningAPI_XMLRPC",
    ]

from inspect import getmembers
from types import MethodType

from zope.interface import Interface
from zope.interface.interface import InterfaceClass


class IProvisioningAPI_Template:
    """A template for building interfaces for the Provisioning API.

    This class is a placeholder for defining attributes and functions that we
    can enumerate when building interfaces.

    The primary use-case is that `IProvisioningAPI_XMLRPC` is related to
    `IProvisioningAPI` by a simple transformation: every method in the latter
    must appear identically in the former, but with `xmlrpc_` prefixed to the
    name.

    Zope's interfaces throw away the original functions, so defining a
    mechanically derived interface in code is not possible (as far as I know).
    The approach taken here allows for mechanically derived interfaces to be
    defined without duplication.
    """

    def add_distro(name, initrd, kernel):
        """Add a distro with the given `name`, `initrd`, and `kernel`.

        :return: The name of the new distro.
        """

    def add_profile(name, distro):
        """Add a profile with the given `name`, and `distro`.

        :return: The name of the new profile.
        """

    def add_node(name, profile):
        """Add a node with the given `name`, and `profile`.

        :return: The name of the new node.
        """

    def modify_distros(deltas):
        """Apply deltas to existing distros.

        :param deltas: A dict, with each key identifying an existing distro by
            name, and each value being a dict of modifications to apply to it.
        """

    def modify_profiles(deltas):
        """Apply deltas to existing profiles.

        :param deltas: A dict, with each key identifying an existing profile
            by name, and each value being a dict of modifications to apply to
            it.
        """

    def modify_nodes(deltas):
        """Apply deltas to existing nodes.

        :param deltas: A dict, with each key identifying an existing node by
            name, and each value being a dict of modifications to apply to it.
        """

    def get_distros_by_name(names):
        """List distros with the given `names`.

        :return: A dict of distro-names -> distro-values.
        """

    def get_profiles_by_name(names):
        """List profiles with the given `names`.

        :return: A dict of profile-names -> profile-values.
        """

    def get_nodes_by_name(names):
        """List nodes with the given `names`.

        :return: A dict of node-names -> node-values.
        """

    def delete_distros_by_name(names):
        """Delete distros with the given `names`."""

    def delete_profiles_by_name(names):
        """Delete profiles with the given `names`."""

    def delete_nodes_by_name(names):
        """Delete nodes with the given `names`."""

    def get_distros():
        """List all distros.

        :return: A dict of distro-names -> distro-values.
        """

    def get_profiles():
        """List all profiles.

        :return: A dict of profile-names -> profile-values.
        """

    def get_nodes():
        """List all nodes.

        :return: A dict of node-names -> node-values.
        """


# All public methods defined in IProvisioningAPI_Template.
PAPI_FUNCTIONS = {
    name: value.im_func
    for name, value in getmembers(IProvisioningAPI_Template)
    if not name.startswith("_") and isinstance(value, MethodType)
    }

# Construct an interface containing IProvisioningAPI_Template's functions.
IProvisioningAPI = InterfaceClass(
    b"IProvisioningAPI", (Interface,), PAPI_FUNCTIONS)


# The XMLRPC interface must define methods with an xmlrpc_ prefix. Twisted's
# XMLRPC code relies upon this as an indication that the method is available
# over-the-wire.
PAPI_XMLRPC_FUNCTIONS = {
    "xmlrpc_%s" % name: value
    for name, value in PAPI_FUNCTIONS.iteritems()
    }

# Construct an interface containing IProvisioningAPI_Template's functions but
# with each given an xmlrpc_ prefix to their name.
IProvisioningAPI_XMLRPC = InterfaceClass(
    b"IProvisioningAPI_XMLRPC", (Interface,), PAPI_XMLRPC_FUNCTIONS)
