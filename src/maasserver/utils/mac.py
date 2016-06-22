# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""MAC-related utilities."""

__all__ = [
    'get_vendor_for_mac',
    ]

from netaddr import (
    EUI,
    NotRegisteredError,
)


def get_vendor_for_mac(mac):
    """Return vendor for MAC."""
    data = EUI(mac)
    try:
        return data.oui.registration().org
    except (NotRegisteredError, UnicodeDecodeError):
        # UnicodeDecodeError can be raised if the name of the vendor cannot
        # be decoded from ascii. This is something broken in the netaddr
        # library, we are just catching the error here not to break the UI.
        return 'Unknown Vendor'
