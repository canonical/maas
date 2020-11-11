# Copyright 2014-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAC-related utilities."""


import re

from netaddr import EUI, NotRegisteredError


def get_vendor_for_mac(mac):
    """Return vendor for MAC."""
    data = EUI(mac)
    try:
        return data.oui.registration().org
    except (IndexError, NotRegisteredError, UnicodeDecodeError):
        # Bug#1655049: IndexError is raised for some unicode strings.  See also
        # Bug#1628761.
        # UnicodeDecodeError can be raised if the name of the vendor cannot
        # be decoded from ascii. This is something broken in the netaddr
        # library, we are just catching the error here not to break the UI.
        return "Unknown Vendor"


def is_mac(mac):
    """Return whether or not the string is a MAC address."""
    m = re.search(r"^([0-9a-f]{2}[-:]){5}[0-9a-f]{2}$", str(mac), re.I)
    return m is not None
