# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DHCP management module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'is_dhcp_management_enabled',
    ]

from maasserver.models import Config


def is_dhcp_management_enabled():
    """Is MAAS configured to manage DHCP?

    This status is controlled by the `manage_dhcp` configuration item.
    """
    return Config.objects.get_config('manage_dhcp')
