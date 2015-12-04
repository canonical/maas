# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
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
    except NotRegisteredError:
        return 'Unknown Vendor'
