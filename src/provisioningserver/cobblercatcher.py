# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helping hands for dealing with Cobbler exceptions."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'convert_cobbler_exception',
    'ProvisioningError',
    ]

import re
from xmlrpclib import Fault

from provisioningserver.enum import PSERV_FAULT


class ProvisioningError(Fault):
    """Fault, as passed from provisioning server to maasserver.

    This acts as a marker class within the provisioning server.  As far as
    maasserver is concerned, when it sees an exception of this kind, it will
    just be a Fault with a more telling faultCode.

    The faultCode is one of :class:`PSERV_FAULT`.
    """


def extract_text(fault_string):
    """Get the actual error message out of a Cobbler fault string.

    This removes exception type information that may have been added on
    the Cobbler side.

    :param fault_string: A `Fault.faultString` as found on an exception
        raised while working with Cobbler.
    :type fault_string: basestring
    :return: Extracted error message.
    :rtype: basestring
    """
    match = re.match(
        "<class 'cobbler\.cexceptions\.CX'>:'(.*)'", fault_string)
    if match is None:
        return fault_string
    else:
        return match.groups(0)[0]


def divine_fault_code(err_str):
    """Parse error string to figure out what kind of error it is.

    :param err_str: An error string, as extracted from a `Fault` by
        `extract_text`.
    :type err_str: basestring
    :return: A fault code from :class:`PSERV_FAULT`, for use as a
        `Fault.faultCode`.
    :rtype: int
    """
    prefixes = [
        ("login failed", PSERV_FAULT.COBBLER_AUTH_FAILED),
        ("invalid token:", PSERV_FAULT.COBBLER_AUTH_ERROR),
        ("invalid profile name", PSERV_FAULT.NO_SUCH_PROFILE),
        ("", PSERV_FAULT.GENERIC_COBBLER_ERROR),
    ]
    for prefix, code in prefixes:
        if err_str.startswith(prefix):
            return code
    assert False, "No prefix matched fault string '%s'." % err_str


def convert_cobbler_exception(fault):
    """Convert a :class:`Fault` from Cobbler to a :class:`ProvisioningError`.

    :param fault: The original exception, as raised by code that tried to
        talk to Cobbler.
    :type fault: Fault
    :return: A more descriptive exception, for consumption by maasserver.
    :rtype: :class:`ProvisioningError`
    """
    assert isinstance(fault, Fault)

    if isinstance(fault, ProvisioningError):
        raise AssertionError(
            "Fault %r went through double conversion." % fault)

    err_str = extract_text(fault.faultString)
    if fault.faultCode != 1:
        fault_code = PSERV_FAULT.NO_COBBLER
    else:
        fault_code = divine_fault_code(err_str)

    return ProvisioningError(faultCode=fault_code, faultString=err_str)
